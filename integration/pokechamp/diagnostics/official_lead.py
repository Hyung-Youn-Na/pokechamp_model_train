"""EX-045's exactly four one-shot, mock HTTP, actual-coordinator local matches."""
import argparse
import json
from pathlib import Path

from .. import benchmark as b, team_preview_study as study, team_preview_run as runner


def run(output):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    root=output/'prepared'
    value=study.prepare(root,experiment_id='EX-045',transport='fake')
    first,_=runner.staged_schedule(value['schedule'])
    purpose=output/'local-plan.json'
    b.seal_json(purpose,dict(planned=4,rows=first,attempts_per_match=1,rematches=0,
                            hard_timeout_seconds=600,external_model_calls=0,efficacy_evidence=False))
    receipt=output/'fake-entry.json'
    b.seal_json(receipt,dict(source_files=value['parent_files'],local_passed=True,wire_passed=True,
        execution_protocol=study.execution_protocol(value),
        purpose='mock_execution_only_not_paid_qualification',
        evidence=[dict(path=str(purpose),sha256=b.digest(purpose))]))
    result=runner.run(root,output/'data',verification=receipt,local_first_four=True)
    gate=b.read_sealed(root/'first-pair-check.json')
    attempts=[b.read_sealed(p) for p in sorted((root/'attempts').glob('*/result.json'))]
    cleanup=b.read_sealed(root/'cleanup.json')
    # Exact mock HTTP messages are independent transport evidence, not just traces.
    wires=0
    for attempt in attempts:
        for role,actor in attempt['actors'].items():
            events=[json.loads(line) for line in (Path(actor['bundle'])/'events.jsonl').read_text().splitlines()]
            calls=[e for e in events if e['event_type']=='llm_call']
            transport=[json.loads(line) for line in (root/'attempts'/attempt['attempt_id']/(role+'-mock-http.jsonl')).read_text().splitlines()]
            assert len(calls)==len(transport)
            for call,wire in zip(calls,transport,strict=True):
                assert wire['request']['messages']==[dict(role='system',content=call['system_prompt']),dict(role='user',content=call['user_prompt'])]
                wires+=1
    passed=(len(attempts)==4 and all(a['eligible'] for a in attempts) and gate['passed']
            and not result['technical_errors'] and cleanup['remaining_permits']==0 and cleanup['socket_removed']
            and study.shared.source_identity()==value['parent_files'])
    final=dict(passed=passed,local_passed=passed,wire_passed=passed,source_files=value['parent_files'],
               attempts=4,valid=sum(a['eligible'] for a in attempts),rematches=0,wire_calls=wires,
               external_model_calls=0,gate=gate,cleanup=cleanup,report=result)
    b.seal_json(output/'verification.json',final)
    return final


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    value=run(p.parse_args().output)
    print(json.dumps({k:value[k] for k in ('passed','attempts','valid','wire_calls','external_model_calls')}))
    raise SystemExit(0 if value['passed'] else 2)
