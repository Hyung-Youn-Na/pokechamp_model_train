"""EX-165 (D-206, EP-229 stage 1): does the opponent model predict the human's moves, including the switch reads?

For every turn the human (`test`, p1) acted in four laya-play games (244, 255, 265 on 11/02 with v7t; 276 on 11/03 with
v9t), the human's decision input is rebuilt from the bot's recorded public stream (`opponent.opponent_input`):
- `oracle`: with the human's true team sets (from the Showdown log), an upper reference;
- `sampled`: with N_SAMPLES usage-sampled teams consistent with the bot's public knowledge, averaged.
The policy is v8lt (EX-155 selected, v8l renderer) on CPU. Reported: probability of the human's actual action,
top-1 agreement, and the eight read scenes. Read-only on all inputs; nothing here touches a battle.

    python -m integration.laya_search.scenes   (laya venv; writes runs/model-training/EX-165)
"""
from __future__ import annotations
import hashlib
import json
import math
import sys
import time
from pathlib import Path

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, sha

from . import opponent, sets

GAMES = Path('/workspace/.artifacts/laya-v7test/games')
LOGS = Path('/workspace/.artifacts/laya-v7test/pokemon-showdown/logs/2026-11/gen9ou')
BATTLES = {244: ('20261102-052821-blimAI-laya-v7t-002', '2026-11-02'),
           255: ('20261102-074448-smogonAI-laya-v7t-002', '2026-11-02'),
           265: ('20261102-081753-trainedAI-laya-v7t-001', '2026-11-02'),
           276: ('20261103-011649-smogonAI-laya-v9t-001', '2026-11-03')}
# (battle, turn) -> scene label (D-205 context: the human's switch reads; 265 T25 is the miss)
SCENES = {(276, 9): 'read: U-turn vs Gholdengo -> Great Tusk in', (244, 2): 'read: Ice Spinner -> Zapdos in',
          (244, 34): 'read: Ice Spinner -> Great Tusk in', (244, 36): 'read: Ice Spinner -> Zapdos in',
          (244, 39): 'read: Freeze-Dry -> Slowking in', (255, 5): 'read: Ice Spinner -> Garchomp in',
          (255, 15): 'read: Earth Power -> Tyranitar in', (265, 21): 'read: Ice Spinner -> Gliscor in',
          (265, 25): 'missed read: Ice Spinner, no switch'}
N_SAMPLES = 8
OUT = c.SHARED / 'runs/model-training/EX-165'
CHECKPOINT = c.RUN_V8L_TRAINING / 'checkpoints/selected'


def ident(x):
    return ''.join(ch for ch in str(x).lower() if ch.isalnum())


def true_team(log):
    """The human's sets in preview order (Showdown log `p1team`)."""
    order = [ident(line.split('|')[3].split(',')[0]) for line in log['log'] if line.startswith('|poke|p1|')]
    by = {ident(s['species']): s for s in log['p1team']}
    out = []
    for sp in order:
        s = by[sp]
        out.append(dict(species=sp, item=ident(s.get('item', '')), ability=ident(s.get('ability', '')),
                        moves=[ident(m) for m in s['moves']], nature=ident(s.get('nature', 'serious')),
                        evs=s.get('evs') or {}, ivs=s.get('ivs') or {}, level=s.get('level', 100),
                        teraType=ident(s.get('teraType', ''))))
    return out, order


def human_actions(log, order):
    """turn -> action id of p1's first own decision in that turn (moves, voluntary switches)."""
    out, turn, tera = {}, 0, False
    for line in log['log']:
        p = line.split('|')
        if len(p) < 2:
            continue
        if p[1] == 'turn':
            turn, tera = int(p[2]), False
        elif p[1] == '-terastallize' and p[2].startswith('p1a'):
            tera = True
        elif turn and turn not in out and p[1] == 'move' and p[2].startswith('p1a') and '[from]' not in line:
            out[turn] = 'move:%s:%s' % (ident(p[3]), 'tera' if tera else 'normal')
        elif turn and turn not in out and p[1] == 'switch' and p[2].startswith('p1a') and '[from]' not in line:
            out[turn] = 'switch:%d' % (order.index(ident(p[3].split(',')[0])) + 1)
    return out


def decisions(battle):
    """(turn, frames before the bot's turn-action input, bot snapshot, bot actor) per turn."""
    events = [json.loads(line) for line in open(GAMES / BATTLES[battle][0] / 'events.jsonl')]
    frames, out, seen = [], [], set()
    for e in events:
        if e['type'] == 'protocol':
            frames.append(e)
        elif e['type'] == 'input':
            s = json.loads(e['body']['state'])['snapshot']
            if s['decision_kind'] == 'turn_action' and s['turn'] not in seen:
                seen.add(s['turn'])
                out.append((s['turn'], list(frames), s, e['actor']))
    return out


def seed(battle, turn):
    return int(hashlib.sha256(('EX-165:%d:%d' % (battle, turn)).encode()).hexdigest()[:8], 16)


def main():
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.policy import Policy
    from integration.laya_imitation.serving import v8l_renderer
    from integration.pokechamp.imitation.metamon_bridge import BridgeClient
    if (OUT / 'result.json').exists():
        raise RuntimeError('EX-165 already run')
    rows, started = [], time.time()
    with Calc() as calc, BridgeClient() as bridge:
        policy = Policy(CHECKPOINT, device='cpu', head_limit=c.V2_HEAD_LIMIT, renderer=v8l_renderer(calc),
                        token_limit=c.TOKEN_LIMIT)
        for battle in BATTLES:
            log = json.load(open(LOGS / BATTLES[battle][1] / ('gen9ou-%d.log.json' % battle)))
            team, order = true_team(log)
            acted = human_actions(log, order)
            for turn, frames, snap, actor in decisions(battle):
                actual = acted.get(turn)
                if actual is None:
                    continue
                row = dict(battle=battle, turn=turn, actual=actual, scene=SCENES.get((battle, turn)))
                try:
                    oracle = policy.predict(opponent.opponent_input(bridge, frames, actor, team))['probabilities']
                    samples = [policy.predict(opponent.opponent_input(bridge, frames, actor, t))['probabilities']
                               for t in sets.sample_teams(snap['opponent_team'], N_SAMPLES, seed(battle, turn))]
                except Exception as exc:   # recorded, not hidden
                    rows.append(dict(row, error='%s: %s' % (type(exc).__name__, exc)))
                    continue
                keys = sorted({k for s in samples for k in s})
                mean = {k: sum(s.get(k, 0.0) for s in samples) / len(samples) for k in keys}
                row.update(p_oracle=oracle.get(actual, 0.0), p_sampled=mean.get(actual, 0.0),
                           p_sampled_each=[round(s.get(actual, 0.0), 4) for s in samples],
                           top_oracle=max(oracle, key=oracle.get), top_sampled=max(mean, key=mean.get),
                           top3_sampled=sorted(mean.items(), key=lambda kv: -kv[1])[:3],
                           top3_oracle=sorted(oracle.items(), key=lambda kv: -kv[1])[:3],
                           p_switch_sampled=sum(v for k, v in mean.items() if k.startswith('switch:')))
                rows.append(row)
                print(json.dumps({k: row[k] for k in ('battle', 'turn', 'actual', 'p_oracle', 'p_sampled', 'scene')}),
                      flush=True)
    ok = [r for r in rows if 'error' not in r]
    nll = lambda key: sum(-math.log(max(r[key], 1e-6)) for r in ok) / len(ok)
    summary = dict(decisions=len(rows), errors=len(rows) - len(ok),
                   nll_oracle=nll('p_oracle'), nll_sampled=nll('p_sampled'),
                   top1_oracle=sum(r['top_oracle'] == r['actual'] for r in ok) / len(ok),
                   top1_sampled=sum(r['top_sampled'] == r['actual'] for r in ok) / len(ok),
                   scenes=[{k: r.get(k) for k in ('battle', 'turn', 'scene', 'actual', 'p_oracle', 'p_sampled',
                                                  'p_sampled_each', 'top3_sampled', 'top3_oracle', 'error')}
                           for r in rows if r['scene']])
    atomic(OUT / 'result.json', dict(summary=summary, rows=rows, checkpoint=str(CHECKPOINT),
                                     samples=N_SAMPLES, usage_sha256=sha(sets.USAGE), seconds=time.time() - started),
           immutable=True)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
