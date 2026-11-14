#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include "DHT.h"

// ==========================================
// ThermoHuddle Pin & Hardware Configuration
// ==========================================
#define DHTPIN        13       // DHT22 Data Pin
#define DHTTYPE       DHT22
#define MQ137_DO_PIN  25       // MQ-137 Digital Backup Trigger Pin
#define FAN_RELAY_PIN 33       // 5V Relay IN1 (12V Intake/Exhaust Fans)
#define I2C_SDA       21       // ADS1115 SDA
#define I2C_SCL       22       // ADS1115 SCL

// Active-LOW relay logic (swap to HIGH/LOW if your relay is Active-HIGH)
#define RELAY_ON      LOW
#define RELAY_OFF     HIGH

const unsigned long SAMPLE_INTERVAL_MS = 2000;
unsigned long lastSampleTime = 0;

// MQ-137 Baseline Constants
const float RL_KOHM = 47.0;
const float R0_KOHM = 10.0;
const float VCC_MQ  = 5.0;

// Local Fail-Safe Thresholds (if Pi 5 is disconnected)
const float FAILSAFE_NH3_PPM = 25.0;
const float FAILSAFE_TEMP_C  = 36.0;

DHT dht(DHTPIN, DHTTYPE);
Adafruit_ADS1X15 ads;
bool adsInitialized = false;
bool piRequestedFan = false;
bool fanRunning = false;

void setFanState(bool turnOn) {
  fanRunning = turnOn;
  digitalWrite(FAN_RELAY_PIN, turnOn ? RELAY_ON : RELAY_OFF);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { delay(10); }

  pinMode(MQ137_DO_PIN, INPUT);
  pinMode(FAN_RELAY_PIN, OUTPUT);
  setFanState(false); // Start with fans OFF

  dht.begin();

  Wire.begin(I2C_SDA, I2C_SCL);
  if (ads.begin(0x48)) {
    adsInitialized = true;
    ads.setGain(GAIN_ONE);
  } else {
    Serial.println("{\"status\":\"error\",\"msg\":\"ADS1115 not detected at 0x48\"}");
  }
}

float estimateRelativeNH3(float vOut) {
  if (vOut <= 0.01) return 0.0;
  float rs = ((VCC_MQ - vOut) / vOut) * RL_KOHM;
  float ratio = rs / R0_KOHM;
  return 34.67 * pow(ratio, -3.19);
}

// Listen for commands from Raspberry Pi 5 ("FAN:1" or "FAN:0")
void checkSerialCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "FAN:1" || cmd == "{\"fan\":true}") {
      piRequestedFan = true;
    } else if (cmd == "FAN:0" || cmd == "{\"fan\":false}") {
      piRequestedFan = false;
    }
  }
}

void loop() {
  checkSerialCommands();

  unsigned long currentMillis = millis();
  if (currentMillis - lastSampleTime < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleTime = currentMillis;

  // 1. Read DHT22
  float humidity = dht.readHumidity();
  float tempC = dht.readTemperature();
  bool dhtValid = !(isnan(humidity) || isnan(tempC));

  // 2. Read MQ-137 via ADS1115
  int16_t adc0 = 0;
  float mqVolts = 0.0;
  float nh3EstPpm = 0.0;

  if (adsInitialized) {
    adc0 = ads.readADC_SingleEnded(0);
    mqVolts = ads.computeVolts(adc0);
    nh3EstPpm = estimateRelativeNH3(mqVolts);
  }
  bool digitalAlert = (digitalRead(MQ137_DO_PIN) == LOW);

  // 3. Evaluate Fan Control (Pi 5 command OR local hardware fail-safe)
  bool localHazard = digitalAlert ||
                     (adsInitialized && nh3EstPpm >= FAILSAFE_NH3_PPM) ||
                     (dhtValid && tempC >= FAILSAFE_TEMP_C);

  setFanState(piRequestedFan || localHazard);

  // 4. Emit Single-Line JSON Payload to Raspberry Pi 5
  Serial.print("{");
  Serial.print("\"status\":\"");
  Serial.print((dhtValid && adsInitialized) ? "ok" : "degraded");
  Serial.print("\",");

  if (dhtValid) {
    Serial.print("\"ambient_temp_c\":");
    Serial.print(tempC, 2);
    Serial.print(",\"humidity_pct\":");
    Serial.print(humidity, 2);
    Serial.print(",");
  } else {
    Serial.print("\"ambient_temp_c\":null,\"humidity_pct\":null,");
  }

  Serial.print("\"mq137_raw\":");
  Serial.print(adc0);
  Serial.print(",\"mq137_volts\":");
  Serial.print(mqVolts, 4);
  Serial.print(",\"nh3_rel_ppm\":");
  Serial.print(nh3EstPpm, 2);
  Serial.print(",\"mq137_do_alert\":");
  Serial.print(digitalAlert ? "true" : "false");
  Serial.print(",\"fan_on\":");
  Serial.print(fanRunning ? "true" : "false");
  Serial.println("}");
}
