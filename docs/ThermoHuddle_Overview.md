# 🐤 ThermoHuddle — Project Overview & Feature Reference

**What the project is, how every feature works, and why the design is the way it is.** For setup/deployment steps, see `ThermoHuddle_Build_Guide.md`.

Team: Bolda · Gabriel · Payumo · Tan · Tangcuangco — CpE 404 Capstone Design 1
Based on: Capstone Proposal Form + Software Build Plan (Oct 14, @James Matthew)

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
| **Cloud telemetry & dashboard** | MQTT (local broker) → SQLite logging → Supabase; the live app is the mobile 3D dashboard |

### The comfort states — behavior signatures and what the system does

| State | Behavioral signature | Action | Authority limit |
|---|---|---|---|
| **Comfortable** | Uniform spread, high entropy, Clark–Evans R ≈ 1, quiet audio | Hold trim | — |
| **Too Cold** | Tight huddle toward the lamp, low NND, R < 1, low entropy, high hidden fraction | Trim **+0.5 °C** | up to **+2.0 °C** |
| **Too Hot** | Spread to edges, high radial distance, empty cells under the lamp | Trim **−0.5 °C** | down to **−2.0 °C** |
| **Draft** | Lopsided clustering, high centroid offset + anisotropy, quadrant temp spread | Alert + check inlet, trim +0.5 °C | up to +1.0 °C while active |
| **Crowding Risk** | High max-cell fraction, strong small-radius clustering, distress audio | **ALARM + vent burst + human ack** — deterministic hard rule *outside* the model; re-alerts every 5 min | Needs a human |

**The key design idea:** the classifier never directly controls the heater. It only nudges the setpoint within a small bounded window (±2 °C), on top of the age-based baseline, after a 10-minute dwell, at most 1 °C/hour, and never while the fans just ran (**fan blanking** — otherwise the fans create a draft, the classifier answers it with more heat, and the loop never ends).

---

## 2. System architecture

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
│      │         fusion → temporal filter → TRIM (bounded)            │
│      │         crowding hard rule · priority arbitration P0–P4      │
│      │                                                              │
│  th-uplink ──► MQTT publish · SQLite (WAL) · outbox · snapshots      │
│      │         (+ frame.jpg upload to Supabase Storage for feed)    │
│                                                                     │
│  Mosquitto broker: :1883 (TCP) + :9001 (WebSocket for the app)       │
└─────────────────────────────────────────────────────────────────────┘
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

## 3. How the science works — spatial dispersion analysis

These three statistics are the **spatial dispersion analysis** in the project title. The trained model consumes them (plus raw positions, temps, audio) as features; the safety rules act on them directly.

- **NND (Nearest-Neighbor Distance)** — the classic point-pattern statistic: the average distance from each chick to its closest neighbor. Huddling ⇒ small NND; spreading ⇒ large NND.
- **Shannon occupancy entropy** — exactly as defined in Shannon (1948): H = −Σ pᵢ·log pᵢ over the chick distribution across the 4×4 floor grid, normalized by log(16). **0 = one pile, 1 = perfectly even spread** — the *evenness* axis.
- **Clark–Evans R** — observed mean NND ÷ expected NND under complete spatial randomness (CSR), expected = 0.5·√(A/N) (A = floor area, N = chicks). **R < 1 clustered, ≈ 1 random, > 1 uniform** — the *clumping* axis.

**The control cascade, end to end:** cam frame → positions → spatial stats (+ audio distress) → classifier → comfort state → (dwell 10 min, rate-limited) trim ±0.5 °C on the age baseline → inner PID drives lamp duty (0–100 %) through the zero-cross dimmer → floor temp changes → chicks redistribute → loop repeats. **There is no prediction/forecast anywhere** — the loop is reactive: detect behavior → correct setpoint → verify stabilization.

**Physical limit (honest boundary):** if HOT persists with the lamp at 0 % duty, the brooder is simply tracking outside air — trim cannot cool below ambient. Fans give convective/panting relief only. The correct response is a farmer-action warning: wet-sack evaporative cooling on the fan intake (standard PH practice, −2–4 °C on incoming air), shade, or brooding during cooler hours.

---

## 4. The live app — every feature explained

The app (hosted at https://tanjames121.github.io/thermohuddle/) is a **viewer only** — the Pi's th-brain is the single decision-maker. It boots in LIVE mode and never shows simulated data unless a human picks a scenario.

### 4.1 Dashboard fields

| Field | Source | Meaning |
|---|---|---|
| **State** | th-brain | TOO COLD / COMFORTABLE / TOO HOT / DRAFT / CROWDING (spatial stats + audio) — drives the trim |
| **Floor temp** | DS18B20 array | Floor temp at chick level, °C — the PID's process variable |
| **Setpoint** | baseline(day) + trim | What the PID targets right now |
| **Lamp duty** | actuator feedback | 0–100 % power to the IR heat lamp (zero-cross dimmer) — the PID's output |
| **Trim** | th-brain outer loop | ±2 °C behavioral adjustment, ±0.5 °C steps every 40 s while a non-comfy state persists |
| **NND / Entropy / Clark R / Max cell %** | th-visiond | the spatial statistics of §3, live |
| **NH₃** | MQ-137 | Ammonia ppm — ≥ 25 ppm vent ON, ≥ 50 ppm critical |
| **Day** | user/system | Brooding day 1–14 — baseline curve 34 → 29 °C |

### 4.2 Behavioral reasoning card ("why are they doing this")

- **COLD → clumping:** chicks huddle to conserve body heat; NND drops, center occupancy rises. Controller raises the setpoint.
- **HOT → wall-seeking + spreading:** chicks avoid each other and the warm center to shed heat; entropy high, center empty. Trim goes negative.
- **DRAFT → one-sided avoidance:** centroid shifts away from the draft; chicks pack on the leeward side. Fix the physical leak — heat won't fix it.
- **CROWDING → piling:** >45 % of chicks in one cell = smothering risk; alarm + vent burst. **Safety rule, not learned behavior** — fires even on day 0.
- **LAMPFAIL:** cold-type clustering despite high setpoint + duty ≈ 0 → heat source fault, not setpoint issue.
- **AMMONIA:** birds avoid the litter center, restlessness/chirping up; NH₃ thresholds drive the fan.
- **COMFY:** NND ≈ CSR expectation, cells balanced, no actuation.
- **STILL HOT @ LAMP 0 % (ambient limit):** the trim cannot cool below ambient — farmer actions listed (see §3).

These are **interpretations of the pattern, not predictions** — the AI reads behavior, the human reads the why.

### 4.3 Pages

| Page | What's on it |
|---|---|
| **📊 Stats** | banner, stat tiles, baseline/trim/crowding chips, alarm card, reasoning card |
| **📈 History** | temp + setpoint chart with **24 hours / Weekly / Monthly** ranges + summary chips (avg, min/max, % comfy) |
| **🔬 Analytics** | summary stats grid, daily rollup table + ⬇ CSV export, control-loop metrics (§4.4) |
| **🗒 Logs** | timestamped event log |
| **⚠️ Warnings** | alarm/warning log |

### 4.4 Control-loop metrics (deliberately no MAPE)

The system is **reactive** — detect behavior → correct setpoint → verify stabilization. No forecasting exists, so no prediction-error metric exists. Instead:

- **Response time** — behavior change detected → actuation (trim step / duty change). ≤ 60 s 🟢, ≤ 180 s 🟡.
- **Stabilization time** — actuation → floor temp back within ±0.5 °C of setpoint, held 5 s. ≤ 300 s 🟢, ≤ 900 s 🟡.
- Classifier quality (once the trained model is deployed): **accuracy, macro-F1, crowding recall** — from the confusion matrix, exactly what Chapter 4 needs.

The Pi publishes `{kind:"control_metrics", data:{resp_s, stab_s, accuracy, f1, crowd_recall, version}}` on `thermohuddle/status` and the cards fill automatically.

### 4.5 Live feed vs tracking dots (🎥 button)

- **3D tracking dots** — the analysis view: every chick = a marker at its detected (x, z). This is what the algorithm sees; best for verifying tracking quality.
- **Live camera feed** — real frames from the NoIR cam for eyeballing the brooder. **The AI never uses video**: th-visiond grabs a frame every 1–2 s (a picture, not a stream), detects, publishes positions. The human feed is a separate transport — the app **polls `live.jpg` from Supabase Storage every 15 s** (configurable via `feed_poll_s`), **only while the feed view is open and the tab is visible** (works from anywhere over HTTPS; bucket setup in Build Guide §3.5).

### 4.6 Frame capture & storage (how the space-saving works)

The camera captures **every 60 s** for analysis — but **only event frames are archived**:

| What | Where | Size |
|---|---|---|
| **Live feed** | `frames/live.jpg` — ONE file, overwritten every capture | ~60 KB total, never grows |
| **Event archive** | `frames/events/<ts>_<state>.jpg` — on state change + one **after stabilization** | ~5 MB/day @ 40 events → ~141 MB/month, 30-day retention |

- Every 60 s frame → detect → publish positions → **overwrite `live.jpg`** → done. No history by default.
- **Archive triggers:** a state transition (→COLD/HOT/DRAFT/CROWDING/LAMPFAIL/NH₃) saves the **before** frame; the recovery transition saves the **after** frame. Each `control_events` row stores both URLs (`img_before`/`img_after`).
- **Why not keep all frames?** 1,440 pics/day ≈ 84 MB/day → the 1 GB free tier dies in ~12 days. Event-based ≈ 141 MB/month, fits free.
- These before/after pairs are exactly the Chapter 4 evidence images: *clustering (cold) → trim applied → evenly spread (recovered)*.
- Bandwidth: while the feed view is open and the tab visible, the app polls `live.jpg` **every 15 s** (configurable: `feed_poll_s` in `broker.js`) ≈ **14 MB/hr per viewer** — free egress ≈ **340 viewer-hours/month**. No polling happens with the feed closed or the tab backgrounded. Monitor, don't 24/7-stream.

### 4.7 Scenarios (demo/debug only)

The 🎛 sheet has 10 scenario buttons (Comfy, Cold, Hot, Draft, Crowding, Lamp fail, NH₃ spike, Auto cycle, LIVE, Next day). **Demo-only** — the app boots in LIVE and waits for real data; no synthetic data ever appears on its own.

---

## 5. Data model (what gets stored and why)

The trained AI **must have raw data** and draw its own conclusions — so the schema keeps raw positions + raw sensor rows + windowed aggregates. Full SQL + setup steps are in the **Build Guide §3**; conceptually:

- **`telemetry_raw`** (1 Hz) — every sensor value, every spatial metric, the **raw `positions` jsonb** (the training set), audio summary, and the th-brain state label. This is the ground truth for training and Chapter 4.
- **`behavior_windows`** (30 s aggregates) — what the dashboard consumes.
- **`control_events`** — one row per actuation: trim/duty before+after, `resp_s`, `stab_s`, and the `img_before`/`img_after` evidence pair.
- **`model_accuracy`** — per-version classifier metrics published by the Pi (accuracy, F1, crowding recall, confusion matrix).
- Chapter-4 views: daily comfort summary, state-transition matrix, hourly baseline, crowd episodes, and the training export (raw positions + labels).

> **Training note:** `positions` jsonb is the raw training data. The model consumes positions + temp + audio → infers comfort. Labels come from the Phase-1 pilot where humans label behavior windows (with Cohen's κ agreement); the model then learns the mapping raw→comfort itself.

---

*Companion doc: `ThermoHuddle_Build_Guide.md` — repo layout, running the app, Supabase setup, Pi deployment, the 16-week roadmap, and troubleshooting. Nya~ (ฅ'ω'ฅ)*
