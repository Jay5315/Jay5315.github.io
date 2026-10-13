#!/usr/bin/env python3
"""Rewrite wrong-option reasons that duplicated another option's reason (round 12).

Usage: python3 scripts/apply_round12_option_rewrites.py REWRITES.json REVIEWS.json

REWRITES.json: [{question_id, reasons: {number: text}, derivation_checks, author}]
REVIEWS.json: [{question_id, reviewer, status, options: [{number, status, note}], notes}]

Only option_notes[].reason of the listed options changes, and only when an independent
reviewer (different from the author) passed every rewritten option. Answers, option
numbers, is_answer flags, checks, sources and every other field stay as they were.
The ledger `round12_option_rewrites` keeps each before object and before/after hashes.
"""
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-13'


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def duplicated(note):
    count = Counter(o['reason'].strip() for o in note['option_notes'])
    return sorted(o['number'] for o in note['option_notes'] if count[o['reason'].strip()] > 1)


def main(rewrites_path, reviews_path):
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'round12_option_rewrites' in audit:
        raise SystemExit('round12_option_rewrites already applied')
    notes = {n['question_id']: n for n in data['items']}
    reviews = {r['question_id']: r for r in json.loads(Path(reviews_path).read_text())}
    records, skipped = [], []
    for row in json.loads(Path(rewrites_path).read_text()):
        id, note = row['question_id'], notes[row['question_id']]
        targets = sorted(int(k) for k in row['reasons'])
        review = reviews.get(id)
        passed = review and review['status'] == 'pass' and review['reviewer'] != row['author'] and \
            sorted(o['number'] for o in review['options']) == targets and \
            all(o['status'] == 'pass' for o in review['options'])
        if targets != duplicated(note) or not passed:
            skipped.append(id)
            continue
        before = copy.deepcopy(note)
        for o in note['option_notes']:
            if o['number'] in targets:
                o['reason'] = row['reasons'][str(o['number'])]
        if len({o['reason'] for o in note['option_notes']}) != 4:
            raise SystemExit(f'{id}: reasons still duplicated')
        records.append(dict(question_id=id, rewritten_options=targets, before=before, before_hash=digest(before),
                            after_hash=digest(note), author=row['author'], derivation_checks=row['derivation_checks'],
                            independent_review=review))
    audit['round12_option_rewrites'] = dict(
        checked_on=CHECKED_ON, count=len(records), skipped_ids=skipped,
        policy='다른 보기와 같은 문구였던 오답 보기 설명만 그 보기 내용에 맞게 다시 썼습니다. 작성자와 다른 검수자가 '
               '다시 쓴 보기를 모두 통과시킨 경우에만 반영했고, 다른 필드는 바꾸지 않았습니다.',
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Rewrote {len(records)} explanations; skipped {skipped}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
