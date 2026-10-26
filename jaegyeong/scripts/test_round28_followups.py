"""Protect the 115-item inventory and exact independently reviewed amendments."""
import copy
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from apply_round10_followups import digest
from apply_round28_followups import GROUP,validate_amendment

R=Path(__file__).resolve().parents[1]
IDS_HASH='de6b656aa19999e6469b8c4e3191ad2636caa61a3fc2bc83a1bf3deccd6ce615'


def load_stage():
    data=json.loads((R/'data/explanations.json').read_text())
    audit=json.loads((R/'reports/explanation-expansion.json').read_text())
    from apply_round30_followups import restore_round30
    data,audit=restore_round30(data,audit)
    from apply_round29_followups import restore_round29
    data,audit=restore_round29(data,audit)
    proposal=json.loads((R/'reports/round28-proposals.json').read_text())
    reviews=json.loads((R/'reports/round28-independent-reviews.json').read_text())
    if GROUP not in audit:raise ValueError('Independently reviewed changes have not been recorded')
    group=audit[GROUP];before=copy.deepcopy(data)
    index={n['question_id']:i for i,n in enumerate(before['items'])}
    for row in group['amendments']:before['items'][index[row['question_id']]]=copy.deepcopy(row['before'])
    for ref in group['new_source_refs']:del before['sources'][ref]
    old_audit={k:v for k,v in audit.items() if k!=GROUP}
    return data,audit,proposal,reviews,group,before,old_audit


class Round28FollowupTests(unittest.TestCase):
    def test_inventory_evidence_and_all_previous_stages_are_preserved(self):
        data,audit,p,qa,g,before,old_audit=load_stage()
        self.assertEqual(digest(p),g['proposal_sha256'])
        self.assertEqual(digest(qa),g['review_sha256'])
        self.assertEqual(digest(before),g['baseline_data_hash'])
        self.assertEqual(digest(old_audit),g['baseline_audit_hash'])
        self.assertEqual(digest(before),p['baseline_data_hash'])
        self.assertEqual(digest(old_audit),p['baseline_audit_hash'])
        rows={i['question_id']:i for i in p['items']}
        grouped=[qid for x in p['groups'] for qid in x['question_ids']]
        self.assertEqual(len(rows),115)
        self.assertEqual(digest(sorted(rows)),IDS_HASH)
        self.assertEqual(len(grouped),115)
        self.assertEqual(sorted(grouped),sorted(rows))
        group_ids={x['group_id'] for x in p['groups']}
        self.assertEqual(len(group_ids),len(p['groups']))
        for row in rows.values():self.assertIn(row['group_id'],group_ids)
        originals={n['question_id']:n for n in before['items']}
        current={n['question_id']:n for n in data['items']}
        self.assertEqual(set(current),set(originals))
        self.assertEqual(len(current),4281)
        changes={x['question_id']:x for x in p['amendments']}
        reviews={x['question_id']:x for x in qa['amendments']}
        evidence={x['id']:x for x in p['source_reads']}
        self.assertEqual(set(changes),set(reviews))
        self.assertEqual(len(changes),len(p['amendments']))
        for qid,row in rows.items():
            self.assertEqual(row['before_hash'],digest(originals[qid]))
        for qid,old in originals.items():
            self.assertEqual(current[qid],changes[qid]['after'] if qid in changes else old,qid)
        for qid,row in changes.items():
            self.assertEqual(row['before'],originals[qid])
            validate_amendment(row,reviews[qid],evidence)
            record=next(r for r in g['amendments'] if r['question_id']==qid)
            self.assertEqual({k:v for k,v in record.items() if k!='independent_review'},row)
            self.assertEqual(record['independent_review'],reviews[qid])
        for file,expected in g['protected_file_sha256'].items():
            self.assertEqual(hashlib.sha256((R/file).read_bytes()).hexdigest(),expected,file)
        for ref,meta in before['sources'].items():
            self.assertEqual(data['sources'][ref],meta,ref)
            self.assertEqual(digest(meta),g['baseline_source_hashes'][ref])
        self.assertEqual(set(data['sources'])-set(before['sources']),set(p['new_sources']))
        self.assertEqual(set(g['new_source_refs']),set(p['new_sources']))
        self.assertEqual(Counter(n['review_status'] for n in before['items']),g['before_counts'])
        self.assertEqual(Counter(n['review_status'] for n in data['items']),g['after_counts'])
        self.assertEqual(audit['review'],old_audit['review'])
        self.assertEqual(len(audit['review']),40)
        self.assertEqual({k:v for k,v in before.items() if k not in {'items','sources'}},
                         {k:v for k,v in data.items() if k not in {'items','sources'}})

    def test_protected_fields_stale_review_and_unproven_upgrade_are_rejected(self):
        data,audit,p,qa,g,before,old_audit=load_stage()
        original=p['amendments'][0]
        review=next(x for x in qa['amendments'] if x['question_id']==original['question_id'])
        evidence={s['id']:s for s in p['source_reads']}
        def reject(mutate):
            row=copy.deepcopy(original);check=copy.deepcopy(review);mutate(row,check)
            row['after_hash']=digest(row['after'])
            row['changed_fields']=sorted(k for k in row['before'] if row['before'][k]!=row['after'][k])
            check['proposal_sha256']=digest(row)
            with self.assertRaises(ValueError):validate_amendment(row,check,evidence)
        reject(lambda r,q:r['after'].update(answers=[9]))
        reject(lambda r,q:r['after'].update(checks=[{'label':'changed','expr':'1+1','expected':2}]))
        reject(lambda r,q:q.update(reviewer=r['author']))
        reject(lambda r,q:r.update(source_read_ids=['not-read']))
        reject(lambda r,q:q.update(four_option_findings=q['four_option_findings'][:3]))
        def unsupported(row,qa):
            row['after']['review_status']='source_checked';row['after']['unchecked_points']=[]
            row['resolved_unchecked_points']=[];qa['all_unchecked_points_resolved']=False
        reject(unsupported)


if __name__=='__main__':unittest.main()
