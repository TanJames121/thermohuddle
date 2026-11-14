# 📐 ThermoHuddle — ArUco Box Mapping & ESP32 Sensor Integration Guide

Step-by-step setup guide for overhead **NoIR camera ArUco floor mapping**, **ESP32 → Raspberry Pi 5 → Website telemetry**, and the consolidated `/home/tanverse_2026/Desktop/Thesis` layout.

---

## 1. Architecture Overview

```
┌───────────────────────────┐        USB Serial (115200 baud, JSON every 2 s)
│ ESP32 Sensor Node         │ ──────────────────────────────────────────────────┐
│ • DHT22 (GPIO 13)         │                                                   ▼
│ • MQ-137 + ADS1115 (I2C)  │                                  ┌─────────────────────────────────┐
│ • MQ-137 DO Alert (GPIO25)│                                  │ Raspberry Pi 5                   │
│ • Exhaust Relay (GPIO 33) │                                  │ • ai_observer.py                 │
└───────────────────────────┘                                  │   - chicken_vision.py (ArUco +   │
                                                               │     YOLOv11m / YOLOv8n)          │
┌───────────────────────────┐   CSI / Libcamera                │   - chicken_audio.py (CNN)       │
│ Pi NoIR Camera + Mic      │ ────────────────────────────────►│   - esp32_sensor_bridge.py     │
│ • 4× ArUco markers (0–3)  │                                  └───────┬─────────────┬───────────┘
└───────────────────────────┘                                          │             │
                      ┌────────────────────────────────────────────────┘             │
                      ▼                                                              ▼
        ┌─────────────────────────────┐                             ┌────────────────────────────┐
        │ Local Pi HTTP & MQTT        │                             │ Supabase Cloud Snapshot    │
        │ • tracking_latest.json      │                             │ • cloud_snapshot_bridge.py │
        │ • frame_latest.jpg          │                             │ • public read-only JSON    │
        │ • thermohuddle/telemetry/env│                             │   via cloud-feed.js        │
        └─────────────┬───────────────┘                             └──────────────┬─────────────┘
                      └──────────────────────────┬─────────────────────────────────┘
                                                 ▼
                                 ┌───────────────────────────────┐
                                 │ ThermoHuddle WebUI            │
                                 │ • Local (:8422) & GitHub Pages│
                                 │ • ESP32 Sensor Telemetry cards│
                                 │ • 3D brooder ArUco markers    │
                                 └───────────────────────────────┘
```

- **Read-only UI safety**: The public/local WebUI displays observations only (`assessment.control_allowed === false`, `#m-set` stays `—`, `#m-duty` stays `Off`, and heater actuation remains disabled in the interface).

---

## 2. Consolidated Folder Structure (`/home/tanverse_2026/Desktop/Thesis`)

Everything lives under `/home/tanverse_2026/Desktop/Thesis`, with backward-compatible symlinks in `/home/tanverse_2026/`:

```
/home/tanverse_2026/Desktop/Thesis/
├── Thermohuddle/                             ← Git repository & WebUI (:8422)
│   ├── index.html / pilot.js / brooder.css / cloud-feed.js
│   ├── tracking_latest.json -> ../tracking_latest.json
│   ├── frame_latest.jpg     -> ../ai_observation/frame_latest.jpg
│   ├── docs/
│   │   ├── ArUco_ESP32_Integration_Guide.md  ← this guide
│   │   ├── ThermoHuddle_Build_Guide.md
│   │   ├── ThermoHuddle_Overview.md
│   │   └── ThermoHuddle_Research_Plan.md
│   ├── firmware/
│   │   ├── Online-ArUco-marker-sheet-generator.pdf
│   │   ├── ThermohaddleDht22Mq_nov13a/
│   │   │   └── ThermohaddleDht22Mq_nov13a.ino
│   │   └── esp32_tests/
│   ├── pipeline/
│   │   ├── ai_observer.py
│   │   ├── chicken_vision.py                 ← YOLO + ArUco homography mapper
│   │   ├── chicken_audio.py
│   │   ├── comfort_observer.py
│   │   ├── esp32_sensor_bridge.py            ← USB-serial + MQTT ESP32 reader
│   │   └── cloud_snapshot_bridge.py
│   └── tests/
├── CameraModel/                              ← YOLO weights (best.pt)
├── Audiomodel/                               ← Audio CNN checkpoint + audio_test.mp3
├── ai_observation/                           ← Latest annotated frame_latest.jpg
├── tracking_latest.json                      ← Latest observation packet
├── thermohuddle_v3.py
├── thermohuddle_draft_v2.py
├── Online-ArUco-marker-sheet-generator.pdf
├── ThermohaddleDht22Mq_nov13a.ino
└── .agents/skills/                           ← Local UI/UX & engineering skills
```

Compatibility symlinks maintained at `/home/tanverse_2026/`:
- `/home/tanverse_2026/Thesis` → `/home/tanverse_2026/Desktop/Thesis`
- `/home/tanverse_2026/Thermohuddle` → `/home/tanverse_2026/Desktop/Thesis/Thermohuddle`
- `/home/tanverse_2026/CameraModel` → `/home/tanverse_2026/Desktop/Thesis/CameraModel`
- `/home/tanverse_2026/Audiomodel` → `/home/tanverse_2026/Desktop/Thesis/Audiomodel`

---

## 3. Printable ArUco Box Mapping (`DICT_4X4_50`, IDs `0–3`)

### 3.1 Print & Place the Markers

1. Print [`firmware/Online-ArUco-marker-sheet-generator.pdf`](../firmware/Online-ArUco-marker-sheet-generator.pdf) at **100% scale (Actual Size)** on matte paper (avoid glossy laminations that reflect the NoIR IR LEDs).
2. Cut out the 4 markers (`DICT_4X4_50`, IDs `0, 1, 2, 3`) leaving their white quiet-zone border intact.
3. Attach them flat along the 4 inner corners of the brooder box **as seen from the overhead NoIR camera**:

```
   [ID 0: (-50, -50)] ─────────────────────────── [ID 1: (50, -50)]
           │                                               │
           │             Brooder Floor [-50, 50]^2         │
           │                                               │
   [ID 2: (-50,  50)] ─────────────────────────── [ID 3: (50,  50)]
```

### 3.2 How Homography & Occlusion Caching Work

- Implemented in `ArucoBoxMapper` inside [`pipeline/chicken_vision.py`](../pipeline/chicken_vision.py).
- When all 4 markers (`0, 1, 2, 3`) are visible, OpenCV computes a 3×3 perspective transform (`cv2.getPerspectiveTransform`) mapping tilted/off-center NoIR camera pixels cleanly into normalized brooder coordinates `[-50, 50] × [-50, 50]`.
- `positions_from_boxes(..., homography=..., clip_to_box=True)` excludes detections outside the perimeter (`|x| > 55` or `|z| > 55`) so outside background objects never skew flock counts or crowding metrics.
- **Occlusion resilience**: Once locked, `ArucoBoxMapper` caches the homography if a chick temporarily stands on or obscures one of the corner tags, updating again automatically as soon as all 4 corners are clear.
- **Visual verification**:
  - In `ai_observation/frame_latest.jpg` (`Thermohuddle/frame_latest.jpg`), locked corners are outlined with green corner labels (`ID:0`..`ID:3`) and a green polygon perimeter.
  - In the WebUI **Brooder Mapping & Hardware** list, `Box mapping` switches to `Mapped (4/4 IDs)`, and the 4 corner fiducial pads on the 3D brooder floor highlight green.

---

## 4. ESP32 Hardware & Firmware (`ThermohaddleDht22Mq_nov13a.ino`)

### 4.1 Pinout Wiring

| Component | Signal | ESP32 GPIO / Bus | Notes |
|---|---|---|---|
| **DHT22** | Data | `GPIO 13` | Air temperature (°C) & relative humidity (%) |
| **ADS1115 (16-bit ADC)** | `SDA` / `SCL` | `GPIO 21` / `GPIO 22` | I2C address `0x48`; channel `A0` reads **MQ-137** analog (`VCC_MQ = 5.0V`, `RL = 47 kΩ`, `R0 = 10 kΩ`) |
| **MQ-137 Digital** | `DO` Alert | `GPIO 25` | Active-LOW hardware threshold alert (`mq137_do_alert`) |
| **5V Fan Relay** | `IN1` | `GPIO 33` | Active-LOW (`RELAY_ON = LOW`, `RELAY_OFF = HIGH`); drives intake/exhaust fan |

> Local firmware fail-safe in the sketch activates the fan if `nh3_rel_ppm >= 25.0` or `ambient_temp_c >= 36.0` even if USB serial from the Pi 5 is disconnected.

### 4.2 Flashing the ESP32

1. Open [`firmware/ThermohaddleDht22Mq_nov13a/ThermohaddleDht22Mq_nov13a.ino`](../firmware/ThermohaddleDht22Mq_nov13a/ThermohaddleDht22Mq_nov13a.ino) in Arduino IDE or Arduino CLI.
2. Install required libraries via Library Manager:
   - `DHT sensor library` (Adafruit) + `Adafruit Unified Sensor`
   - `Adafruit ADS1X15`
3. Select your ESP32 board and upload at `115200` baud.
4. Connect the ESP32 to any Raspberry Pi 5 USB port.

### 4.3 Serial JSON Protocol (`115200` baud, every `2000 ms`)

Normal reading (`status: "ok"`), DHT read failure (`status: "degraded"`), or ADS1115 init error (`status: "error"`):

```json
{"status":"ok","ambient_temp_c":31.4,"humidity_pct":62.5,"mq137_raw":1420,"mq137_volts":0.4216,"nh3_rel_ppm":2.75,"mq137_do_alert":false,"fan_on":false}
```

Serial fan commands accepted by the ESP32 (`pipeline/esp32_sensor_bridge.py` helper `format_fan_command`):
- Turn ON: `FAN:1\n` (or `{"fan":true}`)
- Turn OFF: `FAN:0\n` (or `{"fan":false}`)

---

## 5. Raspberry Pi 5 Services & Operation

### 5.1 Systemd User Services

User units live in `/home/tanverse_2026/.config/systemd/user/`:
- `thermohuddle-ai.service` — runs `pipeline/ai_observer.py` (camera + audio + auto-detected ESP32 serial)
- `thermohuddle-app.service` — serves the local dashboard on port `8422` (`http://localhost:8422/index.html`)
- `thermohuddle-cloud.service` — uploads sanitized snapshots (including `vision.aruco_*` and `sensors`) to Supabase Storage

Useful commands:

```bash
systemctl --user daemon-reload
systemctl --user restart thermohuddle-ai thermohuddle-app thermohuddle-cloud
systemctl --user status thermohuddle-ai thermohuddle-app thermohuddle-cloud --no-pager
```

### 5.2 Auto-Detection & Manual Serial Port Override

`ESP32SerialReader` automatically scans `/dev/serial/by-id/*`, `/dev/ttyUSB*`, and `/dev/ttyACM*` (or `ESP32_SERIAL_PORT` env var) and reconnects automatically if the USB cable is replugged.

To specify a port explicitly in `ai_observer.py`:

```bash
/home/tanverse_2026/thermohuddle-ai-env/bin/python \
  /home/tanverse_2026/Desktop/Thesis/Thermohuddle/pipeline/ai_observer.py \
  --serial-port /dev/ttyUSB0
```

To run the standalone ESP32 MQTT bridge without the vision/audio loop:

```bash
/home/tanverse_2026/thermohuddle-ai-env/bin/python \
  /home/tanverse_2026/Desktop/Thesis/Thermohuddle/pipeline/esp32_sensor_bridge.py \
  --port /dev/ttyUSB0 --mqtt-host localhost --mqtt-port 1883
```

It publishes readings to `thermohuddle/telemetry/env` and listens for `1`/`0` or `FAN:1`/`FAN:0` on `thermohuddle/cmd/fan`.

---

## 6. Running the Verification Tests

```bash
# Python pipeline, ArUco homography, ESP32 serial parser & cloud sanitizer tests (37 tests)
TMPDIR=/tmp /home/tanverse_2026/thermohuddle-ai-env/bin/python -m unittest discover \
  -s /home/tanverse_2026/Desktop/Thesis/Thermohuddle/tests -p 'test_*.py' -v

# WebUI pilot view state, ArUco & ESP32 rendering + safety invariants (18 + 11 tests)
/home/tanverse_2026/.hermes/tools/node-26.12.1-linux-arm64/bin/node \
  /home/tanverse_2026/Desktop/Thesis/Thermohuddle/tests/model-pilot-checks.js
```
