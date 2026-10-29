/*
 * ThermoHuddle bench test 01 — DS18B20 floor-temperature array
 * ------------------------------------------------------------
 * Proves: 1-Wire bus enumerates every waterproof floor probe and
 *         returns sane temperatures (expect ~24-38 C at the bench).
 *
 * Wiring:  DS18B20 RED -> 3.3V, BLACK -> GND, YELLOW -> GPIO 4
 *          4.7 kOhm resistor between GPIO 4 and 3.3V (REQUIRED)
 *
 * Pass criteria: every probe found reports a temperature and no
 * DEVICE_DISCONNECTED (-127) errors after 10 s of polling.
 */

#include <OneWire.h>
#include <DallasTemperature.h>

const uint8_t ONE_WIRE_BUS = 4;        // yellow data wire
const uint8_t EXPECTED_PROBES = 4;     // <-- set to your probe count

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== DS18B20 floor array test ===");
  sensors.begin();

  uint8_t found = sensors.getDeviceCount();
  Serial.printf("Probes on bus: %u (expected %u)\n", found, EXPECTED_PROBES);

  // list every address so you can label the probes
  DeviceAddress addr;
  Serial.println("Addresses:");
  for (uint8_t i = 0; i < found; i++) {
    if (sensors.getAddress(addr, i)) {
      Serial.printf("  #%u: ", i);
      for (uint8_t b = 0; b < 8; b++) Serial.printf("%02X", addr[b]);
      Serial.println();
    }
  }
  if (found < EXPECTED_PROBES) {
    Serial.println("!! Fewer probes than expected - check wiring / pull-up.");
  }
  // 10-bit resolution = 0.0625 C steps, 187.5 ms conversion
  sensors.setResolution(10);
}

void loop() {
  Serial.print("[");
  Serial.print(millis() / 1000);
  Serial.print(" s] Requesting temperatures... ");
  sensors.requestTemperatures();              // blocks ~187 ms @10-bit

  bool allOk = true;
  float t;
  for (uint8_t i = 0; i < sensors.getDeviceCount(); i++) {
    t = sensors.getTempCByIndex(i);
    if (t == DEVICE_DISCONNECTED_C) {
      Serial.printf("#%u:DISCONNECTED  ", i);
      allOk = false;
    } else {
      Serial.printf("#%u:%.2fC  ", i, t);
    }
  }
  Serial.println(allOk ? "  OK" : "  FAULT");

  delay(2000);
}
