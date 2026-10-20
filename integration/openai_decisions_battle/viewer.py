"""실제 OpenAI 원문·v6 상태·턴 로그를 분리해 오프라인 내보낸다."""
import html
import json
import shutil
from pathlib import Path

from integration.jev27b.study import file_hash, verify_seal, seal, write_json, decision_groups, event_rows
from integration.jev_eval.turn_logs import build_turn_log, raw_text
from .core import ROOT,RUN,EXPORT


def export(source=None,output=None):
    from integration.pokechamp.observability.render import _replay_html
    source=Path(source or RUN/'collection');output=Path(output or EXPORT)
    verified=verify_seal(source)
    events=list(event_rows(source));groups=decision_groups(source)
    result=json.loads((source/'result.json').read_text())
    experiment=json.loads((source/'manifest.json').read_text())['experiment_id']
    if experiment not in ('EX-109','EX-110','EX-112'):raise ValueError('unregistered OpenAI experiment')
    inputs={e['decision']:e for e in events if e['type']=='input'}
    output.mkdir(parents=True,exist_ok=False)
    (output/'raw').mkdir()
    originals={}
    for name in ('manifest.json','events.jsonl','result.json','checksums.sha256','final-audit.json','ledger.json'):
        if (source/name).is_file():
            shutil.copyfile(source/name,output/'raw'/name);originals[name]=file_hash(source/name)
    rows=[];decision_count=0
    for outcome in result['outcomes']:
        decisions=groups.get(outcome['username'],[])
        for decision in decisions:
            decision['observation']=inputs[decision['id']]['payload']
            if experiment=='EX-112':
                from integration.candidate_matchup import remove_summaries
                decision['base_observation']=remove_summaries(decision['observation'])
            raw=decision['technical'].get('http_response')
            try:decision['raw_response']=json.loads(raw['raw_body']) if raw else None
            except ValueError:decision['raw_response']=raw['raw_body']
            decision['technical']['input_audit']=inputs[decision['id']]['input_audit']
        log=build_turn_log(events,outcome['username'],outcome['jev_actor'],decisions)
        data=dict(experiment=experiment,slot=outcome['slot'],outcome=outcome,decisions=decisions,turn_log=log)
        target=output/f"battle-{outcome['slot']}";target.mkdir()
        write_json(target/'decisions.json',data)
        text=raw_text([row for turn in log['turns'] for row in turn['rows']])
        (target/'showdown.log').write_text(text)
        (target/'replay.html').write_text(_replay_html(dict(battle_id=experiment.lower().replace('-','')+'-'+str(outcome['slot']),teams=[]),text))
        encoded=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
        page=Path(__file__).with_name('viewer.html').read_text().replace('__TITLE__',f"{experiment} · {outcome['slot']}경기").replace('__DATA__',encoded)
        (target/'index.html').write_text(page)
        decision_count+=len(decisions)
        rows.append(f'<tr><td>{outcome["slot"]}</td><td>{html.escape(outcome["slot_id"])}</td><td>{outcome["jev_actor"]}</td>'
            f'<td>{html.escape(outcome.get("outcome","미완료"))}</td><td>{outcome.get("turns","—")}</td>'
            f'<td><a href="battle-{outcome["slot"]}/index.html">입력·응답·리플레이</a></td></tr>')
    score=result['overall']
    summary=f"유효 {result['completed']}/{result['planned']} · {score['wins']}승 {score['draws']}무 {score['losses']}패 · 완료쌍 {result['completed_pairs']}/16"
    page=f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>{experiment} · OpenAI Decisions</title>'+'<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:32px auto;padding:16px}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}a{color:#165fa5}</style>'
    page+=f'<h1>{experiment} · gpt-6-luna 대 Abyssal</h1><p>{summary}</p>'
    page+='<p>v6 상세 입력·피해/스피드 포함·Planner off·테라 허용. 실제 API 요청/응답과 변환 전 상태를 구분합니다. 고정 대진 탐색 결과이며 일반 성능 우위를 확정하지 않습니다.</p>'
    page+=f'<p>실패 {result["failed"]} · 무효 {result["invalid"]} · 미실행 {result["unattempted"]}</p>'
    page+='<table><tr><th>경기</th><th>대진</th><th>진영</th><th>결과</th><th>턴</th><th>열기</th></tr>'+''.join(rows)+'</table>'
    page+='<p><a href="raw/result.json">상세 결과</a> · <a href="raw/events.jsonl">전체 원문</a> · <a href="provenance.json">출처</a></p></html>'
    (output/'index.html').write_text(page)
    write_json(output/'provenance.json',dict(experiment=experiment,source=str(source),source_files=originals,
        source_seal_sha256=file_hash(source/'checksums.sha256'),decisions=decision_count,
        viewer_source={str(p.relative_to(ROOT)):file_hash(p) for p in (Path(__file__),Path(__file__).with_name('viewer.html'))},
        actual_http_responses=True,normalized_response_separate=True,offline_input_response=True))
    # Copy the compressed calculation audit files referenced by each input.
    for event in inputs.values():
        relative=event['input_audit']['path'];target=output/'raw'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/relative,target)
        if file_hash(target)!=event['input_audit']['sha256']:raise ValueError('audit copy differs')
    for name,expected in originals.items():
        if file_hash(output/'raw'/name)!=expected:raise ValueError('original copy differs')
    seal(output)
    return dict(passed=True,output=str(output),decisions=decision_count,games=len(result['outcomes']))
