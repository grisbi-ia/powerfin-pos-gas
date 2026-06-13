// Minimal service worker for PWA install
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Pass through — no offline caching for LAN-only app
  event.respondWith(fetch(event.request));
});
