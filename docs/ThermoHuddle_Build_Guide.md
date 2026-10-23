# 🐤 ThermoHuddle — Build Guide (Setup, Deployment & Roadmap)

**How to run, connect, store data, and build the whole thing step by step.** For what the project is and how each feature works, see `ThermoHuddle_Overview.md`.

Team: Bolda · Gabriel · Payumo · Tan · Tangcuangco — CpE 404 Capstone Design 1

---

## 1. Repo layout

```
ThermoHuddle/
├── index.html                      ← THE app (mobile 3D dashboard PWA)
├── manifest.json / sw.js / p5.min.js / mqtt.min.js / icons / favicon
├── start_app.bat / start_app.sh    ← one-click launchers (Windows / Pi-Linux-Mac)
├── broker.js.example / mosquitto.conf.example
├── README.md
├── docs/
│   ├── ThermoHuddle_Overview.md        ← what it is + how features work
│   ├── ThermoHuddle_Build_Guide.md     ← this file
│   └── design/                         ← FigCraft design files (historical)
└── pipeline/
    ├── thermohuddle_draft_v2.py        ← Pi pipeline draft (31 unit checks)
    └── test_broker_ws.py               ← demo MQTT broker (zero-hardware demo)
```

---

## 2. Run & install the app

**Hosted (recommended):** **https://tanjames121.github.io/thermohuddle/** — nothing to install, any phone/PC.

**Locally:**
- Windows: double-click `start_app.bat`
- Pi/Linux/Mac: `bash start_app.sh`
- Manual: `python -m http.server 8422` → `http://localhost:8422/index.html`

**Install as a real app (PWA):**

| Platform | Steps |
|---|---|
| Windows (Chrome/Edge) | ⊕ install icon in the address bar → own window, Start-menu entry, offline |
| Android (Chrome) | ⋮ → *Add to Home screen* → *Install* (HTTPS hosted → full install works) |
| iPhone (Safari) | Share → *Add to Home Screen* → fullscreen launch |

**Connect LIVE data:** tap the **⚡ chip** — the app reads `broker.js` (copy `broker.js.example`, keep out of git) or falls back to `ws://<host>:9001`. Telemetry is authoritative — the app never re-simulates.

```json
{
  "v": 1, "ts": 1727800000.5, "boot_id": "a1b2c3", "seq": 42,
  "chicks": [[50.2, 51.1], [48.9, 49.7]],
  "count": 2,
  "floorT": 31.8, "baseline": 33.5, "trim": 0.5, "setpoint": 34.0,
  "duty": 64, "nh3": 6, "state": "COLD", "crowding": false
}
```

**Zero-hardware demo:** `python pipeline/test_broker_ws.py` (needs `pip install amqtt`) → open the app → **⚡** → 45 simulated chicks wander/huddle while the classifier reacts. Ideal adviser demo.

---

## 3. Supabase setup (Chapter 4 data + live feed storage)

### 3.1 Restore the project
`gpllypfnxjjkzzmaxtub.supabase.co` currently doesn't resolve (free-tier pause/deletion).
1. supabase.com dashboard → **Restore** (if paused) or create a new project
2. If the project URL changed, update the `SB`/`KEY` constants in the app code
3. The app reads tables at runtime — no rebuild needed after the SQL is in

### 3.2 Tables — paste in the SQL editor

```sql
-- 1 Hz raw sensor + spatial data (the training set)
create table telemetry_raw (
  ts timestamptz primary key,
  day int,
  temp_floor_avg real, temp_floor_grid jsonb,
  temp_air real, humidity real,
  nh3_ppm real,
  lamp_duty real, setpoint real, trim real,
  nnd_mean real, nnd_std real, entropy real, clark_r real,
  max_cell_frac real, centroid_x real, centroid_y real,
  positions jsonb,          -- RAW chick positions [[x,y],…]
  audio jsonb,              -- MFCC summary / distress-chirp rate
  state text,
  event_flags jsonb
);

-- 30 s aggregates (what the dashboard consumes)
create table behavior_windows (
  ts timestamptz primary key,
  day int, state text,
  nnd_mean real, entropy real, clark_r real, max_cell_frac real,
  chirp_rate real, trim_applied real,
  resp_s real, stab_s real, alarm_flags jsonb
);

-- one row per actuation (Chapter 4: response + stabilization)
create table control_events (
  ts timestamptz primary key,
  state text,
  trim_before real, trim_after real,
  duty_before real, duty_after real,
  resp_s real, stab_s real,
  outcome text,
  img_before text,          -- Supabase Storage URL (event frame)
  img_after text            -- Supabase Storage URL (recovery frame)
);

-- per-version classifier metrics (Pi publishes, app reads)
create table model_accuracy (
  recorded_at timestamptz primary key,
  version text, trained_at timestamptz,
  accuracy real, f1_macro real, crowd_recall real,
  resp_s real, stab_s real,
  confusion_matrix jsonb, n_windows int
);
```

### 3.3 Chapter-4 views

```sql
create view v_daily_comfort as
  select date_trunc('day', ts) as day,
         avg(temp_floor_avg) avg_t, min(temp_floor_avg) min_t, max(temp_floor_avg) max_t,
         avg((state = 'COMFY')::int) * 100 as pct_comfy,
         sum((event_flags->>'crowd')::int) as alarms
  from telemetry_raw group by 1;

create view v_state_transitions as
  with s as (select ts, state,
                    lag(state) over (order by ts) as prev
             from behavior_windows)
  select prev, state, count(*) as n from s where prev is distinct from state group by 1,2;

create view v_training_export as
  select ts, day, positions, temp_floor_avg, temp_air, nh3_ppm, audio, state
  from telemetry_raw;
```

### 3.4 Indexes + RLS (read-only for the public app)

```sql
create index on telemetry_raw (ts desc);
create index on behavior_windows (ts desc);
create index on control_events (ts desc);

-- the anon key is public in the HTML → SELECT-only
alter table telemetry_raw enable row level security;
create policy "anon read" on telemetry_raw for select to anon using (true);
-- repeat enable+policy per table (behavior_windows, control_events, model_accuracy)
```

**Never ship the service key in the HTML** — writes happen only from the Pi via the service role key.

### 3.5 Storage bucket (live feed + event frames)

Create a **public bucket** named `frames`:
- `frames/live.jpg` — overwritten every 60 s capture (the live feed, ~60 KB, never grows). The app polls it every **15 s** while someone is watching (configurable `feed_poll_s`).
- `frames/events/<ts>_<state>.jpg` — before/after event pairs (~141 MB/month)
- th-visiond uploads `live.jpg` every capture; th-brain saves event frames on state transitions + recovery (URLs go into `control_events.img_before/img_after`)

---

## 4. Remote monitoring — two setups

**Setup A — on-site (same Wi-Fi as the Pi):**
1. Pi: `python3 -m http.server 8422` (serves the app)
2. Pi: mosquitto with the WS listener (§5 step 3)
3. Pi: `python3 pipeline/thermohuddle_draft_v2.py --camera 0` (or `--simulate`)
4. Phone/PC: `http://<pi-ip>:8422/index.html` → **⚡ Connect MQTT**

**Setup B — truly remote (anywhere):**
1. App is hosted on GitHub Pages (done — HTTPS → installable PWA)
2. Pi publishes to a **cloud broker** (HiveMQ Cloud free tier — `wss://` + auth); set `mqtt_host` in the pipeline Config
3. `broker.js` next to the HTML: `url: "wss://<cluster>.hivemq.cloud:8884/mqtt"` + credentials
4. Open the app anywhere → **⚡** → live flock from home

> ⚠️ **Security:** anonymous brokers are fine on the LAN pilot, never on the internet — always `wss://` + username/password.

---

## 5. Pi deployment checklist (when equipment arrives)

```bash
# 1. Network + IP (write it down)
hostname -I

# 2. Copy the folder
scp -r ThermoHuddle/ pi@<pi-ip>:~/

# 3. MQTT broker (TCP 1883 + WS 9001)
sudo apt install -y mosquitto mosquitto-clients
sudo cp ~/ThermoHuddle/mosquitto.conf.example /etc/mosquitto/conf.d/thermohuddle.conf
sudo systemctl restart mosquitto
nc -zv <pi-ip> 1883 && nc -zv <pi-ip> 9001

# 4. Python deps
sudo apt install -y python3-picamera2
pip3 install opencv-python-headless numpy paho-mqtt w1thermsensor adafruit-circuitpython-ads1x15 amqtt supabase

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

**Stubs to wire before step 10** (marked in the draft): `read_floor_temp_stub()` → DS18B20 median; `read_nh3_stub()` → ADS1115+MQ-137 (after 24–72 h burn-in + clean-air baseline); `picam` → Picamera2 loop; PID `duty` → zero-cross dimmer driver (try **integral-cycle** firing first — the ceramic emitter is slow, so Linux timing jitter stops mattering).

**Pre-deployment check (the other PC):** browser present → can ping the Pi → app URL renders → **⚡** shows `connected <pi-ip>:9001` → dots move when a hand waves over the floor.

---

## 6. The 16-week build roadmap (from the Software Build Plan)

Build order is dependency-driven: **heater control and safety work before any AI exists.** Everything up to S6 runs on simulators/fakes on your laptops — no hardware needed.

| Step | What you build | Hardware? | Weeks | "Done when" |
|---|---|---|---|---|
| **S0 Foundations** | Repo, config YAML (all `[A]` params), HAL interfaces with fakes, MQTT+SQLite wrappers, schemas, fake clock, replay tool | No | 1–2 | pytest passes; fake th-sensord → Mosquitto → SQLite rows appear |
| **S1 Control loop** | th-sensord: sensor validation (reject 85.0°/−127°/CRC/>5°C-from-median; PV = median), PID @2 s tuned on `simulate_plant`, dimmer driver (integral-cycle first), soft-start ≤5%/min, age baseline 34→29 °C | Fake → real wk 3 | 3–6 | PID meets overshoot/settling on sim; 24 h read-only on real sensors; stable duty on dummy lamp |
| **S2 Safety** | NH₃ 25/15 ppm hysteresis + 5-min min-run, 50 ppm critical, MQ-137 10-min warmup + scheduled vent, over-temp 38→36, zero-cross-loss 100 ms, watchdogs, **priority arbitration as one pure function** | Sim → bench | 5–7 | Fault-matrix rows covered by table tests; **hazards still fire with th-brain killed** |
| **S3 Brain skeleton** | Table-driven FSM (BOOT/STARTUP/NORMAL/DEGRADED/FAULT_SAFE + HAZARD overlay), boot resume-or-cold-start, trim manager (dwell/rate/limits/fan-blank), camera-loss decay | No | 5–8 | Every transition tested with the fake clock; mid-run restart resumes correctly |
| **S4 Vision** | `make_scenes.py` synthetic ground truth, homography (4 floor markers), CLAHE+Otsu+watershed, selective background update (sleeping chicks never absorbed), blob split (area/÷single-chick + k-means), 9 features, quality gate, median-of-12-frames | Synthetic → camera | 3–9 | Synthetic scenes: R≈1 / L−r≈0 for uniform, R<1 for cluster; frame ≪ 5 s on Pi 5 |
| **S5 Audio** | 16 kHz capture, 1 kHz high-pass, 13 MFCC+deltas, 60-s mean/max, fan masking, placeholder threshold until labels | Clips → mic | 5–8 | Precision/recall measured on labeled clips; fan masking kills false alarms |
| **S6 Fusion** | Feature vector (spatial + quadrant spread + thermal error + audio), rule-based v0 from the signature table, Random Forest (100 trees, depth ≤8) + no-audio variant, temporal filter (4-of-5, ≥0.6 conf), **crowding deterministic outside the model**, shadow mode, `evaluate.py` (macro-F1, confusion, leave-one-day-out) | No (until labels) | 8–11 | Rules drive trim end-to-end in sim; RF trains on synthetic; crowd rule fires with model off |
| **S7 Integration** | systemd units + watchdogs, real topics, SQLite + outbox + snapshot ring (48 h), fault-injection harness for the 13-row matrix, 48-h soak | **Yes** | 8–11 | Cold boot reaches NORMAL unattended; all 13 fault rows respond + recover; soak passes |
| **S8 Closed loop** | Run A (shadow mode, baseline schedule) → labeling tool + **Cohen's κ** between two raters → train/tune/deploy RF → trim enabled for run B with instant-off flag → metrics scripts (comfort-band time, trim steps, energy, uptime, faults) → freeze tag + SD image | **Live chicks** | 12–16 | Model meets targets on held-out data; run B completes with no unsafe heater state; Chapter-4 tables produced |

**Two golden rules:** every sensor/actuator behind a small interface with real+fake versions (all logic runs on your laptop); **th-sensord never imports vision or audio** (a crash there cannot stop the heater).

**Open items to confirm with your adviser ([A] assumptions):** T_max 38 °C, NH₃ thresholds, trim limits/dwell/rate, confidence cutoff 0.6, baseline curve 34→29 °C linear, RF size, Supabase vs another dashboard target.

---

## 7. Keeping the artifacts in sync

The same decision math lives in three places. **If you tune one, update the others:**

| Concept | `pipeline/thermohuddle_draft_v2.py` | `index.html` | Build-plan service |
|---|---|---|---|
| Baseline schedule | `baseline_schedule()` | `baselineForDay()` | th-sensord (S1) |
| Trim bounds/dwell/fan-blank | `Config` + `TrimManager` | `PLAN` const | th-brain (S3) |
| Comfort thresholds | `Config` (nnd/entropy/centroid…) | `computeStatsPts()` | th-visiond + th-brain (S4/S6) |
| Cross-modal confidence (behavior × thermal) | `Fusion` + `Config.conf_*`/`hot_tol_c` | `fuseNow()` + `c-conf` chip | th-brain (S6) |
| Crowding rule | `CrowdingOverride` | crowd streak/grace block | th-brain (S6) |
| NH₃/over-temp | `SafetyRules` + `Config` | `PLAN` + alerts | th-sensord (S2) |

---

## 8. Troubleshooting

| Symptom | Cause → Fix |
|---|---|
| Page won't load on another PC | Server not running (`python3 -m http.server 8422`), different Wi-Fi, or firewall on 8422 |
| Dots don't move in LIVE | Pipeline not running; `tracking_latest.json` missing; MQTT not connected (⚡) |
| ⚡ says "error" | Broker WS listener down → `listener 9001 / protocol websockets` in mosquitto conf; restart |
| Works on-site, not from home | Different network → Setup B (cloud broker + `wss://`) |
| LIVE values don't match HUD expectations | Old app version → reload twice (SW updates on second load); or telemetry missing fields |
| Wrong classifications on real data | Tune thresholds via `--replay`, then update **all three artifacts** (§7) |
| Chicks not detected | `px_per_cm` calibration off; blob area limits too tight/loose; IR pods too dim |
| Alarm won't clear | Crowding latch clears only after sustained dispersal (real system: human ack via `cmd/#`) |
| Feed button shows nothing | No `feed_url` in broker.js and not served from the Pi → use the snapshot loop (§3.5) or same Wi-Fi |
| Analytics cards stay "—" | No control_metrics received yet — the Pi publishes them after the first actuation cycle |
| Supabase REST errors / DNS fails | Project paused/deleted → restore (§3.1); anon key gives SELECT only |

---

*Companion doc: `ThermoHuddle_Overview.md` — what the system is, the comfort-state science, and every app feature explained. Nya~ (ฅ'ω'ฅ)*
