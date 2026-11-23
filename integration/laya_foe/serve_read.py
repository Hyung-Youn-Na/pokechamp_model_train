"""EP-238 EX-197 serving: v12 input + the opponent question + the one-turn read (laya env, CPU).

    python -m integration.laya_foe.serve_read --checkpoint DIR --model laya-v11rtc --ready-file F [--device cpu]

`laya_v10.serve_v10` (the `laya_imitation.serving` contract) with `render_v12.install()` as `laya_v12.serve_v12`, and
`training_v10.Policy10.predict` replaced:
1. the action question as served (v12 state) -> laya's distribution p;
2. on turn_action decisions, the opponent question (`data_foe.foe_options` on the same state, `data_foe.INSTRUCTIONS`)
   -> the opponent distribution q;
3. candidates: the actions with p >= NEAR * max p, at most MAX_CANDIDATES, by p. With two or more, `read_worker`
   (foul-play venv; one tracker per game, fed on every decision) returns the one-turn value of each candidate
   against q (`read.values`);
4. pick: the candidate of the highest value if it beats laya's argmax by more than MARGIN; otherwise laya's argmax.
The served `probabilities` are laya's p with the picked action's and the argmax's probabilities exchanged (so the
registered argmax policy plays the pick; nothing changes when the pick is the argmax). Every answer carries `read`
(laya p, q, candidates, values, pick, worker seconds / samples / errors). A worker error falls back to the argmax.
The request input carries the `fp1` member (`laya_fp1.battle_fp1.Fp1Session`); it is taken out before validation,
so `input_sha256` is the plain input's hash.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

from integration.laya_imitation import config as c

NEAR = 0.5
MAX_CANDIDATES = 3
MARGIN = 0.05
FP_PYTHON = c.ROOT / '.tools/foul-play/.venv/bin/python'
_local = threading.local()


class Worker:
    def __init__(self):
        env = dict(os.environ, PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH='%s:%s' % (c.ROOT, c.ROOT / '.tools/foul-play/src'), CUDA_VISIBLE_DEVICES='')
        self.process = subprocess.Popen([str(FP_PYTHON), '-m', 'integration.laya_foe.read_worker'], cwd=c.ROOT,
                                        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        if json.loads(self.process.stdout.readline() or '{}').get('status') != 'ready':
            raise RuntimeError('read worker failed to start')

    def call(self, request):
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('read worker exited')
        return json.loads(line)


def choose(p, values):
    """(pick, candidates) from laya's p and the candidates' values (None: no read)."""
    argmax = max(p, key=p.get)
    if not values:
        return argmax
    best = max(values, key=lambda a: (values[a], p[a]))
    if best != argmax and argmax in values and values[best] - values[argmax] > MARGIN:
        return best
    return argmax


def served(p, pick):
    out = dict(p)
    argmax = max(p, key=p.get)
    if pick != argmax:
        out[pick], out[argmax] = p[argmax], p[pick]
        if max(out, key=out.get) != pick:                     # ties: give the pick a hair more
            out[pick] += 1e-9
            s = sum(out.values())
            out = {k: v / s for k, v in out.items()}
    return out


def install():
    from integration.laya_foe.data_foe import INSTRUCTIONS, foe_options
    from integration.laya_imitation import serving
    from integration.laya_v10 import training_v10
    from integration.pokechamp.imitation.schema import ImitationInput

    class Input:
        @staticmethod
        def from_body(body):
            body = dict(body)
            _local.fp1 = body.pop('fp1', None)
            return ImitationInput.from_body(body)

    serving.ImitationInput = Input
    base = training_v10.Policy10
    worker = Worker()

    class ReadPolicy(base):
        def predict(self, value):
            fp1 = getattr(_local, 'fp1', None)
            state, question = self.renderer(value)
            ids = list(question['criteria'])
            kind = (fp1 or {}).get('decision_kind')
            items = [self.item(state, question)]
            foe_q = None
            if kind == 'turn_action' and len(ids) > 1:
                foe_q = dict(type='choice', instructions=INSTRUCTIONS, criteria=foe_options(state))
                items.append(self.item(state, foe_q))
            rows = self.logits(items)
            probs, _ = self.distribution(rows[0], len(ids))
            p = dict(zip(ids, probs))
            q = None
            if foe_q is not None:
                fids = list(foe_q['criteria'])
                fprobs, _ = self.distribution(rows[1], len(fids))
                q = dict(zip(fids, fprobs))
            top = max(p.values())
            cands = sorted((a for a in ids if p[a] >= NEAR * top), key=p.get, reverse=True)[:MAX_CANDIDATES]
            info = dict(laya=p, foe=q, candidates=cands, values=None, pick=None)
            if fp1 is not None:
                try:
                    reply = worker.call(dict(
                        op='read', game=fp1['game'], side=fp1['side'], own_sets=fp1['own_sets'], lines=fp1['lines'],
                        snapshot=fp1['snapshot'], decision_kind=kind, previous=fp1.get('previous'),
                        sample_id='%s:%s:%d:%s' % (fp1['game'], fp1['side'], len(fp1['lines']), kind),
                        candidates=cands if (q and len(cands) > 1) else [], foe=q))
                except Exception as exc:                  # a dead worker: restart once, play the argmax now
                    reply = dict(error='%s: %s' % (type(exc).__name__, exc))
                    try:
                        worker.__init__()
                    except Exception:
                        pass
                info.update({k: reply.get(k) for k in ('values', 'samples', 'errors', 'seconds', 'error', 'choices')})
            pick = choose(p, info.get('values'))
            info['pick'] = pick
            out = served(p, pick)
            return dict(input_sha256=value.sha256, action_ids=ids, probabilities=out,
                        choice=max(ids, key=lambda k: out[k]), read=info)

    training_v10.Policy10 = ReadPolicy


if __name__ == '__main__':
    from integration.foulplay.serve_v11 import MODELS
    from integration.laya_v10 import serve_v10
    from integration.laya_v11 import render_v11
    from integration.laya_v12 import render_v12
    serve_v10.MODELS = serve_v10.MODELS + tuple(m for m in MODELS if m not in serve_v10.MODELS)
    render_v12.install()
    install()
    v12 = render_v12.version()
    record = dict(version=render_v12.VERSION, judge=render_v11.judge_identity(), code=v12['v12']['code'],
                  v11_code=v12.get('v11_code'))
    from integration.laya_imitation.storage import sha
    here = c.ROOT / 'integration/laya_foe'
    read_identity = dict(near=NEAR, max_candidates=MAX_CANDIDATES, margin=MARGIN,
                         code={n: sha(here / n) for n in ('read.py', 'read_worker.py', 'serve_read.py', 'data_foe.py')})
    print('[serve] v12 input + one-turn read: %s' % json.dumps(read_identity), flush=True)
    create_server = serve_v10.create_server

    def create_server_with_read(*args, **kwargs):
        server = create_server(*args, **kwargs)
        server.model_identity.update(v11_render=record, v12_render=v12['v12'], read=read_identity)
        return server
    serve_v10.create_server = create_server_with_read
    serve_v10.main()
