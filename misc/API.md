# Cabinet administration API (application 3.2.0 / firmware 3.0.0)

Client/admin portal integration: [complete API reference](API_REFERENCE.md) and [OpenAPI contract](openapi.json).

The API is the normal cabinet administration interface. SSH is needed for initial
installation and recovery when the API itself cannot start.
The Python HTTP service starts before serial connection, hardware checks or firmware upload. Faults stay visible; the process does not immediately
exit and lose its API when hardware is unavailable.

## Deploy once on existing cabinets

Update this repository checkout with these changes, retaining the complete `misc`
folder, then run the installer while the cabinet is idle:

```bash
sudo bash misc/linux_bash_daemon
```

The installer adds `mole-host-agent.service`, installs the host collector/agent/
installation updater, and recreates the game with read-only mounts for the host
snapshot and agent Unix socket. There is no API token or authentication layer;
access is controlled by the cabinet router/LAN. The image alone cannot install
a host service, so existing cabinets must rerun the updated installer.

Requests below assume a cabinet named `mole4`; its LAN IP can be used while
changing its hostname or network binding.
Host data is collected by a fixed-action service, without granting the container
access to the Docker socket. Host configuration and action history stay root-owned.

## Read endpoints

| Endpoint | Information |
| --- | --- |
| `/api` | Route inventory and control examples |
| `/health` | Readiness, lifecycle phase, fault, maintenance and degraded optional hardware |
| `/state` | Active/completed players, solve order/progress, next expected mole and payout status |
| `/diagnostics` | App/build/Python/tool versions, firmware, serial queues/receipts summary, recent errors, sensor samples, output-pin/LED-buffer state, audio, game-event logs/storage, configuration, operations and persistent fault/flash history |
| `/host` | Live host OS/kernel/machine identity, CPU/load/memory/pressure, disks, counters, temperatures, USB/PCI, network/routes, processes, service/Docker/container state |
| `/host/packages` | Installed host package/version list; response includes truncation flags |
| `/logs` | Recent system, cabinet, host-agent, container and kernel logs |
| `/host/jobs` | Host action receipts, including failures or jobs interrupted by restart |
| `/commands` and `/commands/ID` | Ordered serial command receipts and actual firmware responses |
| `/operations` and `/operations/ID` | Cabinet operation status/results/errors |
| `/configuration` | Desired application settings, excluding credentials |
| `/host/configuration` | Image, serial path, status bind/port |
| `/firmware` | Persistent flashing attempts, failures and verification history |
| `/audio` | Enabled/device, playback/queue/worker state, last cue/error, available WAV cues |
| `/game/events?limit=100` | Historical observed game states, newest 1..1000 events |

Example:

```bash
curl http://mole4.local:8080/diagnostics
curl http://mole4.local:8080/host
```

`/health` returns 200 when ready to play and 503 during startup, maintenance,
updating or faults. A 503 here does not mean the administration API is unavailable.
Missing RFID/audio can be reported as degraded while serial badge play remains
possible; the output controller and all five accelerometers are required.
For older logs use `/logs?limit=1000&since=2026-10-09T00:00:00Z&until=2026-10-09T01:00:00Z`;
limits are bounded to 1..2000 lines and responses identify truncated output.
Host snapshot fields inside `/diagnostics` are launch-time facts; `/host` is live.
Python/app versions and source hashes distinguish actual image contents from a
Git commit label. The current build can be labeled `working-tree` until committed.

## POST controls

Every POST requires `Content-Type: application/json`; no authentication header is needed. Requests
are bounded to 4096 bytes. They return 202 for queued work; poll the receipt or
operation before relying on execution. Status values distinguish success, command
rejection, timeout, cancellation, operation failure and interrupted host jobs.

| Endpoint | JSON body |
| --- | --- |
| `/serial` | `{"command":"RFID STATUS"}` |
| `/maintenance` | `{}` |
| `/resume` | `{}` |
| `/recover` | `{}` |
| `/game/badge` | `{"player":"001"}` |
| `/game/reset` | `{"confirm":"RESET GAME"}` |
| `/game/restore` | `{"state":{"completed_players":["001"],"active_player":"002","hit_progress":1},"confirm":"RESTORE GAME"}` |
| `/configuration` | `{"settings":{"FAILURE_SECONDS":15,"VICTORY_SECONDS":45,"IDLE_FRAME_SECONDS":2}}` |
| `/firmware/retry` | `{"confirm":"FLASH MEGA"}` |
| `/audio` | `{"cue":"mole_hit"}` or `{"cue":"STOP"}` |
| `/host/actions` | `{"action":"restart_game"}` / `update` / `reboot` / `poweroff` |
| `/host/actions` | `{"action":"update_installation"}` to pull/install host scripts from the recorded checkout |
| `/host/actions` | `{"action":"os_update","confirm":"UPDATE OS"}` for package updates |
| `/host/actions` | `{"action":"hostname","hostname":"mole4"}` |
| `/host/actions` | `{"action":"configuration","settings":{"IMAGE":"myst1cus/mole-game:latest","SERIAL_DEVICE":"","STATUS_BIND":"0.0.0.0","STATUS_PORT":8080}}` |

Raw hardware changes, game reset/restore, configuration, audio tests, firmware
retry and host actions require maintenance first. Reads such as PING, STATUS,
HEALTH and RFID STATUS can be issued during normal play. Maintenance sends SAFE
STOP, pauses the game and stops show audio, while keepalive/health polling continues.
Maintenance is in-memory and clears on restart.
Resume/recover reconnect, verify firmware and revalidate hardware. Every process/power/Arduino restart begins with no completed players, active
puzzle or payout state. Old checkpoints are never read. Observed states remain
in the event logs for administrators.
Recover requires maintenance when a game is already ready; it is available directly
from a fault. Resume clears maintenance mode and starts fresh, unless an administrator has
explicitly staged a state in the current process.

Example serial diagnostic:

```bash
curl http://mole4.local:8080/serial \
  -H 'Content-Type: application/json' \
  --data '{"command":"RFID STATUS"}'
```

The response contains a serial receipt ID and controller session ID. IDs are scoped
to the connection; `/commands/ID?session=SESSION_ID` rejects a replaced controller. Poll `/commands/ID` to see `QUEUED`,
`SENT`, `OK`, `ERROR`, `TIMEOUT` or `CANCELLED`, plus the firmware response lines.
Correlated `ACK ID OK|ERROR` messages prevent unrelated serial output from
acknowledging another command. Command errors remain distinguishable from a lost
connection. Serial and game-event queues are bounded; rejected/overflowed work is
reported rather than accumulated without limit.

Example maintenance and host update:

```bash
curl http://mole4.local:8080/maintenance \
  -H 'Content-Type: application/json' --data '{}'
# Poll /operations/ID until DONE before the next control.
curl http://mole4.local:8080/host/actions \
  -H 'Content-Type: application/json' \
  --data '{"action":"update"}'
```

The cabinet operation's result contains a host job ID; `/host/jobs` records actual
host execution. `update` restarts the installed launcher, which pulls the newest
image and recreates the container. It does not `git pull` or install new host-agent
source. Use `update_installation` for that: it runs a separate systemd job that
pulls the recorded checkout as the original administrator and reruns the daemon
installer. `/host/jobs` includes that job's systemd execution state. `os_update`
updates package lists and upgrades packages noninteractively; inspect its host
job result and `/host` reboot-required flag afterward. A container/machine restart returns to the base game automatically.
Reboot/poweroff naturally interrupt HTTP connections; boot ID and host job history
help distinguish a new boot from an unfulfilled request. A hostname/bind/port change
can move the URL; host bind/port/image/serial changes apply on `restart_game`/`update`.

`/serial` also supports explicit relays for the same controls:

```json
{"target":"game","command":"maintenance"}
{"target":"game","command":"restore_state","confirm":"RESTORE GAME","state":{"completed_players":["001"]}}
{"target":"host","command":"reboot"}
```

The default target is `arduino`; game/host targets create cabinet operation IDs.
These relays use the same validation and maintenance requirements.
They do not allow arbitrary shell commands or file paths.

Application settings additionally support AUDIO_ENABLED, AUDIO_DEVICE,
LOG_RAW_ACCEL, LOG_HEARTBEAT, LOG_RAINBOW_COMMANDS and FIRMWARE_AUTO_FLASH.
Boolean flags use 0/1. Settings persist in the game-data volume and apply on the
next resume/recover; diagnostics distinguishes desired from active configuration.
Game reset starts a fresh session without restoring progress. Game events are
recorded in stdout and rotating, fsynced `/data/game-events.jsonl` logs as rounds,
hits, player completions, shows and ticket reports progress. Logs are never
loaded into live game state. Old checkpoint/control-mode files are ignored.

To restore as an administrator, POST `/game/restore` while in maintenance, supplying
`state` with `completed_players`, optional `active_player` and `hit_progress`, and
optional `ticket_requested`. Use `confirm: RESTORE GAME`. The state is validated
against the known players/puzzles and staged only in memory. POST `/resume` to
rebuild the hardware and apply it. Restoring all players complete does not request
tickets or restart a celebration. Any needed payout is a separate intentional
maintenance serial command. Power loss discards the staged restore, too.

## Recovery protections and limits

- Firmware updates store attempts/errors before uploading. Two failed attempts or
  a ten-minute retry cooldown block repeated automatic flashes across restarts.
  Explicit `/firmware/retry` clears the limit and attempts the bundled Mega image,
  including a board that cannot reach READY. Normal startup does not blindly flash
  an unresponsive board. avrdude checks the ATmega2560 signature and verifies writes.
- HEALTH polls read accelerometers, check the MCP, and report output-pin and LED
  buffer values. These are electrical/software observations, not piston position,
  successful physical ticket delivery, or proof that LEDs are illuminated.
- Unexpected gameplay errors, rejected game commands, stale hardware reports,
  stopped workers, board reset, and serial loss latch a fault and attempt SAFE STOP.
  The API remains available for logs, maintenance and recovery.
- Firmware uses a five-second controller lease and a two-second AVR watchdog.
  Losing Python communication requests output shutdown; a MCU stall triggers reset.
  I2C failure can prevent access to external output hardware. Independent electrical
  cutoff/reset behavior must be tested on the cabinet; software cannot guarantee it.
- A missing/ambiguous USB device leaves the container/API available in degraded
  mode. After fixing the connection, use a host restart so Docker remaps the device.
  Initial pulls get five minutes; cached/offline pull attempts remain 45 seconds.
- An API-responsive faulted update stays available for diagnosis. A container that
  cannot expose its API is rolled back when a previous container exists. Interrupted
  update containers are reconciled by the next launcher run.
- Tokens/passwords, raw environment variables, SSH private keys and unrelated file
  contents are omitted. Resource snapshots/counters are observations, not an ongoing
  metrics database. Current serial receipts are bounded/in-memory; fault, firmware,
  game-event, settings and host-job histories persist. The API reports no fictional
  physical measurements; unsupported sensors and absent host tools remain unknown.
