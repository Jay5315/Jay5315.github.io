"""Import independently reviewed cross-checks without rewriting previous rounds."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from explanation_data import validate_explanations
from merge_explanation_batches import R, digest
from test_concepts import calc


def merge(directory):
    dp, ap = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    original, audit = json.loads(dp.read_text()), json.loads(ap.read_text())
    data = copy.deepcopy(original)
    qs = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R / 'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R / 'data/taxonomy.json').read_text())}
    records = audit.setdefault('extra_rechecks', [])
    completed = {b['batch_id'] for b in records}
    assigned = {id for b in records for id in b['assigned_ids']}
    approved = json.loads((directory / 'approved-followups.json').read_text())
    hashes = json.loads((directory / 'approved-followup-hashes.json').read_text())
    changed = added = 0
    for bid in approved:
        if bid in completed:
            continue
        raw = (directory / (bid + '.output.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != hashes[bid]:
            raise ValueError(f'{bid}: approved output changed')
        batch = json.loads(raw)
        inp = json.loads((directory / (bid + '.input.json')).read_text())
        round_number = int(inp.get('extra_round', 4))
        if round_number < 4:
            raise ValueError('Extra rounds must follow the third pass')
        round_assigned = {id for b in records if b.get('extra_round',4)==round_number for id in b['assigned_ids']}
        ids = [q['id'] for q in inp['questions']]
        pending = {n['question_id']: n for n in audit['review']}
        snapshot = inp['previous_review']
        if isinstance(snapshot, dict):
            if any(id != row['question_id'] for id, row in snapshot.items()):
                raise ValueError(f'{bid}: invalid review snapshot keys')
            snapshot = list(snapshot.values())
        prior = {n['question_id']: n for n in snapshot}
        outcomes = [n['question_id'] for n in batch['items'] + batch['review']]
        if (batch['batch_id'] != bid or not 20 <= len(ids) <= 30
                or len(ids) != len(set(ids)) or set(ids) & round_assigned
                or len(outcomes) != len(set(outcomes)) or set(outcomes) != set(ids)
                or set(prior) != set(ids) or not set(ids) <= pending.keys()
                or any(prior[id] != pending[id] for id in ids)):
            raise ValueError(f'{bid}: overlapping, stale or incomplete assignment')
        validate_explanations(batch, qs, entries, parts)
        rename = {}
        for ref, source in batch['sources'].items():
            if not source.get('version') and source.get('versions'):
                source['version'] = ' / '.join(source['versions'])
            if not all(source.get(k) for k in ('title', 'url', 'version', 'verification', 'checked_on')):
                raise ValueError(f'{bid}: incomplete source')
            key = ref if ref not in data['sources'] or data['sources'][ref] == source else bid + '__' + ref
            if key in data['sources'] and data['sources'][key] != source:
                raise ValueError(f'{bid}: source collision')
            data['sources'][key] = source
            rename[ref] = key
        resolved = []
        for n in batch['items']:
            id = n['question_id']
            if (n['review_status'] != 'source_checked' or n['unchecked_points']
                    or n['part_id'] != qs[id]['classification']['primary_part_id']):
                raise ValueError(f'{id}: not fully checked')
            for c in n['checks']:
                if abs(calc(c['expr']) - c['expected']) > 1e-6:
                    raise ValueError(f'{id}: arithmetic mismatch')
            for citation in n['sources']:
                citation['ref'] = rename[citation['ref']]
            first = next(b for b in audit['batches'] if id in b['review_ids'])
            first['review_ids'].remove(id)
            first['accepted_ids'].append(id)
            data['items'].append(n)
            audit.setdefault('review_resolutions', []).append({
                'question_id': id, 'batch_id': first['batch_id'], 'extra_batch_id': bid,
                'previous_reason': pending[id]['reason'], 'previous_review': pending[id],
                'reason': n['review_note'], 'explanation_hash': digest(n), 'checked_on': n['checked_on']})
            resolved.append(id)
            added += 1
        remaining = {}
        for n in batch['review']:
            if not n.get('reason') or n['category'] not in {
                    'source_unverified', 'answer_suspected', 'parse_problem', 'calculation_unresolved'}:
                raise ValueError(f'{bid}: invalid review')
            id = n['question_id']
            remaining[id] = dict(pending[id], **n, extra_batch_id=bid)
        audit['review'] = [remaining.get(n['question_id'], n) for n in audit['review']
                           if n['question_id'] not in resolved]
        records.append({'batch_id': bid, 'extra_round':round_number, 'worker': inp.get('worker', 'independent cross-review'),
                        'assigned_ids': ids, 'resolved_ids': resolved, 'remaining_ids': list(remaining),
                        'previous_review': list(prior.values()), 'worker_validation': batch.get('validation', {}),
                        'output_hash': hashes[bid], 'snapshot_provenance': inp.get('snapshot_provenance', {})})
        assigned.update(ids)
        changed += 1
    validate_explanations(data, qs, entries, parts)
    assert data['items'][:len(original['items'])] == original['items']
    assert all(data['sources'][ref] == s for ref, s in original['sources'].items())
    audit.update(registered_count=len(data['items']), added_count=len(data['items']) - audit['baseline_count'],
                 review_count=len(audit['review']), extra_rechecked_count=sum(len(b['assigned_ids']) for b in records),
                 extra_rechecked_unique_count=len(assigned),
                 extra_added_count=sum(len(b['resolved_ids']) for b in records))
    if changed:
        dp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        ap.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print('Extra cross-checks:', len(assigned), 'New:', added, 'Registered:', len(data['items']),
          'Remaining review:', len(audit['review']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    merge(parser.parse_args().directory)
