"""EX-090 treatment isolation, including boundaries absent from ordinary games."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import jev_v6, jev_v6_no_damage as no_damage
from integration.pokechamp.diagnostics import jev_offline
from integration.pokechamp.diagnostics.jev_damage_verify import synthesize
from integration.pokechamp.diagnostics.jev_speed import SpeedOnlyEngine
from integration.pokechamp.observation.build import DEFAULT_BUILD

FIXTURES = Path(__file__).parent / 'fixtures'
SAVED = Path(__file__).resolve().parents[3] / 'project_context/exec-plans/evidence/ep093/certainty-v1'


@pytest.fixture(scope='module')
def dex():
    return json.loads((DEFAULT_BUILD / 'dex.json').read_text())


def expected_without_damage(payload):
    value = copy.deepcopy(payload)
    for side in ('self_team', 'opponent_team'):
        for mon in value['state'][side]:
            for field in ('moves', 'current_move_slots', 'known_move_set'):
                for move in mon.get(field, []) if isinstance(mon.get(field), list) else []:
                    move.pop('damage', None)
    value['state']['version'] = no_damage.VERSION
    value['questions']['action']['instructions'] = no_damage.PROMPT.read_text()
    return value


def generate(module, case, dex):
    adapter = module.Adapter(dex)
    try:
        return adapter.generate(case['official'], case['prefix'], case['own_team'], actor=case['actor'])
    finally:
        adapter.close()


@pytest.mark.parametrize('name', ['lead-1', 'turn-sample-01', 'forced-switch'])
def test_same_values_and_commands_except_prediction_profile(dex, name, monkeypatch):
    case = json.loads((SAVED / name / 'source.json').read_text())
    before, commands, audit = generate(jev_v6, case, dex)
    assert 'damage_predictions_enabled' not in audit  # Existing profile's audit is unchanged.
    monkeypatch.setattr(jev_offline, 'damage_transform', lambda *a, **k: pytest.fail('damage path executed'))
    after, new_commands, new_audit = generate(no_damage, case, dex)
    assert after == expected_without_damage(before)
    assert list(new_commands.items()) == list(commands.items())
    assert new_audit['damage_predictions_enabled'] is False
    assert new_audit['damage']['calculations'] == []
    assert 'branches' not in new_audit['damage']
    assert new_audit['speed'] == audit['speed']
    assert new_audit['calculator_calls'] == dict(
        speed=sum('scenario' in row for row in new_audit['speed']), outgoing=0, incoming=0)


@pytest.mark.parametrize('rows', [
    ['|move|p2a: Zapdos|Hurricane|p1a: Lokix', '|-item|p2a: Zapdos|Leftovers',
     '|switch|p2a: Hydrapple|Hydrapple, M|100/100', '|turn|2', '|turn|3', '|turn|4', '|turn|5'],
    ['|move|p2a: Zapdos|Mimic|p1a: Lokix', '|-start|p2a: Zapdos|Mimic|Ice Beam'],
    ['|move|p2a: Zapdos|Sketch|p1a: Lokix', '|-activate|p2a: Zapdos|move: Sketch|Ice Beam'],
    ['|move|p1a: Lokix|U-turn|p2a: Zapdos', '|move|p2a: Zapdos|Transform|p1a: Lokix',
     '|-transform|p2a: Zapdos|p1a: Lokix'],
    ['|-terastallize|p1a: Lokix|Bug', '|-terastallize|p2a: Zapdos|Steel'],
    ['|move|p2a: Zapdos|Tackle|p1a: Lokix'],  # No compatible recommended set.
])
def test_public_bench_copy_tera_and_unavailable_keep_non_damage_values(dex, rows, monkeypatch):
    case = synthesize(json.loads((FIXTURES / 'jev-damage-prefix.json').read_text()), rows, dex)
    before, commands, old_audit = generate(jev_v6, case, dex)
    calls = []
    original = jev_offline.Engine.calculate

    def speed_only(engine, scenario):
        calls.append(copy.deepcopy(scenario))
        assert scenario['scenario_id'].startswith('speed/') and scenario['move'] == 'splash'
        return original(engine, scenario)

    monkeypatch.setattr(jev_offline.Engine, 'calculate', speed_only)
    monkeypatch.setattr(jev_offline, 'damage_transform', lambda *a, **k: pytest.fail('damage scenarios generated'))
    after, new_commands, audit = generate(no_damage, case, dex)
    assert after == expected_without_damage(before)
    assert list(new_commands.items()) == list(commands.items())
    assert audit['speed'] == old_audit['speed']
    assert audit['calculator_calls'] == dict(speed=len(calls), outgoing=0, incoming=0)
    for key in ('normalized_active', 'candidates', 'excluded_candidates', 'history', 'field'):
        assert audit['damage'][key] == old_audit['damage'][key]
    assert audit['damage']['calculations'] == [] and 'branches' not in audit['damage']


def test_speed_failure_is_retained_without_damage_reason_fields(dex, monkeypatch):
    case = json.loads((FIXTURES / 'jev-damage-prefix.json').read_text())
    monkeypatch.setattr(jev_offline.Engine, 'calculate', lambda self, scenario:
                        dict(excluded_with_reason='synthetic_speed_unavailable'))
    payload, _, audit = generate(no_damage, case, dex)
    assert payload['state']['speed_comparison']['reason'] == 'synthetic_speed_unavailable'
    assert audit['calculator_calls']['speed'] == 1
    assert '"damage"' not in json.dumps(payload)
    assert '"damage_reason"' not in json.dumps(payload)
    assert '"damage_pct"' not in json.dumps(payload)


@pytest.mark.parametrize('scenario', [
    dict(scenario_id='outgoing/tackle/current', move='tackle'),
    dict(scenario_id='incoming/tackle/current', move='tackle'),
    dict(scenario_id='speed/set/hp100', move='tackle'),
])
def test_speed_guard_rejects_prediction_calls_before_engine(scenario):
    engine = SpeedOnlyEngine(SimpleNamespace(calculate=lambda _: pytest.fail('forbidden call forwarded')))
    with pytest.raises(ValueError, match='non-speed'):
        engine.calculate(scenario)
    assert engine.calls == 0


def test_general_damage_rules_metadata_and_speed_guidance_remain():
    prompt = no_damage.PROMPT.read_text()
    assert 'Damage ranges name' not in prompt and 'both_tera' not in prompt
    assert 'Base type/category/power/accuracy/priority describe Dex metadata' in prompt
    assert 'Damage depends on more than base power.' in prompt
    assert 'speed_comparison concerns effective Speed' in prompt
    assert 'Speed calculations still concern the current active matchup only.' in prompt


def test_live_session_cannot_switch_input_treatment(dex):
    case = json.loads((SAVED / 'lead-1/source.json').read_text())
    session = SimpleNamespace(dex=dex)

    async def run():
        await no_damage.generate(session, case['official'], case['prefix'], case['own_team'], actor=case['actor'])
        with pytest.raises(ValueError, match='treatment changed'):
            await jev_v6.generate(session, case['official'], case['prefix'], case['own_team'], actor=case['actor'])

    try:
        asyncio.run(run())
    finally:
        session.v6_adapter.close()
