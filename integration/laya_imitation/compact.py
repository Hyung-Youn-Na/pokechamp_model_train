"""laya-compact-v1: render an EX-071 `ImitationInput` as a short text state plus a choice question.

The renderer is a pure function of the model-boundary body that `schema.ImitationInput` already
validated (C-055), so offline rows and live requests produce identical text. Static knowledge
(effect prose, set spreads, the type chart) is not written out; per-candidate type/power/multiplier
facts are derived from the pinned `dex_gen9.json`.
"""
from __future__ import annotations
import json
import re

from integration.pokechamp.imitation.schema import ImitationInput

from . import dex
from .config import RENDER_VERSION

INSTRUCTIONS = 'Pick the action a strong player would choose for me in this Gen 9 OU singles battle.'
HISTORY_TURNS = 2
SKIP_EVENTS = {'turn', 'upkeep'}
FLAGS = {'-supereffective': 'super-effective', '-resisted': 'resisted', '-immune': 'immune', '-crit': 'crit',
         '-miss': 'missed', '-fail': 'failed', 'faint': 'fainted', '-clearboost': 'boosts cleared'}
STATS = ('atk', 'def', 'spa', 'spd', 'spe', 'accuracy', 'evasion')


def _who(value):
    return {'@self': 'me', '@opponent': 'opp', 'self': 'my side', 'opponent': 'opp side'}.get(value, value)


def _name(value):
    """'move: Protect' / '[from] item: Life Orb' / 'Slowking-Galar, F' -> the bare name."""
    value = re.sub(r'^\[(from|of)\]\s*', '', str(value))
    value = value.split(': ', 1)[-1]
    return value.split(',')[0].strip()


def _hp(value):
    """'23/100 tox' -> '23% tox', '0 fnt' -> '0%'."""
    parts = str(value).split()
    head = parts[0].split('/')[0] + '%'
    tail = [p for p in parts[1:] if p != 'fnt']
    return ' '.join([head] + tail)


def _event(e):
    name, args = e['event'], e['args']
    if name in SKIP_EVENTS or '[silent]' in args or '[upkeep]' in args:
        return None
    who = _who(args[0]) if args else ''
    source = next((_name(a) for a in args if str(a).startswith('[from]')), None)
    suffix = ' (%s)' % source if source else ''
    if name == 'move':
        target = _who(args[2]) if len(args) > 2 and args[2] not in ('', args[0]) else None
        return '%s %s%s' % (who, args[1], ' -> ' + target if target else '')
    if name in ('switch', 'drag'):
        return '%s in %s %s' % (who, _name(args[1]), _hp(args[2]) if len(args) > 2 else '')
    if name in ('-damage', '-heal', '-sethp'):
        return '%s %s%s' % (who, _hp(args[1]), suffix)
    if name in FLAGS:
        return '%s %s' % (who, FLAGS[name])
    if name in ('-boost', '-unboost'):
        return '%s %s%s%s' % (who, args[1], '+' if name == '-boost' else '-', args[2])
    if name == '-status':
        return '%s %s%s' % (who, args[1], suffix)
    if name == '-curestatus':
        return '%s cured %s' % (who, args[1])
    if name == '-weather':
        return 'weather %s' % args[0]
    if name in ('-sidestart', '-sideend'):
        return '%s %s %s' % (who, '+' if name == '-sidestart' else '-', _name(args[1]))
    if name in ('-fieldstart', '-fieldend'):
        return 'field %s %s' % ('+' if name == '-fieldstart' else '-', _name(args[0]))
    if name == '-terastallize':
        return '%s tera %s' % (who, args[1])
    if name in ('-ability', '-item', '-enditem'):
        verb = {'-ability': 'ability', '-item': 'item', '-enditem': 'lost'}[name]
        return '%s %s %s%s' % (who, verb, _name(args[1]), suffix if name != '-ability' else '')
    rest = ' '.join(_name(a) for a in args[1:2])
    return ('%s %s %s' % (who, name.lstrip('-'), rest)).strip()


def _history(snapshot):
    keep = snapshot['turn'] - HISTORY_TURNS + 1
    turns = {}
    for e in snapshot['history']:
        if e['turn'] >= keep:
            text = _event(e)
            if text:
                turns.setdefault(e['turn'], []).append(text)
    return ['T%d: %s' % (t, '; '.join(items)) for t, items in sorted(turns.items())]


def _boosts(mon):
    return ' '.join('%s%+d' % (k, mon['boosts'][k]) for k in STATS if mon['boosts'].get(k))


def _types(mon):
    if mon['terastallized'] and mon['tera_type'] and mon['tera_type'] != 'stellar':
        return [mon['tera_type']]
    return list(mon['types'])


def _hp_text(mon):
    if mon['status'] == 'fnt':
        return 'fainted'
    hp = '?' if mon['hp_percent'] is None else '%g%%' % mon['hp_percent']
    return hp + (' ' + mon['status'] if mon['status'] else '')


def _mon(mon, *, own, active):
    parts = ['%s [%s] %s' % (mon['species'], ' '.join(_types(mon)), _hp_text(mon))]
    if mon['status'] == 'fnt':
        return parts[0]
    unknown = '?' if not own else 'none'
    parts.append('ability ' + (mon['ability'] or unknown))
    parts.append('item ' + (mon['item'] or unknown))
    if own or mon['tera_type']:
        tera = mon['tera_type'] or '?'
        parts.append(('terastallized ' if mon['terastallized'] else 'tera ') + tera)
    if active:
        if _boosts(mon):
            parts.append('boosts ' + _boosts(mon))
        if mon['effects']:
            parts.append('effects ' + ' '.join(sorted(mon['effects'])))
    moves = [m['id'] for m in mon['moves']]
    if moves:
        parts.append(('moves ' if own else 'seen ') + ' '.join(moves))
    return ' | '.join(parts)


def _conditions(values):
    out = []
    for key, value in sorted(values.items()):
        layers = value if key in ('spikes', 'toxic_spikes') and isinstance(value, int) else None
        out.append(key + (str(layers) if layers else ''))
    return ' '.join(out) or 'none'


def _move_text(move_id, user, opponent, tera):
    facts = dex.load()['moves'].get(move_id)
    if facts is None:
        return 'unknown move'
    if facts['category'] == 'status':
        text = '%s status' % facts['type']
    else:
        types = [tera] if tera and tera != 'stellar' else _types(user)
        stab = facts['type'] in types or (tera and facts['type'] in user['types'])
        mult = dex.multiplier(facts['type'], _types(opponent)) if opponent else None
        text = '%s %s %d%s%s' % (facts['type'], facts['category'], facts['power'],
                                 ' x%g' % mult if mult is not None else '', ' STAB' if stab else '')
    if facts['priority']:
        text += ' priority%+d' % facts['priority']
    return text


def _switch_text(mon, opponent):
    text = '%s [%s] %s' % (mon['species'], ' '.join(_types(mon)), _hp_text(mon))
    if opponent is not None:
        taken = ' '.join('%s x%g' % (t, m) for t in _types(opponent)
                         for m in [dex.multiplier(t, _types(mon))] if m is not None)
        text += '; takes ' + taken
    return text


def render(value):
    """`ImitationInput` -> (state text, laya choice question). Raises on anything outside the boundary."""
    if not isinstance(value, ImitationInput):
        raise TypeError('render takes a validated ImitationInput')
    body = value.body
    snapshot = json.loads(body['state'])['snapshot']
    own = {m['slot']: m for m in snapshot['own_team']}
    opp = {m['slot']: m for m in snapshot['opponent_team']}
    me = own.get(snapshot['own_active_slot']) if snapshot['own_active_slot'] else None
    foe = opp.get(snapshot['opponent_active_slot']) if snapshot['opponent_active_slot'] else None
    lines = ['turn %d | %s | my tera %s | opp tera %s | weather %s | field %s' % (
        snapshot['turn'], snapshot['decision_kind'], 'ready' if snapshot['can_tera'] else 'used',
        'ready' if snapshot['opponent_can_tera'] else 'used', snapshot['weather'] or 'none',
        ' '.join(sorted(snapshot['field'])) or 'none')]
    lines.append('my side: %s | opp side: %s' % (_conditions(snapshot['own_side_conditions']),
                                                 _conditions(snapshot['opponent_side_conditions'])))
    if me is not None:
        lines.append('ME ' + _mon(me, own=True, active=True))
    if foe is not None:
        lines.append('OPP ' + _mon(foe, own=False, active=True))
    lines.append('my team: ' + ' || '.join(_mon(m, own=True, active=False)
                                         for s, m in sorted(own.items()) if m is not me))
    lines.append('opp team: ' + ' || '.join(_mon(m, own=False, active=False)
                                          for s, m in sorted(opp.items()) if m is not foe))
    lines.extend(_history(snapshot))
    criteria = {}
    for action_id in body['questions']['action']['criteria']:
        kind, *rest = action_id.split(':')
        if kind == 'move':
            tera = None
            if rest[1] == 'tera':
                tera = me['original_set'].get('teraType', me['tera_type'])
            text = _move_text(rest[0], me, foe, tera)
            criteria[action_id] = text + ('; terastallize ' + str(tera) if tera else '')
        else:
            criteria[action_id] = _switch_text(own[int(rest[0])], foe if kind != 'lead' else None)
    question = {'type': 'choice', 'instructions': INSTRUCTIONS, 'criteria': criteria}
    return '\n'.join(lines), question


def version():
    return dict(render=RENDER_VERSION, dex_sha256=dex.digest())
