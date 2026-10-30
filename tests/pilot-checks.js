/* Run in the app browser: evaluate this file, then runPilotChecks(). */
window.runPilotChecks = function () {
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  check(typeof window.pilotViewState === 'function', 'Camera/mic-only view state is missing');
  const now = 1000000;
  const sample = { ts: now / 1000, cam_ok: true, count: 0,
    audio: { level_db: -35, peak_hz: 400, label: 'normal' } };
  const live = window.pilotViewState(sample, now);
  check(live.cameraLive && live.micLive, 'Fresh camera and mic must be live');
  check(live.count === 0, 'Zero detections must not become a missing value');
  check(live.level === '-35.0', 'Mic level must come from the sample');
  const stale = window.pilotViewState(sample, now + 31000);
  check(!stale.cameraLive && !stale.micLive, 'Old telemetry must not appear live');
  check(stale.count === null && stale.level === null, 'Stale values must be unavailable');
  const failed = window.pilotViewState({ ...sample, cam_ok: false, audio: null }, now);
  check(!failed.cameraLive && !failed.micLive, 'Failed camera/mic must not appear connected');
  check(failed.count === null, 'Camera failure must hide the last detection count');
  const missing = window.pilotViewState(null, now);
  check(!missing.cameraLive && !missing.micLive, 'No sample must show waiting state');
  const future = window.pilotViewState({ ...sample, ts: 999999 }, now);
  check(!future.fresh, 'Future timestamps must not bypass stale detection');
  const invalid = window.pilotViewState({ ...sample, audio: { level_db: null } }, now);
  check(!invalid.micLive, 'Null audio is not a zero-decibel measurement');
  return { passed: 11, message: 'Fresh, stale, failed, empty and invalid-input states passed' };
};
