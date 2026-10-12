"""Data integrity and content-based classification regressions."""
import json, unittest
from pathlib import Path
from classify_parts import infer
D=Path(__file__).resolve().parents[1]/'data'
def read(name):return json.loads((D/(name+'.json')).read_text())
class PartsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q={q['id']:q for q in read('questions')};cls.e=read('entries');cls.t={p['id']:p for p in read('taxonomy')}
    def test_complete_valid_subjects(self):
        for e in self.e:
            c=e['classification'];self.assertEqual(self.t[c['primary_part_id']]['subject'],e['subject'])
            self.assertTrue(all(i in self.t for i in c['secondary_part_ids']))
            for id in e['occurrence_ids']:
                self.assertEqual(self.q[id]['classification']['primary_part_id'],c['primary_part_id'])
                self.assertEqual(self.q[id]['classification']['tags'],c['tags'])
        self.assertEqual(sum(p['entry_count'] for p in self.t.values()),len(self.e))
        self.assertEqual(sum(p['source_count'] for p in self.t.values()),len(self.q))
    def test_review_manifest(self):
        flagged={e['id'] for e in self.e if e['classification']['review_required']}
        self.assertEqual(flagged,{e['id'] for e in read('classification-review')})
        self.assertEqual(len(flagged),read('classification-summary')['review_entries'])
        for e in self.e:
            c=e['classification']
            if c['confidence'] in ('low','medium'):self.assertTrue(c['review_required'])
    def test_numeric_families(self):
        for f in read('families'):
            parts={self.q[id]['classification']['primary_part_id'] for id in f['entry_ids']}
            self.assertEqual(set(f['primary_part_ids']),parts)
            if len(parts)>1:
                for id in f['entry_ids']:self.assertTrue(self.q[id]['classification']['review_required'])
    def test_content_focus_regressions(self):
        expected={
            '2022-03-016':'F10', # Contract cash flows of financial assets, not cash flow statement.
            '2022-09-040':'F26',
            '2022-05-038':'F26',
            '2023-01-039':'F26',
            '2026-03-040':'F26', # Investing cash flows despite financial-asset balances.
            '2026-03-031':'F20', # Correcting errors, not accounting for income tax.
            '2023-11-103':'M10', # High-low estimation with incidental cost-driver wording.
            '2025-01-065':'I05', # Other income explicitly excludes business income.
            '2023-06-050':'C05', # Corporate interest recognition, not personal withholding.
            '2024-03-088':'M05', # Equivalent-unit illustration.
            '2026-06-077':'V04', # House and appurtenant-land exemption.
            '2025-07-111':'M13', # Investment-center performance, not capital budgeting.
        }
        for id,part in expected.items():
            with self.subTest(id=id):
                self.assertEqual(self.q[id]['classification']['primary_part_id'],part)
                q={**self.q[id],'id':'unrelated','number':999,'subject_number':999,'answers':[4]}
                self.assertEqual(infer(q)['primary_part_id'],part)
    def test_tags_and_original_answers(self):
        self.assertIn('고저점법',self.q['2023-11-103']['classification']['tags'])
        self.assertEqual(self.q['2026-07-026']['answers'],[1,4])
        self.assertFalse(self.q['2024-09-063']['study_eligible'])
if __name__=='__main__':unittest.main(verbosity=2)
