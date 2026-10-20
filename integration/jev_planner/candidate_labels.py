"""Decision-local readable candidate names; execution continues to use original IDs."""
from __future__ import annotations

import copy

ORIGINAL = 'original'
NAMED = 'names-v1'


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() and value != 'unknown' else None


def _slot(rows, number):
    if not isinstance(rows, list) or type(number) is not int or number < 1:
        return None
    matches = [row for row in rows if isinstance(row, dict)
               and type(row.get('slot')) is int and row['slot'] == number]
    return matches[0] if len(matches) == 1 else None


def _pokemon(mon):
    return (_text(mon.get('species')) or _text(mon.get('nickname'))) if isinstance(mon, dict) else None


def display_name(state, candidate):
    """Resolve only current supplied fields, including temporary current move slots."""
    team = state.get('self_team', [])
    kind, number = candidate.get('kind'), candidate.get('slot')
    slot_text = str(number) if type(number) is int and number > 0 else '?'
    if kind in ('team', 'switch'):
        name = _pokemon(_slot(team, number)) or _text(candidate.get('pokemon'))
        name = name or f'Unknown Pokemon (slot {slot_text})'
        return ('Lead: ' if kind == 'team' else 'Switch to ') + name
    if kind == 'move':
        ref = candidate.get('move_ref')
        if isinstance(ref, dict):
            owner = _slot(team, ref.get('self_team_slot'))
            move_slot = ref.get('current_move_slot')
        else:
            active = [mon for mon in team if isinstance(mon, dict) and mon.get('active') is True]
            owner = active[0] if len(active) == 1 else None
            move_slot = number
        move = _slot(owner.get('current_move_slots', []), move_slot) if owner else None
        supplied = candidate.get('move')
        name = ((_text(move.get('name')) or _text(move.get('move'))) if move else None)
        if name is None and isinstance(supplied, dict):
            name = _text(supplied.get('name')) or _text(supplied.get('move'))
        # Some saved technical fixtures provide a name directly on the option.
        name = name or _text(candidate.get('name')) or f'Unknown move (slot {slot_text})'
        pokemon = _pokemon(owner)
        label = f'{pokemon} — {name}' if pokemon else name
        return label + (' · Terastallize' if candidate.get('terastallize') is True else '')
    return f'Unknown action (slot {slot_text})'


def candidate_input(payload, config):
    """Add display text without mutating the original observation or candidate ordering."""
    result = copy.deepcopy(payload)
    mode = config.get('executor', {}).get('candidate_display', ORIGINAL)
    if mode == ORIGINAL:
        return result
    if mode != NAMED:
        raise ValueError('unknown candidate display profile')
    state = result['state']
    for candidate in result['questions']['action']['criteria'].values():
        candidate['display_name'] = display_name(state, candidate)
    return result
