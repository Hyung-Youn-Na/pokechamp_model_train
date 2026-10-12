"""User requirements and counterexamples for the offline-only JEV projection."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from integration.pokechamp import effects
from integration.pokechamp.diagnostics.jev_damage import Engine
from integration.pokechamp.diagnostics.jev_damage_verify import synthesize
from integration.pokechamp.diagnostics.jev_offline import (
    RoleDB, compact_bench, effect_object, generate_input, natural_events, project, type_chart,
)
from integration.pokechamp.jev_battle import INITIAL_PP_POLICY, VERSION, make_input
from integration.pokechamp.observation.build import DEFAULT_BUILD

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='module')
def dex():
    return json.loads((DEFAULT_BUILD / 'dex.json').read_text())


@pytest.fixture(scope='module')
def case():
    return json.loads((FIXTURES / 'jev-damage-prefix.json').read_text())


@pytest.fixture(scope='module')
def baseline(case, dex):
    return generate_input(case['official'], case['prefix'], case['own_team'], dex)


def active(payload, side):
    return next(m for m in payload['state'][side + '_team'] if m['active'])


def assert_no_keys(value, forbidden):
    if isinstance(value, dict):
        assert not forbidden.intersection(value)
        for child in value.values():
            assert_no_keys(child, forbidden)
    elif isinstance(value, list):
        for child in value:
            assert_no_keys(child, forbidden)


def test_default_and_source_unchanged(case, baseline):
    after, commands, audit = baseline
    assert VERSION == 'jev-choice-v3'
    assert audit['original_payload'] == case['payload']
    assert audit['prefix'] == case['prefix'] and audit['official'] == case['official']
    assert_no_keys(after, {'ident', 'initial_state_source', 'effect_reference', 'current_pp_source'})
    assert audit['original_payload']['state']['self_team'][0]['ident'] == 'p1: Lokix'
    assert after['questions']['action']['criteria'].keys() == commands.keys()


def test_slots_effects_and_actions(case, baseline):
    after, commands, _ = baseline
    own = active(after, 'self')
    assert 'moves' not in own and 'known_move_set' not in own
    assert own['stats'] == case['payload']['state']['self_team'][0]['stats']
    for new, raw in zip(own['current_move_slots'], case['payload']['state']['self_team'][0]['current_move_slots'], strict=True):
        assert all(new[k] == v for k, v in raw.items())
        assert new['general_effect'] and new['priority'] in (0, 1, 2)
        assert new['damage']['target_species'] == 'Zapdos'
        assert new['damage']['target_side'] == 'opponent'
        assert new['damage']['unit'] == 'percent_of_target_max_hp'
        assert new['damage']['ranges']['current'][1] > 0
    for key, candidate in after['questions']['action']['criteria'].items():
        if candidate['kind'] == 'move':
            ref = candidate['move_ref']
            assert ref == {'self_team_slot': own['slot'], 'current_move_slot': candidate['slot']}
            assert commands[key] == '/choose ' + key.replace('_', ' ')
            assert 'move' not in candidate
    assert own['item']['id'] == 'heavydutyboots' and own['item']['general_effect']
    assert own['ability']['id'] == 'tintedlens' and own['ability']['general_effect']


def test_hidden_moves_and_conditional_roles(baseline):
    after, _, _ = baseline
    opponent = active(after, 'opponent')
    assert opponent['moves'] == 'unknown'
    assert opponent['ability'] == opponent['item'] == {'knowledge': 'unknown'}
    assert opponent['hp_percent'] == 100 and opponent['hp_precision'] == 'rounded'
    assert opponent['status'] == '' and opponent['terastallized'] is False
    for mon in after['state']['opponent_team']:
        assert mon['role_summary']['knowledge'] == 'species_possibilities_not_observed_set'
        assert mon['role_summary']['roles']
        if not mon['active']:
            assert 'moves' not in mon and 'stats' not in mon and 'ability' not in mon and 'item' not in mon


def test_compact_is_separate_information_ablation(baseline):
    after, _, _ = baseline
    compact = compact_bench(after)
    assert compact['questions'] == after['questions']
    assert compact['state']['opponent_team'] == after['state']['opponent_team']
    for full, short in zip(after['state']['self_team'], compact['state']['self_team'], strict=True):
        if full['active']:
            assert full == short
        else:
            assert 'known_move_set' in full and 'stats' in full
            assert full['known_move_set'] and all(m['general_effect'] for m in full['known_move_set'])
            assert short == {k: v for k, v in full.items() if k not in ('known_move_set', 'stats')}


@pytest.mark.parametrize('lead_index', [0, 1])
def test_lead_preserves_details_and_links(dex, lead_index):
    lead = json.loads((FIXTURES / 'jev-ex050-leads.json').read_text())[lead_index]
    after, commands, audit = generate_input(lead['event']['official'], lead['prefix'], '', dex, compact=True)
    assert after['state']['decision_kind'] == 'lead'
    assert compact_bench(after) == after
    for mon in after['state']['self_team']:
        assert mon['known_move_set'] and mon['stats']
        assert 'current_move_slots' not in mon and 'moves' not in mon
        assert mon['configured_tera_type'] != 'unknown'
        assert mon['terastallized'] is False
        assert mon['status'] == ''
    assert commands == lead['event']['commands']
    assert audit['original_payload']['state']['version'] == 'jev-choice-v3'
    assert after['state']['speed_comparison']['status'] == 'not_applicable'


def test_required_log_information_and_orientation():
    case = json.loads((FIXTURES / 'jev-offline-public-events.json').read_text())
    asset, _ = effects._asset()
    rows, audit = natural_events(case['recent_completed_turn_events'], 'p1', 2, asset)
    assert len(rows) == 10 and all(r['supported'] for r in audit)
    assert rows[0]['participants'] == ['Your Lokix', 'Opposing Zapdos']
    assert rows[0]['text'] == 'Lokix used **First Impression**! Target: Opposing Zapdos.'
    assert 'not very effective' in rows[1]['text'].lower()
    assert 'remaining public HP approximately 63% (rounded)' in rows[2]['text']
    assert 'remaining HP 0; fainted' in rows[5]['text']
    assert 'Lokix fainted' in rows[6]['text']
    assert 'remaining HP 325/325 (exact)' in rows[7]['text']
    assert 'Dauntless Shield' in rows[8]['text']
    assert 'Defense rose' in rows[9]['text'] and 'def +1; not the final stage' in rows[9]['text']
    swapped = copy.deepcopy(case['recent_completed_turn_events'])
    for row in swapped:
        row['protocol'] = row['protocol'].replace('p1', 'TEMP').replace('p2', 'p1').replace('TEMP', 'p2')
    assert natural_events(swapped, 'p2', 2, asset)[0] == rows


def test_recent_window_status_tera_effect_end_and_unknown():
    asset, _ = effects._asset()
    lines = ['|-status|p2a: Sparky|par', '|-curestatus|p2a: Sparky|par',
             '|-terastallize|p2a: Sparky|Fire', '|-start|p2a: Sparky|confusion',
             '|-end|p2a: Sparky|confusion', '|-fieldstart|move: Trick Room',
             '|-fieldend|move: Trick Room', '|-futureunsupported|p2a: Sparky|public data']
    events = [dict(turn=turn, protocol=line) for turn in (1, 2, 3, 4, 5) for line in lines]
    rows, audit = natural_events(events, 'p1', 5, asset)
    assert [r['turn'] for r in rows] == [2]*8 + [3]*8 + [4]*8
    assert 'paraly' in rows[0]['text'] and 'Fire' in rows[2]['text']
    assert 'confus' in rows[3]['text'] and 'confus' in rows[4]['text']
    assert rows[5]['text'] != rows[6]['text']
    assert rows[7]['raw_protocol'] == lines[7] and not audit[7]['supported']
    assert 'Unsupported event:' in rows[7]['text']


def test_absence_unknown_and_suppression():
    asset, _ = effects._asset()
    assert effect_object('items', None, asset) == {'knowledge': 'confirmed_absent'}
    assert effect_object('items', '', asset) == {'knowledge': 'confirmed_absent'}
    assert effect_object('items', 'unknown', asset) == {'knowledge': 'unknown'}
    assert effect_object('abilities', '(suppressed)', asset)['knowledge'] == 'suppressed'


def test_complete_type_matrix_orientation(dex):
    chart = type_chart(dex)
    assert len(chart['attack_types']) == len(set(chart['attack_types'])) == 18
    assert chart['defense_types'] == chart['attack_types']
    assert len(chart['multipliers']) == 18 and all(len(r) == 18 for r in chart['multipliers'])
    def effectiveness(attack, *defenses):
        value = 1
        for defense in defenses:
            value *= chart['multipliers'][chart['attack_types'].index(attack)][chart['defense_types'].index(defense)]
        return value
    assert effectiveness('Ground', 'Electric', 'Flying') == 0
    assert effectiveness('Ice', 'Ground', 'Flying') == 4
    assert effectiveness('Water', 'Fire') == 2
    assert effectiveness('Fire', 'Water') == .5
    assert effectiveness('Normal', 'Ghost') == 0
    assert effectiveness('Poison', 'Steel') == 0


def test_observed_incoming_moves_only(case, dex):
    observed = synthesize(case, ['|move|p2a: Zapdos|Hurricane|p1a: Lokix'], dex)
    after, _, audit = generate_input(observed['official'], observed['prefix'], observed['own_team'], dex)
    moves = active(after, 'opponent')['moves']
    assert [m['id'] for m in moves] == ['hurricane']
    assert moves[0]['knowledge'] == 'observed' and moves[0]['priority'] == 0
    assert moves[0]['damage']['target_species'] == 'Lokix'
    assert moves[0]['damage']['target_side'] == 'self'
    assert moves[0]['damage']['ranges']['current'][0] > 0
    assert all(r['move'] == 'hurricane' for r in audit['damage']['calculations'] if r['direction'] == 'incoming')


@pytest.mark.parametrize('tera', ['Fire', 'Stellar'])
def test_defense_and_stab_separated_after_tera(case, dex, tera):
    changed = synthesize(case, [f'|-terastallize|p2a: Zapdos|{tera}'], dex)
    after, _, _ = generate_input(changed['official'], changed['prefix'], changed['own_team'], dex)
    enemy = active(after, 'opponent')
    assert enemy['terastallized'] is True and enemy['applied_tera_type'] == tera
    assert enemy['defensive_types'] == (['Fire'] if tera == 'Fire' else ['Electric', 'Flying'])
    assert enemy['stab_types'] == ['Electric', 'Flying']
    assert 'tera_type' not in enemy and 'types' not in enemy


def test_forced_switch_preserves_own_bench_and_fainted_active(dex):
    case = json.loads((FIXTURES / 'jev-offline-forced.json').read_text())
    detailed, commands, audit = generate_input(case['official'], case['prefix'], '', dex)
    assert detailed['state']['decision_kind'] == 'forced_switch'
    assert compact_bench(detailed) == detailed
    assert commands == case['commands']
    assert all(c['kind'] == 'switch' for c in detailed['questions']['action']['criteria'].values())
    for mon in detailed['state']['self_team']:
        assert mon['known_move_set'] and mon['stats']
    assert active(detailed, 'self')['condition'] == '0 fnt'
    assert detailed['state']['speed_comparison']['status'] == 'not_applicable'
    assert audit['original_payload']['state']['version'] == 'jev-choice-v3'


def test_hp_unknown_absent_item_and_nickname_reference(case, dex):
    payload = copy.deepcopy(case['payload'])
    enemy = active(payload, 'opponent')
    enemy.update(hp='unknown', item=None, ability='unknown', status='par')
    own = active(payload, 'self')
    own['ident'] = 'p1: Buggy'
    own['volatiles'] = {'attract': ['attract', {'pokemon_ident': enemy['ident']}]}
    payload['state']['recent_completed_turn_events'] = []
    after, _ = project(payload, dex=dex, roles=RoleDB())
    new = active(after, 'opponent')
    assert new['hp_percent'] == new['hp_precision'] == 'unknown'
    assert new['item']['knowledge'] == 'confirmed_absent' and new['ability']['knowledge'] == 'unknown'
    assert new['status'] == 'par' and new['terastallized'] is False
    assert_no_keys(after, {'ident', 'pokemon_ident', 'initial_state_source'})
    assert active(after, 'self')['nickname'] == 'Buggy'
    linked = active(after, 'self')['volatiles']['attract']['observed'][1]['pokemon_ref']
    assert linked == {'side': 'opponent', 'team_slot': 1, 'species': 'Zapdos'}


def test_disabled_source_and_custom_request_slot(case, dex):
    payload = copy.deepcopy(case['payload'])
    slot = active(payload, 'self')['current_move_slots'][0]
    slot.update(id='struggle', move='Struggle', disabled=True, disabledSource='move: Taunt')
    after, _ = project(payload, dex=dex, roles=RoleDB())
    new = active(after, 'self')['current_move_slots'][0]
    assert new['id'] == 'struggle' and new['power'] == 50
    assert new['general_effect'].startswith('Deals typeless damage')
    assert new['disabled'] is True and new['disabledSource'] == 'move: Taunt'
    assert new['restriction_effects'][0]['id'] == 'taunt'
    assert new['damage']['ranges'] is None and new['damage']['reason'] == 'not_calculated'


def test_log_hp_heal_sethp_and_boost_cause_boundaries():
    asset, _ = effects._asset()
    lines = ['|-heal|p1a: A|123/321 brn', '|-sethp|p1a: A|60/321 brn|p2a: B|38/100 par',
             '|-ability|p1a: A|Dauntless Shield|boost', '|-boost|p1a: A|def|1',
             '|-boost|p2a: B|atk|2', '|-unboost|p1a: A|spe|1']
    rows, _ = natural_events([dict(turn=1, protocol=p) for p in lines], 'p1', 2, asset)
    assert '123/321 (exact); status brn' in rows[0]['text']
    assert '60/321 (exact); status brn' in rows[1]['text']
    assert '38% (rounded); status par' in rows[1]['text']
    assert 'Source: Dauntless Shield' in rows[3]['text']
    assert 'Source:' not in rows[4]['text']
    assert 'spe -1; not the final stage' in rows[5]['text']


def test_speed_reflects_public_modifiers_without_invented_probability(case, dex, baseline):
    base = baseline[0]['state']['speed_comparison']
    assert base['self_effective_speed_range'] == [283, 283]
    # Pinned Zapdos: Bold, 0 Spe EV => 2*100+31+5=236; Timid, 252 EV => floor(299*1.1)=328.
    assert base['opponent_effective_speed_range'] == [236, 328]
    assert not any(key.startswith('p_') for key in base)
    assert base['status'] == 'available'
    assert base['speed_certainty'] == 'depends_on_opponent_set'
    assert {row['set_name']: row['self_speed_relation'] for row in base['by_set']} == {
        'Defensive': ['faster'], 'Offensive': ['slower']}
    assert 'cannot be assured' in base['assessment']
    changed = synthesize(case, ['|-boost|p1a: Lokix|spe|1', '|-status|p2a: Zapdos|par',
                               '|-fieldstart|move: Trick Room'], dex)
    after, _, audit = generate_input(changed['official'], changed['prefix'], changed['own_team'], dex)
    speed = after['state']['speed_comparison']
    assert speed['self_effective_speed_range'] == [424, 424]
    assert speed['opponent_effective_speed_range'] == [118, 164]
    assert speed['speed_certainty'] == 'consistent_within_recommended_support'
    assert speed['self_speed_relation'] == ['faster']
    assert 'all legal opponent sets' in speed['assessment']
    assert 'not action-order probability' in speed['meaning']
    assert audit['speed']
    assert 'Trick Room reverses' in after['questions']['action']['instructions']


def test_missing_pp_is_explicit_without_dex_guess(case, dex):
    payload = copy.deepcopy(case['payload'])
    active(payload, 'self')['current_move_slots'][0].pop('pp')
    after, _ = project(payload, dex=dex, roles=RoleDB())
    slot = active(after, 'self')['current_move_slots'][0]
    assert slot['pp'] == 'unknown' and slot['pp_reason'] == 'active_request_omits_pp'


def test_calculated_zero_differs_from_null(case, dex):
    # Presentation audit independently injects oracle outcomes; calculation
    # correctness itself is covered by EP-082's per-candidate oracle suite.
    damage = copy.deepcopy(case['payload'])
    moves = active(damage, 'self')['moves']
    moves[0].update(damage_pct={'current': [0, 0]})
    moves[1].update(damage_pct=None, damage_reason='no_compatible_recommended_set')
    moves[2].update(damage_pct={'current': None}, damage_reason={'current': 'unsupported_calculation'})
    after, _ = project(case['payload'], dex=dex, roles=RoleDB(), damage_payload=damage)
    slots = active(after, 'self')['current_move_slots']
    assert slots[0]['damage']['ranges']['current'] == [0, 0]
    assert slots[0]['damage']['reason'] is None
    assert slots[1]['damage']['ranges'] is None
    assert slots[1]['damage']['reason'] == 'no_compatible_recommended_set'
    assert slots[2]['damage']['ranges']['current'] is None
    assert slots[2]['damage']['reason']['current'] == 'unsupported_calculation'


def test_all_324_type_cells_against_server_api(dex):
    root = Path(__file__).resolve().parents[3]
    program = """const {Dex}=require('./pokemon-showdown/dist/sim/dex.js');
const types=JSON.parse(require('fs').readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(types.map(a=>types.map(d=>Dex.getImmunity(a,d)?2**Dex.getEffectiveness(a,d):0))));"""
    chart = type_chart(dex)
    oracle = subprocess.run(['node', '-e', program], input=json.dumps(chart['attack_types']),
                            cwd=root, text=True, capture_output=True, check=True)
    assert chart['multipliers'] == json.loads(oracle.stdout)


def replace_final_request(case, mutate, dex):
    changed = copy.deepcopy(case)
    lines = changed['prefix'][-1]['protocol'].splitlines()
    request = json.loads(lines[-1].removeprefix('|request|'))
    mutate(request)
    lines[-1] = '|request|' + json.dumps(request, separators=(',', ':'))
    changed['prefix'][-1]['protocol'] = '\n'.join(lines)
    return synthesize(changed, [], dex)


def test_request_only_struggle_gets_actual_damage(case, dex):
    def only_struggle(request):
        request['active'][0]['moves'] = [dict(move='Struggle', id='struggle', pp=1, maxpp=1, target='randomNormal', disabled=False)]
    changed = replace_final_request(case, only_struggle, dex)
    after, commands, _ = generate_input(changed['official'], changed['prefix'], changed['own_team'], dex)
    slot = active(after, 'self')['current_move_slots'][0]
    assert slot['id'] == 'struggle' and slot['damage']['ranges']['current'][0] > 0
    assert slot['priority'] == 0
    assert 'move_1' in commands and 'move_2' not in commands
    assert all(m['id'] != 'struggle' for m in active(case['payload'], 'self')['moves'])


def test_speed_tie_support_with_exact_own_spread(case, dex):
    def speed_236(request):
        request['side']['pokemon'][0]['stats']['spe'] = 236
    changed = replace_final_request(case, speed_236, dex)
    changed['own_team'] = changed['own_team'].replace('252 Spe', '64 Spe', 1)
    after, _, audit = generate_input(changed['official'], changed['prefix'], changed['own_team'], dex)
    speed = after['state']['speed_comparison']
    assert speed['self_effective_speed_range'] == [236, 236]
    summaries = [r['candidate_summary'] for r in audit['speed'] if 'candidate_summary' in r]
    assert {tuple(r['outcomes']) for r in summaries} == {('tie',), ('slower',)}
    assert speed['self_speed_relation'] == ['slower', 'tie']
    assert speed['speed_certainty'] == 'depends_on_opponent_set'
    assert not any(key.startswith('p_') for key in speed)


@pytest.mark.parametrize('pairs,expected,relations', [
    ([(300, 200), (300, 250)], 'consistent_within_recommended_support', ['faster']),
    ([(100, 200), (100, 250)], 'consistent_within_recommended_support', ['slower']),
    ([(200, 200), (200, 200)], 'consistent_within_recommended_support', ['tie']),
    ([(200, 150), (200, 250)], 'depends_on_set_or_unresolved_state', ['faster', 'slower']),
    ([(200, 200), (200, 250)], 'depends_on_set_or_unresolved_state', ['slower', 'tie']),
])
def test_speed_preserves_within_set_public_hp_uncertainty(monkeypatch, pairs, expected, relations):
    from integration.pokechamp.diagnostics import jev_speed
    monkeypatch.setattr(jev_speed, 'own_spec', lambda own: {})
    monkeypatch.setattr(jev_speed, 'opponent_specs', lambda *args: [
        dict(options=dict(curHP=hp)) for hp in (100, 101)])
    class Engine:
        def calculate(self, scenario):
            a, b = pairs[scenario['defender']['options']['curHP'] - 100]
            return dict(conditional_order=dict(attacker_speed=a, defender_speed=b))
    audit = dict(normalized_active=dict(self={}, opponent={}),
                 candidates=[dict(candidate_id='a', set_index=0, set_name='Conditional')],
                 field={}, history=dict(unsupported=[]))
    result, records = jev_speed.compare(audit, {}, Engine())
    assert result['speed_certainty'] == expected
    assert result['self_speed_relation'] == relations
    assert result['by_set'][0]['self_speed_relation'] == relations
    assert len([r for r in records if 'scenario' in r]) == 2


@pytest.mark.parametrize('failure', ['no_candidates', 'unsupported', 'partial_calculation', 'no_active'])
def test_speed_cannot_claim_certainty_from_missing_or_partial_support(monkeypatch, failure):
    from integration.pokechamp.diagnostics import jev_speed
    monkeypatch.setattr(jev_speed, 'own_spec', lambda own: {})
    monkeypatch.setattr(jev_speed, 'opponent_specs', lambda *args: [dict(options=dict(curHP=100))])
    class Engine:
        def calculate(self, scenario):
            if '/b/' in scenario['scenario_id']:
                return dict(excluded_with_reason='unsupported_second_candidate')
            return dict(conditional_order=dict(attacker_speed=300, defender_speed=200))
    audit = dict(normalized_active=dict(self={}, opponent={}),
                 candidates=[dict(candidate_id=c, set_index=i, set_name=c) for i, c in enumerate(['a', 'b'])],
                 field={}, history=dict(unsupported=[]))
    if failure == 'no_candidates': audit['candidates'] = []
    if failure == 'unsupported': audit['field']['unsupported_reason'] = 'unknown_field'
    if failure == 'no_active': audit.pop('normalized_active')
    result, _ = jev_speed.compare(audit, {}, Engine())
    assert result['status'] == ('not_applicable' if failure == 'no_active' else 'unavailable')
    assert result['speed_certainty'] == ('not_applicable' if failure == 'no_active' else 'unknown')
    assert 'by_set' not in result and 'self_speed_relation' not in result
    assert not any(key.startswith('p_') for key in result)


def test_p2_turn_projection_preserves_actor_relative_targets(case, dex, baseline):
    encoded = json.dumps(case).replace('p1', 'SIDE_TMP').replace('p2', 'p1').replace('SIDE_TMP', 'p2')
    changed = json.loads(encoded)
    after, commands, _ = generate_input(changed['official'], changed['prefix'], changed['own_team'], dex)
    assert after['state']['actor'] == 'p2'
    assert after['state']['self_team'] == baseline[0]['state']['self_team']
    assert after['state']['opponent_team'] == baseline[0]['state']['opponent_team']
    assert commands == baseline[1]


def test_recharge_marker_is_not_an_unknown_dex_attack(case, dex):
    def only_recharge(request):
        request['active'][0]['moves'] = [dict(move='Recharge', id='recharge')]
        request['active'][0].pop('canTerastallize', None)
    changed = replace_final_request(case, only_recharge, dex)
    after, commands, _ = generate_input(changed['official'], changed['prefix'], changed['own_team'], dex)
    slot = active(after, 'self')['current_move_slots'][0]
    assert slot['id'] == 'recharge'
    assert slot['pp'] == slot['priority'] == slot['target'] == 'not_applicable'
    assert slot['damage']['ranges'] is None and slot['damage']['reason'] == 'recharge_action'
    assert 'move_1' in commands


def test_unsupported_event_with_unknown_typed_effect_keeps_original():
    protocol = '|-futureeffect|p2a: Sparky|[from] ability: Future Unknown Ability'
    rows, audit = natural_events([dict(turn=1, protocol=protocol)], 'p1', 2, effects._asset()[0])
    assert rows[0]['raw_protocol'] == protocol
    assert rows[0]['text'] == 'Unsupported event: ' + protocol
    assert not audit[0]['supported']
