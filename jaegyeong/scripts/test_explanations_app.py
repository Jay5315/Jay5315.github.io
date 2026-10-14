"""Exercise registered explanations, answer reveal, review and mobile persistence."""
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
round20 = json.loads((R / 'reports/explanation-expansion.json').read_text()).get('round20_followups',{})
concept_changes = round20.get('concept_amendments',[])
# Render every explanation, then exercise actual grading for the original 30 and
# both conceptual/calculation examples in each newly covered part.
interactive = list(items[:30])
covered = set()
for n in items[30:]:
    group = (n['part_id'], bool(n['checks']))
    if group not in covered:
        interactive.append(n)
        covered.add(group)
interactive_ids={n['question_id'] for n in interactive}
by_id={n['question_id']:n for n in items}
for registration in round20.get('registrations',[]):
    if registration['question_id'] not in interactive_ids:
        interactive.append(by_id[registration['question_id']])
        interactive_ids.add(registration['question_id'])

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL + '#library')
    page.locator('#library-explanations').check()
    expect(page.locator('#library-results .sub').first).to_contain_text(f'{len(items):,}개 문제')
    page.locator('#library-subject').select_option('재무회계')
    finance_count = page.evaluate("BANK_DATA.questions.filter(q=>q.eligible&&q.subject==='재무회계'&&BANK_DATA.explanations.items.some(n=>n.question_id===q.id)).length")
    expect(page.locator('.library-card')).to_have_count(min(20, finance_count))
    page.locator('#library-subject').select_option('')
    expect(page.locator('.library-card')).to_have_count(20)  # pagination, not a truncated data set

    rendered = page.evaluate("""() => {
        const before = localStorage.getItem('chagok.study.v1');
        const trigger = document.createElement('button');
        trigger.dataset.action = 'explanation';
        document.body.append(trigger);
        let count = 0;
        for (const n of BANK_DATA.explanations.items) {
            trigger.dataset.id = n.question_id;
            trigger.click();
            const body = document.querySelector('dialog .explanation-body');
            const fail = message => { throw Error(n.question_id + ': ' + message); };
            if (!body || body.querySelector('h3').textContent !== n.title) fail('title');
            const options = [...body.querySelectorAll('.option-reasons li')];
            const steps = [...body.querySelectorAll('.solution-steps li')];
            if (options.length !== 4 || steps.length !== n.steps.length) fail('coverage');
            n.option_notes.forEach((o, i) => {
                if (!options[i].textContent.includes(o.reason)) fail('option content');
            });
            n.steps.forEach((s, i) => {
                if (steps[i].textContent !== s) fail('step content');
            });
            if (!body.textContent.includes('공식 해설 아님')) fail('authorship');
            if (n.tax_law_year && !body.textContent.includes(`문항 적용 세법 ${n.tax_law_year}년`)) fail('tax year');
            document.querySelector('dialog [data-action=close-modal]').click();
            count++;
        }
        trigger.remove();
        if (localStorage.getItem('chagok.study.v1') !== before) throw Error('Preview changed study records');
        return count;
    }""")
    assert rendered == len(items)

    # Approved concept additions must reach the learner, including expandable
    # example solutions, while browsing remains read-only for study records.
    concept_state = page.evaluate('(k)=>localStorage.getItem(k)', KEY)
    for change in concept_changes:
        n, previous = change['after'], change['before']
        page.goto(URL + '#concept/' + n['part_id'])
        expect(page.locator('.note-page')).to_be_visible()
        for field in ('key_points','pitfalls'):
            for text in n[field][len(previous[field]):]:
                expect(page.locator('.note-page')).to_contain_text(text)
        for index, example in enumerate(n['examples'][len(previous['examples']):],start=len(previous['examples'])):
            box=page.locator('.note-page .example').nth(index)
            expect(box.locator('strong')).to_have_text(example['title'])
            expect(box).to_contain_text(example['setup'])
            box.locator('details summary').click()
            expect(box.locator('details li')).to_have_text(example['steps'])
            expect(box.locator('.example-answer')).to_have_text(example['answer'])
        assert page.evaluate('(k)=>localStorage.getItem(k)', KEY) == concept_state,n['id']

    for i, n in enumerate(interactive):
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
    pending = page.evaluate("BANK_DATA.questions.find(q=>q.eligible&&!BANK_DATA.explanations.items.some(n=>n.question_id===q.id)).id")
    page.locator('#library-query').fill(pending)
    expect(page.locator('[data-action=explanation]')).to_have_count(0)
    page.locator('[data-action=preview]').click()
    page.locator('dialog [data-action=single]').click()
    page.get_by_role('button', name='1번 선택', exact=True).click()
    page.locator('[data-action=grade]').click()
    expect(page.locator('.question-card .explanation-pending')).to_contain_text('준비 중')

    # Official-answer dispute notes appear only after grading and never change the official answer.
    page.goto(URL + '#library')
    disputed = '2025-09-080'
    page.locator('#library-query').fill(disputed)
    page.locator('[data-action=preview]').click()
    expect(page.locator('dialog .answer-dispute')).to_contain_text('공식 정답 이의 가능')
    page.locator('dialog [data-action=single]').click()
    if page.locator('#replace-session').count():
        page.locator('#replace-session').click()
    expect(page.locator('.question-card .answer-dispute')).to_have_count(0)
    page.get_by_role('button', name='1번 선택', exact=True).click()
    page.locator('[data-action=grade]').click()
    expect(page.locator('.question-card .answer-dispute')).to_contain_text('2012년')
    expect(page.locator('.question-card .answer-dispute small')).to_contain_text('공식 정답은 바꾸지 않았고')
    assert page.evaluate("BANK_DATA.questions.find(q=>q.id==='2025-09-080').answers.join()") == '2'
    adjudication_log = json.loads((R / 'reports/explanation-expansion.json').read_text())['answer_adjudication']
    adjudications = adjudication_log['records'] + adjudication_log.get('explained_item_records', [])
    resolved = {r['question_id']: r['verdict'] for r in adjudication_log.get('resolutions', [])}
    expected_notes = {r['question_id'] for r in adjudications if resolved.get(r['question_id'], r['verdict']) in
                      {'official_conflict', 'multiple_candidates', 'ambiguous_wording', 'deferred'}}
    assert set(page.evaluate("Object.keys(BANK_DATA.answerNotes)")) == expected_notes
    # Round 10 resolves the targeted interest ruling; the outsourcing question
    # still shows its explicit deferral. Official answers remain unchanged.
    if any(r['question_id'] == '2025-01-055' and r['verdict'] == 'official_supported' for r in adjudications):
        assert '2025-01-055' not in expected_notes
        assert ('2023-06-112' in expected_notes) == ('2023-06-112' not in resolved)
        assert page.evaluate("BANK_DATA.questions.find(q=>q.id==='2025-01-055').answers.join()") == '2'
    # Source basis labels say what the explanation was actually compared against.
    labels = {}
    for key, basis, subject in [('domestic', 'domestic', '세무회계'), ('ifrs', 'ifrs', '재무회계'),
                                ('weak', 'textbook', '재무회계'), ('cost', 'textbook', '원가관리회계')]:
        qid = page.evaluate("([b,s])=>BANK_DATA.questions.find(q=>BANK_DATA.explanationBasis[q.id]===b&&q.subject===s).id", [basis, subject])
        page.goto(URL + '#library')
        page.locator('#library-query').fill(qid)
        page.locator('[data-action=explanation]').first.click()
        chip = page.locator('dialog .note-badges .chip').first
        note = page.locator('dialog .basis-note')
        labels[key] = [chip.inner_text(), chip.get_attribute('class'), note.inner_text() if note.count() else '']
        page.locator('dialog [data-action=close-modal]').first.click()
    assert labels['domestic'][0].startswith('국내 법령·기준서 대조') and 'status-ok' in labels['domestic'][1] and not labels['domestic'][2]
    assert labels['ifrs'][0].startswith('IFRS 영문 원문 대조') and '한글 K-IFRS 원문 대조는 아니에요' in labels['ifrs'][2]
    assert labels['weak'][0].startswith('공개 교재·강의 대조') and 'status-neutral' in labels['weak'][1] and '시험 기준은' in labels['weak'][2]
    assert labels['cost'][0].startswith('공개 교재·강의 대조') and 'status-ok' in labels['cost'][1]
    # The wrong-answer notebook exposes the same note for a disputed item that has no explanation.
    page.goto(URL + '#wrong')
    page.locator('#library-query').fill(disputed)
    expect(page.locator('[data-action=explanation]')).to_have_count(0)
    page.locator('[data-action=answer-note]').click()
    expect(page.locator('dialog .answer-dispute')).to_contain_text('공식 정답 이의 가능')
    state_dispute = page.evaluate('(k)=>localStorage.getItem(k)', KEY)
    page.locator('dialog [data-action=close-modal]').first.click()
    assert page.evaluate('(k)=>localStorage.getItem(k)', KEY) == state_dispute

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
    assert len(state['active']['ids']) == len(items) and state['version'] == 1
    assert set(state['active']['ids']) == {n['question_id'] for n in items}
    assert state['results']['2026-01-006']['attempts'] == 1
    assert not errors, errors
    browser.close()
    print(f'PASS: all {len(items)} explanation bodies rendered; {len(interactive)} grading flows (original 30 + new part/concept/calculation coverage), {len(concept_changes)} enriched concept pages and new examples, no pre-grade reveal, 4 options, review status/year, reload, wrong notebook, related concepts, unchanged records, independent variants, pending content, mobile, explanation-only practice; no browser errors')
