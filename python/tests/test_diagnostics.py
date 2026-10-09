import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

from app.diagnostics import diagnostics
from app.mole_game import MoleGame
from test_mole_game import Hardware


class DiagnosticsTests(unittest.TestCase):
    def test_solve_status_and_physical_payout_are_distinct(self):
        game = MoleGame(Hardware())
        game.state.completed_players = {'001'}
        game.state.active_player = '002'
        game.state.whack_order = ['MARTIN', 'NILES']
        game.state.hit_progress = 1
        game.state.ticket_dispensed = True
        solve = game.get_state_dict()['solve_state']
        self.assertEqual(solve['completed_count'], 1)
        self.assertEqual(solve['players']['001'], 'SOLVED')
        self.assertEqual(solve['players']['002'], 'ACTIVE')
        self.assertEqual(solve['next_expected_mole'], 'NILES')
        self.assertFalse(solve['fully_solved'])
        self.assertTrue(solve['ticket_requested'])
        self.assertFalse(solve['physical_payout_confirmed'])

    def test_host_snapshot_is_separate_and_absent_information_is_explicit(self):
        game = MoleGame(Hardware())
        game.arduino.get_diagnostics = Mock(return_value={'connected': True})
        with tempfile.TemporaryDirectory() as folder:
            host = Path(folder) / 'host.json'
            firmware = Path(folder) / 'manifest.json'
            host.write_text(json.dumps({'hostname': 'mole4', 'os': {'ID': 'linuxmint'}}))
            firmware.write_text(json.dumps({'version': '2.1.0'}))
            with patch.dict('os.environ', {'HOST_INFO_PATH': str(host), 'FIRMWARE_DIR': folder}):
                report = diagnostics(game, time.monotonic())
            self.assertEqual(report['host']['hostname'], 'mole4')
            self.assertEqual(report['firmware']['expected']['version'], '2.1.0')
            self.assertIsNone(report['firmware']['running_identity'])
            self.assertTrue(report['runtime']['python'])
            self.assertEqual(len(report['application']['source_sha256']), 64)
            self.assertEqual(report['serial'], {'connected': True})
            self.assertGreater(report['storage']['total_bytes'], 0)
