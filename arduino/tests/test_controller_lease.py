from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v2/MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()


class ControllerLeaseTests(unittest.TestCase):
    def test_expired_lease_stops_outputs_and_latches_retry_on_missing_bus(self):
        start = SOURCE.index('  if (leaseEnabled &&', SOURCE.index('void loop()'))
        block = SOURCE[start:SOURCE.index('  loopCounter++;', start)]
        harness = r'''
#include <cassert>
#include <string>
unsigned long clockMs=0, lastControllerCommand=0;
const unsigned long CONTROLLER_LEASE_MS=5000;
bool leaseEnabled=false, hitDetectionEnabled=true, puzzleHitArmed=true;
void stopFifoPolling() {}
bool ticketPayoutActive=true, motor=true, molesUp=true, mcpReady=true, stopOutputsPending=false;
int lowered=0, moleLights=0, playerLights=0;
unsigned long millis() { return clockMs; }
void ticketMotor(bool value) { motor=value; }
void setAllMoles(bool value) { if(mcpReady) molesUp=value; lowered++; }
void turnAllMoleLightsOff() { moleLights++; }
void clearPlayerLights() { playerLights++; }
struct WireType { bool getWireTimeoutFlag() { return false; } } Wire;
struct Logger { std::string message; void println(const char* value) { message=value; } } Serial;
'''
        tests = r'''
int main() {
  checkLease(); assert(lowered==0);
  leaseEnabled=true; clockMs=5000; checkLease(); assert(lowered==0);
  clockMs=5001; checkLease();
  assert(!leaseEnabled && !motor && !ticketPayoutActive && !molesUp);
  assert(!hitDetectionEnabled && !puzzleHitArmed && !stopOutputsPending);
  assert(moleLights==1 && playerLights==1);
  assert(Serial.message.find("LEASE EXPIRED") != std::string::npos);
  checkLease(); assert(lowered==1);
  leaseEnabled=true; lastControllerCommand=clockMs; mcpReady=false;
  clockMs += 5001; checkLease(); assert(stopOutputsPending);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'lease.cpp'
            executable = Path(folder) / 'lease'
            source.write_text(harness + '\nvoid checkLease() {\n' + block + '\n}\n' + tests)
            subprocess.run(['c++', '-std=c++11', str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
