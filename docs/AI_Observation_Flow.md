# Trained-model observation flow

This is an observation-only integration, not a validated automatic brooder controller.

## Data path

1. Pi NoIR camera captures a real 640x480 BGR image every five seconds.
2. Revision-pinned `Williamsanderson/PoultryVision` YOLOv11m detects only class `chicken` (the other class is `egg`). Boxes produce normalized image-plane centroids and a detected count. No synthetic chicks, identity tracking, chick-age recognition or motion-blob count is substituted.
3. The I2S voiceHAT microphone captures continuously at native 48000 Hz. A separate model branch resamples a complete recent 1.5-second audio window to 22050 Hz, normalizes it and builds a 128-band log-Mel spectrogram (training notebook: FFT2048, hop256). `IceKhoffi/chicken-vocalization-classifier` returns Healthy, Noise and Unhealthy probabilities. These are health/noise labels, not heat/cold/draft labels. Silence, incomplete/missing sound and uncertain predictions stay Unknown.
4. A spatial observer measures a 4x4 occupancy distribution, nearest-neighbor distance, centroid displacement and radial distribution in normalized camera coordinates. Sixty-second windows smooth per-frame features. A crowding candidate needs three consecutive windows with median maximum-cell occupancy >=45%; other candidates need agreement in four of five completed windows. Missing detections or a camera gap reset evidence. These thresholds are experimental, not calibrated biology.
5. Audio is independent corroborating evidence, never a direct replacement for spatial or temperature measurements. An Unhealthy call sets an abnormal-vocalization flag; Healthy does not establish thermal comfort. Neither model consumes the other's raw output. Capture is concurrent; inference is CPU-scheduled in the same loop to limit Pi resource use.
6. Atomic packets at `/home/tanverse_2026/Thesis/tracking_latest.json` carry the detections, audio probabilities and assessment. The existing private cloud bridge allowlists public observation fields and updates the public Supabase snapshot. The ThermoHuddle dashboard reads that snapshot and distinguishes trained detections from the old motion regions. Images/audio recordings are not uploaded by this runner.
7. This runner never instantiates the old sensor, thermal-plant or PID stubs, never fabricates floor temperatures/ammonia, and never publishes setpoint/actuator topics. `assessment.control_allowed` is always false. The confirmed assessment remains UNKNOWN while geometry/sensors are uncalibrated; a separate candidate expresses the experimental pattern interpretation.

## Distress warning and live wiring

- The audio classifier's `Unhealthy` label (only when `available: true` and the sample is fresh) raises a distress card on the dashboard with the classifier probability. It is an unvalidated health-proxy warning, not a diagnosis; with zero chicks detected in view it notes the mic may be reacting to background noise. Healthy/Unknown/stale never warn.
- The runner publishes each packet to MQTT `thermohuddle/inference/window` (localhost mosquitto) and writes `/home/tanverse_2026/Thesis/tracking_latest.json`. A symlink `Thermohuddle/tracking_latest.json -> ../Thesis/tracking_latest.json` lets the local `http://<pi>:8422` dashboard fetch the same packet; the MQTT handler now ingests model packets (`d.vision || d.assessment`); the cloud bridge publishes the allowlisted snapshot for the GitHub Pages dashboard. No actuator topics are ever published.

## Pattern interpretation and limits

- Clustered centrally: possible cold or local crowding; not proof of cold. Food, water, fear and occlusion can produce similar observations.
- Sustained >=45% in one image grid cell: crowding candidate. Not a calibrated chicks-per-square-metre measurement.
- Near frame edges: possible hot/avoidance candidate. The image center is NOT yet a calibrated heater location.
- One-sided gathering: possible draft candidate. Draft cannot be confirmed without temperature/airflow context; camera framing/obstacles can imitate it.
- Evenly distributed: comfort candidate, not confirmed comfort. Sleeping, low activity and missing birds require context.
- Too few detections, failed camera, silence/uncertain audio or stale inputs: unknown/unavailable, not comfortable.

The model was trained on poultry, not proven on this particular day-old flock under NoIR lighting. Detection count is not guaranteed to equal the true flock population, especially during overlap/piling. No per-chick identity is assigned. No confidence percentages are combined into a fictional probability of thermal comfort.

## Before enabling closed-loop regulation

Calibrate the actual floor ROI/perspective/scale, heater and fan locations, known flock size, brooding age and day/night conditions. Wire and validate real floor/air temperature and other required sensors. Collect synchronized labeled normal/crowded/cold/hot/draft recordings, evaluate both models and fusion against held-out data, select thresholds and measure false alarms/misses. Validate hard over-temperature cutoff, sensor failure, fan blanking, rate limits and recovery with a dummy load. Only then separately authorize and test actuator integration. This implementation deliberately provides no switch that enables heating from these unvalidated candidates.

## Run and watch

Environment: `/home/tanverse_2026/thermohuddle-ai-env` (system packages visible for Picamera2; CPU-only torch2.9.1/torchvision0.24.1, ultralytics8.3.228, librosa0.11.0).

Service:

    systemctl --user status thermohuddle-ai
    journalctl --user -u thermohuddle-ai -f
    systemctl --user stop thermohuddle-ai
    systemctl --user start thermohuddle-ai

Local evidence: `/home/tanverse_2026/Thesis/ai_observation/frame_latest.jpg` and `observations.jsonl`. These are real observations, not evidence of model accuracy.

For a bounded hardware trial (stop the service first; exclusive camera/mic access):

    /home/tanverse_2026/thermohuddle-ai-env/bin/python /home/tanverse_2026/Thermohuddle/pipeline/ai_observer.py --frames 3 --no-mqtt --output /path/to/trial.json --evidence /path/to/trial-evidence

Tests:

    /home/tanverse_2026/thermohuddle-ai-env/bin/python -m unittest discover -s /home/tanverse_2026/Thermohuddle/tests -p 'test_*.py' -v

Synthetic unit fixtures test code logic only; live packets and the included repository audio sample exercise the actual trained checkpoints. Never present sample-audio inference as live flock validation.
