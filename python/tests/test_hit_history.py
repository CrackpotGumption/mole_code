import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from app.mole_game import MoleGame, MOLE_ID_BY_NAME
from app.hit_history import HitHistory
from test_mole_game import Hardware


class HitHistoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'game-events.jsonl'
        stream = contextlib.redirect_stdout(io.StringIO())
        stream.__enter__()
        self.addCleanup(stream.__exit__, None, None, None)
        self.game = MoleGame(Hardware(), state_log_path=self.path, failure_seconds=0)
        self.game.handle_rfid('001')

    def test_expected_and_resolved_capture_survive_restart(self):
        expected = self.game.state.whack_order[0]
        mole = MOLE_ID_BY_NAME[expected]
        self.game.handle_arduino_event('SCORES 0:12000 1:500 2:700 3:900 4:0')
        self.game.handle_arduino_event(f'HIT {mole} {mole} 12000')
        row = self.game.hit_history.events()[0]
        self.assertEqual(row['expected']['mole'], expected)
        self.assertEqual(row['resolved']['sensor'], mole)
        self.assertEqual(row['decision'], 'CORRECT')
        self.assertEqual(row['arduino']['capture']['scores']['4'], 0)
        restored = HitHistory(self.path.with_name('hit-history.jsonl'))
        self.assertEqual(restored.events()[0], row)
        self.assertEqual(self.game.state.hit_progress, 1)

    def test_wrong_ignored_rejected_and_malformed_events(self):
        expected = self.game.state.whack_order[0]
        wrong = next(mole for name, mole in MOLE_ID_BY_NAME.items() if name != expected)
        self.game.handle_arduino_event(f'HIT {wrong} {wrong} 15000')
        row = self.game.hit_history.events()[-1]
        self.assertEqual(row['decision'], 'WRONG')
        self.assertEqual(row['expected']['mole'], expected)
        self.game.handle_arduino_event('HIT 0 0 12000', received_at=self.game._accept_samples_after - 1)
        self.assertEqual(self.game.hit_history.events()[-1]['reason'], 'stale_event')
        self.game.handle_arduino_event('SCORES 0:9000 1:200 2:100 3:80 4:0')
        self.game.handle_arduino_event('IMPACT_REJECTED winner=0 score=9000 runnerup=200')
        self.assertEqual(self.game.hit_history.events()[-1]['decision'], 'REJECTED')
        self.game.handle_arduino_event('HIT broken')
        self.assertEqual(self.game.hit_history.events()[-1]['reason'], 'malformed_hit')
        for invalid in (0, 1001, True):
            with self.assertRaises(ValueError): self.game.hit_history.events(invalid)
