# Replaceable audio placeholders

These are synthetic stand-ins, not final human laugh recordings:

- `game_start.wav`: rising start cue, played when a badge's puzzle becomes ready.
- `mole_hit.wav`: strike cue for an accepted hit, correct or wrong.
- `failure.wav`: descending failure cue.
- `ouch_1.wav`, `ouch_2.wav`, `ouch_3.wav`: comic reaction placeholders,
  interrupting laughter when a failure-show mole is hit. Replace with final
  DO'OH/OUCH recordings; their file durations control replacement timing.
- `laugh_1.wav`, `laugh_2.wav`, `laugh_3.wav`: distinct synthetic cackle patterns.

Replace the WAV files with recordings using the same names. Required format:
mono, 16-bit PCM, 22050 Hz. Rebuild the container to package them. Alternatively,
mount a replacement sounds directory and set `AUDIO_DIR` to its container path.
Keep individual cues short; the failure mixer overlays all three laughs and
randomly repeats them over `FAILURE_SECONDS`.

Regenerate these originals with `python generate_placeholders.py`.

Victory placeholders:
- `victory.wav`: winning chord.
- `cheer.wav`: synthetic cheering stand-in.
- `whistle.wav`: celebration whistle.
- `kiss.wav`: synthetic "oooooo"/kiss stand-in.
- `encouraging_whistle.wav`: interrupts the victory mix on a bash; its duration
  controls when a replacement mole rises and cheering resumes.

These are synthesized cues for wiring/testing; replace with final human
cheering and vocal recordings in the same WAV format.
