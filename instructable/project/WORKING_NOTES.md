# Build a Customizable Pneumatic Whack-a-Mole Arcade Cabinet

Build a five-target pneumatic whack-a-mole arcade cabinet with removable mechanisms, illuminated collars, and decorations you can customize. Compressed air raises each target; an accelerometer travels with it to detect impacts, while an Arduino Mega controls valves and LEDs and a Linux PC runs the game and audio.

I built four cabinets for an event, with bug puppets and RFID puzzles. This guide documents one cabinet and a simpler standalone game: press Start, wait for a short countdown, then score one point per hit during a 30-second round. RFID, tickets and linked cabinets are optional extensions.

DRAFT STATUS: The cabinet was built; the standalone game is a separate adaptation in progress. Photographs show the original event version. Dimensions are interview-derived unless marked otherwise. Missing print files, measurements and hardware checks are explicitly listed below; this draft is not yet a fully validated reproduction guide.

Overall cabinet: 37.5 inches wide x 24 inches deep x 36 inches high, excluding casters. Five targets use 16mm-bore, 75mm-stroke double-acting cylinders. All original photos are provided by the project owner.


## Supplies

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


## Step 1: Plan the cabinet and work safely

Isolate electrical power and disconnect and depressurize the air system before servicing. Account for trapped pressure and automatic compressor restart. Keep fingers away from moving rods and guides. Use soft decorations, protect moving wiring, and secure heavy equipment.

The compressor has its own external power cord into an appropriately rated outlet. Electronics use a separate external cord and internal power strip. Do not plug the compressor into that electronics strip. Enclose mains connections, use strain relief and appropriate circuit protection, and get qualified help for mains wiring. Branch fuses, grounding/enclosure review, secure supplies and thermal checks are recommendations, not claims about the as-built prototype.

The prototype had no dedicated emergency stop. Document accessible isolation and controlled venting. Never raise pressure beyond component ratings to free a sticking cylinder. Shut down Linux gracefully before cutting electronics power.

TOOLS: saw/jigsaw, drill and countersink, pocket-hole jig, suitable driver including compact/right-angle access, matched edge-slot router cutter if using T-molding, measuring tools, soldering tools, wire stripper, multimeter, tubing cutter, soap solution for leak checks, 3D printer and suitable PPE. Final tools/fasteners depend on verified parts.

## Step 2: Overall cabinet and geometry

- Single cabinet outside dimensions **37.5 in W x 24 in D x 36 in H**, excluding casters. Plywood **3/4 in** throughout. Playfield panel **36 x 24 x 3/4 in**, fitted between side panels.
- Five playfield holes, **8.5 in diameter** cut with jigsaw; printed collars reduce clear aperture to about **8 in**. Coordinates measured from playfield **front-left corner**: front row (depth,left) = (6,6), (6,18), (6,30) inches; back row (18,12), (18,24).
- Indexing, looking from front toward back:
```
       BACK
       3   4
     0   1   2
       FRONT
```
- Rear removable access cover: **36 in W x 34.5 in H** thick felt panel, Velcro to inner 2x2, recessed.

## Step 3: Cabinet 2x2 structure

- Nominal framing cut list: **6 x 36 in; 6 x 31.5 in; 5 x 19.5 in**.
- Top and bottom rectangles approximately **36 x 22.5 in**; centered 19.5-in bottom crossmember; six 31.5-in verticals at corners and centers of 36-in edges. Two additional 36-in interior horizontal rails about 15 in below upper rails support pneumatic deck.
- 19.5-in members pocket-screwed between 36-in members; other 2x2 joints with 2.5-in screws. Plywood secured from inside with 2-in screws. As-built no wood glue for potential disassembly; recommend glue for permanent cabinet.
- Front panel is 36 in wide x ~35.25 in high; side panels 24 x 36 in. Confirm final edge overlap and trim dimensions in drawing; do not force an inconsistent cut plan.

## Step 4: Removable pneumatic deck

- Standalone box frame, nominal **36 in W x 19.2 in D**. Cut list: **4 x 36 in; 2 x 33 in; 4 x 16.2 in; 4 x 8 3/8 in** 2x2s. Two rectangular levels with centered 33-in crossmembers, four short uprights.
- Upper and lower **36 x 19.2 x 3/4 in** plywood sheets. Bottom solid. Top five approximately **4.25-in** flange openings, coordinates (depth,left) inches: (3.75,6), (3.75,18), (3.75,30), (15.75,12), (15.75,24).
- Deck installed about **2.25 in toward rear** relative to playfield. ~1/4-in front/back adjustment during alignment. Screw deck to support rails and tie deck columns to cabinet columns.
- Rear/front service gaps approximately 1.5 in allow wiring routes.

## Step 5: PVC guides and flange

- **Five** closet flanges for nominal **3-in Schedule 40 PVC** (historically Oatey Level-Fit), each solvent-welded to a **2-in long** PVC segment with suitable primer/cement. Flange drops from **above** into deck upper-panel hole, flange rim sits on upper plywood, secured by **1-in wood screws**. PVC pipe extends **down below the upper plywood**, not up.
- Mole body's long cylindrical printed guide remains engaged in PVC throughout 75-mm stroke. Paint on exposed flange as desired.

## Step 6: Pneumatic actuator and printed mechanical stack

- **Five** double-acting pneumatic cylinders, **16 mm bore x 75 mm stroke**. Each cylinder has top rod threaded stud and bottom threaded stud, both connected to prints using **captured hex nuts**. Verify thread and nut dimensions against 3MF/physical sample.
- Printed components per mole (excluding decorative adapter):
  1. Main moving mole body: flat impact platform + long integrated cylindrical guide.
  2. Retainer/piston puck: under mole body, central rod channel, captured nut, **four #8 x 1-in countersunk screws driven into plastic**. Earlier glued pucks made repairs expensive; screw-on puck is final.
  3. Anti-rotation U-guard: attached under puck, straddles cylinder's **two push-to-connect fittings** to limit rotation, mounts MPU6050 on flat back; moves with mole.
  4. Cylinder base mount: captured nut and flat flange, **four #8 x 1-in countersunk screws** into lower deck plywood.
  5. Optional separately printed football-shaped decoration adapter, **superglued atop mole platform**. Original bug puppets made to fit adapter, some retained additionally by zip ties and Velcro due to impacts.
- Sensor board as-built **superglued** to U-guard. Hot glue detached in some trials; prying superglue sometimes broke guard. Suggest mechanical screws/heat-set inserts for serviceability (not as-built).
- Print as-built **PLA**, successful through event. PETG may improve toughness/heat resistance in permanent installations; TPU considered but flexible parts may compromise rigid alignment. Football adapter approximately **20% rectilinear infill, 5 walls**. Other print settings **not yet verified**; master Bambu Studio 3MF includes many plates and modifier regions, including **100% infill near stress points on retainer pucks**. Preserve 3MF modifier regions; STLs alone cannot encode slicer settings.
- Assembly: bench assemble body/puck/guard with prewired accelerometer, cylinder, base mount, fittings; leak-test with temporary air tubing, disconnect temporary tubing; lower full assembly into PVC; guide aligns base; screw base to lower deck through top holes with compact/right-angle driver; route and connect permanent air tubing after mounting.

## Step 7: Pneumatics

- Five **12 V** directional solenoid valves (historical 4V210-08, exact installed SKU VERIFY), mounted in **lower right chamber** under deck (rear view). Each has **two adjustable flow controls on exhaust ports** to tune extend/retract speed, 10 total.
- Separate **six-connection manifold**, **one compressor inlet and five valve outlets**, product reference https://www.amazon.com/dp/B0FCYNYHQF?tag=crackpotgumpt-20 .
- **1/4-in air tubing everywhere**: compressor to manifold, manifold to each valve, two lines from each valve to cylinder. Solenoid/port threads and push-fit adapters need physical verification.
- Compressor: quiet ~**2 SCFM at 90 PSI**, approximately **40 lb**, placed on factory feet on **left cabinet floor**. Regulate to approximately **25 PSI** using compressor's tool-outlet regulator; no second in-cabinet regulator. Alternative source should maintain about **30 PSI** under operating load.
- Threaded pneumatic connections used PTFE plumber's tape where appropriate, **not exhaust controls**; apply sealant only to compatible threads, follow manufacturer's guidance. Leak check with soap solution, sound and pressure drop. Never use tape on push-fit tubing to compensate for damaged fittings; cut tubing square and replace defective fittings.
- Some new valves/cylinders initially stuck at low pressure; user observed cycling at higher pressure sometimes freed them. **Do not prescribe pressure above any component's rating**. Investigate binding/flow/pressure first.
- Tune each valve using Arduino diagnostic sketch over **115200 baud** with commands `0`, `1`, `2`, `3`, `4`, `all`. Diagnostic reports extension/retraction peak accelerations relative to baseline and suggests restrictor adjustments; approximate tolerance +/-3000 units in prototype. **Arduino-only calibration; not Python.** Current source audit supersedes this interview description: see REPOSITORY_COMPARISON.md. The standalone diagnostic defaults to advice disabled; explicit references use a +/-50% band, not a verified +/-3000 tolerance.
- Air tubing and electrical wiring routed separately, no shared tie-downs.

## Step 8: Lighting

- Five LED collars with independently wired cut segments of **20 addressable 5V NeoPixels per collar**, 100 total, from Adafruit NeoPixel strip product #1460: https://www.adafruit.com/product/1460 . Removed weatherproof silicone sleeve.
- Each printed collar has strip channel and snap-in **matte white diffuser ring**, which locks strip mechanically. Rectangular wire outlet carries 5V, GND, data from inside to outside. Diffuser inserted by gently bending into doubled U and letting spring into lip; avoid bending at printed seam; stagger seams and print spares.
- Collars interference/friction fit into **8.5-in** cut holes; hot glue sometimes needed but **retain removability** for service. Chrome-painted collars reflect colored light; matte-white diffuser reduces glare but individual pixels may remain visible.
- Data each independent: Mega D14->ring0, D15->ring1, D16->ring2, D17->ring3, D18->ring4. Pigtails soldered to LED strips (~3 ft as-built), transitions via Wago-style connectors and/or numbered screw terminal rails; 18-22 AWG LED pigtails. Match local and Arduino-end data terminal numbering. Common 5V/GND deck buses.

## Step 9: Electrical and computer

- Arduino Mega connected to Linux host by USB, serial **115200**, **USB is Arduino's only power source**. Separate dedicated **5 V 10 A** supply https://www.amazon.com/dp/B0D76F4W1C?tag=crackpotgumpt-20 for NeoPixels, accelerometers, mux and solenoid-driver logic; separate dedicated **12 V 5 A** supply https://www.amazon.com/dp/B07GFFG1BQ?tag=crackpotgumpt-20 for valves and optional ticket dispenser. **Common grounds** among Arduino/5V/12V, positives not tied together.
- **Adafruit #6318 I2C 8-channel solenoid driver**, includes MCP23017 outputs, MOSFETs and flyback protection. Arduino Mega I2C pins SDA/SCL are 20/21 (also duplicated dedicated SDA/SCL header). No separate external MOSFET board needed.
- **TCA9548A 8-channel I2C multiplexer** for five MPU6050 boards, one on each channels **0-4**. MPU6050 product reference https://www.amazon.com/dp/B0F9DLNHTB?tag=crackpotgumpt-20 . Verify breakout voltage compatibility and I2C pullups before final wiring. Each accelerometer mounted identically; **MPU Y axis is physical vertical**.
- Mega + driver screwed/hot glued to PLA panel, panel double-sided taped to small-form-factor Linux PC case. TCA9548A on separate PLA plate hot-glued to right side of deck near access.
- Distribution blocks https://www.amazon.com/dp/B07CLW5FPS?tag=crackpotgumpt-20 screwed into framing: 6-channel master 5V, 6-channel master 12V, 12-channel master GND, 12-channel local deck 5V, 12-channel local deck GND. 18-AWG feeders to deck power buses. As-built no extra inline branch fuses; **recommend correctly rated branch fusing and safe enclosed mains wiring**.
- SFF PC on factory feet on right floor, next to electronics; 5V/12V supplies were loose as-built, **recommend securing for transport**. USB speakers double-sided taped inside deck. Rear felt cover Velcro. No dedicated cabinet fan; ran ~4-5h in AC environment without observed overheating; verify thermal performance in new environments.
- **Two separate external AC cords**: compressor direct to appropriately rated mains outlet, electronics to internal power strip. Never propose compressor on electronics strip. Avoid unsafe exposed mains terminals, use strain relief, approved enclosures, and qualified installation if needed.
- Linux Mint PC with Docker, systemd autostart, BIOS/UEFI restore-on-AC-power; automatically launches software into idle rainbow. Recommend graceful OS shutdown rather than simply cutting power.
- Moving sensor wiring has generous slack, fixed to moving guard, loops to nearby **stationary screw terminal**, then fixed wiring to mux and 5V/GND deck buses. Harnesses soldered/preassembled before install. Prototype used lever nuts, screw terminal rails, cable tie mounts and electrical tape.

## Step 10: Optional ticket dispenser

- DELTRONIC LABS DL-1275, optional, 12V/GND, motor control **Mega D22 blue**, ticket sensor **Mega D23 white** in prototype; verify colors/polarities against manufacturer and firmware. Front mounting plate ~4x4 in clips dispenser into plywood cutout and is secured with ~3/4-in screws. Two printed parts: saddle attaches to motor top with double-sided tape, collection bin superglued to saddle. Do not make ticket dispenser a dependency of public game.

## Step 11: Finishing

- Two rolled coats Glidden Spred Grab-N-Go black semi-gloss interior paint+primer; two coats Minwax Polycrylic Satin water-based finish https://www.lowes.com/pd/Minwax-Polycrylic-32-fl-oz-Satin-Water-based-Polyurethane/999913687 . Chrome vinyl decals and accents, Rust-Oleum Stops Rust Bright Chrome Metallic spray https://www.homedepot.com/p/Rust-Oleum-Stops-Rust-11-oz-Bright-Chrome-Metallic-Spray-Paint-7718830/100151050 ; Faber-Castell chrome acrylic paint marker https://www.michaels.com/product/fabercastell-chrome-acrylic-paint-marker-10812167 .
- Chrome arcade T-molding on top/front vertical edges. Prototype router/cutter combination cut T-slot too wide, barbs failed to hold; glued trim lips. Recommend correctly matched slotting cutter or purpose-built adhesive trim.

## Step 12: Standalone gameplay and software

# Generic Game and Software Specification

## Desired user experience
- On power restoration, Linux host boots, service/container launches automatically, Arduino connects, all 5 LED collars display continuous rainbow idle animation.
- **Normally-open momentary Start button** mounted at former RFID position on front panel. Wire spare Arduino Mega digital input to GND, firmware `INPUT_PULLUP`; pin TBD after source audit.
- Press Start: short configurable pre-game countdown; then 30-second round begins. Ignore repeated Start during countdown/game/game-over.
- At round start rings turn **solid red**. Select a random mole from 0-4; raise it; active ring **yellow**. Exactly **one scoring-active mole at a time**.
- Active mole has **1 second** to be hit (configurable). Correct hit = **+1 point**; active ring flashes **green twice**, nonblocking; command immediate retract and activate next mole. Timeout = retract without score, restore red, activate next mole.
- Next mole chosen uniformly from **other four indices**, NEVER same as previous, on hit or timeout.
- **Do not wait for previous cylinder to finish retracting** before commanding next raise; there is no end-of-stroke sensing. Two cylinders may briefly move at once. Python/firmware must suppress false positives caused by commanded motion and mechanical settling. Green flash must not delay transition.
- At 30 seconds, retract all moles, stop scoring, perform **brief configurable sequential LED ring chase** (speed, colors, cycles), announce final score using optional audio, then return to rainbow idle.
- Sounds for start, appearance, hit, game-over through optional prerecorded files played asynchronously by Python; no copyrighted/proprietary media included. Missing sound files should not crash gameplay.
- No penalties for misses. No required ticket dispenser, RFID, player badges, puzzle orders, character names, or six-player status strip.
- Expose settings: round length, active duration, countdown, colors, animations, hit threshold/cooldown, sound paths, serial port, optional features. Multi-mole/difficulty modes may be later extensions, not required for baseline.

## Architecture and validation
- Host: Linux Mint small-form-factor PC with Docker and systemd autostart. Python host handles state machine, timing, random choice, scoring, audio, motion-settling suppression, communication. Arduino Mega handles 5 valves via Adafruit #6318, 5 NeoPixel data lines, 5 MPU6050 sensors through TCA9548A, and button input.
- USB serial **115200 baud**. Need inspect actual repo's protocol and firmware before final implementation. Existing event firmware may stream `ACCEL` samples to Python; user specifically wants **Arduino-side hit event detection** for generalized game, which appeared more accurate in testing. Do not assume this already exists; implement/verify it.
- Vertical physical axis is **MPU6050 Y**, not MPU Z. User recalls threshold based on magnitude relative to resting baseline; audit source to determine real axis/sign/threshold/units. Direction, bounce, false-hit and sensor cooldown logic must be experimentally validated.
- Firmware calibration sketch over Arduino Serial Monitor at 115200 supports manual `0`, `1`, `2`, `3`, `4`, `all` to actuate and report extension/retraction acceleration peaks and suggest exhaust restrictor adjustments. Audit sketch; separate calibration and gameplay firmware if necessary.
- Index mapping:
```
           BACK
           3  4
         0  1  2
           FRONT
```
  Sensor mux channel = mole index 0-4; solenoid driver output = index 0-4; NeoPixel Mega data pins = D14 through D18 for index 0 through 4.
- Optional ticket dispenser: D22 motor and D23 pulse sensor historically; keep out of default path.

## Tests Codex should supply
- Mocked serial/sensors so state machine can be tested without hardware.
- Random selection never repeats previous target, including after timeouts.
- Only active mole can score, only once per appearance; hits during motion/settling ignored.
- Timeout transition is nonblocking; green flashes, sounds, chase don't block main loop.
- End-of-round retract-all and idle restoration even after serial errors (best effort); safe startup state valves de-energized.
- Start button debounce and repeated press handling.
- Hardware test procedure for each channel and its matching LED/sensor/valve.
- No assumption that solenoid de-energized direction is safe until actual valve configuration is verified.

## Existing repository
https://github.com/CrackpotGumption/mole_code — main. Historical names mentioned: `mole_game.py`, `app_standard_sensor_logging.py`, `whac_controller_accel_stream_watchdog.ino`, `app.py`. **These names and implementations are not audited in this package.** Preserve working event-specific software and build generic game separately.


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


## Step 13: Commission, calibrate and troubleshoot

Begin with air disconnected: verify power rails, common grounds, I2C addresses and each matching sensor/ring/output. Confirm the valve plumbing and de-energized direction before applying controlled low pressure. Never treat output readback as proof of cylinder travel.

Use the separate Arduino calibration sketch at 115200 baud with the Python controller stopped. Test 0..4 one at a time, then ALL. It measures a resting Y baseline and extension/retraction traces. This is an acceleration response index, not mm/s or an end-of-stroke measurement. Record traces, check clipping/read errors and compare repeatable loads before adjusting the two exhaust controls on each valve. LEFT/RIGHT wording is orientation-dependent; identify which exhaust serves each direction physically. No fabricated end-position feedback is available.

For sticky movement check guide alignment, loads, fittings, leaks and flow controls within ratings. For false hits inspect sensor mount, wiring slack, neighbor motion, settling time, threshold and cooldown. For missing channels check mux/power/wiring with power isolated. For lighting verify direction of data, pixel count, power and ground. Test thermal performance in the intended room.

Acceptance run: countdown and repeated Start presses; correct hit +1 once; inactive hit no score; timeout without penalty; no consecutive target repetition; nonblocking green flashes/audio; round ends at 30 seconds and retracts all; chase returns to rainbow; controlled serial loss shuts outputs down as best effort. Hardware checks remain TODO.

## Step 14: Photos, downloads and remaining work

# Photo Manifest

These are original photos provided by the user. Filenames retained. Use as build documentation; no stock photos needed. The filenames below describe intended placements, not a guaranteed interpretation of every object in frame.

| File | Suggested use |
|---|---|
| `photos/5309.jpg` | Frame pieces and playfield openings |
| `photos/5310.jpg` | Cabinet framing and uprights |
| `photos/5420.jpg` | Batch pneumatic deck assembly and flange work |
| `photos/5468.jpg` | Rear interior / pneumatic deck and mounts |
| `photos/5469.jpg` | Assembled raw cabinet on casters |
| `photos/5473.jpg` | Cabinet surface preparation and seam filling |
| `photos/5501.jpg` | Multiple cabinets, rear access, interior wiring and plumbing |
| `photos/5507.jpg` | Nearly completed exterior without final decoration |
| `photos/5509.jpg` | Finished cabinet, three-quarter view and illuminated rings |
| `photos/5527.jpg` | Finished cabinet with decorated moles, potential cover image |

Additional photos `5498.jpg`, `5508.jpg`, `5550.jpg`, `5551.jpg` exist in conversation workspace but were not explicitly mapped to these build steps; excluded from handoff to avoid accidental misuse. Request if relevant.

When editing images for publication, preserve factual depiction of the original machine; crop/annotate rather than invent hardware. The user plans to supply close-up teardown photos later.


# Owner TODO list

Before the build can be reproduced:
- [ ] Add master Bambu .3mf; identify final production plates, discard prototypes from exports, preserve solid-infill modifiers.
- [ ] Photograph removed mechanism front/back, screw-on puck and captured nut, cylinder base, U-guard and sensor, collar/diffuser, decoration adapter, moving wire loop, numbered terminals, valves/exhaust controls and manifold.
- [ ] Count LEDs on each installed ring: handoff says 20, firmware says 21.
- [ ] Measure cabinet panel overlaps, bottom/front panels, pneumatic deck height and offset; confirm cut list before cutting diagrams are finalized.
- [ ] Record cylinder rod/base thread and nut sizes, valve installed SKU, port labels, fitting threads, flange SKU, compressor model and all component pressure ratings.
- [ ] Identify MPU6050 board and voltage/pullup compatibility; photograph both sides and wiring.
- [ ] Choose Start button diameter/model; confirm proposed Mega D24 is unused.
- [ ] Confirm physical 0..4 sensor/valve/ring mapping and de-energized cylinder direction with controlled air tests.
- [ ] Test Y-based hit thresholds, false triggers during both directions and neighboring movement, settling delay and cooldown.
- [ ] Export final printable parts with profiles and document material, walls, layers, orientation/supports, modifiers, quantities and print time.
- [ ] Add a short gameplay video and a clean cover photo if available.

Before publishing:
- [ ] Review every VERIFY/TODO in draft; replace assumptions with measurements or explicitly keep limitations.
- [ ] Review mains enclosure/strain relief/grounding/fusing, transport restraint, thermal checks and pressure-release procedure.
- [ ] Verify standalone game on cabinet: Start debounce, no-repeat timeout/hit transitions, 30s stop, disconnect/reconnect, no-air diagnostics, and reliable scoring.
- [ ] Approve photo captions and project-owner attribution; confirm availability/license for software and print downloads.
- [ ] Confirm current contest eligibility/deadline in Instructables before entering; saving a draft is not contest entry.

Agent work remaining: final editable cut/wiring/pneumatic diagrams after measurements, final downloadable print pack after .3mf, standalone firmware compilation and hardware validation, publication polish.


# Outstanding Assets, Verification and Publication Caveats

## Awaiting user
1. Master Bambu Studio `.3mf` project: **one large project with many plates**, including older prototypes and final parts; some parts use local modifier regions for solid infill. Need identify final production plates and preserve modifiers. No 3MF/STL provided in this handoff.
2. Disassembly photographs later in week: full removed mole mechanism, both sides, retainer puck/nut, U-guard/sensor, base mount, LED collar/diffuser, valve/exhaust controls, manifold, numbered terminals, moving-wire service loops, decorative adapter and retention.
3. Exact printed-body infill, walls, layer heights, orientations, support settings and modifier volumes from 3MF.
4. Start button diameter/model and chosen spare Mega pin; can be selected during code/wiring audit.
5. Optional original assembly measurements if contradictions arise during drawing.

## Codex research/audit
- Clone/review `CrackpotGumption/mole_code` main; identify firmware and calibration files, true hit detection and valve command protocol, actual I2C addresses and pin mapping, safe power-up valve states.
- Verify MPU6050 breakout's 5V power input and 3.3V logic, proper I2C pullups/level compatibility; the raw MPU6050 IC is not 5V tolerant.
- Verify solenoid driver #6318 wiring, coil power paths and flyback ratings from manufacturer.
- Verify pneumatic valve port labels (P/A/B/R/S), exhaust flow controls, fitting threads, cylinder specs and pressure limits.
- Confirm exact panel overlaps and framing geometry before final dimensioned diagrams.
- Do not fabricate any missing 3D files, test results, electrical schematics or links to assets.
- Make public article self-contained but clearly label any unverified hardware detail. Distinguish what was **built and tested** from recommended upgrades.

## Safety and robustness
- Compressor and electronics **two external cords**, compressor directly into correctly rated outlet.
- Isolate mains, depressurize and disconnect power before servicing. Provide a controlled method to vent trapped pressure; beware automatic compressor restart and moving rods.
- Do not instruct overpressurizing sticky cylinders to force them free.
- Protect fingers around moving moles and avoid sharp/hard decorations; no hard impact surfaces.
- Supply branch fuses, cable strain relief, enclosed mains terminals, secure heavy equipment, ventilation/heat checks, graceful Linux shutdown are **publication recommendations**, not necessarily as-built.
- No dedicated emergency stop in prototype; do not imply one existed.


## Independent software status

The separate software/ directory now includes recreated standalone Mega firmware and Python host/game, plus a de-themed calibration sketch. Six mocked state-machine tests pass. Arduino compilation and hardware validation remain unverified. New Y-only threshold/settling defaults are provisional. See software/README.md. The online draft is an eight-step condensation of this source and remains unpublished.
