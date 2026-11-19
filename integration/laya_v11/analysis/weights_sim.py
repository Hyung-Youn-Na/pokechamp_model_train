"""EX-169 (for D-209 decision 4): what a row weight would do to v10rt's argmax, simulated on held-out human rows.

    python -m integration.laya_v11.analysis.weights_sim table

Training with weight w on the rows of a category whose label is in a response set S moves a calibrated model's
distribution in that category to p'(a) proportional to p(a) * w for a in S and p(a) otherwise. Applying that to
v10rt's probabilities on held-out human rows gives the argmax rate a weight would produce, next to the human rate.
Categories: `duel_lose` (S = switches), `boosted_foe` (S = switches), `stalled_streak` (S = everything but the streak
move), and `all_turns` (S = switches, every turn action) for reference.
"""
from __future__ import annotations
import json
import sys

from .. import paths
from . import features as F

GRID = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0)


def categories(facts, state):
    out = {}
    if facts['kind'] != 'turn_action':
        return out
    switches = {a for a, m in facts['marks'].items() if m['switch']}
    if switches:
        out['all_turns'] = ('random', switches)
    if facts['duel'] == 'lose' and switches:
        out['duel_lose'] = ('duel_lose_switch', switches)
    if facts['opp_offence'] >= 2 and switches:
        out['boosted_foe'] = ('boosted_foe_switch', switches)
    streak = facts['streak']
    if streak and F.loop_class(state, 'move:%s:normal' % streak[0]) == 'stall_repeat':
        out['stalled_streak'] = ('stalled_streak_repeat', {a for a, m in facts['marks'].items() if m['move'] != streak[0]})
    return out


def table():
    cells = {}
    for line in open(paths.TABLES / 'human-scored.jsonl'):
        r = json.loads(line)
        facts = F.describe(r['state'], r['criteria'])
        probs = r['probabilities']
        for name, (tag, S) in categories(facts, r['state']).items():
            if 'random' not in r['tags'] and tag not in r['tags']:
                continue
            for w in GRID:
                q = {a: p * (w if a in S else 1.0) for a, p in probs.items()}
                top = max(q, key=q.get)
                cell = cells.setdefault((name, w), [0, 0, 0, 0, 0.0])
                cell[0] += 1
                cell[1] += r['label'] in S
                cell[2] += top in S
                cell[3] += top == r['label']
                z = sum(q.values())
                cell[4] += sum(v for a, v in q.items() if a in S) / z
    out = []
    print('%-15s %5s %6s  %-9s %-11s %-9s %s' % ('category', 'w', 'n', 'label S', "argmax' S", "mass' S", 'agreement'))
    for (name, w), (n, label, top, agree, mass) in sorted(cells.items()):
        out.append(dict(category=name, weight=w, n=n, label_rate=label / n, argmax_rate=top / n, mass=mass / n,
                        agreement=agree / n))
        print('%-15s %5.2f %6d  %-9.3f %-11.3f %-9.3f %.3f' % (name, w, n, label / n, top / n, mass / n, agree / n))
    (paths.TABLES / 'a2-weight-simulation.json').write_text(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    dict(table=table)[sys.argv[1]]()
