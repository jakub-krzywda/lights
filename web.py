#!/usr/bin/env python3
"""Prosty serwis WWW z kołem kolorów do sterowania ledbarem przez DMX/OLA.

Uruchamiane lokalnie na Raspberry Pi: python3 web.py
Otwórz w przeglądarce: http://<adres-rpi>:8080/
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dmx_control import DmxController

HOST = "0.0.0.0"
PORT = 8080

controller = DmxController()
dmx_lock = threading.Lock()

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
  #status { margin-top: 1rem; font-size: 1rem; }
</style>
</head>
<body>
<h1>Kolor ledbara</h1>
<canvas id="wheel" width="300" height="300"></canvas>
<div id="status">Wybierz kolor</div>
<script>
const canvas = document.getElementById('wheel');
const ctx = canvas.getContext('2d');
const status = document.getElementById('status');
const radius = canvas.width / 2;

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

async function pickColor(evt) {
  const rect = canvas.getBoundingClientRect();
  const clientX = evt.touches ? evt.touches[0].clientX : evt.clientX;
  const clientY = evt.touches ? evt.touches[0].clientY : evt.clientY;
  const x = clientX - rect.left, y = clientY - rect.top;
  const dx = x - radius, dy = y - radius;
  if (Math.sqrt(dx * dx + dy * dy) > radius) return;
  const [r, g, b] = ctx.getImageData(x, y, 1, 1).data;
  status.textContent = `RGB(${r}, ${g}, ${b})`;
  status.style.color = `rgb(${r},${g},${b})`;
  try {
    await fetch('/api/color', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({r, g, b}),
    });
  } catch (e) {
    status.textContent = 'Błąd połączenia z serwerem';
  }
}

canvas.addEventListener('click', pickColor);
canvas.addEventListener('touchstart', (e) => { e.preventDefault(); pickColor(e); });
drawWheel();
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
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/api/color":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))
            r, g, b = int(data["r"]), int(data["g"]), int(data["b"])
        except (ValueError, KeyError, json.JSONDecodeError):
            self.send_error(400, "Nieprawidłowe dane koloru")
            return

        try:
            with dmx_lock:
                controller.set_color(r, g, b)
        except ValueError as e:
            self.send_error(400, str(e))
            return

        self.send_response(204)
        self.end_headers()


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serwis działa na http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
