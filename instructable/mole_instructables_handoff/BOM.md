# Draft BOM — One Cabinet (Quantities and Product References)

Prices are intentionally omitted; current pricing has not been verified. Dimensions/SKUs marked VERIFY must be checked against purchased items and 3MF.

| Item | Quantity | Specification / source |
|---|---:|---|
| 3/4-in plywood | as cut | Cabinet sides/front/top/bottom + two 36 x 19.2-in pneumatic-deck panels; optimize sheet layout after final cut drawing |
| Nominal 2x2 lumber | 1 cabinet + 1 deck | Cabinet: 6x36, 6x31.5, 5x19.5 in; deck: 4x36, 2x33, 4x16.2, 4x8.375 in |
| Casters | 4 or as built VERIFY | Cabinet mobility |
| Felt rear cover | 1 | 36 x 34.5 in, heavy felt with Velcro |
| 16-mm bore x 75-mm stroke double-acting cylinders | 5 | VERIFY rod/bottom threads and ports |
| 12V pneumatic directional valves | 5 | Historical 4V210-08, VERIFY actual installed |
| Exhaust flow controls | 10 | Two per valve, one per exhaust |
| 6-connection manifold | 1 | 1 inlet + 5 outlets: https://www.amazon.com/dp/B0FCYNYHQF?tag=crackpotgumpt-20 |
| 1/4-in pneumatic tubing | sufficient | Compressor-manifold, 5 manifold-valve, 10 valve-cylinder runs |
| Push-to-connect fittings / thread adapters | as required | Match valves/cylinders, VERIFY threads and fitting counts |
| Quiet air compressor | 1 | Approx. 2 SCFM at 90 PSI; tool regulator to ~25 PSI |
| Closet flange for 3-in Sch40 PVC | 5 | Oatey Level-Fit style, VERIFY flange SKU |
| 3-in Schedule 40 PVC | ~10 in total + waste | 5 segments x 2 in, buy at least ~12 in |
| Printed mole body | 5 | STL/3MF pending |
| Printed retainer puck | 5 | Captured nut and 4 countersunk #8 screws each; local solid infill modifiers |
| Printed U-guard/sensor mount | 5 | Prevents rotation by straddling cylinder fittings |
| Printed cylinder base mount | 5 | Captured nut, 4 countersunk #8 screws each |
| Printed LED collar + white diffuser | 5 each | 20 LED cut strip per collar |
| Optional printed football decoration adapter | 5 | ~20% rectilinear infill, 5 walls, PLA as-built |
| #8 x 1-in countersunk screws | at least 40 | 4 per puck and 4 per base x 5, plus spares |
| Captured hex nuts | 10 | Two per cylinder, VERIFY thread and dimensions |
| NeoPixel strip | >=100 LEDs | Adafruit #1460 https://www.adafruit.com/product/1460 |
| MPU6050 breakout accelerometers | 5 | https://www.amazon.com/dp/B0F9DLNHTB?tag=crackpotgumpt-20 ; verify board 5V input and I2C levels |
| TCA9548A I2C multiplexer | 1 | 8-channel, use 0-4 |
| Arduino Mega | 1 | USB power/serial from host |
| Adafruit #6318 I2C 8-channel solenoid driver | 1 | Integrated expander/MOSFET/flyback |
| 5V 10A power supply | 1 | https://www.amazon.com/dp/B0D76F4W1C?tag=crackpotgumpt-20 |
| 12V 5A power supply | 1 | https://www.amazon.com/dp/B07GFFG1BQ?tag=crackpotgumpt-20 |
| Screw-down power distribution blocks | 5 | Master 5V 6-way, master 12V 6-way, master GND 12-way, deck 5V 12-way, deck GND 12-way; https://www.amazon.com/dp/B07CLW5FPS?tag=crackpotgumpt-20 |
| Wire, terminals, ferrules, lever nuts | as required | 18AWG deck feeders; 18-22AWG LED wires; other runs per load/length and safe sizing |
| Normally-open momentary Start button | 1 | Mount in original RFID front-panel area, diameter TBD |
| Linux PC, USB cable, speakers | 1 each | Small form factor PC, Linux Mint + Docker + systemd |
| Electronics power strip and compressor power cord | separate | **Compressor must not share electronics power strip** |
| Cable tie mounts, screws, tape, glue, primer/cement | as required | Keep air and electrical routes separate |
| Black paint + satin clearcoat | as required | Glidden Spred black semigloss, Minwax Polycrylic satin |
| Chrome spray paint, vinyl decals, edge trim | optional | Appearance-only |
| Optional ticket dispenser | 1 | Deltronic Labs DL-1275 + printed bin/saddle, not part of baseline |

## Pending
Actual prices, complete cutting optimization, exact fastener/terminal quantities, printed part weights and print time, cylinder/valve thread standards, electrical wire gauges for all branches, supply mains protection, optional source substitutions.
