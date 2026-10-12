from pathlib import Path
import shutil,os
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
URL=os.environ.get('APP_BASE_URL','http://127.0.0.1:8000/jaegyeong/').rstrip('/')+'/'
ARTIFACTS=Path(os.environ.get('TEST_ARTIFACT_DIR',str(ROOT/'_artifacts')))
ARTIFACTS.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=shutil.which('chromium'))
    page=browser.new_page(viewport={'width':1280,'height':900})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL+'review.html',wait_until='networkidle')
    page.wait_for_selector('.question-image')
    assert page.locator('#question .question-image').evaluate('(img)=>img.complete && img.naturalWidth>0')
    assert '4,322' in page.locator('#stats').inner_text()
    page.locator('#scope').select_option('entries')
    page.locator('#query').fill('2026-07-026')
    page.get_by_role('button',name='1번 선택',exact=True).click()
    assert '정답입니다' in page.locator('.result').inner_text()
    page.get_by_role('button',name='4번 선택',exact=True).click()
    assert '정답입니다' in page.locator('.result').inner_text()
    page.get_by_role('button',name='2번 선택',exact=True).click()
    assert '다시 확인' in page.locator('.result').inner_text()
    page.locator('#query').fill('2022-01-105')
    variant=page.get_by_label('변형 문제 선택')
    assert variant.locator('option').count()>=2
    variant.select_option('2023-09-105')
    assert '2023-09' in page.locator('#question').inner_text()
    page.locator('#query').fill('')
    page.locator('#scope').select_option('quarantine')
    assert '2024-09' in page.locator('#question').inner_text()
    assert page.get_by_role('button',name='1번 선택',exact=True).is_disabled()
    page.locator('#scope').select_option('representatives')
    page.locator('#review-tab').click()
    assert page.locator('#comparison .card').count()==2
    page.locator('#review-next').click()
    assert '2 / ' in page.locator('#review-position').inner_text()
    page.locator('#bank-tab').click()
    page.locator('#subject').select_option('재무회계')
    page.locator('#part').select_option('F26')
    assert '현금흐름표' in page.locator('#question .part-label').inner_text()
    assert page.locator('#part option').count()==27
    page.locator('#subject').select_option('원가관리회계')
    assert page.locator('#part').input_value()==''
    assert page.locator('#part option').count()==21
    page.locator('#part').select_option('M11')
    assert 'CVP' in page.locator('#question .part-label').inner_text()
    page.locator('#part').select_option('M15')
    page.locator('#query').fill('NPV·IRR')
    assert page.locator('#question .question-image').count()==1
    assert 'NPV·IRR' in page.locator('#question .topic-tags').inner_text()
    page.locator('#query').fill('')
    page.locator('#subject').select_option('')
    page.locator('#part').select_option('')
    page.locator('#scope').select_option('entries')
    page.locator('#classification-status').select_option('review')
    import json
    review_count=json.loads((ROOT/'data/classification-summary.json').read_text())['review_entries']
    # Any held source is excluded from the normal entries scope.
    entries=json.loads((ROOT/'data/entries.json').read_text())
    eligible=sum(e['classification']['review_required'] and e['study_eligible'] for e in entries)
    assert f'검색 결과 {eligible:,}문제' in page.locator('#count').inner_text()
    assert page.locator('#question .classification-notice').count()==1
    page.locator('#classification-status').select_option('')
    page.locator('#subject').select_option('재무회계')
    page.locator('#part').select_option('F26')
    page.screenshot(path=str(ARTIFACTS/'browser-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path=str(ARTIFACTS/'browser-mobile.png'),full_page=True)
    assert not errors,errors
    browser.close()
    print('PASS: load, images, search, multiple-answer scoring, variants, quarantine, comparison, part filters, subject reset, tag search, classification review filter, mobile layout; no browser errors.')
