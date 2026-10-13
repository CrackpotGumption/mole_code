# Whack-a-Mole Arcade — Codex Implementation Handoff

This package captures the user's design interview for a reproducible, public-facing Instructables article about a finished five-mole pneumatic arcade cabinet. **This is a project specification, not a transcript or a claim that the published page/software is complete.**

## Goal
Create an excellent, detailed Instructables-style build article for a customizable pneumatic whack-a-mole machine, with clear steps, cut diagrams, pneumatic/electrical schematics, print-file distribution, BOM, and generic playable Arduino/Python software. The finished build used four cabinets with event-specific bug puppets and RFID puzzles; the public article must teach **one standalone cabinet**, using a Start button and simple 30-second scoring game. Optional extras (ticket dispenser, RFID, linked cabinets) may be described separately, never required.

## Contents
- `CODEX_TASK.md`: concrete instructions and implementation order for Codex
- `BUILD_SPEC.md`: dimensions, woodworking, mechanics, pneumatics, electronics, finishing, as-built lessons
- `GAME_AND_SOFTWARE.md`: generic gameplay specification, architecture and code audit requirements
- `BOM.md`: parts, quantities, source references, unresolved specs
- `PHOTO_MANIFEST.md` and `photos/`: user-provided build and finished-product photographs
- `OPEN_ITEMS.md`: verification tasks, missing assets, and accuracy/safety constraints

## Existing code
Repository: https://github.com/CrackpotGumption/mole_code (main branch). **Not cloned or audited for this package.** Codex should inspect the actual repository before claiming code paths, pin definitions, or firmware behaviors are verified. Never overwrite event-specific working software without an explicit migration plan; implement the generalized game in a distinct directory or branch.

## Source fidelity
All dimensions and behaviors below are interview-derived. Treat dimensions marked approximate as approximate. Cross-check drawings against the eventual Bambu Studio 3MF and physical measurements. The user's original master Bambu 3MF has many plates and prototypes and has **not** been provided yet. No actual slicer settings were extracted.

## Getting started
1. Unzip into a Codex workspace or place alongside the cloned GitHub repo.
2. Give Codex the prompt in `CODEX_TASK.md`.
3. Have Codex create the article structure and asset plan first, then diagrams, software and verified BOM.
4. Add the master `.3mf` and disassembly photographs when available.
