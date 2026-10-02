# Puzzle controller

Run from this directory with `python -m app.app` after installing
`requirements.txt`. Set `ARDUINO_PORT` to the cabinet serial device;
`STATUS_PORT` defaults to 8080. Docker uses the same package entry point.

The main puzzle game accepts the raw stream from
`arduino/MOLE_FINAL_NO_INTERVAL_v1/MOLE_FINAL_NO_INTERVAL_v1.ino`:
`ACCEL <mole> <mux_channel> <x> <y> <z>`.

A strike requires Z <= -9000 (the current one-mole test threshold).
X and Y do not contribute to classification. The sensor must recover to
Z > -6400 before another strike, with a 300 ms per-mole cooldown.
These raw-count thresholds assume the firmware's +/-16g accelerometer range
and the mounting orientation used by the directional tests. Validate them
on the cabinet; constants are in `app/mole_game.py`.

Completed/retracted targets, invalid packets and samples received before
hardware setup finishes are ignored. The Queen remains hittable and hitting
her restarts the puzzle. Legacy `HIT` packets remain supported.

Run hardware-free checks with:
`PYTHONPATH=. python3 -B -m unittest discover -s tests -v`.

## Container runtime

Build from the repository root with `docker build -t mole-game:latest ./python`.
The running container is named `mole-game`. Its future Docker Hub repository
is `myst1cus/mole-game`. Publish the image before the first online deployment.
See `docker_cheatsheet.txt` for manual commands or use the cabinet boot installer.

Docker starts `python -m app.app` as the main process. The application opens
`ARDUINO_PORT` at 115200 baud, starts the serial workers and puzzle state,
then serves JSON `/state` and `/health` on `STATUS_PORT` (default 8080).
The cabinet launcher maps the host Arduino to `/dev/cabinet-arduino` inside
the container and publishes port 8080 to the LAN. No internet is needed for
gameplay or status access. State is in memory and resets on container restart.

SIGTERM (`docker stop`) and Ctrl+C lock gameplay, disable sensors, retract all
moles, turn off lights, attempt a bounded command drain, then close the serial
connection and HTTP server. If the serial workers lose the connection, the
main process exits with failure so Docker's restart policy can restart it.
The startup motor/light test remains disabled.

The image health check probes `/health`, which reports HTTP 503 when the serial
controller is disconnected. This verifies connection status, not sensor-stream
freshness or mechanical operation. Docker's unhealthy label alone does not
restart a container; the application exits on detected serial disconnection.
Keyboard badge simulation requires attached stdin (`docker run -i`); a detached
cabinet normally uses physical RFID badges.
