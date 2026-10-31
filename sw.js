/* ThermoHuddle service worker — offline model-aware observation-only shell. */
const CACHE = 'thermohuddle-v18';
const ASSETS = [
  './index.html',
  './brooder.css',
  './pilot.js',
  './cloud-feed.js',
  './p5.min.js',
  './mqtt.min.js',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './favicon-32.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;           // let anything remote pass through

  // LIVE tracking data: always prefer the network, fall back to last known
  if (url.pathname.endsWith('supabase.js')) {
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          const cp = r.clone();
          caches.open(CACHE).then((c) => c.put(e.request, cp));
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  if (url.pathname.endsWith('tracking_latest.json')) {
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          const cp = r.clone();
          caches.open(CACHE).then((c) => c.put(e.request, cp));
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // app shell: cache-first; offline + cache-miss on a navigation → serve the
  // cached app shell so the app still opens with the server completely gone
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then(
      (hit) =>
        hit ||
        fetch(e.request).then((r) => {
          const cp = r.clone();
          caches.open(CACHE).then((c) => c.put(e.request, cp));
          return r;
        })
    ).catch(() => {
      if (e.request.mode === 'navigate') {
        return caches.match('./index.html').then(
          (shell) => shell || Response.error()
        );
      }
      return Response.error();
    })
  );
});
