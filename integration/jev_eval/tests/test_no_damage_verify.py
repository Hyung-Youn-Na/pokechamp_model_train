"""Independent treatment oracle, calculator observation and archived cutoff checks."""
import copy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from integration.jev_eval import no_damage_verify as verify
from integration.jev_eval.config import experiment
from integration.jev_eval.storage import file_hash, write


def old_payload():
    damage = dict(target_side='opponent', target_slot=1, target_species='Mew',
                  unit='percent_of_target_max_hp', ranges={'current': [0, 0], 'self_tera': None},
                  reason={'self_tera': 'unsupported'})
    return dict(state=dict(version='jev-choice-v6', decision_kind='turn_action',
        self_team=[dict(active=True, current_move_slots=[
            dict(id='flamethrower', power=90, general_effect='Inflicts damage.', damage=damage)])],
        opponent_team=[dict(active=True, moves=[dict(id='tackle', damage=damage)]),
                       dict(active=False, moves=[dict(id='mimic')], item={'knowledge': 'unknown'})],
        speed_comparison={'status': 'available', 'self_speed_relation': ['faster']},
        type_matchups={'multipliers': [[1, 0.5]]}, recent_completed_turn_log=['Actual damage event']),
        questions={'action': dict(instructions=('Choose one.\n\n' + verify.DAMAGE_EXPLANATION
            + 'Base type/category/power/accuracy/priority describe Dex metadata.\n'
            + 'Damage depends on more than base power.\n' + verify.ACTIVE_SCOPE),
            criteria={'move_1': {'kind': 'move', 'slot': 1}, 'switch_2': {'kind': 'switch', 'slot': 2}})})


def test_independent_oracle_removes_only_explicit_prediction_fields_and_prompt_text():
    original = old_payload()
    preserved = copy.deepcopy(original)
    expected, removed = verify.expected_payload(original)
    assert original == preserved
    assert len(removed) == 2
    assert all(row['path'].endswith('.damage') for row in removed)
    assert expected['state']['version'] == 'jev-choice-v6-no-damage'
    move = expected['state']['self_team'][0]['current_move_slots'][0]
    assert move == dict(id='flamethrower', power=90, general_effect='Inflicts damage.')
    for key in ('speed_comparison', 'type_matchups', 'recent_completed_turn_log'):
        assert expected['state'][key] == original['state'][key]
    assert expected['state']['opponent_team'][1] == original['state']['opponent_team'][1]
    instructions = expected['questions']['action']['instructions']
    assert 'Damage ranges' not in instructions and 'self_tera/opponent_tera' not in instructions
    assert 'Base type/category/power/accuracy/priority' in instructions
    assert 'Damage depends on more than base power.' in instructions
    assert 'Speed calculations still concern the current active matchup only.' in instructions
    assert expected['questions']['action']['criteria'] == original['questions']['action']['criteria']
    malformed = copy.deepcopy(original)
    malformed['questions']['action']['instructions'] += verify.DAMAGE_EXPLANATION
    with pytest.raises(ValueError, match='whitelist'):
        verify.expected_payload(malformed)


@pytest.mark.parametrize('kind', ['lead', 'forced_switch'])
def test_oracle_cannot_hide_new_damage_fields_outside_normal_active_moves(kind):
    original = old_payload()
    original['state']['decision_kind'] = kind
    expected, removed = verify.expected_payload(original)
    assert removed == []
    assert expected['state']['self_team'][0] == original['state']['self_team'][0]
    extra = copy.deepcopy(expected)
    extra['state']['opponent_team'][1]['moves'][0]['damage'] = {'ranges': {'current': [1, 2]}}
    assert 'keys differ' in verify.differences(expected, extra)


@pytest.mark.parametrize('scenario', [
    {'scenario_id': 'outgoing/tackle/current', 'move': 'tackle'},
    {'scenario_id': 'incoming/tackle/current', 'move': 'tackle'},
    {'scenario_id': 'mystery', 'move': 'splash'},
    {'scenario_id': 'speed/candidate/hp100', 'move': 'tackle'},
])
def test_independent_calculator_spy_rejects_damage_even_when_disguised(scenario):
    calls = verify.SpeedCalls()
    with pytest.raises(ValueError, match='non-Speed'):
        calls.record([scenario])
    assert sum(calls.counts.values()) == 1
    assert calls.scenarios == []


def fake_adapter(original, *, mutate=None, change_commands=False, damage_builder=False):
    from integration.pokechamp import jev_battle
    result, _ = verify.expected_payload(original)
    scenario = {'scenario_id': 'speed/set-1/hp100', 'move': 'splash'}
    commands = {'move_1': '/choose move 1', 'switch_2': '/choose switch 2'}
    adapter = SimpleNamespace(engine=SimpleNamespace(calculate=lambda _scenario: {'speed': 100}))

    def generate(*_args, **_kwargs):
        if damage_builder:
            from integration.pokechamp.diagnostics import jev_offline
            jev_offline.damage_transform()
        reply = adapter.engine.calculate(scenario)
        if mutate:
            mutate(result)
        audit = dict(damage_predictions_enabled=False,
            damage=dict(damage_predictions_enabled=False, disabled_reason='input_profile_no_damage',
                        calculations=[]), speed=[dict(scenario=scenario, result=reply)],
            calculator_calls=dict(speed=1, outgoing=0, incoming=0),
            live_result_sha256=jev_battle.digest(result))
        current = dict(reversed(list(commands.items()))) if change_commands else commands
        return result, current, audit

    adapter.generate = generate
    return adapter, dict(decision='actor-1', event_seq=10, actor='p1', official={},
                         boundary={'protocol_event_seq': 9, 'line_index': 1},
                         payload=original, commands=commands)


def test_actual_generation_is_compared_to_archived_oracle_and_calls_are_observed():
    adapter, event = fake_adapter(old_payload())
    receipt, removed = verify.verify_one(event, [], 'own-team', adapter)
    assert receipt['expected_payload_sha256'] == receipt['actual_payload_sha256']
    assert receipt['engine_calls'] == dict(speed=1, outgoing=0, incoming=0, other=0)
    # This synthetic engine never delegates to the real calculator worker.
    assert receipt['worker_calls'] == dict(speed=0, outgoing=0, incoming=0, other=0)
    assert len(removed) == 2


@pytest.mark.parametrize('change', ['power', 'speed', 'candidate_order', 'command_order', 'builder'])
def test_gate_rejects_unapproved_value_order_and_generate_then_hide_changes(change):
    def mutate(payload):
        if change == 'power':
            payload['state']['self_team'][0]['current_move_slots'][0]['power'] = 0
        elif change == 'speed':
            payload['state']['speed_comparison']['self_speed_relation'] = ['slower']
        elif change == 'candidate_order':
            action = payload['questions']['action']
            action['criteria'] = dict(reversed(list(action['criteria'].items())))
    adapter, event = fake_adapter(old_payload(), mutate=mutate,
        change_commands=change == 'command_order', damage_builder=change == 'builder')
    with pytest.raises(ValueError, match='differs|unexpected input|scenario builder'):
        verify.verify_one(event, [], 'own-team', adapter)


def test_all_input_stream_uses_exact_actor_cutoff_and_own_team(tmp_path):
    manifest = dict(teams={'own': {'showdown_team': 'allowed-own'},
                           'foreign': {'showdown_team': 'secret-other-team'}})
    result = dict(outcomes=[dict(username='model', jev_actor='p2', teams=['foreign', 'own'],
                                 slot_id='slot-1')])
    event = dict(type='input', decision='model-1', actor='p2', official={'consumed': 2},
                 boundary=dict(protocol_event_seq=5, line_index=1))
    rows = [dict(type='protocol', username='other', sequence=1, protocol='|request|secret'),
            dict(type='protocol', username='model', sequence=5,
                 protocol='>battle-a\n|turn|2\n|-item|p1a: A|Future Item'), event,
            dict(type='protocol', username='model', sequence=6, protocol='|win|future')]
    (tmp_path / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    cases = list(verify.archived_inputs(tmp_path, manifest, result))
    assert len(cases) == 1
    assert cases[0][1] == [{'event_seq': 5, 'protocol': '>battle-a\n|turn|2'}]
    assert cases[0][2:] == ('allowed-own', 'slot-1')
    assert 'secret' not in json.dumps(cases) and 'Future' not in json.dumps(cases)
    rows.append(event)
    (tmp_path / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    with pytest.raises(ValueError, match='unique scheduled actor'):
        list(verify.archived_inputs(tmp_path, manifest, result))


def test_receipt_reuse_requires_all_inputs_sources_data_and_zero_damage(tmp_path, monkeypatch):
    from integration.pokechamp import jev_v6_no_damage
    cfg = replace(experiment('EX-090'), run=tmp_path / 'new')
    baseline = tmp_path / 'EX-089/collection'
    baseline.mkdir(parents=True)
    for name in ('manifest.json', 'result.json', 'checksums.sha256'):
        (baseline / name).write_text('{}')
    monkeypatch.setattr(verify, 'RUNS', tmp_path)
    monkeypatch.setattr(jev_v6_no_damage, 'data_identity', lambda: {'fixture': 'identity'})
    cfg.evidence.mkdir(parents=True)
    (cfg.evidence / verify.DETAILS).write_text('observed input receipts\n')
    receipt = dict(passed=True, experiment_id='EX-090', checked_inputs=1139,
        source={'input.py': 'original'}, input_data_identity={'fixture': 'identity'},
        details_sha256=file_hash(cfg.evidence / verify.DETAILS),
        baseline=dict(directory=str(baseline), seal_sha256=file_hash(baseline / 'checksums.sha256'),
            files={name: file_hash(baseline / name) for name in ('manifest.json', 'result.json')}),
        calculator_calls={name: dict(speed=100, outgoing=0, incoming=0, other=0)
                          for name in ('engine', 'worker')})
    write(cfg.evidence / verify.RECEIPT, receipt)
    assert verify.validate_receipt(cfg, receipt['source']) == receipt
    with pytest.raises(ValueError, match='stale'):
        verify.validate_receipt(cfg, {'input.py': 'changed'})
    receipt['calculator_calls']['worker']['outgoing'] = 1
    write(cfg.evidence / verify.RECEIPT, receipt, immutable=False)
    with pytest.raises(ValueError, match='non-Speed'):
        verify.validate_receipt(cfg, receipt['source'])
