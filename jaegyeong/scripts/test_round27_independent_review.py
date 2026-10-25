"""Evidence and binding checks for the separately executed round-27 review."""
import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

from apply_round10_followups import digest

R = Path(__file__).resolve().parents[1]
REPORT = R/'reports/round27-independent-review.json'
TARGETS = {'2025-03-101','2024-06-101','2023-03-102',
           '2026-06-085','2023-01-102','2026-07-102'}


def validate_review(report, data, questions):
    notes = {n['question_id']:n for n in data['items']}
    seen = set()
    reviewers = set()
    for review in report['reviews']:
        reviewer = review['reviewer']
        if not reviewer.startswith('/root/r27_') or reviewer == report['original_author']:
            raise ValueError('Review must be performed by a distinct actual reviewer')
        reviewers.add(reviewer)
        evidence = {s['evidence_id']:s for s in review['source_reads']}
        if len(evidence) != len(review['source_reads']):
            raise ValueError('Duplicate evidence identifier')
        for source in evidence.values():
            if not re.fullmatch(r'[0-9a-f]{64}',source['sha256']):
                raise ValueError('Each actual source file needs one SHA-256')
            if source['kind'] == 'frame':
                if (not re.fullmatch(r'[0-9a-f]{64}',source['video_sha256'])
                        or not isinstance(source['file_time_seconds'],(int,float))
                        or not source['transcription'] or not source['extraction_command']
                        or not source['ffmpeg_version'] or not source['read_locator']):
                    raise ValueError('Incomplete frame evidence')
                meta=data['sources'][source['ref']]
                if source['video_sha256'] != meta['sha256']:
                    raise ValueError('Frame is bound to a different source video')
            elif source['kind']=='repository_file':
                if hashlib.sha256((R/source['repo_path']).read_bytes()).hexdigest()!=source['sha256']:
                    raise ValueError('Original source bytes changed')
        frames={k for k,s in evidence.items() if s['kind']=='frame'}
        for item in review['items']:
            qid=item['question_id']
            if qid not in TARGETS or qid in seen:
                raise ValueError('Unexpected or duplicated question review')
            seen.add(qid)
            note=notes[qid];q=questions[qid]
            if digest(note)!=item['current_explanation_sha256'] or q['answers']!=item['official_answers']:
                raise ValueError('Stale review or changed official answer')
            for field,path in [('question_image_sha256',q['image']),('answer_pdf_sha256',q['answer_pdf'])]:
                if hashlib.sha256((R/path).read_bytes()).hexdigest()!=item[field]:
                    raise ValueError('Review is not bound to the original question/key')
            if item['verdict'] not in {'pass','disagree','unverified'}:
                raise ValueError('Unknown verdict')
            if item['verdict']!='pass' and note['review_status']!='partial':
                raise ValueError('Disagreed or unverified explanation must be partial')
            if not item['summary_finding'] or not item['added_conditions_check'] or not item['limits']:
                raise ValueError('Missing semantic findings or limits')
            steps=item['step_findings']
            numbers=[x.get('step_number',x.get('number')) for x in steps]
            if numbers!=list(range(1,len(note['steps'])+1)):
                raise ValueError('Every current explanation step must be reviewed')
            options=item['four_option_findings']
            if [x['number'] for x in options]!=[1,2,3,4] or any(not x['finding'] for x in steps+options):
                raise ValueError('Four original choices need separate findings')
            refs=set(item['evidence_refs'])
            if not refs<=set(evidence) or not refs&frames:
                raise ValueError('Every item needs actually read frame evidence')
            if item['verdict']=='pass' and any(x['status']!='pass' for x in steps+options):
                raise ValueError('Passing verdict conflicts with detailed findings')
    if seen!=TARGETS or len(reviewers)!=report['actual_independent_reviewers']:
        raise ValueError('Incomplete six-item review or incorrect reviewer count')


class Round27IndependentReviewTests(unittest.TestCase):
    def test_independent_evidence_covers_six_current_explanations(self):
        report=json.loads(REPORT.read_text())
        data=json.loads((R/'data/explanations.json').read_text())
        qs={q['id']:q for q in json.loads((R/'data/questions.json').read_text())}
        validate_review(report,data,qs)

    def test_missing_frame_transcription_and_non_independence_are_rejected(self):
        report=json.loads(REPORT.read_text())
        data=json.loads((R/'data/explanations.json').read_text())
        qs={q['id']:q for q in json.loads((R/'data/questions.json').read_text())}
        bad=copy.deepcopy(report);bad['reviews'][0]['reviewer']=report['original_author']
        with self.assertRaises(ValueError):validate_review(bad,data,qs)
        bad=copy.deepcopy(report)
        next(s for s in bad['reviews'][0]['source_reads'] if s['kind']=='frame')['transcription']=''
        with self.assertRaises(ValueError):validate_review(bad,data,qs)
        bad=copy.deepcopy(report);bad['reviews'][0]['items'].pop()
        with self.assertRaises(ValueError):validate_review(bad,data,qs)


if __name__=='__main__':
    unittest.main()
