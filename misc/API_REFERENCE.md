# Mole cabinet API reference

Implementation baseline: application **3.2.0**, firmware **3.0.0**, host agent **3.0.1**, discovery API version **1**. This describes the shipped implementation, including integration limitations. Machine-readable contract: [OpenAPI 3.1](openapi.json). Installation guide: [API deployment](API.md).

## Connection and protocol

Base URL: `http://<hostname>.local:8080` or `http://<LAN-IP>:8080`. Binding and port are configurable. Endpoints have no `/v1` prefix. `/api` reports the route inventory and API version; application versions are reported separately by `/diagnostics`.

Requests and responses use JSON. Every POST needs `Content-Type: application/json` and a JSON **object**, even when empty (`{}`). Send a Content-Length; chunked request bodies are rejected. Maximum POST body is 4096 bytes. No token, login, TLS, or role permissions are implemented. Network/router access is the access boundary.

The service does **not** implement CORS headers, OPTIONS/preflight, WebSockets, server-sent events, pagination cursors, ETags, or idempotency keys. A portal on another browser origin should use its own backend/reverse proxy to reach cabinets. An HTTPS portal must also account for browser mixed-content restrictions on direct HTTP cabinet requests.

Use a backend registry of cabinet base URLs. `/host.machine_id` identifies the Linux installation, `/host.boot_id` identifies a boot, and `hostname` is mutable. The service does not provide fleet discovery or fleet-wide operations. `.local` resolution depends on the client/network.

Unix numeric timestamps are seconds since the epoch. `observed_at` and game-event `timestamp` are ISO 8601 UTC strings. Ages and uptimes are seconds. Values may be null or unavailable; unknown is not zero. Ignore additional response fields for forward compatibility.

## HTTP outcomes

| Status | Meaning |
| --- | --- |
| 200 | Read succeeded; inspect nested errors and readiness separately |
| 202 | Work accepted/queued, **not proof of execution** |
| 400 | Invalid JSON, payload, serial line, action, or mode requirement |
| 404 | Unknown route, expired/missing receipt/operation, or changed controller session |
| 415 | POST content type is not application/json |
| 429 | Cabinet operation queue full (capacity 16) |
| 503 | Cabinet not ready on `/health`; otherwise unavailable controller/host bridge or runtime error |

Ordinary errors have `{"error":"message"}`. Under connection saturation (32 simultaneous handler slots), 503 may have an empty body. Unsupported HTTP methods use the standard HTTP server response, which may be HTML. Parse JSON only when present. A host bridge failure becomes public 503; an error inside queued work instead appears in an operation/job with status ERROR.

Do not automatically retry POSTs after a lost response: execution may already have occurred. This particularly matters for ticket payout, reboot, and update. Query records and observed state first. Reads can be retried with bounded backoff.

## Three asynchronous result types

### Cabinet operation

Most POSTs return the operation directly:

```json
{"id":"<uuid-hex>","action":"maintenance","status":"QUEUED","created_at":1791520000.0}
```

Poll `GET /operations/<id>`. Statuses: `QUEUED → RUNNING → DONE | ERROR`. Terminal records add `finished_at` and either `result` (action-specific JSON) or `error` (string). No `started_at` is currently provided. GET `/operations` returns an array in insertion order. Approximately 100 recent records are retained; pending records are retained. Records disappear when Python restarts.

Payload validation can occur **after** acceptance. For example, a missing confirmation can produce HTTP 202 followed by operation ERROR. Maintenance prerequisites are checked at submission. Wait for maintenance DONE before submitting dependent actions; issue a single control workflow per cabinet.

### Serial receipt

`POST /serial` with Arduino target returns a wrapper:

```json
{"status":"queued","command":"PING","receipt":{"id":42,"session_id":"<controller-session>","command":"PING","origin":"admin","status":"QUEUED","queued_at":1791520000.0,"response":[]}}
```

Poll `GET /commands/42?session=<controller-session>`. Statuses: `QUEUED → SENT → OK | ERROR | TIMEOUT | CANCELLED`. Terminal records add `finished_at`; `response` contains actual serial lines. Receipt keys: integer `id`, string `session_id`, `command`, `origin`, `status`, numeric `queued_at`, optional `finished_at`, array of strings `response`. No send timestamp is currently provided. Internal game/health commands also appear. Correlated firmware ACKs determine success; OK confirms firmware handling, not physical motion.

IDs restart on controller replacement. **Always include session when polling.** A changed session returns 404 rather than another command's receipt. Up to 128 terminal receipts plus pending commands remain in memory. Serial queue capacity is 128; a full queue currently returns 503, not 429. Closing a controller cancels pending work. Firmware errors remain ERROR; lost acknowledgements become TIMEOUT and stop further serial writes for recovery.

### Host job

Host actions have two stages: poll the cabinet operation, then use its `result.id` to find the host job in `GET /host/jobs`. A cabinet operation DONE means the bridge accepted the host job, not that Linux completed the action.

Host records have `id`, `action`, `status`, `created_at`, optional `finished_at`, `result`, `storage_error`, and `execution_service`. Statuses are QUEUED, RUNNING, DONE, ERROR, INTERRUPTED. `result` can contain an execution result and `service_job` for an installation update. A RUNNING installation job may already have `finished_at` from dispatch: status is authoritative. Job records persist on the host, with up to 100 retained. Only one active host job is accepted at a time. A host conflict appears as a failed cabinet operation, not public HTTP 409.

Reboot/update may terminate HTTP before the operation result is saved. Reconnect, inspect `/host/jobs`, `/host.boot_id`, and `/diagnostics.application`. Do not assume a transport failure means the action failed.

## Cabinet lifecycle and game state

`GET /health` returns 200 if ready for gameplay, otherwise 503 **with a useful report**:

```json
{"status":"maintenance","ready":false,"phase":"MAINTENANCE","maintenance":true,"reasons":[],"degraded":[],"fault":null}
```

Fields: `status` (`ok`, `maintenance`, `fault`), `ready`, `phase`, `maintenance`, `reasons`, `degraded`, `fault` (null or `{message,timestamp}`). Phases include STARTING, CONNECTING, FLASHING, READY, MAINTENANCE, FAULT. Treat new phases as unknown/non-ready.

Reasons currently include SERIAL_DISCONNECTED, REQUIRED_HARDWARE_UNAVAILABLE, CONTROLLER_LEASE_INACTIVE, HARDWARE_HEALTH_COMMAND_FAILED, HARDWARE_HEALTH_STALE, WORKER_STOPPED, FAULT_LATCHED. Degraded values include RFID_NOT_READY and AUDIO_UNAVAILABLE. Missing RFID/audio may permit play; MCP and all five accelerometers are required. Empty reasons alone does not imply readiness: maintenance/startup is also non-ready.

Lifecycle phase and game `status` are different. `/state.status` is display text, including WAITING FOR BADGE, SETTING UP ROUND, PLAYING, LAUGH AT YOU, VICTORY CELEBRATION, GAME COMPLETE, MAINTENANCE, UNAVAILABLE, and other game messages. Prefer `/health.ready` for readiness and `solve_state` for progress.

All process/power restarts start fresh. Arduino reset clears progress and attempts a fresh connection. Other faults can require explicit recovery. Maintenance and staged restores are in memory and clear on restart. Logs are observations, never automatic restore inputs. Neither progress nor ticket payout is automatically recovered.

## GET endpoint catalog

| Endpoint | Response and parameters |
| --- | --- |
| `/api` | Object: `version`, `routes` (GET/POST arrays), `controls_authentication`, `host_actions`, `control_examples`, `notes` |
| `/health` | Health report above; HTTP 200/503 |
| `/state` | Game state below, plus `controller` health report |
| `/diagnostics` | Diagnostic object below; fields depend on initialization |
| `/commands` | Array of current-controller serial receipts; optional `session` query |
| `/commands/{id}` | One receipt; integer id; optional `session` query; 404 if missing |
| `/operations` | Array of cabinet operations |
| `/operations/{id}` | One operation; UUID hex string; 404 if missing |
| `/configuration` | Application settings object; values are strings |
| `/firmware` | History object keyed by firmware identity/hash; may be `{}` |
| `/audio` | Audio report; may be only `{"enabled":false}` before initialization |
| `/game/events` | Array of recent observed state events; `limit` integer 1–1000, default 100; oldest-to-newest within selected tail |
| `/host` | Live host report below; requires host agent |
| `/host/configuration` | Object of IMAGE, SERIAL_DEVICE, STATUS_BIND, STATUS_PORT; values read from file as strings |
| `/host/packages` | Execution-result object with package/version text in stdout |
| `/host/jobs` | Array of persistent host job records |
| `/logs` | Object: `system`, `journal`, `container`, `kernel` execution results; `installation` maps systemd job names to execution results |

`/logs` accepts `limit` 1–2000 (default 200), `since`, `until` ISO 8601 timestamps. Timezone-free timestamps are interpreted as UTC. Limit is per log source, not total. URL-encode timestamps; unknown/repeated log parameters are rejected by the agent and currently surface as 503. `/game/events` invalid limits return 400. There are no page/cursor or individual host-job endpoints.

### Game state fields

| Field | Type / meaning |
| --- | --- |
| `active_player` | Player ID string or null |
| `completed_players` | Sorted player ID array |
| `hit_progress` | Integer number of correct hits in active puzzle |
| `bug_colors` | Map of mole name to color string |
| `queen` | Game-selected mole/name or null |
| `whack_order` | Ordered mole-name array for active puzzle |
| `solution_order` | Corresponding color-string array |
| `locked` | Game processing lock boolean |
| `status` | Human-readable game status |
| `ticket_dispensed` | Legacy name: payout **requested**, not proof of delivery |
| `ticket_status` | NOT REQUESTED, REQUESTED, DISPENSING, DONE, ERROR, ADMIN RESTORED REQUESTED |
| `tickets_dispensed` | Reported ticket count |
| `solve_state` | Structured solve summary below, or null without initialized game |
| `controller` | Health report, on `/state` |

`solve_state` contains `fully_solved`, `completed_count`, `total_players`, `players` (ID → SOLVED/ACTIVE/PENDING), `current_steps_completed`, `current_steps_total`, `next_expected_mole` (string/null), `ticket_requested`, `physical_payout_confirmed`. The last field reflects a firmware DONE report; it is not independent verification that a player received tickets. Startup/unavailable state omits some game fields; clients must tolerate missing fields.

Player IDs: `001`, `002`, `003`, `004`, `005`, `006`. Mole mapping:

| ID | Position | Name |
| --- | --- | --- |
| 0 | Front left | MARTIN |
| 1 | Front center | DAPHNE |
| 2 | Front right | NILES |
| 3 | Back left | FRASIER |
| 4 | Back right | ROZ |

### Diagnostic response

Top-level fields include `application`, `controller`, `recent_errors`, `configuration`, `active_configuration`, `firmware_history`, `fault_history`, `operations`, `operation_queue_depth`, `control_worker_alive`, `pending_admin_restore`. An initialized game additionally supplies `observed_at`, `runtime`, `host`, `firmware`, `serial`, `storage`, `audio`, `game`. These extra fields can be absent during startup/faults.

- `application`: `version`, `source_sha256`, `revision` (Git SHA or label/null), `built_at`, `source`, optional tool-version `packages` map.
- `runtime`: Python/pyserial versions, container hostname, architecture, kernel, OS, process_id, uptime_seconds.
- `host`: **launch-time snapshot**, not live host telemetry. Use `/host` for live data.
- `firmware`: `expected` manifest and, when connected, `running_identity`.
- `serial`: connected/session/protocol/reset cause, port/baud, failure_reason, hardware_health, health_command_status, health_age_seconds, last_received_age_seconds, line and I²C timeout counters, last_ack, RFID status, sensors `0`–`4` with startup_status/last_values/last_sample_age_seconds, output_pin_and_led_buffer_state, queue depths/pending_commands, worker-alive booleans, recent_errors, recent_serial_lines, event_failure.
- `storage`: game_log_path, game_log_exists, free_bytes, total_bytes, log_error.
- `active_configuration`: current failure_seconds, victory_seconds, idle_frame_seconds or null. `configuration` is desired configuration, which can differ until reconnect.
- `firmware_history`: entries can contain attempts, last_attempt, status (FLASHING/FAILED/VERIFIED), last_error, finished_at. Empty history does not mean disconnected.
- `audio`: enabled, device, queue_depth, last_cue, last_error, playing, worker_alive, available_cues. Discover cue names from this array rather than hardcoding them.

Sensor samples, output readbacks and LED buffers describe reported electrical/software state. They do not measure piston position or prove that lights are illuminated. Some serial nested telemetry shapes depend on the firmware report; retain them as extensible objects in client models.

### Live host report

`/host` exposes `observed_at`, `agent` (version/source_sha256/installation metadata), hostname, os, kernel, architecture, machine_id, boot_id, uptime, load_average, memory, cpu_counters, network_counters, audio_cards, pressure, cpu, storage, block_devices, network, routes, usb, pci, temperatures, disk_counters, hardware_monitors, processes, services, containers, images, docker_version, game_container, reboot_required, upgradable_packages_from_local_cache.

Some values are raw Linux text (`memory`, counters, pressure, uptime). Command-derived values are execution-result objects; JSON commands such as network/routes/block_devices can return decoded JSON **or** an execution-result object if collection fails. Temperature values are raw strings, with thermal-zone values in millidegrees Celsius. Storage entries contain device/mount/filesystem/total_bytes/free_bytes. Absent tools/devices remain null or report errors.

Execution result shape: `exit_code` (integer/null), `stdout`, `stderr`, optional `stdout_truncated`, `stderr_truncated`, `error`. Nonzero nested exit codes can occur in an HTTP 200 report. Raw output is not a normalized metrics API; sample counters twice to derive rates. No long-term metrics database is provided.

## POST endpoint catalog

All endpoints below return a cabinet operation unless stated otherwise. Enter maintenance and wait for DONE before maintenance-required controls.

| Endpoint | Body | Maintenance? | Result |
| --- | --- | --- | --- |
| `/maintenance` | `{}` | No | `{maintenance:true}`; requests SAFE STOP, pauses scoring and audio |
| `/resume` | `{}` | No | Connected/firmware result; reconnects and initializes fresh or explicitly staged state |
| `/recover` | `{}` | Required if already READY | Connected/firmware result; fresh reconnection; does not apply staged restore |
| `/game/badge` | `{"player":"001"}` | No; requires READY | Game state after badge handling |
| `/game/reset` | `{"confirm":"RESET GAME"}` | Yes | Fresh game state; stays in maintenance, clears staged restore |
| `/game/restore` | `{"confirm":"RESTORE GAME","state":{...}}` | Yes | `{staged:true,apply:"POST /resume",state:{...}}` |
| `/configuration` | `{"settings":{...}}` | Yes | Desired configuration |
| `/firmware/retry` | `{"confirm":"FLASH MEGA"}` | Yes | Connected/firmware result; clears flash guard and forces upload |
| `/audio` | `{"cue":"<available-cue>"}` or `{"cue":"STOP"}` | Yes | Audio diagnostics |
| `/host/actions` | Action-specific object below | Yes | Host job record nested in operation.result |
| `/serial` | `{"command":"PING","target":"arduino"}` | Depends on command | Serial wrapper/receipt, not cabinet operation |
| `/serial` | `{"target":"game","command":"maintenance"}` | Depends on action | Cabinet operation |
| `/serial` | `{"target":"host","command":"update"}` | Yes | Cabinet operation |

`/resume` is not simply unpause: it reconnects and starts fresh without a staged restore. Use it deliberately. A reconnect into maintenance leaves hardware stopped. SAFE STOP is a request; inspect serial/errors if hardware communication failed.

### Manual restore payload

```json
{"confirm":"RESTORE GAME","state":{"completed_players":["001","002","003"],"active_player":"004","hit_progress":2,"ticket_requested":false}}
```

At least `completed_players` or `active_player` must be supplied. Defaults: completed_players `[]`, active_player null, hit_progress 0, ticket_requested false. IDs must be known; completed players must be unique, and active player cannot already be completed. Progress is integer 0–4. Progress 4 with an active player marks that player completed and clears active/progress. Without an active player only 0 or 4 is accepted, normalized to 0. ticket_requested must be boolean and can be true only when all six players are completed. Legacy ticket_dispensed is accepted as fallback, but clients should use ticket_requested.

Restore is staged **only in current-process memory**. POST `/resume` to apply outputs/sensors. No automatic celebration or ticket payout occurs, including when all players are restored complete. To deliberately issue tickets use a separate maintenance serial command. `/game/events` state snapshots can help an administrator choose a restore, but only the logical fields above form the restore contract.

### Application configuration

POST `/configuration` merges `settings` with existing overrides, persists settings, and updates desired values. Use `/resume` or `/recover` to apply them to newly created game/audio/controller objects.

| Setting | Accepted values | Default |
| --- | --- | --- |
| FAILURE_SECONDS | Number 0–120 | 15 |
| VICTORY_SECONDS | Number 0–120 | 45 |
| IDLE_FRAME_SECONDS | Number 0.5–60 | 2 |
| AUDIO_ENABLED | Integer 0/1 or string "0"/"1" | 1 |
| AUDIO_DEVICE | String ≤128 characters, no control characters | usb |
| LOG_RAW_ACCEL | 0/1 or string equivalent | 0 |
| LOG_HEARTBEAT | 0/1 or string equivalent | 0 |
| LOG_RAINBOW_COMMANDS | 0/1 or string equivalent | 0 |
| FIRMWARE_AUTO_FLASH | 0/1 or string equivalent | 1 |

Unknown settings are rejected. JSON true/false are not accepted for the 0/1 flags. GET returns strings even when POST used numbers. Firmware retry is explicit upload and distinct from the auto-flash setting. Automatic firmware failures are guarded across restarts (two failures/ten-minute cooldown).

### Host actions

| action | Additional fields | Behavior |
| --- | --- | --- |
| `update` | None | Restart launcher, pull latest image with cached fallback, recreate container |
| `restart_game` | None | Same launcher restart; also attempts image pull |
| `update_installation` | None | Git pull --ff-only as recorded admin; rerun daemon installer in separate systemd job |
| `os_update` | `confirm:"UPDATE OS"` | apt package-list update and noninteractive upgrade |
| `reboot` | None | Reboot Linux after a short delay |
| `poweroff` | None | Shut down Linux after a short delay |
| `hostname` | `hostname:"mole4"` | Update hostname/hosts and restart Avahi |
| `configuration` | `settings:{...}` | Persist whitelisted launcher settings; apply on restart_game/update |

Host configuration keys: IMAGE (Docker reference string ≤256 characters using letters/numbers and `./:_@-`), SERIAL_DEVICE (empty for automatic selection, `/dev/ttyACM<N>`, `/dev/ttyUSB<N>` or supported `/dev/serial/by-id/...`), STATUS_BIND (IPv4/IPv6 address), STATUS_PORT (**integer** 1–65535). settings must be nonempty, with no other keys. GET values are strings. Hostname must be 1–63 ASCII letters/digits/hyphens, begin and end with a letter or digit, and contain no dots.

Image update requires registry access or an existing cached image. Installation update requires recorded checkout/admin metadata, a clean fast-forwardable Git checkout, network and repository credentials where needed. OS update needs internet. Changing hostname/port/bind can move the API URL. Keep the cabinet IP available during these changes.

### Serial contract and firmware commands

Default target is arduino. Command must be one nonempty printable ASCII line, ≤128 characters; CR/LF, binary data and control characters are rejected. Leading/trailing spaces are trimmed. Python adds framing and command IDs automatically. Send commands in uppercase: maintenance gating compares uppercase, but firmware handling expects its defined syntax.

Outside maintenance only PING, STATUS, HEALTH, RFID STATUS, HEARTBEAT ON, HEARTBEAT OFF are allowed. In maintenance any valid line is relayed, but unsupported firmware commands return ERROR. This does not permit arbitrary Linux shell execution.

| Command | Meaning |
| --- | --- |
| `PING`, `STATUS`, `HEALTH` | Firmware identity/status/hardware reporting |
| `RFID STATUS`, `RFID INIT` | RFID report/reinitialize |
| `HEARTBEAT ON`, `HEARTBEAT OFF` | Firmware heartbeat logging |
| `SENSORS PUZZLE` | Arm one puzzle hit |
| `SENSORS ENABLE`, `SENSORS DISABLE` | Repeated hit detection on/off |
| `MOLE <0..4> UP`, `MOLE <0..4> DOWN` | Individual piston output |
| `MOLES ALL UP`, `MOLES ALL DOWN` | All piston outputs |
| `LIGHT <0..4> <r> <g> <b>`, `LIGHT <0..4> OFF`, `LIGHTS OFF` | Mole rings; RGB channels 0–255 |
| `PLAYER_LIGHT <0..5> <r> <g> <b>` | Player RGB; index 0 is player 001 |
| `PLAYER_LIGHT <0..5> OFF`, `YELLOW`, `GREEN` | Named player colors (full command with chosen color) |
| `PLAYER_LIGHTS OFF` | All player lights off |
| `TICKET <1..100>` | Deliberate ticket payout; two-second timeout per requested ticket |
| `SAFE STOP` | Disable sensors, stop payout, request moles down and lights off |
| `LEASE ON`, `KEEPALIVE` | Controller lease; Python manages these automatically |

Game relays accept recover, maintenance, resume, badge, reset_game, restore_state, configure, firmware_retry, audio. Host relays accept the host action names above. Put the same supporting fields alongside target/command. Prefer the dedicated endpoints for typed clients.

## Portal workflows

### Monitor a cabinet

Poll `/health` and `/state` every 2–5 seconds; accept a health 503 body. Fetch `/diagnostics` on selection/fault and poll less frequently (10–30 seconds). Fetch `/host` less frequently or on demand: it runs several system commands and is more expensive. Fetch logs/packages only when requested. These intervals are client recommendations, not server guarantees. Avoid overlapping polling requests and stop/back off when unreachable.

Represent separately: API reachable, gameplay ready, maintenance, optional degradation, current fault, fully solved, payout requested, payout report complete. Use raw details in an expandable diagnostics view. Persist meaningful records in the portal if fleet history must outlive bounded cabinet logs.

### Test a piston and return to play

1. POST `/maintenance` `{}`; poll operation to DONE.
2. POST `/serial` `{"command":"MOLE 0 UP"}`; poll receipt with session until terminal.
3. POST `/serial` `{"command":"MOLE 0 DOWN"}`; verify receipt.
4. POST `/resume` `{}`; poll operation, then confirm health.ready true. This starts fresh.

### Restore three completed players

1. Enter maintenance and wait.
2. POST `/game/restore` with confirmation and completed_players `["001","002","003"]`.
3. Wait for DONE; inspect staged state and pending_admin_restore.
4. POST `/resume`, wait for DONE, inspect `/state`. No tickets are issued by restoring.

### Deploy an image or host scripts

Enter maintenance; submit `/host/actions` with action update or update_installation. Poll the cabinet operation, then host job. Expect temporary loss of HTTP. Reconnect with backoff and verify application revision/version, host agent version, health, and boot ID if appropriate. Update starts a fresh game. Resume afterward only if the cabinet is still in maintenance; avoid an unnecessary second reset when it is already READY.

### Client operation helper (JavaScript, server-side or same-origin proxy)

```javascript
async function request(base, path, body) {
  const response = await fetch(base + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : {'Content-Type': 'application/json'},
    ...(body === undefined ? {} : {body: JSON.stringify(body)}),
    signal: AbortSignal.timeout(35000)
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(data?.error ?? `HTTP ${response.status}`);
  return data;
}
async function operation(base, path, body, timeoutMs = 120000) {
  const accepted = await request(base, path, body);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const record = await request(base, '/operations/' + accepted.id);
    if (record.status === 'DONE') return record.result;
    if (record.status === 'ERROR') throw new Error(record.error);
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error('Client wait expired; operation may still be running');
}
```

Use a separate health reader that preserves 503 reports. Host jobs and serial receipts need their own polling logic; the helper above applies only to cabinet operations. Choose longer waits for firmware and package updates. A client timeout cancels waiting, **not server work**.

## Persistence and limits

Persisted: observed game-event logs (current 5 MiB file plus three rotated files), application settings, firmware/fault history, host configuration, host job history. Not persisted: live game progress/payout recovery, maintenance, staged restore, cabinet operations, serial receipts. Game events contain timestamp/session_id/event/state; the event session is separate from the serial session. Firmware telemetry and API snapshots are observations rather than independent physical measurements.

No cancellation endpoint, arbitrary file reader, SSH-key reader, arbitrary shell executor, network reconfiguration endpoint, fleet discovery endpoint, or automatic game restoration is implemented. API self-description is an inventory, not a complete schema; use this reference and the OpenAPI file together. Future endpoint changes should update both artifacts against the handlers and serializers.

Strip-wide command: `PLAYER_LIGHTS <r> <g> <b>` sets all six player pixels in one update (firmware 3.0.1). Idle uses this once per frame; gameplay keeps individual player colors.

## Category audio assets

Docker builds normalize copies from repository `fx/hit`, `fx/laugh`, `fx/cheer` (or `fx/cheers`), and `fx/victory` to mono 16-bit PCM WAV at 22050 Hz. Source files are preserved; WAV/MP3/OGG/FLAC inputs are supported. Playback picks random files for hit, cheer, and victory. Failure mixes 2–3 concurrent laughter lanes, interrupted by a hit clip before resuming laughter. Puzzle completion cheers on returning to idle; all-six completion plays a victory stinger. Startup still uses the game_start placeholder.

GET `/audio` adds `categories` (category → filenames) and `last_files` (selected playback paths). POST `/audio` accepts `mole_hit`, `cheer`, `victory`, plus discovered legacy cue names. Testing cues requires maintenance. `last_cue` can be an internal asset path or mix identifier. Missing category assets fall back to existing placeholders. Local Python runs must point `FX_DIR` at normalized assets (generate with `python tools/prepare_audio.py fx /tmp/mole-fx` using ffmpeg); Docker handles conversion automatically.

USB audio routing: `AUDIO_DEVICE=usb` is the default. Legacy `AUDIO_DEVICE=default` also resolves to the single USB ALSA card; it does not fall back to built-in audio when USB is absent. `AUDIO_DEVICE=usb` requires USB and disables playback with a diagnostic error if none is present. Multiple USB cards require explicit selection, e.g. `plughw:CARD=DeviceID,DEV=0`, discovered from `/audio.usb_cards`. `/audio.requested_device` shows configured routing; `/audio.device` shows selected routing. Settings changes apply on resume/recover.

USB playback volume is set to 100% and unmuted on the selected USB card at startup. `/audio.mixer` reports card, target_percent, controls/readback, status (APPLIED, NO_PLAYBACK_CONTROLS, NOT_USB, DISABLED, ERROR), and optional error. POST `/audio` with `{"cue":"MAX_VOLUME"}` in maintenance reapplies it. Speaker controls not exposed through ALSA cannot be changed this way.

Adjustable playback gain (3.2.9): POST `/audio` `{"volume_percent":200}` in maintenance, or POST `/configuration` `{"settings":{"AUDIO_VOLUME_PERCENT":200}}`. Range 0–400, default 100. Setting persists and applies to the next cue without reconnect. 0 mutes samples, 100 preserves source amplitude, 200 doubles amplitude. USB hardware mixer stays at 100%. GET `/audio.volume_percent` reports gain and `last_clipped_samples` reports saturation during the last rendered cue. Digital boost cannot increase the speaker amplifier's physical output limit; clipping can distort. Volume requests do not play a cue; test with a separate cue request.

Firmware 3.0.2 mirrors all six player status pixels on Mega D6 and D7. Connect the strip DIN to either pin; only one connection is needed. Both pins are reserved for player-light data, including individual status colors and strip-wide idle updates. RFID reset remains D5.
