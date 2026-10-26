#!/usr/bin/env python3
"""Apply independently reviewed space insertions, following apply_spacing_round5.

Usage: python3 scripts/apply_spacing_round6.py
Candidates, including declined rows, are in reports/spacing-round6-candidates.json.
"""
import copy
import json
import re
from pathlib import Path

from apply_spacing_round2 import TEXT_FIELDS, digest, get, keys, put

R = Path(__file__).resolve().parents[1]
GROUP = 'spacing_round6'
CHECKED_ON = '2026-10-26'
PROPOSALS = 'reports/spacing-round6-candidates.json'
REVIEWS = 'reports/spacing-round6-independent-review.json'
# References, compound units and contiguous arithmetic expressions remain joined.
TERM = r'(?:[A-Za-z_][A-Za-z_0-9]*|\d+(?:,\d{3})*(?:\.\d+)?(?:억원|원|단위|시간|[%²])?)'
PROTECTED = re.compile(
    r'제\d+조(?:의\d+)?(?:제\d+[항호목])*[①②③④⑤]?|제\d+[항호목]'
    r'|(?:IAS|IFRS)\d+(?:\.\d+)+|B\d+(?:\.\d+)+(?![\d.%])|문단\d+(?:\.\d+)*'
    r'|\d+(?:\.\d+)?원/시간|'+TERM+r'(?:[=≈+−\-×÷*/><]'+TERM+r')+')


def insertion_positions(old, new):
    """Reject edits other than inserted ASCII spaces, including whitespace removal."""
    i = 0
    positions = []
    for char in new:
        if i < len(old) and char == old[i]:
            i += 1
        elif char == ' ':
            positions.append(i)
        else:
            raise ValueError('Only ASCII space insertions are permitted')
    if i != len(old) or re.sub(r'\s', '', old) != re.sub(r'\s', '', new):
        raise ValueError('The original text, including existing whitespace, is protected')
    for match in PROTECTED.finditer(old):
        if any(match.start() < p < match.end() for p in positions):
            raise ValueError('A reference, unit or arithmetic expression was split')
    return positions


def approved_rows(proposal, reviews, notes):
    rows = proposal['rows']
    qa_rows = reviews['rows']
    qa = {r['candidate_id']: r for r in qa_rows}
    ids = [r['candidate_id'] for r in rows]
    if len(ids) != len(set(ids)) or len(qa) != len(qa_rows) or set(qa) != set(ids):
        raise ValueError('Every candidate, including declines, needs one exact review')
    selected = {}
    for row in rows:
        q = qa[row['candidate_id']]
        loc = (row['question_id'], row['field'], row['index'])
        if loc in selected or row['question_id'] not in notes:
            raise ValueError('Duplicate or unknown candidate location')
        if (q['proposal_sha256'] != digest(row) or q['verdict'] != 'approve'
                or q['decision'] != row['decision'] or not q['reason']
                or not row['author'] or not q['reviewer'] or row['author'] == q['reviewer']):
            raise ValueError('Missing, stale or non-independent candidate review')
        if (row['field'], row['index']) not in set(keys(notes[row['question_id']])):
            raise ValueError('Candidate field is outside TEXT_FIELDS')
        if get(notes[row['question_id']], row['field'], row['index']) != row['before']:
            raise ValueError('Stale candidate text')
        positions = insertion_positions(row['before'], row['after'])
        if row['decision'] not in ('accept', 'decline') or bool(positions) != (row['decision'] == 'accept'):
            raise ValueError('Candidate decision does not match its actual space insertions')
        selected[loc] = row
    return selected


def restore_spacing_round6(data, audit):
    """Verify and reverse this stage before all historical data/hash checks."""
    group = (audit or {}).get(GROUP)
    if not group:
        return data, audit
    before, old_audit = copy.deepcopy(data), copy.deepcopy(audit)
    index = {n['question_id']: i for i, n in enumerate(before['items'])}
    for row in group['notes']:
        if (digest(before['items'][index[row['question_id']]]) != row['after_hash']
                or digest(row['before']) != row['before_hash']):
            raise ValueError('Spacing round 6 encountered an unrecorded change')
        before['items'][index[row['question_id']]] = copy.deepcopy(row['before'])
    del old_audit[GROUP]
    if digest(before) != group['baseline_data_hash'] or digest(old_audit) != group['baseline_audit_hash']:
        raise ValueError('Spacing round 6 does not restore the protected baseline')
    return before, old_audit


def main():
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if GROUP in audit:
        raise SystemExit('spacing_round6 already applied')
    proposal = json.loads((R / PROPOSALS).read_text())
    reviews = json.loads((R / REVIEWS).read_text())
    if digest(data) != proposal['baseline_data_hash'] or digest(audit) != proposal['baseline_audit_hash']:
        raise ValueError('Candidate baseline has changed')
    selected = approved_rows(proposal, reviews, {n['question_id']: n for n in data['items']})
    records = []
    for n in data['items']:
        before = copy.deepcopy(n)
        for field, index in keys(n):
            row = selected.get((n['question_id'], field, index))
            if row and row['decision'] == 'accept':
                put(n, field, index, row['after'])
        if n != before:
            records.append(dict(question_id=n['question_id'], before=before, before_hash=digest(before),
                                after_hash=digest(n),
                                changed_fields=sorted(k for k in TEXT_FIELDS if before[k] != n[k])))
    audit[GROUP] = dict(
        checked_on=CHECKED_ON, count=len(records),
        policy='독립 검수한 후보에 ASCII 공백만 삽입합니다. 기존 공백·비공백 글자·참조·단위·수식 내부는 보존합니다. '
               '정답·보기 번호·is_answer·계산식·출처·상태·문항 결속은 바꾸지 않습니다.',
        baseline_data_hash=proposal['baseline_data_hash'], baseline_audit_hash=proposal['baseline_audit_hash'],
        proposal_sha256=digest(proposal), review_sha256=digest(reviews),
        candidate_count=len(selected), accepted_fields=sum(r['decision'] == 'accept' for r in selected.values()),
        inserted_spaces=sum(len(insertion_positions(r['before'], r['after'])) for r in selected.values()),
        declined_candidate_ids=[r['candidate_id'] for r in selected.values() if r['decision'] == 'decline'],
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Respaced {len(records)} explanations; inserted {audit[GROUP]["inserted_spaces"]} spaces')


if __name__ == '__main__':
    main()
