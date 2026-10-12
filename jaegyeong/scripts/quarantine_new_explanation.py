"""Withdraw a newly added explanation after verified QA, preserving its history."""
import argparse
import hashlib
import json
from pathlib import Path

from merge_explanation_batches import R, digest


def quarantine(path):
    raw = path.read_bytes()
    proposal = json.loads(raw)
    id = proposal['question_id']
    dp, ap = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(dp.read_text()), json.loads(ap.read_text())
    if id in {r['question_id'] for r in audit.get('final_quality_withdrawals', [])}:
        print('Already quarantined:', id)
        return
    if id in audit['third_pass_baseline_hashes']:
        raise ValueError('Existing explanations are protected')
    n = next(n for n in data['items'] if n['question_id'] == id)
    if digest(n) != proposal['before_item_hash'] or n['answers'] != proposal['official_answers_preserved']:
        raise ValueError('Stale explanation or official answer')
    if not proposal['sources_read'] or not proposal['validation']:
        raise ValueError('Missing independent source verification')
    third = next(b for b in audit['third_pass_batches'] if id in b['resolved_ids'])
    previous = next(r for r in third['previous_review'] if r['question_id'] == id)
    first = next(b for b in audit['batches'] if id in b['accepted_ids'])
    review = dict(previous, **proposal['review_proposal'], round3_batch_id=third['batch_id'],
                  final_quality_withdrawal=True)
    if review['question_id'] != id or review['category'] not in {'parse_problem','answer_suspected','source_unverified','calculation_unresolved'}:
        raise ValueError('Invalid quarantine review')
    first['accepted_ids'].remove(id)
    first['review_ids'].append(id)
    data['items'] = [x for x in data['items'] if x['question_id'] != id]
    audit['review'].append(review)
    audit.setdefault('final_quality_withdrawals', []).append({
        'question_id': id, 'before': n, 'before_hash': digest(n), 'reason': review['reason'],
        'source_reads': proposal['sources_read'], 'worker_validation': proposal['validation'],
        'proposal_hash': hashlib.sha256(raw).hexdigest(), 'official_answers_preserved': n['answers'],
        'third_pass_batch_id': third['batch_id'], 'checked_on': n['checked_on']})
    audit.update(registered_count=len(data['items']), added_count=len(data['items']) - audit['baseline_count'],
                 review_count=len(audit['review']),
                 third_pass_net_added_count=audit['third_pass_added_count'] - len(audit['final_quality_withdrawals']))
    dp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    ap.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print('Quarantined:', id, 'Registered:', len(data['items']), 'Review:', len(audit['review']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    quarantine(parser.parse_args().path)
