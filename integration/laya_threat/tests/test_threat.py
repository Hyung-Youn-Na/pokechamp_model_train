"""EP-225 v9: spread fix on the contradictory assumed sets, and the 2026-11-02 human game's Kyurem scene.

`kyurem_scene.json`: two inputs of laya-v7test game 20261102-052243-smogonAI-laya-v7t-001 (the person's Cinderace
Kyurem BO): turn 6, Kyurem just in through Chilly Reception with nothing revealed; turn 7, Iron Crown fainted to a
Tera Ice Choice Specs Blizzard. Run with the laya 0.4.13 interpreter: `python -m pytest integration/laya_threat/tests`.
"""
import json
from pathlib import Path

import pytest

from integration.laya_imitation import data_v7, features
from integration.laya_imitation.data_v2 import OPTION_LIMIT
from integration.pokechamp.imitation.schema import ImitationInput
from integration.laya_threat import data_v9, render_v9, spreads

SCENE = json.loads((Path(__file__).with_name('kyurem_scene.json')).read_text())


def foe(species, item=None, moves=()):
    return dict(species=species, item=item, moves=[dict(id=m) for m in moves], ability=None, boosts={}, status=None,
                hp_percent=100, tera_type=None, terastallized=False)


def test_specs_kyurem_gets_a_special_spread():
    spec, changed = spreads.fixed(spreads._original(foe('kyurem'))[0], foe('kyurem'))
    assert changed and spec['nature'] == 'timid' and spec['evs'].get('spa') == 252 and not spec['evs'].get('atk')


def test_bulky_spreads_stay():
    for mon in (foe('skarmory', moves=('roost', 'spikes', 'bodypress')), foe('tinglu', moves=('ruination',))):
        spec = spreads._original(mon)[0]
        assert spreads.fixed(spec, mon) == (spec, False)


def test_revealed_attacks_decide_without_a_choice_item():
    mon = foe('dragapult', moves=('dragondarts', 'uturn'))
    spec = dict(spreads._original(mon)[0], item='lifeorb', nature='timid', evs={'spa': 252, 'spe': 252})
    fixed, changed = spreads.fixed(spec, mon)
    assert changed and fixed['nature'] not in spreads.LOWERS['atk'] and fixed['evs']['atk'] >= spreads.MIN_EV


@pytest.fixture(scope='module')
def calc():
    with features.Calc() as calc:
        yield calc


def renders(calc, key):
    value = ImitationInput.from_body(SCENE[key])
    v7 = data_v7.live_renderer(calc)(value)
    v9 = data_v9.live_renderer(calc)(value)
    return v7, v9, data_v7.live_renderer(calc)(value)


def test_tera_specs_blizzard_hit_matches_the_game(calc):
    (_, q7), (_, q9), _ = renders(calc, '7-forced_switch')
    assert 'hit 45-53%' in q7['criteria']['switch:4']
    assert 'hit 60-71%' in q9['criteria']['switch:4']   # Kingambit took 60% from this Blizzard in the game


def test_fresh_foe_gets_threat_and_risk(calc):
    (s7, q7), (s9, q9), again = renders(calc, '6-turn_action')
    assert 'risk' not in q7['criteria']['switch:3'] and '; risk ' in q9['criteria']['switch:3']   # Iron Crown
    assert any(x.startswith('opp threat: ') for x in s9.split('\n'))
    assert again == (s7, q7)   # the spread patch does not leak into a later v7 render
    assert not spreads.active()


def test_budget(calc):
    for key in SCENE:
        _, (state, question), _ = renders(calc, key)
        assert render_v9.row_fits(state, question)
        assert all(render_v9.option_tokens(a, t) <= OPTION_LIMIT for a, t in question['criteria'].items())
