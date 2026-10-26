"""Replay test_app with fresh servers; collect evidence without changing its assertions.

Usage (repository root, development venv):
  python jaegyeong/scripts/diagnose_app_flake.py --runs 10
  python jaegyeong/scripts/diagnose_app_flake.py --prefix --cpu-rate 4 --runs 30

--prefix runs the unchanged original flow through the multiple-answer checks only;
it is NOT a full-suite pass. CPU emulation is optional and recorded separately.
The worker wraps the historical line-59 assertions in memory. Failure diagnostics
and screenshots contain synthetic test records only, and stay in _artifacts/.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/test_app.py'
ANCHOR = "  expect(page.locator('.question-text')).to_have_attribute('data-correct','1 4');expect(page.locator('.question-text')).to_have_attribute('data-picked',str(answer))"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def worker(args):
    sys.path.insert(0, str(SCRIPT.parent))
    source = SCRIPT.read_text(encoding='utf-8')
    if source.count(ANCHOR) != 1:
        raise ValueError('Historical diagnostic anchor changed; inspect the test before adapting')
    instrumentation = ''' page.on('pageerror',lambda e:errors.append(str(e)))
 diagnostic_console=[]
 page.on('console',lambda m:diagnostic_console.append({'type':m.type,'text':m.text}))
 page.add_init_script("""window.__appDiagnostic=[]; for(const type of ['keydown','hashchange','focusin']) window.addEventListener(type,e=>{window.__appDiagnostic.push({type,time:performance.now(),key:e.key,hash:location.hash,target:e.target?.tagName});if(window.__appDiagnostic.length>80)window.__appDiagnostic.shift();},true);""")
'''
    if args.cpu_rate != 1:
        instrumentation += f" page.context.new_cdp_session(page).send('Emulation.setCPUThrottlingRate',{{'rate':{args.cpu_rate!r}}})\n"
    source = source.replace(" page.on('pageerror',lambda e:errors.append(str(e)))", instrumentation.rstrip(), 1)
    wrapped = '''  try:
   ORIGINAL_ASSERTIONS
  except Exception as diagnostic_error:
   diagnostic=page.evaluate("""()=>({questions:[...document.querySelectorAll('.question-text')].map(e=>({inMain:!!e.closest('#main'),inModal:!!e.closest('#modal'),attributes:[...e.attributes].map(a=>[a.name,a.value]),text:e.innerText})),dialogs:[...document.querySelectorAll('dialog')].map(e=>({open:e.open,text:e.innerText})),hash:location.hash,focus:document.activeElement.outerHTML,active:JSON.parse(localStorage.getItem('chagok.study.v1'))?.active,events:window.__appDiagnostic})""")
   diagnostic.update(error=str(diagnostic_error),console=diagnostic_console,pageerrors=errors,answer=answer)
   (ARTIFACTS/'failure-state.json').write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2))
   page.screenshot(path=str(ARTIFACTS/'failure.png'),full_page=True)
   raise'''.replace('ORIGINAL_ASSERTIONS', ANCHOR.strip())
    source = source.replace(ANCHOR, wrapped)
    if args.prefix:
        marker = " goto('library');page.locator('#library-query').fill('2024-09-063')"
        source = source[:source.index(marker)] + " browser.close()\n print('PASS: original flow through multi-answer checks ONLY')\n"
    exec(compile(source, str(SCRIPT), 'exec'), {'__file__': str(SCRIPT), '__name__': '__main__'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--port', type=int, default=8055)
    parser.add_argument('--prefix', action='store_true')
    parser.add_argument('--cpu-rate', type=float, default=1)
    parser.add_argument('--output-dir', type=Path, default=ROOT / '_artifacts/app-flake')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.runs < 1 or args.cpu_rate < 1 or not 1 <= args.port <= 65535:
        parser.error('positive runs, CPU rate >= 1 and valid TCP port required')
    if args.worker:
        worker(args)
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))  # Never stop or reuse another server.
    summary = {'mode': 'prefix_only' if args.prefix else 'full_test_app',
               'cpu_rate': args.cpu_rate, 'server_restarted_each_run': True,
               'test_app_sha256': hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
               'historical_root_cause_proven': False, 'runs': []}
    for number in range(1, args.runs + 1):
        folder = args.output_dir / f'run-{number:02}'
        folder.mkdir(exist_ok=False)
        with (folder / 'server.log').open('w') as server_log:
            server = subprocess.Popen([sys.executable, '-m', 'http.server', str(args.port), '--bind', '127.0.0.1'],
                                      cwd=ROOT.parent, stdout=server_log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while True:
                    try:
                        with socket.create_connection(('127.0.0.1', args.port), timeout=.1):
                            break
                    except OSError:
                        if server.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError('Fresh test server failed to become ready')
                        time.sleep(.01)  # TCP readiness polling, not an app/test delay.
                command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--cpu-rate', str(args.cpu_rate)]
                if args.prefix:
                    command.append('--prefix')
                environment = dict(os.environ, APP_BASE_URL=f'http://127.0.0.1:{args.port}/jaegyeong/', TEST_ARTIFACT_DIR=str(folder.resolve()))
                started = time.monotonic()
                with (folder / 'test.log').open('w') as log:
                    result = subprocess.run(command, cwd=ROOT.parent, env=environment,
                                            stdout=log, stderr=subprocess.STDOUT, timeout=900)
                row = {'run': number, 'server_pid': server.pid, 'returncode': result.returncode,
                       'seconds': round(time.monotonic() - started, 3), 'artifact_directory': str(folder)}
                summary['runs'].append(row)
                summary['consecutive_passes'] = sum(r['returncode'] == 0 for r in summary['runs'])
                write(args.output_dir / 'results.json', summary)
                print(json.dumps(row), flush=True)
                if result.returncode:
                    raise SystemExit(result.returncode)
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == '__main__':
    main()
