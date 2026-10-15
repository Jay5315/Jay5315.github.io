#!/usr/bin/env python3
"""Add a space where Hangul runs directly into an uppercase English word (audited).

Usage: python3 scripts/apply_spacing_round3.py

"원본PDF" -> "원본 PDF", "한국어K-IFRS" -> "한국어 K-IFRS", "변동을PL" -> "변동을 PL". The change is
whitespace-only and recorded in the ledger `spacing_round3` (before objects and hashes),
in the same way as `spacing_round2`.
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
HANGUL_THEN_LATIN = re.compile(r'([가-힣])(?=[A-Z])')


def respace(text):
    return HANGUL_THEN_LATIN.sub(r'\1 ', text)


def main():
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'spacing_round3' in audit:
        raise SystemExit('spacing_round3 already applied')
    records = []
    for n in data['items']:
        before = copy.deepcopy(n)
        for field, index in keys(n):
            old = get(n, field, index)
            new = respace(old)
            assert re.sub(r'\s', '', new) == re.sub(r'\s', '', old)
            if new != old:
                put(n, field, index, new)
        if n != before:
            records.append(dict(question_id=n['question_id'], before=before, before_hash=digest(before),
                                after_hash=digest(n),
                                changed_fields=sorted(k for k in TEXT_FIELDS if before[k] != n[k])))
    audit['spacing_round3'] = dict(
        checked_on=CHECKED_ON, count=len(records),
        policy='한글 바로 뒤에 영문 대문자 단어가 붙은 곳에만 공백을 넣었습니다(공백을 모두 지우면 원문과 같음). '
               '정답·보기 번호·is_answer·계산식·출처·문항 결속은 바꾸지 않았습니다.',
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Respaced {len(records)} explanations')


if __name__ == '__main__':
    main()
