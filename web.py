#!/usr/bin/env python3
"""Prosty serwis WWW z kołem kolorów i efektami do sterowania ledbarem przez DMX/OLA.

Uruchamiane lokalnie na Raspberry Pi: python3 web.py
Otwórz w przeglądarce: http://<adres-rpi>:8080/

Efekty 'rainbow' i 'chase' działają per-segment i wymagają ustawienia
ledbara w trybie 24-kanałowym na jego wyświetlaczu (patrz README) oraz
uruchomienia tego skryptu z --channels 24.
"""

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dmx_control import DEFAULT_NUM_CHANNELS, DEFAULT_START_CHANNEL, DEFAULT_UNIVERSE, DmxController, EFFECTS

HOST = "0.0.0.0"
DEFAULT_PORT = 8080

controller: DmxController
state_lock = threading.Lock()
effect_thread = None
effect_stop_event = None


def stop_effect() -> None:
    global effect_thread, effect_stop_event
    with state_lock:
        if effect_thread is not None:
            effect_stop_event.set()
            effect_thread.join()
            effect_thread = None
            effect_stop_event = None


def start_effect(name: str, kwargs: dict) -> None:
    global effect_thread, effect_stop_event
    stop_effect()
    with state_lock:
        effect_stop_event = threading.Event()
        effect_thread = threading.Thread(
            target=EFFECTS[name], args=(controller, effect_stop_event),
            kwargs=kwargs, daemon=True)
        effect_thread.start()


PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sterowanie ledbarem</title>
<style>
  body { font-family: sans-serif; display: flex; flex-direction: column; align-items: center;
         background: #111; color: #eee; margin: 0; padding: 2rem; }
  canvas { border-radius: 50%; cursor: crosshair; touch-action: none; }
  #status { margin: 1rem 0; font-size: 1rem; }
  .buttons { display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: center; max-width: 320px; }
  button { font-size: 1rem; padding: 0.6rem 1rem; border: none; border-radius: 8px;
           background: #333; color: #eee; cursor: pointer; }
  button:hover { background: #444; }
  #note { max-width: 320px; margin-top: 1rem; font-size: 0.8rem; color: #888; text-align: center; }
  .tempo { display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem; }
  .tempo input { width: 200px; }
  .segments { margin-top: 1.5rem; text-align: center; }
  .segment-row { display: flex; gap: 0.4rem; justify-content: center; margin-top: 0.5rem; }
  .segment-row input[type=color] { width: 32px; height: 32px; border: none; padding: 0; background: none; }
</style>
</head>
<body>
<h1>Sterowanie ledbarem</h1>
<canvas id="wheel" width="300" height="300"></canvas>
<div id="status">Wybierz kolor</div>
<div class="tempo">
  <label for="tempo">Tempo</label>
  <input type="range" id="tempo" min="1" max="100" value="50">
</div>
<div class="buttons">
  <button id="rainbow">🌈 Tęcza</button>
  <button id="chase">🏃 Pościg</button>
  <button id="pulse">💓 Puls</button>
  <button id="stop">⏹ Stop</button>
  <button id="blackout">⚫ Blackout</button>
</div>
<div id="note">"Tęcza" i "Pościg" działają per-segment i wymagają trybu 24-kanałowego ustawionego na wyświetlaczu ledbara.</div>
<div id="segments" class="segments"></div>
<script>
const canvas = document.getElementById('wheel');
const ctx = canvas.getContext('2d');
const status = document.getElementById('status');
const radius = canvas.width / 2;
let lastColor = {r: 255, g: 0, b: 0};
let currentEffect = null;
let tempo = 50;

function tempoToSpeed(t) {
  // suwak 1 (wolno) .. 100 (szybko) -> opóźnienie między krokami efektu w sekundach
  return 0.55 - (t / 100) * 0.53;
}

function hsvToRgb(h, s, v) {
  const c = v * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = v - c;
  let r, g, b;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}

function drawWheel() {
  const image = ctx.createImageData(canvas.width, canvas.height);
  for (let y = 0; y < canvas.height; y++) {
    for (let x = 0; x < canvas.width; x++) {
      const dx = x - radius, dy = y - radius;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * canvas.width + x) * 4;
      if (dist <= radius) {
        const angle = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
        const sat = dist / radius;
        const [r, g, b] = hsvToRgb(angle, sat, 1);
        image.data[idx] = r; image.data[idx + 1] = g; image.data[idx + 2] = b; image.data[idx + 3] = 255;
      }
    }
  }
  ctx.putImageData(image, 0, 0);
}

async function post(path, body) {
  try {
    await fetch(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {}),
    });
  } catch (e) {
    status.textContent = 'Błąd połączenia z serwerem';
  }
}

async function pickColor(evt) {
  const rect = canvas.getBoundingClientRect();
  const clientX = evt.touches ? evt.touches[0].clientX : evt.clientX;
  const clientY = evt.touches ? evt.touches[0].clientY : evt.clientY;
  const x = clientX - rect.left, y = clientY - rect.top;
  const dx = x - radius, dy = y - radius;
  if (Math.sqrt(dx * dx + dy * dy) > radius) return;
  const [r, g, b] = ctx.getImageData(x, y, 1, 1).data;
  lastColor = {r, g, b};
  currentEffect = null;
  status.textContent = `RGB(${r}, ${g}, ${b})`;
  status.style.color = `rgb(${r},${g},${b})`;
  await post('/api/color', lastColor);
}

canvas.addEventListener('click', pickColor);
canvas.addEventListener('touchstart', (e) => { e.preventDefault(); pickColor(e); });

function startEffect(name, labelText) {
  currentEffect = name;
  status.textContent = labelText;
  post('/api/effect', {name, speed: tempoToSpeed(tempo), ...lastColor});
}

document.getElementById('rainbow').addEventListener('click', () => startEffect('rainbow', 'Efekt: tęcza'));
document.getElementById('chase').addEventListener('click', () => startEffect('chase', 'Efekt: pościg'));
document.getElementById('pulse').addEventListener('click', () => startEffect('pulse', 'Efekt: puls'));

document.getElementById('stop').addEventListener('click', () => {
  currentEffect = null;
  status.textContent = 'Zatrzymano efekt';
  post('/api/stop');
});
document.getElementById('blackout').addEventListener('click', () => {
  currentEffect = null;
  status.textContent = 'Blackout';
  post('/api/blackout');
});

const tempoInput = document.getElementById('tempo');
tempoInput.addEventListener('input', (e) => { tempo = +e.target.value; });
tempoInput.addEventListener('change', () => {
  if (currentEffect) {
    post('/api/effect', {name: currentEffect, speed: tempoToSpeed(tempo), ...lastColor});
  }
});

async function loadSegments() {
  const cfg = await (await fetch('/api/config')).json();
  const container = document.getElementById('segments');
  if (cfg.segments <= 1) {
    container.textContent = 'Kontrola pojedynczych segmentów wymaga trybu 24-kanałowego (uruchom web.py --channels 24).';
    return;
  }
  const title = document.createElement('div');
  title.textContent = 'Segmenty:';
  container.appendChild(title);
  const row = document.createElement('div');
  row.className = 'segment-row';
  for (let i = 1; i <= cfg.segments; i++) {
    const input = document.createElement('input');
    input.type = 'color';
    input.value = '#ff0000';
    input.title = `Segment ${i}`;
    input.addEventListener('input', () => {
      currentEffect = null;
      const hex = input.value;
      const segColor = {
        r: parseInt(hex.slice(1, 3), 16),
        g: parseInt(hex.slice(3, 5), 16),
        b: parseInt(hex.slice(5, 7), 16),
      };
      status.textContent = `Segment ${i}: RGB(${segColor.r}, ${segColor.g}, ${segColor.b})`;
      post('/api/segment', {segment: i, ...segColor});
    });
    row.appendChild(input);
  }
  container.appendChild(row);
}

drawWheel();
loadSegments();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/config":
            body = json.dumps({
                "channels": controller.num_channels,
                "segments": max(1, controller.num_channels // 3),
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError:
            self.send_error(400, "Nieprawidłowy JSON")
            return None

    def _no_content(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/color":
            data = self._read_json()
            if data is None:
                return
            try:
                r, g, b = int(data["r"]), int(data["g"]), int(data["b"])
            except (KeyError, ValueError):
                self.send_error(400, "Nieprawidłowe dane koloru")
                return
            stop_effect()
            try:
                controller.set_color(r, g, b)
            except ValueError as e:
                self.send_error(400, str(e))
                return
            self._no_content()

        elif self.path == "/api/effect":
            data = self._read_json()
            if data is None:
                return
            name = data.get("name")
            if name not in EFFECTS:
                self.send_error(400, "Nieznany efekt")
                return
            try:
                color = (int(data.get("r", 255)), int(data.get("g", 0)), int(data.get("b", 0)))
                kwargs = {"color": color}
                if "speed" in data:
                    kwargs["speed"] = float(data["speed"])
            except ValueError:
                self.send_error(400, "Nieprawidłowy kolor lub tempo")
                return
            start_effect(name, kwargs)
            self._no_content()

        elif self.path == "/api/segment":
            data = self._read_json()
            if data is None:
                return
            try:
                segment = int(data["segment"])
                r, g, b = int(data["r"]), int(data["g"]), int(data["b"])
            except (KeyError, ValueError):
                self.send_error(400, "Nieprawidłowe dane segmentu")
                return
            stop_effect()
            try:
                controller.set_segment_color(segment, r, g, b)
            except ValueError as e:
                self.send_error(400, str(e))
                return
            self._no_content()

        elif self.path == "/api/stop":
            stop_effect()
            self._no_content()

        elif self.path == "/api/blackout":
            stop_effect()
            controller.blackout()
            self._no_content()

        else:
            self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=int, default=DEFAULT_UNIVERSE)
    parser.add_argument("--start-channel", type=int, default=DEFAULT_START_CHANNEL)
    parser.add_argument("--channels", type=int, default=DEFAULT_NUM_CHANNELS,
                         help="liczba kanałów fixture ustawiona na urządzeniu: 3 lub 24")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    global controller
    controller = DmxController(
        universe=args.universe,
        start_channel=args.start_channel,
        num_channels=args.channels,
    )

    server = ThreadingHTTPServer((HOST, args.port), Handler)
    print(f"Serwis działa na http://{HOST}:{args.port} (tryb {args.channels}ch)")
    server.serve_forever()


if __name__ == "__main__":
    main()
