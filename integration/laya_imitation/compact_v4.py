"""laya-compact-v4: v2 text plus known-failure and switch-in offense modules, from `features_v4.compute` facts.

`render(value, features, facts)` with `features` a subset of MODULES (v2's four plus `fails`, `out`). With no v4
module the output is exactly `compact_v2.render` for the v2 subset. v4 modules only append to options:
`; fails` (or `; bounced` for Magic Bounce) on move options the visible state decides, and `; out a-b%` on
switch options (the switch-in's strongest attack on the active foe).
"""
from __future__ import annotations
import hashlib

from . import compact_v2
from .effect_knowledge import EFFECTS, RULES

V4_MODULES = ('fails', 'out')
MODULES = tuple(sorted(compact_v2.MODULES + V4_MODULES))
OUT_FORMAT = 'max'   # frozen by the EX-130 pre-measurement: 'range' (`out a-b%`) left 5/512 validation rows over budget
FAIL_TEXT = {'fails': 'fails', 'immune': 'fails', 'absorbed': 'fails', 'reflected': 'bounced'}


def normalize(features):
    features = tuple(sorted(set(features)))
    unknown = set(features) - set(MODULES)
    if unknown:
        raise ValueError('unknown v4 modules: %s' % sorted(unknown))
    return features


def version_name(features):
    return 'laya-compact-v4[%s]' % ','.join(normalize(features))


def _out(d, fmt=None):
    if d is None or 'error' in d:
        return ''
    if (fmt or OUT_FORMAT) == 'max':
        return '; out %s%%' % compact_v2._pct(d['max'])
    return '; out %s-%s%%' % (compact_v2._pct(d['min']), compact_v2._pct(d['max']))


def render(value, features=(), facts=None, out_format=None):
    """`ImitationInput` + module set + facts -> (state text, laya choice question)."""
    features = normalize(features)
    state, question = compact_v2.render(value, tuple(f for f in features if f in compact_v2.MODULES), facts)
    if not set(features) & set(V4_MODULES):
        return state, question
    if facts is None or 'v4' not in facts:
        raise ValueError('v4 modules need features_v4 facts')
    v4 = facts['v4']
    criteria = {}
    for action_id, text in question['criteria'].items():
        if 'fails' in features and action_id in v4['fails']:
            text += '; ' + FAIL_TEXT[v4['fails'][action_id]]
        if 'out' in features and action_id.startswith('switch:'):
            text += _out(v4['out'].get(action_id), out_format)
        criteria[action_id] = text
    return state, dict(question, criteria=criteria)


def version(features):
    return dict(render=version_name(features), out_format=OUT_FORMAT,
                effect_rules_sha256=hashlib.sha256(RULES.read_bytes()).hexdigest(),
                effects_sha256=hashlib.sha256(EFFECTS.read_bytes()).hexdigest(),
                v2=compact_v2.version([f for f in normalize(features) if f in compact_v2.MODULES]))
