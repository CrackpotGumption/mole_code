"""Append-only observed game states. Never used for automatic restoration."""
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import uuid


class StateLog:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.session_id = uuid.uuid4().hex
        self.lock = threading.Lock()
        self.last_event = None
        self.error = None

    def record(self, event, state):
        entry = {'timestamp': datetime.now(timezone.utc).isoformat(), 'session_id': self.session_id,
                 'event': event, 'state': state}
        line = json.dumps(entry, separators=(',', ':'))
        print('GAME_STATE ' + line, flush=True)
        with self.lock:
            self.last_event = entry
            if self.path is None:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size >= 5 * 1024 * 1024:
                    for index in (2, 1):
                        source = self.path.with_name(self.path.name + f'.{index}')
                        if source.exists():
                            os.replace(source, self.path.with_name(self.path.name + f'.{index + 1}'))
                    os.replace(self.path, self.path.with_name(self.path.name + '.1'))
                incomplete = False
                if self.path.exists() and self.path.stat().st_size:
                    with self.path.open('rb') as previous:
                        previous.seek(-1, os.SEEK_END)
                        incomplete = previous.read(1) != b'\n'
                with self.path.open('a') as file:
                    if incomplete:
                        file.write('\n')
                    file.write(line + '\n')
                    file.flush()
                    os.fsync(file.fileno())
                self.error = None
            except OSError as error:
                self.error = str(error)
                print(f'STATE LOG ERROR: {error}', flush=True)

    def events(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Event limit must be 1..1000')
        if self.path is None:
            return [self.last_event] if self.last_event else []
        entries = deque(maxlen=limit)
        with self.lock:
            for path in [self.path.with_name(self.path.name + f'.{index}') for index in (3, 2, 1)] + [self.path]:
                try:
                    with path.open() as source:
                        for line in source:
                            try:
                                entries.append(json.loads(line))
                            except ValueError:
                                pass  # A partial last line after power loss is a log artifact.
                except FileNotFoundError:
                    pass
        return list(entries)
