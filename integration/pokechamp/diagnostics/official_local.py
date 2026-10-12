"""Two EP-056 matches only, deterministic HTTP transport and preserved failures."""
from __future__ import annotations

import argparse
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import benchmark as b
from .. import team_preview_study as study
from ..improved_io.live_delivery import original_for_call
from ..observation import OFFICIAL
from ..observation.local_protocol import LIMIT
from ..observation.runtime import OfficialClient
from ..permits import PermitBroker
from .official_observation import bounded, read_rows, statistics_for
from .team_preview import audit


def observe(attempts, root):
    records, metrics = [], []
    for attempt in attempts:
        for role, actor in attempt['actors'].items():
            bundle = Path(actor['bundle'])
            manifest = json.loads((bundle / 'manifest.json').read_text())
            events = read_rows(bundle / 'events.jsonl')
            received = [e for e in events if e['event_type'] == 'protocol_in']
            inputs = {e['event_seq']: e for e in events if e['event_type'] == 'input_snapshot'}
            calls = [e for e in events if e['event_type'] == 'llm_call']
            transport = read_rows(root / 'prepared/attempts' / attempt['attempt_id'] / (role + '-mock-http.jsonl'))
            assert len(transport) == len(calls)
            for call, wire in zip(calls, transport):
                assert wire['request']['messages'] == [
                    dict(role='system', content=call['system_prompt']),
                    dict(role='user', content=call['user_prompt']),
                ]
            with OfficialClient(role) as client:
                snapshots = [e for e in events if e['event_type'] == 'observation_snapshot']
                for snapshot in snapshots:
                    prefix = bounded(received, snapshot['boundary'])
                    state = client.snapshot(prefix, manifest['battle_id'], boundary=snapshot['boundary'])
                    assert state == snapshot['official_state']
                    assert state == client.snapshot(prefix, manifest['battle_id'], replay=True)
                    linked = [c for c in calls if c['decision_seq'] == snapshot['decision_seq']]
                    if linked and linked[0]['request']['call_role'] == 'self_action':
                        full = original_for_call(linked[0], inputs)
                        for key, value in snapshot['normalized'].items():
                            if key not in ('calculation_bundle', 'prior_hypotheses'):
                                assert full[key] == value, key
                        assert full['calculation_bundle']['status'] == 'success'
                    records.append(dict(bundle=str(bundle), decision_seq=snapshot['decision_seq'],
                                        boundary=snapshot['boundary'], incremental_full_equal=True,
                                        call_event_seq=linked[0]['event_seq'] if linked else None))
                metrics.extend(client.metrics)
    return dict(passed=True, decisions=records,
                replay_latency_ms=statistics_for([m['elapsed_ms'] for m in metrics]),
                replay_node_peak_rss=max(m['rss_bytes'] for m in metrics))


def run(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    prepared_root = root / 'prepared'
    prepared = study.prepare(prepared_root, transport='fake', concurrency=2,
                             observation_backend=OFFICIAL, local_validation=True)
    rows = prepared['schedule']
    assert len(rows) == 2
    b.seal_json(root / 'local-validation-plan.json', dict(
        planned_local_matches=2, attempts_per_match=1, rematches=0,
        hard_timeout_seconds=LIMIT, rows=rows, provider_calls=0, efficacy_evidence=False,
    ))
    with tempfile.TemporaryDirectory(prefix='ep056-') as short:
        socket = str(Path(short) / 'permit.sock')
        with PermitBroker(socket, prepared['execution']['account_request_limit'],
                          prepared['execution']['model_request_limits']) as broker:
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = [pool.submit(b.run_attempt, root / 'data', prepared_root, prepared, row, 1,
                                    port=8100 + i, broker_path=socket, hard_timeout_seconds=LIMIT)
                        for i, row in enumerate(rows)]
                attempts = [job.result() for job in jobs]
            permits = broker.snapshot()
    b.seal_json(root / 'attempts.json', attempts)
    b.seal_json(root / 'permits.json', permits)
    try:
        assert not sum(permits['active_at_close'].values())
        result = audit(attempts, prepared, prepared_root)
        result['official_observation'] = observe(attempts, root)
    except Exception as error:
        b.seal_json(root / 'verification-failure.json', dict(passed=False, error=repr(error)))
        raise
    b.seal_json(root / 'verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    print(json.dumps(run(parser.parse_args().output), ensure_ascii=False, indent=2))
