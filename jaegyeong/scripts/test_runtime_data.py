"""Verify split data against the complete original bundle and the bounded HTML audit."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from loader_entrypoint import restore_entrypoint
from runtime_data import packed

R = Path(__file__).resolve().parents[1]


class RuntimeDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = json.loads((R / 'assets/bank-data.js').read_text()[len('window.BANK_DATA='):-2])
        cls.manifest = json.loads((R / 'assets/bank-manifest.json').read_text())

    def test_manifest_file_hashes_and_build_identity(self):
        m = self.manifest
        self.assertEqual(m['format'], 1)
        self.assertEqual(set(m['subjects']), {'finance', 'tax', 'cost'})
        for spec in [m['core'], *m['subjects'].values()]:
            body = (R / spec['url']).read_bytes()
            self.assertEqual(len(body), spec['bytes'])
            self.assertEqual(hashlib.sha256(body).hexdigest(), spec['sha256'])
        for name, spec in m['runtime'].items():
            self.assertEqual(hashlib.sha256((R / name).read_bytes()).hexdigest(), spec['sha256'])
        without_id = {k: v for k, v in m.items() if k != 'build_id'}
        self.assertEqual(hashlib.sha256(packed(without_id).encode()).hexdigest()[:20], m['build_id'])

    def test_full_reconstruction_preserves_all_content_and_order(self):
        m = self.manifest
        core = json.loads((R / m['core']['url']).read_text()[len('window.BANK_DATA='):-2])
        self.assertEqual(core['questions'], self.full['questions'])
        self.assertEqual(core['concepts'], self.full['concepts'])
        self.assertEqual(len(core['explanations']['items']), 4281)
        self.assertTrue(all(set(n) == {'question_id', 'part_id'} for n in core['explanations']['items']))
        notes = {}
        for code, spec in m['subjects'].items():
            body = (R / spec['url']).read_text()
            prefix = '(window.BANK_CHUNKS=window.BANK_CHUNKS||{})[' + json.dumps(spec['url']) + ']='
            self.assertTrue(body.startswith(prefix))
            payload = json.loads(body[len(prefix):-2])
            self.assertEqual(len(payload['items']), spec['count'])
            for n in payload['items']:
                self.assertNotIn(n['question_id'], notes)
                self.assertEqual(m['part_subjects'][n['part_id']], code)
                notes[n['question_id']] = n
                self.assertTrue(all(s['ref'] in payload['sources'] for s in n['sources']))
            for ref, src in payload['sources'].items():
                if ref in core['explanations']['sources']:
                    self.assertEqual(src, core['explanations']['sources'][ref])
                core['explanations']['sources'][ref] = src
        self.assertEqual(len(notes), len(core['explanations']['items']))
        core['explanations']['items'] = [notes[n['question_id']] for n in core['explanations']['items']]
        # Compare per field and note to avoid dumping a 20 MB recursive diff on failure.
        for key in self.full:
            if key == 'explanations':
                self.assertEqual(set(core[key]['sources']), set(self.full[key]['sources']))
                for ref in self.full[key]['sources']:
                    self.assertEqual(core[key]['sources'][ref], self.full[key]['sources'][ref], ref)
                for actual, expected in zip(core[key]['items'], self.full[key]['items']):
                    self.assertEqual(actual, expected, expected['question_id'])
                self.assertEqual({k: v for k, v in core[key].items() if k not in ('items', 'sources')}, {k: v for k, v in self.full[key].items() if k not in ('items', 'sources')})
            else:
                self.assertTrue(core[key] == self.full[key], key)

    def test_initial_data_is_less_than_half_of_complete_bundle(self):
        core = (R / self.manifest['core']['url']).stat().st_size
        full = (R / 'assets/bank-data.js').stat().st_size
        self.assertLess(core, full * .5)

    def test_only_approved_entrypoint_reference_can_change(self):
        current = (R / 'index.html').read_bytes()
        original = restore_entrypoint(current)
        self.assertIn(b'assets/bank-data.js', original)
        for bad in [current + b'\n', current.replace(b'lang="ko"', b'lang="en"'), current.replace(b'assets/data-loader.js', b'assets/other.js')]:
            with self.assertRaises(ValueError):
                restore_entrypoint(bad)
        record = json.loads((R / 'reports/runtime-entrypoint.json').read_text())
        record['before_html'] += '\n'
        with self.assertRaises(ValueError):
            restore_entrypoint(current, record)


if __name__ == '__main__':
    unittest.main()
