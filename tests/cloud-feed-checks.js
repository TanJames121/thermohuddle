/* Browser-only checks. No telemetry is sent by these tests. */
window.runCloudFeedChecks = function () {
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  check(typeof window.cloudShouldPoll === 'function', 'Automatic cloud feed scheduler is missing');
  check(!cloudShouldPoll(true, true, false), 'Hidden app must not poll');
  check(!cloudShouldPoll(false, false, false), 'Demo mode must not poll');
  check(!cloudShouldPoll(false, true, true), 'Fresh MQTT takes priority over polling');
  check(cloudShouldPoll(false, true, false), 'Visible LIVE app must auto-refresh without MQTT');
  const url = new URL(window.PILOT_CLOUD_URL);
  check(url.protocol === 'https:' && !url.username && !url.password, 'Cloud feed must be HTTPS without embedded credentials');
  check(!url.searchParams.has('apikey') && !url.searchParams.has('token'), 'Public snapshot must not require secret query parameters');
  check(typeof window.cloudObservationOf === 'function', 'Cloud model forwarding adapter is missing');
  const vision = { model: 'PoultryVision-YOLOv11m' };
  const assessment = { state: 'UNKNOWN', control_allowed: false };
  const observation = window.cloudObservationOf({ ts: 1, cam_ok: true, count: 0, chicks: [],
    vision, assessment, audio: { label: 'Unknown' }, floorT: 32.5, duty: 100, secret: 'fixture-not-a-key' });
  check(observation.vision === vision && observation.assessment === assessment,
    'Cloud observations must preserve model metadata and assessment');
  check(!('floorT' in observation) && !('duty' in observation) && !('secret' in observation),
    'Cloud forwarding must exclude thermal stubs, controls and unknown fields');
  return { passed: 10, message: 'Cloud scheduling, public URL and trained-model forwarding checks passed' };
};
