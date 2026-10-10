# Reserved accelerometer interrupt wiring

These assignments reserve unused Mega inputs for future interrupt-based hit detection. Current firmware still polls accelerometers; it does not yet configure motion interrupts or enable a pin-change ISR.

| Mole | Position / character | Sensor INT → Mega | Digital alias | Pin-change input |
| --- | --- | --- | --- | --- |
| 0 | Front left / Martin | A8 | D62 | PCINT16 / PK0 |
| 1 | Front center / Daphne | A9 | D63 | PCINT17 / PK1 |
| 2 | Front right / Niles | A10 | D64 | PCINT18 / PK2 |
| 3 | Back left / Frasier | A11 | D65 | PCINT19 / PK3 |
| 4 | Back right / Roz | A12 | D66 | PCINT20 / PK4 |

Use the headers labeled A8–A12. The analog labels do not prevent digital input use. All five share the Mega PCINT2 interrupt group, with independent status bits. These are pin-change inputs, not Arduino attachInterrupt external-interrupt pins.

Each accelerometer needs its own INT wire directly to its assigned Mega input, bypassing the I²C mux. SDA/SCL stay on the existing mux wiring. Retain common ground. Do not combine these five INT wires. Before energizing, verify the sensor board's interrupt voltage/output type; input polarity, pull-ups, latching, motion thresholds and ISR handling remain to be implemented.

Existing wiring remains: player data D6/D7, mole rings D14–D18, ticket motor/sensor D22/D23, RFID reset D5 and SPI D50–D53, I²C D20/D21. The array accelerometerInterruptPin in the main sketch follows the same 0–4 order as the sensors and solenoids.
