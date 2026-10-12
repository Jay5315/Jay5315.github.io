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
  page.locator('#main').focus();page.keyboard.press(str(answer));page.keyboard.press('Enter')
  expect(page.locator('.feedback')).to_contain_text('정답이에요')
  assert '복수 정답' in page.locator('.feedback').inner_text()
  page.locator('[data-action=next]').click()
 assert state()['results']['2026-07-026']['correct']==2
 goto('library');page.locator('#library-query').fill('2024-09-063');expect(page.locator('.library-card')).to_have_count(0)
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
 # Reload, dashboard, desktop and mobile layout, text/original switch, zoom.
 page.reload();expect(page.locator('.stat').first.locator('strong')).to_contain_text(str(len(state()['results'])))
 page.screenshot(path=str(ARTIFACTS/'app-home-desktop.png'),full_page=False)
 mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 m=mobile.new_page();m.on('pageerror',lambda e:errors.append(str(e)));m.goto(URL)
 expect(m.locator('.subject-card')).to_have_count(3)
 m.screenshot(path=str(ARTIFACTS/'app-home-mobile.png'),full_page=True)
 m.locator('#setup-part').select_option('F03');m.locator('[data-action=start]').click()
 expect(m.locator('.question-text')).to_be_visible()
 assert m.evaluate('document.documentElement.scrollWidth<=innerWidth')
 m.screenshot(path=str(ARTIFACTS/'app-quiz-mobile.png'),full_page=True)
 m.locator('[data-action=question-view][data-view=image]').click();expect(m.locator('.question-image')).to_be_visible()
 expect(m.locator('.question-image')).to_have_js_property('complete',True)
 m.locator('.image-note [data-action=zoom]').click();expect(m.locator('dialog')).to_be_visible()
 assert m.evaluate('document.documentElement.scrollWidth<=innerWidth')
 m.locator('[data-action=close-modal]').click();m.reload();expect(m.locator('.question-card')).to_be_visible()
 # New-session replacement is explicit and retains already graded records.
 m.locator('[data-action=home]').click();m.locator('[data-action=start]').click();expect(m.locator('dialog')).to_contain_text('진행 중인 학습')
 m.locator('#keep-session').click();expect(m.locator('.question-card')).to_be_visible()
 assert not errors,errors
 browser.close()
 print('PASS: part/count/review filters, grading, reload/resume, incomplete finish, wrong replay, bookmarks, search, multi-answer, quarantine, export/import, history, keyboard, desktop/mobile/text/zoom; no browser errors')
