"""Apply bounded source-verification amendments without rewriting older ledgers.

Usage: python3 scripts/apply_round27_sources.py /path/to/research/cache
The cache contains the actually inspected files named in round27-sources.json.
No new explanation, official answer or calculation is registered by this stage.
"""
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from apply_round10_followups import digest
from apply_round20_followups import protect_amendment
from explanation_data import validate_explanations

R = Path(__file__).resolve().parents[1]
GROUP = 'round27_sources'
PROPOSAL = 'reports/round27-sources.json'
VERIFIER = 'GPT coordinator /root, 2026-10-21'


def validate_row(row, sources):
    before, after = row['before'], row['after']
    qid = row['question_id']
    fields = protect_amendment(before, after, qid)
    if row['before_hash'] != digest(before) or row['after_hash'] != digest(after):
        raise ValueError(f'{qid}: stale amendment')
    if row['changed_fields'] != fields or not fields:
        raise ValueError(f'{qid}: inaccurate changed fields')
    if before['question_id'] != qid or before['review_status'] != 'partial':
        raise ValueError(f'{qid}: expected existing partial explanation')
    if after['review_status'] != 'source_checked' or after['unchecked_points']:
        raise ValueError(f'{qid}: unresolved source upgrade')
    if not row['previous_author'] or row['verifier'] != VERIFIER:
        raise ValueError(f'{qid}: missing actual verification identity')
    if row['previous_author'] == row['verifier']:
        raise ValueError(f'{qid}: verifier must differ from the prior author')
    # This records the coordinator's verification of prior-authored text. It is
    # deliberately not labelled a new independent agent review.
    if row['review_method'] != 'coordinator_source_check_of_prior_authored_explanation':
        raise ValueError(f'{qid}: inaccurate review attribution')
    resolutions = row['resolved_unchecked_points']
    if [r['before_text'] for r in resolutions] != before['unchecked_points']:
        raise ValueError(f'{qid}: every removed warning needs an exact resolution')
    added = after['sources'][len(before['sources']):]
    added_refs = {s['ref'] for s in added}
    if not added_refs:
        raise ValueError(f'{qid}: no new directly read evidence')
    reads = {s['ref']: s for s in row['source_reads']}
    for ref in added_refs:
        if ref not in reads or ref not in sources:
            raise ValueError(f'{qid}: missing source receipt')
        read = reads[ref]
        if (not re.fullmatch(r'[0-9a-f]{64}', read['sha256'])
                or read['actually_read'] is not True or not read['read_locator']
                or read['sha256'] != sources[ref]['sha256']
                or read['url'] != sources[ref]['url']
                or read['version'] != sources[ref]['version']):
            raise ValueError(f'{qid}: source receipt does not match the catalogue')
    for resolution in resolutions:
        if not resolution['finding'] or resolution['ref'] not in added_refs:
            raise ValueError(f'{qid}: unproven warning removal')
        if not any(s['ref'] == resolution['ref'] and s['locator'] == resolution['locator'] for s in added):
            raise ValueError(f'{qid}: resolution locator differs from the citation')
    findings = row['four_option_findings']
    if (len(findings) != 4 or [x['number'] for x in findings] != [1, 2, 3, 4]
            or any(x['status'] != 'pass' or not x['finding'] for x in findings)):
        raise ValueError(f'{qid}: four specific option checks required')
    return fields


def main():
    cache = Path(sys.argv[1])
    proposal = json.loads((R / PROPOSAL).read_text())
    data_path, audit_path = R/'data/explanations.json', R/'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if GROUP in audit:
        raise ValueError('round27_sources already applied')
    if digest(data) != proposal['baseline_data_hash'] or digest(audit) != proposal['baseline_audit_hash']:
        raise ValueError('Baseline changed; source checks must be rebound to the current objects')
    for receipt in proposal['actual_file_reads']:
        path = R/receipt['repo_path'] if receipt.get('repo_path') else cache/receipt['cache_file']
        if not receipt['actually_read'] or not receipt['read_locator']:
            raise ValueError('Missing actual inspection scope')
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt['sha256']:
            raise ValueError(f'Source bytes changed: {path.name}')
    notes = {n['question_id']: n for n in data['items']}
    before_data, before_audit = copy.deepcopy(data), copy.deepcopy(audit)
    new_sources = proposal['new_sources']
    if set(data['sources']) & set(new_sources):
        raise ValueError('Reuse existing source refs; do not replace a source definition')
    existing_urls = {s.get('url') for s in data['sources'].values()}
    if any(s['url'] in existing_urls for s in new_sources.values()):
        raise ValueError('An existing document must reuse its original ref')
    if len({r['question_id'] for r in proposal['amendments']}) != len(proposal['amendments']):
        raise ValueError('Duplicate amendment')
    for row in proposal['amendments']:
        validate_row(row, new_sources)
        if notes[row['question_id']] != row['before']:
            raise ValueError('Stale before object')
        notes[row['question_id']].update(copy.deepcopy(row['after']))
    data['sources'].update(copy.deepcopy(new_sources))
    qs = {q['id']:q for q in json.loads((R/'data/questions.json').read_text())}
    entries = {e['id'] for e in json.loads((R/'data/entries.json').read_text())}
    parts = {p['id'] for p in json.loads((R/'data/taxonomy.json').read_text())}
    validate_explanations(data, qs, entries, parts)
    group = dict(checked_on=proposal['checked_on'], baseline_commit=proposal['baseline_commit'],
                 proposal_sha256=digest(proposal), verifier=VERIFIER, actual_new_subagents=0,
                 baseline_data_hash=digest(before_data), baseline_audit_hash=digest(before_audit),
                 baseline_source_hashes={k:digest(v) for k,v in before_data['sources'].items()},
                 protected_file_sha256={f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in
                     ['data/questions.json','data/entries.json','data/taxonomy.json',
                      'data/concept-notes.json','reports/concept-expansion.json',
                      'reports/해설추가검토목록.csv','assets/app.js','assets/app.css']},
                 new_source_refs=sorted(new_sources), amendments=proposal['amendments'],
                 amended_count=len(proposal['amendments']),
                 before_counts=dict(Counter(n['review_status'] for n in before_data['items'])),
                 after_counts=dict(Counter(n['review_status'] for n in data['items'])),
                 remaining_unregistered=len(audit['review']))
    audit[GROUP] = group
    for path, obj in [(data_path,data), (audit_path,audit)]:
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(amended=group['amended_count'],counts=group['after_counts']),ensure_ascii=False))


if __name__ == '__main__':
    main()
