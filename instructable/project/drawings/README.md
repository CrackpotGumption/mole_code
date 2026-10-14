# Plywood drawing review

Plywood drawings 01–03 approved by the owner October 14, 2026. Not yet attached to the public draft.

- 01_plywood_cuts.svg/png: seven panel cuts and a two-sheet cutting layout, allowing ⅛-inch kerfs between row blanks.
- 02_hole_layouts.svg/png: playfield and upper-deck holes, measured from separate panel origins. The deck is centered between the cabinet rails.
- 03_front_bottom_setback.svg/png: side section showing the ¾-inch front setback of the bottom and the 35.25-inch-tall front beneath the top panel.
- 04_dc_power.svg/png: wiring review, awaiting owner approval. USB-powered Mega, separate 5 V collar and 12 V coil rails, common DC ground.
- 05_signal_mapping.svg/png: wiring review, awaiting owner approval. Mega D20/D21 I²C, D24 Start, D14–D18 collar data; driver and mux channels 0–4 match target IDs.
- 06_controller_schematic.svg/png: terminal-level replacement for the connection-summary sheets. Mega pins, shared I²C branches, open Start switch and named LED data nets.
- 07_sensor_collar_wiring.svg/png: all five sensor SDA/SCL pairs and all five collar DIN/power/ground connections, including shared collar supply buses.
- 08_valve_coil_wiring.svg/png: all five individual 12 V coils connected between driver + terminals and numbered switched outputs.
- 09_pneumatic_channels.svg/png: compressor regulator, manifold and five valve/cylinder circuits, each with two valve-exhaust controls.
- 10_valve_states.svg/png: one channel's OFF and ON flow paths. OFF supplies the cylinder top; the opposite cylinder end exhausts. Port names are functional labels, not claimed stamped numbers/letters.

Corrected electrical schematics 06–08 approved by the owner. Pneumatic sheets 09–10 approved by the owner after the piston-position and extension/retraction text updates. Plywood 01–03, electrical 06–08 and pneumatic 09–10 are the approved publication set; 04–05 are superseded summaries.

Sheets 06–08 are the current wiring-review set; sheets 04–05 are earlier connection summaries and should not be presented as schematics. Repeated net labels across sheets denote electrical connections. Junction dots distinguish connected branches; crossings without dots are not connected. Power routing has been corrected from owner input; no supply connections remain dashed. SVGs remain editable; the PNGs are the rendered review copies.

Owner correction: driver logic Vcc, TCA9548A VCC/VIN and all five MPU6050 breakout VCC inputs are connected to the dedicated 5 V rail. Sheets 06–07 use DEDICATED_5V for these inputs and leave the Mega 5 V pin unconnected externally. All supply sources are resolved. The 5 V breakout input does not imply 5 V tolerance of the bare MPU6050 chip.

Wiring sources: current standalone sketch; [Adafruit #6318 pinouts](https://learn.adafruit.com/adafruit-i2c-to-8-channel-solenoid-driver/pinouts); [TCA9548A reference](https://learn.adafruit.com/adafruit-tca9548a-1-to-8-i2c-multiplexer-breakout/pinouts). The installed mux is an AITRIP board, not asserted to be the Adafruit reference board. Sensor/mux power and pullup compatibility remain dependent on actual board identification/photos; these sheets intentionally do not invent that interface.

The deck's recorded hole X coordinates are preserved. Its 35.75-inch width differs from the 36-inch playfield by ¼ inch; the diagram does not silently alter hole positions to compensate. Review the fit/alignment before calling the drawings fabrication-ready.

All dimensions are inches. Hole diameter for the upper deck is approximately 4.25 inches and must suit the Oatey flange. Actual saw kerf and sheet edge condition affect cutting allowance. SVGs are editable and PNGs are review copies.

Copyright (c) 2026 crackpotgumption. Drawings licensed CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
