"""laya-compact-v7 (D-200): v6s text plus the `oppset2` module, from `features_v5` facts and `features_v7` facts.

`render(value, features, facts, v7)` with `features` a subset of MODULES (v6s's nine plus `oppset2`). With no v7 module
the output is exactly `compact_v6.render`. `oppset2` only appends:
- `opp set: ...` after the OPP line (hidden slots of the active foe: item / ability / Tera guesses and likely moves),
- `opp watch: ...` after it (game-changing hidden items / moves),
- ` | likely <item> <p>; <move> <p>, ...` at the end of each living benched foe's `opp team:` segment,
- `; fails` on hazard options that `features_v7.typechange_failures` decides (Protean / Libero rows, where v4 is silent).
"""
from __future__ import annotations
import json

from . import compact_v6, features_v3

V7_MODULES = ('oppset2',)
MODULES = tuple(sorted(compact_v6.V6S_MODULES + V7_MODULES))


def normalize(features):
    features = tuple(sorted(set(features)))
    unknown = set(features) - set(MODULES)
    if unknown:
        raise ValueError('unknown v7 modules: %s' % sorted(unknown))
    return features


def version_name(features):
    return 'laya-compact-v7[%s]' % ','.join(normalize(features))


def _p(value):
    return '1' if value >= 0.995 else ('%.2f' % value)[1:]


def _pairs(pairs):
    return ' / '.join('%s %s' % (k, _p(p)) for k, p in pairs)


def set_line(s):
    if s is None:
        return None
    if s['source'] != 'usage':
        return 'opp set: no usage data'
    parts = []
    for name in ('item', 'ability', 'tera'):
        if s[name]:
            parts.append('%s %s' % (name, _pairs(s[name])))
    if s['moves']:
        parts.append('likely moves ' + ', '.join('%s %s' % (m, _p(p)) for m, p in s['moves']))
    return 'opp set: ' + ('; '.join(parts) if parts else 'all known')


def watch_line(watch):
    return 'opp watch: ' + ', '.join('%s %s' % (k, _p(p)) for k, p in watch) if watch else None


def bench_text(b):
    parts = []
    if b['item']:
        parts.append('%s %s' % (b['item'][0][0], _p(b['item'][0][1])))
    if b['moves']:
        parts.append(', '.join('%s %s' % (m, _p(p)) for m, p in b['moves']))
    return ' | likely ' + '; '.join(parts)


def render(value, features=(), facts=None, v7=None):
    """`ImitationInput` + module set + v5 facts + v7 facts -> (state text, laya choice question)."""
    features = normalize(features)
    state, question = compact_v6.render(value, tuple(f for f in features if f in compact_v6.MODULES), facts)
    if 'oppset2' not in features:
        return state, question
    if v7 is None:
        raise ValueError('oppset2 needs features_v7 facts')
    snapshot = json.loads(value.body['state'])['snapshot']
    opp = {m['slot']: m for m in snapshot['opponent_team']}
    foe = opp.get(snapshot['opponent_active_slot']) if snapshot['opponent_active_slot'] else None
    lines = state.split('\n')
    added = [x for x in (set_line(v7['active']), watch_line(v7['watch'])) if x]
    at = next((i for i, line in enumerate(lines) if line.startswith('OPP ')), None)
    if added and at is not None:
        lines[at + 1:at + 1] = added
    if v7['bench']:
        team = [s for s, m in sorted(opp.items()) if m is not foe]
        for i, line in enumerate(lines):
            if line.startswith('opp team: '):
                segments = line[len('opp team: '):].split(' || ')
                if len(segments) != len(team):
                    raise ValueError('team segments do not match the snapshot')
                lines[i] = 'opp team: ' + ' || '.join(
                    seg + (bench_text(v7['bench'][str(slot)]) if str(slot) in v7['bench'] else '')
                    for seg, slot in zip(segments, team))
                break
    criteria = question['criteria']
    if v7['fails_tc']:
        criteria = {a: text + ('; fails' if a in v7['fails_tc'] and '; fails' not in text else '')
                    for a, text in criteria.items()}
    return '\n'.join(lines), dict(question, criteria=criteria)


def version(features):
    return dict(render=version_name(features), usage_sha256=features_v3.digest(),
                v6=compact_v6.version_name([f for f in normalize(features) if f in compact_v6.MODULES]))
