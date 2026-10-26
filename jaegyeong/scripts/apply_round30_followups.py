"""Apply audited round-30 amendments to questions outside the round-29 scope.

Usage: python3 scripts/apply_round30_followups.py PRIVATE_FILE_RECEIPTS.json
Public proposals contain hashes/locations; copyrighted files stay outside git.
"""
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from apply_round10_followups import digest
from apply_round20_followups import protect_amendment
from explanation_data import validate_explanations

R=Path(__file__).resolve().parents[1]
GROUP='round30_followups'


def validate_amendment(row, review, evidence):
    qid=row['question_id'];before=row['before'];after=row['after']
    fields=protect_amendment(before,after,qid)
    if (before['question_id']!=qid or before['review_status']!='partial'
            or row['before_hash']!=digest(before) or row['after_hash']!=digest(after)
            or row['changed_fields']!=fields or not fields):
        raise ValueError(f'{qid}: stale/incorrect amendment')
    if (not review or review['verdict']!='pass'
            or not row['author'] or not review['reviewer']
            or row['author']==review['reviewer']
            or review['proposal_sha256']!=digest(row)):
        raise ValueError(f'{qid}: missing, stale or non-independent review')
    for readings in [row['source_read_ids'],review['source_read_ids']]:
        if not readings or not set(readings)<=set(evidence):
            raise ValueError(f'{qid}: missing actual source evidence')
    options=review['four_option_findings']
    if ([o['number'] for o in options]!=[1,2,3,4]
            or any(o.get('status',o.get('verdict'))!='pass' or not o['finding'] for o in options)):
        raise ValueError(f'{qid}: four original choices need review findings')
    if after['review_status']=='source_checked':
        if after['unchecked_points']:
            raise ValueError(f'{qid}: unresolved source upgrade')
        resolutions=row['resolved_unchecked_points']
        if ([x['before_text'] for x in resolutions]!=before['unchecked_points']
                or any(not x['finding'] or x['evidence_id'] not in row['source_read_ids'] for x in resolutions)
                or not review['all_unchecked_points_resolved']):
            raise ValueError(f'{qid}: every removed warning needs specific evidence')
    elif after['review_status']!='partial' or not after['unchecked_points'] or not review['limits']:
        raise ValueError(f'{qid}: partial changes must retain explicit limitations')
    # Partial amendments also need evidence for each warning they remove.
    removed=set(before['unchecked_points'])-set(after['unchecked_points'])
    resolutions=row.get('resolved_unchecked_points',[])
    if (not removed <= {x['before_text'] for x in resolutions}
            or any(not x['finding'] or x['evidence_id'] not in row['source_read_ids']
                   for x in resolutions)):
        raise ValueError(f'{qid}: removed warnings need explicit primary-source resolutions')
    return fields


def restore_round30(data, audit):
    """Verify and reverse only this stage before running older protection tests."""
    group=(audit or {}).get(GROUP)
    if not group:
        return data,audit
    before=copy.deepcopy(data)
    old_audit=copy.deepcopy(audit)
    index={n['question_id']:i for i,n in enumerate(before['items'])}
    for row in group['amendments']:
        if (digest(before['items'][index[row['question_id']]])!=row['after_hash']
                or digest(row['before'])!=row['before_hash']):
            raise ValueError('Round-30 restoration encountered an unrecorded change')
        before['items'][index[row['question_id']]]=copy.deepcopy(row['before'])
    for ref in group['new_source_refs']:
        del before['sources'][ref]
    del old_audit[GROUP]
    if (digest(before)!=group['baseline_data_hash']
            or digest(old_audit)!=group['baseline_audit_hash']):
        raise ValueError('Round-30 restoration does not match its protected baseline')
    return before,old_audit


def main():
    proposal=json.loads((R/'reports/round30-proposals.json').read_text())
    reviews=json.loads((R/'reports/round30-independent-reviews.json').read_text())
    receipts=json.loads(Path(sys.argv[1]).read_text())
    for receipt in receipts:
        if hashlib.sha256(Path(receipt['path']).read_bytes()).hexdigest()!=receipt['sha256']:
            raise ValueError('Actual source cache changed after review')
    data_path=R/'data/explanations.json';audit_path=R/'reports/explanation-expansion.json'
    data=json.loads(data_path.read_text());audit=json.loads(audit_path.read_text())
    if GROUP in audit:raise ValueError('round30_followups already applied')
    if digest(data)!=proposal['baseline_data_hash'] or digest(audit)!=proposal['baseline_audit_hash']:
        raise ValueError('Baseline changed')
    baseline=copy.deepcopy(data);old_audit=copy.deepcopy(audit)
    notes={n['question_id']:n for n in data['items']}
    qa={x['question_id']:x for x in reviews['amendments']}
    evidence={x['id']:x for x in proposal['source_reads']}
    receipt_map={x['id']:x for x in receipts}
    required={s for row in proposal['amendments'] for s in row['source_read_ids']}
    required.update(s for row in reviews['amendments'] for s in row['source_read_ids'])
    for identifier in required:
        if (identifier not in evidence or identifier not in receipt_map
                or receipt_map[identifier]['sha256']!=evidence[identifier]['sha256']):
            raise ValueError('Public evidence must match the actual inspected file receipt')
    new=proposal['new_sources']
    if set(new)&set(data['sources']):raise ValueError('Existing source definitions are protected')
    if len(qa)!=len(reviews['amendments']) or set(qa)!={r['question_id'] for r in proposal['amendments']}:
        raise ValueError('Missing or duplicate independent review')
    if len({r['question_id'] for r in proposal['amendments']})!=len(proposal['amendments']):
        raise ValueError('Duplicate amendment')
    records=[]
    for row in proposal['amendments']:
        qid=row['question_id'];validate_amendment(row,qa[qid],evidence)
        if notes[qid]!=row['before']:raise ValueError('Stale before object')
        notes[qid].update(copy.deepcopy(row['after']))
        records.append(dict(row,independent_review=copy.deepcopy(qa[qid])))
    data['sources'].update(copy.deepcopy(new))
    qs={q['id']:q for q in json.loads((R/'data/questions.json').read_text())}
    entries={e['id'] for e in json.loads((R/'data/entries.json').read_text())}
    parts={p['id'] for p in json.loads((R/'data/taxonomy.json').read_text())}
    validate_explanations(data,qs,entries,parts)
    audit[GROUP]=dict(baseline_commit=proposal['baseline_commit'],
        proposal_sha256=digest(proposal),review_sha256=digest(reviews),
        baseline_data_hash=digest(baseline),baseline_audit_hash=digest(old_audit),
        new_source_refs=sorted(new),amendments=records,
        amended_count=len(records),before_counts=dict(Counter(n['review_status'] for n in baseline['items'])),
        after_counts=dict(Counter(n['review_status'] for n in data['items'])),
        baseline_source_hashes={k:digest(v) for k,v in baseline['sources'].items()},
        protected_file_sha256={f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in
            ['data/questions.json','data/entries.json','data/taxonomy.json','data/concept-notes.json',
             'reports/concept-expansion.json','reports/해설추가검토목록.csv',
             'assets/app.js','assets/app.css','index.html','MANUAL_ACCEPTANCE.md']})
    for path,obj in [(data_path,data),(audit_path,audit)]:
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'amended':len(records),'counts':audit[GROUP]['after_counts']}))


if __name__=='__main__':main()
