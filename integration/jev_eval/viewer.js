'use strict';
const data = JSON.parse(document.getElementById('viewer-data').textContent);
const items = data.decisions, log = data.turn_log, turns = log.turns;
const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = value => JSON.stringify(value, null, 2);
const phases = {lead:'선봉 선택',turn_action:'일반 행동',forced_switch:'강제 교체'};
let index = items.length ? 0 : -1, turnIndex = 0;

function highlight(value) {
  return pretty(value).replace(/("(?:\\.|[^"\\])*"\s*:?)|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (token, string, literal) => '<span class="json-' + (string ? (token.trimEnd().endsWith(':') ? 'key' : 'string') : literal ? 'literal' : 'number') + '">' + esc(token) + '</span>');
}
function payload(d) { return d && (d.request || d.observation); }
function selected() { return items[index] || null; }
function turnLabel(turn) { return turn === 0 ? '준비 구간 0' : turn + '턴'; }
function effectName(value) {
  if (value == null || value === 'unknown') return '미확인';
  if (typeof value !== 'object') return value === '' ? '확인된 부재' : String(value);
  if (value.knowledge === 'confirmed_absent') return '확인된 부재';
  if (value.knowledge === 'suppressed' || value.suppressed === true) {
    const underlying = value.underlying_ability;
    return '억제됨 · 알려진 특성 ' + effectName(underlying);
  }
  if (value.knowledge === 'unknown') return '미확인';
  const name = value.name || value.id || '미확인';
  return value.suppressed === 'unknown' ? name + ' · 억제 여부 미확인' : name;
}
function publicHp(mon) {
  const value = mon.hp_percent, precision = mon.hp_precision;
  if (!Number.isFinite(value) || value < 0 || value > 100 || !precision || precision === 'unknown') return '미확인';
  const label = {rounded:'반올림 공개',rounded_public_fraction:'반올림 공개',exact:'정확 공개',exact_zero:'0 확인'}[precision] || String(precision);
  return value.toLocaleString('ko-KR', {maximumFractionDigits:2}) + '% · ' + label;
}
function movesName(value) {
  return Array.isArray(value) && value.length ? value.map(effectName).join(', ') : '미공개';
}
function table(headers, rows, kind) {
  return '<div class="table-wrap"><table><thead><tr>' + headers.map(h => '<th>' + esc(h) + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map((row, n) => '<tr' + (kind ? ' data-' + kind + '-index="' + n + '"' : '') + '>' + row.map(value => '<td>' + esc(value ?? '미확인') + '</td>').join('') + '</tr>').join('') + '</tbody></table></div>';
}
function stateView(d, p) {
  if (!d) { $('state-content').textContent = '이 턴에는 결정 시점의 저장 입력이 없습니다.'; return; }
  const s = p.state;
  let content = '<h3>자기 팀</h3>' + table(['슬롯','포켓몬','HP','특성','도구'], s.self_team.map(m =>
    [m.slot,m.species + (m.active && d.kind !== 'lead' ? ' (출전)' : ''),m.condition,effectName(m.ability),effectName(m.item)]));
  content += '<h3>상대 공개 정보</h3><p class="muted">HP는 저장 입력의 공개 비율·정밀도입니다. 벤치 HP는 마지막 공개 값이며 비공개 회복을 추정하지 않습니다. 특성 정체는 현재 발동의 증거가 아닙니다.</p>' +
    table(['포켓몬','HP (공개 %)','공개 기술','현재 특성','공개 기본 특성','도구'], s.opponent_team.map(m =>
      [m.species + (m.active && d.kind !== 'lead' ? ' (출전)' : ' (벤치/프리뷰)'),publicHp(m),movesName(m.moves),effectName(m.ability),effectName(m.baseAbility),effectName(m.item)]), 'opponent');
  const probs = d.response?.answers?.action?.probabilities || {};
  content += '<h3>합법 후보 · 원래 확률값</h3><p class="muted">확률은 배틀 승률이 아닙니다.</p><div class="table-wrap"><table><thead><tr><th>후보 ID</th><th>행동</th><th>확률</th></tr></thead><tbody>' +
    Object.entries(p.questions.action.criteria).map(([key,c]) => '<tr class="' + (key === d.selection?.choice ? 'selected-row' : '') + '"><td>' + esc(key) + (key === d.selection?.choice ? ' ✓' : '') + '</td><td>' + esc(actionLabel(p,key,c)) + '</td><td>' + esc(probs[key] ?? '—') + '</td></tr>').join('') + '</tbody></table></div>';
  $('state-content').innerHTML = content;
}
function beforeCutoff(row, cutoff) {
  return row.sequence < cutoff.sequence || (row.sequence === cutoff.sequence && row.line_index <= cutoff.line_index);
}
function currentRows() {
  const part = turns[turnIndex], d = selected(), cutoff = d && log.decision_cutoffs[d.id];
  return $('until-decision').checked && cutoff ? part.rows.filter(row => beforeCutoff(row,cutoff)) : part.rows;
}
function rawText(rows) { return rows.map(row => row.protocol).join('\n') + (rows.length ? '\n' : ''); }
function rowHtml(row) {
  return '<div class="log-row' + (row.parsed ? '' : ' unparsed') + '" data-sequence="' + row.sequence + '" data-line-index="' + row.line_index + '"><span class="source-ref">' + row.sequence + ':' + row.line_index + '</span>' + esc(row.text) + (row.parsed ? '' : ' <span class="muted">(공개 원문)</span>') + '</div>';
}
function renderTurn() {
  const part = turns[turnIndex], d = selected(), cutoff = d && log.decision_cutoffs[d.id];
  $('until-decision').disabled = !d;
  if (!d) $('until-decision').checked = false;
  const rows = currentRows(), before = cutoff ? rows.filter(row => beforeCutoff(row,cutoff)) : rows;
  const after = cutoff ? rows.filter(row => !beforeCutoff(row,cutoff)) : [];
  $('turn-note').textContent = part.label + ' · 모델 수신 공개 프로토콜 ' + rows.length + '행 · ' + ($('until-decision').checked ? '선택한 결정의 행 cutoff까지' : '선택한 턴 전체');
  $('turn-status').textContent = (log.terminal ? '종료 이벤트: ' + turnLabel(log.terminal.turn) + ' · ' + log.terminal.kind : '진행 중 중단 · win/tie 종료 이벤트 없음') + (d ? ' · 결정 경계 ' + cutoff.sequence + ':' + cutoff.line_index : ' · 이 턴에는 결정이 없습니다.');
  let text = '<section id="turn-before"><h3>' + (d ? '이 결정 전까지' : '전체 턴 기록') + '</h3>' + (before.map(rowHtml).join('') || '<p class="muted">이 구간에 공개 이벤트가 없습니다.</p>') + '</section>';
  if (after.length) text += '<section id="turn-after" class="after-decision"><h3>선택한 결정 이후 결과</h3>' + after.map(rowHtml).join('') + '</section>';
  $('turn-readable').innerHTML = text;
  $('turn-raw').textContent = rawText(rows);
}
function navigateTarget(delta) {
  if (index >= 0) return index + delta;
  if (delta > 0) return items.findIndex(d => d.turn > turns[turnIndex].turn);
  for (let n = items.length - 1; n >= 0; n--) if (items[n].turn < turns[turnIndex].turn) return n;
  return -1;
}
function render() {
  const d = selected(), p = payload(d), part = turns[turnIndex];
  $('turn').value = turnIndex;
  $('previous-turn').disabled = turnIndex === 0;
  $('next-turn').disabled = turnIndex === turns.length - 1;
  $('decision').value = d ? String(index) : '';
  $('position').textContent = d ? (index + 1) + ' / ' + items.length : '이 턴에 결정 없음';
  $('previous').disabled = navigateTarget(-1) < 0;
  const next = navigateTarget(1); $('next').disabled = next < 0 || next >= items.length;
  $('phase').textContent = part.label + (d ? ' · ' + (phases[d.kind] || d.kind) : ' · 결정 없음');
  $('diagnostics').hidden = !d?.diagnostics?.length;
  $('diagnostics').textContent = d?.diagnostics?.length ? '기록된 판단 진단: ' + d.diagnostics.join(', ') : '';
  if (d) {
    $('choice').textContent = actionLabel(p,d.selection?.choice,p.questions.action.criteria[d.selection?.choice]);
    const usage = d.response?.usage;
    $('metrics').innerHTML = '<span><strong>' + (d.automatic ? '자동 선택 · API 미호출' : d.selection ? 'JEV 선택' : d.request ? '요청 후 선택 미완료' : 'API 호출 전 중단') + '</strong></span><span>전송: <strong>' + esc(d.wire?.command || '없음') + '</strong></span>' +
      (Number.isFinite(d.elapsed) ? '<span>응답 ' + d.elapsed.toFixed(3) + '초</span>' : '') + (usage ? '<span>토큰 입력 ' + esc(usage.input_tokens ?? '—') + ' / 출력 ' + esc(usage.output_tokens ?? '—') + '</span>' : '');
    const own = p.state.self_team.find(m => m.active), op = p.state.opponent_team.find(m => m.active);
    $('scene').textContent = (d.kind === 'lead' ? '선봉 선택 전 · 팀 프리뷰' : (own?.species || '출전 정보 없음') + ' ↔ ' + (op?.species || '상대 출전 정보 없음')) + ' · 요청 모델 ' + (d.request?.model || '미호출') + ' · 반환 모델 ' + (d.response?.model || '없음');
    $('request-note').textContent = d.automatic ? '합법 후보가 하나여서 API를 호출하지 않았습니다. 아래는 당시 관측과 후보이며, 전송 요청이 아닙니다.' : !d.request ? 'API 호출 전 중단되었습니다. 아래는 당시 관측과 후보입니다.' : '기록된 실제 HTTP 요청 JSON입니다. 기술 기록에 요청 바이트·ID·본문 해시와 재시도를 보존했습니다.';
    $('request-json').innerHTML = highlight(p);
    $('response-json').innerHTML = d.response ? highlight(d.response) : (d.automatic ? 'API 미호출 — 응답 없음' : d.request ? '요청 기록 있음 — 유효 응답 없음' : 'API 호출 전 중단 — 응답 없음');
    $('technical-json').innerHTML = highlight({decision_id:d.id,...d.technical});
  } else {
    $('choice').textContent = '이 턴에 결정 없음'; $('metrics').textContent = '전송: 없음';
    $('scene').textContent = '턴 로그에서 이 구간의 공개 이벤트를 확인하세요.';
    $('request-note').textContent = '이 턴에는 결정 시점의 저장 입력이 없습니다.';
    for (const kind of ['request','response','technical']) $(kind + '-json').textContent = '결정 기록 없음';
  }
  for (const b of document.querySelectorAll('[data-copy="request"],[data-download="request"]')) b.disabled = !d;
  for (const b of document.querySelectorAll('[data-copy="response"],[data-download="response"]')) b.disabled = !d?.response;
  stateView(d,p); renderTurn(); $('status').textContent = '';
  window.jevDamageView?.update();
  history.replaceState(null,'','#' + (d ? encodeURIComponent(d.id) : 'turn-' + part.turn));
}
function selectDecision(n) {
  if (n < 0 || n >= items.length) return;
  index = n; turnIndex = turns.findIndex(part => part.turn === items[n].turn); render();
}
function selectTurn(n) {
  if (n < 0 || n >= turns.length) return;
  turnIndex = n; index = items.findIndex(d => d.turn === turns[n].turn); render();
}
for (let n = 0; n < turns.length; n++) {
  const option = document.createElement('option'); option.value = n;
  option.textContent = turns[n].label + ' · 결정 ' + turns[n].decision_ids.length + '개'; $('turn').append(option);
}
const empty = document.createElement('option'); empty.value = ''; empty.textContent = '이 턴에 결정 없음'; empty.disabled = true; $('decision').append(empty);
for (let n = 0; n < items.length; n++) {
  const d = items[n], p = payload(d), option = document.createElement('option'); option.value = n;
  option.textContent = turnLabel(d.turn) + ' · ' + (phases[d.kind] || d.kind) + (d.automatic ? ' · 자동' : '') + ' · ' + actionLabel(p,d.selection?.choice,p.questions.action.criteria[d.selection?.choice]) + ' · 결정 ' + (n + 1);
  $('decision').append(option);
}
const label = {player_won:'승리',player_lost:'패배',tied:'무승부',output_failure:'모델 선택 실패'}[data.outcome.outcome] || '기술 실패';
$('heading').textContent = data.experiment + ' · ' + data.slot + '경기 · JEV ' + label;
$('game-summary').textContent = (log.terminal ? turnLabel(log.terminal.turn) + ' · 종료' : '진행 중 중단') + ' · JEV ' + data.outcome.jev_actor + ' · ' + items.length + '개 결정 · ' + log.row_count + '개 공개 행';
if (data.treatment?.damage_predictions_enabled === false && data.treatment?.speed_comparison_enabled === true) {
  $('treatment-note').hidden = false;
  $('treatment-note').textContent = '피해 예측 비활성화 · 스피드 비교 유지';
}
$('synthetic-note').hidden = !data.synthetic;
$('decision').onchange = e => selectDecision(Number(e.target.value));
$('turn').onchange = e => selectTurn(Number(e.target.value));
$('previous').onclick = () => selectDecision(navigateTarget(-1));
$('next').onclick = () => selectDecision(navigateTarget(1));
$('previous-turn').onclick = () => selectTurn(turnIndex - 1);
$('next-turn').onclick = () => selectTurn(turnIndex + 1);
$('until-decision').onchange = renderTurn;
document.addEventListener('keydown', e => {
  if (!['ArrowLeft','ArrowRight'].includes(e.key) || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.isComposing || e.repeat) return;
  if (e.target.closest('input,textarea,select,[role=tab],[role=textbox]') || e.target.isContentEditable) return;
  e.preventDefault(); selectDecision(navigateTarget(e.key === 'ArrowRight' ? 1 : -1));
});
const tabs = [...document.querySelectorAll('[role=tab]')];
function tab(button) { for (const t of tabs) { const active = t === button; t.setAttribute('aria-selected',active); t.tabIndex = active ? 0 : -1; $(t.dataset.tab + '-panel').hidden = !active; } window.jevDamageView?.update(); }
for (const b of tabs) {
  b.onclick = () => tab(b);
  b.onkeydown = e => {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
    e.preventDefault(); let n = tabs.indexOf(b);
    n = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (n + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length;
    tab(tabs[n]); tabs[n].focus();
  };
}
tab(tabs[0]);
function valueFor(kind) { if (kind === 'damage') return pretty(window.jevDamageView.value()); const d = selected(); return kind === 'turn-raw' ? rawText(currentRows()) : pretty(kind === 'request' ? payload(d) : d?.response); }
for (const b of document.querySelectorAll('[data-copy]')) b.onclick = async () => {
  const text = valueFor(b.dataset.copy);
  try { await navigator.clipboard.writeText(text); $('status').textContent = '선택한 구간을 복사했습니다.'; }
  catch { const area = document.createElement('textarea'); area.value = text; area.style.position = 'fixed'; area.style.opacity = 0; document.body.append(area); area.select(); const ok = document.execCommand('copy'); area.remove(); $('status').textContent = ok ? '선택한 구간을 복사했습니다.' : '복사가 제한되어 있습니다. 다운로드를 이용하세요.'; }
};
for (const b of document.querySelectorAll('[data-download]')) b.onclick = () => {
  const kind = b.dataset.download, text = valueFor(kind), raw = kind === 'turn-raw';
  const url = URL.createObjectURL(new Blob([text + (raw ? '' : '\n')],{type:raw ? 'text/plain;charset=utf-8' : 'application/json'}));
  const a = document.createElement('a'); a.href = url;
  a.download = data.experiment.toLowerCase() + '-battle-' + data.slot + (raw ? '-turn-' + turns[turnIndex].turn + ($('until-decision').checked ? '-before-decision-' + (index + 1) : '-full') : '-decision-' + (index + 1) + '-' + (kind === 'request' && selected()?.automatic ? 'observation' : kind)) + (raw ? '.log' : '.json');
  a.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
};
const hash = decodeURIComponent(location.hash.slice(1)), found = items.findIndex(d => d.id === hash);
if (found >= 0) selectDecision(found);
else if (/^turn-\d+$/.test(hash)) { const n = turns.findIndex(t => t.turn === Number(hash.slice(5))); selectTurn(n >= 0 ? n : 0); }
else if (items.length) selectDecision(0);
else selectTurn(0);
