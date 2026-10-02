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
gameplay or status access. Completed players are checkpointed to `/data/progress.json` in the
`mole-game-data` Docker volume. An unfinished puzzle restarts after a badge scan.

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

## Recovery after power loss

The cabinet launcher mounts the named volume `mole-game-data` at `/data`.
Completed badges are saved before their green indicators are set, using an
atomic file replacement and disk synchronization. On startup the controller
retracts the playfield, restores completed players' green indicators, and waits
for an unfinished player's badge. A partial puzzle is restarted rather than
resuming physical target positions.

The volume survives ordinary container deletion, updates, and rollback. Don't
delete it or use volume-pruning commands on the cabinet. Direct Python execution
can opt in with `GAME_STATE_PATH=/path/to/progress.json`; without that environment
variable it remains in-memory for development.

Invalid saved progress stops startup and preserves the file for recovery.
A failed save locks gameplay and exits the process rather than continuing with
unrecorded completions. Ticket request intent is persisted before issuing the
command so reboot does not request another payout. A power cut between recording
intent and actual dispensing can leave tickets unpaid; physical payout
confirmation still needs separate handling. A completed six-player game stays
completed across restarts; starting a new group requires clearing its checkpoint
while the controller is stopped. An automatic/session reset is not implemented.
