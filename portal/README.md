# Cabinet administration portal

A standalone, dependency-free Python backend with a responsive browser UI. The
four cabinet addresses are fixed in `cabinets.json`: mole1.local:8080 through
mole4.local:8080. No changes or installation on cabinets are required.

From the repository root:

```sh
python3 portal/server.py
```

Open http://127.0.0.1:8090. Run on a computer that can resolve those hostnames and
reach the cabinet LAN (or a VPN into that LAN). This portal's backend reaches the
cabinets; the browser does not require direct cabinet connectivity or CORS.

To serve other administrators on a trusted LAN:

```sh
python3 portal/server.py --bind 0.0.0.0 --port 8090
```

The portal, like the cabinet API, has no login. The default loopback binding keeps
it local. For remote access use an SSH tunnel or an authenticated reverse proxy;
do not expose this unauthenticated control interface to the public Internet.
Behind an HTTPS reverse proxy, rewrite the upstream Origin header to match its
HTTP Host, or strip Origin only after authenticating and enforcing same-origin
requests at the reverse proxy. The backend rejects mismatched browser Origins.

## Features

- Four-cabinet overview with reachability, readiness, lifecycle, progress, active
  player, next expected mole, payout status, optional degradation, fault, and logs.
- State polls every 3 seconds by default; configurable to 5 or 10 seconds. Failed
  cabinets back off to a maximum 60 seconds. Requests do not overlap per cabinet.
- Log snapshots every 30 seconds by default; selectable 15/30/60 seconds or off.
  All four log tails are visible together. Polling can be paused globally.
- Per-cabinet controls for lifecycle, badges, staged restore, application settings,
  firmware retry, audio, launcher settings, hostname and all documented host actions.
- Hardware controls for individual/all pistons, sensors, mole/player lights,
  ticket payout, read commands, and raw serial.
- Maintenance-required buttons stay disabled until a current health sample reports
  maintenance. The cabinet API remains authoritative and validates all controls.
- Every POST has a payload preview. Execution polls cabinet operations, serial
  receipts with their session IDs, and persistent host jobs as appropriate. Only
  one control workflow runs at a time in this browser session.
- No POST retries. Connection loss and missing records are treated as uncertain
  execution; inspect observations and jobs before issuing another control.
- Log filters for UTC since/until and bounded line counts; snapshot JSON download.
- On-demand reports and an API explorer driven by the repository OpenAPI contract,
  with all GET/POST routes, request examples, query strings, IDs, and raw schemas.
- Guide with common diagnostic, piston test, restore, and update workflows, plus
  the full API reference.

Logs are bounded snapshots, not an accumulating historical database. Download a
snapshot or use cabinet historical log filters for investigation. Filtered log
results stay fixed while the fleet tails continue polling. The API explorer can
send any documented control, including game/host serial relays. The server only
proxies documented routes to its startup-configured registry.

Health 503 reports remain visible. A firmware command OK or ticket DONE is not
independent verification of physical movement/delivery. Resume and restarts begin
fresh unless an administrator explicitly stages a restore before Resume.

## Verification

```sh
python3 -m unittest discover -s portal/tests -v
node --check portal/static/app.js
node portal/tests/test_client.js
```

The integration tests use a local simulated cabinet and cover useful health 503
bodies, queued POSTs, session query forwarding, registry/route restrictions,
JSON object validation, cross-origin rejection, and base URL validation.

Client workflow tests exercise serial session polling, two-stage host completion,
uncertain transport failures without POST retries, and asynchronous rejection.

## Audio administration

Open a cabinet, then Audio. Status refreshes at the selected state interval while
that tab is open. It shows requested/resolved ALSA devices, detected USB cards,
playback/worker/queue state, last cue/files/error, category filenames, and raw
fields. Errors can be retained after successful playback.

Enter maintenance and wait for DONE, then select a discovered cue or STOP.
Audio operation DONE means dispatched, not finished or audible. Inspect playing
and last_error afterward. mole_hit/victory interrupt; cheer queues; laugh is a
failure category, not a POST cue.

Choose automatic default, required USB, a detected USB card, or an explicit ALSA
device. Save persists AUDIO_ENABLED/AUDIO_DEVICE; apply through Resume or Recover.
Resume starts fresh unless an administrator stages a manual restore. Uploads, category-file selection, and full gameplay audio sequences are not API
controls.

Volume (application 3.2.9+) accepts 0–400% through POST /audio in maintenance.
It persists and applies to the next cue without reconnecting. Above 100% boosts
samples; inspect last_clipped_samples for potential distortion. The hardware
mixer remains at maximum.

## Strike analysis

Open a cabinet → Sensors. It records cached GET /diagnostics observations once per
second while open, with no overlap and backoff on failures. It sends no serial
commands automatically. Closing or changing tabs stops recording. The Sensors
recorder has its own pause button, separate from global fleet polling.

The V3 recorder parses SCORES, HIT, IMPACT_REJECTED and sensor enable/disable
observations, retaining legacy FIFO parsing for older recordings. It deduplicates
by controller session, timestamp and line and marks potential gaps. Capture is
bounded to 5000 observations; export before closing the tab.

The chart shows each mole's largest XYZ range in a shared 75 ms capture. Scores
below zero denote ineligible capture data. The firmware requires 10,000 counts
and a 15% winning margin. Live FIFO tuning and FIFO bench commands are disabled.
In maintenance, raise moles and enable sensors; detection continues after each
500 ms cooldown. Disable sensors and lower moles afterward. Resume starts fresh.

Verify parsing and continuity with `node portal/tests/test_sensors.js`.
