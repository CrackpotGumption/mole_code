import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from app.mole_game import MoleGame, MOLE_ID_BY_NAME, PLAYER_IDS
from test_runtime import Hardware


class SessionStateTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'game-events.jsonl'
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
    def game(self):
        return MoleGame(Hardware(), state_log_path=self.path, victory_seconds=0)
    def complete(self, game, player):
        game.handle_rfid(player)
        for _ in range(4):
            name = game.state.whack_order[game.state.hit_progress]
            game.handle_hit(MOLE_ID_BY_NAME[name])
    def test_restart_has_no_progress_payout_or_active_puzzle(self):
        original = self.game()
        for player in PLAYER_IDS:
            self.complete(original, player)
        fresh = self.game()
        fresh.initialize_hardware()
        self.assertEqual(fresh.state.completed_players, set())
        self.assertFalse(fresh.state.ticket_dispensed)
        self.assertIsNone(fresh.state.active_player)
        self.assertEqual(fresh.state.hit_progress, 0)
        self.assertNotIn('TICKET 7', fresh.arduino.commands)
        events = fresh.state_log.events(100)
        self.assertTrue(any(event['event'] == 'GAME_COMPLETE' for event in events))
        self.assertEqual(events[-1]['event'], 'SESSION_STARTED_FRESH')
    def test_every_hit_and_completion_is_logged(self):
        game = self.game()
        self.complete(game, '001')
        events = game.state_log.events()
        hits = [event for event in events if event['event'] == 'HIT_CORRECT']
        self.assertEqual([event['state']['hit_progress'] for event in hits], [1, 2, 3, 4])
        self.assertEqual(events[-1]['event'], 'PLAYER_COMPLETED')
        self.assertEqual(events[-1]['state']['completed_players'], ['001'])
        self.assertIsNone(events[-1]['state']['active_player'])
    def test_manual_restore_rebuilds_progress_without_payout(self):
        game = self.game()
        game.apply_admin_state({'completed_players': ['001'], 'active_player': '002', 'hit_progress': 2})
        self.assertEqual(game.state.completed_players, {'001'})
        self.assertEqual(game.state.hit_progress, 2)
        self.assertEqual(game.state.status, 'PLAYING')
        self.assertNotIn('TICKET 7', game.arduino.commands)
        for name in game.state.whack_order[:2]:
            self.assertNotIn(f'MOLE {MOLE_ID_BY_NAME[name]} UP', game.arduino.commands)
    def test_manual_completed_restore_does_not_trigger_payout(self):
        game = self.game()
        game.apply_admin_state({'completed_players': list(PLAYER_IDS), 'ticket_requested': False})
        self.assertEqual(game.state.status, 'GAME COMPLETE')
        self.assertNotIn('TICKET 7', game.arduino.commands)
    def test_log_artifacts_do_not_restore_or_block_startup(self):
        self.path.write_text('incomplete previous line')
        game = self.game()
        self.assertEqual(game.state.completed_players, set())
        self.assertFalse(game.state.ticket_dispensed)
        self.assertEqual(game.state_log.events()[-1]["event"], "SESSION_STARTED_FRESH")
    def test_invalid_admin_payload_is_rejected(self):
        for state in ({'completed_players': ['999']}, {'active_player': '001', 'hit_progress': 9},
                      {'completed_players': ['001'], 'active_player': '001'}, {'ticket_requested': True}):
            with self.assertRaises(ValueError):
                MoleGame.validate_admin_state(state)
