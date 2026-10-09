#include <Wire.h>
#include <Adafruit_MCP23X17.h>
#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

// Standard cabinet mapping. No RFID, lights, or tickets in this sketch.
const uint8_t COUNT = 5, MCP_ADDR = 0x20, MUX_ADDR = 0x70, MPU_ADDR = 0x68;
const char* names[COUNT] = {"FRONT LEFT / MARTIN", "FRONT CENTER / DAPHNE",
  "FRONT RIGHT / NILES", "BACK LEFT / FRASIER", "BACK RIGHT / ROZ"};
const unsigned long SAMPLE_MS = 5, BASELINE_MS = 500, GAP_MS = 500;
const unsigned long DEFAULT_WINDOW_MS = 2000, MAX_WINDOW_MS = 3000;
Adafruit_MCP23X17 mcp;
bool ready = false, csv = false, testAll = false;
uint8_t mole = 0;
unsigned long windowMs = DEFAULT_WINDOW_MS, stageStart = 0, lastSample = 0, lastCsv = 0;
enum Stage { IDLE, BASELINE, EXTENDING, RETRACTING, GAP };
Stage stage = IDLE;
float base[3], sums[3], noiseThreshold = 400;
float baselineAverage[COUNT][3] = {};
unsigned int baselineReadCount[COUNT] = {};
int16_t low[3], high[3];
unsigned int baselineSamples = 0;
float speedReference[2] = {3000, 3000}; // accepted Y delta: 1500..4500; zero disables advice
const float FAST_RATIO = 1.5f, SLOW_RATIO = 0.5f;
struct Trace {
  unsigned int samples, failed, clipped;
  bool active;
  unsigned long firstActivity, lastActivity, captureMs;
  float peak;
  int16_t rawMin[3], rawMax[3];
  float deltaMin[3], deltaMax[3], axisPeakDelta[3];
};
Trace records[COUNT][2] = {};

bool selectSensor(uint8_t id) {
  Wire.beginTransmission(MUX_ADDR); Wire.write(1 << id);
  return Wire.endTransmission() == 0;
}
bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU_ADDR); Wire.write(reg); Wire.write(value);
  return Wire.endTransmission() == 0;
}
bool prepareSensor(uint8_t id) {
  return selectSensor(id) && writeRegister(0x6B, 0x00)
    && writeRegister(0x1C, 0x18) && writeRegister(0x1A, 0x00);
}
bool readSensor(int16_t values[3]) {
  Wire.clearWireTimeoutFlag();
  if (!selectSensor(mole)) return false;
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  Wire.requestFrom(MPU_ADDR, (uint8_t)6);
  if (Wire.getWireTimeoutFlag() || Wire.available() < 6) return false;
  for (uint8_t axis = 0; axis < 3; axis++) {
    uint16_t hi = (uint8_t)Wire.read(), lo = (uint8_t)Wire.read();
    values[axis] = (int16_t)((hi << 8) | lo);
  }
  return true;
}
bool output(uint8_t id, bool up) {
  Wire.clearWireTimeoutFlag();
  mcp.digitalWrite(id, up ? HIGH : LOW);
  int actual = mcp.digitalRead(id);
  bool ok = !Wire.getWireTimeoutFlag() && actual == (up ? HIGH : LOW);
  if (!ok) { Serial.print(F("ERROR OUTPUT/I2C mole=")); Serial.println(id); }
  return ok;
}
void stopTest() {
  stage = IDLE; testAll = false;
  if (ready) for (uint8_t id = 0; id < COUNT; id++) output(id, false);
}
bool usable(const Trace& trace) {
  return trace.samples >= 10 && trace.failed * 5UL <= trace.samples;
}
void recommendation(uint8_t id, uint8_t dir) {
  float ref = speedReference[dir];
  if (ref <= 0) return;
  Trace& trace = records[id][dir];
  if (!usable(trace)) { Serial.println(F("ADVICE: insufficient sensor data; retest")); return; }
  Serial.print(F("SPEED_INDEX_Y_DELTA ")); Serial.println((unsigned long)(trace.peak + 0.5f));
  Serial.print(F("REFERENCE_SPEED_INDEX ")); Serial.println((unsigned long)(ref + 0.5f));
  if (trace.clipped) {
    Serial.print(F("ADVICE: TIGHTEN ")); Serial.print(dir == 0 ? "LEFT" : "RIGHT");
    Serial.println(F(" restrictor: sensor saturated/high response; retest for an unclipped comparison"));
  } else if (trace.peak > ref * FAST_RATIO) {
    Serial.print(F("ADVICE: TIGHTEN ")); Serial.print(dir == 0 ? "LEFT" : "RIGHT");
    Serial.println(F(" restrictor: high relative speed index; retest"));
  } else if (trace.peak < ref * SLOW_RATIO) {
    Serial.print(F("ADVICE: LOOSEN ")); Serial.print(dir == 0 ? "LEFT" : "RIGHT");
    Serial.println(F(" restrictor: slow/crawling relative response; confirm movement and retest"));
  } else Serial.println(F("ADVICE: KEEP setting: within target +/-50%"));
}
void printPair(uint8_t id) {
  Serial.print(F("RESULT MOLE ")); Serial.print(id);
  Serial.print(F(" UP_Y_DELTA ")); Serial.print((unsigned long)(records[id][0].peak + 0.5f));
  Serial.print(F(" DOWN_Y_DELTA ")); Serial.print((unsigned long)(records[id][1].peak + 0.5f));
  Serial.print(F(" UP_READS ")); Serial.print(records[id][0].samples);
  Serial.print(F(" DOWN_READS ")); Serial.println(records[id][1].samples);
  Serial.flush();
}
void printBaseline(uint8_t id) {
  Serial.print(F("BASELINE MOLE ")); Serial.print(id);
  Serial.print(F(" READS ")); Serial.print(baselineReadCount[id]);
  Serial.print(F(" Y_AVG ")); Serial.println(baselineAverage[id][1], 1);
}
void printAxes(uint8_t id, uint8_t dir) {
  Trace& t = records[id][dir];
  printBaseline(id);
  if (!t.samples) { Serial.println(F("AXIS_PEAKS UNAVAILABLE: no successful reads")); return; }
  for (uint8_t axis = 1; axis < 2; axis++) {
    Serial.print(F("AXIS ")); Serial.print("XYZ"[axis]);
    Serial.print(F(" BASE_AVG ")); Serial.print(baselineAverage[id][axis], 1);
    Serial.print(F(" RAW_MIN ")); Serial.print(t.rawMin[axis]);
    Serial.print(F(" RAW_MAX ")); Serial.print(t.rawMax[axis]);
    Serial.print(F(" DELTA_MIN ")); Serial.print(t.deltaMin[axis], 1);
    Serial.print(F(" DELTA_MAX ")); Serial.print(t.deltaMax[axis], 1);
    Serial.print(F(" PEAK_DELTA ")); Serial.print(t.axisPeakDelta[axis], 1);
    Serial.print(F(" PEAK_ABS_DELTA ")); Serial.println(fabs(t.axisPeakDelta[axis]), 1);
  }
}
void printTrace(uint8_t id, uint8_t dir) {
  Trace& t = records[id][dir];
  Serial.print(F("MOLE ")); Serial.print(id); Serial.print(F(" ")); Serial.print(names[id]);
  Serial.println(dir == 0 ? " EXTENSION" : " RETRACTION");
  Serial.print(F("READS ")); Serial.print(t.samples); Serial.print(F(" FAILURES ")); Serial.print(t.failed);
  Serial.print(F(" CLIPPED ")); Serial.println(t.clipped);
  printAxes(id, dir);
  if (!t.active) { Serial.println(F("NO MOTION SIGNAL ABOVE BASELINE NOISE")); recommendation(id, dir); return; }
  Serial.print(F("RESPONSE_DELAY_MS ")); Serial.println(t.firstActivity);
  Serial.print(F("ACTIVITY_SPAN_MS ")); Serial.println(t.lastActivity - t.firstActivity);
  Serial.print(F("LAST_ACTIVITY_AFTER_COMMAND_MS ")); Serial.println(t.lastActivity);
  Serial.print(F("PEAK_Y_BASELINE_DELTA_COUNTS ")); Serial.println((unsigned long)(t.peak + 0.5f));
  if (t.active && t.lastActivity + 100 >= t.captureMs)
    Serial.println(F("NOTE: activity continues at end of window; timing incomplete, consider longer window"));
  recommendation(id, dir);
}
void summary() {
  Serial.println(F("=== TIMING / SHOCK COMPARISON (ACCELEROMETER PROXIES) ==="));
  for (uint8_t id = 0; id < COUNT; id++) {
    if (!records[id][0].samples && !records[id][1].samples
        && !records[id][0].failed && !records[id][1].failed) continue;
    printPair(id);
    for (uint8_t dir = 0; dir < 2; dir++) printTrace(id, dir);
  }
}
void startMole() {
  memset(records[mole], 0, sizeof(records[mole]));
  records[mole][0].captureMs = windowMs; records[mole][1].captureMs = windowMs;
  if (!prepareSensor(mole)) { Serial.println(F("ERROR SENSOR NOT RESPONDING")); stopTest(); return; }
  memset(sums, 0, sizeof(sums)); baselineSamples = 0;
  for (uint8_t a = 0; a < 3; a++) { low[a] = 32767; high[a] = -32768; }
  stage = BASELINE; stageStart = millis(); lastSample = stageStart;
  Serial.print(F("TESTING ")); Serial.print(mole); Serial.print(F(" ")); Serial.println(names[mole]);
}
void sampleTrace(unsigned long now) {
  int16_t values[3]; bool ok = readSensor(values);
  if (stage == BASELINE) {
    if (ok) {
      baselineSamples++;
      for (uint8_t a = 0; a < 3; a++) {
        sums[a] += values[a]; if (values[a] < low[a]) low[a] = values[a];
        if (values[a] > high[a]) high[a] = values[a];
      }
    }
    return;
  }
  uint8_t dir = stage == EXTENDING ? 0 : 1; Trace& t = records[mole][dir];
  if (!ok) { t.failed++; return; }
  t.samples++; float magnitude = 0; bool clipped = false;
  for (uint8_t a = 1; a < 2; a++) {
    float delta = values[a] - base[a]; magnitude = fabs(delta);
    if (t.samples == 1 || values[a] < t.rawMin[a]) t.rawMin[a] = values[a];
    if (t.samples == 1 || values[a] > t.rawMax[a]) t.rawMax[a] = values[a];
    if (t.samples == 1 || delta < t.deltaMin[a]) t.deltaMin[a] = delta;
    if (t.samples == 1 || delta > t.deltaMax[a]) t.deltaMax[a] = delta;
    if (fabs(delta) > fabs(t.axisPeakDelta[a])) t.axisPeakDelta[a] = delta;
    if (values[a] <= -32760 || values[a] >= 32760) clipped = true;
  }
  if (clipped) t.clipped++;
  if (magnitude > t.peak) t.peak = magnitude;
  unsigned long elapsed = now - stageStart;
  if (magnitude >= noiseThreshold) {
    if (!t.active) { t.active = true; t.firstActivity = elapsed; }
    t.lastActivity = elapsed;
  }
  if (csv && now - lastCsv >= 10) {
    lastCsv = now;
    Serial.print(F("CSV,")); Serial.print(mole); Serial.print(dir == 0 ? ",EXT," : ",RET,");
    Serial.print(elapsed);
    Serial.print(F(",")); Serial.print(values[1]);
    Serial.print(F(",")); Serial.print(values[1] - base[1], 1);
    Serial.print(F(",")); Serial.println(magnitude, 1);
  }
}
void updateTest() {
  if (stage == IDLE) return;
  unsigned long now = millis();
  if (stage != GAP && now - lastSample >= SAMPLE_MS) { lastSample = now; sampleTrace(now); }
  if (stage == BASELINE && now - stageStart >= BASELINE_MS) {
    if (baselineSamples < 10) { Serial.println(F("ERROR INSUFFICIENT BASELINE READS")); stopTest(); return; }
    noiseThreshold = 400;
    for (uint8_t a = 0; a < 3; a++) {
      base[a] = sums[a] / baselineSamples;
      baselineAverage[mole][a] = base[a];
      float band = 3.0f * ((long)high[a] - low[a]); if (a == 1 && band > noiseThreshold) noiseThreshold = band;
    }
    baselineReadCount[mole] = baselineSamples;
    printBaseline(mole);
    Serial.print(F("ACTIVITY_THRESHOLD_COUNTS ")); Serial.println(noiseThreshold, 1);
    stage = EXTENDING; stageStart = millis();
    if (!output(mole, true)) stopTest();
  } else if (stage == EXTENDING && now - stageStart >= windowMs) {
    stage = RETRACTING; stageStart = millis();
    if (!output(mole, false)) stopTest();
  } else if (stage == RETRACTING && now - stageStart >= windowMs) {
    stage = GAP; stageStart = millis();
    printPair(mole);
    printTrace(mole, 0); printTrace(mole, 1);
    Serial.println(F("RESULT END"));
  } else if (stage == GAP && now - stageStart >= GAP_MS) {
    if (testAll && ++mole < COUNT) startMole();
    else { stopTest(); summary(); Serial.println(F("TEST COMPLETE")); }
  }
}
void help() {
  Serial.println(F("=== PISTON + ACCELEROMETER DIAGNOSTIC ==="));
  Serial.println(F("TEST <0-4> [window_ms] | 0..4 | ALL [window_ms] | STOP | STATUS"));
  Serial.println(F("Window defaults to 2000 ms; allowed 500..3000 ms per direction."));
  Serial.println(F("Y delta target: 3000; acceptable 1500..4500 for UP and DOWN."));
  Serial.println(F("REFERENCE <up_peak_delta> <down_peak_delta>; 0 disables advice"));
  Serial.println(F("UP: high=tighten LEFT, low=loosen LEFT. DOWN: same rule on RIGHT."));
  Serial.println(F("CSV ON|OFF | REPORT | HELP. Configuration resets on board restart."));
  Serial.println(F("Y ONLY: peak absolute Y-baseline delta, not calibrated mm/s."));
}
void handleCommand(char* line) {
  for (char* p = line; *p; p++) *p = toupper((unsigned char)*p);
  char action[12] = ""; int id = -1;
  unsigned long duration = DEFAULT_WINDOW_MS;
  if (sscanf(line, "%11s", action) != 1) return;
  if (!strcmp(action, "STOP")) { stopTest(); Serial.println(F("STOPPED")); return; }
  if (!strcmp(action, "HELP")) { help(); return; }
  if (!strcmp(action, "CSV")) { csv = !strcmp(line, "CSV ON"); Serial.println(csv ? "CSV ON" : "CSV OFF"); return; }
  if (!strcmp(action, "STATUS")) {
    Serial.print(F("MCP_READY ")); Serial.print(ready ? 1 : 0);
    Serial.print(F(" STAGE ")); Serial.print((int)stage); Serial.print(F(" MOLE ")); Serial.println(mole); return;
  }
  if (!strcmp(action, "REPORT")) { summary(); return; }
  if (stage != IDLE) { Serial.println(F("ERROR TEST ACTIVE; STOP first")); return; }
  if (!strcmp(action, "REFERENCE")) {
    unsigned long up, down;
    if (sscanf(line, "%*s %lu %lu", &up, &down) == 2 && up <= 120000 && down <= 120000) {
      speedReference[0] = up; speedReference[1] = down; Serial.println(F("OK REFERENCE"));
    } else Serial.println(F("ERROR REFERENCE"));
    return;
  }
  bool all = !strcmp(action, "ALL");
  if (all) { sscanf(line, "%*s %lu", &duration); id = 0; }
  else if (strlen(action) == 1 && action[0] >= '0' && action[0] <= '4') id = action[0] - '0';
  else if (strcmp(action, "TEST") || sscanf(line, "%*s %d %lu", &id, &duration) < 1) {
    Serial.println(F("ERROR COMMAND")); return;
  }
  if (!ready || id < 0 || id >= COUNT || duration < 500 || duration > MAX_WINDOW_MS) {
    Serial.println(F("ERROR MCP/ID/WINDOW")); return;
  }
  stopTest(); mole = id; windowMs = duration; testAll = all;
  if (all) memset(records, 0, sizeof(records));
  startMole();
}
char commandBuffer[96]; uint8_t commandLength = 0; bool overflowed = false;
void readCommands() {
  while (Serial.available()) {
    char value = Serial.read(); if (value == '\r') continue;
    if (value == '\n') {
      if (!overflowed) { commandBuffer[commandLength] = '\0'; handleCommand(commandBuffer); }
      commandLength = 0; overflowed = false;
    } else if (!overflowed) {
      if (commandLength >= sizeof(commandBuffer) - 1) { overflowed = true; Serial.println(F("ERROR COMMAND TOO LONG")); }
      else commandBuffer[commandLength++] = value;
    }
  }
}
void setup() {
  Serial.begin(115200); Wire.begin(); Wire.setWireTimeout(25000, true);
  ready = mcp.begin_I2C(MCP_ADDR);
  if (ready) {
    for (uint8_t id = 0; id < COUNT; id++) { mcp.digitalWrite(id, LOW); mcp.pinMode(id, OUTPUT); }
    stopTest();
  } else Serial.println(F("ERROR MCP NOT FOUND"));
  help(); Serial.println(F("READY: no automatic movement"));
}
void loop() { readCommands(); updateTest(); }
