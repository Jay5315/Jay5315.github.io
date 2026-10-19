"""Exercise the actual portable ZIP on HTTP, including a full-bundle branch fixture.

The fixture simulates the file-loader branch on an allowed HTTP origin. It is not
an actual file:// browser test and does not change browser or TLS policy.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import threading
import zipfile

from playwright.sync_api import expect, sync_playwright

R = Path(__file__).resolve().parents[1]
KEY = 'chagok.study.v1'


def run():
    archive = R / 'dist/chagok-webapp.zip'
    if not archive.exists():
        raise RuntimeError('Run scripts/package_app.py before this ZIP integration check')
    manifest = json.loads((R / 'assets/bank-manifest.json').read_text())
    full = json.loads((R / 'assets/bank-data.js').read_text()[len('window.BANK_DATA='):-2])
    q = next(q for q in full['questions'] if q['id'] == '2026-01-007')
    required = list(dict.fromkeys(['index.html', 'sw.js', 'assets/bank-data.js', 'assets/bank-manifest.json',
                                   *manifest['runtime'], manifest['core']['url'],
                                   *[s['url'] for s in manifest['subjects'].values()]]))
    summary = {'archive': archive.name, 'build_id': manifest['build_id'], 'runtime_hashes': {}, 'cases': [],
               'actual_file_navigation': 'UNVERIFIED: managed browser policy; HTTP branch simulation only'}
    with tempfile.TemporaryDirectory(prefix='chagok-portable-') as temp:
        root = Path(temp)
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            assert z.testzip() is None
            for name in required:
                body = z.read('chagok-webapp/' + name)
                assert body == (R / name).read_bytes(), name
                summary['runtime_hashes'][name] = hashlib.sha256(body).hexdigest()
            # Validate every source reference against the archive without extracting all PDFs.
            for question in full['questions']:
                for field in ['image', 'pdf', 'answerPdf']:
                    assert 'chagok-webapp/' + question[field] in names, (question['id'], field)
            extract = required + [q[k] for k in ['image', 'pdf', 'answerPdf']]
            for name in dict.fromkeys(extract):
                destination = root / 'chagok-webapp' / name
                assert destination.resolve().is_relative_to(root.resolve())
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(z.read('chagok-webapp/' + name))
        summary['cases'].append('ZIP CRC, 13 exact runtime hashes, every question image/PDF reference')

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/chagok-webapp/'
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
                errors = []
                legacy = browser.new_context(service_workers='block', accept_downloads=True)
                page = legacy.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                requests = []
                page.on('request', lambda request: requests.append(request.url))
                loader = (root / 'chagok-webapp/assets/data-loader.js').read_text()
                condition = "if (location.protocol === 'file:')"
                assert loader.count(condition) == 1
                legacy.route('**/data-loader.js', lambda route: route.fulfill(
                    status=200, content_type='application/javascript', body=loader.replace(condition, 'if (true)', 1)))
                page.goto(url)
                expect(page.locator('.home-head')).to_be_visible()
                assert page.evaluate('BANK_DATA.explanations.items.every(n=>n.option_notes?.length===4)')
                assert not any('bank-manifest.json' in request or '/explanations-' in request for request in requests)
                page.goto(url + '#library')
                page.locator('#library-query').fill(q['id'])
                page.locator('[data-action=preview]').click()
                page.locator('dialog [data-action=single]').click()
                wrong = q['answers'][0] % 4 + 1
                assert wrong not in q['answers']
                page.get_by_role('button', name=f'{wrong}번 선택', exact=True).click()
                page.locator('[data-action=grade]').click()
                expect(page.locator('.feedback')).to_have_class('feedback wrong')
                expect(page.locator('.question-card .option-reasons li')).to_have_count(4)
                page.locator('.question-heading [data-action=bookmark]').click()
                saved = page.evaluate('k=>JSON.parse(localStorage.getItem(k))', KEY)
                page.reload()
                expect(page.locator('.feedback')).to_be_visible()
                assert page.evaluate('k=>JSON.parse(localStorage.getItem(k))', KEY) == saved
                page.locator('[data-action=next]').click()
                expect(page.locator('.result-row')).to_have_count(1)
                page.goto(url + '#wrong')
                expect(page.locator('.library-card .wrong-pick')).to_contain_text('내가 고른 답')
                expect(page.locator('.library-card .wrong-pick')).to_contain_text('정답')
                summary['cases'].append('HTTP full-bundle compatibility simulation: grading, all four reasons, bookmark, reload, result, wrong notebook')

                other = legacy.new_page()
                other.goto(url)
                expect(other.locator('.home-head')).to_be_visible()
                assert other.evaluate('(k)=>JSON.parse(localStorage.getItem(k)).results', KEY) == saved['results']
                other.close()
                page.locator('.avatar').click()
                with page.expect_download() as download:
                    page.locator('[data-action=export]').click()
                backup = root / 'study-backup.json'
                download.value.save_as(backup)
                backup_data = json.loads(backup.read_text())
                restored = browser.new_context(service_workers='block')
                fresh = restored.new_page()
                fresh.on('pageerror', lambda error: errors.append(str(error)))
                fresh.goto(url)
                expect(fresh.locator('.home-head')).to_be_visible()
                fresh.locator('.avatar').click()
                fresh.locator('#backup-file').set_input_files(backup)
                fresh.locator('#confirm-import').click()
                expect(fresh.locator('.home-head')).to_be_visible()
                actual = fresh.evaluate('k=>JSON.parse(localStorage.getItem(k))', KEY)
                assert 'exportedAt' in backup_data
                expected = {key: value for key, value in backup_data.items() if key not in ('exportedAt', 'review')}
                assert actual == expected, {'actual': actual, 'expected': expected}
                # The spaced-review schedule travels in the backup's separate `review` field.
                assert 'review' in backup_data
                assert fresh.evaluate("JSON.parse(localStorage.getItem('chagok.review.v1'))") == backup_data['review']
                summary['cases'].append('Separate tab sees saved results; JSON backup restores in a fresh browser context')
                restored.close()
                legacy.close()

                mobile = browser.new_context(viewport={'width': 390, 'height': 844})
                page = mobile.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(url)
                expect(page.locator('.home-head')).to_be_visible()
                assert page.evaluate('BANK_DATA.explanations.items.filter(n=>n.option_notes).length') == 0
                page.locator('#offline-status[data-state=ready]').wait_for(timeout=90000)
                mobile.set_offline(True)
                page.reload(wait_until='domcontentloaded')
                expect(page.locator('.home-head')).to_be_visible()
                page.goto(url + '#library')
                page.locator('#library-query').fill('2024-11 1번')
                expect(page.locator('.library-card')).to_have_count(3)
                cost = page.evaluate("BANK_DATA.explanations.items.find(n=>n.part_id.startsWith('M')).question_id")
                page.locator('#library-query').fill(cost)
                page.locator('[data-action=explanation]').click()
                expect(page.locator('dialog .option-reasons li')).to_have_count(4)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                summary['cases'].append('Extracted ZIP mobile web: initial lazy loading, real offline reload, exact search, deferred cost explanation, no overflow')
                mobile.close()
                assert not errors, errors
                summary['browser_errors'] = errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    summary['result'] = 'PASS'
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    run()
