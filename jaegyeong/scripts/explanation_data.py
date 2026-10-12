"""Validate authored explanations before they can be published in the app bundle."""
import hashlib
import json
import math


def question_fingerprint(q):
    """Bind to this original wording, options, answer and governing year, never a family."""
    fields = {k: q[k] for k in ('id', 'text', 'choices', 'answers', 'tax_law_year')}
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def validate_explanations(data, questions, entry_ids, part_ids):
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported explanation schema')
    seen = set()
    for n in data['items']:
        id = n['question_id']
        if id in seen or id not in entry_ids:
            raise ValueError(f'{id}: duplicate or unknown entry')
        seen.add(id)
        q = questions[id]
        if not q['study_eligible'] or n['question_fingerprint'] != question_fingerprint(q):
            raise ValueError(f'{id}: original changed or quarantined; re-review explanation')
        if n['answers'] != q['answers'] or n['tax_law_year'] != q['tax_law_year']:
            raise ValueError(f'{id}: official answer or governing year mismatch')
        if n['part_id'] not in part_ids:
            raise ValueError(f'{id}: unknown related part')
        if n['review_status'] not in {'source_checked', 'partial'}:
            raise ValueError(f'{id}: invalid review status')
        if not n['sources'] or not n['summary'] or not n['steps'] or not n['review_note']:
            raise ValueError(f'{id}: missing explanation or verification')
        if {x['number'] for x in n['option_notes']} != {1, 2, 3, 4} or len(n['option_notes']) != 4:
            raise ValueError(f'{id}: all four original options need explanations')
        for x in n['option_notes']:
            if not x['reason'] or x['is_answer'] != (x['number'] in q['answers']):
                raise ValueError(f'{id}: option/answer mismatch')
        if n['review_status'] == 'partial' and not n['unchecked_points']:
            raise ValueError(f'{id}: partial review must specify unchecked content')
        if n['review_status'] == 'source_checked' and n['unchecked_points']:
            raise ValueError(f'{id}: fully checked status contradicts unchecked points')
        for c in n['checks']:
            if (not isinstance(c.get('label'), str) or not c['label'].strip()
                    or not isinstance(c.get('expr'), str) or not c['expr'].strip()
                    or isinstance(c.get('expected'), bool)
                    or not isinstance(c.get('expected'), (int, float))
                    or not math.isfinite(c['expected'])):
                raise ValueError(f'{id}: incomplete arithmetic check')
        for s in n['sources']:
            if s['ref'] not in data['sources'] or not s['locator']:
                raise ValueError(f'{id}: unknown or unlocated verified source')
    return data
