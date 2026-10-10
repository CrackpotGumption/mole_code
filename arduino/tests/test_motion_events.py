"""Exercise the actual FIFO detector with buffered, between-poll strikes."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class FifoTests(unittest.TestCase):
    def test_buffered_peaks_strongest_winner_rearm_and_overflow(self):
        source = (Path(__file__).resolve().parents[1] / 'MOLE_FINAL_NO_INTERVAL_v2/MOLE_FINAL_NO_INTERVAL_v2.ino').read_text()
        block = source[source.index('// Buffered puzzle detection'):source.index('// SENSOR MODES')]
        harness = r'''
#include <cassert>
#include <cstdint>
#include <sstream>
#include <string>
#include <deque>
#define MOLE_COUNT 5
#define MPU_ADDRESS 0x68
bool hitDetectionEnabled=false,commandFailed=false;
const uint8_t sensorChannel[5]={0,1,2,3,4};
unsigned long now=0, lastMechanicalAction=0;
unsigned long millis(){return now;}
void delay(unsigned long ms){now+=ms;}
uint8_t channel=0, reg=0;
uint8_t memory[5][256]={};
std::deque<uint8_t> queues[5], response;
bool failRead[5]={};
int failNext[5]={};
bool selectTCAChannel(uint8_t id){channel=id;return true;}
bool writeMPURegister(uint8_t address,uint8_t value){
 memory[channel][address]=value;
 if(address==0x6A && value==4) queues[channel].clear();
 return true;
}
void reportI2CTimeoutIfNeeded(){}
struct Bus {
 void clearWireTimeoutFlag(){}
 bool getWireTimeoutFlag(){return false;}
 void beginTransmission(uint8_t){}
 void write(uint8_t value){reg=value;}
 int endTransmission(bool=false){return 0;}
 void requestFrom(uint8_t,uint8_t count){
  response.clear();if(failRead[channel])return;
  if(failNext[channel]){failNext[channel]--;return;}
  for(int i=0;i<count;i++){
   if(reg==0x74){if(queues[channel].empty())break;response.push_back(queues[channel].front());queues[channel].pop_front();}
   else if(reg==0x72) response.push_back(i==0 ? queues[channel].size()>>8 : queues[channel].size()&255);
   else response.push_back(memory[channel][reg+i]);
  }
 }
 int available(){return response.size();}
 uint8_t read(){auto v=response.front();response.pop_front();return v;}
} Wire;
struct Logger {
 std::ostringstream buffer;
 template<class T> void print(T value){buffer<<+value;}
 void print(const char* value){buffer<<value;}
 template<class T> void println(T value){buffer<<+value<<"\n";}
 void println(const char* value){buffer<<value<<"\n";}
} Serial;
void sample(int id,int16_t z,int16_t x=0,int16_t y=0){
 if(memory[id][0x23]!=8)return;
 queues[id].push_back(((uint16_t)x)>>8);queues[id].push_back(x&255);
 queues[id].push_back(((uint16_t)y)>>8);queues[id].push_back(y&255);
 queues[id].push_back(((uint16_t)z)>>8);queues[id].push_back(z&255);
}
'''
        tests = r'''
void advance(unsigned long duration){
 auto end=now+duration;
 while(now<end){now+=10;for(int id=0;id<5;id++)sample(id,-2000);checkFifoHits();}
}
int main(){
 for(int id=0;id<5;id++)memory[id][0x75]=0x68;
 failNext[1]=1;assert(enableFifoPolling(7000,1500,2));
 assert(Serial.buffer.str().find("FIFO_CONFIG_RETRY MOLE 1 ATTEMPT 1 REGISTER 117")!=std::string::npos);
 assert(memory[0][0x19]==9 && memory[0][0x1A]==1 && memory[0][0x23]==0);
 advance(1400);assert(!fifoCollecting[0]);
 sample(0,-32768);assert(queues[0].empty());
 advance(200);sample(0,-32768);advance(100);
 assert(!fifoSettled[0] && fifoArmed);
 assert(Serial.buffer.str().find("FIFO WAIT_QUIET MOLE 0")!=std::string::npos);
 advance(340);assert(fifoSettled[4] && fifoBaseline[0]==-2000);
 Serial.buffer.str("");
 // Both impulses are gone before the next poll; their FIFO samples remain.
 sample(0,-12000);sample(3,-18000);advance(50);
 assert(!fifoArmed);
 assert(Serial.buffer.str().find("HIT 3 3 16000")!=std::string::npos);
 assert(Serial.buffer.str().find("WINNER 3 THRESHOLD 7000")!=std::string::npos);
 assert(Serial.buffer.str().find("HIT_TRACE SAMPLE MOLE 3")!=std::string::npos);
 auto first=Serial.buffer.str();advance(100);assert(Serial.buffer.str()==first);
 // Failure show disables collection and empties all old buffered movement.
 stopFifoPolling();
 for(int id=0;id<5;id++) { sample(id,-32768);assert(queues[id].empty()); }
 assert(Serial.buffer.str().find("FIFO CLEARED MOLE 4 BYTES 0")!=std::string::npos);
 assert(enableFifoPolling(7000,1500,2));advance(2040);
 sample(0,-32768);restartFifoSettlingAfterMotion();
 assert(!fifoCollecting[0] && memory[0][0x23]==0);
 advance(2040);assert(fifoArmed);Serial.buffer.str("");
 sample(0,-32768);memory[3][0x3A]=0x10;advance(50);
 assert(fifoArmed && Serial.buffer.str().find("HIT ")==std::string::npos);
 memory[3][0x3A]=0;advance(50);assert(fifoArmed);
 // Failed partial sweep cannot pick a winner.
 sample(1,-20000);failRead[4]=true;advance(50);
 assert(fifoArmed);failRead[4]=false;advance(100);
 sample(4,-32768);advance(50);assert(!fifoArmed);
 assert(Serial.buffer.str().find("HIT 4 4 30768")!=std::string::npos);
 stopFifoPolling();assert(!fifoPolling && memory[0][0x23]==0);
 assert(enableFifoPolling(10000,1500,1));advance(2040);Serial.buffer.str("");
 sample(0,-30000);sample(3,-2000,0,-12000);advance(50);
 assert(!fifoArmed && Serial.buffer.str().find("HIT 3 3 12000")!=std::string::npos);
 stopFifoPolling();
 assert(enableFifoPolling(10000));advance(2040);Serial.buffer.str("");
 sample(1,-2000,0,12000);advance(50);
 assert(fifoArmed && Serial.buffer.str().find("HIT ")==std::string::npos);
 sample(1,-2000,0,-12000);advance(50);
 assert(!fifoArmed && Serial.buffer.str().find("HIT 1 1 12000")!=std::string::npos);
 stopFifoPolling();
 fifoConfiguredMask=0;memory[3][0x75]=0x70;assert(!enableFifoPolling(7000,1500,2));assert(commandFailed && !fifoPolling);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fifo.cpp'
            path.write_text(harness + block + tests)
            binary = Path(folder) / 'fifo'
            subprocess.run(['c++', '-std=c++11', '-Wall', '-Wextra', str(path), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
