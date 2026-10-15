"""Apply round-26 independent partial-explanation and concept-note follow-ups.

Inputs retain private source paths for byte verification. Public audit rows keep
both the immutable input hash and the canonical hash of the sanitized copy.
No registration, answer adjudication or existing citation replacement is allowed.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from apply_round10_followups import arithmetic, digest, public_record
from apply_round20_followups import (four_options_pass, protect_amendment,
                                     APPEND_CONCEPT_FIELDS, unique_rows, verified_review)
from explanation_data import validate_explanations

R = Path(__file__).resolve().parents[1]
GROUP = 'round26_followups'


def validate_coverage(partial_rows, concept_rows, expected_partial, expected_concepts):
    if set(partial_rows) != expected_partial or set(concept_rows) != expected_concepts:
        raise ValueError('Inspections must cover all and only baseline partial explanations/concepts')
    if len(expected_partial) != 122 or len(expected_concepts) != 8:
        raise ValueError('Round-26 baseline target counts changed')


def validate_partial(row, qa, identifier):
    before, after = row['before'], row['after']
    fields = protect_amendment(before, after, identifier)
    decision = row['decision']
    if decision not in {'keep', 'amend', 'upgrade'}:
        raise ValueError(f'{identifier}: unknown partial-inspection decision')
    if row['changed_fields'] != fields:
        raise ValueError(f'{identifier}: unrecorded changed fields')
    if bool(fields) != (decision in {'amend', 'upgrade'}):
        raise ValueError(f'{identifier}: decision disagrees with actual change')
    if before['review_status'] != 'partial':
        raise ValueError(f'{identifier}: only baseline partial notes are in scope')
    if (after['review_status'] == 'source_checked') != (decision == 'upgrade'):
        raise ValueError(f'{identifier}: upgrade decision/status mismatch')
    if after['review_status'] not in {'partial', 'source_checked'}:
        raise ValueError(f'{identifier}: invalid final review status')
    if decision == 'upgrade' and (row.get('all_unchecked_resolved') is not True
            or qa.get('all_unchecked_resolved') is not True or after['unchecked_points']):
        raise ValueError(f'{identifier}: a checked upgrade needs explicit independent proof')
    if not row.get('reason'):
        raise ValueError(f'{identifier}: each inspection requires a specific reason')
    return fields


def validate_concept(row, qa, identifier):
    """Append material; audit narrow text corrections and resolved warnings."""
    before, after = row['before'], row['after']
    if set(before) != set(after):
        raise ValueError(f'{identifier}: concept schema changed')
    cited = {s['ref'] for s in after['sources']}
    author_reads = {s.get('ref') for s in row['source_reads']}
    reviewer_reads = {s.get('ref') for s in qa['source_reads']}
    expected_prefix = copy.deepcopy(before)
    text_amendments = row.get('text_amendments', [])
    if not isinstance(text_amendments, list):
        raise ValueError(f'{identifier}: text amendments must be a list')
    if text_amendments and qa.get('text_amendments_checked') is not True:
        raise ValueError(f'{identifier}: text corrections need independent confirmation')
    seen = set()
    for amendment in text_amendments:
        if not isinstance(amendment, dict):
            raise ValueError(f'{identifier}: text correction must be an object')
        field, index = amendment.get('field'), amendment.get('index')
        if (not isinstance(field,str) or field not in {'key_points', 'pitfalls'} or type(index) is not int
                or index < 0 or index >= len(before[field]) or (field,index) in seen):
            raise ValueError(f'{identifier}: invalid/duplicate text correction target')
        if (not isinstance(amendment.get('before'),str) or not amendment['before'].strip()
                or amendment['before'] != before[field][index]
                or not isinstance(amendment.get('after'), str) or not amendment['after'].strip()
                or amendment['after'] == amendment['before']):
            raise ValueError(f'{identifier}: stale/empty text correction')
        if (not amendment.get('locator') or not amendment.get('reason')
                or amendment.get('evidence_ref') not in cited & author_reads & reviewer_reads):
            raise ValueError(f'{identifier}: text correction must cite an actually read source')
        seen.add((field,index))
        expected_prefix[field][index] = amendment['after']
    for field in APPEND_CONCEPT_FIELDS:
        if after[field][:len(before[field])] != expected_prefix[field]:
            raise ValueError(f'{identifier}: previous {field} content changed without exact authorization')
    for field in set(before) - APPEND_CONCEPT_FIELDS - {'review_note', 'unchecked_points', 'review_status'}:
        if before[field] != after[field]:
            raise ValueError(f'{identifier}: protected concept field {field} changed')
    if before['review_status'] != 'partial' or after['review_status'] not in {'partial', 'source_checked'}:
        raise ValueError(f'{identifier}: only partial-to-checked concept transitions are allowed')
    removed = [text for text in before['unchecked_points'] if text not in after['unchecked_points']]
    retained = [text for text in before['unchecked_points'] if text in after['unchecked_points']]
    if after['unchecked_points'][:len(retained)] != retained:
        raise ValueError(f'{identifier}: retained concept warnings reordered')
    evidence = row.get('resolved_unchecked_points', [])
    if len(evidence) != len(removed) or {e['before_text'] for e in evidence} != set(removed):
        raise ValueError(f'{identifier}: each removed warning needs exact resolution evidence')
    if evidence and qa.get('resolved_unchecked_points_checked') is not True:
        raise ValueError(f'{identifier}: resolved warnings need independent confirmation')
    for e in evidence:
        if (not e.get('locator') or not e.get('reason')
                or e.get('evidence_ref') not in cited & author_reads & reviewer_reads):
            raise ValueError(f'{identifier}: resolution must cite an actually read source')
    if after['review_status'] == 'source_checked':
        if (row.get('all_unchecked_resolved') is not True or qa.get('all_unchecked_resolved') is not True
                or after['unchecked_points'] or not cited
                or not cited & author_reads & reviewer_reads
                or any(f.get('unchecked') for f in after['formulas'])):
            raise ValueError(f'{identifier}: fully checked concept needs explicit independent proof')
    for example in after['examples'][len(before['examples']):]:
        if not example.get('checks'):
            raise ValueError(f'{identifier}: added examples need calculation checks')
        arithmetic(example, restricted=True)
    return sorted(k for k in before if before[k] != after[k])


def audited_record(row, qa):
    return public_record(dict(row, independent_review=qa,
        proposal_record_sha256=digest(row),
        public_proposal_record_sha256=digest(public_record(row))))


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
        raise ValueError('Different round-26 stage already recorded')
    if hashlib.sha256(original_bytes[ap]).hexdigest()!=proposal['baseline_audit_sha256']:
        raise ValueError('The audited baseline changed after authorship')
    qs = {q['id']:q for q in json.loads((R/'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R/'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R/'data/taxonomy.json').read_text())}
    notes = {n['question_id']:n for n in data['items']}
    cn = {n['id']:n for n in concepts['notes']}
    expected_partial = {id for id,n in notes.items() if n['review_status']=='partial'}
    partial_rows = unique_rows(proposal['partial_reviews'], 'question_id')
    concept_rows = unique_rows(proposal['concept_amendments'], 'note_id')
    prqa = unique_rows(reviews['partial'], 'question_id')
    crqa = unique_rows(reviews['concept'], 'note_id')
    expected_concepts = {id for id,n in cn.items() if n['review_status']=='partial'}
    validate_coverage(partial_rows, concept_rows, expected_partial, expected_concepts)
    if set(partial_rows)!=set(prqa) or set(concept_rows)!=set(crqa):
        raise ValueError('Every inspection and change needs an exact independent approval')
    baseline_data, baseline_concepts = copy.deepcopy(data), copy.deepcopy(concepts)
    ledger = dict(schema_version=1, checked_on=proposal['checked_on'], baseline_commit=proposal['baseline_commit'],
                  proposal_sha256=proposal_hash, review_sha256=review_hash,
                  public_proposal_sha256=digest(public_record(proposal)),
                  public_review_sha256=digest(public_record(reviews)),
                  baseline_content_hashes={'explanations':digest(data),'concepts':digest(concepts),
                                           'audit':digest(audit),'concept_audit':digest(concept_audit)},
                  baseline_file_sha256={str(p.relative_to(R)):hashlib.sha256(b).hexdigest()
                                        for p,b in original_bytes.items()},
                  protected_file_sha256={name:hashlib.sha256((R/name).read_bytes()).hexdigest()
                     for name in ('data/questions.json','data/entries.json','data/taxonomy.json')},
                  baseline_count=len(notes), baseline_hashes={id:digest(n) for id,n in notes.items()},
                  baseline_source_hashes={k:digest(v) for k,v in data['sources'].items()},
                  baseline_concept_hashes={id:digest(n) for id,n in cn.items()},
                  baseline_concept_source_hashes={k:digest(v) for k,v in concepts['sources'].items()},
                  original_review=copy.deepcopy(audit['review']), original_concept_audit_sha256=hashlib.sha256(original_bytes[ca]).hexdigest(),
                  baseline_audit_key_hashes={k:digest(v) for k,v in audit.items() if k!='review'},
                  new_source_refs=[], new_concept_source_refs=[], partial_inspections=[],
                  amendments=[], concept_amendments=[],
                  actual_parallel_workers=proposal['actual_parallel_workers'],
                  worker_sessions=proposal['worker_sessions'], expert_reviewed=False)
    for sources, target, added in ((proposal['sources'],data['sources'],ledger['new_source_refs']),
                                    (proposal['concept_sources'],concepts['sources'],ledger['new_concept_source_refs'])):
        for ref, meta in sources.items():
            if ref in target and target[ref]!=meta:
                raise ValueError(f'{ref}: previous source definition changed')
            if ref not in target:
                target[ref]=copy.deepcopy(meta); added.append(ref)
    for id,row in partial_rows.items():
        qa=verified_review(row,prqa[id],id)
        four_options_pass(qa,id)
        before,after=row['before'],row['after']
        if before!=notes[id] or row['before_hash']!=digest(before) or row['after_hash']!=digest(after):
            raise ValueError(f'{id}: stale partial inspection')
        fields=validate_partial(row,qa,id)
        record=audited_record(row,qa)
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
        fields=validate_concept(row,qa,id)
        if not fields or row['changed_fields']!=fields or not row['reason']:
            raise ValueError(f'{id}: empty/unrecorded concept changes')
        if any(s['ref'] not in concepts['sources'] for s in after['sources']):
            raise ValueError(f'{id}: concept cites an unknown source')
        concepts['notes'][next(i for i,n in enumerate(concepts['notes']) if n['id']==id)]=copy.deepcopy(after)
        record=audited_record(row,qa)
        record['output_hash']=digest(row)
        record['stage']=GROUP
        ledger['concept_amendments'].append(record)
        # Existing concept protection checks reverse these append-only changes
        # before checking the untouched earlier snapshots.
        concept_audit.setdefault('followup_note_amendments',[]).append(copy.deepcopy(record))
    validate_explanations(data,qs,entries,parts)
    if any(meta!=data['sources'][ref] for ref,meta in baseline_data['sources'].items()):
        raise ValueError('Previous explanation source definitions changed')
    if any(meta!=concepts['sources'][ref] for ref,meta in baseline_concepts['sources'].items()):
        raise ValueError('Previous concept source definitions changed')
    if len(data['items'])!=len(baseline_data['items']):
        raise ValueError('Existing explanation count changed')
    ledger.update(partial_target_count=len(partial_rows),concept_target_count=len(concept_rows),
                  amended_count=len(ledger['amendments']),
                  concept_amended_count=len(ledger['concept_amendments']),remaining_review_count=len(audit['review']))
    audit[GROUP]=ledger
    output={dp:data,ap:audit,cp:concepts,ca:concept_audit}
    staged={path:path.with_name(path.name+'.round26.tmp') for path in output}
    try:
        for path,value in output.items():
            staged[path].write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for path,tmp in staged.items():tmp.replace(path)
    except Exception:
        for path,body in original_bytes.items():path.write_bytes(body)
        raise
    finally:
        for tmp in staged.values():tmp.unlink(missing_ok=True)
    print(f'Round 26: partial inspections {len(partial_rows)}, amendments {len(ledger["amendments"])}, concepts {len(ledger["concept_amendments"])}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('proposal',type=Path);parser.add_argument('reviews',type=Path)
    parser.add_argument('--proposal-sha256',required=True);parser.add_argument('--review-sha256',required=True)
    args=parser.parse_args()
    apply(args.proposal,args.reviews,args.proposal_sha256,args.review_sha256)
