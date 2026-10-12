"""EP-058 one-shot 8-match/16-actor local concurrency validation, HTTP mocked."""
import argparse
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from .. import benchmark as b, team_preview_study as study, team_preview_run as runner


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = output/'prepared'
    from ..distributed_lead import prepare
    value = prepare(root, experiment_id='EX-045', transport='fake', concurrency=8, local_identity='ep058-local-eight')
    rows = runner.local_eight_rows(value['schedule'])
    purpose = output/'local-plan.json'
    b.seal_json(purpose, dict(identity='ep058-local-eight', planned=8, actors=16, rows=rows,
        attempts_per_match=1, rematches=0, hard_timeout_seconds=1200, total_seconds=1800,
        cleanup_reserve_seconds=60, external_model_calls=0, efficacy_evidence=False))
    receipt = output/'fake-entry.json'
    b.seal_json(receipt, dict(source_files=value['parent_files'], local_passed=True, wire_passed=True,
        execution_protocol=study.execution_protocol(value), purpose='mock_execution_only_not_paid_qualification',
        evidence=[dict(path=str(purpose),sha256=b.digest(purpose))]))
    started = time.time()
    stop = threading.Event()
    samples, owned = [], {}
    def monitor():
        while not stop.is_set():
            table = {}
            for line in subprocess.check_output(['ps','-eo','pid=,ppid=,rss=,args='],text=True).splitlines():
                fields = line.strip().split(None,3)
                if len(fields)==4:
                    pid, parent, rss = map(int,fields[:3])
                    table[pid] = (parent,rss,fields[3])
            descendants = {os.getpid()}
            while True:
                expanded = descendants | {pid for pid,(parent,_,_) in table.items() if parent in descendants}
                if expanded == descendants: break
                descendants = expanded
            children = {pid:table[pid] for pid in descendants if pid != os.getpid() and pid in table
                        and not table[pid][2].startswith('ps -eo')}
            owned.update({str(pid):args for pid,(_,_,args) in children.items()})
            samples.append(dict(at=time.time(), rss_kib=sum(v[1] for v in children.values()),
                actors=sum('improved_io_local_worker --worker' in v[2] for v in children.values()),
                trackers=sum('observation/client.cjs serve' in v[2] for v in children.values()),
                processes=list(children)))
            stop.wait(.25)
    monitor_thread = threading.Thread(target=monitor,daemon=True)
    monitor_thread.start()
    try:
        report = runner.run(root, output/'data', verification=receipt, local_eight=True)
    finally:
        stop.set()
        monitor_thread.join(timeout=5)
        remaining = []
        for pid, args in owned.items():
            try:
                actual = Path('/proc')/pid/'cmdline'
                if actual.exists() and actual.read_bytes().replace(b'\0',b' ').decode().strip() == args:
                    remaining.append(int(pid))
            except FileNotFoundError:
                pass
        b.seal_json(output/'processes.json',dict(samples=samples,owned=owned,remaining=remaining,
            peak_actors=max((r['actors'] for r in samples),default=0),
            peak_trackers=max((r['trackers'] for r in samples),default=0),
            peak_rss_kib=max((r['rss_kib'] for r in samples),default=0)))
    attempts = [b.read_sealed(p) for p in sorted((root/'attempts').glob('*/result.json'))]
    cleanup = b.read_sealed(root/'cleanup.json')
    wires = 0
    for attempt in attempts:
        for role, actor in attempt['actors'].items():
            events = [json.loads(l) for l in (Path(actor['bundle'])/'events.jsonl').read_text().splitlines()]
            calls = [e for e in events if e['event_type']=='llm_call']
            transport = [json.loads(l) for l in (root/'attempts'/attempt['attempt_id']/(role+'-mock-http.jsonl')).read_text().splitlines()]
            assert len(calls) == len(transport)
            for call, wire in zip(calls,transport,strict=True):
                assert wire['request']['messages'] == [dict(role='system',content=call['system_prompt']),dict(role='user',content=call['user_prompt'])]
                wires += 1
    batch = b.read_sealed(root/'batch.json')
    receipts = [b.read_sealed(p) for p in (root/'input-audit-receipts').glob('*.json')]
    process_check = b.read_sealed(output/'processes.json')
    passed = (process_check['peak_actors']==16 and process_check['peak_trackers']==16
              and not process_check['remaining'] and len(attempts)==8 and all(a['eligible'] for a in attempts) and len(receipts)==8
              and all(r['passed'] for r in receipts) and not report['technical_errors']
              and cleanup['remaining_permits']==0 and cleanup['socket_removed']
              and cleanup['completed_at']-started <= 1800
              and study.shared.source_identity()==value['parent_files'])
    final = dict(passed=passed, attempts=len(attempts), valid=sum(a['eligible'] for a in attempts),
        planned=8, rematches=0, wire_calls=wires, external_model_calls=0, cleanup=cleanup,
        batch=batch, report=report, process_check={k:v for k,v in process_check.items() if k not in ('samples','owned')}, source_files=value['parent_files'], elapsed_seconds=time.time()-started,
        main_first_four_gate_created=(root/'first-pair-check.json').exists())
    b.seal_json(output/'verification.json',final)
    return final


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({k:result[k] for k in ('passed','attempts','valid','wire_calls','external_model_calls')}))
    raise SystemExit(0 if result['passed'] else 2)
