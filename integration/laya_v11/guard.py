"""The decision-stage guard of D-210, as one dependency-free module (copied byte for byte into laya-play).

    excluded(state, criteria) -> [action ids the guard removes]
    choose(probabilities, excluded) -> the most likely action that is not removed

Removed: an option the rendered input marks as certain to do nothing (`fails`, `bounced`, or `x0 ... dmg 0-0%`; a
`likely fails` option stays), and the move that failed or hit an immunity on my previous turn while the same foe is
still in. If that removes everything, nothing is removed. Only turn decisions are guarded. It reads the rendered v10 /
v11 input, so it works with either renderer; `integration.laya_v11.analysis.rules.guarded` is the analysis twin.
"""
import re

CONFIRMED = re.compile(r'(?<!likely )\bfails\b|\bbounced\b')
ZERO = re.compile(r' x0\b.*\bdmg 0-0%')
HEAD = re.compile(r'^turn (\d+) \| (\w+) \|')
HISTORY = re.compile(r'^T(\d+): (.*)$', re.M)
OWN_MOVE = re.compile(r'^me ([A-Z][^>]*?)(?: -> (.+))?$')
ACTION = re.compile(r'^(me|opp) (?:[A-Z]|in )')
FOE_IN = re.compile(r'(?:^|; )opp in ')
FAILED = ('me failed', 'opp failed', 'opp immune')


def _move_id(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def failed_move(state, turn):
    """The id of my move that failed or was immune last turn against the foe still in, else None."""
    for number, text in HISTORY.findall(state):
        if int(number) != turn - 1:
            continue
        if FOE_IN.search(text):
            return None
        items = text.split('; ')
        for i, item in enumerate(items):
            found = OWN_MOVE.match(item)
            if not found or item.startswith('me in '):
                continue
            for nxt in items[i + 1:]:
                if ACTION.match(nxt):
                    break
                if nxt in FAILED:
                    return _move_id(found.group(1))
                if nxt in ('me missed',) or nxt.startswith('opp activate '):
                    break
            return None
    return None


def excluded(state, criteria):
    head = HEAD.match(state)
    if not head or head.group(2) != 'turn_action':
        return []
    again = failed_move(state, int(head.group(1)))
    out = []
    for action, text in criteria.items():
        parts = action.split(':')
        if parts[0] != 'move':
            continue
        if CONFIRMED.search(text) or ZERO.search(text) or (again is not None and parts[1] == again):
            out.append(action)
    return [] if len(out) == len(criteria) else out


def choose(probabilities, removed):
    keep = {a: p for a, p in probabilities.items() if a not in set(removed)} or probabilities
    return max(keep, key=keep.get)
