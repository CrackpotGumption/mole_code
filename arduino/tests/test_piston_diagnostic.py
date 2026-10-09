from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PistonDiagnosticTests(unittest.TestCase):
    def test_full_sketch_cycle_stop_and_restrictor_advice(self):
        header = r'''
#pragma once
#include <cstdint>
#include <sstream>
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define F(text) text
extern unsigned long mockTime;
inline unsigned long millis() { return mockTime; }
int16_t mockAxes[3] = {0, 0, 0};
struct WireStub {
  int offset = 0;
  void begin() {} void setWireTimeout(unsigned long, bool) {}
  void clearWireTimeoutFlag() {} bool getWireTimeoutFlag() { return false; }
  void beginTransmission(uint8_t) {} void write(int) {}
  int endTransmission(bool = true) { return 0; }
  void requestFrom(uint8_t, uint8_t) { offset = 0; } int available() { return 6; }
  int read() {
    uint16_t value = (uint16_t)mockAxes[offset / 2];
    int byte = (offset % 2 == 0) ? (value >> 8) : (value & 255);
    offset++; return byte;
  }
} Wire;
struct SerialStub {
  std::ostringstream text;
  void begin(int) {} void flush() {} int available() { return 0; } int read() { return 0; }
  void print(uint8_t value) { text << (unsigned int)value; }
  template<class T> void print(T value) { text << value; }
  template<class T> void println(T value) { text << value << "\n"; }
  template<class T> void println(T value, int) { println(value); }
  template<class T> void print(T value, int) { print(value); }
} Serial;
'''
        mcp = r'''
#pragma once
struct Adafruit_MCP23X17 {
  int state[16] = {};
  bool begin_I2C(int) { return true; }
  void digitalWrite(int pin, int value) { state[pin] = value; }
  int digitalRead(int pin) { return state[pin]; }
  void pinMode(int, int) {}
};
'''
        source = (ROOT / 'MOLE_PISTON_DIAGNOSTIC/MOLE_PISTON_DIAGNOSTIC.ino').read_text()
        tests = r'''
#include <cassert>
#include <string>
unsigned long mockTime = 0;
void command(const char* text) { char buffer[96]; strcpy(buffer, text); handleCommand(buffer); }
void tick(unsigned long until) { while (mockTime < until) { mockTime += 5; updateTest(); } }
void clearLog() { Serial.text.str(""); Serial.text.clear(); }
int main() {
  setup(); assert(ready && stage == IDLE);
  assert(speedReference[0] == 3000 && speedReference[1] == 3000);
  for (int i = 0; i < 5; i++) assert(mcp.state[i] == LOW);
  command("TEST 0"); assert(stage == BASELINE);
  tick(500); assert(stage == EXTENDING && mcp.state[0] == HIGH);
  tick(2500); assert(stage == RETRACTING && mcp.state[0] == LOW);
  tick(5000); assert(stage == IDLE);
  assert(records[0][0].samples > 100 && records[0][1].samples > 100);
  command("ALL 500"); tick(mockTime + 510); assert(stage == EXTENDING);
  command("STOP"); assert(stage == IDLE && !testAll);
  for (int i = 0; i < 5; i++) assert(mcp.state[i] == LOW);
  command("ALL 500"); tick(mockTime + 11000); assert(stage == IDLE);
  for (int i = 0; i < 5; i++) {
    assert(records[i][0].samples >= 50 && records[i][1].samples >= 50);
    assert(mcp.state[i] == LOW);
  }
  command("REFERENCE 1000 1000");
  records[0][0].samples = records[0][1].samples = 100;
  records[0][0].peak = 2000; records[0][1].peak = 300;
  clearLog(); recommendation(0, 0); recommendation(0, 1);
  assert(Serial.text.str().find("TIGHTEN LEFT") != std::string::npos);
  assert(Serial.text.str().find("LOOSEN RIGHT") != std::string::npos);
  records[0][0].peak = 300; records[0][1].peak = 2000;
  clearLog(); recommendation(0, 0); recommendation(0, 1);
  assert(Serial.text.str().find("LOOSEN LEFT") != std::string::npos);
  assert(Serial.text.str().find("TIGHTEN RIGHT") != std::string::npos);
  records[0][0].peak = 1000;
  clearLog(); recommendation(0, 0);
  assert(Serial.text.str().find("KEEP setting") != std::string::npos);
  command("REFERENCE 3000 3000");
  records[0][0].peak = 1500; records[0][1].peak = 4500;
  clearLog(); recommendation(0, 0); recommendation(0, 1);
  assert(Serial.text.str().find("TIGHTEN") == std::string::npos);
  assert(Serial.text.str().find("LOOSEN") == std::string::npos);
  assert(Serial.text.str().find("KEEP setting") != std::string::npos);
  command("TEST 5"); assert(stage == IDLE);
  command("TEST 0 100000"); assert(stage == IDLE);
  command("REFERENCE 0 0");
  memset(records, 0, sizeof(records));
  records[0][0].samples = records[0][1].samples = 100;
  records[0][0].peak = 30000; records[0][1].peak = 3000;
  clearLog(); printPair(0); recommendation(0, 0); recommendation(0, 1);
  assert(Serial.text.str().find("UP_Y_DELTA 30000 DOWN_Y_DELTA 3000") != std::string::npos);
  assert(Serial.text.str().find("ADVICE:") == std::string::npos);
  assert(Serial.text.str().find("REFERENCE_SPEED_INDEX") == std::string::npos);
  memset(records[0], 0, sizeof(records[0]));
  mole = 0; base[0] = 100; base[1] = -200; base[2] = -1900;
  for (int axis = 0; axis < 3; axis++) baselineAverage[0][axis] = base[axis];
  baselineReadCount[0] = 100;
  stage = EXTENDING; stageStart = mockTime;
  mockAxes[0] = 110; mockAxes[1] = -230; mockAxes[2] = -5000;
  sampleTrace(mockTime + 5);
  mockAxes[0] = 80; mockAxes[1] = -150; mockAxes[2] = -1000;
  sampleTrace(mockTime + 10);
  assert(records[0][0].rawMin[1] == -230 && records[0][0].rawMax[1] == -150);
  assert(records[0][0].deltaMin[1] == -30 && records[0][0].deltaMax[1] == 50);
  assert(records[0][0].axisPeakDelta[1] == 50);
  assert(records[0][0].peak == 50); // large Z change doesn't contribute
  stage = RETRACTING;
  mockAxes[0] = 130; mockAxes[1] = -180; mockAxes[2] = -1700;
  sampleTrace(mockTime + 15);
  assert(records[0][1].axisPeakDelta[1] == 20);
  assert(records[0][1].peak == 20);
  assert(records[0][0].axisPeakDelta[1] == 50); // directions are independent
  clearLog(); printAxes(0, 0);
  assert(Serial.text.str().find("AXIS X") == std::string::npos);
  assert(Serial.text.str().find("AXIS Z") == std::string::npos);
  assert(Serial.text.str().find("BASELINE MOLE 0 READS 100 Y_AVG -200") != std::string::npos);
  assert(Serial.text.str().find("AXIS Y BASE_AVG -200 RAW_MIN -230 RAW_MAX -150 DELTA_MIN -30 DELTA_MAX 50 PEAK_DELTA 50 PEAK_ABS_DELTA 50") != std::string::npos);
}

'''
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / 'Wire.h').write_text(header)
            (directory / 'Adafruit_MCP23X17.h').write_text(mcp)
            cpp = directory / 'test.cpp'
            executable = directory / 'test'
            cpp.write_text(source + tests)
            subprocess.run(['c++', '-std=c++11', '-Wall', '-Wextra', '-I', folder,
                            str(cpp), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
