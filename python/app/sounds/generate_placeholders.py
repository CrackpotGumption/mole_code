"""Regenerate synthetic stand-ins; replace WAVs with final cabinet recordings."""
import math
from pathlib import Path
import struct
import wave

RATE = 22050
ROOT = Path(__file__).parent


def write(name, seconds, voice):
    with wave.open(str(ROOT / f'{name}.wav'), 'wb') as target:
        target.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        samples = []
        for index in range(int(seconds * RATE)):
            t = index / RATE
            fade = min(1, t / 0.015, (seconds - t) / 0.03)
            samples.append(struct.pack('<h', int(voice(t) * fade * 7000)))
        target.writeframes(b''.join(samples))


if __name__ == '__main__':
    write('game_start', 0.45, lambda t: math.sin(2 * math.pi * (440 + int(t / 0.15) * 220) * t))
    write('mole_hit', 0.18, lambda t: math.sin(2 * math.pi * (600 * t - 900 * t * t)) * math.exp(-t * 15))
    write('failure', 0.6, lambda t: math.sin(2 * math.pi * (350 * t - 150 * t * t)))
    for number in range(1, 4):
        # Rhythmic, pitch-modulated synthetic cackles, not human laugh recordings.
        frequency = 170 + number * 95
        speed = 3.5 + number
        write(f'laugh_{number}', 1.4, lambda t, f=frequency, speed=speed:
              math.sin(2 * math.pi * f * t + 2 * math.sin(t * 30))
              * max(0, math.sin(2 * math.pi * speed * t)) ** 2)
