"""Bounded observed hit history, persisted separately from game-state snapshots."""
from collections import deque
from copy import deepcopy
from threading import Lock
from .state_log import StateLog


class HitHistory:
    def __init__(self, path=None, session_id=None):
        self.log = StateLog(path)
        if session_id:
            self.log.session_id = session_id
        self.recent = deque(maxlen=1000)
        self.lock = Lock()

    def record(self, details):
        self.log.record('HIT_OBSERVATION', details)
        with self.lock:
            self.recent.append(deepcopy(self.log.last_event))

    def events(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Hit limit must be 1..1000')
        if self.log.path is not None:
            entries = self.log.events(limit)
        else:
            with self.lock:
                entries = list(self.recent)[-limit:]
        return [{'timestamp': entry['timestamp'], 'session_id': entry['session_id'],
                 **entry['state']} for entry in entries]
