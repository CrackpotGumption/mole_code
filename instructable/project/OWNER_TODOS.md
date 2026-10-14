# Owner TODO list

Drawing review: plywood 01–03, corrected terminal-level wiring 06–08 and pneumatic 09–10 approved October 14. Sheets 04–05 are superseded summaries. Dedicated 5 V supply routing for driver, mux and sensor breakouts is confirmed. Remaining agent work is integrating approved diagrams and consolidating repeated/stale draft text.

- [x] Owner selected MIT for standalone software and CC BY 4.0 for the creator's print files, article and photos. License notices are in LICENSES.txt, software/LICENSE and prints/LICENSE.txt.

Photo placeholders are now present in the unpublished draft for the removed mechanism, sensor mount, moving wiring and pneumatic connections. Replace them with the requested photos. Step 8 has a ten-row testing-results template; fill it with observed results. Owner selected MIT for standalone software and CC BY 4.0 for prints and content; notices are applied.

Reviewed October 14, 2026 against the live Instructables preview, current BOM, build steps, original hardware notes and production print inventory. The live draft has 26 Amazon product links tagged crackpotgum00-20, two Adafruit product links, the production 3MF and seven software/setup downloads. Non-Amazon links do not need the Amazon tag.

## Next owner actions, in priority order

Exact finish products are not an owner TODO. Use generic finish/adhesive descriptions. WAGO 221-412 connectors and zip-tie mounts now have owner-supplied links; quantities are as needed.

Host computer resolved: use any suitable computer with USB power/data for the Mega, speaker support and Python capability. The owner supplied a used-workstation example link; no exact model is required.

1. Compressor identified as FORTRESS item 64596; exhaust controls identified as Pneuforce BESL-01. Both supplier links are added online. Builder confirms that each valve's default, de-energized state sends air to the top of its associated cylinder. No additional pneumatic hardware is reported beyond the already linked push-to-connect fittings and cylinder fittings. A plumbing photo can support the diagram without requiring a separate port-marking investigation.
2. Flange resolved: Oatey Fast Set 435032; pipe resolved: Charlotte Pipe 3-inch Schedule 40, cut into five 2-inch sleeves. Captured nuts and pneumatic thread tape are supplied with the purchased pneumatic parts. No separate nuts or tape purchase is needed.
3. LED count confirmed: 19 per collar, 95 total. Suggested Start button is Twidec B08JHVLK84, normally-open momentary, listed 16 mm variant; measure the received switch before drilling. Use Mega D24 as the Start input. Photograph both sides of the MPU6050 breakout and its connections.
4. Plate-5 roles are confirmed: 6 cylinder bottom-to-deck mount; 22 rod-to-body mount/puck; 10 main body; 15 U-channel guard/sensor mount with pin-clearance negative cube. Remaining print work: material/color and slicer review, quantities and material/time estimates.
5. Plywood cuts, hole centers and deck positioning are provided. Produce the cutting/hole drawings and sheet layout from those measurements; this is agent work, not another owner measurement request.
6. Provide the missing purchase links or specifications listed in UNLINKED_PARTS.md. Hardware-store and manufacturer links are acceptable.
7. Photograph the removed mechanism, captured nuts, sensor mount, moving wiring loop, terminals, valves/flow controls and manifold. Add a short video of the standalone build when tested.
8. Test the standalone software on the cabinet: channel mapping/direction, hit calibration, neighboring movement, repeated Start, one score per appearance, round end and serial disconnect/reconnect. Record results.
9. Review captions/attribution and choose licenses for the print files and standalone software. Keep the affiliate disclosure. Check contest requirements only if you decide to enter one.

Before the build can be reproduced:
- [x] Add master Bambu .3mf: instructable/mole_assembly_final.3mf received and inventoried.
- [x] Confirm six plates/ten objects are final production: owner confirms cleaned final production set.
- [x] Attach the production 3MF to the unpublished Instructables draft.
- [x] Add and validate all supplied Amazon links with tag=crackpotgum00-20 and an affiliate disclosure.
- [x] Confirm the included cylinder fittings work with the linked tubing in the completed build.
- [x] Identify all four plate-5 roles. Preserve object 22's solid-infill modifier and object 15's sensor-pin-clearance negative volume.
- [ ] Photograph removed mechanism front/back, screw-on puck and captured nut, cylinder base, U-guard and sensor, collar/diffuser, decoration adapter, moving wire loop, numbered terminals, valves/exhaust controls and manifold.
- [x] Owner confirms 19 LEDs per collar, 95 total; standalone firmware default updated to 19.
- [x] Supply panel cuts, hole locations and deck positioning. The deck is centered between the cabinet rails; each hole layout is measured from its own panel’s front-left corner. Differing depth coordinates account for the different origins. Supports are about 15 inches below the upper rails.
- [x] Identify flange, pipe, captured nuts, thread tape, compressor, valves, cylinders, exhaust controls and push-to-connect fittings.
- [x] Confirm plywood panel cuts; see PLYWOOD_CUT_LIST.md.
- [x] Identify panel screws and caster placement: Grip-Rite 2GCS1 2-inch screws for 2×2-to-plywood and caster-to-rail connections; ¾-inch screws on the caster's other side. Four Harbor Freight 61855 casters about 1 inch inset from corners. 2½-inch screws are for 2×2-to-2×2 joints.
- [ ] Complete sheet layout and final fastener quantities.
- [ ] Identify MPU6050 board and voltage/pullup compatibility; photograph both sides and wiring.
- [x] Provide a suggested Start button: Twidec B08JHVLK84, normally-open momentary, listed 16 mm variant.
- [x] D24 is the Start-button pin.
- [ ] Measure the received button before cutting its mounting hole.
- [ ] Confirm physical 0..4 sensor/valve/ring mapping and de-energized cylinder direction with controlled air tests.
- [ ] Test Y-based hit thresholds, false triggers during both directions and neighboring movement, settling delay and cooldown.
- [ ] Confirm saved profiles match intended production: extracted defaults/overrides are in prints/PRINT_INVENTORY.md. Resolve football-adapter settings discrepancy and diffuser color; validate orientation/supports, then export the final pack and record quantities/time.
- [ ] Add a short gameplay video and a clean cover photo if available.

Before publishing:
- [ ] Review every VERIFY/TODO in draft; replace assumptions with measurements or explicitly keep limitations.
- [ ] Review mains enclosure/strain relief/grounding/fusing, transport restraint, thermal checks and pressure-release procedure.
- [ ] Verify standalone game on cabinet: Start debounce, no-repeat timeout/hit transitions, 30s stop, disconnect/reconnect, no-air diagnostics, and reliable scoring.
- [x] Owner supplied the corrected Amazon Store ID crackpotgum00-20; all 26 online Amazon links verified with it. Retain the affiliate disclosure.
- [ ] Approve photo captions and project-owner attribution; confirm availability/license for software and print downloads.
- [ ] Confirm current contest eligibility/deadline in Instructables before entering; saving a draft is not contest entry.

Agent work remaining: final editable cut, wiring and pneumatic diagrams after measurements; update plate-role labels after owner confirmation; integrate cabinet-test results; final publication polish.

Publication boundary: mention only that the cabinet ran custom game logic for an event; disclose no further details, original code or repository links. See PUBLICATION_RULES.md.
