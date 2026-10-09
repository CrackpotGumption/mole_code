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



const unsigned long SENSOR_INTERVAL = 10;
const unsigned long RFID_POLL_INTERVAL = 250;
unsigned long lastRFIDPoll = 0;
bool rfidReaderAvailable = false;
const unsigned long RAW_REPORT_INTERVAL = 50;
const unsigned long PUZZLE_HIT_INTERVAL = 300;
const unsigned long PUZZLE_ARM_SETTLE = 750;
const int16_t PUZZLE_HIT_Z = -9000;
const int16_t PUZZLE_RELEASE_Z = -6400;



// I2C / main-loop diagnostics.

// Wire timeout prevents a bad I2C transaction from blocking forever.

const unsigned long I2C_TIMEOUT_US = 25000;

const unsigned long HEARTBEAT_INTERVAL = 1000;
bool heartbeatEnabled = false;



unsigned long lastHeartbeat = 0;

unsigned long loopCounter = 0;

// Mechanical movement no longer globally suppresses sensor polling.

// Python/game state decides whether a classified HIT counts.





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

// HIT DETECTION STATE

// ============================================================



bool hitDetectionEnabled = false;



unsigned long lastSensorPoll = 0;

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



  delay(5);
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



void initializeSensors() {



  Serial.println(

    "SENSOR CHECK"

  );



  for (

    int mole = 0;

    mole < MOLE_COUNT;

    mole++

  ) {



    uint8_t channel =

      sensorChannel[mole];



    if (

      sensorExists(channel) && wakeSensor(channel) && configureAccelerometerRange(channel)

    ) {



      sensorConfiguredMask |= (1 << mole);



      Serial.print(

        "SENSOR OK "

      );



      Serial.print(mole);



      Serial.print(

        " CHANNEL "

      );



      Serial.println(channel);



    } else {



      Serial.print(

        "SENSOR MISSING "

      );



      Serial.print(mole);



      Serial.print(

        " CHANNEL "

      );



      Serial.println(channel);

    }

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

// SENSOR MODES
// ============================================================
// SENSORS PUZZLE: 10 ms polling, one downward HIT, then disarm.
// SENSORS ENABLE: 10 ms polling, peak-preserving ACCEL reports every 50 ms.
// Both modes use the same physical sensor mapping. Python owns game rules.
// SENSORS DISABLE: stop polling/reporting.
// HIT <mole> <mux_channel> <positive downward strength>
// ACCEL <mole> <mux_channel> <x> <y> <z>

// PUZZLE: poll frequently, emit one HIT, wait for explicit Python re-arm.
// RAW: keep polling at 10 ms, report the most negative sample in each 50 ms
// window so reducing serial traffic does not discard brief downward strikes.
bool puzzleSensorMode = false;
bool puzzleHitArmed = false;
bool puzzleLatched[MOLE_COUNT] = {false, false, false, false, false};
bool puzzleHasHit = false;
unsigned long lastPuzzleHit = 0;
unsigned long puzzleArmStart = 0;
unsigned long lastRawReport = 0;
bool rawPeakValid[MOLE_COUNT] = {false, false, false, false, false};
int16_t rawPeakX[MOLE_COUNT], rawPeakY[MOLE_COUNT], rawPeakZ[MOLE_COUNT];

unsigned long lastPuzzleDiagnostic = 0;
unsigned long puzzleReads[MOLE_COUNT] = {0, 0, 0, 0, 0};
unsigned long puzzleFailures[MOLE_COUNT] = {0, 0, 0, 0, 0};
int16_t puzzleMinZ[MOLE_COUNT] = {32767, 32767, 32767, 32767, 32767};
int16_t puzzleMaxZ[MOLE_COUNT] = {-32768, -32768, -32768, -32768, -32768};

void emitPuzzleDiagnostics(unsigned long now) {
  if (now - lastPuzzleDiagnostic < 1000) return;
  lastPuzzleDiagnostic = now;
  for (int mole = 0; mole < MOLE_COUNT; mole++) {
    Serial.print("PUZZLE_DIAG MOLE "); Serial.print(mole);
    Serial.print(" ARMED "); Serial.print(puzzleHitArmed ? 1 : 0);
    Serial.print(" LATCHED "); Serial.print(puzzleLatched[mole] ? 1 : 0);
    Serial.print(" READS "); Serial.print(puzzleReads[mole]);
    Serial.print(" FAILURES "); Serial.print(puzzleFailures[mole]);
    Serial.print(" MIN_Z "); Serial.print(puzzleMinZ[mole]);
    Serial.print(" MAX_Z "); Serial.println(puzzleMaxZ[mole]);
    puzzleReads[mole] = 0;
    puzzleFailures[mole] = 0;
    puzzleMinZ[mole] = 32767;
    puzzleMaxZ[mole] = -32768;
  }
}

void enableSensorMode(bool puzzle) {
  puzzleSensorMode = puzzle;
  puzzleHitArmed = puzzle;
  if (puzzle) {
    puzzleArmStart = millis();
    // Each sensor must return to rest AFTER mechanical settling.
    for (int mole = 0; mole < MOLE_COUNT; mole++) puzzleLatched[mole] = true;
  }
  hitDetectionEnabled = true;
  lastRawReport = millis();
  lastPuzzleDiagnostic = lastRawReport;
  for (int mole = 0; mole < MOLE_COUNT; mole++) {
    rawPeakValid[mole] = false;
    puzzleReads[mole] = 0;
    puzzleFailures[mole] = 0;
    puzzleMinZ[mole] = 32767;
    puzzleMaxZ[mole] = -32768;
  }
}

void checkForHits() {
  if (!hitDetectionEnabled) return;
  unsigned long now = millis();
  if (now - lastSensorPoll < SENSOR_INTERVAL) return;
  lastSensorPoll = now;
  int selected = -1;
  bool strikeThisPoll[MOLE_COUNT] = {false, false, false, false, false};
  int16_t strongestZ = 0;
  bool settled = !puzzleSensorMode || now - puzzleArmStart >= PUZZLE_ARM_SETTLE;
  bool intervalReady = settled && (!puzzleHasHit || now - lastPuzzleHit >= PUZZLE_HIT_INTERVAL);
  for (int mole = 0; mole < MOLE_COUNT; mole++) {
    int16_t x, y, z;
    if (!readAccelerometer(sensorChannel[mole], x, y, z)) {
      if (puzzleSensorMode) puzzleFailures[mole]++;
      continue;
    }
    if (puzzleSensorMode) {
      puzzleReads[mole]++;
      if (z < puzzleMinZ[mole]) puzzleMinZ[mole] = z;
      if (z > puzzleMaxZ[mole]) puzzleMaxZ[mole] = z;
    }
    if (settled && z > PUZZLE_RELEASE_Z) puzzleLatched[mole] = false;
    strikeThisPoll[mole] = z <= PUZZLE_HIT_Z;
    if (puzzleSensorMode) {
      if (puzzleHitArmed && intervalReady && !puzzleLatched[mole]
          && z <= PUZZLE_HIT_Z && (selected < 0 || z < strongestZ)) {
        selected = mole;
        strongestZ = z;
      }
    } else if (!rawPeakValid[mole] || z < rawPeakZ[mole]) {
      rawPeakValid[mole] = true;
      rawPeakX[mole] = x;
      rawPeakY[mole] = y;
      rawPeakZ[mole] = z;
    }
  }
  if (puzzleSensorMode) {
    if (selected >= 0) {
      puzzleHitArmed = false;
      for (int mole = 0; mole < MOLE_COUNT; mole++) {
        if (strikeThisPoll[mole]) puzzleLatched[mole] = true;
      }
      puzzleHasHit = true;
      lastPuzzleHit = now;
      Serial.print("HIT ");
      Serial.print(selected);
      Serial.print(" ");
      Serial.print(sensorChannel[selected]);
      Serial.print(" ");
      Serial.println(-(long)strongestZ);
    }
    emitPuzzleDiagnostics(now);
    return;
  }
  if (now - lastRawReport < RAW_REPORT_INTERVAL) return;
  lastRawReport = now;
  for (int mole = 0; mole < MOLE_COUNT; mole++) {
    if (!rawPeakValid[mole]) continue;
    Serial.print("ACCEL ");
    Serial.print(mole);
    Serial.print(" ");
    Serial.print(sensorChannel[mole]);
    Serial.print(" ");
    Serial.print(rawPeakX[mole]);
    Serial.print(" ");
    Serial.print(rawPeakY[mole]);
    Serial.print(" ");
    Serial.println(rawPeakZ[mole]);
    rawPeakValid[mole] = false;
  }
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
  lastMechanicalAction = millis();

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



  lastMechanicalAction = millis();

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





  playerLights.show();

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



  playerLights.show();

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
  if (command == "KEEPALIVE") {
    lastControllerCommand = millis(); Serial.println("OK KEEPALIVE"); return;
  }
  if (command == "LEASE ON") {
    leaseEnabled = true; lastControllerCommand = millis(); Serial.println("OK LEASE ON"); return;
  }
  if (command == "SAFE STOP") {
    hitDetectionEnabled = false; puzzleHitArmed = false;
    ticketMotor(false); ticketPayoutActive = false;
    stopOutputsPending = true; setAllMoles(false);
    if (mcpReady && !Wire.getWireTimeoutFlag()) stopOutputsPending = false;
    turnAllMoleLightsOff(); clearPlayerLights();
    Serial.println("OK SAFE STOP"); return;
  }
  if (command == "HEALTH") {
    if (!mcpInitialized) {
      mcpInitialized = mcp.begin_I2C();
      if (mcpInitialized) for (uint8_t id = 0; id < MOLE_COUNT; id++) {
        mcp.pinMode(solenoidOutput[id], OUTPUT); mcp.digitalWrite(solenoidOutput[id], LOW);
      }
    }
    Wire.beginTransmission(0x20); uint8_t mcpError = Wire.endTransmission(); mcpReady = mcpInitialized && mcpError == 0;
    if (mcpReady && stopOutputsPending) {
      setAllMoles(false);
      if (mcpReady && !Wire.getWireTimeoutFlag()) stopOutputsPending = false;
    }
    uint8_t mask = 0;
    for (uint8_t id = 0; id < MOLE_COUNT; id++) {
      int16_t x, y, z;
      if (!(sensorConfiguredMask & (1 << id)) && wakeSensor(sensorChannel[id]) && configureAccelerometerRange(sensorChannel[id])) sensorConfiguredMask |= (1 << id);
      if ((sensorConfiguredMask & (1 << id)) && readAccelerometer(sensorChannel[id], x, y, z)) {
        mask |= (1 << id);
        Serial.print("SAMPLE "); Serial.print(id); Serial.print(' '); Serial.print(x);
        Serial.print(' '); Serial.print(y); Serial.print(' '); Serial.println(z);
      } else { sensorConfiguredMask &= ~(1 << id); }
      Serial.print("HARDWARE MOLE "); Serial.print(id); Serial.print(" OUTPUT ");
      Serial.print(mcpReady ? mcp.digitalRead(solenoidOutput[id]) : -1);
      Serial.print(" RING "); Serial.println(lights[id]->getPixelColor(0));
      checkForHits(); // Service one-shot hit polling during the telemetry response.
    }
    for (uint8_t id = 0; id < PLAYER_COUNT; id++) {
      Serial.print("HARDWARE PLAYER "); Serial.print(id); Serial.print(" COLOR "); Serial.println(playerLights.getPixelColor(id));
      checkForHits();
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

  if (command == "SENSORS PUZZLE") {
    enableSensorMode(true);
    Serial.println("OK SENSORS PUZZLE ARMED");
    return;
  }

  if (

    command == "SENSORS ENABLE"

  ) {

    enableSensorMode(false);

    lastMechanicalAction = millis();

    Serial.println("OK SENSORS ENABLED");

    return;

  }



  if (

    command == "SENSORS DISABLE"

  ) {

    hitDetectionEnabled = false;
    puzzleHitArmed = false;

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
    playerLights.show();
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



  if (command == "RFID INIT") {
    if (initializeRFIDReader()) Serial.println("OK RFID INIT");
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
  reportRFIDCheckpoint("AFTER PLAYER BEGIN");



  playerLights.setBrightness(

    50

  );



  reportRFIDCheckpoint("AFTER PLAYER BRIGHTNESS");
  playerLights.clear();
  reportRFIDCheckpoint("AFTER PLAYER BUFFER CLEAR");
  playerLights.show();
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
    leaseEnabled = false; hitDetectionEnabled = false; puzzleHitArmed = false;
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
  if (rfidReaderAvailable && now - lastRFIDPoll >= RFID_POLL_INTERVAL) {
    checkRFID();
    lastRFIDPoll = millis();
  }



  reportI2CTimeoutIfNeeded();

}
