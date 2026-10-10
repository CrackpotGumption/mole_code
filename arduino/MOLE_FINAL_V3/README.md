# MOLE_FINAL_V3

V2 cabinet controls with `checkForHits()` copied verbatim from the workspace's
`sketch_sep13a` (identical to `sketch_sep14c`). V1 and V2 are unchanged. The previous experimental periodic
DELTA reporter has been replaced.

## Reproduced September sensing

- With `SENSORS ENABLE`, check for an impact every 10 ms. Scan all eligible
  sensors until one axis reaches 4,000 counts.
- After a trigger, repeatedly read all five sensors inside one shared 75 ms
  capture window. This is not 75 ms per sensor. Each complete inner pass reads
  all five, and transaction duration can extend the window.
- Calculate each sensor's largest axis range (`maximum - minimum`).
- Require a winner score of at least 10,000 and a 15% lead over the runner-up.
- Emit `SCORES`, then `HIT <mole> <mux> <score>` or `IMPACT_REJECTED`.
- Block for 500 ms after any triggered capture, then automatically resume.
- Pause all sensing for 750 ms after any mole movement and after enabling sensing.

These constants, classification rules, capture logic and cooldown match the September sketches.
There is no fixed 66 reads/sec limit: trigger scans and repeated capture reads
both contribute I2C transactions. The shared capture window is 75 ms, not 75 ms per sensor.

## Retained V2 controller

Hardware mapping remains V2's mux channels 0..4 / solenoid outputs 0..4 and
21-pixel mole rings. V2 RFID handling, incremental ticket payout, command ACKs,
health/recovery, safe stop, controller lease, heartbeat, Wire timeout and watchdog
remain. Health telemetry performs independent reads; it does not run impact
capture inside the command handler. The blocking capture/cooldown delays serial,
RFID and ticket servicing until `checkForHits()` returns.

V2 FIFO and puzzle hit engines are removed. FIFO admission and operation are
explicitly disabled during checked initialization. `SENSORS FIFO`,
`SENSORS PUZZLE` and `HIT_DEBUG ON/OFF` return errors. `SENSORS ENABLE/DISABLE`
control the reproduced September engine. V3 emits no periodic ACCEL or DELTA reports.

V3 is the default firmware selected by `tools/prepare_firmware.py` and the Docker
build. Python enables sensing with `SENSORS ENABLE` after setup, correct hits and
hardware recovery. Firmware identity: `MOLE_FINAL_V3`, version `3.0.1`.
On cabinet startup, the bundled source identity is verified; with auto-flash
enabled (default), a mismatched Mega is uploaded and verified before gameplay.
Cabinets receive this change after the updated image is published and their
launcher pulls it on restart. Failed pulls retain the installed image.

Validation: Mega compilation and executable tests of September detection, timing,
cooldown and suppression. A source comparison asserts the entire detection
function is identical to Sep13a/Sep14c. Cabinet reliability and physical strikes remain
untested.
