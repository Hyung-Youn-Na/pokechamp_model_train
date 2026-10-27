"""EX-128 v3 renderer: v2 identity without v3 modules, set inference from public facts, speed chance, switch hit."""
import itertools
import json

import pytest

from integration.laya_imitation import compact_v2, compact_v3, features_v3
from integration.laya_imitation import config as c
from integration.pokechamp.imitation.schema import ImitationInput


def values(n=40):
    with open(c.EX071_PREPARED / 'validation.jsonl') as f:
        return [ImitationInput.from_body(json.loads(line)['input']) for line in itertools.islice(f, n)]


class StubCalc:
    def run(self, requests):
        return [dict(min=10.0 + i, max=20.0 + i) for i, _ in enumerate(requests)]


def foe(**kw):
    base = dict(slot=1, species='greattusk', types=['ground', 'fighting'], terastallized=False, tera_type=None,
                status=None, item=None, ability=None, boosts={}, effects={}, hp_percent=100.0, moves=[])
    base.update(kw)
    return base


def snap(**kw):
    base = dict(weather=None, field={}, own_side_conditions={}, opponent_side_conditions={})
    base.update(kw)
    return base


def test_without_v3_modules_is_exactly_v2():
    calc = StubCalc()
    for v in values():
        facts = features_v3.compute(v, calc)
        assert compact_v3.render(v, compact_v2.MODULES, facts) == compact_v2.render(v, compact_v2.MODULES, facts)
        assert compact_v3.render(v) == compact_v2.render(v)


def test_version_name_digest_and_unknown_module():
    assert compact_v3.version_name(['threat', 'damage']) == 'laya-compact-v3[damage,threat]'
    assert compact_v3.version(compact_v3.MODULES)['usage_sha256'] == features_v3.digest()
    with pytest.raises(ValueError):
        compact_v3.normalize(['oppset', 'nope'])


def test_all_modules_render_and_are_deterministic():
    calc = StubCalc()
    for v in values():
        a = compact_v3.render(v, compact_v3.MODULES, features_v3.compute(v, calc))
        b = compact_v3.render(v, compact_v3.MODULES, features_v3.compute(v, calc))
        assert a == b
        assert list(a[1]['criteria']) == list(v.action_ids)


def test_public_facts_fix_the_set():
    s = features_v3.infer_set(foe(moves=[dict(id='rapidspin', pp=None, max_pp=64)], item='boosterenergy',
                                  ability='protosynthesis', tera_type='steel'), True)
    assert s['source'] == 'usage'
    assert s['item'] == [['boosterenergy', 1.0]] and s['ability'] == [['protosynthesis', 1.0]]
    assert s['tera'] == [['steel', 1.0]]
    assert 'rapidspin' not in dict(s['moves']) and all(0 < p <= 1 for _, p in s['moves'])
    assert abs(sum(p for _, p in features_v3.infer_set(foe(), True)['item']) - 1) < 1e-3


def test_moves_fill_the_remaining_slots_only():
    four = [dict(id=m, pp=None, max_pp=8) for m in ('rapidspin', 'headlongrush', 'icespinner', 'stealthrock')]
    assert features_v3.infer_set(foe(moves=four), True)['moves'] == []
    assert features_v3.threats(features_v3.infer_set(foe(moves=four), True)) == []
    assert features_v3.infer_set(foe(terastallized=True), True)['tera'] == []
    assert features_v3.infer_set(foe(), False)['tera'] == []


def test_species_without_usage_and_aliases():
    assert features_v3.infer_set(foe(species='notapokemon'), True)['source'] == 'default'
    assert features_v3.species_key('ogerponwellspringtera') == 'ogerponwellspring'
    assert features_v3.species_key('mimikyubusted') == 'mimikyu'


def test_first_chance():
    inferred = features_v3.infer_set(foe(), True)
    assert features_v3.first_chance(999, foe(), inferred, snap()) == 1.0
    assert features_v3.first_chance(999, foe(), inferred, snap(field={'trick_room': 1})) == 0.0
    assert features_v3.first_chance(1, foe(), inferred, snap()) == 0.0
    mid = features_v3.first_chance(300, foe(), inferred, snap())
    scarf = features_v3.first_chance(300, foe(item='choicescarf'), inferred, snap())
    assert 0 < mid < 1 and scarf <= mid
    assert features_v3.first_chance(None, foe(), inferred, snap()) is None


def test_switch_hit_uses_the_larger_hit():
    t = dict(move='closecombat', p=0.4, min=50.0, max=60.0)
    seen = dict(min=10.0, max=20.0, move='rapidspin')
    assert compact_v3._switch_hit('x; hit 10-20%', t, seen) == 'x; hit 50-60%?'
    assert compact_v3._switch_hit('x; hit 70-80%', t, dict(min=70.0, max=80.0, move='m')) == 'x; hit 70-80%'
    assert compact_v3._switch_hit('x', t, None) == 'x; hit 50-60%?'
    assert compact_v3._switch_hit('x; hit ?', t, dict(error='e')) == 'x; hit 50-60%?'
    assert compact_v3._switch_hit('x', None, None) == 'x'


def test_oppset_line():
    assert compact_v3._oppset_line(None) is None
    assert compact_v3._oppset_line(dict(source='default')) == 'opp set: no usage data'
    known = dict(source='usage', item=[['leftovers', 1.0]], ability=[['pressure', 1.0]], tera=[], moves=[])
    assert compact_v3._oppset_line(known) == 'opp set: all known'
    line = compact_v3._oppset_line(features_v3.infer_set(foe(), True))
    assert line.startswith('opp set: item ') and 'likely moves ' in line
