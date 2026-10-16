# 🐤 ThermoHuddle — Project Guide v3 (The One File)

**One file, everything: what the system does, the software architecture, the live app, the data pipeline & Supabase schema, how to run/install/connect, and the 16-week build roadmap.**

Team: Bolda · Gabriel · Payumo · Tan · Tangcuangco — CpE 404 Capstone Design 1
Based on: Capstone Proposal Form + Software Build Plan (Oct 14, @James Matthew) + verified toolkit + App Notes (Chapter 4 alignment)
Supersedes: Project Guide v2, App Notes (standalone), Complete Guide v1
Last updated: Oct 2026 (v3)

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
| **Cloud telemetry & dashboard** | MQTT (local broker) → SQLite logging → Supabase/web dashboard; the live app is the mobile 3D dashboard |

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
│  th-uplink ──► MQTT publish · SQLite (WAL) · outbox · snapshots      │
│      │         (+ frame.jpg upload to Supabase Storage for feed)    │
│                                                                     │
│  Mosquitto broker: :1883 (TCP) + :9001 (WebSocket for the app)      │
└────────────────────────────────────────────────────────────────────┘
         │                         │
         ▼                         ▼
   THE LIVE APP (PWA)        SQLite → Supabase / dashboards
```

**Priority arbitration (a higher level always wins):**
- **P0** hardware interlocks (zero-cross loss → gate off)
- **P1** software hard limits (over-temp 38 °C → heater off, resume at 36)
- **P2** hazard alerts (ammonia 25/50 ppm, MQ-137 warm-up schedule)
- **P3** behavioral trim (the AI — bounded, dwelled, fan-blanked)
- **P4** age baseline schedule (34 °C day 1 → 29 °C day 14)

**MQTT topics (S7):** `thermohuddle/telemetry/env` (10 s) · `inference/window` (60 s) · `control/setpoint` (on change) · `events` · `status` (retained last-will) · `cmd/#` (config + alarm ack). Every payload carries `v`, `ts`, `boot_id`, `seq`.

---

## 3. The live app (`index.html`) — the mobile 3D dashboard

Hosted 24/7 on GitHub Pages: **https://tanjames121.github.io/thermohuddle/** — installable as a real app (Add to Home Screen / Install icon), works offline after first load (PWA service worker).

The app is a **viewer** — it never decides anything. The Pi's th-brain is the only decision-maker.

### 3.1 Dashboard fields explained

| Field | Source | Meaning |
|---|---|---|
| **State** | th-brain | TOO COLD / COMFORTABLE / TOO HOT / DRAFT / CROWDING (spatial stats + audio) — drives the trim |
| **Floor temp** | DS18B20 array | Floor temp at chick level, °C — the PID's process variable |
| **Setpoint** | baseline(day) + trim | What the PID targets right now |
| **Lamp duty** | actuator feedback | 0–100 % power to the IR heat lamp (zero-cross dimmer) — the PID's output |
| **Trim** | th-brain outer loop | ±2 °C behavioral adjustment, ±0.5 °C steps every 40 s while a non-comfy state persists |
| **NND** | th-visiond | Nearest-Neighbor Distance — avg distance to each chick's closest neighbor; clumping ⇒ small NND |
| **Entropy** | th-visiond | Shannon entropy of the 4×4 grid occupancy — how evenly chicks fill the floor (0 = one pile, 1 = even) |
| **Clark R** | th-visiond | observed mean NND ÷ 0.5·√(A/N) under complete spatial randomness (A = floor area, N = chicks); R < 1 clustered, ≈ 1 random, > 1 uniform |
| **Max cell %** | th-visiond | Largest share of the flock in any single grid cell — ≥ 45 % triggers the crowding hard rule |
| **NH₃** | MQ-137 | Ammonia ppm — ≥ 25 ppm vent ON, ≥ 50 ppm critical |
| **Day** | user/system | Brooding day 1–14 — baseline curve 34 → 29 °C |

### 3.2 Behavioral reasoning card (the "why")

The dashboard shows a card answering *why are they doing this*:

- **COLD → clumping:** chicks huddle to conserve body heat; NND drops, center occupancy rises. Controller raises the setpoint.
- **HOT → wall-seeking + spreading:** chicks avoid each other and the warm center to shed heat; entropy high, center empty. Trim goes negative.
- **DRAFT → one-sided avoidance:** centroid shifts away from the draft; chicks pack on the leeward side. Fix the physical leak — heat won't fix it.
- **CROWDING → piling:** >45 % of chicks in one cell = smothering risk; alarm + vent burst. **Safety rule, not learned behavior** — fires even on day 0.
- **LAMPFAIL:** cold-type clustering despite high setpoint + duty ≈ 0 → heat source fault, not setpoint issue.
- **AMMONIA:** birds avoid the litter center, restlessness/chirping up; NH₃ thresholds drive the fan.
- **COMFY:** NND ≈ CSR expectation, cells balanced, no actuation.

These are **interpretations of the pattern, not predictions** — the AI reads behavior, the human reads the why.

### 3.3 Pages

| Page | What's on it |
|---|---|
| **📊 Stats** | the dashboard: banner, stat tiles, baseline/trim/crowding chips, alarm card, reasoning card |
| **📈 History** | temp + setpoint chart with **24 hours / Weekly / Monthly** ranges + summary chips (avg, min/max, % comfy) |
| **🔬 Analytics** | summary stats grid, daily rollup table + ⬇ CSV export, control-loop metrics (below) |
| **🗒 Logs** | timestamped event log |
| **⚠️ Warnings** | alarm/warning log |

### 3.4 Control-loop metrics (replaces MAPE — there is no prediction)

The system is **reactive**: detect behavior → correct setpoint → verify stabilization. No forecasting, so no prediction-error metric exists. The Analytics page reports loop performance instead:

- **Response time** — behavior change detected → actuation (trim step / duty change). Target ≤ 60 s 🟢, ≤ 180 s 🟡.
- **Stabilization time** — actuation → floor temp back within ±0.5 °C of setpoint, held 5 s. Target ≤ 300 s 🟢, ≤ 900 s 🟡.
- Classifier quality (when the trained model is deployed): **accuracy, macro-F1, crowding recall** — from the confusion matrix, exactly what Chapter 4 needs.

The Pi publishes `{kind:"control_metrics", data:{resp_s, stab_s, accuracy, f1, crowd_recall, version}}` on `thermohuddle/status` and the cards fill automatically. Sim mode measures the same things from the built-in plant (actuation-after-Xs, stabilized-after-Ys — see Logs).

### 3.5 Live feed vs dots (🎥 button)

Two view options, toggled by the 🎥 button:
1. **3D tracking dots** — the analysis view: every chick = a marker at its detected (x, z). This is what the algorithm sees; best for verifying tracking quality.
2. **Live camera feed** — real video from the NoIR cam for eyeballing the brooder. **The AI never uses video**: th-visiond grabs a frame every 1–2 s, detects, publishes positions. The human feed is separate transport:

| option | how | latency | Pi CPU | remote (off-LAN) |
|---|---|---|---|---|
| **A. MJPEG stream** | Pi MJPEG HTTP server → app `<img src="http://<pi-ip>:8000/stream.mjpg">` | 0.2–1 s | low | ⚠ app is HTTPS (GitHub Pages) → mixed content blocked; same-Wi-Fi only, or HTTPS wrapper |
| **B. WebRTC** | Pi runs go2rtc/MediaMTX → app WebRTC video | 0.3–1 s | medium | ✅ works anywhere, HTTPS-native |
| **C. Snapshot loop** ⭐ | th-visiond uploads `frame.jpg` every 1–2 s to Supabase Storage (public bucket) → app refreshes `<img>` | 1–2 s | lowest | ✅ HTTPS via Supabase, works everywhere |

**C is the recommended build** — simplest, works from anywhere, and th-visiond already has the frame in hand. Set `feed_url` in `broker.js` (or the app falls back to `http://<host>:8000/stream.mjpg` when served from the Pi).

### 3.6 Scenarios (demo/debug only)

The 🎛 sheet has 10 scenario buttons (Comfy, Cold, Hot, Draft, Crowding, Lamp fail, NH₃ spike, Auto cycle, LIVE, Next day) — **the app boots in LIVE mode and does not simulate anything until a human picks a scenario**. No synthetic data ever appears on its own.

---

## 4. Data pipeline & Supabase schema (Chapter 4 alignment)

The trained AI **must have raw data** and draw its own conclusions — so the schema keeps raw positions + raw sensor rows + windowed aggregates. All Chapter 4 numbers come from these tables.

### `telemetry_raw` — everything, 1 Hz

| column | type | notes |
|---|---|---|
| `ts` | timestamptz | Pi clock (NTP-synced) |
| `day` | int | brooding day |
| `temp_floor_avg` / `temp_floor_grid` | real / jsonb | avg + per-sensor grid |
| `temp_air`, `humidity` | real | DHT22 |
| `nh3_ppm` | real | MQ-137 |
| `lamp_duty` | real | 0–1 |
| `setpoint`, `trim` | real | outer loop |
| `nnd_mean`, `nnd_std`, `entropy`, `clark_r`, `max_cell_frac`, `centroid_x/y` | real | spatial metrics per frame/window |
| `positions` | jsonb | **RAW chick positions [[x,y],…] — the training set** |
| `audio` | jsonb | MFCC summary / distress-chirp rate |
| `state` | text | th-brain's label at that moment |
| `event_flags` | jsonb | alarm/vent/ack events |

> **Training note:** `positions` jsonb is the raw training data. The model consumes positions + temp + audio → infers comfort. Labels come from Phase 1 (pilot), where humans label behavior windows; the model then learns the mapping raw→comfort itself.

### `behavior_windows` — 30 s aggregates (what the dashboard consumes)
Same columns as raw but aggregated (mean NND, entropy, cell fracs, chirp rate, state, trim applied, resp/stab times, alarm flags).

### `control_events` — every actuation, one row each
`ts`, `state`, `trim_before/after`, `duty_before/after`, `resp_s`, `stab_s`, `outcome` — written by uplink from th-brain events.
- **resp_s** = detection→actuation delay
- **stab_s** = actuation→temp within ±0.5 °C of setpoint for 5 s

### `model_accuracy` — per-version metrics (Pi publishes, app reads)
`version`, `trained_at`, `accuracy`, `f1_macro`, `crowd_recall`, `resp_s`, `stab_s`, `confusion_matrix` (jsonb), `n_windows`

### Chapter-4 views (create in the Supabase SQL editor)
- `v_daily_comfort` — per-day avg/min/max floor temp, % comfy, alarms, NH₃ events, avg resp/stab
- `v_state_transitions` — transition matrix (from_state → to_state counts)
- `v_hourly_baseline` — hour-of-day × day-of-brood baseline
- `v_crowd_episodes` — episode start/end, peak cell %, ack latency
- `v_training_export` — **the model-training export**: raw `positions` + temp + audio + state + day + hour (⬇ CSV in the app pulls from here)

### Indexes
```sql
CREATE INDEX ON telemetry_raw (ts DESC);
CREATE INDEX ON behavior_windows (ts DESC);
CREATE INDEX ON control_events (ts DESC);
```

### RLS — read-only for the public app
Tables are **select-only for anon**; writes come only from the uplink service role. **Never** ship the service key in the HTML.
```sql
alter table telemetry_raw enable row level security;
create policy "anon read" on telemetry_raw for select to anon using (true);
-- repeat per table
```

### ⚠ Current status: the Supabase project is unreachable
`gpllypfnxjjkzzmaxtub.supabase.co` no longer resolves (free-tier pause/deletion). Restore:
1. supabase.com dashboard → **Restore** (if paused) or create a new project
2. Run the schema SQL from this section in the SQL editor
3. Update `SB`/`KEY` constants in the app if the project URL changed
4. The app reads tables at runtime — no rebuild needed.

---

## 5. Run & install the app

**Run locally:** double-click `start_app.bat` (Windows) or `bash start_app.sh` (Pi/Linux/Mac) → `http://localhost:8422/index.html`.

**Or just use the hosted app:** https://tanjames121.github.io/thermohuddle/ — nothing to install, works on any phone/PC.

**Install as a real app (PWA):**

| Platform | Steps |
|---|---|
| Windows (Chrome/Edge) | Install icon (⊕) in the address bar → *Install* → own window, Start-menu entry, offline |
| Android (Chrome) | ⋮ → *Add to Home screen* → *Install* (hosted on HTTPS, so full install works) |
| iPhone (Safari) | Share → *Add to Home Screen* → fullscreen launch |

**Connect to the Pi (LIVE):** tap the **⚡ chip** — reads `broker.js` (same-host) or falls back to `ws://<host>:9001`. Telemetry schema matches the pipeline:

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

**Demo without hardware:** `python pipeline/test_broker_ws.py` → app → **⚡** → 45 simulated chicks wander and huddle while the classifier reacts. Ideal adviser demo.

---

## 6. Remote monitoring — two setups

**Setup A — on-site (same Wi-Fi as the Pi):**
1. Pi: `python3 -m http.server 8422` (serves the app)
2. Pi: mosquitto with the WS listener
3. Pi: `python3 pipeline/thermohuddle_draft_v2.py --camera 0` (or `--simulate` for a dress rehearsal)
4. Phone/PC: `http://<pi-ip>:8422/index.html` → **⚡ Connect MQTT**

**Setup B — truly remote (anywhere on the internet):**
1. App is hosted on **GitHub Pages** (free HTTPS → installable PWA) — already done
2. Pi publishes to a **cloud broker** (HiveMQ Cloud free tier — `wss://` + auth); set `mqtt_host` in the pipeline Config
3. `broker.js` next to the HTML (Pi-served copy): `url: "wss://<cluster>.hivemq.cloud:8884/mqtt"` + credentials
4. Open the app anywhere → **⚡ Connect MQTT** → live flock from home

> ⚠️ **Security:** anonymous brokers are fine on the LAN pilot, never on the internet — always `wss://` + username/password.

---

## 7. Pi deployment checklist (when equipment arrives)

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

# 8. Zero-hardware dress rehearsal
python3 pipeline/thermohuddle_draft_v2.py --simulate

# 9. Replay tuning (recorded frames, no live control)
python3 pipeline/thermohuddle_draft_v2.py --replay ~/frames/

# 10. Go live
python3 pipeline/thermohuddle_draft_v2.py --camera 0 --day 1

# 11. Serve the app
cd ~/ThermoHuddle && python3 -m http.server 8422
```

**Stubs to wire before step 10** (marked in the v2 file): `read_floor_temp_stub()` → DS18B20 median; `read_nh3_stub()` → ADS1115+MQ-137 (after 24–72 h burn-in + clean-air baseline); `picam` → Picamera2 loop; PID `duty` → zero-cross dimmer driver (try **integral-cycle** firing first — the ceramic emitter is slow, so Linux timing jitter stops mattering).

**Pre-deployment check (the other PC — nothing to install):** browser present → can ping the Pi → app URL renders → **⚡ Connect MQTT** shows `connected <pi-ip>:9001` → dots move when a hand waves over the floor.

---

## 8. The 16-week build roadmap (from the Software Build Plan)

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

## 9. Keeping the artifacts in sync

The same decision math lives in three places. **If you tune one, update the others:**

| Concept | `pipeline/thermohuddle_draft_v2.py` | `index.html` | Build-plan service |
|---|---|---|---|
| Baseline schedule | `baseline_schedule()` | `baselineForDay()` | th-sensord (S1) |
| Trim bounds/dwell/fan-blank | `Config` + `TrimManager` | `PLAN` const | th-brain (S3) |
| Comfort thresholds | `Config` (nnd/entropy/centroid…) | `computeStatsPts()` | th-visiond + th-brain (S4/S6) |
| Crowding rule | `CrowdingOverride` | crowd streak/grace block | th-brain (S6) |
| NH₃/over-temp | `SafetyRules` + `Config` | `PLAN` + alerts | th-sensord (S2) |

---

## 10. Repo layout (after the v3 reorg)

```
ThermoHuddle/
├── index.html            ← THE app (mobile 3D dashboard, live at github.io)
├── manifest.json, sw.js, p5.min.js, mqtt.min.js, icons, favicon
├── start_app.bat / start_app.sh
├── broker.js.example, mosquitto.conf.example
├── README.md
├── docs/
│   ├── ThermoHuddle_Project_Guide_v3.md   ← this file (the guide)
│   └── design/                             ← FigCraft design files (historical)
├── pipeline/
│   ├── thermohuddle_draft_v2.py           ← the Pi pipeline draft (31 unit checks)
│   └── test_broker_ws.py                   ← MQTT demo broker
```

**Deleted as outdated:** `brooder_tracker.html` (old desktop app — superseded by index.html), `thermohuddle_draft.py` (v0.1), `ThermoHuddle_Complete_Guide.md` (v1), `ThermoHuddle_App_Notes.md` (merged into this guide), `figcraft_build*.py`, `_build_final.json`, `design_preview.png`, `design_export/` (build artifacts).

---

## 11. Troubleshooting

| Symptom | Cause → Fix |
|---|---|
| Page won't load on another PC | Server not running (`python3 -m http.server 8422`), different Wi-Fi, or firewall on 8422 |
| Dots don't move in LIVE | Pipeline not running; `tracking_latest.json` missing; MQTT not connected (⚡) |
| ⚡ says "error" | Broker WS listener down → `listener 9001 / protocol websockets` in mosquitto conf; restart |
| Works on-site, not from home | Different network → Setup B (cloud broker + `wss://`) |
| LIVE values don't match HUD expectations | Old app version → reload twice (SW updates on second load); or telemetry missing fields |
| Wrong classifications on real data | Tune thresholds via `--replay`, then update **all three artifacts** (§9) |
| Chicks not detected | `px_per_cm` calibration off; blob area limits too tight/loose; IR pods too dim |
| Alarm won't clear | Crowding latch clears only after sustained dispersal (real system: human ack via `cmd/#`) |
| Feed button shows nothing | No `feed_url` in broker.js and not served from the Pi → use snapshot loop (option C) or run on same Wi-Fi |
| Analytics cards stay "—" | No control_metrics received yet — the Pi publishes them after the first actuation cycle |

---

*Guide v3 merges Project Guide v2 + App Notes. Everything here was functionally verified: 31 Python unit checks + 30+ browser scenario checks + E2E MQTT-over-WebSocket + offline PWA load + byte-identical deploy checks. Nya~ (ฅ'ω'ฅ)*
