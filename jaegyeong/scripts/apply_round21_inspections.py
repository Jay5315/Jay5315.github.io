"""Record independent reviews of all 47 held items without rewriting originals.

Only approved adjudication resolutions and evidence-only corrections may affect
learner review notes. Question data, official keys, completed explanations,
concepts and every original adjudication record remain immutable.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from apply_round10_followups import arithmetic, digest, public_record
from apply_round20_followups import four_options_pass, unique_rows, verified_review

R = Path(__file__).resolve().parents[1]
GROUP = 'round21_inspections'
VERDICTS = {'official_conflict', 'multiple_candidates', 'ambiguous_wording',
            'holiday_nominal_deadline', 'official_supported', 'deferred'}


def review_notes(log):
    records = {r['question_id']: copy.deepcopy(r)
               for r in log['records'] + log.get('explained_item_records', [])}
    for resolution in log.get('resolutions', []):
        records[resolution['question_id']].update(
            verdict=resolution['verdict'], evidence=resolution['evidence'])
    return records


def diagnostic_arithmetic(row):
    """Check research diagnostics without altering the immutable authored rows."""
    checks = []
    for check in row.get('checks', []):
        computed = check.get('computed', check['expected'])
        if (isinstance(computed, bool) or not isinstance(computed, (int, float))
                or not math.isfinite(computed)
                or not math.isclose(computed, check['expected'], rel_tol=0, abs_tol=1e-6)):
            raise ValueError('Recorded diagnostic result does not match expectation')
        checks.append(dict(expr=check.get('expr', check.get('expression')),
                           expected=check['expected']))
    arithmetic({'checks': checks}, restricted=True)


def original_evidence(question, row):
    originals = row['originals']
    for field, source in (('image', 'image'), ('original_pdf', 'source_pdf'), ('answer_pdf', 'answer_pdf')):
        path = R / question[source]
        if (Path(originals[field]).resolve() != path.resolve()
                or originals[field + '_sha256'] != hashlib.sha256(path.read_bytes()).hexdigest()):
            raise ValueError(f'{question["id"]}: original document binding changed')
    if (originals['question_page'] != question['page']
            or originals.get('subject_instructions_checked') is not True
            or not originals.get('official_answers_read') or not originals.get('findings')):
        raise ValueError(f'{question["id"]}: incomplete original/key/instruction inspection')


def inspect(proposal_path, review_path, proposal_sha256, review_sha256):
    for path, expected in ((proposal_path, proposal_sha256), (review_path, review_sha256)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Approved input file changed')
    proposal = json.loads(proposal_path.read_text())
    reviews = json.loads(review_path.read_text())
    audit_path = R / 'reports/explanation-expansion.json'
    original = audit_path.read_bytes()
    audit = json.loads(original)
    if GROUP in audit:
        if (audit[GROUP]['proposal_sha256'], audit[GROUP]['review_sha256']) == (proposal_sha256, review_sha256):
            print('Already applied; no changes')
            return
        raise ValueError('Another round-21 input already recorded')
    if hashlib.sha256(original).hexdigest() != proposal['baseline_audit_sha256']:
        raise ValueError('Baseline audit changed after drafting')
    baseline = proposal['baseline']
    for name, expected in baseline['immutable_files'].items():
        if hashlib.sha256((R / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'{name}: protected original changed')
    for name, expected in (
            ('data/explanations.json', baseline['explanations_file_sha256']),
            ('data/concept-notes.json', baseline['concepts_file_sha256']),
            ('reports/concept-expansion.json', baseline['concept_audit_file_sha256'])):
        if hashlib.sha256((R / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'{name}: completed material changed')
    qs = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    pending = {r['question_id']: r for r in audit['review']}
    before_adjudication = copy.deepcopy(audit['answer_adjudication'])
    effective = review_notes(before_adjudication)
    prior_resolved = {r['question_id'] for r in before_adjudication.get('resolutions', [])}
    ledger = dict(checked_on=proposal['checked_on'], baseline_commit=baseline['commit'],
                  proposal_sha256=proposal_sha256, review_sha256=review_sha256,
                  baseline=copy.deepcopy(baseline), original_review=copy.deepcopy(audit['review']),
                  before_adjudication=before_adjudication, inspections=[], resolutions=[],
                  evidence_amendments=[], actual_workers=proposal['actual_workers'],
                  official_site_access=copy.deepcopy(proposal['official_site_access']),
                  research_sources=copy.deepcopy(proposal['research_sources']), expert_reviewed=False)
    covered = set()
    for category in ('parse_problem', 'answer_suspected', 'source_unverified', 'calculation_unresolved'):
        rows = unique_rows(proposal['inspections'][category], 'question_id')
        qa = unique_rows(reviews[category], 'question_id')
        expected = {id for id, r in pending.items() if r['category'] == category}
        if set(rows) != expected or set(qa) != expected:
            raise ValueError(f'{category}: missing/extra author or reviewer records')
        for id, row in rows.items():
            if id in covered:
                raise ValueError('Assignments overlap')
            covered.add(id)
            review = verified_review(row, qa[id], id)
            four_options_pass(review, id)
            original_evidence(qs[id], row)
            original_evidence(qs[id], review)
            if row['previous_review'] != pending[id] or row['question_row_sha256'] != digest(qs[id]):
                raise ValueError(f'{id}: original binding changed')
            diagnostic_arithmetic(row)
            ledger['inspections'].append(public_record(dict(
                row, category=category, proposal_record_sha256=digest(row), independent_review=review)))
            if category != 'answer_suspected':
                if row['decision'] != 'decline':
                    raise ValueError(f'{id}: unresolved-source inspection cannot silently register or rewrite a question')
                continue
            current = effective[id]
            proposed = row['proposed_verdict']
            if row['current_verdict'] != current['verdict'] or proposed not in VERDICTS:
                raise ValueError(f'{id}: stale/unknown adjudication')
            if row['decision'] == 'resolve':
                if proposed == current['verdict'] or id in prior_resolved:
                    raise ValueError(f'{id}: duplicate/unchanged resolution')
                if not row.get('new_evidence') or not row.get('proposed_evidence'):
                    raise ValueError(f'{id}: resolution needs actual supporting evidence')
                resolution = public_record(dict(
                    question_id=id, previous_verdict=current['verdict'], verdict=proposed,
                    official_answers=qs[id]['answers'], official_answer_changed=False,
                    evidence=row['proposed_evidence'], basis=current['basis'], checked_on=proposal['checked_on'],
                    previous_evidence=current['evidence'], new_evidence=row['new_evidence'],
                    source_reads=row['source_reads'], author=row['author'], independent_review=review,
                    proposal_record_sha256=digest(row), question_row_sha256=digest(qs[id])))
                audit['answer_adjudication'].setdefault('resolutions', []).append(resolution)
                ledger['resolutions'].append(copy.deepcopy(resolution))
            elif row['decision'] in {'uphold', 'refine'}:
                if proposed != current['verdict']:
                    raise ValueError(f'{id}: unchanged decision changes verdict')
                if row.get('evidence_update_required'):
                    text = row.get('proposed_evidence')
                    if not text or text == current['evidence'] or not row.get('evidence_update_reason') or id in prior_resolved:
                        raise ValueError(f'{id}: empty/stale evidence amendment')
                    ledger['evidence_amendments'].append(public_record(dict(
                        question_id=id, verdict=current['verdict'], before_evidence=current['evidence'],
                        after_evidence=text, before_hash=digest(current['evidence']), after_hash=digest(text),
                        reason=row['evidence_update_reason'], author=row['author'], source_reads=row['source_reads'],
                        independent_review=review, official_answers=qs[id]['answers'],
                        official_answer_changed=False, proposal_record_sha256=digest(row))))
            else:
                raise ValueError(f'{id}: unknown adjudication decision')
    if covered != set(pending) or len(covered) != 47:
        raise ValueError('Every initially held item needs an independent review')
    ledger.update(inspected_count=len(covered), registered_count=0, original_corrections=0,
                  resolution_count=len(ledger['resolutions']), evidence_amendment_count=len(ledger['evidence_amendments']))
    audit[GROUP] = ledger
    staged = audit_path.with_name(audit_path.name + '.round21.tmp')
    try:
        staged.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
        staged.replace(audit_path)
    finally:
        staged.unlink(missing_ok=True)
    print(f'Round21: inspected47, resolutions{ledger["resolution_count"]}, evidence corrections{ledger["evidence_amendment_count"]}, original/answer/explanation changes0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('proposal', type=Path)
    parser.add_argument('reviews', type=Path)
    parser.add_argument('--proposal-sha256', required=True)
    parser.add_argument('--review-sha256', required=True)
    args = parser.parse_args()
    inspect(args.proposal, args.reviews, args.proposal_sha256, args.review_sha256)
