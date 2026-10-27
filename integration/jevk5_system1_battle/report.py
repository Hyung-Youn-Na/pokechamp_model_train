"""Aggregate sealed shard results without rewriting their raw event sequences."""
import html
import json
import time
from pathlib import Path
import numpy as np
from integration.jev27b.study import verify_seal,write_json,file_hash,seal
from .core import ROOT,ROOT_RUN,EXPORT_ROOT


def interval(values):
    values=np.asarray(values,dtype=float)
    if not len(values):return None
    rng=np.random.default_rng(42)
    means=values[rng.integers(0,len(values),size=(10000,len(values)))].mean(axis=1)
    return dict(mean=float(values.mean()),ci95=np.quantile(means,[.025,.975]).tolist(),pairs=len(values),replicates=10000,seed=42)


def aggregate(results,schedule):
    expected={r['slot_id']:r for r in schedule};outcomes=[];seen=set();pairs={}
    for gpu,result in results.items():
        for o in result['outcomes']:
            assert o['slot_id'] in expected and o['slot_id'] not in seen
            seen.add(o['slot_id']);source=expected[o['slot_id']]
            assert all(o[k]==v for k,v in source.items()),('schedule drift',o['slot_id'])
            outcomes.append(dict(o,physical_gpu=gpu,local_slot=o['slot']))
        for key,value in result['pair_scores'].items():
            assert key not in pairs; pairs[key]=value
    order={r['slot_id']:i for i,r in enumerate(schedule,1)}
    outcomes.sort(key=lambda o:order[o['slot_id']])
    for o in outcomes:o['global_slot']=order[o['slot_id']]
    valid=[o for o in outcomes if o.get('completed') and o.get('audit_passed') and not o.get('error')]
    overall=dict(games=len(valid),wins=sum(o['outcome']=='player_won' for o in valid),draws=sum(o['outcome']=='tied' for o in valid),losses=sum(o['outcome']=='player_lost' for o in valid))
    overall['score']=(overall['wins']+.5*overall['draws'])/len(valid) if valid else None
    return dict(planned=len(schedule),attempted=len(outcomes),completed=len(valid),
        failed=sum(not o.get('completed') for o in outcomes),invalid=sum(o.get('completed',False) and (not o.get('audit_passed') or bool(o.get('error'))) for o in outcomes),
        unattempted=len(schedule)-len(outcomes),completed_pairs=len(pairs),pair_scores=pairs,overall=overall,outcomes=outcomes,
        passed=len(valid)==len(schedule)==32 and len(pairs)==16 and len(results)==3 and all(r['passed'] for r in results.values()))


def global_viewer(result,summary):
    EXPORT_ROOT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for o in result['outcomes']:
        link=f"gpu{o['physical_gpu']}/battle-{o['local_slot']}/index.html"
        assert (EXPORT_ROOT/link).is_file()
        rows.append(f"<tr><td>{o['global_slot']}</td><td>{html.escape(o['slot_id'])}</td><td>{o['physical_gpu']}</td><td>{o['jev_actor']}</td><td>{html.escape(o.get('outcome','미완료'))}</td><td>{o.get('turns','—')}</td><td><a href='{link}'>입력·응답·리플레이</a></td></tr>")
    s=result['overall']
    text='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EX-123 JevK5 System One 실전32</title><style>body{max-width:1100px;margin:28px auto;padding:16px;font:16px/1.6 system-ui}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}.scroll{overflow:auto}</style>'
    text+='<p><a href="../index.html">실험 목록</a></p><h1>EX-123 · JevK5 System One 대 Abyssal</h1>'
    text+=f"<p>정상 {result['completed']}/{result['planned']}경기 · {s['wins']}승 {s['draws']}무 {s['losses']}패 · 완료 {result['completed_pairs']}/16쌍</p>"
    text+='<p>EX116 선택 epoch2 · 상세 v6 · GPU1/2/3 독립 replica · T=1. 과거 고정 대진의 전이 탐색이며 학습만의 인과효과나 일반 승률을 뜻하지 않습니다.</p>'
    text+=f"<p>실패 {result['failed']} · 무효 {result['invalid']} · 미실행 {result['unattempted']}. 원자료는 GPU별로 보존하며 아래 번호는 원래32슬롯 순서입니다.</p>"
    text+='<div class="scroll"><table><tr><th>경기</th><th>대진</th><th>GPU</th><th>진영</th><th>결과</th><th>턴</th><th>열기</th></tr>'+''.join(rows)+'</table></div><p><a href="summary.json">집계·출처</a></p></html>'
    (EXPORT_ROOT/'index.html').write_text(text);write_json(EXPORT_ROOT/'summary.json',summary)


def finalize():
    manifest=json.loads((ROOT_RUN/'manifest.json').read_text());results={};cleanups={};receipts={}
    for gpu in (1,2,3):
        run=ROOT_RUN/'shards'/f'gpu{gpu}';source=run/'collection'
        if not (source/'result.json').exists():continue
        verify_seal(source);verify_seal(EXPORT_ROOT/f'gpu{gpu}')
        m=json.loads((source/'manifest.json').read_text())
        for key in ['schema_version','teams','prompt','input_data_identity','source']:assert m[key]==manifest[key],key
        assert m['schedule']==manifest['shards'][str(gpu)]
        assert json.loads((source/'final-audit.json').read_text())['passed']
        assert json.loads((run/'browser.json').read_text())['passed']
        results[gpu]=json.loads((source/'result.json').read_text())
        cleanups[gpu]=json.loads((run/'owned-server-cleanup.json').read_text())
        receipts[gpu]=dict(source=str(source),seal_sha256=file_hash(source/'checksums.sha256'),viewer=str(EXPORT_ROOT/f'gpu{gpu}'))
    result=aggregate(results,manifest['schedule']);write_json(ROOT_RUN/'result.json',result)
    comparisons={}
    for ex in ['EX-111','EX-114']:
        directory=ROOT_RUN.parent/ex/'collection';verify_seal(directory)
        m=json.loads((directory/'manifest.json').read_text());old=json.loads((directory/'result.json').read_text())
        for key in ['schema_version','teams','prompt','input_data_identity','schedule']:assert m[key]==manifest[key],(ex,key)
        common=sorted(set(old['pair_scores'])&set(result['pair_scores']))
        comparisons[ex]=dict(overall=old['overall'],paired_difference=interval([result['pair_scores'][k]-old['pair_scores'][k] for k in common]),causal_evidence=False)
    total=lambda name:sum(r[name] for r in results.values())
    lengths=[v for r in results.values() for v in r['input_tokens']];latencies=[v for r in results.values() for v in r['http_latency_seconds']]
    summary={k:v for k,v in result.items() if k!='outcomes'}
    summary.update(score_interval=interval([result['pair_scores'][k] for k in sorted(result['pair_scores'])]),comparisons=comparisons,
        requests=total('requests'),preflight_requests=total('preflight_requests'),automatic_actions=total('automatic_actions'),sent_actions=total('sent_actions'),retry_attempts=total('retry_attempts'),
        received_usage={k:sum(r['received_usage'][k] for r in results.values()) for k in ['input_tokens','output_tokens']},
        unknown_usage_attempts=total('usage_unknown_attempts'),input_length=dict(min=min(lengths,default=None),max=max(lengths,default=None),over_training_limit=sum(v>6144 for v in lengths),n=len(lengths)),
        latency=dict(median=float(np.median(latencies)) if latencies else None,p95=float(np.percentile(latencies,95)) if latencies else None),
        source_shards=receipts,temperature=1,selected_epoch=2,adapter_dtype='bfloat16',base_dtype='bfloat16',gpu_cleanup=cleanups)
    evidence=ROOT_RUN/'evidence';evidence.mkdir(exist_ok=True);write_json(evidence/'summary.json',summary)
    global_viewer(result,summary)
    from .global_browser import inspect
    inspect(EXPORT_ROOT,ROOT_RUN/'global-browser.json',len(result['outcomes']))
    s=result['overall'];lines=['# EX-123 System One JevK5 실전32','',f"정상 {result['completed']}/32 · {s['wins']}승 {s['draws']}무 {s['losses']}패 · 완전 {result['completed_pairs']}/16쌍.",
        f"실패 {result['failed']} · 무효 {result['invalid']} · 미실행 {result['unattempted']}. 미완료를 패배로 바꾸지 않는다.",'',f"완전쌍 점수의 탐색95%구간: {summary['score_interval']}",'',
        '| 과거 동일대진 | 승/무/패 | 쌍점수 차이·95%구간 |','|---|---|---|']
    for ex,c in comparisons.items():
        b=c['overall'];lines.append(f"| {ex} | {b['wins']}/{b['draws']}/{b['losses']} | {c['paired_difference']} |")
    lines+=['','EX116 선택epoch2를 원본JevK5에 비병합 LoRA로 적용했다. GPU1/2/3에12/10/10경기를 배정했고 진영교환쌍은 같은GPU에서 수행했다. T=1·후보점수 첫argmax이며 생성토큰을 정책으로 사용하지 않았다.',
        '상세v6·원팀/게임seed/actor seed·양측테라를 유지했다. 입력 절단·요약·후보제거·학습·추가경기·재수집은 없다.',
        '학습의 FP32 LoRA와 달리 vLLM에서는 BF16 LoRA를 사용한다. backend/정밀도/동시성/학습자료 차이가 있으므로 과거점수 차이를 이번학습만의 인과효과로 해석하지 않는다. 개발에 사용한 고정대진이며 일반 상대·새팀 성능을 보장하지 않는다.',
        f"실제 요청 {summary['requests']}, 사전요청 {summary['preflight_requests']}, 자동선택 {summary['automatic_actions']}, 재시도 {summary['retry_attempts']}. 확인된사용량 {summary['received_usage']}. 입력길이 {summary['input_length']}.",
        '학습최대6144를 넘는 입력의 전이 한계를 유지한다. 확률은 선택지 내 점수이며 승률이나 배틀 보정 성능을 뜻하지 않는다.',
        '',f'[32경기 뷰어]({EXPORT_ROOT}/index.html) · [상세 집계](summary.json). 원문/감사/봉인은 각shard에 보존했다.']
    (evidence/'report.md').write_text('\n'.join(lines)+'\n')
    cleaned=len(cleanups)==3 and all(c['stopped'] and c['gpu_released'] and c['lock_released'] and not c['resource_error'] for c in cleanups.values())
    completed=result['passed'] and cleaned
    write_json(ROOT_RUN/'completion.json',dict(completed=completed,normal_games=result['completed'],complete_pairs=result['completed_pairs'],all_owned_resources_released=cleaned,viewer_passed=True,at=time.time()))
    top=ROOT/'exports/battle_viewers/index.html';text=top.read_text();entry=f'<li><a href="ex123/index.html">EX-123 — JevK5 System One 실전32</a> · {s["wins"]}승{s["draws"]}무{s["losses"]}패 · 정상{result["completed"]}/32</li>'
    if 'href="ex123/index.html"' not in text:top.write_text(text.replace('<ul>','<ul>'+entry,1))
    seal(EXPORT_ROOT)
    return summary
