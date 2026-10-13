# Standalone software setup

These files run the standalone Start-button game. Calibration reports measurements without preset reference advice.

**Not yet cabinet-validated. Both sketches compiled successfully. Standalone Arduino sketch compiled successfully for arduino:avr:mega using the Arduino IDE bundled CLI (14,452 bytes flash; 801 bytes RAM). Do not claim publication-ready hardware reliability.**

## Wiring assumptions

Mega USB power only; rings D14..D18, driver outputs 0..4, sensor mux channels 0..4; MCP 0x20, mux 0x70, sensors 0x68. `PIXELS=20`; confirm the actual number of installed LEDs before use. Proposed Start pin D24/GND with INPUT_PULLUP; verify unused harness. LOW outputs mean de-energized; verify plumbing/direction under controlled conditions. Breakout voltage/pullups and coil power paths still need manufacturer/physical verification.

## Installation

Upload `arduino/STANDALONE/STANDALONE.ino` for Mega using Wire, Adafruit NeoPixel and Adafruit MCP23017/BusIO libraries. Use a virtual environment for host:

```sh
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
.venv/bin/python python/run.py --port /dev/ttyACM0
```

Run from this software directory. Optional `--config config.json` overrides Settings fields; optional `--sounds /path/to/wavs` loads `start.wav`, `appear.wav`, `hit.wav`, `game_over.wav` through asynchronous Linux `aplay`. No audio assets required. Final score is printed; recorded final-score speech is not implemented. Linux autostart service/container packaging remains TODO.

Y-only baseline delta, threshold 6000 counts, settle 200ms, cooldown 300ms are **new unvalidated starting settings**, not established as-built thresholds. Firmware computes resting baseline with outputs de-energized on boot. Never recalibrate against a moving cylinder. Confirm baseline adequacy for raised position and descending-neighbor vibration; adjust/extend classifier after physical traces.

Protocol: READY STANDALONE_V1, START, HIT id appearance_token delta. Host sends SAFE STOP, LEASE ON, CONFIG threshold settle_ms cooldown_ms, TARGET id token, MOLE id DOWN, LIGHT id r g b, KEEPALIVE. Appearance tokens reject stale events. Startup requires all five sensors. Host refuses to move on missing/mismatched READY. Lease expiry after 3 seconds requests LOW outputs. I2C timeout/watchdog mitigate stalls; failed I2C can prevent shutdown reaching driver. Disconnect/pressure-release controls remain necessary. USB reconnect starts a fresh idle session.

Calibration: stop host and upload `arduino/PISTON_DIAGNOSTIC/PISTON_DIAGNOSTIC.ino`. Serial 115200 newline: 0..4, TEST 3, ALL, STOP, REPORT, CSV ON/OFF, REFERENCE up down. References off by default. LEFT/RIGHT advice requires physically confirming exhaust direction. Response index is acceleration, not speed. Restore standalone firmware after calibration.

## Verification

```sh
python3 -B -m unittest discover -s tests -v
```

Six mocked state-machine tests cover target repetition, wrong/stale/early/duplicate hits, repeated Start, immediate transition, round deadline and chase-to-idle. They do not prove firmware compilation, serial fault behavior or hardware performance. Validate full commissioning checklist in OWNER_TODOS.md before publication.
