#!/usr/bin/env python3
"""Fix Korean word spacing in explanation texts with an auditable before/after ledger.

Usage: python3 scripts/apply_spacing_round2.py SPACED.json [SPACED.json ...]

SPACED.json: [{key: "question_id|field|index", text}] whitespace-only rewrites of long runs
of Hangul written without spaces (prepared by reviewers). Afterwards two mechanical rules run
on every learner-facing text: a space after an English abbreviation that is followed by a
Korean word other than a particle ("EU영문미러" -> "EU 영문미러"; "IFRS의" stays), and a space
after a sentence-ending period glued to the next sentence.

Every change must be whitespace-only (removing all whitespace gives the original string).
Answers, option numbers, is_answer flags, checks, sources and question binding never change.
The ledger `spacing_round2` keeps each changed explanation's before object and hashes.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-15'
TEXT_FIELDS = ('title', 'summary', 'review_note', 'steps', 'option_notes', 'unchecked_points')
PARTICLES = ('의', '는', '은', '이', '가', '을', '를', '에', '와', '과', '로', '으로', '도', '만', '에서', '부터', '까지',
             '이며', '이고', '이므로', '입니다', '이다', '인', '라는', '란', '처럼', '보다', '에게', '이나', '나', '이라', '상')
LATIN = re.compile(r'(?<![0-9A-Za-z_./:-])([A-Za-z][A-Za-z-]*[A-Za-z0-9]*)([가-힣]+)')
GLUE = re.compile(r'([가-힣]\.)(?=[가-힣①②③④])')


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def mechanical(text):
    def latin(m):
        word, rest = m.group(1), m.group(2)
        if len(word) == 1 or rest.startswith(PARTICLES):  # A사·X1년 style labels and particles stay joined
            return m.group(0)
        return f'{word} {rest}'
    return GLUE.sub(r'\1 ', LATIN.sub(latin, text))


def get(n, field, index):
    if field in ('title', 'summary', 'review_note'):
        return n[field]
    if field == 'option':
        return next(o for o in n['option_notes'] if o['number'] == int(index))['reason']
    return n[{'steps': 'steps', 'unchecked': 'unchecked_points'}[field]][int(index)]


def put(n, field, index, value):
    if field in ('title', 'summary', 'review_note'):
        n[field] = value
    elif field == 'option':
        next(o for o in n['option_notes'] if o['number'] == int(index))['reason'] = value
    else:
        n[{'steps': 'steps', 'unchecked': 'unchecked_points'}[field]][int(index)] = value


def keys(n):
    yield from (('title', None), ('summary', None), ('review_note', None))
    yield from (('steps', i) for i in range(len(n['steps'])))
    yield from (('option', o['number']) for o in n['option_notes'])
    yield from (('unchecked', i) for i in range(len(n['unchecked_points'])))


def main(paths):
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'spacing_round2' in audit:
        raise SystemExit('spacing_round2 already applied')
    notes = {n['question_id']: n for n in data['items']}
    befores, rejected = {}, []
    reviewed = {}
    for path in paths:
        for row in json.loads(Path(path).read_text()):
            reviewed[row['key']] = row['text']
    for id, n in notes.items():
        for field, index in keys(n):
            old = get(n, field, index)
            new = reviewed.get(f'{id}|{field}|{index}', old)
            if re.sub(r'\s', '', new) != re.sub(r'\s', '', old) or '\n' in new and new.count('\n') != old.count('\n'):
                rejected.append(f'{id}|{field}|{index}')
                new = old
            new = mechanical(new)
            if re.sub(r'\s', '', new) != re.sub(r'\s', '', old):
                raise SystemExit(f'{id}|{field}|{index}: non-whitespace change')
            if new != old:
                befores.setdefault(id, copy.deepcopy(n))
                put(n, field, index, new)
    records = []
    for id in sorted(befores):
        before, after = befores[id], notes[id]
        for k in after:
            if k not in TEXT_FIELDS and k != 'option_notes':
                assert before[k] == after[k], (id, k)
        assert [(o['number'], o['is_answer']) for o in before['option_notes']] == \
               [(o['number'], o['is_answer']) for o in after['option_notes']], id
        records.append(dict(question_id=id, before=before, before_hash=digest(before), after_hash=digest(after),
                            changed_fields=sorted(k for k in TEXT_FIELDS if before[k] != after[k])))
    audit['spacing_round2'] = dict(
        checked_on=CHECKED_ON, count=len(records), rejected_keys=rejected,
        policy='공백만 바꿨습니다(공백을 모두 지우면 원문과 같음). 공백 없이 길게 붙은 한글 문장은 검토자가 띄어 쓴 문장을, '
               '영문 약어 뒤의 한글 단어(조사 제외)와 문장 끝 마침표 뒤에는 기계적으로 공백을 넣었습니다. '
               '정답·보기 번호·is_answer·계산식·출처·문항 결속은 바꾸지 않았습니다.',
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Respaced {len(records)} explanations; rejected reviewer rows {len(rejected)}')


if __name__ == '__main__':
    main(sys.argv[1:])
