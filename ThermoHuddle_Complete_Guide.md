# 🐤 ThermoHuddle — Complete Guide

**Everything in one file: what it is, how to run it, how to install it as an app, how the data flows, and how to deploy it on the Pi for remote monitoring.**

Team: Bolda · Gabriel · Payumo · Tan · Tangcuangco — CpE 404 Capstone
Last updated: Oct 2026

---

## 1. What is this?

ThermoHuddle is your capstone's **visualizer + live tracker app**. It shows a 3D model of your 1 m × 1 m brooder and does two jobs:

1. **Simulator** — 8 demo scenarios (Comfortable, Too cold, Too hot, Draft, Crowding, Lamp failure, Ammonia spike, Auto-cycle) showing how chick *spatial behavior* maps to your comfort classifier (NND + entropy + centroid + floor-temp fusion).
2. **LIVE tracker** — during real testing, the dots represent **real chicks**: the Pi pipeline detects chick positions from the NoIR camera and streams them to this app, which classifies the flock state live and shows the same HUD your controller uses.

**How the data flows:**

```
   REAL CHICKS
       │  (heat, light, sound)
       ▼
 [NoIR camera + mic + DS18B20 + MQ-137 on Raspberry Pi 5]
       │  thermohuddle_draft.py
       │  detect → spatial stats (NND, entropy, centroid) → classify → cascade control
       ▼
 telemetry JSON ──► 2 ways to reach the app:
   │
   ├─ (A) LOCAL : writes tracking_latest.json → app polls it every 2 s
   └─ (B) REMOTE: publishes to MQTT broker (port 1883)
                     │
                     ▼
              broker WebSocket listener (port 9001)
                     │
                     ▼
        THIS APP (any PC/phone browser) ──► dots move, HUD updates,
                                           classification shown live
```

The app works fully **offline** after first load (service worker caches everything) — the simulator needs nothing, and LIVE mode needs only the telemetry source.

---

## 2. What's in the folder

| File | What it is |
|---|---|
| `brooder_tracker.html` | **The app** — everything (3D scene, HUD, scenarios, LIVE, MQTT) in one page |
| `p5.min.js` | 3D/render library (local copy — no internet needed) |
| `mqtt.min.js` | MQTT-over-WebSocket library (local copy) |
| `sw.js` | Service worker — caches the app for offline use + PWA install |
| `manifest.json`, `icon-*.png`, `favicon-32.png` | App identity + icons (installable app) |
| `start_app.bat` / `start_app.sh` | One-click launchers (Windows / Pi-Linux-Mac) |
| `thermohuddle_draft.py` | Pi pipeline DRAFT: camera detection → stats → classify → control → telemetry |
| `test_broker_ws.py` | Test MQTT broker that simulates Pi telemetry (great for demos before hardware exists) |
| `mosquitto.conf.example` | Broker config to copy onto the Pi (opens 1883 + WS 9001) |
| `broker.js.example` | Template for your broker URL/credentials (copy to `broker.js`) |
| `README.md` | Older dev-focused doc (replay mode, thresholds detail) |
| **This file** | The complete team guide |

> The whole app is **just static files** — no build step, no install, no dependencies. Any machine with a browser can run it.

---

## 3. Run the app

### Windows (this PC)
Double-click **`start_app.bat`** → it starts a tiny web server and opens the app.
(Manual way: `python -m http.server 8422` inside this folder → open `http://localhost:8422/brooder_tracker.html`)

### On the Pi / Linux / Mac
```bash
cd ThermoHuddle
bash start_app.sh          # or: python3 -m http.server 8422
```

### Just open the file directly
Double-clicking `brooder_tracker.html` also works — simulator is fine, but LIVE JSON polling and MQTT need the http-server version. Use the server.

> **A web server is required for:** service worker (offline/PWA), JSON polling, MQTT page reload. `start_app.bat` handles it.

---

## 4. Install it as a real app (PWA)

After opening the app in a browser at `http://localhost:8422/brooder_tracker.html` (or `http://<pi-ip>:8422/...`):

| Platform | Steps |
|---|---|
| **Windows (Chrome/Edge)** | Click the **install icon** (monitor with arrow / ⊕) in the address bar → *Install*. It appears in the Start menu, opens in its own window, works offline. |
| **Android (Chrome)** | Menu **⋮ → Add to Home screen → Install** (or the install banner). Launches fullscreen from the home screen. *Note: the full "Install" option appears for HTTPS sites or localhost — on plain `http://<pi-ip>` you get Add-to-Home-screen (works the same in practice).* |
| **iPhone (Safari)** | **Share** button (box with ↑) → scroll → **Add to Home Screen**. Launches fullscreen, no Safari UI. |

Once installed, it keeps itself updated: when the served files change, the service worker picks up the new version on next launch.

---

## 5. Using the simulator

- **Buttons 1–7 / keys 1–7**: force a scenario (Comfortable, Too cold, Too hot, Draft, Crowding, Lamp failure, Ammonia spike)
- **▶ Auto cycle / key A**: cycles through all scenarios (~9 s each)
- **Drag** = orbit camera · **Scroll** = zoom · **S** = save PNG snapshot
- **HUD (left panel)**: setpoint, floor temp, mean NND, occupancy entropy, lamp power, PWM, NH₃, fan, MQTT link, classification, alerts
- The classifier shown is the **real one** (same math as `thermohuddle_draft.py`): a tight pile + cold floor = TOO COLD, tight pile + warm floor = CROWDING RISK, flock pushed off-center = DRAFT, lamp zone abandoned = TOO HOT, etc.

## 6. LIVE mode (real chicks)

Click **◉ LIVE data** (or key **L**). Three data sources, automatic priority:

1. **MQTT (remote)** — if connected via ⚡, dots update instantly per broker message
2. **JSON (local)** — app polls `tracking_latest.json` every 2 s
3. **Manual** — `Load JSON…` button, or from browser console: `setChickPositions([[50,50],[52,51],...])` (cm, 0–100 corner origin or −50..50 centered — detected per batch)

**Telemetry JSON schema** (any subset works; `chicks` + `floorT` are the important ones):

```json
{
  "ts": 1727800000.5,
  "chicks": [[50.2, 51.1], [48.9, 49.7]],
  "count": 2,
  "nnd": 2.1, "entropy": 0.42,
  "state": "COMFY",
  "floorT": 31.8, "setpoint": 33.0,
  "pwm": 200, "nh3": 6
}
```

**Demo without any hardware:** run `python test_broker_ws.py` (needs `pip install amqtt`), open the app, click **⚡ Connect MQTT** → you'll see 45 simulated chicks wander, huddle when the simulated floor cools, and the classifier react. Perfect for showing your adviser the remote-monitoring story before the brooder exists.

---

## 7. Remote monitoring — the two setups

### Setup A — same Wi-Fi as the Pi (at the site)
```
Phone/PC ──(Wi-Fi)──> Pi :8422 (app)  +  Pi :9001 (broker WS)
```
1. Pi serves this folder: `python3 -m http.server 8422`
2. Pi runs mosquitto with the WS listener (see §8, step 3)
3. Pi pipeline publishes telemetry: `python3 thermohuddle_draft.py --camera 0`
4. On phone/PC: open `http://<pi-ip>:8422/brooder_tracker.html` → **◉ LIVE** → **⚡ Connect MQTT** (auto-finds broker on same host)

### Setup B — anywhere on the internet (truly remote)
```
Pi ──publishs──> CLOUD BROKER (HiveMQ Cloud free tier, wss:// + user/pass)
                        │
Your PC at home ──wss───┘   (app opened from GitHub Pages or installed PWA)
```
1. Host the app files on **GitHub Pages** (free HTTPS → full PWA install + works from any network)
2. Pi publishes to the cloud broker (edit `mqtt_host` in `thermohuddle_draft.py` Config)
3. Copy `broker.js.example` → `broker.js` next to the HTML **on GitHub**, set `url: "wss://<cluster>.hivemq.cloud:8884/mqtt"` + credentials
4. Open the app anywhere → **⚡ Connect MQTT** → live flock view from home

> ⚠️ **Security rules:** never expose an anonymous broker to the internet. Use `wss://` (TLS) + username/password always. On LAN pilots anonymous is acceptable; on the internet it is not.
> ⚠️ **What "remote monitoring" means here:** live *telemetry* (positions, temps, classification, alerts) — not a live camera video feed.

---

## 8. Pi deployment checklist (when equipment arrives)

Run these in order on the Raspberry Pi 5:

```bash
# 1. Wi-Fi + find the Pi's IP (write it down — it's in every URL)
ip a | grep inet           # or: hostname -I

# 2. Copy this folder to the Pi (USB, scp, or git clone)
scp -r ThermoHuddle/ pi@<pi-ip>:~/

# 3. Install + configure the MQTT broker
sudo apt install -y mosquitto mosquitto-clients
sudo cp ~/ThermoHuddle/mosquitto.conf.example /etc/mosquitto/conf.d/thermohuddle.conf
sudo systemctl restart mosquitto
# verify both listeners:
#   nc -zv <pi-ip> 1883   (TCP, pipeline publishes here)
#   nc -zv <pi-ip> 9001   (WS, the app connects here)

# 4. Python deps for the pipeline
sudo apt install -y python3-picamera2
pip3 install opencv-python-headless numpy paho-mqtt w1thermsensor adafruit-circuitpython-ads1x15

# 5. Enable the DS18B20 1-Wire interface
sudo raspi-config nonint do_onewire 0     # or enable via raspi-config UI

# 6. Test the camera first (before pointing it at chicks!)
libcamera-still --width 640 --height 480 -o test.jpg

# 7. Calibrate px→cm: put a ruler on the brooder floor, capture a frame,
#    measure the floor width in pixels → px_per_cm = pixels / 100
#    → set it in thermohuddle_draft.py Config

# 8. Dry-run the pipeline with a replay (no chicks needed):
python3 thermohuddle_draft.py --replay ~/frames/

# 9. Go live:
python3 thermohuddle_draft.py --camera 0

# 10. Serve the app:
cd ~/ThermoHuddle && python3 -m http.server 8422
```

Then on any phone/PC on the same Wi-Fi: `http://<pi-ip>:8422/brooder_tracker.html` → **◉ LIVE data** → **⚡ Connect MQTT** → you're watching the real flock.

**Hardware stubs to wire up before step 9** (marked in `thermohuddle_draft.py`):
- `read_floor_temp_stub()` → real DS18B20 array average (w1thermsensor)
- `read_nh3_stub()` → ADS1115 + MQ-137 (after 24–72 h burn-in + clean-air baseline)
- `picam` import → actual Picamera2 capture loop
- PWM output → your zero-cross dimmer driver (controller returns 0–255)

---

## 9. Pre-deployment checklist (the other PC — no setup needed)

The other PC needs **nothing installed**. Verify only:

- [ ] Browser present (Chrome/Edge recommended)
- [ ] Can reach the Pi/app URL over the network (ping `<pi-ip>`)
- [ ] Open `http://<pi-ip>:8422/brooder_tracker.html` — simulator should render
- [ ] Install as app (§4) if desired
- [ ] **⚡ Connect MQTT** shows `connected <pi-ip>:9001` in the HUD
- [ ] Dots move when someone waves a hand over the brooder floor

For Setup B (internet): app hosted on GitHub Pages + cloud broker credentials in `broker.js`.

---

## 10. Troubleshooting

| Symptom | Cause → Fix |
|---|---|
| Page won't load on other PC | Server not running on the Pi → `python3 -m http.server 8422`; check same Wi-Fi; firewall allows port 8422 |
| App loads but dots don't move | LIVE not connected → click **◉ LIVE data**; check pipeline is running; check `tracking_latest.json` exists |
| ⚡ Connect MQTT says "error" | Broker WS listener down → `mosquitto.conf` missing the `listener 9001 / protocol websockets` block; restart mosquitto |
| MQTT works on-site, not from home | You're on a different network → use Setup B (cloud broker + `wss://`) |
| Wrong classification during real tests | Thresholds need tuning → use `--replay` on recorded frames, compare vs. your labels, adjust `Config` in `thermohuddle_draft.py` **and** `computeStatsPts()` in `brooder_tracker.html` (keep in sync!) |
| Chicks not detected by pipeline | `px_per_cm` calibration wrong, blob area limits too tight/loose, or IR illuminator too dim → tune `blob_min_area`/`blob_max_area` |
| App opens old version | Service worker cache → close all app windows, reopen twice; the SW updates on second load |

---

*Classifier thresholds live in two places — `Config` (Python) and `computeStatsPts()` (HTML). If you tune one, update the other, or sim and live results will disagree.*
