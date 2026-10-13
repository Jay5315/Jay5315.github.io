#!/usr/bin/env python3
"""Apply the round-11 review corrections with an auditable before/after ledger.

Usage: python3 scripts/apply_round11_corrections.py SPACED.json

1. Spacing: whitespace-only replacements for text in explanations touched by round 10.
   A replacement is rejected unless removing all whitespace gives the original string.
2. Content: the explicit edits below (2022-07-018 option 1 vs. its unchecked point,
   2024-06-021 and 2026-05-021 status/wording consistency, work-history wording in
   three learner-facing texts).

Answers, option numbers, is_answer flags, checks, sources and question binding never
change. Each changed explanation is recorded in reports/explanation-expansion.json under
`round11_corrections` with before object, before/after hashes and per-string change kind.
answer_adjudication is not edited, so the round-10 ledger stays exactly as recorded.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-13'
FIELDS = {'title': 'title', 'summary': 'summary', 'review_note': 'review_note', 'steps': 'steps',
          'option': 'option_notes', 'unchecked': 'unchecked_points'}
PROTECTED = ('question_id', 'question_fingerprint', 'answers', 'part_id', 'checks', 'sources',
             'tax_law_year', 'authorship')

UNCHECKED_0718 = ('원문은 20X1년 말 표시이자를 지급한 뒤 105,000원에 사채를 상환한 경우입니다. '
                  '첫해 유효이자 8,412.08원, 상환손실 1,436.92원, 장부금액 103,563.08원은 검산됩니다. '
                  '그러나 ①의 "3년 동안 사채의 총이자비용 8,412원"은 실제 보유기간에 인식한 이자비용으로 읽으면 '
                  '옳을 수 있어, 공식 ②만 옳다는 유일성은 확인하지 못했습니다.')
UNCHECKED_0521 = ('보기 ④의 "현금배당 시 부채비율 증가"는 다른 부채 변동이 없고 부채가 양수이며 배당 전후 '
                  '자본이 모두 양수인 기본 모형에서만 성립합니다. 원문이 이 조건을 제시하지 않아 ④가 모든 경우에 '
                  '옳은지, 따라서 공식 ③의 유일성은 확인하지 못했습니다.')
CONTENT = {
    ('2022-07-018', 'option', 1): '8,412원은 첫해 유효이자비용을 반올림한 금액입니다. 사채를 20X1년 말에 상환했으므로 '
                                  '실제로 인식한 이자비용이 이 금액뿐이라고 읽으면 ①도 옳은 설명이 될 여지가 있습니다. '
                                  '"3년 동안"을 만기까지의 계약기간 전체로 읽을 때만 틀린 설명이 되며, 원문은 어느 쪽인지 '
                                  '정하지 않아 ①을 확정적으로 반박하지 않습니다.',
    ('2022-07-018', 'unchecked', 0): UNCHECKED_0718,
    ('2024-06-021', 'steps', 0): '현금배당은 이익잉여금과 총자본을 감소시키며 자본금은 변하지 않습니다. 배당결의 때는 '
                                 '미지급배당금 부채가 생기고, 실제 지급 때는 그 부채와 현금이 함께 줄어듭니다. 배당절차 '
                                 '전과 지급 완료 후를 비교하고 다른 부채 변동이 없으며 부채와 자본이 양수인 기본 모형에서는 '
                                 '자본 감소로 부채비율이 높아집니다. ④는 주식배당 부분만으로도 틀리므로 이 조건은 정답 '
                                 '판단에 영향을 주지 않습니다.',
    ('2026-05-021', 'option', 4): '주식배당은 부채와 총자본을 바꾸지 않으므로 부채비율도 변하지 않습니다. 현금배당으로 '
                                  '비율이 높아진다는 부분은 다른 부채 변동이 없고 부채와 자본이 양수인 기본 모형에서 '
                                  '성립하는 설명이며, 원문이 이 조건을 따로 제시하지 않은 점은 확인하지 못한 내용에 적었습니다.',
}
REPLACE = {  # learner-facing work-history wording
    ('2025-07-083', 'steps', 2): ('새 국내 교안은', '국내 교안은'),
    ('2023-01-083', 'steps', 0): ('새 국내 교안은', '국내 교안은'),
    ('2023-01-108', 'option', 4): ('새 교재는', '교재는'),
}
STATUS = {'2026-05-021': ('partial', [UNCHECKED_0521])}


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def get(n, kind, index):
    if kind in ('title', 'summary', 'review_note'):
        return n[kind]
    if kind == 'option':
        return next(o for o in n['option_notes'] if o['number'] == int(index))['reason']
    return n[FIELDS[kind]][int(index)]


def put(n, kind, index, value):
    if kind in ('title', 'summary', 'review_note'):
        n[kind] = value
    elif kind == 'option':
        next(o for o in n['option_notes'] if o['number'] == int(index))['reason'] = value
    else:
        n[FIELDS[kind]][int(index)] = value


def main(spaced_path):
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'round11_corrections' in audit:
        raise SystemExit('round11_corrections already applied')
    touched = {r['question_id'] for r in audit['round10_followups']['amendments']} | \
              {r['question_id'] for r in audit['round10_followups']['registrations']}
    notes = {n['question_id']: n for n in data['items']}
    befores, changes, rejected = {}, {}, []

    def record(id, kind, index, change, old, new):
        befores.setdefault(id, copy.deepcopy(notes[id]))
        changes.setdefault(id, []).append(dict(field=FIELDS[kind], index=index, change=change,
                                               before=old, after=new))

    content_keys = set(CONTENT) | {(i, k, int(x) if x is not None else None) for i, k, x in REPLACE}
    for row in json.loads(Path(spaced_path).read_text()):
        id, kind, index = row['key'].split('|')
        index = None if index == 'None' else int(index)
        if id not in touched or (id, kind, index) in CONTENT:
            continue
        old, new = get(notes[id], kind, index), row['text']
        if re.sub(r'\s', '', old) != re.sub(r'\s', '', new) or '  ' in new or new != new.strip():
            rejected.append(row['key'])
            continue
        if old != new:
            record(id, kind, index, 'spacing', old, new)
            put(notes[id], kind, index, new)
    for (id, kind, index), (old_part, new_part) in REPLACE.items():
        old = get(notes[id], kind, index)
        if old_part not in old:
            raise SystemExit(f'{id}: expected wording not found')
        new = old.replace(old_part, new_part, 1)
        record(id, kind, index, 'wording', old, new)
        put(notes[id], kind, index, new)
    for (id, kind, index), new in CONTENT.items():
        old = get(notes[id], kind, index)
        record(id, kind, index, 'content', old, new)
        put(notes[id], kind, index, new)
    for id, (status, points) in STATUS.items():
        befores.setdefault(id, copy.deepcopy(notes[id]))
        changes.setdefault(id, []).append(dict(field='review_status', change='status',
                                               before=notes[id]['review_status'], after=status))
        notes[id]['review_status'], notes[id]['unchecked_points'] = status, points
    records = []
    for id in sorted(befores):
        before, after = befores[id], notes[id]
        for field in PROTECTED:
            assert before[field] == after[field], (id, field)
        assert [(o['number'], o['is_answer']) for o in before['option_notes']] == \
               [(o['number'], o['is_answer']) for o in after['option_notes']]
        reasons = [o['reason'] for o in after['option_notes']]
        assert len(reasons) == len(set(reasons)), id
        records.append(dict(question_id=id, before=before, before_hash=digest(before), after_hash=digest(after),
                            changed_fields=sorted({k for k in before if before[k] != after[k]}),
                            changes=changes[id]))
    audit['round11_corrections'] = dict(
        checked_on=CHECKED_ON, count=len(records), rejected_spacing_keys=rejected,
        policy='공식 정답·보기 번호·is_answer·계산식·출처·문항 결속은 바꾸지 않았습니다. 띄어쓰기는 공백만 바꿨고, '
               '내용 수정은 이 스크립트에 적힌 문장만 바꿨습니다. answer_adjudication은 10차 기록을 보존하기 위해 바꾸지 않았습니다.',
        uncertainties=[dict(question_id='2022-07-018', note=UNCHECKED_0718,
                            recommendation='①의 해석에 따라 정답 후보가 둘일 수 있어 multiple_candidates 판정을 별도로 검토할 것'),
                       dict(question_id='2026-05-021', note=UNCHECKED_0521,
                            recommendation='④의 기본 모형 조건이 원문에 없어 공식 ③의 유일성 미확인')],
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Corrected {len(records)} explanations; rejected spacing rows {len(rejected)}')


if __name__ == '__main__':
    main(sys.argv[1])
