"""Resolve reviewed IDs without replacing any registered explanation.

Independent second-pass outputs use the same format as first-pass outputs.
Only explicitly approved output hashes are imported. Original review reasons
are retained in the audit trail, even when a new explanation resolves them.
"""
import argparse
import calendar
import copy
import datetime
import hashlib
import json
import re
from pathlib import Path

from explanation_data import validate_explanations
from merge_explanation_batches import R, digest
from test_concepts import calc


def merge(directory):
    original = json.loads((R / 'data/explanations.json').read_text())
    data = copy.deepcopy(original)
    path = R / 'reports/explanation-expansion.json'
    audit = json.loads(path.read_text())
    questions = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R / 'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R / 'data/taxonomy.json').read_text())}
    completed = {b['batch_id'] for b in audit.get('rechecks', [])}
    assigned = {id for b in audit.get('rechecks', []) for id in b['assigned_ids']}
    hashes = json.loads((directory / 'approved-recheck-hashes.json').read_text())
    changed = 0
    added = 0
    for bid in sorted(json.loads((directory / 'approved-rechecks.json').read_text())):
        if bid in completed:
            continue
        raw = (directory / (bid + '.output.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != hashes[bid]:
            raise ValueError(f'{bid}: approved output changed')
        batch = json.loads(raw)
        inp = json.loads((directory / (bid + '.input.json')).read_text())
        ids = [q['id'] for q in inp['questions']]
        outcomes = [n['question_id'] for n in batch['items'] + batch['review']]
        pending = {n['question_id']: n for n in audit['review']}
        if (batch['batch_id'] != bid or not 20 <= len(ids) <= 30
                or len(set(ids)) != len(ids) or set(ids) & assigned
                or len(set(outcomes)) != len(outcomes) or set(outcomes) != set(ids)
                or not set(ids) <= pending.keys()):
            raise ValueError(f'{bid}: overlapping, missing or non-review assignment')
        prior = {n['question_id']: n for n in inp['previous_review']}
        if set(prior) != set(ids) or any(prior[id] != pending[id] for id in ids):
            raise ValueError(f'{bid}: review changed after assignment')
        validate_explanations(batch, questions, entries, parts)
        rename = {}
        for ref, source in batch['sources'].items():
            if not all(source.get(k) for k in ('title', 'url', 'version', 'verification', 'checked_on')):
                raise ValueError(f'{bid}: incomplete source')
            target = ref if ref not in data['sources'] or data['sources'][ref] == source else bid + '__' + ref
            if target in data['sources'] and data['sources'][target] != source:
                raise ValueError(f'{bid}: source collision')
            data['sources'][target] = source
            rename[ref] = target
        resolved = []
        for n in batch['items']:
            id = n['question_id']
            q = questions[id]
            if (n['review_status'] != 'source_checked' or n['unchecked_points']
                    or n['part_id'] != q['classification']['primary_part_id']):
                raise ValueError(f'{bid}: unverified item or incorrect part')
            for c in n['checks']:
                if abs(calc(c['expr']) - c['expected']) > 1e-6:
                    raise ValueError(f'{id}: arithmetic mismatch')
            for s in n['sources']:
                s['ref'] = rename[s['ref']]
                source = data['sources'][s['ref']]
                dates = re.findall(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', source['version'])
                if 'law.go.kr' in source['url']:
                    cutoff = datetime.date(q['year'], q['month'], calendar.monthrange(q['year'], q['month'])[1])
                    if q['tax_law_year']:
                        cutoff = min(cutoff, datetime.date(q['tax_law_year'], 12, 31))
                    if len(dates) == 1 and datetime.date(*map(int, dates[0])) > cutoff:
                        raise ValueError(f'{id}: future-effective source')
            record = next(b for b in audit['batches'] if id in b['review_ids'])
            record['review_ids'].remove(id)
            record['accepted_ids'].append(id)
            data['items'].append(n)
            audit.setdefault('review_resolutions', []).append({
                'question_id': id, 'batch_id': record['batch_id'], 'recheck_batch_id': bid,
                'previous_reason': pending[id]['reason'], 'reason': n['review_note'],
                'explanation_hash': digest(n), 'checked_on': n['checked_on']})
            resolved.append(id)
            added += 1
        remaining = {}
        for n in batch['review']:
            if not n.get('reason') or n['category'] not in {
                    'source_unverified', 'answer_suspected', 'parse_problem', 'calculation_unresolved'}:
                raise ValueError(f'{bid}: invalid review')
            id = n['question_id']
            remaining[id] = dict(n, batch_id=pending[id]['batch_id'], recheck_batch_id=bid)
        audit['review'] = [remaining.get(n['question_id'], n) for n in audit['review']
                           if n['question_id'] not in resolved]
        audit.setdefault('rechecks', []).append({
            'batch_id': bid, 'assigned_ids': ids, 'resolved_ids': resolved,
            'remaining_ids': list(remaining), 'previous_review': list(prior.values()),
            'worker_validation': batch.get('validation', {}), 'output_hash': hashes[bid]})
        assigned.update(ids)
        changed += 1
    validate_explanations(data, questions, entries, parts)
    assert data['items'][:len(original['items'])] == original['items']
    assert all(data['sources'][ref] == source for ref, source in original['sources'].items())
    assert all(digest(next(n for n in data['items'] if n['question_id'] == id)) == h
               for id, h in audit['baseline_hashes'].items())
    audit.update(registered_count=len(data['items']), added_count=len(data['items']) - audit['baseline_count'],
                 review_count=len(audit['review']), rechecked_count=len(assigned),
                 second_pass_added_count=sum(len(b['resolved_ids']) for b in audit.get('rechecks', [])))
    if changed:
        (R / 'data/explanations.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print('Rechecked:', len(assigned), 'Resolved:', added, 'Registered:', len(data['items']),
          'Remaining review:', len(audit['review']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    merge(parser.parse_args().directory)
