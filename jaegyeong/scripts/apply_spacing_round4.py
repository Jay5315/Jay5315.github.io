#!/usr/bin/env python3
"""Rejoin units, suffixes and endings that spacing_round2 split off English words (audited).

Usage: python3 scripts/apply_spacing_round4.py

spacing_round2 put a space after an English abbreviation followed by any non-particle Korean word.
That was right for nouns ("EU 영문", "FIFO 당기") but wrong for counters, suffixes and endings:
"A160 개" -> "A160개", "A16 억원" -> "A16억원", "PDF9 쪽" -> "PDF9쪽", "kg 당" -> "kg당",
"NPV 법" -> "NPV법", "OCI 라고" -> "OCI라고", "OCI 일 때" -> "OCI일 때". This removes only those
spaces; the ledger `spacing_round4` keeps before objects and hashes.
"""
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_spacing_round2 import TEXT_FIELDS, digest, get, keys, put  # noqa: E402

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-15'
END = r'(?=$|[\s,.)·:;])'
REJOIN = [
    re.compile(r'(?<=[A-Za-z0-9]) (?=일 때)'),                                  # OCI 일 때, DOL4 일 때
    re.compile(r'(?<=[A-Za-z0-9]) (?=(?:라고|라면|이라면|지만|여서|라)' + END + ')'),  # OCI 라고
    re.compile(r'(?<=[A-Za-z]) (?=당\s)'),                                     # kg 당 공헌이익
    re.compile(r'(?<=[A-Z]{2}) (?=법(?:' + END + r'|입니다|의|은|는|을|이|과|와|으로|로))'),  # NPV 법, IRR 법의
]


# Counters after a label with digits (A160 개, A16 억원, A3 회, PDF9 쪽, KASB1001 호79); not when the
# Korean word only starts with that syllable (IFRS17 개정).
COUNTER = re.compile(r'(?<![A-Za-z0-9])([A-Za-z]+\d[\d.]*) (?=개(?![가-힣])|억|회(?![가-힣])|회의|쪽|호(?![가-힣]))')


def rejoin(text):
    text = COUNTER.sub(r'\1', text)
    for pattern in REJOIN:
        text = pattern.sub('', text)
    return text


def main():
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'spacing_round4' in audit:
        raise SystemExit('spacing_round4 already applied')
    records = []
    for n in data['items']:
        before = copy.deepcopy(n)
        for field, index in keys(n):
            old = get(n, field, index)
            new = rejoin(old)
            assert re.sub(r'\s', '', new) == re.sub(r'\s', '', old)
            if new != old:
                put(n, field, index, new)
        if n != before:
            records.append(dict(question_id=n['question_id'], before=before, before_hash=digest(before),
                                after_hash=digest(n),
                                changed_fields=sorted(k for k in TEXT_FIELDS if before[k] != n[k])))
    audit['spacing_round4'] = dict(
        checked_on=CHECKED_ON, count=len(records),
        policy='spacing_round2가 영문 약어 뒤에서 잘못 띄운 단위·접미사·어미(개·억·회·쪽·호·당·법·라고·지만·여서·일 때)만 다시 붙였습니다. '
               '공백만 지웠고 정답·보기 번호·is_answer·계산식·출처·문항 결속은 바꾸지 않았습니다.',
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Rejoined spacing in {len(records)} explanations')


if __name__ == '__main__':
    main()
