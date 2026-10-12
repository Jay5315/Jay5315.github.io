"""Exercise all thirty explanations, answer reveal, review and mobile persistence."""
import json
import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

R = Path(__file__).resolve().parents[1]
URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000/jaegyeong/').rstrip('/') + '/'
ARTIFACTS = Path(os.environ.get('TEST_ARTIFACT_DIR', str(R / '_artifacts')))
ARTIFACTS.mkdir(parents=True, exist_ok=True)
KEY = 'chagok.study.v1'
items = json.loads((R / 'data/explanations.json').read_text())['items']

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL + '#library')
    page.locator('#library-explanations').check()
    expect(page.locator('#library-results .sub').first).to_contain_text('30개 문제')
    page.locator('#library-subject').select_option('재무회계')
    expect(page.locator('.library-card')).to_have_count(10)
    page.locator('#library-subject').select_option('')
    expect(page.locator('.library-card')).to_have_count(20)  # pagination, not a truncated data set

    for i, n in enumerate(items):
        page.goto(URL + '#library')
        page.locator('#library-query').fill(n['question_id'])
        page.locator('[data-action=preview]').click()
        expect(page.locator('dialog .question-explanation')).not_to_have_attribute('open', '')
        page.locator('dialog [data-action=single]').click()
        expect(page.locator('.question-card')).to_be_visible()
        expect(page.locator('.question-card .explanation-body')).to_have_count(0)
        # Some wrong answers too: review must retain explanations without adding an attempt.
        answer = next(x for x in [1, 2, 3, 4] if x not in n['answers']) if i in (0, 10, 20) else n['answers'][0]
        page.get_by_role('button', name=f'{answer}번 선택', exact=True).click()
        page.locator('[data-action=grade]').click()
        expect(page.locator('.question-card .question-explanation[open]')).to_be_visible()
        expect(page.locator('.question-card .explanation-body h3')).to_have_text(n['title'])
        expect(page.locator('.question-card .explanation-authorship')).to_contain_text('공식 해설 아님')
        expect(page.locator('.question-card .option-reasons li')).to_have_count(4)
        expect(page.locator('.question-card .solution-steps li')).to_have_count(len(n['steps']))
        if n['review_status'] == 'partial':
            expect(page.locator('.question-card .explanation-body')).to_contain_text('기준서 재대조 필요')
        if n['tax_law_year']:
            expect(page.locator('.question-card .explanation-body')).to_contain_text(f"문항 적용 세법 {n['tax_law_year']}년")
        if i == 0:
            summary = page.locator('.question-card .question-explanation > summary')
            summary.focus()
            summary.press('Enter')
            expect(page.locator('.question-card .question-explanation')).not_to_have_attribute('open', '')
            summary.press('Enter')
            expect(page.locator('.question-card .question-explanation[open]')).to_be_visible()
            page.reload()
            expect(page.locator('.question-card .explanation-body')).to_be_visible()
            state = page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))', KEY)
            assert state['results'][n['question_id']]['attempts'] == 1
        if i == 10:
            page.screenshot(path=str(ARTIFACTS / 'explanation-desktop.png'), full_page=True)
        page.locator('[data-action=next]').click()  # finish one-question session
        expect(page.locator('.result-hero')).to_be_visible()

    page.goto(URL + '#wrong')
    expect(page.locator('[data-action=explanation]')).to_have_count(3)
    state_before = page.evaluate('(k)=>localStorage.getItem(k)', KEY)
    page.locator('[data-action=explanation]').first.click()
    expect(page.locator('dialog .explanation-body')).to_be_visible()
    page.locator('dialog [data-action=close-modal]').first.click()
    assert page.evaluate('(k)=>localStorage.getItem(k)', KEY) == state_before
    # Related concepts are separate and opening them preserves the same learning records.
    page.locator('[data-action=explanation]').first.click()
    page.locator('dialog [data-action=concept-modal]').click()
    expect(page.locator('dialog')).to_contain_text('이 문제의 해설이 아니라')
    page.locator('dialog [data-action=close-modal]').first.click()
    assert page.evaluate('(k)=>localStorage.getItem(k)', KEY) == state_before

    # No family-based fallback to a different numerical version of a question.
    page.goto(URL + '#library')
    page.locator('#library-query').fill('2026-03-094')
    expect(page.locator('[data-action=explanation]')).to_have_count(0)
    page.locator('[data-action=preview]').click()
    page.locator('dialog [data-action=single]').click()
    page.get_by_role('button', name='1번 선택', exact=True).click()
    page.locator('[data-action=grade]').click()
    expect(page.locator('.question-card .explanation-pending')).to_contain_text('준비 중')

    page.set_viewport_size({'width': 375, 'height': 812})
    page.goto(URL + '#wrong')
    page.locator('#library-query').fill('2026-01-054')
    page.locator('[data-action=explanation]').click()
    expect(page.locator('dialog .explanation-body')).to_contain_text('12,800,000원')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert page.locator('dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
    page.screenshot(path=str(ARTIFACTS / 'explanation-mobile.png'), full_page=True)
    page.locator('dialog [data-action=close-modal]').first.click()
    # Existing active session replacement still asks and preserves records.
    page.goto(URL + '#home')
    page.locator('[data-action=practice-explanations]').click()
    page.locator('#replace-session').click()
    state = page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))', KEY)
    assert len(state['active']['ids']) == 30 and state['version'] == 1
    assert set(state['active']['ids']) == {n['question_id'] for n in items}
    assert state['results']['2026-01-006']['attempts'] == 1
    assert not errors, errors
    browser.close()
    print('PASS: all 30 explanations, no pre-grade reveal, 4 options, review status/year, reload, wrong notebook, related concepts, unchanged records, independent variants, pending content, mobile, explanation-only practice; no browser errors')
