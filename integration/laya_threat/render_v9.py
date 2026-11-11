"""laya-compact-v9 (D-202): the v7 text on item-consistent foe spreads, plus worst plausible incoming damage.

`render(value, facts, v7, risk)`: `facts` are v5 facts computed inside `spreads.patched()` (so every `dmg`,
`hit` and `out` already uses the fixed spread), `v7` the `features_v7` facts, `risk` the `threat.compute` facts.
On top of `compact_v7.render` with all v7 modules:
- a switch option gets `; risk a-b% <move>` when its worst plausible hit reaches SWITCH_FLOOR and either no `hit` is
  shown or the worst maximum is at least GAP points above the shown one;
- on `turn_action`, `opp threat: <move> a-b% to me` (with `(<item>?, tera <type>)` when the worst case assumes a hidden
  item or a Tera not yet used) goes right after the OPP block (OPP line, `opp set`, `opp watch`) when it reaches
  ACTIVE_FLOOR.
Token budget (v7 rows already sit at the EX-149 limits): an option whose `risk` mark would pass OPTION_LIMIT tokens
gets `; risk a-b%` instead, or nothing; if the row then passes the row limits, the threat line goes first, then the
risk marks one by one from the smallest worst case. A row that does not fit even without them is v7's and is
excluded as before. The budget uses the pinned laya tokenizer, so offline and live renders are the same.
With no risk shown the text is v7's on the fixed spreads.
"""
from __future__ import annotations

from integration.laya_imitation import compact_v7, features_v3
from integration.laya_imitation import config as c

MODULES = compact_v7.MODULES
NAME = 'threat'
VERSION = 'laya-compact-v9[%s]' % ','.join(MODULES + (NAME,))
SWITCH_FLOOR = 20
ACTIVE_FLOOR = 20
GAP = 10


def _pct(value):
    return '%d' % round(value)


_tok = None


def tokenizer():
    global _tok
    if _tok is None:
        from integration.laya_imitation.data_v2 import _tokenizer
        _tok = _tokenizer()
    return _tok


def option_tokens(action_id, text):
    from laya.common import _encode_question_text, render_criterion
    return len(_encode_question_text(tokenizer(), ' %s: %s' % (action_id, render_criterion(text)),
                                     add_special_tokens=False))


def row_fits(state, question):
    from integration.laya_imitation.data_v2 import measure_row
    from integration.laya_imitation.data_v6 import fits
    return fits(measure_row(tokenizer(), state, question, c.V2_HEAD_LIMIT), c.TOKEN_LIMIT)


def shown_risk(entry, shown):
    if entry is None or entry['max'] < SWITCH_FLOOR:
        return False
    return shown is None or 'error' in shown or entry['max'] >= shown['max'] + GAP


def switch_text(action_id, text, entry):
    """The option's risk mark that keeps it within OPTION_LIMIT tokens ('' when none does)."""
    from integration.laya_imitation.data_v2 import OPTION_LIMIT
    for mark in ('; risk %s-%s%% %s' % (_pct(entry['min']), _pct(entry['max']), entry['move']),
                 '; risk %s-%s%%' % (_pct(entry['min']), _pct(entry['max']))):
        if option_tokens(action_id, text + mark) <= OPTION_LIMIT:
            return mark
    return ''


def active_line(entry):
    if entry is None or entry['max'] < ACTIVE_FLOOR:
        return None
    notes = []
    if not entry['item_known'] and entry['item']:
        notes.append(entry['item'] + '?')
    if entry['tera'] and not entry['terastallized']:
        notes.append('tera ' + entry['tera'])
    return 'opp threat: %s %s-%s%% to me%s' % (entry['move'], _pct(entry['min']), _pct(entry['max']),
                                               ' (%s)' % ', '.join(notes) if notes else '')


def _with_threat(state, line):
    lines = state.split('\n')
    at = next((i for i, x in enumerate(lines) if x.startswith('OPP ')), None)
    if line is None or at is None:
        return state
    end = at + 1
    while end < len(lines) and lines[end].startswith(('opp set: ', 'opp watch: ')):
        end += 1
    return '\n'.join(lines[:end] + [line] + lines[end:])


def render(value, facts, v7, risk):
    state, question = compact_v7.render(value, MODULES, facts, v7)
    base = question['criteria']
    marks = {}
    for a, text in base.items():
        entry = risk['switch'].get(a)
        if a.startswith('switch:') and shown_risk(entry, facts['damage'].get(a)):
            mark = switch_text(a, text, entry)
            if mark:
                marks[a] = (entry['max'], mark)
    line = active_line(risk['active'])

    def build(with_line, kept):
        criteria = {a: text + (marks[a][1] if a in kept else '') for a, text in base.items()}
        return _with_threat(state, line if with_line else None), dict(question, criteria=criteria)

    kept = set(marks)
    out = build(True, kept)
    if row_fits(*out):
        return out
    out = build(False, kept)
    for a in sorted(marks, key=lambda a: (marks[a][0], a)):
        if row_fits(*out):
            return out
        kept.discard(a)
        out = build(False, kept)
    return out


def marks(state, question):
    """(threat line shown, switch options with a risk mark) of a rendered row."""
    return (any(x.startswith('opp threat: ') for x in state.split('\n')),
            sum('; risk ' in t for t in question['criteria'].values()))


def version():
    return dict(render=VERSION, usage_sha256=features_v3.digest(), v7=compact_v7.version_name(MODULES))
