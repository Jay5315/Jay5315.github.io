"""Protect space-only insertions, every candidate review, and the prior audit."""
import copy
import json
import re
import unittest
from pathlib import Path

from apply_spacing_round2 import TEXT_FIELDS, digest, get, keys
from apply_spacing_round6 import (GROUP, PROPOSALS, REVIEWS, approved_rows,
                                  insertion_positions, restore_spacing_round6)

R = Path(__file__).resolve().parents[1]


class SpacingRound6Tests(unittest.TestCase):
    def test_every_candidate_and_previous_record_are_protected(self):
        data = json.loads((R / 'data/explanations.json').read_text())
        audit = json.loads((R / 'reports/explanation-expansion.json').read_text())
        proposal = json.loads((R / PROPOSALS).read_text())
        reviews = json.loads((R / REVIEWS).read_text())
        self.assertTrue(GROUP in audit, 'Missing spacing_round6 audit stage')
        group = audit[GROUP]
        before, previous = restore_spacing_round6(data, audit)
        self.assertEqual(digest(before), proposal['baseline_data_hash'])
        self.assertEqual(digest(previous), proposal['baseline_audit_hash'])
        self.assertEqual(digest(proposal), group['proposal_sha256'])
        self.assertEqual(digest(reviews), group['review_sha256'])
        notes = {n['question_id']: n for n in before['items']}
        selected = approved_rows(proposal, reviews, notes)
        patterns = [re.compile(p) for p in proposal['selection_patterns']]
        expected_locations = {(n['question_id'], field, index) for n in before['items']
                              for field, index in keys(n)
                              if any(p.search(get(n, field, index)) for p in patterns)}
        self.assertEqual(set(selected), expected_locations)
        self.assertEqual(len(selected), group['candidate_count'])
        self.assertEqual(sum(r['decision'] == 'accept' for r in selected.values()), group['accepted_fields'])
        self.assertEqual(sum(len(insertion_positions(r['before'], r['after'])) for r in selected.values()),
                         group['inserted_spaces'])
        self.assertEqual([r['candidate_id'] for r in selected.values() if r['decision'] == 'decline'],
                         group['declined_candidate_ids'])
        self.assertEqual(data['sources'], before['sources'])
        self.assertEqual(list(data), list(before))
        self.assertEqual([n['question_id'] for n in data['items']], list(notes))
        records = {r['question_id']: r for r in group['notes']}
        self.assertEqual(len(records), len(group['notes']))
        self.assertEqual(group['count'], len(records))
        for n in data['items']:
            qid = n['question_id']
            old = notes[qid]
            for key in set(old) - set(TEXT_FIELDS):
                self.assertEqual(n[key], old[key], (qid, key))
            self.assertEqual([(o['number'], o['is_answer']) for o in n['option_notes']],
                             [(o['number'], o['is_answer']) for o in old['option_notes']])
            for field, index in keys(old):
                row = selected.get((qid, field, index))
                expected = row['after'] if row else get(old, field, index)
                self.assertEqual(get(n, field, index), expected, (qid, field, index))
                self.assertEqual(re.sub(r'\s', '', get(old, field, index)),
                                 re.sub(r'\s', '', expected))
                insertion_positions(get(old, field, index), expected)
            self.assertEqual(qid in records, n != old)
            if qid in records:
                row = records[qid]
                self.assertEqual(row['before'], old)
                self.assertEqual(row['before_hash'], digest(old))
                self.assertEqual(row['after_hash'], digest(n))
                self.assertEqual(row['changed_fields'], sorted(k for k in TEXT_FIELDS if old[k] != n[k]))

    def test_rejects_nonspace_deletion_reference_formula_and_self_review(self):
        for old, new in [('3개', '4 개'), ('정답 ②', '정답②'), ('가나', '가\t나'),
                         ('제72조⑤', '제72조 ⑤'), ('제1항', '제1 항'),
                         ('IAS12.5', 'IAS 12.5'), ('B3.3.2', 'B3.3. 2'),
                         ('1.5원/시간', '1.5원 /시간'), ('A=B÷C', 'A= B÷C'),
                         ('1,500−300×2=900', '1,500−300 ×2=900')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                insertion_positions(old, new)
        insertion_positions('B8.75%는맞지만', 'B 8.75%는 맞지만')
        row = dict(candidate_id='one', question_id='q', field='summary', index=None,
                   before='220원증가', after='220원 증가', author='writer', decision='accept')
        note = dict(title='', summary=row['before'], review_note='', steps=[], option_notes=[], unchecked_points=[])
        qa = dict(candidate_id='one', proposal_sha256=digest(row), verdict='approve',
                  decision='accept', reviewer='reviewer', reason='문장 경계를 직접 확인했습니다.')
        p, r = {'rows': [row]}, {'rows': [qa]}
        approved_rows(p, r, {'q': note})
        for mutate in [lambda x: x.update(reviewer='writer'),
                       lambda x: x.update(proposal_sha256='0'*64),
                       lambda x: x.update(verdict='changes_requested'),
                       lambda x: x.update(reason='')]:
            bad = copy.deepcopy(r)
            mutate(bad['rows'][0])
            with self.assertRaises(ValueError):
                approved_rows(p, bad, {'q': note})
        with self.assertRaises(ValueError):
            approved_rows(p, {'rows': []}, {'q': note})


if __name__ == '__main__':
    unittest.main()
