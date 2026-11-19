"""EX-169: decision features read from a rendered v10 input (state text + option criteria).

The same function describes a human training row and a bot decision, so the three-way comparison (human label,
v10rt on human states, the bot on its own states) uses one definition per measure.

`describe(state, criteria)` -> facts of the position; `chosen(facts, criteria, action)` -> what an action is there.
"""
from __future__ import annotations
import re

from integration.laya_imitation import loop_weights

CONFIRMED = re.compile(r'(?<!likely )\bfails\b|\bbounced\b')
ZERO = re.compile(r' x0\b.*\bdmg 0-0%')
PROTECT = ('protect', 'detect', 'kingsshield', 'spikyshield', 'banefulbunker', 'silktrap', 'burningbulwark',
           'obstruct')
HEAD = re.compile(r'^turn (\d+) \| (\w+) \| my tera (\w+) \| opp tera (\w+)')
DUEL = re.compile(r'^duel: me (\S+) hits \((\w+)\) vs opp (\S+) hits \((\w+)\), (me|opp) first -> (\w+)', re.M)
BOARD = re.compile(r'^board: me (\d) alive (\d+)% \| opp (\d) alive (\d+)%', re.M)
ME = re.compile(r'^ME (\S+) \[([a-z ]+)\] (\d+(?:\.\d+)?)%', re.M)
OPP = re.compile(r'^OPP (\S+) \[([a-z ]+)\] (\d+(?:\.\d+)?|\?)%?', re.M)
BOOSTS = re.compile(r'\| boosts ([^|\n]+)')
STREAK_ANY = re.compile(r'^ME [^\n]* \| streak ([a-z0-9]+) x(\d+)', re.M)
HISTORY = re.compile(r'^T(\d+): (.*)$', re.M)
OWN_MOVE = re.compile(r'^me ([A-Z][^>]*?)(?: -> (.+))?$')
ACTION = re.compile(r'^(me|opp) (?:[A-Z]|in )')
FAILED = {'me failed': 'fail', 'opp failed': 'fail', 'opp immune': 'immune', 'me missed': 'miss',
          'opp activate Protect': 'protect', 'opp activate Detect': 'protect',
          'opp activate Spiky Shield': 'protect', 'opp activate Baneful Bunker': 'protect',
          "opp activate King's Shield": 'protect', 'opp activate Silk Trap': 'protect',
          'opp activate Burning Bulwark': 'protect', 'opp activate Obstruct': 'protect'}


def move_id(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def _boosts(line):
    found = BOOSTS.search(line or '')
    out = {}
    if found:
        for part in found.group(1).split():
            m = re.match(r'([a-z]+)([+-]\d+)$', part)
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


def last_own_move(state, turn):
    """(move id, fate) of my move in the previous turn's history line; fate in ok/fail/immune/miss/protect."""
    for number, text in HISTORY.findall(state):
        if int(number) != turn - 1:
            continue
        items = text.split('; ')
        for i, item in enumerate(items):
            found = OWN_MOVE.match(item)
            if not found or item.startswith('me in '):
                continue
            fate = 'ok'
            for nxt in items[i + 1:]:
                if ACTION.match(nxt):
                    break
                if nxt in FAILED:
                    fate = FAILED[nxt]
                    break
            return move_id(found.group(1)), fate
    return None, None


def describe(state, criteria):
    head = HEAD.match(state)
    lines = state.split('\n')
    me_line = next((x for x in lines if x.startswith('ME ')), None)
    opp_line = next((x for x in lines if x.startswith('OPP ')), None)
    turn, kind = (int(head.group(1)), head.group(2)) if head else (None, None)
    duel = DUEL.search(state)
    board = BOARD.search(state)
    me, opp = ME.search(state), OPP.search(state)
    marks = {}
    for action, text in criteria.items():
        parts = action.split(':')
        confirmed = bool(CONFIRMED.search(text))
        zero = bool(ZERO.search(text))
        marks[action] = dict(move=parts[1] if parts[0] == 'move' else None, tera=parts[0] == 'move' and parts[2] == 'tera',
                             switch=parts[0] == 'switch', status=parts[0] == 'move' and ' status' in text.split(';')[0],
                             confirmed=confirmed, zero=zero, dead=confirmed or zero,
                             likely_fail='likely fails' in text)
    moves = [a for a, m in marks.items() if m['move'] and not m['tera']]
    opp_boosts = _boosts(opp_line)
    streak = STREAK_ANY.search(state)
    last_move, last_fate = last_own_move(state, turn) if turn is not None else (None, None)
    return dict(turn=turn, kind=kind, tera_ready=bool(head) and head.group(3) == 'ready',
                duel=duel.group(6) if duel else None,
                board=tuple(int(x) for x in board.groups()) if board else None,
                me=me.group(1) if me else None, me_hp=float(me.group(3)) if me else None,
                opp=opp.group(1) if opp else None,
                opp_offence=max(opp_boosts.get('atk', 0), opp_boosts.get('spa', 0)), opp_boosts=opp_boosts,
                me_boosts=_boosts(me_line),
                has_switch=any(m['switch'] for m in marks.values()),
                has_dead=any(marks[a]['dead'] for a in moves), has_live=any(not marks[a]['dead'] for a in moves),
                all_dead=bool(moves) and all(marks[a]['dead'] for a in moves),
                streak=(streak.group(1), int(streak.group(2))) if streak else None,
                last_move=last_move, last_fate=last_fate, marks=marks)


def loop_class(state, action):
    """EX-146's classes for a stalled damaging streak: none / progress / stall_repeat / stall_break."""
    return loop_weights.classify(state, action)


def chosen(facts, action):
    """What `action` is in this position."""
    m = facts['marks'][action]
    return dict(switch=m['switch'], tera=m['tera'], status=m['status'], dead=m['dead'], confirmed=m['confirmed'],
                zero=m['zero'], likely_fail=m['likely_fail'], move=m['move'],
                repeats_last=m['move'] is not None and m['move'] == facts['last_move'],
                protect=m['move'] in PROTECT)


def measures(facts, state, action):
    """{measure name: 0/1} for the measures whose condition holds in this position (the A2 denominators)."""
    c = chosen(facts, action)
    out = {}
    if facts['kind'] != 'turn_action':
        return out
    out['switch'] = int(c['switch'])
    out['status_move'] = int(c['status'])
    if facts['tera_ready'] and any(m['tera'] for m in facts['marks'].values()):
        out['tera'] = int(c['tera'])
    if facts['has_dead'] and (facts['has_live'] or facts['has_switch']):
        out['dead_pick'] = int(c['dead'])
    if facts['has_dead'] and facts['has_live']:
        out['dead_pick_live_move'] = int(c['dead'])
    if facts['all_dead'] and facts['has_switch']:
        out['all_dead_switch'] = int(c['switch'])
    last = facts['last_move']
    if last and facts['last_fate'] in ('fail', 'immune', 'protect') and \
            any(m['move'] == last for m in facts['marks'].values()):
        out['repeat_after_fail'] = int(c['repeats_last'])
    if last and facts['last_fate'] == 'ok' and any(m['move'] == last for m in facts['marks'].values()):
        out['repeat_after_ok'] = int(c['repeats_last'])
    loop = loop_class(state, action)
    if loop in ('stall_repeat', 'stall_break'):
        out['stalled_streak_repeat'] = int(loop == 'stall_repeat')
    if facts['duel'] == 'lose' and facts['has_switch']:
        out['duel_lose_switch'] = int(c['switch'])
    if facts['duel'] == 'win' and facts['has_switch']:
        out['duel_win_switch'] = int(c['switch'])
    if facts['opp_offence'] >= 2:
        out['boosted_foe_switch'] = int(c['switch']) if facts['has_switch'] else 0
        out['boosted_foe_status'] = int(c['status'] and not c['protect'])
    if any(m['likely_fail'] and m['move'] in PROTECT for m in facts['marks'].values()):
        out['protect_again'] = int(c['protect'] and c['likely_fail'])
    return out


def mass(facts, state, probabilities):
    """{measure name: probability mass} — `measures` with the model's distribution instead of one action."""
    total = {}
    for action, p in probabilities.items():
        for name, value in measures(facts, state, action).items():
            total[name] = total.get(name, 0.0) + p * value
    return total
