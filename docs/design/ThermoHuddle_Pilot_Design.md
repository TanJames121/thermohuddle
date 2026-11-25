# ThermoHuddle — camera/mic pilot design (v23 Bento Glassmorphism)

## Direction
Obsidian Bento Glassmorphic Control Room paired with a Warm Architectural Light theme. Semi-transparent frosted glass containers (`backdrop-filter: blur(18px)`), ambient thermal mesh glows, crisp 1px edge highlights, and tabular monospaced instrumentation frame the 3D WebGL brooder reconstruction and live telemetry strips without requiring any CSS framework or build step. Optional `Plus Jakarta Sans` + `JetBrains Mono` fonts load non-blockingly over HTTPS with clean offline system fallbacks.

## Tokens
### Dark Theme (Default — Obsidian Thermal Lab)
- Canvas: `#0b0f17` with warm kiln-amber, emerald, and cyan ambient radial glows
- Surface (glass): `rgba(20, 28, 44, 0.78)` | Inner tile: `rgba(13, 19, 31, 0.78)`
- Ink: `#f1f5f9` | Muted text: `#94a3b8`
- Thermal Accent: `#f97316` | Live Healthy: `#22c55e` | Caution: `#f59e0b` | Alert: `#ef4444`
- Glass edge: `rgba(148, 163, 184, 0.18)`
- Major radius: `22px` | Inner cards: `12px–14px` | Buttons: `11px–12px`

### Light Theme (Warm Architectural Glass)
- Canvas: `#f3f5f8` | Surface: `rgba(255, 255, 255, 0.88)` | Inner tile: `#f8fafc`
- Ink: `#0f172a` | Muted text: `#475569` | Thermal Accent: `#ea580c` | Healthy: `#15803d`

## Hierarchy
1. Floating Glass Command Bar (`#topbar`): Identity, RPi 5 edge badge, quick Scenario Command Palette trigger, and live MQTT/Cloud transport pill.
2. Compact Hero & Live State HUD (`#intro`, `#statebanner`): Freshness-aware camera/microphone availability, never an unvalidated comfort diagnosis.
3. Left Bento Column (`#observation`): Interactive 3D WebGL spatial reconstruction (`p5.js`), ArUco 4x4 homography HUD, and 36-sample acoustic bar chart.
4. Right Bento Sheet (`#sheet`): Segmented 5-tab navigation (`Overview`, `History`, `Analytics`, `Field log`, `Warnings`) housing live KPI tiles, spatial dispersion metrics, ArUco 4-corner pills, flock clumping strip, ESP32 sensor grid, and hardware bus status.

## Safety and truthfulness
LIVE mode excludes floor/ammonia stubs, heater duty, cross-modal comfort confidence, thermal history, thermal CSV exports and unvalidated welfare alarms. It generates no simulated thermal samples. Samples older than 30 seconds stop appearing live; invalid/future timestamps cannot bypass that rule. Demo scenarios are explicitly simulated and remain separate from arriving MQTT data. A video stream requires separate setup; its button must not imply video is already available.

## Responsive and accessibility
Two-column Bento grid on desktop (`1.42fr : 1fr`) collapsing cleanly to a single column on mobile (`<= 760px`). Native buttons, 44px scene/topbar controls, visible keyboard focus, zoom allowed, modal focus wrapping/Escape, inline SVG sprite icons (no emoji UI icons), tabular numerals, and reduced animation frame rate for reduced-motion preferences. Four viewport widths are verified: `375`, `768`, `1024`, and `1440px`.

## Verification
Browser checks live in `tests/pilot-checks.js`, `tests/pilot-ui-checks.js`, `tests/cloud-feed-checks.js` and `tests/pilot-regressions.js`. Offline checks run in Node via `tests/model-pilot-checks.js`. Browser evidence is recorded in `docs/design/pilot-browser-verification.json`.
