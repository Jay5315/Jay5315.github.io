"""Regression checks for state safety, focus/caret preservation, and malformed routes.

Each check uses its own browser context so saved learner history in other tests is untouched.
"""
import json
import os
import shutil
from playwright.sync_api import expect, sync_playwright

KEY = 'chagok.study.v1'
URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000/jaegyeong/').rstrip('/') + '/'


def _context(browser, **kw):
    context = browser.new_context(service_workers='block', **kw)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    return context, page, errors


def _storage_event(page):
    # The same event another tab's save would deliver.
    page.evaluate("k=>dispatchEvent(new StorageEvent('storage',{key:k,newValue:localStorage.getItem(k)}))", KEY)


def run_robustness(browser, url=URL):
    # 1. A malformed percent escape in the hash falls back to home instead of breaking the app.
    context, page, errors = _context(browser)
    page.goto(url + '#%')
    expect(page.locator('.home-head')).to_be_visible()
    assert not errors, errors
    context.close()

    # 2. An unreadable record is preserved before the first new save; a newer-format record is never overwritten.
    context, page, errors = _context(browser)
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    broken = '{"version":1,"results":{"2022-01-001":{"attempts":5'
    page.evaluate('([k,v])=>localStorage.setItem(k,v)', [KEY, broken])
    page.reload()
    expect(page.locator('#toast')).to_contain_text('따로 보관')
    page.goto(url + '#library')
    page.locator('.library-card [data-action=bookmark]').first.click()
    assert page.evaluate("k=>localStorage.getItem(k+'.unreadable')", KEY) == broken
    assert json.loads(page.evaluate('k=>localStorage.getItem(k)', KEY))['bookmarks'], 'new record should still save'
    page.locator('.avatar').click()
    with page.expect_download() as info:
        page.locator('[data-action=export-unreadable]').click()
    with open(info.value.path(), encoding='utf-8') as fh:
        assert json.load(fh) == {KEY + '.unreadable': broken}, 'preserved record must download verbatim'
    page.keyboard.press('Escape')
    future = json.dumps({'version': 2, 'results': {}, 'bookmarks': [], 'sessions': [], 'futureField': True})
    page.evaluate('([k,v])=>localStorage.setItem(k,v)', [KEY, future])
    page.reload()
    page.goto(url + '#library')
    page.locator('.library-card [data-action=bookmark]').first.click()
    assert page.evaluate('k=>localStorage.getItem(k)', KEY) == future, 'newer-format record was overwritten'
    assert not errors, errors
    context.close()

    # 3/5. Quiz re-renders keep open sections and link focus; arrow keys in a scrollable table do not change question.
    context, page, errors = _context(browser, viewport={'width': 375, 'height': 800})
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    ids = page.evaluate("['2022-11-095',BANK_DATA.questions.find(q=>q.eligible&&q.id!=='2022-11-095').id]")
    page.evaluate("([k,ids])=>{localStorage.setItem(k,JSON.stringify({version:1,results:{},bookmarks:[],sessions:[],active:{id:'rb',title:'rb',ids,answers:{},index:0,startedAt:Date.now(),finishedAt:null}}));}", [KEY, ids])
    page.goto(url + '#quiz')
    page.reload()
    wrap = page.locator('.question-text .q-table-wrap').first
    expect(wrap).to_be_visible()
    wrap.evaluate('e=>{e.tabIndex=0;e.focus();}')
    page.keyboard.press('ArrowRight')
    assert page.evaluate('k=>JSON.parse(localStorage.getItem(k)).active.index', KEY) == 0
    details = page.locator('.question-card details').first
    details.locator('summary').click()
    assert details.evaluate('d=>d.open')
    summary_text = details.locator('summary').inner_text()
    link = page.locator('.question-card a[href]').first
    link.focus()
    href = link.get_attribute('href')
    _storage_event(page)
    reopened = page.locator('.question-card details', has=page.locator('summary', has_text=summary_text)).first
    assert reopened.evaluate('d=>d.open'), 'open section collapsed after re-render'
    assert page.evaluate('document.activeElement.getAttribute("href")') == href, 'link focus lost after re-render'
    assert not errors, errors
    context.close()

    # 4/6. Cross-tab updates keep the search caret; removing a bookmark keeps focus in the list.
    context, page, errors = _context(browser)
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    marks = page.evaluate("BANK_DATA.questions.filter(q=>q.eligible&&q.representative).slice(0,2).map(q=>q.id)")
    page.evaluate("([k,b])=>localStorage.setItem(k,JSON.stringify({version:1,results:{},bookmarks:b,sessions:[],active:null}))", [KEY, marks])
    page.goto(url + '#bookmarks')
    page.reload()
    query = page.locator('#library-query')
    query.fill('재고')
    query.evaluate('e=>e.setSelectionRange(1,1)')
    _storage_event(page)
    assert page.evaluate("[document.activeElement.id,document.activeElement.selectionStart,document.activeElement.value]") == ['library-query', 1, '재고']
    query.fill('')
    page.locator('.library-card [data-action=bookmark]').first.focus()
    page.keyboard.press('Enter')
    expect(page.locator('.library-card')).to_have_count(1)
    assert page.evaluate('document.activeElement.id') == 'library-results'
    assert not errors, errors
    context.close()

    # 7. When storage is full, the oldest finished sessions are dropped so new progress still saves.
    context, page, errors = _context(browser)
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    all_ids = page.evaluate('BANK_DATA.questions.filter(q=>q.eligible).map(q=>q.id)')
    page.evaluate("""([k,ids])=>{const sessions=[];for(let i=0;i<12;i++)sessions.push({id:'s'+i,title:'t'+i,ids,answers:{},index:0,startedAt:i,finishedAt:i+1});
      localStorage.setItem(k,JSON.stringify({version:1,results:{},bookmarks:[],sessions,active:null}));
      let size=1<<22;while(size>=1){try{localStorage.setItem('rb.filler',(localStorage.getItem('rb.filler')||'')+'x'.repeat(size));}catch(e){size>>=1;}}}""", [KEY, all_ids])
    page.reload()
    page.goto(url + '#library')
    page.locator('.library-card [data-action=bookmark]').first.click()
    saved = json.loads(page.evaluate('k=>localStorage.getItem(k)', KEY))
    assert saved['bookmarks'] and len(saved['sessions']) < 12, len(saved['sessions'])
    assert saved['sessions'][0]['id'] == 's0', 'newest session must be kept'
    page.evaluate("localStorage.removeItem('rb.filler')")
    assert not errors, errors
    context.close()
    # Cross-tab: a finish dialog opened for one session never ends a session another tab started.
    context, page, errors = _context(browser)
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    three = page.evaluate("BANK_DATA.questions.filter(q=>q.eligible&&q.representative).slice(0,3).map(q=>q.id)")
    seed = "([k,ids,id])=>localStorage.setItem(k,JSON.stringify({version:1,results:{},bookmarks:[],sessions:[],active:{id,title:id,ids,answers:{},index:0,startedAt:Date.now(),finishedAt:null}}))"
    page.evaluate(seed, [KEY, three, 'old'])
    other = context.new_page()
    other.goto(url + '#quiz')
    page.goto(url + '#quiz')
    page.reload()
    page.locator('[data-action=finish]').click()
    expect(page.locator('[data-action=finish-now]')).to_be_visible()
    other.evaluate(seed, [KEY, three, 'new'])
    expect(page.locator('dialog[open]')).to_have_count(0)
    assert page.evaluate('k=>JSON.parse(localStorage.getItem(k)).active.id', KEY) == 'new'
    assert not errors, errors
    context.close()

    # Resuming after a rebuild removed an id keeps the learner on the question they were viewing.
    context, page, errors = _context(browser)
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    three = page.evaluate("BANK_DATA.questions.filter(q=>q.eligible&&q.representative).slice(0,3).map(q=>q.id)")
    page.evaluate("([k,ids])=>localStorage.setItem(k,JSON.stringify({version:1,results:{},bookmarks:[],sessions:[],active:{id:'gap',title:'gap',ids,answers:{},index:2,startedAt:Date.now(),finishedAt:null}}))", [KEY, [three[0], '1999-01-999', three[1], three[2]]])
    page.goto(url + '#quiz')
    page.reload()
    expect(page.locator('.quiz-top .sub')).to_contain_text('2 / 3')
    assert not errors, errors
    context.close()
    return 'stale cross-tab finish dialog, resume position after removed ids, malformed hash, unreadable/newer record preservation and download, re-render keeps details/focus/caret, table arrow keys, bookmark focus, quota pruning'


if __name__ == '__main__':
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
        try:
            print('PASS: ' + run_robustness(browser))
        finally:
            browser.close()
