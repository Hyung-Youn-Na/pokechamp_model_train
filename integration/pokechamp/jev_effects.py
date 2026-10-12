"""JEV-specific visible reference projection onto the pinned Gen9 dictionary."""
from . import effects


def references(state, criteria):
    """Read only named JEV fields; reuse the pinned public protocol grammar.

    Never traverse candidate flags, species, prose, or descriptions as effects.
    Request slots and candidate move objects use stable IDs, not display names.
    """
    visible = []
    for team in ('self_team', 'opponent_team'):
        for mon in state[team]:
            visible.append({k: mon[k] for k in ('item', 'ability', 'baseAbility') if k in mon})
            visible.append({'moves': [m['id'] for m in mon['moves']]})
            visible.append({'moves': [
                {k: m[k] for k in ('id', 'disabledSource') if k in m}
                for m in mon.get('current_move_slots', [])]})
            for field in ('volatiles', 'turnstatuses', 'movestatuses'):
                value = mon.get(field)
                if isinstance(value, dict):
                    visible.append({'effects': dict.fromkeys(value)})
    visible.extend({'move': candidate['move']['id']} for candidate in criteria.values()
                   if candidate['kind'] == 'move')
    for field in ('weather', 'field'):
        value = state[field]
        if isinstance(value, dict):
            visible.append({'effects': dict.fromkeys(value)})
        elif isinstance(value, str):
            visible.append({'effect': value})
    for conditions in state['side_conditions'].values():
        visible.append({'effects': dict.fromkeys(conditions)})
    visible.extend(state['recent_completed_turn_events'])
    yield from effects.references(visible)


def build(state, criteria):
    asset, _ = effects._asset()
    keys = {kind: set() for kind in effects.KINDS}
    for kind, key, _ in references(state, criteria):
        keys[kind].add(key)
    result = {}
    for kind in effects.KINDS:
        result[kind] = {}
        for key in sorted(keys[kind]):
            entry = asset[kind][key]
            if not all(isinstance(entry.get(field), str) and entry[field].strip()
                       for field in ('name', 'desc')):
                raise effects.EffectReferenceError('state.effect_reference', kind, key)
            result[kind][key] = {field: entry[field] for field in ('name', 'desc')}
    return result


def without_pp_source(value):
    """Keep provenance outside the model payload, including nested request slots."""
    if isinstance(value, dict):
        return {key: without_pp_source(child) for key, child in value.items()
                if key != 'current_pp_source'}
    if isinstance(value, list):
        return [without_pp_source(child) for child in value]
    return value
