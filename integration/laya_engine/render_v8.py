"""EX-152 renderer v8 (D-201): the v7 text with every `; fails` / `; bounced` mark taken from the engine judge.

`render(value, facts, judged)`: `facts` are the v5 facts (`features_v5.compute`, the `laya-compact-features/v5` store
offline), `judged` the judge's answer for the same input (`judged_of`, or a `laya-engine-judge/v1` row offline).
- confirmed engine failures (`fails`, `immune`, `absorbed` -> `; fails`, `reflected` -> `; bounced`) replace the
  rule marks (`facts['v4']['fails']`, v7's typechange hazard marks);
- an option the judge could not rebuild (an engine error, not a case that merely never executed) keeps the rule mark,
  and so does every option of a decision the judge could not rebuild at all (`fallback`);
- `likely fails` (Protect streaks, Sleep Talk near waking) is not shown (EX-151: 132 of 176 failed).
Everything else is `compact_v7.render` with all v7 modules, so with no mark change the text is v7's.
"""
from __future__ import annotations
import copy

from integration.laya_imitation import compact_v7, features_v7

from . import judge as J

MODULES = compact_v7.MODULES
VERSION = 'laya-compact-v8[%s]' % ','.join(MODULES)
SHOWN = frozenset(J.FAILING)


def judged_of(value, judge):
    """The judge's answer in the `laya-engine-judge/v1` row shape."""
    labels, detail = J.option_outcomes(value, judge)
    return dict(labels=labels, reproduced=detail.get('reproduced'),
                engine={k: v['label'] for k, v in detail['options'].items()},
                errors={k: v.get('error') for k, v in detail['options'].items() if v['label'] == 'unknown'})


def fallback(judged, action_id):
    if judged['reproduced'] is False:
        return True
    error = (judged.get('errors') or {}).get(action_id)
    return bool(error) and str(error).startswith('error:')


def marks(value, facts, judged, v7):
    """({action id: label} shown, [action ids that kept the rule mark])."""
    rule = dict(facts['v4']['fails'])
    rule.update(v7['fails_tc'])
    out, kept = {}, []
    for action_id in value.action_ids:
        if not action_id.startswith('move:'):
            continue
        if fallback(judged, action_id):
            kept.append(action_id)
            if action_id in rule:
                out[action_id] = rule[action_id]
        elif judged['labels'].get(action_id) in SHOWN:
            out[action_id] = judged['labels'][action_id]
    return out, kept


def render(value, facts, judged):
    v7 = features_v7.compute(value)
    shown, _ = marks(value, facts, judged, v7)
    facts = copy.deepcopy(facts)
    facts['v4']['fails'] = shown
    return compact_v7.render(value, MODULES, facts, dict(v7, fails_tc={}))


def version():
    return dict(render=VERSION, judge=J.identity(), v7=compact_v7.version(MODULES))
