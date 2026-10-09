"""Exercise the installed launcher without Docker, systemd, or cabinet hardware."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'linux_bash_daemon'
LAUNCHER = SOURCE.read_text().split("<<'LAUNCHER'\n", 1)[1].split('\nLAUNCHER\n', 1)[0]

DOCKER = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p = Path(os.environ['MOCK_STATE'])
s = json.loads(p.read_text())
a = sys.argv[1:]
s['calls'].append(a)
code = 0
out = ''
if a[0] == 'pull':
 code = int(s.get('offline', False))
elif a[:2] == ['image', 'inspect']:
 code = int(not s.get('cached', True))
 out = 'sha256:cached'
elif a[:2] == ['container', 'inspect']:
 code = int(a[2] not in s['containers'])
elif a[0] == 'inspect':
 code = int(a[-1] not in s['containers'])
 out = 'true' if 'Running' in a[2] else 'sha256:cached'
elif a[0] == 'rename':
 s['containers'][a[2]] = s['containers'].pop(a[1])
elif a[0] == 'run':
 name = a[a.index('--name') + 1]
 s['containers'][name] = 'new'
 code = int(s.get('run_fails', False))
elif a[0] == 'exec':
 code = int(s.get('unhealthy', False))
elif a[0] == 'rm':
 s['containers'].pop(a[-1], None)
p.write_text(json.dumps(s))
if out: print(out)
sys.exit(code)
'''


class LauncherTests(unittest.TestCase):
    def run_launcher(self, **options):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = dict(containers={'mole-game': 'old'}, calls=[], **options)
            path = root / 'state.json'
            path.write_text(json.dumps(state))
            config = root / 'cabinet.conf'
            config.write_text("IMAGE='example/mole-game:latest'\nCONTAINER_NAME=mole-game\n"
                              "SERIAL_DEVICE=/dev/null\nSTATUS_BIND=0.0.0.0\nSTATUS_PORT=8080\n")
            for name, content in [('docker', DOCKER), ('sleep', '#!/bin/sh\nexit 0\n'),
                                  ('flock', '#!/bin/sh\nexit 0\n'),
                                  ('timeout', '#!/bin/sh\nshift\nexec "$@"\n')]:
                file = root / name
                file.write_text(content)
                file.chmod(0o755)
            runner = root / 'launch'
            runner.write_text(LAUNCHER.replace('/etc/mole-cabinet/cabinet.conf', str(config))
                              .replace('/run/mole-cabinet.lock', str(root / 'lock')))
            env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}", MOCK_STATE=str(path))
            result = subprocess.run(['bash', str(runner)], env=env, capture_output=True, text=True)
            return result, json.loads(path.read_text())

    def test_online_update_and_lan_mapping(self):
        result, state = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state['containers'], {'mole-game': 'new'})
        run = next(call for call in state['calls'] if call[0] == 'run')
        self.assertIn('0.0.0.0:8080:8080', run)
        self.assertIn('/dev/null:/dev/cabinet-arduino', run)
        self.assertIn('max-size=10m', run)
        self.assertIn('type=volume,source=mole-game-data,target=/data', run)
        self.assertIn('GAME_STATE_PATH=/data/progress.json', run)

    def test_offline_uses_cached_image(self):
        result, state = self.run_launcher(offline=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state['containers'], {'mole-game': 'new'})
        self.assertIn('using installed image', result.stderr)

    def test_unhealthy_replacement_restores_previous(self):
        result, state = self.run_launcher(unhealthy=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state['containers'], {'mole-game': 'old'})
        self.assertIn(['start', 'mole-game'], state['calls'])

    def test_failed_creation_restores_previous(self):
        result, state = self.run_launcher(run_fails=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state['containers'], {'mole-game': 'old'})

    def test_no_cached_image_preserves_previous(self):
        result, state = self.run_launcher(offline=True, cached=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state['containers'], {'mole-game': 'old'})
        self.assertFalse(any(call[0] == 'stop' for call in state['calls']))

    def test_placeholder_refused_before_docker(self):
        text = LAUNCHER.replace('/etc/mole-cabinet/cabinet.conf', '/dev/null')
        result = subprocess.run(['bash', '-c', text], capture_output=True, text=True,
                                env=dict(os.environ, IMAGE='REPLACE_WITH_IMAGE'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set IMAGE', result.stderr)


class SerialDiscoveryTests(unittest.TestCase):
    def discover(self, count=0, configured=''):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for index in range(count):
                (root / f'ttyUSB{index}').symlink_to('/dev/null')
            block = LAUNCHER.split('# Wait for USB enumeration,', 1)[1].split('# A failed pull', 1)[0]
            block = '# Wait for USB enumeration,' + block
            block = block.replace('/dev/serial/by-id/*', str(root / 'by-id' / '*'))
            block = block.replace('/dev/ttyACM*', str(root / 'ttyACM*'))
            block = block.replace('/dev/ttyUSB*', str(root / 'ttyUSB*'))
            return subprocess.run(['bash', '-c', 'set -eu; sleep() { :; }; ' + block],
                                  env=dict(os.environ, SERIAL_DEVICE=configured),
                                  capture_output=True, text=True)

    def test_missing_device_has_exact_message(self):
        result = self.discover()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip(), 'NO SERIAL DEVICE FOUND')

    def test_invalid_configured_device(self):
        result = self.discover(configured='/not/a/serial/device')
        self.assertEqual(result.returncode, 1)
        self.assertIn('NO SERIAL DEVICE FOUND', result.stderr)
        self.assertIn('Configured SERIAL_DEVICE is unavailable', result.stderr)

    def test_multiple_devices_listed(self):
        result = self.discover(count=2)
        self.assertEqual(result.returncode, 1)
        self.assertIn('MULTIPLE SERIAL DEVICES FOUND', result.stderr)
        self.assertIn('ttyUSB0', result.stderr)
        self.assertIn('ttyUSB1', result.stderr)

    def test_single_device_selected(self):
        result = self.discover(count=1)
        self.assertEqual(result.returncode, 0, result.stderr)
