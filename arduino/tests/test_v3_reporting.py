"""Verify V3 reproduces V1 hit detection while retaining V2 controls."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def detection(source):
    start = source.index('void checkForHits() {')
    end = source.index('// MOLE CONTROL', start)
    return source[start:end].strip()


class V3V1DetectionTests(unittest.TestCase):
    def test_detection_is_verbatim_v1(self):
        v1 = (ROOT / 'MOLE_FINAL_V1/MOLE_FINAL_V1.ino').read_text()
        v3 = (ROOT / 'MOLE_FINAL_V3/MOLE_FINAL_V3.ino').read_text()
        self.assertEqual(detection(v1), detection(v3))
        for constant in ('HIT_REPORT_THRESHOLD = 4000', 'HIT_COOLDOWN = 125',
                         'SENSOR_INTERVAL = 10', 'MOLE_MECHANICAL_SUPPRESS_MS = 300'):
            self.assertIn(constant, v3)
        for retained in ('"SAFE STOP"', '"HEALTH RECOVER"', '"LEASE ON"', '"KEEPALIVE"',
                         'Wire.setWireTimeout', 'wdt_reset()', '"ACK "', 'updateTickets();'):
            self.assertIn(retained, v3)
        for removed in ('checkFifoHits', 'fifoArmed', 'puzzleLatched', '"DELTA "', '"ACCEL "'):
            self.assertNotIn(removed, v3)
        self.assertIn('moleMechanicalSuppressUntil[mole] = movementTime + MOLE_MECHANICAL_SUPPRESS_MS;', v3)

    def test_trigger_capture_cooldown_and_suppression(self):
        source = (ROOT / 'MOLE_FINAL_V3/MOLE_FINAL_V3.ino').read_text()
        harness = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <algorithm>
#include <sstream>
#include <string>
using std::max;
#define MOLE_COUNT 5
const long HIT_REPORT_THRESHOLD = 4000;
const unsigned long HIT_COOLDOWN = 125, SENSOR_INTERVAL = 10;
bool hitDetectionEnabled = false;
unsigned long lastSensorPoll = 0, clockMs = 0;
unsigned long moleMechanicalSuppressUntil[5] = {};
const uint8_t sensorChannel[5] = {0,1,2,3,4};
int calls[5] = {};
unsigned long millis() { return clockMs; }
void delay(unsigned long ms) { clockMs += ms; }
bool readAccelerometer(uint8_t id, int16_t& x, int16_t& y, int16_t& z) {
  clockMs++; calls[id]++;
  x = id == 0 ? (calls[id] % 2 ? 6000 : -6000) : 0;
  y = 0; z = 0; return true;
}
struct Logger {
  std::ostringstream buffer;
  template<class T> void print(T v) { buffer << +v; }
  void print(const char* v) { buffer << v; }
  template<class T> void println(T v) { print(v); buffer << '\n'; }
  void println() { buffer << '\n'; }
} Serial;
'''
        tests = r'''
int main() {
  checkForHits(); assert(calls[0] == 0);
  hitDetectionEnabled = true; clockMs = 9; checkForHits(); assert(calls[0] == 0);
  clockMs = 10; checkForHits();
  assert(Serial.buffer.str().find("HIT 0 0 12000") != std::string::npos);
  assert(calls[0] >= 3);
  for (int id = 1; id < 5; id++) assert(calls[id] > 0);
  assert(clockMs == 151); // 1 ms trigger read + shared 15 ms capture + 125 ms cooldown.
  Serial.buffer.str(""); auto before = calls[0];
  moleMechanicalSuppressUntil[0] = clockMs + 300;
  checkForHits(); assert(calls[0] == before);
  assert(Serial.buffer.str().empty());
}
'''
        with tempfile.TemporaryDirectory() as folder:
            cpp = Path(folder) / 'v1.cpp'
            exe = Path(folder) / 'v1'
            cpp.write_text(harness + detection(source) + tests)
            subprocess.run(['c++', '-std=c++11', '-Wall', '-Wextra', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
