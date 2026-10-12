"""Export a sealed Kev battle into a portable, locally readable research viewer."""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .branch_rollouts.common import file_hash, rows, write
from .kev_audit import PROFILES, decision_user, expected_request
from .joint_q.serializer import JointInput
from .observability.render import _replay_html
from .qwen_viewer import seal


def verify_source(source):
    """Check required source evidence and every entry without following escapes."""
    source = Path(source).resolve()
    recorded = {}
    for line in (source / 'checksums.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = (source / name).resolve()
        if not path.is_relative_to(source) or name in recorded:
            raise ValueError('invalid or duplicate source seal path: ' + name)
        if file_hash(path) != digest:
            raise ValueError('source seal mismatch: ' + name)
        recorded[name] = digest
    required = {'manifest.json', 'events.jsonl', 'result.json'}
    if not required <= recorded.keys():
        raise ValueError('source seal omits required evidence')
    return recorded


def _data_json(value):
    # A literal </script> must not terminate the non-executable JSON element.
    return (json.dumps(value, ensure_ascii=False, allow_nan=False)
            .replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e'))


def export(source, output, *, result_path=None):
    source, output = Path(source), Path(output)
    source_files = verify_source(source)
    manifest = json.loads((source / 'manifest.json').read_text())
    result_path = Path(result_path) if result_path else source / 'result.json'
    result = json.loads(result_path.read_text())
    events = rows(source / 'events.jsonl')
    template = Path(__file__).with_name('viewer_assets') / 'kev-local.html'
    experiment = manifest['experiment_id']
    if manifest.get('profile') not in PROFILES:
        raise ValueError('not a Kev battle bundle')
    for event in events:
        if event['type'] == 'http_request':
            body = event['body']
            expected = expected_request(JointInput(body['state']), body['model'], profile=manifest['profile'])
            if (body != expected or list(body['questions']) != list(expected['questions']) or
                    event.get('profile', manifest['profile']) != manifest['profile']):
                raise ValueError('request differs from declared Kev profile')
    output.mkdir(parents=True, exist_ok=False)
    matches, links = [], []
    for outcome in result['outcomes']:
        slot, user = outcome['slot'], outcome.get('username')
        folder = output / f'battle-{slot}'
        folder.mkdir()
        grouped = {}
        for event in events:
            key = event.get('decision')
            if key and decision_user(key, result['outcomes']) == user:
                grouped.setdefault(key, []).append(event)
        decisions = []
        for key, records in grouped.items():
            typed = {}
            for event in records:
                typed.setdefault(event['type'], []).append(event)
            if 'input' not in typed:
                continue
            first = lambda kind: typed.get(kind, [None])[0]
            entry = first('input')
            state = entry['payload']['state']
            request, response = first('http_request'), first('response')
            decisions.append(dict(id=key, turn=state['turn'], kind=state['decision_kind'],
                actions=entry['actions'], commands=entry['commands'],
                input_sha256=entry['input_sha256'], payload_json=entry['payload_json'],
                request=request['body'] if request else None,
                response=response['body'] if response else None,
                selection=first('selection'), wire=first('wire'), revalidation=first('revalidation'),
                technical=dict(boundary=entry['boundary'], observation_identity=entry['observation_identity'],
                    input_audit=entry['input_audit'], input_generation_seconds=entry['input_generation_seconds'],
                    snapshot_seconds=entry.get('snapshot_seconds'),
                    elapsed_seconds=response.get('elapsed_seconds') if response else None),
                records=records))
        protocol = '\n'.join(line for event in events if event['type'] == 'protocol' and event['username'] == user
            for line in event['protocol'].splitlines()
            if line.startswith('|') and not line.startswith(('|request|', '|sentchoice|'))) + '\n'
        (folder / 'showdown.log').write_text(protocol)
        (folder / 'replay.html').write_text(_replay_html(
            dict(battle_id=f'{experiment.lower().replace("-", "")}-{slot}',
                 showdown_battle_tag=outcome.get('battle_tag'), teams=[]), protocol))
        data = dict(experiment=experiment, profile=manifest['profile'], outcome=outcome, decisions=decisions,
                    source=dict(directory=str(source), manifest_sha256=source_files['manifest.json'],
                                events_sha256=source_files['events.jsonl']))
        (folder / 'index.html').write_text(template.read_text().replace('__EXPERIMENT__', html.escape(experiment))
                                           .replace('__DATA__', _data_json(data)))
        write(folder / 'decisions.json', data)
        matches.append(dict(slot=slot, completed=outcome['completed'], decisions=len(decisions),
                            candidates=sum(len(d['actions']) for d in decisions),
                            decisions_sha256=file_hash(folder / 'decisions.json'),
                            protocol_sha256=file_hash(folder / 'showdown.log')))
        labels = dict(player_won='승리', player_lost='패배', tied='무승부')
        links.append(f'<li><a href="battle-{slot}/index.html">{slot}경기 · Kev '
            f'{html.escape(outcome["kev_actor"])} · {labels.get(outcome.get("outcome"), "미완료")} · '
            f'{outcome.get("turns", "—")}턴 · 결정 {len(decisions)}개</a></li>')
    completed = sum(o['completed'] for o in result['outcomes'])
    planned = result.get('planned', len(manifest['schedule']))
    interpretation = ('재학습 없는 후속 정책 질문 진단입니다. 학습 타깃은 Abyssal 후속 정책 기준으로 남으며 '
        '새 질문이 Kev 후속 승률의 정확한 예측을 보장하지 않습니다. 단일 재실행으로 승률 개선이나 '
        '전패 원인을 확정하지 않습니다.' if manifest['profile'] == 'kev-continuation-noul-v1' else
        '연결 검증 결과이며 승률이나 성능 향상 근거가 아닙니다.')
    corrected = result_path.resolve() != (source / 'result.json').resolve()
    correction = ('<p>별도 평가 결과를 함께 제공하며 <a href="original-result.json">원 결과</a>를 보존합니다.</p>'
                  if corrected else '')
    (output / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(experiment)} · Kev 배틀</title>'
        '<style>body{font:17px system-ui;max-width:1000px;margin:40px auto;padding:0 16px;line-height:1.8}</style>'
        f'<a href="../index.html">실험 목록</a><h1>{html.escape(experiment)} · Kev-4B 배틀 연결</h1>'
        f'<p>정상 완료 {completed}/{planned} · 결정 {sum(m["decisions"] for m in matches)}개</p>'
        f'<p>{interpretation} 후보별 p(true)는 독립적인 모델 추정값이며 '
        '후보 간 합계가 1일 필요가 없습니다. 설명 평가는 미평가(기본 제외)입니다.</p>'
        '<p>입력·응답·모든 후보 확률·선택·실제 전송·경기 로그는 오프라인에서 열립니다. '
        '리플레이 애니메이션에는 인터넷 연결이 필요합니다. 폴더 전체를 이동해 열 수 있습니다.</p>'
        + correction + '<ul>' + ''.join(links) + '</ul><p><a href="result.json">결과 JSON</a> · '
        '<a href="manifest.json">실행 manifest</a> · <a href="provenance.json">출처·해시</a></p></html>')
    shutil.copyfile(result_path, output / 'result.json')
    shutil.copyfile(source / 'manifest.json', output / 'manifest.json')
    if corrected:
        shutil.copyfile(source / 'result.json', output / 'original-result.json')
    write(output / 'provenance.json', dict(experiment=experiment, source=str(source),
        planned=planned, completed=completed, matches=matches,
        evaluation_result=dict(path=str(result_path), sha256=file_hash(result_path)),
        source_files=source_files, source_seal_sha256=file_hash(source / 'checksums.sha256'),
        builder_sha256=file_hash(Path(__file__)), template_sha256=file_hash(template)))
    (output / 'README.md').write_text(f'# {experiment} Kev 뷰어\n\n'
        '폴더 전체를 이동한 뒤 index.html을 여세요. 입력·응답·모든 후보 p(true)·선택·전송·공개 protocol은 '
        '오프라인에서 열립니다. 애니메이션만 외부 Showdown 자산을 사용합니다.\n\n'
        'state는 실제 요청의 JSON 문자열이며 파싱한 상태 열람본도 함께 제공합니다. '
        '미전송/미수신과 실제 모델 응답을 구분하며 원 요청·응답 값을 바꾸지 않습니다.\n\n'
        f'원본: {source}\n원본 봉인은 유지하며 내보내기 사본으로 대체하지 않습니다.\n')
    seal(output)
    return dict(matches=matches, export_sha256=file_hash(output / 'checksums.sha256'))
