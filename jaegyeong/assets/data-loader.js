'use strict';
(() => {
  const base = new URL('../', document.currentScript.src);
  document.querySelectorAll('.appbar button').forEach(button => { button.disabled = true; });
  const loading = new Map();
  let manifest;
  const integrity = hex => 'sha256-' + btoa(hex.match(/../g).map(x => String.fromCharCode(parseInt(x, 16))).join(''));
  function script(spec) {
    return new Promise((resolve, reject) => {
      const node = document.createElement('script');
      node.src = new URL(spec.url, base).href;
      if (spec.sha256) { node.integrity = integrity(spec.sha256); node.crossOrigin = 'anonymous'; }
      node.onload = () => { node.remove(); resolve(); };
      node.onerror = () => { node.remove(); reject(new Error('학습 자료를 불러오지 못했습니다.')); };
      document.head.append(node);
    });
  }
  function validSpec(spec) {
    return spec && /^assets\/bank\/[a-z-]+-[a-f0-9]{16}\.js$/.test(spec.url) && /^[a-f0-9]{64}$/.test(spec.sha256);
  }
  const ready = (async () => {
    if (location.protocol === 'file:') {
      await script({url: 'assets/bank-data.js'});
      return window.BANK_DATA;
    }
    const response = await fetch(new URL('assets/bank-manifest.json', base), {cache: 'no-cache'});
    if (!response.ok) throw new Error('학습 자료 목록을 불러오지 못했습니다.');
    manifest = await response.json();
    if (manifest.format !== 1 || !/^[a-f0-9]{20}$/.test(manifest.build_id) || !validSpec(manifest.core) ||
        !['finance', 'tax', 'cost'].every(k => validSpec(manifest.subjects?.[k]))) throw new Error('학습 자료 판본이 올바르지 않습니다.');
    window.BANK_MANIFEST = manifest;
    await script(manifest.core);
    if (!window.BANK_DATA?.questions || !window.BANK_DATA.explanations?.items) throw new Error('학습 자료가 비어 있습니다.');
    return window.BANK_DATA;
  })();
  async function subject(code) {
    await ready;
    if (!manifest) return;
    if (loading.has(code)) return loading.get(code);
    const pending = (async () => {
      const spec = manifest.subjects[code];
      if (!spec) throw new Error('과목을 찾을 수 없습니다.');
      await script(spec);
      const payload = window.BANK_CHUNKS?.[spec.url];
      const data = window.BANK_DATA, byId = new Map(data.explanations.items.map(n => [n.question_id, n]));
      const expected = data.explanations.items.filter(n => manifest.part_subjects[n.part_id] === code);
      if (!payload || payload.items.length !== expected.length || new Set(payload.items.map(n => n.question_id)).size !== expected.length ||
          payload.items.some(n => !byId.has(n.question_id) || manifest.part_subjects[n.part_id] !== code || !Array.isArray(n.option_notes))) {
        throw new Error('해설 자료의 문항 구성이 일치하지 않습니다.');
      }
      Object.assign(data.explanations.sources, payload.sources);
      payload.items.forEach(n => Object.assign(byId.get(n.question_id), n));
      delete window.BANK_CHUNKS[spec.url];
    })();
    loading.set(code, pending);
    try { await pending; } catch (error) { loading.delete(code); throw error; }
  }
  window.BANK_DATA_LOADER = {
    async explanation(id) {
      await ready;
      const note = window.BANK_DATA.explanations.items.find(n => n.question_id === id);
      if (note && !note.option_notes) await subject(manifest.part_subjects[note.part_id]);
    },
    async all() { await ready; if (manifest) await Promise.all(Object.keys(manifest.subjects).map(subject)); }
  };
  // Attach an early rejection handler; app.js supplies the visible retry UI after DOM setup.
  ready.catch(() => {});
  window.BANK_READY = ready;
  // A build-specific URL and SRI prevent an older cached app from consuming a new index.
  ready.then(() => script(manifest
    ? {url: 'assets/app.js?build=' + manifest.build_id, sha256: manifest.runtime['assets/app.js'].sha256}
    : {url: 'assets/app.js'})).catch(() => {
      const main = document.getElementById('main');
      let record = null;
      try { record = localStorage.getItem('chagok.study.v1'); } catch (_) {}
      main.innerHTML = '<div class="empty"><h1>문제은행을 다시 불러와 주세요</h1><p>자료를 불러오지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.</p><button class="btn primary" id="retry-bank">다시 불러오기</button>' +
        (record ? '<p>학습 기록은 이 브라우저에 그대로 있습니다. 필요하면 지금 내려받아 둘 수 있습니다.</p><button class="btn" id="export-record">학습 기록 내려받기</button>' : '') + '</div>';
      document.getElementById('retry-bank').onclick = () => location.reload();
      // app.js is not running, so the footer backup button needs its own minimal fallback.
      const exportRecord = () => {
        const url = URL.createObjectURL(new Blob([record], {type: 'application/json'})), link = document.createElement('a');
        link.href = url; link.download = '차곡-학습기록-' + new Date().toISOString().slice(0, 10) + '.json'; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      };
      const footerButton = document.querySelector('footer [data-action="settings"]');
      if (record) {
        document.getElementById('export-record').onclick = exportRecord;
        if (footerButton) footerButton.onclick = exportRecord;
      } else if (footerButton) footerButton.disabled = true;
    });
})();
