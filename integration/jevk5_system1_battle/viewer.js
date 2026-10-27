'use strict';
const data = JSON.parse(document.getElementById('viewer-data').textContent);
const decisions = data.decisions || [], $ = id => document.getElementById(id);
const tabs = {request:'요청 JSON', response:'응답 원문', state:'상태·후보 요약', log:'턴 로그', technical:'기술 기록',
  prompt:'실제 프롬프트', probabilities:'선택지 확률', selection:'선택·전송'};
const phases = {lead:'선봉 선택', turn_action:'일반 행동', forced_switch:'강제 교체'};
const outcomes = {player_won:'승리', player_lost:'패배', tied:'무승부', output_failure:'모델 응답 실패', incomplete:'미완료'};
const pretty = v => JSON.stringify(v ?? null, null, 2);
const esc = v => String(v ?? '미확인').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function highlight(text) {
  return text.replace(/("(?:\\.|[^"\\])*"\s*:?)|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (token, string, literal) => '\u0000' + (string ? (token.trimEnd().endsWith(':') ? 'key' : 'string') : literal ? 'literal' : 'number') + '\u0001' + token + '\u0002')
    .split(/(\u0000(?:key|string|literal|number)\u0001[^\u0002]*\u0002)/g)
    .map(part => {const m = /^\u0000(\w+)\u0001([\s\S]*)\u0002$/.exec(part);return m ? '<span class="json-'+m[1]+'">'+esc(m[2])+'</span>' : esc(part);}).join('');
}
function table(headers, rows) {
  return '<div class="table-wrap"><table><thead><tr>' + headers.map(h=>'<th>'+esc(h)+'</th>').join('') + '</tr></thead><tbody>' +
    rows.map(r=>'<tr>'+r.map(v=>'<td>'+esc(v)+'</td>').join('')+'</tr>').join('') + '</tbody></table></div>';
}
const logMap = new Map((data.turn_log?.turns || []).map(t=>[t.turn,t]));
const turnValues = [...new Set([...logMap.keys(), ...decisions.map(d=>d.turn)])].sort((a,b)=>a===null?1:b===null?-1:a-b);
const turnLabel = t => t === 0 ? '준비 구간' : t === null ? '턴 미상' : t+'턴';
const turnValue = t => t === null ? 'unknown' : String(t);
let index = decisions.length ? 0 : -1, turn = decisions[0]?.turn ?? turnValues[0] ?? null;
let tab = 'request', current = '', currentIsText = false, replayReady = false;
function chosenLabel(d) {
  const key = d?.selection?.choice;
  return actionLabel(d?.observation, key, d?.observation?.questions?.action?.criteria?.[key]);
}
function effect(v) {return typeof v === 'string' ? (v==='unknown'?'미확인':v) : v?.name || v?.id || '미확인';}
function responseNames(d) {
  const a=d?.response?.answers?.action;
  if (!a) return '';
  const criteria=d.observation?.questions?.action?.criteria || {};
  return '<h3>선택지 점수 판독 결과 · HTTP 원문과 구분</h3>'+table(['후보 ID','실제 행동 이름','보정 분포','선택'],
    Object.entries(a.probabilities || {}).map(([key,p])=>[key,actionLabel(d.observation,key,criteria[key]),p,key===a.choice?'선택됨':'—']));
}

function stateSummary(d) {
  const s = d.observation?.state;
  if (!s) return '<p class="empty">상태 자료 미수집</p>';
  const self = table(['포켓몬','HP','특성','도구'], (s.self_team || []).map(m=>[m.species+(m.active?' · 출전':''),m.condition,effect(m.ability),effect(m.item)]));
  const opponent = table(['포켓몬','HP (공개 %)','특성','도구'], (s.opponent_team || []).map(m=>[m.species+(m.active?' · 출전':''),
    Number.isFinite(m.hp_percent)?m.hp_percent+'%':'미확인',effect(m.ability),effect(m.item)]));
  const candidates = table(['후보 ID','행동','선택'], Object.entries(d.observation.questions?.action?.criteria || {}).map(([k,c])=>[
    k,actionLabel(d.observation,k,c),k===d.selection?.choice?'선택됨':'—']));
  return '<h3>자기 팀</h3>'+self+'<h3>상대 공개 정보</h3><p class="muted">당시 공개된 HP 비율입니다. 미공개 정보는 미확인으로 유지합니다.</p>'+opponent+'<h3>합법 후보</h3>'+candidates;
}
function adjacent(delta) {
  if (index >= 0) return index+delta >= 0 && index+delta < decisions.length ? index+delta : -1;
  const eligible = decisions.map((d,i)=>({d,i})).filter(x=>delta>0?x.d.turn>turn:x.d.turn<turn);
  return (delta>0?eligible[0]:eligible.at(-1))?.i ?? -1;
}
function visibleRows() {
  const rows = logMap.get(turn)?.rows || [], d = decisions[index];
  const cutoff = data.turn_log?.decision_cutoffs?.[d?.id];
  if (!$('cutoff').checked || !cutoff) return rows;
  return rows.filter(r=>r.sequence<cutoff.sequence||(r.sequence===cutoff.sequence&&r.line_index<=cutoff.line_index));
}
function renderContent() {
  const d = decisions[index], rows = visibleRows();
  let value = null, note = '', rich = '';
  if (tab==='request') {
    value = d?.request;
    note = !d?'이 턴에 결정 없음':d.automatic?'단일 후보 자동 선택 · 모델 미호출. 관측은 상태·후보 요약에서 확인하세요.':
      d.request?'실제로 전송한 vLLM completion 요청 JSON · 저장된 원값':'요청 자료 없음 · 전송 여부는 기술 기록을 확인하세요.';
  } else if (tab==='response') {
    value = d?.raw_response;
    note = !d?'이 턴에 결정 없음':d.automatic?'모델 미호출 · 응답 없음':d.raw_response!=null?
      '이름은 결정 당시 후보를 연결한 표시입니다. 아래 HTTP 원문과 복사·다운로드에는 원래 값만 유지합니다. 선택 확률은 배틀 승률이 아닙니다.':d.request?'요청 기록 있음 · 응답 미수신':'응답 자료 없음';
    rich = responseNames(d);
  } else if (tab==='state') {
    value = d?.observation;
    note = '결정 당시 저장된 입력·공개 상태·합법 후보. 전체 원문은 아래에서 펼쳐 확인할 수 있습니다.';
    rich = d?stateSummary(d):'<p class="empty">이 턴에 결정 없음 · 상태를 추정하지 않습니다.</p>';
  } else if (tab==='log') {
    value = rows.map(r=>r.protocol).join('\n')+(rows.length?'\n':'');
    note = $('cutoff').checked?'저장 cutoff까지의 공개 로그 · 결정 전 관측 범위':'선택한 턴 전체 공개 로그 · 결정 이후 결과 포함';
    rich = rows.map(r=>'<div class="log-row"><div class="source-ref">'+esc(r.sequence+':'+r.line_index)+'</div>'+esc(r.text)+'</div>').join('') || '<p class="empty">이 구간에 공개 로그 없음</p>';
  } else if (tab==='technical') {
    value = d?{...d.technical,normalized_response:d.response,diagnostics:d.diagnostics}:null;
    note = '저장된 요청/응답 시도·입력 경계·감사 출처·선택·전송과 내부 호환 응답. 외부 응답 원문과 구분합니다.';
  } else if (tab==='prompt') {
    value=d?.prompt_text; note='실제 전송 token IDs를 고정 tokenizer로 해독한 공식 비Thinking 프롬프트.';
  } else if (tab==='probabilities') {
    value=d?.response; note='원후보 점수에서 사전 고정한 T로 계산한 선택 분포입니다. QA 보정값이며 배틀 승률이 아닙니다.';
    rich=responseNames(d);
  } else if (tab==='selection') {
    value = d?{selection:d.selection,wire:d.wire}:null; note = '실제 저장된 선택·전송 기록. 실패·미전송은 성공한 행동으로 표시하지 않습니다.';
  }
  if (!d && tab!=='log') note = '이 턴에 결정 없음 · 해당 결정 자료 없음';
  currentIsText = typeof value === 'string';
  current = currentIsText ? value : pretty(value);
  $('note').textContent = note;
  $('state-content').hidden = !rich; $('state-content').innerHTML = rich;
  $('raw-wrap').open = !rich || tab==='response';
  $('raw-wrap').querySelector('summary').textContent = tab==='log'?'같은 구간의 공개 서버 원문':'저장 원문 전체';
  $('raw').innerHTML = currentIsText ? esc(current) : highlight(current);
  $('log-controls').hidden = tab!=='log';
  $('status').textContent = '';
  document.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b.dataset.tab===tab));b.tabIndex=b.dataset.tab===tab?0:-1;});
  $('content').setAttribute('aria-labelledby',tab+'-tab');
}
function render() {
  const d = decisions[index];
  $('decision').value = d?String(index):''; $('turn').value = turnValue(turn);
  $('previous').disabled = adjacent(-1)<0; $('next').disabled = adjacent(1)<0;
  const t = turnValues.indexOf(turn);
  $('previous-turn').disabled = t<=0; $('next-turn').disabled = t<0 || t>=turnValues.length-1;
  $('position').textContent = d?(index+1)+' / '+decisions.length:'이 턴에 결정 없음';
  $('phase').textContent = turnLabel(turn)+' · '+(d?phases[d.kind]||d.kind:'공개 로그');
  $('choice').textContent = d?chosenLabel(d):'결정 없음';
  const retries = d?.technical?.http_attempt_history?.filter(e=>e.type==='provider_retry').length || 0;
  const state = !d?'결정 없음':d.automatic?'자동 선택 · 모델 미호출':d.selection?'모델 선택':d.raw_response!=null?'모델 응답 실패 · 선택 없음':d.request?'요청 기록 · 응답 미수신':'요청 미수집';
  $('metrics').textContent = state+' · 전송: '+(d?.wire?.command || '없음')+(retries?' · 통신 재시도 '+retries+'회':'');
  $('diagnostics').hidden = !d?.diagnostics?.length; $('diagnostics').textContent = pretty(d?.diagnostics);
  const cutoff = data.turn_log?.decision_cutoffs?.[d?.id];
  $('cutoff').disabled = !cutoff;
  if (!cutoff) $('cutoff').checked = false;
  $('cutoff-note').textContent = cutoff?'원문 좌표 '+cutoff.sequence+':'+cutoff.line_index:'이 결정의 cutoff 없음 · 전체 턴 로그만 표시';
  $('replay-log').textContent = (logMap.get(turn)?.rows || []).map(r=>r.protocol).join('\n') || '공개 로그 없음';
  renderContent();
}
function seekReplay() {
  if (!Number.isInteger(turn) || turn<0) {$('replay-status').textContent='턴 미상 · 영상 위치를 추정하지 않습니다.';return;}
  $('animation').contentWindow?.postMessage({type:'planner-replay-seek',turn},'*');
  $('replay-status').textContent = replayReady?'선택한 '+turnLabel(turn)+' 시작으로 이동 · 영상 조작은 결정 선택과 독립':'영상 준비 시 선택한 '+turnLabel(turn)+'으로 이동 · 오프라인은 공개 로그 사용';
}
function moveDecision(n) {
  if (n<0 || n>=decisions.length) return;
  index=n; turn=decisions[n].turn;
  history.replaceState(null,'','#decision='+encodeURIComponent(decisions[n].id));
  render();seekReplay();
}
function moveTurn(t) {
  if (!turnValues.includes(t)) return;
  turn=t;index=decisions.findIndex(d=>d.turn===t);
  history.replaceState(null,'',index>=0?'#decision='+encodeURIComponent(decisions[index].id):'#turn='+turnValue(t));
  render();seekReplay();
}
for (const [key,label] of Object.entries(tabs)) {
  const b=document.createElement('button');b.id=key+'-tab';b.dataset.tab=key;b.textContent=label;b.setAttribute('role','tab');b.setAttribute('aria-controls','content');
  b.onclick=()=>{tab=key;renderContent();};
  b.onkeydown=e=>{const keys=Object.keys(tabs);let n=keys.indexOf(key);
    if(e.key==='ArrowRight')n=(n+1)%keys.length;else if(e.key==='ArrowLeft')n=(n+keys.length-1)%keys.length;
    else if(e.key==='Home')n=0;else if(e.key==='End')n=keys.length-1;else return;
    e.preventDefault();e.stopPropagation();tab=keys[n];renderContent();$(tab+'-tab').focus();};
  document.querySelector('.tabs').append(b);
}
$('heading').textContent=data.experiment+' · 경기 '+data.slot+' · JevK5 규칙 LoRA';
$('game-summary').textContent=data.outcome.slot_id+' · 관점 '+data.outcome.jev_actor+' · '+(outcomes[data.outcome.outcome]||'기술 중단/미완료')+' · '+decisions.length+'결정';
$('synthetic').hidden=!data.synthetic;
$('decision').add(new Option('이 턴에 결정 없음',''));
decisions.forEach((d,i)=>$('decision').add(new Option((i+1)+' · '+turnLabel(d.turn)+' · '+(phases[d.kind]||d.kind)+' · '+chosenLabel(d)+(d.automatic?' · 자동':''),String(i))));
turnValues.forEach(t=>$('turn').add(new Option(turnLabel(t),turnValue(t))));
$('decision').onchange=()=>{if($('decision').value!=='')moveDecision(Number($('decision').value));else render();};
$('previous').onclick=()=>moveDecision(adjacent(-1));$('next').onclick=()=>moveDecision(adjacent(1));
$('turn').onchange=()=>moveTurn($('turn').value==='unknown'?null:Number($('turn').value));
$('previous-turn').onclick=()=>moveTurn(turnValues[turnValues.indexOf(turn)-1]);$('next-turn').onclick=()=>moveTurn(turnValues[turnValues.indexOf(turn)+1]);
$('cutoff').onchange=renderContent;$('align-replay').onclick=seekReplay;
document.addEventListener('keydown',e=>{
  if(e.defaultPrevented||e.altKey||e.ctrlKey||e.metaKey||e.shiftKey||e.isComposing||e.target.closest('button,select,input,textarea,[contenteditable],[role=tab]'))return;
  if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();moveDecision(adjacent(e.key==='ArrowRight'?1:-1));}
});
$('copy').onclick=async()=>{try{
  if(navigator.clipboard)await navigator.clipboard.writeText(current);
  else {const t=document.createElement('textarea');t.value=current;document.body.append(t);t.select();const ok=document.execCommand('copy');t.remove();if(!ok)throw Error();}
  $('status').textContent='복사했습니다.';
}catch{$('status').textContent='복사 제한 · 다운로드를 이용하세요.';}};
$('download').onclick=()=>{const url=URL.createObjectURL(new Blob([current],{type:currentIsText?'text/plain;charset=utf-8':'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='ex123-battle-'+data.slot+'-'+(decisions[index]?.id||'turn-'+turnValue(turn))+'-'+tab+(currentIsText?'.txt':'.json');a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
window.addEventListener('message',e=>{if(e.source===$('animation').contentWindow&&e.data?.type==='planner-replay-ready'){replayReady=true;seekReplay();}});
$('animation').addEventListener('load',seekReplay);
function restoreLocation() {
  const fragment=new URLSearchParams(location.hash.slice(1)),target=fragment.get('decision'),found=decisions.findIndex(d=>d.id===target);
  if(found>=0){index=found;turn=decisions[index].turn;}
  else if(fragment.has('turn')){const v=fragment.get('turn'),t=v==='unknown'?null:Number(v);if(turnValues.includes(t)){turn=t;index=decisions.findIndex(d=>d.turn===t);}}
  else if(!location.hash){index=decisions.length?0:-1;turn=decisions[0]?.turn??turnValues[0]??null;}
  tab='request';render();
}
window.addEventListener('hashchange',()=>{restoreLocation();seekReplay();});
restoreLocation();$('animation').src='replay.html#embedded';
