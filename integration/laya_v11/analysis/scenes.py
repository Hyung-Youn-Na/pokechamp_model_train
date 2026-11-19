"""EX-169 A6: the ladder regression scenes — the bot's real inputs, kept so any renderer and model can be re-scored.

    python -m integration.laya_v11.analysis.scenes build      # scenes/scenes.jsonl (+ manifest)

A scene is one request body of a ladder game (`events.jsonl` input) with what is known about the options there.
`unacceptable` is set from facts the renderer under test cannot change: the fixed engine judge's confirmed failures and
x0 damage (computed here once with the EX-170 configuration: usage extension + fixed judge), and a move that had just
failed against the same foe. Kinds:
- `dead`: v10rt (as deployed that day) chose an unacceptable option.
- `repeat_fail`: v10rt repeated the move that had just failed against the same foe.
- `setup`: the foe had +2 or more Atk / SpA, or used a set-up move that turn, and v10rt chose a status move, Protect or
  an unacceptable option. No single right answer is marked; the report gives the probability of passive options.
- `losing_duel`: `duel -> lose` with a switch available and v10rt stayed in. Reported as switch probability.
- `control`: decisions of won games with none of the attribution tags; reported as agreement with v10rt's choice.
The scenes come only from the ladder games, which no training row uses (D-209 decision 4).
"""
from __future__ import annotations
from collections import Counter
import json
import random
import sys

from .. import paths
from . import attribution, games, render
from . import features as F
from . import rules
from . import score as S

CONTROL = 300
QUIET = ('dead_pick', 'failed_unmarked', 'protect_blocked', 'sucker_whiff', 'duel_lose_stay', 'boosted_foe_stay',
         'let_setup', 'repeat_after_fail', 'stalled_repeat', 'protect_again', 'ko_taken')


def build():
    paths.SCENES.mkdir(parents=True, exist_ok=True)
    target = paths.SCENES / 'scenes.jsonl'
    if target.exists():
        raise FileExistsError(target)
    from integration.pokechamp.imitation.schema import ImitationInput
    identity = render.configure(ext=True, fix=True)
    renderer = render.live_renderer()
    rng = random.Random(paths.SEED)
    bodies = {}
    for name in games.names():
        game = games.Game(name)
        for e in game.inputs:
            bodies[e['decision'], name] = e['body']
    scenes, quiet = [], []
    for row in S.decisions():
        if row['automatic'] or row['state'] is None:
            continue
        body = bodies[row['decision'], row['game']]
        state, question = renderer(ImitationInput.from_body(body))
        facts = F.describe(state, question['criteria'])
        if facts['kind'] != 'turn_action':
            continue
        own = F.describe(row['state'], row['criteria'])            # as v10rt saw it that day
        chosen = F.chosen(facts, row['choice'])
        dead = sorted(a for a, m in facts['marks'].items() if m['dead'])
        repeat = sorted(a for a, m in facts['marks'].items()
                        if m['move'] and m['move'] == facts['last_move'] and facts['last_fate'] in ('fail', 'immune')
                        and rules._same_foe(state, facts['turn']))
        unacceptable = sorted(set(dead) | set(repeat))
        passive = sorted(a for a, m in facts['marks'].items() if m['move'] and (m['status'] or m['dead']))
        after = row['after']
        kinds = []
        if row['choice'] in dead:
            kinds.append('dead')
        if row['choice'] in repeat:
            kinds.append('repeat_fail')
        if (facts['opp_offence'] >= 2 or (after['opp_boosts'] >= 2 and after['opp_move'] in games.SETUP)) and \
                row['choice'] in passive:
            kinds.append('setup')
        if facts['duel'] == 'lose' and facts['has_switch'] and not chosen['switch']:
            kinds.append('losing_duel')
        base = dict(game=row['game'], decision=row['decision'], turn=facts['turn'], result=row['result'],
                    policy=row['policy'], v10rt_choice=row['choice'], v10rt_probability=row['probabilities'][row['choice']],
                    unacceptable=unacceptable, passive=passive, body=body)
        if kinds:
            scenes.append(dict(base, kinds=kinds))
        elif row['result'] == 'win' and row['policy'] != 'sample' and not unacceptable and \
                not any(t in QUIET for t in attribution.tags(row, own)):
            quiet.append(dict(base, kinds=['control']))
    quiet.sort(key=lambda s: (s['game'], s['decision']))
    scenes.extend(rng.sample(quiet, min(CONTROL, len(quiet))))
    scenes.sort(key=lambda s: (s['game'], s['decision']))
    with open(target, 'w') as f:
        for s in scenes:
            f.write(json.dumps(s, ensure_ascii=False, separators=(',', ':')) + '\n')
    counts = Counter(k for s in scenes for k in s['kinds'])
    manifest = dict(scenes=len(scenes), kinds=dict(counts), games=len({s['game'] for s in scenes}),
                    control_pool=len(quiet), configuration=identity, seed=paths.SEED,
                    note='unacceptable/passive are action ids under usage extension + fixed judge')
    (paths.SCENES / 'manifest.json').write_text(json.dumps(manifest, indent=1, default=str))
    print(json.dumps(manifest, indent=1, default=str))
    return manifest


if __name__ == '__main__':
    dict(build=build)[sys.argv[1]]()
