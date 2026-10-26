"""Keep historical UI pins valid only along the complete recorded hash chain."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from log_ui_change import FILES, expected_ui_hash

R = Path(__file__).resolve().parents[1]


class UIChangeChainTests(unittest.TestCase):
    def test_actual_recorded_ui_versions_reach_current_bytes(self):
        log = json.loads((R / 'reports/ui-changes.json').read_text())
        for name in FILES:
            steps = [c['files'][name] for c in log['changes'] if name in c['files']]
            actual = hashlib.sha256((R / name).read_bytes()).hexdigest()
            for pin in [steps[0]['before'], *[s['after'] for s in steps]]:
                self.assertEqual(expected_ui_hash(name, pin), actual, name)
        self.assertEqual(expected_ui_hash('data/questions.json', 'original'), 'original')

    def test_missing_broken_or_invalid_chain_never_blesses_changed_files(self):
        a, b, c = 'a'*64, 'b'*64, 'c'*64
        rows = [dict(date='2026-10-26', summary='first', files={'assets/app.js':dict(before=a,after=b)}),
                dict(date='2026-10-26', summary='second', files={'assets/app.js':dict(before=b,after=c)})]
        original = copy.deepcopy(rows)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'reports').mkdir()
            path = root / 'reports/ui-changes.json'
            def write(value):
                path.write_text(json.dumps({'changes':value}))
            write(rows)
            self.assertEqual(expected_ui_hash('assets/app.js', a, root), c)
            self.assertEqual(expected_ui_hash('assets/app.js', b, root), c)
            self.assertEqual(rows, original)
            write(rows[:1])
            self.assertNotEqual(expected_ui_hash('assets/app.js', a, root), c)
            write([])
            self.assertNotEqual(expected_ui_hash('assets/app.js', a, root), c)
            for mutate in [lambda r:r[1]['files']['assets/app.js'].update(before='0'*64),
                           lambda r:r[1]['files']['assets/app.js'].update(after='not-a-hash'),
                           lambda r:r[1]['files'].update({'data/questions.json':dict(before=b,after=c)}),
                           lambda r:r[1].update(summary='')]:
                bad = copy.deepcopy(original)
                mutate(bad)
                write(bad)
                with self.assertRaises(ValueError):
                    expected_ui_hash('assets/app.js', a, root)


if __name__ == '__main__':
    unittest.main()
