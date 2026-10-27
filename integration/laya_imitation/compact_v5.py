"""laya-compact-v5 (D-195): v4 text plus `items` and `counters` modules, from `features_v5.compute` facts.

`render(value, features, facts)` with `features` a subset of MODULES (v4's six plus `items`, `counters`). With no v5
module the output is exactly `compact_v4.render` for the same value and facts. v5 modules only rewrite their own
segments of the v1 text:
- `items`: opponent `item ?` becomes the held item (effect reveals included) or `item none (knocked off X)` /
  `item none (popped)` / `item none (used X)` / `item none (lost X)`; ground options get `; balloon?` when the foe's
  item is unknown and its assumed set holds Air Balloon (damage is then computed without it, see features_v5).
- `counters`: `slp t<n>` (`slp t<n> rest`) on sleeping mons and `tox t<n>` on the active mons, where n counts asleep
  move attempts / toxic ticks since switch-in; weather, field and timed side conditions get `t<n>` turns elapsed.
"""
from __future__ import annotations
import json
import re

from . import compact, compact_v4
from .features_v5 import has_fields

V5_MODULES = ('counters', 'items')
MODULES = tuple(sorted(compact_v4.MODULES + V5_MODULES))
TIMED_SIDE = ('aurora_veil', 'light_screen', 'reflect', 'tailwind')
REMOVED = {'knockoff': 'knocked off %s', 'popped': 'popped', 'consumed': 'used %s', 'other': 'lost %s'}


def normalize(features):
    features = tuple(sorted(set(features)))
    unknown = set(features) - set(MODULES)
    if unknown:
        raise ValueError('unknown v5 modules: %s' % sorted(unknown))
    return features


def version_name(features):
    return 'laya-compact-v5[%s]' % ','.join(normalize(features))


def item_text(state):
    if state['state'] == 'held':
        return state['item']
    if state['state'] == 'removed':
        text = REMOVED[state['cause']]
        return 'none (%s)' % (text % state['item'] if '%s' in text else text)
    return None


def _status_text(mon, active):
    counter = mon.get('status_counter')
    if counter is None or (mon['status'] == 'tox' and not active):
        return None
    return '%s t%d%s' % (mon['status'], counter, ' rest' if mon.get('status_source') == 'rest' else '')


def _rewrite_mon(text, mon, *, own, active, features):
    """One v1 `_mon` segment -> the same segment with v5 replacements (fainted segments carry no item/status)."""
    if mon['status'] == 'fnt':
        return text
    head, sep, rest = text.partition(' | ')
    if 'counters' in features:
        status = _status_text(mon, active)
        if status:
            head = re.sub(r' %s$' % mon['status'], ' ' + status, head)
    if 'items' in features and not own:
        item = item_text(mon['item_state'])
        if item is not None:
            rest = re.sub(r'(^| \| )item [^|]*?(?= \||$)', lambda m: m.group(1) + 'item ' + item, rest, count=1)
    return head + sep + rest


def _elapsed(turn, start):
    return ' t%d' % max(0, turn - int(start)) if isinstance(start, (int, float)) else ''


def _conditions(values, turn):
    out = []
    for key, value in sorted(values.items()):
        layers = value if key in ('spikes', 'toxic_spikes') and isinstance(value, int) else None
        out.append(key + (str(layers) if layers else '') + (_elapsed(turn, value) if key in TIMED_SIDE else ''))
    return ' '.join(out) or 'none'


def render(value, features=(), facts=None):
    """`ImitationInput` + module set + facts -> (state text, laya choice question)."""
    features = normalize(features)
    state, question = compact_v4.render(value, tuple(f for f in features if f in compact_v4.MODULES), facts)
    if not set(features) & set(V5_MODULES):
        return state, question
    snapshot = json.loads(value.body['state'])['snapshot']
    if not has_fields(snapshot):
        raise ValueError('v5 modules need the D-195 snapshot fields')
    if 'items' in features and (facts is None or 'v5' not in facts):
        raise ValueError('the items module needs features_v5 facts')
    own = {m['slot']: m for m in snapshot['own_team']}
    opp = {m['slot']: m for m in snapshot['opponent_team']}
    me = own.get(snapshot['own_active_slot']) if snapshot['own_active_slot'] else None
    foe = opp.get(snapshot['opponent_active_slot']) if snapshot['opponent_active_slot'] else None
    turn = snapshot['turn']
    lines = state.split('\n')
    for i, line in enumerate(lines):
        if i == 0 and 'counters' in features:
            head, sep, tail = line.partition(' | weather ')
            weather = snapshot['weather'] or 'none'
            fields = ' '.join(k + _elapsed(turn, v) for k, v in sorted(snapshot['field'].items())) or 'none'
            lines[i] = head + sep + weather + (_elapsed(turn, snapshot['weather_turn']) if snapshot['weather'] else '') \
                + ' | field ' + fields
        elif i == 1 and 'counters' in features and line.startswith('my side: '):
            lines[i] = 'my side: %s | opp side: %s' % (_conditions(snapshot['own_side_conditions'], turn),
                                                      _conditions(snapshot['opponent_side_conditions'], turn))
        elif line.startswith('ME ') and me is not None:
            lines[i] = 'ME ' + _rewrite_mon(line[3:], me, own=True, active=True, features=features)
        elif line.startswith('OPP ') and foe is not None:
            lines[i] = 'OPP ' + _rewrite_mon(line[4:], foe, own=False, active=True, features=features)
        elif line.startswith(('my team: ', 'opp team: ')):
            mine = line.startswith('my team: ')
            prefix = 'my team: ' if mine else 'opp team: '
            team = [m for s, m in sorted((own if mine else opp).items()) if m is not (me if mine else foe)]
            segments = line[len(prefix):].split(' || ')
            if len(segments) != len(team):
                raise ValueError('team segments do not match the snapshot')
            lines[i] = prefix + ' || '.join(_rewrite_mon(t, m, own=mine, active=False, features=features)
                                            for t, m in zip(segments, team))
    criteria = dict(question['criteria'])
    if 'items' in features:
        for action_id in facts['v5']['balloon']:
            if action_id in criteria:
                criteria[action_id] += '; balloon?'
    return '\n'.join(lines), dict(question, criteria=criteria)


def version(features):
    return dict(render=version_name(features), timed_side=list(TIMED_SIDE), removed=REMOVED,
                v1=compact.version(),
                v4=compact_v4.version([f for f in normalize(features) if f in compact_v4.MODULES]))
