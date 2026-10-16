"""Browser checks for deferred explanations, retries, integrity, and portable file use."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from playwright.sync_api import Error, expect, sync_playwright

R = Path(__file__).resolve().parents[1]
URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000/jaegyeong/').rstrip('/') + '/'
KEY = 'chagok.study.v1'


def run_lazy_loading(browser, url=URL):
    context = browser.new_context(service_workers='block')
    page = context.new_page()
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.url))
    page.goto(url)
    expect(page.locator('.home-head')).to_be_visible()
    assert page.evaluate('BANK_DATA.explanations.items.filter(n=>n.option_notes).length') == 0
    assert not any('/explanations-' in u or '/bank-data.js' in u for u in requests), requests
    assert page.evaluate('BANK_DATA.questions.length') == 4322
    assert page.evaluate('BANK_DATA.concepts.notes.length') == 74

    def open_note(qid):
        page.goto(url + '#library')
        page.locator('#library-query').fill(qid)
        page.locator('[data-action=explanation]').click()

    open_note('2026-01-007')
    expect(page.locator('dialog .solution-steps')).to_be_visible()
    assert len([u for u in requests if '/explanations-finance-' in u]) == 1
    assert not any('/explanations-tax-' in u or '/explanations-cost-' in u for u in requests)
    page.locator('dialog [data-action=close-modal]').first.click()
    open_note('2026-01-007')
    expect(page.locator('dialog .solution-steps')).to_be_visible()
    assert len([u for u in requests if '/explanations-finance-' in u]) == 1
    page.locator('dialog [data-action=close-modal]').first.click()

    tax_id = page.evaluate("BANK_DATA.explanations.items.find(n=>n.part_id.startsWith('C')).question_id")
    blocked = {'value': True}
    page.route('**/explanations-tax-*.js', lambda route: route.abort() if blocked['value'] else route.continue_())
    before = page.evaluate('k=>localStorage.getItem(k)', KEY)
    open_note(tax_id)
    expect(page.locator('[data-action=reload-explanation]')).to_be_visible()
    expect(page.locator('dialog .explanation-loading')).to_contain_text('불러오지 못했습니다')
    assert page.evaluate('k=>localStorage.getItem(k)', KEY) == before
    blocked['value'] = False
    page.locator('[data-action=reload-explanation]').click()
    expect(page.locator('dialog .solution-steps')).to_be_visible()
    assert page.evaluate('k=>localStorage.getItem(k)', KEY) == before
    page.locator('dialog [data-action=close-modal]').first.click()
    # Concurrent consumers share one subject download and mutate the same indexed note objects.
    page.evaluate("""async () => {
      const ids=BANK_DATA.explanations.items.filter(n=>n.part_id.startsWith('M')).slice(0,3).map(n=>n.question_id);
      await Promise.all(ids.map(id=>BANK_DATA_LOADER.explanation(id)));
    }""")
    assert len([u for u in requests if '/explanations-cost-' in u]) == 1
    assert page.evaluate('BANK_DATA.explanations.items.every(n=>n.option_notes?.length===4)')
    assert not errors, errors
    context.close()

    # Corrupt code never bypasses the generated SHA-256 integrity attribute.
    context = browser.new_context(service_workers='block')
    page = context.new_page()
    page.route('**/explanations-finance-*.js', lambda route: route.fulfill(status=200, content_type='application/javascript', body='window.CHAGOK_CORRUPTED=true;'))
    page.goto(url + '#library')
    page.locator('#library-query').fill('2026-01-007')
    page.locator('[data-action=explanation]').click()
    expect(page.locator('[data-action=reload-explanation]')).to_be_visible()
    assert page.evaluate('window.CHAGOK_CORRUPTED !== true')
    assert page.evaluate('BANK_DATA.explanations.items.filter(n=>n.option_notes).length') == 0
    context.close()

    # An old/corrupt cached app must not run against a newer manifest and data index.
    context = browser.new_context(service_workers='block')
    page = context.new_page()
    page.route('**/app.js?build=*', lambda route: route.fulfill(status=200, content_type='application/javascript', body='window.CHAGOK_OLD_APP_RAN=true;'))
    page.goto(url)
    expect(page.locator('#retry-bank')).to_be_visible()
    assert page.evaluate('window.CHAGOK_OLD_APP_RAN !== true')
    assert page.evaluate('BANK_DATA.questions.length') == 4322
    context.close()

    # Startup failures expose retry and preserve browser history rather than silently replacing it.
    context = browser.new_context(service_workers='block')
    seed = json.dumps({'version': 1, 'results': {}, 'bookmarks': ['2026-09-001'], 'sessions': [], 'active': None})
    context.add_init_script("if(!localStorage.getItem('chagok.study.v1'))localStorage.setItem('chagok.study.v1'," + json.dumps(seed) + ');')
    page = context.new_page()
    tries = {'value': 0}
    def first_failure(route):
        tries['value'] += 1
        route.abort() if tries['value'] == 1 else route.continue_()
    page.route('**/bank-manifest.json', first_failure)
    page.goto(url)
    expect(page.locator('#retry-bank')).to_be_visible()
    assert page.evaluate('k=>localStorage.getItem(k)', KEY) == seed
    page.locator('#retry-bank').click()
    expect(page.locator('.home-head')).to_be_visible()
    assert page.evaluate('k=>localStorage.getItem(k)', KEY) == seed
    context.close()

    # file:// uses the unchanged complete bundle and never relies on fetch or a service worker.
    context = browser.new_context(service_workers='block')
    page = context.new_page()
    local_requests = []
    page.on('request', lambda r: local_requests.append(r.url))
    try:
        page.goto((R / 'index.html').as_uri())
    except Error as error:
        if 'ERR_BLOCKED_BY_ADMINISTRATOR' not in str(error):
            raise
        context.close()
        subprocess.run(['node', str(R/'scripts/test_file_loader.cjs')], check=True)
        print('SKIP: real file:// browser navigation is blocked by managed browser policy; file-loader unit branch passed.')
        return 'lightweight startup, deferred explanations, shared downloads, retry/storage, SRI including stale-app rejection, startup retry; file:// unit passed (real browser blocked)'
    expect(page.locator('.home-head')).to_be_visible()
    assert page.evaluate('BANK_DATA.explanations.items.filter(n=>n.option_notes).length') == 4281
    assert any('/bank-data.js' in u for u in local_requests)
    assert not any('/bank-manifest.json' in u or '/explanations-' in u for u in local_requests)
    page.get_by_role('link', name='문제 둘러보기', exact=True).click()
    page.locator('#library-query').fill('2026-01-007')
    page.locator('[data-action=explanation]').click()
    expect(page.locator('dialog .solution-steps')).to_be_visible()
    context.close()
    return 'lightweight startup, deferred subject explanations, shared downloads, retry/storage preservation, SRI corruption rejection, startup retry, file:// full-bundle compatibility'


if __name__ == '__main__':
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
        try:
            print('PASS: ' + run_lazy_loading(browser))
        finally:
            browser.close()
