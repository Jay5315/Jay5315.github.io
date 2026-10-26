"""Real UI regression for deferred preview cleanup before keyboard grading.

The controlled close-listener gate makes a valid scheduling window deterministic.
It establishes selector ambiguity, not the cause of any historical test failure.
"""
import hashlib
import json
from pathlib import Path

from playwright.sync_api import expect


KEY = 'chagok.study.v1'
QUESTION = '2026-07-026'


def wait_for_quiz_ready(page, *, timeout=None):
    """Match test_app's precise cleanup guard; timeout bounds negative probes only."""
    expect(page.locator('#modal-body')).to_be_empty(timeout=timeout)
    expect(page.locator('.question-text')).to_have_count(1, timeout=timeout)


_CLOSE_GATE = r"""(() => {
  const original = EventTarget.prototype.addEventListener;
  const gate = window.__gradingCloseGate = {
    hold: false, pending: [], registered: 0, keys: [],
    release() {
      this.hold = false;
      for (const call of this.pending.splice(0)) {
        if (typeof call.callback === 'function') call.callback.call(call.target, call.event);
        else call.callback.handleEvent(call.event);
      }
    }
  };
  EventTarget.prototype.addEventListener = function(type, callback, options) {
    if (type === 'close' && this instanceof HTMLDialogElement && this.id === 'modal') {
      gate.registered += 1;
      return original.call(this, type, function(event) {
        if (gate.hold) { gate.pending.push({callback, target: this, event}); return; }
        if (typeof callback === 'function') callback.call(this, event);
        else callback.handleEvent(event);
      }, options);
    }
    return original.call(this, type, callback, options);
  };
  original.call(document, 'keydown', event => gate.keys.push({
    key: event.key, target: event.target.id || event.target.tagName,
    modalOpen: document.getElementById('modal')?.open
  }), true);
})();"""


def _snapshot(page):
    return page.evaluate("""key => ({
      count: document.querySelectorAll('.question-text').length,
      mainCount: document.querySelectorAll('#main .question-text').length,
      previewCount: document.querySelectorAll('#modal-body .question-text').length,
      nodes: [...document.querySelectorAll('.question-text')].map(node => ({
        inMain: !!node.closest('#main'), correct: node.getAttribute('data-correct'),
        picked: node.getAttribute('data-picked')
      })),
      dialogOpen: document.getElementById('modal').open,
      hash: location.hash, focus: document.activeElement?.id || document.activeElement?.tagName,
      active: JSON.parse(localStorage.getItem(key) || 'null')?.active,
      heldCallbacks: __gradingCloseGate.pending.length,
      keys: __gradingCloseGate.keys.slice()
    })""", KEY)


def run_grading_readiness(browser, url, artifact_dir=None):
    """Require the readiness guard to reject held cleanup and pass after release."""
    context = browser.new_context(service_workers='block', viewport={'width': 1440, 'height': 1000})
    context.add_init_script(_CLOSE_GATE)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    evidence = {'controlled_scheduling': True, 'historical_root_cause_proven': False}
    try:
        page.goto(url.rstrip('/') + '/#library')
        page.locator('#library-query').fill(QUESTION)
        expect(page.locator('.library-card')).to_have_count(1)
        page.locator('[data-action=preview]').click()
        expect(page.locator('#modal-body .question-text')).to_have_count(1)
        assert page.evaluate('__gradingCloseGate.registered') == 1
        page.evaluate('__gradingCloseGate.hold = true')
        page.locator('[data-action=single]').click()
        expect(page.locator('.question-card')).to_be_visible()
        page.wait_for_function('__gradingCloseGate.pending.length === 1')
        evidence['held_before_keys'] = _snapshot(page)
        assert evidence['held_before_keys']['count'] == 2, evidence
        assert evidence['held_before_keys']['mainCount'] == 1, evidence
        assert evidence['held_before_keys']['previewCount'] == 1, evidence
        assert not evidence['held_before_keys']['dialogOpen'], evidence
        assert evidence['held_before_keys']['active']['ids'] == [QUESTION], evidence
        expect(page.locator('.question-text[data-correct]')).to_have_count(0)
        evidence['original_guard_accepted'] = True

        # The old visible-card precondition already passes above. A real guard
        # must refuse this exact state; removing the cleanup guard fails here.
        try:
            wait_for_quiz_ready(page, timeout=250)
        except AssertionError as error:
            evidence['guard_rejection'] = str(error)
        else:
            raise AssertionError('Quiz readiness accepted a retained preview before keyboard input')

        # Deliberately proceed within the held scheduling window to distinguish
        # successful keyboard grading from failure of the unscoped assertion.
        page.locator('#main').focus()
        page.keyboard.press('1')
        page.keyboard.press('Enter')
        expect(page.locator('#main .question-text')).to_have_attribute('data-correct', '1 4')
        expect(page.locator('#main .question-text')).to_have_attribute('data-picked', '1')
        evidence['held_after_grading'] = _snapshot(page)
        assert evidence['held_after_grading']['active']['answers'] == {QUESTION: 1}, evidence
        assert evidence['held_after_grading']['keys'][-2:] == [
            {'key': '1', 'target': 'main', 'modalOpen': False},
            {'key': 'Enter', 'target': 'main', 'modalOpen': False},
        ], evidence
        try:
            expect(page.locator('.question-text')).to_have_attribute('data-correct', '1 4', timeout=250)
        except AssertionError as error:
            evidence['original_assertion_rejection'] = str(error)
            assert 'strict mode violation' in str(error), evidence
            if artifact_dir is not None:
                image=Path(artifact_dir)/'grading-readiness-controlled-failure.png'
                image.parent.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(image),full_page=True)
                evidence['controlled_failure_screenshot']={'path':str(image),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}
        else:
            raise AssertionError('Original unscoped assertion unexpectedly resolved two matching nodes')

        page.evaluate('__gradingCloseGate.release()')
        wait_for_quiz_ready(page)
        # Keep both original assertions intact after the exact cleanup condition.
        expect(page.locator('.question-text')).to_have_attribute('data-correct', '1 4')
        expect(page.locator('.question-text')).to_have_attribute('data-picked', '1')
        expect(page.locator('.feedback')).to_contain_text('정답이에요')
        evidence['released'] = _snapshot(page)
        assert evidence['released']['heldCallbacks'] == 0, evidence
        assert evidence['released']['count'] == 1, evidence
        assert evidence['released']['active']['answers'] == {QUESTION: 1}, evidence
        assert not errors, errors
        evidence['page_errors'] = errors
        return evidence
    except Exception as error:
        raise AssertionError('Deferred-close grading readiness regression failed: ' + json.dumps(
            evidence, ensure_ascii=False)) from error
    finally:
        context.close()
