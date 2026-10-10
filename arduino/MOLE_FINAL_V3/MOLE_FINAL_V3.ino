// V3: V2 cabinet controls with the verbatim September hit-detection implementation.
#include "firmware_identity.h"
#ifdef __AVR__
#include <avr/wdt.h>
uint8_t resetCause __attribute__((section(".noinit")));
void rememberReset() __attribute__((naked, section(".init3")));
void rememberReset() { resetCause = MCUSR; MCUSR = 0; wdt_disable(); }
#endif
bool commandFailed = false;
bool mcpReady = false;
bool mcpInitialized = false;
bool stopOutputsPending = false;
uint8_t sensorConfiguredMask = 0;
bool leaseEnabled = false;
unsigned long lastControllerCommand = 0;
const unsigned long CONTROLLER_LEASE_MS = 5000;
#include <Wire.h>

#include <SPI.h>

#include <Adafruit_NeoPixel.h>

#include <Adafruit_MCP23X17.h>

#include <MFRC522.h>

#include <math.h>

// ============================================================

// GENERAL

// ============================================================

#define MOLE_COUNT 5

#define MOLE_LED_COUNT 21

#define PLAYER_COUNT 6

#define TCA_ADDRESS 0x70

#define MPU_ADDRESS 0x68

// Reserved accelerometer INT inputs, in standard mole order.
// Mega A8..A12 are digital 62..66 / PK0..PK4 / PCINT16..PCINT20.
// Pin-change ISR/configuration is not enabled yet; polling remains active.
const uint8_t accelerometerInterruptPin[MOLE_COUNT] = {A8, A9, A10, A11, A12};

const long HIT_REPORT_THRESHOLD = 4000;
const unsigned long HIT_COOLDOWN = 500;
const unsigned long SENSOR_INTERVAL = 10;
const unsigned long RFID_POLL_INTERVAL = 250;
unsigned long lastRFIDPoll = 0;
bool rfidReaderAvailable = false;
bool rfidPollingEnabled = true;

// I2C / main-loop diagnostics.

// Wire timeout prevents a bad I2C transaction from blocking forever.

const unsigned long I2C_TIMEOUT_US = 25000;

const unsigned long HEARTBEAT_INTERVAL = 1000;
bool heartbeatEnabled = false;

unsigned long lastHeartbeat = 0;

unsigned long loopCounter = 0;

// V1 performs hit classification; Python applies gameplay rules.

// ============================================================

// MOLE LOGICAL ORDER

//

// Hardware IDs only. Game/character mapping lives in Python.

// 0 = sensor 0 / solenoid 0 / ring pin 14

// 1 = sensor 1 / solenoid 1 / ring pin 15

// 2 = sensor 2 / solenoid 2 / ring pin 16

// 3 = sensor 3 / solenoid 3 / ring pin 17

// 4 = sensor 4 / solenoid 4 / ring pin 18

// ============================================================

const char* positionName[MOLE_COUNT] = {

  "MOLE 0",

  "MOLE 1",

  "MOLE 2",

  "MOLE 3",

  "MOLE 4"

};

// ============================================================

// ACCELEROMETER / TCA CHANNELS

// ============================================================

const uint8_t sensorChannel[MOLE_COUNT] = {

  0,

  1,

  2,

  3,

  4

};

// ============================================================

// SOLENOID MCP23017 OUTPUTS

// ============================================================

const uint8_t solenoidOutput[MOLE_COUNT] = {

  0,

  1,

  2,

  3,

  4

};

Adafruit_MCP23X17 mcp;

// ============================================================

// MOLE NEOPIXELS

// ============================================================

Adafruit_NeoPixel mole0Lights(

  MOLE_LED_COUNT,

  14,

  NEO_GRB + NEO_KHZ800

);

Adafruit_NeoPixel mole1Lights(

  MOLE_LED_COUNT,

  15,

  NEO_GRB + NEO_KHZ800

);

Adafruit_NeoPixel mole2Lights(

  MOLE_LED_COUNT,

  16,

  NEO_GRB + NEO_KHZ800

);

Adafruit_NeoPixel mole3Lights(

  MOLE_LED_COUNT,

  17,

  NEO_GRB + NEO_KHZ800

);

Adafruit_NeoPixel mole4Lights(

  MOLE_LED_COUNT,

  18,

  NEO_GRB + NEO_KHZ800

);

Adafruit_NeoPixel* lights[MOLE_COUNT] = {

  &mole0Lights,

  &mole1Lights,

  &mole2Lights,

  &mole3Lights,

  &mole4Lights

};

// ============================================================

// PLAYER STATUS NEOPIXELS

//

// 0 = 001

// 1 = 002

// 2 = 003

// 3 = 004

// 4 = 005

// 5 = 006

// ============================================================

#define PLAYER_LIGHT_PIN 6

Adafruit_NeoPixel playerLights(

  PLAYER_COUNT,

  PLAYER_LIGHT_PIN,

  NEO_GRB + NEO_KHZ800

);

// ============================================================

Adafruit_NeoPixel playerLightsAlternate(PLAYER_COUNT, 7, NEO_GRB + NEO_KHZ800);

// RFID RC522

//

// MEGA:

//

// SDA / SS -> 53

// SCK      -> 52

// MOSI     -> 51

// MISO     -> 50

// RST      -> 5

// VCC      -> 3.3V

// GND      -> GND

// ============================================================

#define RFID_SS_PIN 53

#define RFID_RST_PIN 5

MFRC522 rfid(

  RFID_SS_PIN,

  RFID_RST_PIN

);

MFRC522::MIFARE_Key defaultKey;

// ============================================================

// TICKET DISPENSER

// ============================================================

#define TICKET_MOTOR_PIN 22

#define TICKET_SENSOR_PIN 23

const uint8_t TICKET_MOTOR_ACTIVE = HIGH;

const uint8_t TICKET_MOTOR_INACTIVE = LOW;

const uint8_t TICKET_SENSOR_ACTIVE = LOW;

const unsigned long TICKET_TIMEOUT_PER_TICKET = 2000;

// ============================================================

// SEPTEMBER HIT DETECTION STATE

// ============================================================

bool hitDetectionEnabled = false;
unsigned long lastSensorPoll = 0;
const unsigned long MECHANICAL_SETTLE_TIME = 750;

unsigned long lastMechanicalAction = 0;

unsigned long lastHitTime[MOLE_COUNT] = {

  0, 0, 0, 0, 0

};

// ============================================================

// SERIAL COMMAND BUFFER

// ============================================================

String commandBuffer = "";
bool commandOverflow = false;

// ============================================================

// MAIN LOOP HEARTBEAT

// ============================================================

//

// Emitted once per second from loop(). If ACCEL stops but this keeps

// printing, the Mega is alive and the sensor path has failed.

// If both ACCEL and HEARTBEAT stop, loop() is blocked/stalled.

//

void emitHeartbeat() {
  if (!heartbeatEnabled) return;

  unsigned long now = millis();

  if (now - lastHeartbeat < HEARTBEAT_INTERVAL) {

    return;

  }

  lastHeartbeat = now;

  Serial.print("HEARTBEAT ");

  Serial.print(now);

  Serial.print(" LOOPS ");

  Serial.print(loopCounter);

  Serial.print(" SENSORS ");

  Serial.println(

    hitDetectionEnabled

      ? "ENABLED"

      : "DISABLED"

  );

}

// ============================================================

// I2C TIMEOUT CHECK

// ============================================================

//

// On AVR Wire implementations that support timeout flags, report and

// clear the flag after a timed-out transaction. setWireTimeout(..., true)

// also asks Wire to reset its internal TWI state on timeout.

//

void configureI2CTimeout() {
  // Requires a current Arduino AVR Boards core. Wire.h exposes these methods
  // but does not define WIRE_HAS_TIMEOUT.
  Wire.setWireTimeout(I2C_TIMEOUT_US, true);
  Serial.print("I2C TIMEOUT ENABLED ");
  Serial.print(I2C_TIMEOUT_US);
  Serial.println(" us");
}

void reportI2CTimeoutIfNeeded() {
  if (Wire.getWireTimeoutFlag()) {
    Serial.println("I2C_TIMEOUT");
    Wire.clearWireTimeoutFlag();
  }
}

// ============================================================

// TCA9548A

// ============================================================

bool selectTCAChannel(

  uint8_t channel

) {

  if (channel > 7) {

    return false;

  }

  Wire.beginTransmission(

    TCA_ADDRESS

  );

  Wire.write(

    1 << channel

  );

  return Wire.endTransmission() == 0;

}

// ============================================================

// MPU REGISTER WRITE

// ============================================================

bool writeMPURegister(

  uint8_t reg,

  uint8_t value

) {

  Wire.beginTransmission(

    MPU_ADDRESS

  );

  Wire.write(reg);

  Wire.write(value);

  return Wire.endTransmission() == 0;

}

// ============================================================

// WAKE MPU

// ============================================================

bool wakeSensor(

  uint8_t channel

) {

  if (!selectTCAChannel(channel)) return false;

  delay(2);

  bool awake = writeMPURegister(

    0x6B,

    0x00

  );

  delay(50);
  return awake;

}

// ============================================================

// SENSOR EXISTS

// ============================================================

bool sensorExists(

  uint8_t channel

) {

  if (!selectTCAChannel(channel)) return false;

  delay(2);

  Wire.beginTransmission(

    MPU_ADDRESS

  );

  return (

    Wire.endTransmission() == 0

  );

}

// ============================================================

// INITIALIZE SENSORS

// ============================================================

bool initializeSensorChecked(uint8_t id) {
  const char* step = "MUX_SELECT";
  uint8_t actual = 255;
  Wire.clearWireTimeoutFlag();
  bool ok = selectTCAChannel(sensorChannel[id]);
  if (ok) {
    delay(10); step = "ADDRESS_ACK";
    Wire.beginTransmission(MPU_ADDRESS); ok = Wire.endTransmission() == 0;
  }
  if (ok) { step = "WAKE_REG_107"; ok = wakeSensor(sensorChannel[id]); }
  if (ok) { step = "FIFO_DISABLE"; ok = writeMPURegister(0x23, 0) && writeMPURegister(0x6A, 0); }
  if (ok) { step = "RANGE_WRITE_REG_28"; ok = configureAccelerometerRange(sensorChannel[id]); }
  if (ok) {
    step = "RANGE_READBACK_REG_28";
    Wire.beginTransmission(MPU_ADDRESS); Wire.write(0x1C);
    ok = Wire.endTransmission(false) == 0;
    if (ok) {
      Wire.requestFrom((uint8_t)MPU_ADDRESS, (uint8_t)1);
      ok = !Wire.getWireTimeoutFlag() && Wire.available() == 1;
      if (ok) { actual = Wire.read(); ok = actual == 0x18; }
    }
  }
  if (!ok) {
    Serial.print("SENSOR_INIT_FAIL MOLE "); Serial.print(id);
    Serial.print(" CHANNEL "); Serial.print(sensorChannel[id]);
    Serial.print(" STEP "); Serial.print(step);
    Serial.print(" ACTUAL "); Serial.print(actual);
    Serial.print(" TIMEOUT "); Serial.println(Wire.getWireTimeoutFlag() ? 1 : 0);
    reportI2CTimeoutIfNeeded(); return false;
  }
  delay(25); // Space configuration of consecutive mux channels.
  return true;
}

void initializeSensors() {
  Serial.println("SENSOR CHECK");
  for (uint8_t id = 0; id < MOLE_COUNT; id++) {
    bool ok = initializeSensorChecked(id);
    if (ok) sensorConfiguredMask |= (1 << id);
    Serial.print(ok ? "SENSOR OK " : "SENSOR MISSING "); Serial.print(id);
    Serial.print(" CHANNEL "); Serial.println(sensorChannel[id]);
    if (!ok) delay(25);
  }
}

// ============================================================

// READ ACCELEROMETER

// ============================================================

bool readAccelerometer(

  uint8_t channel,

  int16_t& x,

  int16_t& y,

  int16_t& z

) {

  if (!selectTCAChannel(channel)) return false;

  Wire.beginTransmission(

    MPU_ADDRESS

  );

  Wire.write(0x3B);

  if (

    Wire.endTransmission(false)

    != 0

  ) {

    reportI2CTimeoutIfNeeded();

    return false;

  }

  reportI2CTimeoutIfNeeded();

  Wire.requestFrom(

    (uint8_t)MPU_ADDRESS,

    (uint8_t)6

  );

  reportI2CTimeoutIfNeeded();

  if (

    Wire.available() < 6

  ) {

    return false;

  }

  x =

    (Wire.read() << 8)

    |

    Wire.read();

  y =

    (Wire.read() << 8)

    |

    Wire.read();

  z =

    (Wire.read() << 8)

    |

    Wire.read();

  return true;

}

// ============================================================

// MPU6050 ACCELEROMETER RANGE

// ============================================================

//

// Default MPU6050 range is +/-2g, which was clipping badly during

// mole strikes. Use +/-16g (AFS_SEL = 3) so directional peak data

// survives instead of constantly railing at +/-32768.

//

bool configureAccelerometerRange(

  uint8_t channel

) {

  if (!selectTCAChannel(channel)) return false;

  Wire.beginTransmission(0x68);

  Wire.write(0x1C);       // ACCEL_CONFIG register

  Wire.write(0x18);       // AFS_SEL = 3 => +/-16g

  return Wire.endTransmission() == 0;

}

// ============================================================

// September hit acquisition and classification, copied verbatim from sketch_sep13a.
// Health samples are separate and do not participate in impact capture.
void enableSensorReporting() { hitDetectionEnabled = true; lastMechanicalAction = millis(); }

void checkForHits() {

  if (!hitDetectionEnabled) {
    return;
  }

  unsigned long now = millis();

  if (
    now - lastMechanicalAction
    < MECHANICAL_SETTLE_TIME
  ) {
    return;
  }

  if (
    now - lastSensorPoll
    < SENSOR_INTERVAL
  ) {
    return;
  }

  lastSensorPoll = now;

  // ----------------------------------------------------------
  // Detect the beginning of a physical impact.
  // ----------------------------------------------------------

  bool impactTriggered = false;

  for (int mole = 0; mole < MOLE_COUNT; mole++) {

    int16_t x;
    int16_t y;
    int16_t z;

    if (!readAccelerometer(sensorChannel[mole], x, y, z)) {
      continue;
    }

    long strongestAxis = max(
      abs((long)x),
      max(abs((long)y), abs((long)z))
    );

    if (strongestAxis >= HIT_REPORT_THRESHOLD) {
      impactTriggered = true;
      break;
    }
  }

  if (!impactTriggered) {
    return;
  }


  // ----------------------------------------------------------
  // Capture all five sensors for one 75 ms physical-impact window.
  // ----------------------------------------------------------

  int16_t minX[MOLE_COUNT];
  int16_t maxX[MOLE_COUNT];
  int16_t minY[MOLE_COUNT];
  int16_t maxY[MOLE_COUNT];
  int16_t minZ[MOLE_COUNT];
  int16_t maxZ[MOLE_COUNT];

  for (int mole = 0; mole < MOLE_COUNT; mole++) {
    minX[mole] = 32767;
    maxX[mole] = -32768;
    minY[mole] = 32767;
    maxY[mole] = -32768;
    minZ[mole] = 32767;
    maxZ[mole] = -32768;
  }

  const unsigned long IMPACT_CAPTURE_MS = 75;
  unsigned long captureStart = millis();

  while (millis() - captureStart < IMPACT_CAPTURE_MS) {

    for (int mole = 0; mole < MOLE_COUNT; mole++) {

      int16_t x;
      int16_t y;
      int16_t z;

      if (!readAccelerometer(sensorChannel[mole], x, y, z)) {
        continue;
      }

      if (x < minX[mole]) minX[mole] = x;
      if (x > maxX[mole]) maxX[mole] = x;
      if (y < minY[mole]) minY[mole] = y;
      if (y > maxY[mole]) maxY[mole] = y;
      if (z < minZ[mole]) minZ[mole] = z;
      if (z > maxZ[mole]) maxZ[mole] = z;
    }
  }


  // ----------------------------------------------------------
  // Score each mole by its largest directional range.
  //
  // score = max(
  //   maxX - minX,
  //   maxY - minY,
  //   maxZ - minZ
  // )
  //
  // The struck mole should have the largest local movement over
  // the complete impact rather than merely the largest instantaneous
  // cabinet vibration.
  // ----------------------------------------------------------

  long scores[MOLE_COUNT];

  int winner = -1;
  long winnerScore = -1;
  long runnerUpScore = -1;

  for (int mole = 0; mole < MOLE_COUNT; mole++) {

    long xRange =
      (long)maxX[mole] - (long)minX[mole];

    long yRange =
      (long)maxY[mole] - (long)minY[mole];

    long zRange =
      (long)maxZ[mole] - (long)minZ[mole];

    scores[mole] = max(
      xRange,
      max(yRange, zRange)
    );

    if (scores[mole] > winnerScore) {

      runnerUpScore = winnerScore;
      winnerScore = scores[mole];
      winner = mole;

    } else if (scores[mole] > runnerUpScore) {

      runnerUpScore = scores[mole];
    }
  }


  // Keep diagnostics visible while we tune classification.
  Serial.print("SCORES");

  for (int mole = 0; mole < MOLE_COUNT; mole++) {
    Serial.print(" ");
    Serial.print(mole);
    Serial.print(":");
    Serial.print(scores[mole]);
  }

  Serial.println();


  // ----------------------------------------------------------
  // Classification requirements.
  //
  // 1. Winner must show at least 10,000 counts of directional travel.
  // 2. Winner must beat runner-up by at least 15%.
  // ----------------------------------------------------------

  const long MIN_HIT_SCORE = 10000;

  bool strongEnough =
    winnerScore >= MIN_HIT_SCORE;

  bool clearWinner =
    runnerUpScore <= 0
    ||
    winnerScore * 100L
      >= runnerUpScore * 115L;


  if (
    winner >= 0
    &&
    strongEnough
    &&
    clearWinner
  ) {

    Serial.print("HIT ");
    Serial.print(winner);
    Serial.print(" ");
    Serial.print(sensorChannel[winner]);
    Serial.print(" ");
    Serial.println(winnerScore);

  } else {

    Serial.print("IMPACT_REJECTED winner=");
    Serial.print(winner);
    Serial.print(" score=");
    Serial.print(winnerScore);
    Serial.print(" runnerup=");
    Serial.println(runnerUpScore);
  }


  // Treat ringing from this capture as part of the same strike.
  delay(HIT_COOLDOWN);
}


// ============================================================
// MOLE CONTROL

// ============================================================

void setMole(

  int mole,

  bool up

) {

  if (

    mole < 0

    ||

    mole >= MOLE_COUNT

  ) {

    return;

  }

  if (!mcpReady) { commandFailed = true; Serial.println("ERROR MCP NOT READY"); return; }
  mcp.digitalWrite(

    solenoidOutput[mole],

    up ? HIGH : LOW

  );

  if (mcp.digitalRead(solenoidOutput[mole]) != (up ? HIGH : LOW)) {
    commandFailed = true; mcpReady = false; stopOutputsPending = true; Serial.println("ERROR OUTPUT READBACK FAILED");
  }
  unsigned long movementTime = millis();
  lastMechanicalAction = movementTime;

}

// ============================================================

// ALL MOLES

// ============================================================

void setAllMoles(

  bool up

) {

  for (

    int mole = 0;

    mole < MOLE_COUNT;

    mole++

  ) {

    mcp.digitalWrite(

      solenoidOutput[mole],

      up ? HIGH : LOW

    );

  }

  unsigned long movementTime = millis();
  lastMechanicalAction = movementTime;

}

// ============================================================

// MOLE LIGHT

// ============================================================

void setMoleLight(

  int mole,

  int r,

  int g,

  int b

) {

  if (

    mole < 0

    ||

    mole >= MOLE_COUNT

  ) {

    return;

  }

  uint32_t color =

    lights[mole]->Color(

      constrain(r, 0, 255),

      constrain(g, 0, 255),

      constrain(b, 0, 255)

    );

  for (

    int pixel = 0;

    pixel < MOLE_LED_COUNT;

    pixel++

  ) {

    lights[mole]->setPixelColor(

      pixel,

      color

    );

  }

  lights[mole]->show();

}

// ============================================================

// MOLE LIGHT OFF

// ============================================================

void turnMoleLightOff(

  int mole

) {

  if (

    mole < 0

    ||

    mole >= MOLE_COUNT

  ) {

    return;

  }

  lights[mole]->clear();

  lights[mole]->show();

}

// ============================================================

// ALL MOLE LIGHTS OFF

// ============================================================

void turnAllMoleLightsOff() {

  for (

    int mole = 0;

    mole < MOLE_COUNT;

    mole++

  ) {

    lights[mole]->clear();

    lights[mole]->show();

  }

}

// ============================================================

// PLAYER LIGHT

// ============================================================

// Mirror one six-pixel buffer to both pins, allowing a D6/D7 wiring fallback.
void showPlayerLights() {
  memcpy(playerLightsAlternate.getPixels(), playerLights.getPixels(), PLAYER_COUNT * 3);
  playerLights.show();
  playerLightsAlternate.show();
}

void setPlayerLight(

  int player,

  int r,

  int g,

  int b

) {

  if (

    player < 0

    ||

    player >= PLAYER_COUNT

  ) {

    return;

  }

  playerLights.setPixelColor(

    player,

    playerLights.Color(

      constrain(r, 0, 255),

      constrain(g, 0, 255),

      constrain(b, 0, 255)

    )

  );

  showPlayerLights();

}

void setPlayerOff(

  int player

) {

  setPlayerLight(

    player,

    0,

    0,

    0

  );

}

void setPlayerYellow(

  int player

) {

  setPlayerLight(

    player,

    255,

    255,

    0

  );

}

void setPlayerGreen(

  int player

) {

  setPlayerLight(

    player,

    0,

    255,

    0

  );

}

void clearPlayerLights() {

  playerLights.clear();

  showPlayerLights();

}

// ============================================================

// RFID HELPER: PRINT HEX

// ============================================================

void printHexByte(

  byte value

) {

  if (

    value < 0x10

  ) {

    Serial.print("0");

  }

  Serial.print(

    value,

    HEX

  );

}

// ============================================================

// RFID UID

// ============================================================

void printRFIDUID() {

  Serial.print(

    "RFID_DIAG UID "

  );

  for (

    byte i = 0;

    i < rfid.uid.size;

    i++

  ) {

    printHexByte(

      rfid.uid.uidByte[i]

    );

    if (

      i < rfid.uid.size - 1

    ) {

      Serial.print(":");

    }

  }

  Serial.println();

}

// ============================================================

// RFID DATA

// ============================================================

void printRFIDData(

  byte* buffer,

  byte count

) {

  Serial.print(

    "RFID_DIAG DATA HEX "

  );

  for (

    byte i = 0;

    i < count;

    i++

  ) {

    printHexByte(

      buffer[i]

    );

    Serial.print(" ");

  }

  Serial.println();

  Serial.print(

    "RFID_DIAG DATA ASCII "

  );

  for (

    byte i = 0;

    i < count;

    i++

  ) {

    char c =

      (char)buffer[i];

    if (

      c >= 32

      &&

      c <= 126

    ) {

      Serial.print(c);

    } else {

      Serial.print(".");

    }

  }

  Serial.println();

}

// ============================================================

// RFID PLAYER ID

//

// First 3 bytes of block/page 4:

//

// 30 30 31 -> RFID 001

// ============================================================

bool emitPlayerID(

  byte* buffer

) {

  if (

    buffer[0] < '0'

    ||

    buffer[0] > '9'

    ||

    buffer[1] < '0'

    ||

    buffer[1] > '9'

    ||

    buffer[2] < '0'

    ||

    buffer[2] > '9'

  ) {

    Serial.println(

      "RFID_DIAG ADDRESS4_NO_VALID_ID"

    );

    return false;

  }

  char cardID[4];

  cardID[0] =

    (char)buffer[0];

  cardID[1] =

    (char)buffer[1];

  cardID[2] =

    (char)buffer[2];

  cardID[3] =

    '\0';

  Serial.print(

    "RFID "

  );

  Serial.println(

    cardID

  );

  return true;

}

// ============================================================

// RFID CLEANUP

// ============================================================

void cleanupRFID() {

  rfid.PICC_HaltA();

  rfid.PCD_StopCrypto1();

}

// ============================================================

// READ MIFARE CLASSIC BLOCK 4

// ============================================================

bool readClassicBlock4() {

  Serial.println(

    "RFID_DIAG MODE CLASSIC_BLOCK_4"

  );

  MFRC522::StatusCode status;

  // ----------------------------------------------------------

  // Authenticate with Key A

  // ----------------------------------------------------------

  status =

    rfid.PCD_Authenticate(

      MFRC522::PICC_CMD_MF_AUTH_KEY_A,

      4,

      &defaultKey,

      &(rfid.uid)

    );

  if (

    status != MFRC522::STATUS_OK

  ) {

    Serial.print(

      "RFID_DIAG AUTH_A_FAILED "

    );

    Serial.println(

      rfid.GetStatusCodeName(

        status

      )

    );

    // --------------------------------------------------------

    // Try Key B

    // --------------------------------------------------------

    status =

      rfid.PCD_Authenticate(

        MFRC522::PICC_CMD_MF_AUTH_KEY_B,

        4,

        &defaultKey,

        &(rfid.uid)

      );

    if (

      status != MFRC522::STATUS_OK

    ) {

      Serial.print(

        "RFID_DIAG AUTH_B_FAILED "

      );

      Serial.println(

        rfid.GetStatusCodeName(

          status

        )

      );

      return false;

    }

  }

  Serial.println(

    "RFID_DIAG AUTH_OK"

  );

  // ----------------------------------------------------------

  // Large receive buffer

  // ----------------------------------------------------------

  byte buffer[64];

  byte bufferSize =

    sizeof(buffer);

  status =

    rfid.MIFARE_Read(

      4,

      buffer,

      &bufferSize

    );

  if (

    status != MFRC522::STATUS_OK

  ) {

    Serial.print(

      "RFID_DIAG BLOCK4_READ_ERROR "

    );

    Serial.println(

      rfid.GetStatusCodeName(

        status

      )

    );

    Serial.print(

      "RFID_DIAG RETURNED_SIZE "

    );

    Serial.println(

      bufferSize

    );

    return false;

  }

  Serial.print(

    "RFID_DIAG BLOCK4_READ_OK SIZE "

  );

  Serial.println(

    bufferSize

  );

  // Classic block = 16 bytes.

  printRFIDData(

    buffer,

    16

  );

  return emitPlayerID(

    buffer

  );

}

// ============================================================

// READ ULTRALIGHT / NTAG PAGE 4

// ============================================================

bool readUltralightPage4() {

  Serial.println(

    "RFID_DIAG MODE ULTRALIGHT_PAGE_4"

  );

  byte buffer[64];

  byte bufferSize =

    sizeof(buffer);

  MFRC522::StatusCode status =

    rfid.MIFARE_Read(

      4,

      buffer,

      &bufferSize

    );

  if (

    status != MFRC522::STATUS_OK

  ) {

    Serial.print(

      "RFID_DIAG PAGE4_READ_ERROR "

    );

    Serial.println(

      rfid.GetStatusCodeName(

        status

      )

    );

    Serial.print(

      "RFID_DIAG RETURNED_SIZE "

    );

    Serial.println(

      bufferSize

    );

    return false;

  }

  Serial.print(

    "RFID_DIAG PAGE4_READ_OK SIZE "

  );

  Serial.println(

    bufferSize

  );

  // First 4 bytes correspond to page 4.

  printRFIDData(

    buffer,

    4

  );

  return emitPlayerID(

    buffer

  );

}

// ============================================================

// GENERIC ADDRESS-4 FALLBACK

// ============================================================

bool readUnknownTypeAddress4() {

  Serial.println(

    "RFID_DIAG MODE GENERIC_ADDRESS_4"

  );

  byte buffer[64];

  byte bufferSize =

    sizeof(buffer);

  MFRC522::StatusCode status =

    rfid.MIFARE_Read(

      4,

      buffer,

      &bufferSize

    );

  if (

    status != MFRC522::STATUS_OK

  ) {

    Serial.print(

      "RFID_DIAG ADDRESS4_READ_ERROR "

    );

    Serial.println(

      rfid.GetStatusCodeName(

        status

      )

    );

    Serial.print(

      "RFID_DIAG RETURNED_SIZE "

    );

    Serial.println(

      bufferSize

    );

    return false;

  }

  Serial.print(

    "RFID_DIAG ADDRESS4_READ_OK SIZE "

  );

  Serial.println(

    bufferSize

  );

  printRFIDData(

    buffer,

    16

  );

  return emitPlayerID(

    buffer

  );

}

// ============================================================

// RFID SCAN

// ============================================================

void checkRFID() {

  if (

    !rfid.PICC_IsNewCardPresent()

  ) {

    return;

  }

  if (

    !rfid.PICC_ReadCardSerial()

  ) {

    Serial.println(

      "RFID_DIAG CARD_SERIAL_FAILED"

    );

    rfid.PCD_StopCrypto1();

    return;

  }

  Serial.println(

    "RFID_DIAG CARD_PRESENT"

  );

  printRFIDUID();

  MFRC522::PICC_Type piccType =

    rfid.PICC_GetType(

      rfid.uid.sak

    );

  Serial.print(

    "RFID_DIAG TYPE "

  );

  Serial.println(

    rfid.PICC_GetTypeName(

      piccType

    )

  );

  bool success =

    false;

  // ----------------------------------------------------------

  // CLASSIC

  // ----------------------------------------------------------

  if (

    piccType ==

      MFRC522::PICC_TYPE_MIFARE_MINI

    ||

    piccType ==

      MFRC522::PICC_TYPE_MIFARE_1K

    ||

    piccType ==

      MFRC522::PICC_TYPE_MIFARE_4K

  ) {

    success =

      readClassicBlock4();

  }

  // ----------------------------------------------------------

  // ULTRALIGHT / NTAG

  // ----------------------------------------------------------

  else if (

    piccType ==

      MFRC522::PICC_TYPE_MIFARE_UL

  ) {

    success =

      readUltralightPage4();

  }

  // ----------------------------------------------------------

  // UNKNOWN TYPE

  // ----------------------------------------------------------

  else {

    success =

      readUnknownTypeAddress4();

  }

  if (

    !success

  ) {

    Serial.println(

      "RFID_DIAG ADDRESS_4_FAILED"

    );

  }

  // Always clean up after any transaction.

  cleanupRFID();

  Serial.println(

    "RFID_DIAG READY_FOR_NEXT_CARD"

  );

  delay(100);

}

// ============================================================

// RFID STATUS

// ============================================================

void printRFIDStatus() {

  byte version =

    rfid.PCD_ReadRegister(

      MFRC522::VersionReg

    );

  rfidReaderAvailable = version != 0x00 && version != 0xFF;

  Serial.print(

    "RFID_DIAG VERSION 0x"

  );

  Serial.println(

    version,

    HEX

  );

  if (

    version == 0x00

    ||

    version == 0xFF

  ) {

    Serial.println(

      "RFID_DIAG ERROR READER_NOT_RESPONDING"

    );

  } else {

    Serial.println(

      "RFID_DIAG READER_READY"

    );

  }

}

void reportRFIDCheckpoint(const char* phase) {
  Serial.print("RFID_DIAG PHASE ");
  Serial.println(phase);
  printRFIDStatus();
}

// Match the known-working tester and retry a transient startup failure.
bool initializeRFIDReader() {
  SPI.begin();
  rfidReaderAvailable = false;
  for (int attempt = 1; attempt <= 3; attempt++) {
    Serial.print("RFID_DIAG INIT ATTEMPT ");
    Serial.println(attempt);
    rfid.PCD_Init();
    delay(100);
    printRFIDStatus();
    if (rfidReaderAvailable) return true;
  }
  return false;
}

// ============================================================

// TICKET MOTOR

// ============================================================

void ticketMotor(

  bool on

) {

  digitalWrite(

    TICKET_MOTOR_PIN,

    on

      ? TICKET_MOTOR_ACTIVE

      : TICKET_MOTOR_INACTIVE

  );

}

// ============================================================

// DISPENSE TICKETS

// ============================================================

// Nonblocking ticket payout: loop() keeps servicing serial and accelerometers.
bool ticketPayoutActive = false;
int ticketTarget = 0;
int ticketDispensed = 0;
int ticketLastSensorState = HIGH;
unsigned long ticketPayoutStart = 0;
unsigned long ticketLastPulse = 0;

bool dispenseTickets(int count) {
  if (ticketPayoutActive) {
    Serial.println("ERROR TICKET BUSY");
    return false;
  }
  ticketTarget = count;
  ticketDispensed = 0;
  ticketLastSensorState = digitalRead(TICKET_SENSOR_PIN);
  ticketPayoutStart = millis();
  ticketLastPulse = ticketPayoutStart - 25;
  ticketPayoutActive = true;
  ticketMotor(true);
  Serial.print("TICKET_START ");
  Serial.println(count);
  Serial.print("OK TICKET STARTED ");
  Serial.println(count);
  return true;
}

void updateTickets() {
  if (!ticketPayoutActive) return;
  unsigned long now = millis();
  int sensor = digitalRead(TICKET_SENSOR_PIN);
  if (sensor == TICKET_SENSOR_ACTIVE && ticketLastSensorState != TICKET_SENSOR_ACTIVE
      && now - ticketLastPulse >= 25) {
    ticketDispensed++;
    ticketLastPulse = now;
    Serial.print("TICKET_COUNT ");
    Serial.println(ticketDispensed);
  }
  ticketLastSensorState = sensor;
  if (ticketDispensed >= ticketTarget) {
    ticketMotor(false);
    ticketPayoutActive = false;
    Serial.print("TICKET_DONE ");
    Serial.println(ticketDispensed);
  } else if (now - ticketPayoutStart > TICKET_TIMEOUT_PER_TICKET * ticketTarget) {
    ticketMotor(false);
    ticketPayoutActive = false;
    Serial.print("TICKET_ERROR TIMEOUT ");
    Serial.println(ticketDispensed);
  }
}

// ============================================================

// STATUS

// ============================================================

void printStatus() {

  Serial.print(

    "STATUS SENSORS "

  );

  Serial.println(

    hitDetectionEnabled

      ? "ENABLED"

      : "DISABLED"

  );

  printRFIDStatus();

}

// ============================================================

// SERIAL COMMAND HANDLER

// ============================================================

void handleCommand(

  String command

) {

  command.trim();
  bool preserveMcpOutputs = false;
  if (command == "HIT_DEBUG ON" || command == "HIT_DEBUG OFF"
      || command == "SENSORS PUZZLE" || command.startsWith("SENSORS FIFO")) {
    commandFailed = true;
    Serial.println("ERROR V3 V1 HIT MODE USE SENSORS ENABLE");
    return;
  }
  if (command == "KEEPALIVE") {
    lastControllerCommand = millis(); Serial.println("OK KEEPALIVE"); return;
  }
  if (command == "LEASE ON") {
    leaseEnabled = true; lastControllerCommand = millis(); Serial.println("OK LEASE ON"); return;
  }
  if (command == "SAFE STOP") {
    hitDetectionEnabled = false;
    ticketMotor(false); ticketPayoutActive = false;
    stopOutputsPending = true; setAllMoles(false);
    if (mcpReady && !Wire.getWireTimeoutFlag()) stopOutputsPending = false;
    turnAllMoleLightsOff(); clearPlayerLights();
    Serial.println("OK SAFE STOP"); return;
  }
  if (command == "HEALTH RECOVER" || command == "HEALTH RECOVER KEEP_OUTPUTS") {
    preserveMcpOutputs = command == "HEALTH RECOVER KEEP_OUTPUTS";
    // Show recovery preserves output registers, sensing mode and ticket payout.
    if (!preserveMcpOutputs) hitDetectionEnabled = false;
    Wire.end(); Wire.begin(); Wire.setWireTimeout(I2C_TIMEOUT_US, true);
    Wire.beginTransmission(TCA_ADDRESS); Wire.write((uint8_t)0); Wire.endTransmission();
    if (!preserveMcpOutputs) mcpInitialized = false;
    sensorConfiguredMask = 0;
    command = "HEALTH";
  }
  if (command == "HEALTH") {
    if (!mcpInitialized && !preserveMcpOutputs) {
      mcpInitialized = mcp.begin_I2C();
      if (mcpInitialized) for (uint8_t id = 0; id < MOLE_COUNT; id++) {
        mcp.pinMode(solenoidOutput[id], OUTPUT); mcp.digitalWrite(solenoidOutput[id], LOW);
      }
    }
    Wire.beginTransmission(0x20); uint8_t mcpError = Wire.endTransmission(); mcpReady = mcpInitialized && mcpError == 0;
    if (mcpReady && stopOutputsPending && !preserveMcpOutputs) {
      setAllMoles(false);
      if (mcpReady && !Wire.getWireTimeoutFlag()) stopOutputsPending = false;
    }
    uint8_t mask = 0;
    for (uint8_t id = 0; id < MOLE_COUNT; id++) {
      int16_t x, y, z;
      if (!(sensorConfiguredMask & (1 << id)) && initializeSensorChecked(id)) sensorConfiguredMask |= (1 << id);
      bool sampleOK = (sensorConfiguredMask & (1 << id)) && readAccelerometer(sensorChannel[id], x, y, z);
      if (sampleOK) {
        mask |= (1 << id);
        Serial.print("SAMPLE "); Serial.print(id); Serial.print(' '); Serial.print(x);
        Serial.print(' '); Serial.print(y); Serial.print(' '); Serial.println(z);
      } else { sensorConfiguredMask &= ~(1 << id); }
      Serial.print("HARDWARE MOLE "); Serial.print(id); Serial.print(" OUTPUT ");
      Serial.print(mcpReady ? mcp.digitalRead(solenoidOutput[id]) : -1);
      Serial.print(" RING "); Serial.println(lights[id]->getPixelColor(0));
      // Gameplay capture runs once in loop(), outside health telemetry.
    }
    for (uint8_t id = 0; id < PLAYER_COUNT; id++) {
      Serial.print("HARDWARE PLAYER "); Serial.print(id); Serial.print(" COLOR "); Serial.println(playerLights.getPixelColor(id));
    }
    Serial.print("HARDWARE TICKETS ACTIVE "); Serial.print(ticketPayoutActive ? 1 : 0);
    Serial.print(" TARGET "); Serial.print(ticketTarget); Serial.print(" COUNT "); Serial.print(ticketDispensed);
    Serial.print(" MOTOR "); Serial.println(digitalRead(TICKET_MOTOR_PIN));
    Serial.print("HEALTH MCP "); Serial.print(mcpReady ? 1 : 0);
    Serial.print(" SENSORS "); Serial.print(mask);
    Serial.print(" RFID "); Serial.print(rfidReaderAvailable ? 1 : 0);
    Serial.print(" LEASE "); Serial.println(leaseEnabled ? 1 : 0);
    Serial.println("OK HEALTH"); return;
  }

  if (

    command.length() == 0

  ) {

    return;

  }

  if (

    command == "PING"

  ) {

    Serial.println("PONG");

    return;

  }

  if (command == "HEARTBEAT ON" || command == "HEARTBEAT OFF") {
    heartbeatEnabled = command == "HEARTBEAT ON";
    Serial.println(heartbeatEnabled ? "OK HEARTBEAT ON" : "OK HEARTBEAT OFF");
    return;
  }

  if (

    command == "SENSORS ENABLE"

  ) {

    enableSensorReporting();

    lastMechanicalAction = millis();

    Serial.println("OK SENSORS ENABLED");

    return;

  }

  if (

    command == "SENSORS DISABLE"

  ) {

    hitDetectionEnabled = false;

    Serial.println("OK SENSORS DISABLED");

    return;

  }

  if (

    command == "MOLES ALL UP"

  ) {

    setAllMoles(true);

    Serial.println("OK MOLES ALL UP");

    return;

  }

  if (

    command == "MOLES ALL DOWN"

  ) {

    setAllMoles(false);

    Serial.println("OK MOLES ALL DOWN");

    return;

  }

  if (

    command == "LIGHTS OFF"

  ) {

    turnAllMoleLightsOff();

    Serial.println("OK LIGHTS OFF");

    return;

  }

  int stripR, stripG, stripB;
  if (sscanf(command.c_str(), "PLAYER_LIGHTS %d %d %d", &stripR, &stripG, &stripB) == 3) {
    uint32_t color = playerLights.Color(constrain(stripR, 0, 255),
                                       constrain(stripG, 0, 255), constrain(stripB, 0, 255));
    for (uint8_t player = 0; player < PLAYER_COUNT; player++) {
      playerLights.setPixelColor(player, color);
    }
    showPlayerLights();
    Serial.println("OK PLAYER_LIGHTS RGB");
    return;
  }

  if (

    command == "PLAYER_LIGHTS OFF"

  ) {

    clearPlayerLights();

    Serial.println("OK PLAYER_LIGHTS OFF");

    return;

  }

  // ----------------------------------------------------------

  // INDIVIDUAL MOLE

  // ----------------------------------------------------------

  int mole;

  char moleAction[16];

  if (

    sscanf(

      command.c_str(),

      "MOLE %d %15s",

      &mole,

      moleAction

    ) == 2

  ) {

    if (

      mole < 0

      ||

      mole >= MOLE_COUNT

    ) {

      commandFailed = true; Serial.println("ERROR BAD MOLE");

      return;

    }

    if (

      strcmp(

        moleAction,

        "UP"

      ) == 0

    ) {

      setMole(mole, true);

      Serial.print("OK MOLE ");

      Serial.print(mole);

      Serial.println(" UP");

      return;

    }

    if (

      strcmp(

        moleAction,

        "DOWN"

      ) == 0

    ) {

      setMole(mole, false);

      Serial.print("OK MOLE ");

      Serial.print(mole);

      Serial.println(" DOWN");

      return;

    }

    commandFailed = true; Serial.println("ERROR BAD MOLE ACTION");

    return;

  }

  // ----------------------------------------------------------

  // RGB MOLE LIGHT

  // ----------------------------------------------------------

  int r;

  int g;

  int b;

  if (

    sscanf(

      command.c_str(),

      "LIGHT %d %d %d %d",

      &mole,

      &r,

      &g,

      &b

    ) == 4

  ) {

    if (

      mole >= 0

      &&

      mole < MOLE_COUNT

    ) {

      setMoleLight(

        mole,

        r,

        g,

        b

      );

      Serial.print("OK LIGHT ");

      Serial.print(mole);

      Serial.print(" ");

      Serial.print(r);

      Serial.print(" ");

      Serial.print(g);

      Serial.print(" ");

      Serial.println(b);

    } else {

      commandFailed = true; Serial.println("ERROR BAD LIGHT");

    }

    return;

  }

  // ----------------------------------------------------------

  // INDIVIDUAL LIGHT OFF

  // ----------------------------------------------------------

  char lightAction[16];

  if (

    sscanf(

      command.c_str(),

      "LIGHT %d %15s",

      &mole,

      lightAction

    ) == 2

  ) {

    if (

      mole < 0

      ||

      mole >= MOLE_COUNT

    ) {

      commandFailed = true; Serial.println("ERROR BAD LIGHT");

      return;

    }

    if (

      strcmp(

        lightAction,

        "OFF"

      ) == 0

    ) {

      turnMoleLightOff(mole);

      Serial.print("OK LIGHT ");

      Serial.print(mole);

      Serial.println(" OFF");

      return;

    }

    commandFailed = true; Serial.println("ERROR BAD LIGHT ACTION");

    return;

  }

  // ----------------------------------------------------------

  // PLAYER LIGHT

  // ----------------------------------------------------------

  int rgbPlayer, playerR, playerG, playerB;
  if (sscanf(command.c_str(), "PLAYER_LIGHT %d %d %d %d",
      &rgbPlayer, &playerR, &playerG, &playerB) == 4) {
    if (rgbPlayer < 0 || rgbPlayer >= PLAYER_COUNT) {
      commandFailed = true; Serial.println("ERROR BAD PLAYER");
      return;
    }
    setPlayerLight(rgbPlayer, playerR, playerG, playerB);
    Serial.println("OK PLAYER_LIGHT RGB");
    return;
  }

  int player;

  char playerAction[16];

  if (

    sscanf(

      command.c_str(),

      "PLAYER_LIGHT %d %15s",

      &player,

      playerAction

    ) == 2

  ) {

    if (

      player < 0

      ||

      player >= PLAYER_COUNT

    ) {

      commandFailed = true; Serial.println("ERROR BAD PLAYER");

      return;

    }

    if (

      strcmp(

        playerAction,

        "OFF"

      ) == 0

    ) {

      setPlayerOff(player);

      Serial.print("OK PLAYER_LIGHT ");

      Serial.print(player);

      Serial.println(" OFF");

      return;

    }

    if (

      strcmp(

        playerAction,

        "YELLOW"

      ) == 0

    ) {

      setPlayerYellow(player);

      Serial.print("OK PLAYER_LIGHT ");

      Serial.print(player);

      Serial.println(" YELLOW");

      return;

    }

    if (

      strcmp(

        playerAction,

        "GREEN"

      ) == 0

    ) {

      setPlayerGreen(player);

      Serial.print("OK PLAYER_LIGHT ");

      Serial.print(player);

      Serial.println(" GREEN");

      return;

    }

    commandFailed = true; Serial.println("ERROR BAD PLAYER LIGHT ACTION");

    return;

  }

  // ----------------------------------------------------------

  // TICKET

  // ----------------------------------------------------------

  int ticketCount;

  if (

    sscanf(

      command.c_str(),

      "TICKET %d",

      &ticketCount

    ) == 1

  ) {

    if (

      ticketCount < 1

      ||

      ticketCount > 100

    ) {

      commandFailed = true; Serial.println("ERROR BAD TICKET COUNT");

      return;

    }

    if (!dispenseTickets(ticketCount)) commandFailed = true;

    return;

  }

  // ----------------------------------------------------------

  // STATUS

  // ----------------------------------------------------------

  if (

    command == "STATUS"

  ) {

    printStatus();

    return;

  }

  if (

    command == "RFID STATUS"

  ) {

    printRFIDStatus();
    Serial.println("OK RFID STATUS");

    return;

  }

  if (command == "RFID PAUSE") {
    rfidPollingEnabled = false;
    rfid.PCD_AntennaOff();
    Serial.println("OK RFID PAUSED"); return;
  }
  if (command == "RFID INIT") {
    rfidPollingEnabled = false;
    if (initializeRFIDReader()) {
      rfidPollingEnabled = true; lastRFIDPoll = 0;
      Serial.println("OK RFID INIT");
    }
    else { commandFailed = true; Serial.println("ERROR RFID INIT FAILED"); }
    return;
  }

  // ----------------------------------------------------------

  // UNKNOWN

  // ----------------------------------------------------------

  commandFailed = true; Serial.print("ERROR UNKNOWN COMMAND ");

  Serial.println(command);

}

// ============================================================

// SERIAL READER

// ============================================================

void readSerialCommands() {

  while (

    Serial.available()

  ) {

    char c =

      Serial.read();

    if (

      c == '\n'

    ) {

      if (commandOverflow) { commandOverflow = false; commandBuffer = ""; Serial.println("ERROR COMMAND TOO LONG"); continue; }
      String line = commandBuffer;
      unsigned long commandId = 0;
      bool tracked = line.startsWith("@");
      if (tracked) {
        int split = line.indexOf(' ');
        if (split <= 1) { commandBuffer = ""; Serial.println("ERROR BAD COMMAND ID"); continue; }
        commandId = line.substring(1, split).toInt(); line = line.substring(split + 1);
      }
      commandFailed = false;
      Wire.clearWireTimeoutFlag();
      lastControllerCommand = millis();
      handleCommand(line);
      if (Wire.getWireTimeoutFlag()) { commandFailed = true; reportI2CTimeoutIfNeeded(); }
      if (tracked) {
        Serial.print("ACK "); Serial.print(commandId);
        Serial.println(commandFailed ? " ERROR" : " OK");
      }

      commandBuffer =

        "";

    } else if (

      c != '\r'

    ) {

      if (commandOverflow) continue;
      commandBuffer +=

        c;

      if (

        commandBuffer.length()

        > 192

      ) {

        commandOverflow = true;
        commandBuffer =

          "";

      }

    }

  }

}

// ============================================================

// SETUP

// ============================================================

void setup() {

  Serial.begin(

    115200

  );

  delay(

    500

  );

  Serial.println("PROTOCOL 2");
#ifdef __AVR__
  Serial.print("RESET_CAUSE "); Serial.println(resetCause);
#endif
  Serial.print(F("FIRMWARE "));
  Serial.print(F(MOLE_SKETCH_NAME));
  Serial.print(' ');
  Serial.print(F(MOLE_SKETCH_VERSION));
  Serial.print(' ');
  Serial.println(F(MOLE_SOURCE_SHA256));

  // ----------------------------------------------------------

  // I2C

  // ----------------------------------------------------------

  // Check RFID before cabinet peripherals, matching the standalone tester.
  Serial.println("RFID_DIAG PHASE EARLY BEFORE CABINET");
  Serial.print("RFID_DIAG SS_PIN "); Serial.print(RFID_SS_PIN);
  Serial.print(" RST_PIN "); Serial.println(RFID_RST_PIN);
  initializeRFIDReader();

  Wire.begin();

  configureI2CTimeout();
  reportRFIDCheckpoint("AFTER I2C");

  // ----------------------------------------------------------

  // Mole LEDs

  // ----------------------------------------------------------

  for (

    int mole = 0;

    mole < MOLE_COUNT;

    mole++

  ) {

    lights[mole]->begin();

    lights[mole]->setBrightness(

      50

    );

    lights[mole]->clear();

    lights[mole]->show();

  }

  reportRFIDCheckpoint("AFTER MOLE LEDS");

  // ----------------------------------------------------------

  // Player LEDs

  // ----------------------------------------------------------

  playerLights.begin();
  playerLightsAlternate.begin();
  playerLightsAlternate.setBrightness(50);
  reportRFIDCheckpoint("AFTER PLAYER BEGIN");

  playerLights.setBrightness(

    50

  );

  reportRFIDCheckpoint("AFTER PLAYER BRIGHTNESS");
  playerLights.clear();
  reportRFIDCheckpoint("AFTER PLAYER BUFFER CLEAR");
  showPlayerLights();
  reportRFIDCheckpoint("AFTER PLAYER LEDS");

  // ----------------------------------------------------------

  // MCP23017

  // ----------------------------------------------------------

  if (

    !(mcpInitialized = mcp.begin_I2C())

  ) {

    Serial.println(

      "ERROR MCP23017"

    );

  } else {

    for (

      int mole = 0;

      mole < MOLE_COUNT;

      mole++

    ) {

      mcp.pinMode(

        solenoidOutput[mole],

        OUTPUT

      );

      mcp.digitalWrite(

        solenoidOutput[mole],

        LOW

      );

    }

  }

  mcpReady = mcpInitialized;
  reportRFIDCheckpoint("AFTER SOLENOIDS");

  // ----------------------------------------------------------

  // Accelerometers

  // ----------------------------------------------------------

  initializeSensors();
  reportRFIDCheckpoint("AFTER SENSORS");

  // ----------------------------------------------------------

  // RFID

  // ----------------------------------------------------------

  // Default MIFARE Classic factory key:

  //

  // FF FF FF FF FF FF

  for (

    byte i = 0;

    i < 6;

    i++

  ) {

    defaultKey.keyByte[i] =

      0xFF;

  }

  Serial.println(

    "RFID_DIAG INIT"

  );

  printRFIDStatus();

  // ----------------------------------------------------------

  // Ticket dispenser

  // ----------------------------------------------------------

  pinMode(

    TICKET_MOTOR_PIN,

    OUTPUT

  );

  ticketMotor(

    false

  );

  pinMode(

    TICKET_SENSOR_PIN,

    INPUT_PULLUP

  );

  // ----------------------------------------------------------

  // Passive startup

  // ----------------------------------------------------------

  hitDetectionEnabled =

    false;

  lastMechanicalAction =

    millis();

  // Increase all MPU6050 accelerometers to +/-16g before gameplay.

  for (int mole = 0; mole < MOLE_COUNT; mole++) {

    configureAccelerometerRange(

      sensorChannel[mole]

    );

  }

  Serial.println("ACCEL_RANGE +/-16G");

  Serial.println(

    "MAPPING logical_mole -> mux_channel"

  );

  for (int mole = 0; mole < MOLE_COUNT; mole++) {

    Serial.print("MAPPING mole=");

    Serial.print(mole);

    Serial.print(" mux=");

    Serial.println(sensorChannel[mole]);

  }

  Serial.println(

    "READY"

  );
#ifdef __AVR__
  wdt_enable(WDTO_2S);
#endif

}

// ============================================================

// LOOP

// ============================================================

void loop() {

#ifdef __AVR__
  wdt_reset();
#endif
  if (leaseEnabled && millis() - lastControllerCommand > CONTROLLER_LEASE_MS) {
    leaseEnabled = false; hitDetectionEnabled = false;
    ticketMotor(false); ticketPayoutActive = false;
    stopOutputsPending = true; setAllMoles(false);
    if (mcpReady && !Wire.getWireTimeoutFlag()) stopOutputsPending = false;
    turnAllMoleLightsOff(); clearPlayerLights();
    Serial.println("ERROR CONTROLLER LEASE EXPIRED SAFE STOP REQUESTED");
  }
  loopCounter++;

  emitHeartbeat();

  readSerialCommands();

  // Sample first. RC522 card-presence checks can block on a missing card;
  // running one on every loop was delaying every accelerometer scan.
  checkForHits();
  updateTickets();
  unsigned long now = millis();
  if (rfidPollingEnabled && rfidReaderAvailable && now - lastRFIDPoll >= RFID_POLL_INTERVAL) {
    checkRFID();
    lastRFIDPoll = millis();
  }

  reportI2CTimeoutIfNeeded();

}
