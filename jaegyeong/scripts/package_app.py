"""Create portable runtime and full-source archives, validating bundled references."""
from pathlib import Path
import json,zipfile
R=Path(__file__).resolve().parents[1]
DIST=R/'dist'
DIST.mkdir(exist_ok=True)
bundle=(R/'assets/bank-data.js').read_text();data=json.loads(bundle.removeprefix('window.BANK_DATA=').strip().removesuffix(';'))
assert len(data['questions'])==4322
assert sum(q['eligible'] and q['representative'] for q in data['questions'])==4144
for q in data['questions']:
 for key in ['image','pdf','answerPdf']:assert (R/q[key]).is_file(),(q['id'],key)
for filename,full in [('chagok-webapp.zip',False),('jaegyeong-question-bank.zip',True)]:
 target=DIST/filename;prefix='chagok-webapp' if not full else R.name
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(R.rglob('*')):
   if not p.is_file() or p.relative_to(R).parts[0] in ['dist','_artifacts','.venv'] or '__pycache__' in p.parts or p.name.startswith('extraction-cache') or p.name=='build.log':continue
   rel=p.relative_to(R)
   if full or rel.parts[0] in ['assets','images','sources'] or str(rel) in ['index.html','sw.js','실행방법.txt']:
    z.write(p,Path(prefix)/rel)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  assert f'{prefix}/index.html' in z.namelist()
  assert f'{prefix}/assets/app.js' in z.namelist()
  plan=json.loads((R/'assets/bank-manifest.json').read_text())
  for name in ['assets/data-loader.js','assets/offline.js','assets/bank-manifest.json','sw.js',plan['core']['url'],*[s['url'] for s in plan['subjects'].values()]]:
   assert f'{prefix}/{name}' in z.namelist(),name
  for q in data['questions']:
   for key in ['image','pdf','answerPdf']:assert f'{prefix}/{q[key]}' in z.namelist()
 print(f'{target}: {target.stat().st_size/1048576:.1f} MiB, CRC and all question assets verified',flush=True)
