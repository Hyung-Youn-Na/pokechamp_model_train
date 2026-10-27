"""EX-130 v4 renderer: v2 identity without v4 modules, known-failure markers, switch-in offense (`out`)."""
import itertools
import json

import pytest

from integration.laya_imitation import compact_v2, compact_v4, features, features_v4
from integration.laya_imitation import config as c
from integration.pokechamp.imitation.schema import ImitationInput

EX122 = c.SHARED / 'runs/model-training/EX-122/games'


def values(n=40):
    with open(c.EX071_PREPARED / 'validation.jsonl') as f:
        return [ImitationInput.from_body(json.loads(line)['input']) for line in itertools.islice(f, n)]


class StubCalc:
    def run(self, requests):
        return [dict(min=10.0 + i, max=20.0 + i) for i, _ in enumerate(requests)]


def battle_input(slot, turn):
    """The model input of `slot` at `turn` in EX-122 (live serving body)."""
    for line in open(EX122 / slot / 'events.jsonl'):
        e = json.loads(line)
        if e['type'] == 'input' and json.loads(e['body']['state'])['snapshot']['turn'] == turn:
            return e['body']
    raise LookupError((slot, turn))


def with_spikes(body, layers):
    state = json.loads(body['state'])
    state['snapshot']['opponent_side_conditions'] = dict(state['snapshot']['opponent_side_conditions'], spikes=layers)
    return ImitationInput.from_body(dict(body, state=json.dumps(state)))


needs_ex122 = pytest.mark.skipif(not EX122.exists(), reason='EX-122 games are not mounted')


def test_without_v4_modules_is_exactly_v2():
    calc = StubCalc()
    for v in values():
        facts = features_v4.compute(v, calc)
        assert compact_v4.render(v, compact_v2.MODULES, facts) == compact_v2.render(v, compact_v2.MODULES, facts)
        assert compact_v4.render(v) == compact_v2.render(v)


def test_version_name_and_unknown_module():
    assert compact_v4.version_name(['out', 'damage', 'fails']) == 'laya-compact-v4[damage,fails,out]'
    version = compact_v4.version(compact_v4.MODULES)
    assert version['out_format'] == compact_v4.OUT_FORMAT and len(version['effect_rules_sha256']) == 64
    with pytest.raises(ValueError):
        compact_v4.normalize(['fails', 'nope'])


def test_all_modules_render_and_are_deterministic():
    calc = StubCalc()
    for v in values():
        a = compact_v4.render(v, compact_v4.MODULES, features_v4.compute(v, calc))
        b = compact_v4.render(v, compact_v4.MODULES, features_v4.compute(v, calc))
        assert a == b and a[0] == compact_v2.render(v, compact_v2.MODULES, features_v4.compute(v, calc))[0]
        assert list(a[1]['criteria']) == list(v.action_ids)


def test_markers_only_append():
    v = values(1)[0]
    facts = features_v4.compute(v, StubCalc())
    move = next(a for a in v.action_ids if a.startswith('move:'))
    switch = next(a for a in v.action_ids if a.startswith('switch:'))
    facts['v4'] = dict(fails={move: 'immune'}, out={switch: dict(move='surf', min=40.2, max=47.6)})
    base = compact_v2.render(v, compact_v2.MODULES, facts)[1]['criteria']
    got = compact_v4.render(v, compact_v4.MODULES, facts)[1]['criteria']
    assert got[move] == base[move] + '; fails'
    assert got[switch] == base[switch] + ('; out 48%' if compact_v4.OUT_FORMAT == 'max' else '; out 40-48%')
    assert compact_v4.render(v, compact_v4.MODULES, facts, out_format='range')[1]['criteria'][switch].endswith(
        '; out 40-48%')
    facts['v4'] = dict(fails={move: 'reflected'}, out={switch: dict(error='calc')})
    got = compact_v4.render(v, compact_v4.MODULES, facts)[1]['criteria']
    assert got[move] == base[move] + '; bounced' and got[switch] == base[switch]


def test_tera_typed_moves_keep_the_tera_option(monkeypatch):
    v = values(1)[0]
    monkeypatch.setattr(features_v4, 'option_outcomes', lambda record: {
        'move:terablast:normal': 'immune', 'move:terablast:tera': 'immune', 'move:spikes:tera': 'fails'})
    assert features_v4.known_failures(v) == {'move:terablast:normal': 'immune', 'move:spikes:tera': 'fails'}


@needs_ex122
def test_spikes_fail_only_at_three_layers():
    body = battle_input('v2-m23-s2-a', 13)
    assert features_v4.known_failures(with_spikes(body, 3))['move:spikes:normal'] == 'fails'
    assert 'move:spikes:normal' not in features_v4.known_failures(with_spikes(body, 2))


@needs_ex122
def test_ex122_cases_render_the_missing_answers():
    """EX-122 loops (m23 turn 13, m27 turn 10, m29-s1-b turn 6): Spikes fails, and the counters' damage shows."""
    expect = {('v2-m23-s2-a', 13): ('latios', 103), ('v2-m27-s2-a', 10): ('kyurem', 158),
              ('v2-m29-s1-b', 6): ('irontreads', 85)}
    with features.Calc() as calc:
        for (slot, turn), (species, top) in expect.items():
            v = ImitationInput.from_body(battle_input(slot, turn))
            _, question = compact_v4.render(v, compact_v4.MODULES, features_v4.compute(v, calc))
            criteria = question['criteria']
            assert criteria['move:spikes:normal'].endswith('; fails')
            line = next(t for a, t in criteria.items() if a.startswith('switch:') and t.startswith(species))
            assert line.endswith('; out %d%%' % top if compact_v4.OUT_FORMAT == 'max' else '%d%%' % top)
