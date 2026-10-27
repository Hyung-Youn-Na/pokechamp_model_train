"""Read-only EX-112 re-export; preserve the original sealed viewer and collection."""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import hashlib
import html
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
ASSETS = ROOT / 'integration/pokechamp/viewer_assets'
UI_VERSION = 'battle-viewer-ui-v1'
RENDERER = 'openai-matchup-researcher-v2'
EXTENSIONS = ['요약 제거 원본', '후보별 상성 요약', '선택·전송']


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def script_json(value):
    return json_text(value).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')


def style():
    return (ASSETS / 'jev-researcher.html').read_text().split('<style>', 1)[1].split('</style>', 1)[0]


def render(data):
    script = (ASSETS / 'action-labels.js').read_text() + '\n' + (HERE / 'viewer_v1.js').read_text()
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (f"default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; "
           "frame-src 'self' file:; object-src 'none'; base-uri 'none'; connect-src 'none'")
    replacements = {'__TITLE__': html.escape(f"{data['experiment']} · {data['slot']}경기"),
                    '__CSP__': html.escape(csp, quote=True), '__STYLE__': style(),
                    '__DATA__': script_json(data), '__SCRIPT__': script}
    page = (HERE / 'viewer_v1.html').read_text()
    # Replace source placeholders once, before untrusted data can resemble a placeholder.
    import re
    return re.sub('|'.join(re.escape(k) for k in replacements), lambda m: replacements[m[0]], page)


def render_replay(battle, protocol):
    from integration.pokechamp.observability.render import _replay_html
    page = _replay_html(dict(battle_id=battle, teams=[]), protocol)
    bridge = (ROOT / 'integration/jev_planner/replay.js').read_text()
    script_hash = base64.b64encode(hashlib.sha256(bridge.encode()).digest()).decode()
    page = page.replace('script-src https://play.pokemonshowdown.com;',
                        f"script-src 'sha256-{script_hash}' https://play.pokemonshowdown.com;")
    start = page.index('<script type="text/plain" class="battle-log-data">')
    end = page.index('</script>', start) + len('</script>')
    page = page[:start] + '<script type="application/json" id="replay-protocol">' + script_json(protocol) + '</script>' + page[end:]
    # The existing renderer escapes CSP quotes in its HTML attribute.
    page = page.replace('base-uri &#x27;none&#x27;', 'base-uri https://play.pokemonshowdown.com;')
    page = page.replace('<title>', '<base href="https://play.pokemonshowdown.com/fx/"><title>')
    page = page.replace('<script defer src=', '<script>' + bridge + '</script>\n<script defer src=')
    return page.replace('Static protocol fallback', '오프라인 공개 로그')


def audit_saved_data(previous, source):
    """Compare every retained decision and public row to its original collection."""
    from integration.jev_eval.turn_logs import public_rows, raw_text
    events = [json.loads(line) for line in (source / 'events.jsonl').read_text().splitlines()]
    grouped = {}
    for event in events:
        if event.get('decision'):
            grouped.setdefault(event['decision'], []).append(event)
    result = json.loads((source / 'result.json').read_text())
    count = rows_count = 0
    seen = set()
    history_types = {'transport', 'http_request', 'http_response', 'local_transport',
                     'attempt_failure', 'provider_retry', 'request_cancelled'}
    for outcome in result['outcomes']:
        folder = previous / f"battle-{outcome['slot']}"
        data = json.loads((folder / 'decisions.json').read_text())
        assert data['experiment'] == 'EX-112' and data['outcome'] == outcome
        for d in data['decisions']:
            assert d['id'] not in seen
            seen.add(d['id'])
            records = grouped[d['id']]
            by_type = {e['type']: e for e in records}
            inp = by_type['input']
            assert d['id'].split('-')[0] == outcome['username']
            assert d['observation'] == inp['payload']
            assert d['turn'] == inp['payload']['state']['turn']
            assert d['kind'] == inp['payload']['state']['decision_kind']
            assert d['request'] == by_type.get('http_request', {}).get('body')
            assert d['response'] == by_type.get('response', {}).get('body')
            raw = by_type.get('http_response', {}).get('raw_body')
            try:
                parsed = json.loads(raw) if raw is not None else None
            except ValueError:
                parsed = raw
            assert d['raw_response'] == parsed
            assert d['selection'] == by_type.get('selection') and d['wire'] == by_type.get('wire')
            assert d['automatic'] == bool(by_type.get('selection', {}).get('automatic'))
            assert not d['automatic'] or (d['request'] is None and d['raw_response'] is None)
            tech = d['technical']
            assert tech['input_boundary'] == inp['boundary']
            assert tech['input_audit'] == inp['input_audit']
            assert tech['observation_identity'] == inp['observation_identity']
            assert tech['http_response'] == by_type.get('http_response')
            assert tech['http_attempt_history'] == [e for e in records if e['type'] in history_types]
            base = deepcopy(inp['payload'])
            for candidate in base['questions']['action']['criteria'].values():
                candidate.pop('current_matchup', None)
            assert d['base_observation'] == base
            cutoff = data['turn_log']['decision_cutoffs'][d['id']]
            assert cutoff == dict(sequence=inp['boundary']['protocol_event_seq'], line_index=inp['boundary']['line_index'])
            count += 1
        rows, _, _, _ = public_rows(events, outcome['username'])
        saved_rows = [row for turn in data['turn_log']['turns'] for row in turn['rows']]
        assert len(rows) == len(saved_rows)
        assert all(all(saved[k] == v for k, v in row.items()) for row, saved in zip(rows, saved_rows))
        assert raw_text(rows) == (folder / 'showdown.log').read_text()
        rows_count += len(rows)
    assert seen == {e['decision'] for e in events if e['type'] == 'input'}
    return dict(games=len(result['outcomes']), decisions=count, public_rows=rows_count,
                completed=result['completed'], failed=result['failed'], completed_pairs=result['completed_pairs'])


def reexport(previous, output):
    from integration.jev27b.study import verify_seal, seal
    previous, output = Path(previous).resolve(), Path(output).resolve()
    previous_link = Path(os.path.relpath(previous, output)).as_posix()
    if output.exists():
        raise FileExistsError(output)
    old_provenance = json.loads((previous / 'provenance.json').read_text())
    if old_provenance['experiment'] != 'EX-112':
        raise ValueError('This renderer is registered for EX-112 only')
    source = Path(old_provenance['source']).resolve()
    if output.is_relative_to(previous) or output.is_relative_to(source):
        raise ValueError('Output must be separate from preserved evidence')
    previous_files = verify_seal(previous)
    source_files = verify_seal(source)
    assert digest(source / 'checksums.sha256') == old_provenance['source_seal_sha256']
    for name, expected in old_provenance['source_files'].items():
        assert digest(source / name) == expected == digest(previous / 'raw' / name)
    audited = audit_saved_data(previous, source)
    shutil.copytree(previous, output)
    (output / 'checksums.sha256').unlink()
    (output / 'previous-provenance.json').write_text(json_text(old_provenance) + '\n')
    result = json.loads((source / 'result.json').read_text())
    rows = []
    for outcome in result['outcomes']:
        folder = output / f"battle-{outcome['slot']}"
        data = json.loads((folder / 'decisions.json').read_text())
        (folder / 'index.html').write_text(render(data))
        (folder / 'replay.html').write_text(render_replay(f"ex112-{outcome['slot']}", (folder / 'showdown.log').read_text()))
        rows.append(f'<tr><td><a href="battle-{outcome["slot"]}/index.html">경기 {outcome["slot"]}</a></td>'
                    f'<td>{html.escape(outcome["slot_id"])}</td><td>{html.escape(outcome["jev_actor"])}</td>'
                    f'<td>{html.escape(outcome.get("outcome") or "미완료")}</td>'
                    f'<td>{outcome.get("turns") if outcome.get("turns") is not None else "미완료"}</td><td>{len(data["decisions"])}</td></tr>')
    score = result['overall']
    page = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    page += '<title>EX-112 · OpenAI Decisions · UI v1</title><style>' + style() + 'main{max-width:1200px;margin:auto;padding:20px}.panel{padding:18px}</style>'
    page += '<main><a href="../index.html">← 실험 목록</a><h1>EX-112 · 후보별 상성 요약</h1><p>gpt-6-luna 대 Abyssal · Gen9 OU</p>'
    page += f'<p class="notice">유효 {result["completed"]}/{result["planned"]} · {score["wins"]}승 {score["draws"]}무 {score["losses"]}패 · 완료 {result["completed_pairs"]}/16쌍 · 실험 Stopped / 계획 Blocked</p>'
    page += f'<p>실패 {result["failed"]} · 무효 {result["invalid"]} · 미실행 {result["unattempted"]} · {audited["decisions"]}개 결정. 실패 경기를 패배로 세지 않습니다.</p>'
    page += '<p class="muted">고정 대진의 탐색 결과입니다. UI 재구성으로 실험 조건·성적·분모·미완료 판정을 변경하지 않았습니다.</p>'
    page += '<div class="panel table-wrap"><table><thead><tr><th>경기</th><th>대진</th><th>관점</th><th>결과</th><th>턴</th><th>결정</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
    page += '<p><a href="raw/result.json">전체 결과</a> · <a href="provenance.json">판본·출처</a> · ' + f'<a href="{html.escape(previous_link, quote=True)}/index.html">이전 봉인 판본</a>' + ' · <a href="README.md">열람 안내</a></p>'
    page += f'<p class="muted">{UI_VERSION} · {RENDERER} · 확장: {" / ".join(EXTENSIONS)}</p></main></html>'
    (output / 'index.html').write_text(page)
    (output / 'README.md').write_text('# EX-112 UI v1\n\n폴더 전체를 이동한 뒤 index.html을 여세요.\n'
        '기본5탭 뒤 요약 제거 원본·후보별 상성 요약·선택/전송 확장을 제공합니다.\n'
        '응답 탭은 choice와 확률 후보의 실제 기술·포켓몬 이름을 함께 표시합니다. 원문·복사·다운로드 값은 유지합니다.\n'
        '결정/턴 선택은 영상을 일시정지하고 턴 시작으로 이동합니다. 영상/탭 조작은 결정 선택을 바꾸지 않습니다.\n'
        '입력·응답·상태·공개 로그는 오프라인에서도 열립니다. 애니메이션은 공식 Showdown 외부 자산이 필요합니다.\n'
        '상위 실험 목록과 이전 판본 링크는 해당 폴더가 함께 있을 때 열립니다.\n'
        'EX-112의 Stopped/EP-183의 Blocked 및 유효31/32·실패1·15/16쌍은 유지됩니다.\n')
    renderer_paths = [Path(__file__), HERE/'viewer_v1.html', HERE/'viewer_v1.js',
        ASSETS/'jev-researcher.html', ASSETS/'action-labels.js', ROOT/'integration/jev_planner/replay.js',
        ROOT/'integration/pokechamp/observability/render.py', ROOT/'integration/pokechamp/observability/recorder.py',
        ROOT/'integration/pokechamp/observability/issues.py']
    renderer_files = {}
    for path in renderer_paths:
        relative = path.relative_to(ROOT)
        target = output / 'renderer-source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        renderer_files[str(relative)] = digest(target)
    # All copied evidence and data must retain the previous sealed bytes.
    preserved = {name: checksum for name, checksum in previous_files.items()
                 if name.startswith('raw/') or name.endswith(('/decisions.json', '/showdown.log'))}
    assert all(digest(output/name) == checksum for name, checksum in preserved.items())
    provenance = dict(experiment='EX-112', ui_version=UI_VERSION, renderer=RENDERER,
        extensions=EXTENSIONS, source=str(source), source_seal_sha256=digest(source/'checksums.sha256'),
        source_files=old_provenance['source_files'], previous_viewer=previous_link,
        previous_seal_sha256=digest(previous/'checksums.sha256'), renderer_files=renderer_files,
        renderer_source_copy='renderer-source', unchanged_files=preserved, validation=audited,
        source_verified_files=len(source_files), previous_verified_files=len(previous_files),
        decision='D-172', plan='EP-189', changelog='project_context/shared/viewers/CHANGELOG.md#ex112-response-names',
        offline_input_response=True, animation='official external Showdown assets required')
    (output/'provenance.json').write_text(json_text(provenance)+'\n')
    seal(output)
    return dict(passed=True, output=str(output), **audited)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json_text(reexport(args.previous, args.output)))
