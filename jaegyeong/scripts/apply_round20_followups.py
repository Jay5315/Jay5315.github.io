"""Apply independently reviewed source research, partial corrections and concept tips.

Only the coordinator applies immutable proposal/review files. Original answers,
question bindings, calculations, source definitions and all older audit ledgers
remain protected. Every inspection, including an unchanged/held item, has a
distinct independent reviewer bound to the exact proposal object.
"""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

from apply_round10_followups import ALLOWED_FIELDS, PROTECTED, arithmetic, digest, public_record, source_evidence
from explanation_data import question_fingerprint, validate_explanations

R = Path(__file__).resolve().parents[1]
GROUP = 'round20_followups'
APPEND_CONCEPT_FIELDS = {'key_points', 'formulas', 'examples', 'pitfalls', 'sources'}


def verified_review(row, review, identifier):
    """Reject missing, non-independent or stale approvals before any write."""
    if (not review or review.get('status') != 'pass'
            or not row.get('author') or not review.get('reviewer')
            or review.get('reviewer') == row['author']
            or review.get('proposal_sha256') != digest(row)):
        raise ValueError(f'{identifier}: missing/stale/non-independent review')
    source_evidence(row['source_reads'])
    source_evidence(review['source_reads'])
    for reads in (row['source_reads'], review['source_reads']):
        if any(not re.fullmatch(r'[0-9a-f]{64}', read['sha256']) for read in reads):
            raise ValueError(f'{identifier}: each actual file needs one SHA-256')
    return copy.deepcopy(review)


def four_options_pass(review, identifier):
    options=review.get('four_option_logic',[])
    if (len(options)!=4 or sorted(x['number'] for x in options)!=[1,2,3,4]
            or any(x['status']!='pass' or not x.get('note',x.get('finding')) for x in options)):
        raise ValueError(f'{identifier}: four specific original-option findings must pass')


def protect_amendment(before, after, identifier):
    if set(before) != set(after):
        raise ValueError(f'{identifier}: explanation schema changed')
    fields = {k for k in before if before[k] != after[k]}
    if not fields <= ALLOWED_FIELDS or fields & PROTECTED:
        raise ValueError(f'{identifier}: protected fields changed')
    if [(o['number'], o['is_answer']) for o in before['option_notes']] != [
            (o['number'], o['is_answer']) for o in after['option_notes']]:
        raise ValueError(f'{identifier}: original option bindings changed')
    if after['sources'][:len(before['sources'])] != before['sources']:
        raise ValueError(f'{identifier}: prior citations must be preserved')
    if 'option_notes' in fields and len({o['reason'] for o in after['option_notes']}) != 4:
        raise ValueError(f'{identifier}: four option reasons must differ')
    arithmetic(after)
    return sorted(fields)


def protect_concept(before, after, identifier):
    if set(before) != set(after):
        raise ValueError(f'{identifier}: concept schema changed')
    for field in APPEND_CONCEPT_FIELDS:
        if after[field][:len(before[field])] != before[field]:
            raise ValueError(f'{identifier}: previous {field} content changed')
    if after['unchecked_points'][:len(before['unchecked_points'])] != before['unchecked_points']:
        raise ValueError(f'{identifier}: previous unverified concept warnings changed')
    for field in set(before) - APPEND_CONCEPT_FIELDS - {'review_note', 'unchecked_points'}:
        if before[field] != after[field]:
            raise ValueError(f'{identifier}: protected concept field {field} changed')
    for example in after['examples'][len(before['examples']):]:
        if not example.get('checks'):
            raise ValueError(f'{identifier}: added examples need calculation checks')
        arithmetic(example, restricted=True)
    return sorted(k for k in before if before[k] != after[k])


def unique_rows(rows, field):
    mapping = {r[field]: r for r in rows}
    if len(mapping) != len(rows):
        raise ValueError('Overlapping assignments or duplicate approvals')
    return mapping


def authored_note(q, draft, checked_on):
    """Use the approved draft verbatim with original, immutable question bindings."""
    reasons = {o['number']:o['reason'] for o in draft['option_notes']}
    if len(draft['option_notes'])!=4 or set(reasons)!={1,2,3,4}:
        raise ValueError('An authored draft needs all four original options')
    return dict(question_id=q['id'],question_fingerprint=question_fingerprint(q),answers=q['answers'],
                part_id=q['classification']['primary_part_id'],title=draft['title'],summary=draft['summary'],
                steps=draft['steps'],option_notes=[dict(number=i,is_answer=i in q['answers'],reason=reasons[i]) for i in (1,2,3,4)],
                checks=draft['checks'],sources=draft['sources'],tax_law_year=q['tax_law_year'],
                review_status=draft['review_status'],review_note=draft['review_note'],unchecked_points=draft['unchecked_points'],
                authorship='AI 작성 학습용 해설 · 삼일회계법인의 공식 해설 아님',checked_on=checked_on)


def apply(proposal_path, review_path, proposal_hash, review_hash):
    for path, expected in ((proposal_path, proposal_hash), (review_path, review_hash)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Approved input file changed')
    proposal = json.loads(proposal_path.read_text())
    reviews = json.loads(review_path.read_text())
    dp, ap = R/'data/explanations.json', R/'reports/explanation-expansion.json'
    cp, ca = R/'data/concept-notes.json', R/'reports/concept-expansion.json'
    original_bytes = {p:p.read_bytes() for p in (dp,ap,cp,ca)}
    data, audit, concepts, concept_audit = (json.loads(original_bytes[p]) for p in (dp,ap,cp,ca))
    if GROUP in audit:
        if audit[GROUP]['proposal_sha256'] == proposal_hash and audit[GROUP]['review_sha256'] == review_hash:
            print('Already applied; no files changed')
            return
        raise ValueError('Different round-20 stage already recorded')
    if hashlib.sha256(original_bytes[ap]).hexdigest()!=proposal['baseline_audit_sha256']:
        raise ValueError('The audited baseline changed after authorship')
    qs = {q['id']:q for q in json.loads((R/'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R/'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R/'data/taxonomy.json').read_text())}
    notes = {n['question_id']:n for n in data['items']}
    cn = {n['id']:n for n in concepts['notes']}
    pending = {r['question_id']:r for r in audit['review']}
    expected_sources = {id for id,row in pending.items() if row['category']=='source_unverified'}
    expected_partial = {id for id,n in notes.items() if n['review_status']=='partial'}
    source_rows = unique_rows(proposal['source_reviews'], 'question_id')
    partial_rows = unique_rows(proposal['partial_reviews'], 'question_id')
    concept_rows = unique_rows(proposal['concept_amendments'], 'note_id')
    srqa = unique_rows(reviews['source'], 'question_id')
    prqa = unique_rows(reviews['partial'], 'question_id')
    crqa = unique_rows(reviews['concept'], 'note_id')
    if set(source_rows)!=expected_sources or set(partial_rows)!=expected_partial:
        raise ValueError('Source/partial inspections must cover their exact starting targets')
    if set(source_rows)!=set(srqa) or set(partial_rows)!=set(prqa) or set(concept_rows)!=set(crqa):
        raise ValueError('Every inspection and change needs an exact independent approval')
    baseline_data, baseline_concepts = copy.deepcopy(data), copy.deepcopy(concepts)
    ledger = dict(schema_version=1, checked_on=proposal['checked_on'], baseline_commit=proposal['baseline_commit'],
                  proposal_sha256=proposal_hash, review_sha256=review_hash,
                  baseline_count=len(notes), baseline_hashes={id:digest(n) for id,n in notes.items()},
                  baseline_source_hashes={k:digest(v) for k,v in data['sources'].items()},
                  baseline_concept_hashes={id:digest(n) for id,n in cn.items()},
                  baseline_concept_source_hashes={k:digest(v) for k,v in concepts['sources'].items()},
                  original_review=copy.deepcopy(audit['review']), original_concept_audit_sha256=hashlib.sha256(original_bytes[ca]).hexdigest(),
                  baseline_audit_key_hashes={k:digest(v) for k,v in audit.items() if k!='review'},
                  new_source_refs=[], new_concept_source_refs=[], source_inspections=[], partial_inspections=[],
                  registrations=[], amendments=[], concept_amendments=[],
                  actual_parallel_workers=proposal['actual_parallel_workers'],
                  worker_sessions=proposal['worker_sessions'], expert_reviewed=False)
    for sources, target, added in ((proposal['sources'],data['sources'],ledger['new_source_refs']),
                                    (proposal['concept_sources'],concepts['sources'],ledger['new_concept_source_refs'])):
        for ref, meta in sources.items():
            if ref in target and target[ref]!=meta:
                raise ValueError(f'{ref}: previous source definition changed')
            if ref not in target:
                target[ref]=copy.deepcopy(meta); added.append(ref)
    for id,row in source_rows.items():
        qa = verified_review(row,srqa[id],id)
        if row.get('previous_review',pending[id])!=pending[id]:
            raise ValueError(f'{id}: original held review changed')
        four_options_pass(qa,id)
        ledger['source_inspections'].append(public_record(dict(row,independent_review=qa,proposal_record_sha256=digest(row))))
        if row['decision']=='decline':
            if not row.get('decline_reason'):
                raise ValueError(f'{id}: held item needs an exact reason')
            continue
        if row['decision']!='register' or id in notes:
            raise ValueError(f'{id}: invalid or duplicate registration')
        q=qs[id]
        n=authored_note(q,row,proposal['checked_on'])
        if n['question_id']!=id or n['question_fingerprint']!=question_fingerprint(q):
            raise ValueError(f'{id}: registered original mismatch')
        arithmetic(n,restricted=True)
        if len({o['reason'] for o in n['option_notes']})!=4:
            raise ValueError(f'{id}: new reasons must differ')
        data['items'].append(copy.deepcopy(n))
        ledger['registrations'].append(public_record(dict(row,note=n,previous_review=pending[id],independent_review=qa,
            explanation_sha256=digest(n),question_row_sha256=digest(q),official_answers=q['answers'],proposal_record_sha256=digest(row))))
    for id,row in partial_rows.items():
        qa=verified_review(row,prqa[id],id)
        four_options_pass(qa,id)
        if row['decision'] not in {'keep','amend','upgrade'}:
            raise ValueError(f'{id}: unknown partial-inspection decision')
        before,after=row['before'],row['after']
        if before!=notes[id] or row['before_hash']!=digest(before) or row['after_hash']!=digest(after):
            raise ValueError(f'{id}: stale partial inspection')
        fields=protect_amendment(before,after,id)
        if row['changed_fields']!=fields:
            raise ValueError(f'{id}: unrecorded changed fields')
        if bool(fields)!=(row['decision'] in {'amend','upgrade'}):
            raise ValueError(f'{id}: decision disagrees with actual change')
        if after['review_status']=='source_checked' and (not row.get('all_unchecked_resolved') or not qa.get('all_unchecked_resolved')):
            raise ValueError(f'{id}: a fully checked upgrade needs explicit independent proof')
        record=public_record(dict(row,independent_review=qa,proposal_record_sha256=digest(row)))
        ledger['partial_inspections'].append(record)
        if fields:
            data['items'][next(i for i,n in enumerate(data['items']) if n['question_id']==id)]=copy.deepcopy(after)
            ledger['amendments'].append(record)
    for id,row in concept_rows.items():
        qa=verified_review(row,crqa[id],id)
        if not qa.get('addition_findings') or not qa.get('arithmetic_findings'):
            raise ValueError(f'{id}: specific concept and example findings are required')
        before,after=row['before'],row['after']
        if before!=cn[id] or row['before_hash']!=digest(before) or row['after_hash']!=digest(after):
            raise ValueError(f'{id}: stale concept amendment')
        fields=protect_concept(before,after,id)
        if not fields or row['changed_fields']!=fields or not row['reason']:
            raise ValueError(f'{id}: empty/unrecorded concept changes')
        if any(s['ref'] not in concepts['sources'] for s in after['sources']):
            raise ValueError(f'{id}: concept cites an unknown source')
        concepts['notes'][next(i for i,n in enumerate(concepts['notes']) if n['id']==id)]=copy.deepcopy(after)
        record=public_record(dict(row,independent_review=qa,output_hash=digest(row),proposal_record_sha256=digest(row)))
        ledger['concept_amendments'].append(record)
        # Existing concept protection checks reverse these append-only changes
        # before checking the untouched earlier snapshots.
        concept_audit.setdefault('followup_note_amendments',[]).append(copy.deepcopy(record))
    registered={r['question_id'] for r in ledger['registrations']}
    audit['review']=[r for r in audit['review'] if r['question_id'] not in registered]
    validate_explanations(data,qs,entries,parts)
    if any(meta!=data['sources'][ref] for ref,meta in baseline_data['sources'].items()):
        raise ValueError('Previous explanation source definitions changed')
    if any(meta!=concepts['sources'][ref] for ref,meta in baseline_concepts['sources'].items()):
        raise ValueError('Previous concept source definitions changed')
    ledger.update(source_target_count=len(source_rows),partial_target_count=len(partial_rows),
                  registered_count=len(registered),amended_count=len(ledger['amendments']),
                  concept_amended_count=len(ledger['concept_amendments']),remaining_review_count=len(audit['review']))
    audit[GROUP]=ledger
    output={dp:data,ap:audit,cp:concepts,ca:concept_audit}
    staged={path:path.with_name(path.name+'.round20.tmp') for path in output}
    try:
        for path,value in output.items():
            staged[path].write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for path,tmp in staged.items():tmp.replace(path)
    except Exception:
        for path,body in original_bytes.items():path.write_bytes(body)
        raise
    finally:
        for tmp in staged.values():tmp.unlink(missing_ok=True)
    print(f'Round 20: source inspections {len(source_rows)}, new {len(registered)}, partial inspections {len(partial_rows)}, amendments {len(ledger["amendments"])}, concepts {len(ledger["concept_amendments"])}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('proposal',type=Path);parser.add_argument('reviews',type=Path)
    parser.add_argument('--proposal-sha256',required=True);parser.add_argument('--review-sha256',required=True)
    args=parser.parse_args()
    apply(args.proposal,args.reviews,args.proposal_sha256,args.review_sha256)
