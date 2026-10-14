# 🐤 ThermoHuddle — Complete Project Guide

**One file, everything: what the system does, the software architecture, the toolkit we built, how to run/install/connect it, and the 16-week build roadmap.**

Team: Bolda · Gabriel · Payumo · Tan · Tangcuangco — CpE 404 Capstone Design 1
Based on: Capstone Proposal Form + Software Build Plan (Oct 14, @James Matthew) + verified toolkit
Last updated: Oct 2026 (v2 — supersedes the first Complete Guide)

---

## 1. What ThermoHuddle does

**One sentence:** an Edge AI brooder that watches how day-old chicks *distribute themselves* on the floor, infers their thermal comfort from that spatial behavior, and gently adjusts the heat lamp around an age-based schedule — instead of trusting a point-source air thermostat.

### From the proposal — the feature set

| Feature | What it means technically |
|---|---|
| **Overhead vision tracking** | NoIR Camera Module 3 (wide) + 940 nm IR pods at 0.2 fps, 24/7, no photoperiod disruption |
| **Spatial statistics engine** | Nearest-Neighbour Distance, Clark–Evans ratio, Shannon occupancy entropy (4×4 grid), Ripley's K/L, centroid offset, anisotropy, max-cell fraction, radial distance, hidden fraction |
| **Dual-modal distress detection** | Vision classification fused with MFCC audio distress scoring (INMP441, 1–8 kHz, fan-masked) |
| **Cascade heater control** | Behavioral inference **trims** the age-based baseline setpoint of an inner PID loop → zero-cross/integral-cycle AC dimmer → ceramic emitter |
| **Safety & hazard overrides** | Deterministic rules for drafts, crowding (smothering prevention), over-temp, ammonia, sensor faults — work even if the AI is dead |
| **Cloud telemetry & dashboard** | MQTT (local broker) → SQLite logging → Supabase/web dashboard; this app is the live 3D dashboard |

### The comfort states and what the system does about them

| State | Behavioral signature | Action | Authority limit |
|---|---|---|---|
| **Comfortable** | Uniform spread, high entropy, Clark–Evans R ≈ 1, quiet audio | Hold trim | — |
| **Too Cold** | Tight huddle toward the lamp, low NND, R < 1, low entropy, high hidden fraction | Trim **+0.5 °C** | up to **+2.0 °C** |
| **Too Hot** | Spread to edges, high radial distance, empty cells under the lamp | Trim **−0.5 °C** | down to **−2.0 °C** |
| **Draft** | Lopsided clustering, high centroid offset + anisotropy, quadrant temp spread | Alert + check inlet, trim +0.5 °C | up to +1.0 °C while active |
| **Crowding Risk** | High max-cell fraction, strong small-radius clustering, distress audio | **ALARM + vent burst + human ack** — a deterministic hard rule *outside* the model; re-alerts every 5 min | Needs a human |

**Key idea from the build plan:** the classifier never directly controls the heater. It only nudges the setpoint within a small bounded window (±2 °C), on top of the age-based baseline, after a 10-minute dwell, at most 1 °C/hour, and never while the fans just ran (fan blanking — otherwise the fans create a draft, the classifier answers it with more heat, and the loop never ends).

---

## 2. System architecture (per the Software Build Plan)

Five isolated services on the Pi, so a crash in the AI can never stop the heater control:

```
┌─────────────────────────── Raspberry Pi 5 ───────────────────────────┐
│                                                                     │
│  th-sensord ──► sensors, validation, PID, dimmer (NO vision imports)│
│      │         age baseline schedule + hard limits + watchdogs      │
│      │                                                              │
│  th-visiond ─► frames → segmentation → positions → spatial features │
│  th-audiod ──► INMP441 → MFCC → distress probability (fan-masked)   │
│      │                                                              │
│  th-brain ───► FSM (BOOT/STARTUP/NORMAL/DEGRADED/FAULT_SAFE)        │
│      │         fusion → temporal filter → TRIM (bounded)           │
│      │         crowding hard rule · priority arbitration P0–P4      │
│      │                                                              │
│  th-uplink ──► MQTT publish · SQLite (WAL) · outbox · snapshots     │
│                                                                     │
│  Mosquitto broker: :1883 (TCP) + :9001 (WebSocket for the app)      │
└─────────────────────────────────────────────────────────────────────┘
         │                         │
         ▼                         ▼
   THIS APP (browser/PWA)     SQLite → Supabase / dashboards
```

**Priority arbitration (a higher level always wins):**
- **P0** hardware interlocks (zero-cross loss → gate off)
- **P1** software hard limits (over-temp 38 °C → heater off, resume at 36)
- **P2** hazard alerts (ammonia 25/50 ppm, MQ-137 warm-up schedule)
- **P3** behavioral trim (the AI — bounded, dwelled, fan-blanked)
- **P4** age baseline schedule (34 °C day 1 → 29 °C day 14)

**MQTT topics (S7):** `thermohuddle/telemetry/env` (10 s) · `inference/window` (60 s) · `control/setpoint` (on change) · `events` · `status` (retained last-will) · `cmd/#` (config + alarm ack). Every payload carries `v`, `ts`, `boot_id`, `seq`.

---

## 3. The toolkit in this folder (what we built & verified)

> The real system is the five services above. This folder is the **bring-up toolkit**: the same decision math, testable on a laptop with zero hardware, plus the live 3D dashboard your phones install as an app.

| File | What it is | Verified |
|---|---|---|
| **`brooder_tracker.html`** | The app: 3D brooder, 8 scenarios, plan-aligned control model (baseline+trim, crowding hard rule, NH₃ hysteresis), LIVE tracking, MQTT-over-WS, PWA | ✅ 20+ browser checks |
| **`thermohuddle_draft_v2.py`** | Single-file pipeline draft with the plan's core logic: baseline+trim manager (dwell/rate/fan-blank/cam-loss), S2 safety rules, crowding override, temporal filter, tuned PID, plant simulator, `--simulate` / `--replay` modes | ✅ 31 unit checks |
| `thermohuddle_draft.py` | v0.1 draft (absolute setpoints) — kept for reference only; **use v2** | — |
| **`test_broker_ws.py`** | amqtt WS broker simulating the Pi's telemetry every 2 s — demo the whole remote-monitoring story **before hardware exists** | ✅ E2E |
| `mosquitto.conf.example` | Broker config for the Pi (1883 TCP + 9001 WS) | — |
| `broker.js.example` | Your broker URL/credentials template (copy to `broker.js`, keep out of git) | — |
| `p5.min.js` / `mqtt.min.js` | Local libs — fully offline app | ✅ |
| `sw.js` + `manifest.json` + icons | PWA install + offline cache (v3) | ✅ offline load verified |
| `start_app.bat` / `start_app.sh` | One-click launchers | — |
| `README.md` + `ThermoHuddle_Complete_Guide.md` (v1) | Older docs — superseded by this file | — |

**Everything is static files** — no build step, no install. Any PC/phone with a browser runs it.

---

## 4. Run & install the app

**Run:** double-click `start_app.bat` (Windows) or `bash start_app.sh` (Pi/Linux/Mac) → opens `http://localhost:8422/brooder_tracker.html`. On the Pi use its LAN IP instead of localhost.

**Install as a real app (PWA):**

| Platform | Steps |
|---|---|
| Windows (Chrome/Edge) | Install icon (⊕) in the address bar → *Install* → own window, Start-menu entry, offline |
| Android (Chrome) | ⋮ → *Add to Home screen* → *Install* (full install needs HTTPS/localhost; LAN http still gives the home-screen app) |
| iPhone (Safari) | Share → *Add to Home Screen* → fullscreen launch |

---

## 5. Using the simulator (plan-aligned)

- **Buttons/keys 1–7**: Comfortable · Too cold · Too hot · Draft · Crowding · Lamp failure · Ammonia spike
- **A** auto-cycle · **L** LIVE · **N** advance brooding day (baseline drops 34→29 °C) · **S** PNG snapshot · **Drag** orbit · **Scroll** zoom
- **HUD** shows the plan's control model live:
  - Brooding day → **Baseline setpoint** (age schedule)
  - **Behavioral trim** (±2.0 °C bounded; turns red at the limit)
  - **Active setpoint** = baseline + trim
  - Floor temp (PV), NND, entropy, **Clark–Evans R** (≈1 uniform, <1 huddle), **max cell %** (red ≥ 45%)
  - **Crowding rule row**: `clear` → `streak 1/3…` → `ALARM — ack needed` (hard rule, not the classifier)
  - NH₃ with 25-ppm vent / 50-ppm critical alerts

The classifier in the app is the same math as `thermohuddle_draft_v2.py` — the sim is a faithful demo of the real decision chain.

## 6. LIVE mode — real chicks

Click **◉ LIVE data**. Data sources, automatic priority: **MQTT** (⚡ button) → **JSON poll** (`tracking_latest.json`, 2 s) → **manual** (Load JSON… / `setChickPositions([[x,z],…])`, cm, corner-0–100 or centered).

**Telemetry schema (v2, matches the pipeline):**

```json
{
  "v": 1, "ts": 1727800000.5, "boot_id": "a1b2c3", "seq": 42,
  "chicks": [[50.2, 51.1], [48.9, 49.7]],
  "count": 2,
  "floorT": 31.8, "baseline": 33.5, "trim": 0.5, "setpoint": 34.0,
  "duty": 64, "nh3": 6, "state": "COLD", "crowding": false
}
```

In LIVE mode **telemetry is authoritative** — the app displays exactly what the pipeline reports, never re-simulates it.

**Demo without hardware:** `python test_broker_ws.py` → app → **⚡ Connect MQTT** → 45 simulated chicks wander, huddle on simulated cold snaps, classifier + trim react. Ideal adviser demo.

---

## 7. Remote monitoring — two setups

**Setup A — on-site (same Wi-Fi as the Pi):**
1. Pi: `python3 -m http.server 8422` (serves the app)
2. Pi: mosquitto with the WS listener (§8 step 3)
3. Pi: `python3 thermohuddle_draft_v2.py --camera 0` (or `--simulate` for a full dress rehearsal without hardware)
4. Phone/PC: `http://<pi-ip>:8422/brooder_tracker.html` → **◉ LIVE** → **⚡ Connect MQTT**

**Setup B — truly remote (anywhere on the internet):**
1. Host the app folder on **GitHub Pages** (free HTTPS → installable PWA)
2. Pi publishes to a **cloud broker** (HiveMQ Cloud free tier — `wss://` + auth built in); set `mqtt_host` in the pipeline Config
3. `broker.js` next to the HTML: `url: "wss://<cluster>.hivemq.cloud:8884/mqtt"` + credentials
4. Open the app anywhere → **⚡ Connect MQTT** → live flock from home

> ⚠️ **Security:** anonymous brokers are fine on the LAN pilot, never on the internet — always `wss://` + username/password.
> ⚠️ **Scope:** remote monitoring = live *telemetry* (positions, temps, states, alerts), not a camera video stream.

---

## 8. Pi deployment checklist (when equipment arrives)

```bash
# 1. Network + IP (write the IP down — it's in every URL)
hostname -I

# 2. Copy the folder to the Pi
scp -r ThermoHuddle/ pi@<pi-ip>:~/

# 3. MQTT broker (TCP 1883 for services, WS 9001 for the app)
sudo apt install -y mosquitto mosquitto-clients
sudo cp ~/ThermoHuddle/mosquitto.conf.example /etc/mosquitto/conf.d/thermohuddle.conf
sudo systemctl restart mosquitto
nc -zv <pi-ip> 1883 && nc -zv <pi-ip> 9001

# 4. Python deps
sudo apt install -y python3-picamera2
pip3 install opencv-python-headless numpy paho-mqtt w1thermsensor adafruit-circuitpython-ads1x15 amqtt

# 5. DS18B20 1-Wire
sudo raspi-config nonint do_onewire 0

# 6. Camera test BEFORE chicks
libcamera-still --width 640 --height 480 -o test.jpg

# 7. Calibrate px→cm (ruler on floor, one frame) → set px_per_cm in Config

# 8. Zero-hardware dress rehearsal (synthetic flock + simulated plant):
python3 thermohuddle_draft_v2.py --simulate

# 9. Replay tuning (recorded frames, no live control):
python3 thermohuddle_draft_v2.py --replay ~/frames/

# 10. Go live
python3 thermohuddle_draft_v2.py --camera 0 --day 1

# 11. Serve the app
cd ~/ThermoHuddle && python3 -m http.server 8422
```

**Stubs to wire before step 10** (marked in the v2 file): `read_floor_temp_stub()` → DS18B20 median; `read_nh3_stub()` → ADS1115+MQ-137 (after 24–72 h burn-in + clean-air baseline); `picam` → Picamera2 loop; PID `duty` → zero-cross dimmer driver (try **integral-cycle** firing first — the ceramic emitter is slow, so Linux timing jitter stops mattering).

**Pre-deployment check (the other PC — nothing to install):** browser present → can ping the Pi → app URL renders → **⚡ Connect MQTT** shows `connected <pi-ip>:9001` → dots move when a hand waves over the floor.

---

## 9. The 16-week build roadmap (from the Software Build Plan)

Build order is dependency-driven: **heater control and safety work before any AI exists.** Everything up to S6 runs on simulators/fakes on your laptops — no hardware needed.

| Step | What you build | Hardware? | Weeks | "Done when" |
|---|---|---|---|---|
| **S0 Foundations** | Repo, config YAML (all `[A]` params), HAL interfaces with fakes, MQTT+SQLite wrappers, schemas (`v/ts/boot_id/seq`), fake clock, replay tool | No | 1–2 | pytest passes; fake th-sensord → Mosquitto → SQLite rows appear |
| **S1 Control loop** | th-sensord: sensor validation (reject 85.0°/−127°/CRC/>5°C-from-median; PV = median), PID @2 s tuned on `simulate_plant`, dimmer driver (integral-cycle first), soft-start ≤5%/min, age baseline 34→29 °C | Fake → real wk 3 | 3–6 | PID meets overshoot/settling on sim; 24 h read-only on real sensors; stable duty on dummy lamp |
| **S2 Safety** | NH₃ 25/15 ppm hysteresis + 5-min min-run, 50 ppm critical, MQ-137 10-min warmup + scheduled vent, over-temp 38→36, zero-cross-loss 100 ms, watchdogs, **priority arbitration as one pure function** | Sim → bench | 5–7 | Fault-matrix rows covered by table tests; **hazards still fire with th-brain killed** |
| **S3 Brain skeleton** | Table-driven FSM (BOOT/STARTUP/NORMAL/DEGRADED/FAULT_SAFE + HAZARD overlay), boot resume-or-cold-start, trim manager (dwell/rate/limits/fan-blank), camera-loss decay | No | 5–8 | Every transition tested with the fake clock; mid-run restart resumes correctly |
| **S4 Vision** | `make_scenes.py` synthetic ground truth, homography (4 floor markers), CLAHE+Otsu+watershed, selective background update (sleeping chicks never absorbed), blob split (area/÷single-chick + k-means), 9 features, quality gate, median-of-12-frames | Synthetic → camera | 3–9 | Synthetic scenes: R≈1 / L−r≈0 for uniform, R<1 for cluster; frame ≪ 5 s on Pi 5 |
| **S5 Audio** | 16 kHz capture, 1 kHz high-pass, 13 MFCC+deltas, 60-s mean/max, fan masking, placeholder threshold until labels | Clips → mic | 5–8 | Precision/recall measured on labeled clips; fan masking kills false alarms |
| **S6 Fusion** | Feature vector (spatial + quadrant spread + thermal error + audio), **rule-based v0 from the signature table**, Random Forest (100 trees, depth ≤8) + no-audio variant, temporal filter (4-of-5, ≥0.6 conf), **crowding deterministic outside the model**, shadow mode, `evaluate.py` (macro-F1, confusion, leave-one-day-out) | No (until labels) | 8–11 | Rules drive trim end-to-end in sim; RF trains on synthetic; crowd rule fires with model off |
| **S7 Integration** | systemd units + watchdogs, real topics, SQLite + outbox + snapshot ring (48 h), **fault-injection harness for the 13-row matrix**, 48-h soak | **Yes** | 8–11 | Cold boot reaches NORMAL unattended; all 13 fault rows respond + recover; soak passes |
| **S8 Closed loop** | Run A (shadow mode, baseline schedule) → labeling tool + **Cohen's κ** between two raters → train/tune/deploy RF → trim enabled for run B with instant-off flag → metrics scripts (comfort-band time, trim steps, energy, uptime, faults) → freeze tag + SD image | **Live chicks** | 12–16 | Model meets targets on held-out data; run B completes with no unsafe heater state; Chapter-4 tables produced |

**Two golden rules from the plan:** every sensor/actuator behind a small interface with real+fake versions (all logic runs on your laptop); **th-sensord never imports vision or audio** (a crash there cannot stop the heater).

**Open items to confirm with your adviser ([A] assumptions):** T_max 38 °C, NH₃ thresholds, trim limits/dwell/rate, confidence cutoff 0.6, baseline curve 34→29 °C linear, RF size, and whether th-uplink's cloud target is Supabase (proposal) or another dashboard.

---

## 10. Keeping the three artifacts in sync

The same decision math lives in three places. **If you tune one, update the others:**

| Concept | `thermohuddle_draft_v2.py` | `brooder_tracker.html` | Build-plan service |
|---|---|---|---|
| Baseline schedule | `baseline_schedule()` | `baselineForDay()` | th-sensord (S1) |
| Trim bounds/dwell/fan-blank | `Config` + `TrimManager` | `PLAN` const | th-brain (S3) |
| Comfort thresholds | `Config` (nnd/entropy/centroid…) | `computeStatsPts()` | th-visiond + th-brain (S4/S6) |
| Crowding rule | `CrowdingOverride` | crowd streak/grace block | th-brain (S6) |
| NH₃/over-temp | `SafetyRules` + `Config` | `PLAN` + alerts | th-sensord (S2) |

---

## 11. Troubleshooting

| Symptom | Cause → Fix |
|---|---|
| Page won't load on another PC | Server not running (`python3 -m http.server 8422`), different Wi-Fi, or firewall on 8422 |
| Dots don't move in LIVE | Pipeline not running; `tracking_latest.json` missing; MQTT not connected (⚡) |
| ⚡ says "error" | Broker WS listener down → `listener 9001 / protocol websockets` in mosquitto conf; restart |
| Works on-site, not from home | Different network → Setup B (cloud broker + `wss://`) |
| LIVE values don't match HUD expectations | Old app version → reload twice (SW updates on second load); or telemetry missing fields |
| Wrong classifications on real data | Tune thresholds via `--replay`, then update **all three artifacts** (§10) |
| Chicks not detected | `px_per_cm` calibration off; blob area limits too tight/loose; IR pods too dim |
| Alarm won't clear | Crowding latch clears only after sustained dispersal (real system: human ack via `cmd/#`) |

---

*This guide, the app, and the v2 pipeline were all functionally verified: 31 Python unit checks + 20+ browser scenario checks + E2E MQTT-over-WebSocket test + offline PWA load test. Nya~ (ฅ'ω'ฅ)*
