import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('host_agent', Path(__file__).resolve().parents[1] / 'host_agent.py')
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class HostAgentTests(unittest.TestCase):
    def test_reboot_is_fixed_command_not_shell(self):
        with patch.object(agent, 'command', return_value={'exit_code': 0}) as command, patch.object(agent.time, 'sleep'):
            agent.execute('reboot', {})
        command.assert_called_once_with(['systemctl', 'reboot'])
    def test_unknown_command_and_invalid_hostname_are_rejected(self):
        with patch.object(agent, 'command') as command:
            with self.assertRaises(ValueError):
                agent.execute('shell', {'command': 'arbitrary'})
            with self.assertRaises(ValueError):
                agent.execute('hostname', {'hostname': 'bad;command'})
        command.assert_not_called()
    def test_config_changes_preserve_other_settings_and_do_not_interpret_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'cabinet.conf').write_text("IMAGE='old/game:latest'\nFAILURE_SECONDS=15\nSTATUS_PORT=8080\nSERIAL_DEVICE=''\n")
            with patch.object(agent, 'ROOT', root):
                result = agent.configure({'IMAGE': 'myst1cus/mole-game:latest', 'STATUS_PORT': 8081})
                self.assertEqual(result['exit_code'], 0)
                self.assertEqual(agent.configuration()['STATUS_PORT'], '8081')
                self.assertIn('FAILURE_SECONDS=15', (root / 'cabinet.conf').read_text())
                with self.assertRaises(ValueError):
                    agent.configure({'IMAGE': '$(arbitrary)'})
                with self.assertRaises(ValueError):
                    agent.configure({'SERIAL_DEVICE': '/dev/sda'})
                with self.assertRaises(ValueError):
                    agent.configure({'UNSUPPORTED': 'value'})

    def test_unauthenticated_unix_socket_bridge_and_job_receipts(self):
        import os
        import threading
        import time
        root_source = Path(__file__).resolve().parents[2]
        bridge_spec = importlib.util.spec_from_file_location('host_bridge', root_source / 'python/app/host_bridge.py')
        bridge = importlib.util.module_from_spec(bridge_spec)
        bridge_spec.loader.exec_module(bridge)
        with tempfile.TemporaryDirectory(dir='/tmp', prefix='mha-') as folder:
            root = Path(folder)
            socket = str(root / 'control.sock')
            with patch.object(agent, 'ROOT', root), patch.dict(agent.JOBS, {}, clear=True), \
                    patch.object(agent, 'information', return_value={'hostname': 'mole4'}), \
                    patch.object(agent, 'execute', return_value={'exit_code': 0}) as execute, \
                    patch.dict(os.environ, {'HOST_AGENT_SOCKET': socket}):
                with agent.Server(socket, agent.Handler) as server:
                    threading.Thread(target=server.serve_forever, daemon=True).start()
                    try:
                        self.assertEqual(bridge.request('GET', '/host')['hostname'], 'mole4')
                        execute.assert_not_called()
                        with self.assertRaisesRegex(RuntimeError, 'Unsupported host action'):
                            bridge.request('POST', '/actions', {'action': 'shell'})
                        receipt = bridge.request('POST', '/actions', {'action': 'restart_game'})
                        deadline = time.monotonic() + 1
                        while time.monotonic() < deadline:
                            jobs = bridge.request('GET', '/jobs')
                            if jobs[0]['status'] == 'DONE':
                                break
                            time.sleep(0.01)
                        self.assertEqual(jobs[0]['id'], receipt['id'])
                        self.assertEqual(jobs[0]['status'], 'DONE')
                        self.assertTrue((root / 'host-jobs.json').is_file())
                    finally:
                        server.shutdown()
