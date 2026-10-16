# ThermoHuddle 🐤

**Edge AI smart brooder** — infers chick thermal comfort from spatial flock behavior and gently trims the heat lamp around an age-based schedule. CpE 404 Capstone Design 1.

Team: Bolda · Gabriel · Payumo · Tan · Tangcuangco

## Use the app (no install)

**https://tanjames121.github.io/thermohuddle/** — works on any phone/PC. Install it as a real app: Chrome/Edge ⊕ install icon, Android ⋮ → Add to Home screen, iOS Share → Add to Home Screen.

Or run locally: double-click `start_app.bat` (Windows) / `bash start_app.sh` (Pi/Linux/Mac) → `http://localhost:8422/index.html`.

- **LIVE**: tap the **⚡ chip** — connects MQTT (reads `broker.js`, or falls back to `ws://<host>:9001`). Telemetry is authoritative; the app never re-simulates.
- **🎥** toggles 3D tracking dots ↔ live camera feed (set `feed_url` in `broker.js`; recommended: snapshot loop to Supabase Storage).
- **🎛 scenarios** (Comfy/Cold/Hot/Draft/Crowding/Lamp-fail/NH₃, Auto, Next-day) are demo/debug only — the app boots in LIVE and waits for real data.
- **📊 Stats · 📈 History (24h/weekly/monthly) · 🔬 Analytics (CSV export, response/stabilization metrics) · 🗒 Logs · ⚠️ Warnings**

## Repo layout

| Path | Purpose |
|---|---|
| `index.html` | **The app** — mobile 3D dashboard PWA (plan-aligned control model, LIVE tracking, MQTT-over-WS, offline) |
| `manifest.json`, `sw.js`, `p5.min.js`, `mqtt.min.js`, icons | PWA plumbing + local libs (fully offline) |
| `start_app.bat` / `start_app.sh` | One-click launchers |
| `broker.js.example`, `mosquitto.conf.example` | Broker credentials/config templates (keep real `broker.js` out of git) |
| **`docs/ThermoHuddle_Overview.md`** | **What the project is + how every feature works** — comfort states, spatial science (NND/Shannon/Clark–Evans), app manual, data model |
| **`docs/ThermoHuddle_Build_Guide.md`** | **How to build it** — run/install, Supabase setup (full SQL), remote monitoring, Pi deployment, 16-week roadmap, troubleshooting |
| `docs/design/` | FigCraft design files (historical) |
| `pipeline/thermohuddle_draft_v2.py` | Pi pipeline draft: detection → spatial features → classification → trim manager → PID → telemetry. Modes: `--simulate`, `--replay`, `--camera` |
| `pipeline/test_broker_ws.py` | Test MQTT broker simulating Pi telemetry — demo the whole remote-monitoring story with zero hardware (`python pipeline/test_broker_ws.py`, needs `pip install amqtt`) |

## Architecture (summary)

Five services on the Pi: `th-sensord` (safety-critical control, no AI imports) · `th-visiond` · `th-audiod` · `th-brain` (fusion + bounded trim) · `th-uplink` (MQTT/SQLite/Supabase).

The classifier never drives the heater directly — it only adjusts a ±2 °C trim on the age-based baseline (34→29 °C over 14 days), with a 10-min dwell, 1 °C/h rate limit, and fan blanking. Crowding is a deterministic max-cell-fraction rule outside the model with human acknowledgement.

Full details: **`docs/ThermoHuddle_Overview.md`** (what it is & how it works) + **`docs/ThermoHuddle_Build_Guide.md`** (setup & deployment)
