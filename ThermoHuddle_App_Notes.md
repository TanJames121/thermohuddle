# ThermoHuddle — App & Data Notes (Chapter 4 / live-app alignment)

_What the app shows, where each number comes from, and how the Pi pipeline feeds it. Short but complete — everything below maps to a real field/table/topic._

---

## 1. The pipeline (how data reaches this app)

```
NoIR cam + INMP441 + DS18B20 + MQ-137 + DHT22
        │  (raw frames / readings, all on the Pi)
        ▼
Raspberry Pi 5  ── th-sensord ─► MQTT: thermohuddle/telemetry/env
        │  (raw chick positions, per-frame)
th-visiond ─► MQTT: thermohuddle/vision/positions (+ window metrics)
        │
th-brain ─► MQTT: thermohuddle/inference/window, /events, /status
        │        (state, trim, control metrics)
        ▼
Supabase (Postgres) ◄─ uplink service (writes every table row)
        ▼
This web app (GitHub Pages) ◄─ MQTT-over-WebSocket for live, Supabase REST for history/analytics
```

- **Live values** (state, temps, dots) → MQTT WebSocket, near-real-time.
- **History/analytics** → Supabase REST (`urban_history`-style tables).
- **No middle layer decides anything** — the Pi's th-brain is the only decision-maker; the app is a viewer.

## 2. Dashboard fields explained (what each number means)

| Field | Source | Meaning |
|---|---|---|
| **State** | th-brain | One of TOO COLD / COMFORTABLE / TOO HOT / DRAFT / CROWDING (from spatial stats + audio) — drives the trim |
| **Floor temp** | DS18B20 array | Actual floor temp at chick level, °C — the PID's process variable |
| **Setpoint** | baseline(day) + trim | What the PID targets right now |
| **Lamp duty** | actuator feedback | 0–100 % power to the IR heat lamp (zero-cross dimmer) — the PID's output |
| **Trim** | th-brain outer loop | ±2 °C behavioral adjustment, ±0.5 °C steps every 40 s while a non-comfy state persists |
| **NND** | th-visiond | Nearest-Neighbor Distance — avg distance from each chick to its closest neighbor; clumping ⇒ small NND |
| **Entropy** | th-visiond | Shannon entropy of the 4×4 grid occupancy — how evenly chicks fill the floor (0 = one pile, 1 = even) |
| **Clark R** | th-visiond | observed mean NND ÷ 0.5·√(A/N) under complete spatial randomness (A = floor area, N = chicks); R < 1 clustered, ≈ 1 random, > 1 uniform |
| **Max cell %** | th-visiond | Largest share of the flock in any single grid cell — ≥ 45 % triggers the crowding hard rule |
| **NH₃** | MQ-137 | Ammonia ppm — ≥ 25 ppm vent ON, ≥ 50 ppm critical |
| **Day** | user/system | Brooding day 1–14 — baseline curve 34 → 29 °C |

## 2b. Behavioral reasoning card (the "why" line)

The dashboard shows a card that answers "why are they doing this?":
- **COLD → clumping:** chicks huddle to conserve body heat; NND drops, center occupancy rises. The controller responds by raising the setpoint.
- **HOT → wall-seeking + spreading:** chicks avoid each other and the warm center to shed heat; entropy high, center occupancy low. Trim goes negative.
- **DRAFT → one-sided avoidance:** centroid shifts away from the draft; chicks pack on the leeward side. Fix the physical leak — heat won't fix it.
- **CROWDING → piling:** >45 % of chicks in one cell = smothering risk; alarm + vent burst. **This is a safety rule, not learned behavior** — it must fire even on day 0.
- **LAMPFAIL:** cold-type clustering despite high setpoint + duty ≈ 0 → heat source fault, not setpoint issue.
- **AMMONIA:** birds avoid the litter center, restlessness/chirping up; NH₃ thresholds drive the fan.
- **COMFY:** NND ≈ CSR expectation, cells balanced, no actuation.

These texts are **interpretations of the pattern**, not predictions — exactly "the AI reads behavior, the human reads the why".

## 3. Chapter 4 data analysis — what Supabase must store

The AI you'll train **must have raw data** and draw its own conclusions — so the schema keeps **raw positions + raw sensor rows + windowed aggregates**. All Chapter 4 numbers can be computed from these tables.

### `telemetry_raw` — everything, 1 Hz
| column | type | notes |
|---|---|---|
| `ts` | timestamptz PK-ish | Pi clock (NTP-synced) |
| `day` | int | brooding day |
| `temp_floor_avg` / `temp_floor_grid` | real / jsonb | avg + 4×4 per-sensor grid (jsonb array) |
| `temp_air`, `humidity` | real | DHT22 |
| `nh3_ppm` | real | MQ-137 |
| `lamp_duty` | real | 0–1 |
| `setpoint`, `trim` | real | outer loop |
| `nnd_mean`, `nnd_std`, `entropy`, `clark_r`, `max_cell_frac`, `centroid_x/y` | real | spatial metrics per frame/window |
| `positions` | jsonb | **RAW chick positions [[x,y],…] — the training set** |
| `audio` | jsonb | MFCC summary / distress-chirp rate |
| `state` | text | th-brain's label at that moment |
| `event_flags` | jsonb | alarm/vent/ack events |

> **Training note:** `positions` jsonb is the raw training data. The model consumes positions + temp + audio → infers comfort. Labels for supervised training come from Phase 1 (pilot) where humans labelled behavior windows; the model then learns the mapping raw→comfort itself.

### `behavior_windows` — 30 s aggregates (what the dashboard consumes)
Same columns as raw but aggregated (mean NND, entropy, cell fracs, chirp rate, state, trim applied, response/stab times, alarm flags).

### `control_events` — every actuation, one row each
| column | notes |
|---|---|
| `ts`, `state`, `trim_before/after`, `duty_before/after`, `resp_s`, `stab_s`, `outcome` | written by uplink from th-brain events |

- **resp_s** = detection→actuation delay (s)
- **stab_s** = actuation→floor temp within ±0.5 °C of setpoint for 5 s

### `model_accuracy` — per-version metrics (Pi publishes, app reads)
`version`, `trained_at`, `accuracy`, `f1_macro`, `crowd_recall`, `resp_s`, `stab_s`, `confusion_matrix` (jsonb), `n_windows`

> MAPE **removed** from the app — this is a reactive classifier + PID loop, not a forecaster. Chapter 4 reports **accuracy/F1/confusion matrix for the classifier** and **response/stabilization times for the loop** — no prediction error because there is no prediction.

### Views for Chapter 4 (create these in Supabase SQL editor)
- `v_daily_comfort`: per-day avg/min/max floor temp, % comfy, alarms, NH₃ events, avg resp/stab
- `v_state_transitions`: transition matrix (from_state → to_state counts)
- `v_hourly_baseline`: hour-of-day × day-of-brood baseline for the adaptive baseline
- `v_crowd_episodes`: episode start/end, peak cell %, ack latency
- `v_training_export`: **the model-training export** — raw `positions` jsonb + temp + audio + state + day + hour; the app's ⬇ CSV button downloads from here

### Indexes you'll want
```sql
CREATE INDEX ON telemetry_raw (ts DESC);
CREATE INDEX ON behavior_windows (ts DESC);
CREATE INDEX ON control_events (ts DESC);
```

### RLS note
With the anon key in a public web app, tables must be **read-only for anon** (`select` only); writes come only from the uplink service role (server-side key). **Never** ship the service key in the HTML.

```sql
alter table telemetry_raw enable row level security;
create policy "anon read" on telemetry_raw for select to anon using (true);
```

## 4. Live feed vs dots — how both work

**Two view options in the app (🎥 button toggles):**
1. **3D tracking dots** — the analysis view: every chick = a marker at its detected (x, z). This is what the algorithm actually sees; best for verifying tracking quality.
2. **Live camera feed** — real video from the NoIR camera, **not** what the algorithm computes. Best for eyeballing the brooder.

**How the feed reaches your phone:**

| option | how | latency | Pi CPU cost | remote (off-LAN) |
|---|---|---|---|---|
| **A. MJPEG stream** | Pi runs a tiny MJPEG HTTP server, app loads `http://<pi-ip>:8000/stream.mjpg` into the viewport as a moving-image element | ~0.2–1 s | low | ⚠ app is HTTPS (GitHub Pages) → browser blocks the HTTP stream (mixed content); works on same Wi-Fi, or behind an HTTPS wrapper |
| **B. WebRTC** | Pi runs go2rtc/MediaMTX (single binary) → app connects WebRTC video | ~0.3–1 s | medium | ✅ works from anywhere, HTTPS-native |
| **C. Snapshot loop** | th-visiond uploads `frame.jpg` every 1–2 s to Supabase Storage (public bucket) → app refreshes `<img src=frame.jpg?t=…>` | 1–2 s | lowest | ✅ HTTPS via Supabase, trivially reliable, works everywhere |

**C is the recommended build** — simplest, works from anywhere, and th-visiond already has the frame in hand.

**Answering "pic or video?":** The **analysis** is snapshot-based (th-visiond grabs a frame every ~1–2 s → detects → publishes positions). The **feed** is whatever transport you pick above; option C **is** a picture loop (1–2 s), option A/B give true live video. **The AI never needs video** — 0.5–2 fps snapshots are enough for behavior tracking, keep the Pi's CPU for inference, and use whatever transport you pick for the human-facing feed.

- **PI-side components:**
  - th-visiond: grab → detect → publish positions + (option C) upload frame.jpg → Supabase Storage `frames/frame.jpg` (overwrite same name)
  - uplink: also write `media_url` on the window row so history items can show the frame from that moment.

## 5. Shannon / spatial theory — yes, and where

- **Shannon entropy** is used exactly as defined in Shannon (1948): H = −Σ pᵢ log pᵢ over the chick distribution across the 4×4 floor grid, normalized by log(16). 0 = one pile, 1 = perfectly even spread. This is the **even-spread** axis of the behavior reading.
- **Clark–Evans R** = observed mean NND / expected NND under complete spatial randomness (CSR), expected = 0.5·√(A/N). R < 1 clustering, R ≈ 1 random, R > 1 uniform. This is the **clumping vs even** axis.
- **NND** itself is the classic spatial-statistics tool for point patterns — "how close does the typical bird sit to its nearest neighbor".
These three together = the **spatial dispersion analysis** in your title. The AI (trained model) consumes them as features; the rules engine (safety) acts on them directly. The trained AI draws its own conclusions from **raw positions + temps + audio**; the entropy/Clark R/NND are the interpretable summary the app shows humans and Chapter 4 statistics the thesis needs.

## 6. What was NOT added (per your instruction)
- **No simulations in this build.** The scenario buttons exist for demo/debug only (hidden under 🎛) — the app now boots into LIVE mode and shows "awaiting first behavior window" until real data arrives.
- **No prediction/forecast anywhere.** No "predict the state in 1h" cards — the system is reactive: **detect behavior → correct setpoint → verify stabilization**.

## 7. Supabase is currently unreachable — restore it
The project `gpllypfnxjjkzzmaxtub.supabase.co` no longer resolves (free-tier pause/deletion). To restore:
1. Log into supabase.com dashboard → the project should offer **Restore** if paused (or create a new project).
2. Run the SQL from §3 in the SQL editor (tables + views + RLS + indexes).
3. Update the SB URL/key in the app code (`SB` and `KEY` constants) if the new project has a different URL.
4. The app reads the tables at runtime — no rebuild needed after the SQL is in.
