# Cabinet 1 hit history — October 10, 2026

Source: current mole-game container logs, last two hours, collected around
01:22 EDT. App 3.2.31; firmware MOLE_FINAL_V3 3.0.3. CSV times are EDT;
raw log timestamps are UTC. No cabinet settings or hardware state were changed.

15 firmware HIT reports: 11 correct game decisions, three wrong decisions and
one report ignored by the game (a repeated NILES hit after that target was solved).
There were also three IMPACT_REJECTED captures. No logged I2C timeouts or sensor
initialization failures appeared in the collected snapshot.

Wrong decisions:
- 01:18:18: expected ROZ; reported MARTIN, score 29344; ROZ score 2213.
- 01:19:02: expected ROZ; reported FRASIER, score 11093; ROZ score 0.
- 01:19:37: expected ROZ; reported FRASIER, score 11058; ROZ score 0.

At 01:22:54, Sensor 4 / ROZ / back right / mux channel 4 reported X=Y=Z=0
in health telemetry, with 26 consecutive zero health samples and
suspicious_zero_readings=true. All other sensors had plausible resting values.
ROZ's capture score was zero in all eight captures from 01:18:45 through
01:19:37. The controller nevertheless reported Ready, sensor mask 31 and zero
I2C timeouts, because the transactions answered despite returning zero data.
This indicates unusable ROZ sensing in this snapshot, not proof of a specific
hardware cause. Missing ROZ data could leave another sensor's vibration as the
winning classification. Logs cannot independently identify the physically
struck mole, so the three WRONG decisions alone do not prove misregistration.

See hits.csv for each reported hit with all five associated capture scores,
expected target and decision. See raw.log for captured classifications and
rejected captures. This is a bounded snapshot, not ongoing recording.
