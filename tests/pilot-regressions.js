/* Regression fixtures only. These tests never publish or upload telemetry. */
window.checkPilotFrameWork = function () {
  const saved = sim.stats;
  updateSim();
  if (sim.stats !== saved) throw new Error('LIVE frames recomputed unchanged spatial statistics');
  return true;
};
window.checkPilotModeTransition = function () {
  const saved = { ...HIST };
  try {
    HIST.floorT = [32.5, 32.5]; HIST.setpoint = [34, 34]; HIST.state = ['COMFY', 'COMFY'];
    setScenario('COMFY');
    document.querySelector('[data-p="analytics"]').click();
    if (document.getElementById('an-avg').textContent === '—') throw new Error('Demo fixture did not populate analytics');
    setScenario('LIVE');
    if (!document.getElementById('csvbtn').disabled || document.getElementById('an-avg').textContent !== '—')
      throw new Error('Demo thermal analytics leaked across the LIVE transition');
    return true;
  } finally {
    Object.assign(HIST, saved); setScenario('LIVE');
    document.querySelector('[data-p="stats"]').click();
  }
};

window.checkPilotHistoryScrub = function () {
  const saved = HIST_REMOTE.series;
  try {
    HIST_REMOTE.series = [0, 1].map(i => ({ ts: new Date(Date.now() + i * 1000).toISOString(),
      floor_avg: 32.5, setpoint_avg: 34, nh3_avg: 6, state: 'COMFY', samples: 1 }));
    setScenario('COMFY');
    document.querySelector('[data-p="hist"]').click();
    renderHist();
    setScenario('LIVE'); renderHist();
    if (HIST_LAYOUT !== null) throw new Error('Live pilot retained demo thermal scrub layout');
    const cv = document.getElementById('histcanvas'), rect = cv.getBoundingClientRect();
    cv.dispatchEvent(new PointerEvent('pointermove', { clientX: rect.left + rect.width / 2 }));
    cv.dispatchEvent(new PointerEvent('pointerleave'));
    if (!document.getElementById('histread').textContent.includes('no thermal samples'))
      throw new Error('Live history interaction replaced the no-thermal-data message');
    return true;
  } finally {
    HIST_REMOTE.series = saved; setScenario('LIVE');
    document.querySelector('[data-p="stats"]').click();
  }
};

window.checkPilotFutureRecovery = function () {
  const saved = PILOT_SAMPLE;
  try {
    PILOT_SAMPLE = null;
    const now = Date.now() / 1000;
    const sample = { ts: now, count: 0, chicks: [], cam_ok: false, audio: null };
    ingestPilotSample({ ...sample, ts: now + 3600 });
    if (PILOT_SAMPLE !== null) throw new Error('Future packet poisoned the telemetry ordering watermark');
    ingestPilotSample(sample);
    if (!PILOT_SAMPLE || PILOT_SAMPLE.ts !== now) throw new Error('Valid telemetry did not recover after future packet');
    return true;
  } finally { PILOT_SAMPLE = saved; pilotLastPaint = 0; renderPilot(); }
};
