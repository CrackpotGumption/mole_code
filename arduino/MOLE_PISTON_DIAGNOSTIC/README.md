# Piston speed-index diagnostic

Upload `MOLE_PISTON_DIAGNOSTIC.ino` to the Mega. Libraries: current Arduino AVR
Boards core, Adafruit MCP23017 Arduino Library (`Adafruit_MCP23X17.h`). Stop
the Python controller/container first and open Serial Monitor at **115200**, newline.

Solenoid outputs and accelerometer mux channels both use:

| ID | Position | Bug |
| --- | --- | --- |
| 0 | Front left | Martin |
| 1 | Front center | Daphne |
| 2 | Front right | Niles |
| 3 | Back left | Frasier |
| 4 | Back right | Roz |

The sketch starts with all pistons down. RFID, lights and tickets aren't used.
It talks to MCP23017 at 0x20, TCA9548A at 0x70 and MPU6050 at 0x68, configured
for +/-16g. Each test measures 500 ms of resting accelerometer baseline, raises
the piston and samples for 2 seconds, retracts it and samples for another
2 seconds. Samples are read every 5 ms; only Y is analyzed and reported. Peaks are the
absolute change from that mole's resting Y average. X and Z do not contribute. Commands remain available
while testing; `STOP` requests all pistons down immediately.

Every completed cycle first prints a compact paired line:
`RESULT MOLE 0 UP_Y_DELTA 32749 DOWN_Y_DELTA ... UP_READS ... DOWN_READS ...`.
The actual down value comes from its own recorded retraction trace.

`ALL` tests all five sequentially. By default it reports measured deltas,
Y peaks and timing without inventing a speed reference or restrictor advice.
Use `TEST 0` (or the appropriate ID) to retest one mole.

You can override the targets with `REFERENCE <up_target> <down_target>`.
Advice uses each target with a +/-50% band:
- Up index over 150% of your up reference: **tighten LEFT** restrictor.
- Up index under 50%: **loosen LEFT** restrictor.
- Down index over 150% of your down reference: **tighten RIGHT** restrictor.
- Down index under 50%: **loosen RIGHT** restrictor.
- Within that band: keep the setting. Saturation is flagged as high response.

`REFERENCE 0 0` disables advice again; you can also disable one direction with
zero for that reference. Resting Y averages are still measured automatically
for sensor-delta calculation; these are separate from your optional speed
references. `REPORT` reprints recorded measurements. Settings/results live in RAM.

Commands:
```
ALL                   test all five, 2000 ms capture per direction
TEST 3                test back-left / Frasier
3                     shortcut for TEST 3
TEST 3 3000           longer capture window (500–3000 ms)
ALL 3000              longer window for all moles
REFERENCE 3000 3000    default up/down Y targets, +/-1500 each
REFERENCE 0 0          report deltas only, without advice
REPORT                print current comparisons and advice
CSV ON                stream elapsed time, X/Y/Z, baseline delta
CSV OFF               summary output only (default)
STATUS                current stage, mole and MCP status
STOP                  cancel and request all pistons down
HELP                  command list
```

The readout includes response delay, activity span, last activity after the
command, peak delta, clipping and read errors. **Speed index means acceleration
response, not measured travel speed in mm/s.** End impacts can raise the index;
use the trace, observed movement and repeatable loading when comparing settings.
No peer median or paired-motion reference is calculated. You control whether
reference-based recommendations are enabled.

Output readback verifies the control signal, not piston travel or air pressure.
If I2C fails, a requested DOWN may not reach the output chip; keep normal cabinet
air/power controls available. Re-upload the main v2 firmware after diagnosis.

## Y-only readout

`BASELINE ... Y_AVG ...` reports the resting Y average for the mole.
Both direction reports include `AXIS Y` with raw minimum/maximum, signed
`DELTA_MIN`/`DELTA_MAX`, signed largest `PEAK_DELTA` and its `PEAK_ABS_DELTA`.
`UP_Y_DELTA` and `DOWN_Y_DELTA` are the greatest absolute Y changes in the
respective traces. Activity timing, clipping detection and optional reference
advice all use Y alone. CSV is
`mole,direction,elapsed_ms,y,delta_y,absolute_delta_y`.
