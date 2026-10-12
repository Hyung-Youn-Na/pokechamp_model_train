"""Standalone offline comparison export; no battle-viewer or model mutations."""
from __future__ import annotations

import argparse
import base64
import gzip
import json
from pathlib import Path

from . import qwen_state_study as study

DEFAULT_OUTPUT = study.v.ROOT / 'exports/qwen_candidate_state/ex064'
DOWNLOAD_FILES = ('comparison.json', *(f'conditions/{c}.json' for c in study.CONDITIONS),
                  'diffs.json', 'rubric.json', 'result.json')


def label_for(body, action):
    desc = action['description']
    state = body['observation']['state']
    slot = desc.get('move_ref', {}).get('self_team_slot', desc.get('slot'))
    mon = next((p for p in state['self_team'] if p['slot'] == slot), {})
    if desc['kind'] == 'move':
        move_slot = desc['move_ref']['current_move_slot']
        move = next((m for m in mon.get('current_move_slots', []) if m['slot'] == move_slot), {})
        name = desc.get('name') or move.get('name') or move.get('move') or action['action_id']
        user = desc.get('user') or mon.get('species', '')
        if isinstance(user, dict):
            user = user.get('species', '')
        label = name + (' · ' + user if user else '')
    else:
        name = desc.get('pokemon') or mon.get('species') or desc.get('name') or action['action_id']
        label = ('선봉 ' if desc['kind'] == 'team' else '교체 ') + name
    if desc.get('terastallize'):
        label += ' · Tera ' + (desc.get('tera_type') or mon.get('configured_tera_type', 'unknown'))
    return dict(action_id=action['action_id'], label=label,
                tera=bool(desc.get('terastallize')), command=action['command'])


def script_json(value):
    # JSON inside a raw-text HTML element must not contain an HTML end tag.
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace(
        '&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace(
        '\u2028', '\\u2028').replace('\u2029', '\\u2029')


def embedded_downloads(output):
    """Keep exact exported bytes available without file-URL fetch or navigation."""
    return {name: base64.b64encode(gzip.compress((Path(output) / name).read_bytes(),
                                               mtime=0)).decode('ascii')
            for name in DOWNLOAD_FILES}


def export(study_directory, output=DEFAULT_OUTPUT):
    source, output = Path(study_directory), Path(output)
    result = study.read(source / 'result.json')
    saved = {c: study.rows(source / c / 'inputs.jsonl') for c in study.CONDITIONS}
    comparisons = study.rows(source / 'comparisons.jsonl')
    compare_index = {r['decision']: r for r in comparisons}
    cases = study.read(source / 'diagnostic-cases.json')
    rubrics = study.read(source / 'rubric.json')
    decisions = []
    lookup = {c: {r['decision']: r for r in saved[c]} for c in study.CONDITIONS}
    for original in saved['C1']:
        key = original['decision']
        state = original['body']['observation']['state']
        enriched = lookup['C3'][key]['body']
        actions = [label_for(enriched, a) for a in enriched['actions']]
        decisions.append(dict(decision=key, turn=state['turn'], kind=state['decision_kind'],
            actions=actions, original_choice=original['original_selection']['choice'],
            original_wire=original['original_wire'], comparison=compare_index.get(key),
            inputs={c: lookup[c][key]['body'] for c in study.CONDITIONS}))
    diagnoses = study.rows(source / 'diagnostics/responses.jsonl') if (source / 'diagnostics/responses.jsonl').exists() else []
    # Keep generated output and its schema/HTTP status, without duplicating each entire request.
    diagnoses = [{k: value for k, value in row.items() if k != 'request'} for row in diagnoses]
    data = dict(experiment='EX-064', result=result, decisions=decisions,
                cases=cases, rubric=rubrics, diagnoses=diagnoses,
                diagnostic_is_not_internal_reasoning=True, q_is_not_calibrated_win_probability=True)
    output.mkdir(parents=True, exist_ok=False)
    for condition in study.CONDITIONS:
        study.write_new(output / 'conditions' / (condition + '.json'), saved[condition])
    study.write_new(output / 'comparison.json', data)
    study.write_new(output / 'diffs.json', comparisons)
    study.write_new(output / 'rubric.json', rubrics)
    study.write_new(output / 'result.json', result)
    if (source / 'report.md').exists():
        with (output / 'report.md').open('xb') as stream:
            stream.write((source / 'report.md').read_bytes())
    downloads = embedded_downloads(output)
    with (output / 'index.html').open('x', encoding='utf-8') as stream:
        stream.write(HTML.replace('__DOWNLOAD_DATA__', script_json(downloads)).replace(
            '__COMPARISON_DATA__', script_json(data)))
    receipt = dict(experiment='EX-064', decisions=len(decisions),
        candidates_per_condition=sum(len(d['actions']) for d in decisions),
        diagnostic_cases_per_condition=len(cases), prediction_rows=len(result['predictions']),
        model_calls=0, battle_transmissions=0, original_battle_viewer_changed=False,
        output=str(output.resolve()), files={str(p.relative_to(output)): study.file_hash(p)
            for p in sorted(output.rglob('*')) if p.is_file()})
    study.write_new(output / 'export-receipt.json', receipt)
    return receipt


HTML = r'''<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EX-064 후보 상태·지침 비교</title>
<style>
:root{font-family:system-ui,sans-serif;color:#142139;background:#f4f6fa;line-height:1.5}body{margin:0}
header{padding:24px 30px;background:#152945;color:white}h1{font-size:23px;margin:0 0 8px}header p{margin:5px 0;max-width:1100px}
nav{display:flex;gap:16px;flex-wrap:wrap;padding:12px 30px;background:white;border-bottom:1px solid #dbe2ec}a{color:#215fac}
main{padding:22px 30px;max-width:1700px;margin:auto}.controls{display:flex;align-items:center;gap:12px;margin:16px 0;flex-wrap:wrap}
button,select{font:inherit;padding:7px 10px;border:1px solid #bac8da;border-radius:6px;background:white}button{cursor:pointer}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}.card,details,.cost{background:white;border:1px solid #dbe2ec;border-radius:9px;padding:14px;margin-bottom:14px}
h2{font-size:18px;margin:0 0 10px}h3{font-size:16px;margin:0 0 10px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:7px;border-bottom:1px solid #e5eaf0;text-align:left;vertical-align:top}th{background:#f6f8fb}
.selected{background:#edf5ff}.muted{color:#63758b;font-size:13px}.tag{font-size:12px;padding:2px 6px;background:#edf1f7;border-radius:4px}
pre{font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-height:520px;overflow:auto;margin:10px 0 0}summary{cursor:pointer;font-weight:600}.wide{overflow-x:auto}
@media(max-width:1000px){.cards{grid-template-columns:1fr}header,main,nav{padding-left:15px;padding-right:15px}}
</style>
<header><h1>EX-064 · 후보 상태와 결정별 지침 비교</h1>
<p>C1 원입력·원지침 / C2 지침만 변경 / C3 보완 입력·C2와 동일 지침. 원 18결정과 합법 후보를 비교하는 오프라인 개발 진단입니다.</p>
<p>q는 보정된 실제 승률이 아닙니다. 별도 상태 예측은 내부 사고 과정이나 실제 q 산출에 그 예측을 사용했다는 증거가 아닙니다.</p></header>
<nav><a href="comparison.json" download>전체 비교 JSON</a><a href="conditions/C1.json" download>C1 입력</a><a href="conditions/C2.json" download>C2 입력</a><a href="conditions/C3.json" download>C3 입력</a><a href="diffs.json" download>입력 차이</a><a href="rubric.json" download>독립 기준</a><a href="result.json" download>결과 JSON</a><a href="report.md">한국어 보고</a></nav>
<main><div class="cost wide" id="cost"></div><div class="controls"><button id="previous">이전</button><select id="decision"></select><button id="next">다음</button><span id="position" class="muted"></span></div>
<h2 id="title"></h2><p id="original" class="muted"></p><div id="rankings" class="cards"></div>
<div id="diagnostics"></div><details><summary>현재 결정의 입력 차이</summary><pre id="diff"></pre></details><details><summary>현재 결정의 조건별 입력 JSON</summary><pre id="inputs"></pre></details>
<p class="muted">학습에 노출된 대진이며 새로운 입력 형식의 영향도 포함합니다. 몇 장면의 개선이나 후보 순위 변화로 전체 배틀 승률 개선을 주장하지 않습니다. 새 배틀 전송과 추가 학습은 0입니다.</p></main>
<script type="application/json" id="comparison-data">__COMPARISON_DATA__</script>
<script type="application/json" id="download-data">__DOWNLOAD_DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('comparison-data').textContent);
const downloads=JSON.parse(document.getElementById('download-data').textContent);
// file:// download attributes may navigate; use the exact bundled file bytes.
if(typeof DecompressionStream==='function'&&typeof Blob==='function'&&typeof URL.createObjectURL==='function'){
 document.querySelectorAll('a[download]').forEach(anchor=>{
  const name=anchor.getAttribute('href');if(!Object.hasOwn(downloads,name))return;
  anchor.addEventListener('click',async event=>{
   event.preventDefault();
   try{
    const compressed=Uint8Array.from(atob(downloads[name]),character=>character.charCodeAt(0));
    const stream=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
    const bytes=await new Response(stream).arrayBuffer();
    const url=URL.createObjectURL(new Blob([bytes],{type:'application/json;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download=anchor.getAttribute('download')||name.split('/').pop();
    link.hidden=true;document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),5000);
   }catch(_error){window.location.href=anchor.href;}
  });
 });
}
const conditions=['C1','C2','C3'];let selected=0;
const element=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);return e;};
const pretty=value=>JSON.stringify(value,null,2);
const table=(head,rows)=>{const t=element('table'),h=element('thead'),tr=element('tr');head.forEach(v=>tr.append(element('th',v)));h.append(tr);t.append(h);const b=element('tbody');rows.forEach(row=>{const r=element('tr');row.forEach(v=>r.append(element('td',v)));b.append(r);});t.append(b);return t;};
const details=(title,value)=>{const d=element('details');d.append(element('summary',title),element('pre',pretty(value)));return d;};
const select=document.getElementById('decision');
data.decisions.forEach((d,i)=>{const o=element('option',`${i+1}. ${d.turn}턴 · ${d.kind}`);o.value=String(i);select.append(o);});
const num=value=>value===null||value===undefined?'미측정':Number(value).toFixed(3);
const cost=document.getElementById('cost');cost.append(element('h2','조건별 비용과 측정 분모'));
cost.append(table(['조건','q 완료/18','후보/121','누적 입력 토큰','입력 생성 초','선택 지연 평균/최대 초','별도 진단 시도/30','진단 입력/출력 토큰','진단 시간 초'],conditions.map(c=>{const q=data.result.q[c],m=q.costs,d=data.result.diagnostics[c];return[c,`${q.completed}/18`,`${q.observed_candidates}/121`,m.input_tokens.toLocaleString(),num(m.input_generation_seconds),`${num(m.selection_seconds_mean)} / ${num(m.selection_seconds_max)}`,`${d.attempted}/30`,`${d.input_tokens.toLocaleString()} / ${d.output_tokens.toLocaleString()}`,num(d.roundtrip_seconds)];})));
cost.append(element('p','선택 지연은 입력 생성 시간을 제외합니다. 진단 호출 비용은 q 비교 비용과 분리했습니다.'));
function render(){
 const d=data.decisions[selected];select.value=String(selected);document.getElementById('position').textContent=`${selected+1} / ${data.decisions.length}`;
 document.getElementById('title').textContent=`${d.turn}턴 · ${d.kind} · ${d.decision}`;
 const actionById=new Map(d.actions.map(a=>[a.action_id,a]));const original=actionById.get(d.original_choice);
 document.getElementById('original').textContent=`원 EX-063 선택: ${original?original.label:d.original_choice} (${d.original_choice}); 실제 전송: ${d.original_wire.command}`;
 const panels=document.getElementById('rankings');panels.replaceChildren();
 conditions.forEach(c=>{const card=element('section');card.className='card';card.append(element('h3',c));
  const result=data.result.rankings.find(r=>r.condition===c&&r.decision===d.decision);
  if(result){const chosen=result.values[0]?.action_id;const rows=result.values.map(r=>{const a=actionById.get(r.action_id);return[r.rank,a?a.label:r.action_id,r.action_id,r.q.toFixed(6),r.action_id===chosen?'선택':'',a?a.command:''];});const t=table(['순위','후보','ID','q','선택','명령'],rows);t.querySelector('tbody tr')?.classList.add('selected');card.append(t);}else card.append(element('p','미완료 또는 실패: 결과 원장의 분모를 확인하세요.'));panels.append(card);
 });
 document.getElementById('diff').textContent=pretty(d.comparison);document.getElementById('inputs').textContent=pretty(d.inputs);
 const diagnostics=document.getElementById('diagnostics');diagnostics.replaceChildren();
 const cases=data.cases.filter(c=>c.decision===d.decision);
 if(!cases.length)diagnostics.append(element('p','이 일반 행동은 별도 모델 상태 진단 대상 장면에 포함되지 않습니다.'));
 cases.forEach(c=>{const a=actionById.get(c.action_id);diagnostics.append(element('h2',`별도 상태 진단 · ${a?a.label:c.action_id}`));diagnostics.append(details('조건부 시나리오와 독립 판단 기준',{scenario:c.scenario,rubric:data.rubric.find(r=>r.case_id===c.case_id)}));
  const grid=element('div');grid.className='cards';conditions.forEach(condition=>{const p=data.result.predictions.find(r=>r.condition===condition&&r.case_id===c.case_id);const raw=data.diagnoses.find(r=>r.condition===condition&&r.case_id===c.case_id);const card=element('section');card.className='card';card.append(element('h3',`${condition} · ${p?p.status:'unattempted'}`));card.append(element('pre',pretty(p?.prediction??null)));card.append(details('독립 rubric 판정',p?.checks??[]));if(raw)card.append(details('모델 응답 원문과 비용',raw));grid.append(card);});diagnostics.append(grid);
  const code=data.result.calculated_states.find(r=>r.case_id===c.case_id);diagnostics.append(details('C3 코드 계산 결과 · 모델 예측과 별도',code?.evaluation??null));
 });
}
select.addEventListener('change',()=>{selected=Number(select.value);render();});
document.getElementById('previous').addEventListener('click',()=>{selected=Math.max(0,selected-1);render();});
document.getElementById('next').addEventListener('click',()=>{selected=Math.min(data.decisions.length-1,selected+1);render();});
document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;if(e.key==='ArrowLeft'){selected=Math.max(0,selected-1);render();}if(e.key==='ArrowRight'){selected=Math.min(data.decisions.length-1,selected+1);render();}});
if(data.decisions.length)render();
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(export(args.study, args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
