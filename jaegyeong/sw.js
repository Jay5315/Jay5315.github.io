// Each generated build has an independent complete offline snapshot.
const SCOPE = new URL('./', self.location.href);
const BUILD = new URL(self.location.href).searchParams.get('build') || 'legacy';
const CORE_CACHE = 'chagok-offline-v3-' + BUILD;
const MEDIA_CACHE = 'chagok-offline-media-v2';
const MANIFEST_URL = new URL('assets/bank-manifest.json', SCOPE).href;
const RUNTIME = ['index.html', 'assets/app.css', 'assets/app.js', 'assets/data-loader.js',
  'assets/offline.js', 'assets/icon.svg'];
const MEDIA_LIMIT = 40, MEDIA_MAX_BYTES = 5 * 1024 * 1024;
let planPromise;
const absolute = path => new URL(path, SCOPE).href;
const hex = bytes => [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, '0')).join('');
function validate(m) {
  if (m.format !== 1 || !/^[a-f0-9]{20}$/.test(m.build_id) || (BUILD !== 'legacy' && BUILD !== m.build_id)) throw Error('Build mismatch');
  if (!RUNTIME.every(path => /^[a-f0-9]{64}$/.test(m.runtime?.[path]?.sha256)) || Object.keys(m.runtime).length !== RUNTIME.length) throw Error('Runtime manifest mismatch');
  for (const spec of [m.core, ...['finance', 'tax', 'cost'].map(k => m.subjects?.[k])]) {
    if (!/^assets\/bank\/[a-z-]+-[a-f0-9]{16}\.js$/.test(spec?.url) || !/^[a-f0-9]{64}$/.test(spec.sha256)) throw Error('Invalid data asset');
  }
  return m;
}
function specs(m) {
  return new Map([[absolute('./'), m.runtime['index.html']], ...RUNTIME.map(p => [absolute(p), m.runtime[p]]),
    [absolute(m.core.url), m.core], ...Object.values(m.subjects).map(s => [absolute(s.url), s])]);
}
async function verified(response, spec) {
  if (response.status !== 200 || !response.ok) throw Error('Offline download failed');
  if (hex(await crypto.subtle.digest('SHA-256', await response.clone().arrayBuffer())) !== spec.sha256) throw Error('Offline file hash mismatch');
  return response;
}
async function plan() {
  if (!planPromise) planPromise = (async () => {
    const saved = await (await caches.open(CORE_CACHE)).match(MANIFEST_URL);
    if (!saved) throw Error('Offline manifest missing');
    return validate(await saved.json());
  })().catch(error => { planPromise = null; throw error; });
  return planPromise;
}
self.addEventListener('install', event => event.waitUntil((async () => {
  const response = await fetch(new Request(MANIFEST_URL, {cache: 'no-cache'}));
  if (!response.ok) throw Error('Manifest download failed');
  const m = validate(await response.clone().json());
  const entries = [...specs(m)];
  // Verify everything before changing a cache or taking over existing clients.
  const bodies = await Promise.all(entries.map(async ([url, spec]) => verified(await fetch(new Request(url, {cache: 'no-cache'})), spec)));
  const cache = await caches.open(CORE_CACHE);
  await Promise.all(entries.map(([url], i) => cache.put(url, bodies[i])));
  await cache.put(MANIFEST_URL, response);
  await self.skipWaiting();
})()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  const keys = (await caches.keys()).filter(k => k.startsWith('chagok-offline-') && k !== MEDIA_CACHE);
  const complete = [];
  for (const key of keys) if (key !== CORE_CACHE && (key === 'chagok-offline-v2' || await (await caches.open(key)).match(MANIFEST_URL))) complete.push(key);
  // Keep one previous snapshot for tabs that are still using its immutable scripts.
  const keep = new Set([CORE_CACHE, complete.at(-1)]);
  await self.clients.claim();
  await Promise.all(keys.filter(k => !keep.has(k)).map(k => caches.delete(k)));
})()));
function mediaRequest(url) {
  const relative = url.pathname.slice(SCOPE.pathname.length);
  return /^images\/[^/]+\.(webp|png|jpe?g)$/i.test(relative) || /^sources\/.+\.pdf$/i.test(relative);
}
async function saveMedia(request, response) {
  if (Number(response.headers.get('content-length')) > MEDIA_MAX_BYTES || (await response.clone().blob()).size > MEDIA_MAX_BYTES) return;
  const cache = await caches.open(MEDIA_CACHE);
  await cache.delete(request, {ignoreSearch: true});
  await cache.put(request, response);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - MEDIA_LIMIT)).map(k => cache.delete(k)));
}
async function saved(request, media) {
  const current = await (await caches.open(media ? MEDIA_CACHE : CORE_CACHE)).match(request, {ignoreSearch: true});
  if (current || media) return current;
  for (const key of (await caches.keys()).reverse()) if (key.startsWith('chagok-offline-v') && key !== CORE_CACHE) {
    const previous = await (await caches.open(key)).match(request, {ignoreSearch: true});
    if (previous) return previous;
  }
}
self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || request.headers.has('range') || url.origin !== SCOPE.origin || !url.pathname.startsWith(SCOPE.pathname)) return;
  const media = mediaRequest(url), relative = url.pathname.slice(SCOPE.pathname.length);
  const core = relative === '' || RUNTIME.includes(relative) || relative === 'assets/bank-manifest.json' || /^assets\/bank\/[a-z-]+-[a-f0-9]{16}\.js$/.test(relative);
  if (!core && !media) return;
  let done;
  event.waitUntil(new Promise(resolve => { done = resolve; }));
  event.respondWith((async () => {
    let response;
    try {
      response = await fetch(request);
      if (response.ok) {
        const copy = response.clone();
        (async () => {
          if (response.status !== 200 || response.type !== 'basic') return;
          if (media) return saveMedia(request, copy);
          // The installed snapshot remains internally consistent during a later deployment.
          if (url.pathname === new URL(MANIFEST_URL).pathname) return;
          const m = await plan(), spec = specs(m).get(url.origin + url.pathname);
          if (spec) await (await caches.open(CORE_CACHE)).put(url.origin + url.pathname, await verified(copy, spec));
        })().catch(() => {}).finally(done);
        return response;
      }
    } catch (_) { /* Use the complete saved copy on network and HTTP errors. */ }
    done();
    return await saved(request, media) || response || Response.error();
  })());
});
self.addEventListener('message', event => {
  if (event.data?.type !== 'CHAGOK_OFFLINE_STATUS' || !event.ports[0]) return;
  event.waitUntil((async () => {
    try {
      const m = await plan(), cache = await caches.open(CORE_CACHE);
      const missing = (await Promise.all([...specs(m).keys(), MANIFEST_URL].map(async url => await cache.match(url) ? null : url))).filter(Boolean);
      event.ports[0].postMessage({type: 'CHAGOK_OFFLINE_STATUS', ready: missing.length === 0, buildId: m.build_id,
        cacheVersion: CORE_CACHE, missing, mediaLimit: MEDIA_LIMIT, mediaMaxBytes: MEDIA_MAX_BYTES});
    } catch (_) { event.ports[0].postMessage({type: 'CHAGOK_OFFLINE_STATUS', ready: false}); }
  })());
});
