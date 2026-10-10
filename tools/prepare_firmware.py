"""Stage the repository sketch with an exact source identity for compilation."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

NAME = 'MOLE_FINAL_NO_INTERVAL_v2'
VERSION = '3.0.5'

def prepare(source, destination):
    source = Path(source)
    destination = Path(destination)
    sketch = destination / NAME
    sketch.mkdir(parents=True, exist_ok=True)
    data = (source / f'{NAME}.ino').read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    shutil.copy2(source / f'{NAME}.ino', sketch)
    (sketch / 'firmware_identity.h').write_text(
        f'#define MOLE_SKETCH_NAME "{NAME}"\n#define MOLE_SKETCH_VERSION "{VERSION}"\n'
        f'#define MOLE_SOURCE_SHA256 "{digest}"\n')
    manifest = {'name': NAME, 'version': VERSION, 'sha256': digest, 'board': 'arduino:avr:mega',
                'toolchain': {'arduino_cli': '1.2.2', 'avr_core': '1.8.6',
                              'Adafruit BusIO': '1.17.4', 'Adafruit NeoPixel': '1.12.3',
                              'Adafruit MCP23017 Arduino Library': '2.3.2', 'MFRC522': '1.4.12'}}
    (destination / 'manifest.json').write_text(json.dumps(manifest) + '\n')
    return manifest

if __name__ == '__main__':
    prepare(sys.argv[1], sys.argv[2])
