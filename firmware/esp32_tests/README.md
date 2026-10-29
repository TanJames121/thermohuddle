# ESP32 Sensor Bench Tests — ThermoHuddle

Standalone test sketches to **validate each sensor on an ESP32 before Pi deployment**.
These are bring-up/bench tools: in the production build the sensors read on the Pi 5
(build plan S0/S1) — proving them here first means a dead reading later is a wiring or
software problem on the Pi, never a suspect sensor.

## Sketches

| # | Folder | Sensor | What it proves | ESP32 pins |
|---|--------|--------|----------------|------------|
| 01 | `01_ds18b20_floor_array/` | DS18B20 (×N waterproof probes) | 1-Wire bus enumerates all floor probes; °C readings sane | DATA → **GPIO 4** (+ 4.7 kΩ pull-up to 3.3 V) |
| 02 | `02_dht22_air/` | DHT22 | Air temp + RH readable, 2 s cadence | DATA → **GPIO 15** |
| 03 | `03_mq137_ammonia/` | MQ-137 | ADC reads; Rs/R0 computed; rough NH₃ ppm (≥10 ppm band) | Aout → **GPIO 34** (ADC1, WiFi-safe) |
| 04 | `04_inmp441_audio/` | INMP441 MEMS mic | I²S RX @ 16 kHz works; RMS/peak level prints | SCK → **GPIO 32** · WS → **GPIO 25** · SD → **GPIO 33** |
| 05 | `05_all_sensors_mqtt/` | All of the above | Publishes the real `thermohuddle/telemetry/env` JSON over MQTT | same as above |

## Wiring quick reference

```
DS18B20 (waterproof, floor array)        DHT22
  RED    → 3.3V                            VCC → 3.3V
  BLACK  → GND                             GND → GND
  YELLOW → GPIO 4 ── 4.7kΩ ── 3.3V        DATA → GPIO 15
  (pull-up is REQUIRED, one resistor for the whole bus)

MQ-137 module                            INMP441
  VCC → 5V (Vin)                          VDD  → 3.3V  (NEVER 5V)
  GND → GND                               GND  → GND
  Aout → GPIO 34                          L/R  → GND  (left slot = mono)
  (module onboard load resistor RL —      SCK  → GPIO 32
   check yours: usually 1kΩ, set in       WS   → GPIO 25
   sketch as MQ_RL)                       SD   → GPIO 33
```

⚠️ MQ-137 needs a **24–48 h burn-in** (first power-up) and ~5–10 min warm-up each
session before ppm values mean anything — the sketch prints the warm-up countdown.
⚠️ INMP441 is 3.3 V only. 5 V kills it.
⚠️ GPIO 34 is input-only (fine) and belongs to **ADC1** — ADC2 pins cannot be used
while WiFi is on, which is why sketch 05 uses GPIO 34.

## Libraries (Arduino IDE → Library Manager)

| Library | For |
|---|---|
| **OneWire** (Paul Stoffregen) | 01, 05 |
| **DallasTemperature** (Miles Burton) | 01, 05 |
| **DHT sensor library** (Adafruit) + **Adafruit Unified Sensor** | 02, 05 |
| **PubSubClient** (Nick O'Leary) | 05 |

No library needed for the MQ-137 (plain ADC). Sketch 04 uses the built-in I²S
driver — it compiles on both arduino-esp32 core **2.x** (`driver/i2s.h`) and
**3.x** (`ESP_I2S.h`); the sketch auto-detects the core version.

## Board settings (Arduino IDE)

- Board: **ESP32 Dev Module** (most DevKit V1/V4 boards)
- Upload speed 921600 · CPU 160 MHz · Flash 4 MB
- If upload fails with `Failed to connect`: hold the **BOOT** button while
  "Connecting…" appears, release after upload starts
- Serial Monitor: **115200 baud**

## MQTT in sketch 05

Edit the config block at the top: `WIFI_SSID`, `WIFI_PASS`, `MQTT_HOST`
(PC running the demo broker `pipeline/test_broker_ws.py`, or later the Pi's
mosquitto — see `mosquitto.conf.example`), port 1883. Payload matches the
documented env topic: `v`, `ts`, `boot_id`, `seq`, `temp_floor_avg`,
`temp_floor_grid`, `temp_air`, `humidity`, `nh3_ppm` — the same fields the
dashboard and Supabase uplink expect.

## Not in this folder (deliberately)

The **zero-cross AC dimmer / heater tests** involve mains voltage and are not
bench-safe on a breadboard — they get their own procedure with isolation
(low-voltage lamp first, enclosure, and the P0 interlock). Ask before wiring
anything that plugs into the wall.
