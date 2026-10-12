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

R = Path(__file__).resolve().parents[1]


class ExplanationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def read(name):
            return json.loads((R / 'data' / (name + '.json')).read_text())
        cls.data = read('explanations')
        cls.qs = {q['id']: q for q in read('questions')}
        cls.entries = {e['id'] for e in read('entries')}
        cls.parts = {p['id'] for p in read('taxonomy')}
        cls.notes = {n['question_id']: n for n in cls.data['items']}
        audit = R / 'reports/explanation-expansion.json'
        cls.audit = json.loads(audit.read_text()) if audit.exists() else None
        cls.baseline_ids = set(cls.audit['baseline_hashes']) if cls.audit else set(list(cls.notes)[:30])

    def validate(self, data=None, qs=None):
        return validate_explanations(data or self.data, qs or self.qs, self.entries, self.parts)

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
        withdrawn = {n['question_id'] for n in self.audit.get('final_quality_withdrawals', [])}
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
        withdrawn = {n['question_id'] for n in self.audit.get('final_quality_withdrawals', [])}
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
        self.assertEqual(len(resolved), self.audit['extra_added_count'])
        for index,b in enumerate(records):
            self.assertTrue(20 <= len(b['assigned_ids']) <= 30)
            done, remaining = set(b['resolved_ids']), set(b['remaining_ids'])
            self.assertFalse(done & remaining)
            self.assertEqual(set(b['assigned_ids']), done | remaining)
            self.assertEqual(set(b['assigned_ids']), {r['question_id'] for r in b['previous_review']})
            self.assertTrue(b['output_hash'] and b['worker_validation'])
            for id in done:
                self.assertIn(id, self.notes)
                self.assertEqual(resolved[id]['extra_batch_id'], b['batch_id'])
                self.assertTrue(resolved[id]['previous_reason'])
            for id in remaining:
                later=[x for x in records[index+1:] if id in x['assigned_ids']]
                if later:
                    previous=next(r for r in later[0]['previous_review'] if r['question_id']==id)
                    self.assertEqual(previous['extra_batch_id'],b['batch_id'])
                if id in resolved:
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
        for row in withdrawn:
            id=row['question_id']
            self.assertNotIn(id,self.audit['third_pass_baseline_hashes'])
            self.assertNotIn(id,self.notes)
            self.assertTrue(reviews[id]['final_quality_withdrawal'])
            self.assertEqual(row['before_hash'],digest(row['before']))
            self.assertEqual(row['official_answers_preserved'],self.qs[id]['answers'])
            self.assertTrue(row['source_reads'] and row['worker_validation'] and row['proposal_hash'])
            self.assertTrue(any(id in b['resolved_ids'] for b in self.audit['third_pass_batches']))
        if withdrawn:
            self.assertEqual(self.audit['third_pass_net_added_count'],self.audit['third_pass_added_count']-len(ids))

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

    def test_bundle_has_exact_explanations_and_unchanged_question_rows(self):
        raw = (R / 'assets/bank-data.js').read_text()
        b = json.loads(raw[len('window.BANK_DATA='):-2])
        self.assertEqual(b['explanations'], self.data)
        self.assertEqual(len(b['questions']), 4322)
        for q in b['questions']:
            self.assertEqual(q['answers'], self.qs[q['id']]['answers'])
            self.assertEqual(q['text'], self.qs[q['id']]['text'])
            self.assertEqual(q['taxYear'], self.qs[q['id']]['tax_law_year'])


if __name__ == '__main__':
    unittest.main()
