"""Compile the actual ticket state machine against a small host hardware stub."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class TicketPayoutTests(unittest.TestCase):
    def test_nonblocking_counter_timeout_and_busy(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v1'
                  / 'MOLE_FINAL_NO_INTERVAL_v1.ino').read_text()
        block = source[source.index('// Nonblocking ticket payout:'):source.index(
            '// ============================================================\n// STATUS', source.index('// Nonblocking ticket payout:'))]
        harness = r'''
#include <cassert>
#include <sstream>
#include <string>
#define HIGH 1
#define LOW 0
const int TICKET_SENSOR_PIN = 23;
const int TICKET_SENSOR_ACTIVE = LOW;
const unsigned long TICKET_TIMEOUT_PER_TICKET = 5000;
unsigned long clockMs = 0;
int sensorState = HIGH;
bool motorOn = false;
unsigned long millis() { return clockMs; }
int digitalRead(int) { return sensorState; }
void ticketMotor(bool on) { motorOn = on; }
struct Logger {
  std::ostringstream buffer;
  template<class T> void print(T value) { buffer << value; }
  template<class T> void println(T value) { buffer << value << "\n"; }
} Serial;
'''
        tests = r'''
int main() {
  assert(dispenseTickets(2));
  assert(motorOn && ticketPayoutActive && clockMs == 0);
  assert(!dispenseTickets(8)); // no nested/repeated payout
  assert(ticketTarget == 2);
  sensorState = LOW; clockMs = 1; updateTickets();
  assert(ticketDispensed == 1 && motorOn);
  sensorState = HIGH; clockMs = 3; updateTickets();
  sensorState = LOW; clockMs = 5; updateTickets(); // bounce rejected
  assert(ticketDispensed == 1);
  sensorState = HIGH; clockMs = 26; updateTickets();
  sensorState = LOW; clockMs = 27; updateTickets();
  assert(ticketDispensed == 2 && !motorOn && !ticketPayoutActive);
  assert(Serial.buffer.str().find("OK TICKET STARTED 2") != std::string::npos);
  assert(Serial.buffer.str().find("TICKET_DONE 2") != std::string::npos);
  sensorState = HIGH;
  assert(dispenseTickets(1));
  clockMs += 5001; updateTickets();
  assert(!motorOn && !ticketPayoutActive);
  assert(Serial.buffer.str().find("TICKET_ERROR TIMEOUT 0") != std::string::npos);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            cpp = Path(folder) / 'tickets.cpp'
            executable = Path(folder) / 'tickets'
            cpp.write_text(harness + block + tests)
            subprocess.run(['c++', '-std=c++11', '-Wall', '-Wextra', str(cpp), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
