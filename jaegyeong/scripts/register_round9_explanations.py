#!/usr/bin/env python3
"""Register explanations for answer-suspected items whose official answer was upheld.

Usage: python3 scripts/register_round9_explanations.py AUTHORED.json REVIEWS.json

AUTHORED.json: list of drafts {question_id, title, summary, steps, option_notes[{number, reason}],
checks, sources, new_sources, review_status, unchecked_points, review_note, source_reads, author}.
REVIEWS.json: list of independent reviews {question_id, reviewer, status: pass|issue,
four_option_logic[{number, status, note}], sources_checked[...], notes}.

Only drafts whose independent review passed and whose adjudication upheld the official
answer are registered. Each registered item leaves audit['review'] but its previous row is
kept in audit['round9_registrations'] together with the explanation hash and the review.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explanation_data import question_fingerprint, validate_explanations  # noqa: E402

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-13'
UPHELD = {'official_supported', 'ambiguous_wording'}


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def main(authored_path, reviews_path):
    read = lambda name: json.loads((R / 'data' / (name + '.json')).read_text())
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'round9_registrations' in audit:
        raise SystemExit('round9_registrations already applied')
    qs = {q['id']: q for q in read('questions')}
    verdicts = {a['question_id']: a for a in audit['answer_adjudication']['records']}
    reviews = {r['question_id']: r for r in json.loads(Path(reviews_path).read_text())}
    pending = {r['question_id']: r for r in audit['review']}
    existing = {n['question_id'] for n in data['items']}
    records, new_refs, skipped = [], [], []
    for d in json.loads(Path(authored_path).read_text()):
        id, q = d['question_id'], qs[d['question_id']]
        review = reviews.get(id)
        if (id in existing or id not in pending or verdicts[id]['verdict'] not in UPHELD
                or not review or review['status'] != 'pass' or review['reviewer'] == d['author']
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
        records.append(dict(question_id=id, previous_review=pending[id], adjudication_verdict=verdicts[id]['verdict'],
                            explanation_sha256=digest(note), question_row_sha256=digest(q),
                            official_answers=q['answers'], author=d['author'], reviewer=review['reviewer'],
                            source_reads=d['source_reads'], independent_review=review))
    registered = {r['question_id'] for r in records}
    audit['review'] = [r for r in audit['review'] if r['question_id'] not in registered]
    audit['round9_registrations'] = dict(
        checked_on=CHECKED_ON, registered_count=len(records), skipped_ids=skipped, new_source_refs=new_refs,
        policy='공식 정답이 유지된 정답 의심 항목만, 작성자와 다른 검수자가 네 보기 모두 통과로 판정한 경우 등록',
        items=records)
    validate_explanations(data, qs, {e['id'] for e in read('entries')}, {p['id'] for p in read('taxonomy')})
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Registered {len(records)} explanations; skipped {skipped}; new sources {len(new_refs)}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
