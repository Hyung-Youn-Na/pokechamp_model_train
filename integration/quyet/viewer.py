"""Portable stage evidence and a bounded, relocated offline browser check."""
import argparse
import copy
import html
import json
from pathlib import Path
import re
import shutil
import tempfile

from .config import EXPORT, ROOT, RUN
from .study import event_rows, file_hash, seal, verify_seal, write_json


def decision_groups(events):
    groups = {}
    for event in events:
        if event['type'] == 'input':
            groups[event['decision']] = dict(id=event['decision'], input=event,
                stages={'action_type': [], 'action_detail': []}, selection=None, wire=None)
        elif event.get('decision') in groups:
            target = groups[event['decision']]
            if event.get('stage') in target['stages']:
                target['stages'][event['stage']].append(event)
            elif event['type'] in ('selection', 'wire'):
                target[event['type']] = event
    battles = {}
    for key, value in groups.items():
        battles.setdefault(key.split('-')[0], []).append(value)
    return battles


def render_data(data):
    template = Path(__file__).with_name('viewer.html').read_text()
    labels = (ROOT / 'integration/pokechamp/viewer_assets/action-labels.js').read_text()
    encoded = json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    return template.replace('__DATA__', encoded).replace('__ACTION_LABELS__', labels)


def export(source=RUN / 'collection', output=EXPORT, compared=None):
    from integration.pokechamp.observability.render import _replay_html
    source, output = Path(source), Path(output)
    verify_seal(source)
    result = json.loads((source / 'result.json').read_text())
    events = list(event_rows(source)); groups = decision_groups(events)
    protocols = {}
    for event in events:
        if event['type'] == 'protocol':
            protocols.setdefault(event['username'], []).extend(line for line in event['protocol'].splitlines()
                if line.startswith('|') and not line.startswith(('|request|', '|sentchoice|')))
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for outcome in result['outcomes']:
        slot, user = outcome['slot'], outcome['username']; target = output / f'battle-{slot}'
        target.mkdir()
        data = dict(experiment='EX-084', slot=slot, outcome=outcome, decisions=groups.get(user, []))
        write_json(target / 'decisions.json', data)
        (target / 'index.html').write_text(render_data(data))
        protocol = '\n'.join(protocols.get(user, [])) + '\n'
        (target / 'showdown.log').write_text(protocol)
        (target / 'replay.html').write_text(_replay_html(dict(battle_id=f'ex084-battle-{slot}', teams=[]), protocol))
        label = dict(player_won='승리', player_lost='패배', tied='무승부', output_failure='모델 선택 실패').get(outcome.get('outcome'), '기술 중단')
        if outcome.get('completed') and not outcome.get('audit_passed'):
            label += ' · 유효성 미충족'
        rows.append(f'<tr><td>{slot}</td><td>{html.escape(outcome["slot_id"])}</td><td>{outcome["jev_actor"]}</td>'
                    f'<td>{label}</td><td>{outcome.get("turns", "—")}</td>'
                    f'<td><a href="battle-{slot}/index.html">입력·단계별 선택·리플레이</a></td></tr>')
    score = result['overall']
    summary = f'유효 {result["completed"]}/32 · {score["wins"]}승 {score["draws"]}무 {score["losses"]}패 · 완료쌍 {result["completed_pairs"]}/16'
    if result.get('final_audit_passed') is False:
        summary = '최종 기술 감사 실패 · 성적 확정 보류 · ' + summary
    (output / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>EX-084 · Quyet-Medium</title>'
        '<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:35px auto;padding:0 20px;background:#f4f8f8;color:#173c43}table{width:100%;border-collapse:collapse}td,th{padding:8px;text-align:left;border-bottom:1px solid #cdd}a{color:#087678}</style>'
        '<a href="../index.html">← 실험 목록</a><h1>EX-084 · Quyet-Medium 대 Abyssal</h1>'
        f'<p>{summary}</p><p>Quyet-Medium + 2단계 정책 + 긴 입력 확장의 고정 대진 탐색 평가입니다. '
        'EX-083 대비 차이는 모델 가중치만의 효과로 해석하지 않습니다.</p>'
        '<p>전체 입력·응답·단계별 원문·공개 로그를 오프라인에서 열 수 있습니다. 리플레이 애니메이션에는 인터넷 연결이 필요합니다.</p>'
        f'<p>실패 {result["failed"]} · 무효 {result["invalid"]} · 미실행 {result["unattempted"]}</p>'
        '<table><thead><tr><th>경기</th><th>대진</th><th>진영</th><th>결과</th><th>턴</th><th>열기</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table><p><a href="result.json">상세 결과</a> · '
        '<a href="comparison.json">EX-083 공통쌍 비교</a></p></html>')
    write_json(output / 'result.json', result);write_json(output / 'comparison.json', compared)
    write_json(output / 'provenance.json', dict(experiment='EX-084', source=str(source),
        source_files={name:file_hash(source / name) for name in ('manifest.json','events.jsonl','result.json','checksums.sha256')},
        renderer_sha256=file_hash(Path(__file__)), template_sha256=file_hash(Path(__file__).with_name('viewer.html')),
        decisions=sum(map(len,groups.values())), actual_http_bytes_preserved=True,
        probability_scope='stage_specific; detail conditional on selected type; no invented full distribution'))
    seal(output)
    return verify_data(source, output)


def verify_data(source, output):
    """Full data comparison is separate from the representative browser check."""
    source, output = Path(source), Path(output)
    groups = decision_groups(list(event_rows(source)))
    result = json.loads((source / 'result.json').read_text()); decisions=0
    for outcome in result['outcomes']:
        target=output/f'battle-{outcome["slot"]}'
        data=json.loads((target/'decisions.json').read_text())
        embedded=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',
                                     (target/'index.html').read_text(),re.S).group(1))
        expected=dict(experiment='EX-084',slot=outcome['slot'],outcome=outcome,decisions=groups.get(outcome['username'],[]))
        if data != expected or embedded != expected:
            raise ValueError('exported observation/stage originals differ')
        decisions+=len(data['decisions'])
    if decisions != result['decisions']:
        raise ValueError('exported decision denominator differs')
    verify_seal(output)
    return dict(passed=True, games=len(result['outcomes']), decisions=decisions, all_stage_data_compared=True)


def verify_browser(output):
    from playwright.sync_api import sync_playwright
    output=Path(output);verify_seal(output)
    samples={}; errors=[]
    with tempfile.TemporaryDirectory(prefix='ex084-offline-') as temp:
        moved=Path(temp)/'moved';shutil.copytree(output,moved)
        for path in sorted(moved.glob('battle-*/decisions.json')):
            data=json.loads(path.read_text())
            for i,d in enumerate(data['decisions']):
                all_events=sum(d['stages'].values(),[])
                if sum(e['type']=='stage_response' for e in all_events)==2:
                    samples.setdefault('two_stage',(path.parent,i))
                if any(e['type']=='stage_selection' and e['automatic'] for e in all_events):
                    samples.setdefault('automatic',(path.parent,i))
                if any(e['type']=='stage_failure' for e in d['stages']['action_detail']):
                    samples.setdefault('detail_failure',(path.parent,i))
            if len(samples)==3:break
        synthetic=False
        if 'detail_failure' not in samples and samples:
            source, i = samples.get('two_stage', next(iter(samples.values())))
            data=copy.deepcopy(json.loads((source/'decisions.json').read_text()))
            data['synthetic']=True;data['decisions']=[data['decisions'][i]]
            d=data['decisions'][0];d['selection']=d['wire']=None
            d['stages']['action_detail']=[e for e in d['stages']['action_detail'] if e['type'] not in
                                        ('stage_response','stage_selection','judgment_diagnostics','http_response')]
            d['stages']['action_detail'].append(dict(type='stage_failure',decision=d['id'],stage='action_detail',
                error=dict(type='UnusableChoice',detail='표시 검증용 선택 분기 밖 응답')))
            target=moved/'synthetic-detail-failure';target.mkdir()
            (target/'index.html').write_text(render_data(data));write_json(target/'decisions.json',data)
            samples['detail_failure']=(target,0);synthetic=True
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-gpu'])
            context=browser.new_context(offline=True);page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto((moved/'index.html').as_uri(),wait_until='domcontentloaded')
            for name,(folder,i) in samples.items():
                data=json.loads((folder/'decisions.json').read_text());d=data['decisions'][i]
                page.goto((folder/'index.html').as_uri(),wait_until='domcontentloaded')
                page.select_option('#decision',str(i))
                for stage in ('action_type','action_detail'):
                    page.locator(f'[data-stage="{stage}"]').click()
                    records=d['stages'][stage]
                    request=next((e['body'] for e in records if e['type']=='http_request'),None)
                    response=next((e['body'] for e in records if e['type']=='stage_response'),None)
                    if json.loads(page.locator('#request-json').inner_text()) != request or \
                            json.loads(page.locator('#response-json').inner_text()) != response:
                        raise ValueError('offline visible stage JSON differs')
                if name=='detail_failure' and '전송하지 않았습니다' not in page.locator('#final').inner_text():
                    raise ValueError('failed detail incorrectly displayed as transmitted')
                if name=='detail_failure' and '실패' not in page.locator('#status').inner_text():
                    raise ValueError('detail failure missing from screen')
            context.close();browser.close()
        if errors:raise ValueError('browser errors: '+repr(errors))
    return dict(passed=True, offline_relocated=True, representative_screens=list(samples),
                synthetic_failure_fixture=synthetic, browser_errors=errors, full_browser_replay=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['verify-browser'])
    parser.add_argument('--output',type=Path,default=EXPORT)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();write_json(args.receipt,verify_browser(args.output))
