import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class HostInfoTests(unittest.TestCase):
    def test_host_snapshot_filters_docker_networks_and_records_image(self):
        script = Path(__file__).resolve().parents[1] / 'collect_host_info.py'
        interfaces = [{'ifname': 'wlp3s0', 'addr_info': [{'local': '192.168.8.206'}]},
                      {'ifname': 'docker0', 'addr_info': [{'local': '172.17.0.1'}]}]
        def command(args, **kwargs):
            value = json.dumps(interfaces) if args[0] == 'ip' else 'test-version'
            return subprocess.CompletedProcess(args, 0, stdout=value)
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'host.json'
            with patch('sys.argv', [str(script), str(destination), 'sha256:image', 'myst1cus/mole-game:latest']), \
                    patch('subprocess.run', side_effect=command), \
                    patch('platform.freedesktop_os_release', return_value={'ID': 'linuxmint'}), \
                    patch('platform.node', return_value='mole4'):
                runpy.run_path(str(script))
            report = json.loads(destination.read_text())
            self.assertEqual(report['hostname'], 'mole4')
            self.assertEqual(report['os']['ID'], 'linuxmint')
            self.assertEqual(report['image_id'], 'sha256:image')
            self.assertEqual(report['network'], [{'interface': 'wlp3s0', 'addresses': ['192.168.8.206']}])
            self.assertIn('openssh-server', report['packages'])
