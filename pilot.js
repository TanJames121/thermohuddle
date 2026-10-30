/* Read-only pilot presentation. Thermal payload values are stubs, not measurements. */
window.pilotViewState = function (sample, now = Date.now()) {
  const timestamp = sample && Number.isFinite(sample.ts) ? sample.ts * 1000 : NaN;
  const age = now - timestamp;
  const fresh = Number.isFinite(age) && age >= -5000 && age <= 30000;
  const cameraLive = fresh && sample.cam_ok === true;
  const audio = sample && sample.audio;
  const micLive = fresh && !!audio && Number.isFinite(audio.level_db);
  return {
    fresh, cameraLive, micLive,
    age: Number.isFinite(age) ? Math.max(0, Math.floor(age / 1000)) : null,
    count: cameraLive && Number.isInteger(sample.count) && sample.count >= 0 ? sample.count : null,
    level: micLive ? audio.level_db.toFixed(1) : null,
    peak: micLive && Number.isFinite(audio.peak_hz) ? Math.round(audio.peak_hz) : null,
    label: micLive ? ({ quiet: 'Quiet input', normal: 'Sound detected', loud: 'Loud input', distress_like: 'High-band activity' }[audio.label] || 'Sound detected') : 'Awaiting microphone',
    title: cameraLive && micLive ? 'Eyes & ears online' : cameraLive ? 'Camera online · mic waiting' : micLive ? 'Mic online · camera waiting' : 'Waiting for the brooder',
  };
};

window.PILOT_SAMPLE = null;
window.PILOT_AUDIO = [];
let pilotLastKey = '', pilotLastPaint = 0;
window.ingestPilotSample = function (sample) {
  if (!sample || !Number.isFinite(sample.ts) || !('cam_ok' in sample)) return;
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
  put('sbsub', !navigator.onLine ? 'Cached observation only. Reconnect for live updates.' : view.fresh ? 'Observation only. Thermal sensing comes next.' : 'No fresh telemetry. Check the Pi or connect MQTT.');
  put('sbtemp', view.age === null ? '—' : `${view.age}s`);
  put('signal-count', view.count === null ? '—' : view.count);
  put('signal-level', view.level === null ? '—' : view.level);
  put('signal-camera-state', view.cameraLive ? 'Motion regions · not a chick count' : 'Waiting for a valid camera sample');
  put('signal-mic-state', view.label);
  put('audio-level', view.level === null ? '—' : view.level);
  put('audio-peak', view.peak === null ? 'Peak —' : `Peak ${view.peak} Hz`);
  put('audio-label', view.micLive ? `${view.label} · heuristic, not a diagnosis` : 'Waiting for live sound samples');
  put('audio-window', `${window.PILOT_AUDIO.length} received samples`);
  document.getElementById('audio-chart').style.opacity = view.micLive ? '1' : '.25';
  put('camera-source', view.cameraLive ? 'NoIR camera · receiving' : 'NoIR camera · waiting');
  put('vplabel', view.cameraLive ? `CAMERA POSITIONS / ${view.count === null ? '—' : view.count} REGIONS` : 'SPATIAL VIEW / WAITING');
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
  put('whyico', 'i');
  put('whyt', 'Observe first. Calibrate next.');
  put('whyb', 'Positions come from motion blobs, not a trained chick detector. Calibrate the floor area and scale before interpreting spatial metrics. Comfort classification is not validated.');
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
