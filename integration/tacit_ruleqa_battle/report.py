"""Decision audit, explicit denominators, and standalone offline viewer."""
import collections
import html
import json
import random
import statistics
from pathlib import Path
from .core import ROOT,RUN,build_input,select
from .storage import write,digest,seal


def audit_events(events):
    errors=[]
    grouped={}
    for e in events:
        if e.get('decision'):
            grouped.setdefault(e['decision'],[]).append(e)
    for decision,rows in grouped.items():
        by={kind:[r for r in rows if r['type']==kind] for kind in ('input','response','selection','wire')}
        if len(by['input'])!=1:
            errors.append(f'{decision}: input count');continue
        inp=by['input'][0];legal=inp['payload']['candidates']
        if len(by['response'])>1 or len(by['selection'])>1 or len(by['wire'])>1:
            errors.append(f'{decision}: duplicate event')
        if by['selection']:
            selection=by['selection'][0]
            response=by['response'][0] if by['response'] else None
            if bool(response)!=(len(legal)>1):
                errors.append(f'{decision}: model/automatic mismatch')
            expected=select(response['raw'] if response else '',legal,inp['slot_id'],decision)
            if any(selection[k]!=v for k,v in expected.items()):
                errors.append(f'{decision}: parsing/fallback mismatch')
            candidate=next((c for c in legal if c['id']==selection['choice']),None)
            if not candidate or candidate['command']!=selection['command'] or selection['revalidated_candidates']!=legal:
                errors.append(f'{decision}: candidate/command mismatch')
            if selection['latest_request_id']!=inp['official']['request']['rqid'] or selection['revalidated_request_id']!=selection['latest_request_id']:
                errors.append(f'{decision}: request boundary mismatch')
            if not by['wire']:
                errors.append(f'{decision}: selected but not sent')
        if by['wire']:
            wire=by['wire'][0]
            if not by['selection'] or wire['command']!=by['selection'][0]['command'] or 'terastallize' in wire['command'] or wire['request_id']!=inp['official']['request']['rqid']:
                errors.append(f'{decision}: wire mismatch')
    return dict(passed=not errors,errors=errors,decisions=len(grouped),wires=sum(e['type']=='wire' for e in events))


def quantile(values,q):
    if not values:return None
    ordered=sorted(values);pos=(len(ordered)-1)*q;low=int(pos);high=min(low+1,len(ordered)-1)
    return ordered[low]+(ordered[high]-ordered[low])*(pos-low)


def summarize(manifest,result,events):
    outcomes=result.get('outcomes',[])
    completed=[r for r in outcomes if r.get('completed')]
    scores={'player_won':1,'player_lost':0,'tied':.5}
    pairs=collections.defaultdict(list)
    for row in completed:pairs[row['paired_slot_id']].append(scores[row['outcome']])
    means=[sum(v)/2 for v in pairs.values() if len(v)==2]
    rng=random.Random(42)
    boot=[sum(rng.choices(means,k=len(means)))/len(means) for _ in range(10000)] if means else []
    inputs={e['decision']:e for e in events if e['type']=='input'}
    responses={e['decision']:e for e in events if e['type']=='response'}
    attempts={e['decision'] for e in events if e['type']=='model_call'}
    selections={e['decision']:e for e in events if e['type']=='selection'}
    metrics={}
    for kind in ('lead','turn_action','forced_switch'):
        ids=[k for k,v in inputs.items() if v['payload']['kind']==kind]
        rs=[responses[k] for k in ids if k in responses];ss=[selections[k] for k in ids if k in selections]
        called=[s for s in ss if not s['automatic']]
        ncalls=sum(k in attempts for k in ids)
        rate=lambda n,d:n/d if d else None
        errors=collections.Counter(s['error'] for s in called if s['error'])
        metrics[kind]=dict(decisions=len(ids),model_calls=ncalls,received_responses=len(rs),selected=len(ss),
            parsing_success=sum(bool(s['parsed']) for s in called),
            parsing_success_rate=rate(sum(bool(s['parsed']) for s in called),ncalls),
            first_legal=sum(not s['error'] for s in called),first_legal_rate=rate(sum(not s['error'] for s in called),ncalls),
            errors=dict(errors),fallback=sum(s['fallback'] for s in ss),fallback_rate=rate(sum(s['fallback'] for s in ss),len(ids)),
            automatic=sum(s['automatic'] for s in ss),automatic_rate=rate(sum(s['automatic'] for s in ss),len(ids)),
            input_tokens=sum(r['input_tokens'] for r in rs),output_tokens=sum(r['output_tokens'] for r in rs),
            input_min=min((r['input_tokens'] for r in rs),default=None),input_max=max((r['input_tokens'] for r in rs),default=None),
            input_median=statistics.median([r['input_tokens'] for r in rs]) if rs else None,
            over5120=sum(r['input_tokens']>5120 for r in rs),over5120_rate=rate(sum(r['input_tokens']>5120 for r in rs),len(rs)),
            truncated=sum(r['truncated'] for r in rs),truncated_rate=rate(sum(r['truncated'] for r in rs),len(rs)),
            latency_median=quantile([r['latency_seconds'] for r in rs],.5),latency_p95=quantile([r['latency_seconds'] for r in rs],.95))
    fallback_games={inputs[k]['slot_id'] for k,s in selections.items() if s['fallback']}
    return dict(label='Tacit RuleQA와 등록된 무작위 대체 정책이 결합된 결과',planned=32,
        completed=len(completed),failed=sum(r.get('outcome')=='failed' for r in outcomes),
        incomplete=sum(r.get('outcome')=='incomplete' for r in outcomes),invalid=0,unplayed=32-len(outcomes),
        wins=sum(r['outcome']=='player_won' for r in completed),draws=sum(r['outcome']=='tied' for r in completed),
        losses=sum(r['outcome']=='player_lost' for r in completed),
        score=sum(scores[r['outcome']] for r in completed)/len(completed) if completed else None,
        complete_pairs=len(means),paired_mean=statistics.mean(means) if means else None,
        bootstrap95=[quantile(boot,.025),quantile(boot,.975)],bootstrap_unit='complete side-swapped pair',
        fallback_games=len(fallback_games),metrics=metrics,error=result.get('error'))


def export():
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    manifest=json.loads((RUN/'manifest.json').read_text())
    result_path=RUN/'collection/result.json'
    result=json.loads(result_path.read_text()) if result_path.exists() else dict(outcomes=[],error=json.loads((RUN/'execution-result.json').read_text()).get('error'))
    event_path=RUN/'collection/events.jsonl'
    events=[json.loads(l) for l in event_path.open()] if event_path.exists() else []
    audit=audit_events(events)
    dex=json.loads((DEFAULT_BUILD/'dex.json').read_text())
    for e in events:
        if e['type']=='input':
            rebuilt=build_input(e['official'],e['prefix'],e['actor'],dex,e['own_team'])
            if rebuilt!=e['payload']:audit['errors'].append(e['decision']+': input reconstruction differs')
    for attempt in (RUN/'collection').glob('battle-*'):
        wire=attempt/'abyssal-wire.jsonl'
        if wire.exists() and 'terastallize' in wire.read_text():audit['errors'].append(attempt.name+': Abyssal tera')
        seed_path=attempt/'battle-seed.jsonl'
        if seed_path.exists():
            actual=[json.loads(l) for l in seed_path.open()]
            request=json.loads((attempt/'request.json').read_text())
            if actual != [dict(seed=request['slot']['battle_seed'],format='gen9ou')]:
                audit['errors'].append(attempt.name+': battle seed mismatch')
            write(attempt/'seed-audit.json',dict(recorded=actual))
    for row in result['outcomes']:
        if row.get('completed'):
            protocol='\n'.join(e['protocol'] for e in events if e['type']=='protocol' and e['username']==row['username'])
            terminals=[line for line in protocol.splitlines() if (line.startswith('|win|') or line in ('|tie','|tie|'))]
            expected='|win|'+row['username'] if row['outcome']=='player_won' else '|tie|' if row['outcome']=='tied' else None
            if len(terminals)!=1 or expected and terminals[0].rstrip('|')!=expected.rstrip('|') or row['outcome']=='player_lost' and terminals[0]=='|win|'+row['username']:
                audit['errors'].append(row['slot_id']+': terminal mismatch')
            ids={e['decision'] for e in events if e['type']=='input' and e['slot_id']==row['slot_id']}
            wires={e['decision'] for e in events if e['type']=='wire'}
            if not ids or not ids.issubset(wires):
                audit['errors'].append(row['slot_id']+': unfinished decision in completed battle')
    requests_path=RUN/'model-requests.jsonl';responses_path=RUN/'model-responses.jsonl'
    requests=[json.loads(l) for l in requests_path.open()] if requests_path.exists() else []
    raw_responses=[json.loads(l) for l in responses_path.open()] if responses_path.exists() else []
    main_requests=[r for r in requests if not r['id'].startswith('gate:')]
    calls=[e for e in events if e['type']=='model_call']
    if [r['id'] for r in main_requests] != [e['decision'] for e in calls]:
        audit['errors'].append('physical model calls differ from decision attempts')
    audit['physical_calls']=len(requests);audit['physical_responses']=len(raw_responses)
    audit['passed']=not audit['errors']
    write(RUN/'audit.json',audit)
    report=summarize(manifest,result,events)
    report['audit_passed']=audit['passed']
    report['resources']=json.loads((RUN/'model-cleanup.json').read_text()) if (RUN/'model-cleanup.json').exists() else None
    write(RUN/'report.json',report)
    (RUN/'report.md').write_text('# EX-108 Tacit RuleQA 첫 배틀\n\n'+report['label']+'\n\n'+
        f"정상 {report['completed']}/32, 실패 {report['failed']}, 미완료 {report['incomplete']}, 미실행 {report['unplayed']}.\n"+
        f"승/무/패 {report['wins']}/{report['draws']}/{report['losses']}; 대체 발생 경기 {report['fallback_games']}.\n\n"+
        '과거 JEV와 직접 성능 비교를 하지 않는다. EX107 선택 어댑터의 탐색 성적이며 미학습 기반과의 직접 비교는 수행하지 않았다.\n\n'+
        '세부 분모·토큰·지연·자원은 report.json, 결정 감사는 audit.json에 기록한다.\n')
    output=ROOT/'exports/battle_viewers/ex108';output.mkdir(parents=True,exist_ok=True)
    # Standalone HTML embeds escaped raw text, so file:// needs no fetch or external assets.
    links=[]
    inputs={e['decision']:e for e in events if e['type']=='input'}
    for row in result['outcomes']:
        slot=row['slot_id'];name=f"battle-{row['slot']}.html";links.append(f'<li><a href="{name}">{html.escape(slot)}: {html.escape(row.get("outcome","unknown"))}</a></li>')
        decisions=[]
        for key,inp in inputs.items():
            if inp['slot_id']!=slot:continue
            related={e['type']:e for e in events if e.get('decision')==key}
            payload=inp['payload'];response=related.get('response');selection=related.get('selection')
            decisions.append(f'<section class="decision"><h2>{html.escape(key)} · turn {inp["official"]["turn"]} · {payload["kind"]}</h2>'+block('입력',payload['messages'])+block('원응답',response['raw'] if response else '모델 호출 없음')+block('파싱·대체·실행',selection)+block('전송',related.get('wire'))+'</section>')
        protocol=[]
        for e in events:
            if e['type']=='protocol' and e['username']==row['username']:
                protocol.extend(l for l in e['protocol'].splitlines() if not l.startswith('|request|') and not l.startswith('>'))
        replay='\n'.join(protocol)
        (output/f"battle-{row['slot']}.log").write_text(replay+'\n')
        from integration.pokechamp.observability.render import _replay_html
        (output/f"replay-{row['slot']}.html").write_text(_replay_html(dict(battle_id=f"ex108-battle-{row['slot']}",teams=[]),replay))
        body='<a href="index.html">목록</a><h1>'+html.escape(slot)+'</h1>'+block('결과',row)+''.join(decisions)
        body+=f'<p><a href="replay-{row["slot"]}.html">Showdown 리플레이</a> (애니메이션은 외부 자산 연결 필요)</p>'
        body+='<h2>공개 리플레이 · 턴 로그</h2><p>오프라인 텍스트 재생. 다음 턴 버튼으로 순서대로 표시합니다.</p><button id="next">다음 턴</button><button id="all">전체</button><pre id="replay"></pre>'
        parts=replay.split('|turn|');encoded=json.dumps(parts,ensure_ascii=False).replace('<','\\u003c')
        body+=f'<script>const turns={encoded};let cursor=1;function show(){{document.getElementById("replay").textContent=turns.slice(0,cursor).join("|turn|");}}document.getElementById("next").onclick=()=>{{cursor=Math.min(cursor+1,turns.length);show();}};document.getElementById("all").onclick=()=>{{cursor=turns.length;show();}};show();</script>'
        (output/name).write_text(page(body))
    (output/'index.html').write_text(page('<h1>EX-108 Tacit RuleQA</h1>'+block('결과·지표',report)+'<ul>'+''.join(links)+'</ul>'))
    write(output/'provenance.json',dict(source=str(RUN),manifest_sha256=digest(RUN/'manifest.json'),
        events_sha256=digest(event_path) if event_path.exists() else None,normal_completed=report['completed'],
        replay='actor public protocol, offline text playback',report=report))
    write(output/'report.json',report)
    index=output.parent/'index.html'
    if index.exists():
        text=index.read_text()
        if 'ex108/index.html' not in text:
            index.write_text(text.replace('</body>','<p><a href="ex108/index.html">EX-108 Tacit RuleQA 첫 배틀</a></p></body>'))
    seal(output)
    return report


def block(title,value):
    text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)
    return '<details open><summary>'+html.escape(title)+'</summary><pre>'+html.escape(text)+'</pre></details>'


def page(body):
    controls="""<script>document.querySelectorAll('details pre').forEach((pre,i)=>{const bar=document.createElement('div');const copy=document.createElement('button');copy.textContent='복사';copy.onclick=()=>{const t=document.createElement('textarea');t.value=pre.textContent;document.body.append(t);t.select();document.execCommand('copy');t.remove();};const download=document.createElement('a');download.textContent='다운로드';download.download='record-'+i+'.txt';download.href=URL.createObjectURL(new Blob([pre.textContent],{type:'text/plain'}));bar.append(copy,download);pre.before(bar);});</script>"""
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>EX-108 Tacit RuleQA</title><style>body{font:16px system-ui;max-width:1100px;margin:2em auto;padding:1em;background:#fafafa;color:#18232e}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef2f5;padding:1em}section{border-top:2px solid #678;margin-top:2em}button{padding:.7em;margin:.3em}</style><body>'+body+controls+'</body></html>'
