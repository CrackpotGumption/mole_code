# Cabinet error handling: implemented protections and remaining limits

Application 3.2.0 / firmware 3.0.0 implements the priorities identified in the initial
review. See [API guide](API.md) for control requests and recovery semantics.

## Implemented

- Correlated serial command IDs and ACK OK/ERROR receipts, with response lines,
  timestamps and controller session IDs. Rejected game commands propagate to a
  latched fault; administrative rejections remain visible in their receipts.
- Bounded serial/event/operation queues and bounded HTTP concurrency/body size.
  Diagnostic telemetry is not added to the gameplay event queue. Overflow is
  reported, and an unrelated serial reply cannot release another command.
- Hardware HEALTH polls check the MCP and read all five accelerometers. Failed
  multiplexer selection/register writes no longer silently select the wrong
  sensor. Health ages, I2C counts, last samples, readback/LED-buffer state and
  worker liveness are available through diagnostics. Required hardware blocks
  readiness; missing optional RFID/audio is distinguished from a required fault.
- Persistent firmware attempts and errors, a ten-minute retry cooldown and a
  two-failure automatic limit. Normal matching firmware is not rewritten. Explicit
  maintenance recovery can force a bootloader upload even without
  READY. The uploaded sketch is revalidated and avrdude checks signature/writes.
- Unexpected gameplay errors, rejected commands, board reset, stopped workers,
  stale health and serial loss latch faults and attempt SAFE STOP. Fault history
  persists. HTTP starts first and remains available during startup/update faults.
- Firmware controller lease (five seconds), safe-stop command, two-second AVR
  watchdog and reported reset cause. Pending output shutdown is retried on bus
  recovery. Commands too long for the firmware buffer discard the entire line.
- No automatic game/payout/maintenance restoration. Every restart starts fresh.
  State transitions are logged to stdout and fsynced rotating game-event files.
  Explicit administrator restoration accepts a validated state via POST, stages
  it in memory, and applies it on resume without automatic ticket payout.
- Fixed-action host bridge via a read-only Unix socket mount.
  Host inventory, packages, services, logs, machine identity, CPU/memory/network/disk
  counters and temperature/audio/USB/PCI information are available through the API.
  Credentials, private keys, raw environment variables and arbitrary files/commands
  are not exposed. Game, serial, audio, configuration, firmware and host controls
  use POSTs and operation/command receipts.
- Persistent host action history and systemd execution status for installer updates.
  Reboot/update/hostname/configuration/OS package updates can be requested in
  maintenance through the API. Update operations preserve data and provide
  logs/errors rather than implying a queued action has physically completed.
- Launcher keeps an API-responsive degraded container, including missing USB.
  It checks readiness, reconciles interrupted rollback containers, allows longer
  first downloads, retains cached/offline fallback, validates root configuration
  ownership/permissions, and remaps USB on a host restart.

## Remaining limits and validation

- These protections do not measure piston position, air pressure, illuminated LEDs
  or physically delivered tickets. GPIO/LED buffers and ticket pulses are reported
  observations. Payout recovery is intentionally not implemented. A restart clears its intent
  and counts, and an administrator decides whether any manual payout is needed.
- A failed external output bus can prevent shutdown despite an MCU lease/watchdog.
  Independent electrical cutoff/reset behavior and cold-start states must be tested
  with the cabinet circuitry. Watchdog reset-cause flags depend on what the Mega
  bootloader preserves. Firmware recovery must be tested on actual Mega hardware.
- Histories are bounded. Serial receipts/line history and application operation
  receipts are in memory and change on reconnect/restart; session IDs distinguish
  a new controller. Fault/flash/settings/host-job records and observational logs persist; game state does not.
  Host counters are snapshots, not a time-series monitoring database.
- Initial setup and failure of the administration HTTP process or host-agent/socket
  deployment may still require SSH. The image cannot install host services by
  itself. Complete Linux provisioning/systemd power actions require a Linux cabinet
  smoke test; automated tests mock machine power/update commands.
- Router/LAN access is the administration boundary. API and host-agent token
  authentication have been removed at the owner's request. Maintenance gating,
  fixed actions, validation and request/queue bounds remain. The container retains
  read-only host snapshot/socket mounts and does not receive the Docker socket.
