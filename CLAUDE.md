# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python scripts controlling a DMX512 RGB ledbar from a Raspberry Pi 3, via OLA (Open Lighting Architecture)'s local Python API — no Art-Net/network layer, no QLC+ GUI. They replace manual `ola_set_dmx` calls and the QLC+ GUI with reusable CLI/web control.

Hardware chain (already working, not something to debug): RPi → USB → uDMX interface (anyma.ch, `16c0:05dc`) → DMX512 → **Fun Generation LED BARbara 24** ledbar (24 RGB LEDs in 8 independently controllable segments). OLA is installed on the RPi with the `usbdmx` plugin active, universe 1 patched to the Anyma USB device.

The fixture's DMX address and channel mode are set on the ledbar's own display (MODE/SETUP/UP/DOWN buttons), not dip-switches. It supports 2/3/5/24-channel DMX modes (manufacturer manual §7.4–7.7); this setup uses address `d001` and mode `3-ch` by default. In **3-ch mode**, channels 1/2/3 = R/G/B for the whole bar (matches this repo's defaults). In **24-ch mode**, each of the 8 segments gets its own R/G/B (channels 1-24) — required for the per-segment effects (`segment`, `rainbow`, `chase`); switching modes on the software side (`--channels 24`) only works if the fixture's own display is also set to `24ch` at a matching address.

This code only runs meaningfully on the target Raspberry Pi with `ola-python` installed (`sudo apt install ola-python` — a system package, not pip-installable; despite common online references, the package is *not* named `python3-ola` in Debian). It cannot be executed or integration-tested from a dev machine; changes can only be syntax-checked (`python3 -m py_compile dmx_control.py web.py`) until run on-device.

## Running

```bash
python3 dmx_control.py color R G B          # one-shot: set whole-bar color, then exit
python3 dmx_control.py segment N R G B      # one-shot: set one segment's color (24ch mode)
python3 dmx_control.py blackout             # one-shot: zero fixture channels
python3 dmx_control.py effect rainbow|chase|pulse [R G B]   # run until Ctrl+C
python3 dmx_control.py interactive          # loop: color/segment/raw/effect/stop/blackout/exit
python3 web.py                              # HTTP UI on :8080 — color wheel + effect buttons
```

Optional flags (all `dmx_control.py` commands and `web.py`): `--universe` (default 1), `--start-channel` (default 1), `--channels` (default 3; pass 24 once the fixture display is set to `24ch`). `web.py` also takes `--port` (default 8080).

## Architecture

- `DmxController` (`dmx_control.py`) wraps `ola.ClientWrapper`/`OlaClient`. `send_dmx(channels: dict[int, int])` is the low-level primitive (1-indexed channel → 0-255 value, validated); `set_color()` (writes the same RGB to every segment implied by `num_channels // 3`) and `set_segment_color()`/`blackout()` build on it.
- OLA's `ClientWrapper` is event-loop based (`wrapper.Run()`/`wrapper.Stop()`), not a simple blocking call — `send_dmx` runs one `Run()`/`Stop()` cycle per send, kicked off by the `SendDmx` callback. `DmxController` holds an internal `threading.Lock` around this cycle because sends can now come from multiple threads at once (a running effect thread plus a foreground command); keep using `send_dmx`/`set_color`/`set_segment_color` as the only write paths rather than touching `client.SendDmx` directly.
- Effects (`effect_rainbow`, `effect_chase`, `effect_pulse`, collected in `EFFECTS`) are plain functions with signature `(controller, stop_event, color=..., speed=...)` that loop calling `send_dmx`-based methods until `stop_event` is set. Both `dmx_control.py`'s `interactive` command and `web.py` run them in a daemon thread and cooperatively stop the previous one (`stop_event.set()` + `join()`) before starting a new one or applying a plain color/blackout — that's the pattern to follow for any new effect or new call site.
- `web.py` has no pip dependencies (stdlib `http.server` only) and imports `DmxController`/`EFFECTS` from `dmx_control.py` directly rather than shelling out to it. Its HTML/JS color wheel computes RGB client-side (HSV wheel via canvas) and only ever POSTs final `{r,g,b}` or effect names — the server does no color math.

See `README.md` for the full Polish-language project brief, including the DMX channel tables and remaining deferred-iteration ideas (arbitrary color fades, presets, sound reactivity).
