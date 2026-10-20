"""Read-only EX108 re-export with the established researcher viewer layout."""
import argparse
import html
import json
import shutil
from pathlib import Path

from .core import ROOT, RUN
from .storage import digest, seal, write

HERE = Path(__file__).parent
STYLE = ROOT/'integration/pokechamp/viewer_assets/jev-researcher.html'


def render(data):
    template = (HERE/'viewer.html').read_text()
    css = STYLE.read_text().split('<style>', 1)[1].split('</style>', 1)[0]
    encoded = json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    return template.replace('__STYLE__', css).replace('__DATA__', encoded).replace('__SCRIPT__', (HERE/'viewer.js').read_text())


def export_viewer(output, previous):
    """Write only a new viewer directory; never audit/reseal the source experiment."""
    output, previous = Path(output), Path(previous)
    if output.exists():
        raise FileExistsError(output)
    report = json.loads((RUN/'report.json').read_text())
    outcomes = json.loads((RUN/'collection/result.json').read_text())['outcomes']
    events = [json.loads(line) for line in (RUN/'collection/events.jsonl').open()]
    grouped = {}
    for event in events:
        if event.get('decision'):
            grouped.setdefault(event['decision'], {})[event['type']] = event
    output.mkdir(parents=True)
    links = []
    for row in outcomes:
        slot = row['slot']
        decisions = []
        for key, records in grouped.items():
            inp = records.get('input')
            if not inp or inp['slot_id'] != row['slot_id']:
                continue
            decisions.append(dict(id=key, turn=inp['official']['turn'], kind=inp['payload']['kind'],
                messages=inp['payload']['messages'], candidates=inp['payload']['candidates'],
                response=records.get('response'), selection=records.get('selection'), wire=records.get('wire'),
                boundary=inp['boundary'], observation_identity=inp['observation_identity']))
        # Reuse the already verified public replay, without rebuilding game state.
        for name in (f'battle-{slot}.log', f'replay-{slot}.html'):
            shutil.copy2(previous/name, output/name)
        data = dict(outcome=row, decisions=decisions, replay=(previous/f'battle-{slot}.log').read_text())
        (output/f'battle-{slot}.html').write_text(render(data))
        links.append(f'<tr><td><a href="battle-{slot}.html">경기 {slot} · {html.escape(row["slot_id"])}</a></td><td>{html.escape(row["outcome"])}</td><td>{len(decisions)}</td></tr>')
    css = STYLE.read_text().split('<style>', 1)[1].split('</style>', 1)[0]
    (output/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EX-108 Tacit RuleQA</title><style>'+css+'</style><body><header class="page-header"><a href="../index.html">← 실험 목록</a><h1>EX-108 · Tacit RuleQA</h1><p>정상 '+str(report['completed'])+'/32 · '+str(report['wins'])+'승 '+str(report['draws'])+'무 '+str(report['losses'])+'패</p><p class="muted">학습 모델의 고정 대진 탐색 결과 · 미학습 모델과의 직접 비교 없음</p><p><a href="report.json">세부 지표</a> · <a href="provenance.json">출처</a> · <a href="../ex108-v1/index.html">이전 뷰어 판본</a></p><section class="panel table-wrap"><table><thead><tr><th>경기</th><th>결과</th><th>결정 수</th></tr></thead><tbody>'+''.join(links)+'</tbody></table></section></header></body></html>')
    shutil.copy2(RUN/'report.json', output/'report.json')
    write(output/'provenance.json', dict(renderer='tacit-ruleqa-researcher-v2', source=str(RUN),
        previous_viewer='../ex108-v1', previous_seal_sha256=digest(previous/'checksums.sha256'),
        source_files={name:digest(RUN/name) for name in ('manifest.json','report.json','collection/events.jsonl','collection/result.json')},
        renderer_files={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__), HERE/'viewer.html', HERE/'viewer.js', STYLE)},
        normal_completed=report['completed'], replay='unchanged actor public protocol and original replay',
        request='stored messages; automatic decisions were not sent to the model'))
    seal(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    args = parser.parse_args()
    export_viewer(args.output, args.previous)
