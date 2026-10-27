"""laya-compact-v3: v2 text plus opponent-set modules, rendered from `features_v3.compute` facts.

`render(value, features, facts)` with `features` a subset of MODULES (v2's four plus `oppset`, `threat`,
`speedp`). With no v3 module the output is exactly `compact_v2.render` for the v2 subset. v3 modules only
append: an `opp set` state line, an `opp threat` state line, a larger switch `hit` (`?` when it comes from a likely
unseen move) and `first p` on the speed line.
"""
from __future__ import annotations

from . import compact_v2, features_v3

V3_MODULES = ('oppset', 'speedp', 'threat')
MODULES = tuple(sorted(compact_v2.MODULES + V3_MODULES))


def normalize(features):
    features = tuple(sorted(set(features)))
    unknown = set(features) - set(MODULES)
    if unknown:
        raise ValueError('unknown v3 modules: %s' % sorted(unknown))
    return features


def version_name(features):
    return 'laya-compact-v3[%s]' % ','.join(normalize(features))


def _p(value):
    return '1' if value >= 0.995 else ('%.2f' % value)[1:]


def _dist(pairs, limit):
    shown = [(k, p) for k, p in pairs if p >= features_v3.SHOW_FLOOR][:limit]
    return ' / '.join('%s %s' % (k, _p(p)) for k, p in shown)


def _oppset_line(s):
    if s is None:
        return None
    if s['source'] != 'usage':
        return 'opp set: no usage data'
    parts = []
    for name, key, limit in (('item', 'item', 2), ('ability', 'ability', 2), ('tera', 'tera', 2)):
        pairs = s[key]
        if pairs and pairs[0][1] < 0.995:
            text = _dist(pairs, limit)
            if text:
                parts.append('%s %s' % (name, text))
    moves = [(m, p) for m, p in s['moves'] if p >= features_v3.SHOW_FLOOR][:4]
    if moves:
        parts.append('likely moves ' + ', '.join('%s %s' % (m, _p(p)) for m, p in moves))
    return 'opp set: ' + ('; '.join(parts) if parts else 'all known')


def _threat(t):
    return '%s p%s hit %s-%s%%' % (t['move'], _p(t['p']), compact_v2._pct(t['min']), compact_v2._pct(t['max']))


def _hit(d):
    return '; hit %s-%s%%' % (compact_v2._pct(d['min']), compact_v2._pct(d['max']))


def _switch_hit(text, threat, seen):
    """Option budget (48 tokens): the v2 `hit` becomes the larger of the seen and likely unseen hits, `?` if unseen."""
    if threat is None or (seen is not None and 'error' not in seen and seen['max'] >= threat['max']):
        return text
    shown = _hit(seen) if seen is not None and 'error' not in seen else '; hit ?' if seen is not None else None
    likely = _hit(threat) + '?'
    if shown and text.endswith(shown):
        return text[:-len(shown)] + likely
    return text + likely


def render(value, features=(), facts=None):
    """`ImitationInput` + module set + facts -> (state text, laya choice question)."""
    features = normalize(features)
    v2 = tuple(f for f in features if f in compact_v2.MODULES)
    state, question = compact_v2.render(value, v2, facts)
    extra = [f for f in features if f in V3_MODULES]
    if not extra:
        return state, question
    if facts is None or 'v3' not in facts:
        raise ValueError('v3 modules need features_v3 facts')
    v3 = facts['v3']
    lines = state.split('\n')
    at = next((i for i, line in enumerate(lines) if line.startswith('OPP ')), None)
    if 'speedp' in features and v3['first'] is not None:
        i = next((i for i, line in enumerate(lines) if line.startswith('speed: ')), None)
        if i is not None:
            lines[i] += ' | first p%s' % _p(v3['first'])
    added = []
    if 'oppset' in features:
        line = _oppset_line(v3['oppset'])
        if line:
            added.append(line)
    if 'threat' in features and v3['threat']['active']:
        added.append('opp threat: ' + _threat(v3['threat']['active']))
    if added:
        at = len(lines) if at is None else at + 1
        lines[at:at] = added
    criteria = question['criteria']
    if 'threat' in features and v3['threat']['switch']:
        criteria = {a: _switch_hit(text, v3['threat']['switch'].get(a), facts['damage'].get(a))
                    for a, text in criteria.items()}
    return '\n'.join(lines), dict(question, criteria=criteria)


def version(features):
    return dict(render=version_name(features), usage_sha256=features_v3.digest(), v2=compact_v2.version(
        [f for f in normalize(features) if f in compact_v2.MODULES]))
