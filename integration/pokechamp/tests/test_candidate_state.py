"""Independent mechanics/cutoff checks; no model, service or collected battle."""
import copy
import gzip
import json
import subprocess
from pathlib import Path

import pytest

from integration.pokechamp.diagnostics import candidate_state as c
from integration.pokechamp.diagnostics.jev_damage import Engine
from integration.pokechamp.diagnostics.jev_damage_verify import individual_calls
from integration.pokechamp.diagnostics.jev_offline import generate_input
from integration.pokechamp.observation.build import DEFAULT_BUILD

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='module')
def dex():
    return json.loads((DEFAULT_BUILD / 'dex.json').read_text())


@pytest.fixture(scope='module')
def engine():
    with Engine() as worker:
        yield worker


def spec(dex, name, *, hp=None, ability='', item='', boosts=None, evs=None, nature='Serious', ivs=None):
    base = dex['BattlePokedex'][name]
    ev = {s: (evs or {}).get(s, 0) for s in c.STATS}
    iv = {s: (ivs or {}).get(s, 31) for s in c.STATS}
    maximum = 2 * base['baseStats']['hp'] + iv['hp'] + ev['hp'] // 4 + 110
    return dict(name=name, options=dict(level=100, gender='N', ability=ability, item=item,
        nature=nature, evs=ev, ivs=iv, boosts=boosts or {}, curHP=maximum if hp is None else hp, status=''),
        expectedStats={'hp': maximum}, battle_types=base['types'], projected_entry=False,
        entry_effects_observed=True, qp_source=None)


def outcome(dex, engine, own, enemy, move, opposing_move, *, field=None, official=None):
    audit = {'calculations': []}
    rows = c._scenario(own, enemy, move, opposing_move, {'assumption_id': 's0'},
        official or {'field': []}, dex, c._Runner(engine, audit), 'move_1',
        field or {'attackerSide': {}, 'defenderSide': {}})
    return rows, audit


def test_close_combat_applies_defense_before_same_set_blaze_counter(dex, engine):
    own = spec(dex, 'zamazenta', hp=222, ability='Dauntless Shield', item='Heavy-Duty Boots',
        boosts={'def': 1}, evs={'atk': 252, 'spd': 4, 'spe': 252}, nature='Jolly')
    enemy = spec(dex, 'cinderace', ability='Blaze', item='Heavy-Duty Boots',
        evs={'atk': 252, 'spd': 4, 'spe': 252}, nature='Jolly')
    rows, audit = outcome(dex, engine, own, enemy, 'closecombat', 'pyroball')
    assert len(rows) == 1 and rows[0]['order'] == 'self_first'
    row = rows[0]
    assert row['after_first_action']['self_boosts']['def'] == 0
    assert row['after_first_action']['self_boosts']['spd'] == -1
    assert row['supplied_incoming_damage_applicable'] is False
    assert row['target_survival'] == 'survives'
    assert row['self_survival'] == 'ko'
    replies = [r for r in audit['calculations'] if r['phase'] == 'after_candidate_response']
    assert replies and all(r['scenario']['attacker']['options']['ability'] == 'Blaze' for r in replies)
    assert all(r['scenario']['defender']['options']['boosts']['def'] == 0 for r in replies)
    assert all(r['scenario']['attacker']['options']['curHP'] <= enemy['expectedStats']['hp'] / 3 for r in replies)
    oracle = individual_calls([r['scenario'] for r in replies])
    assert [r['damage_range_hp'] for r in oracle['entries']] == [r['result']['damage_range_hp'] for r in replies]


def test_opponent_first_ko_prevents_candidate_execution_and_effects(dex, engine):
    own = spec(dex, 'tinglu', hp=1, ability='Vessel of Ruin')
    enemy = spec(dex, 'cinderace', ability='Blaze', evs={'atk': 252, 'spe': 252}, nature='Jolly')
    rows, audit = outcome(dex, engine, own, enemy, 'earthquake', 'pyroball')
    assert rows[0]['order'] == 'opponent_first'
    assert rows[0]['self_survival'] == 'ko'
    assert rows[0]['target_survival'] == 'survives'
    assert not any(r['phase'] == 'after_opponent_candidate' for r in audit['calculations'])
    assert 'outgoing_damage_pct' not in rows[0]


def test_ruination_uses_current_hp_and_one_hp_edge_case(dex, engine):
    own = spec(dex, 'tinglu', ability='Vessel of Ruin')
    for hp, expected in [(33, 'survives'), (1, 'ko')]:
        enemy = spec(dex, 'cinderace', hp=hp, ability='Blaze', evs={'spe': 252}, nature='Jolly')
        rows, audit = outcome(dex, engine, own, enemy, 'ruination', 'pyroball')
        assert rows[0]['target_survival'] == expected
        after = next(r for r in audit['calculations'] if r['phase'] == 'after_opponent_candidate')
        assert after['result']['damage_range_hp'] == [max(1, hp // 2)] * 2


def test_hydrapple_survives_then_hits_low_hp_target(dex, engine):
    own = spec(dex, 'hydrapple', ability='Regenerator', item='Heavy-Duty Boots',
        evs={'hp': 248, 'def': 176, 'spa': 16, 'spd': 56, 'spe': 12}, nature='Modest', ivs={'atk': 0})
    enemy = spec(dex, 'cinderace', hp=18, ability='Blaze', evs={'atk': 252, 'spe': 252}, nature='Jolly')
    rows, audit = outcome(dex, engine, own, enemy, 'earthpower', 'pyroball')
    assert rows[0]['order'] == 'opponent_first'
    assert rows[0]['self_survival'] == 'survives' and rows[0]['target_survival'] == 'ko'
    attacks = [r for r in audit['calculations'] if r['phase'] == 'after_opponent_candidate']
    assert attacks and all(0 < r['scenario']['attacker']['options']['curHP'] < own['options']['curHP'] for r in attacks)


def test_opponent_first_close_combat_and_drain_apply_before_our_counter(dex, engine):
    own = spec(dex, 'tinglu', ability='Vessel of Ruin')
    enemy = spec(dex, 'zamazenta', ability='Dauntless Shield', boosts={'def': 1},
                 evs={'atk': 252, 'spe': 252}, nature='Jolly')
    rows, audit = outcome(dex, engine, own, enemy, 'earthquake', 'closecombat')
    counters = [r for r in audit['calculations'] if r['phase'] == 'after_opponent_candidate']
    assert counters and rows[0]['order'] == 'opponent_first'
    assert all(r['scenario']['defender']['options']['boosts'] == {'def': 0, 'spd': -1} for r in counters)
    enemy = spec(dex, 'mew', hp=100, boosts={'spe': 1})
    rows, audit = outcome(dex, engine, own, enemy, 'ruination', 'gigadrain')
    counters = [r for r in audit['calculations'] if r['phase'] == 'after_opponent_candidate']
    assert counters and all(r['scenario']['defender']['options']['curHP'] > 100 for r in counters)
    assert all(r['result']['damage_range_hp'] == [r['scenario']['defender']['options']['curHP'] // 2] * 2 for r in counters)


def test_speed_tie_and_unresolved_order_items_keep_both_orders(dex, engine):
    own, enemy = spec(dex, 'mew'), spec(dex, 'mew')
    rows, _ = outcome(dex, engine, own, enemy, 'tackle', 'tackle')
    assert {r['order'] for r in rows} == {'self_first', 'opponent_first'}
    own['options']['item'] = 'Quick Claw'
    enemy['options']['boosts']['spe'] = 2
    rows, _ = outcome(dex, engine, own, enemy, 'tackle', 'tackle')
    assert {r['order'] for r in rows} == {'self_first', 'opponent_first'}
    assert all('action_order_activation_not_resolved' in r['limitations'] for r in rows)


def test_unmodeled_libero_type_change_and_fractional_roll_are_unknown(dex, engine):
    own = spec(dex, 'tinglu', ability='Vessel of Ruin')
    enemy = spec(dex, 'cinderace', ability='Libero', evs={'spe': 252}, nature='Jolly')
    rows, _ = outcome(dex, engine, own, enemy, 'earthquake', 'surf')
    assert rows[0]['target_survival'] == 'unknown'
    assert 'opponent_post_move_transition_not_supported' in rows[0]['limitations']
    assert c._rolls({'damage_rolls': [1.5, 2.5]}) is None
    own = spec(dex, 'cinderace', ability='Libero', evs={'spe': 252}, nature='Jolly')
    enemy = spec(dex, 'mew')
    rows, _ = outcome(dex, engine, own, enemy, 'surf', 'tackle')
    assert rows[0]['order'] == 'self_first' and rows[0]['self_survival'] == 'unknown'
    assert 'libero_or_protean_persistent_type_transition_not_supported' in rows[0]['limitations']
    own = spec(dex, 'mew', hp=100, item='Big Root')
    states, errors = c._direct_outcomes(own, enemy, 'gigadrain', {'damage_rolls': [50]}, dex)
    assert 'drain_modifier_not_supported' in errors
    assert states[0][0]['options']['curHP'] == 100


def test_odd_hp_recovery_and_drain_match_canonical_showdown(dex):
    # Isolated CPU mechanics oracle: call useMove directly, no battle collection.
    code = """
    const {Battle}=require('./pokemon-showdown/dist/sim');
    const b=new Battle({formatid:'gen9customgame'});
    b.setPlayer('p1',{name:'own',team:[{species:'Mew',ability:'Synchronize',ivs:{hp:15},moves:['Recover','Giga Drain']}]});
    b.setPlayer('p2',{name:'foe',team:[{species:'Mew',ability:'Synchronize',moves:['Tackle']}]});
    if(!b.p1.active[0]){b.choose('p1','team 1');b.choose('p2','team 1');}
    const a=b.p1.active[0],d=b.p2.active[0];a.hp=100;b.actions.useMove('recover',a);
    const recovery=a.hp-100;a.hp=100;d.hp=5;b.actions.useMove('gigadrain',a);
    process.stdout.write(JSON.stringify({maximum:a.maxhp,recovery,drain:a.hp-100}));b.destroy();
    """
    oracle = json.loads(subprocess.run(['node', '-e', code], cwd=ROOT, text=True,
                                     capture_output=True, check=True).stdout)
    own = spec(dex, 'mew', hp=100, ivs={'hp': 15})
    enemy = spec(dex, 'mew', hp=5)
    states, errors = c._status_outcomes(own, enemy, 'recover', dex, {})
    assert not errors and own['expectedStats']['hp'] == oracle['maximum'] == 325
    assert states[0][0]['options']['curHP'] - 100 == oracle['recovery'] == 163
    states, errors = c._direct_outcomes(own, enemy, 'gigadrain', {'damage_rolls': [50]}, dex)
    assert not errors and states[0][0]['options']['curHP'] - 100 == oracle['drain'] == 3


def context_fixture(lines, *, faint=False):
    request = dict(forceSwitch=[True], side=dict(id='p1', pokemon=[
        dict(active=True, condition='0 fnt' if faint else '100/100')]))
    prefix = [dict(event_seq=1, protocol='\n'.join(['|start', '|turn|2'] + lines))]
    return dict(request=request, turn=2), prefix


def test_forced_switch_completed_attack_not_reapplied_and_phase_not_from_faint():
    official, prefix = context_fixture(['|move|p2a: Cinderace|Pyro Ball|p1a: Mew', '|faint|p1a: Mew'], faint=True)
    context = c.decision_context(official, prefix, 'p1')
    assert context['opponent_action_remaining'] == 'no' and context['phase'] == 'unknown'
    official, prefix = context_fixture(['|move|p1a: Mew|U-turn|p2a: Cinderace'])
    context = c.decision_context(official, prefix, 'p1')
    assert context['phase'] == 'mid_turn_pivot' and context['opponent_action_remaining'] == 'unknown'
    official, prefix = context_fixture(['|faint|p1a: Mew', '|upkeep'], faint=True)
    context = c.decision_context(official, prefix, 'p1')
    assert context['phase'] == 'after_turn_faint'
    assert context['opponent_action_remaining'] == context['residual_remaining'] == 'no'


def test_lead_active_is_only_request_flag_without_established_matchup(dex, engine):
    raw = json.loads((FIXTURES / 'jev-ex050-leads.json').read_text())[0]
    official = raw['event']['official']
    payload, commands, _ = generate_input(official, raw['prefix'], '', dex, engine=engine)
    after, audit = c.enrich(payload, official, raw['prefix'], '', dex, engine=engine)
    assert after['state']['decision_context']['phase'] == 'team_preview'
    assert after['state']['decision_context']['active_interpretation'] == 'request_slot_flag_not_entered_matchup'
    assert list(after['questions']['action']['criteria']) == list(commands)
    assert all(c.candidate_evaluation(after, aid)['status'] == 'not_applicable' for aid in commands)
    assert audit['calculations'] == []


@pytest.fixture(scope='module')
def bounded_case(dex, engine):
    raw = json.loads((FIXTURES / 'jev-damage-prefix.json').read_text())
    payload, _, _ = generate_input(raw['official'], raw['prefix'], raw['own_team'], dex, engine=engine)
    return raw, payload


def test_cutoff_foreign_actor_stale_request_and_candidate_order_fail_closed(bounded_case, dex, engine):
    raw, payload = bounded_case
    cases = []
    foreign = copy.deepcopy(payload)
    foreign['state']['actor'] = 'p2'
    cases.append((foreign, raw['official'], raw['prefix']))
    future = copy.deepcopy(raw['prefix'])
    future[-1]['protocol'] += '\n|move|p2a: Zapdos|Thunder|p1a: Lokix'
    cases.append((payload, raw['official'], future))
    stale = copy.deepcopy(payload)
    stale['state']['request_id'] = 99999
    cases.append((stale, raw['official'], raw['prefix']))
    reordered = copy.deepcopy(payload)
    criteria = reordered['questions']['action']['criteria']
    reordered['questions']['action']['criteria'] = dict(reversed(list(criteria.items())))
    cases.append((reordered, raw['official'], raw['prefix']))
    for value, official, prefix in cases:
        with pytest.raises(ValueError):
            c.enrich(value, official, prefix, raw['own_team'], dex, engine=engine)


def test_payload_immutable_ids_instructions_and_no_private_audit_fields(bounded_case, dex, engine):
    raw, payload = bounded_case
    original = copy.deepcopy(payload)
    after, audit = c.enrich(payload, raw['official'], raw['prefix'], raw['own_team'], dex, engine=engine)
    assert payload == original
    assert list(after['questions']['action']['criteria']) == list(payload['questions']['action']['criteria'])
    assert after['questions']['action']['instructions'] == payload['questions']['action']['instructions']
    assert after['state']['version'] == c.VERSION
    forbidden = {'ident', 'original_set', 'prefix', 'server_snapshot', 'rng', 'provenance', 'counts', 'values'}
    def keys(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                keys(child)
        elif isinstance(value, list):
            for child in value:
                keys(child)
    keys(after)
    assert 'supported_candidates' in audit
    for aid, candidate in after['questions']['action']['criteria'].items():
        assert candidate['evaluation_ref'] == aid and 'evaluation' not in candidate
        expected = copy.deepcopy(audit['candidate_evaluations'][aid])
        if expected.get('same_outcomes_as_action_id'):
            expected['scenarios'] = audit['candidate_evaluations'][expected['same_outcomes_as_action_id']]['scenarios']
        assert c.candidate_evaluation(after, aid) == expected


def test_switch_entry_hazards_once_and_no_finished_attack_reapplication(bounded_case, dex, engine):
    raw, _ = bounded_case
    actor = raw['official']['request']['side']['id']
    owns = c._own_contexts(raw['official'], raw['prefix'], raw['own_team'], actor)
    entrant = next(m for m in owns.values() if m['species'] == 'zamazenta')
    entrant['item'] = ''
    enemy = c._opponent_context(raw['official'], raw['prefix'], actor)
    enemy['moves'] = ['heatwave']
    sets, _ = c.SetSnapshot().load(enemy['species'])
    supported, _ = c.candidates(sets, enemy, c.public_history(raw['prefix'], enemy['ident']))
    profiles = c._profiles(supported, enemy, dex)
    audit = {'calculations': []}
    result = c._switch({}, entrant, enemy, profiles,
        {'attackerSide': {'isSR': True, 'spikes': 1}, 'defenderSide': {}},
        {'opponent_action_remaining': 'no'}, c._Runner(engine, audit), dex, 'switch_3')
    assert result['entry']['hp_before'] == 325
    # Fighting resists Rock: floor(325/16) + one Spikes layer floor(325/8).
    assert result['entry']['hazard_damage'] == 60 and result['entry']['hp_after'] == 265
    assert result['incoming_applicable'] == 'not_applicable'
    assert all(r['phase'] == 'switch_entry_only' for r in audit['calculations'])
    for row in audit['calculations']:
        assert row['scenario']['defender']['options']['curHP'] == 325
        assert row['result']['scenario_state']['entry'][0]['hp_after_hazards'] == 265


def test_one_failed_calculation_never_promotes_partial_support_to_survival(dex, engine):
    class PartialEngine:
        def calculate(self, scenario):
            if scenario['scenario_id'].startswith('after_candidate_response'):
                return {'excluded_with_reason': 'authored_unsupported_response'}
            return engine.calculate(scenario)
    own = spec(dex, 'zamazenta', boosts={'def': 1}, evs={'spe': 252}, nature='Jolly')
    enemy = spec(dex, 'cinderace', ability='Blaze')
    rows, _ = outcome(dex, PartialEngine(), own, enemy, 'closecombat', 'pyroball')
    assert rows[0]['self_survival'] == 'unknown'
    assert rows[0]['incoming_damage_pct'] == 'unknown'
    assert 'authored_unsupported_response' in rows[0]['limitations']


def test_guaranteed_post_hit_triggers_do_not_publish_unresolved_hp(dex, engine):
    own = spec(dex, 'mew', boosts={'spe': 1}, hp=100)
    enemy = spec(dex, 'mew', ability='Water Absorb')
    rows, _ = outcome(dex, engine, own, enemy, 'surf', 'tackle')
    assert rows[0]['self_survival'] == 'unknown' and 'after_first_action' not in rows[0]
    assert 'target_post_hit_ability_or_item_transition_not_supported' in rows[0]['limitations']
    own['options']['item'] = 'Sitrus Berry'
    enemy['options']['ability'] = ''
    rows, _ = outcome(dex, engine, own, enemy, 'tackle', 'tackle')
    assert rows[0]['self_survival'] == 'unknown'
    assert 'target_post_hit_ability_or_item_transition_not_supported' in rows[0]['limitations']


@pytest.mark.parametrize('case', ['absorb', 'big_root', 'liquid_ooze', 'berry'])
def test_unsupported_candidate_effect_after_opponent_first_stays_unknown(case, dex, engine):
    if case == 'absorb':
        own = spec(dex, 'mew', hp=200, ability='Synchronize')
        enemy = spec(dex, 'vaporeon', hp=200, ability='Water Absorb',
                     evs={'spe': 252}, nature='Timid')
        move, opposing_move = 'surf', 'tackle'
        reason = 'target_post_hit_ability_or_item_transition_not_supported'
    elif case == 'big_root':
        own = spec(dex, 'hydrapple', hp=300, ability='Regenerator', item='Big Root')
        enemy = spec(dex, 'cinderace', hp=200, ability='Blaze', evs={'spe': 252}, nature='Jolly')
        move, opposing_move = 'gigadrain', 'pyroball'
        reason = 'drain_modifier_not_supported'
    elif case == 'liquid_ooze':
        own = spec(dex, 'hydrapple', hp=300, ability='Regenerator')
        enemy = spec(dex, 'tentacruel', hp=250, ability='Liquid Ooze')
        move, opposing_move = 'gigadrain', 'surf'
        reason = 'drain_modifier_not_supported'
    else:
        own = spec(dex, 'mew', hp=200, ability='Synchronize')
        enemy = spec(dex, 'mew', hp=200, ability='Synchronize',
                     item='Sitrus Berry', boosts={'spe': 2})
        move, opposing_move = 'surf', 'psychic'
        reason = 'target_post_hit_ability_or_item_transition_not_supported'
    rows, audit = outcome(dex, engine, own, enemy, move, opposing_move)
    assert len(rows) == 1 and rows[0]['order'] == 'opponent_first'
    row = rows[0]
    assert reason in row['limitations']
    assert row['self_survival'] == row['target_survival'] == 'unknown'
    assert 'target_hp_pct_after_candidate' not in row
    # The first ordinary hit is resolved; only the following candidate effect is unsupported.
    incoming = next(r['result'] for r in audit['calculations'] if r['phase'] == 'before_actions_incoming')
    assert row['after_first_action']['self_hp'] == [
        own['options']['curHP'] - max(incoming['damage_rolls']),
        own['options']['curHP'] - min(incoming['damage_rolls'])]
    counters = [r for r in audit['calculations'] if r['phase'] == 'after_opponent_candidate']
    assert counters and all('damage_range_hp' in r['result'] for r in counters)
    states, reasons = c._direct_outcomes(counters[0]['scenario']['attacker'],
        counters[0]['scenario']['defender'], move, counters[0]['result'], dex)
    assert states and reason in reasons


@pytest.mark.parametrize('initial_comparison', [None, 'compare_same_assumption_outcomes; future_strategic_value_unknown'])
def test_empty_tera_outcomes_preserve_cost_without_claiming_equivalence(initial_comparison):
    baseline = dict(status='unknown', scenarios=[], unsupported=['no_public_opposing_action_to_compare'])
    tera = copy.deepcopy(baseline)
    if initial_comparison:
        tera['tera_comparison'] = dict(non_tera_action_id='move_1', resource_spent=True,
                                      benefit=initial_comparison)
    criteria = {'move_1': dict(kind='move', terastallize=False, evaluation=baseline),
                'move_1_terastallize': dict(kind='move', terastallize=True, evaluation=tera)}
    c._compact(criteria)
    assert 'same_outcomes_as_action_id' not in tera
    assert tera['status'] == 'unknown' and tera['scenarios'] == []
    assert tera['unsupported'] == ['no_public_opposing_action_to_compare']
    assert tera['tera_comparison'] == dict(non_tera_action_id='move_1', resource_spent=True,
        benefit='unknown_without_nonempty_comparison_scenarios; future_strategic_value_unknown')
    assert baseline == dict(status='unknown', scenarios=[], unsupported=['no_public_opposing_action_to_compare'])


def test_saved_ex063_five_scenes_integer_support_and_tera_dedup(dex, engine):
    root = ROOT / '.pokechamp-data/qwen/ex063-live'
    if not root.exists():
        pytest.skip('archived EX-063 not installed')
    request = json.loads((root / 'battle-1/request.json').read_text())
    own_team_id = request['slot']['teams'][1 if request['slot']['qwen_actor'] == 'p2' else 0]
    # Read exclusively the actor's declared set, never the opponent entry.
    own_team = request['teams'][own_team_id]['showdown_team']
    scenes = {}
    for path in (root / 'input-audits').glob('*.gz'):
        raw = json.loads(gzip.decompress(path.read_bytes()))
        state = raw['original_payload']['state']
        if state['turn'] not in (3, 4, 5, 6, 8) or state['decision_kind'] != 'turn_action':
            continue
        payload, _, _ = generate_input(raw['official'], raw['prefix'], own_team, dex, engine=engine)
        after, audit = c.enrich(payload, raw['official'], raw['prefix'], own_team, dex, engine=engine)
        scenes[state['turn']] = after
        assert audit['calculations']
    assert set(scenes) == {3, 4, 5, 6, 8}
    cc = c.candidate_evaluation(scenes[3], 'move_1')['scenarios']
    assert cc and all(r['order'] == 'self_first' for r in cc)
    assert all(r['after_first_action']['self_boosts']['def'] == 0 and
               not r['supplied_incoming_damage_applicable'] for r in cc)
    assert any(a['support_kind'] == 'counterfactual_species_ability' for a in scenes[3]['state']['candidate_assumptions'])
    for turn in (4, 6):
        assert all(r['target_survival'] == 'ko' and r['self_survival'] == 'survives'
                   for r in c.candidate_evaluation(scenes[turn], 'move_1')['scenarios'])
        assert all(r['target_survival'] == 'survives'
                   for r in c.candidate_evaluation(scenes[turn], 'move_3')['scenarios'])
    tera = scenes[5]['state']['candidate_evaluations']['move_3_terastallize']
    assert tera['same_outcomes_as_action_id'] == 'move_3'
    assert tera['tera_comparison']['resource_spent'] is True
    assert all(r['self_survival'] == 'survives' and r['target_survival'] == 'ko'
               for r in c.candidate_evaluation(scenes[8], 'move_3')['scenarios'])
