from pathlib import Path
import subprocess
import tempfile
import unittest


class RFIDInitTests(unittest.TestCase):
    def test_tester_delay_and_bounded_retry(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v2'
                  / 'MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()
        start = source.index('bool initializeRFIDReader()')
        end = source.index('// ============================================================', start)
        block = source[start:end]
        harness = r'''
#include <cassert>
bool rfidReaderAvailable = false;
unsigned long waited = 0;
void delay(unsigned long ms) { assert(ms == 100); waited += ms; }
struct SPIStub { int starts = 0; void begin() { starts++; } } SPI;
struct Reader { int attempts = 0; int successOn = 0; void PCD_Init() { attempts++; } } rfid;
struct Logger {
  template<class T> void print(T) {}
  template<class T> void println(T) {}
} Serial;
void printRFIDStatus() { rfidReaderAvailable = rfid.successOn > 0 && rfid.attempts >= rfid.successOn; }
'''
        tests = r'''
int main() {
  rfid.successOn = 1;
  assert(initializeRFIDReader());
  assert(rfid.attempts == 1 && waited == 100);
  rfid.attempts = 0; waited = 0; rfid.successOn = 2;
  assert(initializeRFIDReader());
  assert(rfid.attempts == 2 && waited == 200);
  rfid.attempts = 0; waited = 0; rfid.successOn = 0;
  assert(!initializeRFIDReader());
  assert(rfid.attempts == 3 && waited == 300);
  assert(!rfidReaderAvailable && SPI.starts == 3);
}
'''
        self.assertIn('initializeRFIDReader();', source[source.index('void setup()'):])
        self.assertIn('Serial.println("OK RFID STATUS")', source)
        self.assertIn('Serial.println("OK RFID INIT")', source)
        with tempfile.TemporaryDirectory() as folder:
            cpp = Path(folder) / 'rfid.cpp'
            executable = Path(folder) / 'rfid'
            cpp.write_text(harness + block + tests)
            subprocess.run(['c++', '-std=c++11', str(cpp), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

    def test_rfid_precedes_peripherals_and_has_stage_checkpoints(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v2'
                  / 'MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()
        setup = source[source.index('void setup()'):]
        self.assertLess(setup.index('initializeRFIDReader();'), setup.index('Wire.begin();'))
        for phase in ('AFTER I2C', 'AFTER MOLE LEDS', 'AFTER PLAYER BEGIN',
                      'AFTER PLAYER BRIGHTNESS', 'AFTER PLAYER BUFFER CLEAR', 'AFTER PLAYER LEDS',
                      'AFTER SOLENOIDS', 'AFTER SENSORS'):
            self.assertIn(f'reportRFIDCheckpoint("{phase}");', setup)
