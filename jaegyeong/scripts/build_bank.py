"""Build a conservative, reproducible question-bank corpus from supplied PDFs.

Original PDFs remain immutable. No network or language-model services are used.
Similarity is used for review suggestions, never to silently discard a question.
"""
from pathlib import Path
import collections
import hashlib
import json
import re
import shutil
import unicodedata
import csv
import io
import sys
import fitz
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[1]
SUBJECTS = ['재무회계', '세무회계', '원가관리회계']
CHOICE_RE = re.compile('[①②③④]')
MARKER_RE = re.compile(r'^\s*【\s*(\d+)\s*】')
SEMANTIC_RULES = [
    ('가장올바르지않은것은', '옳지않은것은'),
    ('올바르지않은것은', '옳지않은것은'),
    ('가장옳지않은것은', '옳지않은것은'),
    ('가장올바른것은', '옳은것은'),
    ('올바른것은', '옳은것은'),
    ('가장옳은것은', '옳은것은'),
    ('에관한설명', '에대한설명'),
    ('과관련된설명', '에대한설명'),
    ('와관련된설명', '에대한설명'),
    ('국제회계기준의적용으로자산및부채에대한공정가치측정대상이확대되었다', '국제회계기준은자산및부채에대한공정가치적용이확대되었다'),
    ('국제회계기준의적용으로자산및부채에대한공정가치적용이확대되었다', '국제회계기준은자산및부채에대한공정가치적용이확대되었다'),
]

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def normalize(text, semantic=False):
    # Keep all numbers, negations, units, decimal points, minus signs and operators.
    text = re.sub(r'(?<=\d)\s+(?=\d)', '|', text)
    text = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))
    text = text.replace('·', 'ㆍ').replace('，', ',')
    if semantic:
        for old, new in SEMANTIC_RULES:
            text = text.replace(old, new)
    return text

def parse_choices(text):
    # Some PDFs use circled Latin l (ⓛ) for choice 1. Table column labels and
    # references such as "④ ①, ②, ③ 모두" must not become extra answer options.
    pattern = re.compile(r'(?m)(?:^| {2,}|[：:]\s*)([①②③④ⓛ])')
    matches = list(pattern.finditer(text))
    selected = []
    cursor = len(matches)
    for label in reversed('①②③④'):
        found = next((i for i in range(cursor-1,-1,-1) if matches[i][1].replace('ⓛ','①')==label), None)
        if found is None: return text, [], False
        selected.append(matches[found]); cursor=found
    selected.reverse()
    stem=text[:selected[0].start(1)].strip()
    choices=[text[m.end(1):(selected[i+1].start(1) if i<3 else len(text))].strip() for i,m in enumerate(selected)]
    return stem, choices, all(choices)

def number_template(text):
    # Units, polarity, parentheses and operators survive this transformation.
    return re.sub(r'\d[\d,]*(?:\.\d+)?', '#', text)

def read_answers(exam, info):
    with fitz.open(info['answer_file']) as doc:
        text = doc[-1 if exam.startswith('2022') else 0].get_text()
    tokens = []
    for line in text.splitlines():
        line = line.strip()
        if re.fullmatch(r'\d+번', line): tokens.append(line[:-1])
        elif re.fullmatch(r'\[?\d+\]?', line): tokens.append(line.strip('[]'))
        elif re.fullmatch(r'[1-4]\s*또는\s*[1-4]', line): tokens.append(line)
    assert len(tokens) == 240, (exam, len(tokens))
    pairs = list(zip(tokens[::2], tokens[1::2]))
    answers = {}
    for subject in range(3):
        group = pairs[subject*40:(subject+1)*40]
        local = {int(n) for n, _ in group} == set(range(1, 41))
        for n, a in group:
            number = int(n) + (subject*40 if local else 0)
            answers[number] = [int(x) for x in re.findall(r'\d+', a)]
    assert set(answers) == set(range(1, 121))
    return answers

def page_lines(page):
    result = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            result.append({'text': ''.join(s['text'] for s in line['spans']),
                           'bbox': list(line['bbox'])})
    return result

def ordered_text(lines):
    # Group baselines before sorting horizontally, so table cells remain in row order.
    rows = []
    for line in sorted(lines, key=lambda x: (x['bbox'][1], x['bbox'][0])):
        if rows and abs(line['bbox'][1] - rows[-1][0]) < 3:
            rows[-1][1].append(line)
        else: rows.append((line['bbox'][1], [line]))
    return '\n'.join('  '.join(x['text'].strip() for x in sorted(row, key=lambda x: x['bbox'][0])) for _, row in rows)

def extract(summary):
    questions = []
    for exam, info in sorted(summary['exams'].items()):
        answers = read_answers(exam, info)
        question_pdf = ROOT / 'sources' / f'{exam}-questions.pdf'
        answer_pdf = ROOT / 'sources' / f'{exam}-answers.pdf'
        for source, target in [(info['question_file'], question_pdf), (info['answer_file'], answer_pdf)]:
            if not target.exists(): shutil.copyfile(source, target)
            assert hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(Path(source).read_bytes()).digest()
        with fitz.open(question_pdf) as doc:
            subject_notes={}
            tax_years=[]
            for subject_index, first_page in enumerate([0,16,32]):
                p=doc[first_page]
                ls=page_lines(p)
                first=min(l['bbox'][1] for l in ls if MARKER_RE.match(l['text']))
                note=ordered_text([l for l in ls if 70<l['bbox'][1]<first-1 and not re.match(r'^\s*<',l['text'])]).strip()
                subject_notes[SUBJECTS[subject_index]]=note
                if subject_index==1:
                    tax_years=re.findall(r'(20\d{2})\s*년\s*세법',note)
            for pno in range(info['question_pages']):
                page = doc[pno]
                lines = page_lines(page)
                markers = sorted([(int(MARKER_RE.match(l['text'])[1]), l['bbox'][1]) for l in lines if MARKER_RE.match(l['text'])], key=lambda x: x[1])
                assert markers, (exam, pno)
                drawings = page.get_drawings()
                for pos, (number, top) in enumerate(markers):
                    bottom = markers[pos+1][1]-3 if pos+1 < len(markers) else 780
                    selected = [l for l in lines if top-1 <= l['bbox'][1] < bottom and l['bbox'][3] < 790]
                    selected = [l for l in selected if not re.match(r'^(본 시험은 현행 기준|[ü✓] 특별한 언급)', l['text'].strip())]
                    text = ordered_text(selected)
                    text = MARKER_RE.sub('', text, count=1).strip()
                    stem,choices,clean_choices=parse_choices(text)
                    graphic_objects = [d for d in drawings if d['rect'].y0 >= top-1 and d['rect'].y1 <= bottom]
                    # Conservatively distinguish non-text material, including table geometry.
                    graphic_signature = []
                    for d in graphic_objects:
                        items = []
                        for item in d['items']:
                            coords = []
                            for value in item[1:]:
                                if isinstance(value, fitz.Point): coords.append([round(value.x, 1), round(value.y-top, 1)])
                                elif isinstance(value, fitz.Rect): coords.append([round(value.x0, 1), round(value.y0-top, 1), round(value.x1, 1), round(value.y1-top, 1)])
                                else: coords.append(str(value))
                            items.append([item[0], coords])
                        graphic_signature.append(items)
                    images = [i for i in page.get_image_info(hashes=True) if fitz.Rect(i['bbox']).intersects(fitz.Rect(0, top, page.rect.width, bottom))]
                    graphics_hash = hashlib.sha256(json.dumps(graphic_signature, sort_keys=True).encode()).hexdigest() if graphic_signature else ''
                    image_hashes = sorted(i['digest'].hex() for i in images)
                    orthogonal=True
                    for d in graphic_objects:
                        for item in d['items']:
                            if item[0]=='re':continue
                            if item[0]=='l' and (abs(item[1].x-item[2].x)<.5 or abs(item[1].y-item[2].y)<.5):continue
                            orthogonal=False
                    looks_like_chart=bool(re.search(r'그래프|도표|곡선|그림|도식|[XxYy]축',text))
                    graphics_kind='none' if not graphic_objects and not images else ('table_or_box' if orthogonal and not looks_like_chart and not images else 'diagram_or_image')
                    max_bottom = max(l['bbox'][3] for l in selected)
                    if graphic_objects: max_bottom = max(max_bottom, max(d['rect'].y1 for d in graphic_objects))
                    if images: max_bottom = max(max_bottom, max(i['bbox'][3] for i in images))
                    clip = [25, max(65, top-5), 570, min(bottom, max_bottom+8)]
                    qid = f'{exam}-{number:03}'
                    image_path = ROOT / 'images' / f'{qid}.webp'
                    if not image_path.exists():
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), clip=fitz.Rect(clip), alpha=False)
                        Image.frombytes('RGB', [pix.width, pix.height], pix.samples).save(image_path, format='WEBP', quality=90)
                    q = {'id': qid, 'exam': exam, 'year': info['year'], 'month': info['month'],
                         'number': number, 'subject': SUBJECTS[(number-1)//40],
                         'subject_number': (number-1)%40+1, 'source_pdf': f'sources/{question_pdf.name}',
                         'answer_pdf': f'sources/{answer_pdf.name}', 'page': pno+1, 'clip': clip,
                         'image': f'images/{qid}.webp', 'text': text, 'stem': stem,
                         'choices': choices, 'answers': answers[number],
                         'choice_parse_ok': clean_choices, 'graphics_hash': graphics_hash,
                         'graphics_kind':graphics_kind,
                         'option_order_sensitive':any(re.search(r'[①②③④ⓛ]|[1-4]\s*번|(?:위의|이상|상기).{0,5}모두',c) for c in choices),
                         'subject_instructions':subject_notes[SUBJECTS[(number-1)//40]],
                         'tax_law_year':int(tax_years[0]) if tax_years and 41<=number<=80 else None,
                         'has_graphics': bool(graphic_objects or images), 'image_hashes': image_hashes,
                         'review_flags': []}
                    if not clean_choices: q['review_flags'].append('choice_layout_requires_review')
                    if '\ufffd' in text: q['review_flags'].append('replacement_character')
                    if re.search(r'[\ue000-\uf8ff]',text):q['review_flags'].append('formula_font_use_original_image')
                    q['study_eligible']=True
                    if qid=='2024-09-063':
                        q['review_flags'].append('source_has_three_visible_choices')
                        q['study_eligible']=False
                    if len(answers[number]) > 1: q['review_flags'].append('official_multiple_answers')
                    questions.append(q)
        print(f'extracted {exam}: 120 questions', flush=True)
    assert len(questions) == 4560
    assert len({q['id'] for q in questions}) == 4560
    return questions

def content_key(q, semantic=False):
    if not q['choice_parse_ok'] or 'formula_font_use_original_image' in q['review_flags']: return None
    options=[normalize(c,semantic) for c in q['choices']]
    return (q['subject'], normalize(q['stem'], semantic),
            tuple(options if q['option_order_sensitive'] else sorted(options)),
            q['graphics_hash'] if q['graphics_kind']=='diagram_or_image' else '', tuple(q['image_hashes']))

def answer_key(q, semantic=False):
    return tuple(sorted(normalize(q['choices'][i-1], semantic) for i in q['answers']))

def groups(questions):
    # Only exact content equivalence and documented wording rules suppress entries.
    buckets = collections.defaultdict(list)
    for q in questions:
        key = content_key(q, True)
        buckets[key if key is not None else ('unparsed', q['id'])].append(q)
    entries, conflicts = [], []
    for members in buckets.values():
        by_answer = collections.defaultdict(list)
        for q in members: by_answer[answer_key(q, True) if q['choice_parse_ok'] else q['id']].append(q)
        if len(by_answer) > 1:
            conflicts.append({'kind': 'same_content_different_official_answer', 'ids': [q['id'] for q in members]})
            for q in members: q['review_flags'].append('official_answer_conflict')
        for same_answer in by_answer.values():
            rep = max(same_answer, key=lambda q: (not q['review_flags'], q['exam'], q['id']))
            for q in same_answer: q['entry_id'] = rep['id']
            exact = len({content_key(q) for q in same_answer}) == 1
            entries.append({'id': rep['id'], 'representative_id': rep['id'], 'subject': rep['subject'],
                            'occurrence_ids': sorted(q['id'] for q in same_answer),
                            'occurrence_count': len(same_answer),
                            'merge_rule': 'exact_content_or_option_permutation' if exact else 'documented_equivalent_wording',
                            'study_eligible':rep['study_eligible'],
                            'review_required': any(q['review_flags'] for q in same_answer)})
    entries.sort(key=lambda e: e['id'])
    return entries, conflicts

def variants_and_candidates(questions, entries):
    by_id = {q['id']: q for q in questions}
    # Numeric-template families require exact same nonnumeric text and geometry.
    # Tax questions are scoped to year because tax rules can change independently.
    family_buckets = collections.defaultdict(list)
    for e in entries:
        q = by_id[e['id']]
        if not q['choice_parse_ok'] or q['review_flags']:
            key = ('single', q['id'])
        else:
            options=[number_template(normalize(c,True)) for c in q['choices']]
            key = (q['subject'], (q['tax_law_year'] or q['year']) if q['subject']=='세무회계' else None,
                   number_template(normalize(q['stem'], True)),
                   tuple(options if q['option_order_sensitive'] else sorted(options)),
                   q['graphics_hash'] if q['graphics_kind']=='diagram_or_image' else '', tuple(q['image_hashes']))
        family_buckets[key].append(e)
    families = []
    for members in family_buckets.values():
        rep = max(members, key=lambda e: e['id'])
        fid = rep['id']
        for e in members: e['family_id'] = fid
        families.append({'id': fid, 'representative_entry_id': rep['id'],
                         'entry_ids': sorted(e['id'] for e in members),
                         'kind': 'numeric_variants' if len(members)>1 else 'single',
                         'subject': rep['subject']})
    # Broad recall search produces review suggestions only: no fuzzy merging.
    candidates, done = [], set()
    for subject in SUBJECTS:
        items = [e for e in entries if e['subject']==subject]
        texts = [normalize(by_id[e['id']]['text'], True) for e in items]
        vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(3,5), min_df=2, sublinear_tf=True)
        matrix = vectorizer.fit_transform(texts)
        neighbors = NearestNeighbors(n_neighbors=min(16,len(items)), metric='cosine', algorithm='brute').fit(matrix)
        distances, indices = neighbors.kneighbors(matrix)
        for i, (ds, js) in enumerate(zip(distances, indices)):
            for distance, j in zip(ds, js):
                if i==j or distance > .18: continue
                a,b=items[i],items[int(j)]
                if a['family_id']==b['family_id']: continue
                pair=tuple(sorted([a['id'],b['id']]))
                if pair in done: continue
                done.add(pair)
                qa,qb=by_id[pair[0]],by_id[pair[1]]
                same_stem=normalize(qa['stem'],True)==normalize(qb['stem'],True)
                candidates.append({'left_id':pair[0], 'right_id':pair[1], 'similarity':round(1-float(distance),4),
                                   'reason':'same_stem_changed_choices' if same_stem else 'similar_wording_or_numeric_variant',
                                   'status':'review_pending_keep_both'})
    candidates.sort(key=lambda c: (-c['similarity'], c['left_id'], c['right_id']))
    return families, candidates

def validate(questions, entries, families):
    by_id={q['id']:q for q in questions}
    occurrences=[qid for e in entries for qid in e['occurrence_ids']]
    assert len(occurrences)==len(set(occurrences))==4560
    assert set(occurrences)==set(by_id)
    member_entries=[i for f in families for i in f['entry_ids']]
    assert len(member_entries)==len(set(member_entries))==len(entries)
    for e in entries:
        members=[by_id[i] for i in e['occurrence_ids']]
        if len(members)>1:
            assert len({content_key(q,True) for q in members})==1
            assert len({answer_key(q,True) for q in members})==1
        assert e['representative_id'] in e['occurrence_ids']
    assert by_id['2026-07-026']['answers']==[1,4]
    assert by_id['2022-06-001']['entry_id']==by_id['2022-09-001']['entry_id']
    assert by_id['2024-06-001']['entry_id']!=by_id['2024-11-001']['entry_id']
    for q in questions:
        assert (ROOT/q['image']).is_file()
        assert q['clip'][1]<q['clip'][3]
        assert q['answers'] and all(1<=a<=4 for a in q['answers'])

def main():
    for folder in ['data','sources','images','reports']: (ROOT/folder).mkdir(parents=True,exist_ok=True)
    source_manifest=ROOT/'data'/'source-exams.json'
    if not source_manifest.exists():
        raise FileNotFoundError('Required portable manifest: data/source-exams.json')
    summary=json.loads(source_manifest.read_text())
    for info in summary['exams'].values():
        for key in ['question_file','answer_file']:info[key]=str(ROOT/info[key])
    portable={'exams':{exam:{**info,'question_file':f'sources/{exam}-questions.pdf','answer_file':f'sources/{exam}-answers.pdf'} for exam,info in summary['exams'].items()}}
    dump(source_manifest,portable)
    cache=ROOT/'data'/'extraction-cache-v3.json'
    exported=ROOT/'data'/'questions.json'
    if '--reextract' in sys.argv:questions=extract(summary)
    elif exported.exists():questions=json.loads(exported.read_text())
    elif cache.exists(): questions=json.loads(cache.read_text())
    else:
        questions=extract(summary)
        dump(cache,questions)
    entries,conflicts=groups(questions)
    families,candidates=variants_and_candidates(questions,entries)
    validate(questions,entries,families)
    result={'source_questions':len(questions),'bank_entries':len(entries),
            'duplicate_occurrences_suppressed':len(questions)-len(entries),
            'duplicate_groups':sum(e['occurrence_count']>1 for e in entries),
            'families':len(families),'numeric_variant_families':sum(len(f['entry_ids'])>1 for f in families),
            'review_candidate_pairs':len(candidates),'answer_conflicts':len(conflicts),
            'choice_parse_review_count':sum(not q['choice_parse_ok'] for q in questions),
            'quarantined_source_questions':sum(not q['study_eligible'] for q in questions),
            'subjects':{s:{'source_questions':sum(q['subject']==s for q in questions),
                           'entries':sum(e['subject']==s for e in entries),
                           'families':sum(f['subject']==s for f in families)} for s in SUBJECTS},
            'semantic_rules':SEMANTIC_RULES,
            'status':'conservative_dedup_complete_semantic_candidates_pending'}
    dump(ROOT/'data'/'questions.json',questions)
    dump(ROOT/'data'/'entries.json',entries)
    dump(ROOT/'data'/'families.json',families)
    dump(ROOT/'data'/'review-candidates.json',candidates)
    dump(ROOT/'data'/'answer-conflicts.json',conflicts)
    dump(ROOT/'data'/'summary.json',result)
    with (ROOT/'reports'/'출처와중복매핑.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['원본문항','과목','대표문항','유형그룹','정답','검토표시'])
        entry_by_id={e['id']:e for e in entries}
        for q in questions:writer.writerow([q['id'],q['subject'],q['entry_id'],entry_by_id[q['entry_id']]['family_id'],','.join(map(str,q['answers'])),';'.join(q['review_flags'])])
    print(json.dumps(result,ensure_ascii=False,indent=2))
    from classify_parts import main as classify
    classify()

if __name__=='__main__':main()
