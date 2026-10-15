"""Concept-note data: structure, part links, source/status honesty, example arithmetic, bundle."""
import ast, copy, hashlib, json, operator, re, unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'data'
def read(name):return json.loads((D/(name+'.json')).read_text())
OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.USub:operator.neg}
FUNCS={'min':min,'max':max,'round':round}
def calc(expr):
    """Evaluate the small arithmetic subset used by example checks (no names, no attribute access)."""
    def ev(n):
        if isinstance(n,ast.Expression):return ev(n.body)
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)):return n.value
        if isinstance(n,ast.BinOp) and type(n.op) in OPS:return OPS[type(n.op)](ev(n.left),ev(n.right))
        if isinstance(n,ast.UnaryOp) and type(n.op) in OPS:return OPS[type(n.op)](ev(n.operand))
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in FUNCS and not n.keywords:return FUNCS[n.func.id](*map(ev,n.args))
        raise ValueError(f'unsupported expression: {ast.dump(n)}')
    return ev(ast.parse(expr,mode='eval'))
class ConceptNotesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=read('concept-notes');cls.t={p['id']:p for p in read('taxonomy')};cls.notes=cls.c['notes']
        # Notes as they were before the newest concept wording fix; earlier audits are checked on these.
        cls.wording=json.loads((R/'reports/concept-wording.json').read_text()) if (R/'reports/concept-wording.json').exists() else None
        cls.notes_before_wording=copy.deepcopy(cls.notes)
        if cls.wording:
            index={n['id']:i for i,n in enumerate(cls.notes_before_wording)}
            for r in cls.wording['notes']:cls.notes_before_wording[index[r['note_id']]]=copy.deepcopy(r['before'])
    def test_concept_wording_applies_only_listed_fixes(self):
        if not self.wording:self.skipTest('No concept wording fix')
        import sys;sys.path.insert(0,str(R/'scripts'))
        from apply_concept_wording import fix_note,PARTICLE_FIXES
        def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(self.wording['particle_fixes'],[list(x) for x in PARTICLE_FIXES])
        current={n['id']:n for n in self.notes};ids={r['note_id'] for r in self.wording['notes']}
        self.assertEqual(self.wording['count'],len(ids))
        for before in self.notes_before_wording:
            id=before['id']
            # Re-applying the fix to the earlier note must give exactly the current note.
            self.assertEqual(fix_note(before),current[id],id)
            self.assertEqual(id in ids,before!=current[id],id)
        for r in self.wording['notes']:
            self.assertEqual(digest(r['before']),r['before_hash'],r['note_id'])
            self.assertEqual(digest(current[r['note_id']]),r['after_hash'],r['note_id'])
            b,a=r['before'],current[r['note_id']]
            for k in ('id','part_id','related_part_ids','tags','sources','review_status','year_table'):
                self.assertEqual(b.get(k),a.get(k),(r['note_id'],k))
            for fb,fa in zip(b['formulas'],a['formulas']):
                for k in ('name','expression','variables'):self.assertEqual(fb.get(k),fa.get(k),r['note_id'])
    def test_structure_and_part_links(self):
        fields={'id','part_id','title','summary','key_points','formulas','pitfalls','examples','related_part_ids','tags','applicability','sources','review_status','review_note'}
        ids=[n['id'] for n in self.notes];parts=[n['part_id'] for n in self.notes]
        self.assertEqual(len(ids),len(set(ids)));self.assertEqual(len(parts),len(set(parts)),'one note per primary part')
        tags={t for e in read('entries') for t in e['classification']['tags']}
        for n in self.notes:
            self.assertLessEqual(fields,set(n),n['id']);self.assertEqual(n['id'],'note-'+n['part_id'])
            self.assertIn(n['part_id'],self.t)
            for r in n['related_part_ids']:self.assertIn(r,self.t,n['id']);self.assertNotEqual(r,n['part_id'])
            for t in n['tags']:self.assertIn(t,tags,f"{n['id']}: tag {t} is not an existing classification tag")
            self.assertTrue(n['summary'].strip() and n['key_points'],n['id'])
            for f in n['formulas']:self.assertTrue(f['expression'].strip() and isinstance(f['variables'],list),n['id'])
            if 'year_table' in n:
                yt=n['year_table']
                for row in yt['rows']:self.assertEqual(len(row),len(yt['years'])+1,n['id'])
                self.assertTrue(set(yt['years'])<=set(n['applicability']['tax_law_years'] or []),n['id'])
    def test_sources_and_status_are_honest(self):
        v=self.c['verification'];self.assertTrue(v['checked_on'] and v['method'])
        for n in self.notes:
            s=n['review_status'];self.assertIn(s,{'source_checked','partial','calc_checked','needs_source'},n['id'])
            for src in n['sources']:self.assertIn(src['ref'],self.c['sources']);self.assertTrue(src['locator'])
            unchecked=n.get('unchecked_points',[])
            flagged=any(f.get('unchecked') for f in n['formulas'])
            if s=='source_checked':
                self.assertTrue(n['sources'],f"{n['id']} claims checked sources but lists none")
                self.assertFalse(unchecked or flagged,f"{n['id']}: fully checked notes cannot carry unchecked content")
            elif s=='partial':
                self.assertTrue(n['sources'],n['id']);self.assertTrue(unchecked or flagged,f"{n['id']}: partial notes must say what was not checked")
            else:self.assertEqual(n['sources'],[],f"{n['id']}: unverified notes must not list verified sources")
            years=n['applicability']['tax_law_years']
            if self.t[n['part_id']]['subject']=='세무회계':
                self.assertEqual(s,'source_checked',f"{n['id']}: tax notes need checked law text")
                self.assertTrue(years and all(isinstance(y,int) for y in years),n['id'])
                sources=[self.c['sources'][x['ref']] for x in n['sources']]
                self.assertTrue(any(x['url'].startswith('https://www.law.go.kr/') for x in sources),
                                f"{n['id']}: Korean tax rules still need Korean law sources")
                for source in sources:
                    url=source['url']
                    if url.startswith(('https://www.law.go.kr/','https://www.nts.go.kr/')):
                        continue
                    self.assertRegex(url,r'^https://github\.com/saylordotorg/[^/]+/blob/[0-9a-f]{40}/')
                    self.assertTrue(source.get('provenance_limit'),
                                    f"{n['id']}: foreign economics material must state its limited role")
                    self.assertIn('한국',source['provenance_limit'])
                    self.assertIn('일반',source['provenance_limit'])
            else:self.assertIsNone(years,f"{n['id']}: non-tax notes must not claim a tax-law year")
            if n['part_id'].startswith('F') and s in ('source_checked','partial'):
                self.assertTrue(any(x['ref'].startswith(('KIFRS','EUIFRS')) for x in n['sources']),
                                f"{n['id']}: financial notes need an actually read standard source")
                if not any(x['ref'].startswith('KIFRS') for x in n['sources']):
                    self.assertIn('K-IFRS',n['review_note'])
                    self.assertIn('직접',n['review_note'])
                    self.assertTrue(all(self.c['sources'][x['ref']].get('provenance_limit')
                                        for x in n['sources']),n['id'])
        for k,r in self.c['sources'].items():
            self.assertTrue(r['versions'],k)
            prefix={'OSX':('https://openstax.org/books/','https://github.com/openstax/'),
                    'KIFRS':'https://www.kasb.or.kr/','SAYLOR':'https://github.com/saylordotorg/',
                    'NTS':'https://www.nts.go.kr/',
                    'MSDOCS':'https://github.com/MicrosoftDocs/',
                    'IFRSCF':'https://github.com/DhestyaSyafaAmanda/tugas-akhir-analisis-dan-desain-sistem-dhestya-syafa-amanda/blob/',
                    'COST':('https://www.accaglobal.com/','https://biz.libretexts.org/','https://ocw.mit.edu/'),
                    'EUIFRS':'https://github.com/legalize-dev/legalize-eu/blob/'}.get(k.split('_')[0],'https://www.law.go.kr/')
            domestic_course_sources = {
                'R7_CONCEPT_M03_HANYANG_ALLOCATION': 'https://contents.kocw.or.kr/KOCW/document/2014/hanyang/yisungwook/3.pdf',
                'R7_COST03_HANYANG4': 'https://contents.kocw.or.kr/KOCW/document/2014/hanyang/yisungwook/4.pdf',
                'R26_CONCEPT_HANYANG5': 'https://contents.kocw.or.kr/KOCW/document/2014/hanyang/yisungwook/5.pdf',
                'R26_CONCEPT_HANYANG2_10': 'https://contents.kocw.or.kr/KOCW/document/2014/hanyang/leeseonguk/10.pdf',
                'R7_COST06_KOCW_QUALITY2018': 'https://contents2.kocw.or.kr/KOCW/document/2018/bufs/yukgeunhyo0123/8.pdf',
                'R7_COST06_KOCW_LCC2018': 'https://contents2.kocw.or.kr/KOCW/document/2018/bufs/yukgeunhyo0123/7.pdf',
                'R26_CONCEPT_CUP8': 'https://contents2.kocw.or.kr/KOCW/data/document/2019/cup/shinsungwook0713/8.pdf',
            }
            if k in domestic_course_sources:
                prefix = domestic_course_sources[k]
                self.assertEqual(r['url'], prefix, k)
            self.assertTrue(r['url'].startswith(prefix),k)
            if k.startswith('EUIFRS'):
                self.assertRegex(r['url'],r'/blob/[0-9a-f]{40}/eu/1c/32023R1803\.md')
                self.assertTrue(r.get('original_url') and r.get('publisher') and r.get('provenance_limit'),k)
            if k.startswith('IFRSCF'):
                self.assertRegex(r['url'],r'/blob/[0-9a-f]{40}/conceptual-framework-for-financial-reporting\.pdf$')
                self.assertTrue(r.get('original_publisher') and r.get('provenance_limit'),k)
    def test_example_arithmetic(self):
        checked=0
        for n in self.notes:
            for e in n['examples']:
                self.assertTrue(e.get('checks'),f"{n['id']}: every example needs arithmetic checks")
                for c in e['checks']:
                    self.assertAlmostEqual(calc(c['expr']),c['expected'],places=6,msg=f"{n['id']} {c['label']}");checked+=1
        self.assertGreater(checked,10)
    def test_source_metadata_amendments_preserve_verified_provenance(self):
        a=json.loads((R/'reports/concept-expansion.json').read_text())
        def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        for u in a.get('source_metadata_amendments',[]):
            self.assertEqual(digest(u['before']),u['before_hash'])
            self.assertEqual(digest(self.c['sources'][u['ref']]),u['after_hash'])
            self.assertTrue(u['reason'])
            allowed={'title','versions','url','download_url'}
            self.assertEqual({k:v for k,v in u['before'].items() if k not in allowed},
                             {k:v for k,v in u['after'].items() if k not in allowed})
    def test_tax_year_values(self):
        n={x['part_id']:x for x in self.notes}
        rates=n['C11']['year_table'];self.assertEqual(rates['years'],[2024,2025,2026])
        self.assertEqual(rates['rows'][0],['2억원 이하','9%','9%','10%'])
        gross=[r for r in n['I02']['year_table']['rows'] if r[0].startswith('배당가산율')][0]
        self.assertTrue(gross[1]=='10%' and gross[2]=='10%' and gross[3].startswith('10%'),'11% gross-up starts with 2027 payments')
    def test_expansion_preserves_initial_notes_and_sources(self):
        path=R/'reports/concept-expansion.json'
        if not path.exists():self.skipTest('No concept expansion audit yet')
        a=json.loads(path.read_text())
        def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        notes=copy.deepcopy({n['id']:n for n in self.notes_before_wording})
        # Verify later enrichments first, then reconstruct the previous protected snapshots.
        for u in reversed(a.get('followup_note_amendments',[])):
            id=u['note_id'];after=notes[id];before=u['before']
            self.assertEqual(digest(after),u['after_hash'],id)
            self.assertEqual(digest(before),u['before_hash'],id)
            self.assertTrue(u['source_reads'] and u['reason'] and u['output_hash'],id)
            if u.get('stage') == 'round26_followups':
                from apply_round26_followups import validate_concept
                self.assertEqual(u['after'], after, id)
                self.assertEqual(validate_concept(u, u['independent_review'], id), u['changed_fields'], id)
                notes[id]=before
                continue
            append_fields={'key_points','formulas','examples','pitfalls','sources'}
            for field in append_fields:self.assertEqual(after[field][:len(before[field])],before[field],id)
            for field in set(before)-append_fields-{'unchecked_points','review_note','applicability'}:
                self.assertEqual(after[field],before[field],id)
            if before['applicability']!=after['applicability']:
                self.assertEqual(before['applicability']['tax_law_years'],after['applicability']['tax_law_years'],id)
                self.assertEqual(before['applicability']['year_note'],after['applicability']['year_note'],id)
                self.assertTrue(after['applicability']['basis'].startswith(before['applicability']['basis']),id)
            self.assertEqual(before['review_status'],after['review_status'])
            notes[id]=before
        upgrades={u['note_id']:u for u in a.get('source_upgrades',[])}
        for id,h in a['baseline_hashes'].items():
            if id in upgrades:
                u=upgrades[id]
                self.assertEqual(digest(u['before']),h,id)
                self.assertEqual(digest(notes[id]),u['after_hash'],id)
                self.assertEqual(u['before']['review_status'],'partial')
                self.assertTrue(u['source_reads'] and u['reason'])
                self.assertLessEqual(set(u['changed_fields']),{'sources','review_status','review_note',
                                                            'unchecked_points','formulas','examples','pitfalls'})
                for field in u['before']:
                    if field not in u['changed_fields']:self.assertEqual(notes[id][field],u['before'][field],id)
                for old,new in zip(u['before']['formulas'],notes[id]['formulas']):
                    for key in ('name','expression','variables'):self.assertEqual(old[key],new[key],id)
                for old,new in zip(u['before']['examples'],notes[id]['examples']):
                    for key in old:
                        if key!='unchecked_note':self.assertEqual(old[key],new[key],id)
                self.assertTrue(all(s in notes[id]['sources'] for s in u['before']['sources']))
            else:self.assertEqual(digest(notes[id]),h,id)
        for ref,h in a['baseline_source_hashes'].items():self.assertEqual(digest(self.c['sources'][ref]),h,ref)
        amendments={u['note_id']:u for u in a.get('source_amendments',[])}
        for id,h in a.get('followup_baseline_hashes',{}).items():
            if id not in amendments:
                self.assertEqual(digest(notes[id]),h,id)
                continue
            u=amendments[id];before=u['before'];after=notes[id]
            self.assertEqual(digest(before),h,id);self.assertEqual(digest(after),u['after_hash'],id)
            self.assertTrue(u['source_reads'] and u['reason'] and u['operations'],id)
            self.assertEqual(before['review_status'],'partial');self.assertEqual(after['review_status'],'partial')
            append_fields={'key_points','formulas','examples','pitfalls','sources'}
            for field in append_fields:self.assertEqual(after[field][:len(before[field])],before[field],id)
            for field in set(before)-append_fields-{'unchecked_points','review_note'}:
                self.assertEqual(after[field],before[field],id)
        for ref,h in a.get('followup_baseline_source_hashes',{}).items():self.assertEqual(digest(self.c['sources'][ref]),h,ref)
        self.assertEqual(a['registered_count'],len(notes))
        assigned=[id for b in a['jobs'] for id in b['assigned_part_ids']]
        self.assertEqual(len(assigned),len(set(assigned)))
        accepted={id for b in a['jobs'] for id in b['accepted_part_ids']}
        deferred={n['part_id'] for n in a['deferred']}
        self.assertFalse(accepted&deferred)
        self.assertEqual(set(assigned),accepted|deferred)
        self.assertEqual({'note-'+p for p in accepted},set(notes)-set(a['baseline_hashes']))
        for p in accepted:
            n=notes['note-'+p]
            for s in n['sources']:
                source=self.c['sources'][s['ref']]
                self.assertTrue(source.get('checked_on') and source.get('verification'),p)
    def test_bundle_contains_notes_and_keeps_questions(self):
        raw=(R/'assets/bank-data.js').read_text();b=json.loads(raw[len('window.BANK_DATA='):-2])
        self.assertEqual(b['concepts'],self.c)
        qs={q['id']:q for q in b['questions']}
        self.assertEqual(qs['2026-07-026']['answers'],[1,4]);self.assertFalse(qs['2024-09-063']['eligible'])
        self.assertTrue(all('secondary' in q for q in b['questions']))
if __name__=='__main__':unittest.main()
