"""EX115 portable UI-v1 renderer, every response attempt and final choice."""
import base64
import gzip
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

from integration.jev27b.study import verify_seal, seal, file_hash, write_json, decision_groups, event_rows
from integration.jev_eval.turn_logs import build_turn_log, raw_text
from integration.openai_decisions_matchup_battle.viewer_v1 import style, script_json, render_replay
from integration.openai_decisions_battle.core import ROOT
from .transform import restore

HERE=Path(__file__).parent
RENDERER='candidate-action-researcher-v2'
UI_VERSION='battle-viewer-ui-v1'
EXTENSIONS=['재구성 전 입력','후보별 적용 결과','선택·전송']


def render(data):
    script=(ROOT/'integration/pokechamp/viewer_assets/action-labels.js').read_text()+'\n'+(HERE/'viewer.js').read_text()
    sha=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp=f"default-src 'none'; script-src 'sha256-{sha}'; style-src 'unsafe-inline'; frame-src 'self' file:; object-src 'none'; base-uri 'none'; connect-src 'none'"
    replacements={'__TITLE__':html.escape(f"{data['experiment']} · {data['slot']}경기"),'__CSP__':html.escape(csp,quote=True),
        '__STYLE__':style(),'__DATA__':script_json(data),'__SCRIPT__':script}
    return re.sub('|'.join(re.escape(k) for k in replacements),lambda m:replacements[m[0]],(HERE/'viewer.html').read_text())


def export(source, output):
    source,output=Path(source),Path(output)
    verify_seal(source)
    manifest=json.loads((source/'manifest.json').read_text())
    experiment=manifest['experiment_id']
    if experiment not in ('EX-115','EX-117') or manifest['input_profile']!='candidate-action-v1':
        raise ValueError('unregistered source')
    result=json.loads((source/'result.json').read_text())
    events=list(event_rows(source)); groups=decision_groups(source)
    inputs={e['decision']:e for e in events if e['type']=='input'}
    history={key:[] for key in inputs}
    for e in events:
        if e.get('decision') in history: history[e['decision']].append(e)
    output.mkdir(parents=True,exist_ok=False);(output/'raw').mkdir()
    originals={}
    for name in ('manifest.json','events.jsonl','result.json','checksums.sha256','final-audit.json','ledger.json'):
        shutil.copyfile(source/name,output/'raw'/name);originals[name]=file_hash(source/name)
    count=0;rows=[]
    for outcome in result['outcomes']:
        decisions=groups.get(outcome['username'],[])
        for d in decisions:
            inp=inputs[d['id']];records=history[d['id']]
            d['observation']=inp['payload']
            evidence=source/inp['input_audit']['path']
            assert file_hash(evidence)==inp['input_audit']['sha256']
            audit=json.loads(gzip.decompress(evidence.read_bytes()))
            d['base_observation']=audit['candidate_action']['original_payload']
            assert restore(d['observation'])==d['base_observation']
            d['response_attempts']=[e for e in records if e['type']=='http_response']
            raw=d['response_attempts'][-1]['raw_body'] if d['response_attempts'] else None
            try: d['raw_response']=json.loads(raw) if raw is not None else None
            except ValueError: d['raw_response']=raw
            d['technical']['http_attempt_history']=[e for e in records if e['type'] in (
                'transport','http_request','http_response','attempt_failure','provider_retry','response_attempt','response_retry','request_cancelled')]
            d['technical']['input_audit']=inp['input_audit']
            target=output/'raw'/inp['input_audit']['path'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(evidence,target)
            assert file_hash(target)==inp['input_audit']['sha256']
        log=build_turn_log(events,outcome['username'],outcome['jev_actor'],decisions)
        data=dict(experiment=experiment,slot=outcome['slot'],outcome=outcome,decisions=decisions,turn_log=log)
        target=output/f"battle-{outcome['slot']}";target.mkdir()
        write_json(target/'decisions.json',data)
        text=raw_text([row for turn in log['turns'] for row in turn['rows']])
        (target/'showdown.log').write_text(text)
        (target/'replay.html').write_text(render_replay(f"{experiment.lower().replace('-','')}-{outcome['slot']}",text))
        (target/'index.html').write_text(render(data))
        count+=len(decisions)
        rows.append(f'<tr><td><a href="battle-{outcome["slot"]}/index.html">경기 {outcome["slot"]}</a></td><td>{html.escape(outcome["slot_id"])}</td><td>{html.escape(outcome.get("outcome","미완료"))}</td></tr>')
    assert count==len(inputs)
    for name,expected in originals.items(): assert file_hash(output/'raw'/name)==expected
    score=result['overall']
    page=f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>{experiment}</title><h1>{experiment} · 후보 중심 v7 · gpt-6-luna 대 Abyssal</h1><p><a href="../index.html">실험 목록</a></p>'
    page+=f'<p>유효 {result["completed"]}/{result["planned"]} · {score["wins"]}승 {score["draws"]}무 {score["losses"]}패 · 완료쌍 {result["completed_pairs"]}/16</p>'
    description = '생존·교체 비용 지시문과 EX115의 과거 탐색 비교.' if experiment=='EX-117' else '입력 재배치와 응답 복구의 복합 탐색 비교.'
    page+=f'<p>실패 {result["failed"]} · 무효 {result["invalid"]} · 미실행 {result["unattempted"]}. {description}</p>'
    page+='<table><tbody>'+''.join(rows)+'</tbody></table><p><a href="provenance.json">출처</a> · <a href="raw/result.json">결과</a></p></html>'
    (output/'index.html').write_text(page)
    write_json(output/'provenance.json',dict(experiment=experiment,source=str(source),source_files=originals,
        source_seal_sha256=file_hash(source/'checksums.sha256'),decisions=count,ui_version=UI_VERSION,
        renderer=RENDERER,extensions=EXTENSIONS,viewer_source={str(p.relative_to(ROOT)):file_hash(p) for p in (
            Path(__file__),HERE/'viewer.html',HERE/'viewer.js',ROOT/'integration/openai_decisions_matchup_battle/viewer_v1.py',
            ROOT/'integration/pokechamp/viewer_assets/action-labels.js',ROOT/'integration/jev_planner/replay.js')},
        original_input_from_audit=True,all_http_responses=True))
    checked=audit_export(source,output)
    write_json(output/'export-audit.json',checked)
    seal(output)
    return dict(output=str(output),**checked)


def audit_export(source, output):
    """Full original-value, attempt history and public-log comparison after serialization."""
    from integration.jev_eval.turn_logs import public_rows
    events=list(event_rows(source));inputs={e['decision']:e for e in events if e['type']=='input'}
    records={k:[] for k in inputs}
    for e in events:
        if e.get('decision') in records: records[e['decision']].append(e)
    result=json.loads((source/'result.json').read_text());seen=set()
    for outcome in result['outcomes']:
        folder=output/f"battle-{outcome['slot']}";data=json.loads((folder/'decisions.json').read_text())
        assert data['outcome']==outcome
        for d in data['decisions']:
            assert d['id'] not in seen;seen.add(d['id'])
            source_records=records[d['id']];by_type={e['type']:e for e in source_records};inp=inputs[d['id']]
            assert d['observation']==inp['payload'] and d['base_observation']==restore(inp['payload'])
            assert d['request']==by_type.get('http_request',{}).get('body')
            assert d['response']==by_type.get('response',{}).get('body')
            assert d['selection']==by_type.get('selection') and d['wire']==by_type.get('wire')
            assert d['response_attempts']==[e for e in source_records if e['type']=='http_response']
            assert d['technical']['http_attempt_history']==[e for e in source_records if e['type'] in (
                'transport','http_request','http_response','attempt_failure','provider_retry','response_attempt','response_retry','request_cancelled')]
            assert data['turn_log']['decision_cutoffs'][d['id']]==dict(sequence=inp['boundary']['protocol_event_seq'],line_index=inp['boundary']['line_index'])
        rows,_,_,_=public_rows(events,outcome['username'])
        saved=[r for t in data['turn_log']['turns'] for r in t['rows']]
        assert len(saved)==len(rows) and all(all(s[k]==v for k,v in r.items()) for s,r in zip(saved,rows))
        assert raw_text(rows)==(folder/'showdown.log').read_text()
    assert seen==set(inputs)
    return dict(passed=True,decisions=len(seen),games=len(result['outcomes']))
