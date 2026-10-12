"""Render researcher-facing JEV views from a sealed run and existing replay export."""
import argparse
import hashlib
import html
import json
from pathlib import Path

ASSETS = Path(__file__).with_name('viewer_assets')


def load_decisions(source):
    for line in (source / 'checksums.sha256').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != checksum:
            raise ValueError(f'Source seal mismatch: {name}')
    events = [json.loads(line) for line in (source / 'events.jsonl').read_text().splitlines()]
    result = json.loads((source / 'result.json').read_text())
    scheduled = json.loads((source / 'manifest.json').read_text()).get('execution_profile') == 'jev-abyssal32-v1'
    groups = {}
    for event in events:
        if event.get('decision'):
            groups.setdefault(event['decision'], []).append(event)
    battles = {}
    for decision, records in groups.items():
        by_type = {e['type']: e for e in records}
        entry = by_type['input']
        transport = by_type.get('transport')
        response = by_type.get('response')
        selection = by_type.get('selection')
        automatic = bool(selection and selection['automatic'])
        if not automatic and not transport and not scheduled:
            raise ValueError(f'No recorded request model: {decision}')
        request = dict(model=transport['model'], **entry['payload']) if transport else None
        item = dict(id=decision, turn=entry['payload']['state']['turn'],
                    kind=entry['payload']['state']['decision_kind'], automatic=automatic,
                    request=request, observation=entry['payload'] if not request else None,
                    response=response['body'] if response else None,
                    selection=selection, wire=by_type.get('wire'),
                    elapsed=response['elapsed_seconds'] if response else None,
                    diagnostics=by_type.get('judgment_diagnostics', {}).get('diagnostics', []),
                    technical=dict(input_boundary=entry['boundary'], observation_identity=entry['observation_identity'],
                                   transport=transport, http_response=by_type.get('http_response'),
                                   selection=selection, wire=by_type.get('wire')))
        item['technical']['http_attempt_history'] = [e for e in records if e['type'] in
            ('transport', 'http_request', 'http_response', 'attempt_failure', 'provider_retry')]
        battles.setdefault(decision.split('-')[0], []).append(item)
    assert sum(map(len, battles.values())) == (sum(e['type'] == 'input' for e in events) if scheduled else result['sent_actions'])
    return result, battles


def render(source, output):
    source, output = Path(source), Path(output)
    result, battles = load_decisions(source)
    template = (ASSETS / 'jev-researcher.html').read_text().replace(
        '__ACTION_LABELS__', (ASSETS / 'action-labels.js').read_text())
    experiment = json.loads((source / 'manifest.json').read_text())['experiment_id']
    outcomes = result['outcomes']
    if outcomes and 'username' in outcomes[0]:
        pairs = [(o['username'], battles.get(o['username'], []), o) for o in outcomes]
    else:
        pairs = [(u, ds, o) for (u, ds), o in zip(battles.items(), outcomes)]
    for slot, (username, decisions, outcome) in enumerate(pairs, 1):
        target = output / f'battle-{slot}'
        if not (target / 'replay.html').exists():
            raise ValueError('Create the replay export before rendering researcher views')
        if not decisions:
            (target / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
                '<p>입력 수집 전 종료된 경기입니다.</p><a href="replay.html">보존된 경기 로그</a>'
                '<pre>' + html.escape(json.dumps(outcome, ensure_ascii=False, indent=2)) + '</pre></html>')
            continue
        data = dict(experiment=experiment, slot=slot, username=username, outcome=outcome, decisions=decisions)
        encoded = json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
        page = template.replace('__TITLE__', html.escape(f'{experiment} · {slot}경기 · 실험자 뷰어'))
        page = page.replace('__DATA__', encoded)
        (target / 'index.html').write_text(page)
    provenance = json.loads((output / 'provenance.json').read_text())
    provenance['researcher_view'] = dict(version='jev-researcher-v2',
        renderer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        template_sha256=hashlib.sha256((ASSETS/'jev-researcher.html').read_bytes()).hexdigest(),
        action_labels_sha256=hashlib.sha256((ASSETS/'action-labels.js').read_bytes()).hexdigest(),
        request_provenance='recorded transport.model + input.payload; JSON object reconstruction, not HTTP bytes',
        requests=sum(d['request'] is not None for ds in battles.values() for d in ds),
        automatic=sum(d['automatic'] for ds in battles.values() for d in ds))
    (output / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')
    (output / 'checksums.sha256').write_text(''.join(
        hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(output))+'\n'
        for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'checksums.sha256'))
    return provenance['researcher_view']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.source, args.output), ensure_ascii=False))
