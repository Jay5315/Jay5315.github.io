"""Apply reviewed append-only concept enrichments with source and hash audit."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from merge_explanation_batches import R, digest
from test_concepts import calc


def merge(path):
    raw = path.read_bytes()
    proposal = json.loads(raw)
    sha = hashlib.sha256(raw).hexdigest()
    dp, ap = R / 'data/concept-notes.json', R / 'reports/concept-expansion.json'
    data, audit = json.loads(dp.read_text()), json.loads(ap.read_text())
    if sha in audit.get('applied_followup_delta_hashes', []):
        print('Already applied:', path.name)
        return
    notes = {n['id']: n for n in data['notes']}
    append_fields = {'key_points', 'formulas', 'pitfalls', 'examples', 'sources'}
    used = {s['ref'] for d in proposal['deltas'] for s in d['append']['sources']}
    for ref in used:
        source = proposal['sources'][ref]
        if not all(source.get(k) for k in ('title', 'url', 'versions', 'checked_on', 'verification')):
            raise ValueError(f'{ref}: incomplete source')
        if ref in data['sources'] and data['sources'][ref] != source:
            raise ValueError(f'{ref}: source overwrite')
        data['sources'][ref] = source
    for d in proposal['deltas']:
        if not any(d['append'].values()):
            continue
        n = notes[d['note_id']]
        if digest(n) != d['before_sha256_canonical_sorted_compact_utf8']:
            raise ValueError(f"{n['id']}: stale note")
        if not d['actual_source_reads'] or set(d['append']) != append_fields:
            raise ValueError(f"{n['id']}: unverified/unsupported edit")
        before = copy.deepcopy(n)
        for field in append_fields:
            n[field].extend(d['append'][field])
        status = d['status_delta']
        if status['review_status'] != before['review_status']:
            raise ValueError('Status upgrades require separate direct verification')
        n['unchecked_points'] = status['unchecked_points']
        n['review_note'] += ' ' + status['review_note_append']
        for e in d['append']['examples']:
            if not e['checks']:
                raise ValueError('Example without arithmetic checks')
            for c in e['checks']:
                if abs(calc(c['expr']) - c['expected']) > 1e-6:
                    raise ValueError('Arithmetic mismatch')
        for s in n['sources']:
            if s['ref'] not in data['sources'] or not s['locator']:
                raise ValueError('Unregistered/unlocated source')
        audit.setdefault('followup_note_amendments', []).append({
            'note_id': n['id'], 'before': before, 'before_hash': digest(before),
            'after_hash': digest(n), 'operations': d['append'], 'source_reads': d['actual_source_reads'],
            'reason': status['verification_scope'], 'worker_validation': proposal['validation'],
            'output_hash': sha})
    audit.setdefault('applied_followup_delta_hashes', []).append(sha)
    dp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    ap.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print('Enriched notes:', sum(any(d['append'].values()) for d in proposal['deltas']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    merge(parser.parse_args().path)
