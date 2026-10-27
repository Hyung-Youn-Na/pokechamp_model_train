"""laya-compact-v2: v1 text plus optional information modules, rendered from precomputed facts.

`render(value, features, facts)` with `features` a subset of MODULES. With no module the output is exactly
v1 `compact.render(value)`. Each module only rewrites or appends its own segments, so any combination can
be rendered from the same `features.compute` facts (cached per input for datasets, computed live in serving).
"""
from __future__ import annotations
import json

from . import compact
from . import dex_v2

MODULES = ('damage', 'moves', 'speed', 'switch')


def version_name(features):
    features = normalize(features)
    return 'laya-compact-v2[%s]' % ','.join(features)


def normalize(features):
    features = tuple(sorted(set(features)))
    unknown = set(features) - set(MODULES)
    if unknown:
        raise ValueError('unknown v2 modules: %s' % sorted(unknown))
    return features


ORDER = {'first': 'faster', 'second': 'slower', 'likely first': 'faster?', 'likely second': 'slower?', 'tie': 'tie?'}


def _pct(value):
    return '%d' % round(value)


def _move_text(fact, v1_text):
    if fact['category'] == 'status':
        text = '%s status' % fact['type']
    else:
        mult = fact.get('mult')
        text = '%s %s %d%s%s' % (fact['type'], fact['category'], fact['power'],
                                 ' x%g' % mult if mult is not None else '',
                                 {0: '', 1: ' STAB', 2: ' STABx2'}[fact['stab']])
    if fact['priority']:
        text += ' priority%+d' % fact['priority']
    if fact['reasons']:
        text += ' (%s)' % ', '.join(fact['reasons'])
    tera = v1_text.split('; terastallize ', 1)
    return text + ('; terastallize ' + tera[1] if len(tera) == 2 else '')


def _damage_move(d, hp):
    if d is None:
        return ''
    if 'error' in d:
        return '; dmg ?'
    hp = 100 if hp is None else hp
    ko = ''
    if d['min'] >= hp:
        ko = ' KO'
    elif d['max'] >= hp:
        ko = ' KO?'
    elif 2 * d['min'] >= hp:
        ko = ' 2HKO'
    return '; dmg %s-%s%%%s' % (_pct(d['min']), _pct(d['max']), ko)


def _speed_line(s):
    if s['me'] is None or s['opp'] is None:
        return None
    o = s['opp']
    return 'speed: me %d vs opp %d-%d est %d -> %s%s' % (s['me'], o['lo'], o['hi'], o['est'], ORDER[s['order']],
                                                       ' (trick room)' if s['trick_room'] else '')


def render(value, features=(), facts=None):
    """`ImitationInput` + module set + facts -> (state text, laya choice question)."""
    features = normalize(features)
    state, question = compact.render(value)
    if not features:
        return state, question
    if facts is None:
        raise ValueError('v2 modules need precomputed facts')
    lines = state.split('\n')
    if 'speed' in features:
        line = _speed_line(facts['speed'])
        if line:
            lines.insert(2, line)
    snapshot = json.loads(value.body['state'])['snapshot']
    opp = {m['slot']: m for m in snapshot['opponent_team']}
    foe = opp.get(snapshot['opponent_active_slot']) if snapshot['opponent_active_slot'] else None
    foe_hp = foe['hp_percent'] if foe is not None else None
    criteria = {}
    for action_id, text in question['criteria'].items():
        kind = action_id.split(':')[0]
        if kind == 'move':
            fact = facts['moves'].get(action_id)
            if 'moves' in features and fact is not None:
                text = _move_text(fact, text)
            if 'damage' in features:
                text += _damage_move(facts['damage'].get(action_id), foe_hp)
        elif kind == 'switch':
            sw = facts['switch'].get(action_id)
            if 'switch' in features and sw is not None:
                if sw['worst']:
                    text += '; worst x%g' % sw['worst']['mult']
                h = sw['hazards']
                if h['pct'] or h['extra']:
                    text += '; entry %s%%%s' % (_pct(h['pct']), ''.join(' ' + e for e in h['extra']))
            b = facts['speed']['bench'].get(action_id)
            if 'speed' in features and b is not None and b['spe'] is not None:
                text += '; ' + ORDER[b['order']] if b['order'] else ''
            d = facts['damage'].get(action_id)
            if 'damage' in features and d is not None:
                text += '; hit ?' if 'error' in d else '; hit %s-%s%%' % (_pct(d['min']), _pct(d['max']))
        criteria[action_id] = text
    return '\n'.join(lines), dict(question, criteria=criteria)


def version(features):
    return dict(render=version_name(features), dex_sha256=dex_v2.digest(), v1=compact.version())
