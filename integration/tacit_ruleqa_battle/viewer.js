'use strict';
const data=JSON.parse(document.getElementById('viewer-data').textContent), items=data.decisions;
const $=id=>document.getElementById(id), pretty=v=>JSON.stringify(v,null,2);
const esc=v=>String(v??'미확인').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const phases={lead:'선봉 선택',turn_action:'일반 행동',forced_switch:'강제 교체'};
let index=0, tab='request', text='';
const tabs={request:'요청 JSON',response:'응답 원문',state:'상태·후보 요약',log:'턴 로그',technical:'기술 기록'};
const logs=new Map([[0,[]]]);let currentTurn=0;
for(const line of data.replay.split('\n')){if(line.startsWith('|turn|'))currentTurn=Number(line.split('|')[2]);if(!logs.has(currentTurn))logs.set(currentTurn,[]);logs.get(currentTurn).push(line);}
const turns=[...logs.keys()];let turn=items[0]?.turn||0;
function highlight(value){return value.replace(/("(?:\\.|[^"\\])*"\s*:?)|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,(token,string,literal)=>'<span class="json-'+(string?(token.trimEnd().endsWith(':')?'key':'string'):literal?'literal':'number')+'">'+esc(token)+'</span>');}
function table(headers,rows){return '<div class="table-wrap"><table><thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
function state(d){
 const user=JSON.parse(d.messages.find(m=>m.role==='user').content),s=user.context.state;
 const value=v=>typeof v==='object'?pretty(v):v;
 return '<h3>자기 팀</h3>'+table(['포켓몬','HP','특성','도구'],(s.self_team||[]).map(m=>[m.species,m.condition,value(m.ability),value(m.item)]))+
 '<h3>상대 공개 정보</h3>'+table(['포켓몬','HP (공개 %)','기술'],(s.opponent_team||[]).map(m=>[m.species,m.hp_percent==null?'미확인':m.hp_percent+'%',value(m.moves)]))+
 '<h3>합법 후보</h3>'+table(['선택지','행동','명령'],d.candidates.map(c=>[c.option_id+(d.selection?.choice===c.id?' ✓':''),user.context.battle_actions[c.id]?.display_name||c.name,c.command]))+
 '<details><summary>당시 상태 전체 · 저장된 조건부 계산 포함</summary><pre class="code">'+esc(pretty(s))+'</pre></details>';
}
function render(){
 const d=items[index];$('decision').value=d?String(index):'';$('turn').value=turn;
 $('previous').disabled=index<=0;$('next').disabled=index>=items.length-1;
 $('previous-turn').disabled=turns.indexOf(turn)<=0;$('next-turn').disabled=turns.indexOf(turn)>=turns.length-1;
 $('position').textContent=d?(index+1)+' / '+items.length:'이 턴에 결정 없음';
 $('phase').textContent=turn+'턴 · '+(d?phases[d.kind]:'경기 로그');
 const chosen=d?.candidates.find(c=>c.id===d.selection?.choice);
 $('choice').textContent=chosen?chosen.verb+' '+chosen.name:'선택 없음';
 $('metrics').textContent=d?(d.selection?.automatic?'자동 선택 · 모델 미호출':d.selection?.fallback?'오류 대체 선택':'Tacit 모델 선택')+' · 전송: '+(d.wire?.command||'없음'):'';
 const log=(logs.get(turn)||[]).join('\n');$('replay-log').textContent=log;
 $('state-content').hidden=tab!=='state'||!d;$('raw').hidden=tab==='state'&&!!d;
 let value=null,note='';
 if(tab==='request'){value=d?(d.selection?.automatic?{model_called:false,observation_messages:d.messages}: {messages:d.messages}):null;note=d?.selection?.automatic?'관측 메시지 · 모델에 전송하지 않음':'저장된 실제 모델 입력 메시지';}
 if(tab==='response'){value=d?.response?.raw??'모델 호출 없음';note='저장된 원응답 · 자동 선택은 응답 없음';}
 if(tab==='state'){value=d?JSON.parse(d.messages.find(m=>m.role==='user').content):null;if(d)$('state-content').innerHTML=state(d);note='당시 입력의 공개 상태와 합법 후보 · 조건부 계산은 상대 비공개 사실이 아닙니다.';}
 if(tab==='log'){value=log;note='선택한 턴 전체의 공개 로그 · 결정 이후 결과 포함';}
 if(tab==='technical'){value=d?{id:d.id,boundary:d.boundary,observation_identity:d.observation_identity,response:d.response,selection:d.selection,wire:d.wire}:null;note='원응답 메타데이터·파싱·대체·실제 전송 기록';}
 text=typeof value==='string'?value:pretty(value);$('raw').innerHTML=typeof value==='string'?esc(text):highlight(text);$('note').textContent=note;$('status').textContent='';
 document.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',b.dataset.tab===tab);b.tabIndex=b.dataset.tab===tab?0:-1;});$('content').setAttribute('aria-labelledby',tab+'-tab');
}
function move(n){if(n<0||n>=items.length)return;index=n;turn=items[n].turn;history.replaceState(null,'','#decision='+encodeURIComponent(items[n].id));render();}
function changeTurn(t){turn=t;index=items.findIndex(d=>d.turn===turn);render();}
for(const [key,label] of Object.entries(tabs)){const b=document.createElement('button');b.role='tab';b.id=key+'-tab';b.dataset.tab=key;b.textContent=label;b.setAttribute('aria-controls','content');b.onclick=()=>{tab=key;render();};b.onkeydown=e=>{const keys=Object.keys(tabs);let n=keys.indexOf(key);if(e.key==='ArrowRight')n=(n+1)%keys.length;else if(e.key==='ArrowLeft')n=(n+keys.length-1)%keys.length;else return;e.preventDefault();e.stopPropagation();tab=keys[n];render();$(tab+'-tab').focus();};document.querySelector('.tabs').append(b);}
$('heading').textContent='EX-108 · 경기 '+data.outcome.slot+' · Tacit RuleQA';$('game-summary').textContent=data.outcome.slot_id+' · '+data.outcome.outcome+' · '+items.length+'결정';
for(const [i,d] of items.entries())$('decision').add(new Option(d.turn+'턴 · '+phases[d.kind]+' · '+(i+1),i));
for(const t of turns)$('turn').add(new Option(t===0?'준비 구간':t+'턴',t));
$('previous').onclick=()=>move(index-1);$('next').onclick=()=>move(index+1);$('decision').onchange=()=>move(Number($('decision').value));
$('turn').onchange=()=>changeTurn(Number($('turn').value));$('previous-turn').onclick=()=>changeTurn(turns[turns.indexOf(turn)-1]);$('next-turn').onclick=()=>changeTurn(turns[turns.indexOf(turn)+1]);
 document.addEventListener('keydown',e=>{if(e.target.closest('button,select,input,textarea,[contenteditable]')||e.altKey||e.ctrlKey||e.metaKey)return;if(e.key==='ArrowLeft'){e.preventDefault();move(index-1);}if(e.key==='ArrowRight'){e.preventDefault();move(index+1);}});
$('copy').onclick=async()=>{try{if(navigator.clipboard)await navigator.clipboard.writeText(text);else{const t=document.createElement('textarea');t.value=text;document.body.append(t);t.select();if(!document.execCommand('copy'))throw Error();t.remove();}$('status').textContent='복사했습니다.';}catch{$('status').textContent='복사할 수 없습니다. 다운로드를 이용하세요.';}};
$('download').onclick=()=>{const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='ex108-'+data.outcome.slot+'-'+(index+1)+'-'+tab+'.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
const replay='replay-'+data.outcome.slot+'.html';$('animation').src=replay+'#embedded';$('replay-link').href=replay;$('log-link').href='battle-'+data.outcome.slot+'.log';
const match=new URLSearchParams(location.hash.slice(1)).get('decision'),found=items.findIndex(d=>d.id===match);if(found>=0){index=found;turn=items[index].turn;}render();
