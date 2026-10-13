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
