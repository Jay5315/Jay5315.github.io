// The complete app shell is committed during installation, including on a first visit.
const CORE_CACHE = 'chagok-offline-v2';
const MEDIA_CACHE = 'chagok-offline-media-v2';
const SCOPE = new URL('./', self.location.href);
const CORE_URLS = ['./', 'index.html', 'assets/app.css', 'assets/app.js',
  'assets/bank-data.js', 'assets/offline.js', 'assets/icon.svg'].map(path => new URL(path, SCOPE).href);
const CORE_PATHS = new Set(CORE_URLS.map(url => new URL(url).pathname));
const MEDIA_LIMIT = 40;
const MEDIA_MAX_BYTES = 5 * 1024 * 1024;

self.addEventListener('install', event => event.waitUntil((async () => {
  // A failed install never activates a worker with an incomplete first-use cache.
  const responses = await Promise.all(CORE_URLS.map(async url => {
    const response = await fetch(new Request(url, {cache: 'reload', credentials: 'same-origin'}));
    if (!response.ok || response.status !== 200) throw new Error('App shell download failed');
    return response;
  }));
  const cache = await caches.open(CORE_CACHE);
  await Promise.all(CORE_URLS.map((url, i) => cache.put(url, responses[i])));
  await self.skipWaiting();
})()));

self.addEventListener('activate', event => event.waitUntil((async () => {
  const keep = new Set([CORE_CACHE, MEDIA_CACHE]);
  await self.clients.claim();
  await Promise.all((await caches.keys()).filter(key => key.startsWith('chagok-offline-') && !keep.has(key))
    .map(key => caches.delete(key)));
})()));

function mediaRequest(url) {
  const relative = url.pathname.slice(SCOPE.pathname.length);
  return /^images\/[^/]+\.(webp|png|jpe?g)$/i.test(relative) || /^sources\/.+\.pdf$/i.test(relative);
}

async function saveResponse(request, response, core) {
  if (core) {
    const url = new URL(request.url);
    url.search = '';
    await (await caches.open(CORE_CACHE)).put(url.href, response);
    return;
  }
  // Keep only recent small source files, rather than filling storage with the PDF archive.
  if (Number(response.headers.get('content-length')) > MEDIA_MAX_BYTES ||
      (await response.clone().blob()).size > MEDIA_MAX_BYTES) return;
  const cache = await caches.open(MEDIA_CACHE);
  await cache.delete(request, {ignoreSearch: true});
  await cache.put(request, response);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - MEDIA_LIMIT)).map(key => cache.delete(key)));
}

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || request.headers.has('range') || url.origin !== SCOPE.origin ||
      !url.pathname.startsWith(SCOPE.pathname)) return;
  const core = CORE_PATHS.has(url.pathname);
  if (!core && !mediaRequest(url)) return;
  // Attach cache writes to the fetch event so the worker stays alive until they finish.
  let finishWrite;
  const writeDone = new Promise(resolve => { finishWrite = resolve; });
  event.waitUntil(writeDone);
  event.respondWith((async () => {
    let networkResponse;
    try {
      networkResponse = await fetch(request);
      if (networkResponse.ok) {
        if (networkResponse.status === 200 && networkResponse.type === 'basic') {
          saveResponse(request, networkResponse.clone(), core).catch(() => {}).finally(finishWrite);
        } else finishWrite();
        return networkResponse;
      }
    } catch (_) { /* A network error or bad HTTP response can use a saved copy. */ }
    finishWrite();
    const cache = await caches.open(core ? CORE_CACHE : MEDIA_CACHE);
    const saved = await cache.match(request, {ignoreSearch: true});
    return saved || networkResponse || Response.error();
  })());
});

self.addEventListener('message', event => {
  if (event.data?.type !== 'CHAGOK_OFFLINE_STATUS' || !event.ports[0]) return;
  event.waitUntil((async () => {
    const cache = await caches.open(CORE_CACHE);
    const missing = (await Promise.all(CORE_URLS.map(async url => await cache.match(url) ? null : url))).filter(Boolean);
    event.ports[0].postMessage({type: 'CHAGOK_OFFLINE_STATUS', ready: missing.length === 0,
      cacheVersion: CORE_CACHE, missing, mediaLimit: MEDIA_LIMIT, mediaMaxBytes: MEDIA_MAX_BYTES});
  })());
});
