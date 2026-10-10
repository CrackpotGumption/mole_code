# mole4 V3 investigation — October 9, 2026

Read-only SSH inspection of application 3.2.22 / MOLE_FINAL_V3 3.0.0 before
the September-timing update. Times below are America/New_York (EDT).

- 23:00:27: startup identified old V2 3.0.10 and began V3 upload.
- 23:00:36: avrdude wrote and verified all 29,322 bytes.
- 23:00:38: running V3 3.0.0 source hash matched the bundled identity;
  application reported FIRMWARE VERIFIED AFTER FLASH.
- 23:02:02 and 23:02:05: card UID 0B:24:C7:CB authenticated and read block 4,
  but its data was all zeros. Firmware rejected the missing player ID.
- 23:02:14: card UID FD:65:2A:3E read player ID 006 successfully. All moles
  were raised at 23:02:14.395, sensors enabled at 23:02:14.494, and NILES
  reported score 10,480 at 23:02:14.734. Expected target was DAPHNE; this
  triggered the gameplay failure show. Mechanical motion is a plausible cause,
  not proven from sensor scores alone.
- 23:03:11: first failed health check showed mask 29 (channel 1 missing),
  while MCP, RFID and controller lease remained ready.
- 23:03:13: player 006 completed all four targets. A capture showed sensor 1
  score -65535 (no valid samples) while the accepted target NILES scored 15,991.
- 23:03:14, 17 and 20: health failures 2, 3 and 4; sensor 1 failed ADDRESS_ACK.
- 23:03:23.690: RFID 006 was read again. This is the already-completed player,
  not evidence of a successful start of a distinct second player puzzle.
- 23:03:24: health failure 5 latched a hardware fault, before any new puzzle
  can be inferred from this scan. It was not an RFID-specific failure.
- Automated recovery ran three times and returned FAILED with sensor mask 29.
  Repeated sensor 1 ADDRESS_ACK failures continued while sensing was disabled
  and all five output pins were low. Serial workers remained connected/healthy.
  Twelve I2C timeouts were recorded during earlier gameplay.

Existing HEALTH RECOVER resets the AVR Wire peripheral, deselects mux branches,
and reinitializes/probes MCP and sensors. It does not pulse SCL for bus clearing,
assert the mux hardware RESET pin, power-cycle a sensor branch, or issue a full
MPU device reset. Repeating it did not recover this observed channel failure.
No hardware damage diagnosis is established. A failed health transaction is real,
but the all-sensors-required fault policy is separate from its underlying cause.

Requested update: application 3.2.23 / V3 3.0.1 uses Sep13a/Sep14c's verbatim
hit-detection function (10 ms scan, shared 75 ms capture, 500 ms cooldown,
750 ms global settling), retaining V2 controls and no FIFO. Tests compare the
whole function to Sep13a and exercise actual capture timing and global settling.

## Slower update applied

Published `myst1cus/mole-game:latest` and `:v3-3.2.23` for AMD64/ARM64,
manifest digest `87f4b788f114969ecb0988949e007644068fe73ab8c90b46c798c2b5a560e24d`.
Restarted mole4's cabinet service, which pulled the update. At 23:13:02,
avrdude verified all 29,372 bytes; at 23:13:04 the Mega reported V3 3.0.1
hash `46d470256ed9be63303a06993efd93f7165ab43059bebaad756940829a152b97`;
at 23:13:05 application reported FIRMWARE VERIFIED AFTER FLASH.
Sensor 1 continued failing ADDRESS_ACK immediately after reboot/flashing and
subsequent health retries. Application 3.2.23 is serving its diagnostic API in
FAULT: required hardware unavailable, sensor mask 29. Slower timing has not
restored that branch. No fault-policy bypass or power-cycle was performed.
