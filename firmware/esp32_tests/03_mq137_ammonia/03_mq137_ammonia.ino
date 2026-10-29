/*
 * ThermoHuddle bench test 03 — MQ-137 ammonia sensor
 * --------------------------------------------------
 * Proves: ADC sampling works, warm-up behaviour is visible, and a
 *         rough NH3 ppm can be computed from Rs/R0.
 *
 * Wiring:  MQ-137 VCC -> 5V (Vin pin), GND -> GND, A0/Aout -> GPIO 34
 *          (GPIO 34 is input-only, ADC1 - safe with WiFi on)
 *
 * IMPORTANT calibration notes (honest sensor):
 *  - First ever power-up: burn the sensor 24-48 h (it conditions the
 *    heater). Later sessions need ~5-10 min warm-up.
 *  - R0 must be calibrated in CLEAN AIR: let readings stabilise after
 *    warm-up, note the printed "Rs", set MQ_R0 below to that value
 *    (or in clean air R0 = Rs, since ppm ~ 0).
 *  - MQ-137 is a semiconductor gas sensor: it cross-reacts with VOCs,
 *    alcohol, CO2 shifts, humidity. Values are INDICATIVE (the 25 ppm
 *    vent / 50 ppm critical bands), not lab-grade. The Pi-side schema
 *    treats nh3_ppm exactly that way.
 *
 * Datasheet curve (MQ-137, NH3 band): ppm = (Rs/R0) scaling via
 * log-log fit; constants below follow the common 10-1000 ppm approximation.
 */

#include <math.h>

const uint8_t MQ_PIN = 34;         // ADC1_CH6, input-only
const float   ADC_MAX = 4095.0f;   // 12-bit ADC
const float   VCC = 3.3f;
const float   MQ_RL = 1.0f;        // module load resistor in kOhm (check yours!)
const float   MQ_R0 = 10.0f;       // kOhm in clean air - CALIBRATE (see header)
const float   MQ_VC = 5.0f;        // sensor heater/sense voltage (5 V module)

// curve constants for NH3 band (log-log): log(ppm) = m*log(rs/r0) + b
const float CURVE_M = -0.405f;     // slope from typical MQ-137 NH3 curve
const float CURVE_B = 0.325f;      // intercept (tune after calibration)

const uint32_t WARMUP_S = 300;     // 5 min warm-up each session (print countdown)

uint32_t t0;

float readRs() {
  // average 20 samples to kill ADC noise (ESP32 ADC is noisy)
  uint32_t acc = 0;
  for (int i = 0; i < 20; i++) {
    acc += analogRead(MQ_PIN);
    delay(5);
  }
  float v = (acc / 20.0f) * VCC / ADC_MAX;
  if (v < 0.01f) return -1;                       // open circuit
  float rs = (MQ_VC - v) * MQ_RL / v;             // sensor resistance in kOhm
  return rs;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  analogSetPinAttenuation(MQ_PIN, ADC_11db);      // full 0-3.3 V range
  Serial.println("\n=== MQ-137 ammonia test ===");
  Serial.println("!! First ever power-up: burn-in 24-48 h before trusting values.");
  t0 = millis();
}

void loop() {
  uint32_t elapsed = (millis() - t0) / 1000;
  float rs = readRs();
  float ratio = rs / MQ_R0;
  float ppm = pow(10.0f, CURVE_M * log10f(ratio) + CURVE_B);

  if (elapsed < WARMUP_S) {
    Serial.printf("[%3lus/%us warming up] Rs=%.2f kOhm (raw)\n",
                  elapsed, WARMUP_S, rs);
  } else if (rs < 0) {
    Serial.println("Aout OPEN - check A0 wire / module power");
  } else {
    Serial.printf("Rs=%.2f kOhm | Rs/R0=%.2f | NH3 ~ %.1f ppm", rs, ratio, ppm);
    if (ppm >= 50)      Serial.println("  >> CRITICAL (>=50 ppm)");
    else if (ppm >= 25) Serial.println("  >> VENT (>=25 ppm)");
    else                Serial.println("  OK");
    Serial.println("  (re-calibrate MQ_R0 in clean air if this looks off)");
  }
  delay(2000);
}
