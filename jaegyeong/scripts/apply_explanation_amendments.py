"""Apply reviewed prose-only deltas, retaining original worker output hashes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from explanation_data import validate_explanations
from merge_explanation_batches import R, digest


def apply(path):
    raw = path.read_bytes()
    delta = json.loads(raw)
    sha = hashlib.sha256(raw).hexdigest()
    dp, ap = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(dp.read_text()), json.loads(ap.read_text())
    if sha in audit.get('applied_prose_delta_hashes', []):
        print('Already applied:', path.name)
        return
    notes = {n['question_id']: n for n in data['items']}
    changes = delta.get('changes', []) + [c for b in delta.get('batches', []) for c in b['changes']]
    if not changes or len({c['question_id'] for c in changes}) != len(changes):
        raise ValueError('Empty or overlapping amendment')
    for c in changes:
        id = c['question_id']
        if id in audit['third_pass_baseline_hashes']:
            raise ValueError(f'{id}: existing explanation protected')
        n = notes[id]
        if digest(n) != c['before_item_sha256']:
            raise ValueError(f'{id}: stale before hash')
        before = copy.deepcopy(n)
        if c.get('changed_fields'):
            for field, v in c['changed_fields'].items():
                if field not in {'summary', 'steps', 'option_notes'} or n[field] != v['before']:
                    raise ValueError(f'{id}: unsupported/stale field')
                if field == 'option_notes':
                    if len(v['before']) != len(v['after']):
                        raise ValueError(f'{id}: options added/removed')
                    for old, new in zip(v['before'], v['after']):
                        if ({k: val for k, val in old.items() if k != 'reason'}
                                != {k: val for k, val in new.items() if k != 'reason'}):
                            raise ValueError(f'{id}: option binding changed')
                n[field] = v['after']
        for op in c.get('operations', []):
            segments = op['path'].strip('/').split('/')
            if segments[:1] == ['items']:
                segments = segments[2:]
            if (op['op'] != 'replace' or not segments or segments[0] not in {'summary', 'steps'}
                    or len(segments) > 2):
                raise ValueError(f'{id}: unsupported operation')
            target = n if len(segments) == 1 else n[segments[0]]
            key = segments[0] if len(segments) == 1 else int(segments[1])
            if target[key] != op['before']:
                raise ValueError(f'{id}: stale field')
            target[key] = op['after']
        if digest(n) != c['after_item_sha256']:
            raise ValueError(f'{id}: after hash mismatch')
        protected = {k: v for k, v in before.items() if k not in {'summary', 'steps', 'option_notes'}}
        if protected != {k: v for k, v in n.items() if k not in {'summary', 'steps', 'option_notes'}}:
            raise ValueError(f'{id}: non-prose field changed')
        audit.setdefault('third_pass_prose_amendments', []).append({
            'question_id': id, 'before': before, 'after_hash': digest(n),
            'changed_fields': [k for k in before if before[k] != n[k]],
            'reason': c.get('reason', '실제 검증한 보기의 핵심 원리를 구체화하고 표현을 교정. 정답·계산·출처 불변.'),
            'delta_hash': sha})
    qs = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    es = {e['id'] for e in json.loads((R / 'data/entries.json').read_text())}
    ps = {p['id'] for p in json.loads((R / 'data/taxonomy.json').read_text())}
    validate_explanations(data, qs, es, ps)
    audit.setdefault('applied_prose_delta_hashes', []).append(sha)
    dp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    ap.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print('Applied prose amendments:', len(changes))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    apply(parser.parse_args().path)
