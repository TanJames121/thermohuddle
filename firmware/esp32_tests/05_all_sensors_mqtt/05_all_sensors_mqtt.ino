/*
 * ThermoHuddle bench test 05 — ALL sensors + MQTT env telemetry
 * -------------------------------------------------------------
 * Proves the full sensing chain end to end: DS18B20 floor array +
 * DHT22 + MQ-137 (+ INMP441 level) publishing the REAL production
 * env payload to the MQTT broker, in the documented topic
 * "thermohuddle/telemetry/env" with v/ts/boot_id/seq envelope.
 *
 * This is the bench rehearsal of what th-sensord will do on the Pi.
 * Point MQTT_HOST at the machine running pipeline/test_broker_ws.py
 * (the zero-hardware demo broker) or the Pi's mosquitto later.
 *
 * Wiring: same as sketches 01-04. GPIO 34 chosen for MQ-137 because
 * ADC2 pins die while WiFi is on; 34 is ADC1 = safe.
 *
 * Libraries: OneWire, DallasTemperature, DHT sensor library,
 *            Adafruit Unified Sensor, PubSubClient
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>

// ----------------- CONFIG (edit these) -----------------
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASS";
const char* MQTT_HOST = "192.168.1.100";   // PC running test_broker_ws.py / Pi
const int   MQTT_PORT = 1883;
// --------------------------------------------------------

const uint8_t ONE_WIRE_BUS = 4;
const uint8_t DHT_PIN = 15;
const uint8_t MQ_PIN = 34;
const float   ADC_MAX = 4095.0f, VCC = 3.3f, MQ_VC = 5.0f, MQ_RL = 1.0f, MQ_R0 = 10.0f;
const float   CURVE_M = -0.405f, CURVE_B = 0.325f;

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature ds(&oneWire);
DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient wifi;
PubSubClient mqtt(wifi);

char bootId[13];
uint32_t seq = 0;
uint32_t mqWarmT0;

void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  Serial.printf(" connected %s\n", WiFi.localIP().toString().c_str());
}

void ensureMqtt() {
  while (!mqtt.connected()) {
    String cid = String("esp32-bench-") + bootId;
    bool ok = mqtt.connect(cid.c_str());
    Serial.println(ok ? "MQTT connected" : "MQTT retrying...");
    if (!ok) delay(1500);
  }
}

float mq137ppm() {
  uint32_t acc = 0;
  for (int i = 0; i < 20; i++) { acc += analogRead(MQ_PIN); delay(5); }
  float v = (acc / 20.0f) * VCC / ADC_MAX;
  if (v < 0.01f) return -1;
  float rs = (MQ_VC - v) * MQ_RL / v;
  return powf(10.0f, CURVE_M * log10f(rs / MQ_R0) + CURVE_B);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== ThermoHuddle env telemetry bench (ESP32) ===");
  snprintf(bootId, sizeof(bootId), "%08lX", (unsigned long)ESP.getEfuseMac());

  analogSetPinAttenuation(MQ_PIN, ADC_11db);
  ds.begin();
  Serial.printf("DS18B20 probes: %u\n", ds.getDeviceCount());
  ds.setResolution(10);
  dht.begin();

  ensureWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqWarmT0 = millis();
}

void loop() {
  ensureWiFi();
  ensureMqtt();
  mqtt.loop();

  static uint32_t lastPub = 0;
  if (millis() - lastPub < 10000) return;      // env topic cadence: 10 s
  lastPub = millis();

  // --- read everything ---
  ds.requestTemperatures();
  float floorAvg = 0; int nOk = 0;
  String grid = "[";
  uint8_t n = ds.getDeviceCount();
  for (uint8_t i = 0; i < n; i++) {
    float t = ds.getTempCByIndex(i);
    grid += (t == DEVICE_DISCONNECTED_C) ? String("null") : String(t, 2);
    grid += (i < n - 1) ? "," : "]";
    if (t != DEVICE_DISCONNECTED_C) { floorAvg += t; nOk++; }
  }
  grid += n ? "]" : "]";
  if (nOk) floorAvg /= nOk; else floorAvg = NAN;

  float airT = dht.readTemperature();
  float hum  = dht.readHumidity();
  float nh3  = mq137ppm();
  uint32_t warmS = (millis() - mqWarmT0) / 1000;

  // --- build the production-style env payload ---
  // (fields mirror the documented env topic: v, ts, boot_id, seq + env values)
  char payload[512];
  snprintf(payload, sizeof(payload),
    "{\"v\":1,\"ts\":%lld,\"boot_id\":\"%s\",\"seq\":%lu,"
    "\"temp_floor_avg\":%s,\"temp_floor_grid\":%s,"
    "\"temp_air\":%s,\"humidity\":%s,\"nh3_ppm\":%s,\"mq_warmup_s\":%lu}",
    (long long)(millis() / 1000), bootId, (unsigned long)++seq,
    isnan(floorAvg) ? "null" : String(floorAvg, 2).c_str(),
    grid.c_str(),
    isnan(airT) ? "null" : String(airT, 1).c_str(),
    isnan(hum)  ? "null" : String(hum, 1).c_str(),
    (nh3 < 0)   ? "null" : String(nh3, 1).c_str(),
    (unsigned long)warmS);

  bool ok = mqtt.publish("thermohuddle/telemetry/env", payload);
  Serial.printf("[%6lus] pub:%d %s\n", millis() / 1000, ok, payload);

  // bench verdict line
  Serial.printf("  floor %.2fC (%u probes) | air %.1fC RH %.1f%% | NH3 ~%.1f ppm%s\n",
    floorAvg, nOk, airT, hum, nh3, warmS < 300 ? "  (MQ warming up)" : "");
}
