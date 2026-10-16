// Exercise the file:// branch without changing managed browser URL policies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {pathToFileURL, fileURLToPath} = require('node:url');
const root = path.resolve(__dirname, '..');
const requested = [];
const context = {URL, console, location: {protocol: 'file:'}};
context.window = context;
context.fetch = () => { throw Error('file:// fallback must not use fetch'); };
context.document = {
  querySelectorAll: () => [],
  currentScript: {src: pathToFileURL(path.join(root, 'assets/data-loader.js')).href},
  createElement: () => ({remove() {}}),
  head: {append(node) {
    requested.push(node.src);
    assert([path.join(root, 'assets/bank-data.js'), path.join(root, 'assets/app.js')].includes(fileURLToPath(node.src)));
    assert.equal(node.integrity, undefined);
    queueMicrotask(() => {
      try { if (node.src.endsWith('/bank-data.js')) vm.runInContext(fs.readFileSync(fileURLToPath(node.src), 'utf8'), sandbox); node.onload(); }
      catch (error) { node.onerror(error); }
    });
  }}
};
const sandbox = vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'assets/data-loader.js'), 'utf8'), sandbox);
context.BANK_READY.then(async () => {
  assert.equal(context.BANK_DATA.questions.length, 4322);
  assert.equal(context.BANK_DATA.explanations.items.length, 4281);
  assert(context.BANK_DATA.explanations.items.every(n => n.option_notes.length === 4));
  await context.BANK_DATA_LOADER.all();
  await context.BANK_DATA_LOADER.explanation('2026-01-007');
  assert.equal(requested.length, 2);
  assert(requested[0].endsWith('/bank-data.js') && requested[1].endsWith('/app.js'));
  assert.equal(context.BANK_MANIFEST, undefined);
  console.log('PASS: file:// loader branch uses the complete local bundle, no fetch/manifest/subject requests.');
}).catch(error => { console.error(error); process.exitCode = 1; });
