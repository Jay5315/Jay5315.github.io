"""Exercise the learning app through real UI and persistence (Chromium)."""
from pathlib import Path
import json,shutil,os
from playwright.sync_api import sync_playwright,expect
R=Path(__file__).resolve().parents[1]
URL=os.environ.get('APP_BASE_URL','http://127.0.0.1:8000/jaegyeong/').rstrip('/')+'/'
ARTIFACTS=Path(os.environ.get('TEST_ARTIFACT_DIR',str(R/'_artifacts')))
ARTIFACTS.mkdir(parents=True,exist_ok=True)
KEY='chagok.study.v1'
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'))
 context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
 page=context.new_page();errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(URL);expect(page.locator('.subject-card')).to_have_count(3)
 def state():return page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY)
 def active_q():return page.evaluate('(k)=>{const s=JSON.parse(localStorage.getItem(k)).active;return BANK_DATA.questions.find(q=>q.id===s.ids[s.index])}',KEY)
 def goto(route):page.goto(URL+'#'+route);page.wait_for_timeout(100)
 def choose(n):page.get_by_role('button',name=f'{n}번 선택',exact=True).click();page.locator('[data-action=grade]').click()
 # Specific part, count, order and classification eligibility.
 page.locator('[data-action=subject][data-subject="재무회계"]').click()
 page.locator('#setup-part').select_option('F03')
 page.locator('[data-action=count][data-count="10"]').click()
 page.locator('#setup-random').uncheck();page.locator('#setup-review').check()
 page.locator('[data-action=start]').click();expect(page.locator('.question-card')).to_be_visible()
 s=state();assert len(s['active']['ids'])==10
 assert page.evaluate('(ids)=>ids.every(id=>{const q=BANK_DATA.questions.find(q=>q.id===id);return q.part==="F03"&&!q.review&&q.representative&&q.eligible})',s['active']['ids'])
 q=active_q();first=q['id'];bad=next(n for n in [1,2,3,4] if n not in q['answers'])
 page.locator('[data-action=bookmark]').click();choose(bad)
 expect(page.locator('.feedback')).to_contain_text('오답 노트에 담았어요')
 assert state()['results'][first]['attempts']==1
 page.reload();expect(page.locator('.feedback')).to_be_visible();assert state()['results'][first]['attempts']==1
 page.locator('[data-action=next]').click();second=active_q();choose(second['answers'][0])
 page.locator('[data-action=home]').click();expect(page.locator('.resume')).to_be_visible()
 page.locator('[data-action=resume]').click();assert state()['active']['index']==1
 page.locator('[data-action=finish]').click();expect(page.locator('dialog')).to_contain_text('8문제가 남았어요')
 page.locator('[data-action=finish-now]').click();expect(page.locator('.result-hero')).to_be_visible()
 assert len(state()['sessions'])==1 and state()['active'] is None
 assert page.locator('.result-row').count()==10
 # Wrong-only replay clears latest wrong state, preserving total attempts/history.
 page.locator('[data-action=retry]').click();assert state()['active']['ids']==[first]
 choose(active_q()['answers'][0]);page.locator('[data-action=next]').click()
 assert state()['results'][first]['lastCorrect'] and state()['results'][first]['attempts']==2
 goto('wrong');expect(page.locator('.empty')).to_contain_text('복습할 오답이 없어요')
 goto('bookmarks');expect(page.locator('.library-card')).to_have_count(1)
 # Search, preview and both accepted official answers.
 for answer in [1,4]:
  goto('library');page.locator('#library-query').fill('2026-07-026');expect(page.locator('.library-card')).to_have_count(1)
  page.locator('[data-action=preview]').click();page.locator('[data-action=single]').click();expect(page.locator('.question-card')).to_be_visible()
  assert active_q()['id']=='2026-07-026'
  expect(page.locator('.question-text[data-correct]')).to_have_count(0)
  page.locator('#main').focus();page.keyboard.press(str(answer));page.keyboard.press('Enter')
  expect(page.locator('.question-text')).to_have_attribute('data-correct','1 4');expect(page.locator('.question-text')).to_have_attribute('data-picked',str(answer))
  marked=page.evaluate("[...document.querySelectorAll('.question-text .q-choice')].map(e=>getComputedStyle(e).backgroundColor)")
  assert marked[0]==marked[3]!=marked[1]==marked[2],marked
  expect(page.locator('.feedback')).to_contain_text('정답이에요')
  assert '복수 정답' in page.locator('.feedback').inner_text()
  page.locator('[data-action=next]').click()
 assert state()['results']['2026-07-026']['correct']==2
 goto('library');page.locator('#library-query').fill('2024-09-063');expect(page.locator('.library-card')).to_have_count(0)
 # A finished session spanning several parts shows a per-part breakdown, weakest part first.
 page.evaluate("""k=>{const s=JSON.parse(localStorage.getItem(k));const qs=BANK_DATA.questions.filter(q=>q.eligible!==false&&q.representative);const a=qs.find(q=>q.part==='F03'),b=qs.find(q=>q.part==='F04');
  s.sessions.unshift({id:'parts-test',title:'parts',ids:[a.id,b.id],answers:{[a.id]:a.answers[0],[b.id]:b.answers[0]%4+1},index:1,startedAt:Date.now()-720000,finishedAt:Date.now()});localStorage.setItem(k,JSON.stringify(s));}""",KEY)
 goto('result/parts-test');page.reload();expect(page.locator('.part-result')).to_have_count(2)
 assert '12분 소요' in page.locator('.result-hero .sub').inner_text()
 expect(page.locator('.part-result').first).to_contain_text('0/1');expect(page.locator('.part-result').last).to_contain_text('1/1 · 100%')
 page.evaluate("k=>{const s=JSON.parse(localStorage.getItem(k));s.sessions=s.sessions.filter(x=>x.id!=='parts-test');localStorage.setItem(k,JSON.stringify(s));}",KEY);goto('library');page.reload()
 # Wrong-answer notes list the most recently missed question first.
 saved=page.evaluate("k=>localStorage.getItem(k)",KEY)
 old_new=page.evaluate("""k=>{const s=JSON.parse(localStorage.getItem(k));const qs=BANK_DATA.questions.filter(q=>q.eligible!==false&&q.representative).sort((a,b)=>a.id.localeCompare(b.id));const a=qs[0],b=qs[qs.length-1];
  s.results={[a.id]:{attempts:1,correct:0,lastCorrect:false,lastAnswer:a.answers[0]%4+1,updatedAt:2000},[b.id]:{attempts:1,correct:0,lastCorrect:false,lastAnswer:b.answers[0]%4+1,updatedAt:1000}};localStorage.setItem(k,JSON.stringify(s));return [a.id,b.id];}""",KEY)
 goto('wrong');page.reload();expect(page.locator('.library-card')).to_have_count(2);expect(page.locator('.section-head .sub').first).to_contain_text('최근에 틀린 순')
 expect(page.locator('#nav a[href="#wrong"]')).to_have_attribute('aria-label','오답 노트 2문제')
 assert page.evaluate("[...document.querySelectorAll('.library-card [data-action=preview]')].map(b=>b.dataset.id)")==old_new
 page.evaluate("([k,v])=>localStorage.setItem(k,v)",[KEY,saved]);goto('library');page.reload()
 # Search terms are highlighted in result previews (whitespace-insensitive, special characters escaped).
 page.locator('#library-query').fill('보고기간 후사건');expect(page.locator('.library-card h3 mark').first).to_be_visible()
 assert all(''.join(t.split()) in {'보고기간','후사건','보고기간후사건'} for t in page.locator('.library-card h3 mark').all_inner_texts())
 for q in ['(주)','a+b','[1]','<b>']:
  page.locator('#library-query').fill(q);assert page.locator('.library-card h3 b').count()==0
 page.locator('#library-query').fill('')
 # Backup download is actual JSON, restore requires explicit confirmation.
 page.locator('.avatar').click()
 with page.expect_download() as download:page.locator('[data-action=export]').click()
 file=ARTIFACTS/'test-backup.json';download.value.save_as(str(file));backup=json.loads(file.read_text());assert first in backup['bookmarks']
 page.locator('[data-action=close-modal]').click();goto('bookmarks');page.locator('[data-action=bookmark]').click();assert not state()['bookmarks']
 page.locator('.avatar').click();page.locator('#backup-file').set_input_files({'name':'invalid.json','mimeType':'application/json','buffer':b'{"hello":true}'})
 expect(page.locator('#toast')).to_contain_text('올바른 백업 파일이 아니에요')
 page.locator('#backup-file').set_input_files(str(file));expect(page.locator('dialog')).to_contain_text('백업 기록을 복원할까요')
 assert not state()['bookmarks'];page.locator('#confirm-import').click();assert first in state()['bookmarks']
 file.unlink()
 # Concept notes: index, written/pending parts, related links, part study, quiz/wrong/preview entry points.
 def start_or_replace():
  if page.locator('#replace-session').count():page.locator('#replace-session').click()
 goto('concepts');expect(page.locator('.concept-card')).to_have_count(74)
 notes=page.evaluate('BANK_DATA.concepts.notes.length');expect(page.locator('.concept-card:not(.pending)')).to_have_count(notes)
 # Every registered note renders its actual examples and verified source locators.
 before_notes=state()
 for note in page.evaluate('BANK_DATA.concepts.notes'):
  goto('concept/'+note['part_id'])
  expect(page.locator('h1')).to_have_text(note['title'])
  expect(page.locator('.note-summary')).to_have_text(note['summary'])
  expect(page.locator('.note-page .example')).to_have_count(len(note['examples']))
  for source in note['sources']:expect(page.locator('.source-box')).to_contain_text(source['locator'])
  if note.get('unchecked_points'):expect(page.locator('.unchecked-box')).to_be_visible()
 assert state()==before_notes,'Reading concept notes changed study records'
 goto('concepts')
 page.locator('[data-action=concept-subject][data-subject="세무회계"]').click();expect(page.locator('.concept-card')).to_have_count(28)
 goto('concept/F01');expect(page.locator('.note-page .note-summary')).to_be_visible()
 goto('concept/C11');expect(page.locator('.note-page h3').first).to_contain_text('핵심 개념')
 expect(page.locator('.year-table thead')).to_contain_text('2026년');expect(page.locator('.source-box')).to_contain_text('법인세법')
 page.locator('.note-page [data-action=concept][data-id=C02]').click();expect(page.locator('h1')).to_contain_text('세무조정과 소득처분')
 page.locator('.page-title [data-action=study-part]').click();start_or_replace();expect(page.locator('.question-card')).to_be_visible()
 ids=state()['active']['ids'];assert ids and page.evaluate('(ids)=>ids.every(id=>BANK_DATA.questions.find(q=>q.id===id).part==="C02")',ids)
 # Opening and closing the related-concept dialog keeps position and the ungraded selection.
 page.get_by_role('button',name='1번 선택',exact=True).click();idx=state()['active']['index']
 page.locator('.question-card [data-action=concept-modal]').click();expect(page.locator('dialog')).to_contain_text('이 문제의 해설이 아니라')
 expect(page.locator('dialog .note-title')).to_contain_text('세무조정과 소득처분')
 page.locator('dialog [data-action=close-modal]').first.click();expect(page.locator('dialog')).not_to_be_visible()
 expect(page.get_by_role('button',name='1번 선택',exact=True)).to_have_attribute('aria-pressed','true');assert state()['active']['index']==idx
 # A question with an explicit tax-law year highlights that year in the note table.
 qid=page.evaluate('BANK_DATA.questions.find(q=>q.eligible&&q.part==="C11"&&q.taxYear===2025).id')
 goto('library');page.locator('#library-query').fill(qid);page.locator('.library-card [data-action=concept-modal]').click()
 expect(page.locator('dialog .notice.ok')).to_contain_text('2025년');expect(page.locator('dialog .year-table th.hi')).to_contain_text('2025년')
 page.locator('dialog [data-action=close-modal]').first.click()
 # Wrong-answer review links to the part note; newly written financial notes open too.
 page.locator('.library-card [data-action=preview]').click();page.locator('[data-action=single]').click();start_or_replace()
 q=active_q();choose(next(n for n in [1,2,3,4] if n not in q['answers']))
 goto('wrong');card=page.locator('.library-card').filter(has_text=q['exam'])
 card.first.locator('[data-action=concept-modal]').click();expect(page.locator('dialog .note-title')).to_contain_text('과세표준')
 page.locator('dialog a[data-action=close-modal-link]').click();expect(page.locator('h1')).to_contain_text('법인세 과세표준')
 financial=page.evaluate('BANK_DATA.questions.find(q=>q.eligible&&q.part==="F01").id')
 goto('library');page.locator('#library-query').fill(financial);page.locator('.library-card [data-action=concept-modal]').click()
 expect(page.locator('dialog .note-summary')).to_be_visible()
 expect(page.locator('dialog .source-box')).to_contain_text('IAS1')
 page.locator('dialog [data-action=close-modal]').first.click()
 # Keep the missing-note regression using an isolated fixture now that all 74 parts are written.
 fixture=json.loads((R/'assets/bank-data.js').read_text()[len('window.BANK_DATA='):-2])
 fixture['concepts']['notes']=[n for n in fixture['concepts']['notes'] if n['part_id']!='F01']
 pending_context=browser.new_context()
 pending_context.route('**/bank-data.js',lambda route:route.fulfill(
  status=200,content_type='application/javascript',body='window.BANK_DATA='+json.dumps(fixture,ensure_ascii=False)+';'))
 pending_page=pending_context.new_page();pending_page.on('pageerror',lambda e:errors.append(str(e)))
 pending_page.goto(URL+'#concept/F01');expect(pending_page.locator('.empty')).to_contain_text('준비 중')
 pending_page.goto(URL+'#library');pending_page.locator('#library-query').fill(financial)
 pending_page.locator('.library-card [data-action=concept-modal]').click()
 expect(pending_page.locator('dialog')).to_contain_text('준비 중');pending_context.close()
 # Text view splits ①-④ into blocks without changing the question text; arrow keys move between questions.
 qid=page.evaluate("BANK_DATA.questions.find(q=>q.eligible&&q.representative&&q.graphics==='none'&&!q.originalOnly&&[1,2,3,4].every(n=>q.text.split('\\n').some(l=>l.trim().startsWith('①②③④'[n-1])))).id")
 goto('library');page.locator('#library-query').fill(qid);page.locator('.library-card [data-action=preview]').click();page.locator('[data-action=single]').click();start_or_replace()
 expect(page.locator('.question-text .q-choice')).to_have_count(4)
 shown,orig=page.evaluate("(id)=>[document.querySelector('.question-text').textContent,BANK_DATA.questions.find(q=>q.id===id).text]",qid)
 assert ''.join(shown.split())==''.join(orig.split()),'text view must keep the original wording'
 page.locator('[data-action=finish]').click();page.locator('[data-action=finish-now]').click()
 goto('history');stamp=page.locator('.history-card .sub').first.inner_text().split('\n')[0]
 assert __import__('re').search(r'\d:\d\d$',stamp) and not __import__('re').search(r'\d:\d\d:\d\d',stamp),stamp
 retry_ids=[q['id'] for q in page.evaluate("BANK_DATA.questions.filter(q=>q.eligible&&q.part==='F03'&&q.representative).slice(0,3)")]
 page.evaluate("([k,ids])=>{const s=JSON.parse(localStorage.getItem(k));s.active={id:'arrow',title:'arrow',ids,answers:{},index:0,startedAt:Date.now(),finishedAt:null};localStorage.setItem(k,JSON.stringify(s));}",[KEY,retry_ids])
 goto('quiz');page.reload();page.locator('#main').focus();page.keyboard.press('ArrowRight');assert state()['active']['index']==1
 page.keyboard.press('ArrowLeft');assert state()['active']['index']==0
 # Concept index keeps the per-status part list folded and hides a zero pending count.
 goto('concepts');expect(page.locator('.status-list').first).not_to_have_attribute('open','');expect(page.locator('.status-parts a').first).to_be_hidden()
 assert ('준비 중' in page.locator('.concept-intro strong').inner_text())==(page.evaluate('BANK_DATA.parts.length')>page.evaluate('(BANK_DATA.concepts||{notes:[]}).notes.length'))
 page.locator('.status-list summary').first.click();expect(page.locator('.status-parts a').first).to_be_visible()
 goto('quiz')
 # Keyboard focus survives re-renders: choosing keeps the option focused, grading moves to the next button.
 saved=page.evaluate("k=>localStorage.getItem(k)",KEY)
 page.locator('[data-action="choose"][data-answer="1"]').focus();page.keyboard.press('Enter')
 assert page.evaluate("document.activeElement.dataset.action+document.activeElement.dataset.answer")=='choose1'
 page.locator('[data-action="grade"]').focus();page.keyboard.press('Enter')
 assert page.evaluate("document.activeElement.dataset.action")=='next'
 page.evaluate("([k,v])=>localStorage.setItem(k,v)",[KEY,saved]);goto('quiz');page.reload()
 # Wide screens get a sticky table of contents for concept notes; it scrolls to the section without changing the route.
 goto('concept/C11');expect(page.locator('.note-toc button')).to_have_count(page.locator('.note-page > section.note-sec > h3').count())
 page.locator('.note-toc button',has_text='자주 틀리는 포인트').click();page.wait_for_timeout(800)
 assert page.evaluate("location.hash")=='#concept/C11'
 top=page.evaluate("[...document.querySelectorAll('.note-page > section.note-sec > h3')].find(h=>h.textContent==='자주 틀리는 포인트').getBoundingClientRect().top");assert 0<=top<200,top
 # Printing hides app chrome and uses light colours whatever the theme.
 goto('concept/C11');page.emulate_media(media='print',color_scheme='dark')
 assert page.evaluate("[getComputedStyle(document.querySelector('.appbar')).display,getComputedStyle(document.body).backgroundColor,getComputedStyle(document.querySelector('.note-page')).color]")==['none','rgb(255, 255, 255)','rgb(17, 17, 17)']
 page.emulate_media(media='screen',color_scheme='light');goto('quiz')
 # Korean text wraps between words, not inside them.
 assert page.evaluate("getComputedStyle(document.querySelector('.question-text')).wordBreak")=='keep-all'
 # Shortcuts still work after clicking a choice (focus sits on a button).
 page.locator('[data-action="choose"]').first.click();page.keyboard.press('ArrowRight');assert state()['active']['index']==1
 page.keyboard.press('ArrowLeft');assert state()['active']['index']==0
 # Returning learners get next steps; parts are grouped so each chapter heading appears once.
 goto('home');n=page.evaluate("(()=>{const t=new Date().setHours(0,0,0,0);return Object.values(JSON.parse(localStorage.getItem('chagok.study.v1')).results).filter(r=>r.updatedAt>=t).length})()")
 assert (f'오늘 {n}문제 풀이' in page.locator('.home-date').inner_text()) if n else ('오늘' not in page.locator('.home-date').inner_text())
 goto('home');expect(page.locator('.next-steps')).to_be_visible();expect(page.locator('.hero')).to_have_count(0)
 page.locator('[data-action=subject][data-subject="재무회계"]').click()
 heads=page.locator('.chapter-title').all_inner_texts();assert len(heads)==len(set(heads)),heads
 # Theme toggle cycles system → light → dark, persists separately from study records, and scans can stay original.
 before=json.dumps(state(),sort_keys=True)
 goto('home');page.locator('#theme-btn').click();assert page.evaluate("document.documentElement.dataset.theme")=='light'
 page.locator('#theme-btn').click();assert page.evaluate("document.documentElement.dataset.theme")=='dark'
 page.reload();assert page.evaluate("document.documentElement.dataset.theme")=='dark'
 assert page.evaluate("getComputedStyle(document.body).backgroundColor")!='rgb(245, 246, 243)'
 page.locator('.avatar').click();page.locator('#img-invert').uncheck();assert page.evaluate("localStorage.getItem('chagok.img')")=='original'
 page.locator('#img-invert').check();page.locator('[data-action=theme-set][data-theme=system]').click()
 # Text size is a per-browser display preference kept outside the study record.
 page.locator('[data-action=size-set][data-size=xl]').click();assert page.evaluate("[document.documentElement.dataset.size,localStorage.getItem('chagok.size')]")==['xl','xl']
 page.locator('[data-action=size-set][data-size=""]').click();assert page.evaluate("[document.documentElement.dataset.size||'',localStorage.getItem('chagok.size')]")==['',None];page.keyboard.press('Escape')
 assert page.evaluate("document.documentElement.dataset.theme") is None and page.evaluate("localStorage.getItem('chagok.theme')") is None
 assert json.dumps(state(),sort_keys=True)==before,'theme settings must not touch chagok.study.v1'
 goto('home');page.locator('#setup-subject').select_option('');page.locator('#setup-part').select_option('F04');expect(page.locator('.setup-concept')).to_contain_text('핵심 개념')
 # Reload, dashboard, desktop and mobile layout, text/original switch, zoom.
 page.reload();expect(page.locator('.stat').first.locator('strong')).to_contain_text(str(len(state()['results'])))
 page.screenshot(path=str(ARTIFACTS/'app-home-desktop.png'),full_page=False)
 assert page.evaluate("[...document.querySelectorAll('.step')].map(e=>e.textContent)")==['01','02','03']
 mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 m=mobile.new_page();m.on('pageerror',lambda e:errors.append(str(e)));m.goto(URL)
 expect(m.locator('.subject-card')).to_have_count(3)
 # List cards keep their actions on one row at phone width.
 m.goto(URL+'#library');m.wait_for_timeout(200)
 # Phone previews follow the quiz text view; the original image sits in a toggle.
 m.locator('[data-action=preview]').first.click();expect(m.locator('dialog .question-text')).to_be_visible()
 expect(m.locator('dialog details.instructions summary').first).to_have_text('원본 이미지 보기');m.keyboard.press('Escape')
 assert m.evaluate("[...document.querySelectorAll('.list-actions')].every(a=>new Set([...a.children].map(c=>{const k=c.getBoundingClientRect();return Math.round((k.top+k.bottom)/20)})).size===1)")
 m.goto(URL);m.wait_for_timeout(200)
 # Section numbers follow the on-screen order (mobile moves study setup above the part list).
 assert m.evaluate("[...document.querySelectorAll('.step')].map(e=>[e.getBoundingClientRect().top,e.textContent]).sort((a,b)=>a[0]-b[0]).map(x=>x[1])")==['01','02','03']
 m.screenshot(path=str(ARTIFACTS/'app-home-mobile.png'),full_page=True)
 m.locator('#setup-part').select_option('F03');m.locator('[data-action=start]').click()
 expect(m.locator('.question-text')).to_be_visible()
 assert m.evaluate('document.documentElement.scrollWidth<=innerWidth')
 m.screenshot(path=str(ARTIFACTS/'app-quiz-mobile.png'),full_page=True)
 m.locator('[data-action=question-view][data-view=image]').click();expect(m.locator('.question-image')).to_be_visible()
 expect(m.locator('.question-image')).to_have_js_property('complete',True)
 m.locator('.image-note [data-action=zoom]').click();expect(m.locator('dialog')).to_be_visible()
 assert m.evaluate('document.documentElement.scrollWidth<=innerWidth')
 m.locator('[data-action=close-modal]').click()
 m.locator('.question-card [data-action=concept-modal]').click();expect(m.locator('dialog')).to_be_visible();assert m.evaluate('document.documentElement.scrollWidth<=innerWidth')
 m.screenshot(path=str(ARTIFACTS/'app-concept-modal-mobile.png'));m.locator('dialog [data-action=close-modal]').first.click()
 m.goto(URL+'#concept/C11');expect(m.locator('.year-table')).to_be_visible();assert m.evaluate('document.documentElement.scrollWidth<=innerWidth')
 m.screenshot(path=str(ARTIFACTS/'app-concept-mobile.png'),full_page=True)
 # New long formulas and immutable source versions must fit a phone screen too.
 mobile_before=m.evaluate('localStorage.getItem("chagok.study.v1")')
 for note in m.evaluate('BANK_DATA.concepts.notes'):
  m.goto(URL+'#concept/'+note['part_id'])
  expect(m.locator('h1')).to_have_text(note['title'])
  assert m.evaluate('document.documentElement.scrollWidth<=innerWidth'),note['part_id']
 assert m.evaluate('localStorage.getItem("chagok.study.v1")')==mobile_before
 m.goto(URL+'#quiz')
 m.reload();expect(m.locator('.question-card')).to_be_visible()
 # New-session replacement is explicit and retains already graded records.
 m.locator('[data-action=home]').click();m.locator('[data-action=start]').click();expect(m.locator('dialog')).to_contain_text('진행 중인 학습')
 m.locator('#keep-session').click();expect(m.locator('.question-card')).to_be_visible()
 assert not errors,errors
 browser.close()
 print('PASS: part/count/review filters, grading, reload/resume, incomplete finish, wrong replay, bookmarks, search, multi-answer, quarantine, export/import, history, keyboard, desktop/mobile/text/zoom, concept notes (index/pending/related/part study/quiz-wrong-preview links/tax-year highlight/state kept), choice blocks, arrow keys, next steps, grouped chapters, theme toggle; no browser errors')
