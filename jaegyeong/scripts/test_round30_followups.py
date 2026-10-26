"""Protect actual source/review scope and audited round-30 changes."""
import copy
import hashlib
import json
import re
import unittest
from collections import Counter
from pathlib import Path

from apply_round10_followups import digest
from apply_round30_followups import GROUP, restore_round30, validate_amendment

R=Path(__file__).resolve().parents[1]
PARTIAL_IDS='3c136c0ba7fca2034a28289007b5349876ed2cbdc1a216d79cc66d0f0bdb2eda'
SELECTED_IDS='c9bec5659be1821651e616bf1f2c0a157be47edf9a730df7a4b6d66ae19ed983'


def load():
    data=json.loads((R/'data/explanations.json').read_text())
    audit=json.loads((R/'reports/explanation-expansion.json').read_text())
    from apply_spacing_round6 import restore_spacing_round6
    data,audit=restore_spacing_round6(data,audit)
    proposal=json.loads((R/'reports/round30-proposals.json').read_text())
    review=json.loads((R/'reports/round30-independent-reviews.json').read_text())
    before,previous=restore_round30(data,audit)
    return data,audit,proposal,review,before,previous


class Round30FollowupTests(unittest.TestCase):
    def test_scope_and_all_previous_data_are_protected(self):
        data,audit,p,qa,before,previous=load()
        partials=sorted(n['question_id'] for n in before['items'] if n['review_status']=='partial')
        self.assertEqual(len(partials),113)
        self.assertEqual(digest(partials),PARTIAL_IDS)
        self.assertEqual(sorted(p['baseline_partial_ids']),partials)
        self.assertEqual(digest(before),p['baseline_data_hash'])
        self.assertEqual(digest(previous),p['baseline_audit_hash'])
        items={r['question_id']:r for r in p['items']}
        self.assertEqual(len(items),len(p['items']))
        self.assertEqual(len(items),76)
        self.assertEqual(digest(sorted(items)),SELECTED_IDS)
        groups={g['group_id']:g for g in p['groups']}
        self.assertEqual(len(groups),35)
        grouped=[qid for g in groups.values() for qid in g['question_ids']]
        self.assertEqual(sorted(grouped),sorted(items))
        old=json.loads((R/'reports/round28-proposals.json').read_text())
        prior=json.loads((R/'reports/round29-proposals.json').read_text())
        read_before={r['question_id'] for r in prior['items']}
        targets=set(partials)-read_before
        self.assertEqual(set(items),targets)
        self.assertEqual(set(groups),{g['group_id'] for g in old['groups'] if set(g['question_ids'])&targets})
        completed={qid for qid,r in items.items() if r['decision']!='blocked'}
        self.assertEqual(set(p['completed_question_ids']),completed)
        self.assertEqual(set(p['unverified_question_ids']),set(items)-completed)
        current={n['question_id']:n for n in data['items']}
        originals={n['question_id']:n for n in before['items']}
        self.assertEqual(list(current),list(originals))
        self.assertEqual(len(current),4281)
        changes={r['question_id']:r for r in p['amendments']}
        self.assertEqual(len(changes),len(p['amendments']))
        self.assertTrue(set(changes)<=set(items))
        for qid,old_note in originals.items():
            self.assertEqual(current[qid],changes[qid]['after'] if qid in changes else old_note,qid)
        for qid,row in items.items():
            self.assertIn(qid,groups[row['group_id']]['question_ids'])
            self.assertEqual(row['before_hash'],digest(originals[qid]))
            self.assertEqual(row['after_hash'],digest(current[qid]))
            self.assertEqual(row['changed_fields'],sorted(k for k in current[qid] if current[qid][k]!=originals[qid][k]))
            if row['decision']!='blocked':
                self.assertIs(row['originals_reread_this_task'],True)
                self.assertIs(row['official_answers_reread_this_task'],True)
            else:self.assertEqual(row['changed_fields'],[])
            self.assertTrue(row['reason'])
            if current[qid]['review_status']=='source_checked':
                self.assertEqual(row['decision'],'upgrade_source_checked')
                self.assertEqual(current[qid]['unchecked_points'],[])
            else:
                self.assertTrue(row['limits'])
        self.assertEqual(set(data['sources'])-set(before['sources']),set(p['new_sources']))
        for ref,source in before['sources'].items():self.assertEqual(data['sources'][ref],source,ref)
        self.assertEqual(audit['review'],previous['review'])
        self.assertEqual(len(audit['review']),40)
        self.assertEqual(p['before_counts'],dict(Counter(n['review_status'] for n in before['items'])))
        self.assertEqual(p['after_counts'],dict(Counter(n['review_status'] for n in data['items'])))
        for filename,expected in p['protected_file_sha256'].items():
            self.assertEqual(hashlib.sha256((R/filename).read_bytes()).hexdigest(),expected,filename)
        if changes:
            self.assertEqual(audit[GROUP]['proposal_sha256'],digest(p))
            self.assertEqual(audit[GROUP]['review_sha256'],digest(qa))
            self.assertEqual({r['question_id'] for r in audit[GROUP]['amendments']},set(changes))
        else:self.assertNotIn(GROUP,audit)

    def test_independent_primary_evidence_and_amendment_safety(self):
        data,audit,p,qa,before,previous=load()
        items={r['question_id']:r for r in p['items']}
        reviews={r['question_id']:r for r in qa['items']}
        evidence={r['id']:r for r in p['source_reads']}
        self.assertEqual(len(evidence),len(p['source_reads']))
        self.assertEqual(set(reviews),set(items))
        self.assertEqual(len(reviews),len(qa['items']))
        for s in evidence.values():
            self.assertRegex(s['sha256'],r'^[0-9a-f]{64}$')
            self.assertIs(s['actually_read'],True)
            self.assertTrue(s['url'] and s['version'] and s['locator'] and s['read_method'])
        amended={r['question_id']:r for r in p['amendments']}
        for qid,row in items.items():
            independent=reviews[qid]
            bound=amended.get(qid,row)
            self.assertEqual(independent['proposal_sha256'],digest(bound),qid)
            self.assertNotEqual(row['author'],independent['reviewer'])
            self.assertTrue(independent['reviewer'] and row['author'])
            self.assertIn(independent['verdict'],{'keep_supported','pass','blocked'})
            if row['decision']=='blocked':self.assertEqual(independent['verdict'],'blocked')
            else:self.assertNotEqual(independent['verdict'],'blocked')
            self.assertTrue(independent['finding'])
            for ids in (row['source_read_ids'],independent['source_read_ids']):
                self.assertTrue(ids,qid)
                self.assertTrue(set(ids)<=set(evidence),qid)
        exact_reviews={r['question_id']:r for r in qa['amendments']}
        self.assertEqual(set(exact_reviews),set(amended))
        for qid,row in amended.items():
            validate_amendment(row,exact_reviews[qid],evidence)
            original=copy.deepcopy(row)
            # Required safeguards, each rebound to its mutated object so a stale
            # digest alone cannot make the negative cases pass accidentally.
            for kind in ('answer','check','same_reviewer','unknown_source','missing_choice','unproven_warning'):
                candidate=copy.deepcopy(original);review=copy.deepcopy(exact_reviews[qid])
                if kind=='answer':candidate['after']['answers']=[99]
                elif kind=='check':candidate['after']['checks']=[{'expr':'2+2','expected':4}]
                elif kind=='same_reviewer':review['reviewer']=candidate['author']
                elif kind=='unknown_source':candidate['source_read_ids']=['unread-source']
                elif kind=='missing_choice':review['four_option_findings']=review['four_option_findings'][:3]
                else:
                    candidate['after']['unchecked_points']=[]
                    candidate['after']['review_status']='source_checked'
                    candidate['resolved_unchecked_points']=[]
                candidate['after_hash']=digest(candidate['after'])
                candidate['changed_fields']=sorted(k for k in candidate['before'] if candidate['before'][k]!=candidate['after'][k])
                review['proposal_sha256']=digest(candidate)
                with self.subTest(question=qid,kind=kind),self.assertRaises(ValueError):
                    validate_amendment(candidate,review,evidence)


if __name__=='__main__':unittest.main()
