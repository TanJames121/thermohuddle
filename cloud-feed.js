/* Public read-only camera/mic snapshots. All write credentials stay on the Pi. */
window.PILOT_CLOUD_URL = 'https://thoissoyiupjrrsqmika.supabase.co/storage/v1/object/public/frames/telemetry/latest.json';
window.cloudShouldPoll = (hidden, live, mqttFresh) => !hidden && live && !mqttFresh;
window.cloudObservationOf = sample => ({ ts: sample.ts, seq: sample.seq, boot_id: sample.boot_id,
  count: sample.count, chicks: sample.chicks, cam_ok: sample.cam_ok, audio: sample.audio,
  vision: sample.vision, assessment: sample.assessment });
let cloudInFlight = false;
if (location.protocol === 'https:') {
  document.getElementById('connchip').textContent = 'Connecting to cloud';
  document.getElementById('connchip').title = 'Automatic read-only cloud observations';
}

window.pollCloudObservation = async function () {
  const mqttFresh = window.__mqttLive && window.pilotViewState(window.PILOT_SAMPLE).fresh;
  if (cloudInFlight || !window.cloudShouldPoll(document.hidden, sim.forced === 'LIVE', mqttFresh)) return;
  cloudInFlight = true;
  const chip = document.getElementById('connchip');
  try {
    const response = await fetch(window.PILOT_CLOUD_URL + '?t=' + Date.now(), {
      cache: 'no-store', credentials: 'omit', signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) throw new Error('Cloud observation unavailable');
    const text = await response.text();
    if (text.length > 262144) throw new Error('Observation too large');
    const sample = JSON.parse(text);
    if (!sample || !Number.isFinite(sample.ts) || typeof sample.cam_ok !== 'boolean'
      || !Number.isInteger(sample.count) || !Array.isArray(sample.chicks)
      || sample.count !== sample.chicks.length || sample.count > 4096
      || !sample.chicks.every(p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite))
      || !window.pilotViewState(sample).fresh) throw new Error('No valid fresh cloud observation');
    // The Pi allowlists this payload; never ingest its stub thermal/control fields.
    const observation = window.cloudObservationOf(sample);
    ingestTrackingJSON(JSON.stringify(observation));
    window.__pilotSource = 'cloud';
    chip.textContent = 'Auto updates · 2s';
    chip.className = 'on';
    chip.title = 'Read-only cloud feed. Click to refresh now.';
  } catch (_) {
    if (!window.__mqttLive) {
      chip.textContent = 'Awaiting cloud data';
      chip.className = '';
      chip.title = 'No fresh cloud sample. The Pi and cloud bridge must be running.';
    }
  } finally {
    cloudInFlight = false;
    pilotLastPaint = 0;
    if (sim.forced === 'LIVE') window.renderPilot();
  }
};

function resumeCloudObservation() {
  if (location.protocol === 'https:') window.pollCloudObservation();
}
window.addEventListener('load', resumeCloudObservation);
document.addEventListener('visibilitychange', resumeCloudObservation);
window.addEventListener('online', resumeCloudObservation);
