"""Content regression and safety checks for authored question explanations."""
import copy
import calendar
import datetime
import hashlib
import json
import re
import unittest
from collections import Counter
from pathlib import Path

from explanation_data import validate_explanations
from test_concepts import calc
from test_runtime_data import RuntimeDataTests
from test_round27_independent_review import Round27IndependentReviewTests
from test_work_order_reports import WorkOrderStep2Tests

R = Path(__file__).resolve().parents[1]


# UI files may change after an audit baseline only along reports/ui-changes.json.
UI_FILES = {'assets/app.js', 'assets/app.css'}

# Registration ledgers, newest first; setUpClass reverses them in this order.
REGISTRATION_LEDGERS = ['round17_registrations', 'round16_registrations', 'round15_registrations', 'round14_registrations', 'round13_registrations']

class ExplanationTests(unittest.TestCase):
    def test_round10_rejects_non_numeric_or_non_finite_checks(self):
        from apply_round10_followups import arithmetic
        for expr, expected in [('True+1', 2), ('1e309-1e309', 0),
                               ('1e309/1e309', 17), ('1e308*1e308', 0),
                               ('2//1', 2), ('2==2', 1)]:
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                arithmetic({'checks': [{'expr': expr, 'expected': expected}]}, restricted=True)
        arithmetic({'checks': [{'expr': '(3+2)*4/2-1', 'expected': 9}]}, restricted=True)
        arithmetic({'checks': [{'expr': '+1-(-2)', 'expected': 3}]}, restricted=True)

    def test_round10_preserves_previous_stages_and_official_data(self):
        group = (self.current_audit or {}).get('round10_followups')
        if not group:
            self.skipTest('No round-10 follow-ups recorded')
        from apply_round10_followups import digest, arithmetic, ALLOWED_FIELDS, PROTECTED
        before = {n['question_id']: n for n in self.before_round10_data['items']}
        after = self.latest_notes
        self.assertEqual(list(before), group['baseline_ids'])
        self.assertEqual(len(before), group['baseline_count'])
        self.assertEqual({id: digest(n) for id, n in before.items()}, group['baseline_hashes'])
        self.assertEqual({ref: digest(s) for ref, s in self.before_round10_data['sources'].items()},
                         group['baseline_source_hashes'])
        for ref, expected in group['baseline_source_hashes'].items():
            self.assertEqual(digest(self.current_data['sources'][ref]), expected, ref)
        amended = [r['question_id'] for r in group['amendments']]
        registered = [r['question_id'] for r in group['registrations']]
        self.assertEqual(len(amended), len(set(amended)))
        self.assertEqual(len(registered), len(set(registered)))
        self.assertFalse(set(amended) & set(registered))
        self.assertEqual(set(after), set(before) | set(registered))
        self.assertEqual(list(after)[:len(before)], list(before))
        self.assertEqual(group['amended_count'], len(amended))
        self.assertEqual(group['registered_count'], len(registered))
        self.assertEqual(group['current_registered_count'], len(after))
        for row in group['amendments']:
            id = row['question_id']
            self.assertEqual(row['before'], before[id])
            self.assertEqual(digest(before[id]), row['before_hash'])
            self.assertEqual(digest(after[id]), row['after_hash'])
            self.assertEqual(row['after'], after[id])
            fields = {k for k in before[id] if before[id][k] != after[id][k]}
            self.assertEqual(fields, set(row['changed_fields']))
            self.assertTrue(fields and fields <= ALLOWED_FIELDS)
            self.assertFalse(fields & PROTECTED)
            self.assertEqual(set(before[id]), set(after[id]))
            self.assertEqual(after[id]['sources'][:len(before[id]['sources'])], before[id]['sources'])
            for old, new in zip(before[id]['option_notes'], after[id]['option_notes']):
                self.assertEqual({k: v for k, v in old.items() if k != 'reason'},
                                 {k: v for k, v in new.items() if k != 'reason'})
            arithmetic(after[id])
        for id in set(before) - set(amended):
            self.assertEqual(after[id], before[id], id)
        original_pending = {r['question_id']: r for r in group['original_review']}
        pending = {r['question_id']: r for r in self.current_audit['review']}
        self.assertEqual(set(pending), set(original_pending) - set(registered))
        updates = {r['question_id']: r for r in group['review_updates']}
        self.assertEqual(len(updates), len(group['review_updates']))
        for id, row in updates.items():
            self.assertEqual(row['before'], original_pending[id])
            self.assertEqual(row['after'], pending[id])
            self.assertEqual(row['before_hash'], digest(row['before']))
            self.assertEqual(row['after_hash'], digest(row['after']))
            self.assertEqual({k: v for k, v in row['before'].items() if k != 'reason'},
                             {k: v for k, v in row['after'].items() if k != 'reason'})
        for id in set(pending) - set(updates):
            self.assertEqual(pending[id], original_pending[id])
        for row in group['registrations']:
            id, note = row['question_id'], after[row['question_id']]
            self.assertEqual(row['previous_review'], original_pending[id])
            self.assertEqual(digest(note), row['explanation_sha256'])
            self.assertEqual(digest(self.qs[id]), row['question_row_sha256'])
            self.assertEqual(row['official_answers'], self.qs[id]['answers'])
            self.assertTrue(self.qs[id]['study_eligible'])
            self.assertEqual(note['review_status'], 'source_checked')
            self.assertEqual(note['unchecked_points'], [])
            self.assertEqual(len({o['reason'] for o in note['option_notes']}), 4)
            arithmetic(note, restricted=True)
        original_verdicts = {r['question_id']: r for r in group['original_adjudication']['records']}
        verdicts = {r['question_id']: r for r in self.current_audit['answer_adjudication']['records']}
        changes = {r['question_id']: r for r in group['adjudication_amendments']}
        self.assertEqual(len(changes), len(group['adjudication_amendments']))
        self.assertEqual(set(verdicts), set(original_verdicts))
        for id, row in changes.items():
            self.assertEqual(row['before'], original_verdicts[id])
            self.assertEqual(row['after'], verdicts[id])
            self.assertEqual(row['before_hash'], digest(row['before']))
            self.assertEqual(row['after_hash'], digest(row['after']))
            self.assertEqual(verdicts[id]['previous_verdict'], original_verdicts[id]['verdict'])
            self.assertTrue(verdicts[id]['corrected_on'] and verdicts[id]['evidence'])
            self.assertEqual(verdicts[id]['official_answers'], self.qs[id]['answers'])
            self.assertIs(verdicts[id]['official_answer_changed'], False)
        for id in set(verdicts) - set(changes):
            self.assertEqual(verdicts[id], original_verdicts[id])
        self.assertEqual(self.current_audit['answer_adjudication']['counts'],
                         dict(Counter(v['verdict'] for v in verdicts.values())))
        uncertainties = group['adjudication_uncertainties']
        self.assertEqual(self.current_audit['answer_adjudication']['followup_uncertainties'],
                         group['original_adjudication'].get('followup_uncertainties', []) + uncertainties)
        partial_changes = {r['question_id']: r for r in group['amendments']
                           if r['before']['review_status'] != 'partial' and r['after']['review_status'] == 'partial'}
        self.assertEqual({r['question_id'] for r in uncertainties}, set(partial_changes))
        self.assertEqual(len(uncertainties), len(partial_changes))
        for notice in uncertainties:
            id = notice['question_id']
            self.assertEqual(notice['verdict'], 'deferred')
            self.assertIs(notice['official_answer_changed'], False)
            self.assertEqual(notice['official_answers'], self.qs[id]['answers'])
            self.assertEqual(notice['evidence'], after[id]['unchecked_points'])
            self.assertEqual(notice['explanation_after_hash'], digest(after[id]))
            self.assertEqual(notice['independent_review_proposal_sha256'],
                             partial_changes[id]['independent_review']['proposal_sha256'])
            self.assertNotEqual(notice['author'], notice['reviewer'])
        self.assertEqual(group['remaining_review_count'], len(pending))

    def test_round10_independent_reviews_bind_actual_sources_and_four_options(self):
        group = (self.current_audit or {}).get('round10_followups')
        if not group:
            self.skipTest('No round-10 follow-ups recorded')
        self.assertFalse(group['expert_reviewed'])
        self.assertRegex(group['proposal_sha256'], r'^[0-9a-f]{64}$')
        self.assertRegex(group['review_sha256'], r'^[0-9a-f]{64}$')
        for key, kind in [('amendments', 'amendment'), ('registrations', 'registration'),
                          ('adjudication_amendments', 'adjudication')]:
            for row in group[key]:
                qa = row['independent_review']
                self.assertEqual(qa['target_kind'], kind)
                self.assertEqual(qa['question_id'], row['question_id'])
                self.assertEqual(qa['status'], 'pass')
                self.assertEqual(qa['author'], row['author'])
                self.assertNotEqual(qa['reviewer'], row['author'])
                self.assertEqual(qa['proposal_sha256'], row['proposal_record_sha256'])
                if kind in {'amendment', 'adjudication'}:
                    self.assertEqual(qa.get('before_hash', qa.get('before_hash_checked')), row['before_hash'])
                    self.assertEqual(qa.get('after_hash', qa.get('after_hash_checked')), row['after_hash'])
                else:
                    self.assertEqual(qa.get('explanation_sha256', qa.get('note_sha256')), row['explanation_sha256'])
                self.assertEqual(len(qa['four_option_logic']), 4)
                self.assertEqual({x['number'] for x in qa['four_option_logic']}, {1, 2, 3, 4})
                allowed_statuses = {'pass'}
                if kind == 'adjudication':
                    self.assertIs(qa['adjudication_scope_checked'], True)
                    self.assertTrue(qa['limits'])
                    allowed_statuses.add('outside_adjudicated_scope')
                    if row['after']['verdict'] == 'deferred':
                        allowed_statuses.add('deferred_not_proven_wrong')
                    if row['after']['verdict'] == 'official_supported':
                        self.assertTrue(all(x['status'] == 'pass' for x in qa['four_option_logic']
                                            if x['number'] in row['after']['official_answers']))
                self.assertTrue(all(x['status'] in allowed_statuses and x['finding']
                                    for x in qa['four_option_logic']))
                self.assertTrue(all(qa[k] for k in ('original_pdf_checked', 'original_image_checked',
                                                  'subject_instructions_checked', 'official_answers_checked')))
                for reads in [row['source_reads'], qa['source_reads']]:
                    self.assertTrue(reads)
                    for read in reads:
                        self.assertTrue(read['url'].startswith('https://'))
                        self.assertRegex(read['sha256'], r'^[0-9a-f]{64}$')
                        self.assertTrue(read['version'] and read['read_locator'])
                        self.assertIs(read['actually_read'], True)
        for id, note in self.latest_notes.items():
            answers = {o['reason'].strip() for o in note['option_notes'] if o['is_answer']}
            other = {o['reason'].strip() for o in note['option_notes'] if not o['is_answer']}
            self.assertFalse(answers & other, id)

    def active_quality_withdrawals(self):
        """Keep historical withdrawals and verify any subsequent re-registration."""
        active = set()
        for withdrawal in self.audit.get('final_quality_withdrawals', []):
            id = withdrawal['question_id']
            if id not in self.notes:
                active.add(id)
                continue
            snapshot = self.audit['seventh_pass_snapshot']
            self.assertNotIn(id, snapshot['baseline_hashes'])
            self.assertIn(id, snapshot['initial_review_ids'])
            resolutions = [r for r in self.audit['review_resolutions']
                           if r['question_id'] == id and 'extra_batch_id' in r]
            resolution = resolutions[-1]
            batch = next(b for b in self.audit['extra_rechecks']
                         if b['batch_id'] == resolution['extra_batch_id'])
            self.assertIn(batch['extra_round'], snapshot['included_extra_rounds'])
            self.assertIn(id, batch['resolved_ids'])
            self.assertTrue(resolution['previous_review']['final_quality_withdrawal'])
            self.assertTrue(resolution['previous_reason'] and resolution['reason'])
            digest = lambda x: hashlib.sha256(json.dumps(x, ensure_ascii=False,
                             sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(resolution['explanation_hash'], digest(self.notes[id]))
            self.assertNotEqual(resolution['explanation_hash'], withdrawal['before_hash'])
            qa = json.loads((R / 'reports/round7-quality-review.json').read_text())
            rows = [row for row in qa['items'] if row['question_id'] == id]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['status'], 'pass')
            self.assertNotEqual(row['author'], row['reviewer'])
            self.assertEqual(row['explanation_sha256'], resolution['explanation_hash'])
            self.assertEqual(row['official_answers'], withdrawal['official_answers_preserved'])
            self.assertEqual(row['official_answers'], self.qs[id]['answers'])
            self.assertTrue(row['actual_source_reads'])
            self.assertTrue(all(x['status'] == 'pass' for x in row['four_option_logic']))
            self.assertTrue(row['original_pdf_checked'] and row['original_image_checked']
                            and row['subject_instructions_checked'])
        return active

    def test_seventh_pass_preserves_existing_data_and_exclusive_assignments(self):
        snapshot = (self.audit or {}).get('seventh_pass_snapshot')
        if snapshot is None:
            self.skipTest('No seventh-pass review started')
        def digest(value):
            return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        baseline = snapshot['baseline_hashes']
        self.assertEqual(len(baseline), snapshot['baseline_registered'])
        self.assertEqual([n['question_id'] for n in self.data['items'][:len(baseline)]], list(baseline))
        for id, expected in baseline.items():
            self.assertEqual(digest(self.notes[id]), expected, id)
        for ref, expected in snapshot['baseline_source_hashes'].items():
            self.assertEqual(digest(self.data['sources'][ref]), expected, ref)
        # Reconstruct the earlier concept stage before checking its protected
        # snapshot; round-20 additions have their own complete audit below.
        concepts = copy.deepcopy(self.before_round20_concepts)
        concept_items = {n['id']: n for n in concepts['notes']}
        concept_audit = json.loads((R / 'reports/concept-expansion.json').read_text())
        approved_concept_deltas = self.audit.get('seventh_pass_concept_delta_hashes', [])
        if approved_concept_deltas:
            qa = json.loads((R / 'reports/round7-concept-review.json').read_text())
            self.assertTrue(qa['complete'] and qa['status'] == 'pass')
            self.assertNotEqual(qa['author'], qa['reviewer'])
            self.assertFalse(qa['expert_reviewed'])
            self.assertTrue(qa['technical_followup']['all_requested_tests_passed'])
            for check in qa['content_qa']['numeric_checks'] + qa['content_qa']['source_example_checks']:
                self.assertAlmostEqual(calc(check['expr']), check['expected'], places=6)
            for amendment in reversed(concept_audit['followup_note_amendments']):
                if amendment['output_hash'] in approved_concept_deltas:
                    id = amendment['note_id']
                    self.assertEqual(digest(concept_items[id]), amendment['after_hash'], id)
                    self.assertEqual(digest(amendment['before']), amendment['before_hash'], id)
                    self.assertEqual(amendment['before_hash'], snapshot['baseline_concept_hashes'][id])
                    concept_items[id] = amendment['before']
        for id, expected in snapshot['baseline_concept_hashes'].items():
            self.assertEqual(digest(concept_items[id]), expected, id)
        records = [b for b in self.audit['extra_rechecks'] if b.get('extra_round') == 7]
        processed = [id for b in records for id in b['assigned_ids']]
        self.assertEqual(len(processed), len(set(processed)))
        self.assertTrue(all(20 <= len(b['assigned_ids']) <= 30 for b in records))
        target = set(snapshot['initial_review_ids'])
        self.assertEqual(len(target), snapshot['initial_review_count'])
        self.assertTrue(set(processed) <= target)
        added = set(self.notes) - set(baseline)
        pending = {r['question_id'] for r in self.audit['review']}
        self.assertFalse(added & pending)
        self.assertEqual(added | pending, target)
        self.assertEqual(snapshot['processed_count'], len(processed))
        self.assertEqual(snapshot['new_registered_count'], len(added))
        self.assertEqual(snapshot['remaining_review_count'], len(pending))
        followups = [b for b in self.audit['extra_rechecks'] if b.get('extra_round') == 8]
        followup_ids = [id for b in followups for id in b['assigned_ids']]
        self.assertEqual(len(followup_ids), len(set(followup_ids)))
        self.assertTrue(set(followup_ids) <= target)
        self.assertTrue(all(20 <= len(b['assigned_ids']) <= 30 for b in followups))
        self.assertEqual(snapshot.get('followup_rechecked_count', 0), len(followup_ids))
        for batch in records + followups:
            approved = self.audit['seventh_pass_parent_checks'][batch['batch_id']]
            self.assertEqual(approved['approved_output_sha256'], batch['output_hash'])
            self.assertTrue(approved['exact_original_input_match'] and approved['exact_outcome_coverage'])
            self.assertEqual(set(batch['resolved_ids']) | set(batch['remaining_ids']), set(batch['assigned_ids']))
            self.assertFalse(set(batch['resolved_ids']) & set(batch['remaining_ids']))
            self.assertEqual({row['question_id'] for row in batch['previous_review']}, set(batch['assigned_ids']))
        if snapshot['complete']:
            self.assertEqual(set(processed), target)
            self.assertEqual(snapshot['unprocessed_ids'], [])

    def test_seventh_pass_new_explanations_have_independent_quality_evidence(self):
        snapshot = (self.audit or {}).get('seventh_pass_snapshot')
        if not snapshot or not snapshot['complete']:
            self.skipTest('Seventh-pass assignments are not complete')
        def digest(value):
            return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        report = json.loads((R / 'reports/round7-quality-review.json').read_text())
        self.assertTrue(report['complete'])
        self.assertFalse(report['expert_reviewed'])
        included_rounds = snapshot.get('included_extra_rounds', [7])
        candidates = {id for b in self.audit['extra_rechecks'] if b.get('extra_round') in included_rounds
                      for id in b['resolved_ids']}
        rows = {row['question_id']: row for row in report['items']}
        self.assertEqual(len(rows), len(report['items']))
        self.assertEqual(set(rows), candidates)
        withdrawals = {row['question_id']: row for row in self.audit['final_quality_withdrawals']
                       if row.get('extra_round') in included_rounds}
        amendments = {row['question_id']: row for row in self.audit.get('seventh_pass_prose_amendments', [])}
        for id, row in rows.items():
            self.assertNotEqual(row['reviewer'], row['author'], id)
            self.assertEqual(row['official_answers'], self.qs[id]['answers'], id)
            self.assertEqual(row['tax_law_year'], self.qs[id]['tax_law_year'], id)
            self.assertEqual(row['question_row_sha256'], digest(self.qs[id]), id)
            self.assertTrue(row['original_pdf_checked'] and row['original_image_checked']
                            and row['subject_instructions_checked'], id)
            self.assertFalse(row['expert_reviewed'], id)
            self.assertEqual({x['number'] for x in row['four_option_logic']}, {1, 2, 3, 4}, id)
            self.assertTrue(row['actual_source_reads'], id)
            for source in row['actual_source_reads']:
                self.assertTrue(source['source_read'], id)
                self.assertRegex(source['sha256'], r'^[0-9a-f]{64}$')
            for check in row['math']['checks']:
                self.assertAlmostEqual(calc(check['expr']), check['expected'], places=6, msg=id)
            if id in withdrawals:
                self.assertEqual(row['status'], 'issue', id)
                self.assertEqual(row['explanation_sha256'], withdrawals[id]['before_hash'], id)
                self.assertNotIn(id, self.notes)
            else:
                self.assertEqual(row['status'], 'pass', id)
                if id in amendments:
                    amendment = amendments[id]
                    self.assertEqual(row['explanation_sha256'], amendment['before_hash'], id)
                    self.assertEqual(digest(amendment['before']), amendment['before_hash'], id)
                    self.assertEqual(digest(self.notes[id]), amendment['after_hash'], id)
                    self.assertTrue(amendment['final_independent_followup']['passed'], id)
                    self.assertEqual(amendment['changed_fields'], ['steps'], id)
                    before, after = dict(amendment['before']), dict(self.notes[id])
                    for index, old_step in enumerate(before['steps']):
                        if index not in amendment['changed_step_indices']:
                            self.assertEqual(old_step, after['steps'][index], id)
                    self.assertEqual(len(before['steps']), len(after['steps']), id)
                    before.pop('steps'); after.pop('steps')
                    self.assertEqual(before, after, id)
                else:
                    self.assertEqual(row['explanation_sha256'], digest(self.notes[id]), id)
                self.assertTrue(all(x['status'] == 'pass' for x in row['four_option_logic']), id)
        added = set(self.notes) - set(snapshot['baseline_hashes'])
        self.assertEqual(added, candidates - set(withdrawals))
        self.assertEqual(report['registered_pass_count'], len(added))
        self.assertEqual(report['withdrawn_issue_count'], len(withdrawals))

    def test_sixth_pass_protects_completed_explanations_and_review_partition(self):
        snapshot = (self.audit or {}).get('sixth_pass_snapshot')
        if snapshot is None:
            self.skipTest('No sixth-pass review started')
        def digest(value):
            return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        baseline = snapshot['baseline_hashes']
        self.assertEqual(len(baseline), snapshot['baseline_registered'])
        self.assertEqual([n['question_id'] for n in self.data['items'][:len(baseline)]], list(baseline))
        for id, expected in baseline.items():
            self.assertEqual(digest(self.notes[id]), expected, id)
        for ref, expected in snapshot['baseline_source_hashes'].items():
            self.assertEqual(digest(self.data['sources'][ref]), expected, ref)
        records = [b for b in self.audit['extra_rechecks'] if b.get('extra_round',4)==6]
        processed = [id for b in records for id in b['assigned_ids']]
        self.assertEqual(len(processed), len(set(processed)))
        target = set(snapshot['initial_review_ids'])
        self.assertEqual(len(target), snapshot['initial_review_count'])
        self.assertTrue(set(processed) <= target)
        new = set(self.notes)-set(baseline)
        pending = {r['question_id'] for r in self.audit['review']}
        self.assertFalse(new & pending)
        self.assertEqual(new | pending, target)
        if snapshot['complete']:
            self.assertEqual(set(processed),target)
            self.assertEqual(snapshot['unprocessed_ids'],[])

    def test_sixth_pass_new_explanations_have_independent_quality_evidence(self):
        snapshot = (self.audit or {}).get('sixth_pass_snapshot')
        if not snapshot or not snapshot['complete']:
            self.skipTest('Sixth-pass assignments are not complete')
        report = json.loads((R / 'reports/round6-quality-review.json').read_text())
        self.assertTrue(report['complete'])
        self.assertFalse(report['expert_reviewed'])
        def digest(value):
            return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        candidates = {id for b in self.audit['extra_rechecks'] if b.get('extra_round') == 6
                      for id in b['resolved_ids']}
        rows = {r['question_id']: r for r in report['items']}
        self.assertEqual(len(rows), len(report['items']))
        self.assertEqual(set(rows), candidates)
        withdrawals = {r['question_id']: r for r in self.audit['final_quality_withdrawals']
                       if r.get('extra_round') == 6}
        amendments = {r['question_id']: r for r in self.audit.get('sixth_pass_locator_amendments', [])
                      + self.audit.get('sixth_pass_prose_amendments', [])}
        for id, row in rows.items():
            self.assertNotEqual(row['reviewer'], row['author'], id)
            self.assertEqual(row['official_answers'], self.qs[id]['answers'], id)
            self.assertEqual(row['question_row_sha256'], digest(self.qs[id]), id)
            self.assertTrue(row['original_pdf_checked'] and row['original_image_checked'], id)
            self.assertFalse(row['expert_reviewed'], id)
            self.assertEqual({x['number'] for x in row['four_option_logic']}, {1, 2, 3, 4}, id)
            self.assertTrue(row['actual_source_reads'], id)
            for source in row['actual_source_reads']:
                self.assertTrue(source['source_read'], id)
                self.assertRegex(source['sha256'], r'^[0-9a-f]{64}$')
            for check in row['math']['checks']:
                self.assertAlmostEqual(calc(check['expr']), check['expected'], places=6, msg=id)
            if id in withdrawals:
                self.assertEqual(row['status'], 'issue', id)
                self.assertEqual(row['explanation_sha256'], withdrawals[id]['before_hash'], id)
                self.assertNotIn(id, self.notes)
            else:
                self.assertEqual(row['status'], 'pass', id)
                if id in amendments:
                    amendment = amendments[id]
                    self.assertEqual(row['explanation_sha256'], amendment['before_hash'], id)
                    self.assertEqual(digest(self.notes[id]), amendment['after_hash'], id)
                    before = dict(amendment['before'])
                    after = dict(self.notes[id])
                    if amendment in self.audit.get('sixth_pass_prose_amendments', []):
                        self.assertEqual(amendment['changed_fields'], ['option_notes'])
                        self.assertTrue(amendment['final_independent_followup']['passed'])
                        for old, new in zip(before['option_notes'], after['option_notes']):
                            self.assertEqual({k:v for k,v in old.items() if k!='reason'},
                                             {k:v for k,v in new.items() if k!='reason'}, id)
                        for check in amendment['checks']:
                            self.assertAlmostEqual(calc(check['expr']), check['expected'], places=6, msg=id)
                        before.pop('option_notes'); after.pop('option_notes')
                    else:
                        before.pop('sources'); after.pop('sources')
                    self.assertEqual(before, after, id)
                else:
                    self.assertEqual(row['explanation_sha256'], digest(self.notes[id]), id)
        # This historical QA report covers sixth-pass candidates only. Later
        # additions have their own immutable baseline and independent QA ledger.
        new = set(self.notes) & candidates
        self.assertEqual(new, candidates - set(withdrawals))
        self.assertEqual(report['registered_pass_count'], len(new))
        self.assertEqual(report['withdrawn_issue_count'], len(withdrawals))

    def assert_protected_file(self, name, sha):
        """A file pinned by an audit baseline must still have that hash. Only the app's UI files
        may move on along reports/ui-changes.json. The HTML entrypoint has a separate
        exact, reversible script-reference amendment; all earlier HTML bytes are still checked."""
        body = (R / name).read_bytes()
        if name == 'index.html':
            from loader_entrypoint import restore_entrypoint
            body = restore_entrypoint(body)
        current = hashlib.sha256(body).hexdigest()
        if name in UI_FILES:
            for change in json.loads((R / 'reports/ui-changes.json').read_text())['changes']:
                step = change['files'].get(name)
                if step and step['before'] == sha:
                    sha = step['after']
        self.assertEqual(current, sha, name)

    def test_bundle_line_break_decisions_match_build(self):
        import sys
        sys.path.insert(0, str(R / 'scripts'))
        from choice_breaks import corpus_counts, choice_breaks, stem_breaks
        raw = (R / 'assets/bank-data.js').read_text()
        b = json.loads(raw[len('window.BANK_DATA='):-2])
        # Example: the PDF wrapped '비재\n무적' mid-word; the stem decision joins it without a space.
        q = self.qs['2023-06-112']
        texts = [x['text'] for x in self.qs.values()]
        texts += [s for n in self.current_data['items']
                  for s in [n['summary'], *n['steps'], *[o['reason'] for o in n['option_notes']]]]
        words, pairs = corpus_counts(texts)
        self.assertEqual(stem_breaks(q['text'], words, pairs), 'j')
        self.assertEqual(b['stemBreaks']['2023-06-112'], 'j')
        for row in b['questions']:
            self.assertEqual(b['choiceBreaks'].get(row['id'], ''), choice_breaks(row['text'], words, pairs), row['id'])
            sb = stem_breaks(row['text'], words, pairs)
            self.assertEqual(b['stemBreaks'].get(row['id'], ''), sb if set(sb) - {'k'} else '', row['id'])

    def test_theme_text_colours_meet_wcag_contrast(self):
        css = (R / 'assets/app.css').read_text()
        def theme(block):
            found = re.findall(r'--([a-z0-9-]+):#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b', block)
            return {k: '#' + (v if len(v) == 6 else ''.join(c * 2 for c in v)) for k, v in found}
        def block(start):
            i = css.index(start)
            return css[i:css.index('}', i)]
        light = theme(block(':root{'))
        dark = {**light, **theme(block('@media(prefers-color-scheme:dark){:root:not([data-theme=light]){'))}
        forced_dark = {**light, **theme(block(':root[data-theme=dark]{'))}
        def lum(h):
            c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
            return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        def ratio(a, b):
            hi, lo = sorted((lum(a), lum(b)), reverse=True)
            return (hi + 0.05) / (lo + 0.05)
        # Body-size text pairs used across the app must reach WCAG AA (4.5:1).
        pairs = [('ink', 'bg'), ('ink-2', 'surface'), ('muted', 'bg'), ('muted', 'surface-2'), ('faint', 'bg'),
                 ('faint', 'surface-2'), ('accent', 'accent-soft'), ('ok', 'ok-bg'), ('bad', 'bad-bg'),
                 ('warn', 'warn-bg'), ('brand-text', 'surface'), ('brand-ink', 'brand'), ('brand-ink', 'brand-hover')]
        for name, colours in (('light', light), ('dark', dark), ('forced dark', forced_dark)):
            for fg, bg in pairs:
                self.assertGreaterEqual(ratio(colours[fg], colours[bg]), 4.5, (name, fg, bg))

    def test_ui_change_log_is_a_chain_ending_at_current_files(self):
        log = json.loads((R / 'reports/ui-changes.json').read_text())
        for name in UI_FILES:
            steps = [c['files'][name] for c in log['changes'] if name in c['files']]
            for prev, nxt in zip(steps, steps[1:]):
                self.assertEqual(prev['after'], nxt['before'], name)
            if steps:
                self.assertEqual(hashlib.sha256((R / name).read_bytes()).hexdigest(), steps[-1]['after'], name)
        for change in log['changes']:
            self.assertTrue(change['summary'] and change['date'])
            self.assertTrue(set(change['files']) <= UI_FILES)

    @classmethod
    def setUpClass(cls):
        def read(name):
            return json.loads((R / 'data' / (name + '.json')).read_text())
        cls.current_data = read('explanations')
        cls.qs = {q['id']: q for q in read('questions')}
        cls.entries = {e['id'] for e in read('entries')}
        cls.parts = {p['id'] for p in read('taxonomy')}
        audit = R / 'reports/explanation-expansion.json'
        cls.audit = json.loads(audit.read_text()) if audit.exists() else None
        # Historical protection checks run against the content before the recorded
        # post-review amendments; test_post_review_amendments verifies each before/after hash.
        cls.data = copy.deepcopy(cls.current_data)
        cls.stage_after = {}
        cls.audit_after = {}
        # Reverse the latest source checks before all historical protection tests.
        round27 = (cls.audit or {}).get('round27_sources')
        if round27:
            cls.stage_after['round27_sources'] = copy.deepcopy(cls.data)
            cls.audit_after['round27_sources'] = copy.deepcopy(cls.audit)
            index = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in round27['amendments']:
                cls.data['items'][index[record['question_id']]] = copy.deepcopy(record['before'])
            for ref in round27['new_source_refs']:
                del cls.data['sources'][ref]
            del cls.audit['round27_sources']
        cls.before_round27_data = copy.deepcopy(cls.data)
        cls.before_round27_audit = copy.deepcopy(cls.audit)
        # Newest stage: round-4 wording clean-up (double spaces, comma spacing, doubled periods).
        wording4 = (cls.audit or {}).get('wording_round4')
        if wording4:
            cls.stage_after['wording_round4'] = copy.deepcopy(cls.data)
            cls.audit_after['wording_round4'] = copy.deepcopy(cls.audit)
            index = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in wording4['notes']:
                cls.data['items'][index[record['question_id']]] = copy.deepcopy(record['before'])
            del cls.audit['wording_round4']
        cls.before_wording4 = copy.deepcopy(cls.data)
        # Next: round-5 spacing (space before a circled option number after Hangul).
        spacing5 = (cls.audit or {}).get('spacing_round5')
        if spacing5:
            cls.stage_after['spacing_round5'] = copy.deepcopy(cls.data)
            cls.audit_after['spacing_round5'] = copy.deepcopy(cls.audit)
            index = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in spacing5['notes']:
                cls.data['items'][index[record['question_id']]] = copy.deepcopy(record['before'])
            del cls.audit['spacing_round5']
        cls.before_spacing5 = copy.deepcopy(cls.data)
        # Next: round-4 spacing (rejoins counters/suffixes split off English words).
        spacing4 = (cls.audit or {}).get('spacing_round4')
        if spacing4:
            cls.stage_after['spacing_round4'] = copy.deepcopy(cls.data)
            cls.audit_after['spacing_round4'] = copy.deepcopy(cls.audit)
            index = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in spacing4['notes']:
                cls.data['items'][index[record['question_id']]] = copy.deepcopy(record['before'])
            del cls.audit['spacing_round4']
        cls.before_spacing4 = copy.deepcopy(cls.data)
        # Next: round-3 spacing (whitespace only, Hangul followed by an English word).
        spacing3 = (cls.audit or {}).get('spacing_round3')
        if spacing3:
            cls.stage_after['spacing_round3'] = copy.deepcopy(cls.data)
            cls.audit_after['spacing_round3'] = copy.deepcopy(cls.audit)
            index = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in spacing3['notes']:
                cls.data['items'][index[record['question_id']]] = copy.deepcopy(record['before'])
            del cls.audit['spacing_round3']
        cls.before_spacing3 = copy.deepcopy(cls.data)
        # Next: round-3 wording fixes (particles, contaminated common-instruction quotes).
        wording3 = (cls.audit or {}).get('wording_round3')
        if wording3:
            cls.stage_after['wording_round3'] = copy.deepcopy(cls.data)
            cls.audit_after['wording_round3'] = copy.deepcopy(cls.audit)
            index = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in wording3['notes']:
                cls.data['items'][index[record['question_id']]] = copy.deepcopy(record['before'])
            del cls.audit['wording_round3']
        cls.before_wording3 = copy.deepcopy(cls.data)
        # Next: the round-2 spacing fix only changed whitespace; restore the before objects
        # so every earlier ledger (round 26 and older) is checked against what it recorded.
        spacing2 = (cls.audit or {}).get('spacing_round2')
        if spacing2:
            cls.stage_after['spacing_round2'] = copy.deepcopy(cls.data)
            cls.audit_after['spacing_round2'] = copy.deepcopy(cls.audit)
            index = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in spacing2['notes']:
                cls.data['items'][index[record['question_id']]] = copy.deepcopy(record['before'])
            del cls.audit['spacing_round2']
        cls.before_spacing2 = copy.deepcopy(cls.data)
        # Reverse round 26 first; every earlier ledger keeps its original checks.
        # The concept wording fix (reports/concept-wording.json) is newer than round 26; undo it so
        # round 26 and older concept checks see the file they recorded.
        cls.concepts_before_wording = read('concept-notes')
        wording_path = R / 'reports/concept-wording.json'
        if wording_path.exists():
            index = {n['id']: i for i, n in enumerate(cls.concepts_before_wording['notes'])}
            for record in json.loads(wording_path.read_text())['notes']:
                cls.concepts_before_wording['notes'][index[record['note_id']]] = copy.deepcopy(record['before'])
        cls.before_round26_concepts = copy.deepcopy(cls.concepts_before_wording)
        cls.before_round26_concept_audit = json.loads((R/'reports/concept-expansion.json').read_text())
        round26 = (cls.audit or {}).get('round26_followups')
        if round26:
            cls.stage_after['round26_followups'] = copy.deepcopy(cls.data)
            cls.audit_after['round26_followups'] = copy.deepcopy(cls.audit)
            indices = {n['question_id']:i for i,n in enumerate(cls.data['items'])}
            for record in reversed(round26['amendments']):
                cls.data['items'][indices[record['question_id']]] = copy.deepcopy(record['before'])
            for ref in round26['new_source_refs']:
                del cls.data['sources'][ref]
            ci = {n['id']:i for i,n in enumerate(cls.before_round26_concepts['notes'])}
            for record in reversed(round26['concept_amendments']):
                cls.before_round26_concepts['notes'][ci[record['note_id']]] = copy.deepcopy(record['before'])
                # Exact appended audit rows are verified by the dedicated test.
                cls.before_round26_concept_audit['followup_note_amendments'].pop()
            for ref in round26['new_concept_source_refs']:
                del cls.before_round26_concepts['sources'][ref]
            del cls.audit['round26_followups']
        cls.before_round26_data = copy.deepcopy(cls.data)
        cls.before_round26_audit = copy.deepcopy(cls.audit)
        round24 = (cls.audit or {}).get('round24_followups')
        if round24:
            cls.stage_after['round24_followups'] = copy.deepcopy(cls.data)
            cls.audit_after['round24_followups'] = copy.deepcopy(cls.audit)
            registered = {r['question_id'] for r in round24['registrations']}
            cls.data['items'] = [n for n in cls.data['items'] if n['question_id'] not in registered]
            for ref in round24['new_source_refs']:
                del cls.data['sources'][ref]
            cls.audit['review'] = copy.deepcopy(round24['original_review'])
            del cls.audit['round24_followups']
        round23 = (cls.audit or {}).get('round23_followups')
        if round23:
            cls.stage_after['round23_followups'] = copy.deepcopy(cls.data)
            cls.audit_after['round23_followups'] = copy.deepcopy(cls.audit)
            registered = {r['question_id'] for r in round23['registrations']}
            cls.data['items'] = [n for n in cls.data['items'] if n['question_id'] not in registered]
            for ref in round23['new_source_refs']:
                del cls.data['sources'][ref]
            cls.audit['review'] = copy.deepcopy(round23['original_review'])
            del cls.audit['round23_followups']
        round22 = (cls.audit or {}).get('round22_followups')
        if round22:
            cls.stage_after['round22_followups'] = copy.deepcopy(cls.data)
            cls.audit_after['round22_followups'] = copy.deepcopy(cls.audit)
            registered = {r['question_id'] for r in round22['registrations']}
            cls.data['items'] = [n for n in cls.data['items'] if n['question_id'] not in registered]
            for ref in round22['new_source_refs']:
                del cls.data['sources'][ref]
            cls.audit['review'] = copy.deepcopy(round22['original_review'])
            del cls.audit['round22_followups']
        round21 = (cls.audit or {}).get('round21_inspections')
        if round21:
            # Reverse the newest adjudication-only stage before round20 and all
            # older protected snapshots. Completed study data was not edited.
            cls.stage_after['round21_inspections'] = copy.deepcopy(cls.data)
            cls.audit_after['round21_inspections'] = copy.deepcopy(cls.audit)
            cls.audit['answer_adjudication'] = copy.deepcopy(round21['before_adjudication'])
            del cls.audit['round21_inspections']
        cls.before_round20_concepts = copy.deepcopy(cls.before_round26_concepts)
        round20 = (cls.audit or {}).get('round20_followups')
        if round20:
            # Restore this newest stage before the unchanged registration-ledger
            # loop, so round17 and every earlier protection check see their own
            # recorded objects and pending rows.
            cls.stage_after['round20_followups'] = copy.deepcopy(cls.data)
            cls.audit_after['round20_followups'] = copy.deepcopy(cls.audit)
            indices = {n['question_id']:i for i,n in enumerate(cls.data['items'])}
            for record in reversed(round20['amendments']):
                cls.data['items'][indices[record['question_id']]] = copy.deepcopy(record['before'])
            added = {r['question_id'] for r in round20['registrations']}
            cls.data['items'] = [n for n in cls.data['items'] if n['question_id'] not in added]
            for ref in round20['new_source_refs']:
                del cls.data['sources'][ref]
            cls.audit['review'] = copy.deepcopy(round20['original_review'])
            ci = {n['id']:i for i,n in enumerate(cls.before_round20_concepts['notes'])}
            for record in reversed(round20['concept_amendments']):
                cls.before_round20_concepts['notes'][ci[record['note_id']]] = copy.deepcopy(record['before'])
            for ref in round20['new_concept_source_refs']:
                del cls.before_round20_concepts['sources'][ref]
        cls.before_round20_data = copy.deepcopy(cls.data)
        for key in REGISTRATION_LEDGERS:
            group = (cls.audit or {}).get(key)
            if not group:
                continue
            # Newest stages first: remove each round's registrations and restore their review
            # rows so every earlier ledger sees exactly the state it recorded.
            cls.stage_after[key] = copy.deepcopy(cls.data)
            cls.audit_after[key] = copy.deepcopy(cls.audit)
            added = {r['question_id'] for r in group['items']}
            cls.data['items'] = [n for n in cls.data['items'] if n['question_id'] not in added]
            for ref in group['new_source_refs']:
                del cls.data['sources'][ref]
            cls.audit['review'] = cls.audit['review'] + [r['previous_review'] for r in group['items']]
        cls.current_audit = copy.deepcopy(cls.audit)
        rewrites = (cls.audit or {}).get('round12_option_rewrites')
        if rewrites:
            cls.stage_after['round12_option_rewrites'] = copy.deepcopy(cls.data)
            indices = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in reversed(rewrites['notes']):
                cls.data['items'][indices[record['question_id']]] = copy.deepcopy(record['before'])
        corrections = (cls.audit or {}).get('round11_corrections')
        if corrections:
            # Newest stage first: restore the post-round-10 objects so every earlier
            # ledger (round 10, round 9, spacing, post-review) is checked unchanged.
            cls.stage_after['round11_corrections'] = copy.deepcopy(cls.data)
            indices = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in reversed(corrections['notes']):
                cls.data['items'][indices[record['question_id']]] = copy.deepcopy(record['before'])
        cls.latest_notes = {n['question_id']: n for n in cls.data['items']}
        followups = (cls.audit or {}).get('round10_followups')
        if followups:
            # Undo the newest data stage before the unchanged round-9/spacing/
            # post-review checks. Current verdicts remain visible to the existing
            # bundle assertion; their complete before/after ledger is checked below.
            cls.stage_after['round10_followups'] = copy.deepcopy(cls.data)
            indices = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
            for record in reversed(followups['amendments']):
                cls.data['items'][indices[record['question_id']]] = copy.deepcopy(record['before'])
            registered = {r['question_id'] for r in followups['registrations']}
            cls.data['items'] = [n for n in cls.data['items'] if n['question_id'] not in registered]
            for ref in followups['new_source_refs']:
                del cls.data['sources'][ref]
            cls.audit['review'] = copy.deepcopy(followups['original_review'])
        cls.before_round10_data = copy.deepcopy(cls.data)
        registrations = (cls.audit or {}).get('round9_registrations', {})
        if registrations:
            cls.stage_after['round9_registrations'] = copy.deepcopy(cls.data)
            registered = {r['question_id'] for r in registrations['items']}
            cls.data['items'] = [n for n in cls.data['items'] if n['question_id'] not in registered]
            for ref in registrations.get('new_source_refs', []):
                del cls.data['sources'][ref]
            cls.audit['review'] = cls.audit['review'] + [r['previous_review'] for r in registrations['items']]
        items = {n['question_id']: i for i, n in enumerate(cls.data['items'])}
        for group in ('spacing_amendments', 'post_review_amendments'):  # newest first
            cls.stage_after[group] = copy.deepcopy(cls.data)
            amendments = (cls.audit or {}).get(group, {})
            for record in reversed(amendments.get('notes', [])):
                cls.data['items'][items[record['question_id']]] = copy.deepcopy(record['before'])
            for record in reversed(amendments.get('sources', [])):
                cls.data['sources'][record['ref']] = copy.deepcopy(record['before'])
        cls.notes = {n['question_id']: n for n in cls.data['items']}
        cls.current_notes = {n['question_id']: n for n in cls.before_round10_data['items']}
        cls.baseline_ids = set(cls.audit['baseline_hashes']) if cls.audit else set(list(cls.notes)[:30])

    def validate(self, data=None, qs=None):
        return validate_explanations(data or self.current_data, qs or self.qs, self.entries, self.parts)

    def assert_preserved_or_source_upgraded(self, id, expected_hash):
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        upgrades = {u['question_id']: u for u in self.audit.get('baseline_source_upgrades', [])}
        if id not in upgrades:
            self.assertEqual(digest(self.notes[id]), expected_hash, id)
            return
        u = upgrades[id]
        self.assertIn(id, self.baseline_ids)
        self.assertEqual(self.qs[id]['subject'], '재무회계')
        self.assertEqual(digest(u['before']), expected_hash, id)
        self.assertEqual(digest(self.notes[id]), u['after_hash'], id)
        self.assertEqual(u['before']['review_status'], 'partial')
        self.assertEqual(self.notes[id]['review_status'], 'source_checked')
        self.assertTrue(u['source_reads'] and u['reason'] and u['validation'], id)
        self.assertEqual(set(u['changed_fields']), {'sources', 'review_status', 'review_note', 'unchecked_points'})
        for field in set(u['before']) - set(u['changed_fields']):
            self.assertEqual(self.notes[id][field], u['before'][field], id)
        self.assertEqual(self.notes[id]['sources'][:len(u['before']['sources'])], u['before']['sources'], id)
        self.assertFalse(self.notes[id]['unchecked_points'])

    def test_coverage_original_binding_and_four_options(self):
        self.validate()
        self.assertGreaterEqual(len(self.notes), 30)
        self.assertEqual(Counter(self.qs[id]['subject'] for id in self.baseline_ids),
                         {'재무회계': 10, '세무회계': 10, '원가관리회계': 10})
        self.assertNotIn('2024-09-063', self.notes)
        for id, n in self.notes.items():
            self.assertEqual(n['part_id'], self.qs[id]['classification']['primary_part_id'])
            self.assertTrue(n['authorship'] and n['checked_on'])

    def test_calculations_and_specific_answer_regressions(self):
        for n in self.notes.values():
            for check in n['checks']:
                self.assertAlmostEqual(calc(check['expr']), check['expected'], places=6,
                                       msg=n['question_id'] + ': ' + check['label'])
        expected = {
            '2026-01-006': 4300000, '2026-01-008': 1050000, '2026-01-032': 500,
            '2026-01-054': 12800000, '2026-09-054': 1000000,
            '2026-05-054': 44000000, '2026-01-062': 28000000,
            '2026-03-062': 36500000, '2026-05-062': 36500000, '2026-09-062': 36000000,
            '2026-03-077': 6000, '2026-05-077': 6000, '2026-09-077': 7000,
            '2026-09-095': 300, '2026-09-104': 10000, '2026-09-114': -21000,
            '2026-07-114': 310, '2026-07-115': 100000,
        }
        for id, value in expected.items():
            self.assertAlmostEqual(calc(self.notes[id]['checks'][-1]['expr']), value, places=6, msg=id)
        a, b = self.notes['2026-01-094'], self.notes['2026-09-094']
        self.assertEqual(a['checks'][0]['expected'], 13500)
        self.assertEqual(b['checks'][0]['expected'], 4500)
        self.assertNotEqual(a['answers'], b['answers'])

    def test_review_status_and_exact_source_years(self):
        self.assertFalse(self.data['verification']['expert_reviewed'])
        for id, n in self.notes.items():
            upgraded = {u['question_id'] for u in (self.audit or {}).get('baseline_source_upgrades', [])}
            if id in self.baseline_ids and self.qs[id]['subject'] == '재무회계' and id not in upgraded:
                self.assertEqual(n['review_status'], 'partial')
                self.assertTrue(n['unchecked_points'])
                self.assertTrue(all(s['ref'].startswith('NOTE_') for s in n['sources']))
            else:
                self.assertEqual(n['review_status'], 'source_checked')
            if self.qs[id]['subject'] == '세무회계':
                self.assertEqual(n['tax_law_year'], self.qs[id]['tax_law_year'])
            for s in n['sources']:
                src = self.data['sources'][s['ref']]
                self.assertTrue(src['checked_on'] and src['verification'] and src['version'])
        self.assertEqual(self.notes['2026-03-062']['tax_law_year'], 2025)
        self.assertEqual(self.notes['2026-09-062']['tax_law_year'], 2026)

    def test_expansion_preserves_baseline_and_separates_reviews(self):
        if not self.audit:
            self.skipTest('No expansion audit yet')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        for id, hash in self.audit['baseline_hashes'].items():
            self.assert_preserved_or_source_upgraded(id, hash)
        for ref, hash in self.audit['baseline_source_hashes'].items():
            self.assertEqual(digest(self.data['sources'][ref]), hash, ref)
        self.assertEqual(self.audit['registered_count'], len(self.notes))
        assigned = [id for b in self.audit['batches'] for id in b['assigned_ids']]
        self.assertEqual(len(assigned), len(set(assigned)))
        accepted = {id for b in self.audit['batches'] for id in b['accepted_ids']}
        reviews = {n['question_id'] for n in self.audit['review']}
        pending = set(self.audit['unprocessed_ids'])
        self.assertEqual(accepted, set(self.notes) - self.baseline_ids)
        self.assertFalse(accepted & reviews or accepted & pending or reviews & pending)
        self.assertEqual(set(assigned), accepted | reviews)
        eligible = {id for id in self.entries if self.qs[id]['study_eligible']}
        self.assertEqual(eligible, self.baseline_ids | accepted | reviews | pending)
        for id in accepted:
            self.assertEqual(self.notes[id]['review_status'], 'source_checked')
            self.assertEqual(self.notes[id]['unchecked_points'], [])

    def test_second_pass_review_transitions(self):
        if not self.audit or not self.audit.get('rechecks'):
            self.skipTest('No second-pass audit yet')
        records = self.audit['rechecks']
        ids = [id for b in records for id in b['assigned_ids']]
        self.assertEqual(len(ids), len(set(ids)), 'second-pass assignments overlap')
        self.assertEqual(self.audit['rechecked_count'], len(ids))
        reviews = {n['question_id']: n for n in self.audit['review']}
        resolved = {n['question_id']: n for n in self.audit['review_resolutions']
                    if 'recheck_batch_id' in n}
        later = {n['question_id']: n for n in self.audit['review_resolutions']
                 if 'round3_batch_id' in n or 'extra_batch_id' in n}
        withdrawn = self.active_quality_withdrawals()
        for b in records:
            self.assertTrue(20 <= len(b['assigned_ids']) <= 30)
            prior = {n['question_id'] for n in b['previous_review']}
            done, remaining = set(b['resolved_ids']), set(b['remaining_ids'])
            self.assertFalse(done & remaining)
            self.assertEqual(prior, set(b['assigned_ids']))
            self.assertEqual(prior, done | remaining)
            self.assertTrue(b['output_hash'] and b['worker_validation'])
            for id in done:
                self.assertIn(id, self.notes)
                self.assertEqual(resolved[id]['recheck_batch_id'], b['batch_id'])
                self.assertTrue(resolved[id]['previous_reason'])
            for id in remaining:
                if id in later:
                    if id in withdrawn:
                        self.assertTrue(reviews[id]['final_quality_withdrawal'])
                        self.assertNotIn(id,self.notes)
                    else:self.assertIn(id, self.notes)
                    self.assertTrue(later[id]['previous_reason'])
                else:
                    self.assertEqual(reviews[id]['recheck_batch_id'], b['batch_id'])
        self.assertEqual(self.audit['second_pass_added_count'], len(resolved))

    def test_followup_review_transitions_and_existing_explanations(self):
        if not self.audit or not self.audit.get('third_pass_batches'):
            self.skipTest('No follow-up audit yet')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        records = self.audit['third_pass_batches']
        ids = [id for b in records for id in b['assigned_ids']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), self.audit['third_pass_processed_count'])
        self.assertLessEqual(len(ids), self.audit['third_pass_target_count'])
        pending = set(self.audit.get('third_pass_unprocessed_ids', []))
        if 'third_pass_unprocessed_ids' in self.audit:
            self.assertFalse(set(ids) & pending)
            self.assertEqual(len(ids) + len(pending), self.audit['third_pass_target_count'])
            self.assertEqual(self.audit['third_pass_complete'], not pending)
        for id, h in self.audit['third_pass_baseline_hashes'].items():
            self.assert_preserved_or_source_upgraded(id, h)
        for ref, h in self.audit['third_pass_baseline_source_hashes'].items():
            self.assertEqual(digest(self.data['sources'][ref]), h, ref)
        reviews = {n['question_id']: n for n in self.audit['review']}
        resolved = {n['question_id']: n for n in self.audit['review_resolutions']
                    if 'round3_batch_id' in n}
        extra = {n['question_id']: n for n in self.audit['review_resolutions']
                 if 'extra_batch_id' in n}
        withdrawn = self.active_quality_withdrawals()
        for b in records:
            assigned, done, remaining = map(set, (b['assigned_ids'], b['resolved_ids'], b['remaining_ids']))
            self.assertTrue(20 <= len(assigned) <= 30)
            self.assertFalse(done & remaining)
            self.assertEqual(assigned, done | remaining)
            self.assertEqual(assigned, {n['question_id'] for n in b['previous_review']})
            self.assertTrue(b['worker_validation'] and b['output_hash'])
            for id in done:
                if id in withdrawn:
                    self.assertNotIn(id,self.notes)
                    self.assertTrue(reviews[id]['final_quality_withdrawal'])
                else:self.assertIn(id, self.notes)
                self.assertEqual(resolved[id]['round3_batch_id'], b['batch_id'])
            for id in remaining:
                if id in extra:
                    self.assertEqual(extra[id]['previous_review']['round3_batch_id'], b['batch_id'])
                    if id in withdrawn:
                        self.assertNotIn(id,self.notes)
                        self.assertTrue(reviews[id]['final_quality_withdrawal'])
                    else:
                        self.assertIn(id, self.notes)
                else:
                    self.assertEqual(reviews[id]['round3_batch_id'], b['batch_id'])
        self.assertEqual(self.audit['third_pass_added_count'], len(resolved))
        self.assertEqual(set(self.notes), (set(self.audit['third_pass_baseline_hashes']) | set(resolved) | set(extra))-withdrawn)

    def test_independent_cross_review_preserves_prior_rounds(self):
        records = (self.audit or {}).get('extra_rechecks', [])
        if not records:
            self.skipTest('No extra cross-review imported yet')
        ids = [id for b in records for id in b['assigned_ids']]
        self.assertEqual(len(ids), self.audit['extra_rechecked_count'])
        for round_number in {b.get('extra_round',4) for b in records}:
            round_ids=[id for b in records if b.get('extra_round',4)==round_number for id in b['assigned_ids']]
            self.assertEqual(len(round_ids),len(set(round_ids)),'overlap within one extra round')
        if 'extra_rechecked_unique_count' in self.audit:
            self.assertEqual(len(set(ids)),self.audit['extra_rechecked_unique_count'])
        resolved = {r['question_id']: r for r in self.audit['review_resolutions'] if 'extra_batch_id' in r}
        reviews = {r['question_id']: r for r in self.audit['review']}
        withdrawn = self.active_quality_withdrawals()
        self.assertEqual(len(resolved), self.audit['extra_added_count'])
        for index,b in enumerate(records):
            self.assertTrue(20 <= len(b['assigned_ids']) <= 30)
            done, remaining = set(b['resolved_ids']), set(b['remaining_ids'])
            self.assertFalse(done & remaining)
            self.assertEqual(set(b['assigned_ids']), done | remaining)
            self.assertEqual(set(b['assigned_ids']), {r['question_id'] for r in b['previous_review']})
            self.assertTrue(b['output_hash'] and b['worker_validation'])
            for id in done:
                if id in withdrawn:
                    self.assertNotIn(id, self.notes)
                    self.assertTrue(reviews[id]['final_quality_withdrawal'])
                else:
                    self.assertIn(id, self.notes)
                self.assertEqual(resolved[id]['extra_batch_id'], b['batch_id'])
                self.assertTrue(resolved[id]['previous_reason'])
            for id in remaining:
                later=[x for x in records[index+1:] if id in x['assigned_ids']]
                if later:
                    previous=next(r for r in later[0]['previous_review'] if r['question_id']==id)
                    self.assertEqual(previous['extra_batch_id'],b['batch_id'])
                if id in resolved and id not in withdrawn:
                    self.assertIn(id,self.notes)
                else:
                    self.assertEqual(reviews[id]['extra_batch_id'],later[-1]['batch_id'] if later else b['batch_id'])

    def test_source_links_point_to_actual_law_repository(self):
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        for ref, source in self.data['sources'].items():
            self.assertNotIn('github.com/legalize-dev/legalize-kr/', source['url'], ref)
        for correction in (self.audit or {}).get('source_url_corrections', []):
            ref = correction['ref']
            self.assertEqual(digest(correction['before']), correction['before_hash'])
            self.assertEqual(digest(self.data['sources'][ref]), correction['after_hash'])
            self.assertTrue(correction['git_blob_sha256'] and correction['reason'])
            before, after = dict(correction['before']), dict(correction['after'])
            self.assertTrue(after.pop('url').startswith('https://github.com/legalize-kr/legalize-kr/blob/'))
            before.pop('url')
            self.assertEqual(before, after)

    def test_targeted_prose_amendments_keep_answers_and_calculations(self):
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        histories = {}
        withdrawn = {n['question_id']:n for n in (self.audit or {}).get('final_quality_withdrawals', [])}
        for amendment in (self.audit or {}).get('third_pass_prose_amendments', []):
            id = amendment['question_id']
            self.assertNotIn(id, self.audit['third_pass_baseline_hashes'])
            self.assertTrue(set(amendment['changed_fields']) <= {'summary', 'steps', 'option_notes'})
            self.assertTrue(amendment['reason'] and amendment['delta_hash'])
            histories.setdefault(id, []).append(amendment)
        for id, chain in histories.items():
            for index, amendment in enumerate(chain):
                after = (chain[index + 1]['before'] if index + 1 < len(chain)
                         else withdrawn[id]['before'] if id in withdrawn else self.notes[id])
                self.assertEqual(digest(after), amendment['after_hash'], id)
                for field, value in amendment['before'].items():
                    if field not in amendment['changed_fields']:
                        self.assertEqual(after[field], value, id + ': ' + field)
                for old, new in zip(amendment['before']['option_notes'],after['option_notes']):
                    self.assertEqual({k:v for k,v in old.items() if k!='reason'},
                                     {k:v for k,v in new.items() if k!='reason'},id)

    def test_quality_withdrawals_preserve_history_and_official_questions(self):
        def digest(x):
            return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        reviews={r['question_id']:r for r in (self.audit or {}).get('review',[])}
        withdrawn=(self.audit or {}).get('final_quality_withdrawals',[])
        ids=[r['question_id'] for r in withdrawn]
        self.assertEqual(len(ids),len(set(ids)))
        active = self.active_quality_withdrawals()
        for row in withdrawn:
            id=row['question_id']
            self.assertNotIn(id,self.audit['third_pass_baseline_hashes'])
            if id in active:
                self.assertNotIn(id,self.notes)
                self.assertTrue(reviews[id]['final_quality_withdrawal'])
            else:
                self.assertNotIn(id,reviews)
            self.assertEqual(row['before_hash'],digest(row['before']))
            self.assertEqual(row['official_answers_preserved'],self.qs[id]['answers'])
            self.assertTrue(row['source_reads'] and row['worker_validation'] and row['proposal_hash'])
            records = self.audit['extra_rechecks'] if 'extra_batch_id' in row else self.audit['third_pass_batches']
            field = 'extra_batch_id' if 'extra_batch_id' in row else 'third_pass_batch_id'
            self.assertTrue(any(id in b['resolved_ids'] and b['batch_id']==row[field] for b in records))
            if row.get('extra_round')==6:
                self.assertNotIn(id,self.audit['sixth_pass_snapshot']['baseline_hashes'])
            if row.get('extra_round') in self.audit.get('seventh_pass_snapshot', {}).get('included_extra_rounds', [7]):
                self.assertNotIn(id,self.audit['seventh_pass_snapshot']['baseline_hashes'])
        if withdrawn:
            self.assertEqual(self.audit['third_pass_net_added_count'],self.audit['third_pass_added_count']-sum('third_pass_batch_id' in r for r in withdrawn))
            if 'extra_net_added_count' in self.audit:
                self.assertEqual(self.audit['extra_net_added_count'],self.audit['extra_added_count']-sum('extra_batch_id' in r for r in withdrawn))

    def test_source_locator_corrections_preserve_explanation_content(self):
        def digest(x):
            return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        for row in (self.audit or {}).get('final_source_locator_amendments',[]):
            id=row['question_id'];after=self.notes[id];before=row['before']
            self.assertNotIn(id,self.audit['third_pass_baseline_hashes'])
            self.assertEqual(digest(after),row['after_hash'])
            for field in set(before)-{'sources'}:self.assertEqual(before[field],after[field],id)
            self.assertEqual([s['ref'] for s in before['sources']],[s['ref'] for s in after['sources']],id)
            ref=row['source_ref'];source=self.data['sources'][ref]
            self.assertEqual(digest(source),row['source_after_hash'])
            for field in set(row['source_before'])-{'verification'}:
                self.assertEqual(source[field],row['source_before'][field],ref)
            self.assertTrue(row['reason'] and row['proposal_hash'] and row['evidence_parent_sha256'])

    def test_legal_source_effective_dates_do_not_follow_question_scope(self):
        for id, n in self.notes.items():
            q = self.qs[id]
            latest = datetime.date(q['year'], q['month'],
                                   calendar.monthrange(q['year'], q['month'])[1])
            if q['tax_law_year']:
                latest = min(latest, datetime.date(q['tax_law_year'], 12, 31))
            for citation in n['sources']:
                source = self.data['sources'][citation['ref']]
                if 'law.go.kr' not in source['url']:
                    continue
                dates = re.findall(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', source['version'])
                if len(dates) == 1:
                    effective = datetime.date(*map(int, dates[0]))
                    self.assertLessEqual(effective, latest,
                                         id + ': ' + citation['ref'] + ' · ' + source['version'])

    def test_stale_wording_options_answer_or_year_blocks_build(self):
        id = '2026-03-062'
        for field, value in [('text', 'changed number'), ('choices', ['reordered'] * 4),
                             ('answers', [1]), ('tax_law_year', 2026), ('study_eligible', False)]:
            qs = copy.deepcopy(self.qs)
            qs[id][field] = value
            with self.assertRaises(ValueError, msg=field):
                self.validate(qs=qs)
        for mutate in ('duplicate', 'answer', 'source', 'status', 'unchecked', 'option', 'check_label', 'check_number'):
            d = copy.deepcopy(self.data)
            if mutate == 'duplicate': d['items'].append(d['items'][0])
            elif mutate == 'answer': d['items'][0]['answers'] = [1]
            elif mutate == 'source': d['items'][0]['sources'][0]['ref'] = 'invented'
            elif mutate == 'status': d['items'][0]['review_status'] = 'invented'
            elif mutate == 'unchecked':
                d['items'][0]['review_status'] = 'source_checked'
                d['items'][0]['unchecked_points'] = ['검증하지 않은 내용']
            elif mutate == 'option': d['items'][0]['option_notes'][0]['is_answer'] = True
            elif mutate == 'check_label': d['items'][0]['checks'][0].pop('label')
            elif mutate == 'check_number': d['items'][0]['checks'][0]['expected'] = float('inf')
            with self.assertRaises(ValueError, msg=mutate): self.validate(d)

    def test_answer_adjudication_records_keep_official_answers_and_review_rows(self):
        adj = self.audit['answer_adjudication']
        records = adj['records']
        ids = [r['question_id'] for r in records]
        suspected = {r['question_id'] for r in self.audit['review'] if r['category'] == 'answer_suspected'}
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), suspected)
        self.assertEqual(adj['counts'], dict(Counter(r['verdict'] for r in records)))
        allowed = {'official_conflict', 'multiple_candidates', 'ambiguous_wording', 'deferred',
                   'holiday_nominal_deadline', 'official_supported'}
        for r in records:
            self.assertIn(r['verdict'], allowed)
            self.assertIs(r['official_answer_changed'], False)
            self.assertEqual(r['official_answers'], self.qs[r['question_id']]['answers'])
            self.assertTrue(r['evidence'] and r['basis'])
            self.assertNotIn(r['question_id'], self.notes)
            if r['basis'] == 'statute':
                self.assertTrue(r['source_read'])


    def test_post_review_amendments_keep_answers_and_record_hashes(self):
        amendments = (self.audit or {}).get('post_review_amendments')
        if not amendments:
            self.skipTest('No post-review amendments')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        ids = [r['question_id'] for r in amendments['notes']]
        self.assertEqual(len(ids), len(set(ids)))
        for r in amendments['notes']:
            stage = {n['question_id']: n for n in self.stage_after['post_review_amendments']['items']}
            id, before, after = r['question_id'], r['before'], stage[r['question_id']]
            self.assertEqual(digest(before), r['before_hash'], id)
            self.assertEqual(digest(after), r['after_hash'], id)
            self.assertTrue(r['reason'] and r['source_reads'], id)
            self.assertTrue(set(r['changed_fields']) <= {'summary', 'option_notes', 'sources'}, id)
            for field in set(before) - set(r['changed_fields']):
                self.assertEqual(after[field], before[field], id + ': ' + field)
            self.assertEqual(after['answers'], self.qs[id]['answers'])
            for old, new in zip(before['option_notes'], after['option_notes']):
                self.assertEqual({k: v for k, v in old.items() if k != 'reason'},
                                 {k: v for k, v in new.items() if k != 'reason'}, id)
            changed = {o['number'] for o, n in zip(before['option_notes'], after['option_notes']) if o['reason'] != n['reason']}
            self.assertEqual(changed, set(r['changed_options']), id)
            reasons = [o['reason'] for o in after['option_notes']]
            self.assertEqual(len(reasons), len(set(reasons)), id)
            if 'sources' in r['changed_fields']:
                self.assertEqual([{k: v for k, v in s.items() if k != 'locator'} for s in before['sources']],
                                 [{k: v for k, v in s.items() if k != 'locator'} for s in after['sources']], id)
        for r in amendments['sources']:
            before, after = dict(r['before']), dict(self.stage_after['post_review_amendments']['sources'][r['ref']])
            self.assertEqual(digest(r['before']), r['before_hash'], r['ref'])
            self.assertEqual(digest(after), r['after_hash'], r['ref'])
            self.assertTrue(r['reason'] and r['verification'])
            self.assertTrue(after.pop(r['field']).startswith('https://github.com/openstax/'))
            before.pop(r['field'])
            self.assertEqual(before, after)
        stage = {n['question_id']: n for n in self.stage_after['post_review_amendments']['items']}
        for id in set(stage) - set(ids):
            self.assertEqual(stage[id], self.notes[id], id)

    def test_wording_round4_reapplies_to_recorded_result(self):
        group = (self.audit_after.get('wording_round4') or {}).get('wording_round4')
        if not group:
            self.skipTest('No round-4 wording clean-up')
        import importlib.util
        spec = importlib.util.spec_from_file_location('wording4', R / 'scripts/apply_wording_round4.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        after_stage = {n['question_id']: n for n in self.stage_after['wording_round4']['items']}
        before_stage = {n['question_id']: n for n in self.before_wording4['items']}
        ids = {r['question_id'] for r in group['notes']}
        self.assertEqual(group['count'], len(ids))
        for id, before in before_stage.items():
            self.assertEqual(module.fix_note(before), after_stage[id], id)
            self.assertEqual(id in ids, before != after_stage[id], id)
        for r in group['notes']:
            self.assertEqual(r['before'], before_stage[r['question_id']])
            self.assertEqual(digest(r['before']), r['before_hash'])
            self.assertEqual(digest(after_stage[r['question_id']]), r['after_hash'])

    def test_wording_round3_applies_only_listed_fixes(self):
        group = (self.audit_after.get('wording_round3') or {}).get('wording_round3')
        if not group:
            self.skipTest('No round-3 wording fix')
        import importlib.util
        spec = importlib.util.spec_from_file_location('wording3', R / 'scripts/apply_wording_round3.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        after_stage = {n['question_id']: n for n in self.stage_after['wording_round3']['items']}
        before_stage = {n['question_id']: n for n in self.before_wording3['items']}
        self.assertEqual(group['particle_fixes'], [list(x) for x in module.PARTICLE_FIXES])
        ids = {r['question_id'] for r in group['notes']}
        self.assertEqual(group['count'], len(ids))
        for id, before in before_stage.items():
            # Re-applying the listed fixes to the stage before must give exactly the recorded result.
            self.assertEqual(module.fix_note(before, self.qs[id]), after_stage[id], id)
            self.assertEqual(id in ids, before != after_stage[id], id)
        for r in group['notes']:
            self.assertEqual(r['before'], before_stage[r['question_id']])
            self.assertEqual(digest(r['before']), r['before_hash'])
            self.assertEqual(digest(after_stage[r['question_id']]), r['after_hash'])

    def check_whitespace_ledger(self, key, before_snapshot):
        group = (self.audit_after.get(key) or {}).get(key)
        if not group:
            self.skipTest(f'No {key}')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        def strip(x):
            if isinstance(x, str):
                return re.sub(r'\s', '', x)
            if isinstance(x, list):
                return [strip(v) for v in x]
            if isinstance(x, dict):
                return {k: strip(v) for k, v in x.items()}
            return x
        after_stage = {n['question_id']: n for n in self.stage_after[key]['items']}
        before_stage = {n['question_id']: n for n in before_snapshot['items']}
        ids = [r['question_id'] for r in group['notes']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(group['count'], len(ids))
        self.assertEqual(set(after_stage), set(before_stage))
        for id in set(after_stage) - set(ids):
            self.assertEqual(after_stage[id], before_stage[id], id)
        for r in group['notes']:
            id, after = r['question_id'], after_stage[r['question_id']]
            self.assertEqual(digest(r['before']), r['before_hash'], id)
            self.assertEqual(digest(after), r['after_hash'], id)
            self.assertNotEqual(r['before'], after, id)
            self.assertEqual(strip(r['before']), strip(after), id)
            for k in after:
                if k not in ('title', 'summary', 'review_note', 'steps', 'option_notes', 'unchecked_points'):
                    self.assertEqual(r['before'][k], after[k], (id, k))
            self.assertEqual([(o['number'], o['is_answer']) for o in r['before']['option_notes']],
                             [(o['number'], o['is_answer']) for o in after['option_notes']], id)

    def test_spacing_round2_changes_only_whitespace(self):
        self.check_whitespace_ledger('spacing_round2', self.before_spacing2)

    def test_spacing_round3_changes_only_whitespace(self):
        self.check_whitespace_ledger('spacing_round3', self.before_spacing3)

    def test_spacing_round4_changes_only_whitespace(self):
        self.check_whitespace_ledger('spacing_round4', self.before_spacing4)

    def test_spacing_round5_changes_only_whitespace(self):
        self.check_whitespace_ledger('spacing_round5', self.before_spacing5)

    def test_spacing_amendments_change_only_whitespace(self):
        amendments = (self.audit or {}).get('spacing_amendments')
        if not amendments:
            self.skipTest('No spacing amendments')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        def strip(x):
            if isinstance(x, str):
                return re.sub(r'\s', '', x)
            if isinstance(x, list):
                return [strip(v) for v in x]
            if isinstance(x, dict):
                return {k: strip(v) for k, v in x.items()}
            return x
        ids = [r['question_id'] for r in amendments['notes']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(amendments['count'], len(ids))
        before_stage = {n['question_id']: n for n in self.stage_after['post_review_amendments']['items']}
        for r in amendments['notes']:
            after_stage = {n['question_id']: n for n in self.stage_after['spacing_amendments']['items']}
            id, after = r['question_id'], after_stage[r['question_id']]
            self.assertEqual(digest(r['before']), r['before_hash'], id)
            self.assertEqual(r['before'], before_stage[id], id)
            self.assertEqual(digest(after), r['after_hash'], id)
            self.assertNotEqual(r['before'], after, id)
            self.assertEqual(strip(r['before']), strip(after), id)
            self.assertTrue(set(r['changed_fields']) <= {'title', 'summary', 'steps', 'option_notes', 'unchecked_points'}, id)
            for field in set(after) - set(r['changed_fields']):
                self.assertEqual(after[field], r['before'][field], id + ': ' + field)
            def texts(x):
                return [x['title'], x['summary'], *x['steps'], *(o['reason'] for o in x['option_notes']), *x['unchecked_points']]
            for old, text in zip(texts(r['before']), texts(after)):
                if old != text:
                    self.assertNotIn('  ', text, id)
                    self.assertEqual(text, text.strip(), id)
        after_stage = {n['question_id']: n for n in self.stage_after['spacing_amendments']['items']}
        for r in amendments['notes']:
            self.assertEqual(after_stage[r['question_id']], self.current_notes[r['question_id']])
        for id in set(after_stage) - set(ids):
            self.assertEqual(after_stage[id], before_stage[id], id)
        self.assertEqual(self.stage_after['spacing_amendments']['sources'], self.stage_after['post_review_amendments']['sources'])


    def test_round9_registrations_follow_upheld_adjudication_and_independent_review(self):
        registrations = (self.current_audit or {}).get('round9_registrations')
        if not registrations:
            self.skipTest('No round-9 registrations')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        verdicts = {a['question_id']: a['verdict'] for a in self.current_audit['answer_adjudication']['records']}
        pending = {r['question_id'] for r in self.current_audit['review']}
        ids = [r['question_id'] for r in registrations['items']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(registrations['registered_count'], len(ids))
        self.assertEqual(set(self.current_notes), set(self.notes) | set(ids))
        self.assertFalse(set(ids) & set(self.notes))
        for r in registrations['items']:
            id, note = r['question_id'], self.current_notes[r['question_id']]
            self.assertNotIn(id, pending)
            self.assertEqual(r['previous_review']['question_id'], id)
            self.assertEqual(r['previous_review']['category'], 'answer_suspected')
            self.assertIn(verdicts[id], {'official_supported', 'ambiguous_wording'})
            self.assertEqual(digest(note), r['explanation_sha256'], id)
            self.assertEqual(r['question_row_sha256'], digest(self.qs[id]), id)
            self.assertEqual(note['answers'], self.qs[id]['answers'])
            self.assertEqual(r['official_answers'], self.qs[id]['answers'])
            self.assertNotEqual(r['author'], r['reviewer'], id)
            review = r['independent_review']
            self.assertEqual(review['status'], 'pass', id)
            self.assertEqual({x['number'] for x in review['four_option_logic']}, {1, 2, 3, 4}, id)
            self.assertTrue(all(x['status'] == 'pass' for x in review['four_option_logic']), id)
            self.assertTrue(r['source_reads'], id)
            for read in r['source_reads']:
                self.assertRegex(read['sha256'], r'^[0-9a-f]{64}$')
            for check in note['checks']:
                self.assertAlmostEqual(calc(check['expr']), check['expected'], places=6, msg=id)
            reasons = [o['reason'] for o in note['option_notes']]
            self.assertEqual(len(reasons), len(set(reasons)), id)
        for ref in registrations['new_source_refs']:
            self.assertIn(ref, self.current_data['sources'])
            self.assertNotIn(ref, self.data['sources'])


    def test_round11_corrections_change_only_recorded_text(self):
        group = (self.current_audit or {}).get('round11_corrections')
        if not group:
            self.skipTest('No round-11 corrections')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        current = {n['question_id']: n for n in self.stage_after['round11_corrections']['items']}
        previous = self.latest_notes
        ids = [r['question_id'] for r in group['notes']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(group['count'], len(ids))
        self.assertEqual(group['rejected_spacing_keys'], [])
        protected = ('question_id', 'question_fingerprint', 'answers', 'part_id', 'checks', 'sources',
                     'tax_law_year', 'authorship')
        kinds = {'spacing', 'wording', 'content', 'status'}
        def value(note, field, index):
            if field == 'option_notes':
                return next(o for o in note['option_notes'] if o['number'] == index)['reason']
            if index is None:
                return note[field]
            return note[field][index]
        for r in group['notes']:
            id, before, after = r['question_id'], r['before'], current[r['question_id']]
            self.assertEqual(before, previous[id], id)
            self.assertEqual(digest(before), r['before_hash'], id)
            self.assertEqual(digest(after), r['after_hash'], id)
            self.assertEqual(sorted({k for k in before if before[k] != after[k]}), r['changed_fields'], id)
            for field in protected:
                self.assertEqual(before[field], after[field], id + ': ' + field)
            self.assertEqual([(o['number'], o['is_answer']) for o in before['option_notes']],
                             [(o['number'], o['is_answer']) for o in after['option_notes']], id)
            self.assertEqual(after['answers'], self.qs[id]['answers'])
            answer = {o['reason'] for o in after['option_notes'] if o['is_answer']}
            self.assertFalse(answer & {o['reason'] for o in after['option_notes'] if not o['is_answer']}, id)
            self.assertGreaterEqual(len({o['reason'] for o in after['option_notes']}),
                                    len({o['reason'] for o in before['option_notes']}), id)
            if after['review_status'] == 'partial':
                self.assertTrue(after['unchecked_points'], id)
            else:
                self.assertEqual(after['unchecked_points'], [], id)
            for change in r['changes']:
                self.assertIn(change['change'], kinds, id)
                if change['change'] == 'status':
                    self.assertEqual(change['before'], before['review_status'])
                    self.assertEqual(change['after'], after['review_status'])
                    continue
                self.assertEqual(value(before, change['field'], change['index']), change['before'], id)
                if change['change'] == 'spacing':
                    self.assertEqual(re.sub(r'\s', '', change['before']), re.sub(r'\s', '', change['after']), id)
                    self.assertNotIn('  ', change['after'], id)
            final = {}
            for change in r['changes']:
                if change['change'] != 'status':
                    final[(change['field'], change['index'])] = change['after']
            for (field, index), text in final.items():
                self.assertEqual(value(after, field, index), text, id)
        for id in set(current) - set(ids):
            self.assertEqual(current[id], previous[id], id)
        self.assertEqual(set(current), set(previous))


    def test_round12_option_rewrites_change_only_duplicated_wrong_option_reasons(self):
        group = (self.current_audit or {}).get('round12_option_rewrites')
        if not group:
            self.skipTest('No round-12 option rewrites')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        current = {n['question_id']: n for n in self.stage_after['round12_option_rewrites']['items']}
        previous = {n['question_id']: n for n in self.stage_after['round11_corrections']['items']} \
            if 'round11_corrections' in self.stage_after else self.latest_notes
        ids = [r['question_id'] for r in group['notes']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(group['count'], len(ids))
        for r in group['notes']:
            id, before, after = r['question_id'], r['before'], current[r['question_id']]
            self.assertEqual(before, previous[id], id)
            self.assertEqual(digest(before), r['before_hash'], id)
            self.assertEqual(digest(after), r['after_hash'], id)
            count = Counter(o['reason'].strip() for o in before['option_notes'])
            duplicated = sorted(o['number'] for o in before['option_notes'] if count[o['reason'].strip()] > 1)
            self.assertEqual(r['rewritten_options'], duplicated, id)
            self.assertEqual({k: v for k, v in before.items() if k != 'option_notes'},
                             {k: v for k, v in after.items() if k != 'option_notes'}, id)
            for old, new in zip(before['option_notes'], after['option_notes']):
                self.assertEqual({k: v for k, v in old.items() if k != 'reason'},
                                 {k: v for k, v in new.items() if k != 'reason'}, id)
                if old['number'] not in r['rewritten_options']:
                    self.assertEqual(old['reason'], new['reason'], id)
                else:
                    self.assertFalse(old['is_answer'], id)
                    self.assertTrue(new['reason'] and new['reason'] == new['reason'].strip())
                    self.assertNotIn('  ', new['reason'], id)
            self.assertEqual(len({o['reason'] for o in after['option_notes']}), 4, id)
            review = r['independent_review']
            self.assertNotEqual(review['reviewer'], r['author'], id)
            self.assertEqual(review['status'], 'pass', id)
            self.assertEqual(sorted(o['number'] for o in review['options']), r['rewritten_options'], id)
            self.assertTrue(all(o['status'] == 'pass' for o in review['options']), id)
        for id in set(current) - set(ids):
            self.assertEqual(current[id], previous[id], id)


    def test_every_current_explanation_has_four_distinct_option_reasons(self):
        for id, n in {n['question_id']: n for n in self.current_data['items']}.items():
            self.assertEqual(len({o['reason'].strip() for o in n['option_notes']}), 4, id)

    def test_explained_item_adjudications_keep_answers_and_match_partial_explanations(self):
        records = self.current_audit['answer_adjudication'].get('explained_item_records', [])
        if not records:
            self.skipTest('No adjudications for explained items')
        main = {r['question_id'] for r in self.current_audit['answer_adjudication']['records']}
        pending = {r['question_id'] for r in self.current_audit['review']}
        current = {n['question_id']: n for n in self.current_data['items']}
        ids = [r['question_id'] for r in records]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(set(ids) & main)
        for r in records:
            id = r['question_id']
            self.assertIn(id, current)
            self.assertNotIn(id, pending)
            self.assertIn(r['verdict'], {'official_conflict', 'multiple_candidates', 'ambiguous_wording', 'deferred'})
            self.assertIs(r['official_answer_changed'], False)
            self.assertEqual(r['official_answers'], self.qs[id]['answers'])
            self.assertEqual(current[id]['answers'], self.qs[id]['answers'])
            self.assertTrue(r['evidence'] and r['basis'])
            self.assertEqual(current[id]['review_status'], 'partial', id)
            self.assertTrue(current[id]['unchecked_points'], id)


    def test_adjudication_resolutions_keep_answers_and_previous_verdicts(self):
        log = self.current_audit['answer_adjudication']
        resolutions = log.get('resolutions', [])
        if not resolutions:
            self.skipTest('No adjudication resolutions')
        records = {r['question_id']: r for r in log['records'] + log.get('explained_item_records', [])}
        ids = [r['question_id'] for r in resolutions]
        self.assertEqual(len(ids), len(set(ids)))
        for r in resolutions:
            id = r['question_id']
            self.assertIn(id, records)
            self.assertEqual(r['previous_verdict'], records[id]['verdict'], id)
            self.assertNotEqual(r['verdict'], r['previous_verdict'], id)
            self.assertIs(r['official_answer_changed'], False)
            self.assertEqual(r['official_answers'], self.qs[id]['answers'])
            self.assertTrue(r['evidence'] and r['basis'])
            for read in r.get('official_answer_key_reads', []):
                self.assertIs(read['actually_read'], True)
                self.assertEqual(self.qs[read['question_id']]['answers'], [read['official_answer']])
                path = R / read['answer_pdf']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), read['answer_pdf_sha256'])


    def check_registrations(self, key):
        if key not in self.audit_after:
            self.skipTest(f'No {key}')
        def digest(x):
            return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode()).hexdigest()
        audit, after = self.audit_after[key], self.stage_after[key]
        group = audit[key]
        older = REGISTRATION_LEDGERS[REGISTRATION_LEDGERS.index(key) + 1:]
        before = next((self.stage_after[k] for k in older if k in self.stage_after), None) or \
            self.stage_after.get('round12_option_rewrites')
        previous_stage = {n['question_id'] for n in before['items']} if before else set(self.latest_notes)
        current = {n['question_id']: n for n in after['items']}
        pending = {r['question_id'] for r in audit['review']}
        ids = [r['question_id'] for r in group['items']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(group['registered_count'], len(ids))
        self.assertEqual(set(current), previous_stage | set(ids))
        self.assertFalse(set(ids) & previous_stage)
        for r in group['items']:
            id, note = r['question_id'], current[r['question_id']]
            self.assertNotIn(id, pending)
            self.assertEqual(r['previous_review']['question_id'], id)
            self.assertEqual(digest(note), r['explanation_sha256'], id)
            self.assertEqual(r['question_row_sha256'], digest(self.qs[id]), id)
            self.assertEqual(note['answers'], self.qs[id]['answers'])
            self.assertEqual(r['official_answers'], self.qs[id]['answers'])
            self.assertTrue(r['blocker_resolution'], id)
            review = r['independent_review']
            self.assertNotEqual(review['reviewer'], r['author'], id)
            self.assertEqual(review['status'], 'pass', id)
            self.assertEqual(sorted(x['number'] for x in review['four_option_logic']), [1, 2, 3, 4], id)
            self.assertTrue(all(x['status'] == 'pass' for x in review['four_option_logic']), id)
            self.assertTrue(r['source_reads'], id)
            for read in r['source_reads']:
                self.assertRegex(read['sha256'], r'^[0-9a-f]{64}$')
            for check in note['checks']:
                self.assertAlmostEqual(calc(check['expr']), check['expected'], places=6, msg=id)
            self.assertEqual(len({o['reason'] for o in note['option_notes']}), 4, id)
            if note['review_status'] == 'partial':
                self.assertTrue(note['unchecked_points'], id)
        for d in group['declined']:
            self.assertIn(d['question_id'], pending)
            self.assertTrue(d['reason'])
        for ref in group['new_source_refs']:
            self.assertIn(ref, after['sources'])

    def test_round13_registrations_resolve_blockers_with_independent_review(self):
        self.check_registrations('round13_registrations')

    def test_round14_registrations_resolve_blockers_with_independent_review(self):
        self.check_registrations('round14_registrations')

    def test_round15_registrations_resolve_blockers_with_independent_review(self):
        self.check_registrations('round15_registrations')

    def test_round16_registrations_resolve_blockers_with_independent_review(self):
        self.check_registrations('round16_registrations')

    def test_round17_registrations_resolve_blockers_with_independent_review(self):
        self.check_registrations('round17_registrations')

    def test_round20_all_inspections_changes_and_independent_proposal_bindings(self):
        from apply_round10_followups import digest, public_record
        from apply_round20_followups import protect_amendment, protect_concept
        after = self.stage_after.get('round20_followups')
        if after is None:
            self.skipTest('No round-20 follow-up applied')
        group = self.audit_after['round20_followups']['round20_followups']
        proposal_path = R / 'reports/round20-proposals.json'
        review_path = R / 'reports/round20-independent-reviews.json'
        self.assertEqual(hashlib.sha256(proposal_path.read_bytes()).hexdigest(), group['proposal_sha256'])
        self.assertEqual(hashlib.sha256(review_path.read_bytes()).hexdigest(), group['review_sha256'])
        for key, expected_hash in group['baseline_audit_key_hashes'].items():
            self.assertEqual(digest(self.audit_after['round20_followups'][key]),expected_hash,key)
        workers=group['worker_sessions']
        self.assertEqual(workers['distinct_worker_sessions'],group['actual_parallel_workers'])
        self.assertEqual(len(set(workers['workers_before_restart']+workers['workers_after_restart'])),group['actual_parallel_workers'])
        self.assertEqual(workers['max_concurrent_subagents'],6)
        proposal, qa = json.loads(proposal_path.read_text()), json.loads(review_path.read_text())
        current = {n['question_id']:n for n in after['items']}
        before = {n['question_id']:n for n in self.before_round20_data['items']}
        self.assertEqual({id:digest(n) for id,n in before.items()}, group['baseline_hashes'])
        self.assertEqual({ref:digest(meta) for ref,meta in self.before_round20_data['sources'].items()}, group['baseline_source_hashes'])
        expected_source = {r['question_id'] for r in group['original_review'] if r['category']=='source_unverified'}
        expected_partial = {id for id,n in before.items() if n['review_status']=='partial'}
        self.assertEqual(len(expected_source),18)
        self.assertEqual(len(expected_partial),115)
        for key, records, identifier, expected in (
                ('source',proposal['source_reviews'],'question_id',expected_source),
                ('partial',proposal['partial_reviews'],'question_id',expected_partial),
                ('concept',proposal['concept_amendments'],'note_id',None)):
            ids = [row[identifier] for row in records]
            self.assertEqual(len(ids),len(set(ids)))
            if expected is not None:self.assertEqual(set(ids),expected)
            approved = {r[identifier]:r for r in qa[key]}
            self.assertEqual(set(ids),set(approved))
            self.assertEqual(len(qa[key]),len(approved))
            for row in records:
                id = row[identifier]
                review = approved[id]
                self.assertEqual(review['status'],'pass',id)
                self.assertNotEqual(review['reviewer'],row['author'],id)
                self.assertEqual(review['proposal_sha256'],digest(row),id)
                self.assertTrue(row['source_reads'] and review['source_reads'],id)
                for read in row['source_reads']+review['source_reads']:
                    self.assertRegex(read['sha256'],r'^[0-9a-f]{64}$')
                    self.assertIs(read['actually_read'],True)
                    self.assertTrue(read['url'].startswith('https://') and read['version'] and read['read_locator'])
                if key=='source':
                    self.assertEqual(sorted(x['number'] for x in review['four_option_logic']),[1,2,3,4],id)
                    self.assertTrue(all(x['status']=='pass' for x in review['four_option_logic']),id)
                elif key=='partial':
                    self.assertEqual(row['before'],before[id],id)
                    self.assertEqual(row['after'],current[id],id)
                    self.assertEqual(row['changed_fields'],protect_amendment(row['before'],row['after'],id))
                    self.assertEqual(row['before_hash'],digest(row['before']),id)
                    self.assertEqual(row['after_hash'],digest(row['after']),id)
                    if row['after']['review_status']=='source_checked':
                        self.assertTrue(row['all_unchecked_resolved'] and review['all_unchecked_resolved'],id)
                else:
                    self.assertEqual(row['changed_fields'],protect_concept(row['before'],row['after'],id))
        amendments = {r['question_id']:r for r in group['amendments']}
        for id,n in before.items():
            self.assertEqual(current[id],amendments[id]['after'] if id in amendments else n,id)
        for ref,meta in self.before_round20_data['sources'].items():self.assertEqual(after['sources'][ref],meta,ref)
        registered = {r['question_id'] for r in group['registrations']}
        self.assertEqual(set(current),set(before)|registered)
        self.assertEqual(group['registered_count'],len(registered))
        self.assertEqual(group['amended_count'],len(amendments))
        original_pending={r['question_id']:r for r in group['original_review']}
        for row in group['registrations']:
            id=row['question_id']
            self.assertEqual(row['previous_review'],original_pending[id],id)
            self.assertEqual(row['official_answers'],self.qs[id]['answers'],id)
            self.assertEqual(row['explanation_sha256'],digest(current[id]),id)
            self.assertEqual(row['question_row_sha256'],digest(self.qs[id]),id)
        self.assertEqual(self.audit_after['round20_followups']['review'],
                         [r for r in group['original_review'] if r['question_id'] not in registered])
        concepts=copy.deepcopy(self.before_round26_concepts)
        self.assertEqual({n['id']:digest(n) for n in self.before_round20_concepts['notes']},group['baseline_concept_hashes'])
        self.assertEqual({ref:digest(meta) for ref,meta in self.before_round20_concepts['sources'].items()},group['baseline_concept_source_hashes'])
        for ref,meta in self.before_round20_concepts['sources'].items():
            self.assertEqual(concepts['sources'][ref],meta,ref)
        cmap={n['id']:n for n in concepts['notes']}
        changed={r['note_id']:r for r in group['concept_amendments']}
        for n in self.before_round20_concepts['notes']:
            id=n['id'];self.assertEqual(cmap[id],changed[id]['after'] if id in changed else n,id)
        self.assertEqual(len(concepts['notes']),len(self.before_round20_concepts['notes']))

    def test_round20_guards_reject_answer_calculation_and_stale_review_changes(self):
        from apply_round10_followups import digest
        from apply_round20_followups import protect_amendment, protect_concept, verified_review
        n=copy.deepcopy(self.current_data['items'][0])
        for field,value in [('answers',[4]),('checks',[]),('question_id','wrong-original')]:
            changed=copy.deepcopy(n)
            changed[field]=value if value!=n[field] else ['changed']
            with self.assertRaises(ValueError):protect_amendment(n,changed,n['question_id'])
        row={'author':'author','source_reads':[]}
        with self.assertRaisesRegex(ValueError, 'stale'):
            verified_review(row,{'status':'pass','reviewer':'reviewer','proposal_sha256':'0'*64},'stale')
        with self.assertRaisesRegex(ValueError, 'non-independent'):
            verified_review(row,{'status':'pass','reviewer':'','proposal_sha256':digest(row)},'unnamed')
        concept=copy.deepcopy(self.before_round20_concepts['notes'][0])
        changed=copy.deepcopy(concept);changed['key_points'][0]='replace protected prior tip'
        with self.assertRaisesRegex(ValueError,'previous key_points'):
            protect_concept(concept,changed,concept['id'])
        changed=copy.deepcopy(concept);changed['examples'].append({'checks':[{'expr':'9//2','expected':4}]})
        with self.assertRaises(ValueError):protect_concept(concept,changed,concept['id'])


    def test_round27_source_checks_preserve_all_older_content_and_bind_actual_evidence(self):
        from apply_round27_sources import GROUP, PROPOSAL, VERIFIER, digest, validate_row
        after = self.stage_after.get(GROUP)
        if after is None:
            self.skipTest('No round-27 source checks applied')
        audit = self.audit_after[GROUP]
        group = audit[GROUP]
        proposal = json.loads((R/PROPOSAL).read_text())
        self.assertEqual(digest(proposal),group['proposal_sha256'])
        self.assertEqual(digest(self.before_round27_data),group['baseline_data_hash'])
        self.assertEqual(digest(self.before_round27_audit),group['baseline_audit_hash'])
        self.assertEqual(proposal['baseline_data_hash'],group['baseline_data_hash'])
        self.assertEqual(proposal['baseline_audit_hash'],group['baseline_audit_hash'])
        self.assertEqual({k:v for k,v in audit.items() if k!=GROUP},self.before_round27_audit)
        self.assertEqual(group['actual_new_subagents'],0)
        self.assertEqual(group['verifier'],VERIFIER)
        self.assertEqual(group['amendments'],proposal['amendments'])
        self.assertEqual(group['amended_count'],len(proposal['amendments']))
        expected_ids={'2023-01-102','2026-07-102','2026-06-085',
                      '2025-03-101','2024-06-101','2023-03-102'}
        rows={r['question_id']:r for r in proposal['amendments']}
        self.assertEqual(set(rows),expected_ids)
        self.assertEqual(len(rows),len(proposal['amendments']))
        before={n['question_id']:n for n in self.before_round27_data['items']}
        current={n['question_id']:n for n in after['items']}
        self.assertEqual(set(current),set(before))
        self.assertEqual(len(current),4281)
        for qid,n in before.items():
            self.assertEqual(current[qid],rows[qid]['after'] if qid in rows else n,qid)
        for qid,row in rows.items():
            self.assertEqual(row['before'],before[qid])
            validate_row(row,proposal['new_sources'])
            original=next(r for r in self.audit_after['round26_followups']['round26_followups']['partial_inspections']
                          if r['question_id']==qid)
            self.assertEqual(row['previous_author'],original['author'])
        self.assertEqual(Counter(n['review_status'] for n in before.values()),group['before_counts'])
        self.assertEqual(Counter(n['review_status'] for n in current.values()),group['after_counts'])
        self.assertEqual(group['after_counts'],{'source_checked':4166,'partial':115})
        self.assertEqual(group['remaining_unregistered'],len(audit['review']))
        self.assertEqual(len(audit['review']),40)
        old_sources=self.before_round27_data['sources']
        self.assertEqual({k:digest(v) for k,v in old_sources.items()},group['baseline_source_hashes'])
        self.assertEqual(set(after['sources'])-set(old_sources),set(group['new_source_refs']))
        self.assertEqual({k:v for k,v in after['sources'].items() if k not in old_sources},proposal['new_sources'])
        for ref,source in old_sources.items():self.assertEqual(after['sources'][ref],source,ref)
        self.assertEqual({k:v for k,v in self.before_round27_data.items() if k not in {'items','sources'}},
                         {k:v for k,v in after.items() if k not in {'items','sources'}})
        for file,expected in group['protected_file_sha256'].items():
            self.assertEqual(hashlib.sha256((R/file).read_bytes()).hexdigest(),expected,file)
        receipts={r['sha256']:r for r in proposal['actual_file_reads']}
        for read in proposal['actual_file_reads']:
            self.assertIs(read['actually_read'],True)
            self.assertRegex(read['sha256'],r'^[0-9a-f]{64}$')
            self.assertTrue(read['version'] and read['read_locator'])
            self.assertNotIn('private_path',read)
            if read.get('repo_path'):
                self.assertEqual(hashlib.sha256((R/read['repo_path']).read_bytes()).hexdigest(),read['sha256'])
        for row in proposal['amendments']:
            for read in row['source_reads']:
                self.assertIn(read['sha256'],receipts)
                self.assertEqual(read['read_locator'],receipts[read['sha256']]['read_locator'])

    def test_round27_rejects_stale_answers_missing_options_and_unproven_source_upgrades(self):
        from apply_round27_sources import PROPOSAL, digest, validate_row
        proposal=json.loads((R/PROPOSAL).read_text())
        original=proposal['amendments'][0]
        def rejected(mutate):
            row=copy.deepcopy(original)
            mutate(row)
            # Rebind hashes so protected-field checks cannot rely on a stale hash.
            row['after_hash']=digest(row['after'])
            with self.assertRaises(ValueError):validate_row(row,proposal['new_sources'])
        rejected(lambda r:r['after'].update(answers=[1]))
        rejected(lambda r:r['after'].update(checks=[{'expr':'2+2','expected':4}]))
        rejected(lambda r:r['after']['option_notes'][0].update(is_answer=True))
        rejected(lambda r:r.update(resolved_unchecked_points=[]))
        rejected(lambda r:r['resolved_unchecked_points'][0].update(locator='unread location'))
        rejected(lambda r:r['after'].update(unchecked_points=['still unresolved']))
        rejected(lambda r:r.update(source_reads=[]))
        rejected(lambda r:r['source_reads'][0].update(sha256='0'*64))
        rejected(lambda r:r.update(four_option_findings=r['four_option_findings'][:3]))
        rejected(lambda r:r.update(review_method='independent agent review'))

    def test_round26_all_inspections_and_append_only_concept_evidence(self):
        from apply_round10_followups import digest, public_record
        from apply_round20_followups import four_options_pass
        from apply_round26_followups import validate_concept, validate_partial, validate_coverage
        after = self.stage_after.get('round26_followups')
        if after is None:
            self.skipTest('No round-26 follow-up applied')
        audit = self.audit_after['round26_followups']
        group = audit['round26_followups']
        proposal = json.loads((R/'reports/round26-proposals.json').read_text())
        reviews = json.loads((R/'reports/round26-independent-reviews.json').read_text())
        self.assertEqual(digest(proposal),group['public_proposal_sha256'])
        self.assertEqual(digest(reviews),group['public_review_sha256'])
        self.assertEqual(proposal,public_record(proposal))
        self.assertEqual(reviews,public_record(reviews))
        self.assertEqual(proposal['baseline_audit_sha256'],
                         group['baseline_file_sha256']['reports/explanation-expansion.json'])
        self.assertEqual(proposal['baseline_commit'],group['baseline_commit'])
        self.assertEqual(proposal['checked_on'],group['checked_on'])
        self.assertEqual(proposal['worker_sessions'],group['worker_sessions'])
        self.assertEqual(proposal['actual_parallel_workers'],group['actual_parallel_workers'])
        for field in ('proposal_sha256','review_sha256'):
            self.assertRegex(group[field],r'^[0-9a-f]{64}$')
        for filename,expected in group['protected_file_sha256'].items():
            self.assertEqual(hashlib.sha256((R/filename).read_bytes()).hexdigest(),expected,filename)
        self.assertEqual(set(audit)-{'round26_followups'},set(self.before_round26_audit))
        for key,value in self.before_round26_audit.items():
            self.assertEqual(audit[key],value,key)
            if key != 'review':self.assertEqual(digest(value),group['baseline_audit_key_hashes'][key])
        for key,value in [('explanations',self.before_round26_data),('concepts',self.before_round26_concepts),
                          ('audit',self.before_round26_audit),('concept_audit',self.before_round26_concept_audit)]:
            self.assertEqual(digest(value),group['baseline_content_hashes'][key],key)
        self.assertEqual(audit['review'],group['original_review'])
        self.assertEqual(len(audit['review']),40)
        self.assertEqual(group['remaining_review_count'],40)
        before = {n['question_id']:n for n in self.before_round26_data['items']}
        current = {n['question_id']:n for n in after['items']}
        cbefore = {n['id']:n for n in self.before_round26_concepts['notes']}
        concepts=copy.deepcopy(self.concepts_before_wording)
        cafter={n['id']:n for n in concepts['notes']}
        self.assertEqual(len(current),4281)
        self.assertEqual(group['baseline_count'],4281)
        self.assertEqual(set(current),set(before))
        self.assertEqual(set(cafter),set(cbefore))
        self.assertEqual({k:digest(v) for k,v in before.items()},group['baseline_hashes'])
        self.assertEqual({k:digest(v) for k,v in cbefore.items()},group['baseline_concept_hashes'])
        pmap={r['question_id']:r for r in proposal['partial_reviews']}
        cmap={r['note_id']:r for r in proposal['concept_amendments']}
        validate_coverage(pmap,cmap,{k for k,v in before.items() if v['review_status']=='partial'},
                          {k for k,v in cbefore.items() if v['review_status']=='partial'})
        self.assertEqual(group['partial_target_count'],122)
        self.assertEqual(group['concept_target_count'],8)
        for kind,rows,ledger,identifier in (
                ('partial',proposal['partial_reviews'],group['partial_inspections'],'question_id'),
                ('concept',proposal['concept_amendments'],group['concept_amendments'],'note_id')):
            approvals={r[identifier]:r for r in reviews[kind]}
            records={r[identifier]:r for r in ledger}
            ids=[r[identifier] for r in rows]
            self.assertEqual(len(ids),len(set(ids)))
            self.assertEqual(len(approvals),len(reviews[kind]))
            self.assertEqual(len(records),len(ledger))
            self.assertEqual(set(ids),set(approvals))
            self.assertEqual(set(ids),set(records))
            for row in rows:
                id=row[identifier];qa=approvals[id];record=records[id]
                self.assertEqual(qa['status'],'pass',id)
                self.assertTrue(row['author'] and qa['reviewer'],id)
                self.assertNotEqual(row['author'],qa['reviewer'],id)
                self.assertEqual(qa['proposal_sha256'],record['proposal_record_sha256'],id)
                self.assertEqual(digest(row),record['public_proposal_record_sha256'],id)
                self.assertEqual(record['independent_review'],qa,id)
                metadata={'independent_review','proposal_record_sha256','public_proposal_record_sha256'}
                if kind=='concept':metadata.update({'output_hash','stage'})
                self.assertEqual({k:v for k,v in record.items() if k not in metadata},row,id)
                self.assertTrue(row['source_reads'] and qa['source_reads'],id)
                for read in row['source_reads']+qa['source_reads']:
                    self.assertRegex(read['sha256'],r'^[0-9a-f]{64}$')
                    self.assertIs(read['actually_read'],True)
                    self.assertTrue(read['url'].startswith('https://') and read['version'] and read['read_locator'])
                    self.assertNotIn('private_path',read)
                self.assertEqual(digest(row['before']),row['before_hash'],id)
                self.assertEqual(digest(row['after']),row['after_hash'],id)
                if kind=='partial':
                    four_options_pass(qa,id)
                    self.assertEqual(row['changed_fields'],validate_partial(row,qa,id))
                    self.assertEqual(row['before'],before[id],id)
                    self.assertEqual(row['after'],current[id],id)
                else:
                    self.assertTrue(qa['addition_findings'] and qa['arithmetic_findings'],id)
                    self.assertEqual(row['changed_fields'],validate_concept(row,qa,id))
                    self.assertEqual(row['before'],cbefore[id],id)
                    self.assertEqual(row['after'],cafter[id],id)
                    self.assertEqual(record['output_hash'],record['proposal_record_sha256'])
        amended=[r for r in group['partial_inspections'] if r['changed_fields']]
        self.assertEqual(group['amendments'],amended)
        self.assertEqual(group['amended_count'],len(amended))
        self.assertEqual(group['concept_amended_count'],8)
        amendments={r['question_id']:r for r in amended}
        for id,note in before.items():
            self.assertEqual(current[id],amendments[id]['after'] if id in amendments else note,id)
        for id,note in cbefore.items():
            self.assertEqual(cafter[id],cmap[id]['after'] if id in cmap else note,id)
        for previous,result,key,added in (
                (self.before_round26_data,after,'baseline_source_hashes','new_source_refs'),
                (self.before_round26_concepts,concepts,'baseline_concept_source_hashes','new_concept_source_refs')):
            self.assertEqual({k:digest(v) for k,v in previous['sources'].items()},group[key])
            self.assertEqual(set(result['sources'])-set(previous['sources']),set(group[added]))
            for ref,meta in previous['sources'].items():self.assertEqual(result['sources'][ref],meta,ref)
            self.assertEqual({k:v for k,v in previous.items() if k not in {'items','notes','sources'}},
                             {k:v for k,v in result.items() if k not in {'items','notes','sources'}})
        concept_audit=json.loads((R/'reports/concept-expansion.json').read_text())
        reconstructed=copy.deepcopy(self.before_round26_concept_audit)
        reconstructed['followup_note_amendments']+=group['concept_amendments']
        self.assertEqual(concept_audit,reconstructed)

    def test_round26_guards_reject_missing_coverage_protected_edits_and_unproven_upgrades(self):
        from apply_round10_followups import digest
        from apply_round20_followups import four_options_pass, unique_rows, verified_review
        from apply_round26_followups import validate_concept, validate_partial, validate_coverage
        with self.assertRaises(ValueError):validate_coverage({'a':{}},{},{'a','b'},set())
        with self.assertRaises(ValueError):unique_rows([{'id':'a'},{'id':'a'}],'id')
        for numbers in ([1,2,3],[1,1,3,4]):
            with self.assertRaises(ValueError):
                four_options_pass({'four_option_logic':[dict(number=n,status='pass',note='specific') for n in numbers]},'bad')
        with self.assertRaises(ValueError):
            four_options_pass({'four_option_logic':[dict(number=n,status='pass',note='') for n in range(1,5)]},'bad')
        row={'author':'author','source_reads':[]}
        for qa in ({'reviewer':'author','status':'pass','proposal_sha256':digest(row)},
                   {'reviewer':'independent','status':'pass','proposal_sha256':'0'*64}):
            with self.assertRaises(ValueError):verified_review(row,qa,'bad')
        note=next(n for n in self.before_round26_data['items'] if n['review_status']=='partial')
        row=dict(before=copy.deepcopy(note),after=copy.deepcopy(note),decision='keep',changed_fields=[],reason='retain limitation')
        for field,value in [('answers',[0]),('checks',[{'expr':'1+1','expected':2}]),
                            ('question_id','wrong-original')]:
            bad=copy.deepcopy(row);bad['after'][field]=value
            with self.assertRaises(ValueError):validate_partial(bad,{},note['question_id'])
        bad=copy.deepcopy(row);bad['decision']='upgrade';bad['after']['review_status']='source_checked'
        bad['after']['unchecked_points']=[];bad['changed_fields']=sorted(k for k in note if note[k]!=bad['after'][k])
        with self.assertRaises(ValueError):validate_partial(bad,{},note['question_id'])
        concept=next(n for n in self.before_round26_concepts['notes'] if n['review_status']=='partial')
        crow=dict(before=copy.deepcopy(concept),after=copy.deepcopy(concept),source_reads=[])
        bad=copy.deepcopy(crow);bad['after']['key_points'][0]='overwrite protected content'
        with self.assertRaises(ValueError):validate_concept(bad,{'source_reads':[]},concept['id'])
        bad=copy.deepcopy(crow);bad['after']['unchecked_points']=[]
        with self.assertRaises(ValueError):validate_concept(bad,{'source_reads':[]},concept['id'])
        bad=copy.deepcopy(crow);bad['after']['examples'].append({'checks':[{'expr':'9//2','expected':4}]})
        with self.assertRaises(ValueError):validate_concept(bad,{'source_reads':[]},concept['id'])


    def test_round26_concept_resolution_requires_exact_citation_and_both_approvals(self):
        from apply_round26_followups import validate_concept
        note=next(n for n in self.before_round26_concepts['notes']
                  if n['review_status']=='partial' and not any(f.get('unchecked') for f in n['formulas']))
        ref=note['sources'][0]['ref']
        row=dict(before=copy.deepcopy(note),after=copy.deepcopy(note),source_reads=[{'ref':ref}],
                 all_unchecked_resolved=True,
                 resolved_unchecked_points=[dict(before_text=text,evidence_ref=ref,locator='direct passage',
                                                  reason='passage resolves this specific warning')
                                            for text in note['unchecked_points']])
        row['after']['unchecked_points']=[]
        row['after']['review_status']='source_checked'
        qa=dict(source_reads=[{'ref':ref}],resolved_unchecked_points_checked=True,all_unchecked_resolved=True)
        self.assertEqual(validate_concept(row,qa,note['id']),['review_status','unchecked_points'])
        # Resolving one warning while another remains must preserve partial status.
        partial=copy.deepcopy(row);partial['after']['review_status']='partial'
        partial['after']['unchecked_points']=['A separate limitation remains.']
        partial['all_unchecked_resolved']=False
        self.assertEqual(validate_concept(partial,qa,note['id']),['unchecked_points'])
        for field in ('resolved_unchecked_points_checked','all_unchecked_resolved'):
            bad=copy.deepcopy(qa);bad[field]=False
            with self.assertRaises(ValueError):validate_concept(row,bad,note['id'])
        for side in ('author','reviewer','citation','evidence'):
            badrow,badqa=copy.deepcopy(row),copy.deepcopy(qa)
            if side=='author':badrow['source_reads']=[]
            elif side=='reviewer':badqa['source_reads']=[]
            elif side=='citation':badrow['after']['sources']=[]
            else:badrow['resolved_unchecked_points'][0]['evidence_ref']='unread-reference'
            with self.assertRaises(ValueError):validate_concept(badrow,badqa,note['id'])
        bad=copy.deepcopy(row);bad['resolved_unchecked_points'].append(copy.deepcopy(bad['resolved_unchecked_points'][0]))
        with self.assertRaises(ValueError):validate_concept(bad,qa,note['id'])
        bad=copy.deepcopy(row);bad['resolved_unchecked_points'][0]['before_text']='invented warning'
        with self.assertRaises(ValueError):validate_concept(bad,qa,note['id'])
        bad=copy.deepcopy(row);bad['all_unchecked_resolved']=False
        with self.assertRaises(ValueError):validate_concept(bad,qa,note['id'])


    def test_round26_text_corrections_require_exact_targets_sources_and_approval(self):
        from apply_round26_followups import validate_concept
        note=next(n for n in self.before_round26_concepts['notes'] if n['review_status']=='partial')
        ref=note['sources'][0]['ref']
        row=dict(before=copy.deepcopy(note),after=copy.deepcopy(note),source_reads=[{'ref':ref}],
                 text_amendments=[dict(field='pitfalls',index=0,before=note['pitfalls'][0],
                                      after='직접 확인한 근거의 적용 조건을 구분합니다.',
                                      evidence_ref=ref,locator='specific passage',reason='correct an obsolete limitation')])
        row['after']['pitfalls'][0]=row['text_amendments'][0]['after']
        qa=dict(source_reads=[{'ref':ref}],text_amendments_checked=True)
        self.assertEqual(validate_concept(row,qa,note['id']),['pitfalls'])
        # An audited correction can coexist with an ordinary append-only tip.
        extra=copy.deepcopy(row);extra['after']['pitfalls'].append('새 예제에서는 주어진 조건을 먼저 확인합니다.')
        self.assertEqual(validate_concept(extra,qa,note['id']),['pitfalls'])
        for field,value in [('field','examples'),('field','unknown'),('index',-1),
                            ('index',len(note['pitfalls'])),('index',True),
                            ('before','wrong old text'),('after','  '),
                            ('after',note['pitfalls'][0]),('evidence_ref','unread-reference'),
                            ('locator',''),('reason','')]:
            bad=copy.deepcopy(row);bad['text_amendments'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                validate_concept(bad,qa,note['id'])
        bad=copy.deepcopy(row);bad['text_amendments']*=2
        with self.assertRaises(ValueError):validate_concept(bad,qa,note['id'])
        bad=copy.deepcopy(row);bad['text_amendments']=[]
        with self.assertRaises(ValueError):validate_concept(bad,qa,note['id'])
        bad=copy.deepcopy(row);bad['after']['key_points'][0]='unlisted change'
        with self.assertRaises(ValueError):validate_concept(bad,qa,note['id'])
        for side in ('author','reviewer','approval'):
            bad,badqa=copy.deepcopy(row),copy.deepcopy(qa)
            if side=='author':bad['source_reads']=[]
            elif side=='reviewer':badqa['source_reads']=[]
            else:badqa['text_amendments_checked']=False
            with self.assertRaises(ValueError):validate_concept(bad,badqa,note['id'])


    def test_round24_append_only_registrations_preserve_originals_and_earlier_audits(self):
        from apply_round10_followups import digest,public_record
        from apply_round20_followups import authored_note
        stage=self.stage_after.get('round24_followups')
        if stage is None:self.skipTest('No round24 followup yet')
        after=self.audit_after['round24_followups'];group=after['round24_followups'];baseline=group['baseline']
        proposal_path=R/'reports/round24-proposals.json';qa_path=R/'reports/round24-independent-reviews.json'
        self.assertEqual(hashlib.sha256(proposal_path.read_bytes()).hexdigest(),group['proposal_sha256'])
        self.assertEqual(hashlib.sha256(qa_path.read_bytes()).hexdigest(),group['review_sha256'])
        proposal=json.loads(proposal_path.read_text());qa=json.loads(qa_path.read_text())
        self.assertEqual(proposal['baseline'],baseline)
        rows={r['question_id']:r for r in proposal['inspections']};reviews={r['question_id']:r for r in qa}
        self.assertEqual(len(rows),len(proposal['inspections']));self.assertEqual(len(reviews),len(qa))
        pending={r['question_id']:r for r in group['original_review']}
        self.assertEqual(set(rows),set(pending));self.assertEqual(set(reviews),set(rows))
        previous={r['question_id']:r for r in after['round23_followups']['inspections']}
        self.assertEqual(group['previous_inspection_hashes'],{id:digest(previous[id]) for id in rows})
        self.assertEqual(proposal['previous_inspection_hashes'],group['previous_inspection_hashes'])
        recorded={r['question_id']:r for r in group['inspections']}
        self.assertEqual(len(recorded),len(group['inspections']));self.assertEqual(set(recorded),set(rows))
        for id,row in rows.items():
            q=reviews[id]
            self.assertEqual(row['previous_review'],pending[id]);self.assertEqual(row['question_row_sha256'],digest(self.qs[id]))
            self.assertEqual(q['status'],'pass');self.assertNotEqual(q['reviewer'],row['author'])
            self.assertEqual(q['proposal_sha256'],digest(row))
            self.assertEqual(sorted(o['number'] for o in q['four_option_logic']),[1,2,3,4])
            self.assertTrue(all(o['status']=='pass' and o['note'] for o in q['four_option_logic']))
            self.assertEqual(recorded[id],public_record(dict(row,proposal_record_sha256=digest(row),independent_review=q)))
            if row['decision']=='register':
                self.assertTrue(row['source_reads']);self.assertTrue(q['source_reads'])
                self.assertEqual(q['approved_decision'], 'register')
                self.assertIs(q['registration_approved'], True)
                self.assertIs(row['originals']['subject_instructions_checked'],True)
                self.assertIs(q['originals']['subject_instructions_checked'],True)
            else:self.assertEqual(row['decision'],'decline')
            for read in row.get('source_reads',[])+q.get('source_reads',[]):
                self.assertRegex(read['sha256'],r'^[0-9a-f]{64}$');self.assertIs(read['actually_read'],True)
                self.assertTrue(read['url'].startswith('https://') and read['version'] and read['read_locator'])
        current={n['question_id']:n for n in stage['items']}
        self.assertEqual({id:digest(current[id]) for id in baseline['explanation_hashes']},baseline['explanation_hashes'])
        registered={r['question_id']:r for r in group['registrations']}
        self.assertEqual(set(registered),{id for id,row in rows.items() if row['decision']=='register'})
        self.assertEqual(set(current),set(baseline['explanation_hashes'])|set(registered))
        self.assertEqual(len(registered),len(group['registrations']));self.assertEqual(len(registered),group['registered_count'])
        for id,registration in registered.items():
            note=authored_note(self.qs[id],rows[id]['draft_note'],group['checked_on'])
            self.assertEqual(current[id],note);self.assertEqual(registration['note'],note)
            self.assertEqual(registration['explanation_sha256'],digest(note))
            self.assertEqual(registration['proposal_record_sha256'],digest(rows[id]))
            self.assertEqual(registration['official_answers'],self.qs[id]['answers'])
            self.assertFalse(registration['official_answer_changed'])
            self.assertEqual(len({o['reason'] for o in note['option_notes']}),4)
        self.assertEqual({ref:digest(stage['sources'][ref]) for ref in baseline['source_hashes']},baseline['source_hashes'])
        self.assertEqual(set(stage['sources']),set(baseline['source_hashes'])|set(group['new_source_refs']))
        for ref in group['new_source_refs']:self.assertEqual(stage['sources'][ref],proposal['sources'][ref])
        self.assertEqual(after['review'],[r for r in group['original_review'] if r['question_id'] not in registered])
        self.assertEqual(group['remaining_review_count'],len(after['review']))
        for key,sha in baseline['audit_key_hashes'].items():
            if key!='review':self.assertEqual(digest(after[key]),sha,key)
        for name,sha in baseline['immutable_files'].items():self.assert_protected_file(name,sha)
        self.assertEqual(hashlib.sha256((json.dumps(self.before_round26_concepts,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),baseline['concepts_file_sha256'])
        self.assertEqual(hashlib.sha256((json.dumps(self.before_round26_concept_audit,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),baseline['concept_audit_file_sha256'])

    def test_round23_append_only_registrations_preserve_originals_and_earlier_audits(self):
        from apply_round10_followups import digest,public_record
        from apply_round20_followups import authored_note
        stage=self.stage_after.get('round23_followups')
        if stage is None:self.skipTest('No round23 followup yet')
        after=self.audit_after['round23_followups'];group=after['round23_followups'];baseline=group['baseline']
        proposal_path=R/'reports/round23-proposals.json';qa_path=R/'reports/round23-independent-reviews.json'
        self.assertEqual(hashlib.sha256(proposal_path.read_bytes()).hexdigest(),group['proposal_sha256'])
        self.assertEqual(hashlib.sha256(qa_path.read_bytes()).hexdigest(),group['review_sha256'])
        proposal=json.loads(proposal_path.read_text());qa=json.loads(qa_path.read_text())
        self.assertEqual(proposal['baseline'],baseline)
        rows={r['question_id']:r for r in proposal['inspections']};reviews={r['question_id']:r for r in qa}
        self.assertEqual(len(rows),len(proposal['inspections']));self.assertEqual(len(reviews),len(qa))
        pending={r['question_id']:r for r in group['original_review']}
        self.assertEqual(set(rows),set(pending));self.assertEqual(set(reviews),set(rows))
        previous={r['question_id']:r for r in after['round22_followups']['inspections']}
        self.assertEqual(group['previous_inspection_hashes'],{id:digest(previous[id]) for id in rows})
        self.assertEqual(proposal['previous_inspection_hashes'],group['previous_inspection_hashes'])
        recorded={r['question_id']:r for r in group['inspections']}
        self.assertEqual(len(recorded),len(group['inspections']));self.assertEqual(set(recorded),set(rows))
        for id,row in rows.items():
            q=reviews[id]
            self.assertEqual(row['previous_review'],pending[id]);self.assertEqual(row['question_row_sha256'],digest(self.qs[id]))
            self.assertEqual(q['status'],'pass');self.assertNotEqual(q['reviewer'],row['author'])
            self.assertEqual(q['proposal_sha256'],digest(row))
            self.assertEqual(sorted(o['number'] for o in q['four_option_logic']),[1,2,3,4])
            self.assertTrue(all(o['status']=='pass' and o['note'] for o in q['four_option_logic']))
            self.assertEqual(recorded[id],public_record(dict(row,proposal_record_sha256=digest(row),independent_review=q)))
            if row['decision']=='register':
                self.assertTrue(row['source_reads']);self.assertTrue(q['source_reads'])
                self.assertEqual(q['approved_decision'], 'register')
                self.assertIs(q['registration_approved'], True)
                self.assertIs(row['originals']['subject_instructions_checked'],True)
                self.assertIs(q['originals']['subject_instructions_checked'],True)
            else:self.assertEqual(row['decision'],'decline')
            for read in row.get('source_reads',[])+q.get('source_reads',[]):
                self.assertRegex(read['sha256'],r'^[0-9a-f]{64}$');self.assertIs(read['actually_read'],True)
                self.assertTrue(read['url'].startswith('https://') and read['version'] and read['read_locator'])
        current={n['question_id']:n for n in stage['items']}
        self.assertEqual({id:digest(current[id]) for id in baseline['explanation_hashes']},baseline['explanation_hashes'])
        registered={r['question_id']:r for r in group['registrations']}
        self.assertEqual(set(registered),{id for id,row in rows.items() if row['decision']=='register'})
        self.assertEqual(set(current),set(baseline['explanation_hashes'])|set(registered))
        self.assertEqual(len(registered),len(group['registrations']));self.assertEqual(len(registered),group['registered_count'])
        for id,registration in registered.items():
            note=authored_note(self.qs[id],rows[id]['draft_note'],group['checked_on'])
            self.assertEqual(current[id],note);self.assertEqual(registration['note'],note)
            self.assertEqual(registration['explanation_sha256'],digest(note))
            self.assertEqual(registration['proposal_record_sha256'],digest(rows[id]))
            self.assertEqual(registration['official_answers'],self.qs[id]['answers'])
            self.assertFalse(registration['official_answer_changed'])
            self.assertEqual(len({o['reason'] for o in note['option_notes']}),4)
        self.assertEqual({ref:digest(stage['sources'][ref]) for ref in baseline['source_hashes']},baseline['source_hashes'])
        self.assertEqual(set(stage['sources']),set(baseline['source_hashes'])|set(group['new_source_refs']))
        for ref in group['new_source_refs']:self.assertEqual(stage['sources'][ref],proposal['sources'][ref])
        self.assertEqual(after['review'],[r for r in group['original_review'] if r['question_id'] not in registered])
        self.assertEqual(group['remaining_review_count'],len(after['review']))
        for key,sha in baseline['audit_key_hashes'].items():
            if key!='review':self.assertEqual(digest(after[key]),sha,key)
        for name,sha in baseline['immutable_files'].items():self.assert_protected_file(name,sha)
        self.assertEqual(hashlib.sha256((json.dumps(self.before_round26_concepts,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),baseline['concepts_file_sha256'])
        self.assertEqual(hashlib.sha256((json.dumps(self.before_round26_concept_audit,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),baseline['concept_audit_file_sha256'])

    def test_round22_append_only_registrations_preserve_originals_and_earlier_audits(self):
        from apply_round10_followups import digest,public_record
        from apply_round20_followups import authored_note
        stage=self.stage_after.get('round22_followups')
        if stage is None:self.skipTest('No round22 followup yet')
        after=self.audit_after['round22_followups'];group=after['round22_followups'];baseline=group['baseline']
        proposal_path=R/'reports/round22-proposals.json';qa_path=R/'reports/round22-independent-reviews.json'
        self.assertEqual(hashlib.sha256(proposal_path.read_bytes()).hexdigest(),group['proposal_sha256'])
        self.assertEqual(hashlib.sha256(qa_path.read_bytes()).hexdigest(),group['review_sha256'])
        proposal=json.loads(proposal_path.read_text());qa=json.loads(qa_path.read_text())
        self.assertEqual(proposal['baseline'],baseline)
        rows={r['question_id']:r for r in proposal['inspections']};reviews={r['question_id']:r for r in qa}
        self.assertEqual(len(rows),len(proposal['inspections']));self.assertEqual(len(reviews),len(qa))
        pending={r['question_id']:r for r in group['original_review']}
        self.assertEqual(set(rows),set(pending));self.assertEqual(set(reviews),set(rows))
        previous={r['question_id']:r for r in after['round21_inspections']['inspections']}
        self.assertEqual(group['previous_inspection_hashes'],{id:digest(previous[id]) for id in rows})
        self.assertEqual(proposal['previous_inspection_hashes'],group['previous_inspection_hashes'])
        recorded={r['question_id']:r for r in group['inspections']}
        self.assertEqual(len(recorded),len(group['inspections']));self.assertEqual(set(recorded),set(rows))
        for id,row in rows.items():
            q=reviews[id]
            self.assertEqual(row['previous_review'],pending[id]);self.assertEqual(row['question_row_sha256'],digest(self.qs[id]))
            self.assertEqual(q['status'],'pass');self.assertNotEqual(q['reviewer'],row['author'])
            self.assertEqual(q['proposal_sha256'],digest(row))
            self.assertEqual(sorted(o['number'] for o in q['four_option_logic']),[1,2,3,4])
            self.assertTrue(all(o['status']=='pass' and o['note'] for o in q['four_option_logic']))
            self.assertEqual(recorded[id],public_record(dict(row,proposal_record_sha256=digest(row),independent_review=q)))
            if row['decision']=='register':
                self.assertTrue(row['source_reads']);self.assertTrue(q['source_reads'])
                self.assertIs(row['originals']['subject_instructions_checked'],True)
                self.assertIs(q['originals']['subject_instructions_checked'],True)
            else:self.assertEqual(row['decision'],'decline')
            for read in row.get('source_reads',[])+q.get('source_reads',[]):
                self.assertRegex(read['sha256'],r'^[0-9a-f]{64}$');self.assertIs(read['actually_read'],True)
                self.assertTrue(read['url'].startswith('https://') and read['version'] and read['read_locator'])
        current={n['question_id']:n for n in stage['items']}
        self.assertEqual({id:digest(current[id]) for id in baseline['explanation_hashes']},baseline['explanation_hashes'])
        registered={r['question_id']:r for r in group['registrations']}
        self.assertEqual(set(registered),{id for id,row in rows.items() if row['decision']=='register'})
        self.assertEqual(set(current),set(baseline['explanation_hashes'])|set(registered))
        self.assertEqual(len(registered),len(group['registrations']));self.assertEqual(len(registered),group['registered_count'])
        for id,registration in registered.items():
            note=authored_note(self.qs[id],rows[id]['draft_note'],group['checked_on'])
            self.assertEqual(current[id],note);self.assertEqual(registration['note'],note)
            self.assertEqual(registration['explanation_sha256'],digest(note))
            self.assertEqual(registration['proposal_record_sha256'],digest(rows[id]))
            self.assertEqual(registration['official_answers'],self.qs[id]['answers'])
            self.assertFalse(registration['official_answer_changed'])
            self.assertEqual(len({o['reason'] for o in note['option_notes']}),4)
        self.assertEqual({ref:digest(stage['sources'][ref]) for ref in baseline['source_hashes']},baseline['source_hashes'])
        self.assertEqual(set(stage['sources']),set(baseline['source_hashes'])|set(group['new_source_refs']))
        for ref in group['new_source_refs']:self.assertEqual(stage['sources'][ref],proposal['sources'][ref])
        self.assertEqual(after['review'],[r for r in group['original_review'] if r['question_id'] not in registered])
        self.assertEqual(group['remaining_review_count'],len(after['review']))
        for key,sha in baseline['audit_key_hashes'].items():
            if key!='review':self.assertEqual(digest(after[key]),sha,key)
        for name,sha in baseline['immutable_files'].items():self.assert_protected_file(name,sha)
        self.assertEqual(hashlib.sha256((json.dumps(self.before_round26_concepts,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),baseline['concepts_file_sha256'])
        self.assertEqual(hashlib.sha256((json.dumps(self.before_round26_concept_audit,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),baseline['concept_audit_file_sha256'])

    def test_round22_rejects_self_review_stale_approval_and_unread_registration(self):
        import tempfile
        from apply_round10_followups import digest
        from apply_round22_followups import approve
        row={'question_id':'sample','author':'writer','decision':'decline','source_reads':[],'checks':[]}
        qa={'reviewer':'reader','status':'pass','proposal_sha256':digest(row),
            'four_option_logic':[{'number':i,'status':'pass','note':f'original option {i}'} for i in (1,2,3,4)]}
        approve(row,qa)
        for key,value in [('reviewer','writer'),('status','issue'),('proposal_sha256','0'*64)]:
            invalid=dict(qa);invalid[key]=value
            with self.assertRaises(ValueError):approve(row,invalid)
        register=dict(row,decision='register')
        registration_review=dict(qa,proposal_sha256=digest(register),approved_decision='register',registration_approved=True)
        with self.assertRaisesRegex(ValueError,'actual independent source reads'):approve(register,registration_review)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'actual-body.txt';path.write_text('actual validation fixture body')
            read={'url':'https://example.test/source','private_path':str(path),'actually_read':True,
                  'version':'test fixture','read_locator':'body','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            register=dict(row,decision='register',source_reads=[read])
            registration_review=dict(qa,proposal_sha256=digest(register),source_reads=[read],
                                     approved_decision='register',registration_approved=True)
            approve(register,registration_review)
            for fields in ({'approved_decision':'decline'}, {'registration_approved':False},
                           {'approved_decision':'decline','registration_approved':False}):
                invalid=dict(registration_review,**fields)
                with self.assertRaises(ValueError):approve(register,invalid)

    def test_round21_complete_inspections_preserve_data_and_bind_independent_reviews(self):
        from apply_round10_followups import digest,public_record
        stage=self.stage_after.get('round21_inspections')
        if stage is None:self.skipTest('No round21 inspection yet')
        after=self.audit_after['round21_inspections'];group=after['round21_inspections']
        proposal_path=R/'reports/round21-proposals.json';qa_path=R/'reports/round21-independent-reviews.json'
        self.assertEqual(hashlib.sha256(proposal_path.read_bytes()).hexdigest(),group['proposal_sha256'])
        self.assertEqual(hashlib.sha256(qa_path.read_bytes()).hexdigest(),group['review_sha256'])
        proposal=json.loads(proposal_path.read_text());qa=json.loads(qa_path.read_text());baseline=group['baseline']
        self.assertEqual(baseline,proposal['baseline'])
        self.assertEqual({n['question_id']:digest(n) for n in stage['items']},baseline['explanation_hashes'])
        self.assertEqual({ref:digest(meta) for ref,meta in stage['sources'].items()},baseline['source_hashes'])
        for name,sha in baseline['immutable_files'].items():
            self.assert_protected_file(name,sha)
        self.assertEqual(hashlib.sha256((json.dumps(self.before_round26_concepts,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),baseline['concepts_file_sha256'])
        self.assertEqual(hashlib.sha256((json.dumps(self.before_round26_concept_audit,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),baseline['concept_audit_file_sha256'])
        for key,sha in baseline['audit_key_hashes'].items():
            if key!='answer_adjudication':self.assertEqual(digest(after[key]),sha,key)
        self.assertEqual(digest(group['before_adjudication']),baseline['audit_key_hashes']['answer_adjudication'])
        previous=group['before_adjudication'];expected=copy.deepcopy(previous)
        expected['resolutions']+=group['resolutions']
        self.assertEqual(after['answer_adjudication'],expected)
        self.assertEqual(after['review'],group['original_review'])
        pending={r['question_id']:r for r in group['original_review']};seen=set();authored={}
        recorded={r['question_id']:r for r in group['inspections']}
        self.assertEqual(len(recorded),len(group['inspections']))
        for category,count in [('parse_problem',11),('answer_suspected',18),('source_unverified',16),('calculation_unresolved',2)]:
            rows=proposal['inspections'][category];approved={r['question_id']:r for r in qa[category]}
            self.assertEqual(len(rows),count);self.assertEqual(len(approved),len(qa[category]))
            self.assertEqual({r['question_id'] for r in rows},set(approved))
            for row in rows:
                id=row['question_id'];review=approved[id]
                authored[id]=row
                self.assertNotIn(id,seen);seen.add(id)
                self.assertEqual(pending[id]['category'],category)
                self.assertEqual(row['previous_review'],pending[id])
                self.assertEqual(row['question_row_sha256'],digest(self.qs[id]))
                self.assertEqual(review['status'],'pass');self.assertNotEqual(review['reviewer'],row['author'])
                self.assertEqual(review['proposal_sha256'],digest(row))
                self.assertEqual(recorded[id],public_record(dict(
                    row,category=category,proposal_record_sha256=digest(row),independent_review=review)))
                self.assertEqual(sorted(r['number'] for r in review['four_option_logic']),[1,2,3,4])
                self.assertTrue(all(r['status']=='pass' and r['note'] for r in review['four_option_logic']))
                for read in row['source_reads']+review['source_reads']:
                    self.assertRegex(read['sha256'],r'^[0-9a-f]{64}$')
                    self.assertIs(read['actually_read'],True)
                    self.assertTrue(read['url'].startswith('https://') and read['version'] and read['read_locator'])
        self.assertEqual(seen,set(pending));self.assertEqual(group['inspected_count'],47)
        self.assertEqual(set(recorded),seen)
        self.assertEqual(group['registered_count'],0);self.assertEqual(group['original_corrections'],0)
        self.assertEqual({r['question_id'] for r in group['resolutions']},
                         {id for id,row in authored.items() if row['decision']=='resolve'})
        self.assertEqual({r['question_id'] for r in group['evidence_amendments']},
                         {id for id,row in authored.items() if row.get('evidence_update_required')})
        self.assertEqual(len(group['resolutions']),group['resolution_count'])
        self.assertEqual(len(group['evidence_amendments']),group['evidence_amendment_count'])
        self.assertEqual(len(group['resolutions']),len({r['question_id'] for r in group['resolutions']}))
        self.assertEqual(len(group['evidence_amendments']),len({r['question_id'] for r in group['evidence_amendments']}))
        original={r['question_id']:r for r in previous['records']+previous.get('explained_item_records',[])}
        for amendment in group['evidence_amendments']:
            id=amendment['question_id'];self.assertEqual(amendment['before_evidence'],original[id]['evidence'])
            self.assertEqual(amendment['verdict'],original[id]['verdict'])
            self.assertEqual(amendment['before_hash'],digest(amendment['before_evidence']))
            self.assertEqual(amendment['after_hash'],digest(amendment['after_evidence']))
            self.assertEqual(amendment['after_evidence'],authored[id]['proposed_evidence'])
            self.assertEqual(amendment['proposal_record_sha256'],digest(authored[id]))
            self.assertFalse(amendment['official_answer_changed'])
        for resolution in group['resolutions']:
            id=resolution['question_id'];self.assertEqual(resolution['previous_verdict'],original[id]['verdict'])
            self.assertNotEqual(resolution['verdict'],resolution['previous_verdict'])
            self.assertEqual(resolution['verdict'],authored[id]['proposed_verdict'])
            self.assertEqual(resolution['evidence'],authored[id]['proposed_evidence'])
            self.assertEqual(resolution['proposal_record_sha256'],digest(authored[id]))
            self.assertEqual(resolution['official_answers'],self.qs[id]['answers'])
            self.assertFalse(resolution['official_answer_changed'])

    def test_round21_evidence_replay_rejects_stale_duplicate_and_unknown_changes(self):
        from build_app_data import amend_adjudication_evidence
        original=[{'question_id':'sample','verdict':'official_conflict','evidence':'old','official_answers':[3]}]
        change={'question_id':'sample','verdict':'official_conflict','before_evidence':'old','after_evidence':'corrected'}
        corrected=amend_adjudication_evidence(original,[change])
        self.assertEqual(original[0]['evidence'],'old')
        self.assertEqual(corrected[0]['evidence'],'corrected')
        self.assertEqual(corrected[0]['official_answers'],[3])
        for key,value in [('verdict','official_supported'),('before_evidence','stale'),('question_id','missing'),('after_evidence','')]:
            invalid=dict(change);invalid[key]=value
            with self.assertRaises(ValueError):amend_adjudication_evidence(original,[invalid])
        with self.assertRaises(ValueError):amend_adjudication_evidence(original,[change,change])

    def test_round21_diagnostics_reject_unsupported_operators_and_false_results(self):
        from apply_round21_inspections import diagnostic_arithmetic
        diagnostic_arithmetic({'checks':[{'expression':'(10 + 2) / 3','expected':4,'computed':4}]})
        diagnostic_arithmetic({'checks':[{'expression':'922687*1.12-50000','expected':983409.44,
                                          'computed':983409.4400000001}]})
        for expression in ('10 // 3','10 > 3','10 ** 2','float("nan")'):
            with self.assertRaises((ValueError,SyntaxError)):
                diagnostic_arithmetic({'checks':[{'expression':expression,'expected':3}]})
        for check in ({'expression':'10 / 2','expected':4},
                      {'expression':'10 / 2','expected':5,'computed':4},
                      {'expression':'1','expected':1,'computed':True},
                      {'expression':'1','expected':True},
                      {'expression':'1','expected':float('nan')}):
            with self.assertRaises(ValueError):diagnostic_arithmetic({'checks':[check]})

    def test_answer_option_never_shares_reason_with_other_options(self):
        for id, n in self.current_notes.items():
            answer = {o['reason'].strip() for o in n['option_notes'] if o['is_answer']}
            others = {o['reason'].strip() for o in n['option_notes'] if not o['is_answer']}
            self.assertFalse(answer & others, id)


    def test_bundle_has_exact_explanations_and_unchanged_question_rows(self):
        raw = (R / 'assets/bank-data.js').read_text()
        b = json.loads(raw[len('window.BANK_DATA='):-2])
        self.assertEqual(b['explanations'], self.current_data)
        self.assertEqual(len(b['questions']), 4322)
        # The bundle shows current approved opinions; historical protection
        # tests above use the separately reconstructed earlier audit snapshots.
        live_audit = json.loads((R / 'reports/explanation-expansion.json').read_text())
        log = live_audit['answer_adjudication']
        resolved = {r['question_id']: r['verdict'] for r in log.get('resolutions', [])}
        shown = {a['question_id'] for a in log['records'] + log.get('explained_item_records', [])
                 if resolved.get(a['question_id'], a['verdict']) in
                 {'official_conflict', 'multiple_candidates', 'ambiguous_wording', 'deferred'}}
        self.assertEqual(set(b['answerNotes']), shown)
        expected_text={r['question_id']:r['evidence'] for r in log['records']+log.get('explained_item_records',[])}
        expected_text.update({r['question_id']:r['after_evidence'] for r in live_audit.get('round21_inspections',{}).get('evidence_amendments',[])})
        expected_text.update({r['question_id']:r['evidence'] for r in log.get('resolutions',[])})
        for id, note in b['answerNotes'].items():
            self.assertTrue(note['label'] and note['text'])
            self.assertEqual(note['text'],expected_text[id],id)
            self.assertEqual(b['questions'][[q['id'] for q in b['questions']].index(id)]['answers'], self.qs[id]['answers'])
        for q in b['questions']:
            self.assertEqual(q['answers'], self.qs[q['id']]['answers'])
            self.assertEqual(q['text'], self.qs[q['id']]['text'])
            self.assertEqual(q['taxYear'], self.qs[q['id']]['tax_law_year'])


if __name__ == '__main__':
    unittest.main()
