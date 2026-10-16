"""Generate a lightweight index and immutable, subject-specific explanation scripts."""
import copy
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
SUBJECTS = {'재무회계': 'finance', '세무회계': 'tax', '원가관리회계': 'cost'}
RUNTIME = ['index.html', 'assets/app.css', 'assets/app.js', 'assets/data-loader.js',
           'assets/offline.js', 'assets/icon.svg']


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')


def sha(body):
    return hashlib.sha256(body).hexdigest()


def build_runtime_data(data):
    target = R / 'assets/bank'
    target.mkdir(exist_ok=True)
    manifest_path = R / 'assets/bank-manifest.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    written = set()

    def emit(label, make_body):
        # The payload hash determines the filename; the complete script gets its own SRI hash.
        payload = make_body(None)
        name = f'assets/bank/{label}-{sha(payload)[:16]}.js'
        body = make_body(name)
        (R / name).write_bytes(body)
        written.add(name)
        return {'url': name, 'sha256': sha(body), 'bytes': len(body)}

    parts = {p['id']: p['subject'] for p in data['parts']}
    subjects = {}
    all_refs = {s['ref'] for n in data['explanations']['items'] for s in n['sources']}
    unused_refs = set(data['explanations']['sources']) - all_refs
    for subject, code in SUBJECTS.items():
        items = [n for n in data['explanations']['items'] if parts[n['part_id']] == subject]
        refs = {s['ref'] for n in items for s in n['sources']}
        if code == 'finance':
            refs |= unused_refs  # Preserve historical, currently unreferenced source definitions too.
        payload = {'items': items, 'sources': {k: v for k, v in data['explanations']['sources'].items() if k in refs}}
        body = packed(payload)
        subjects[code] = emit('explanations-' + code, lambda name, body=body:
            ('(window.BANK_CHUNKS=window.BANK_CHUNKS||{})[' + json.dumps(name or '') + ']=' + body + ';\n').encode())
        subjects[code]['count'] = len(items)

    index = copy.deepcopy(data)
    index['explanations']['items'] = [{'question_id': n['question_id'], 'part_id': n['part_id']}
                                      for n in data['explanations']['items']]
    index['explanations']['sources'] = {}
    core = emit('core', lambda _name: ('window.BANK_DATA=' + packed(index) + ';\n').encode())
    runtime = {name: {'sha256': sha((R / name).read_bytes()), 'bytes': (R / name).stat().st_size}
               for name in RUNTIME}
    plan = {'format': 1, 'core': core, 'subjects': subjects, 'runtime': runtime,
            'part_subjects': {p['id']: SUBJECTS[p['subject']] for p in data['parts']}}
    plan['build_id'] = sha(packed(plan).encode())[:20]
    manifest_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    # Delete only obsolete generated scripts referenced by the previous manifest.
    for spec in [old.get('core', {}), *old.get('subjects', {}).values()]:
        name = spec.get('url', '')
        if name.startswith('assets/bank/') and Path(name).parent == Path('assets/bank') and name not in written:
            (R / name).unlink(missing_ok=True)
    print(f"Runtime core {core['bytes'] / 1048576:.2f} MiB; 3 deferred explanation subjects; build {plan['build_id']}")
