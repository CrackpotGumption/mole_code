> Current policy (application 3.2.0): no API tokens, no automatic game or payout
> restoration. Every restart starts fresh. Observational game-state logs persist;
> admins can explicitly supply a restore state through POST /game/restore or the
> /serial game relay, then apply it with /resume. See [API guide](../misc/API.md).
> Legacy checkpoint/recovery instructions below no longer apply.

> Application/firmware 3.0.1 uses an API-first controller. See
> [cabinet API guide](../misc/API.md) for current controls and recovery.
> The API stays available during hardware faults and flashing; it no longer exits
> immediately on serial failure. Historical serial troubleshooting notes below
> describe earlier controller versions.

# Puzzle controller

Run from this directory with `python -m app.app` after installing
`requirements.txt`. Set `ARDUINO_PORT` to the cabinet serial device;
`STATUS_PORT` defaults to 8080. Docker uses the same package entry point.

The main puzzle game uses one-shot `HIT` events from v2's `SENSORS PUZZLE`
mode. It also accepts the raw stream used by the interactive shows from
`arduino/MOLE_FINAL_NO_INTERVAL_v2/MOLE_FINAL_NO_INTERVAL_v2.ino`:
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

Build from the repository root with `docker build -f python/Dockerfile -t mole-game:latest .`.
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

## Audio and the failure show

An accepted hit plays `mole_hit.wav`, and each ready puzzle plays
`game_start.wav`. A wrong hit enters `LAUGH AT YOU` for `FAILURE_SECONDS`
(default 15; allowed 0–120). Sensor reporting stays active while puzzle scoring remains locked.
Random groups of one to three moles move every approximately half second,
and all five mole lights flash randomized colors. All three laugh placeholders
are mixed together and repeated randomly for the configured duration. The
playfield then retracts and the same player starts the same puzzle again.
A failure-show strike retracts that mole, cuts laughter, plays a random
`ouch_1`/`ouch_2`/`ouch_3` reaction, then raises a different mole and resumes
laughter. Replacements wait for the reaction to finish. Another strike can
interrupt the reaction with a new one; it does not extend the failure timer.
Completed players and their indicators remain unchanged. Shutdown interrupts
the show at its next step and prevents a puzzle restart.

Placeholders live in `app/sounds`; see its README for replacement WAV format.
The Docker image includes ALSA's `aplay`. The cabinet launcher passes through
`/dev/snd` when present and disables audio when absent. No sound hardware,
missing files, or playback errors do not prevent gameplay.

Set these optional values in `/etc/mole-cabinet/cabinet.conf` and reinstall the
launcher with `sudo bash misc/linux_bash_daemon` after copying the new script:

```bash
FAILURE_SECONDS=15
VICTORY_SECONDS=45
AUDIO_ENABLED=1
AUDIO_DEVICE='default'
```

Then apply them with `sudo systemctl restart mole-cabinet` between games.
List actual sound devices with `sudo docker exec mole-game aplay -l` and logical
ALSA names with `sudo docker exec mole-game aplay -L`. If `default` is not the
cabinet speaker, set `AUDIO_DEVICE` to the appropriate name (for example
`plughw:0,0`, using the card/device numbers shown on that machine).
Manual `docker run` needs `--device /dev/snd:/dev/snd` for playback; without a
sound device, set `-e AUDIO_ENABLED=0`. Physical audio and pneumatic timing
still need cabinet verification.

## Final victory celebration

The sixth completed player starts a `VICTORY CELEBRATION` lasting
`VICTORY_SECONDS` (default 45, allowed 0–120). Ticket payout starts alongside
this show, while all five mole lights and six player lights cycle through
rainbow colors. Cheering, whistles, and an "oooooo"/kiss placeholder mix plays.
A raised mole can be bashed: it retracts, the mix stops for an encouraging
whistle, then a different mole rises and the victory mix resumes. Hits do not
change completed players or request extra tickets. A reaction does not extend
the timer. At the end moles retract, sound stops, and all six player indicators
return to green. The game remains completed.

**Firmware compatibility:** Python now uses the standard v2 wiring below.
The updated v2 sketch includes nonblocking ticket dispensing and
`PLAYER_LIGHT <index> <r> <g> <b>` command support for the interactive victory
show. Flash the updated v2; v1 uses the older sensor and wiring map.

`/state` includes `ticket_status` and `tickets_dispensed` from Arduino payout
reports. Jam/timeout events set the ticket status to `ERROR`; the motor shuts
itself off. These live reports don't change the earlier recovery guarantee:
ticket request intent is saved, while delivery after power loss remains
unconfirmed and is not automatically retried.

Set `VICTORY_SECONDS=45` in cabinet.conf, copy/reinstall the updated launcher,
and restart the cabinet service between games to apply it. The image and
firmware both need updating. WAV replacements are described in `app/sounds`.

## Standard cabinet mapping

IDs, accelerometer mux channels, and solenoid outputs all use the same number.
Bug identities follow the confirmed cabinet positions below.

| Position | ID/channel/output | Bug | Ring pin |
| --- | --- | --- | --- |
| Front left | 0 | Martin | 14 |
| Front center | 1 | Daphne | 15 |
| Front right | 2 | Niles | 16 |
| Back left | 3 | Frasier | 17 |
| Back right | 4 | Roz | 18 |

This matches `MOLE_FINAL_NO_INTERVAL_v2`. The legacy v1/sketch firmware uses
older mappings and is incompatible with this Python sensor validation.
Completed-player checkpoints are badge-based and do not require conversion.

## Idle rainbow mode

With no active player, the five mole rings cycle through a thirty-second rainbow
with one frame every two seconds by default (`IDLE_FRAME_SECONDS=2`). Moles stay down and idle hits do not count.
Completed-player indicators stay green; they are not recolored by the idle
animation. A real RFID badge or incoming `RFID 001` serial event engages the
puzzle and replaces rainbow ring colors with that badge's fixed puzzle colors.
The console accepts `1` through `6`, `001` through `006`, or `RFID 001` through
`RFID 006` and queues the same badge events.

After a player completes their puzzle, or the final victory show finishes,
idle rainbows resume. Completed-player progress and ticket-request protection
are retained. Completed badges remain ignored; idle lighting does not start
a fresh six-player session. Power-loss recovery also restores idle rainbow
rings and completed players' green indicators.

Idle frames are skipped during puzzle setup/play, failure/victory shows,
shutdown, persistence errors, or while hardware commands are pending. This
prevents animation commands from building up or replacing puzzle colors.

## Serial load and one-hit puzzle polling

Flash the latest v2 firmware together with this Python update. Puzzle setup
keeps sensors disabled while moles/colors are configured, then Python sends
`SENSORS PUZZLE`. Arduino polls all sensors every 10 ms, picks the strongest
qualifying downward strike in that poll, emits one `HIT`, and disarms. It emits
no raw ACCEL stream in puzzle mode. Python processes that event and re-arms only
after the target/light update is finished. There is a 300 ms global interval
between emitted puzzle hits, and every struck sensor must recover above -6400
before it can qualify again. If several sensors strike in the same poll, their
latches prevent the unselected impulses from becoming delayed duplicate hits.

Shows use `SENSORS ENABLE`, which still polls every 10 ms but reports each mole's
most negative sample from each 50 ms window. This reduces raw serial traffic to
about 100 lines/second without throwing away brief downward peaks. Logs omit
raw ACCEL packets unless `LOG_RAW_ACCEL=1` is explicitly set for debugging.

Idle ring colors change only every two seconds; pending commands still prevent
extra idle frames from being queued. Add `IDLE_FRAME_SECONDS=2` and
`LOG_RAW_ACCEL=0` to cabinet.conf if desired, copy/reinstall the launcher, then
restart the service between games. Existing configs use these defaults even if
the keys are absent. For slower lighting set `IDLE_FRAME_SECONDS=4` (allowed
0.5–60 seconds). Actual sensor thresholds/timing still need cabinet testing.

### Troubleshooting puzzle hits

`OK SENSORS PUZZLE ARMED` confirms the flashed firmware recognizes puzzle mode.
The updated v2 loop polls sensors before checking RFID, and card-presence checks
run no more often than every 250 ms. This avoids imposing an RFID timeout on
every sensor scan. A card scan can still briefly delay polling.

Once per second during puzzle mode, `PUZZLE_DIAG` reports each mole's `ARMED`,
`LATCHED`, successful `READS`, read `FAILURES`, and `MIN_Z`/`MAX_Z`. These low-rate
lines distinguish failed sensor reads from thresholds/orientation issues
without restoring the full sample stream. A valid downward strike must reach
Z <= -9000. With `READS 0`, min/max values are sentinel values, not readings.
Record these lines while bashing each mole before adjusting thresholds.

### Recovery from missing acknowledgments

The controller stops on the first command ACK timeout, rejects new commands,
and exits with failure so the Docker restart policy can reopen/reset the Arduino.
This prevents a queue of animation commands from continuing into a stalled
connection. It does not guarantee the physical moles retract while the Arduino
is unresponsive; firmware initialization retracts them after a successful reset.
A direct Python run needs restarting manually after this error.

For recurring stalls, retain the last heartbeat, `PUZZLE_DIAG` readings and
startup Wire-timeout message. These distinguish sensor/I2C failures from a
connection or power interruption. V2 also uses nonblocking ticket payout so
sensor/serial processing continues while dispensing.

### Startup-motion suppression and Wire timeout fix

Puzzle arming now waits 750 ms after each arm request, then requires each sensor
to return above Z=-6400 before it can detect a new downward strike. This keeps
pneumatic startup/retraction motion from immediately becoming a wrong answer.
The sensor poll continues during settling, and diagnostic latches remain set
until the resting sample is observed.

V2 requires the Wire timeout API directly rather than checking the unsupported
`WIRE_HAS_TIMEOUT` macro. Use a current Arduino AVR Boards core; if compilation
reports missing `setWireTimeout`/timeout-flag methods, update that core in Boards
Manager. Startup must print `I2C TIMEOUT ENABLED 25000 us`. This bounds stalled
Wire transfers and resets the TWI peripheral on timeout; electrical problems
still need correction if `I2C_TIMEOUT` repeats.

A disconnected RFID reader (version 0x00 or 0xFF at startup) is not polled.
Console badges continue to work. Connect it before boot/restart or issue
`RFID STATUS` to refresh detection after reconnecting.

### RFID initialization

V2 uses the tester's `SPI.begin()` / `PCD_Init()` / 100 ms settling delay and
retries initialization up to three times before disabling an unresponsive
reader. Console commands `RFID STATUS` and `RFID INIT` query or reinitialize
it through the controller's existing serial connection. Both firmware commands
reply with an ACK, so querying status does not trip the ACK-timeout recovery.
The tester reads card UIDs; game badges still need player ID 001–006 stored at
address/block/page 4 as expected by the game firmware.

RFID startup now initializes before cabinet peripherals and logs version checks
under `RFID_DIAG PHASE`: `EARLY BEFORE CABINET`, `AFTER I2C`, `AFTER MOLE LEDS`,
`AFTER PLAYER LEDS`, `AFTER SOLENOIDS`, and `AFTER SENSORS`. When a standalone
tester works but the game doesn't, compare the earliest version with the later
checkpoints. This is diagnostic instrumentation, not confirmation of a hardware
fix. Test the standalone reader with the same full cabinet wiring and power.

### Quiet logs

Heartbeat lines and idle/victory rainbow commands/ACKs are hidden by default.
V2 heartbeat emission is also disabled by default. Flash the updated sketch
to remove heartbeat lines from Arduino Serial Monitor itself. Send
`HEARTBEAT ON`/`HEARTBEAT OFF` over serial or through the Python console to
toggle firmware emission; Python displays them only with `LOG_HEARTBEAT=1`.
Errors, timeouts, RFID diagnostics, puzzle setup commands, and hits stay visible.
Enable either category with `LOG_HEARTBEAT=1` or `LOG_RAINBOW_COMMANDS=1`.
For a direct run: `LOG_HEARTBEAT=1 LOG_RAINBOW_COMMANDS=1 python -m app.app`.
For cabinets, add those variables to cabinet.conf, reinstall the updated
launcher and restart the service. Set them to 0 for quiet operation.

Startup now waits up to 10 seconds for the firmware's `READY` line before
sending commands, instead of assuming boot completes after a fixed two seconds.
If no boot response arrives, the port is closed and a startup error explains
that reset/power-cycle and boot diagnostics are needed. An intentionally closed
serial port no longer produces a misleading reader error during shutdown.
Persistent I2C timeouts during piston movement still require investigating the
shared bus/power/wiring; serial reconnection cannot power-cycle external sensors.

### Serial commands over HTTP

POST a JSON command to `/serial` to use the running controller's ordered serial
queue. For example, from an administration computer on the cabinet LAN:

```bash
curl -i http://mole4.local:8080/serial \
  -H 'Content-Type: application/json' \
  --data '{"command":"RFID STATUS"}'
```

A successful request returns HTTP 202 with
`{"status":"queued","command":"RFID STATUS"}`. This confirms queuing, not
an Arduino acknowledgement or successful execution. View replies with
`sudo docker logs --tail 100 -f mole-game` over SSH. Firmware errors also appear
there. A disconnected controller returns 503; invalid JSON/commands return 400.
Commands must be a single printable ASCII line of at most 128 characters;
request bodies are limited to 1024 bytes.

This endpoint sends raw firmware commands for cabinet administration. It does
not update Python's puzzle state or payout checkpoint; use manual movement and
payout commands between games. The endpoint shares the status service's LAN
exposure and currently has no authentication. Browser cross-origin access is
not enabled. Cabinets need an updated Docker image to receive this endpoint;
updating the repository checkout alone does not update the running container.

### Firmware identity and automatic Mega updates

The main sketch prints `FIRMWARE <sketch-name> <version> <source-sha256>` during
startup, before `READY`. Python logs its expected identity and validates the
banner before starting command/event workers or the game. A legacy sketch that
prints `READY` but has no identity also counts as a mismatch. A board that never
prints `READY` stops startup for diagnosis rather than triggering a blind upload.

The Docker build compiles `arduino/MOLE_FINAL_NO_INTERVAL_v2` for
`arduino:avr:mega`, bundles its HEX and identity manifest, and includes avrdude.
A mismatch closes the serial connection, uploads the bundled firmware using the
Mega bootloader, then reconnects and verifies the new banner. Flashing and game
startup stop on upload/verification failure; there is one upload attempt per
controller startup. Normal container restart policies still retry failed
startups. Matching firmware is not rewritten. Flashing works offline with the
cached image, and requires the Mega's working USB bootloader. avrdude checks the
ATmega2560 device signature and verifies writes.

The reference on cabinets is the repository sketch **packaged into their Docker
image**, not a live GitHub lookup or arbitrary host checkout. Publish a rebuilt
image after sketch changes to synchronize cabinets. Builds now use the whole
repository as context:

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -f python/Dockerfile -t myst1cus/mole-game:latest --push .
```

`tools/prepare_firmware.py` owns the sketch version and generates the identity
header/hash automatically during Docker builds. For manual Arduino IDE uploads,
regenerate the header after changing the sketch:

```bash
python3 tools/prepare_firmware.py arduino/MOLE_FINAL_NO_INTERVAL_v2 /tmp/mole-firmware
cp /tmp/mole-firmware/MOLE_FINAL_NO_INTERVAL_v2/firmware_identity.h \
  arduino/MOLE_FINAL_NO_INTERVAL_v2/firmware_identity.h
```

Running Python directly from the repository compares against its current sketch.
If an update is needed, install Arduino CLI with the AVR core and libraries used
in `python/Dockerfile`; it compiles and uploads that checkout. Docker cabinets
need no host compiler. Set `FIRMWARE_AUTO_FLASH=0` in the controller environment
to reject mismatches without uploading. Updating firmware resets the Arduino;
perform application updates between games. Completed-player data remains in the
persistent Docker volume.

### Cabinet diagnostics and solve state

`GET /diagnostics` reports application version (`3.0.1`), exact source hash, build
time/revision (when supplied), Python/pyserial, container platform, firmware
identities, serial queue/thread state, last received ACK, recent errors and I2C
counts, sensor/RFID reports, checkpoint/storage information, audio configuration
and the current game. `/state` now includes `solve_state`, with per-player
SOLVED/ACTIVE/PENDING states, next expected mole, step counts and separate ticket
request/payout confirmation. These are read-only observations; no commands or
hardware probes are sent by a diagnostics request.

The updated daemon installer also installs `misc/collect_host_info.py` from this
checkout and mounts a read-only host snapshot into the container. Rerun
`sudo bash misc/linux_bash_daemon` after updating the checkout to enable this.
Without the mount, diagnostics reports `host: null`. Host information is captured
at launch; container OS information is reported separately from Mint host OS.
Do not copy only the two shell scripts; retain the collector beside them.
Supply `--build-arg APP_REVISION=YOUR_GIT_COMMIT` when building to record the commit;
the source hash identifies actual application contents even with uncommitted edits.
No credentials or complete environment variables are included.

See `misc/ERROR_HANDLING_REVIEW.md` for current limitations and recovery additions.


V3 default deployment (application 3.2.23): the image bundles MOLE_FINAL_V3
3.0.1 with V1 hit detection and V2 cabinet controls. Startup verifies the bundled
identity and automatically flashes mismatched firmware when FIRMWARE_AUTO_FLASH
is enabled (default). Gameplay and recovery use SENSORS ENABLE; FIFO modes and
FIFO tuning are disabled. Saved FIFO tuning is retired on startup.
Publish the rebuilt image before restarting cabinet services; restarting an old
container alone does not update its image. The installed launcher pulls the
configured image before starting it, retaining its previous image on pull failure.
