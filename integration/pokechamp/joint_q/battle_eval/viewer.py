"""Portable original-input, all-q and replay viewer for complete/partial EX081."""
from __future__ import annotations

import html
import json
from pathlib import Path
import shutil

from ..storage import atomic, read, rows, sha
from ...observability.render import _replay_html
from ...qwen_viewer import seal
from .audit import PROFILE, expected_request, _json
from ..serializer import JointInput
from .outputs import LIMITATION, _inside, verify_seal, verify_final, _verify_baseline_sources


def _data_json(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False)
            .replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e'))


def _bundle(live, result, hashes):
    manifest = read(live / 'manifest.json')
    if manifest.get('profile') != PROFILE:
        raise ValueError('not a joint q live bundle')
    events = rows(live / 'events.jsonl')
    if len(result.get('outcomes', [])) != 1:
        raise ValueError('per-game bundle needs exactly one outcome')
    outcome = result['outcomes'][0]
    grouped = {}
    for event in events:
        if event['type'] == 'http_request':
            request = event['body']
            if request != expected_request(JointInput(request['payload_json'])):
                raise ValueError('request differs from declared joint q profile')
        if event.get('decision'):
            grouped.setdefault(event['decision'], []).append(event)
    decisions = []
    for key, records in grouped.items():
        first = lambda kind: next((e for e in records if e['type'] == kind), None)
        entry = first('input')
        if entry is None:
            continue
        state = entry['payload']['state']
        request, response, http = first('http_request'), first('response'), first('http_response')
        body = response['body'] if response else None
        raw = http.get('raw_body') if http else None
        if body is None and raw:
            try:
                body = _json(raw)
            except (TypeError, ValueError):
                pass
        decisions.append(dict(id=key, turn=state['turn'], kind=state['decision_kind'],
            actions=entry['actions'], commands=entry['commands'],
            payload_json=entry['payload_json'], input_sha256=entry['input_sha256'],
            request=request['body'] if request else None,
            raw_request=request.get('raw_body') if request else None,
            response=body, raw_response=raw,
            selection=first('selection'), wire=first('wire'), revalidation=first('revalidation'),
            technical=dict(boundary=entry['boundary'], observation_identity=entry['observation_identity'],
                input_audit=entry['input_audit'], input_generation_seconds=entry.get('input_generation_seconds'),
                snapshot_seconds=entry.get('snapshot_seconds'),
                elapsed_seconds=response.get('elapsed_seconds') if response else None), records=records))
    user = outcome.get('username')
    protocol = '\n'.join(line for event in events
                         if event['type'] == 'protocol' and event.get('username') == user
                         for line in event['protocol'].splitlines()
                         if line.startswith('|') and not line.startswith(('|request|', '|sentchoice|')))
    if protocol:
        protocol += '\n'
    return dict(experiment='EX-081', profile=PROFILE,
                outcome={**outcome, 'slot': manifest.get('global_slot', outcome['slot'])}, decisions=decisions,
                source=dict(directory=str(live), manifest_sha256=hashes['manifest.json'],
                            events_sha256=hashes['events.jsonl'], result_sha256=hashes['result.json'])), protocol


def export(source, output, *, metrics=None, final_directory=None):
    """Export immutable per-game sources; the outer source may be sealed later.

    A stopped-before-battle landing page reports zero games and contains no
    fabricated decision, model response or replay.
    """
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    configuration = read(source / 'configuration.json')
    if configuration.get('experiment_id') != 'EX-081' or configuration.get('profile') != PROFILE:
        raise ValueError('not an EX081 source')
    final = _inside(source, final_directory) if final_directory is not None else source / 'final'
    corrective = final != source / 'final'
    final, receipts, saved_metrics = verify_final(source, final, verify_sources=corrective)
    if metrics is not None and metrics != saved_metrics:
        raise ValueError('supplied metrics differ from the selected final receipt')
    metrics = saved_metrics
    if metrics.get('configuration_sha256') != sha(source / 'configuration.json'):
        raise ValueError('metrics configuration identity differs from source')
    if corrective:
        if receipts.get('correction_profile') != 'baseline-lineage-v2' or receipts.get('passed') is not True:
            raise ValueError('unsupported or incomplete corrective final receipt')
        _verify_baseline_sources(configuration, metrics['baseline_provenance'])
    verified, bundles = {}, []
    for game in metrics['games']:
        if not game.get('live'):
            continue
        live = _inside(source, game['live'])
        hashes = verify_seal(live, required=('manifest.json', 'events.jsonl', 'result.json'))
        data, protocol = _bundle(live, read(live / 'result.json'), hashes)
        data['eligibility'] = dict(valid=game['valid'], audit_passed=game['audit_passed'], error=game.get('error'))
        if data['outcome']['slot'] != game['slot']:
            raise ValueError('viewer global slot mismatch')
        bundles.append((game, data, protocol))
        verified[game['game_id']] = dict(directory=str(live), source_files=hashes,
                                        source_seal_sha256=sha(live / 'checksums.sha256'))
    template = Path(__file__).with_name('viewer.html')
    output.mkdir(parents=True, exist_ok=False)
    matches, links = [], []
    for game, data, protocol in bundles:
        folder = output / f"battle-{game['slot']}"
        folder.mkdir()
        (folder / 'showdown.log').write_text(protocol)
        (folder / 'replay.html').write_text(_replay_html(
            dict(battle_id=f"ex081-{game['slot']}", showdown_battle_tag=data['outcome'].get('battle_tag'), teams=[]), protocol))
        (folder / 'index.html').write_text(template.read_text().replace('__EXPERIMENT__', 'EX-081')
                                           .replace('__DATA__', _data_json(data)))
        atomic(folder / 'decisions.json', data, immutable=True)
        match = dict(slot=game['slot'], game_id=game['game_id'], completed=game['completed'], valid=game['valid'],
                     decisions=len(data['decisions']), candidates=sum(len(d['actions']) for d in data['decisions']),
                     decisions_sha256=sha(folder / 'decisions.json'), protocol_sha256=sha(folder / 'showdown.log'))
        matches.append(match)
        label = {'player_won': '승리', 'player_lost': '패배', 'tied': '무승부'}.get(game['outcome'], '미완료')
        qualification = '유효' if game['valid'] else '미완료/무효'
        links.append(f'<li><a href="battle-{game["slot"]}/index.html">{game["slot"]}경기 · '
                     f'{html.escape(game["game_id"])} · {label} · {qualification} · 결정 {match["decisions"]}개</a></li>')
    counts = metrics['denominators']
    no_games = '<p id="no-games">배틀 미실행. 보존된 실제 결정·응답·리플레이가 없습니다.</p>' if not bundles else ''
    correction = ('<p id="correction">역사 기준선 경로 해석을 정정한 별도 분석입니다. '
                  '모델·배틀·원승패·전수 감사는 동일합니다. '
                  '<a href="original-report.md">최초 보고</a>와 '
                  '<a href="original-metrics.json">최초 지표</a>를 보존합니다.</p>' if corrective else '')
    comparison = metrics['comparison']
    (output / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>EX-081 · 공동 q 배틀 평가</title>'
        '<style>body{font:17px system-ui;max-width:1000px;margin:40px auto;padding:0 16px;line-height:1.8}</style>'
        '<h1>EX-081 · EX066 epoch3 공동 q 배틀 평가</h1>'
        f'<p id="denominators">예정 {counts["planned"]} · 시도 {counts["attempted"]} · 정상 완료 {counts["completed"]} · '
        f'유효 {counts["valid"]} · 실패 {counts["failed"]} · 무효 {counts["invalid"]} · 미실행 {counts["unrun"]}</p>'
        f'<p>유효 p2 결과: {counts["wins"]}승·{counts["draws"]}무·{counts["losses"]}패</p>'
        f'<p id="comparison">역사 기준선 공통 유효 대진 {comparison["common_valid"]}개 · '
        f'대응 보정 점수 차이 {comparison["difference"] if comparison["difference"] is not None else "미평가"}</p>'
        f'<p>{html.escape(LIMITATION)}</p>'
        '<p>모든 후보 q·실제 요청·응답·선택·전송·공개 로그는 오프라인에서 열립니다. '
        '배틀 애니메이션만 외부 Showdown 자산을 사용합니다. 폴더 전체를 이동해 열 수 있습니다.</p>'
        + correction + no_games + '<ul>' + ''.join(links) + '</ul>'
        '<p><a href="report.md">한국어 보고</a> · <a href="metrics.json">지표 JSON</a> · '
        '<a href="audit.json">독립 감사</a> · <a href="configuration.json">동결 설정</a> · '
        '<a href="provenance.json">출처·해시</a></p></html>')
    copies = {'configuration.json': source / 'configuration.json',
              'metrics.json': final / 'metrics.json', 'report.md': final / 'report.md',
              'audit.json': final / 'audit.json', 'final-receipt.json': final / 'receipt.json'}
    if corrective:
        copies.update({name: final / name for name in ('original-metrics.json', 'original-report.md', 'original-receipt.json')})
    for name, original in copies.items():
        shutil.copyfile(original, output / name)
    atomic(output / 'provenance.json', dict(experiment_id='EX-081', source=str(source),
        configuration_sha256=sha(source / 'configuration.json'), final_receipt_sha256=sha(final / 'receipt.json'),
        final_directory=str(final), analysis_profile=receipts.get('correction_profile', 'original'),
        normal_completed=counts['completed'], valid_completed=counts['valid'], planned=counts['planned'],
        matches=matches, source_bundles=verified, builder_sha256=sha(Path(__file__)),
        template_sha256=sha(template), original_source_unchanged=True,
        copied_files={name: dict(source=str(original), source_sha256=sha(original), copy_sha256=sha(output / name))
                      for name, original in copies.items()}),
        immutable=True)
    (output / 'README.md').write_text('# EX-081 공동 q 뷰어\n\n'
        '폴더 전체를 이동한 뒤 index.html을 여세요. 실제 입력·원응답·모든 후보 q·선택·전송·'
        '공개 protocol은 오프라인에서 열립니다. 배틀 애니메이션만 인터넷 연결이 필요합니다.\n\n'
        'payload_json은 실제 요청의 JSON 문자열입니다. 원값을 그대로 보존하고 별도로 파싱한 열람본을 제공합니다. '
        '실패 응답·미수신·미전송을 완료된 선택으로 표시하지 않습니다.\n\n'
        f'원본: {source}\n원본을 수정하거나 내보내기 사본으로 대체하지 않았습니다.\n')
    seal(output)
    return dict(experiment_id='EX-081', matches=matches, export=str(output),
                export_sha256=sha(output / 'checksums.sha256'), source_changed=False,
                final_directory=str(final), final_receipt_sha256=sha(final / 'receipt.json'),
                completed=counts['completed'], valid_completed=counts['valid'])


def check_export(path):
    """Full moved-folder offline browser check, callable from an existing tool env."""
    import tempfile
    from playwright.sync_api import sync_playwright

    path = Path(path).resolve()
    verify_seal(path, required=('index.html', 'provenance.json', 'metrics.json', 'configuration.json'))
    provenance = read(path / 'provenance.json')
    if (path / 'final-receipt.json').exists():
        assert provenance['final_receipt_sha256'] == sha(path / 'final-receipt.json')
        selected_receipt = read(path / 'final-receipt.json')
        for name in ('metrics.json', 'audit.json', 'report.md'):
            assert selected_receipt['output_files'][name] == sha(path / name)
    failures, observations, candidates, selections, wires = [], 0, 0, 0, 0
    with tempfile.TemporaryDirectory(prefix='ex081-viewer-offline-') as temporary, sync_playwright() as tool:
        moved = Path(temporary) / 'viewer'
        shutil.copytree(path, moved)
        browser = tool.chromium.launch()
        context = browser.new_context(viewport=dict(width=1500, height=1000), accept_downloads=True)
        context.set_offline(True)
        context.route('http://**/*', lambda route: route.abort())
        context.route('https://**/*', lambda route: route.abort())
        page = context.new_page()
        page.on('pageerror', lambda error: failures.append(str(error)))
        page.goto((moved / 'index.html').as_uri())
        metrics = read(moved / 'metrics.json')
        assert str(metrics['denominators']['planned']) in page.locator('#denominators').inner_text()
        folders = sorted(moved.glob('battle-*'))
        if not folders:
            assert page.locator('#no-games').count() == 1
            assert page.locator('a[href*="battle-"]').count() == 0
        for folder in folders:
            data = read(folder / 'decisions.json')
            page.goto((moved / 'index.html').as_uri())
            page.locator(f'a[href="{folder.name}/index.html"]').click()
            # A completed click/navigation does not mean the new page's inline
            # data and decision list have initialized. Keep the exact count
            # assertion, but wait for that declared DOM state before reading it.
            page.wait_for_function('(expected) => document.querySelectorAll("#decision option").length === expected',
                                   arg=len(data['decisions']), timeout=30000)
            assert page.locator('#decision option').count() == len(data['decisions'])
            for i, decision in enumerate(data['decisions']):
                page.locator('#decision').select_option(str(i))
                assert json.loads(page.locator('#request').inner_text()) == decision['request']
                assert json.loads(page.locator('#response').inner_text()) == decision['response']
                assert json.loads(page.locator('#state').text_content()) == json.loads(decision['payload_json'])
                assert page.locator('#raw-response').text_content() == (decision['raw_response'] or '미수신')
                visible = page.locator('#p-values tr').evaluate_all(
                    'rows=>rows.map(r=>({id:r.dataset.actionId,label:r.cells[0].firstChild.textContent,q:r.cells[2].textContent}))')
                assert [r['id'] for r in visible] == [a['action_id'] for a in decision['actions']]
                for row, action in zip(visible, decision['actions']):
                    expected_label = (('선봉 → ' if action['kind'] == 'team' else '교체 → ') + action['pokemon']
                                      if action['kind'] in ('team', 'switch') else
                                      action.get('name', '기술명 미확인') +
                                      (' · 테라스탈' if action['action_id'].endswith('_terastallize') else ''))
                    assert row['label'] == expected_label
                    response = decision['response']
                    q = response.get('q_values', {}).get(action['action_id']) if isinstance(response, dict) else None
                    assert float(row['q']) == q if type(q) in (int, float) else row['q'] == '미수신'
                if decision['selection']:
                    selections += 1
                    assert page.locator('#p-values .chosen').get_attribute('data-action-id') == decision['selection']['choice']
                else:
                    assert page.locator('#p-values .chosen').count() == 0
                if decision['wire']:
                    wires += 1
                    assert decision['wire']['command'] in page.locator('#sent-action').inner_text()
                observations += 1
                candidates += len(visible)
            if data['decisions']:
                page.locator('#decision').select_option('0')
                if len(data['decisions']) > 1:
                    page.locator('#next').click()
                    assert page.locator('#decision').input_value() == '1'
                    page.locator('h1').click()
                    page.keyboard.press('ArrowLeft')
                    assert page.locator('#decision').input_value() == '0'
                with page.expect_download() as download:
                    page.locator('[data-download=request]').click()
                assert read(download.value.path()) == data['decisions'][0]['request']
                page.locator('[data-copy=request]').click()
            assert page.frame_locator('iframe').locator('pre').text_content() == (folder / 'showdown.log').read_text()
        browser.close()
    assert not failures, failures
    return dict(passed=True, moved_folder=True, offline=True, matches=len(folders),
                observations=observations, candidates=candidates, selections=selections, wires=wires,
                browser_errors=failures, export_sha256=sha(path / 'checksums.sha256'))
