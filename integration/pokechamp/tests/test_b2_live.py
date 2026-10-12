"""Real archived inputs through the B2 player/backend, with no provider network."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import ab_head_to_head as h
from integration.pokechamp import benchmark as b
from integration.pokechamp.improved_io import battle_prompts, live_delivery
from integration.pokechamp.improved_io.backend import FixedBackend
from integration.pokechamp.improved_io.player import make_fixed_player
from integration.pokechamp.observability.recorder import BattleBundleConfig, BattleRecorder
from integration.pokechamp.observability.render import _decision_card, _group_decisions


@pytest.fixture
def setup(tmp_path):
    path = Path('/workspace/.pokechamp-data/experiments/ex037-cloud/battles/b01-r1-s0-a1-p2/events.jsonl')
    event = next(e for e in map(json.loads, path.open()) if e['event_type'] == 'llm_call')
    full = json.loads(event['user_prompt'])
    sent = []
    recorder = BattleRecorder.create(tmp_path, BattleBundleConfig(
        experiment_id='unit', battle_id='unit', battle_format='gen9ou',
        teams=[], model={}, source={},
    ))
    for _ in range(full['identity']['decision_seq']):
        recorder.begin_decision(showdown_turn=1, decision_kind='turn_action', battle_state={})
    raw = dict(model='glm-5.3-flash', message=dict(content='reason\n' + json.dumps(full['request']['legal_actions'][0])), done=True, done_reason='stop')
    backend = FixedBackend(
        environ={'OLLAMA_API_KEY': 'offline-provider-key-fixture'}, trace_sink=recorder,
        client_factory=lambda **kw: SimpleNamespace(chat=lambda **kw: sent.append(kw) or raw),
    )
    backend.experiment_policy = h.policy_selection(h.B2)
    backend.runtime_identity = h.runtime_identity()
    backend.io_profile = 'io-battle-only-v1'
    backend.battle_prompt_identity = battle_prompts.identity('v1.2.0')
    backend.input_context = full
    backend.delivery = live_delivery.build(full)
    return full, backend, recorder, sent


def call(backend):
    return backend.get_LLM_action(backend.delivery.system_prompt, backend.delivery.user_json,
                                  'glm-5.3-flash', temperature=0, json_format=False)


def test_player_backend_actual_wire_original_output_and_trace(setup):
    full, backend, recorder, sent = setup
    cls = make_fixed_player(object)
    actor = SimpleNamespace(io_profile=backend.io_profile, llm=backend,
                            io_battle_prompt_identity=backend.battle_prompt_identity,
                            io_summary_prompt_identity=None, temperature=0)
    cls._call_fixed(actor, 'self_action', full, 'replaced legacy prompt', None)
    assert backend.input_context is full
    assert backend.parsed_action.action == full['request']['legal_actions'][0]
    assert sent[0]['messages'] == [dict(role='system', content=backend.delivery.system_prompt),
                                   dict(role='user', content=backend.delivery.user_json)]
    assert 'condition_id' not in json.loads(sent[0]['messages'][1]['content'])
    events = list(map(json.loads, (recorder.bundle_path / 'events.jsonl').read_text().splitlines()))
    snapshots = {e['event_seq']: e for e in events if e['event_type'] == 'input_snapshot'}
    event = next(e for e in events if e['event_type'] == 'llm_call')
    assert live_delivery.original_for_call(event, snapshots) == full
    assert event['request']['identity']['input_version'] == 'calculator-input-v2'
    decisions, _ = _group_decisions(events)
    card = _decision_card(decisions[-1])
    assert '검증용 원본 입력' in card and 'Effective user prompt' in card
    broken = copy.deepcopy(event)
    broken['decision_seq'] += 1
    with pytest.raises(ValueError, match='linkage'):
        live_delivery.original_for_call(broken, snapshots)


@pytest.mark.parametrize('change', ['system', 'user', 'version', 'original', 'missing_recorder', 'wrong_policy'])
def test_tampering_rejected_before_provider(setup, change):
    full, backend, recorder, sent = setup
    if change == 'system':
        backend.delivery = replace(backend.delivery, system_prompt=backend.delivery.system_prompt + ' ')
    elif change == 'user':
        backend.delivery = replace(backend.delivery, user_json=backend.delivery.user_json + ' ')
    elif change == 'version':
        backend.delivery = replace(backend.delivery, calculator_semantics_version='wrong')
    elif change == 'original':
        full['identity']['state_hash'] = 'wrong'
    elif change == 'missing_recorder':
        backend.trace_sink = None
    else:
        backend.experiment_policy = h.policy_selection(h.PROTECTFIX)
    with pytest.raises((ValueError, KeyError)):
        call(backend)
    assert sent == []


def test_snapshot_failure_blocks_network(setup, monkeypatch):
    _, backend, recorder, sent = setup
    monkeypatch.setattr(recorder, 'record_input_snapshot', lambda **kw: None)
    with pytest.raises(ValueError, match='persisted'):
        call(backend)
    assert sent == []


def test_b2_preparation_copies_ex037_and_requires_current_code_receipt(tmp_path):
    root = tmp_path / 'prepared'
    prepared = h.prepare(root, transport='fake', policy=h.B2)
    old = b.read_sealed(h.B2_PREVIOUS / 'plan.json')
    assert prepared['schedule'] == old['schedule'] and prepared['teams'] == old['teams']
    assert prepared['experiment_id'] == 'ex038-fake'
    assert prepared['execution']['battle_concurrency'] == 8
    assert h.verify_prepared(root) == prepared
    assert h.protocol_for(root).continuous_submission
    assert str(h.protocol_for(root).STUDY_LINK).endswith('ex038-study-link.json')
    with pytest.raises(ValueError, match='receipt'):
        h.verify_entry(root, None)
    receipt = tmp_path / 'checks.json'
    b.seal_json(receipt, dict(source_files=prepared['parent_files'], local_passed=True,
                            wire_passed=True, experiment_policy=h.B2, skipped_checks=h.B2_SKIPPED))
    h.verify_entry(root, receipt)
    assert h.B2_POLICY['call_limit'] == 8000
    assert h.B2_POLICY['first_batch'] is None
    assert 'local_regression' not in h.B2_SKIPPED
    (root / 'teams/1.txt').write_text('tampered')
    with pytest.raises(ValueError, match='team drift'):
        h.verify_prepared(root)


def test_continuous_coordinator_has_no_first10_barrier_or_replacement(tmp_path, monkeypatch):
    from integration.pokechamp import a_diagnostic as shared

    root = tmp_path / 'study'
    root.mkdir()
    b.seal_json(root / 'plan.json', dict(experiment_policy=h.B2))
    value = dict(transport='fake', schedule=h.schedule()[:11], parent_files={},
                 execution=h.execution('fake', h.B2))
    monkeypatch.setattr(h, 'verify_prepared', lambda *a, **kw: value)
    monkeypatch.setattr(h, 'verify_entry', lambda *a: None)
    monkeypatch.setattr(shared, 'check_ports', lambda *a: None)
    monkeypatch.setattr(b.cli, 'ARTIFACT_ROOT', tmp_path / 'artifacts')
    calls = []

    def attempt(data, study, plan, slot, number, **kw):
        assert number == 1
        calls.append(slot['slot_id'])
        return dict(slot_id=slot['slot_id'], category='timeout' if len(calls) == 1 else None)

    monkeypatch.setattr(b, 'run_attempt', attempt)
    monkeypatch.setattr(h, 'inspect_batch', lambda *a: pytest.fail('unexpected first10 gate'))
    monkeypatch.setattr(h, 'report', lambda *a: dict(attempted=len(calls)))
    assert h.run(root, tmp_path / 'data')['attempted'] == 11
    assert len(set(calls)) == 11
    assert not (root / 'first10-check.json').exists()
    with pytest.raises(FileExistsError):
        h.run(root, tmp_path / 'data')
