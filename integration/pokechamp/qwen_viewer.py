"""Portable offline candidate-q/decision viewer beside the saved Showdown replay."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import qwen_value as v
from .branch_rollouts.common import rows, file_hash, write
from .observability.render import _replay_html


def seal(folder):
    files = sorted(p for p in folder.rglob('*') if p.is_file() and p.name != 'checksums.sha256')
    (folder / 'checksums.sha256').write_text(''.join(
        file_hash(p) + '  ' + str(p.relative_to(folder)) + '\n' for p in files))


def export(source, output, *, result_path=None):
    source, output = Path(source), Path(output)
    for line in (source / 'checksums.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if file_hash(source / name) != digest:
            raise ValueError('source seal mismatch: ' + name)
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((source / 'manifest.json').read_text())
    result_path = Path(result_path) if result_path else source / 'result.json'
    result = json.loads(result_path.read_text())
    experiment = manifest['experiment_id']
    events = rows(source / 'events.jsonl')
    template = Path(__file__).with_name('viewer_assets') / 'qwen-local.html'
    action_labels = template.with_name('action-labels.js')
    matches = []
    links = []
    for outcome in result['outcomes']:
        slot = outcome['slot']
        folder = output / f'battle-{slot}'
        folder.mkdir()
        user = outcome['username']
        by_decision = {}
        for event in events:
            if event.get('decision', '').split('-')[0] == user:
                by_decision.setdefault(event['decision'], {})[event['type']] = event
        decisions = []
        for key, records in by_decision.items():
            if 'input' not in records:
                continue
            entry = records['input']
            decisions.append(dict(id=key, turn=entry['payload']['state']['turn'],
                kind=entry['payload']['state']['decision_kind'],
                request=records.get('http_request', {}).get('body'),
                response=records.get('response', {}).get('body'),
                selection=records.get('selection'), wire=records.get('wire'),
                technical=dict(boundary=entry['boundary'], observation_identity=entry['observation_identity'],
                               input_audit=entry['input_audit'], input_generation_seconds=entry['input_generation_seconds'])))
        protocol = '\n'.join(line for event in events if event['type'] == 'protocol' and event['username'] == user
            for line in event['protocol'].splitlines()
            if line.startswith('|') and not line.startswith(('|request|', '|sentchoice|'))) + '\n'
        (folder / 'showdown.log').write_text(protocol)
        (folder / 'replay.html').write_text(_replay_html(dict(battle_id=f'{experiment.lower().replace("-", "")}-{slot}', teams=[]), protocol))
        data = dict(experiment=experiment, outcome=outcome, decisions=decisions)
        encoded = json.dumps(data, ensure_ascii=False).replace('&', '\u0026').replace('<', '\u003c').replace('>', '\u003e')
        (folder / 'index.html').write_text(template.read_text().replace('__EXPERIMENT__', experiment)
            .replace('__ACTION_LABELS__', action_labels.read_text()).replace('__DATA__', encoded))
        (folder / 'decisions.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        matches.append(dict(slot=slot, decisions=len(decisions), protocol_sha256=file_hash(folder / 'showdown.log')))
        labels = dict(player_won='승리', player_lost='패배', tied='무승부')
        links.append(f'<li><a href="battle-{slot}/index.html">{slot}경기 · Qwen {outcome["qwen_actor"]} · '
            f'{labels.get(outcome.get("outcome"), "미완료")} · {outcome.get("turns", "—")}턴</a></li>')
    (output / 'index.html').write_text(f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>{experiment} Qwen 배틀</title>'
        '<style>body{font:17px system-ui;max-width:1000px;margin:40px auto;line-height:1.8}</style>'
        f'<a href="../index.html">실험 목록</a><h1>{experiment} · Qwen 로컬 배틀 연결</h1>'
        f'<p>정상 완료 {result["completed"]}/{result["planned"]} · {result["wins"]}승 {result["draws"]}무 {result["losses"]}패</p>'
        '<p>연결 검증 결과이며 성능 개선 판정에 사용하지 않습니다. 입력·후보별 q·선택·전송·경기 로그는 오프라인에서 열립니다. '
        '애니메이션은 인터넷 연결이 필요합니다.</p><ul>' + ''.join(links) + '</ul><a href="result.json">결과 JSON</a></html>')
    shutil.copyfile(result_path, output / 'result.json')
    if result_path != source / 'result.json':
        shutil.copyfile(source / 'result.json', output / 'original-result.json')
        index = output / 'index.html'
        index.write_text(index.read_text().replace('<ul>',
            '<p>원 자동 감사의 protocol 빈 줄 누락을 교정한 전수 감사 결과입니다. '
            '<a href="original-result.json">원 감사 실패 결과</a>도 보존합니다.</p><ul>', 1))
    write(output / 'provenance.json', dict(experiment=experiment, source=str(source),
        planned=result['planned'], completed=result['completed'], matches=matches,
        evaluation_result=dict(path=str(result_path), sha256=file_hash(result_path)),
        source_files={n: file_hash(source / n) for n in ['manifest.json', 'events.jsonl', 'result.json', 'checksums.sha256']},
        builder_sha256=file_hash(Path(__file__)), template_sha256=file_hash(template),
        action_labels_sha256=file_hash(action_labels)))
    (output / 'README.md').write_text(f'# {experiment} 뷰어\n\n폴더 전체를 이동하여 index.html을 여세요.\n'
        '입력·후보별 q·실제 전송·공개 protocol은 오프라인, 애니메이션은 온라인입니다.\n'
        f'원본: {source}\n원본 봉인은 유지하며 사본으로 대체하지 않습니다.\n')
    seal(output)
    return dict(matches=matches, export_sha256=file_hash(output / 'checksums.sha256'))
