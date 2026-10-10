from pathlib import Path
import subprocess
import tempfile
import unittest


class SensorInitializationTests(unittest.TestCase):
    def test_staggered_init_and_register_failure_diagnostics(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v2/MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()
        block = source[source.index('bool initializeSensorChecked'):source.index('void initializeSensors()')]
        harness = r'''
#include <cassert>
#include <cstdint>
#include <sstream>
#include <string>
#define MPU_ADDRESS 0x68
uint8_t sensorChannel[5]={0,1,2,3,4};
unsigned long waited=0;
uint8_t selected=0;
void delay(unsigned long ms){waited+=ms;}
bool selectTCAChannel(uint8_t id){selected=id;return id!=1;}
bool wakeSensor(uint8_t){delay(52);return true;}
bool configureAccelerometerRange(uint8_t){return true;}
void reportI2CTimeoutIfNeeded(){}
struct Bus{
 void clearWireTimeoutFlag(){}
 bool getWireTimeoutFlag(){return false;}
 void beginTransmission(uint8_t){}
 void write(uint8_t){}
 int endTransmission(bool=true){return 0;}
 void requestFrom(uint8_t,uint8_t){}
 int available(){return 1;}
 uint8_t read(){return selected==2?0:0x18;}
}Wire;
struct Logger{
 std::ostringstream buffer;
 template<class T>void print(T v){buffer<<+v;}
 void print(const char* v){buffer<<v;}
 template<class T>void println(T v){buffer<<+v<<"\n";}
}Serial;
'''
        test = r'''
int main(){
 assert(initializeSensorChecked(0));assert(waited==87);
 assert(!initializeSensorChecked(1));
 assert(Serial.buffer.str().find("MOLE 1 CHANNEL 1 STEP MUX_SELECT")!=std::string::npos);
 assert(!initializeSensorChecked(2));
 assert(Serial.buffer.str().find("STEP RANGE_READBACK_REG_28 ACTUAL 0 TIMEOUT 0")!=std::string::npos);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'init.cpp'; binary = Path(folder) / 'init'
            path.write_text(harness + block + test)
            subprocess.run(['c++', '-std=c++11', str(path), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
