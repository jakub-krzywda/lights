#!/usr/bin/env python3
"""Sterowanie ledbarem RGB przez lokalne API OLA (uDMX), uniwersum DMX 1.

Uruchamiane lokalnie na Raspberry Pi, wymaga zainstalowanego ola-python
(sudo apt install ola-python).
"""

import argparse
import colorsys
import sys
import threading
from array import array

from ola.ClientWrapper import ClientWrapper

DEFAULT_UNIVERSE = 1
DEFAULT_START_CHANNEL = 1
# 3 = prosty tryb R,G,B (ustawiony fizycznie na ledbarze jako '3-ch').
# 24 = tryb per-segment (8 segmentów x R,G,B), wymaga ustawienia na ledbarze jako '24ch'.
DEFAULT_NUM_CHANNELS = 3
SEGMENT_CHANNELS = 3


class DmxController:
    def __init__(self, universe=DEFAULT_UNIVERSE,
                 start_channel=DEFAULT_START_CHANNEL,
                 num_channels=DEFAULT_NUM_CHANNELS):
        self.universe = universe
        self.start_channel = start_channel
        self.num_channels = num_channels
        self.wrapper = ClientWrapper()
        self.client = self.wrapper.Client()
        self._lock = threading.Lock()

    def send_dmx(self, channels: dict[int, int]) -> None:
        """Wysyła {kanał (1-indexed): wartość 0-255} do uniwersum."""
        for channel, value in channels.items():
            if not 1 <= channel <= 512:
                raise ValueError(f"kanał poza zakresem 1-512: {channel}")
            if not 0 <= value <= 255:
                raise ValueError(f"wartość poza zakresem 0-255: {value}")

        data = array('B', [0] * max(channels))
        for channel, value in channels.items():
            data[channel - 1] = value

        def on_sent(status):
            self.wrapper.Stop()

        with self._lock:
            self.client.SendDmx(self.universe, data, on_sent)
            self.wrapper.Run()

    def set_color(self, r: int, g: int, b: int) -> None:
        """Ustawia jeden kolor na wszystkich segmentach fixture (1 segment w trybie 3ch, 8 w trybie 24ch)."""
        segments = max(1, self.num_channels // SEGMENT_CHANNELS)
        channels = {}
        for i in range(segments):
            base = self.start_channel + i * SEGMENT_CHANNELS
            channels[base], channels[base + 1], channels[base + 2] = r, g, b
        self.send_dmx(channels)

    def set_segment_color(self, segment: int, r: int, g: int, b: int) -> None:
        """Ustawia kolor pojedynczego segmentu (1-indexed), wymaga trybu 24ch."""
        max_segment = max(1, self.num_channels // SEGMENT_CHANNELS)
        if not 1 <= segment <= max_segment:
            raise ValueError(f"segment poza zakresem 1-{max_segment}: {segment}")
        base = self.start_channel + (segment - 1) * SEGMENT_CHANNELS
        self.send_dmx({base: r, base + 1: g, base + 2: b})

    def blackout(self) -> None:
        """Zeruje wszystkie kanały fixture."""
        self.send_dmx({
            self.start_channel + i: 0
            for i in range(self.num_channels)
        })


def effect_rainbow(controller: DmxController, stop_event: threading.Event,
                    color=(255, 0, 0), speed: float = 0.1) -> None:
    """Tęczowy chase po segmentach. Wymaga trybu 24ch (koloru nie używa - zachowany dla wspólnego interfejsu wywołania efektów)."""
    segments = max(1, controller.num_channels // SEGMENT_CHANNELS)
    offset = 0.0
    while not stop_event.is_set():
        for i in range(segments):
            hue = ((i / segments) + offset) % 1.0
            r, g, b = (round(c * 255) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0))
            controller.set_segment_color(i + 1, r, g, b)
        offset += 0.02
        stop_event.wait(speed)


def effect_chase(controller: DmxController, stop_event: threading.Event,
                  color=(255, 0, 0), speed: float = 0.15) -> None:
    """Pojedynczy segment w danym kolorze 'ucieka' wzdłuż bara. Wymaga trybu 24ch."""
    segments = max(1, controller.num_channels // SEGMENT_CHANNELS)
    position = 0
    while not stop_event.is_set():
        for i in range(segments):
            r, g, b = color if i == position else (0, 0, 0)
            controller.set_segment_color(i + 1, r, g, b)
        position = (position + 1) % segments
        stop_event.wait(speed)


def effect_pulse(controller: DmxController, stop_event: threading.Event,
                  color=(0, 0, 255), speed: float = 0.02) -> None:
    """Pulsowanie jasności całego bara w danym kolorze. Działa w każdym trybie."""
    brightness, step = 0.0, 0.05
    while not stop_event.is_set():
        r, g, b = (round(c * brightness) for c in color)
        controller.set_color(r, g, b)
        brightness += step
        if brightness >= 1.0 or brightness <= 0.0:
            brightness = max(0.0, min(1.0, brightness))
            step = -step
        stop_event.wait(speed)


EFFECTS = {
    "rainbow": effect_rainbow,
    "chase": effect_chase,
    "pulse": effect_pulse,
}


def parse_channel_assignments(assignments: list[str]) -> dict[int, int]:
    """Parsuje ['1=255', '2=0'] na {1: 255, 2: 0}."""
    channels = {}
    for assignment in assignments:
        channel_str, _, value_str = assignment.partition("=")
        channels[int(channel_str)] = int(value_str)
    return channels


def run_interactive(controller: DmxController) -> None:
    print("Tryb interaktywny. Komendy: 'color R G B', 'segment N R G B', 'raw CH=VAL ...', "
          f"'effect {'|'.join(EFFECTS)} [R G B]', 'stop', 'blackout', 'exit'.")
    effect_thread = None
    stop_event = threading.Event()

    def stop_effect():
        nonlocal effect_thread
        if effect_thread is not None:
            stop_event.set()
            effect_thread.join()
            effect_thread = None

    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("exit", "quit"):
            stop_effect()
            break
        elif cmd == "stop":
            stop_effect()
        elif cmd == "blackout":
            stop_effect()
            controller.blackout()
        elif cmd == "color" and len(parts) == 4:
            stop_effect()
            try:
                r, g, b = (int(x) for x in parts[1:4])
                controller.set_color(r, g, b)
            except ValueError as e:
                print(f"Błąd: {e}")
        elif cmd == "segment" and len(parts) == 5:
            stop_effect()
            try:
                segment, r, g, b = (int(x) for x in parts[1:5])
                controller.set_segment_color(segment, r, g, b)
            except ValueError as e:
                print(f"Błąd: {e}")
        elif cmd == "raw" and len(parts) > 1:
            stop_effect()
            try:
                controller.send_dmx(parse_channel_assignments(parts[1:]))
            except ValueError as e:
                print(f"Błąd: {e}")
        elif cmd == "effect" and len(parts) >= 2 and parts[1] in EFFECTS:
            stop_effect()
            name = parts[1]
            color = tuple(int(x) for x in parts[2:5]) if len(parts) >= 5 else (255, 0, 0)
            stop_event.clear()
            effect_thread = threading.Thread(
                target=EFFECTS[name], args=(controller, stop_event), kwargs={"color": color}, daemon=True)
            effect_thread.start()
        else:
            print("Nieznana komenda.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=int, default=DEFAULT_UNIVERSE)
    parser.add_argument("--start-channel", type=int, default=DEFAULT_START_CHANNEL)
    parser.add_argument("--channels", type=int, default=DEFAULT_NUM_CHANNELS,
                         help="liczba kanałów fixture ustawiona na urządzeniu: 3 lub 24")

    subparsers = parser.add_subparsers(dest="command", required=True)

    color_parser = subparsers.add_parser("color", help="ustaw kolor RGB na całym barze i zakończ")
    color_parser.add_argument("r", type=int)
    color_parser.add_argument("g", type=int)
    color_parser.add_argument("b", type=int)

    segment_parser = subparsers.add_parser("segment", help="ustaw kolor pojedynczego segmentu (tryb 24ch)")
    segment_parser.add_argument("segment", type=int)
    segment_parser.add_argument("r", type=int)
    segment_parser.add_argument("g", type=int)
    segment_parser.add_argument("b", type=int)

    subparsers.add_parser("blackout", help="wyzeruj kanały i zakończ")
    subparsers.add_parser("interactive", help="uruchom tryb interaktywny (CLI)")

    raw_parser = subparsers.add_parser(
        "raw", help="ustaw dowolne kanały wprost, np. 'raw 1=255 2=0 3=0' (do wykrywania układu kanałów fixture)")
    raw_parser.add_argument("assignments", nargs="+", metavar="CH=VAL")

    effect_parser = subparsers.add_parser(
        "effect", help="uruchom efekt (rainbow/chase/pulse) do przerwania Ctrl+C")
    effect_parser.add_argument("name", choices=sorted(EFFECTS))
    effect_parser.add_argument("color", type=int, nargs="*", metavar="R G B",
                                help="kolor dla chase/pulse, domyślnie 255 0 0")

    args = parser.parse_args()

    controller = DmxController(
        universe=args.universe,
        start_channel=args.start_channel,
        num_channels=args.channels,
    )

    try:
        if args.command == "color":
            controller.set_color(args.r, args.g, args.b)
        elif args.command == "segment":
            controller.set_segment_color(args.segment, args.r, args.g, args.b)
        elif args.command == "blackout":
            controller.blackout()
        elif args.command == "interactive":
            run_interactive(controller)
        elif args.command == "raw":
            controller.send_dmx(parse_channel_assignments(args.assignments))
        elif args.command == "effect":
            color = tuple(args.color) if len(args.color) == 3 else (255, 0, 0)
            print(f"Uruchomiono efekt '{args.name}'. Ctrl+C aby zatrzymać.")
            try:
                EFFECTS[args.name](controller, threading.Event(), color=color)
            except KeyboardInterrupt:
                controller.blackout()
    except ValueError as e:
        print(f"Błąd: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
