"""EX-121 v2 renderer: v1 identity with no module, frozen module rules, determinism, damage request mapping."""
import itertools
import json

import pytest

from integration.laya_imitation import compact, compact_v2, features
from integration.laya_imitation import config as c
from integration.pokechamp.imitation.schema import ImitationInput


def values(n=40):
    with open(c.EX071_PREPARED / 'validation.jsonl') as f:
        return [ImitationInput.from_body(json.loads(line)['input']) for line in itertools.islice(f, n)]


class StubCalc:
    def __init__(self):
        self.requests = []

    def run(self, requests):
        self.requests.extend(requests)
        return [dict(min=10.0 + i, max=20.0 + i) for i, _ in enumerate(requests)]


def mon(**kw):
    base = dict(species='zapdos', types=['electric', 'flying'], terastallized=False, tera_type=None, status=None,
                item='', ability='', boosts={}, effects={}, hp_percent=100.0, moves=[])
    base.update(kw)
    return base


def snap(**kw):
    base = dict(weather=None, field={}, own_side_conditions={}, opponent_side_conditions={})
    base.update(kw)
    return base


def test_no_module_is_exactly_v1():
    for v in values():
        assert compact_v2.render(v) == compact.render(v)
        assert compact_v2.render(v, (), None) == compact.render(v)


def test_version_name_and_unknown_module():
    assert compact_v2.version_name(['switch', 'damage']) == 'laya-compact-v2[damage,switch]'
    with pytest.raises(ValueError):
        compact_v2.normalize(['speed', 'nope'])


def test_move_rules():
    e = features.effective_move
    assert e('weatherball', mon(), mon(), snap(weather='snowscape'), ability='', item='', tera=None)['type'] == 'ice'
    assert e('weatherball', mon(), mon(), snap(weather='snowscape'), ability='', item='', tera=None)['power'] == 100
    assert e('weatherball', mon(), mon(), snap(), ability='', item='', tera=None)['reasons'] == []
    grounded = mon(types=['normal'])
    assert e('terrainpulse', grounded, None, snap(field={'grassy_terrain': 1}), ability='', item='', tera=None)['type'] == 'grass'
    assert e('terrainpulse', mon(), None, snap(field={'grassy_terrain': 1}), ability='', item='', tera=None)['type'] == 'normal'
    pix = e('hypervoice', mon(types=['fairy']), None, snap(), ability='pixilate', item='', tera=None)
    assert (pix['type'], pix['power'], pix['stab']) == ('fairy', 108, 1)
    blast = e('terablast', mon(), None, snap(), ability='', item='', tera='grass', user_stats=dict(atk=300, spa=200))
    assert (blast['type'], blast['category']) == ('grass', 'physical')
    assert e('facade', mon(status='brn'), None, snap(), ability='', item='', tera=None)['power'] == 140
    assert e('knockoff', mon(), mon(item='leftovers'), snap(), ability='', item='', tera=None)['power'] == 98
    assert e('knockoff', mon(), mon(item=None), snap(), ability='', item='', tera=None)['power'] == 65
    assert e('acrobatics', mon(), None, snap(), ability='', item='', tera=None)['power'] == 110
    assert e('bulletpunch', mon(types=['steel']), None, snap(), ability='technician', item='', tera=None)['power'] == 60
    assert e('thunderbolt', mon(), None, snap(), ability='adaptability', item='', tera=None)['stab'] == 2
    assert e('thunderbolt', mon(), None, snap(), ability='', item='', tera='grass')['stab'] == 1


def test_speed_formula_order_and_trick_room():
    assert features._stat(100, 31, 184, 100, 1.1) == 310          # Zapdos, Timid 184 Spe
    assert features._order(300, dict(lo=200, hi=250, est=230), False) == 'first'
    assert features._order(300, dict(lo=200, hi=350, est=320), False) == 'likely second'
    assert features._order(300, dict(lo=200, hi=350, est=320), True) == 'likely first'
    assert features._order(100, dict(lo=200, hi=350, est=320), True) == 'first'
    scarf = features._speed_mods(200, mon(), snap(), 'own_side_conditions', '', 'choicescarf')
    assert scarf == 300
    par = features._speed_mods(200, mon(status='par', boosts={'spe': 1}), snap(own_side_conditions={'tailwind': 1}),
                               'own_side_conditions', '', '')
    assert par == 300


def test_hazards():
    rocks = {'stealth_rock': 1, 'spikes': 2, 'toxic_spikes': 2, 'sticky_web': 1}
    own = lambda **kw: mon(original_set={'ability': ''}, **kw)
    assert features._hazards(own(types=['fire', 'flying']), rocks) == dict(pct=50.0, extra=[])
    assert features._hazards(own(types=['fire', 'flying'], item='heavydutyboots'), rocks) == dict(pct=0.0, extra=[])
    assert features._hazards(own(types=['water']), rocks) == dict(pct=29.2, extra=['tox', 'web'])
    assert features._hazards(own(types=['poison']), rocks)['extra'] == ['absorbs tspikes', 'web']


def test_compute_is_deterministic_and_maps_damage_requests():
    for v in values(20):
        a, b = StubCalc(), StubCalc()
        fa, fb = features.compute(v, a), features.compute(v, b)
        assert fa == fb and a.requests == b.requests
        moves = [k for k, f in fa['moves'].items() if f['category'] != 'status']
        snapshot = json.loads(v.body['state'])['snapshot']
        if snapshot['opponent_active_slot']:
            assert all(k in fa['damage'] for k in moves)
        state, question = compact_v2.render(v, compact_v2.MODULES, fa)
        assert list(question['criteria']) == list(v.action_ids)
        assert state.startswith(compact.render(v)[0].split('\n')[0])
