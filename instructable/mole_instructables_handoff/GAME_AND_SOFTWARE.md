# Generic Game and Software Specification

## Desired user experience
- On power restoration, Linux host boots, service/container launches automatically, Arduino connects, all 5 LED collars display continuous rainbow idle animation.
- **Normally-open momentary Start button** mounted at former RFID position on front panel. Wire spare Arduino Mega digital input to GND, firmware `INPUT_PULLUP`; pin TBD after source audit.
- Press Start: short configurable pre-game countdown; then 30-second round begins. Ignore repeated Start during countdown/game/game-over.
- At round start rings turn **solid red**. Select a random mole from 0-4; raise it; active ring **yellow**. Exactly **one scoring-active mole at a time**.
- Active mole has **1 second** to be hit (configurable). Correct hit = **+1 point**; active ring flashes **green twice**, nonblocking; command immediate retract and activate next mole. Timeout = retract without score, restore red, activate next mole.
- Next mole chosen uniformly from **other four indices**, NEVER same as previous, on hit or timeout.
- **Do not wait for previous cylinder to finish retracting** before commanding next raise; there is no end-of-stroke sensing. Two cylinders may briefly move at once. Python/firmware must suppress false positives caused by commanded motion and mechanical settling. Green flash must not delay transition.
- At 30 seconds, retract all moles, stop scoring, perform **brief configurable sequential LED ring chase** (speed, colors, cycles), announce final score using optional audio, then return to rainbow idle.
- Sounds for start, appearance, hit, game-over through optional prerecorded files played asynchronously by Python; no copyrighted/proprietary media included. Missing sound files should not crash gameplay.
- No penalties for misses. No required ticket dispenser, RFID, player badges, puzzle orders, character names, or six-player status strip.
- Expose settings: round length, active duration, countdown, colors, animations, hit threshold/cooldown, sound paths, serial port, optional features. Multi-mole/difficulty modes may be later extensions, not required for baseline.

## Architecture and validation
- Host: Linux Mint small-form-factor PC with Docker and systemd autostart. Python host handles state machine, timing, random choice, scoring, audio, motion-settling suppression, communication. Arduino Mega handles 5 valves via Adafruit #6318, 5 NeoPixel data lines, 5 MPU6050 sensors through TCA9548A, and button input.
- USB serial **115200 baud**. Need inspect actual repo's protocol and firmware before final implementation. Existing event firmware may stream `ACCEL` samples to Python; user specifically wants **Arduino-side hit event detection** for generalized game, which appeared more accurate in testing. Do not assume this already exists; implement/verify it.
- Vertical physical axis is **MPU6050 Y**, not MPU Z. User recalls threshold based on magnitude relative to resting baseline; audit source to determine real axis/sign/threshold/units. Direction, bounce, false-hit and sensor cooldown logic must be experimentally validated.
- Firmware calibration sketch over Arduino Serial Monitor at 115200 supports manual `0`, `1`, `2`, `3`, `4`, `all` to actuate and report extension/retraction acceleration peaks and suggest exhaust restrictor adjustments. Audit sketch; separate calibration and gameplay firmware if necessary.
- Index mapping:
```
           BACK
           3  4
         0  1  2
           FRONT
```
  Sensor mux channel = mole index 0-4; solenoid driver output = index 0-4; NeoPixel Mega data pins = D14 through D18 for index 0 through 4.
- Optional ticket dispenser: D22 motor and D23 pulse sensor historically; keep out of default path.

## Tests Codex should supply
- Mocked serial/sensors so state machine can be tested without hardware.
- Random selection never repeats previous target, including after timeouts.
- Only active mole can score, only once per appearance; hits during motion/settling ignored.
- Timeout transition is nonblocking; green flashes, sounds, chase don't block main loop.
- End-of-round retract-all and idle restoration even after serial errors (best effort); safe startup state valves de-energized.
- Start button debounce and repeated press handling.
- Hardware test procedure for each channel and its matching LED/sensor/valve.
- No assumption that solenoid de-energized direction is safe until actual valve configuration is verified.

## Existing repository
https://github.com/CrackpotGumption/mole_code — main. Historical names mentioned: `mole_game.py`, `app_standard_sensor_logging.py`, `whac_controller_accel_stream_watchdog.ino`, `app.py`. **These names and implementations are not audited in this package.** Preserve working event-specific software and build generic game separately.
