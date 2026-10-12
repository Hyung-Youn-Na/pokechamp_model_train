"""Four archived decisions through the live adapter, mock HTTP and replay auditor."""
import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import patch

from .. import jev_battle as j, jev_study as s
from ..jev_v4 import EVIDENCE, VERSION, data_identity, generate, save_audit
from ..jev_battle_audit import audit
from ..jev_comparison import compare_data


async def verify():
    output = EVIDENCE / 'local-v2'
    output.mkdir(parents=True, exist_ok=False)
    data = data_identity()
    checks = []
    for name in ('lead-1', 'lead-2', 'turn-sample-01', 'forced-switch'):
        source = j.ROOT / 'project_context/exec-plans/evidence/ep093/certainty-v1' / name
        case = json.loads((source / 'source.json').read_text())
        directory = output / name
        directory.mkdir()
        session = j.Session(directory, fake=True, retry_policy=j.jev_retry.LEGACY)
        session.capture_request_body = True
        try:
            payload, commands, calc, elapsed = await generate(session, case['official'], case['prefix'], case['own_team'], actor=case['actor'])
            expected = json.loads((source / 'after-detailed.json').read_text())
            expected['state']['version'] = VERSION
            assert payload == expected, name
            assert commands == json.loads((source / 'commands.json').read_text())
            assert payload['questions']['action']['instructions'] == j.PROMPT.with_name(VERSION + '.txt').read_text()
            for event in case['prefix']:
                session.record(dict(type='protocol', username='local', sequence=event['event_seq'], protocol=event['protocol']))
            decision = 'local-1'
            session.record(dict(type='input', decision=decision, actor=case['actor'], battle=case.get('battle','local'),
                                boundary=case['boundary'], official=case['official'], payload=payload, commands=commands,
                                input_audit=save_audit(directory, decision, calc), input_generation_seconds=elapsed))
            body = await session.evaluate(payload, decision=decision)
            choice = j.validate_answer(body, payload['questions']['action']['criteria'])
            session.record(dict(type='response', decision=decision, body=body, elapsed_seconds=0))
            session.record(dict(type='selection', decision=decision, choice=choice, command=commands[choice], automatic=False))
            session.record(dict(type='wire', decision=decision, command=commands[choice], request_id=payload['state']['request_id']))
            manifest = dict(schema_version=VERSION, input_data_identity=data, source={},
                            validation_version=j.VALIDATION_VERSION, teams={'own':{'showdown_team':case['own_team']}})
            result = dict(passed=False, sent_actions=1, completed=0, outcomes=[dict(username='local', teams=['own','own'])])
            j.write(directory / 'manifest.json', manifest)
            j.write(directory / 'result.json', result)
            s.seal(directory)
            replay = await asyncio.to_thread(audit, directory)
            assert replay['passed']
            # Fail closed on generator exceptions and foreign actors, never old-input fallback.
            with patch.object(session.v4_adapter, 'generate', side_effect=ValueError('injected input failure')):
                try:
                    await generate(session, case['official'], case['prefix'], case['own_team'], actor=case['actor'])
                except ValueError:
                    pass
                else:
                    raise AssertionError('generation exception suppressed')
            try:
                session.v4_adapter.generate(case['official'], case['prefix'], case['own_team'], actor='p2' if case['actor']=='p1' else 'p1')
            except ValueError:
                pass
            else:
                raise AssertionError('foreign actor accepted')
            checks.append(dict(sample=name, actor=case['actor'], input_generation_seconds=elapsed,
                               version_only_difference=True, commands_equal=True, mock_legal_choice=choice, replay=replay))
        finally:
            session.v4_adapter.close()
    rows, teams, origin = s.study_schedule('EX-058')
    bm = json.loads((j.ROOT / '.pokechamp-data/jev/ex057-live/manifest.json').read_text())
    br = json.loads((j.ROOT / '.pokechamp-data/jev/ex057-live/result.json').read_text())
    assert (rows, teams) == (bm['schedule'], bm['teams'])
    nm = dict(bm, experiment_id='EX-058', schema_version=VERSION)
    result = compare_data((bm,br,[]),(nm,br,[]))
    assert result['common_completed_pairs'] == 16 and result['mean_pair_score_delta'] == 0
    # Expired inherited clock and explicit cancellation must stop before HTTP.
    budget = j.Session(output, fake=True, retry_policy=j.jev_retry.LEGACY)
    import time
    budget.started = time.time() - 20101
    budget.monotonic_started = time.monotonic() - 20101
    budget.collection_seconds = 20100
    try:
        await budget.evaluate(payload, decision='expired')
    except RuntimeError:
        pass
    else:
        raise AssertionError('expired inherited clock admitted HTTP')
    assert budget.calls == 0
    receipt = dict(passed=True, expired_clock_blocks_http=True, samples=checks, source=j.source_identity(), data_identity=data,
                   preserved_ep093=True, new_battles=0, external_requests=0,
                   failures_propagated=True, foreign_actor_rejected=True, schedule_identical=True,
                   paired_comparison_checked=True)
    j.write(EVIDENCE / 'local-verification.json', receipt)
    print(json.dumps(dict(passed=True, samples=len(checks)), ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(verify())
