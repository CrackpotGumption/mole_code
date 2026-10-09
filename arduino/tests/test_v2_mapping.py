"""Keep the standard cabinet wiring consistent with the Python controller."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class V2MappingTests(unittest.TestCase):
    def test_channels_solenoids_lights_and_characters(self):
        firmware = (ROOT / 'arduino/MOLE_FINAL_NO_INTERVAL_v2/MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()
        for name in ('sensorChannel', 'solenoidOutput'):
            match = re.search(r'const uint8_t ' + name + r'\[MOLE_COUNT\]\s*=\s*\{(.*?)\};', firmware, re.S)
            self.assertIsNotNone(match)
            values = [int(value.strip()) for value in match[1].split(',') if value.strip()]
            self.assertEqual(values, list(range(5)))
        pins = re.findall(r'Adafruit_NeoPixel mole(\d)Lights\(\s*MOLE_LED_COUNT,\s*(\d+),', firmware)
        self.assertEqual(dict((int(mole), int(pin)) for mole, pin in pins),
                         {mole: 14 + mole for mole in range(5)})
        module = ast.parse((ROOT / 'python/app/mole_game.py').read_text())
        mappings = {}
        for node in ast.walk(module):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ('MOLE_BY_ID', 'SENSOR_CHANNELS'):
                        mappings[target.id] = ast.literal_eval(node.value)
        self.assertEqual(mappings['SENSOR_CHANNELS'], {mole: mole for mole in range(5)})
        self.assertEqual(mappings['MOLE_BY_ID'],
                         {0: 'MARTIN', 1: 'DAPHNE', 2: 'NILES', 3: 'FRASIER', 4: 'ROZ'})
