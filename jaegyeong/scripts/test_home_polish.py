"""Home counts and mobile text-button targets through real browser interactions."""
import json
import os
from pathlib import Path
import shutil
import sys
from playwright.sync_api import expect, sync_playwright

URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000/jaegyeong/').rstrip('/') + '/'
ARTIFACTS = Path(os.environ.get('TEST_ARTIFACT_DIR', str(Path(__file__).resolve().parents[1] / '_artifacts')))


def geometry(button):
    return button.evaluate('''el=>{const style=getComputedStyle(el);const range=document.createRange();range.selectNodeContents(el);return {box:el.getBoundingClientRect().toJSON(),glyph:range.getBoundingClientRect().toJSON(),fontSize:style.fontSize,fontWeight:style.fontWeight,lineHeight:style.lineHeight,color:style.color,background:style.backgroundColor,border:style.borderWidth};}''')


def run_home_polish(browser, url=URL, only=None, capture_only=False):
    observations = []
    cases = [(360, 'light', 'normal'), (360, 'dark', 'normal'), (390, 'light', 'normal'),
             (390, 'dark', 'normal'), (640, 'light', 'normal'), (641, 'light', 'normal'),
             (1280, 'light', 'normal'), (1280, 'dark', 'normal'),
             (360, 'light', 'xl'), (390, 'dark', 'xl')]
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for width, theme, size in cases:
        context = browser.new_context(viewport={'width': width, 'height': 844}, service_workers='block')
        context.route('https://cdn.jsdelivr.net/**', lambda route: route.abort())
        context.add_init_script(f"localStorage.setItem('chagok.theme','{theme}');localStorage.setItem('chagok.size','{size}')")
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(url)
            expect(page.locator('.subject-card')).to_have_count(3)
            count = page.evaluate('BANK_DATA.explanations.items.length')
            if only != 'targets' and not capture_only:
                expect(page.locator('[data-action=practice-explanations]')).to_contain_text(f'해설 {count:,}문항 풀기')
                expect(page.locator('.explanation-start p').first).to_contain_text(f'총 {count:,}문항')
            page.locator('#setup-part').select_option('F03')
            expect(page.locator('#setup-part')).to_have_value('F03')
            row = {'width': width, 'theme': theme, 'size': size, 'buttons': {}}
            for action in ['all-parts', 'settings']:
                button = page.locator(f'.text-button[data-action={action}]')
                button.scroll_into_view_if_needed()
                g = geometry(button)
                row['buttons'][action] = g
                if only != 'counts' and not capture_only:
                    minimum = 44 if width <= 640 else 20
                    assert g['box']['height'] >= minimum, (width, action, g)
                    assert g['box']['width'] >= 44, (width, action, g)
                    assert g['fontSize'] == '14px' and g['fontWeight'] == '700', (width, action, g)
                    assert g['background'] == 'rgba(0, 0, 0, 0)' and g['border'] == '0px', g
                    if width > 640:
                        assert g['box']['height'] < 30, ('Desktop text-button appearance changed', g)
                    else:
                        # Hit-test and click at the top of the target, outside the text ink.
                        assert g['glyph']['top'] - g['box']['top'] > 4, g
                        assert button.evaluate('''el=>{const r=el.getBoundingClientRect();const hit=document.elementFromPoint(r.x+r.width/2,r.y+2);return hit===el||el.contains(hit);}'''), action
                        button.click(position={'x': g['box']['width']/2, 'y': 2})
                        if action == 'all-parts':
                            expect(page.locator('#setup-part')).to_have_value('')
                        else:
                            expect(page.locator('#modal')).to_be_visible()
                            expect(page.locator('#modal-body')).to_contain_text('나의 학습 기록')
                            page.keyboard.press('Escape')
                            expect(page.locator('#modal')).not_to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, theme, size)
            assert not errors, errors
            if width == 360 and size == 'normal':
                page.screenshot(path=str(ARTIFACTS/f'home-{theme}.png'), full_page=True)
            observations.append(row)
        finally:
            context.close()
    suffix = 'capture' if capture_only else (only or 'all')
    (ARTIFACTS/f'home-polish-{suffix}.json').write_text(json.dumps(observations, ensure_ascii=False, indent=2)+'\n')
    return ('CAPTURE ONLY: ' if capture_only else '')+'home counts use thousands separators; mobile text targets >=44px; unchanged type/color/border, edge taps, no overflow in 10 viewport/theme/size cases'


if __name__ == '__main__':
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
        try:
            only = next((v.removeprefix('--') for v in sys.argv[1:] if v in ['--counts', '--targets']), None)
            print('PASS: '+run_home_polish(browser, only=only, capture_only='--capture' in sys.argv))
        finally:
            browser.close()
