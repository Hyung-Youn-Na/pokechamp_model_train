"""EX-169 A5: decision-stage rules replayed on logged probabilities (no model call).

    python -m integration.laya_v11.analysis.rules table

Rules act on v10rt's distribution for one decision:
- `argmax`: the deployed policy.
- `guard`: drop dead options (confirmed fail, bounced, x0 damage) and the move that just failed against the same foe
  (D-209 decision 5); if nothing is left, keep the original options.
- `group`: decide between switching and using a move by total probability (switch when the switch options together
  outweigh the move options together), then take the best option inside the group.
- `group_top`: switch when the switch options together outweigh the single best move.
- `guard+group`: `guard` first, then `group` on what is left (renormalised).
On held-out human rows (the random draw of `human-scored.jsonl`) the table gives agreement with the human label and
the switch rate next to the human switch rate; on the bot's decisions, how many choices change.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import json
import re
import sys

from .. import paths
from . import compare
from . import features as F
from . import score as S

RULES = ('argmax', 'guard', 'group', 'group_top', 'guard+group')
FOE_IN = re.compile(r'(?:^|; )opp in ')


def _same_foe(state, turn):
    """The foe did not enter in the previous turn (the move that failed was aimed at the current foe)."""
    for number, text in F.HISTORY.findall(state):
        if int(number) == turn - 1:
            return not FOE_IN.search(text)
    return True


def guarded(facts, state, probs):
    keep = {}
    for action, p in probs.items():
        mark = facts['marks'][action]
        if mark['dead']:
            continue
        if mark['move'] and mark['move'] == facts['last_move'] and facts['last_fate'] in ('fail', 'immune') and \
                _same_foe(state, facts['turn']):
            continue
        keep[action] = p
    return keep or dict(probs)


def _best(probs):
    return max(probs, key=probs.get)


def _group(probs, top_only=False):
    switches = {a: p for a, p in probs.items() if a.startswith('switch:')}
    moves = {a: p for a, p in probs.items() if a.startswith('move:')}
    if not switches or not moves:
        return _best(probs)
    against = max(moves.values()) if top_only else sum(moves.values())
    return _best(switches) if sum(switches.values()) > against else _best(moves)


def choose(rule, facts, state, probs):
    if facts['kind'] != 'turn_action':
        return _best(probs)
    if rule == 'argmax':
        return _best(probs)
    if rule == 'guard':
        return _best(guarded(facts, state, probs))
    if rule == 'group':
        return _group(probs)
    if rule == 'group_top':
        return _group(probs, top_only=True)
    if rule == 'guard+group':
        return _group(guarded(facts, state, probs))
    raise ValueError(rule)


def table():
    out = dict(human={}, bot={})
    # held-out human rows, random draw only
    cells = {rule: defaultdict(lambda: [0, 0, 0, 0, 0.0]) for rule in RULES}
    for line in open(paths.TABLES / 'human-scored.jsonl'):
        r = json.loads(line)
        if 'random' not in r['tags']:
            continue
        facts = F.describe(r['state'], r['criteria'])
        if facts['kind'] != 'turn_action':
            continue
        replay = r['sample_id'].split(':')[0]
        mass = sum(p for a, p in r['probabilities'].items() if a.startswith('switch:'))
        for rule in RULES:
            pick = choose(rule, facts, r['state'], r['probabilities'])
            cell = cells[rule][replay]
            cell[0] += 1
            cell[1] += pick == r['label']
            cell[2] += pick.startswith('switch:')
            cell[3] += r['label'].startswith('switch:')
            cell[4] += mass
    print('held-out human rows (random draw, turn actions)')
    print('%-12s %6s  %-28s %-28s %-10s %s' % ('rule', 'n', 'agreement with label', 'switch rate', 'label sw', 'mass sw'))
    for rule in RULES:
        cs = list(cells[rule].values())
        n = sum(c[0] for c in cs)
        agree = compare._interval([(c[0], c[1]) for c in cs], draws=5000)
        switch = compare._interval([(c[0], c[2]) for c in cs], draws=5000)
        label, mass = sum(c[3] for c in cs) / n, sum(c[4] for c in cs) / n
        out['human'][rule] = dict(n=n, agreement=agree, switch=switch, label_switch=label, mass_switch=mass)
        print('%-12s %6d  %.3f [%.3f, %.3f]          %.3f [%.3f, %.3f]          %.3f      %.3f' % (
            (rule, n) + agree + switch + (label, mass)))
    # the bot's own decisions (argmax-policy games)
    rows = [r for r in S.decisions() if not r['automatic'] and r['state'] and r['policy'] != 'sample']
    base = {}
    print('\nbot decisions in argmax games (turn actions)')
    print('%-12s %6s %8s %8s  %s' % ('rule', 'n', 'changed', 'switch', 'dead picks left / failed-repeat left / changes by kind'))
    for rule in RULES:
        n = changed = switch = dead = repeat = 0
        kinds = Counter()
        for r in rows:
            facts = F.describe(r['state'], r['criteria'])
            if facts['kind'] != 'turn_action':
                continue
            pick = choose(rule, facts, r['state'], r['probabilities'])
            first = base.setdefault((r['game'], r['decision']), choose('argmax', facts, r['state'], r['probabilities']))
            c = F.chosen(facts, pick)
            n += 1
            switch += c['switch']
            dead += c['dead']
            repeat += c['repeats_last'] and facts['last_fate'] in ('fail', 'immune')
            if pick != first:
                changed += 1
                was = F.chosen(facts, first)
                kinds['%s->%s' % ('switch' if was['switch'] else 'dead' if was['dead'] else 'move',
                                  'switch' if c['switch'] else 'move')] += 1
        out['bot'][rule] = dict(n=n, changed=changed, switch_rate=switch / n, dead=dead, repeat_after_fail=repeat,
                                changes=dict(kinds))
        print('%-12s %6d %8d %8.3f  %d / %d / %s' % (rule, n, changed, switch / n, dead, repeat, dict(kinds)))
    (paths.TABLES / 'a5-rules.json').write_text(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    dict(table=table)[sys.argv[1]]()
