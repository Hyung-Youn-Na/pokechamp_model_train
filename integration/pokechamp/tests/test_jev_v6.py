"""Public lifetime counterexamples and saved v4/v5 compatibility (no battles)."""
import copy
import json
from pathlib import Path

import pytest

from integration.jev27b.formatting import format_request
from integration.pokechamp import jev_v4, jev_v5, jev_v6
from integration.pokechamp.diagnostics.jev_damage_verify import synthesize
from integration.pokechamp.diagnostics.public_facts_v6 import apply, history, reconstruct
from integration.pokechamp.observation.build import DEFAULT_BUILD

FIXTURES = Path(__file__).parent / 'fixtures'
SAVED = Path(__file__).resolve().parents[3] / 'project_context/exec-plans/evidence/ep093/certainty-v1'


@pytest.fixture(scope='module')
def dex():
    return json.loads((DEFAULT_BUILD / 'dex.json').read_text())


@pytest.fixture(scope='module')
def case():
    return json.loads((FIXTURES / 'jev-damage-prefix.json').read_text())


def replay(case, dex, lines):
    result = synthesize(case, lines, dex)
    return result, reconstruct(result['official'], result['prefix'], actor=result['actor'], dex=dex)


def enemy(facts, name='Zapdos'):
    return facts['pokemon']['p2: ' + name]


def run(case, dex):
    adapter = jev_v6.Adapter(dex)
    try:
        return adapter.generate(case['official'], case['prefix'], case['own_team'], actor=case['actor'])
    finally:
        adapter.close()


def switch_out():
    return '|switch|p2a: Hydrapple|Hydrapple, M|100/100'


def switch_back(hp='63/100'):
    return '|switch|p2a: Zapdos|Zapdos|' + hp


def test_full_prefix_keeps_moves_item_ability_and_public_hp_on_bench(case, dex):
    changed, facts = replay(case, dex, [
        '|move|p2a: Zapdos|Hurricane|p1a: Lokix',
        '|-item|p2a: Zapdos|Leftovers', '|-ability|p2a: Zapdos|Static',
        '|-damage|p2a: Zapdos|63/100', '|-boost|p2a: Zapdos|spe|2',
        '|-start|p2a: Zapdos|confusion', switch_out(),
        '|turn|2', '|turn|3', '|turn|4', '|turn|5'])
    # A client can infer recovery or retain old volatiles; public facts cannot.
    raw = next(m for m in changed['official']['sides'][1]['pokemon'] if m['ident'] == 'p2: Zapdos')
    raw['hp'] = 100
    facts = reconstruct(changed['official'], changed['prefix'], actor='p1', dex=dex)
    projected, _ = apply(changed['payload'], facts, dex)
    mon = next(m for m in projected['state']['opponent_team'] if m['ident'] == 'p2: Zapdos')
    assert [m['id'] for m in mon['moves']] == ['hurricane']
    assert mon['item'] == 'leftovers' and mon['ability'] == mon['baseAbility'] == 'static'
    assert mon['hp']['current'] == 63
    assert all(mon[k] == {} for k in ('boosts', 'volatiles', 'turnstatuses', 'movestatuses'))
    payload, _, audit = run(changed, dex)
    bench = next(m for m in payload['state']['opponent_team'] if m['species'] == 'Zapdos')
    assert bench['moves'][0]['name'] == 'Hurricane' and bench['moves'][0]['general_effect']
    assert bench['ability']['id'] == bench['baseAbility']['id'] == 'static'
    assert bench['item']['id'] == 'leftovers' and bench['hp_percent'] == 63
    assert 'damage' not in bench['moves'][0]
    assert 'boosts' not in bench and 'volatiles' not in bench
    assert all('Hurricane' not in r['text'] for r in payload['state']['recent_completed_turn_log'])
    assert audit['official'] == changed['official'] and audit['public_supplements']
    returned, returned_facts = replay(changed, dex, [switch_back()])
    assert enemy(returned_facts)['moves'] == ['hurricane']
    assert enemy(returned_facts)['item'] == 'leftovers'


@pytest.mark.parametrize('removal', [
    '|-enditem|p2a: Zapdos|Sitrus Berry|[eat]',
    '|-enditem|p2a: Zapdos|Sitrus Berry|[from] move: Knock Off'])
def test_absence_survives_bench_late_consumption_effect_and_new_trick(case, dex, removal):
    changed, facts = replay(case, dex, [
        '|-item|p2a: Zapdos|Sitrus Berry', removal,
        '|-heal|p2a: Zapdos|75/100|[from] item: Sitrus Berry', switch_out()])
    assert enemy(facts)['item'] is None
    changed, facts = replay(changed, dex, [switch_back(),
        '|-item|p2a: Zapdos|Choice Scarf|[from] move: Trick|[of] p1a: Lokix'])
    assert enemy(facts)['item'] == 'choicescarf'
    assert history(facts, 'p2: Zapdos')['initial_items'] == ['sitrusberry']
    assert history(facts, 'p2: Zapdos')['item_changed']


def test_stolen_item_owner_and_frisk_owner(case, dex):
    _, facts = replay(case, dex, [
        '|-item|p2a: Zapdos|Leftovers|[from] ability: Frisk|[of] p1a: Lokix',
        '|-item|p1a: Lokix|Leftovers|[from] move: Thief|[of] p2a: Zapdos'])
    assert enemy(facts)['item'] is None
    assert enemy(facts)['ability'] == 'unknown'
    assert facts['pokemon']['p1: Lokix']['ability'] == 'frisk'


@pytest.mark.parametrize('original,event,expected', [
    ('Mimic', '-start|p2a: Zapdos|Mimic|Ice Beam', 'mimic'),
    ('Sketch', '-activate|p2a: Zapdos|move: Sketch|Ice Beam', 'icebeam')])
def test_mimic_temporary_sketch_persistent(case, dex, original, event, expected):
    changed, facts = replay(case, dex, [f'|move|p2a: Zapdos|{original}|p1a: Lokix',
        '|' + event, '|move|p2a: Zapdos|Ice Beam|p1a: Lokix'])
    assert enemy(facts)['moves'] == ['icebeam']
    assert enemy(facts)['original_moves'] == [original.lower()]
    changed, facts = replay(changed, dex, [switch_out(), switch_back()])
    assert enemy(facts)['moves'] == [expected]
    assert not enemy(facts)['temporary_replacements']


def test_transform_only_public_copies_revert_and_called_reflected_are_not_slots(case, dex):
    changed, facts = replay(case, dex, [
        '|move|p1a: Lokix|U-turn|p2a: Zapdos',
        '|move|p2a: Zapdos|Transform|p1a: Lokix',
        '|-transform|p2a: Zapdos|p1a: Lokix',
        '|move|p2a: Zapdos|First Impression|p1a: Lokix',
        '|move|p2a: Zapdos|Spore|p1a: Lokix|[from] move: Metronome',
        '|move|p2a: Zapdos|Toxic|p1a: Lokix|[from] ability: Magic Bounce'])
    assert enemy(facts)['moves'] == ['uturn', 'firstimpression']
    assert 'suckerpunch' not in enemy(facts)['moves']  # present only in own private request
    assert enemy(facts)['original_moves'] == ['transform']
    assert history(facts, 'p2: Zapdos')['unsupported'] == ['transformed_stats_and_moves']
    _, facts = replay(changed, dex, [switch_out(), switch_back()])
    assert enemy(facts)['moves'] == ['transform']
    assert not history(facts, 'p2: Zapdos')['unsupported']


@pytest.mark.parametrize('copy_rows,expected', [
    (['|move|p2a: Zapdos|Mimic|p1a: Lokix', '|-start|p2a: Zapdos|Mimic|Ice Beam'], ['mimic']),
    (['|move|p2a: Zapdos|Transform|p1a: Lokix', '|-transform|p2a: Zapdos|p1a: Lokix',
      '|move|p2a: Zapdos|Ice Beam|p1a: Lokix'], ['transform'])])
def test_faint_clears_temporary_copy_for_inactive_reserve(case, dex, copy_rows, expected):
    _, facts = replay(case, dex, [*copy_rows, '|faint|p2a: Zapdos'])
    assert enemy(facts)['moves'] == expected
    assert enemy(facts)['active'] is False and not enemy(facts)['transformed']
    assert not enemy(facts)['temporary_replacements']


def test_trace_owner_native_and_switch_restore_override_observer(case, dex):
    changed, facts = replay(case, dex, [
        '|-ability|p2a: Zapdos|Tinted Lens|[from] ability: Trace|[of] p1a: Lokix'])
    assert enemy(facts)['ability'] == 'tintedlens' and enemy(facts)['baseAbility'] == 'trace'
    assert facts['pokemon']['p1: Lokix']['baseAbility'] == 'tintedlens'
    assert history(facts, 'p2: Zapdos')['initial_abilities'] == ['trace']
    changed, facts = replay(changed, dex, [switch_out()])
    assert enemy(facts)['ability'] == enemy(facts)['baseAbility'] == 'trace'
    changed, facts = replay(changed, dex, [switch_back()])
    assert enemy(facts)['ability'] == 'trace'
    raw = next(m for m in changed['official']['sides'][1]['pokemon'] if m['ident'] == 'p2: Zapdos')
    raw['ability'] = 'Tinted Lens'  # reproduce official stale-copy memory explicitly
    facts = reconstruct(changed['official'], changed['prefix'], actor='p1', dex=dex)
    projection, _ = apply(changed['payload'], facts, dex)
    assert next(m for m in projection['state']['opponent_team'] if m['active'])['ability'] == 'trace'


def test_skill_swap_public_owner_order_and_restoration(case, dex):
    changed, facts = replay(case, dex, [
        '|-activate|p2a: Zapdos|move: Skill Swap|Tinted Lens|Static|[of] p1a: Lokix'])
    assert enemy(facts)['ability'] == 'tintedlens' and enemy(facts)['baseAbility'] == 'static'
    assert facts['pokemon']['p1: Lokix']['ability'] == 'static'
    assert facts['pokemon']['p1: Lokix']['baseAbility'] == 'tintedlens'
    assert history(facts, 'p2: Zapdos')['initial_abilities'] == ['static']
    _, facts = replay(changed, dex, [switch_out(), switch_back()])
    assert enemy(facts)['ability'] == 'static'
    assert not history(facts, 'p2: Zapdos')['ability_changed']


def test_suppression_retains_underlying_identity_and_ends_on_switch(case, dex):
    changed, facts = replay(case, dex, ['|-ability|p2a: Zapdos|Static', '|-endability|p2a: Zapdos'])
    payload, _, audit = run(changed, dex)
    mon = next(m for m in payload['state']['opponent_team'] if m['active'])
    assert mon['ability']['knowledge'] == 'suppressed'
    assert mon['ability']['underlying_ability']['id'] == 'static'
    assert mon['baseAbility']['id'] == 'static'
    assert audit['damage']['normalized_active']['opponent']['ability'] == ''
    assert all(c['current_ability'] == '' for c in audit['damage']['candidates'])
    _, facts = replay(changed, dex, [switch_out(), switch_back()])
    assert enemy(facts)['ability'] == 'static' and not enemy(facts)['suppressed']


def test_ability_change_end_is_not_suppression(case, dex):
    _, facts = replay(case, dex, [
        '|-endability|p2a: Zapdos|Static|[from] move: Worry Seed',
        '|-ability|p2a: Zapdos|Insomnia|[from] move: Worry Seed'])
    assert enemy(facts)['ability'] == 'insomnia' and enemy(facts)['baseAbility'] == 'static'
    assert not enemy(facts)['suppressed']


@pytest.mark.parametrize('extra,expected', [
    ([], 'unknown'),
    (['|-block|p2a: Zapdos|item: Ability Shield'], False),
    (['|-item|p2a: Zapdos|Leftovers'], True),
    (['|-enditem|p2a: Zapdos|Leftovers|[from] move: Knock Off'], True)])
def test_neutralizing_gas_public_exceptions_no_hidden_shield_guess(case, dex, extra, expected):
    changed, facts = replay(case, dex, ['|-ability|p2a: Zapdos|Static',
        '|-ability|p1a: Lokix|Neutralizing Gas', *extra])
    assert enemy(facts)['suppressed'] == expected
    if expected == 'unknown':
        payload, _, audit = run(changed, dex)
        assert payload['state']['speed_comparison']['status'] == 'unavailable'
        assert 'suppression_unresolved' in payload['state']['speed_comparison']['reason']
        assert not audit['damage']['calculations']
    _, ended = replay(changed, dex, ['|-end|p1a: Lokix|ability: Neutralizing Gas'])
    assert enemy(ended)['suppressed'] is False


def test_unsuppressible_public_ability_and_no_implicit_activation(case, dex):
    _, facts = replay(case, dex, ['|-ability|p2a: Zapdos|Multitype',
        '|-ability|p1a: Lokix|Neutralizing Gas'])
    assert enemy(facts)['suppressed'] is False
    assert not any(e['field'] == 'activation' for e in enemy(facts)['evidence'])


@pytest.mark.parametrize('start,end', [
    ('|-start|p2a: Zapdos|Embargo', '|-end|p2a: Zapdos|Embargo'),
    ('|-fieldstart|move: Magic Room', '|-fieldend|move: Magic Room')])
def test_public_item_suppression_disables_shield_without_guessing(case, dex, start, end):
    changed, facts = replay(case, dex, ['|-ability|p2a: Zapdos|Static',
        '|-ability|p1a: Lokix|Neutralizing Gas', '|-block|p2a: Zapdos|item: Ability Shield', start])
    assert enemy(facts)['item'] == 'abilityshield' and enemy(facts)['suppressed'] is True
    _, facts = replay(changed, dex, [end])
    assert enemy(facts)['suppressed'] is False


def test_form_change_does_not_disclose_observer_default_ability(case, dex):
    changed, facts = replay(case, dex, ['|-ability|p2a: Zapdos|Static',
        '|detailschange|p2a: Zapdos|Zapdos-Galar'])
    assert next(m for m in changed['official']['sides'][1]['pokemon'] if m['active'])['ability'] == 'Defiant'
    assert enemy(facts)['ability'] == enemy(facts)['baseAbility'] == 'unknown'
    assert 'public_form_ability_unknown' in history(facts, 'p2: Zapdos')['unsupported']
    _, facts = replay(changed, dex, ['|-ability|p2a: Zapdos|Defiant'])
    assert enemy(facts)['ability'] == enemy(facts)['baseAbility'] == 'defiant'
    assert history(facts, 'p2: Zapdos')['initial_abilities'] == ['static']


def test_zero_rounded_hp_and_unknown_preview(case, dex):
    changed, facts = replay(case, dex, ['|-damage|p2a: Zapdos|1/100',
        '|-damage|p2a: Zapdos|0 fnt', '|faint|p2a: Zapdos'])
    projected, _ = apply(changed['payload'], facts, dex)
    zero = next(m for m in projected['state']['opponent_team'] if m['ident'] == 'p2: Zapdos')
    assert zero['hp']['current'] == 0 and zero['hp']['maximum'] == 100
    assert all(m['hp'] == 'unknown' and m['item'] == m['ability'] == 'unknown'
               for m in projected['state']['opponent_team'] if not m['ident'])


def test_mid_frame_cutoff_does_not_read_future_public_disclosure(case, dex):
    changed, facts = replay(case, dex, ['|move|p2a: Zapdos|Hurricane|p1a: Lokix'])
    assert enemy(facts)['moves'] == ['hurricane'] and enemy(facts)['item'] == 'unknown'
    unbounded = copy.deepcopy(changed['prefix'])
    unbounded[-1]['protocol'] += '\n|-item|p2a: Zapdos|Choice Scarf'
    with pytest.raises(ValueError, match='cutoff'):
        reconstruct(changed['official'], unbounded, actor='p1', dex=dex)


@pytest.mark.parametrize('side_name', ['opposing-trainer', 'Zapdos'])
@pytest.mark.parametrize('condition', ['Spikes', 'move: Stealth Rock', 'move: Reflect', 'move: Tailwind'])
def test_sidewide_rows_never_identify_pokemon_even_when_trainer_matches_nickname(case, dex, side_name, condition):
    _, facts = replay(case, dex, [f'|-sidestart|p2: {side_name}|{condition}',
        '|-swapsideconditions', f'|-sideend|p1: own-trainer|{condition}'])
    assert set(facts['pokemon']) == {'p1: Lokix', 'p2: Zapdos'}
    assert enemy(facts)['ability'] == enemy(facts)['baseAbility'] == 'unknown'
    assert enemy(facts)['item'] == 'unknown' and not enemy(facts)['moves']


@pytest.mark.parametrize('line,holder,ability', [
    ('|-weather|RainDance|[from] ability: Drizzle|[of] p2a: Zapdos', 'p2: Zapdos', 'drizzle'),
    ('|-fieldstart|move: Electric Terrain|[from] ability: Electric Surge|[of] p1a: Lokix', 'p1: Lokix', 'electricsurge'),
])
def test_field_ability_disclosure_belongs_only_to_explicit_pokemon_source(case, dex, line, holder, ability):
    _, facts = replay(case, dex, [line])
    assert set(facts['pokemon']) == {'p1: Lokix', 'p2: Zapdos'}
    assert facts['pokemon'][holder]['ability'] == facts['pokemon'][holder]['baseAbility'] == ability
    other = next(key for key in facts['pokemon'] if key != holder)
    assert facts['pokemon'][other]['ability'] == 'unknown'


def test_field_without_disclosed_holder_does_not_infer_an_ability(case, dex):
    _, facts = replay(case, dex, ['|-weather|RainDance', '|-weather|none',
        '|-fieldstart|move: Electric Terrain', '|-fieldactivate|move: Perish Song',
        '|-fieldend|move: Electric Terrain'])
    assert set(facts['pokemon']) == {'p1: Lokix', 'p2: Zapdos'}
    assert all(mon['ability'] == mon['baseAbility'] == 'unknown' for mon in facts['pokemon'].values())


def test_non_state_text_cannot_disclose_a_pokemon_ability(case, dex):
    _, facts = replay(case, dex, [
        '|-message|p2: Zapdos|[from] ability: Static',
        '|c|p2: fake-trainer|[from] ability: Drizzle|[of] p2a: Zapdos'])
    assert set(facts['pokemon']) == {'p1: Lokix', 'p2: Zapdos'}
    assert enemy(facts)['ability'] == enemy(facts)['baseAbility'] == 'unknown'


def test_current_calculations_set_filter_and_display_share_same_facts(case, dex):
    changed, _ = replay(case, dex, ['|move|p2a: Zapdos|Hurricane|p1a: Lokix',
        '|-ability|p2a: Zapdos|Static', '|-item|p2a: Zapdos|Heavy-Duty Boots',
        '|-enditem|p2a: Zapdos|Heavy-Duty Boots|[from] move: Knock Off'])
    payload, commands, audit = run(changed, dex)
    mon = next(m for m in payload['state']['opponent_team'] if m['active'])
    normalized = audit['damage']['normalized_active']['opponent']
    assert mon['item'] == {'knowledge': 'confirmed_absent'} and normalized['item'] is None
    assert mon['ability']['id'] == normalized['ability'] == 'static'
    assert [m['id'] for m in mon['moves']] == normalized['moves'] == ['hurricane']
    assert audit['damage']['candidates']
    assert all(c['current_item'] == '' and c['current_ability'] == 'static' for c in audit['damage']['candidates'])
    assert all(m['active'] for team in ('self', 'opponent') for m in [audit['damage']['normalized_active'][team]])
    assert list(commands) == list(case['payload']['questions']['action']['criteria'])
    assert 'public_facts' not in json.dumps(payload) and 'protocol' not in json.dumps(mon)


@pytest.mark.parametrize('violation', ['future', 'foreign', 'split', 'reorder', 'identity'])
def test_cutoff_private_and_identity_fail_closed(case, dex, violation):
    changed = copy.deepcopy(case)
    if violation == 'future':
        changed['prefix'][-1]['protocol'] += '\n|-item|p2a: Zapdos|Choice Scarf'
    elif violation == 'foreign':
        bad = copy.deepcopy(changed['official']['request'])
        bad['side']['id'] = 'p2'
        changed['prefix'][0]['protocol'] += '\n|request|' + json.dumps(bad)
        changed['official']['consumed'] += 1
    elif violation == 'split':
        changed['prefix'][0]['protocol'] += '\n|split|p2'
        changed['official']['consumed'] += 1
    elif violation == 'reorder':
        changed['prefix'][1]['event_seq'] = changed['prefix'][0]['event_seq']
    else:
        changed['official']['sides'][1]['pokemon'].append(copy.deepcopy(changed['official']['sides'][1]['pokemon'][0]))
    with pytest.raises(ValueError):
        reconstruct(changed['official'], changed['prefix'], actor='p1', dex=dex)


def test_same_nickname_different_individual_and_illusion_rejected(case, dex):
    for line in ('|switch|p2a: Zapdos|Hydrapple, M|100/100',
                 '|replace|p2a: Zapdos|Zoroark, M|100/100'):
        changed = copy.deepcopy(case)
        changed['prefix'][-1]['protocol'] = line + '\n' + changed['prefix'][-1]['protocol']
        changed['official']['consumed'] += 1
        with pytest.raises(ValueError):
            reconstruct(changed['official'], changed['prefix'], actor='p1', dex=dex)


@pytest.mark.parametrize('name', ['lead-1', 'lead-2', 'turn-sample-01', 'forced-switch'])
@pytest.mark.parametrize('version', ['v4', 'v5'])
def test_archived_payload_commands_candidate_order_and_formatter_unchanged(dex, name, version):
    source = SAVED / name
    case = json.loads((source / 'source.json').read_text())
    module = jev_v4 if version == 'v4' else jev_v5
    adapter = module.Adapter(dex)
    try:
        payload, commands, _ = adapter.generate(case['official'], case['prefix'], case['own_team'], actor=case['actor'])
    finally:
        adapter.close()
    expected = json.loads((source / ('after-detailed.json' if version == 'v4' else 'after-compact.json')).read_text())
    expected['state']['version'] = module.VERSION
    assert payload == expected
    assert commands == json.loads((source / 'commands.json').read_text())
    assert list(payload['questions']['action']['criteria']) == list(expected['questions']['action']['criteria'])
    assert format_request(payload) == format_request(expected)


@pytest.mark.parametrize('name,count', [('lead-1', 6), ('turn-sample-01', 13), ('forced-switch', 5)])
def test_v6_saved_case_candidates_self_details_and_audit_boundaries(dex, name, count):
    source = SAVED / name
    case = json.loads((source / 'source.json').read_text())
    payload, commands, audit = run(case, dex)
    previous = json.loads((source / 'after-detailed.json').read_text())
    assert payload['state']['self_team'] == previous['state']['self_team']
    assert payload['questions']['action']['criteria'] == previous['questions']['action']['criteria']
    assert len(commands) == count
    assert payload['state']['version'] == jev_v6.VERSION
    assert payload['questions']['action']['instructions'] == jev_v6.PROMPT.read_text()
    assert audit['public_facts']['prefix_sha256']
    assert audit['official'] == case['official'] and audit['prefix'] == case['prefix']
