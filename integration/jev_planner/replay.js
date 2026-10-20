/* Sandboxed child: only the parent may request a pause/seek. Latest pending turn wins. */
(() => {
  'use strict';
  const node = document.createElement('script');
  node.type = 'text/plain'; node.className = 'battle-log-data';
  node.textContent = JSON.parse(document.getElementById('replay-protocol').textContent);
  document.querySelector('.replay-wrapper').append(node);
  let pending = null;
  let ready = false;
  const fallback = () => {
    if (!ready) document.querySelector('.replay-wrapper').hidden = true;
  };
  window.addEventListener('error', event => {
    if (event.target?.src?.includes('/js/replay-embed.js')) fallback();
  }, true);
  setTimeout(fallback, 8000);
  const apply = () => {
    const battle = window.Replays?.battle;
    if (!battle) return;
    if (!ready) { ready = true; document.querySelector('.replay-wrapper').hidden = false; parent.postMessage({type:'planner-replay-ready'}, '*'); }
    if (pending !== null) {
      battle.pause(); battle.seekTurn(pending); battle.pause();
      document.body.dataset.selectedTurn = String(pending);
      pending = null;
    }
  };
  window.addEventListener('message', event => {
    if (event.source !== parent || event.data?.type !== 'planner-replay-seek' ||
        !Number.isInteger(event.data.turn) || event.data.turn < 0) return;
    pending = event.data.turn; apply();
  });
  // Official embed initializes after its dependent scripts load.
  const timer = setInterval(() => { apply(); if (ready) clearInterval(timer); }, 100);
  window.addEventListener('pagehide', () => clearInterval(timer));
})();
