"""EX-169 A3: how much v10rt's choice depends on one piece of the input (the only interventional analysis here).

    python -m integration.laya_v11.analysis.counterfactual run      # GPU3
    python -m integration.laya_v11.analysis.counterfactual table

Each edit changes one thing in the rendered text and nothing else, then v10rt scores the edited input:
- `fails_removed`: `; fails` taken off a confirmed-fail option            -> change of that option's probability
- `fails_added`: `; fails` put on the model's top (live) move option      -> change of that option's probability
- `streak_removed`: the ME line's `| streak <move> x<n> (...)` removed    -> change of the streak move's probability
- `history_removed`: the `T<n>:` lines removed                            -> change of the last own move's probability
- `duel_flipped`: `-> lose` <-> `-> win` on the duel line                 -> change of the total switch probability
- `boosts_removed`: `| boosts ...` taken off the OPP line (+2 or more)    -> change of the total switch probability
Rows: the bot's own decisions and held-out human rows (`human-scored.jsonl`), same edits on both. An edit touches the
text only: damage numbers and other lines that came from the same fact stay, so this measures reliance on the
written signal, not on the underlying situation.
"""
from __future__ import annotations
from collections import defaultdict
import json
import random
import re
import sys

from .. import paths
from . import compare
from . import features as F
from . import score as S

STREAK = re.compile(r' \| streak [a-z0-9]+ x\d+\+?(?: \([^)\n]*\))?')
HISTORY_LINE = re.compile(r'^T\d+: .*$\n?', re.M)
DUEL_RESULT = re.compile(r'^(duel: .* -> )(win|lose)$', re.M)
OPP_BOOSTS = re.compile(r'^(OPP [^\n]*?) \| boosts [^|\n]*?(?= \||$)', re.M)
CAP = 1500     # human rows per edit


def _add_fails(text):
    parts = text.split('; ')
    at = 1
    while at < len(parts) and parts[at].startswith(('terastallize', 'dmg ')):
        at += 1
    return '; '.join(parts[:at] + ['fails'] + parts[at:])


def edits(row):
    """[(edit name, target, state, criteria)] for one row; `target` names what is measured (an action or 'switch')."""
    state, criteria = row['state'], row['criteria']
    facts = F.describe(state, criteria)
    if facts['kind'] != 'turn_action':
        return []
    probs = row['probabilities']
    out = []
    for action, mark in facts['marks'].items():
        if mark['confirmed'] and not mark['zero'] and not mark['tera'] and '; fails' in criteria[action]:
            changed = dict(criteria)
            for other in criteria:      # the Tera variant of the same move carries the same mark
                if other.split(':')[:2] == action.split(':')[:2]:
                    changed[other] = criteria[other].replace('; fails', '')
            out.append(('fails_removed', action, state, changed))
            break
    top = max((a for a, m in facts['marks'].items() if m['move'] and not m['tera']), key=lambda a: probs[a],
              default=None)
    if top is not None and not facts['marks'][top]['dead'] and not facts['marks'][top]['likely_fail']:
        changed = dict(criteria)
        for other in criteria:
            if other.split(':')[:2] == top.split(':')[:2]:
                changed[other] = _add_fails(criteria[other])
        out.append(('fails_added', top, state, changed))
    if facts['streak']:
        action = 'move:%s:normal' % facts['streak'][0]
        if action in criteria and STREAK.search(state):
            out.append(('streak_removed', action, STREAK.sub('', state, count=1), criteria))
    if facts['last_move'] and HISTORY_LINE.search(state):
        action = 'move:%s:normal' % facts['last_move']
        if action in criteria:
            out.append(('history_removed', action, HISTORY_LINE.sub('', state).rstrip('\n'), criteria))
            if facts['last_fate'] in ('fail', 'immune', 'protect'):
                out.append(('history_removed_after_fail', action, HISTORY_LINE.sub('', state).rstrip('\n'), criteria))
    if facts['duel'] in ('win', 'lose') and facts['has_switch']:
        flip = lambda m: m.group(1) + ('win' if m.group(2) == 'lose' else 'lose')
        out.append(('duel_%s_flipped' % facts['duel'], 'switch', DUEL_RESULT.sub(flip, state), criteria))
    if facts['opp_offence'] >= 2 and facts['has_switch'] and OPP_BOOSTS.search(state):
        out.append(('boosts_removed', 'switch', OPP_BOOSTS.sub(r'\1', state), criteria))
    return out


def _value(probs, target):
    return sum(p for a, p in probs.items() if a.startswith('switch:')) if target == 'switch' else probs[target]


def run():
    target_path = paths.TABLES / 'a3-counterfactual.jsonl'
    if target_path.exists():
        raise FileExistsError(target_path)
    rng = random.Random(paths.SEED)
    jobs = []
    for row in S.decisions():
        if row['automatic'] or row['state'] is None:
            continue
        for name, target, state, criteria in edits(row):
            jobs.append(dict(source='bot', cluster=row['game'], id=row['decision'], edit=name, target=target,
                             base=_value(row['probabilities'], target), state=state, criteria=criteria,
                             instructions=row['instructions'], chosen=row['choice']))
    human = defaultdict(list)
    for line in open(paths.TABLES / 'human-scored.jsonl'):
        row = json.loads(line)
        for name, target, state, criteria in edits(row):
            human[name].append(dict(source='human', cluster=row['sample_id'].split(':')[0], id=row['sample_id'],
                                    edit=name, target=target, base=_value(row['probabilities'], target), state=state,
                                    criteria=criteria, instructions=row['instructions'], chosen=row['label']))
    for name, rows in sorted(human.items()):
        rows.sort(key=lambda r: r['id'])
        jobs.extend(rng.sample(rows, min(CAP, len(rows))))
    with S.held_gpu():
        probs = S.Scorer().probabilities(jobs, batch_size=32)
    with open(target_path, 'w') as f:
        for job, p in zip(jobs, probs):
            f.write(json.dumps(dict(source=job['source'], cluster=job['cluster'], id=job['id'], edit=job['edit'],
                                    target=job['target'], base=job['base'], edited=_value(p, job['target']),
                                    chosen_is_target=(job['chosen'] == job['target']) if job['target'] != 'switch'
                                    else job['chosen'].startswith('switch:'),
                                    top_after=max(p, key=p.get))) + '\n')
    print(json.dumps(dict(jobs=len(jobs))))


def table():
    cells = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0.0]))
    for line in open(paths.TABLES / 'a3-counterfactual.jsonl'):
        r = json.loads(line)
        cell = cells[(r['edit'], r['source'])][r['cluster']]
        cell[0] += 1
        cell[1] += r['base']
        cell[2] += r['edited']
    out = []
    print('%-28s %-6s %6s  %-8s %-8s  %s' % ('edit', 'rows', 'n', 'before', 'after', 'after - before (95%)'))
    for (edit, source), clusters in sorted(cells.items()):
        cs = list(clusters.values())
        n = sum(c[0] for c in cs)
        d = compare._diff([(c[0], c[1], c[2]) for c in cs], draws=5000)
        before, after = sum(c[1] for c in cs) / n, sum(c[2] for c in cs) / n
        out.append(dict(edit=edit, source=source, n=n, before=before, after=after, diff=d))
        print('%-28s %-6s %6d  %-8.3f %-8.3f  %+.3f [%+.3f, %+.3f]' % (edit, source, n, before, after, d[0], d[1], d[2]))
    (paths.TABLES / 'a3-counterfactual.json').write_text(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    dict(run=run, table=table)[sys.argv[1]]()
