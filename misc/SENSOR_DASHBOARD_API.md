# V3 sensor dashboard contract

Application 3.2.23 / firmware MOLE_FINAL_V3 3.0.1.

FIFO modes and live FIFO tuning are disabled. Old saved HIT_AXIS,
HIT_THRESHOLD_COUNTS, HIT_ARM_DELAY_MS and HIT_DEBUG settings are retired on
startup; new configuration requests for these fields return an error.

The Sensors dashboard polls cached `/diagnostics` and sends no commands while
recording. V3 lines are `SCORES 0:<range> 1:<range> 2:<range> 3:<range> 4:<range>`,
`HIT <mole> <mux> <strength>` and `IMPACT_REJECTED winner=... score=... runnerup=...`.
Each score is the largest XYZ max-minus-min range within a shared 75 ms capture;
Negative scores indicate missing capture data and are not eligible hits. There is no FIFO baseline or
per-sensor sample-count report. Health SAMPLE values are separate observations.
Legacy FIFO lines remain readable for earlier recordings.

V3 requires a 10,000-count score and 15% lead over second place. Trigger scans
are spaced by 10 ms; each capture is followed by a blocking 500 ms cooldown.
Movement pauses all sensing for 750 ms. All settings are firmware constants.

Bench sequence: enter maintenance; raise moles; send SENSORS ENABLE; strike and
observe scores and classification; send SENSORS DISABLE; lower moles; Resume.
Wait for command receipts at each step. Detection resumes automatically after
cooldown. Recording is bounded and may have gaps; export before closing the tab.
