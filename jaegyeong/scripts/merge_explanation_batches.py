"""Merge independent worker batches without overwriting existing explanations.

Usage: python scripts/merge_explanation_batches.py /absolute/batch-directory
Workers write *.input.json and *.output.json; only the coordinator runs this script.
All inputs and outputs are checked before any repository data is written.
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
from test_concepts import calc

R = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def merge(directory):
    original = json.loads((R / 'data/explanations.json').read_text())
    data = copy.deepcopy(original)
    questions = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R / 'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R / 'data/taxonomy.json').read_text())}
    old_ids = {n['question_id'] for n in original['items']}
    seen = set(old_ids)
    report_path = R / 'reports/explanation-expansion.json'
    audit = json.loads(report_path.read_text()) if report_path.exists() else {
        'schema_version': 1, 'started_on': '2026-10-12',
        'baseline_count': len(original['items']),
        'baseline_hashes': {n['question_id']: digest(n) for n in original['items']},
        'baseline_sources_hash': digest(original['sources']),
        'baseline_source_hashes': {ref: digest(s) for ref, s in original['sources'].items()},
        'batches': [], 'review': []}
    completed = {b['batch_id'] for b in audit['batches']}
    assigned = {id for b in audit['batches'] for id in b['assigned_ids']}
    added = 0
    approved = json.loads((directory / 'approved-batches.json').read_text())
    hashes_path = directory / 'approved-batch-hashes.json'
    approved_hashes = json.loads(hashes_path.read_text()) if hashes_path.exists() else {}
    for bid_to_read in sorted(approved):
        path = directory / (bid_to_read + '.output.json')
        output_bytes = path.read_bytes()
        batch = json.loads(output_bytes)
        if batch['batch_id'] != bid_to_read:
            raise ValueError('Output filename and batch ID differ')
        bid = batch['batch_id']
        if bid in completed:
            continue
        if bid in approved_hashes and hashlib.sha256(output_bytes).hexdigest() != approved_hashes[bid]:
            raise ValueError(f'{bid}: output changed after coordinator approval')
        inp = json.loads((directory / (bid + '.input.json')).read_text())
        input_ids = [q['id'] for q in inp['questions']]
        expected = set(input_ids)
        if (len(input_ids) != len(expected) or not 20 <= len(expected) <= 30
                or expected & assigned or expected & old_ids):
            raise ValueError(f'{bid}: invalid size or overlapping assignment')
        ids = [n['question_id'] for n in batch['items']]
        reviews = [n['question_id'] for n in batch['review']]
        if len(set(ids + reviews)) != len(ids + reviews) or set(ids + reviews) != expected:
            raise ValueError(f'{bid}: missing, duplicated or unassigned result')
        for id in expected:
            if id not in entries or not questions[id]['study_eligible']:
                raise ValueError(f'{bid}: unavailable original {id}')
        rename = {}
        for ref, source in batch['sources'].items():
            if not all(source.get(f) for f in ('title', 'url', 'version', 'verification', 'checked_on')):
                raise ValueError(f'{bid}: incomplete verified source {ref}')
            new_ref = ref
            if ref in data['sources'] and data['sources'][ref] != source:
                new_ref = bid + '__' + ref
            if new_ref in data['sources'] and data['sources'][new_ref] != source:
                raise ValueError(f'{bid}: source collision {ref}')
            data['sources'][new_ref] = source
            rename[ref] = new_ref
        for n in batch['items']:
            id = n['question_id']
            if id in seen or n['review_status'] != 'source_checked' or n['unchecked_points']:
                raise ValueError(f'{bid}: duplicate or unverified item {id}')
            if n['part_id'] != questions[id]['classification']['primary_part_id']:
                raise ValueError(f'{bid}: wrong concept link {id}')
            for c in n['checks']:
                if abs(calc(c['expr']) - c['expected']) > 1e-6:
                    raise ValueError(f'{bid}: arithmetic mismatch {id}: {c}')
            for s in n['sources']:
                s['ref'] = rename[s['ref']]
                source = data['sources'][s['ref']]
                q = questions[id]
                if 'law.go.kr' in source['url']:
                    dates = re.findall(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', source['version'])
                    latest = datetime.date(q['year'], q['month'],
                                           calendar.monthrange(q['year'], q['month'])[1])
                    if q['tax_law_year']:
                        latest = min(latest, datetime.date(q['tax_law_year'], 12, 31))
                    if len(dates) == 1 and datetime.date(*map(int, dates[0])) > latest:
                        raise ValueError(f'{bid}: future-effective tax source {id}: {s["ref"]}')
            seen.add(id)
            data['items'].append(n)
            added += 1
        for n in batch['review']:
            if not n.get('reason') or n['category'] not in {
                'source_unverified', 'answer_suspected', 'parse_problem', 'calculation_unresolved'}:
                raise ValueError(f'{bid}: incomplete review record')
            audit['review'].append(dict(n, batch_id=bid))
        audit['batches'].append({
            'batch_id': bid, 'assigned_ids': sorted(expected), 'accepted_ids': ids,
            'review_ids': reviews, 'worker_validation': batch.get('validation', {})})
        assigned.update(expected)
        completed.add(bid)
    validate_explanations(data, questions, entries, parts)
    for id, hash in audit['baseline_hashes'].items():
        n = next(n for n in data['items'] if n['question_id'] == id)
        if digest(n) != hash:
            raise ValueError(f'Existing explanation changed: {id}')
    if data['items'][:len(original['items'])] != original['items']:
        raise ValueError('Existing items overwritten')
    for ref, source in original['sources'].items():
        if data['sources'].get(ref) != source:
            raise ValueError('Existing verified source overwritten')
    eligible = {id for id in entries if questions[id]['study_eligible']}
    audit.update(target_count=len(eligible), registered_count=len(data['items']),
                 added_count=len(data['items']) - audit['baseline_count'],
                 processed_count=len(assigned), review_count=len(audit['review']),
                 unprocessed_ids=sorted(eligible - seen - {n['question_id'] for n in audit['review']}))
    if added or set(completed) != {b['batch_id'] for b in
                                (json.loads(report_path.read_text())['batches'] if report_path.exists() else [])}:
        (R / 'data/explanations.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        report_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: audit[k] for k in ('target_count', 'registered_count', 'added_count',
                                          'processed_count', 'review_count')}, ensure_ascii=False))
    print('Unprocessed:', len(audit['unprocessed_ids']), 'Newly merged:', added)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    merge(parser.parse_args().directory)
