"""Regression checks against independently inspected source examples."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class BankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.questions={q['id']:q for q in json.loads((ROOT/'data/questions.json').read_text())}
        cls.entries={e['id']:e for e in json.loads((ROOT/'data/entries.json').read_text())}
        cls.families=json.loads((ROOT/'data/families.json').read_text())

    def test_every_source_is_retained_exactly_once(self):
        members=[i for e in self.entries.values() for i in e['occurrence_ids']]
        self.assertEqual(len(members),4560)
        self.assertEqual(len(set(members)),4560)
        self.assertEqual(set(members),set(self.questions))

    def test_reordered_options_keep_representative_answer(self):
        a,b=(self.questions[i] for i in ['2022-06-001','2022-09-001'])
        self.assertEqual(a['entry_id'],b['entry_id'])
        self.assertEqual(a['answers'],[1])
        self.assertEqual(b['answers'],[4])
        rep=self.questions[a['entry_id']]
        self.assertIn('경영진',rep['choices'][rep['answers'][0]-1])

    def test_same_question_with_reordered_all_word_not_over_restricted(self):
        self.assertEqual(self.questions['2023-09-001']['entry_id'],self.questions['2023-12-001']['entry_id'])

    def test_verified_equivalent_wording(self):
        self.assertEqual(self.questions['2024-07-001']['entry_id'],self.questions['2025-07-001']['entry_id'])

    def test_changed_knowledge_and_negation_not_merged(self):
        for left,right in [('2024-06-001','2024-11-001'),('2023-06-005','2024-06-005'),('2022-07-092','2023-05-092')]:
            self.assertNotEqual(self.questions[left]['entry_id'],self.questions[right]['entry_id'])

    def test_numeric_variations_retained_in_same_family(self):
        a,b=(self.questions[i]['entry_id'] for i in ['2022-01-105','2023-09-105'])
        self.assertNotEqual(a,b)
        self.assertEqual(self.entries[a]['family_id'],self.entries[b]['family_id'])

    def test_multiple_official_answers(self):
        self.assertEqual(self.questions['2026-07-026']['answers'],[1,4])

    def test_incomplete_original_is_quarantined(self):
        q=self.questions['2024-09-063']
        self.assertFalse(q['study_eligible'])
        self.assertIn('source_has_three_visible_choices',q['review_flags'])

    def test_governing_tax_year_is_not_assumed_from_exam_year(self):
        self.assertEqual(self.questions['2026-01-041']['tax_law_year'],2025)
        self.assertEqual(self.questions['2026-03-041']['tax_law_year'],2025)
        self.assertEqual(self.questions['2026-05-041']['tax_law_year'],2026)

    def test_family_membership_and_assets(self):
        members=[i for f in self.families for i in f['entry_ids']]
        self.assertEqual(set(members),set(self.entries))
        self.assertEqual(len(members),len(self.entries))
        for q in self.questions.values():
            self.assertTrue((ROOT/q['image']).is_file(),q['id'])
            self.assertTrue((ROOT/q['source_pdf']).is_file(),q['id'])
            self.assertTrue((ROOT/q['answer_pdf']).is_file(),q['id'])

if __name__=='__main__':unittest.main(verbosity=2)
