"""Regression checks for spaced review (separate chagok.review.v1 key).

Review schedules use Leitner boxes 1-5 with 1/3/7/14/30-day intervals. The study record
chagok.study.v1 must keep its exact format; every check runs in an isolated context.
"""
import json
import os
import shutil
import time
from playwright.sync_api import expect, sync_playwright

KEY = 'chagok.study.v1'
RKEY = 'chagok.review.v1'
DAY = 86400000
URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000/jaegyeong/').rstrip('/') + '/'
STUDY_FIELDS = {'version', 'results', 'bookmarks', 'sessions', 'active'}


def run_spaced_review(browser, url=URL):
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, service_workers='block', accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    qs = page.evaluate("BANK_DATA.questions.filter(q=>q.eligible&&q.representative).slice(0,6).map(q=>({id:q.id,answer:q.answers[0]}))")
    ids = [q['id'] for q in qs]
    answer = {q['id']: q['answer'] for q in qs}

    def seed(results, items=None, active=None):
        page.evaluate("""([k,rk,results,items,active])=>{localStorage.setItem(k,JSON.stringify({version:1,results,bookmarks:[],sessions:[],active}));
          if(items===null)localStorage.removeItem(rk);else localStorage.setItem(rk,JSON.stringify({version:1,items}));}""", [KEY, RKEY, results, items, active])
        page.goto(url + '#home')
        page.reload()
        expect(page.locator('.home-head')).to_be_visible()

    def review():
        raw = page.evaluate('k=>localStorage.getItem(k)', RKEY)
        return json.loads(raw)['items'] if raw else {}

    def study():
        return json.loads(page.evaluate('k=>localStorage.getItem(k)', KEY))

    def solve(qid, correct):
        pick = answer[qid] if correct else answer[qid] % 4 + 1
        seed_state = study()
        seed_state['active'] = {'id': 'rv-' + qid, 'title': 'rv', 'ids': [qid], 'answers': {}, 'index': 0, 'startedAt': int(time.time() * 1000), 'finishedAt': None}
        page.evaluate('([k,v])=>localStorage.setItem(k,JSON.stringify(v))', [KEY, seed_state])
        page.goto(url + '#quiz')
        page.reload()
        page.locator(f'[data-action="choose"][data-answer="{pick}"]').click()
        page.locator('[data-action=grade]').click()
        expect(page.locator('.feedback')).to_contain_text('다음 복습은')

    now = int(time.time() * 1000)
    # Existing records without a schedule are derived (wrong: 1 day, correct: 3 days) without writing anything.
    old = now - 5 * DAY
    seed({ids[0]: {'attempts': 1, 'correct': 0, 'lastCorrect': False, 'lastAnswer': 1, 'updatedAt': old},
          ids[1]: {'attempts': 1, 'correct': 1, 'lastCorrect': True, 'lastAnswer': 1, 'updatedAt': old},
          ids[2]: {'attempts': 1, 'correct': 1, 'lastCorrect': True, 'lastAnswer': 1, 'updatedAt': now}}, None)
    expect(page.locator('[data-action=practice-review]')).to_contain_text('오늘 복습 2문제')
    assert page.evaluate('k=>localStorage.getItem(k)', RKEY) is None, 'deriving must not write'
    page.locator('[data-action=practice-review]').click()
    active = study()['active']
    assert active['title'] == '오늘의 복습' and active['ids'] == [ids[0], ids[1]], active

    # Leitner moves: due + correct → next box; early + correct → same box; wrong → box 1 / 1 day.
    seed({}, {ids[3]: {'box': 3, 'due': now - DAY}, ids[4]: {'box': 3, 'due': now + 5 * DAY}, ids[5]: {'box': 4, 'due': now - DAY}})
    solve(ids[3], True)
    solve(ids[4], True)
    solve(ids[5], False)
    items = review()
    for qid, box, days in [(ids[3], 4, 14), (ids[4], 3, 7), (ids[5], 1, 1)]:
        assert items[qid]['box'] == box, (qid, items[qid])
        assert abs(items[qid]['due'] - (time.time() * 1000 + days * DAY)) < 120000, (qid, items[qid])
    assert set(study()) == STUDY_FIELDS, 'study record format changed'

    # Nothing due today → the home shows the next review date instead of a start button.
    seed({ids[0]: {'attempts': 1, 'correct': 1, 'lastCorrect': True, 'lastAnswer': 1, 'updatedAt': now}}, {ids[0]: {'box': 2, 'due': now + 2 * DAY}})
    expect(page.locator('.next-tile-info')).to_contain_text('오늘 복습 완료')
    expect(page.locator('[data-action=practice-review]')).to_have_count(0)

    # Backups carry the schedule; restoring an older backup without it clears stale schedules.
    seed({ids[0]: {'attempts': 1, 'correct': 1, 'lastCorrect': True, 'lastAnswer': 1, 'updatedAt': now}}, {ids[0]: {'box': 5, 'due': now + 30 * DAY}})
    page.locator('.avatar').click()
    with page.expect_download() as info:
        page.locator('[data-action=export]').click()
    with open(info.value.path(), encoding='utf-8') as fh:
        backup = json.load(fh)
    assert backup['review'] == {'version': 1, 'items': {ids[0]: {'box': 5, 'due': now + 30 * DAY}}}
    page.keyboard.press('Escape')
    for payload, expected in [(backup, backup['review']['items']), ({k: v for k, v in backup.items() if k != 'review'}, {})]:
        seed({}, {ids[1]: {'box': 1, 'due': now}})
        page.locator('.avatar').click()
        path = str(info.value.path()) + '.restore.json'
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False)
        page.locator('#backup-file').set_input_files(path)
        page.locator('#confirm-import').click()
        assert review() == expected, (review(), expected)
        assert set(study()) == STUDY_FIELDS

    # Unreadable schedules are preserved and replaced by an empty one; other tabs pick up changes.
    page.evaluate("k=>localStorage.setItem(k,'{\"version\":1,\"items\":')", RKEY)
    page.reload()
    expect(page.locator('.home-head')).to_be_visible()
    assert page.evaluate("k=>localStorage.getItem(k+'.unreadable')", RKEY) == '{"version":1,"items":'
    seed({ids[0]: {'attempts': 1, 'correct': 1, 'lastCorrect': True, 'lastAnswer': 1, 'updatedAt': now}}, {})
    other = context.new_page()
    other.goto(url)
    expect(other.locator('.home-head')).to_be_visible()
    page.evaluate('([k,v])=>localStorage.setItem(k,v)', [RKEY, json.dumps({'version': 1, 'items': {ids[0]: {'box': 1, 'due': now - 1000}}})])
    expect(other.locator('[data-action=practice-review]')).to_contain_text('오늘 복습 1문제')
    assert not errors, errors
    context.close()
    return 'derived schedule without writes, due-ordered review session, Leitner box moves, next-date tile, backup/restore with and without schedule, unreadable schedule preserved, cross-tab update, unchanged study schema'


if __name__ == '__main__':
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
        try:
            print('PASS: ' + run_spaced_review(browser))
        finally:
            browser.close()
