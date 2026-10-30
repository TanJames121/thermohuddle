/* Run after pilot-checks.js in a real app browser. Fixtures are test-only. */
window.runPilotUiChecks = function () {
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  check(sim.forced === 'LIVE', 'UI checks require LIVE pilot mode');
  const savedSeries = HIST_REMOTE.series;
  try {
    HIST_REMOTE.series = [{ ts: '2026-01-01', floor_avg: 32.5, setpoint_avg: 34, state: 'COMFY' },
      { ts: '2026-01-02', floor_avg: 32.5, setpoint_avg: 34, state: 'COMFY' }];
    check(histSeries().floorT.length === 0, 'Pilot must not display unvalidated thermal history');
  } finally { HIST_REMOTE.series = savedSeries; }
  renderAnalytics();
  check(document.getElementById('csvbtn').disabled, 'Pilot must not export placeholder temperatures');
  check(document.getElementById('an-avg').textContent === '—', 'Pilot thermal analytics must be unavailable');
  const before = HIST.floorT.length;
  for (let i = 0; i < 120; i++) updateSim();
  check(HIST.floorT.length === before, 'Live observation must not generate thermal samples');
  const controls = [...document.querySelectorAll('.control-metric, .legacy-controls')];
  check(controls.every(e => getComputedStyle(e).display === 'none'), 'Placeholder controls must stay hidden');
  const savedDots = liveDots;
  try {
    window.setChickPositions([[60, 0], [-15, 5]], true);
    check(liveDots[0].x === 60 && liveDots[1].x === -15, 'Centered Pi coordinates must not be shifted by corner-format detection');
  } finally { liveDots = savedDots; }
  check(document.querySelectorAll('#p5canvas').length === 1, 'Only one scene canvas may have p5canvas ID');
  check(document.documentElement.scrollWidth <= innerWidth, 'Dashboard must not overflow horizontally');
  return { passed: 9, message: 'Live-only history, export, analytics, controls, canvas and layout checks passed' };
};
