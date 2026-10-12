"""Lossless representation changes preserve facts, role text and exact wording."""
import copy
import json

import pytest

from integration.pokechamp.candidate_descriptions import compact, expand


def test_shared_long_descriptions_preserve_exact_original_and_json_order():
    effect = 'First sentence.\n  Keep spacing, Unicode: 방어. ' * 3
    payload = {'state': {'version': 'qwen-candidate-state-v1', 'self_team': [
        {'species': 'Zamazenta', 'hp': 140, 'general_effect': effect, 'boosts': {'def': 1}},
        {'species': 'Tinkaton', 'ability': {'general_effect': effect, 'id': 'moldbreaker'}, 'hp': 20}],
        'opponent_team': [{'species': 'Cinderace', 'hp_percent': 22}],
        'role_summary': {'roles': [{'description': effect}], 'scope': 'Conditional capability.'}},
        'questions': {'action': {'instructions': 'Original contract unchanged.',
            'criteria': {'move_1': {'kind': 'move', 'name': 'Close Combat', 'slot': 1}}}}}
    before = copy.deepcopy(payload)
    result = compact(payload)
    assert payload == before and result is not payload
    assert result['state']['effect_descriptions'] == {'e0': effect}
    assert result['state']['self_team'][0]['general_effect_ref'] == 'e0'
    assert result['state']['self_team'][1]['ability']['general_effect_ref'] == 'e0'
    assert result['state']['role_summary'] == payload['state']['role_summary']
    assert result['state']['opponent_team'] == payload['state']['opponent_team']
    assert result['questions'] == payload['questions']
    assert expand(result) == payload
    assert json.dumps(expand(result), ensure_ascii=False) == json.dumps(payload, ensure_ascii=False)
    assert compact(result) == result


def test_only_exact_repeated_long_general_effect_strings_are_interned():
    repeated = 'A detailed effect rule. ' * 5
    near_match = repeated + ' '
    unique = 'An entirely different long rule. ' * 5
    payload = {'state': {'records': [{'general_effect': repeated}, {'general_effect': repeated},
        {'general_effect': near_match}, {'general_effect': unique}, {'general_effect': 'short'},
        {'general_effect': 'short'}, {'description': repeated}, {'name': repeated},
        {'general_effect': {'knowledge': 'unknown'}}]}}
    result = compact(payload)
    assert result['state']['effect_descriptions'] == {'e0': repeated}
    for index in range(2, 9):
        assert result['state']['records'][index] == payload['state']['records'][index]
    assert expand(result) == payload


def test_no_repeats_returns_independent_unchanged_payload():
    payload = {'state': {'general_effect': 'one unique long general rule ' * 8, 'damage': [27.6, 39.1]}}
    result = compact(payload)
    assert result == payload and 'effect_descriptions' not in result['state']
    result['state']['damage'][0] = 0
    assert payload['state']['damage'][0] == 27.6


def test_role_wording_is_shared_only_in_team_roles_with_ids_and_knowledge_intact():
    scope = 'Conditional capabilities; not a current role or guaranteed matchup.'
    description = 'Checks an opposing threat under compatible move, item and type assumptions.'
    own_role = {'knowledge': 'own_set_supported_capabilities',
                'roles': [{'id': 'special_wall', 'description': description}], 'scope': scope}
    other_role = {'knowledge': 'species_possibilities_not_observed_set',
                  'roles': [{'id': 'special_wall', 'description': description}], 'scope': scope}
    payload = {'state': {'self_team': [{'species': 'Ting-Lu', 'role_summary': own_role}],
                        'opponent_team': [{'species': 'Blissey', 'role_summary': other_role}]},
               'questions': {'action': {'criteria': {'switch_1': {'description': description}}}},
               'notes': {'role_summary': {'roles': [{'description': description}], 'scope': scope}}}
    before = copy.deepcopy(payload)
    result = compact(payload)
    assert payload == before
    assert result['state']['role_descriptions'] == {'r0': description, 'r1': scope}
    for team, original_role in [('self_team', own_role), ('opponent_team', other_role)]:
        role = result['state'][team][0]['role_summary']
        assert role['roles'] == [{'id': 'special_wall', 'description_ref': 'r0'}]
        assert role['scope_ref'] == 'r1' and role['knowledge'] == original_role['knowledge']
    assert result['questions'] == payload['questions'] and result['notes'] == payload['notes']
    assert expand(result) == payload
    assert json.dumps(expand(result)) == json.dumps(payload)
    assert compact(result) == result


def test_different_role_text_with_the_same_id_is_never_merged():
    descriptions = ['Different conditions.', 'Different conditions. ']
    payload = {'state': {'self_team': [{'role_summary': {
        'roles': [{'id': 'same_role', 'description': text}]}} for text in descriptions]}}
    assert compact(payload) == payload


def test_role_reference_cannot_resolve_from_an_effect_registry():
    payload = {'state': {'effect_descriptions': {'e0': 'An effect'}, 'self_team': [
        {'role_summary': {'roles': [{'id': 'wall', 'description_ref': 'e0'}]}}]}}
    with pytest.raises(ValueError, match='unresolved description_ref'):
        expand(payload)


@pytest.mark.parametrize('payload', [
    {'state': {'effect_descriptions': {'e0': 'text'}, 'entry': {'general_effect_ref': 'missing'}}},
    {'state': {'entry': {'general_effect_ref': 'e0'}}},
    {'state': {'effect_descriptions': {'e0': 'text'}}},
    {'state': {'effect_descriptions': {'bad': 'text'}, 'entry': {'general_effect_ref': 'bad'}}},
    {'state': {'effect_descriptions': {'e0': 'text'},
               'entry': {'general_effect_ref': 'e0', 'general_effect': 'other'}}},
])
def test_invalid_or_ambiguous_registry_is_rejected(payload):
    before = copy.deepcopy(payload)
    with pytest.raises(ValueError):
        expand(payload)
    with pytest.raises(ValueError):
        compact(payload)
    assert payload == before
