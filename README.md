# ThermoHuddle 🐤

**Edge AI smart brooder** — infers chick thermal comfort from spatial flock behavior and gently trims the heat lamp around an age-based schedule. CpE 404 Capstone Design 1.

Team: Bolda · Gabriel · Payumo · Tan · Tangcuangco

## Use the app (no install)

**https://tanjames121.github.io/thermohuddle/** — works on any phone/PC. Install it as a real app: Chrome/Edge ⊕ install icon, Android ⋮ → Add to Home screen, iOS Share → Add to Home Screen.

Or run locally: double-click `start_app.bat` (Windows) / `bash start_app.sh` (Pi/Linux/Mac) → `http://localhost:8422/index.html`.

- **GitHub Pages LIVE:** opens in observation mode and automatically checks the public HTTPS camera/microphone snapshot every 2 seconds while visible. No MQTT password or connect click is needed. New readings appear at the Pi pipeline cadence (currently about 10 seconds), not at a fabricated animation rate. Hidden tabs pause requests and refresh when visible again.
- **Local LIVE:** MQTT remains available through private, ignored `broker.js`; same-origin Pi JSON is the fallback. Never commit publisher credentials to a public repository.
- **Camera view:** a spatial reconstruction of motion regions, not live video or a validated chick count. Video needs a separately configured stream.
- **Camera/mic pilot:** temperature, humidity and ammonia are not connected. Thermal controls, thermal history/export and comfort claims are unavailable in LIVE mode. Scenario controls explicitly use simulated data.
- **Panels:** Overview, History, Analytics, Field log and Warnings. The Pi and its cloud bridge must stay running for fresh remote observations.

## Repo layout

| Path | Purpose |
|---|---|
| `index.html` | **The app** — mobile 3D dashboard PWA (plan-aligned control model, LIVE tracking, MQTT-over-WS, offline) |
| `manifest.json`, `sw.js`, `p5.min.js`, `mqtt.min.js`, icons | PWA plumbing + local libs (fully offline) |
| `start_app.bat` / `start_app.sh` | One-click launchers |
| `broker.js.example`, `mosquitto.conf.example` | Broker credentials/config templates (keep real `broker.js` out of git) |
| **`docs/ThermoHuddle_Overview.md`** | **What the project is + how every feature works** — comfort states, spatial science (NND/Shannon/Clark–Evans), app manual, data model |
| **`docs/ThermoHuddle_Build_Guide.md`** | **How to build it** — run/install, Supabase setup (full SQL), remote monitoring, Pi deployment, 16-week roadmap, troubleshooting |
| `brooder.css`, `pilot.js`, `cloud-feed.js` | Brooder-themed design, honest pilot status and automatic public HTTPS updates |
| `docs/design/` | Pilot design notes, desktop/mobile previews and browser verification records |
| `pipeline/thermohuddle_draft_v2.py` | Pi pipeline draft: detection → spatial features → classification → trim manager → PID → telemetry. Modes: `--simulate`, `--replay`, `--camera` |
| `pipeline/test_broker_ws.py` | Test MQTT broker simulating Pi telemetry — demo the whole remote-monitoring story with zero hardware (`python pipeline/test_broker_ws.py`, needs `pip install amqtt`) |

## Public camera/microphone uplink

`pipeline/cloud_snapshot_bridge.py` reads the running Pi pipeline snapshot and uploads only allowlisted positions, count, camera availability and microphone measurements. The public object is overwritten, not appended. Source timestamps remain unchanged; old samples are never relabeled as fresh. The browser checks every2s while visible; the source currently reports about every10s.

The installed user service is `thermohuddle-cloud.service` (see `pipeline/thermohuddle-cloud.service.example`). It reads private Supabase write credentials from the Pi configuration, never from GitHub. Check it with `systemctl --user status thermohuddle-cloud.service`. Both this bridge and the camera/mic pipeline must be running. An enabled bridge cannot produce new observations if the source pipeline is stopped.

This is a public dashboard: sanitized motion positions and microphone levels are visible to anyone with the URL. No raw microphone recording, camera video, thermal placeholders or write credentials are uploaded.

## Architecture (summary)

Five services on the Pi: `th-sensord` (safety-critical control, no AI imports) · `th-visiond` · `th-audiod` · `th-brain` (fusion + bounded trim) · `th-uplink` (MQTT/SQLite/Supabase).

The classifier never drives the heater directly — it only adjusts a ±2 °C trim on the age-based baseline (34→29 °C over 14 days), with a 10-min dwell, 1 °C/h rate limit, and fan blanking. Crowding is a deterministic max-cell-fraction rule outside the model with human acknowledgement.

Full details: **`docs/ThermoHuddle_Overview.md`** (what it is & how it works) + **`docs/ThermoHuddle_Build_Guide.md`** (setup & deployment)
