#!/usr/bin/env python3
"""Apply whitespace-only spacing fixes to explanation text with an audit record.

Usage: python3 scripts/apply_spacing_amendments.py SPACED.json
SPACED.json is a list of {"key": "<question_id>|<field>|<index or option number>", "text": ...}.
A replacement is applied only when removing all whitespace gives exactly the original text,
so wording, numbers, answers and calculations cannot change. Every amended explanation is
recorded in reports/explanation-expansion.json under `spacing_amendments` with its
before object and before/after hashes.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-13'
FIELDS = {'title': 'title', 'summary': 'summary', 'steps': 'steps', 'option': 'option_notes', 'unchecked': 'unchecked_points'}


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def same_text(a, b):
    return re.sub(r'\s', '', a) == re.sub(r'\s', '', b)


def main(path):
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'spacing_amendments' in audit:
        raise SystemExit('spacing_amendments already applied')
    notes = {n['question_id']: n for n in data['items']}
    befores, changed, rejected = {}, {}, []
    for row in json.loads(Path(path).read_text()):
        id, kind, index = row['key'].split('|')
        new = row['text']
        n = notes[id]
        if kind in ('title', 'summary'):
            old = n[kind]
        elif kind == 'option':
            old = next(o for o in n['option_notes'] if o['number'] == int(index))['reason']
        else:
            old = n[FIELDS[kind]][int(index)]
        if not same_text(old, new) or '  ' in new or new != new.strip():
            rejected.append(row['key'])
            continue
        if old == new:
            continue
        befores.setdefault(id, copy.deepcopy(n))
        changed.setdefault(id, set()).add(FIELDS[kind])
        if kind in ('title', 'summary'):
            n[kind] = new
        elif kind == 'option':
            next(o for o in n['option_notes'] if o['number'] == int(index))['reason'] = new
        else:
            n[FIELDS[kind]][int(index)] = new
    records = [dict(question_id=id, changed_fields=sorted(changed[id]), before=befores[id],
                    before_hash=digest(befores[id]), after_hash=digest(notes[id]))
               for id in sorted(befores)]
    audit['spacing_amendments'] = dict(
        checked_on=CHECKED_ON, count=len(records), rejected_keys=rejected,
        rule='공백만 추가·삭제했습니다. 공백을 모두 지운 문자열이 원문과 다르면 반영하지 않았습니다.',
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Respaced {len(records)} explanations; rejected {len(rejected)} rows')


if __name__ == '__main__':
    main(sys.argv[1])
