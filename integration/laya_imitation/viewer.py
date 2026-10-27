"""EX-119 offline viewer (battle-viewer-ui-v1), renderer `laya-imitation-researcher-v1`.

Layout, navigation, replay bridge and styling are the EX-114 v1 generator's
(`jevk5_ruleqa_battle/viewer.html`, `viewer_ui.style/render_replay`); `viewer.js` is that file with
the EX-071 event format, an extra `압축 입력` tab and plain candidate labels.
"""
from __future__ import annotations
import base64
import hashlib
import html
import json
from pathlib import Path
import re
import shutil

from integration.jev_eval.turn_logs import build_turn_log, raw_text
from integration.jevk5_ruleqa_battle.viewer_ui import render_replay, script_json, style
from integration.pokechamp.imitation.schema import ImitationInput

from . import config as c
from .compact import render as render_compact
from .storage import atomic, jsonl, read, seal, sha

HERE = Path(__file__).parent
UI_VERSION = 'battle-viewer-ui-v1'
RENDERER = 'laya-imitation-researcher-v1'
EXTENSIONS = ['압축 입력', '선택지 확률', '선택·전송']
SOURCES = ('integration/laya_imitation/viewer.py', 'integration/laya_imitation/viewer.html',
           'integration/laya_imitation/viewer.js', 'integration/jevk5_ruleqa_battle/viewer_ui.py',
           'integration/jev_planner/replay.js', 'integration/pokechamp/viewer_assets/jev-researcher.html',
           'integration/jev_eval/turn_logs.py')


def render_page(data):
    script = (HERE / 'viewer.js').read_text()
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (f"default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; "
           "frame-src 'self' file:; object-src 'none'; base-uri 'none'; connect-src 'none'")
    replacements = {'__TITLE__': html.escape(f"{data['experiment']} · {data['slot']}경기"),
                    '__CSP__': html.escape(csp, quote=True), '__STYLE__': style(),
                    '__DATA__': script_json(data), '__SCRIPT__': script}
    page = (HERE / 'viewer.html').read_text()
    return re.sub('|'.join(re.escape(k) for k in replacements), lambda m: replacements[m[0]], page)


def decisions_for(events, renderer=render_compact):
    grouped = {}
    for e in events:
        if e.get('decision'):
            grouped.setdefault(e['decision'], {}).setdefault(e['type'], e)
    out = []
    for decision_id, typed in grouped.items():
        entry = typed['input']
        value = ImitationInput(entry['body_json'])
        state, question = renderer(value)
        raw = typed.get('http_response')
        try:
            raw_response = json.loads(raw['raw_body']) if raw else None
        except ValueError:
            raw_response = raw['raw_body']
        out.append(dict(
            id=decision_id, turn=entry['official']['turn'], kind=entry['snapshot']['decision_kind'],
            automatic=len(value.action_ids) == 1, boundary=entry['boundary'],
            request=typed['http_request']['body'] if 'http_request' in typed else None,
            raw_response=raw_response, response=typed['response']['body'] if 'response' in typed else None,
            observation=value.body, snapshot=entry['snapshot'], compact=dict(state=state, question=question),
            selection=typed.get('selection'), wire=typed.get('wire'),
            diagnostics=[typed['decision_rejected']] if 'decision_rejected' in typed else [],
            technical=dict(input_boundary=entry['boundary'], input_sha256=entry['input_sha256'],
                           commands=entry['commands'], slot_map=entry['slot_map'], actions=entry['actions'],
                           official_request=entry['official']['request'], revalidation=typed.get('revalidation'),
                           observation_identity=entry['observation_identity'], input_seconds=entry['input_seconds'])))
    return out


EX119 = dict(experiment='EX-119', plan='EP-208', slug='ex119', pairs=16, title='EX-119 · laya 압축 입력',
             heading='EX-119 · laya 압축 입력 모방 모델 대 Abyssal',
             intro='EX-118 선택 체크포인트, EX-071 입력 경계 → laya-compact-v1 압축 → 로컬 laya 서빙(GPU0). '
                   'EX-089 표준 32경기 일정. 확률은 행동 선택 확률이며 승률이 아닙니다. 고정 대진 탐색 결과입니다.',
             changelog='project_context/shared/viewers/CHANGELOG.md#ex119-laya-v1')


def export(run, output, meta=EX119, columns=None, renderer_for=None):
    """`meta` names the experiment; `columns(row)` optionally adds (header, cell) pairs before 결과;
    `renderer_for(row)` picks the compressed-input renderer of that slot's model (v1 by default)."""
    run, output = Path(run), Path(output)
    extra = (lambda row: []) if columns is None else columns
    manifest, result = read(run / 'manifest.json'), read(run / 'result.json')
    output.mkdir(parents=True, exist_ok=False)
    rows, total = [], 0
    by_slot = {o['slot_id']: o for o in result['outcomes']}
    for number, row in enumerate(manifest['schedule'], 1):
        outcome = by_slot.get(row['slot_id'])
        if outcome is None:
            rows.append('<tr><td>%d</td><td>%s</td><td>%s</td>%s<td>미실행</td><td>—</td><td>—</td></tr>'
                        % (number, html.escape(row['slot_id']), row['model_side'],
                           ''.join('<td>%s</td>' % html.escape(str(v)) for _, v in extra(row))))
            continue
        game = run / 'games' / row['slot_id']
        request = read(game / 'request.json')
        events = list(jsonl(game / 'events.jsonl'))
        decisions = decisions_for(events, renderer_for(row) if renderer_for else render_compact)
        username = request['names'][row['model_side']]
        log = build_turn_log(events, username, row['model_side'], decisions)
        target = output / ('battle-%02d' % number)
        (target / 'raw').mkdir(parents=True)
        for name in ('events.jsonl', 'opponent-events.jsonl', 'outcome.json', 'audit.json', 'request.json'):
            if (game / name).exists():
                shutil.copyfile(game / name, target / 'raw' / name)
        data = dict(experiment=meta['experiment'], slot=number, outcome=outcome, decisions=decisions, turn_log=log,
                    synthetic=False)
        atomic(target / 'decisions.json', data)
        text = raw_text([r for turn in log['turns'] for r in turn['rows']])
        (target / 'showdown.log').write_text(text)
        (target / 'replay.html').write_text(render_replay('%s-%d' % (meta['slug'], number), text))
        (target / 'index.html').write_text(render_page(data))
        total += len(decisions)
        label = dict(win='승리', loss='패배', draw='무승부').get(outcome.get('result'), outcome['status'])
        rows.append('<tr><td>%d</td><td>%s</td><td>%s</td>%s<td>%s</td><td>%s</td>'
                    '<td><a href="battle-%02d/index.html">입력·응답·리플레이</a></td></tr>'
                    % (number, html.escape(row['slot_id']), row['model_side'],
                       ''.join('<td>%s</td>' % html.escape(str(v)) for _, v in extra(row)), html.escape(label),
                       outcome.get('turns', '—'), number))
    s = result
    summary = ('정상 %d/%d · %d승 %d무 %d패 · 완료쌍 %d/%d' % (s['status']['completed'], s['scheduled'], s['wins'],
                                                         s['draws'], s['losses'], s['completed_pairs'], meta['pairs']))
    headers = ''.join('<th>%s</th>' % html.escape(h) for h, _ in extra(manifest['schedule'][0]))
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            'initial-scale=1"><title>' + html.escape(meta['title']) + '</title><style>body{font:16px/1.7 system-ui;max-width:1100px;'
            'margin:32px auto;padding:16px}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:'
            '1px solid #ddd;text-align:left}a{color:#165fa5}</style><p><a href="../index.html">← 실험 목록</a></p>'
            '<h1>' + html.escape(meta['heading']) + '</h1><p>' + summary + '</p>'
            '<p>' + html.escape(meta['intro']) + '</p>'
            '<p>실패 %d · 미완료 %d · 무효 %d · 미실행 %d</p>' % (s['status']['failed'], s['status']['incomplete'],
                                                          s['status']['invalid'], s['status']['unattempted'])
            + '<table><tr><th>경기</th><th>슬롯</th><th>진영</th>' + headers + '<th>결과</th><th>턴</th><th>열기</th></tr>'
            + ''.join(rows) + '</table><p><a href="raw/result.json">상세 결과</a> · <a href="raw/manifest.json">'
            'manifest</a> · <a href="provenance.json">출처</a></p></html>')
    (output / 'index.html').write_text(page)
    (output / 'raw').mkdir()
    originals = {}
    for name in ('manifest.json', 'result.json', 'ledger.jsonl'):
        shutil.copyfile(run / name, output / 'raw' / name)
        originals[name] = sha(run / name)
    sources = {rel: sha(c.ROOT / rel) for rel in SOURCES}
    for rel in SOURCES:
        target = output / 'renderer-source' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / rel, target)
    provenance = dict(experiment=meta['experiment'], plan=meta['plan'], run=str(run), source_files=originals, decisions=total,
                      games=len(result['outcomes']), ui_version=UI_VERSION, renderer=RENDERER, extensions=EXTENSIONS,
                      renderer_source=sources, offline_input_response=True, animation_requires_network=True,
                      changelog=meta['changelog'])
    atomic(output / 'provenance.json', provenance)
    seal(output)
    return dict(output=str(output), decisions=total, games=len(result['outcomes']))
