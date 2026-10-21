"""Local Chromium acceptance journey; desktop keyboard and mobile touch emulation.

No physical phone, screen-reader speech, or public HTTPS verification is implied.
Runs its own temporary local server unless APP_BASE_URL is supplied.
"""
import functools
import http.server
import json
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ART = Path(os.environ.get('TEST_ARTIFACT_DIR', ROOT / '_artifacts' / 'user-journey'))
KEY = 'chagok.study.v1'
RKEY = 'chagok.review.v1'


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def run_journey(browser, url):
    ART.mkdir(parents=True, exist_ok=True)
    local = urlsplit(url).hostname in ('127.0.0.1', 'localhost', '::1')
    report = {'method': 'Chromium; desktop keyboard and mobile touch emulation',
              'origin': 'loopback HTTP server' if local else url,
              'physical_devices': False, 'screen_reader_speech': 'UNVERIFIED',
              'external_fonts': 'blocked for local-only test; installed fallback fonts',
              'cases': [], 'browser_errors': [], 'screenshots': []}
    if not local:
        report['external_fonts'] = 'normal network loading'
    contexts = []

    def new_context(**options):
        context = browser.new_context(service_workers='block', accept_downloads=True,
                                      locale='ko-KR', timezone_id='Asia/Seoul',
                                      reduced_motion='reduce', **options)
        contexts.append(context)
        if local:
            # Keep this local test off external networks, including the font CDN.
            context.route('**/*', lambda route: route.continue_()
                          if urlsplit(route.request.url).hostname in ('127.0.0.1', 'localhost', '::1')
                          else route.abort())
        page = context.new_page()
        page.on('pageerror', lambda error: report['browser_errors'].append(str(error)))
        page.goto(url)
        expect(page.locator('.home-head')).to_be_visible()
        return context, page

    def record(page):
        return page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))', KEY)

    def review(page):
        return page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))', RKEY)

    def active_question(page):
        return page.evaluate('(k)=>{const s=JSON.parse(localStorage.getItem(k)).active;return BANK_DATA.questions.find(q=>q.id===s.ids[s.index]);}', KEY)

    def keyboard_to(page, selector, key='Enter'):
        # Tab through actual controls instead of programmatically focusing the target.
        for _ in range(180):
            if page.locator(selector).evaluate('(e)=>e===document.activeElement'):
                page.keyboard.press(key)
                return
            page.keyboard.press('Tab')
        raise AssertionError('Keyboard target unreachable: ' + selector)

    def no_overflow(page, label):
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'), label

    def capture(page, name):
        no_overflow(page, name)
        page.screenshot(path=str(ART / (name + '.png')), full_page=True)
        page.screenshot(path=str(ART / (name + '-viewport.png')))
        report['screenshots'].extend([name + '.png', name + '-viewport.png'])

    def downloadable_backup(page, mobile=False):
        if mobile:
            page.locator('.avatar').tap()
        else:
            keyboard_to(page, '.avatar')
        with page.expect_download() as download:
            if mobile:
                page.locator('[data-action=export]').tap()
            else:
                keyboard_to(page, '[data-action=export]')
        data = json.loads(Path(download.value.path()).read_text())
        if mobile:
            page.locator('[data-action=close-modal]').tap()
        else:
            page.keyboard.press('Escape')
        return data

    def backup_equals(data, saved, schedule):
        assert {k: v for k, v in data.items() if k not in ('exportedAt', 'review')} == saved
        assert data['review'] == schedule

    try:
        _, desktop = new_context(viewport={'width': 1440, 'height': 1000})
        capture(desktop, 'desktop-home')
        keyboard_to(desktop, '[data-action=subject][data-subject="재무회계"]')
        keyboard_to(desktop, '[data-action=count][data-count="10"]')
        keyboard_to(desktop, '#setup-random', 'Space')
        keyboard_to(desktop, '[data-action=start]')
        expect(desktop.locator('.question-card')).to_be_visible()
        q = active_question(desktop)
        first = q['id']
        bad = next(n for n in (1, 2, 3, 4) if n not in q['answers'])
        keyboard_to(desktop, '.question-heading [data-action=bookmark]', 'Space')
        # Main is not focused here: a digit shortcut must retain the bookmark focus.
        desktop.keyboard.press(str(bad))
        keyboard_to(desktop, '[data-action=grade]')
        expect(desktop.locator('.feedback.wrong')).to_be_visible()
        expect(desktop.locator('.pick-reasons')).to_be_visible()
        before_concept = record(desktop)
        keyboard_to(desktop, '.question-card>.concept-row [data-action=concept-modal]')
        expect(desktop.locator('dialog[open]')).to_be_visible()
        desktop.keyboard.press('Escape')
        assert record(desktop) == before_concept
        expect(desktop.locator('.question-card>.concept-row [data-action=concept-modal]')).to_be_focused()
        capture(desktop, 'desktop-graded')
        keyboard_to(desktop, '[data-action=home]')
        expect(desktop.locator('.resume')).to_be_visible()
        keyboard_to(desktop, '[data-action=resume]')
        expect(desktop.locator('.feedback.wrong')).to_be_visible()
        keyboard_to(desktop, '[data-action=finish]')
        keyboard_to(desktop, '[data-action=finish-now]')
        expect(desktop.locator('.result-hero')).to_be_visible()
        capture(desktop, 'desktop-result')
        keyboard_to(desktop, '#nav a[href="#wrong"]')
        expect(desktop.locator('.library-card')).to_have_count(1)
        keyboard_to(desktop, '[data-action=preview]')
        keyboard_to(desktop, '[data-action=single]')
        expect(desktop.locator('.question-card')).to_be_visible()
        desktop.keyboard.press(str(active_question(desktop)['answers'][0]))
        keyboard_to(desktop, '[data-action=grade]')
        expect(desktop.locator('.feedback:not(.wrong)')).to_be_visible()
        keyboard_to(desktop, '[data-action=next]')
        expect(desktop.locator('.result-hero')).to_be_visible()
        assert record(desktop)['results'][first]['attempts'] == 2
        assert record(desktop)['results'][first]['lastCorrect']
        keyboard_to(desktop, '#nav a[href="#wrong"]')
        expect(desktop.locator('.library-card')).to_have_count(0)
        report['cases'].append('desktop keyboard: setup, bookmark, wrong grade, concept/return focus, resume, finish, correct replay removes wrong entry')

        # Export real UI-created results, completed sessions, bookmarks, and an in-progress session.
        keyboard_to(desktop, '.brand')
        keyboard_to(desktop, '[data-action=start]')
        expect(desktop.locator('.question-card')).to_be_visible()
        desktop.keyboard.press(str(active_question(desktop)['answers'][0]))
        keyboard_to(desktop, '[data-action=grade]')
        keyboard_to(desktop, '[data-action=next]')
        keyboard_to(desktop, '[data-action=home]')
        saved, schedule = record(desktop), review(desktop)
        assert saved['active']['index'] == 1 and len(saved['active']['answers']) == 1
        backup = downloadable_backup(desktop)
        backup_equals(backup, saved, schedule)

        _, mobile = new_context(viewport={'width': 360, 'height': 800},
                                is_mobile=True, has_touch=True, device_scale_factor=2)
        mobile.locator('.avatar').tap()
        mobile.locator('[data-action=size-set][data-size=xl]').tap()
        mobile.locator('[data-action=theme-set][data-theme=dark]').tap()
        capture(mobile, 'mobile-settings-xl-dark')
        expect(mobile.locator('html')).to_have_attribute('data-size', 'xl')
        assert record(mobile) is None, 'fresh context must have no learner record'
        upload = {'name': 'journey-backup.json', 'mimeType': 'application/json',
                  'buffer': json.dumps(backup, ensure_ascii=False).encode()}
        mobile.locator('#backup-file').set_input_files(upload)
        expect(mobile.locator('#confirm-import')).to_be_visible()
        assert record(mobile) is None, 'import must wait for confirmation'
        mobile.get_by_role('button', name='취소', exact=True).tap()
        assert record(mobile) is None, 'cancelled import changed storage'
        mobile.locator('.avatar').tap()
        mobile.locator('#backup-file').set_input_files(upload)
        mobile.locator('#confirm-import').tap()
        expect(mobile.locator('dialog[open]')).to_have_count(0)
        assert record(mobile) == saved and review(mobile) == schedule
        backup_equals(downloadable_backup(mobile, mobile=True), saved, schedule)
        assert record(desktop) == saved and review(desktop) == schedule, 'fresh-context restore affected original browser'
        report['cases'].append('JSON backup/restore across isolated browser contexts: all study fields, review schedule, active position, cancel safety, export round-trip')

        mobile.locator('[data-action=resume]').tap()
        expect(mobile.locator('.quiz-top .sub')).to_contain_text('2 / 10')
        q = active_question(mobile)
        answer = q['answers'][0]
        mobile.locator(f'[data-action=choose][data-answer="{answer}"]').tap()
        button = mobile.locator('[data-action=grade]')
        button.scroll_into_view_if_needed()
        assert button.evaluate('e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}'), 'grade button covered by another element'
        button.tap()
        expect(mobile.locator('.feedback:not(.wrong)')).to_be_visible()
        expect(mobile.locator('.pick-reasons')).to_be_visible()
        capture(mobile, 'mobile-graded-xl-dark')
        mobile.reload()
        expect(mobile.locator('.feedback:not(.wrong)')).to_be_visible()
        assert record(mobile)['active']['answers'][q['id']] == answer
        # Rotate a touch viewport while the same graded question remains open.
        mobile.set_viewport_size({'width': 800, 'height': 360})
        capture(mobile, 'mobile-landscape-xl-dark')
        mobile.set_viewport_size({'width': 360, 'height': 800})
        mobile.locator('[data-action=home]').tap()
        expect(mobile.locator('.home-head')).to_be_visible()
        capture(mobile, 'mobile-home-xl-dark')
        report['cases'].append('360px touch emulation: xl/dark, resume at 2/10, unobstructed grading, explanation, reload persistence, landscape resize')

        for width, height in [(360, 800), (390, 844), (820, 1180)]:
            mobile.set_viewport_size({'width': width, 'height': height})
            mobile.locator('#nav a[href="#library"]').tap()
            mobile.locator('#library-query').fill('2024-11 1번')
            mobile.locator('#library-subject').select_option('재무회계')
            expect(mobile.locator('.library-card')).to_have_count(1)
            mobile.locator('[data-action=preview]').tap()
            capture(mobile, f'preview-{width}-xl-dark')
            mobile.locator('[data-action=close-modal]').first.tap()
            mobile.goto(url + '#concept/F02')
            expect(mobile.locator('.note-page')).to_be_visible()
            capture(mobile, f'concept-{width}-xl-dark')
            mobile.locator('.note-toc-fold summary').tap()
            mobile.locator('.note-toc-fold [data-toc="1"]').tap()
            assert mobile.evaluate('document.activeElement.matches(".note-sec>h3")')
            mobile.locator('.avatar').tap()
            mobile.locator('[data-action=theme-set][data-theme=light]').tap()
            mobile.locator('[data-action=close-modal]').first.tap()
            capture(mobile, f'concept-{width}-xl-light')
            mobile.locator('.avatar').tap()
            mobile.locator('[data-action=theme-set][data-theme=dark]').tap()
            mobile.locator('[data-action=close-modal]').first.tap()
        report['cases'].append('360/390/820px: exact exam search, subject filter, preview, xl concept page, TOC focus, light/dark; no document overflow')
        assert not report['browser_errors'], report['browser_errors']
        report['result'] = 'PASS'
    except Exception as error:
        report.update(result='FAIL', error=str(error))
        raise
    finally:
        (ART / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        for context in contexts:
            context.close()
    return report


if __name__ == '__main__':
    server = None
    url = os.environ.get('APP_BASE_URL')
    if not url:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT.parent)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/jaegyeong/'
    try:
        with sync_playwright() as playwright:
            options = {'headless': True, 'executable_path': shutil.which('chromium')}
            if urlsplit(url).hostname not in ('127.0.0.1', 'localhost', '::1') and os.environ.get('HTTPS_PROXY'):
                options['proxy'] = {'server': os.environ['HTTPS_PROXY']}
            browser = playwright.chromium.launch(**options)
            try:
                print(json.dumps(run_journey(browser, url.rstrip('/') + '/'), ensure_ascii=False, indent=2))
            finally:
                browser.close()
    finally:
        if server:
            server.shutdown()
            server.server_close()
