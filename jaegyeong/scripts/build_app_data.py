"""Bundle local scripts so index.html also works via file:// without a server."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
def read(n):return json.loads((R/'data'/f'{n}.json').read_text())
def main():
 qs={q['id']:q for q in read('questions')};entries=read('entries');families=read('families')
 representatives={f['representative_entry_id'] for f in families}
 rows=[]
 for e in entries:
  q=qs[e['id']];c=e['classification']
  rows.append(dict(id=q['id'],subject=q['subject'],number=q['subject_number'],exam=q['exam'],part=c['primary_part_id'],tags=c['tags'],secondary=c.get('secondary_part_ids',[]),review=c['review_required'],graphics=q['graphics_kind'],originalOnly=('formula_font_use_original_image' in q['review_flags'] or q['graphics_kind']=='diagram_or_image'),image=q['image'],pdf=q['source_pdf'],answerPdf=q['answer_pdf'],page=q['page'],answers=q['answers'],eligible=q['study_eligible'],text=q['text'],stem=q['stem'],taxYear=q['tax_law_year'],instructions=q['subject_instructions'],representative=e['id'] in representatives,occurrences=e['occurrence_ids'],family=e['family_id']))
 concepts=read('concept-notes');part_ids={p['id'] for p in read('taxonomy')}
 for n in concepts['notes']:
  bad=[x for x in [n['part_id'],*n['related_part_ids']] if x not in part_ids]
  if bad:raise SystemExit(f"{n['id']}: unknown part ids {bad}")
  missing=[s['ref'] for s in n['sources'] if s['ref'] not in concepts['sources']]
  if missing:raise SystemExit(f"{n['id']}: unknown source refs {missing}")
 data=dict(questions=rows,parts=read('taxonomy'),summary=read('summary'),classification=read('classification-summary'),concepts=concepts)
 out=R/'assets/bank-data.js';out.write_text('window.BANK_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n')
 print(f'Bundled {len(rows)} questions, {len(concepts["notes"])} concept notes: {out.stat().st_size/1048576:.1f} MiB')
if __name__=='__main__':main()
