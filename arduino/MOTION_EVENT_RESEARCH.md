# Detection approach

The local implementation now uses the acceleration FIFO at 100 samples/second per sensor. The motion-flag experiment was replaced because flags cannot supply peak strength for strongest-of-five arbitration. The notes below document the earlier research, not the current implementation.

# Motion-event polling without extra wires

Current release: Python 3.2.15, firmware 3.0.5. Failure and victory shows have no hit polling. Puzzle hit detection still uses XYZ samples; no motion-register changes were included in this release.

## Manufacturer documentation findings

For the MPU-6050 family targeted by our register code, motion detection uses a high-pass-filtered acceleration threshold and a duration counter. It detects qualifying motion on any axis and reports its direction. This differs from our current absolute negative-Z strike test. The product specification describes a 1 mg threshold increment and 1 ms duration increment; these must be verified against the installed silicon/revision before calibration. [InvenSense product specification, section 8.1](https://dfimg.dfrobot.com/enshop/image/data/SEN0142/PS-MPU-6000A.pdf)

The older manufacturer register map documents:

| Register | Address | Purpose |
| --- | --- | --- |
| ACCEL_CONFIG | 0x1C | Range and motion-detector high-pass filter |
| MOT_THR | 0x1F | 8-bit motion threshold |
| MOT_DUR | 0x20 | Motion duration |
| INT_PIN_CFG | 0x37 | Interrupt clear policy |
| INT_ENABLE | 0x38 | Motion event enable (bit 6) |
| INT_STATUS | 0x3A | Pending motion event (bit 6), cleared by reading |
| MOT_DETECT_STATUS | 0x61 | Axis/polarity flags; negative Z is bit 3 |

Keep INT_RD_CLEAR disabled so ordinary health/XYZ reads do not clear pending interrupt status. Direction flags clear when their status register is read. The high-pass detector output is distinct from XYZ data registers. The INT wire is not needed to read these registers through the mux. [InvenSense register map, sections 4.5, 4.8–4.9, 4.20–4.22 and 4.27](https://arduino.ua/docs/RM-MPU-6000A.pdf)

## Proposed experiment — not yet implemented

First add a diagnostic-only mode: read WHO_AM_I and configuration back on all five sensors, configure motion detection, and report latched status without advancing gameplay. Verify that an event survives between polls and that unrelated XYZ/health reads leave it intact.

Then test one short strike on each mole, adjacent-mole strikes, sustained vibration, extension/retraction, and quiet idle. Explicitly clear old events after mechanical settling and before every puzzle arm. Accept one qualifying event, then disarm until Python rearms. Evaluate negative-Z flags rather than treating any motion as a hit. Do not fabricate strength: these flags do not preserve the original peak acceleration.

A candidate schedule is one status check every 10 ms, giving each sensor a 50 ms revisit interval. Event retention could prevent brief events being missed, with up to approximately 50 ms reporting latency plus processing. This is a proposed latency budget, not a tested guarantee. Continuous status polling still switches the mux and performs register transactions; no-wiring operation cannot remove polling entirely.

Measure transactions, timeout counts and false/missed hits before switching normal gameplay. Fewer payload bytes alone provide a smaller reduction than reducing polling frequency. A latched event is not a history of multiple strikes or a peak recorder. Motion-counter behavior and the limited threshold range may make crosstalk difficult to reject on the cabinet.

Our existing firmware assumes the MPU register family, but hardware identity and actual feature behavior have not been verified by this research. Validate FIFO sampling and strike discrimination on the installed devices. Avoid a blanket automatic fallback that silently changes detection semantics.
