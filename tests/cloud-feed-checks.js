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
  return { passed: 7, message: 'Visible-tab automatic refresh, MQTT priority and public URL checks passed' };
};
