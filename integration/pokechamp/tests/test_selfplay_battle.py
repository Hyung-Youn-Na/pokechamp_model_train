"""Synthetic EX-072 action/terminal/HTTP checks; no live match or GPU forward."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import random
import time
from types import SimpleNamespace
import urllib.error

import pytest

from integration.pokechamp.imitation import player as old_player, schema
from integration.pokechamp.selfplay import battle, player
from integration.pokechamp.selfplay.storage import atomic, jsonl, write_jsonl
from integration.pokechamp.tests.test_imitation_battle import (
    choice, fixture_player, http_server, official, request, snapshot,
)


def answer(value, seed=0, *, model='initial', checkpoint='frozen-checkpoint'):
    ids = list(value.action_ids)
    ps = [.6, .3, .1] if len(ids) == 3 else [1 / len(ids)] * len(ids)
    predictions = [[.1, .2, .7], [.7, .2, .1], [.2, .5, .3]][:len(ids)]
    return dict(model=model, checkpoint_sha256=checkpoint, input_sha256=value.sha256,
                action_ids=ids, probabilities=dict(zip(ids, ps)),
                log_probabilities=dict(zip(ids, map(math.log, ps))),
                wdl_probabilities=dict(zip(ids, predictions)),
                baseline=sum(p * (wdl[0] + .5 * wdl[1]) for p, wdl in zip(ps, predictions)),
                choice=random.Random(seed).choices(ids, weights=ps, k=1)[0], rng_seed=seed)


def validate(response, value, seed=0):
    return player.validate_response(response, value, model='initial',
                                    checkpoint_sha256='frozen-checkpoint', seed=seed)


def test_seeded_non_argmax_choice_is_valid_and_reproducible(choice):
    response = answer(choice)
    assert response['choice'] != max(response['probabilities'], key=response['probabilities'].get)
    chosen, ps = validate(response, choice)
    assert (chosen, ps) == validate(answer(choice), choice)
    assert tuple(ps) == choice.action_ids
    assert response['baseline'] == pytest.approx(.405)
    assert ps[chosen] != response['wdl_probabilities'][chosen][0]
    assert player.sampling_seed(23, 1) != player.sampling_seed(23, 2)
    assert player.sampling_seed(23, 1) == player.sampling_seed(23, 1)


@pytest.mark.parametrize('mutation', [
    'reorder', 'missing_policy', 'missing_logp', 'wrong_logp', 'missing_wdl',
    'unnormalized_wdl', 'nan_wdl', 'baseline', 'rng', 'input', 'choice',
])
def test_full_distribution_and_identity_corruption_is_rejected(choice, mutation):
    response = answer(choice)
    first = choice.action_ids[0]
    if mutation == 'reorder':
        response['action_ids'].reverse()
    elif mutation == 'missing_policy':
        del response['probabilities'][first]
    elif mutation == 'missing_logp':
        del response['log_probabilities'][first]
    elif mutation == 'wrong_logp':
        response['log_probabilities'][first] += .2
    elif mutation == 'missing_wdl':
        del response['wdl_probabilities'][first]
    elif mutation == 'unnormalized_wdl':
        response['wdl_probabilities'][first] = [.7, .3, .2]
    elif mutation == 'nan_wdl':
        response['wdl_probabilities'][first][0] = float('nan')
    elif mutation == 'baseline':
        response['baseline'] = .9
    elif mutation == 'rng':
        response['rng_seed'] += 1
    elif mutation == 'input':
        response['input_sha256'] = 'changed'
    elif mutation == 'choice':
        response['choice'] = first
    with pytest.raises(player.PhaseError):
        validate(response, choice)


@pytest.mark.parametrize('values', [[.9, .9, .9], [float('nan'), .5, .5], [1, 0]])
def test_alternate_head_predictions_are_validated_before_calibration_use(choice, values):
    response = answer(choice)
    response['wdl_probabilities_after'] = copy.deepcopy(response['wdl_probabilities'])
    response['wdl_probabilities_after'][choice.action_ids[0]] = values
    with pytest.raises(player.PhaseError):
        validate(response, choice)


def test_native_player_transmits_sampled_choice_not_argmax(snapshot):
    actor, sent, records, calls = fixture_player(snapshot)

    async def evaluate(value, decision):
        calls.append(value.body_json)
        return validate(answer(value), value)

    actor.session.evaluate = evaluate
    asyncio.run(actor._handle_battle_request(SimpleNamespace(in_team_preview=False, battle_tag='fixture')))
    selected = next(row for row in records if row['type'] == 'selection')
    assert selected['choice'] == 'move:tackle:tera'
    assert sent == [('/choose move 1 terastallize', 'fixture', '1')]
    assert len(calls) == 1


def test_native_singleton_bypasses_model_and_requery(snapshot):
    actor, sent, records, calls = fixture_player(snapshot, singleton=True)
    battle_view = SimpleNamespace(in_team_preview=False, battle_tag='fixture')
    asyncio.run(actor._handle_battle_request(battle_view))
    assert calls == [] and len(sent) == 1
    assert next(row for row in records if row['type'] == 'selection')['automatic'] is True
    with pytest.raises(player.PhaseError, match='requery forbidden'):
        asyncio.run(actor._handle_battle_request(battle_view))
    assert len(sent) == 1


def test_session_preserves_exact_http_rng_and_response_bytes(tmp_path, choice, http_server):
    seed = player.sampling_seed(23, 1)
    response = answer(choice, seed)
    http_server.raw = json.dumps(response).encode()
    session = player.Session(tmp_path, model='initial', own_sets=[], seed=23,
        serving=dict(endpoint=http_server.endpoint, checkpoint_sha256='frozen-checkpoint'),
        deadline=time.monotonic() + 10)
    try:
        chosen, ps = asyncio.run(session.evaluate(choice, 'decision'))
        assert chosen == response['choice'] and ps == response['probabilities']
        expected = dict(model='initial', input=choice.body, seed=seed)
        assert http_server.requests == [player.compact(expected).encode()]
        assert [r['type'] for r in session.records] == ['http_request', 'http_response', 'response']
        assert session.records[1]['raw_sha256'] == hashlib.sha256(http_server.raw).hexdigest()
    finally:
        session.close()


@pytest.mark.parametrize('status,error', [(413, old_player.legacy.UnusableChoice),
                                          (422, player.PhaseError), (500, player.PhaseError)])
def test_transport_failures_have_one_attempt_and_no_selection(tmp_path, choice, http_server, status, error):
    http_server.status = status
    session = player.Session(tmp_path, model='initial', own_sets=[], seed=23,
        serving=dict(endpoint=http_server.endpoint, checkpoint_sha256='frozen-checkpoint'),
        deadline=time.monotonic() + 10)
    try:
        with pytest.raises(error):
            asyncio.run(session.evaluate(choice, 'decision'))
        assert len(http_server.requests) == 1
        assert [r['type'] for r in session.records] == ['http_request', 'http_response']
    finally:
        session.close()


def test_malformed_response_bytes_are_recorded_as_battle_local_failure(tmp_path, choice, http_server):
    http_server.raw = b'\xff'
    session = player.Session(tmp_path, model='initial', own_sets=[], seed=23,
        serving=dict(endpoint=http_server.endpoint, checkpoint_sha256='frozen-checkpoint'),
        deadline=time.monotonic() + 10)
    try:
        with pytest.raises(old_player.legacy.UnusableChoice, match='malformed'):
            asyncio.run(session.evaluate(choice, 'decision'))
        assert len(http_server.requests) == 1
        assert [r['type'] for r in session.records] == ['http_request', 'http_response']
        assert session.records[1]['raw_sha256'] == hashlib.sha256(b'\xff').hexdigest()
    finally:
        session.close()


def audit_bundle(directory, snapshot, *, learner='p1', singleton=False, interrupted=False,
                 opponent_model=False, result='win'):
    directory.mkdir()
    row = dict(slot_id='synthetic', stage='train', round=1, model='initial', pair_id='pair1',
               model_side=learner, opponent='snapshot' if opponent_model else 'abyssal',
               teams={side: dict(packed='synthetic-' + side) for side in ('p1', 'p2')},
               simulator_seed=[1, 2, 3, 4], model_seed=23, opponent_seed=47)
    actors = {side: dict(kind='model' if side == learner or opponent_model else 'bot',
                        policy='initial' if side == learner else 'snapshot' if opponent_model else 'abyssal',
                        serving=dict(checkpoint_sha256='frozen-checkpoint' if side == learner else 'opponent-checkpoint'))
              for side in ('p1', 'p2')}
    names = dict(p1='fixture1', p2='fixture2')
    atomic(directory / 'request.json', dict(slot=row, actors=actors, names=names))
    for side in ('p1', 'p2'):
        log = player.EventLog(directory / ('events.jsonl' if side == learner else 'opponent-events.jsonl'))
        log.record(dict(type='team_submission', packed_team=row['teams'][side]['packed']))
        if actors[side]['kind'] == 'model':
            preview = request(preview=True)
            current = request()
            for req in (preview, current):
                req['side']['id'] = side
                for mon in req['side']['pokemon']:
                    mon['ident'] = mon['ident'].replace('p1:', side + ':')
            slots = old_player.FixedSlots()
            slots.observe(preview)
            obs = official(current, wires=['move 1'] if singleton else None)
            actions, commands = old_player.actions_and_commands(obs, slots)
            value = schema.from_snapshot(snapshot, actions)
            log.record(dict(type='input', decision='decision', body=value.body, body_json=value.body_json,
                            input_sha256=value.sha256, snapshot=snapshot, actions=actions,
                            commands=commands, official=obs, slot_map=slots.mapping))
            if not singleton:
                seed = player.sampling_seed(row['model_seed'] if side == learner else row['opponent_seed'], 1)
                envelope = dict(model=actors[side]['policy'], input=value.body, seed=seed)
                log.record(dict(type='http_request', decision='decision', body=envelope,
                                body_json=player.compact(envelope), attempt=1))
            if not interrupted:
                if singleton:
                    chosen, probabilities = value.action_ids[0], None
                else:
                    response = answer(value, seed, model=actors[side]['policy'],
                                      checkpoint=actors[side]['serving']['checkpoint_sha256'])
                    raw = player.compact(response)
                    log.record(dict(type='http_response', decision='decision', status_code=200,
                                    raw_body=raw, raw_sha256=hashlib.sha256(raw.encode()).hexdigest()))
                    log.record(dict(type='response', decision='decision', body=response))
                    chosen, probabilities = response['choice'], response['probabilities']
                log.record(dict(type='revalidation', decision='decision', passed=True, commands=commands,
                                request_id=1, latest_request_id=1, current_request_id=1))
                log.record(dict(type='selection', decision='decision', choice=chosen,
                                command=commands[chosen], automatic=singleton, probabilities=probabilities))
                log.record(dict(type='ps_send', command=commands[chosen], request_id='1'))
                log.record(dict(type='wire', decision='decision', command=commands[chosen], request_id=1, status='sent'))
        if not interrupted:
            winning = learner if result == 'win' else ('p2' if learner == 'p1' else 'p1')
            terminal = '|tie|' if result == 'draw' else '|win|' + names[winning]
            # The submitted action remains a valid choice even if paralysis
            # prevents execution; the auditor must not demand a matching move.
            log.record(dict(type='protocol', protocol='|cant|' + side + 'a: Test|par\n' + terminal))
        log.close()
    write_jsonl(directory / 'battle-seed.jsonl', [dict(seed='1,2,3,4', format='gen9ou')])
    outcome = battle.base_outcome(row, 'incomplete' if interrupted else 'completed')
    outcome['result'] = None if interrupted else result
    return outcome


@pytest.mark.parametrize('learner', ['p1', 'p2'])
@pytest.mark.parametrize('opponent_model', [False, True])
@pytest.mark.parametrize('result', ['win', 'draw', 'loss'])
def test_normal_terminal_and_two_model_audit_use_learner_only(tmp_path, snapshot, learner, opponent_model, result):
    directory = tmp_path / 'match'
    outcome = audit_bundle(directory, snapshot, learner=learner, opponent_model=opponent_model, result=result)
    receipt, records = battle.audit_match(directory, outcome)
    assert receipt['passed'], receipt['errors']
    assert receipt['valid_decisions'] == len(records) == 1
    assert receipt['counts'] == {'inputs': 1, 'wires': 1}
    record = records[0]
    assert record['outcome'] == dict(win='W', draw='D', loss='L')[result]
    assert record['model_version'] == 'frozen-checkpoint'
    assert record['rng_seed'] == player.sampling_seed(23, 1)
    assert len(record['log_probabilities']) == len(record['wdl_probabilities']) == len(record['action_ids'])
    assert record['baseline'] == pytest.approx(.405)


def test_automatic_terminal_decision_is_audited_but_not_trainable(tmp_path, snapshot):
    directory = tmp_path / 'automatic'
    outcome = audit_bundle(directory, snapshot, singleton=True, opponent_model=True)
    receipt, records = battle.audit_match(directory, outcome)
    assert receipt['passed'], receipt['errors']
    assert receipt['counts']['inputs'] == receipt['counts']['wires'] == 1
    assert receipt['valid_decisions'] == 0 and records == []


@pytest.mark.parametrize('status', ['incomplete', 'failed'])
def test_incomplete_or_failed_trajectory_has_no_outcome_targets(tmp_path, snapshot, status):
    directory = tmp_path / 'pending'
    outcome = audit_bundle(directory, snapshot, interrupted=True, opponent_model=True)
    outcome['status'] = status
    receipt, records = battle.audit_match(directory, outcome)
    assert receipt['passed'], receipt['errors']
    assert records == [] and receipt['valid_decisions'] == 0


def test_failed_trajectory_cannot_be_relabelled_as_draw(tmp_path, snapshot):
    directory = tmp_path / 'failed'
    outcome = audit_bundle(directory, snapshot, interrupted=True)
    outcome.update(status='failed', result='draw')
    receipt, records = battle.audit_match(directory, outcome)
    assert not receipt['passed']
    assert records == []


@pytest.mark.parametrize('tamper', ['wire', 'opponent_wire', 'terminal', 'candidate', 'rng', 'missing_http'])
def test_actual_transport_candidate_and_opponent_corruption_invalidates_game(tmp_path, snapshot, tamper):
    directory = tmp_path / 'tampered'
    outcome = audit_bundle(directory, snapshot, opponent_model=True)
    path = directory / ('opponent-events.jsonl' if tamper == 'opponent_wire' else 'events.jsonl')
    rows = list(jsonl(path))
    if tamper in ('wire', 'opponent_wire'):
        next(r for r in rows if r['type'] == 'ps_send')['command'] = '/choose move 2'
    elif tamper == 'terminal':
        next(r for r in rows if r['type'] == 'protocol')['protocol'] = '|tie|'
    elif tamper == 'candidate':
        next(r for r in rows if r['type'] == 'input')['official']['candidates'].reverse()
    elif tamper == 'rng':
        event = next(r for r in rows if r['type'] == 'http_request')
        event['body']['seed'] += 1
        event['body_json'] = player.compact(event['body'])
    elif tamper == 'missing_http':
        rows = [r for r in rows if r['type'] != 'http_request']
    write_jsonl(path, rows)
    receipt, _ = battle.audit_match(directory, outcome)
    assert not receipt['passed']


def test_service_switches_frozen_models_and_restores_seeded_sampling(choice):
    from integration.pokechamp.selfplay.serving import Service

    class Policy:
        def __init__(self):
            self.loads = []
        def load_weights(self, weights):
            self.loads.append(weights)
        def set_stage(self, stage):
            assert stage == 'inference'
        def predict(self, body, *, seed, alternate_head=None):
            assert tuple(body['questions']['action']['criteria']) == choice.action_ids
            return answer(schema.ImitationInput.from_body(body), seed)

    policy = Policy()
    snapshots = {name: dict(weights=name + '-weights', identity=name + '-identity') for name in ('a', 'b')}
    with Service(policy, snapshots, port=0) as service:
        results = [old_player.http_json(service.endpoint, '/evaluate',
                    body=dict(model=model, input=choice.body, seed=0)) for model in ('a', 'b', 'a')]
        assert service.failure is None
    assert policy.loads == ['a-weights', 'b-weights', 'a-weights']
    assert [r['model'] for r in results] == ['a', 'b', 'a']
    assert [r['checkpoint_sha256'] for r in results] == ['a-identity', 'b-identity', 'a-identity']
    assert results[0] == results[2]


@pytest.mark.parametrize('failure', ['overflow', 'model', 'schema'])
def test_service_failure_flags_distinguish_overflow_from_shared_fault(choice, monkeypatch, failure):
    from integration.pokechamp.imitation import model as old_model
    from integration.pokechamp.selfplay.serving import Service

    class Overflow(ValueError):
        pass

    monkeypatch.setattr(old_model, '_kev', lambda: (None, SimpleNamespace(ContextOverflow=Overflow)))

    class Policy:
        def load_weights(self, weights):
            pass
        def set_stage(self, stage):
            pass
        def predict(self, body, **kwargs):
            raise Overflow('synthetic too long') if failure == 'overflow' else RuntimeError('synthetic model fault')

    with Service(Policy(), {'initial': dict(weights={}, identity='frozen-checkpoint')}, port=0) as service:
        payload = dict(model='initial', input=choice.body, seed=0)
        if failure == 'schema':
            payload['unregistered'] = 'forbidden'
        expected = old_player.legacy.UnusableChoice if failure == 'overflow' else player.PhaseError
        with pytest.raises(expected):
            old_player.http_json(service.endpoint, '/evaluate', body=payload)
        assert (service.failure is None) == (failure == 'overflow')


def test_client_disconnect_does_not_become_shared_model_failure(choice, monkeypatch):
    from integration.pokechamp.imitation import model as old_model
    from integration.pokechamp.selfplay.serving import Service

    monkeypatch.setattr(old_model, '_kev', lambda: (None, SimpleNamespace(ContextOverflow=type('Overflow', (Exception,), {}))))

    class Policy:
        def load_weights(self, weights):
            pass
        def set_stage(self, stage):
            pass
        def predict(self, body, *, seed, **kwargs):
            return answer(schema.ImitationInput.from_body(body), seed)

    with Service(Policy(), {'initial': dict(weights={}, identity='frozen-checkpoint')}, port=0) as service:
        handler = service.server.RequestHandlerClass
        original = handler.respond

        def disconnected(self, code, body):
            if code == 200:
                raise BrokenPipeError('synthetic client disconnected after inference')
            return original(self, code, body)

        monkeypatch.setattr(handler, 'respond', disconnected)
        try:
            old_player.http_json(service.endpoint, '/evaluate', body=dict(model='initial', input=choice.body, seed=0))
        except (OSError, player.PhaseError):
            pass
        assert service.failure is None
