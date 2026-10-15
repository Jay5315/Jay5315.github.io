#!/usr/bin/env python3
"""Mechanical punctuation and spacing clean-up in explanation texts (audited).

Usage: python3 scripts/apply_wording_round4.py

- runs of spaces become one space, except inside 「…」 quotes of original options, which keep
  the table spacing of the source;
- leading and trailing spaces are trimmed;
- a space is added after a comma between Hangul words ("차감,기말" -> "차감, 기말");
- a doubled period after Hangul becomes one ("명시합니다.." -> "명시합니다.").

The ledger `wording_round4` keeps before objects and hashes; the test re-applies `fix_note`
to each before object and requires the recorded result.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-15'
TEXT_FIELDS = ('title', 'summary', 'review_note', 'steps', 'option_notes', 'unchecked_points')
QUOTE = re.compile(r'(「[^」]*」)')


def fix_text(text):
    parts = QUOTE.split(text)
    for i in range(0, len(parts), 2):  # even parts are outside quotes
        s = re.sub(r'(?<=\S) {2,}(?=\S)', ' ', parts[i])
        s = re.sub(r'(?<=[가-힣]),(?=[가-힣])', ', ', s)
        s = re.sub(r'(?<=[가-힣])\.\.(?!\.)', '.', s)
        parts[i] = s
    return ''.join(parts).strip()


def fix_note(note, question=None):
    n = copy.deepcopy(note)
    for key in ('title', 'summary', 'review_note'):
        n[key] = fix_text(n[key])
    n['steps'] = [fix_text(s) for s in n['steps']]
    n['unchecked_points'] = [fix_text(s) for s in n['unchecked_points']]
    for o in n['option_notes']:
        o['reason'] = fix_text(o['reason'])
    return n


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def main():
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'wording_round4' in audit:
        raise SystemExit('wording_round4 already applied')
    records = []
    for i, note in enumerate(data['items']):
        after = fix_note(note)
        if after == note:
            continue
        records.append(dict(question_id=note['question_id'], before=note, before_hash=digest(note),
                            after_hash=digest(after),
                            changed_fields=sorted(k for k in TEXT_FIELDS if note[k] != after[k])))
        data['items'][i] = after
    audit['wording_round4'] = dict(
        checked_on=CHECKED_ON, count=len(records),
        policy='인용한 원문 보기(「…」) 밖의 이중 공백·앞뒤 공백을 정리하고, 한글 사이 쉼표 뒤에 공백을 넣고, 한글 뒤 마침표 중복(..)을 '
               '하나로 줄였습니다. 정답·보기 번호·is_answer·계산식·출처·문항 결속은 바꾸지 않았습니다.',
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Cleaned {len(records)} explanations')


if __name__ == '__main__':
    main()
