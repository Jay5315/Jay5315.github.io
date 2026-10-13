"""Apply independently reviewed follow-ups while preserving every prior audit stage.

Inputs are approved, immutable proposal and independent-review JSON files. External
source bodies stay in private caches; only URLs, editions, hashes and read scopes
are recorded in the repository. The new stage is reversed first by the tests.
"""
import argparse
import ast
import copy
import hashlib
import json
import math
from pathlib import Path

from explanation_data import validate_explanations
from test_concepts import calc

R = Path(__file__).resolve().parents[1]
GROUP = 'round10_followups'
PROTECTED = {'question_id', 'question_fingerprint', 'answers', 'part_id',
             'tax_law_year', 'authorship', 'checks'}
ALLOWED_FIELDS = {'title', 'summary', 'steps', 'option_notes', 'sources',
                  'review_status', 'review_note', 'unchecked_points', 'checked_on'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def source_evidence(reads):
    if not reads:
        raise ValueError('Actual source reads are required')
    for read in reads:
        if (not all(read.get(k) for k in ('url', 'sha256', 'version', 'read_locator', 'private_path'))
                or read.get('actually_read') is not True):
            raise ValueError('Incomplete actual-source evidence')
        if not read['url'].startswith('https://'):
            raise ValueError('A public HTTPS source URL is required')
        path = Path(read['private_path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != read['sha256']:
            raise ValueError('Source cache changed after inspection')


def arithmetic(note, restricted=False):
    class StripUnaryPlus(ast.NodeTransformer):
        def visit_UnaryOp(self, node):
            node = self.generic_visit(node)
            return node.operand if isinstance(node.op, ast.UAdd) else node

    for check in note['checks']:
        expression = check['expr']
        if restricted:
            parsed = ast.parse(expression, mode='eval')
            allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                       ast.Add, ast.Sub, ast.Mult, ast.Div, ast.UAdd, ast.USub)
            if any(not isinstance(node, allowed) for node in ast.walk(parsed)):
                raise ValueError('New checks allow only numbers, +, -, *, / and parentheses')
            for node in ast.walk(parsed):
                if isinstance(node, ast.Constant) and (isinstance(node.value, bool)
                        or not isinstance(node.value, (int, float)) or not math.isfinite(node.value)):
                    raise ValueError('New checks require finite numeric constants')
            expression = ast.unparse(StripUnaryPlus().visit(parsed))
        expected = check['expected']
        if isinstance(expected, bool) or not isinstance(expected, (int, float)) or not math.isfinite(expected):
            raise ValueError('Numeric finite expected value is required')
        actual = calc(expression)
        if (isinstance(actual, bool) or not isinstance(actual, (int, float))
                or not math.isfinite(actual) or abs(actual - expected) > 1e-6):
            raise ValueError('Arithmetic check does not match')


def independent_review(row, kind, reviews):
    key = (kind, row['question_id'])
    review = reviews.get(key)
    if (not review or review['status'] != 'pass'
            or review['reviewer'] == row['author']
            or review['proposal_sha256'] != digest(row)
            or review['author'] != row['author']):
        raise ValueError(f'{key}: missing, stale or non-independent passing review')
    if kind in {'amendment', 'adjudication'}:
        if (review.get('before_hash', review.get('before_hash_checked')) != digest(row['before'])
                or review.get('after_hash', review.get('after_hash_checked')) != digest(row['after'])):
            raise ValueError(f'{key}: reviewed objects do not match the approved hashes')
    elif review.get('explanation_sha256', review.get('note_sha256')) != digest(row['note']):
        raise ValueError(f'{key}: reviewed explanation does not match the approved hash')
    options = review['four_option_logic']
    allowed_statuses = {'pass'}
    if kind == 'adjudication':
        # A targeted ruling or an accurately retained deferral does not certify
        # a complete explanation. Preserve the reviewer's explicit limitations.
        if review.get('adjudication_scope_checked') is not True or not review.get('limits'):
            raise ValueError(f'{key}: adjudication scope and limits must be checked')
        allowed_statuses.add('outside_adjudicated_scope')
        if row['after']['verdict'] == 'deferred':
            allowed_statuses.add('deferred_not_proven_wrong')
        if row['after']['verdict'] == 'official_supported' and any(
                o['status'] != 'pass' for o in options if o['number'] in row['after']['official_answers']):
            raise ValueError(f'{key}: the supported official answer must actually pass')
    if (len(options) != 4 or {o['number'] for o in options} != {1, 2, 3, 4}
            or any(o['status'] not in allowed_statuses or not o.get('finding') for o in options)
            or not all(review.get(k) for k in ('original_pdf_checked', 'original_image_checked',
                                             'subject_instructions_checked', 'official_answers_checked'))):
        raise ValueError(f'{key}: original conditions and all four options must pass')
    source_evidence(review['source_reads'])
    return copy.deepcopy(review)


def public_record(value):
    if isinstance(value, dict):
        # Immutable objects must retain their exact canonical hashes. Sanitize
        # only supplementary evidence, never the recorded before/after objects.
        return {k: copy.deepcopy(v) if k in {'before', 'after', 'note', 'previous_review'}
                else public_record(v) for k, v in value.items() if k != 'private_path'}
    if isinstance(value, list):
        return [public_record(v) for v in value]
    if isinstance(value, str) and value.startswith(('/tmp/', '/workspace/')):
        return Path(value).name
    return value


def apply(proposal_path, review_path, proposal_hash, review_hash):
    for path, expected in ((proposal_path, proposal_hash), (review_path, review_hash)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('An approved input changed')
    proposal, review_input = json.loads(proposal_path.read_text()), json.loads(review_path.read_text())
    dp, ap = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(dp.read_text()), json.loads(ap.read_text())
    if GROUP in audit:
        previous = audit[GROUP]
        if previous['proposal_sha256'] == proposal_hash and previous['review_sha256'] == review_hash:
            print('Already applied; no files changed')
            return
        raise ValueError('A different round-10 stage is already recorded')
    original_data, original_audit = copy.deepcopy(data), copy.deepcopy(audit)
    qs = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R / 'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R / 'data/taxonomy.json').read_text())}
    notes = {n['question_id']: n for n in data['items']}
    pending = {r['question_id']: r for r in audit['review']}
    records = review_input['items']
    reviews = {(r['target_kind'], r['question_id']): r for r in records}
    if len(reviews) != len(records):
        raise ValueError('Duplicate independent reviews')
    ledger = dict(schema_version=1, checked_on=proposal['checked_on'],
                  baseline_commit=proposal['baseline_commit'],
                  baseline_count=len(notes), baseline_ids=list(notes),
                  baseline_hashes={i: digest(n) for i, n in notes.items()},
                  baseline_source_hashes={k: digest(v) for k, v in data['sources'].items()},
                  proposal_sha256=proposal_hash, review_sha256=review_hash,
                  original_review=copy.deepcopy(audit['review']),
                  original_adjudication=copy.deepcopy(audit['answer_adjudication']),
                  new_source_refs=[], amendments=[], registrations=[],
                  review_updates=[], adjudication_amendments=[], adjudication_uncertainties=[],
                  inspection_records=public_record(proposal['inspection_records']),
                  actual_parallel_workers=proposal['actual_parallel_workers'], expert_reviewed=False)
    for ref, source in proposal['sources'].items():
        if ref in data['sources'] and data['sources'][ref] != source:
            raise ValueError('Existing source metadata is protected')
        if ref not in data['sources']:
            data['sources'][ref] = copy.deepcopy(source)
            ledger['new_source_refs'].append(ref)
    changed, registered = set(), set()
    for row in proposal['amendments']:
        id = row['question_id']
        if id in changed or id not in notes or notes[id] != row['before']:
            raise ValueError('Duplicate or stale explanation amendment')
        before, after = row['before'], row['after']
        fields = {k for k in before if before[k] != after[k]}
        if (set(before) != set(after) or not fields or fields != set(row['changed_fields'])
                or not fields <= ALLOWED_FIELDS or fields & PROTECTED
                or row['before_hash'] != digest(before) or row['after_hash'] != digest(after)):
            raise ValueError('Unapproved explanation field or hash change')
        for old, new in zip(before['option_notes'], after['option_notes']):
            if {k: v for k, v in old.items() if k != 'reason'} != {k: v for k, v in new.items() if k != 'reason'}:
                raise ValueError('Option number and answer flags are protected')
        if len(after['option_notes']) != 4:
            raise ValueError('Four original options must remain')
        if after['sources'][:len(before['sources'])] != before['sources']:
            raise ValueError('Previous source citations must remain; append new verified evidence')
        if 'option_notes' in fields and len({o['reason'] for o in after['option_notes']}) != 4:
            raise ValueError('Edited option explanations must be distinct')
        source_evidence(row['source_reads'])
        qa = independent_review(row, 'amendment', reviews)
        arithmetic(after)
        data['items'][ledger['baseline_ids'].index(id)] = copy.deepcopy(after)
        ledger['amendments'].append(public_record(dict(row, independent_review=qa,
                                                       proposal_record_sha256=digest(row))))
        if after['review_status'] == 'partial' and before['review_status'] != 'partial':
            # Keep newly found answer/condition uncertainty in the requested
            # adjudication area, separate from the earlier 51 primary rulings.
            ledger['adjudication_uncertainties'].append(public_record(dict(
                question_id=id, verdict='deferred', official_answers=qs[id]['answers'],
                official_answer_changed=False, basis='unconfirmed_original_condition',
                evidence=copy.deepcopy(after['unchecked_points']),
                explanation_after_hash=digest(after), checked_on=proposal['checked_on'],
                verification_scope='partial-warning accuracy; official-answer uniqueness remains unconfirmed',
                source_reads=row['source_reads'], author=row['author'], reviewer=qa['reviewer'],
                independent_review_proposal_sha256=qa['proposal_sha256'])))
        changed.add(id)
    for row in proposal['registrations']:
        id, note = row['question_id'], row['note']
        if id in registered or id in notes or id not in pending or row['previous_review'] != pending[id]:
            raise ValueError('Duplicate, existing or stale explanation registration')
        if not qs[id]['study_eligible'] or note['question_id'] != id:
            raise ValueError('A quarantined or unrelated question cannot be registered')
        if note['review_status'] != 'source_checked' or note['unchecked_points']:
            raise ValueError('Only verified new explanations may be registered')
        if len({o['reason'] for o in note['option_notes']}) != 4:
            raise ValueError('New option explanations must be distinct')
        source_evidence(row['source_reads'])
        qa = independent_review(row, 'registration', reviews)
        arithmetic(note, restricted=True)
        data['items'].append(copy.deepcopy(note))
        ledger['registrations'].append(public_record(dict(row, explanation_sha256=digest(note),
                                                         question_row_sha256=digest(qs[id]),
                                                         official_answers=qs[id]['answers'], independent_review=qa,
                                                         proposal_record_sha256=digest(row))))
        registered.add(id)
    update_ids = set()
    for row in proposal['review_updates']:
        id = row['question_id']
        if id in update_ids or id in registered or id not in pending or row['before'] != pending[id]:
            raise ValueError('Duplicate, resolved or stale pending review update')
        before, after = row['before'], row['after']
        if (row['before_hash'] != digest(before) or row['after_hash'] != digest(after)
                or after['question_id'] != id or not after['reason']
                or set(after) != set(before) or any(after[k] != before[k] for k in before if k != 'reason')):
            raise ValueError('Pending updates preserve category and audit history')
        source_evidence(row['source_reads'])
        pending[id] = copy.deepcopy(after)
        ledger['review_updates'].append(public_record(row))
        update_ids.add(id)
    audit['review'] = [pending[r['question_id']] for r in audit['review'] if r['question_id'] not in registered]
    verdicts = {v['question_id']: v for v in audit['answer_adjudication']['records']}
    adjudication_ids = set()
    for row in proposal['adjudication_amendments']:
        id = row['question_id']
        if id in adjudication_ids or row['before'] != verdicts[id]:
            raise ValueError('Duplicate or stale adjudication amendment')
        before, after = row['before'], row['after']
        if (row['before_hash'] != digest(before) or row['after_hash'] != digest(after)
                or after['question_id'] != id or after['official_answers'] != qs[id]['answers']
                or after['official_answer_changed'] is not False or not after['evidence']
                or after['previous_verdict'] != before['verdict'] or not after['corrected_on']):
            raise ValueError('Adjudication must preserve official answers and previous verdict')
        source_evidence(row['source_reads'])
        qa = independent_review(row, 'adjudication', reviews)
        verdicts[id].clear(); verdicts[id].update(copy.deepcopy(after))
        ledger['adjudication_amendments'].append(public_record(dict(row, independent_review=qa,
                                                                 proposal_record_sha256=digest(row))))
        adjudication_ids.add(id)
    from collections import Counter
    audit['answer_adjudication']['counts'] = dict(Counter(v['verdict'] for v in verdicts.values()))
    previous_uncertainties = audit['answer_adjudication'].get('followup_uncertainties', [])
    if {r['question_id'] for r in previous_uncertainties} & {r['question_id'] for r in ledger['adjudication_uncertainties']}:
        raise ValueError('Duplicate follow-up uncertainty')
    audit['answer_adjudication']['followup_uncertainties'] = (
        copy.deepcopy(previous_uncertainties) + copy.deepcopy(ledger['adjudication_uncertainties']))
    for row in ledger['registrations']:
        id = row['question_id']
        if (row['previous_review']['category'] == 'answer_suspected'
                and verdicts[id]['verdict'] not in {'official_supported', 'ambiguous_wording'}):
            raise ValueError('An unresolved official-answer conflict cannot be registered')
    validate_explanations(data, qs, entries, parts)
    for ref, source in original_data['sources'].items():
        if source != data['sources'][ref]:
            raise ValueError('Original sources were modified')
    expected_reviews = {(kind, row['question_id']) for kind, key in
                        [('amendment', 'amendments'), ('registration', 'registrations'),
                         ('adjudication', 'adjudication_amendments')] for row in proposal[key]}
    if expected_reviews != set(reviews):
        raise ValueError('Independent reviews must cover the approved proposals exactly')
    ledger.update(amended_count=len(changed), registered_count=len(registered),
                  current_registered_count=len(data['items']), remaining_review_count=len(audit['review']))
    audit[GROUP] = ledger
    # Older counters and frozen snapshots describe older stages; keep them intact.
    for key, value in original_audit.items():
        if key not in {'review', 'answer_adjudication'} and audit[key] != value:
            raise ValueError('Historical audit data changed')
    original_bytes = {p: p.read_bytes() for p in (dp, ap)}
    staged = {p: p.with_name(p.name + '.round10.tmp') for p in (dp, ap)}
    try:
        staged[dp].write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        staged[ap].write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
        for path, temporary in staged.items():
            temporary.replace(path)
    except Exception:
        for path, content in original_bytes.items():
            if path.read_bytes() != content:
                path.write_bytes(content)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
    print(f'Round 10: {len(changed)} amendments, {len(registered)} new explanations, {len(audit["review"])} pending')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('proposals', type=Path)
    parser.add_argument('reviews', type=Path)
    parser.add_argument('--proposal-sha256', required=True)
    parser.add_argument('--review-sha256', required=True)
    args = parser.parse_args()
    apply(args.proposals, args.reviews, args.proposal_sha256, args.review_sha256)
