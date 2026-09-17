#!/usr/bin/env python3
"""Sterowanie ledbarem RGB przez lokalne API OLA (uDMX), uniwersum DMX 1.

Uruchamiane lokalnie na Raspberry Pi, wymaga zainstalowanego python3-ola
(sudo apt install python3-ola).
"""

import argparse
import sys

from ola.ClientWrapper import ClientWrapper

DEFAULT_UNIVERSE = 1
# Adres startowy i liczba kanałów fixture nie zostały jeszcze fizycznie
# potwierdzone na ledbarze (dip-switche / instrukcja) — patrz README.
# Domyślnie zakładamy prosty tryb 3-kanałowy (R, G, B) od kanału 1;
# w razie potrzeby zmień poniższe stałe lub podaj --start-channel / --channels.
DEFAULT_START_CHANNEL = 1
DEFAULT_NUM_CHANNELS = 3


class DmxController:
    def __init__(self, universe=DEFAULT_UNIVERSE,
                 start_channel=DEFAULT_START_CHANNEL,
                 num_channels=DEFAULT_NUM_CHANNELS):
        self.universe = universe
        self.start_channel = start_channel
        self.num_channels = num_channels
        self.wrapper = ClientWrapper()
        self.client = self.wrapper.Client()

    def send_dmx(self, channels: dict[int, int]) -> None:
        """Wysyła {kanał (1-indexed): wartość 0-255} do uniwersum."""
        for channel, value in channels.items():
            if not 1 <= channel <= 512:
                raise ValueError(f"kanał poza zakresem 1-512: {channel}")
            if not 0 <= value <= 255:
                raise ValueError(f"wartość poza zakresem 0-255: {value}")

        data = bytearray(max(channels))
        for channel, value in channels.items():
            data[channel - 1] = value

        def on_sent(status):
            self.wrapper.Stop()

        self.client.SendDmx(self.universe, data, on_sent)
        self.wrapper.Run()

    def set_color(self, r: int, g: int, b: int) -> None:
        """Ustawia kolor RGB na kanałach startowych fixture."""
        self.send_dmx({
            self.start_channel: r,
            self.start_channel + 1: g,
            self.start_channel + 2: b,
        })

    def blackout(self) -> None:
        """Zeruje wszystkie kanały fixture."""
        self.send_dmx({
            self.start_channel + i: 0
            for i in range(self.num_channels)
        })


def run_interactive(controller: DmxController) -> None:
    print("Tryb interaktywny. Komendy: 'color R G B', 'blackout', 'exit'.")
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
            break
        elif cmd == "blackout":
            controller.blackout()
        elif cmd == "color" and len(parts) == 4:
            try:
                r, g, b = (int(x) for x in parts[1:4])
                controller.set_color(r, g, b)
            except ValueError as e:
                print(f"Błąd: {e}")
        else:
            print("Nieznana komenda. Użyj: 'color R G B', 'blackout', 'exit'.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=int, default=DEFAULT_UNIVERSE)
    parser.add_argument("--start-channel", type=int, default=DEFAULT_START_CHANNEL)
    parser.add_argument("--channels", type=int, default=DEFAULT_NUM_CHANNELS,
                         help="liczba kanałów fixture (do blackout)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    color_parser = subparsers.add_parser("color", help="ustaw kolor RGB i zakończ")
    color_parser.add_argument("r", type=int)
    color_parser.add_argument("g", type=int)
    color_parser.add_argument("b", type=int)

    subparsers.add_parser("blackout", help="wyzeruj kanały i zakończ")
    subparsers.add_parser("interactive", help="uruchom tryb interaktywny (CLI)")

    args = parser.parse_args()

    controller = DmxController(
        universe=args.universe,
        start_channel=args.start_channel,
        num_channels=args.channels,
    )

    try:
        if args.command == "color":
            controller.set_color(args.r, args.g, args.b)
        elif args.command == "blackout":
            controller.blackout()
        elif args.command == "interactive":
            run_interactive(controller)
    except ValueError as e:
        print(f"Błąd: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
