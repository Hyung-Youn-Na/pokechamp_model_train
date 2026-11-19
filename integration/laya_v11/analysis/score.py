"""EX-169: score rendered inputs with a checkpoint (serving's own path, `Policy10`), on GPU3.

    python -m integration.laya_v11.analysis.score verify     # re-rendered bot decisions vs the logged probabilities

`Scorer.probabilities(rows)` takes dicts with `state`, `criteria` and `instructions` and returns one
{action id: probability} per row at the checkpoint's temperature, as serving does.
"""
from __future__ import annotations
import json
import os
import sys

from integration.laya_imitation import config as c
from integration.laya_imitation.resources import gpu

from .. import paths


def question(row):
    return dict(type='choice', instructions=row['instructions'], criteria=row['criteria'])


class Scorer:
    def __init__(self, checkpoint=paths.V10RT, device='cuda'):
        from integration.laya_v10 import paths as p10, training_v10
        training_v10.require_laya()
        self.policy = training_v10.Policy10(checkpoint, device=device, token_limit=p10.TOKEN_LIMIT,
                                            head_limit=p10.HEAD_LIMIT)

    def probabilities(self, rows, batch_size=16):
        items = [self.policy.item(r['state'], question(r)) for r in rows]
        out = []
        for row, logits in zip(rows, self.policy.logits(items, batch_size)):
            ids = list(row['criteria'])
            probs, _ = self.policy.distribution(logits, len(ids))
            out.append(dict(zip(ids, probs)))
        return out


def held_gpu(index=c.GPU3_INDEX, uuid=c.GPU3_UUID):
    """Context manager: hold the GPU (pinned UUID, idle) and point this process at it. Enter before importing torch."""
    holder = gpu(index, uuid)

    class _Held:
        def __enter__(self):
            env, device = holder.__enter__()
            os.environ.update(env)
            return device

        def __exit__(self, *args):
            return holder.__exit__(*args)
    return _Held()


def decisions():
    return [json.loads(line) for line in open(paths.TABLES / 'decisions.jsonl')]


def verify():
    """The re-rendered text reproduces what the model saw when the re-scored probabilities equal the logged ones."""
    rows = [r for r in decisions() if not r['automatic'] and r['state'] is not None]
    with held_gpu():
        probs = Scorer().probabilities(rows)
    diffs, bad = [], []
    for row, p in zip(rows, probs):
        logged = row['probabilities']
        if set(logged) != set(p):
            bad.append(dict(game=row['game'], decision=row['decision'], reason='action ids differ'))
            continue
        d = max(abs(p[a] - logged[a]) for a in p)
        diffs.append(d)
        if d > 0.01:
            bad.append(dict(game=row['game'], decision=row['decision'], turn=row['turn'], diff=round(d, 4),
                            ext=row['ext'], fix=row['fix']))
    diffs.sort()
    out = dict(rows=len(rows), compared=len(diffs), max=diffs[-1], p99=diffs[int(0.99 * len(diffs))],
               median=diffs[len(diffs) // 2], over_0_01=len(bad), games_with_mismatch=sorted({b['game'] for b in bad}),
               examples=bad[:40])
    (paths.TABLES / 'verify.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'examples'}, indent=1))
    for b in bad[:40]:
        print(b)
    return out


if __name__ == '__main__':
    dict(verify=verify)[sys.argv[1]]()
