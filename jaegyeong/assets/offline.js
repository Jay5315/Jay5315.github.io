// Offline status uses CacheStorage through the worker; study records are never read or changed.
(() => {
  let started;
  const SOURCE_NOTE = '원본 이미지·PDF는 최근에 온라인으로 연 자료만 일부 저장됩니다.';
  function status(state, message) {
    let node = document.getElementById('offline-status');
    if (!node) {
      node = document.createElement('p');
      node.id = 'offline-status';
      node.className = 'footer-note';
      node.setAttribute('role', 'status');
      node.setAttribute('aria-live', 'polite');
      node.style.cssText = 'flex-basis:100%;margin:0';
      (document.querySelector('.footer-inner') || document.body).append(node);
    }
    node.dataset.state = state;
    node.textContent = message;
  }
  function unavailable() {
    status('unavailable', '오프라인 저장을 완료하지 못했습니다. 인터넷 연결과 브라우저 저장 공간을 확인한 뒤 다시 접속해 주세요.');
  }
  function activate(worker) {
    return new Promise((resolve, reject) => {
      const check = () => {
        if (worker.state === 'activated') { worker.removeEventListener('statechange', check); resolve(); }
        else if (worker.state === 'redundant') { worker.removeEventListener('statechange', check); reject(new Error('Offline installation failed')); }
      };
      worker.addEventListener('statechange', check);
      check();
    });
  }
  function probe(worker) {
    return new Promise((resolve, reject) => {
      const channel = new MessageChannel();
      const timer = setTimeout(() => { channel.port1.close(); reject(new Error('Offline status unavailable')); }, 6000);
      channel.port1.onmessage = event => {
        clearTimeout(timer);
        channel.port1.close();
        resolve(event.data);
      };
      worker.postMessage({type: 'CHAGOK_OFFLINE_STATUS'}, [channel.port2]);
    });
  }
  async function start() {
    if (started) return started;
    started = (async () => {
      if (!/^https?:$/.test(location.protocol) || !('serviceWorker' in navigator)) return;
      status('preparing', '오프라인 사용 준비 중입니다. 문제·해설을 저장하고 있습니다.');
      try {
        const registration = await navigator.serviceWorker.register('sw.js'+(window.BANK_MANIFEST?'?build='+window.BANK_MANIFEST.build_id:''), {scope: './', updateViaCache: 'none'});
        const watched = new WeakSet();
        async function refresh() {
          const worker = registration.active;
          if (!worker) return;
          try {
            await activate(worker);
            if (registration.active !== worker) return;
            const result = await probe(worker);
            if (registration.active !== worker) return;
            if (result.type !== 'CHAGOK_OFFLINE_STATUS' || !result.ready || (window.BANK_MANIFEST && result.buildId !== window.BANK_MANIFEST.build_id)) { unavailable(); return; }
            status('ready', '오프라인 준비 완료 · 문제 텍스트·해설은 인터넷 없이 열 수 있습니다. ' + SOURCE_NOTE);
          } catch (_) { if (registration.active === worker) unavailable(); }
        }
        async function watch(worker) {
          if (!worker || watched.has(worker)) return;
          watched.add(worker);
          status('preparing', '오프라인 사용 준비 중입니다. 문제·해설을 저장하고 있습니다.');
          try { await activate(worker); await refresh(); } catch (_) { unavailable(); }
        }
        registration.addEventListener('updatefound', () => { watch(registration.installing); });
        navigator.serviceWorker.addEventListener('controllerchange', () => { if (!registration.installing) refresh(); });
        if (registration.installing || registration.waiting) await watch(registration.installing || registration.waiting);
        else await refresh();
      } catch (_) { unavailable(); }
    })();
    return started;
  }
  window.CHAGOK_OFFLINE = {start};
})();
