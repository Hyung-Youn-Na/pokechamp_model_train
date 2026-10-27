"""Lossless relocation of observed facts, move metadata and damage branches."""
from copy import deepcopy
from pathlib import Path

VERSION = 'jev-choice-v7'
PROFILE = 'candidate-action-v1'
INFORMATION_RULES = 'unknown means unavailable evidence; confirmed_absent means verified absence. Empty status means no major status; false terastallized means not used on this Pokemon. General effects and species roles are rules/possibilities, not observed activation or hidden sets. Opponent bench moves/items/abilities retain public disclosures across turns. Moves describe current publicly known slots after temporary/permanent copying; no opponent PP is inferred. baseAbility is the publicly known native identity; suppressed is a current effect state, and suppressed=unknown leaves activation unresolved. Known identity alone does not prove activation. Bench HP is the last public observation, without inferred private recovery.'
PROMPT = Path(__file__).with_name('prompt.txt')
# Only these exact, invariant annotations are shortened. Exceptions remain verbatim.
COMMON = {
    'roles': 'Conditional capabilities; not a current role or guaranteed matchup.',
    'matchup': 'Current opponent unchanged; selected own Tera included; no opponent switch/Tera or other intervening state changes.',
    'damage': 'Copied v6 calculation, conditional on hits and finite compatible recommended sets; zero does not identify an immunity cause.',
    'types': 'type chart plus supported move-specific type rule; excludes item/ability/grounding overrides',
    'success': 'Unknown is not evidence of bypass; no_known_blocker does not guarantee execution or success.',
    'status': 'Status component only; a damaging move can still deal damage when its status is blocked.',
    'bypass': 'Unknown is not evidence that an immunity is bypassed.',
}


def annotations(value, *, restore=False):
    mapping = {'@'+k: v for k, v in COMMON.items()} if restore else {v: '@'+k for k, v in COMMON.items()}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('scope', 'note') and isinstance(item, str):
                value[key] = mapping.get(item, item)
            else:
                annotations(item, restore=restore)
    elif isinstance(value, list):
        for item in value:
            annotations(item, restore=restore)


def transform(payload):
    if payload['state']['version'] != 'jev-choice-v6':
        raise ValueError('candidate-action requires v6 with candidate-matchup-v1')
    result = deepcopy(payload)
    state = result['state']
    if state.pop('information_rules') != INFORMATION_RULES:
        raise ValueError('unregistered information rules; cannot silently remove')
    state['version'] = VERSION
    state['input_profile'] = PROFILE
    question = result['questions']['action']
    question['instructions'] = PROMPT.read_text()
    moved = {}
    for candidate in question['criteria'].values():
        if candidate['kind'] != 'move':
            continue
        ref = candidate['move_ref']
        mon, = [m for m in state['self_team'] if m['slot'] == ref['self_team_slot']]
        move, = [m for m in mon['current_move_slots'] if m['slot'] == ref['current_move_slot']]
        if candidate['slot'] != move['slot'] or 'current_matchup' not in candidate:
            raise ValueError('move/profile identity mismatch')
        candidate['move'] = deepcopy(move)
        damage = candidate['move'].pop('damage', None)
        if damage is not None:
            branch = 'self_tera' if candidate['terastallize'] else 'current'
            ranges = damage.pop('ranges')
            candidate['damage'] = dict(selected_branch=branch,
                selected_range=({branch: ranges[branch]} if branch in ranges else {}) if isinstance(ranges, dict) else None,
                other_assumptions={k: v for k, v in ranges.items() if k != branch} if isinstance(ranges, dict) else ranges,
                **damage)
        moved.setdefault(mon['slot'], set()).add(move['slot'])
    for mon in state['self_team']:
        if mon['slot'] in moved:
            mon['current_move_slots'] = [m for m in mon['current_move_slots'] if m['slot'] not in moved[mon['slot']]]
    annotations(result)
    return result


def restore(payload):
    """Reconstruct EX112's input from model-visible v7 alone, without audit files."""
    from integration.pokechamp.jev_v6 import PROMPT as OLD_PROMPT
    result = deepcopy(payload)
    if result['state']['version'] != VERSION or result['state'].pop('input_profile') != PROFILE:
        raise ValueError('unexpected profile')
    result['state']['version'] = 'jev-choice-v6'
    result['state']['information_rules'] = INFORMATION_RULES
    result['questions']['action']['instructions'] = OLD_PROMPT.read_text()
    annotations(result, restore=True)
    moved = {}
    for candidate in result['questions']['action']['criteria'].values():
        if candidate['kind'] != 'move':
            continue
        ref = candidate['move_ref']
        move = candidate.pop('move')
        if 'damage' in candidate:
            damage = candidate.pop('damage')
            damage.pop('selected_branch')
            selected = damage.pop('selected_range')
            other = damage.pop('other_assumptions')
            damage['ranges'] = {**selected, **other} if isinstance(other, dict) else other
            move['damage'] = damage
        key = (ref['self_team_slot'], ref['current_move_slot'])
        if key in moved and moved[key] != move:
            raise ValueError('ordinary/Tera move information differs')
        moved[key] = move
    for mon in result['state']['self_team']:
        slots = [move for (slot, _), move in moved.items() if slot == mon['slot']]
        if slots:
            mon['current_move_slots'] = sorted(mon['current_move_slots'] + slots, key=lambda m: m['slot'])
    return result
