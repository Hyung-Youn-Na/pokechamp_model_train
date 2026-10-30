"""laya-compact-v6 (D-198): v5 text plus one of two past-turn modules, from the same `features_v5.compute` facts.

`render(value, features, facts, fit=None)` with `features` a subset of MODULES (v5's eight plus `streaks`, `longhist`).
With no v6 module the output is exactly `compact_v5.render`. v6 modules only touch their own segments:
- `streaks` (EX-141, 1024 tokens): on the ME / OPP line, ` | streak <move> x<n>` when that active Pokemon used the
  same move in each of the last n >= 2 complete turns (`+` when the run reaches the start of the four-turn `history`
  window, so it may be longer), followed by the other active Pokemon's HP at the end of each of those turns, e.g.
  `streak ruination x4+ (opp hp 33>23>18>40)`. Counted from `history` alone, so it needs no new input field.
- `longhist` (EX-142, 2048 tokens): the `T<n>:` history lines (v1 shows turns T-1 and T) are rebuilt from `history`
  plus the opt-in `early_history` (D-198), adding older turns one at a time while `fit(state, question)` holds.
  Turns T-1 and T are always kept; `fit=None` keeps every turn.
"""
from __future__ import annotations
import json
import re

from . import compact, compact_v5

V6_MODULES = ('longhist', 'streaks')
MODULES = tuple(sorted(compact_v5.MODULES + V6_MODULES))
V6S_MODULES = tuple(sorted(compact_v5.MODULES + ('streaks',)))
V6H_MODULES = tuple(sorted(compact_v5.MODULES + ('longhist',)))
MIN_STREAK = 2
WINDOW = 4   # turns T-4..T-1 of `history` (schema.py)
HISTORY_LINE = re.compile(r'^T\d+: ')


def normalize(features):
    features = tuple(sorted(set(features)))
    unknown = set(features) - set(MODULES)
    if unknown:
        raise ValueError('unknown v6 modules: %s' % sorted(unknown))
    if {'longhist', 'streaks'} <= set(features):
        raise ValueError('streaks and longhist are separate experiments')
    return features


def version_name(features):
    return 'laya-compact-v6[%s]' % ','.join(normalize(features))


def _move_id(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def _hp(value):
    return str(value).split()[0].split('/')[0]


def streak(history, turn, side):
    """(move id, turns, open-ended, other side's end-of-turn HP list or None) for `side` ('@self' / '@opponent').

    Walks the complete turns before `turn` backwards; a switch-in of `side` ends the run at that turn."""
    other = '@opponent' if side == '@self' else '@self'
    by_turn = {}
    for e in history:
        if e['turn'] < turn:
            by_turn.setdefault(e['turn'], []).append(e)
    first = turn - WINDOW
    move, count, other_hp, other_switched, boundary = None, 0, [], False, False
    last_hp = {}
    for t in sorted(by_turn):   # the other side's HP as of each turn's end, carried across turns without HP events
        for e in by_turn[t]:
            if e['event'] in ('switch', 'drag', 'replace') and len(e['args']) > 2 and e['args'][0] == other:
                last_hp['now'] = _hp(e['args'][2])
            elif e['event'] in ('-damage', '-heal', '-sethp') and len(e['args']) > 1 and e['args'][0] == other:
                last_hp['now'] = _hp(e['args'][1])
        last_hp[t] = last_hp.get('now')
    for t in range(turn - 1, first - 1, -1):
        events = by_turn.get(t, [])
        used = [_move_id(e['args'][1]) for e in events if e['event'] == 'move' and e['args'][:1] == [side]
                and not any(str(a).startswith('[from]') for a in e['args'])]
        stopped = any(e['event'] == 'cant' and e['args'][:1] == [side] for e in events)
        entered = any(e['event'] in ('switch', 'drag', 'replace') and e['args'][:1] == [side] for e in events)
        if not used or stopped or (move is not None and used[-1] != move):
            break
        move = used[-1]
        count += 1
        other_hp.append(last_hp.get(t))
        if any(e['event'] in ('switch', 'drag', 'replace') and e['args'][:1] == [other] for e in events):
            other_switched = True
        if entered:
            boundary = True
            break
    if count < MIN_STREAK:
        return None
    open_ended = not boundary and turn - count == first and first > 0
    hp = None if other_switched or None in other_hp else list(reversed(other_hp))
    return move, count, open_ended, hp


def _streak_text(found, other_label):
    move, count, open_ended, hp = found
    text = ' | streak %s x%d%s' % (move, count, '+' if open_ended else '')
    if hp is not None:
        text += ' (%s hp %s)' % (other_label, '>'.join(hp))
    return text


def _history_lines(events, keep_from):
    turns = {}
    for e in events:
        if e['turn'] >= keep_from:
            text = compact._event(e)
            if text:
                turns.setdefault(e['turn'], []).append(text)
    return ['T%d: %s' % (t, '; '.join(items)) for t, items in sorted(turns.items())]


def render(value, features=(), facts=None, fit=None):
    """`ImitationInput` + module set + facts (+ `fit` for `longhist`) -> (state text, laya choice question)."""
    features = normalize(features)
    state, question = compact_v5.render(value, tuple(f for f in features if f in compact_v5.MODULES), facts)
    if not set(features) & set(V6_MODULES):
        return state, question
    snapshot = json.loads(value.body['state'])['snapshot']
    turn = snapshot['turn']
    lines = state.split('\n')
    if 'streaks' in features:
        for i, line in enumerate(lines):
            if line.startswith('ME ') and snapshot['own_active_slot']:
                found = streak(snapshot['history'], turn, '@self')
                if found:
                    lines[i] = line + _streak_text(found, 'opp')
            elif line.startswith('OPP ') and snapshot['opponent_active_slot']:
                found = streak(snapshot['history'], turn, '@opponent')
                if found:
                    lines[i] = line + _streak_text(found, 'my')
    if 'longhist' in features:
        if 'early_history' not in snapshot:
            raise ValueError('the longhist module needs the D-198 early_history field')
        body = [ln for ln in lines if not HISTORY_LINE.match(ln)]
        if lines[len(body):] != [ln for ln in lines if HISTORY_LINE.match(ln)]:
            raise ValueError('history lines are not the tail of the v5 text')
        events = snapshot['early_history'] + snapshot['history']
        turns = sorted({e['turn'] for e in events if e['turn'] < turn - 1})
        start = 0
        candidate = lambda k: '\n'.join(body + _history_lines(events, turns[k] if k < len(turns) else turn - 1))
        if fit is not None:
            # Oldest turn first: drop turns from the front until the text fits (T-1 and T always stay).
            lo, hi = 0, len(turns)
            while lo < hi:
                mid = (lo + hi) // 2
                if fit(candidate(mid), question):
                    hi = mid
                else:
                    lo = mid + 1
            start = lo
        return candidate(start), question
    return '\n'.join(lines), question


def version(features):
    return dict(render=version_name(features), min_streak=MIN_STREAK, window=WINDOW,
                v5=compact_v5.version([f for f in normalize(features) if f in compact_v5.MODULES]))
