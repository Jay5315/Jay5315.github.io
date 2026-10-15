"""Browser regression checks for first-visit offline storage and failed updates.

Uses APP_BASE_URL for the normal app (defaults to the documented local server).
A temporary local HTTP server supplies deterministic HTTP failures for the final cases.
No repository files or existing browser profiles are changed.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000/jaegyeong/').rstrip('/') + '/'
READY = '#offline-status[data-state="ready"]'
TIMEOUT = 90000


def open_ready(context, url):
    page = context.new_page()
    page.goto(url, wait_until='domcontentloaded')
    page.wait_for_selector(READY, timeout=TIMEOUT)
    page.wait_for_function('navigator.serviceWorker.controller !== null')
    assert page.locator('#offline-status').get_attribute('role') == 'status'
    return page


class FailureServer:
    def __init__(self):
        self.fail = set()
        self.sw_suffix = ''
        self.sw_source = None
        owner = self

        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                path = urlsplit(self.path).path
                if path in owner.fail:
                    self.send_error(503, 'Deliberate offline regression failure')
                    return
                if path == '/jaegyeong/sw.js':
                    body = ((owner.sw_source if owner.sw_source is not None else (ROOT / 'sw.js').read_text()) + owner.sw_suffix).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/javascript; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT.parent)))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.http.server_port}/jaegyeong/'

    def close(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    seed = json.dumps({'version': 1, 'results': {}, 'bookmarks': ['2026-09-001'], 'sessions': [], 'active': None}, separators=(',', ':'))
    context.add_init_script('''(seed => {
      if (localStorage.getItem('chagok.study.v1') === null) {
        localStorage.setItem('chagok.study.v1', seed);
        caches.open('chagok-offline-v1');
      }
    })(%s);''' % json.dumps(seed))
    page = open_ready(context, URL)
    assert page.evaluate("localStorage.getItem('chagok.study.v1')") == seed
    assert 'chagok-offline-v1' not in page.evaluate('caches.keys()')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert '일부 저장' in page.locator('#offline-status').inner_text()
    images = page.evaluate('window.BANK_DATA.questions.filter(q => q.eligible).slice(0, 2).map(q => q.image)')
    assert len(images) == 2 and images[0] != images[1]
    assert page.evaluate('async url => (await fetch(url)).ok', images[0])
    page.wait_for_function('''async url => {
      const keys = (await caches.keys()).filter(key => key.startsWith('chagok-offline-media-'));
      for (const key of keys) if (await (await caches.open(key)).match(url)) return true;
      return false;
    }''', arg=images[0])
    assert not page.evaluate('async url => !!(await caches.match(url))', images[1])
    context.set_offline(True)
    # This is the FIRST reload after the first visit, without an intervening online reload.
    page.reload(wait_until='domcontentloaded')
    page.wait_for_selector(READY, timeout=TIMEOUT)
    assert page.locator('#main h1').count() > 0
    assert page.evaluate('window.BANK_DATA.explanations.items.length') > 0
    assert page.evaluate("localStorage.getItem('chagok.study.v1')") == seed
    assert page.evaluate('async url => (await fetch(url)).ok', images[0])
    assert not page.evaluate('async url => { try { return (await fetch(url)).ok; } catch (_) { return false; } }', images[1])
    context.close()
    print('PASS: first visit → ready → first offline reload; text/explanations, saved image, limited-media notice, study storage, v1 migration, mobile layout.')

    server = FailureServer()
    try:
        failed = browser.new_context()
        server.fail.add('/jaegyeong/assets/icon.svg')
        page = failed.new_page()
        page.goto(server.url, wait_until='domcontentloaded')
        page.wait_for_selector('#offline-status[data-state="unavailable"]', timeout=TIMEOUT)
        assert not page.locator(READY).count()
        assert page.evaluate('navigator.serviceWorker.controller === null')
        failed.close()
        print('PASS: failed essential download never announces offline readiness.')

        server.fail.clear()
        # Simulate an already installed worker with the former v1 caching behavior.
        server.sw_source = '''const CACHE='chagok-offline-v1';
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
 if(event.request.method!=='GET'||new URL(event.request.url).origin!==self.location.origin)return;
 event.respondWith(fetch(event.request).then(response=>{
   if(response.ok){const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)));}
   return response;
 }).catch(()=>caches.match(event.request)));
});'''
        legacy = browser.new_context()
        page = legacy.new_page()
        page.goto(server.url, wait_until='domcontentloaded')
        page.wait_for_function('navigator.serviceWorker.controller !== null')
        page.evaluate("async () => { await (await caches.open('chagok-offline-v1')).put('assets/icon.svg', await fetch('assets/icon.svg')); }")
        server.sw_source = None
        server.sw_suffix = '\n// upgrade from legacy v1 regression\n'
        page.evaluate('async () => await (await navigator.serviceWorker.getRegistration()).update()')
        page.wait_for_selector(READY, timeout=TIMEOUT)
        assert 'chagok-offline-v1' not in page.evaluate('caches.keys()')
        # Allow an obsolete v1 status probe to time out; it must not replace new readiness.
        page.wait_for_timeout(6500)
        assert page.locator(READY).count() == 1
        legacy.set_offline(True)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_selector(READY, timeout=TIMEOUT)
        assert page.locator('#main h1').count() > 0
        legacy.close()
        print('PASS: active legacy v1 worker upgrades to the complete v2 cache; obsolete status probes do not overwrite readiness.')

        server.sw_suffix = ''
        updated = browser.new_context()
        page = open_ready(updated, server.url)
        # HTTP errors use an existing complete saved response, not the 503 response.
        server.fail.add('/jaegyeong/assets/app.css')
        assert page.evaluate("async () => (await fetch('assets/app.css')).status") == 200
        server.fail.clear()
        # A changed worker whose precache fails must report failure rather than ready.
        server.sw_suffix = '\n// deterministic update regression\n'
        server.fail.add('/jaegyeong/assets/icon.svg')
        page.evaluate('async () => { try { await (await navigator.serviceWorker.getRegistration()).update(); } catch (_) {} }')
        page.wait_for_selector('#offline-status[data-state="unavailable"]', timeout=TIMEOUT)
        assert not page.locator(READY).count()
        # The failed update preserves the previously usable offline app.
        updated.set_offline(True)
        page.reload(wait_until='domcontentloaded')
        assert page.locator('#main h1').count() > 0
        updated.close()
        print('PASS: HTTP 503 cache fallback; failed update reports unavailable while preserving the previous offline app.')
    finally:
        server.close()
    browser.close()
print('PASS: offline browser regressions complete.')
