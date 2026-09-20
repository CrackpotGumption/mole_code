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
#define MOLE_LED_COUNT 3
#define PLAYER_COUNT 6

#define TCA_ADDRESS 0x70
#define MPU_ADDRESS 0x68

const unsigned long SENSOR_INTERVAL = 10;

// I2C / main-loop diagnostics.
// Wire timeout prevents a bad I2C transaction from blocking forever.
const unsigned long I2C_TIMEOUT_US = 25000;
const unsigned long HEARTBEAT_INTERVAL = 1000;

unsigned long lastHeartbeat = 0;
unsigned long loopCounter = 0;
// Mechanical movement no longer globally suppresses sensor polling.
// Python/game state decides whether a classified HIT counts.


// ============================================================
// MOLE LOGICAL ORDER
//
// 0 = Back left
// 1 = Back right
// 2 = Front left
// 3 = Front center
// 4 = Front right
// ============================================================

const char* positionName[MOLE_COUNT] = {
  "BACK LEFT",
  "BACK RIGHT",
  "FRONT LEFT",
  "FRONT CENTER",
  "FRONT RIGHT"
};


// ============================================================
// ACCELEROMETER / TCA CHANNELS
// ============================================================

const uint8_t sensorChannel[MOLE_COUNT] = {
  1, // Back left
  0, // Back right
  2, // Front left
  4, // Front center
  7  // Front right
};


// ============================================================
// SOLENOID MCP23017 OUTPUTS
// ============================================================

const uint8_t solenoidOutput[MOLE_COUNT] = {
  2, // Back left
  3, // Back right
  1, // Front left
  0, // Front center
  4  // Front right
};

Adafruit_MCP23X17 mcp;


// ============================================================
// MOLE NEOPIXELS
// ============================================================

Adafruit_NeoPixel backLeftLights(
  MOLE_LED_COUNT,
  17,
  NEO_GRB + NEO_KHZ800
);

Adafruit_NeoPixel backRightLights(
  MOLE_LED_COUNT,
  16,
  NEO_GRB + NEO_KHZ800
);

Adafruit_NeoPixel frontLeftLights(
  MOLE_LED_COUNT,
  15,
  NEO_GRB + NEO_KHZ800
);

Adafruit_NeoPixel frontCenterLights(
  MOLE_LED_COUNT,
  14,
  NEO_GRB + NEO_KHZ800
);

Adafruit_NeoPixel frontRightLights(
  MOLE_LED_COUNT,
  18,
  NEO_GRB + NEO_KHZ800
);

Adafruit_NeoPixel* lights[MOLE_COUNT] = {
  &backLeftLights,
  &backRightLights,
  &frontLeftLights,
  &frontCenterLights,
  &frontRightLights
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

const unsigned long TICKET_TIMEOUT_PER_TICKET = 5000;


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


// ============================================================
// MAIN LOOP HEARTBEAT
// ============================================================
//
// Emitted once per second from loop(). If ACCEL stops but this keeps
// printing, the Mega is alive and the sensor path has failed.
// If both ACCEL and HEARTBEAT stop, loop() is blocked/stalled.
//
void emitHeartbeat() {
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
void reportI2CTimeoutIfNeeded() {
#if defined(WIRE_HAS_TIMEOUT)
  if (Wire.getWireTimeoutFlag()) {
    Serial.println("I2C_TIMEOUT");
    Wire.clearWireTimeoutFlag();
  }
#endif
}


// ============================================================
// TCA9548A
// ============================================================

void selectTCAChannel(
  uint8_t channel
) {

  if (channel > 7) {
    return;
  }

  Wire.beginTransmission(
    TCA_ADDRESS
  );

  Wire.write(
    1 << channel
  );

  Wire.endTransmission();
}


// ============================================================
// MPU REGISTER WRITE
// ============================================================

void writeMPURegister(
  uint8_t reg,
  uint8_t value
) {

  Wire.beginTransmission(
    MPU_ADDRESS
  );

  Wire.write(reg);
  Wire.write(value);

  Wire.endTransmission();
}


// ============================================================
// WAKE MPU
// ============================================================

void wakeSensor(
  uint8_t channel
) {

  selectTCAChannel(channel);

  delay(2);

  writeMPURegister(
    0x6B,
    0x00
  );

  delay(5);
}


// ============================================================
// SENSOR EXISTS
// ============================================================

bool sensorExists(
  uint8_t channel
) {

  selectTCAChannel(channel);

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
      sensorExists(channel)
    ) {

      wakeSensor(channel);

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

  selectTCAChannel(channel);

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
    MPU_ADDRESS,
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

void configureAccelerometerRange(
  uint8_t channel
) {

  selectTCAChannel(channel);

  Wire.beginTransmission(0x68);
  Wire.write(0x1C);       // ACCEL_CONFIG register
  Wire.write(0x18);       // AFS_SEL = 3 => +/-16g
  Wire.endTransmission();

}


// ============================================================
// ACCELEROMETER STREAMING
// ============================================================
//
// Arduino does no hit classification and no movement filtering.
//
// While sensors are enabled, poll all five MPU6050s every
// SENSOR_INTERVAL and send EVERY sample to Python.
//
// Python owns all interpretation:
//   - gameplay state
//   - Z direction
//   - thresholds
//   - pneumatic-motion handling
//   - debounce/cooldown
//   - hit decisions
//
// Format:
// ACCEL <mole> <mux_channel> <x> <y> <z>
//
// Example:
// ACCEL 2 2 -1200 18342 -2100
// ============================================================

void checkForHits() {

  if (!hitDetectionEnabled) {
    return;
  }

  unsigned long now = millis();

  if (
    now - lastSensorPoll
    < SENSOR_INTERVAL
  ) {
    return;
  }

  lastSensorPoll = now;

  for (int mole = 0; mole < MOLE_COUNT; mole++) {

    int16_t x;
    int16_t y;
    int16_t z;

    if (
      !readAccelerometer(
        sensorChannel[mole],
        x,
        y,
        z
      )
    ) {
      continue;
    }

    Serial.print("ACCEL ");
    Serial.print(mole);
    Serial.print(" ");
    Serial.print(sensorChannel[mole]);
    Serial.print(" ");
    Serial.print(x);
    Serial.print(" ");
    Serial.print(y);
    Serial.print(" ");
    Serial.println(z);
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


  mcp.digitalWrite(
    solenoidOutput[mole],
    up ? HIGH : LOW
  );

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

bool dispenseTickets(
  int count
) {

  if (
    count <= 0
  ) {
    return true;
  }


  Serial.print(
    "TICKET_START "
  );

  Serial.println(
    count
  );


  int dispensed =
    0;


  int lastSensorState =
    digitalRead(
      TICKET_SENSOR_PIN
    );


  unsigned long startTime =
    millis();


  unsigned long maxTime =
    TICKET_TIMEOUT_PER_TICKET
    * count;


  ticketMotor(
    true
  );


  while (
    dispensed < count
  ) {

    int currentState =
      digitalRead(
        TICKET_SENSOR_PIN
      );


    if (
      currentState ==
        TICKET_SENSOR_ACTIVE
      &&
      lastSensorState !=
        TICKET_SENSOR_ACTIVE
    ) {

      dispensed++;


      Serial.print(
        "TICKET_COUNT "
      );

      Serial.println(
        dispensed
      );


      delay(25);
    }


    lastSensorState =
      currentState;


    if (
      millis() - startTime
      > maxTime
    ) {

      ticketMotor(
        false
      );


      Serial.print(
        "TICKET_ERROR TIMEOUT "
      );

      Serial.println(
        dispensed
      );


      return false;
    }
  }


  ticketMotor(
    false
  );


  Serial.print(
    "TICKET_DONE "
  );

  Serial.println(
    dispensed
  );


  return true;
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

  if (
    command == "SENSORS ENABLE"
  ) {
    hitDetectionEnabled = true;
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
      Serial.println("ERROR BAD MOLE");
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

    Serial.println("ERROR BAD MOLE ACTION");
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
      Serial.println("ERROR BAD LIGHT");
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
      Serial.println("ERROR BAD LIGHT");
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

    Serial.println("ERROR BAD LIGHT ACTION");
    return;
  }

  // ----------------------------------------------------------
  // PLAYER LIGHT
  // ----------------------------------------------------------

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
      Serial.println("ERROR BAD PLAYER");
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

    Serial.println("ERROR BAD PLAYER LIGHT ACTION");
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
      Serial.println("ERROR BAD TICKET COUNT");
      return;
    }

    dispenseTickets(ticketCount);
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
    return;
  }

  // ----------------------------------------------------------
  // UNKNOWN
  // ----------------------------------------------------------

  Serial.print("ERROR UNKNOWN COMMAND ");
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

      handleCommand(
        commandBuffer
      );


      commandBuffer =
        "";

    } else if (
      c != '\r'
    ) {

      commandBuffer +=
        c;


      if (
        commandBuffer.length()
        > 100
      ) {

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


  // ----------------------------------------------------------
  // I2C
  // ----------------------------------------------------------

  Wire.begin();

#if defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(I2C_TIMEOUT_US, true);
  Serial.print("I2C TIMEOUT ENABLED ");
  Serial.print(I2C_TIMEOUT_US);
  Serial.println(" us");
#else
  Serial.println("WIRE TIMEOUT API NOT AVAILABLE");
#endif


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


  // ----------------------------------------------------------
  // Player LEDs
  // ----------------------------------------------------------

  playerLights.begin();

  playerLights.setBrightness(
    50
  );

  clearPlayerLights();


  // ----------------------------------------------------------
  // MCP23017
  // ----------------------------------------------------------

  if (
    !mcp.begin_I2C()
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


  // ----------------------------------------------------------
  // Accelerometers
  // ----------------------------------------------------------

  initializeSensors();


  // ----------------------------------------------------------
  // RFID
  // ----------------------------------------------------------

  SPI.begin();


  pinMode(
    RFID_SS_PIN,
    OUTPUT
  );


  rfid.PCD_Init();


  delay(
    50
  );


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
}


// ============================================================
// LOOP
// ============================================================

void loop() {

  loopCounter++;

  emitHeartbeat();

  readSerialCommands();

  checkRFID();

  checkForHits();

  reportI2CTimeoutIfNeeded();
}
