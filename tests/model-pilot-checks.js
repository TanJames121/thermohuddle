/* Node-only, offline fixtures. Run: node tests/model-pilot-checks.js */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const elements = new Map();
function element() {
  return { textContent: '', style: {}, dataset: {}, disabled: false,
    classList: { _s: new Set(), add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      toggle(c, v) { if (v === undefined) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); } else { v ? this._s.add(c) : this._s.delete(c); } return this._s.has(c); },
      contains(c) { return this._s.has(c); } },
    parentElement: { classList: { remove() {} }, querySelector: () => element() },
    replaceChildren(...children) { this.children = children; },
    setAttribute(name, value) { this[name] = value; },
    querySelector() { return element(); }, querySelectorAll() { return []; } };
}
const controls = [element(), element()];
const context = { console, Date, navigator: { onLine: true }, location: { protocol: 'https:' },
  document: { body: element(), getElementById(id) {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  }, createElement: element, querySelectorAll: () => controls, querySelector: () => element() },
  addEventListener() {} };
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'pilot.js'), 'utf8'), context);
const now = 1700000000000;
function sample() {
  return { ts: now / 1000, seq: 1, boot_id: '012345abcdef', count: 2,
    chicks: [[-1, 0], [1, 0]], cam_ok: true,
    vision: { model: 'PoultryVision-YOLOv11m', inference_ms: 123.5, confidence_min: 0.25,
      coordinate_system: 'uncalibrated_camera', calibrated: false },
    audio: { level_db: -35, peak_hz: 3200, distress_ratio: 0.2, label: 'Healthy',
      probabilities: { Healthy: 0.7, Noise: 0.2, Unhealthy: 0.1 },
      model: 'chicken-vocalization-classifier', available: true, inference_ms: 12.5, ts: now / 1000 },
    assessment: { state: 'UNKNOWN', candidate: 'POSSIBLE_COLD', pattern: 'CLUSTERED',
      status: 'uncalibrated', reason: 'Scale needs calibration.', control_allowed: false,
      window_s: 30, samples: 3, audio_support: 'healthy_vocalization' } };
}
let passed = 0;
function test(name, fn) { fn(); passed++; console.log(`ok ${passed} - ${name}`); }
const view = input => context.pilotViewState(input, now);
test('model-aware chicken detections, not motion regions', () => {
  const state = view(sample());
  assert.equal(state.detector, true);
  assert.match(state.cameraLabel, /Chicken detections/);
  assert.doesNotMatch(state.cameraLabel, /motion/i);
  assert.equal(state.count, 2);
});
test('candidate stays explicitly unvalidated, never a thermal diagnosis', () => {
  const state = view(sample());
  assert.equal(state.candidate, 'POSSIBLE_COLD');
  assert.equal(state.assessmentState, 'UNKNOWN');
  assert.match(state.assessmentTitle, /unvalidated/i);
  assert.equal(state.controlAllowed, false);
});
test('classifier label and probability are not thermal comfort', () => {
  const state = view(sample());
  assert.match(state.label, /Healthy/);
  assert.match(state.audioDetail, /70%/);
  assert.match(state.audioDetail, /uncalibrated/);
  assert.match(state.audioDetail, /not.*diagnosis/);
  assert.doesNotMatch(state.label, /comfortable|comfy/i);
});
test('Noise, Unhealthy, Unknown remain classifier labels', () => {
  for (const label of ['Noise', 'Unhealthy', 'Unknown']) {
    const input = sample(); input.audio.label = label;
    assert.match(view(input).label, new RegExp(label));
    assert.match(view(input).audioDetail, /not.*diagnosis/);
  }
});
test('no chicks, stale, failed, malformed or legacy camera means UNKNOWN', () => {
  for (const change of [
    { count: 0, chicks: [] }, { ts: now / 1000 - 30 }, { cam_ok: false },
    { chicks: [] }, { chicks: [[NaN, 0], [1, 0]] }, { vision: null },
    { vision: { ...sample().vision, model: 'motion' } },
  ]) {
    const state = view({ ...sample(), ...change });
    assert.equal(state.candidate, 'UNKNOWN');
    assert.equal(state.assessmentState, 'UNKNOWN');
    assert.equal(state.controlAllowed, false);
  }
  assert.equal(view(null).candidate, 'UNKNOWN');
});
test('unavailable or stale audio cannot reuse a Healthy label', () => {
  for (const change of [{ available: false }, { ts: now / 1000 - 30 }, { ts: now / 1000 + 10 },
    { probabilities: { Healthy: 1.1, Noise: -0.2, Unhealthy: 0.1 } },
    { probabilities: { Healthy: 0.7, Noise: 0.2, Unhealthy: 0.1, secret: 0 } }]) {
    const input = sample(); Object.assign(input.audio, change);
    assert.equal(view(input).classifierLive, false);
    assert.doesNotMatch(view(input).label, /Healthy/);
  }
});
test('missing assessment never inferred from Healthy or legacy thermal fields', () => {
  const input = sample(); delete input.assessment;
  Object.assign(input, { floorT: 32.5, state: 'COMFY', duty: 100, fan: true });
  assert.equal(view(input).candidate, 'UNKNOWN');
  assert.equal(view(input).controlAllowed, false);
});
test('bad enum or control authorization cannot become a candidate', () => {
  for (const change of [{ candidate: 'COMFY' }, { control_allowed: true }, { status: 'validated' },
    { pattern: 'HOT' }, { state: 'COLD' }, { samples: -1 }]) {
    const input = sample(); Object.assign(input.assessment, change);
    assert.equal(view(input).candidate, 'UNKNOWN');
    assert.equal(view(input).controlAllowed, false);
  }
});
test('legacy motion/audio wording and empty detections remain compatible', () => {
  const input = { ts: now / 1000, count: 0, chicks: [], cam_ok: true,
    audio: { level_db: -35, peak_hz: 400, label: 'normal' } };
  const state = view(input);
  assert.equal(state.count, 0);
  assert.match(state.cameraLabel, /Motion regions/);
  assert.equal(state.label, 'Sound detected');
  assert.match(state.audioDetail, /heuristic/);
});
test('malformed audio never crashes observation rendering', () => {
  for (const audio of [null, false, 4, 'text', [], {}]) {
    const state = view({ ...sample(), audio });
    assert.equal(state.micLive, false);
    assert.equal(state.classifierLive, false);
  }
});
test('near-future packets cannot poison the ingestion watermark', () => {
  context.PILOT_SAMPLE = null;
  const input = sample(); input.ts = Date.now() / 1000 + 4;
  context.ingestPilotSample(input);
  assert.equal(context.PILOT_SAMPLE, null);
  input.ts = Date.now() / 1000; input.audio = null;
  context.ingestPilotSample(input);
  assert.equal(context.PILOT_SAMPLE, input);
});
test('render uses existing DOM and suppresses all live thermal controls', () => {
  const input = sample(); input.ts = Date.now() / 1000; input.audio.ts = input.ts;
  context.PILOT_SAMPLE = input;
  context.setPilotMode(true);
  context.renderPilot();
  const text = id => elements.get(id).textContent;
  assert.match(text('signal-camera-state'), /Chicken detections/);
  assert.match(text('vplabel'), /DETECTIONS/);
  assert.match(text('audio-label'), /Healthy.*70%.*uncalibrated/);
  assert.match(text('whyt'), /POSSIBLE_COLD.*unvalidated/);
  assert.match(text('whyb'), /Heater and fan control.*disabled/);
  assert.equal(text('m-set'), '—');
  assert.equal(text('m-duty'), 'Off');
  assert.match(elements.get('viewport')['aria-label'], /chicken detections/);
});
test('Unhealthy classifier label raises an unvalidated distress warning', () => {
  const input = sample();
  input.audio.label = 'Unhealthy';
  input.audio.probabilities = { Healthy: 0.1, Noise: 0.1, Unhealthy: 0.8 };
  const state = view(input);
  assert.equal(state.distress, true);
  assert.match(state.distressTitle, /UNHEALTHY/);
  assert.match(state.distressTitle, /80%/);
  assert.match(state.distressDetail, /Not an automated diagnosis/);
});
test('no chicks in view means room noise can never trigger the distress alarm', () => {
  const input = sample(); input.count = 0; input.chicks = [];
  input.audio.label = 'Unhealthy';
  input.audio.probabilities = { Healthy: 0.001, Noise: 0.0001, Unhealthy: 0.9989 };
  const state = view(input);
  assert.equal(state.distress, false);
  assert.equal(state.distressTitle, '—');
});
test('distress warning needs live classifier evidence, never Healthy/Unknown/stale', () => {
  for (const label of ['Healthy', 'Unknown']) {
    const input = sample(); input.audio.label = label;
    assert.equal(view(input).distress, false);
  }
  const stale = sample(); stale.audio.ts = now / 1000 - 30;
  assert.equal(view(stale).distress, false);
  const off = sample(); off.audio.available = false;
  assert.equal(view(off).distress, false);
});
test('render toggles the distress card only from live classifier evidence', () => {
  const input = sample(); input.ts = Date.now() / 1000; input.audio.ts = input.ts;
  context.PILOT_SAMPLE = input;
  context.renderPilot();
  assert.equal(elements.get('distresscard').classList.contains('show'), false);
  input.audio.label = 'Unhealthy';
  input.audio.probabilities = { Healthy: 0.05, Noise: 0.05, Unhealthy: 0.9 };
  context.ingestPilotSample(input);
  context.renderPilot();
  assert.equal(elements.get('distresscard').classList.contains('show'), true);
  assert.match(elements.get('distress-title').textContent, /UNHEALTHY.*90%/);
  // Restore the Healthy baseline for the freshness suite that runs after these tests.
  input.audio.label = 'Healthy';
  input.audio.probabilities = { Healthy: 0.7, Noise: 0.2, Unhealthy: 0.1 };
  context.ingestPilotSample(input);
  context.renderPilot();
  assert.equal(elements.get('distresscard').classList.contains('show'), false);
});

test('valid ArUco mapping and live ESP32 sensors surface without breaking pilot safety invariants', () => {
  const input = sample();
  input.vision.aruco_mapped = true;
  input.vision.aruco_markers = [0, 1, 2, 3];
  input.sensors = {
    available: true,
    status: 'ok',
    ts: now / 1000,
    ambient_temp_c: 31.4,
    humidity_pct: 62.5,
    mq137_raw: 1200,
    mq137_volts: 0.375,
    nh3_rel_ppm: 3.15,
    mq137_do_alert: false,
    fan_on: true,
  };
  const v = view(input);
  assert.equal(v.arucoMapped, true);
  assert.deepEqual(v.arucoMarkers, [0, 1, 2, 3]);
  assert.equal(v.sensorsLive, true);
  assert.equal(v.ambientTempC, 31.4);
  assert.equal(v.humidityPct, 62.5);
  assert.equal(v.nh3Ppm, 3.15);
  assert.equal(v.fanOn, true);

  input.ts = Date.now() / 1000;
  input.audio.ts = input.ts;
  input.sensors.ts = input.ts;
  context.PILOT_SAMPLE = null;
  context.ingestPilotSample(input);
  context.renderPilot();
  const text = id => elements.get(id).textContent;
  assert.equal(text('m-set'), '—');
  assert.equal(text('m-duty'), 'Off');
  assert.equal(text('m-nh3'), '—');
  assert.equal(text('esp32-status-badge'), 'ESP32 · LIVE');
  assert.equal(text('esp32-temp-val'), '31.4 °C');
  assert.equal(text('esp32-hum-val'), '62.5 %');
  assert.equal(text('esp32-nh3-val'), '3.15 ppm');
  assert.equal(text('esp32-fan-val'), 'ON');
  assert.equal(text('sensor-aruco-state'), 'Mapped (4/4 IDs)');
  assert.equal(text('aruco-hud-text'), 'ARUCO 4×4 · BOX MAPPED (4/4 CORNERS)');
  assert.equal(text('aruco-status-badge'), 'HOMOGRAPHY LOCKED');
  for (const id of [0, 1, 2, 3]) {
    assert.equal(elements.get(`aruco-tag-${id}`).classList.contains('live'), true);
  }
  input.chicks = [[0, 0], [3, 4], [2, 1], [-1, 2]];
  input.count = 4;
  context.PILOT_SAMPLE = null;
  context.ingestPilotSample(input);
  context.renderPilot();
  assert.equal(text('clump-state-val'), 'CLUMPING');
  assert.equal(text('clump-pairs-val'), '6 (4/4)');
});

test('standalone ESP32 MQTT payload updates telemetry cards safely', () => {
  context.PILOT_SAMPLE = null;
  context.ingestEsp32Sensors({
    status: 'degraded',
    ambient_temp_c: null,
    humidity_pct: null,
    mq137_raw: 910,
    mq137_volts: 0.412,
    nh3_rel_ppm: 1.85,
    mq137_do_alert: false,
    fan_on: false,
  }, Date.now());
  const text = id => elements.get(id).textContent;
  assert.equal(text('esp32-status-badge'), 'ESP32 · DEGRADED');
  assert.equal(text('esp32-temp-val'), '—');
  assert.equal(text('esp32-nh3-val'), '1.85 ppm');
  assert.equal(text('esp32-fan-val'), 'OFF');
  assert.equal(context.pilotViewState(context.PILOT_SAMPLE, Date.now()).cameraLive, false);
});
// Execute the existing browser-independent freshness suite in the same VM.
vm.runInContext(fs.readFileSync(path.join(__dirname, 'pilot-checks.js'), 'utf8'), context);
console.log('existing pilot checks:', context.runPilotChecks());
console.log(`model pilot checks: ${passed} passed`);
