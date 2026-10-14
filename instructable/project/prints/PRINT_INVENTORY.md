# Saved 3MF print inventory

Source: [mole_assembly_final.3mf](../../mole_assembly_final.3mf). Original archive preserved unchanged.

This records saved configuration, not proof of historical print settings or a validated print recommendation. Owner confirms this is the cleaned final production set: all six plates and ten objects are production parts. The owner identified all four plate-5 roles on October 14, 2026. No sliced G-code, measured print times or material-use totals are included.

## Confirmed plate-5 roles — mole_base_plate

| Object | Filename | Physical role |
|---|---|---|
| 6 | MAL16_mounting_plate_test(4).stl 5 2 | Cylinder bottom-to-deck mount. Captures the larger cylinder hex nut and provides countersunk screw holes for fastening to the plywood deck base. |
| 22 | piston_mount_non_hex_countersinks.stl | Cylinder rod-to-mole-body mount/retainer puck. Captures the piston-rod hex nut and screws to the mole body's flat platform. Preserve its local 100% infill modifier. |
| 10 | mole_bottom_rebuilt_true_cylinders_73p2mm.stl 3 | Main mole body. Its cylindrical guide remains inside the nominal 3-inch PVC sleeve; the flat top platform accepts decorations. |
| 15 | pneumatic_mount_4_COUNTERSUNK_UNDERSIDE_PUCK_ONLY_v21.stl | U-channel anti-rotation guard and accelerometer mount. Despite the filename, it is not the puck. The negative cube creates clearance for the sensor pins so they can float freely without interfering with the mount or glue. |

## Project defaults

- Printer: Bambu Lab P1S; 0.4 mm nozzle.
- Filament preset: Generic PLA (saved black color; diffuser color needs separate selection).
- Layer height: 0.20 mm; first layer: 0.20 mm.
- Walls: 3; top shells: 5; bottom shells: 3.
- Sparse infill: 15% grid.
- Supports disabled globally; automatic brim configured.

## Plates and saved object settings

| Plate | Objects | Overrides / important volumes |
|---|---|---|
| 1 — arduino_base | mega_breadboard_holder_2x_terminal(1).stl | Project defaults |
| 2 — light_diffuser | mole_collar_diffuser_ring(5).stl | Project defaults |
| 3 — mole_collar | mole_collar_70mm_led(8).stl | mole_collar_70mm_led(8).stl: layer_height=0.24, sparse_infill_density=15%, sparse_infill_pattern=zig-zag, wall_loops=2 |
| 4 — mount_football_mount | mole_2_A_clean_cylindrical_base.stl | Project defaults |
| 5 — mole_base_plate | MAL16_mounting_plate_test(4).stl 5 2<br>mole_bottom_rebuilt_true_cylinders_73p2mm.stl 3<br>pneumatic_mount_4_COUNTERSUNK_UNDERSIDE_PUCK_ONLY_v21.stl<br>piston_mount_non_hex_countersinks.stl | MAL16_mounting_plate_test(4).stl 5 2: sparse_infill_density=20%, sparse_infill_pattern=gyroid, wall_loops=5<br>mole_bottom_rebuilt_true_cylinders_73p2mm.stl 3: sparse_infill_density=10%<br>pneumatic_mount_4_COUNTERSUNK_UNDERSIDE_PUCK_ONLY_v21.stl: negative_part Generic-Cube<br>piston_mount_non_hex_countersinks.stl: wall_loops=6<br>piston_mount_non_hex_countersinks.stl: modifier_part Generic-Cylinder — 100% infill |
| 6 — ticket_bin | ticket_bin_165mm_internal.stl<br>ticket_saddle_7mm_sidewalls.stl | Project defaults |

## Corrections to the interview notes

- Saved 100% infill modifier belongs to the rod-to-body mount (object 22), which also has six walls.
- The U-channel guard/sensor mount (object 15) includes a negative cube for accelerometer-pin clearance. Exporting its unmodified mesh would not reproduce the sliced geometry.
- Plate 4’s named football mount has no per-object override: saved settings inherit 15% grid and three walls, rather than the interview’s approximately 20% rectilinear/five walls. Do not equate the current saved project with historical print conditions.
- MAL16 mounting plate (object 6) explicitly uses 20% gyroid and five walls.
- Main body object 10 uses 10% infill. Collar object 8 uses 0.24 mm layers, two walls and 15% zig-zag sparse infill.
- Diffuser inherits Generic PLA black in the file, while the as-built diffuser was matte white. Select the intended material/color before slicing.

## Next checks

- All plates/objects and the four plate-5 physical roles are confirmed by the owner.
- Inspect assembled fits using the nuts supplied with the linked cylinders, repurposed as captured nuts for the wood/printed mounts. No separate nut purchase is needed.
- Preserve negative and modifier volumes in any simplified production 3MF.
- Verify orientations, support needs and actual sliced geometry in Bambu Studio.
- Release the verified production 3MF first; export STLs only when negative volumes have been applied and modifier requirements are separately documented.
