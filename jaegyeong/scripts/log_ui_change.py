"""Append an app.js/app.css change to reports/ui-changes.json.

The round 21-24 audit baselines pin assets/app.js and assets/app.css; test_explanations.py
accepts later versions only along this hash chain. Run after editing either file:

    python3 scripts/log_ui_change.py "변경 요약"

It fails if neither file changed since the last recorded hash. Afterwards run
python3 scripts/build_app_data.py so the manifest/SRI match the new runtime files.
"""
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ('assets/app.js', 'assets/app.css')


def expected_ui_hash(name, pinned, root=ROOT):
    """Advance only UI baselines along the existing, continuous audited chain.

    Other files retain their exact hash. Historical hashes are never rewritten.
    Callers still compare the returned hash with the actual file bytes.
    """
    if name not in FILES:
        return pinned
    changes = json.loads((root / 'reports/ui-changes.json').read_text())['changes']
    previous = None
    expected = pinned
    for change in changes:
        if not change['summary'] or not change['date'] or not set(change['files']) <= set(FILES):
            raise ValueError('Invalid UI change record')
        step = change['files'].get(name)
        if not step:
            continue
        if any(not isinstance(step.get(k), str) or not re.fullmatch(r'[0-9a-f]{64}', step[k])
               for k in ('before', 'after')):
            raise ValueError('Invalid UI hash')
        if previous is not None and step['before'] != previous:
            raise ValueError('Broken UI change chain')
        if step['before'] == expected:
            expected = step['after']
        previous = step['after']
    return expected


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        sys.exit('usage: log_ui_change.py "summary"')
    path = ROOT / 'reports/ui-changes.json'
    log = json.loads(path.read_text(encoding='utf-8'))
    previous = {f: [c['files'][f]['after'] for c in log['changes'] if f in c['files']][-1] for f in FILES}
    files = {f: {'before': previous[f], 'after': sha(f)} for f in FILES if previous[f] != sha(f)}
    if not files:
        sys.exit('No change in assets/app.js or assets/app.css since the last recorded entry.')
    log['changes'].append({'date': datetime.date.today().isoformat(), 'summary': sys.argv[1].strip(), 'files': files})
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('recorded:', ', '.join(files))


if __name__ == '__main__':
    main()
