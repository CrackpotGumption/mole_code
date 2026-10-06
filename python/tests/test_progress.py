import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.mole_game import MoleGame, MOLE_ID_BY_NAME, PLAYER_IDS
from app.progress_store import ProgressStore
from test_runtime import Hardware


class ProgressTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'progress.json'
        self.hardware = Hardware()
        self.game = MoleGame(self.hardware, state_path=self.path, victory_seconds=0)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def complete(self, player):
        self.game.handle_rfid(player)
        for _ in range(4):
            name = self.game.state.whack_order[self.game.state.hit_progress]
            self.game.handle_hit(MOLE_ID_BY_NAME[name])

    def test_completed_players_recover_without_shutdown(self):
        for player in ('001', '002', '003'):
            self.complete(player)
        # Begin another round but don't finish it; no shutdown save is called.
        self.game.handle_rfid('004')
        self.game.handle_hit(MOLE_ID_BY_NAME[self.game.state.whack_order[0]])
        hardware = Hardware()
        restored = MoleGame(hardware, state_path=self.path, victory_seconds=0)
        restored.restore_hardware()
        self.assertEqual(restored.state.completed_players, {'001', '002', '003'})
        self.assertIsNone(restored.state.active_player)
        self.assertEqual(restored.state.hit_progress, 0)
        self.assertTrue(restored.state.locked)
        self.assertEqual(restored.state.status, 'WAITING FOR BADGE')
        for index in range(3):
            self.assertIn(f'PLAYER_LIGHT {index} GREEN', hardware.commands)
        restored.handle_rfid('001')
        self.assertIsNone(restored.state.active_player)
        restored.handle_rfid('004')
        self.assertEqual(restored.state.active_player, '004')
        self.assertEqual(restored.state.hit_progress, 0)

    def test_full_game_recovery_does_not_repeat_payout(self):
        for player in PLAYER_IDS:
            self.complete(player)
        hardware = Hardware()
        restored = MoleGame(hardware, state_path=self.path, victory_seconds=0)
        restored.restore_hardware()
        self.assertEqual(restored.state.status, 'GAME COMPLETE')
        self.assertTrue(restored.state.ticket_dispensed)
        self.assertNotIn('TICKET 8', hardware.commands)

    def test_final_completion_saved_before_payout_intent(self):
        ProgressStore(self.path, PLAYER_IDS).save(set(PLAYER_IDS), False)
        hardware = Hardware()
        restored = MoleGame(hardware, state_path=self.path, victory_seconds=0)
        restored.restore_hardware()
        self.assertEqual(hardware.commands.count('TICKET 8'), 1)
        self.assertTrue(ProgressStore(self.path, PLAYER_IDS).load()[1])

    def test_failed_save_preserves_checkpoint_and_blocks_play(self):
        self.complete('001')
        self.game.handle_rfid('002')
        self.game.state.hit_progress = 3
        with patch('app.progress_store.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.game.complete_player()
        self.assertEqual(ProgressStore(self.path, PLAYER_IDS).load()[0], {'001'})
        self.assertIsNotNone(self.game.persistence_error)
        self.assertTrue(self.game.state.locked)
        commands = list(self.hardware.commands)
        self.game.handle_arduino_event('RFID 003')
        self.assertEqual(self.hardware.commands, commands)

    def test_corrupt_or_unknown_saved_state_is_not_overwritten(self):
        for payload in ('broken JSON', json.dumps({'version': 99}),
                        json.dumps({'version': 1, 'completed_players': ['999'],
                                    'ticket_requested': False})):
            self.path.write_text(payload)
            with self.assertRaises(ValueError):
                MoleGame(Hardware(), state_path=self.path, victory_seconds=0)
            self.assertEqual(self.path.read_text(), payload)

    def test_payout_intent_survives_failed_ticket_command(self):
        ProgressStore(self.path, PLAYER_IDS).save(set(PLAYER_IDS), False)
        hardware = Hardware()
        restored = MoleGame(hardware, state_path=self.path, victory_seconds=0)
        original_send = hardware.send

        def send(command):
            if command == 'TICKET 8':
                raise RuntimeError('power loss before command')
            original_send(command)

        hardware.send = send
        with self.assertRaises(RuntimeError):
            restored.restore_hardware()
        next_hardware = Hardware()
        next_game = MoleGame(next_hardware, state_path=self.path, victory_seconds=0)
        next_game.restore_hardware()
        self.assertNotIn('TICKET 8', next_hardware.commands)

    def test_new_game_with_no_checkpoint(self):
        self.assertEqual(self.game.state.completed_players, set())
        self.assertFalse(self.game.state.ticket_dispensed)
