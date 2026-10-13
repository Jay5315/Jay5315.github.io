#!/usr/bin/env python3
"""Register explanations for held items resolved with cross-sitting evidence (round 13).

Usage: python3 scripts/register_round13_explanations.py AUTHORED.json REVIEWS.json

AUTHORED.json: drafts with decision "register" or "decline" (see round 13 brief).
REVIEWS.json: independent reviews {question_id, reviewer, status, four_option_logic[{number,status,note}], notes}.

Only drafts with decision "register" whose four options all passed an independent reviewer
(different from the author) are registered. The previous review row is kept in the ledger
`round13_registrations` and removed from audit['review']. Declined drafts are recorded with
their reasons and stay in the review queue. Official answers never change.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explanation_data import question_fingerprint, validate_explanations  # noqa: E402

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-13'
POLICY = ('다른 회차의 같은 진술에 대한 출제기관 판단과 검증된 해설을 출발점으로 삼되, 각 문항의 보류 사유를 '
          '실제로 읽은 원문으로 해소하고 작성자와 다른 검수자가 네 보기를 모두 통과시킨 경우에만 등록했습니다.')


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def main(authored_path, reviews_path, ledger='round13_registrations', policy=POLICY):
    read = lambda name: json.loads((R / 'data' / (name + '.json')).read_text())
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if ledger in audit:
        raise SystemExit(f'{ledger} already applied')
    qs = {q['id']: q for q in read('questions')}
    reviews = {r['question_id']: r for r in json.loads(Path(reviews_path).read_text())}
    pending = {r['question_id']: r for r in audit['review']}
    existing = {n['question_id'] for n in data['items']}
    records, declined, skipped, new_refs = [], [], [], []
    for d in json.loads(Path(authored_path).read_text()):
        id = d['question_id']
        if d['decision'] != 'register':
            declined.append(dict(question_id=id, author=d['author'], reason=d['decline_reason']))
            continue
        q, review = qs[id], reviews.get(id)
        if (id in existing or id not in pending or not q['study_eligible'] or not review
                or review['status'] != 'pass' or review['reviewer'] == d['author']
                or sorted(x['number'] for x in review['four_option_logic']) != [1, 2, 3, 4]
                or any(x['status'] != 'pass' for x in review['four_option_logic'])):
            skipped.append(id)
            continue
        for ref, source in d.get('new_sources', {}).items():
            if ref in data['sources']:
                if data['sources'][ref] != source:
                    raise SystemExit(f'{ref}: conflicting source metadata')
                continue
            data['sources'][ref] = source
            new_refs.append(ref)
        reasons = {o['number']: o['reason'] for o in d['option_notes']}
        note = dict(question_id=id, question_fingerprint=question_fingerprint(q), answers=q['answers'],
                    part_id=q['classification']['primary_part_id'], title=d['title'], summary=d['summary'],
                    steps=d['steps'],
                    option_notes=[dict(number=n, is_answer=n in q['answers'], reason=reasons[n]) for n in (1, 2, 3, 4)],
                    checks=d['checks'], sources=d['sources'], tax_law_year=q['tax_law_year'],
                    review_status=d['review_status'], review_note=d['review_note'],
                    unchecked_points=d['unchecked_points'],
                    authorship='AI 작성 학습용 해설 · 삼일회계법인의 공식 해설 아님', checked_on=CHECKED_ON)
        data['items'].append(note)
        records.append(dict(question_id=id, previous_review=pending[id], explanation_sha256=digest(note),
                            question_row_sha256=digest(q), official_answers=q['answers'], author=d['author'],
                            blocker_resolution=d['blocker_resolution'], source_reads=d['source_reads'],
                            independent_review=review))
    registered = {r['question_id'] for r in records}
    audit['review'] = [r for r in audit['review'] if r['question_id'] not in registered]
    audit[ledger] = dict(
        checked_on=CHECKED_ON, registered_count=len(records), declined=declined, skipped_ids=skipped,
        new_source_refs=new_refs, policy=policy, items=records)
    validate_explanations(data, qs, {e['id'] for e in read('entries')}, {p['id'] for p in read('taxonomy')})
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Registered {len(records)}; declined {len(declined)}; skipped {skipped}; new sources {len(new_refs)}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
