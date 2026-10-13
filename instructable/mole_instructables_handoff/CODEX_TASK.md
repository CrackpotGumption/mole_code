# Instructions for Codex

You are implementing a public, detailed, reproducible Instructables article for a pneumatic five-mole whack-a-mole arcade machine. Read **all** files in this handoff before coding or writing. User's target contest: https://www.instructables.com/contest/ToysGamesPuzzles26/ . Existing software repo: https://github.com/CrackpotGumption/mole_code .

## Primary deliverable
A publication-ready, visually organized, step-by-step article (Markdown suitable for pasting/adapting into Instructables; if building a preview website, also supply its source), with:
- compelling intro and finished build photo
- safety and tools sections
- precise materials/BOM with quantities and clearly marked optional parts
- dimensioned carpentry drawings and cut list
- printable-parts overview and STL/3MF download instructions (do not invent files)
- sequential assembly of frame, pneumatic deck, PVC guides, cylinders, valves, electrical, NeoPixel collars, software, finishing
- detailed pneumatic and electrical diagrams, plus the five-mole indexing diagram
- generic 30-second game implementation and calibration/testing instructions
- troubleshooting, lessons learned, and optional enhancements
- original photos captioned and placed at appropriate steps

## Implementation strategy
1. Inventory existing repo. Identify actual Arduino sketches, calibration firmware, Python host code, pin maps and commands. Report verified vs assumed. Preserve original working event software.
2. Draft article and file structure using this handoff as source of truth. Place `TODO: PHOTO`, `TODO: STL`, `VERIFY` where needed instead of fabricating data.
3. Produce diagrams (SVG source preferred for editable schematics) and cut diagrams. Use consistent index 0-4, see `BUILD_SPEC.md`.
4. Build a separate **generic** Arduino/Python game, with a Start button, random nonrepeating targets, hit scoring, LED states, 30-second timer, nonblocking effects, audio placeholders, game-over chase. Verify command compatibility with repo and update firmware as required.
5. Create BOM with sourced links where provided; prices should be current only if independently checked. Do not infer unverified manufacturer ratings or wire colors.
6. Document installation, diagnostics and safety, including mains isolation, compressor outlet, fusing, grounding, graceful PC shutdown, and depressurization.
7. Produce a list of unresolved items requiring user files/photos or physical validation. Do not claim untested software/hardware works.

## Critical constraints
- Single cabinet, 5 moles, **no RFID requirement**, **no event-specific characters, puzzle sequences or 6-player status LEDs**.
- Start button goes where RFID reader was on front panel, normally-open to a spare Mega input and GND using INPUT_PULLUP; **pin not yet chosen**.
- Compressor and electronics have **separate external power cords**. Compressor directly into a suitable outlet per manufacturer; electronics through its own power strip. **Never suggest connecting compressor to the internal electronics power strip**.
- Keep AC mains work within appropriate safety scope; recommend approved enclosures, strain relief, circuit protection, and qualified help where needed.
- Cylinder ports and exhaust restrictors: **two exhaust flow controls per solenoid valve**, not on cylinder ports.
- MPU6050 board **Y axis corresponds to physical vertical** as mounted. Do not mistakenly use MPU Z.
- Adafruit #6318 I2C 8-channel solenoid driver already includes MCP23017/MOSFET/flyback. Do not duplicate drivers.
- NeoPixel rings are cut strip segments of **20 LEDs each**, individually driven on Mega D14-D18; not prebuilt 3-pixel rings.
- No accurate end-of-stroke sensor; next mole may rise while previous is still descending. Never require precise completion feedback.
- Don't silently substitute a mechanical E-stop requirement: no dedicated E-stop in the design, but explain isolation and depressurization.
- Treat PETG/TPU as potential alternatives, **not tested in completed machines**; PLA is as-built.
- Do not present unverified electrical connections, thresholds, source code, or STL dimensions as verified.

## Acceptance criteria
Article can be followed by a technically capable hobbyist; every major assembly has an illustration or photo; all circuit and tubing connections have a clear diagram; reproducible BOM; generic software runs without RFID/ticket dispenser; calibration path documented; unresolved questions called out explicitly; original photos are attributed to the project owner.
