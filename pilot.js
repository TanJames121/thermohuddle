/* Read-only pilot: detections and classifier outputs are not comfort diagnoses. */
const pilotNumber = (value, low, high) => Number.isFinite(value) && value >= low && value <= high;
const pilotAudioClasses = ['Healthy', 'Noise', 'Unhealthy'];
const pilotAssessmentStates = ['UNKNOWN', 'CROWDING', 'POSSIBLE_COLD', 'POSSIBLE_HOT', 'POSSIBLE_DRAFT', 'COMFY_CANDIDATE'];
const pilotProbabilitiesValid = probabilities => !!probabilities && !Array.isArray(probabilities)
  && Object.keys(probabilities).length === 3
  && pilotAudioClasses.every(key => pilotNumber(probabilities[key], 0, 1))
  && Math.abs(pilotAudioClasses.reduce((sum, key) => sum + probabilities[key], 0) - 1) <= 0.001;
const pilotAssessmentValid = assessment => !!assessment
  && pilotAssessmentStates.includes(assessment.state) && pilotAssessmentStates.includes(assessment.candidate)
  && ['CLUSTERED', 'DISPERSED', 'ASYMMETRIC', 'EVEN', 'NO_DETECTIONS', 'INSUFFICIENT'].includes(assessment.pattern)
  && ['uncalibrated', 'warming_up', 'observation_only'].includes(assessment.status)
  && assessment.control_allowed === false && pilotNumber(assessment.window_s, 0, 86400)
  && Number.isInteger(assessment.samples) && assessment.samples >= 0 && assessment.samples <= 1000000
  && ['abnormal_vocalization', 'healthy_vocalization', 'noise', 'unavailable'].includes(assessment.audio_support)
  && typeof assessment.reason === 'string' && assessment.reason.length <= 512
  && !/[\u0000-\u001f\u007f-\u009f]/.test(assessment.reason);

window.pilotViewState = function (sample, now = Date.now()) {
  const timestamp = sample && Number.isFinite(sample.ts) ? sample.ts * 1000 : NaN;
  const age = now - timestamp;
  const fresh = Number.isFinite(age) && age >= 0 && age < 30000;
  const cameraLive = fresh && sample.cam_ok === true;
  const vision = sample && sample.vision;
  const detector = !!vision && ['PoultryVision-YOLOv11m', 'ChickDetector-YOLOv8n'].includes(vision.model)
    && vision.coordinate_system === 'uncalibrated_camera' && vision.calibrated === false
    && pilotNumber(vision.inference_ms, 0, 3600000) && pilotNumber(vision.confidence_min, 0, 1);
  const positionsValid = !!sample && Array.isArray(sample.chicks) && sample.chicks.length === sample.count
    && sample.chicks.every(point => Array.isArray(point) && point.length === 2
      && point.every(value => pilotNumber(value, -10000, 10000)));
  const count = cameraLive && Number.isInteger(sample.count) && sample.count >= 0 && sample.count <= 1000
    && (!detector || positionsValid) ? sample.count : null;
  const audio = sample && sample.audio && typeof sample.audio === 'object' && !Array.isArray(sample.audio) ? sample.audio : null;
  const audioFresh = fresh && !!audio && (!('ts' in audio)
    || (Number.isFinite(audio.ts) && now - audio.ts * 1000 >= 0 && now - audio.ts * 1000 < 30000));
  const micLive = audioFresh && pilotNumber(audio.level_db, -200, 10);
  const classifier = !!audio && audio.model === 'chicken-vocalization-classifier';
  const classifierLive = audioFresh && classifier && audio.available === true
    && [...pilotAudioClasses, 'Unknown'].includes(audio.label) && pilotProbabilitiesValid(audio.probabilities)
    && pilotNumber(audio.inference_ms, 0, 3600000);
  const probability = classifierLive && pilotAudioClasses.includes(audio.label) ? audio.probabilities[audio.label] : null;
  const label = classifierLive ? `${audio.label} · classifier label` : classifier ? 'Classifier unavailable / Unknown'
    : micLive ? ({ quiet: 'Quiet input', normal: 'Sound detected', loud: 'Loud input', distress_like: 'High-band activity' }[audio.label] || 'Sound detected') : 'Awaiting microphone';
  const audioDetail = classifierLive
    ? `${label} · ${probability === null ? 'uncertain' : `${Math.round(probability * 100)}% uncalibrated probability`} · not a health or thermal diagnosis`
    : classifier ? `${label} · not a health or thermal diagnosis`
      : micLive ? `${label} · heuristic, not a diagnosis` : 'Waiting for live sound samples';
  const assessment = sample && sample.assessment;
  const usableAssessment = cameraLive && detector && positionsValid && count > 0
    && pilotAssessmentValid(assessment) && assessment.samples > 0
    && !['NO_DETECTIONS', 'INSUFFICIENT'].includes(assessment.pattern);
  const candidate = usableAssessment ? assessment.candidate : 'UNKNOWN';
  // Audio-model distress flag: real classifier evidence AND chicks detected in view,
  // so room noise with no birds can never trigger the alarm.
  const distress = classifierLive && audio.label === 'Unhealthy' && count > 0;
  const distressTitle = distress
    ? `⚠ UNHEALTHY VOCALIZATION — ${Math.round(audio.probabilities.Unhealthy * 100)}% classifier probability`
    : '—';
  const distressDetail = distress
    ? `Audio model flags Unhealthy · uncalibrated. Possible distress or illness — check the brooder directly. Not an automated diagnosis; no equipment is triggered.`
    : '—';
  return {
    fresh, cameraLive, micLive, detector, detectorModel: detector ? vision.model : null, classifierLive,
    age: Number.isFinite(age) ? Math.max(0, Math.floor(age / 1000)) : null,
    count, candidate, assessmentState: 'UNKNOWN', controlAllowed: false,
    distress, distressTitle, distressDetail,
    assessmentTitle: `${candidate} · unvalidated candidate`,
    assessmentDetail: usableAssessment
      ? `${assessment.pattern} · ${assessment.status} · ${assessment.samples} samples / ${assessment.window_s}s. Model note (unvalidated): ${assessment.reason}`
      : 'UNKNOWN: no fresh, valid chicken-detection assessment. No comfort inference is available.',
    cameraLabel: !cameraLive ? 'Waiting for a valid camera sample' : detector
      ? 'Chicken detections · YOLOv11m · uncalibrated' : 'Motion regions · not a chick count',
    level: micLive ? audio.level_db.toFixed(1) : null,
    peak: micLive && pilotNumber(audio.peak_hz, 0, 96000) ? Math.round(audio.peak_hz) : null,
    label, audioDetail,
    title: cameraLive && micLive ? 'Eyes & ears online' : cameraLive ? 'Camera online · mic waiting' : micLive ? 'Mic online · camera waiting' : 'Waiting for the brooder',
  };
};

window.PILOT_SAMPLE = null;
window.PILOT_AUDIO = [];
let pilotLastKey = '', pilotLastPaint = 0;
window.ingestPilotSample = function (sample) {
  if (!sample || !Number.isFinite(sample.ts) || sample.ts * 1000 > Date.now() || typeof sample.cam_ok !== 'boolean') return;
  // Older packets and retained messages must not overwrite newer observations.
  if (window.PILOT_SAMPLE && sample.ts < window.PILOT_SAMPLE.ts) return;
  window.PILOT_SAMPLE = sample;
  const state = window.pilotViewState(sample);
  const key = `${sample.boot_id || ''}:${sample.seq || ''}:${sample.ts}`;
  if (state.micLive && key !== pilotLastKey) {
    pilotLastKey = key;
    window.PILOT_AUDIO.push(sample.audio.level_db);
    if (window.PILOT_AUDIO.length > 36) window.PILOT_AUDIO.shift();
    const chart = document.getElementById('audio-chart');
    chart.replaceChildren(...window.PILOT_AUDIO.map(level => {
      const bar = document.createElement('span');
      bar.style.height = `${Math.max(4, Math.min(100, (level + 70) / 70 * 100))}%`;
      bar.title = `${level.toFixed(1)} dBFS`;
      return bar;
    }));
  }
  pilotLastPaint = 0;
};

window.renderPilot = function () {
  const now = Date.now();
  if (now - pilotLastPaint < 250) return;
  pilotLastPaint = now;
  const view = window.pilotViewState(window.PILOT_SAMPLE, now);
  const put = (id, text) => { const e = document.getElementById(id); if (e && e.textContent !== String(text)) e.textContent = text; };
  put('subtitle', 'BEHAVIORAL COMFORT LAB');
  put('sbstate', navigator.onLine ? view.title : 'Offline · last observation');
  document.getElementById('sbstate').style.color = 'var(--ink)';
  const dot = document.getElementById('sbdot');
  dot.style.background = navigator.onLine && view.cameraLive && view.micLive ? 'var(--green)' : 'var(--amber)';
  dot.style.boxShadow = '0 0 0 4px #60734b18';
  put('sbsub', !navigator.onLine ? 'Cached observation only. Reconnect for live updates.' : view.fresh ? 'Observation only. Thermal sensing comes next.' : location.protocol === 'https:' ? 'No fresh cloud observations. Check the Pi and cloud bridge.' : 'No fresh telemetry. Check the Pi or connect MQTT.');
  put('sbtemp', view.age === null ? '—' : `${view.age}s`);
  put('signal-count', view.count === null ? '—' : view.count);
  put('signal-level', view.level === null ? '—' : view.level);
  put('signal-camera-state', view.cameraLabel);
  put('signal-mic-state', view.label);
  put('audio-level', view.level === null ? '—' : view.level);
  put('audio-peak', view.peak === null ? 'Peak —' : `Peak ${view.peak} Hz`);
  put('audio-label', view.audioDetail);
  put('audio-window', `${window.PILOT_AUDIO.length} received samples`);
  document.getElementById('audio-chart').style.opacity = view.micLive ? '1' : '.25';
  put('camera-source', view.cameraLive ? 'NoIR camera · receiving' : 'NoIR camera · waiting');
  put('vplabel', view.cameraLive ? `CAMERA POSITIONS / ${view.count === null ? '—' : view.count} ${view.detector ? 'DETECTIONS' : 'REGIONS'}` : 'SPATIAL VIEW / WAITING');
  document.getElementById('viewport').setAttribute('aria-label', view.detector
    ? 'Uncalibrated camera chicken detections; not physical floor coordinates'
    : 'Interactive spatial view of camera-derived motion regions');
  const keyLabel = document.querySelector('.view-key');
  if (keyLabel) keyLabel.textContent = view.detector ? 'Chicken detections' : 'Motion regions';
  const countLabel = document.getElementById('m-count').parentElement.querySelector('.k');
  if (countLabel) countLabel.textContent = view.detector ? 'detections' : 'motion regions';
  put('transport-state', !navigator.onLine ? 'Offline · cached observation' : view.fresh ? (window.__mqttLive ? 'Cloud MQTT · receiving' : window.__pilotSource === 'cloud' ? 'Cloud feed · auto-updating' : 'Pi JSON · receiving') : 'No fresh observations');
  put('sample-state', view.age === null ? 'Waiting for a sample' : `Last sample ${view.age}s ago`);
  const validStats = view.cameraLive && view.count > 1 && typeof sim !== 'undefined' && sim.stats;
  const stats = validStats ? sim.stats : null;
  put('m-nnd', stats ? stats.nnd.toFixed(1) : '—');
  put('m-ent', stats ? stats.entropyN.toFixed(2) : '—');
  put('m-r', stats ? stats.clarkEvans.toFixed(2) : '—');
  put('m-count', view.count === null ? '—' : view.count);
  put('m-cell', stats ? `${Math.round(stats.cellFrac * 100)}%` : '—');
  put('m-set', '—'); put('m-duty', 'Off'); put('m-nh3', '—');
  document.getElementById('m-cellwrap').classList.remove('warn');
  document.getElementById('m-nh3').parentElement.classList.remove('warn');
  document.getElementById('crowdcard').classList.remove('show');
  document.getElementById('distresscard').classList.toggle('show', view.distress === true);
  put('distress-title', view.distressTitle);
  put('distress-sub', view.distressDetail);
  put('whyico', 'i');
  put('whyt', view.assessmentTitle);
  put('whyb', `${view.assessmentDetail} ${view.detector
    ? (view.detectorModel === 'ChickDetector-YOLOv8n'
        ? 'ChickDetector-YOLOv8n detects day-old chicks, not individual identities. Coordinates and spatial metrics are uncalibrated.'
        : 'PoultryVision-YOLOv11m detects chickens, not individual identities. Coordinates and spatial metrics are uncalibrated.')
    : 'Positions come from motion blobs, not a trained chick detector. Calibrate the floor area and scale before interpreting spatial metrics.'} Healthy is an audio class, not evidence of comfort. Health and thermal interpretation are not validated. Heater and fan control are disabled.`);
};

window.setPilotMode = function (live) {
  document.body.dataset.mode = live ? 'live' : 'demo';
  document.getElementById('sbtemp-label').textContent = live ? 'sample age' : 'demo floor';
  document.getElementById('pilot-mode-name').textContent = live ? 'Camera + mic pilot' : 'Simulation · not live';
  document.getElementById('observation-note').textContent = live
    ? 'Camera-derived positions, not live video. Drag to orbit; scroll to zoom.'
    : 'Simulated flock and thermal values. No hardware is controlled by this demo.';
  pilotLastPaint = 0;
};

// Respect reduced motion without stopping incoming telemetry or freshness updates.
window.addEventListener('load', () => {
  window.setPilotMode(true);
  window.renderPilot();
});
