#!/usr/bin/env python3
"""Fix spacing and a particle error in concept notes (audited, separate ledger).

Usage: python3 scripts/apply_concept_wording.py

Applies to learner-facing prose only: title, summary, key_points, pitfalls, review_note,
unchecked_points, formula conditions, example title/setup/steps and the applicability note.
Formula expressions and variables, year tables, tags and sources are never touched.
Fixes: the particle error "구별를" -> "구별을", a space after an English abbreviation followed by a
non-particle Korean word, a space where Hangul runs into an uppercase English word, and a space
after a sentence-ending period glued to the next sentence, without splitting counters, suffixes
or endings off English words (same rules as spacing_round2/3/4).

The ledger is reports/concept-wording.json (before objects and hashes); concept-expansion.json is
not edited so earlier concept audits stay exactly as recorded. Tests re-apply fix_note to each
before object and require the current note.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_spacing_round2 import mechanical  # noqa: E402
from apply_spacing_round3 import respace  # noqa: E402
from apply_spacing_round4 import rejoin  # noqa: E402

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-15'
PARTICLE_FIXES = [(r'구별를(?=[\s,.)·:;]|$)', '구별을')]


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def fix_text(text):
    for pattern, repl in PARTICLE_FIXES:
        text = re.sub(pattern, repl, text)
    return rejoin(respace(mechanical(text)))


def fix_note(note):
    n = copy.deepcopy(note)
    for key in ('title', 'summary', 'review_note'):
        n[key] = fix_text(n[key])
    for key in ('key_points', 'pitfalls', 'unchecked_points'):
        n[key] = [fix_text(x) for x in n.get(key, [])] if key in n else n.get(key)
        if n[key] is None:
            del n[key]
    for f in n['formulas']:
        if f.get('conditions'):
            f['conditions'] = fix_text(f['conditions'])
    for e in n['examples']:
        for key in ('title', 'setup'):
            if isinstance(e.get(key), str):
                e[key] = fix_text(e[key])
        if isinstance(e.get('steps'), list):
            e['steps'] = [fix_text(s) if isinstance(s, str) else s for s in e['steps']]
    if isinstance(n.get('applicability'), dict) and isinstance(n['applicability'].get('year_note'), str):
        n['applicability']['year_note'] = fix_text(n['applicability']['year_note'])
    return n


def main():
    path, ledger = R / 'data/concept-notes.json', R / 'reports/concept-wording.json'
    if ledger.exists():
        raise SystemExit('concept wording already applied')
    data = json.loads(path.read_text())
    records = []
    for i, note in enumerate(data['notes']):
        after = fix_note(note)
        if after != note:
            records.append(dict(note_id=note['id'], before=note, before_hash=digest(note), after_hash=digest(after),
                                changed_fields=sorted(k for k in after if after[k] != note[k])))
            data['notes'][i] = after
    ledger.write_text(json.dumps(dict(
        checked_on=CHECKED_ON, count=len(records),
        policy='개념 노트의 설명 문장만 고쳤습니다. 조사 오류 "구별를"→"구별을" 1곳과, 영문 약어 뒤 한글 단어(조사 제외)·한글 '
               '뒤 영문 단어·문장 끝 마침표 뒤의 띄어쓰기입니다. 공식·변수·연도표·태그·출처는 바꾸지 않았습니다.',
        particle_fixes=[list(x) for x in PARTICLE_FIXES], notes=records), ensure_ascii=False, indent=2) + '\n')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f'Fixed {len(records)} concept notes')


if __name__ == '__main__':
    main()
