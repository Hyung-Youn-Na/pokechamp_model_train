"""EX-050 bounded saved-input regression and synthetic uncertainty boundaries."""
import copy
import json
from pathlib import Path

import pytest

from integration.pokechamp.jev_battle import (
    INITIAL_PP_POLICY, LEGACY_INPUT_VERSION, V2_INPUT_VERSION as VERSION, make_input,
)
from integration.pokechamp.observation.build import DEFAULT_BUILD

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/jev-ex050-leads.json').read_text())
FIELDS = ('boosts', 'status', 'volatiles', 'turnstatuses', 'movestatuses', 'status_data', 'tera_type')

@pytest.fixture(params=FIXTURES, ids=['line7-p1', 'line641-p2'])
def lead(request):
    return copy.deepcopy(request.param), json.loads((DEFAULT_BUILD / 'dex.json').read_text())


def project(lead, **kwargs):
    case, dex = lead
    event = case['event']
    return make_input(event['official'], case['prefix'], actor=event['actor'], dex=dex,
                      **{'version': VERSION, **kwargs})


def test_saved_v1_reproduction(lead):
    case, _ = lead
    payload, commands = project(lead, version=LEGACY_INPUT_VERSION)
    assert payload == case['event']['payload']
    assert commands == case['event']['commands']
    for mon in payload['state']['self_team']:
        assert all(mon[key] == 'unknown' for key in FIELDS)


def test_lead_known_initial_values_and_private_boundary(lead):
    case, _ = lead
    before = copy.deepcopy(case)
    payload, commands = project(lead, initial_pp_policy=INITIAL_PP_POLICY)
    assert case == before
    assert payload['state']['version'] == VERSION
    assert commands == case['event']['commands']
    assert payload['state']['opponent_team'] == case['event']['payload']['state']['opponent_team']
    for mon, raw in zip(payload['state']['self_team'], case['event']['official']['request']['side']['pokemon']):
        assert mon['status'] == mon['tera_type'] == mon['terastallized'] == ''
        assert mon['status_data'] == dict(sleepTurns=0, toxicTurns=0)
        for key in ('boosts', 'volatiles', 'turnstatuses', 'movestatuses'):
            assert mon[key] == {}
        for key in ('condition', 'stats', 'item', 'ability', 'teraType'):
            assert mon[key] == raw[key]
        assert all(m['current_pp'] > 0 and m['current_pp_source'] == INITIAL_PP_POLICY for m in mon['moves'])
    assert 'teraType is the configured Tera type' in payload['questions']['action']['instructions']


def test_pp_evidence_and_no_boost_exception(lead):
    case, dex = lead
    own = project(lead)[0]['state']['self_team']
    assert all(m['current_pp'] == 'unknown' and m['current_pp_reason'] for p in own for m in p['moves'])
    move = case['event']['official']['request']['side']['pokemon'][0]['moves'][0]
    dex['BattleMovedex'][move].update(pp=1, noPPBoosts=True)
    assert project(lead, initial_pp_policy=INITIAL_PP_POLICY)[0]['state']['self_team'][0]['moves'][0]['current_pp'] == 1
    dex['BattleMovedex'][move].pop('pp')
    assert project(lead, initial_pp_policy=INITIAL_PP_POLICY)[0]['state']['self_team'][0]['moves'][0]['current_pp'] == 'unknown'


@pytest.mark.parametrize('condition,expected', [('100/100', ''), ('99/100 brn', 'brn'), ('99/100 tox', 'tox'), ('99/100 slp', 'slp'), ('?', 'unknown'), ('', 'unknown')])
def test_status_is_from_private_condition(lead, condition, expected):
    case, _ = lead
    case['event']['official']['request']['side']['pokemon'][0]['condition'] = condition
    mon = project(lead)[0]['state']['self_team'][0]
    assert mon['status'] == expected
    if expected:
        assert mon['status_data'] == 'unknown'


def test_unidentified_preview_never_joins_by_species_order_or_nickname(lead):
    case, _ = lead
    event = case['event']
    own_side = next(s for s in event['official']['sides'] if s['id'] == event['actor'])
    own_side['pokemon'].reverse()
    for mon in own_side['pokemon']:
        mon.update(ident='', status='slp', boosts={'atk': 6}, tera_type='SECRET')
    raw = event['official']['request']['side']['pokemon']
    raw[1]['ident'] = raw[0]['ident']  # identical nickname: still distinct request slots
    raw[1]['details'] = raw[0]['details']  # duplicate species cannot drive a join
    payload, commands = project(lead)
    assert [m['slot'] for m in payload['state']['self_team']] == list(range(1, 7))
    assert all(m['status'] == '' and m['boosts'] == {} and m['tera_type'] == '' for m in payload['state']['self_team'])
    assert commands == event['commands']


@pytest.mark.parametrize('change', ['start', 'effect', 'turn', 'missing_init'])
def test_initial_values_require_prebattle_evidence(lead, change):
    case, _ = lead
    if change == 'turn':
        case['event']['official']['turn'] = 1
    elif change == 'missing_init':
        case['prefix'][0]['protocol'] = case['prefix'][0]['protocol'].replace('|init|battle', '|title|synthetic')
    else:
        case['prefix'].append(dict(event_seq=99, protocol='|start' if change == 'start' else '|-boost|p1a: X|atk|1'))
        case['event']['official']['consumed'] += 1
    with pytest.raises(ValueError, match='initial team preview'):
        project(lead, initial_pp_policy=INITIAL_PP_POLICY)


def test_tera_configured_and_applied_are_distinct(lead):
    case, _ = lead
    raw = case['event']['official']['request']['side']['pokemon'][0]
    raw['teraType'] = 'Water'
    raw['terastallized'] = 'Fire'
    mon = project(lead)[0]['state']['self_team'][0]
    assert mon['teraType'] == 'Water' and mon['tera_type'] == 'Fire'
    raw.pop('terastallized')
    mon = project(lead)[0]['state']['self_team'][0]
    assert mon['tera_type'] == '' and mon['terastallized'] == 'unknown'


def test_normal_and_forced_switch_preserve_observations_and_pp():
    from integration.pokechamp.tests.test_observation_comparison import fixture
    from integration.pokechamp.observation.runtime import OfficialClient
    prefix, _ = fixture()
    with OfficialClient('p1') as client:
        state = client.snapshot(prefix, 'offline-unit')
    dex = json.loads((DEFAULT_BUILD / 'dex.json').read_text())
    for forced in (False, True):
        if forced:
            state['request'].pop('active')
            state['request']['forceSwitch'] = [True]
            state['candidates'] = [dict(wire='switch 2')]
        new, commands = make_input(state, prefix, actor='p1', dex=dex, initial_pp_policy=INITIAL_PP_POLICY)
        old, old_commands = make_input(state, prefix, actor='p1', dex=dex, version=LEGACY_INPUT_VERSION)
        assert commands == old_commands
        assert new['state']['opponent_team'] == old['state']['opponent_team']
        for actual, expected in zip(new['state']['self_team'], old['state']['self_team']):
            for move in actual['moves']:
                move.pop('current_pp_source', None)
                move.pop('current_pp_reason', None)
            assert actual == expected
        if not forced:
            assert [m['current_pp'] for m in new['state']['self_team'][0]['moves']] == [16, 0]
    state['request']['side']['pokemon'][1]['ident'] = state['request']['side']['pokemon'][0]['ident']
    with pytest.raises(ValueError, match='ambiguous own request'):
        make_input(state, prefix, actor='p1', dex=dex)
    state['request']['side']['pokemon'][1]['ident'] = 'p1: Pikachu'
    state['sides'][0]['pokemon'].append(copy.deepcopy(state['sides'][0]['pokemon'][0]))
    with pytest.raises(ValueError, match='ambiguous own identity'):
        make_input(state, prefix, actor='p1', dex=dex)


def test_unverified_format_and_unknown_form_stay_unknown(lead):
    case, _ = lead
    for event in case['prefix']:
        event['protocol'] = event['protocol'].replace('|tier|Gen 9 OU', '|tier|Custom Game')
    raw = case['event']['official']['request']['side']['pokemon'][0]
    raw['details'] = 'Unknown-Form, M'
    mon = project(lead, initial_pp_policy=INITIAL_PP_POLICY)[0]['state']['self_team'][0]
    assert mon['types'] == 'unknown'
    assert all(m['current_pp'] == 'unknown' and m['current_pp_reason'] for m in mon['moves'])


def test_session_verifies_pp_provenance_before_opt_in(tmp_path, monkeypatch):
    from integration.pokechamp import jev_battle
    def fail():
        raise ValueError('synthetic build drift')
    monkeypatch.setattr(jev_battle, 'verify', fail)
    with pytest.raises(ValueError, match='build drift'):
        jev_battle.Session(tmp_path, fake=True)
