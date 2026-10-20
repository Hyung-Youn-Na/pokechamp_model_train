/* All original values enter the DOM as text nodes, never executable markup. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('viewer-data').textContent);
  const app = document.getElementById('app');
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  };
  const link = (label, href) => {
    const node = element('a', label);
    node.setAttribute('href', href);
    return node;
  };
  const pretty = value => JSON.stringify(value, null, 2);
  const number = value => value === null || value === undefined ? '미확인' : Number(value).toLocaleString('ko-KR', {maximumFractionDigits: 3});
  const percentage = value => value === null || value === undefined ? '미산출' : `${(value * 100).toFixed(2)}%`;
  const event = (decision, type) => decision.records.find(row => row.type === type);
  const candidateLabel = (payload, key, description) =>
    typeof description?.display_name === 'string' && description.display_name.trim()
      ? description.display_name : actionLabel(payload, key, description);
  const original = (container, title, value, filename, open = false) => {
    const details = element('details');
    details.open = open;
    details.append(element('summary', title));
    const tools = element('div', undefined, 'toolbar');
    const copy = element('button', '복사');
    const download = element('button', '다운로드');
    const status = element('span', '', 'status');
    tools.append(copy, download, status);
    const text = typeof value === 'string' ? value : (pretty(value) ?? '미제공');
    const pre = element('pre');
    pre.dataset.original = filename;
    // Tokenization only adds safe spans; .textContent stays byte-for-byte equal
    // to the JSON/text shown by the copy and download controls.
    if (typeof value === 'string') pre.textContent = text;
    else {
      const tokens = /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
      let start = 0;
      for (const match of text.matchAll(tokens)) {
        pre.append(document.createTextNode(text.slice(start, match.index)));
        const token = match[0];
        const kind = token.startsWith('"') ? (token.endsWith(':') ? 'key' : 'string') : (/^(true|false|null)$/.test(token) ? 'literal' : 'number');
        pre.append(element('span', token, `json-${kind}`));
        start = match.index + token.length;
      }
      pre.append(document.createTextNode(text.slice(start)));
    }
    copy.addEventListener('click', async () => {
      try {
        if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
        else {
          const area = element('textarea');
          area.value = text;
          area.style.position = 'fixed';
          area.style.left = '-10000px';
          document.body.append(area);
          area.select();
          const copied = document.execCommand('copy');
          area.remove();
          if (!copied) throw new Error('clipboard unavailable');
        }
        status.textContent = '복사됨';
      } catch (_) { status.textContent = '복사를 허용하거나 다운로드를 이용하세요.'; }
    });
    download.addEventListener('click', () => {
      const url = URL.createObjectURL(new Blob([text], {type: typeof value === 'string' ? 'text/plain;charset=utf-8' : 'application/json;charset=utf-8'}));
      const anchor = link('', url);
      anchor.download = filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    details.append(tools, pre);
    container.append(details);
    return details;
  };
  const table = (parent, headings, rows) => {
    const scroll = element('div', undefined, 'scroll');
    const node = element('table');
    const head = element('tr');
    headings.forEach(text => head.append(element('th', text)));
    const thead = element('thead');
    thead.append(head);
    const body = element('tbody');
    rows.forEach(row => {
      const tr = element('tr');
      row.forEach(value => {
        const td = element('td');
        td.append(value instanceof Node ? value : document.createTextNode(String(value)));
        tr.append(td);
      });
      body.append(tr);
    });
    node.append(thead, body);
    scroll.append(node);
    parent.append(scroll);
    return body;
  };
  const summary = (parent, metrics) => {
    const f = metrics.failures;
    parent.append(element('p', `예정 ${f.planned} · 완료 ${f.completed} · 실패 ${f.failed} · 미실행 ${f.unattempted} · 시도 중 실패율 ${percentage(f.failure_rate)}`));
    table(parent, ['역할', '논리 호출', 'HTTP 시도', '입력 토큰 (기록분)', '출력 토큰 (기록분)', '평균 응답 지연'], ['planner', 'executor'].map(role => {
      const value = metrics[role];
      const input = value.tokens.input;
      const output = value.tokens.output;
      return [role, value.logical_calls, `${value.http_attempts} · 모의 ${value.simulated_http_attempts} (원장 없는 호출 ${value.calls_without_http_ledger})`,
        `${number(input.total)} / 미확인 ${input.unknown_records}건`, `${number(output.total)} / 미확인 ${output.unknown_records}건`, `${number(value.latency_seconds.mean)}초`];
    }));
    if (metrics.simulated) parent.append(element('p', '모의 usage·지연·비용은 기술 검증용 기록이며 실제 공급자 사용량이 아닙니다.', 'muted'));
    const score = metrics.battle_score || metrics.technical_battle_score;
    if (score) parent.append(element('p', `${metrics.battle_score ? '실제 배틀 기술통계' : '모의 배틀 종료 결과 · 효능 근거 아님'}: ${score.wins}승 ${score.draws}무 ${score.losses}패 · ${score.denominator}경기 · 평균 점수 ${percentage(score.mean_score)}`));
    parent.append(element('p', `계획 재사용 ${metrics.planner.decisions_reusing_plan}결정 · 계획 경과 평균 ${number(metrics.planner.plan_age_turns.mean)}턴 · 단일 후보 자동 선택 ${metrics.automatic_selections} · 요청 재사용 기록 ${metrics.cached_selection_records}`, 'muted'));
  };
  const mode = data.mode === 'mock' ? '모의 실행 · simulated' : '실제 모델 실행';
  document.getElementById('mode').append(element('span', mode, 'badge'), document.createTextNode(data.kind === 'trace' ? '저장 궤적의 입력·호출 검증 · 배틀 성능 미평가' : data.mode === 'mock' ? '로컬 연결 기술 검증 · 모델 성능 미평가' : '새 배틀 기록'));
  document.getElementById('title').textContent = `${data.run_id || ''} · ${data.condition || 'Planner–JEV 조건 비교'}${data.battle ? ` · ${data.battle}` : ''}`;
  (data.backlinks || []).forEach(item => document.getElementById('navigation').append(link(item.label, item.href)));
  if (data.page === 'run') {
    table(app, ['조건', 'Planner 호출', 'JEV 호출', '완료 / 예정', '유형'], data.links.map(item => [
      link(item.label, item.href), item.summary.planner.logical_calls, item.summary.executor.logical_calls,
      `${item.summary.failures.completed} / ${item.summary.failures.planned}`, item.summary.interpretation]));
    const statuses = {compatible:'비교 가능', technical_only:'기술 비교만 가능', incompatible:'조건 불일치', confounded:'여러 축 변경', identical_settings:'동일 설정'};
    if (data.comparison.contrasts.length) {
      app.append(element('h2', '비교 가능한 설정과 공통 완료쌍'));
      table(app, ['대비', '판정', '변경 축 / 불일치', '공통 완료쌍', '오른쪽 − 왼쪽'], data.comparison.contrasts.map(row => [
        `${row.left} → ${row.right}`, statuses[row.status] || row.status,
        [...row.differences, ...row.reasons].join(', '), row.paired?.common_completed_pairs ?? '미산출',
        row.paired ? percentage(row.paired.mean_difference_right_minus_left) : '미산출']));
    }
    original(app, '비교 집계 원문', data.comparison, 'comparison.json');
    original(app, '동결 manifest · 설정·프롬프트·코드 identity', data.manifest, 'manifest.json');
    app.append(element('h2', '원자료 복사본'));
    const list = element('ul');
    data.originals.forEach(item => { const li = element('li'); li.append(link(item.label, item.href)); list.append(li); });
    app.append(list, link('원본·복사본 해시 및 분모', 'provenance.json'));
    return;
  }
  if (data.page === 'condition') {
    summary(app, data.summary);
    app.append(element('h2', '경기·저장 궤적 목록'));
    table(app, ['경기 / 궤적', '결정 수', '종료 기록'], data.links.map(item => [link(item.label, item.href), item.decisions,
      item.outcomes.length ? item.outcomes.map(row => `${row.status} / ${row.outcome ?? '미확인'}`).join(', ') : '저장 궤적 또는 종료 원문 참조']));
    original(app, '호출 정책·프롬프트·모델 설정', data.config, 'condition-config.json');
    original(app, '조건별 집계', data.summary, 'summary.json');
    original(app, '예정·완료·실패·미실행 원장', data.outcomes, 'outcomes.json');
    app.append(link('이 조건의 전체 events.jsonl', data.raw_events));
    return;
  }
  const decisions = data.decisions;
  const cache = new Map(), pending = new Map();
  window.plannerPacket = (key, value) => {
    const task = pending.get(key);
    if (!task) return;
    cache.set(key, value);
    while (cache.size > 8) cache.delete(cache.keys().next().value);
    task.resolve(value);
  };
  const load = ref => {
    if (cache.has(ref.key)) return Promise.resolve(cache.get(ref.key));
    if (pending.has(ref.key)) return pending.get(ref.key).promise;
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    const script = element('script');
    const finish = fn => value => { pending.delete(ref.key); script.remove(); fn(value); };
    pending.set(ref.key, {promise, resolve:finish(resolve), reject:finish(reject)});
    script.onerror = () => pending.get(ref.key)?.reject(new Error('로컬 자료를 열 수 없습니다. 폴더 전체를 함께 이동하세요.'));
    script.onload = () => pending.get(ref.key)?.reject(new Error('결정 자료 연결이 일치하지 않습니다.'));
    script.src = ref.src; document.head.append(script);
    return promise;
  };
  const button = (text, action) => {
    const node = element('button', text); node.addEventListener('click', action); return node;
  };
  const controls = element('div', undefined, 'toolbar');
  const turnSelect = element('select'), select = element('select');
  turnSelect.setAttribute('aria-label', '턴 선택'); select.setAttribute('aria-label', '결정 선택');
  const turns = [...new Set([...(data.turn_log?.turns || []).map(t => t.turn), ...decisions.map(d => d.turn ?? 0)])].sort((a,b) => a-b);
  if (!turns.length) turns.push(0);
  for (const turn of turns) { const o = element('option', `${turn}턴`); o.value = turn; turnSelect.append(o); }
  let current = decisions.length ? 0 : -1, selectedTurn = decisions[0]?.turn ?? turns[0], active = 'plan', epoch = 0;
  const previous = button('← 이전 결정', () => choose(current < 0 ? decisions.findLastIndex(d => d.turn < selectedTurn) : current - 1));
  const next = button('다음 결정 →', () => choose(current < 0 ? decisions.findIndex(d => d.turn > selectedTurn) : current + 1));
  const matches = (data.matches || []).map(m => ({...m}));
  if (matches.length) {
    const matchSelect = element('select'); matchSelect.setAttribute('aria-label', '경기 선택');
    for (const m of matches) { const o = element('option', m.label); o.value = m.href; o.selected = m.label === data.battle; matchSelect.append(o); }
    matchSelect.onchange = () => { location.href = matchSelect.value; }; controls.append(matchSelect);
  }
  controls.append(previous, turnSelect, select, next); app.append(controls);
  const overview = element('section', undefined, 'card'); overview.setAttribute('aria-live', 'polite'); app.append(overview);
  const layout = element('div', undefined, 'battle-layout'), left = element('section', undefined, 'information');
  const tabs = element('div', undefined, 'tabs'); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', '결정 정보');
  const panels = element('section'); panels.id = 'decision-panel'; panels.setAttribute('role', 'tabpanel'); panels.tabIndex = 0;
  const tabNames = {plan:'GLM 계획', request:'JEV 요청', response:'JEV 응답', state:'상태·후보', log:'턴 로그', damage:'Damage-calc', technical:'기술 기록'};
  const tabButtons = [];
  for (const [key, label] of Object.entries(tabNames)) {
    const b = button(label, () => { active = key; render(); }); b.id = `tab-${key}`;
    b.setAttribute('role', 'tab'); b.setAttribute('aria-controls', panels.id); b.dataset.tab = key;
    b.addEventListener('keydown', e => {
      const i = tabButtons.indexOf(b); let j;
      if (e.key === 'ArrowRight') j = (i + 1) % tabButtons.length;
      if (e.key === 'ArrowLeft') j = (i + tabButtons.length - 1) % tabButtons.length;
      if (e.key === 'Home') j = 0;
      if (e.key === 'End') j = tabButtons.length - 1;
      if (j !== undefined) { e.preventDefault(); tabButtons[j].focus(); tabButtons[j].click(); }
    });
    tabs.append(b); tabButtons.push(b);
  }
  left.append(tabs, panels);
  const replay = element('aside', undefined, 'replay card');
  replay.append(element('h2', '배틀 리플레이'));
  replay.append(element('p', '애니메이션은 공식 Showdown 외부 자산을 사용합니다. 외부 연결 실패 시 아래 로컬 공개 로그를 열 수 있습니다.', 'muted'));
  const frame = element('iframe'); frame.title = '배틀 리플레이'; frame.setAttribute('sandbox', 'allow-scripts'); frame.referrerPolicy = 'no-referrer';
  const sync = () => frame.contentWindow?.postMessage({type:'planner-replay-seek', turn:selectedTurn}, '*');
  const align = button('선택한 턴으로 이동', sync); replay.append(align);
  frame.addEventListener('load', sync);
  window.addEventListener('message', e => { if (e.source === frame.contentWindow && e.data?.type === 'planner-replay-ready') sync(); });
  frame.src = data.replay + '#embedded'; replay.append(frame);
  const rawLog = (data.turn_log?.turns || []).flatMap(t => t.rows).map(r => r.protocol).join('\n');
  original(replay, '로컬 공개 로그 · 외부 자산 없이 열람', rawLog || '저장된 공개 리플레이가 없습니다.', 'showdown.log');
  layout.append(left, replay); app.append(layout);
  const rowNow = () => current >= 0 ? decisions[current] : null;
  function choose(index) {
    if (index < 0 || index >= decisions.length) return;
    current = index; selectedTurn = decisions[current].turn ?? 0; updateControls(); sync(); render();
  }
  function updateControls() {
    turnSelect.value = String(selectedTurn); select.replaceChildren();
    decisions.forEach((row, index) => {
      if ((row.turn ?? 0) !== selectedTurn) return;
      const o = element('option', `${index + 1}. ${row.actor ?? '?'} · ${row.overview.decision_kind ?? '행동'} · ${row.id}`);
      o.value = index; select.append(o);
    });
    if (current < 0) { const o = element('option', '이 턴에는 결정이 없습니다.'); o.value = -1; select.append(o); }
    select.value = String(current); select.disabled = current < 0;
    previous.disabled = current === 0 || (current < 0 && !decisions.some(d => d.turn < selectedTurn));
    next.disabled = current === decisions.length - 1 && current >= 0 || (current < 0 && !decisions.some(d => d.turn > selectedTurn));
  }
  turnSelect.onchange = () => {
    selectedTurn = Number(turnSelect.value); current = decisions.findIndex(d => (d.turn ?? 0) === selectedTurn);
    updateControls(); sync(); render();
  };
  select.onchange = () => choose(Number(select.value));
  document.addEventListener('keydown', e => {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.target.closest('input,textarea,select,button,[contenteditable="true"],[role="tab"]')) return;
    if (e.key === 'ArrowLeft' && !previous.disabled) { e.preventDefault(); previous.click(); }
    if (e.key === 'ArrowRight' && !next.disabled) { e.preventDefault(); next.click(); }
  });
  function logPanel(row) {
    const part = data.turn_log?.turns.find(t => t.turn === selectedTurn);
    const cutoff = row && data.turn_log?.decision_cutoffs[row.id];
    const check = element('input'); check.type = 'checkbox'; check.disabled = !cutoff;
    const label = element('label'); label.append(check, document.createTextNode('선택한 결정 전까지'));
    panels.append(label);
    const target = element('div'); panels.append(target);
    const show = () => {
      target.replaceChildren();
      const rows = (part?.rows || []).filter(r => !check.checked || r.sequence < cutoff.sequence || r.sequence === cutoff.sequence && r.line_index <= cutoff.line_index);
      if (!cutoff) target.append(element('p', row ? '정확한 결정 cutoff 미기록 · 결정 전 보기 불가' : '결정 없는 턴 · 공개 사건만 표시', 'muted'));
      original(target, `${selectedTurn}턴 공개 사건`, rows.map(r => r.text || r.protocol).join('\n'), 'turn-log.txt', true);
      original(target, '공개 protocol · 원래 행 좌표', rows, 'turn-log.json');
    };
    check.onchange = show; show();
  }
  function planPanel(row, records) {
    const policy = row.overview.policy;
    const attempts = records.filter(r => r.type === 'planner_output_attempt');
    const retries = records.filter(r => r.type === 'planner_json_retry');
    const formats = records.filter(r => r.type === 'planner_format_retry');
    if (attempts.length) {
      panels.append(element('p', `GLM 생성 ${attempts.length}회 · JSON 구문 재시도 ${retries.length}회 · 기타 형식 재시도 ${formats.length}회`));
      original(panels, 'GLM 생성별 원문 · 형식 오류·reasoning·usage', attempts, 'planner-output-attempts.json');
    }
    panels.append(element('p', `호출 사유: ${(policy.reasons || []).join(', ') || '미기록'}`));
    if (row.applied_plan) {
      const ap = row.applied_plan;
      panels.append(element('p', `생성 ${ap.turn}턴 · 경과 ${selectedTurn - ap.turn}턴 · ${ap.decision === row.id ? '현재 결정에서 생성' : '이전 계획 재사용'}`));
      if (ap.index) panels.append(button(`적용 계획 생성 결정 ${ap.index} · ${ap.turn}턴`, () => choose(ap.index - 1)));
      const labels = {objective:'목표', priorities:'우선순위', preserve:'보존 대상', threats:'위협', tera_policy:'테라 방침', contingencies:'조건별 대응'};
      for (const [key, label] of Object.entries(labels)) {
        panels.append(element('h3', label));
        const value = ap.plan?.[key]; panels.append(element('pre', value === undefined ? '미제공' : typeof value === 'string' ? value : pretty(value)));
      }
      original(panels, '현재 적용 전략 계획', ap.plan, 'applied-plan.json');
    } else panels.append(element('p', '적용 계획 없음'));
    const originals = element('div'); panels.append(originals);
    const showOriginals = (source, reused) => {
      if (reused) originals.append(element('p', '아래 원문은 계획 생성 결정의 기록입니다. 현재 결정은 GLM 미호출입니다.', 'muted'));
      const request = source.find(r => r.type === 'planner_request'), response = source.find(r => r.type === 'planner_response');
      if (request) original(originals, 'GLM 실제 요청 messages', request.messages, 'planner-messages.json');
      if (response) {
        original(originals, 'GLM 실제 응답 원문', response.content, 'planner-content.txt');
        if (response.reasoning != null) original(originals, 'GLM reasoning · JEV에는 전달하지 않음', response.reasoning, 'planner-reasoning.txt');
        original(originals, 'GLM 응답 기록 · usage 포함', response, 'planner-response.json');
      }
      if (!request && !response) originals.append(element('p', 'GLM 요청·응답 원문 없음', 'muted'));
    };
    const source = row.applied_plan?.index ? decisions[row.applied_plan.index - 1] : row;
    if (source !== row) {
      const token = epoch;
      load(source.detail).then(packet => { if (epoch === token) showOriginals(packet.records, true); }).catch(e => { if (epoch === token) originals.append(element('p', e.message)); });
    } else showOriginals(records, false);
  }
  function damagePanel(row, input, token) {
    const state = input?.payload?.state || {};
    const summary = [];
    for (const side of ['self_team', 'opponent_team']) for (const mon of state[side] || []) if (mon.active) {
      for (const move of mon.current_move_slots || mon.moves || []) if (move.damage) summary.push([side, move.name || move.id, pretty(move.damage)]);
    }
    table(panels, ['방향', '기술', '당시 입력 피해 요약 · 0은 계산 결과'], summary);
    const target = element('section', '저장 계산 자료 불러오는 중…'); panels.append(target);
    load(row.damage_detail).then(packet => {
      if (token !== epoch) return;
      target.replaceChildren(element('p', `저장 계산 상태: ${packet.status} · ${packet.reason || '저장된 계산 결과'}`));
      if (!packet.damage) { target.append(element('p', '피해 자료 미제공 · 0으로 해석하지 않음')); return; }
      original(target, '계산 전체 원문 · 가정 세트·필터·공개 근거', packet.damage, 'damage.json');
      const rows = packet.damage.calculations || [];
      const filters = element('div', undefined, 'toolbar'), selectors = {};
      for (const [key, label] of [['direction','방향'],['move','기술'],['branch','테라 분기'],['candidate_id','가정 세트']]) {
        const s = element('select'); s.setAttribute('aria-label', label);
        const all = element('option', `${label} 전체`); all.value = ''; s.append(all);
        for (const value of new Set(rows.map(r => r[key]).filter(v => v != null))) { const o = element('option', value); o.value = value; s.append(o); }
        selectors[key] = s; filters.append(s);
      }
      target.append(filters);
      const page = element('div'), nav = element('div', undefined, 'toolbar'); let offset = 0;
      const prev = button('이전 시나리오', () => { offset -= 50; show(); }), more = button('다음 시나리오', () => { offset += 50; show(); });
      const count = element('span'); nav.append(prev, count, more); target.append(nav, page);
      const show = () => {
        const filtered = rows.filter(r => Object.entries(selectors).every(([key, s]) => !s.value || String(r[key]) === s.value));
        page.replaceChildren(); count.textContent = `${filtered.length} / ${rows.length}개 · ${Math.floor(offset / 50) + 1}페이지`;
        prev.disabled = offset <= 0; more.disabled = offset + 50 >= filtered.length;
        for (const r of filtered.slice(offset, offset + 50)) {
          const value = r.result?.damage_range_hp;
          const result = value == null ? (r.error || r.result?.excluded_with_reason || '결과 미제공 / 미계산') : value.join('–') + ' HP';
          original(page, `${r.direction} · ${r.move} · ${r.branch} · ${r.candidate_id} · ${result}`, r, 'damage-scenario.json');
        }
        if (!filtered.length) page.append(element('p', '저장 시나리오 없음 · 원문의 미계산/제외 사유 확인'));
      };
      Object.values(selectors).forEach(s => { s.onchange = () => { offset = 0; show(); }; }); show();
    }).catch(e => { if (epoch === token) target.textContent = e.message; });
  }
  function thinkingPanel(body, input) {
    if (!body?.thinking || !body?.first_pass) return;
    const first = body.first_pass, final = body.answers?.action || {}, thinking = body.thinking;
    const criteria = input?.payload?.questions?.action?.criteria || {};
    panels.append(element('h3', 'Tacit thinking 전후 판단'));
    panels.append(element('p', `첫 판단 ${first.choice ?? '미제공'} → 최종 ${final.choice ?? '미제공'} · ${first.choice === final.choice ? '선택 유지' : '선택 변경'}`));
    panels.append(element('p', '첫 판단은 기록용 그림자 판단이며 실제 명령에는 최종 선택을 사용합니다.', 'muted'));
    table(panels, ['후보 ID', '행동 이름', '첫 판단 확률', '최종 확률', '선택'], Object.entries(criteria).map(([key, value]) => [
      key, candidateLabel(input?.payload, key, value), first.probabilities?.[key] ?? '미제공', final.probabilities?.[key] ?? '미제공',
      [first.choice === key ? '첫 판단' : '', final.choice === key ? '최종' : ''].filter(Boolean).join(' · ')]));
    const finishes = {natural:'자연 </think> 종료', length:'토큰 한도 소진', eos:'EOS 종료'};
    panels.append(element('p', `생성 종료: ${finishes[thinking.finish_reason] || thinking.finish_reason || '미확인'} · 강제 마감: ${thinking.forced_close === true ? '예 (추론 완결을 뜻하지 않음)' : thinking.forced_close === false ? '아니요' : '미확인'} · 생성 ${number(thinking.token_ids?.length)}토큰 · seed ${thinking.seed ?? '미확인'}`));
    const external = body.external_http_calls !== undefined;
    const measured = value => value === null ? '미관측' : number(value);
    const headings = ['단계', '지연 (초)', '단계 입력 길이', '처리 입력 토큰', '실제 forward'];
    if (external) headings.push('외부 HTTP', '출력 토큰');
    table(panels, headings, Object.entries(body.stages || {}).map(([name, stage]) => {
      const row = [name, number(stage.seconds), number(stage.input_tokens), measured(stage.processed_input_tokens), measured(stage.forward_calls)];
      if (external) row.push(number(stage.http_calls), number(stage.output_tokens));
      return row;
    }));
    panels.append(element('p', `논리 판단 파이프라인 1회 · 실제 forward ${measured(body.physical_forward_calls)}${body.physical_forward_calls == null ? '' : '회'} · 원입력 길이 ${pretty(body.original_input_tokens) ?? '미제공'}`, 'muted'));
    if (external) {
      const firstOutput = body.stages?.first_pass?.output_tokens, finalOutput = body.stages?.final_read?.output_tokens;
      const readoutOutput = Number.isFinite(firstOutput) && Number.isFinite(finalOutput) ? firstOutput + finalOutput : null;
      panels.append(element('p', `외부 HTTP ${number(body.external_http_calls)}회 · thinking 생성 ${number(thinking.token_ids?.length)}토큰 · 첫/최종 판독 생성 ${number(readoutOutput)}토큰 · 전체 출력 ${number(body.usage?.output_tokens)}토큰`));
      if (body.measurement_unavailable_reason) panels.append(element('p', `외부 서버의 실제 forward·처리 입력 토큰·allocator는 미관측입니다. HTTP 횟수나 출력 토큰으로 추정하지 않습니다. 사유: ${body.measurement_unavailable_reason}`, 'muted'));
    }
    original(panels, 'Tacit 생성 원문 · 강제 마감 전', thinking.text, 'tacit-thinking.txt', true);
    original(panels, 'Tacit 생성 token ID', thinking.token_ids, 'tacit-thinking-token-ids.json');
  }
  async function render() {
    const token = ++epoch, row = rowNow();
    for (const b of tabButtons) { b.setAttribute('aria-selected', String(b.dataset.tab === active)); b.tabIndex = b.dataset.tab === active ? 0 : -1; }
    panels.setAttribute('aria-labelledby', `tab-${active}`); panels.replaceChildren(); overview.replaceChildren();
    if (!row) {
      overview.append(element('p', `${selectedTurn}턴 · 결정 없음`));
      if (active === 'log') logPanel(null); else panels.append(element('p', '이 턴에는 저장된 결정이 없습니다. 턴 로그와 리플레이를 확인하세요.'));
      return;
    }
    const ov = row.overview, selection = ov.selection, policy = ov.policy;
    overview.append(element('h2', `${selectedTurn}턴 · 결정 ${current + 1} · ${ov.decision_kind === 'forced_switch' ? '강제 교체' : ov.decision_kind === 'lead' ? '선봉 선택' : '일반 행동'} · ${row.actor ?? '?'} · ${row.id}`));
    const plannerStatus = selection?.automatic ? '자동 선택 · GLM/JEV 미호출' : policy.should_call ? 'GLM 호출' : row.applied_plan ? 'GLM 미호출 · 계획 재사용' : 'GLM 미호출 · 계획 없음';
    overview.append(element('p', plannerStatus + (ov.failed ? ' · 응답/실행 실패 기록 있음' : '')));
    panels.append(element('p', '로컬 결정 자료 불러오는 중…', 'muted'));
    try {
      const packet = await load(row.detail);
      if (token !== epoch) return;
      const records = packet.records, d = {records};
      const input = event(d, 'input'), response = event(d, 'response');
      const criteria = input?.payload?.questions?.action?.criteria || {};
      overview.append(element('p', selection ? `${selection.reused ? '기존 요청 선택 재사용 · ' : ''}${candidateLabel(input?.payload, selection.choice, criteria[selection.choice])} · ${selection.choice} · ${selection.command}` : '선택 없음 · 실패 또는 미완료', 'choice'));
      panels.replaceChildren();
      if (active === 'plan') planPanel(row, records);
      if (active === 'request') {
        if (input) {
          panels.append(element('p', selection?.automatic ? '자동 선택 입력 · JEV 미호출' : '실제 전달된 계획·표시 이름 포함'));
          original(panels, 'JEV 입력 원문', input.payload, 'executor-input.json', true);
          if (input.base_payload) original(panels, '계획 추가 전 입력', input.base_payload, 'executor-base-input.json');
        } else panels.append(element('p', 'JEV 요청 없음'));
      }
      if (active === 'response') {
        if (response) {
          thinkingPanel(response.body, input);
          original(panels, 'JEV 실제 응답 원문 · 선택·후보 확률·usage', response.body, 'executor-response.json', !response.body?.thinking);
        }
        else panels.append(element('p', selection?.automatic ? '모델 응답 없음 · 자동 선택' : '저장된 JEV 응답 없음 · 실패 또는 미호출'));
      }
      if (active === 'state') {
        const state = input?.payload?.state;
        if (state) {
          original(panels, '자기 팀', state.self_team, 'self-team.json', true);
          original(panels, '상대 공개 정보', state.opponent_team ?? [], 'opponent-team.json', true);
        }
        const answer = response?.body?.answers?.action;
        const probs = answer?.probabilities || {};
        const tbody = table(panels, ['선택', '후보 ID', '행동 이름', '후보 확률', '명령'], Object.entries(criteria).map(([key, value]) => [selection?.choice === key ? '✓' : '', key, candidateLabel(input?.payload, key, value), probs[key] === undefined ? '미제공' : pretty(probs[key]), input?.commands?.[key] ?? '미기록']));
        for (const tr of tbody.children) if (tr.firstChild.textContent === '✓') tr.className = 'chosen';
      }
      if (active === 'log') logPanel(row);
      if (active === 'damage') damagePanel(row, input, token);
      if (active === 'technical') original(panels, '관측 cutoff·전송·HTTP 시도·재시도·실패', records, 'decision-events.json', true);
    } catch (e) { if (token === epoch) panels.replaceChildren(element('p', e.message)); }
  }
  updateControls(); render();
  original(app, '경기 종료 기록', data.outcomes, 'battle-outcomes.json');
  original(app, '동결 호출 정책·프롬프트·모델 설정', data.config, 'condition-config.json');
  app.append(link('이 조건의 전체 events.jsonl', data.raw_events));
})();
