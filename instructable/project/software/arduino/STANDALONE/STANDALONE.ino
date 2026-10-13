// Independent standalone prototype. Physical calibration/AVR compile pending.
#include <Wire.h>
#include <Adafruit_MCP23X17.h>
#include <Adafruit_NeoPixel.h>
#include <avr/wdt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint8_t resetCause __attribute__((section(".noinit")));
void rememberReset() __attribute__((naked, section(".init3")));
void rememberReset() { resetCause = MCUSR; MCUSR = 0; wdt_disable(); }
const uint8_t COUNT=5, PIXELS=20, START_PIN=24;
Adafruit_MCP23X17 driver;
Adafruit_NeoPixel rings[COUNT] = {
  Adafruit_NeoPixel(PIXELS,14,NEO_GRB+NEO_KHZ800),
  Adafruit_NeoPixel(PIXELS,15,NEO_GRB+NEO_KHZ800),
  Adafruit_NeoPixel(PIXELS,16,NEO_GRB+NEO_KHZ800),
  Adafruit_NeoPixel(PIXELS,17,NEO_GRB+NEO_KHZ800),
  Adafruit_NeoPixel(PIXELS,18,NEO_GRB+NEO_KHZ800)};
bool ready=false, lease=false, armed=false;
int active=-1;
unsigned long token=0, lastHost=0, raisedAt=0, lastSample=0, lastHit=0;
long baseline[COUNT]={}, threshold=6000;
unsigned long settleMs=200, cooldownMs=300;
char buffer[96]; uint8_t used=0; bool overflow=false;
bool buttonRaw=HIGH, buttonStable=HIGH;
unsigned long buttonChanged=0;

bool selectSensor(uint8_t i) {
  Wire.beginTransmission(0x70); Wire.write((uint8_t)(1<<i));
  return Wire.endTransmission()==0;
}
bool writeReg(uint8_t reg,uint8_t value) {
  Wire.beginTransmission(0x68); Wire.write(reg); Wire.write(value);
  return Wire.endTransmission()==0;
}
bool readY(uint8_t i,int16_t &y) {
  Wire.clearWireTimeoutFlag();
  if (!selectSensor(i)) return false;
  Wire.beginTransmission(0x68); Wire.write(0x3D);
  if (Wire.endTransmission(false)!=0) return false;
  Wire.requestFrom((uint8_t)0x68,(uint8_t)2);
  if (Wire.getWireTimeoutFlag() || Wire.available()!=2) return false;
  uint16_t hi=Wire.read(),lo=Wire.read(); y=(int16_t)((hi<<8)|lo);
  return true;
}
bool output(uint8_t i,bool up) {
  if (!ready) return false;
  Wire.clearWireTimeoutFlag();
  driver.digitalWrite(i,up?HIGH:LOW);
  return driver.digitalRead(i)==(up?HIGH:LOW) && !Wire.getWireTimeoutFlag();
}
void stopAll() {
  armed=false; active=-1; lease=false;
  bool failed=false;
  for (uint8_t i=0;i<COUNT;i++) {
    if (!output(i,false)) failed=true;
    rings[i].clear(); rings[i].show();
  }
  if (failed) Serial.println(F("ERROR STOP OUTPUT FAILED"));
}
void command(char *line) {
  int i,r,g,b; unsigned long id,s,c; long t;
  if (!strcmp(line,"SAFE STOP")) { stopAll(); Serial.println(F("OK SAFE STOP")); return; }
  if (!ready) { Serial.println(F("ERROR NOT READY")); return; }
  if (!strcmp(line,"LEASE ON")) { lease=true; lastHost=millis(); Serial.println(F("OK LEASE")); return; }
  if (!strcmp(line,"KEEPALIVE")) { lastHost=millis(); return; }
  if (sscanf(line,"CONFIG %ld %lu %lu",&t,&s,&c)==3 && t>0 && t<65536 && s<=3000 && c<=3000) {
    threshold=t;settleMs=s;cooldownMs=c; Serial.println(F("OK CONFIG"));return;
  }
  if (sscanf(line,"LIGHT %d %d %d %d",&i,&r,&g,&b)==4 && i>=0 && i<COUNT) {
    rings[i].fill(rings[i].Color(constrain(r,0,255),constrain(g,0,255),constrain(b,0,255)));
    rings[i].show(); return;
  }
  if (!strcmp(line,"MOLES ALL DOWN")) {
    armed=false;active=-1;
    for(uint8_t j=0;j<COUNT;j++) if(!output(j,false)) {stopAll();Serial.println(F("ERROR OUTPUT"));return;}
    Serial.println(F("OK MOLES ALL DOWN"));return;
  }
  char direction[8];
  if(sscanf(line,"MOLE %d %7s",&i,direction)==2 && i>=0 && i<COUNT && !strcmp(direction,"DOWN")) {
    if(active==i) {armed=false;active=-1;}
    if(!output(i,false)) {stopAll();Serial.println(F("ERROR OUTPUT"));}return;
  }
  if(sscanf(line,"TARGET %d %lu",&i,&id)==2 && i>=0 && i<COUNT && lease) {
    armed=false;
    // Resting baseline was collected while outputs LOW at startup.
    if(!output(i,true)) {stopAll();Serial.println(F("ERROR OUTPUT"));return;}
    active=i;token=id;raisedAt=millis();armed=true;return;
  }
  Serial.println(F("ERROR UNKNOWN COMMAND"));
}
void setup() {
  pinMode(START_PIN,INPUT_PULLUP);
  buttonRaw=buttonStable=digitalRead(START_PIN);
  Serial.begin(115200);Wire.begin();Wire.setWireTimeout(25000,true);
  ready=driver.begin_I2C(0x20);
  if(ready) {
    for(uint8_t i=0;i<COUNT;i++) {
      driver.digitalWrite(i,LOW);driver.pinMode(i,OUTPUT);
      if(driver.digitalRead(i)!=LOW) ready=false;
    }
  }
  for(uint8_t i=0;i<COUNT;i++) {rings[i].begin();rings[i].clear();rings[i].show();}
  bool sensors=true;
  for(uint8_t i=0;i<COUNT;i++) {
    if(!selectSensor(i)||!writeReg(0x6B,0)||!writeReg(0x1C,0x18)) {sensors=false;continue;}
    long sum=0;uint8_t n=0;
    for(uint8_t k=0;k<32;k++) {int16_t y;if(readY(i,y)){sum+=y;n++;}delay(5);}
    if(n<32) sensors=false;else baseline[i]=sum/n;
  }
  if(!ready || !sensors) {
    stopAll(); ready=false; Serial.println(F("ERROR STARTUP HARDWARE"));
  } else Serial.println(F("READY STANDALONE_V1"));
  // Subsequent resets request LOW again. LOW direction requires plumbing verification.
  wdt_enable(WDTO_2S);
}
void loop() {
  wdt_reset();
  // Limit work per loop so malformed serial cannot starve lease/button logic.
  for(uint8_t n=0;n<64 && Serial.available();n++) {
    char ch=Serial.read();
    if(ch=='\n') {
      buffer[used]=0;
      if(!overflow) command(buffer); else Serial.println(F("ERROR LINE TOO LONG"));
      used=0;overflow=false;
    } else if(ch!='\r') {
      if(used<sizeof(buffer)-1) buffer[used++]=ch;else overflow=true;
    }
  }
  unsigned long now=millis();
  if(lease && now-lastHost>3000) {stopAll();Serial.println(F("LEASE EXPIRED"));}
  bool raw=digitalRead(START_PIN);
  if(raw!=buttonRaw) {buttonRaw=raw;buttonChanged=now;}
  if(raw!=buttonStable && now-buttonChanged>=30) {
    buttonStable=raw; if(raw==LOW) Serial.println(F("START"));
  }
  if(armed && active>=0 && now-raisedAt>=settleMs && now-lastSample>=10 && now-lastHit>=cooldownMs) {
    lastSample=now;int16_t y;
    if(!readY(active,y)) {stopAll();Serial.println(F("ERROR SENSOR READ"));return;}
    long delta=labs((long)y-baseline[active]);
    if(delta>=threshold) {
      armed=false;lastHit=now;
      Serial.print(F("HIT "));Serial.print(active);Serial.print(' ');Serial.print(token);Serial.print(' ');Serial.println(delta);
    }
  }
}
