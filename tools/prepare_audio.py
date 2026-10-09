"""Normalize cabinet audio assets at image build time; preserve source files."""
from pathlib import Path
import subprocess
import sys


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    for category in ('hit', 'laugh', 'cheer', 'victory'):
        paths = sorted((source / category).glob('*'))
        if category == 'cheer':
            paths += sorted((source / 'cheers').glob('*'))
        for index, path in enumerate(paths):
            if path.suffix.lower() not in ('.wav', '.mp3', '.ogg', '.flac'):
                continue
            output = destination / category / f'{index:03d}-{path.stem}.wav'
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(path),
                            '-ac', '1', '-ar', '22050', '-c:a', 'pcm_s16le', str(output)], check=True)


if __name__ == '__main__':
    prepare(*sys.argv[1:])
