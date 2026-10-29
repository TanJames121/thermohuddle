/*
 * ThermoHuddle bench test 02 — DHT22 air temperature + humidity
 * -------------------------------------------------------------
 * Proves: the DHT22 reads at its native 0.5 Hz cadence with sane values
 *         (bench expect: 22-35 C, 40-90 %RH indoors).
 *
 * Wiring:  DHT22 VCC -> 3.3V, GND -> GND, DATA -> GPIO 15
 *          (10k pull-up to 3.3V helps on bare sensors; most 3-pin
 *           modules already have it onboard)
 *
 * Notes:   DHT22 minimum sampling period is 2 s - faster polling returns
 *          NaN. In the real system DHT22 is humidity + sanity check only;
 *          the floor channel is the DS18B20 array.
 */

#include <DHT.h>

const uint8_t DHT_PIN = 15;
const uint8_t DHT_TYPE = DHT22;

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== DHT22 air sensor test ===");
  dht.begin();
}

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();      // Celsius
  float hic = dht.computeHeatIndex(t, h, false);

  bool ok = !(isnan(h) || isnan(t));
  if (ok) {
    Serial.printf("[%6lus] air %.1f C | RH %.1f %% | heat index %.1f C   OK\n",
                  millis() / 1000, t, h, hic);
  } else {
    Serial.printf("[%6lus] read FAILED (check wiring, 3.3V, 2 s cadence)\n",
                  millis() / 1000);
  }
  delay(2000);                          // DHT22 spec: >= 2 s between reads
}
