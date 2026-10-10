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
const unsigned long SENSOR_INTERVAL = 5;
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
void advance(unsigned long duration) {
  unsigned long until = clockMs + duration;
  while(clockMs < until) { clockMs++; checkForHits(); }
}
int main() {
  enableSensorMode(true);
  advance(4); assert(reads==0);
  advance(1); assert(reads==1); // Only one transaction per scheduler slot.
  advance(20); assert(reads==5);
  values[0]=-12000; advance(725);
  assert(Serial.buffer.str().find("HIT ")==std::string::npos);
  values[0]=-1900; advance(25); // Require rest after settling.
  values[0]=-12000; advance(25);
  assert(Serial.buffer.str().find("HIT 0 0 12000")!=std::string::npos);
  assert(!puzzleHitArmed);
  auto first=Serial.buffer.str(); auto previousReads=reads;
  values[1]=-15000; advance(100);
  assert(reads==previousReads); // Stop extra traffic after the one puzzle hit.
  assert(Serial.buffer.str()==first);
  for(int id=0;id<5;id++) values[id]=-1900;
  enableSensorMode(true); advance(775);
  values[4]=-32768; advance(25);
  assert(Serial.buffer.str().find("HIT 4 4 32768")!=std::string::npos);
  assert(Serial.buffer.str().find("ACCEL ")==std::string::npos);
  Serial.buffer.str(""); for(int id=0;id<5;id++) values[id]=-1900;
  enableSensorMode(false); values[2]=-16000; advance(15);
  values[2]=-1900; advance(35);
  assert(Serial.buffer.str().find("ACCEL 2 2 0 0 -16000")!=std::string::npos);
  Serial.buffer.str(""); failing[3]=true;
  enableSensorMode(true); advance(1000);
  assert(puzzleFailures[3]>0 || Serial.buffer.str().find("FAILURES 40")!=std::string::npos);
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
