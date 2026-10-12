"""Concept-note data: structure, part links, source/status honesty, example arithmetic, bundle."""
import ast, json, operator, unittest
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
                self.assertTrue(all(x['ref'] in ('CIT_LAW','CIT_DECREE','PIT_LAW','VAT_LAW','VAT_DECREE') for x in n['sources']),n['id'])
            else:self.assertIsNone(years,f"{n['id']}: non-tax notes must not claim a tax-law year")
            if n['part_id'].startswith('F') and s in ('source_checked','partial'):
                self.assertTrue(any(x['ref'].startswith('KIFRS') for x in n['sources']),f"{n['id']}: financial notes must cite the K-IFRS standard they were checked against")
        for k,r in self.c['sources'].items():
            self.assertTrue(r['versions'],k)
            prefix={'OSX':'https://openstax.org/books/','KIFRS':'https://www.kasb.or.kr/'}.get(k.split('_')[0],'https://www.law.go.kr/')
            self.assertTrue(r['url'].startswith(prefix),k)
    def test_example_arithmetic(self):
        checked=0
        for n in self.notes:
            for e in n['examples']:
                self.assertTrue(e.get('checks'),f"{n['id']}: every example needs arithmetic checks")
                for c in e['checks']:
                    self.assertAlmostEqual(calc(c['expr']),c['expected'],places=6,msg=f"{n['id']} {c['label']}");checked+=1
        self.assertGreater(checked,10)
    def test_tax_year_values(self):
        n={x['part_id']:x for x in self.notes}
        rates=n['C11']['year_table'];self.assertEqual(rates['years'],[2024,2025,2026])
        self.assertEqual(rates['rows'][0],['2억원 이하','9%','9%','10%'])
        gross=[r for r in n['I02']['year_table']['rows'] if r[0].startswith('배당가산율')][0]
        self.assertTrue(gross[1]=='10%' and gross[2]=='10%' and gross[3].startswith('10%'),'11% gross-up starts with 2027 payments')
    def test_bundle_contains_notes_and_keeps_questions(self):
        raw=(R/'assets/bank-data.js').read_text();b=json.loads(raw[len('window.BANK_DATA='):-2])
        self.assertEqual(b['concepts'],self.c)
        qs={q['id']:q for q in b['questions']}
        self.assertEqual(qs['2026-07-026']['answers'],[1,4]);self.assertFalse(qs['2024-09-063']['eligible'])
        self.assertTrue(all('secondary' in q for q in b['questions']))
if __name__=='__main__':unittest.main()
