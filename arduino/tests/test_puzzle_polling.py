"""Verify v2's real polling code without connecting Arduino hardware."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class PuzzlePollingTests(unittest.TestCase):
    def test_one_shot_polling_rearm_and_raw_peak_retention(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v2'
                  / 'MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()
        start = source.index('// PUZZLE: poll frequently')
        end = source.index('// MOLE CONTROL', start)
        block = source[start:end]
        # The trailing comment separator is harmless C++.
        harness = r'''
#include <cassert>
#include <cstdint>
#include <sstream>
#include <string>
#define MOLE_COUNT 5
const unsigned long SENSOR_INTERVAL = 10;
const unsigned long RAW_REPORT_INTERVAL = 50;
const unsigned long PUZZLE_HIT_INTERVAL = 300;
const unsigned long PUZZLE_ARM_SETTLE = 750;
const int16_t PUZZLE_HIT_Z = -9000;
const int16_t PUZZLE_RELEASE_Z = -6400;
bool hitDetectionEnabled = false;
unsigned long lastSensorPoll = 0;
unsigned long clockMs = 0;
unsigned long reads = 0;
int16_t values[5] = {-1900, -1900, -1900, -1900, -1900};
bool failing[5] = {false, false, false, false, false};
const uint8_t sensorChannel[5] = {0, 1, 2, 3, 4};
unsigned long millis() { return clockMs; }
bool readAccelerometer(uint8_t channel, int16_t& x, int16_t& y, int16_t& z) {
  reads++; x = 0; y = 0; z = values[channel]; return !failing[channel];
}
struct Logger {
  std::ostringstream buffer;
  template<class T> void print(T value) { buffer << +value; }
  void print(const char* value) { buffer << value; }
  template<class T> void println(T value) { buffer << +value << "\n"; }
} Serial;
'''
        tests = r'''
int main() {
  enableSensorMode(true);
  clockMs = 9; checkForHits(); assert(reads == 0);
  clockMs = 10; values[0] = -10000; values[1] = -12000;
  checkForHits(); assert(Serial.buffer.str().empty()); // startup movement
  clockMs = 750; checkForHits(); assert(Serial.buffer.str().empty()); // not rested
  values[0] = -1900; values[1] = -1900;
  clockMs = 760; checkForHits();
  values[0] = -10000; values[1] = -12000;
  clockMs = 770; checkForHits();
  assert(!puzzleHitArmed);
  assert(puzzleLatched[0] && puzzleLatched[1]);
  assert(Serial.buffer.str() == "HIT 1 1 12000\n");
  clockMs = 780; values[2] = -15000; checkForHits();
  assert(Serial.buffer.str() == "HIT 1 1 12000\n");
  enableSensorMode(true);
  clockMs = 790; checkForHits();
  assert(Serial.buffer.str() == "HIT 1 1 12000\n");
  for (int i = 0; i < 5; i++) values[i] = -1900;
  clockMs = 1530; checkForHits();
  values[4] = -32768; clockMs = 1540; checkForHits();
  assert(Serial.buffer.str().find("HIT 4 4 32768\n") != std::string::npos);
  assert(Serial.buffer.str().find("ACCEL") == std::string::npos);
  auto text = Serial.buffer.str();
  clockMs = 1640; enableSensorMode(true);
  clockMs = 2390; checkForHits(); assert(Serial.buffer.str() == text);
  values[4] = -1900; clockMs = 2400; checkForHits();
  values[4] = -10000; clockMs = 2410; checkForHits();
  assert(Serial.buffer.str().find("HIT 4 4 10000\n") != std::string::npos);

  Serial.buffer.str(""); Serial.buffer.clear();
  clockMs = 2500; enableSensorMode(false);
  for (int i = 0; i < 5; i++) values[i] = -1900;
  values[2] = -16000; clockMs = 2510; checkForHits();
  assert(Serial.buffer.str().empty());
  values[2] = -1900; clockMs = 2520; checkForHits();
  clockMs = 2540; checkForHits(); assert(Serial.buffer.str().empty());
  clockMs = 2550; checkForHits();
  assert(Serial.buffer.str().find("ACCEL 2 2 0 0 -16000\n") != std::string::npos);
  auto frame = Serial.buffer.str();
  clockMs = 2560; checkForHits(); assert(Serial.buffer.str() == frame);
  clockMs = 2600; enableSensorMode(true);
  for (int i = 0; i < 5; i++) values[i] = -1900;
  values[0] = -7000; failing[3] = true;
  clockMs = 3710; checkForHits();
  assert(Serial.buffer.str().find("PUZZLE_DIAG MOLE 0 ARMED 1 LATCHED 1 READS 1 FAILURES 0 MIN_Z -7000 MAX_Z -7000") != std::string::npos);
  assert(Serial.buffer.str().find("PUZZLE_DIAG MOLE 3 ARMED 1 LATCHED 1 READS 0 FAILURES 1") != std::string::npos);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            cpp = Path(folder) / 'poll.cpp'
            executable = Path(folder) / 'poll'
            cpp.write_text(harness + block + tests)
            subprocess.run(['c++', '-std=c++11', '-Wall', '-Wextra', str(cpp), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

    def test_rfid_is_throttled_and_sensors_are_serviced_first(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v2'
                  / 'MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()
        loop = source[source.index('void loop() {'):]
        self.assertLess(loop.index('checkForHits();'), loop.index('checkRFID();'))
        self.assertIn('now - lastRFIDPoll >= RFID_POLL_INTERVAL', loop)
        self.assertIn('lastRFIDPoll = millis();', loop)
