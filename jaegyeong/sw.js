// Offline support for 차곡. Network first: when online every request goes to the network as before
// (so new deploys show immediately) and a copy is kept; when offline the kept copy is served.
const CACHE = 'chagok-offline-v1';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('chagok-offline-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return;
  event.respondWith(fetch(request).then(response => {
    if (response.ok && response.type === 'basic') {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(request, copy));
    }
    return response;
  }).catch(() => caches.match(request, {ignoreSearch: true}).then(hit => hit ||
    (request.mode === 'navigate' ? caches.match(new URL('./', self.location).href) : undefined)
  ).then(hit => hit || Response.error())));
});
