"""EP-056 full-prefix equivalence and observation→calculator→B/B2 string audit."""

from __future__ import annotations

import argparse
import copy
import gzip
import html
import json
import statistics
import time
from pathlib import Path

from ..improved_io.calculations import compute
from ..improved_io.calculator import Calculator
from ..improved_io.gate import validate_input
from ..improved_io.state import stable_id
from ..observation.delivery import build, validate
from ..observation.normalize import normalize
from ..observation.runtime import OfficialClient
from ..observability import verify_bundle

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / ".pokechamp-data/observation-comparison/ep055/comparison-final-v2"


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def bounded(received, boundary):
    prefix = [dict(e) for e in received if e["event_seq"] <= boundary["protocol_event_seq"]]
    if not prefix or prefix[-1]["event_seq"] != boundary["protocol_event_seq"]:
        raise ValueError("missing source boundary event")
    lines = prefix[-1]["protocol"].splitlines()
    if not 0 <= boundary["line_index"] < len(lines):
        raise ValueError("missing source boundary line")
    prefix[-1]["protocol"] = "\n".join(lines[:boundary["line_index"] + 1])
    return prefix


def statistics_for(values):
    values = sorted(values)
    if not values:
        return None
    return dict(count=len(values), mean=statistics.mean(values), median=statistics.median(values),
                p95=values[min(len(values) - 1, int(len(values) * .95))], maximum=max(values))


def render_record(record, target):
    def detail(label, value):
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'
    title = f"{record['actor_view']} · 결정 {record['decision_seq']} · 턴 {record['turn']}"
    parts = ['<!doctype html><html lang="ko"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
             '<style>body{font:16px system-ui;max-width:1200px;margin:24px auto;padding:0 16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer;background:#edf3f7;padding:12px;margin-top:10px}a{color:#167}</style>',
             '<title>' + html.escape(title) + '</title><h1>' + html.escape(title) + '</h1>',
             '<p><a href="../index.html">결정 목록</a> · <a href="' + target.stem + '.json.gz">전체 연결 기록 gzip</a></p>',
             '<p>공식 증분/전체 재생 일치. 문자열은 오프라인 생성값이며 과거 모델에 전송된 교정 입력이 아닙니다.</p>']
    for label, key in [('수신 경계', 'boundary'), ('행 경계까지의 수신 원문', 'received_prefix'),
                       ('공식 상태', 'official_state'), ('정규화 관측', 'normalized'),
                       ('계산기 요청', 'calculator_request'), ('선봉의 별도 입력 경계', 'lead'),
                       ('오류', 'error')]:
        if key in record:
            parts.append(detail(label, record[key]))
    for kind, delivered in record.get('deliveries', {}).items():
        parts.extend([detail(kind + ' system 원문', delivered['system_prompt']),
                      detail(kind + ' user 원문', delivered['user_json']),
                      detail(kind + ' 전송 연결', json.loads(delivered['source_link_json']))])
    target.write_text('\n'.join(parts) + '</html>')


def audit(output, source=SOURCE):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    records_dir = output / 'decisions'
    records_dir.mkdir()
    summary, timings, operations = [], [], []
    source_hashes = {}
    from ..benchmark import digest, source_files

    implementation = {str(p): digest(p) for p in source_files()}

    for directory in sorted(Path(source).iterdir()):
        if not directory.is_dir():
            continue
        previous = read_rows(directory / 'comparisons.jsonl')
        received = read_rows(directory / 'received.jsonl')
        bundle = Path(previous[0]['source_bundle'])
        if not verify_bundle(bundle)['valid']:
            raise ValueError('source bundle seal mismatch')
        manifest = json.loads((bundle / 'manifest.json').read_text())
        for path in (directory / 'comparisons.jsonl', directory / 'received.jsonl',
                     bundle / 'events.jsonl', bundle / 'manifest.json'):
            source_hashes[str(path)] = digest(path)
        own = next(t['showdown_team'] for t in manifest['teams'] if t['role'] == 'player')
        boundaries = []
        with OfficialClient(previous[0]['actor']) as client, Calculator() as calc:
            for row in previous:
                record = dict(actor_view=directory.name, actor=row['actor'], decision_seq=row['decision_seq'],
                              turn=row['turn'], decision_kind=row['decision_kind'], source_bundle=str(bundle),
                              boundary=row['boundary'], source_prefix_sha256=row['prefix_sha256'])
                started = time.monotonic()
                try:
                    prefix = bounded(received, row['boundary'])
                    # EP-055's digest uses ensure_ascii=False and a different serializer.
                    import hashlib
                    old_digest = hashlib.sha256(json.dumps(prefix, sort_keys=True, ensure_ascii=False,
                                                          separators=(',', ':')).encode()).hexdigest()
                    if old_digest != row['prefix_sha256']:
                        raise ValueError('EP-055 source-prefix digest mismatch')
                    official = client.snapshot(prefix, manifest['battle_id'], boundary=row['boundary'])
                    full = client.snapshot(prefix, manifest['battle_id'], replay=True)
                    if official != full:
                        raise ValueError('incremental/full official state mismatch')
                    record.update(received_prefix=prefix, official_state=official, incremental_full_equal=True)
                    if row['decision_kind'] == 'team_preview':
                        if not official['request']:
                            record['lead'] = dict(policy='seeded_random', self_request_available=False,
                                                  information_boundary='public_preview_only; unchanged existing shuffle')
                        else:
                            from ..team_preview import build_input
                            context = build_input(own, prefix, battle_id=manifest['battle_id'], actor_id=row['actor'], decision_seq=row['decision_seq'])
                            record['lead'] = dict(self_request_available=True, input=context)
                            events = read_rows(bundle / 'events.jsonl')
                            snapshots = [e['original_input'] for e in events if e['event_type'] == 'input_snapshot'
                                         and e.get('decision_seq') == row['decision_seq']]
                            if snapshots and context not in snapshots:
                                raise ValueError('historical lead cutoff/input changed')
                        record['status'] = 'lead_boundary_verified'
                    else:
                        cutoff = boundaries[-10] if len(boundaries) >= 10 else -1
                        recent = [e for e in prefix if e['event_seq'] > cutoff]
                        value, candidates = normalize(official, own, recent, prefix,
                            battle_id=manifest['battle_id'], actor_id=row['actor'], decision_seq=row['decision_seq'],
                            build_identity=client.identity)
                        value['condition_id'] = 'B'
                        value['calculation_bundle'] = compute(value, calc)
                        validate_input(value)
                        record.update(normalized=value, calculator_request=copy.deepcopy(calc.last_request),
                                      calculator_response=copy.deepcopy(calc.last_response),
                                      candidate_slots=[dict(action=c.record()['action'], wire=c.target) for c in candidates.entries])
                        deliveries = {}
                        for name, kind in [('B', 'battle'), ('B2', 'b2')]:
                            delivery = build(value, kind=kind)
                            link = validate(value, delivery, delivery.system_prompt, delivery.user_json, kind=kind)
                            wire = json.dumps(dict(messages=[dict(role='system', content=delivery.system_prompt),
                                                           dict(role='user', content=delivery.user_json)]), ensure_ascii=False)
                            if json.loads(wire)['messages'][1]['content'] != delivery.user_json:
                                raise ValueError('final string serialization mismatch')
                            deliveries[name] = dict(**delivery.as_dict(), wire_sha256=stable_id(json.loads(wire)),
                                                    source_kind='offline_generated_not_sent')
                            assert link['identity'] == value['identity']
                        record.update(deliveries=deliveries, status='battle_chain_verified')
                        boundaries.append(prefix[-1]['event_seq'])
                except Exception as error:
                    record.update(status='failed', error=f'{type(error).__name__}: {error}')
                record['elapsed_ms'] = (time.monotonic() - started) * 1000
                timings.append(record['elapsed_ms'])
                name = f"{directory.name}-d{row['decision_seq']:04}"
                with gzip.open(records_dir / (name + '.json.gz'), 'wt', encoding='utf-8') as stream:
                    json.dump(record, stream, ensure_ascii=False, allow_nan=False)
                render_record(record, records_dir / (name + '.html'))
                summary.append({k: record[k] for k in ('actor_view', 'decision_seq', 'turn', 'decision_kind', 'status', 'elapsed_ms')}
                               | dict(viewer='decisions/' + name + '.html', error=record.get('error')))
            operations.extend(client.metrics)
    preserved = all(digest(path) == checksum for path, checksum in source_hashes.items())
    implementation_preserved = all(digest(path) == checksum for path, checksum in implementation.items())
    result = dict(decisions=len(summary), battle_verified=sum(r['status'] == 'battle_chain_verified' for r in summary),
                  lead_verified=sum(r['status'] == 'lead_boundary_verified' for r in summary),
                  failures=[r for r in summary if r['status'] == 'failed'], source_preserved=preserved,
                  source_hashes=source_hashes, implementation_hashes=implementation,
                  implementation_preserved=implementation_preserved, records=summary,
                  decision_chain_ms=statistics_for(timings),
                  incremental_ms=statistics_for([r['elapsed_ms'] for r in operations if r['operation'] == 'append']),
                  full_replay_ms=statistics_for([r['elapsed_ms'] for r in operations if r['operation'] == 'replay']),
                  node_rss_bytes=statistics_for([r['rss_bytes'] for r in operations]),
                  provider_calls=0, efficacy_evidence=False)
    result['passed'] = result['decisions'] == 100 and result['battle_verified'] == 96 and result['lead_verified'] == 4 and preserved and implementation_preserved
    write(output / 'report.json', result)
    write(output / 'operations.json', operations)
    links = ''.join('<li><a href="' + r['viewer'] + '">' + html.escape(f"{r['actor_view']} 결정{r['decision_seq']} 턴{r['turn']}") + '</a> — ' + r['status'] + '</li>' for r in summary)
    (output / 'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EP-056 관측 연결</title><h1>EP-056 공식 관측 → 계산 → B/B2</h1><p>100개 보존 경계의 오프라인 재생. 모델 선택·승률 평가는 아닙니다.</p><p><a href="report.json">검증·지연·메모리 보고</a></p><ul>' + links + '</ul></html>')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = audit(args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in ('records', 'source_hashes')}, ensure_ascii=False))
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
