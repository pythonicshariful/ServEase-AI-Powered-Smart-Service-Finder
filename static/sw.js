// ServEase Service Worker – Cache-first for static assets
const CACHE_NAME = 'servease-v1';
const STATIC_ASSETS = [
  '/',
  '/static/style.css',
  '/static/profile.css',
  '/static/manifest.json',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip SSE streams, POST requests, and non-GET
  if (event.request.method !== 'GET') return;
  if (url.pathname.startsWith('/notifications/stream')) return;

  // Cache-first for static assets; network-first for pages
  if (url.pathname.startsWith('/static/') || url.hostname !== location.hostname) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
  } else {
    // Network-first for HTML pages
    event.respondWith(
      fetch(event.request)
        .then(res => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
  }
});
