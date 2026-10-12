"""Import explicitly reviewed follow-up batches, preserving earlier audit rounds."""
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
    data_path = R / 'data/explanations.json'
    audit_path = R / 'reports/explanation-expansion.json'
    original = json.loads(data_path.read_text())
    data = copy.deepcopy(original)
    audit = json.loads(audit_path.read_text())
    questions = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R / 'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R / 'data/taxonomy.json').read_text())}
    records = audit.setdefault('third_pass_batches', [])
    completed = {b['batch_id'] for b in records}
    assigned = {id for b in records for id in b['assigned_ids']}
    hashes = json.loads((directory / 'approved-followup-hashes.json').read_text())
    manifest_path = directory / 'manifest.json'
    manifest = ({b['batch_id']: b for b in json.loads(manifest_path.read_text())}
                if manifest_path.exists() else {})
    changed = added = 0
    for bid in sorted(json.loads((directory / 'approved-followups.json').read_text())):
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
        prior = {n['question_id']: n for n in inp['previous_review']}
        if (batch['batch_id'] != bid or not 20 <= len(ids) <= 30
                or len(set(ids)) != len(ids) or set(ids) & assigned
                or len(set(outcomes)) != len(outcomes) or set(outcomes) != set(ids)
                or set(prior) != set(ids) or not set(ids) <= pending.keys()
                or any(prior[id] != pending[id] for id in ids)):
            raise ValueError(f'{bid}: overlapping, missing, stale or non-review assignment')
        if 'third_pass_baseline_hashes' not in audit:
            audit.update(third_pass_target_count=len(pending),
                         third_pass_baseline_hashes={n['question_id']: digest(n) for n in original['items']},
                         third_pass_baseline_source_hashes={ref: digest(s) for ref, s in original['sources'].items()})
        validate_explanations(batch, questions, entries, parts)
        rename = {}
        for ref, source in batch['sources'].items():
            if not source.get('version') and source.get('versions'):
                source['version'] = ' / '.join(source['versions'])
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
            for citation in n['sources']:
                citation['ref'] = rename[citation['ref']]
                source = data['sources'][citation['ref']]
                if 'law.go.kr' in source['url']:
                    cutoff = datetime.date(q['year'], q['month'], calendar.monthrange(q['year'], q['month'])[1])
                    if q['tax_law_year']:
                        cutoff = min(cutoff, datetime.date(q['tax_law_year'], 12, 31))
                    dates = re.findall(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', source['version'])
                    if len(dates) == 1 and datetime.date(*map(int, dates[0])) > cutoff:
                        raise ValueError(f'{id}: future-effective legal source')
            first = next(b for b in audit['batches'] if id in b['review_ids'])
            first['review_ids'].remove(id)
            first['accepted_ids'].append(id)
            data['items'].append(n)
            audit.setdefault('review_resolutions', []).append({
                'question_id': id, 'batch_id': first['batch_id'], 'round3_batch_id': bid,
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
            remaining[id] = dict(n, batch_id=pending[id]['batch_id'],
                                 recheck_batch_id=pending[id]['recheck_batch_id'], round3_batch_id=bid)
        audit['review'] = [remaining.get(n['question_id'], n) for n in audit['review'] if n['question_id'] not in resolved]
        records.append({'batch_id': bid, 'assigned_ids': ids, 'resolved_ids': resolved,
                        'remaining_ids': list(remaining), 'previous_review': list(prior.values()),
                        'worker_validation': batch.get('validation', {}), 'output_hash': hashes[bid]})
        assigned.update(ids)
        changed += 1
    validate_explanations(data, questions, entries, parts)
    assert data['items'][:len(original['items'])] == original['items']
    assert all(data['sources'][ref] == s for ref, s in original['sources'].items())
    audit.update(registered_count=len(data['items']), added_count=len(data['items']) - audit['baseline_count'],
                 review_count=len(audit['review']), third_pass_processed_count=len(assigned),
                 third_pass_added_count=sum(len(b['resolved_ids']) for b in records),
                 third_pass_unprocessed_ids=sorted(n['question_id'] for n in audit['review']
                                                  if n['question_id'] not in assigned),
                 third_pass_complete=len(assigned) == audit.get('third_pass_target_count'))
    for b in records:
        if b['batch_id'] in manifest:
            assignment = manifest[b['batch_id']]
            if set(assignment['assigned_ids']) != set(b['assigned_ids']):
                raise ValueError(f"{b['batch_id']}: changed manifest assignment")
            b['worker'] = assignment['worker']
    audit['third_pass_workers'] = sorted({b['worker'] for b in records if b.get('worker')})
    if changed:
        data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print('Third pass:', len(assigned), 'New:', added, 'Registered:', len(data['items']),
          'Remaining review:', len(audit['review']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    merge(parser.parse_args().directory)
