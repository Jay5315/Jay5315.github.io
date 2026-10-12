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
            if id in self.baseline_ids and self.qs[id]['subject'] == '재무회계':
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
            self.assertEqual(digest(self.notes[id]), hash, id)
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
                self.assertEqual(reviews[id]['recheck_batch_id'], b['batch_id'])
        self.assertEqual(self.audit['second_pass_added_count'], len(resolved))

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
        for mutate in ('duplicate', 'answer', 'source', 'status', 'option'):
            d = copy.deepcopy(self.data)
            if mutate == 'duplicate': d['items'].append(d['items'][0])
            elif mutate == 'answer': d['items'][0]['answers'] = [1]
            elif mutate == 'source': d['items'][0]['sources'][0]['ref'] = 'invented'
            elif mutate == 'status': d['items'][0]['review_status'] = 'source_checked'
            elif mutate == 'option': d['items'][0]['option_notes'][0]['is_answer'] = True
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
