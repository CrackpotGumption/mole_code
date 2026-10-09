"""Validate and update the Mega before the game takes ownership of hardware."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from app.control_state import read, write


class FirmwareMismatch(RuntimeError):
    pass


def identity_line(manifest):
    return 'FIRMWARE {name} {version} {sha256}'.format(**manifest)


def run(command):
    try:
        result = subprocess.run(command, check=True, timeout=180, capture_output=True, text=True)
        print(result.stdout[-8192:])
        print(result.stderr[-8192:])
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f'Firmware tool failed (exit {error.returncode}): {(error.stderr or error.stdout or str(error))[-4096:]}') from error


def history_path():
    return Path(os.environ.get('FIRMWARE_HISTORY_PATH',
                str(Path(os.environ.get('GAME_LOG_PATH', '/data/game-events.jsonl')).parent / 'firmware-history.json')))


def connect_verified(controller_factory, port, baud, on_status=None, force_flash=False):
    bundle = Path(os.environ.get('FIRMWARE_DIR', '/opt/mole-firmware'))
    temporary = None
    try:
        if not (bundle / 'manifest.json').exists():
            root = Path(__file__).resolve().parents[2]
            helper = root / 'tools/prepare_firmware.py'
            if not helper.exists():
                raise RuntimeError('Firmware bundle missing; rebuild the cabinet image')
            spec = importlib.util.spec_from_file_location('prepare_firmware', helper)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            temporary = tempfile.TemporaryDirectory()
            bundle = Path(temporary.name)
            module.prepare(root / 'arduino' / module.NAME, bundle)
        manifest = json.loads((bundle / 'manifest.json').read_text())
        expected = identity_line(manifest)
        print(f'EXPECTED {expected}')
        try:
            connected = controller_factory(port=port, baud=baud, expected_firmware=expected)
            if not force_flash:
                return connected
            connected.close()
        except FirmwareMismatch as error:
            print(f'FIRMWARE MISMATCH: {error}')
        except TimeoutError:
            if not force_flash:
                raise
        if not force_flash and os.environ.get('FIRMWARE_AUTO_FLASH', '1') == '0':
            raise RuntimeError('Firmware mismatch; automatic flashing is disabled')
        if temporary is not None:
            if not shutil.which('arduino-cli'):
                raise RuntimeError('Install arduino-cli and the AVR core/libraries to update the Mega locally')
            run(['arduino-cli', 'compile', '--fqbn', 'arduino:avr:mega', '--output-dir', str(bundle),
                 str(bundle / manifest['name'])])
        hex_file = bundle / (manifest['name'] + '.ino.hex')
        if not hex_file.is_file():
            raise RuntimeError(f'Mega firmware image missing: {hex_file}')
        path = history_path()
        history = read(path, {})
        key = expected
        previous = history.get(key, {})
        attempts = previous.get('attempts', 0)
        last_attempt = previous.get('last_attempt', 0)
        if attempts >= 2 or (attempts and time.time() - last_attempt < 600):
            raise RuntimeError('Firmware retry blocked: inspect /firmware and POST /firmware/retry to clear the retry limit')
        history[key] = {'attempts': attempts + 1, 'last_attempt': time.time(), 'status': 'FLASHING'}
        write(path, history)
        if on_status:
            on_status('FLASHING', {'expected': manifest, 'attempt': attempts + 1})
        print(f'FLASHING MEGA: {manifest["name"]} {manifest["version"]}')
        try:
            if temporary is not None:
                run(['arduino-cli', 'upload', '--fqbn', 'arduino:avr:mega', '--port', port,
                     '--input-dir', str(bundle)])
            else:
                run(['avrdude', '-p', 'atmega2560', '-c', 'wiring', '-P', port,
                     '-b', '115200', '-D', '-U', f'flash:w:{hex_file}:i'])
            controller = controller_factory(port=port, baud=baud, expected_firmware=expected)
        except Exception as error:
            history[key].update(status='FAILED', last_error=str(error), finished_at=time.time())
            write(path, history)
            raise
        history[key].update(status='VERIFIED', finished_at=time.time(), attempts=0)
        try:
            write(path, history)
        except Exception:
            connected_controller = controller
            connected_controller.close()
            raise
        print('FIRMWARE VERIFIED AFTER FLASH')
        return controller
    finally:
        if temporary is not None:
            temporary.cleanup()
