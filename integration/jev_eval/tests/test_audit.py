"""Actual v6 saved-observation regeneration and receipt-only final arithmetic."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from integration.jev_eval import audit, battle, client, config, study
from integration.jev27b.formatting import format_request
from integration.pokechamp import jev_battle as j, jev_v6
from integration.pokechamp.observation.build import DEFAULT_BUILD


def transport_events(payload, cfg):
    identity, rid, decision = 'a' * 64, cfg.namespace + '-fixture', 'fixture-1'
    raw = client.request_bytes(payload, config=cfg).decode()
    checksum = hashlib.sha256(raw.encode()).hexdigest()
    choice = next(iter(payload['questions']['action']['criteria']))
    response = dict(model=cfg.model_id, answers={'action': dict(type='choice', choice=choice)},
        usage=dict(input_tokens=123, output_tokens=0), transport=dict(protocol=client.PROTOCOL,
            serving_identity=identity, request_id=rid, body_sha256=checksum, inference_calls=1,
            inference_id=hashlib.sha256((identity + '\0' + rid + '\0' + checksum).encode()).hexdigest()))
    fields = dict(decision=decision, request_number=1, request_id=rid, body_sha256=checksum, attempt=1)
    events = [dict(type='transport', model=cfg.model_id, endpoint=cfg.endpoint + '/v1/systemone',
        serving_identity=identity, timeout=600, **fields),
        dict(type='http_request', body=dict(model=cfg.model_id, **payload), raw_body=raw, **fields),
        dict(type='local_transport', metadata=dict(request_id=rid, body_sha256=checksum,
            request_body=raw, serving_identity=identity), **fields),
        dict(type='http_response', raw_body=json.dumps(response), status_code=200, **fields),
        dict(type='response', decision=decision, body=response)]
    return events, identity


@pytest.mark.parametrize('experiment', ['EX-088', 'EX-089', 'EX-090'])
@pytest.mark.parametrize('illegal', [False, True])
def test_one_match_audit_reconstructs_original_facts_and_rejects_command_drift(
        tmp_path, monkeypatch, experiment, illegal):
    cfg = config.experiment(experiment)
    input_adapter = cfg.input_adapter
    saved = config.ROOT / 'project_context/exec-plans/evidence/ep093/certainty-v1/turn-sample-01/source.json'
    source = json.loads(saved.read_text())
    baseline, _ = study.load_baseline(cfg.baseline)
    row = next(r for r in baseline['schedule'] if r['jev_actor'] == source['actor'] and
               baseline['teams'][r['teams'][int(source['actor'][-1]) - 1]]['showdown_team'] == source['own_team'])
    adapter = input_adapter.Adapter(json.loads((DEFAULT_BUILD / 'dex.json').read_text()))
    try:
        payload, commands, input_audit = adapter.generate(
            source['official'], source['prefix'], source['own_team'], actor=source['actor'])
    finally:
        adapter.close()
    assert input_audit['public_facts']['actor'] == source['actor']
    decision, user = source['decision'], source['decision'].split('-')[0]
    wire_events, identity = transport_events(payload, cfg)
    choice = 'outside-candidates' if illegal else next(iter(commands))
    response = wire_events[-1]['body']
    response['answers']['action']['choice'] = choice
    response['metadata'] = dict(revision=cfg.revision, serving_identity=identity, format=cfg.format_version,
        candidate_ids=list(commands), prompt_sha256=format_request(payload).prompt_sha256)
    wire_events[-2]['raw_body'] = json.dumps(response)
    for event in wire_events:
        event['decision'] = decision
    events = [dict(type='protocol', username=user, sequence=f['event_seq'], protocol=f['protocol'])
              for f in source['prefix']]
    events.append(dict(type='input', decision=decision, payload=payload, commands=commands,
        boundary=source['boundary'], actor=source['actor'], battle='audit-fixture', official=source['official'],
        input_audit=input_adapter.save_audit(tmp_path, decision, input_audit)))
    events.extend(wire_events)
    if illegal:
        events.append(dict(type='battle_output_failure', username=user))
    else:
        rqid = payload['state']['request_id']
        events.extend([dict(type='selection', decision=decision, automatic=False, choice=choice,
            command=commands[choice], revalidated_request_id=rqid, latest_request_id=rqid,
            revalidated_commands=commands),
            dict(type='wire', decision=decision, command=commands[choice], request_id=rqid, status='sent')])
    for number, event in enumerate(events, 1):
        event['event_seq'] = number
    outcome = dict(row, username=user, completed=False, requests=1,
        failure_scope='battle' if illegal else 'collection',
        error=dict(type='UnusableChoice' if illegal else 'RuntimeError', detail='CPU fixture stop'))
    manifest = dict(baseline, experiment_id=experiment, execution_profile=cfg.execution_profile,
        schema_version=cfg.input_version, prompt=input_adapter.PROMPT.read_text(),
        input_data_identity=input_adapter.data_identity(),
        model=dict(model=cfg.model_id, revision=cfg.revision, serving_identity=identity,
                   endpoint=cfg.endpoint + '/v1/systemone'),
        server_journal='fixture', transport_policy=battle.TRANSPORT_POLICY,
        provider_retries=3, retry_delays_seconds=list(battle.RETRY_DELAYS),
        limits=dict(collection_seconds=None, total_seconds=None, stage_seconds=None, battle_seconds=None,
            request_timeout_seconds=600, input_tokens=32768, options=16, concurrency=1, inference_concurrency=1))
    study.write_json(tmp_path / 'manifest.json', manifest)
    monkeypatch.setattr(audit, 'audit_registry', lambda *_a, **kw: dict(passed=kw['protocol'] == client.PROTOCOL))
    checked = audit.audit(tmp_path, checkpoint=True, events=events, result=dict(outcomes=[outcome]))
    assert checked['passed'], checked['errors']
    assert checked['audit_scope'] == 'new_match_once' and checked['inputs'] == 1
    assert checked['wires'] == (0 if illegal else 1)
    assert bool(checked['rejected_responses']) is illegal
    if experiment == 'EX-090':
        assert checked['damage_predictions_enabled'] is False
        assert checked['speed_comparison_retained'] is True
        assert checked['calculator_calls'] == input_audit['calculator_calls']
        assert checked['calculator_calls']['outgoing'] == checked['calculator_calls']['incoming'] == 0
    if cfg.model_id == 'autotrust/JEV-9B':
        wrong_format = copy.deepcopy(events)
        next(event for event in wrong_format if event['type'] == 'response')['body']['metadata']['format'] = (
            config.experiment('EX-088').format_version)
        failed = audit.audit(tmp_path, checkpoint=True, events=wrong_format, result=dict(outcomes=[outcome]))
        assert not failed['passed'] and 'formatter differs' in failed['errors'][0]['detail']
    # A changed command is a shared integrity defect, even if the choice ID exists.
    changed = copy.deepcopy(events)
    next(event for event in changed if event['type'] == 'input')['commands'][next(iter(commands))] = '/choose default'
    rejected = audit.audit(tmp_path, checkpoint=True, events=changed, result=dict(outcomes=[outcome]))
    assert not rejected['passed']
    assert 'regeneration mismatch' in rejected['errors'][0]['detail']


def test_final_check_uses_sealed_match_receipts_without_observation_reaudits(tmp_path, monkeypatch):
    cfg = config.experiment('EX-088')
    baseline, _ = study.load_baseline()
    row = baseline['schedule'][0]
    outcome = dict(row, slot=1, username='fixture', completed=False, audit_passed=True,
        error=dict(type='ModelFailure', detail='server stopped'), requests=0)
    events = [dict(type='protocol', username='fixture', sequence=1, protocol='|init|battle', event_seq=1)]
    session = SimpleNamespace(records=events, calls=0, started=None, monotonic_started=None)
    result = study.summarize(session, [outcome], baseline['schedule'],
        error=dict(type='ModelFailure', detail='server stopped', scope='model'), config=cfg)
    attempt = tmp_path / 'battle-1'
    attempt.mkdir()
    study.write_json(tmp_path / 'manifest.json', dict(experiment_id=cfg.experiment,
        schedule=baseline['schedule'], teams=baseline['teams']))
    study.write_json(tmp_path / 'result.json', result)
    study.write_json(attempt / 'outcome.json', outcome)
    study.write_json(attempt / 'audit.json', dict(passed=True, audit_scope='new_match_once',
        slot_id=row['slot_id'], outcome_sha256=audit.outcome_digest(outcome), event_range=[1, 1],
        events_sha256=j.digest(events), inputs=0, wires=0, physical_attempts=0, logical_requests=0))
    study.write_json(tmp_path / 'ledger.json', dict(requests=0, logical_requests=0, limit=None, deadline=None))
    (tmp_path / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    monkeypatch.setattr(audit, 'audit', lambda *_a, **_k: pytest.fail('observations must not be audited twice'))
    receipt = audit.final_check(tmp_path, result)
    assert receipt['passed'], receipt['errors']
    assert receipt['match_audits_checked'] == 1 and receipt['observation_reaudits'] == 0
    events[0]['protocol'] = '|init|changed'
    (tmp_path / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    changed = audit.final_check(tmp_path, result)
    assert not changed['passed'] and 'audited events changed' in changed['errors'][0]['detail']
