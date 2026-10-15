#!/usr/bin/env python3
"""Add a space where Hangul runs directly into a circled option number (audited).

Usage: python3 scripts/apply_spacing_round5.py

"이라고 한②가" -> "이라고 한 ②가", "정답은③입니다" -> "정답은 ③입니다". Statute references such as "제72조⑤" stay
joined (조·항·호·관·절·목 before the number). The change is
whitespace-only and recorded in the ledger `spacing_round5` (before objects and hashes),
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
HANGUL_THEN_CIRCLED = re.compile(r'([가-힣])(?<![조항호관절목])(?=[①②③④⑤])')


def respace(text):
    return HANGUL_THEN_CIRCLED.sub(r'\1 ', text)


def main():
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'spacing_round5' in audit:
        raise SystemExit('spacing_round5 already applied')
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
    audit['spacing_round5'] = dict(
        checked_on=CHECKED_ON, count=len(records),
        policy='한글 바로 뒤에 보기 번호(①~⑤)가 붙은 곳에만 공백을 넣었습니다(조문 번호 뒤 항 번호는 제외)(공백을 모두 지우면 원문과 같음). '
               '정답·보기 번호·is_answer·계산식·출처·문항 결속은 바꾸지 않았습니다.',
        notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Respaced {len(records)} explanations')


if __name__ == '__main__':
    main()
