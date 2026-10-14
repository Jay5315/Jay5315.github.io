"""Append independently approved explanations without rewriting earlier study data."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from apply_round10_followups import digest, public_record, arithmetic
from apply_round20_followups import authored_note, unique_rows
from apply_round22_followups import approve, check_originals
from explanation_data import validate_explanations

R = Path(__file__).resolve().parents[1]
GROUP = 'round24_followups'


def apply(proposal_path, review_path, proposal_sha256, review_sha256):
    for path, expected in ((proposal_path, proposal_sha256), (review_path, review_sha256)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Approved input file changed')
    proposal, reviews = json.loads(proposal_path.read_text()), json.loads(review_path.read_text())
    dp, ap = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    original = {path: path.read_bytes() for path in (dp, ap)}
    data, audit = (json.loads(original[path]) for path in (dp, ap))
    if GROUP in audit:
        recorded = audit[GROUP]
        if (recorded['proposal_sha256'], recorded['review_sha256']) == (proposal_sha256, review_sha256):
            print('Already applied; no changes')
            return
        raise ValueError('Another round-24 input is already recorded')
    baseline = proposal['baseline']
    if hashlib.sha256(original[ap]).hexdigest() != baseline['audit_file_sha256']:
        raise ValueError('The audited baseline changed after authorship')
    if hashlib.sha256(original[dp]).hexdigest() != baseline['explanations_file_sha256']:
        raise ValueError('Completed explanations changed after authorship')
    protected = dict(baseline['immutable_files'])
    protected.update({'data/concept-notes.json': baseline['concepts_file_sha256'],
                      'reports/concept-expansion.json': baseline['concept_audit_file_sha256']})
    for name, expected in protected.items():
        if hashlib.sha256((R / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'{name}: protected original changed')
    qs = {q['id']: q for q in json.loads((R / 'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R / 'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R / 'data/taxonomy.json').read_text())}
    pending = {r['question_id']: r for r in audit['review']}
    previous = {r['question_id']: r for r in audit['round23_followups']['inspections']}
    rows = unique_rows(proposal['inspections'], 'question_id')
    qa = unique_rows(reviews, 'question_id')
    if set(rows) != set(pending) or set(qa) != set(rows):
        raise ValueError('Every starting held item needs one exact author and independent reviewer')
    if proposal['previous_inspection_hashes'] != {id: digest(previous[id]) for id in rows}:
        raise ValueError('Reused round-23 inspections do not match the protected originals')
    ledger = dict(checked_on=proposal['checked_on'], baseline=copy.deepcopy(baseline),
                  proposal_sha256=proposal_sha256, review_sha256=review_sha256,
                  original_review=copy.deepcopy(audit['review']),
                  previous_inspection_hashes=copy.deepcopy(proposal['previous_inspection_hashes']),
                  actual_workers=proposal['actual_workers'], max_concurrent_subagents=proposal['max_concurrent_subagents'],
                  worker_sessions=proposal['worker_sessions'], inspections=[], registrations=[], new_source_refs=[],
                  expert_reviewed=False)
    existing = {n['question_id']: n for n in data['items']}
    original_sources = copy.deepcopy(data['sources'])
    used_new_refs = set()
    for id, row in rows.items():
        if row['previous_review'] != pending[id] or row['question_row_sha256'] != digest(qs[id]):
            raise ValueError(f'{id}: original question/review binding changed')
        if row['decision'] not in {'decline', 'register'}:
            raise ValueError(f'{id}: unsupported decision; adjudication requires a separate approved resolution')
        approve(row, qa[id])
        record = public_record(dict(row, proposal_record_sha256=digest(row), independent_review=qa[id]))
        ledger['inspections'].append(record)
        if row['decision'] == 'decline':
            if not row.get('reason', row.get('decline_reason')):
                raise ValueError(f'{id}: an unresolved item needs its precise remaining blocker')
            continue
        q = qs[id]
        if id in existing or not q['study_eligible']:
            raise ValueError(f'{id}: duplicate or quarantined registration')
        check_originals(q, row)
        check_originals(q, qa[id])
        draft = row['draft_note']
        for citation in draft['sources']:
            ref = citation['ref']
            if ref in original_sources:
                continue
            meta = proposal['sources'].get(ref)
            if not meta:
                raise ValueError(f'{id}: unknown new source {ref}')
            if ref in data['sources'] and data['sources'][ref] != meta:
                raise ValueError(f'{ref}: conflicting new source metadata')
            data['sources'][ref] = copy.deepcopy(meta)
            used_new_refs.add(ref)
        note = authored_note(q, draft, proposal['checked_on'])
        arithmetic(note, restricted=True)
        if len({o['reason'] for o in note['option_notes']}) != 4:
            raise ValueError(f'{id}: four option reasons must differ')
        data['items'].append(copy.deepcopy(note))
        existing[id] = note
        ledger['registrations'].append(public_record(dict(
            row, note=note, previous_review=pending[id], independent_review=qa[id],
            explanation_sha256=digest(note), proposal_record_sha256=digest(row),
            official_answers=q['answers'], official_answer_changed=False)))
    if set(proposal['sources']) - set(original_sources) != used_new_refs:
        raise ValueError('Only actually cited new source definitions may enter the study catalogue')
    for ref, meta in original_sources.items():
        if data['sources'][ref] != meta:
            raise ValueError(f'{ref}: previous source definition changed')
    if {n['question_id']: digest(n) for n in data['items'] if n['question_id'] in baseline['explanation_hashes']} != baseline['explanation_hashes']:
        raise ValueError('Completed explanations changed')
    registered = {r['question_id'] for r in ledger['registrations']}
    audit['review'] = [r for r in audit['review'] if r['question_id'] not in registered]
    ledger.update(inspected_count=len(rows), registered_count=len(registered),
                  remaining_review_count=len(audit['review']), new_source_refs=sorted(used_new_refs))
    audit[GROUP] = ledger
    validate_explanations(data, qs, entries, parts)
    for key, expected in baseline['audit_key_hashes'].items():
        if key != 'review' and digest(audit[key]) != expected:
            raise ValueError(f'{key}: previous audit history changed')
    staged = {path: path.with_name(path.name + '.round24.tmp') for path in original}
    try:
        for path, value in ((dp, data), (ap, audit)):
            staged[path].write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        for path, tmp in staged.items():
            tmp.replace(path)
    except Exception:
        for path, body in original.items():
            path.write_bytes(body)
        raise
    finally:
        for tmp in staged.values():
            tmp.unlink(missing_ok=True)
    print(f'Round24: inspected {len(rows)}, registered {len(registered)}, held {len(audit["review"])}, completed material/official answer changes 0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('proposal', type=Path)
    parser.add_argument('reviews', type=Path)
    parser.add_argument('--proposal-sha256', required=True)
    parser.add_argument('--review-sha256', required=True)
    args = parser.parse_args()
    apply(args.proposal, args.reviews, args.proposal_sha256, args.review_sha256)
