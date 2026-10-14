# ThermoHuddle 🐤

**Edge AI smart brooder** — infers chick thermal comfort from spatial flock behavior and gently trims the heat lamp around an age-based schedule. CpE 404 Capstone Design 1.

Team: Bolda · Gabriel · Payumo · Tan · Tangcuangco

## Try it now (no install)

Open **`brooder_tracker.html`** in any browser — or serve it for the full PWA experience:

```bash
# Windows:  double-click start_app.bat
# Linux/Pi: bash start_app.sh
# manual:   python -m http.server 8422 → http://localhost:8422/brooder_tracker.html
```

- **Simulator**: keys 1–7 force scenarios (Comfortable, Too cold, Too hot, Draft, Crowding, Lamp failure, Ammonia) · **A** auto-cycle · **N** next brooding day · **S** PNG · drag/scroll to move the camera
- **LIVE**: click **◉ LIVE data** — dots = real (or simulated) chick detections, classified in real time
- **MQTT**: click **⚡ Connect MQTT** — needs a WebSocket broker (mosquitto with `listener 9001 / protocol websockets`, or a cloud broker via `broker.js` — copy `broker.js.example` and keep `broker.js` out of git)
- **Install as app**: install icon in the address bar (Chrome/Edge) / Add to Home Screen (Android/iOS)

**Demo with zero hardware:** `python test_broker_ws.py` (needs `pip install amqtt`) → in the app click ⚡ → 45 simulated chicks wander and huddle while the classifier reacts.

## What's here

| File | Purpose |
|---|---|
| `brooder_tracker.html` | The 3D dashboard app — plan-aligned control model (baseline + bounded trim, crowding hard rule), LIVE tracking, MQTT-over-WS, installable PWA |
| `thermohuddle_draft_v2.py` | Pi pipeline draft: detection → spatial features → classification → trim manager → PID → telemetry. Modes: `--simulate` (no hardware), `--replay` (tune on recorded frames), `--camera` (live) |
| `thermohuddle_draft.py` | v0.1 draft — kept for reference, use v2 |
| `test_broker_ws.py` | Test MQTT broker simulating Pi telemetry for demos |
| `mosquitto.conf.example` / `broker.js.example` | Broker config + credentials template |
| `start_app.bat` / `start_app.sh` | One-click launchers |
| `p5.min.js` / `mqtt.min.js` / `sw.js` / `manifest.json` / icons | Local libs + PWA plumbing (fully offline) |
| **`ThermoHuddle_Project_Guide_v2.md`** | **The full guide** — architecture, 16-week roadmap, Pi deployment, remote monitoring, troubleshooting |

## Architecture (summary)

Five services on the Pi: `th-sensord` (safety-critical control, no AI imports) · `th-visiond` · `th-audiod` · `th-brain` (fusion + bounded trim) · `th-uplink` (MQTT/SQLite).

The classifier never drives the heater directly — it only adjusts a ±2 °C trim on the age-based baseline (34→29 °C over 14 days), with a 10-min dwell, 1 °C/h rate limit, and fan blanking. Crowding is a deterministic max-cell-fraction rule outside the model with human acknowledgement.

Full details, deployment checklists, and the S0–S8 roadmap: **`ThermoHuddle_Project_Guide_v2.md`**
