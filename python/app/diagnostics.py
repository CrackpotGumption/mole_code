"""Read-only cabinet diagnostics; host snapshots are distinct from container data."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import time

APP_VERSION = '3.2.1'


def app_source_hash():
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.name != 'build_info.json':
            digest.update(path.relative_to(root).as_posix().encode() + b'\0')
            digest.update(path.read_bytes())
    return digest.hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None
    except (ValueError, OSError) as error:
        return {'read_error': str(error)}


def application_info():
    bundled = read_json(Path(__file__).with_name('build_info.json'))
    if bundled is not None:
        return bundled
    return {'version': APP_VERSION, 'source_sha256': app_source_hash(),
            'revision': None, 'built_at': None, 'source': 'local checkout'}


def diagnostics(game, started_at):
    controller = game.arduino
    try:
        pyserial = importlib.metadata.version('pyserial')
    except importlib.metadata.PackageNotFoundError:
        pyserial = None
    host = read_json(os.environ.get('HOST_INFO_PATH', '/run/mole-host-info.json'))
    state_path = os.environ.get('GAME_LOG_PATH')
    storage = shutil.disk_usage(Path(state_path).parent if state_path and Path(state_path).parent.exists() else Path.cwd())
    return {
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'application': application_info(),
        'runtime': {'python': platform.python_version(), 'pyserial': pyserial,
                    'container_hostname': platform.node(), 'architecture': platform.machine(),
                    'kernel': platform.release(), 'os': platform.freedesktop_os_release() if Path('/etc/os-release').exists() else platform.system(),
                    'process_id': os.getpid(), 'uptime_seconds': round(time.monotonic() - started_at, 1)},
        'host': host,
        'firmware': {'running_identity': getattr(controller, 'firmware_identity', None),
                     'expected': read_json(Path(os.environ.get('FIRMWARE_DIR', '/opt/mole-firmware')) / 'manifest.json')},
        'serial': controller.get_diagnostics(),
        'storage': {'game_log_path': state_path, 'game_log_exists': bool(state_path and Path(state_path).is_file()),
                    'free_bytes': storage.free, 'total_bytes': storage.total,
                    'log_error': game.state_log.error},
        'audio': (game.audio.get_diagnostics() if hasattr(game.audio, 'get_diagnostics')
                  else {'enabled': False, 'device': None}),
        'configuration': {'failure_seconds': game.failure_seconds, 'victory_seconds': game.victory_seconds,
                          'idle_frame_seconds': game.idle_frame_seconds},
        'game': game.get_state_dict(),
    }
