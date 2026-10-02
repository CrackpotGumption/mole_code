"""Durable, atomic checkpoints for completed cabinet players."""
import json
import os
from pathlib import Path
import tempfile


class ProgressStore:
    def __init__(self, path, player_ids):
        self.path = Path(path)
        self.player_ids = set(player_ids)

    def load(self):
        try:
            with self.path.open() as source:
                data = json.load(source)
        except FileNotFoundError:
            return set(), False
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('Unsupported saved game progress')
        players = data.get('completed_players')
        ticket = data.get('ticket_requested')
        if (not isinstance(players, list) or any(not isinstance(p, str) for p in players)
                or len(set(players)) != len(players)
                or not set(players) <= self.player_ids or type(ticket) is not bool
                or (ticket and set(players) != self.player_ids)):
            raise ValueError('Invalid saved game progress; preserve file for recovery')
        return set(players), ticket

    def save(self, completed_players, ticket_requested):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'version': 1, 'completed_players': sorted(completed_players),
                   'ticket_requested': ticket_requested}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path.parent,
                                             prefix='.progress-', delete=False) as target:
                temporary = target.name
                json.dump(payload, target)
                target.write('\n')
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
