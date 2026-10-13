# Repository comparison — 2026-10-13

Scope: local working tree, including existing uncommitted edits; no hardware verification or remote-main comparison. Existing event code is preserved.

| Topic | Handoff | Current source | Draft consequence |
|---|---|---|---|
| Mole indexing | Front 0,1,2; back 3,4 | V3 sensorChannel and solenoidOutput are 0..4; ring pins 14..18 | Code-confirmed mapping; physically check all channels |
| LED count | 20 per collar | V3 MOLE_LED_COUNT=21 | Count actual strip pixels; standalone default will be 20 |
| Detection | Physical vertical Y, Arduino events | V3 trigger max absolute X/Y/Z >=4000; 75ms shared capture; largest axis range >=10000 and 15% lead | Existing detection is not Y-only or baseline-relative |
| Timing | Nonblocking, one-second appearances | V3 global 750ms motion suppression and blocking delay(500) after capture | Cannot reuse unchanged for proposed game |
| Python gameplay | Start, countdown, 30 seconds, +1, no repeat | mole_game.py is badge/character puzzles, six players, failure/victory shows, ticket payout | Implement separate standalone controller |
| Legacy ACCEL fallback | Y | Python still contains Z<=-9000, release Z>-6400 | Do not copy legacy thresholds as verified Y behavior |
| Calibration | Y delta; approximate +/-3000 | Diagnostic reads Y relative to 500ms baseline, 2s each direction; actual source initializes reference 3000/3000 (+/-50%) | README contradicts source default; standalone diagnostic disables advice by default |
| Addresses | Audit needed | V3/diagnostic use MCP 0x20, TCA 0x70, MPU 0x68, +/-16g | Code assumptions, not proof of board voltage compatibility |
| Startup | Outputs de-energized | V3 initializes outputs LOW, SAFE STOP, controller lease, Wire timeout/watchdog | Control state does not prove valve plumbing/retraction |
| Start button | Spare input TBD | No standalone Start input in V3; RFID uses 53/5, tickets 22/23, player LEDs 6; reserved A8..A12 | Propose D24 for new build; verify unused on physical harness |
| Firmware identity | Unknown historical names | tools/prepare_firmware.py selects MOLE_FINAL_V3 version 3.0.3 | Do not use old sketches' mapping or obsolete README instructions |

Protocol confirmed in V3: MOLE <0..4> UP/DOWN, MOLES ALL DOWN, LIGHT <id> <r> <g> <b>, SENSORS ENABLE/DISABLE, HIT <id> <mux> <score>, SAFE STOP, LEASE ON, KEEPALIVE. Standalone firmware will retain basic motion/light vocabulary and add a Start event and appearance tokens to reject stale hits.

Unverified: installed firmware identity, physical LED count, valve polarity/plumbing, sensor breakout voltage and pullups, hit calibration, mechanical dimensions, startup under pressure. No claim of cabinet testing.
