"""Regression checks for state safety, focus/caret preservation, and malformed routes.

Each check uses its own browser context so saved learner history in other tests is untouched.
"""
import json
import os
import shutil
import sys
from playwright.sync_api import expect, sync_playwright
from test_home_polish import run_home_polish

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


def run_accessibility(browser, url=URL, only=None):
    """Actual keyboard focus plus persistent live-region mutations, not spoken SR output."""
    def ready(page, route='home'):
        page.goto(url + '#' + route)
        expect(page.locator('body')).to_have_attribute('data-route', route)

    def activate(page, selector):
        page.locator(selector).focus()
        page.keyboard.press('Enter')

    def seed(page, ids, bookmarks=None):
        page.evaluate("""([k,ids,bookmarks])=>localStorage.setItem(k,JSON.stringify({version:1,
          results:{},bookmarks,sessions:[],active:{id:'a11y',title:'a11y',ids,answers:{},
          index:0,startedAt:Date.now(),finishedAt:null}}))""", [KEY, ids, bookmarks or []])
        page.reload()
        expect(page.locator('body')).to_have_attribute('data-route', 'quiz')

    def groups(page):
        ready(page)
        for selector, attr, value in [
            ('[data-action=count][data-count="20"]', 'data-count', '20'),
            ('[data-action=subject][data-subject="세무회계"]', 'data-subject', '세무회계'),
        ]:
            activate(page, selector)
            assert page.evaluate('(a)=>document.activeElement.getAttribute(a)', attr) == value, selector
            page.keyboard.press('Enter')
            assert page.evaluate('(a)=>document.activeElement.getAttribute(a)', attr) == value, selector
        expect(page.locator('[data-action=count][data-count="20"]')).to_have_attribute('aria-pressed', 'true')
        ready(page, 'concepts')
        selector = '[data-action=concept-subject][data-subject="원가관리회계"]'
        activate(page, selector)
        expect(page.locator(selector)).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator(selector)).to_have_attribute('aria-pressed', 'true')
        ready(page, 'quiz')  # Seed a real question with both display modes.
        ids = page.evaluate('BANK_DATA.questions.filter(q=>q.eligible&&!q.originalOnly).slice(0,1).map(q=>q.id)')
        seed(page, ids)
        activate(page, '[data-action=question-view][data-view=image]')
        expect(page.locator('[data-action=question-view][data-view=image]')).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('[data-action=question-view][data-view=image]')).to_have_attribute('aria-pressed', 'true')
        # Numeric question navigation has the same shared action name.
        activate(page, '[data-action=choose][data-answer="2"]')
        expect(page.locator('[data-action=choose][data-answer="2"]')).to_be_focused()

    def modal_replace(page):
        ready(page, 'library')
        activate(page, '.library-card:first-child [data-action=preview]')
        activate(page, '#modal-body [data-action=concept-modal]')
        assert page.evaluate('document.querySelector("#modal-body").contains(document.activeElement)'), 'modal replacement lost focus'
        # Find a question with multiple concept tabs through real preview UI.
        page.keyboard.press('Escape')
        candidates = page.evaluate("BANK_DATA.questions.filter(q=>q.eligible&&q.secondary?.length).slice(0,30).map(q=>q.id)")
        for qid in candidates:
            page.locator('#library-query').fill(qid)
            activate(page, '.library-card:first-child [data-action=concept-modal]')
            if page.locator('#modal-body [role=tab]').count() > 1:
                tab = page.locator('#modal-body [role=tab]').nth(1)
                tab.focus()
                page.keyboard.press('Enter')
                expect(page.locator('#modal-body [role=tab][aria-selected=true]')).to_be_focused()
                break
            page.keyboard.press('Escape')
        else:
            raise AssertionError('multi-concept fixture not found')
        page.keyboard.press('Escape')
        activate(page, '.avatar')
        page.locator('#backup-file').set_input_files({'name':'backup.json','mimeType':'application/json',
            'buffer':json.dumps({'version':1,'results':{},'bookmarks':[],'sessions':[],'active':None}).encode()})
        expect(page.locator('#confirm-import')).to_be_visible()
        assert page.evaluate('document.querySelector("#modal-body").contains(document.activeElement)'), 'import confirmation lost focus'

    def bookmark_close(page):
        ready(page)
        ids = page.evaluate('BANK_DATA.questions.filter(q=>q.eligible&&q.representative).slice(0,1).map(q=>q.id)')
        page.evaluate('([k,ids])=>localStorage.setItem(k,JSON.stringify({version:1,results:{},bookmarks:ids,sessions:[],active:null}))', [KEY, ids])
        ready(page, 'bookmarks')
        page.reload()
        activate(page, '.library-card:first-child [data-action=preview]')
        activate(page, '#modal-body [data-action=bookmark]')
        page.keyboard.press('Escape')
        expect(page.locator('#library-results')).to_be_focused()
        expect(page.locator('.library-card')).to_have_count(0)
        # A surviving opener keeps the browser's normal return focus.
        ready(page, 'library')
        opener = '.library-card:first-child [data-action=preview]'
        activate(page, opener)
        page.keyboard.press('Escape')
        expect(page.locator(opener)).to_be_focused()

    def grading_live(page):
        ready(page)
        ids = page.evaluate("""()=>{const qs=BANK_DATA.questions.filter(q=>q.eligible&&!q.originalOnly);
          return [...qs.filter(q=>q.answers.includes(1)).slice(0,2),qs.find(q=>!q.answers.includes(1))].map(q=>q.id);}""")
        ready(page, 'quiz')
        seed(page, ids)
        # Persist outside #main, empty before grading, with one mutation per grade.
        expect(page.locator('#study-announcement')).to_have_count(1)
        assert page.evaluate('!document.querySelector("#main").contains(document.querySelector("#study-announcement"))')
        page.evaluate("""()=>{window.liveNode=document.querySelector('#study-announcement');window.liveMessages=[];
          new MutationObserver(()=>{if(liveNode.textContent)liveMessages.push(liveNode.textContent);})
            .observe(liveNode,{childList:true,characterData:true,subtree:true});}""")
        # Delay body arrival to prove it never announces the same grade twice.
        held = []
        page.route('**/assets/bank/explanations-*.js', lambda route: held.append(route))
        activate(page, '[data-action=choose][data-answer="1"]')
        activate(page, '[data-action=grade]')
        expect(page.locator('#study-announcement')).to_contain_text('공식 정답')
        expect(page.locator('#study-announcement')).to_have_attribute('aria-live', 'polite')
        assert page.evaluate('liveMessages.length') == 1
        expect(page.locator('.feedback[role=status]')).to_have_count(0)
        page.wait_for_function('document.querySelector("[data-explanation-id]")')
        # Pump pending request events, then release the subject script.
        page.wait_for_timeout(100)
        assert held, 'explanation request was not intercepted'
        for request in held:
            request.fulfill(response=request.fetch())
        expect(page.locator('.pick-reasons')).to_be_visible()
        activate(page, '[data-action=question-view][data-view=image]')
        _storage_event(page)
        assert page.evaluate('document.querySelector("#study-announcement")===liveNode&&liveMessages.length===1')
        # A second grade with identical wording still makes a fresh announcement.
        activate(page, '[data-action=next]')
        activate(page, '[data-action=choose][data-answer="1"]')
        activate(page, '[data-action=grade]')
        expect(page.locator('.feedback')).to_be_visible()
        page.wait_for_function('liveMessages.length===2')
        assert page.evaluate('liveMessages[0]===liveMessages[1]'), 'same-answer fixture must repeat identical feedback'
        activate(page, '[data-action=next]')
        activate(page, '[data-action=choose][data-answer="1"]')
        activate(page, '[data-action=grade]')
        page.wait_for_function('liveMessages.length===3')
        expect(page.locator('#study-announcement')).to_contain_text('내가 고른 답 ①')
        expect(page.locator('.feedback.wrong')).to_be_visible()

    def search_live(page):
        ready(page, 'library')
        expect(page.locator('#study-announcement')).to_have_count(1)
        page.evaluate("""()=>{window.liveMessages=[];window.liveNode=document.querySelector('#study-announcement');
          new MutationObserver(()=>{if(liveNode.textContent)liveMessages.push(liveNode.textContent);})
            .observe(liveNode,{childList:true,characterData:true,subtree:true});}""")
        page.locator('#library-query').focus()
        page.keyboard.type('2024-11', delay=20)
        page.wait_for_function('liveMessages.length===1')
        expected = page.locator('#library-results .section-head .sub').inner_text().split('·')[0].strip()
        expect(page.locator('#study-announcement')).to_contain_text(expected)
        expect(page.locator('#library-query')).to_be_focused()
        page.locator('#library-subject').select_option('세무회계')
        page.wait_for_function('liveMessages.length===2')
        expected = page.locator('#library-results .section-head .sub').inner_text().split('·')[0].strip()
        expect(page.locator('#study-announcement')).to_contain_text(expected)
        page.locator('#library-part').select_option('V01')
        page.wait_for_function('liveMessages.length===3')
        page.locator('#library-explanations').check()
        page.wait_for_function('liveMessages.length===4')
        page.locator('#library-query').fill('아무결과없는검색XYZ')
        page.wait_for_function('liveMessages.length===5')
        expect(page.locator('#study-announcement')).to_contain_text('0개 문제')
        # IME composition updates the list but waits until the syllable is committed.
        page.locator('#library-query').evaluate("""e=>{e.value='재고';
          e.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true}));}""")
        page.wait_for_timeout(500)
        assert page.evaluate('liveMessages.length') == 5
        page.locator('#library-query').evaluate("e=>e.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true}))")
        page.wait_for_function('liveMessages.length===6')
        # Navigating away cancels pending result announcements.
        page.locator('#library-query').fill('재고')
        page.locator('.brand').click()
        expect(page.locator('.home-head')).to_be_visible()
        page.wait_for_timeout(500)
        assert page.evaluate('liveMessages.length') == 6

    cases = {'groups':groups, 'modal':modal_replace, 'bookmark':bookmark_close,
             'grading':grading_live, 'search':search_live}
    for name, check in cases.items():
        if only and name != only:
            continue
        context, page, errors = _context(browser)
        try:
            check(page)
            assert not errors, errors
        finally:
            context.close()
    return 'keyboard groups/modal replacement/bookmark return focus; persistent grade-once and debounced result live regions'


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
    # Preview keeps review notes (which name the official answer) inside the folded answer section.
    context, page, errors = _context(browser, viewport={'width': 360, 'height': 800})
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    noted = page.evaluate("BANK_DATA.questions.find(q=>q.id==='2026-06-054')?'2026-06-054':null")
    assert noted, 'expected question with a review note'
    page.goto(url + '#library')
    page.locator('#library-query').fill(noted)
    page.locator('[data-action=preview]').first.click()
    expect(page.locator('dialog .answer-dispute')).to_be_hidden()
    page.locator('dialog details.instructions summary', has_text='공식 정답 확인').click()
    expect(page.locator('dialog .answer-dispute')).to_be_visible()
    page.keyboard.press('Escape')
    # The largest text size reaches explanation/concept modals and pick reasons without double zoom or overflow.
    page.evaluate("localStorage.setItem('chagok.size','xl')")
    page.goto(url + '#concept/F02')
    page.reload()
    expect(page.locator('.note-page')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'concept page scrolls sideways at xl'
    page.goto(url + '#library')
    page.locator('#library-query').fill('')
    page.locator('.library-card [data-action=explanation]').first.click()
    page.evaluate('async()=>{await BANK_DATA_LOADER.all();}')
    expect(page.locator('#modal-body>.explanation-body .note-summary')).to_be_visible()
    assert abs(page.evaluate("document.querySelector('#modal-body>.explanation-body').currentCSSZoom") - 1.25) < 0.01
    page.keyboard.press('Escape')
    page.locator('.library-card [data-action=concept-modal]').first.click()
    assert abs(page.evaluate("document.querySelector('#modal-body .note-zoom').currentCSSZoom") - 1.25) < 0.01
    page.keyboard.press('Escape')
    assert not errors, errors
    context.close()

    # Subject counts in the bookmark filter follow un-bookmarking.
    context, page, errors = _context(browser)
    page.goto(url)
    expect(page.locator('.subject-card').first).to_be_visible()
    pair = page.evaluate("['재무회계','세무회계'].map(s=>BANK_DATA.questions.find(q=>q.eligible&&q.representative&&q.subject===s).id)")
    page.evaluate("([k,b])=>localStorage.setItem(k,JSON.stringify({version:1,results:{},bookmarks:b,sessions:[],active:null}))", [KEY, pair])
    page.goto(url + '#bookmarks')
    page.reload()
    expect(page.locator('#library-subject option', has_text='세무회계 (1)')).to_have_count(1)
    page.locator(f'.library-card [data-action=bookmark][data-id="{pair[1]}"]').click()
    expect(page.locator('#library-subject option', has_text='세무회계 (0)')).to_have_count(1)
    assert not errors, errors
    context.close()
    run_home_polish(browser, url)
    accessibility = run_accessibility(browser, url)
    return accessibility + '; preview hides review notes until the answer is opened, xl text in modals/pick reasons, no concept overflow at xl, live bookmark subject counts, stale cross-tab finish dialog, resume position after removed ids, malformed hash, unreadable/newer record preservation and download, re-render keeps details/focus/caret, table arrow keys, bookmark focus, quota pruning'


if __name__ == '__main__':
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
        try:
            print('PASS: ' + (run_accessibility(browser, only=sys.argv[2] if len(sys.argv)>2 else None)
                             if '--accessibility' in sys.argv else run_robustness(browser)))
        finally:
            browser.close()
