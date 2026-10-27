"""EX-136 v5 renderer (D-195): v4 identity, opponent item states, Air Balloon handling, status/turn counters."""
import itertools
import json
from pathlib import Path

import pytest

from integration.laya_imitation import compact, compact_v4, compact_v5, features, features_v4, features_v5, item_state
from integration.laya_imitation import config as c
from integration.pokechamp.imitation.schema import ImitationInput

CASES = json.loads((Path(__file__).with_name('d195_cases.json')).read_text())['cases']


class StubCalc:
    def run(self, requests):
        return [dict(min=10.0 + i, max=20.0 + i) for i, _ in enumerate(requests)]


def case(name):
    return ImitationInput.from_body(CASES[name])


def render(name, calc):
    value = case(name)
    facts = features_v5.compute(value, calc)
    return compact_v5.render(value, compact_v5.MODULES, facts), facts


def line(state, prefix):
    return next(x for x in state.split('\n') if x.startswith(prefix))


needs_store = pytest.mark.skipif(not (c.ITEM_STATE / 'validation.jsonl').exists(), reason='item-state store missing')


@pytest.fixture(scope='module')
def calc():
    with features.Calc() as worker:
        yield worker


def test_without_v5_modules_the_text_is_v4():
    for name in CASES:
        value = case(name)
        facts = features_v5.compute(value, StubCalc())
        for modules in ((), ('damage',), compact_v4.MODULES):
            assert compact_v5.render(value, modules, facts) == compact_v4.render(value, modules, facts)


@needs_store
def test_new_snapshot_fields_leave_v1_to_v4_text_unchanged():
    rows = zip(itertools.islice(open(c.EX071_PREPARED / 'validation.jsonl'), 40), item_state.load('validation'))
    for line_, extra in rows:
        record = json.loads(line_)
        assert extra['sample_id'] == record['sample_id']
        old = ImitationInput.from_body(record['input'])
        new = ImitationInput.from_body(item_state.merge(record['input'], extra))
        assert compact.render(new) == compact.render(old)
        assert compact_v4.render(new, compact_v4.MODULES, features_v4.compute(new, StubCalc())) == \
            compact_v4.render(old, compact_v4.MODULES, features_v4.compute(old, StubCalc()))


def test_v5_refuses_inputs_without_parser_fields():
    with open(c.EX071_PREPARED / 'validation.jsonl') as f:
        value = ImitationInput.from_body(json.loads(next(f))['input'])
    with pytest.raises(ValueError):
        features_v5.compute(value, StubCalc())


def test_popped_balloon_is_no_item_and_ground_damage_returns(calc):
    # NHJ game 23 turn 13: Knock Off popped Gholdengo's balloon at turn 10; v2-v4 still showed `dmg 0-0%`.
    (state, question), facts = render('nhj23_t13', calc)
    assert 'item none (popped)' in line(state, 'OPP gholdengo')
    assert facts['v5']['recomputed']
    text = question['criteria']['move:earthpower:normal']
    assert text.startswith('ground special 90 x2;') and 'dmg 0-0%' not in text and 'fails' not in text
    old_text = compact_v4.render(case('nhj23_t13'), compact_v4.MODULES, features_v4.compute(case('nhj23_t13'), calc))
    assert 'dmg 0-0%' in old_text[1]['criteria']['move:earthpower:normal']


def test_held_balloon_shows_ground_as_x0(calc):
    for name, moves in (('nhj23_t4', ['move:earthquake:normal']),
                        ('nhj25_t10', ['move:earthquake:normal', 'move:headlongrush:normal'])):
        (state, question), facts = render(name, calc)
        assert 'item airballoon' in line(state, 'OPP gholdengo')
        for move in moves:
            assert ' x0 ' in question['criteria'][move] and question['criteria'][move].endswith('; fails')
            assert move in facts['v5']['grounded_x0']
        assert 'balloon?' not in json.dumps(question)


def test_knocked_off_and_effect_revealed_items(calc):
    (state, _), _ = render('nhj25_t10', calc)
    assert 'kingambit [dark steel] 79% | ability ? | item none (knocked off leftovers)' in line(state, 'opp team:')
    (state, question), _ = render('nhj26_t44', calc)
    # Leftovers was only ever revealed by its end-of-turn heal: the legacy field kept it hidden.
    assert json.loads(CASES['nhj26_t44']['state'])['snapshot']['opponent_team'][3]['item'] is None
    assert '| item leftovers |' in line(state, 'OPP kingambit')
    assert '(target item)' in question['criteria']['move:knockoff:normal']


def test_unknown_item_never_assumes_air_balloon(calc):
    body = json.loads(json.dumps(CASES['nhj23_t4']))
    state = json.loads(body['state'])
    foe = state['snapshot']['opponent_team'][state['snapshot']['opponent_active_slot'] - 1]
    foe.update(item=None, item_state=dict(state='unknown', item=None, cause=None))
    body['state'] = json.dumps(state)
    value = ImitationInput.from_body(body)
    facts = features_v5.compute(value, calc)
    text = compact_v5.render(value, compact_v5.MODULES, facts)[1]['criteria']['move:earthquake:normal']
    assert facts['v5']['balloon'] == ['move:earthquake:normal', 'move:earthquake:tera']
    assert ' x2 ' in text and 'dmg 0-0%' not in text and text.endswith('; balloon?')


def test_status_and_turn_counters(calc):
    (state, _), _ = render('ex131_t9', calc)
    assert line(state, 'OPP ').startswith('OPP cinderace [fire] 68% tox t2 |')
    (state, _), _ = render('ex131_t106', calc)
    assert line(state, 'OPP ').startswith('OPP dondozo [water] 94% slp t1 rest |')
    assert state.split('\n')[0].endswith('| weather none | field grassy_terrain t2')
    (state, _), _ = render('nhj25_t10', calc)
    assert state.split('\n')[0].endswith('| field grassy_terrain t4')


def test_counters_formatting_is_local():
    value = case('ex131_t106')
    snapshot = json.loads(CASES['ex131_t106']['state'])['snapshot']
    snapshot.update(weather='sunnyday', weather_turn=snapshot['turn'] - 3,
                    own_side_conditions=dict(reflect=snapshot['turn'] - 1, spikes=2))
    value = ImitationInput.from_body(dict(CASES['ex131_t106'], state=json.dumps(dict(version=json.loads(
        CASES['ex131_t106']['state'])['version'], snapshot=snapshot))))
    facts = features_v5.compute(value, StubCalc())
    state = compact_v5.render(value, ('counters',), facts)[0].split('\n')
    assert '| weather sunnyday t3 |' in state[0]
    assert state[1].startswith('my side: reflect t1 spikes2 | opp side:')
