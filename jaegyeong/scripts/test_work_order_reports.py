"""Coverage checks for the source research required by GPT_WORK_ORDER.md."""
import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

from apply_round10_followups import digest
from explanation_data import question_fingerprint

R=Path(__file__).resolve().parents[1]
STEP2_IDS_HASH='7f1922670ba429b5296b9009916dfec7aa24fce0887ee449b73ad68c882649c0'


def validate_matrix(report, questions, explanations):
    rows=report['items'];ids=[x['question_id'] for x in rows]
    if len(ids)!=40 or len(set(ids))!=40 or digest(sorted(ids))!=STEP2_IDS_HASH:
        raise ValueError('Every one of the original 40 pending items needs a row')
    sources={s['id']:s for s in report['source_reads']}
    if len(sources)!=len(report['source_reads']):raise ValueError('Duplicated source receipt')
    for source in sources.values():
        if not re.fullmatch(r'[0-9a-f]{64}',source['sha256']):
            raise ValueError('Each actual file needs a separate SHA-256')
        if not source['read_location'] or not source['version']:
            raise ValueError('Missing actual reading scope/version')
        if source.get('repo_path'):
            if hashlib.sha256((R/source['repo_path']).read_bytes()).hexdigest()!=source['sha256']:
                raise ValueError('Original source file changed')
    for row in rows:
        q=questions[row['question_id']]
        if (row['official_answers']!=q['answers']
                or row['question_fingerprint']!=question_fingerprint(q)):
            raise ValueError('Research is bound to different wording or official answer')
        if any(not row.get(k) for k in ['needed_evidence','searched_scope','reason','source_read_ids']):
            raise ValueError('Missing required-evidence/search/outcome evidence')
        if not set(row['source_read_ids'])<=set(sources):
            raise ValueError('A claimed source was not actually recorded')
        if row['decision'] not in {'hold','register'}:raise ValueError('Unknown research outcome')
        if row['decision']=='register' and row['question_id'] not in explanations:
            raise ValueError('Unregistered draft must not be reported as registered')


class WorkOrderStep2Tests(unittest.TestCase):
    def test_complete_pending_matrix_and_original_bindings(self):
        report=json.loads((R/'reports/work-order-step2-matrix.json').read_text())
        qs={q['id']:q for q in json.loads((R/'data/questions.json').read_text())}
        notes={n['question_id']:n for n in json.loads((R/'data/explanations.json').read_text())['items']}
        validate_matrix(report,qs,notes)

    def test_missing_row_unknown_source_and_unsupported_registration_are_rejected(self):
        report=json.loads((R/'reports/work-order-step2-matrix.json').read_text())
        qs={q['id']:q for q in json.loads((R/'data/questions.json').read_text())}
        notes={n['question_id']:n for n in json.loads((R/'data/explanations.json').read_text())['items']}
        bad=copy.deepcopy(report);bad['items'].pop()
        with self.assertRaises(ValueError):validate_matrix(bad,qs,notes)
        bad=copy.deepcopy(report);bad['items'][0]['source_read_ids']=['never-read']
        with self.assertRaises(ValueError):validate_matrix(bad,qs,notes)
        bad=copy.deepcopy(report);bad['items'][0]['decision']='register'
        with self.assertRaises(ValueError):validate_matrix(bad,qs,notes)


if __name__=='__main__':unittest.main()
