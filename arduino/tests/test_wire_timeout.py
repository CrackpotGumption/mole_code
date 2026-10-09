from pathlib import Path
import subprocess
import tempfile
import unittest


class WireTimeoutTests(unittest.TestCase):
    def test_timeout_api_enabled_without_feature_macro(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v2'
                  / 'MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()
        start = source.index('void configureI2CTimeout()')
        end = source.index('// TCA9548A', start)
        block = source[start:end]
        harness = r'''
#include <cassert>
#include <sstream>
const unsigned long I2C_TIMEOUT_US = 25000;
struct WireStub {
  unsigned long timeout = 0; bool reset = false; bool flag = false;
  void setWireTimeout(unsigned long value, bool resetTwi) { timeout = value; reset = resetTwi; }
  bool getWireTimeoutFlag() { return flag; }
  void clearWireTimeoutFlag() { flag = false; }
} Wire;
struct Logger {
  std::ostringstream buffer;
  template<class T> void print(T value) { buffer << value; }
  template<class T> void println(T value) { buffer << value << "\n"; }
} Serial;
'''
        tests = r'''
int main() {
  configureI2CTimeout();
  assert(Wire.timeout == 25000 && Wire.reset);
  assert(Serial.buffer.str().find("I2C TIMEOUT ENABLED 25000 us") != std::string::npos);
  Wire.flag = true;
  reportI2CTimeoutIfNeeded();
  assert(!Wire.flag);
  assert(Serial.buffer.str().find("I2C_TIMEOUT") != std::string::npos);
}
'''
        self.assertNotIn('#if defined(WIRE_HAS_TIMEOUT)', source)
        self.assertIn('configureI2CTimeout();', source[source.index('void setup()'):])
        self.assertIn('rfidReaderAvailable &&', source[source.index('void loop()'):])
        with tempfile.TemporaryDirectory() as folder:
            cpp = Path(folder) / 'wire.cpp'
            executable = Path(folder) / 'wire'
            cpp.write_text(harness + block + tests)
            subprocess.run(['c++', '-std=c++11', str(cpp), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
