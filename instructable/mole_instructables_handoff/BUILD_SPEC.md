# Build Specification — Interview-Derived

## Overall cabinet and geometry
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

## Cabinet 2x2 structure
- Nominal framing cut list: **6 x 36 in; 6 x 31.5 in; 5 x 19.5 in**.
- Top and bottom rectangles approximately **36 x 22.5 in**; centered 19.5-in bottom crossmember; six 31.5-in verticals at corners and centers of 36-in edges. Two additional 36-in interior horizontal rails about 15 in below upper rails support pneumatic deck.
- 19.5-in members pocket-screwed between 36-in members; other 2x2 joints with 2.5-in screws. Plywood secured from inside with 2-in screws. As-built no wood glue for potential disassembly; recommend glue for permanent cabinet.
- Front panel is 36 in wide x ~35.25 in high; side panels 24 x 36 in. Confirm final edge overlap and trim dimensions in drawing; do not force an inconsistent cut plan.

## Removable pneumatic deck
- Standalone box frame, nominal **36 in W x 19.2 in D**. Cut list: **4 x 36 in; 2 x 33 in; 4 x 16.2 in; 4 x 8 3/8 in** 2x2s. Two rectangular levels with centered 33-in crossmembers, four short uprights.
- Upper and lower **36 x 19.2 x 3/4 in** plywood sheets. Bottom solid. Top five approximately **4.25-in** flange openings, coordinates (depth,left) inches: (3.75,6), (3.75,18), (3.75,30), (15.75,12), (15.75,24).
- Deck installed about **2.25 in toward rear** relative to playfield. ~1/4-in front/back adjustment during alignment. Screw deck to support rails and tie deck columns to cabinet columns.
- Rear/front service gaps approximately 1.5 in allow wiring routes.

## PVC guides and flange
- **Five** closet flanges for nominal **3-in Schedule 40 PVC** (historically Oatey Level-Fit), each solvent-welded to a **2-in long** PVC segment with suitable primer/cement. Flange drops from **above** into deck upper-panel hole, flange rim sits on upper plywood, secured by **1-in wood screws**. PVC pipe extends **down below the upper plywood**, not up.
- Mole body's long cylindrical printed guide remains engaged in PVC throughout 75-mm stroke. Paint on exposed flange as desired.

## Pneumatic actuator and printed mechanical stack
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

## Pneumatics
- Five **12 V** directional solenoid valves (historical 4V210-08, exact installed SKU VERIFY), mounted in **lower right chamber** under deck (rear view). Each has **two adjustable flow controls on exhaust ports** to tune extend/retract speed, 10 total.
- Separate **six-connection manifold**, **one compressor inlet and five valve outlets**, product reference https://www.amazon.com/dp/B0FCYNYHQF?tag=crackpotgumpt-20 .
- **1/4-in air tubing everywhere**: compressor to manifold, manifold to each valve, two lines from each valve to cylinder. Solenoid/port threads and push-fit adapters need physical verification.
- Compressor: quiet ~**2 SCFM at 90 PSI**, approximately **40 lb**, placed on factory feet on **left cabinet floor**. Regulate to approximately **25 PSI** using compressor's tool-outlet regulator; no second in-cabinet regulator. Alternative source should maintain about **30 PSI** under operating load.
- Threaded pneumatic connections used PTFE plumber's tape where appropriate, **not exhaust controls**; apply sealant only to compatible threads, follow manufacturer's guidance. Leak check with soap solution, sound and pressure drop. Never use tape on push-fit tubing to compensate for damaged fittings; cut tubing square and replace defective fittings.
- Some new valves/cylinders initially stuck at low pressure; user observed cycling at higher pressure sometimes freed them. **Do not prescribe pressure above any component's rating**. Investigate binding/flow/pressure first.
- Tune each valve using Arduino diagnostic sketch over **115200 baud** with commands `0`, `1`, `2`, `3`, `4`, `all`. Diagnostic reports extension/retraction peak accelerations relative to baseline and suggests restrictor adjustments; approximate tolerance +/-3000 units in prototype. **Arduino-only calibration; not Python.** Verify exact sketch before documenting algorithm.
- Air tubing and electrical wiring routed separately, no shared tie-downs.

## Lighting
- Five LED collars with independently wired cut segments of **20 addressable 5V NeoPixels per collar**, 100 total, from Adafruit NeoPixel strip product #1460: https://www.adafruit.com/product/1460 . Removed weatherproof silicone sleeve.
- Each printed collar has strip channel and snap-in **matte white diffuser ring**, which locks strip mechanically. Rectangular wire outlet carries 5V, GND, data from inside to outside. Diffuser inserted by gently bending into doubled U and letting spring into lip; avoid bending at printed seam; stagger seams and print spares.
- Collars interference/friction fit into **8.5-in** cut holes; hot glue sometimes needed but **retain removability** for service. Chrome-painted collars reflect colored light; matte-white diffuser reduces glare but individual pixels may remain visible.
- Data each independent: Mega D14->ring0, D15->ring1, D16->ring2, D17->ring3, D18->ring4. Pigtails soldered to LED strips (~3 ft as-built), transitions via Wago-style connectors and/or numbered screw terminal rails; 18-22 AWG LED pigtails. Match local and Arduino-end data terminal numbering. Common 5V/GND deck buses.

## Electrical and computer
- Arduino Mega connected to Linux host by USB, serial **115200**, **USB is Arduino's only power source**. Separate dedicated **5 V 10 A** supply https://www.amazon.com/dp/B0D76F4W1C?tag=crackpotgumpt-20 for NeoPixels, accelerometers, mux and solenoid-driver logic; separate dedicated **12 V 5 A** supply https://www.amazon.com/dp/B07GFFG1BQ?tag=crackpotgumpt-20 for valves and optional ticket dispenser. **Common grounds** among Arduino/5V/12V, positives not tied together.
- **Adafruit #6318 I2C 8-channel solenoid driver**, includes MCP23017 outputs, MOSFETs and flyback protection. Arduino Mega I2C pins SDA/SCL are 20/21 (also duplicated dedicated SDA/SCL header). No separate external MOSFET board needed.
- **TCA9548A 8-channel I2C multiplexer** for five MPU6050 boards, one on each channels **0-4**. MPU6050 product reference https://www.amazon.com/dp/B0F9DLNHTB?tag=crackpotgumpt-20 . Verify breakout voltage compatibility and I2C pullups before final wiring. Each accelerometer mounted identically; **MPU Y axis is physical vertical**.
- Mega + driver screwed/hot glued to PLA panel, panel double-sided taped to small-form-factor Linux PC case. TCA9548A on separate PLA plate hot-glued to right side of deck near access.
- Distribution blocks https://www.amazon.com/dp/B07CLW5FPS?tag=crackpotgumpt-20 screwed into framing: 6-channel master 5V, 6-channel master 12V, 12-channel master GND, 12-channel local deck 5V, 12-channel local deck GND. 18-AWG feeders to deck power buses. As-built no extra inline branch fuses; **recommend correctly rated branch fusing and safe enclosed mains wiring**.
- SFF PC on factory feet on right floor, next to electronics; 5V/12V supplies were loose as-built, **recommend securing for transport**. USB speakers double-sided taped inside deck. Rear felt cover Velcro. No dedicated cabinet fan; ran ~4-5h in AC environment without observed overheating; verify thermal performance in new environments.
- **Two separate external AC cords**: compressor direct to appropriately rated mains outlet, electronics to internal power strip. Never propose compressor on electronics strip. Avoid unsafe exposed mains terminals, use strain relief, approved enclosures, and qualified installation if needed.
- Linux Mint PC with Docker, systemd autostart, BIOS/UEFI restore-on-AC-power; automatically launches software into idle rainbow. Recommend graceful OS shutdown rather than simply cutting power.
- Moving sensor wiring has generous slack, fixed to moving guard, loops to nearby **stationary screw terminal**, then fixed wiring to mux and 5V/GND deck buses. Harnesses soldered/preassembled before install. Prototype used lever nuts, screw terminal rails, cable tie mounts and electrical tape.

## Optional ticket dispenser
- DELTRONIC LABS DL-1275, optional, 12V/GND, motor control **Mega D22 blue**, ticket sensor **Mega D23 white** in prototype; verify colors/polarities against manufacturer and firmware. Front mounting plate ~4x4 in clips dispenser into plywood cutout and is secured with ~3/4-in screws. Two printed parts: saddle attaches to motor top with double-sided tape, collection bin superglued to saddle. Do not make ticket dispenser a dependency of public game.

## Finishing
- Two rolled coats Glidden Spred Grab-N-Go black semi-gloss interior paint+primer; two coats Minwax Polycrylic Satin water-based finish https://www.lowes.com/pd/Minwax-Polycrylic-32-fl-oz-Satin-Water-based-Polyurethane/999913687 . Chrome vinyl decals and accents, Rust-Oleum Stops Rust Bright Chrome Metallic spray https://www.homedepot.com/p/Rust-Oleum-Stops-Rust-11-oz-Bright-Chrome-Metallic-Spray-Paint-7718830/100151050 ; Faber-Castell chrome acrylic paint marker https://www.michaels.com/product/fabercastell-chrome-acrylic-paint-marker-10812167 .
- Chrome arcade T-molding on top/front vertical edges. Prototype router/cutter combination cut T-slot too wide, barbs failed to hold; glued trim lips. Recommend correctly matched slotting cutter or purpose-built adhesive trim.
