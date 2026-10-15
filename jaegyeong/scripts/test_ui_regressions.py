"""Regression checks for exact exam search, provenance badges, and progress scope.

Use isolated browser storage so the integration test's learner history stays intact.
Service-worker behavior has a separate test; these checks exercise the live app UI.
"""
import json
import os
import shutil
from playwright.sync_api import expect, sync_playwright

KEY = 'chagok.study.v1'
URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000/jaegyeong/').rstrip('/') + '/'
SESSION_FIELDS = {'id', 'title', 'ids', 'answers', 'index', 'startedAt', 'finishedAt'}
RESULT_FIELDS = {'attempts', 'correct', 'lastCorrect', 'lastAnswer', 'updatedAt'}


def run_ui_regressions(browser, url=URL):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, service_workers='block')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(url)
    expect(page.locator('.subject-card')).to_have_count(3)

    def state():
        return page.evaluate('k=>JSON.parse(localStorage.getItem(k))', KEY)

    def library(query, subject=''):
        page.goto(url + '#library')
        expect(page.locator('#library-query')).to_be_visible()
        page.locator('#library-subject').select_option(subject)
        page.locator('#library-part').select_option('')
        page.locator('#library-query').fill(query)

    def ids():
        return page.locator('.library-card [data-action=preview]').evaluate_all('(buttons)=>buttons.map(b=>b.dataset.id)')

    def expected_occurrences(exam, number):
        return page.evaluate("""([exam,number])=>BANK_DATA.questions.filter(q=>q.eligible&&q.occurrences.some(o=>
          o.startsWith(exam+'-')&&((Number(o.slice(-3))-1)%40)+1===number)).map(q=>q.id).sort()""", [exam, number])

    # 1번 must not match the suffix of 11번, 21번, or 31번.
    for number in [1, 5, 12, 32, 40]:
        library(f'2024-11 {number}번')
        expected = expected_occurrences('2024-11', number)
        assert len(expected) == 3, (number, expected)
        expect(page.locator('.library-card')).to_have_count(3)
        assert sorted(ids()) == expected, (number, ids(), expected)
        actual_numbers = page.evaluate("""ids=>ids.map(id=>BANK_DATA.questions.find(q=>q.id===id).occurrences
          .filter(o=>o.startsWith('2024-11-')).map(o=>((Number(o.slice(-3))-1)%40)+1))""", ids())
        assert all(number in values for values in actual_numbers), actual_numbers
    library('2024-11 1번', '원가관리회계')
    expect(page.locator('.library-card')).to_have_count(1)
    # A full occurrence ID finds its representative even if that representative is from another sitting.
    library('2024-11-092')
    expect(page.locator('.library-card')).to_have_count(1)
    assert ids() == ['2026-06-092'], ids()
    # Out-of-range local numbers do not fall back to arbitrary body-text matches.
    for query in ['2024-11 0번', '2024-11 41번']:
        library(query)
        expect(page.locator('.library-card')).to_have_count(0)

    # Existing AND and whitespace-insensitive natural-language search still works.
    library('보고기간 후사건')
    assert ids(), 'Natural-language AND search returned no results'
    assert page.evaluate("""ids=>ids.every(id=>{
      const q=BANK_DATA.questions.find(q=>q.id===id),text=(q.text+'|'+q.stem).replace(/\\s/g,'');
      return text.includes('보고기간')&&text.includes('후사건');})""", ids())

    # Selected sitting and representative provenance survive practice, reload, resume, and results.
    library('2024-11 12번', '원가관리회계')
    expect(page.locator('.library-card')).to_have_count(1)
    assert ids() == ['2026-06-092']
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('.library-card .library-copy > .meta').first).to_contain_text(value)
    before_reading = page.evaluate('k=>localStorage.getItem(k)', KEY)
    page.locator('.library-card [data-action=preview]').click()
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('dialog .meta').first).to_contain_text(value)
    page.locator('dialog [data-action=close-modal]').first.click()
    assert page.evaluate('k=>localStorage.getItem(k)', KEY) == before_reading
    page.locator('[data-action=practice-list]').click()
    expect(page.locator('.question-card')).to_be_visible()
    active = state()['active']
    assert set(active) == SESSION_FIELDS, active
    assert active['ids'] == ['2026-06-092'] and '2024-11' in active['title']
    assert set(state()) == {'version', 'results', 'bookmarks', 'sessions', 'active'}
    assert state()['version'] == 1
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('.question-heading .meta')).to_contain_text(value)
    page.reload()
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('.question-heading .meta')).to_contain_text(value)
    page.locator('[data-action=home]').click()
    expect(page.locator('.resume')).to_contain_text('2024-11')
    page.locator('[data-action=resume]').click()
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('.question-heading .meta')).to_contain_text(value)
    answer = page.evaluate("BANK_DATA.questions.find(q=>q.id==='2026-06-092').answers[0]")
    page.get_by_role('button', name=f'{answer}번 선택', exact=True).click()
    page.locator('[data-action=grade]').click()
    assert set(state()['results']['2026-06-092']) == RESULT_FIELDS
    page.locator('[data-action=next]').click()
    expect(page.locator('.result-row')).to_have_count(1)
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('.result-row small')).to_contain_text(value)
    assert state()['active'] is None
    assert set(state()['sessions'][0]) == SESSION_FIELDS
    page.locator('.result-row [data-action=preview]').click()
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('dialog .meta').first).to_contain_text(value)
    page.locator('dialog [data-action=close-modal]').first.click()

    # All retry entry points retain the original sitting without adding persisted fields.
    page.locator('[data-action=retry-all]').click()
    expect(page.locator('.question-card')).to_be_visible()
    assert set(state()['active']) == SESSION_FIELDS
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('.question-heading .meta')).to_contain_text(value)
    wrong = page.evaluate("BANK_DATA.questions.find(q=>q.id==='2026-06-092').answers[0]%4+1")
    page.get_by_role('button', name=f'{wrong}번 선택', exact=True).click()
    page.locator('[data-action=grade]').click()
    page.locator('[data-action=next]').click()
    page.locator('[data-action=retry]').click()
    expect(page.locator('.question-card')).to_be_visible()
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('.question-heading .meta')).to_contain_text(value)
    page.locator('[data-action=finish]').click()
    page.locator('[data-action=finish-now]').click()
    page.locator('[data-action=unanswered]').click()
    expect(page.locator('.question-card')).to_be_visible()
    for value in ['2024-11', '2026-06', '12번']:
        expect(page.locator('.question-heading .meta')).to_contain_text(value)
    assert set(state()['active']) == SESSION_FIELDS

    # Source checking and arithmetic checking are separate claims.
    def open_explanation(qid):
        library(qid)
        expect(page.locator('.library-card')).to_have_count(1)
        page.locator('.library-card [data-action=explanation]').click()
        expect(page.locator('dialog .explanation-body')).to_be_visible()

    open_explanation('2026-01-007')
    assert page.evaluate("BANK_DATA.explanations.items.find(e=>e.question_id==='2026-01-007').checks.length") == 0
    expect(page.locator('dialog .explanation-body .note-badges')).not_to_contain_text('계산 검산')
    page.locator('dialog [data-action=close-modal]').first.click()
    checked_id = page.evaluate("BANK_DATA.explanations.items.find(e=>e.review_status==='source_checked'&&e.checks.length&&BANK_DATA.questions.some(q=>q.id===e.question_id&&q.eligible)).question_id")
    open_explanation(checked_id)
    expect(page.locator('dialog .explanation-body .note-badges')).to_contain_text('계산 검산')
    page.locator('dialog [data-action=close-modal]').first.click()
    partial_id = page.evaluate("BANK_DATA.explanations.items.find(e=>e.review_status==='partial'&&e.unchecked_points.length&&BANK_DATA.questions.some(q=>q.id===e.question_id&&q.eligible)).question_id")
    open_explanation(partial_id)
    expect(page.locator('dialog .explanation-body .note-badges')).to_contain_text('부분 확인')
    expect(page.locator('dialog .explanation-body .note-badges')).not_to_contain_text('기준서 재대조 필요')
    points = page.evaluate('id=>BANK_DATA.explanations.items.find(e=>e.question_id===id).unchecked_points', partial_id)
    assert page.locator('dialog .unchecked-box li').all_inner_texts() == points
    page.locator('dialog [data-action=close-modal]').first.click()
    part = page.evaluate("BANK_DATA.concepts.notes.find(n=>n.review_status==='partial'&&n.unchecked_points.length).part_id")
    page.goto(url + '#concept/' + part)
    expect(page.locator('.note-page > .note-badges')).to_contain_text('부분 확인')
    expect(page.locator('.note-page .unchecked-box h3')).to_have_text('추가 확인이 필요한 내용')
    expect(page.locator('.note-page .unchecked-box')).not_to_contain_text('국내 교재의 일반적인 내용이며')
    points = page.evaluate('id=>BANK_DATA.concepts.notes.find(n=>n.part_id===id).unchecked_points', part)
    assert page.locator('.note-page .unchecked-box li').all_inner_texts() == points

    # Both numerator and denominator follow variants and classification-review filters.
    counts = page.evaluate("""k=>{const s=JSON.parse(localStorage.getItem(k)),qs=BANK_DATA.questions.filter(q=>q.eligible&&q.part==='F02');
      s.results=Object.fromEntries(qs.map(q=>[q.id,{attempts:1,correct:1,lastCorrect:true,lastAnswer:q.answers[0],updatedAt:Date.now()}]));
      localStorage.setItem(k,JSON.stringify(s));return {all:qs.length,representative:qs.filter(q=>q.representative).length,
        checked:qs.filter(q=>q.representative&&!q.review).length,allChecked:qs.filter(q=>!q.review).length};}""", KEY)
    assert counts['all'] == 65 and counts['representative'] == 64, counts
    page.goto(url + '#home')
    page.reload()
    record_before_filters = json.dumps(state(), sort_keys=True)
    row = page.locator('.part-row[data-id="F02"]')

    def check_progress(expected):
        expect(row.locator('.part-count')).to_have_text(f'{expected}문제')
        expect(row.locator('.part-progress')).to_contain_text(f'{expected}문제 풀이')
        expect(row.locator('.part-progress')).to_contain_text('최근 정답률 100%')

    check_progress(counts['representative'])
    page.locator('#setup-variants').check()
    check_progress(counts['all'])
    page.locator('#setup-variants').uncheck()
    page.locator('#setup-review').check()
    check_progress(counts['checked'])
    page.locator('#setup-variants').check()
    check_progress(counts['allChecked'])
    assert json.dumps(state(), sort_keys=True) == record_before_filters, 'Display filters changed saved study records'
    assert not errors, errors
    context.close()
    return 'exact sitting/number/occurrence search, requested vs representative metadata, source/calculation badges, partial warnings, filtered progress, unchanged study schema'


if __name__ == '__main__':
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
        try:
            print('PASS: ' + run_ui_regressions(browser))
        finally:
            browser.close()
