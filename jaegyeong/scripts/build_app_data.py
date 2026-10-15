"""Bundle local scripts so index.html also works via file:// without a server."""
from pathlib import Path
import json
from explanation_data import validate_explanations
from choice_breaks import corpus_counts,choice_breaks
R=Path(__file__).resolve().parents[1]
def read(n):return json.loads((R/'data'/f'{n}.json').read_text())
def amend_adjudication_evidence(records, amendments):
 """Replay approved text-only changes without mutating historical records."""
 result=[dict(record) for record in records]
 by_id={record['question_id']:record for record in result};seen=set()
 for amendment in amendments:
  id=amendment['question_id'];record=by_id.get(id)
  if id in seen or not record:
   raise ValueError(f'{id}: duplicate/unknown evidence correction')
  seen.add(id)
  if record['verdict']!=amendment['verdict'] or record['evidence']!=amendment['before_evidence'] or not amendment['after_evidence']:
   raise ValueError(f'{id}: stale/empty evidence correction')
  record['evidence']=amendment['after_evidence']
 return result
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
 explanations=validate_explanations(read('explanations'),qs,{e['id'] for e in entries},part_ids)
 audit=json.loads((R/'reports/explanation-expansion.json').read_text())
 adjudication_log=audit.get('answer_adjudication',{})
 # Evidence corrections preserve original records. Apply them before later
 # resolutions, whose independently reviewed verdict/evidence takes priority.
 adjudication=amend_adjudication_evidence(
  adjudication_log.get('records',[])+adjudication_log.get('explained_item_records',[]),
  audit.get('round21_inspections',{}).get('evidence_amendments',[]))
 resolved={r['question_id']:r for r in adjudication_log.get('resolutions',[])}
 adjudication=[dict(a,verdict=resolved[a['question_id']]['verdict'],evidence=resolved[a['question_id']]['evidence']) if a['question_id'] in resolved else a for a in adjudication]
 labels={'official_conflict':'공식 정답 이의 가능','multiple_candidates':'정답 후보가 둘 이상','ambiguous_wording':'문항 표현이 모호','deferred':'근거 보완 필요'}
 answer_notes={}
 for a in adjudication:
  if a['verdict'] not in labels:continue
  q=qs.get(a['question_id'])
  if not q or q['answers']!=a['official_answers']:raise SystemExit(f"{a['question_id']}: adjudication does not match official answer")
  answer_notes[a['question_id']]=dict(kind=a['verdict'],label=labels[a['verdict']],text=a['evidence'])
 def source_basis(source):
  u=' '.join(source.get(k) or '' for k in ('url','mirror_url','original_url')).lower()
  if any(x in u for x in ('kasb.or.kr','law.go.kr','legalize-kr/legalize-kr','precedent-kr','nts.go.kr','gwanbo')):return 'domestic'
  if any(x in u for x in ('ifrs.org','legalize-eu','tyefraser','agd-assb')):return 'ifrs'
  return 'textbook'
 rank={'domestic':0,'ifrs':1,'textbook':2}
 explanation_basis={n['question_id']:min((source_basis(explanations['sources'][s['ref']]) for s in n['sources']),key=rank.get) for n in explanations['items']}
 texts=[q['text'] for q in qs.values()]+[s for n in explanations['items'] for s in [n['summary'],*n['steps'],*[o['reason'] for o in n['option_notes']]]]
 words,pairs=corpus_counts(texts)
 breaks={r['id']:b for r in rows if (b:=choice_breaks(r['text'],words,pairs))}
 data=dict(answerNotes=answer_notes,choiceBreaks=breaks,explanationBasis=explanation_basis,questions=rows,parts=read('taxonomy'),summary=read('summary'),classification=read('classification-summary'),concepts=concepts,explanations=explanations)
 out=R/'assets/bank-data.js';out.write_text('window.BANK_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n')
 print(f'Bundled {len(rows)} questions, {len(concepts["notes"])} concept notes, {len(explanations["items"])} explanations: {out.stat().st_size/1048576:.1f} MiB')
if __name__=='__main__':main()
