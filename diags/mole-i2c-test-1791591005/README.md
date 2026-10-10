# mole4 I²C diagnostic run

Python 3.2.13; firmware 3.0.3. Four 60-second tests, same controller session, with snapshots every ten seconds. Tests ran in maintenance; all moles were safe-stopped afterward. The cabinet remains in maintenance.

| Test | Added timeouts |
| --- | ---: |
| baseline | 0 |
| solenoids | 1 |
| sensors | 1 |
| combined | 24 |

All sampled health reports showed MCP ready, five sensors available, RFID ready, lease active, and an unchanged serial session. Armed-polling diagnostics showed approximately 35–37 reads per second per sensor and no spontaneous HIT/disarming. The combined test confirmed all five outputs high in subsequent health reports; its initial output snapshot was stale (last health report preceded the UP command).

Earlier snapshots contained increments of 0 for baseline, 0 solenoids-only, 5 sensors-only, and 112 combined. The exact earlier phase start times/durations are unavailable, so these raw counts do not establish a percentage reduction in fault rate. This run suggests improvement but still has 24 combined timeouts per minute. It does not establish an overload-only cause or a completed fix. Maintenance does not latch transient readiness failures like gameplay; these tests do not prove normal gameplay will remain fault-free. Hit detection with physical player strikes was not tested.

Recommended next diagnostic: sensors armed with one solenoid energized at a time, using equal measured durations. This can isolate an especially noisy load/branch before further polling changes.
