#!/usr/bin/env python3
"""Fix particle errors and contaminated quotes in explanation texts (audited).

Usage: python3 scripts/apply_wording_round3.py

1. Particles: a fixed list of word-final particle errors found by checking the final
   consonant of the preceding syllable (e.g. "현재가치을" -> "현재가치를", "증가은" -> "증가는",
   "12,000개은" -> "12,000개는", "휴대폰로" -> "휴대폰으로"). Verb forms such as 짝지은·뒤이은·모은
   were checked and are not particles, so they are not in the list.
2. Common instructions: in some review notes the text quoted after "공통 문구:" mixed another
   question's options or a cut-off sentence ("…의미하지는 않 본 시험은") with the instructions.
   It is replaced by the question's own subject_instructions, which the quote contained.

Answers, option numbers, is_answer flags, checks, sources and question binding never change.
The ledger `wording_round3` keeps each changed explanation's before object and hashes; the test
re-applies `fix_text` to every before object and requires the recorded after object.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-15'
TEXT_FIELDS = ('title', 'summary', 'review_note', 'steps', 'option_notes', 'unchecked_points')
END = r'(?=[\s,.)·:;!?]|$)'
PARTICLE_FIXES = [  # (regex, replacement); each matches only at the end of a word
    (r'현재가치을' + END, '현재가치를'), (r'보존를' + END, '보존을'), (r'증가은' + END, '증가는'),
    (r'분배을' + END, '분배를'), (r'감소은' + END, '감소는'), (r'단위은' + END, '단위는'),
    (r'냉장고을' + END, '냉장고를'), (r'(\d원)를' + END, r'\1을'), (r'필요경비은' + END, '필요경비는'),
    (r'차이을' + END, '차이를'), (r'금지을' + END, '금지를'), (r'(\d개)은' + END, r'\1는'),
    (r'(?<![가-힣])개은' + END, '개는'), (r'가공완성도은' + END, '가공완성도는'), (r'라면와' + END, '라면과'),
    (r'휴대폰로' + END, '휴대폰으로'), (r'군함로' + END, '군함으로'), (r'원유입로' + END, '원유입으로'),
]


def norm(s):
    return re.sub(r'\s', '', s)


def fix_common_quote(note, instructions):
    m = re.search(r'(공통 ?문구: ?)(.*)$', note, re.S)
    if not m or norm(m.group(2)).startswith(norm(instructions)[:20]):
        return note
    if norm(instructions) not in norm(m.group(2)):
        raise SystemExit(f'quoted common text does not contain the instructions: {m.group(2)[:60]}')
    # The quote contains the instructions mixed with other text; keep only the instructions.
    text = re.sub(r'\s*\n\s*', ' ', instructions.strip())
    return note[:m.start(2)] + re.sub(r'(\d) (월|일)', r'\1\2', text)


def fix_text(text):
    for pattern, repl in PARTICLE_FIXES:
        text = re.sub(pattern, repl, text)
    return text


def fix_note(note, question):
    n = copy.deepcopy(note)
    n['title'], n['summary'] = fix_text(n['title']), fix_text(n['summary'])
    n['review_note'] = fix_common_quote(fix_text(n['review_note']), question['subject_instructions'])
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
    if 'wording_round3' in audit:
        raise SystemExit('wording_round3 already applied')
    qs = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    records = []
    for i, note in enumerate(data['items']):
        after = fix_note(note, qs[note['question_id']])
        if after == note:
            continue
        assert [(o['number'], o['is_answer']) for o in note['option_notes']] == \
               [(o['number'], o['is_answer']) for o in after['option_notes']]
        records.append(dict(question_id=note['question_id'], before=note, before_hash=digest(note),
                            after_hash=digest(after),
                            changed_fields=sorted(k for k in TEXT_FIELDS if note[k] != after[k])))
        data['items'][i] = after
    audit['wording_round3'] = dict(
        checked_on=CHECKED_ON, count=len(records),
        policy='조사 오류는 앞 음절의 받침으로 찾은 뒤 동사 활용형(짝지은·뒤이은·모은 등)을 빼고 고정 목록으로만 고쳤고, '
               '"공통 문구:" 뒤에 다른 문항 보기나 잘린 문장이 섞인 검토 의견은 해당 문항의 실제 공통 유의사항으로 바꿨습니다. '
               '정답·보기 번호·is_answer·계산식·출처·문항 결속은 바꾸지 않았습니다.',
        particle_fixes=[[p, r] for p, r in PARTICLE_FIXES], notes=records)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Fixed wording in {len(records)} explanations')


if __name__ == '__main__':
    main()
