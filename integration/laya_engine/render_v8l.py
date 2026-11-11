"""EX-155 renderer v8l (user instruction 2026-11-02, D-201 addendum): the v8 text plus `; likely fails` on chance-based
failures.

`render(value, facts, judged)` is `render_v8.render` with one more mark: a move option the judge labels `likely fails`
(a Protect-family move after a successful Protect streak, success 1/3^n; Sleep Talk / Snore when waking this turn is at
least as likely as not) and that carries no confirmed `; fails` / `; bounced` mark gets `; likely fails`. Everything
else is v8's, so with no likely label the text is exactly v8's.
"""
from __future__ import annotations

from . import judge as J
from . import render_v8

MODULES = render_v8.MODULES
VERSION = 'laya-compact-v8l[%s]' % ','.join(MODULES)
LIKELY_TEXT = '; likely fails'


def likely(value, judged):
    return sorted(a for a in value.action_ids if judged['labels'].get(a) == J.LIKELY)


def render(value, facts, judged):
    state, question = render_v8.render(value, facts, judged)
    marks = set(likely(value, judged))
    criteria = {a: text + (LIKELY_TEXT if a in marks and '; fails' not in text and '; bounced' not in text else '')
                for a, text in question['criteria'].items()}
    return state, dict(question, criteria=criteria)


def version():
    return dict(render_v8.version(), render=VERSION, likely=LIKELY_TEXT)
