"""Atomic JSON records used by firmware recovery and the administration API."""
import json
import os
from pathlib import Path
import tempfile


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as file:
            temporary = file.name
            json.dump(data, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()
