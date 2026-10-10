"""Exercise V3's actual RFID pause/resume command branches."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class RFIDResumeTests(unittest.TestCase):
    def test_pause_antenna_and_resume_only_after_success(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_V3/MOLE_FINAL_V3.ino').read_text()
        start = source.index('  if (command == "RFID PAUSE")')
        end = source.index('// UNKNOWN', start)
        block = source[start:end]
        harness = r'''
#include <cassert>
#include <string>
bool rfidPollingEnabled = true, commandFailed = false, initOK = true;
unsigned long lastRFIDPoll = 42;
struct Reader { bool antenna = true; void PCD_AntennaOff() { antenna = false; } } rfid;
bool initializeRFIDReader() { rfid.antenna = initOK; return initOK; }
struct Logger { void println(const char*) {} } Serial;
void handle(std::string command) {
'''
        tests = r'''
}
int main() {
 handle("RFID PAUSE"); assert(!rfidPollingEnabled && !rfid.antenna);
 handle("RFID INIT"); assert(rfidPollingEnabled && rfid.antenna && lastRFIDPoll == 0);
 handle("RFID PAUSE"); initOK = false; handle("RFID INIT");
 assert(!rfidPollingEnabled && commandFailed);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            cpp = Path(folder) / 'rfid.cpp'
            exe = Path(folder) / 'rfid'
            cpp.write_text(harness + block + tests)
            subprocess.run(['c++', '-std=c++11', '-Wall', '-Wextra', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
