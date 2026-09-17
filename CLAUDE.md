# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python script controlling a DMX512 RGB ledbar from a Raspberry Pi 3, via OLA (Open Lighting Architecture)'s local Python API — no Art-Net/network layer, no QLC+ GUI. It replaces manual `ola_set_dmx` calls with a reusable script.

Hardware chain (already working, not something to debug): RPi → USB → uDMX interface (anyma.ch, `16c0:05dc`) → DMX512 → ledbar. OLA is installed on the RPi with the `usbdmx` plugin active, universe 1 patched to the Anyma USB device.

This code only runs meaningfully on the target Raspberry Pi with `python3-ola` installed (`sudo apt install python3-ola` — a system package, not pip-installable). It cannot be executed or integration-tested from a dev machine; changes can only be syntax-checked (`python3 -m py_compile dmx_control.py`) until run on-device.

## Running

```bash
python3 dmx_control.py color R G B      # one-shot: set color, then exit
python3 dmx_control.py blackout          # one-shot: zero fixture channels
python3 dmx_control.py interactive       # interactive loop: 'color R G B' / 'blackout' / 'exit'
```

Optional flags (all commands): `--universe` (default 1), `--start-channel` (default 1), `--channels` (default 3).

## Architecture

- `DmxController` wraps `ola.ClientWrapper`/`OlaClient`. `send_dmx(channels: dict[int, int])` is the low-level primitive (1-indexed channel → 0-255 value, validated); `set_color()` and `blackout()` are built on top of it, mapping to `start_channel`.
- OLA's `ClientWrapper` is event-loop based (`wrapper.Run()`/`wrapper.Stop()`), not a simple blocking call — `send_dmx` runs one `Run()`/`Stop()` cycle per send, kicked off by the `SendDmx` callback. Keep this pattern when adding new send paths rather than trying to call the client synchronously.
- The ledbar's physical DMX start address and total channel count (RGB only vs RGBW/dimmer/strobe) are **not yet confirmed** on the actual hardware — this is why they're runtime-configurable (`--start-channel`, `--channels`) rather than hardcoded. Don't assume the 3-channel RGB default is final; check `README.md`'s "Otwarte pytania" section before changing fixture-mapping logic.

See `README.md` for the full Polish-language project brief, including open questions and deferred-iteration ideas (fades, presets, sound reactivity) that are explicitly out of scope for now.
