# ThermoHuddle — camera/mic pilot design

## Direction
An observational field instrument, not a generic admin panel. Eggshell paper, graphite-green scene, kiln-orange accents and a small drawn chick mark connect the interface to warmth, care and the brooder. A serif headline provides character; compact monospaced readings keep instrumentation distinct from narrative labels. No downloaded font, icon package, UI framework or build dependency is required.

UI/UX Pro Max informed the real-time monitoring hierarchy, organic palette, accessible controls, visible focus and reduced-motion behavior. Its generic landing-page and glassmorphism suggestions were deliberately not copied into this operational interface.

## Tokens
- Paper: #f5f2e9
- Surface: #fffdf7
- Ink: #2d332a
- Muted text: #6b6d60
- Warm accent: #af542d
- Healthy input: #60734b
- Quiet scene: #292e27
- Edges: #dfd9ca
- Major radius: 20px; instrument controls: 8px
- Headline: Georgia; UI: system/Trebuchet; readings: system monospace

## Hierarchy
1. Observation stage and transport connection.
2. Freshness-aware camera/microphone availability, not a comfort diagnosis.
3. Camera-derived spatial reconstruction, explicitly not live video.
4. Microphone level and a short received-sample chart; no invented waveform.
5. Raw spatial descriptors, clearly marked as uncalibrated.
6. Future floor, air/humidity and ammonia sensors: Not connected.

## Safety and truthfulness
LIVE mode excludes floor/ammonia stubs, heater duty, cross-modal comfort confidence, thermal history, thermal CSV exports and unvalidated welfare alarms. It generates no simulated thermal samples. Samples older than 30 seconds stop appearing live; invalid/future timestamps cannot bypass that rule. Demo scenarios are explicitly simulated and remain separate from arriving MQTT data. A video stream requires separate setup; its button must not imply video is already available.

## Responsive and accessibility
One column on mobile; scene plus instrument panel on desktop. Native buttons, 44px scene controls, visible keyboard focus, zoom allowed, modal focus wrapping/Escape, SVG icons, and reduced animation frame rate for reduced-motion preferences. Four viewport widths are checked: 375, 768, 1024 and 1440px.

## Public Pages updates
GitHub Pages automatically polls the read-only Supabase Storage camera/mic snapshot every 2 seconds while the app is visible. The Pi publishes new observations at its existing pipeline cadence (about 10 seconds). The browser receives no MQTT password or storage-write credential. Only position/count and audio measurements are public; raw audio/video and thermal placeholders are not uploaded.

## Verification
Browser checks live in tests/pilot-checks.js, tests/pilot-ui-checks.js, tests/cloud-feed-checks.js and tests/pilot-regressions.js. Load each script in the app browser and call runPilotChecks() / runPilotUiChecks(). They use local fixtures only and do not publish to MQTT or write telemetry. Browser evidence is recorded in pilot-browser-verification.json. Screenshots document the design, not detector accuracy or hardware safety certification.
