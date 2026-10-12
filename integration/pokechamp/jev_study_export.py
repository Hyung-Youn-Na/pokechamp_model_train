"""Portable researcher views and Korean results for sealed JEV schedule runs."""
import argparse
import html
import json
from pathlib import Path
import shutil

from . import jev_study as s
from .jev_viewer import render
from .observability.render import _replay_html


def export(source, output):
    source, output = Path(source), Path(output)
    for line in (source / 'checksums.sha256').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        if s.sha(source / name) != checksum:
            raise ValueError('source seal mismatch')
    manifest = json.loads((source / 'manifest.json').read_text())
    result = json.loads((source / 'result.json').read_text())
    events = [json.loads(line) for line in (source / 'events.jsonl').read_text().splitlines()]
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source / 'result.json', output / 'result.json')
    matches, table = [], []
    labels = dict(player_won='승리', player_lost='패배', tied='무승부', output_failure='출력 실패')
    for outcome in result['outcomes']:
        slot = outcome['slot']
        target = output / f'battle-{slot}'
        target.mkdir()
        user = outcome['username']
        lines = [line for e in events if e['type'] == 'protocol' and e['username'] == user
                 for line in e['protocol'].splitlines() if line.startswith('|') and not line.startswith(('|request|', '|sentchoice|'))]
        protocol = '\n'.join(lines) + '\n'
        if outcome.get('completed') and outcome.get('audit_passed'):
            winners = [line.split('|')[2] for line in lines if line.startswith('|win|')]
            if outcome['outcome'] == 'tied':
                assert '|tie|' in lines and not winners
            else:
                assert len(winners) == 1 and (winners[0] == user) == (outcome['outcome'] == 'player_won')
            assert max(int(line.split('|')[2]) for line in lines if line.startswith('|turn|')) == outcome['turns']
        (target / 'showdown.log').write_text(protocol)
        page = _replay_html(dict(battle_id=f'{manifest["experiment_id"].lower()}-battle-{slot}', teams=[]), protocol)
        page = page.replace('<html lang="en">', '<html lang="ko">').replace(
            'The animated panel uses the official Pokémon Showdown replay asset.\nIf it is unavailable, the Static protocol fallback below remains fully local.',
            '애니메이션은 인터넷 연결이 필요합니다. 오프라인에서는 아래 저장된 경기 로그를 볼 수 있습니다.').replace('Static protocol fallback', '오프라인 경기 로그')
        (target / 'replay.html').write_text(page)
        label = labels.get(outcome.get('outcome'), '기술 실패')
        if outcome.get('completed') and not outcome.get('audit_passed'):
            label += ' · 유효성 미충족'
        table.append(f'<tr><td>{slot}</td><td>{html.escape(outcome["slot_id"])}</td><td>{" / ".join(outcome["teams"])}</td>'
                     f'<td>{outcome["jev_actor"]}</td><td>{label}</td><td>{outcome.get("turns", "—")}</td>'
                     f'<td><a href="battle-{slot}/index.html">입력·응답 + 리플레이</a></td></tr>')
        matches.append(dict(slot=slot, slot_id=outcome['slot_id'], username=user, actor=outcome['jev_actor'],
                            completed=outcome['completed'], protocol_sha256=s.sha(target / 'showdown.log')))
    summary = f'유효완료 {result["completed"]}/{result["planned"]} · JEV {result["actual_wins"]}승 {result["actual_draws"]}무 {result["actual_losses"]}패 · 완료쌍 {result["completed_pairs"]}'
    title = manifest['experiment_id'] + ' · JEV 대 Abyssal'
    (output / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title><style>body{{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px;line-height:1.7}}'
        'table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ccc;padding:10px;text-align:left}.scroll{overflow:auto}a{color:#165fa5}</style>'
        f'<a href="../index.html">← 실험 목록</a><h1>{title}</h1><p>{summary}</p>'
        '<p>GLM EX-046의 팀·seed 대진을 사용하고 상대를 Abyssal로 고정한 탐색 실험입니다. GLM과의 모델 우열 비교가 아닙니다.</p>'
        '<p>입력·응답·경기 로그는 오프라인에서 열립니다. 배틀 애니메이션에는 인터넷 연결이 필요합니다.</p>'
        f'<p>실패 {result["failed"]} · 무효 {result["invalid"]} · 미실행 {result["unattempted"]}</p>'
        '<div class="scroll"><table><thead><tr><th>경기</th><th>대진 ID</th><th>p1 / p2 팀</th><th>JEV 진영</th><th>결과</th><th>턴</th><th>열기</th></tr></thead><tbody>'
        + ''.join(table) + '</tbody></table></div><p><a href="result.json">상세 결과 JSON</a></p></html>')
    (output / 'README.md').write_text(f'# {title}\n\n폴더 전체를 이동한 뒤 index.html을 여세요.\n입력·응답·공개 로그는 오프라인, 애니메이션은 인터넷 연결이 필요합니다.\n원본: {source}\n원본을 복사본으로 대체하지 않습니다. 기술 실패는 패배로 집계하지 않습니다.\n')
    s.j.write(output / 'provenance.json', dict(experiment=manifest['experiment_id'], source=str(source),
        planned=result['planned'], completed=result['completed'], matches=matches,
        source_files={n: s.sha(source / n) for n in ('events.jsonl', 'result.json', 'manifest.json', 'checksums.sha256')},
        builder_sha256=s.sha(Path(__file__)), renderer_sha256=s.sha(Path(__file__).parent / 'observability/render.py')))
    render(source, output)
    return dict(summary=summary, matches=len(matches), source_seal=s.sha(source / 'checksums.sha256'), export_seal=s.sha(output / 'checksums.sha256'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    print(json.dumps(export(args.source, args.output), ensure_ascii=False))
