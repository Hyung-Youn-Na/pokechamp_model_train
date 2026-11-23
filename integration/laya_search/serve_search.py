"""EP-243 / D-219 (2-A): v13 GPU 0 serving + multi-turn MCTS root-Q & KL-regularized prior fusion.

    python -m integration.laya_search.serve_search --checkpoint DIR --model laya-v11rtc --ready-file F [--device cuda]

Non-invasively composes:
- `integration.laya_v13.render_v13.install()` (v13 input bugfixes preserved);
- `integration.laya_foe.data_foe` (batched opponent distribution `q` logged alongside `p` for diagnostics & 2-B);
- `integration.laya_search.search_worker` (pool of `WORKERS` CPU subprocesses in `foul-play` venv with per-game
  affinity + per-worker `threading.Lock`, eliminating the concurrent stdin/stdout race while running 4 battles'
  Rust MCTS in parallel);
- `search_core.choose_fused`: `score(a) = Q_mcts(a) + PRIOR_LAMBDA * ln(max(p(a), PRIOR_FLOOR))`, overriding argmax
  when `delta > MARGIN`, across BOTH `turn_action` AND `forced_switch` decisions (all legal actions searched).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import sha

from . import search_core as SC

FP_PYTHON = c.ROOT / '.tools/foul-play/.venv/bin/python'
DEFAULT_WORKERS = 4
_local = threading.local()


class SearchWorker:
    """Thread-safe single subprocess worker speaking line-delimited JSON to `search_worker.py`."""

    def __init__(self):
        self._lock = threading.Lock()
        self.process = None
        self._start()

    def _start(self):
        env = dict(
            os.environ,
            PYTHONHASHSEED='0',
            PYTHONDONTWRITEBYTECODE='1',
            PYTHONPATH='%s:%s' % (c.ROOT, c.ROOT / '.tools/foul-play/src'),
            CUDA_VISIBLE_DEVICES='',
        )
        self.process = subprocess.Popen(
            [str(FP_PYTHON), '-m', 'integration.laya_search.search_worker'],
            cwd=c.ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        )
        ready = json.loads(self.process.stdout.readline() or '{}')
        if ready.get('status') != 'ready':
            raise RuntimeError('search worker failed to start: %r' % (ready,))

    def call(self, request: dict) -> dict:
        with self._lock:
            try:
                self.process.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
                self.process.stdin.flush()
                line = self.process.stdout.readline()
                if not line:
                    raise RuntimeError('search worker exited')
                return json.loads(line)
            except Exception as exc:
                # Restart dead worker once; caller falls back cleanly to laya argmax for this turn
                try:
                    self.process.kill()
                except Exception:
                    pass
                try:
                    self._start()
                except Exception:
                    pass
                return dict(error='%s: %s' % (type(exc).__name__, exc))

    def close(self):
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                try:
                    self.process.terminate()
                except Exception:
                    pass


class WorkerPool:
    """Fixed-size pool of `SearchWorker`s with deterministic per-game affinity (preserves per-game Tracker state)."""

    def __init__(self, size: int = DEFAULT_WORKERS):
        self.workers = [SearchWorker() for _ in range(max(1, int(size)))]

    def _slot(self, game: str) -> int:
        h = int(hashlib.sha256(str(game).encode()).hexdigest()[:8], 16)
        return h % len(self.workers)

    def call(self, request: dict) -> dict:
        return self.workers[self._slot(request.get('game', ''))].call(request)

    def close(self):
        for w in self.workers:
            w.close()


def install(*, iterations: int = SC.MCTS_ITERATIONS, lam: float = SC.PRIOR_LAMBDA,
            floor: float = SC.PRIOR_FLOOR, margin: float = SC.MARGIN, workers: int = DEFAULT_WORKERS,
            value_checkpoint: str | None = None, value_alpha: float = 0.50, value_device: str = 'cuda'):
    from integration.laya_foe.data_foe import INSTRUCTIONS, foe_options
    from integration.laya_imitation import serving
    from integration.laya_v10 import training_v10
    from integration.pokechamp.imitation.schema import ImitationInput

    value_scorer = None
    if value_checkpoint:
        from . import value_model as VM
        value_scorer = VM.ValueScorer(value_checkpoint, device=value_device)

    class Input:
        @staticmethod
        def from_body(body):
            body = dict(body)
            _local.fp1 = body.pop('fp1', None)
            return ImitationInput.from_body(body)

    serving.ImitationInput = Input
    base = training_v10.Policy10
    pool = WorkerPool(size=workers)
    infer_lock = threading.Lock()

    class SearchPolicy(base):
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
            with infer_lock:
                rows = self.logits(items)
            probs, _ = self.distribution(rows[0], len(ids))
            p = dict(zip(ids, probs))
            q = None
            if foe_q is not None:
                fids = list(foe_q['criteria'])
                fprobs, _ = self.distribution(rows[1], len(fids))
                q = dict(zip(fids, fprobs))

            use_2b = value_scorer is not None
            info = dict(
                version='laya-search-2b-v1' if use_2b else SC.VERSION,
                laya=p, foe=q, q_mcts=None, v_mcts=None, q_vphi=None, root_q=None,
                scores=None, delta=0.0, pick=None, overridden=False,
            )
            expand_payload = None
            if fp1 is not None:
                req = dict(
                    op='search',
                    game=fp1['game'],
                    side=fp1['side'],
                    own_sets=fp1['own_sets'],
                    lines=fp1['lines'],
                    snapshot=fp1['snapshot'],
                    decision_kind=kind,
                    previous=fp1.get('previous'),
                    sample_id='%s:%s:%d:%s' % (fp1['game'], fp1['side'], len(fp1['lines']), kind),
                    action_ids=ids if (kind in ('turn_action', 'forced_switch') and len(ids) >= 2) else [],
                    iterations=iterations,
                )
                if use_2b and kind == 'turn_action' and q and len(ids) >= 2:
                    req['expand_2b'] = True
                    req['foe'] = q
                reply = pool.call(req)
                expand_payload = reply.pop('expand_2b', None)
                for k in ('q_mcts', 'v_mcts', 'root_q', 'unmapped', 'samples', 'used_samples',
                          'errors', 'seconds', 'worker_seconds', 'error', 'choices', 'iterations'):
                    if k in reply:
                        info[k] = reply[k]

            argmax = max(sorted(p), key=lambda a: p[a])
            if use_2b and expand_payload is not None:
                from . import search_2b as S2B
                raws = expand_payload.get('unique_raws') or []
                with infer_lock:
                    state_probs = value_scorer.score_raw_batch(raws) if raws else []
                q_vphi = S2B.aggregate_value_2b(expand_payload, state_probs)
                info['q_vphi'] = q_vphi
                info['vphi_states'] = len(raws)
                pick, scores, delta = S2B.choose_fused_2b(
                    p, info.get('q_mcts'), q_vphi, alpha=value_alpha, lam=lam, floor=floor, margin=margin,
                )
            else:
                pick, scores, delta = SC.choose_fused(p, info.get('q_mcts'), lam=lam, floor=floor, margin=margin)
            info['scores'] = {k: round(v, 6) for k, v in scores.items()} if scores else None
            info['delta'] = round(delta, 6)
            info['pick'] = pick
            info['overridden'] = bool(pick != argmax)
            out = SC.served_probs(p, pick)
            return dict(
                input_sha256=value.sha256,
                action_ids=ids,
                probabilities=out,
                choice=max(ids, key=lambda k: out[k]),
                search=info,
            )

    training_v10.Policy10 = SearchPolicy
    return pool


def search_identity(iterations=SC.MCTS_ITERATIONS, lam=SC.PRIOR_LAMBDA,
                    floor=SC.PRIOR_FLOOR, margin=SC.MARGIN, workers=DEFAULT_WORKERS,
                    value_checkpoint: str | None = None, value_alpha: float = 0.50) -> dict:
    here = c.ROOT / 'integration/laya_search'
    files = ['search_core.py', 'search_worker.py', 'serve_search.py']
    if value_checkpoint:
        files += ['featurize.py', 'value_model.py', 'search_2b.py']
    out = dict(
        version='laya-search-2b-v1' if value_checkpoint else SC.VERSION,
        iterations=iterations,
        prior_lambda=lam,
        prior_floor=floor,
        margin=margin,
        workers=workers,
        decision_kinds=['turn_action', 'forced_switch'],
        code={n: sha(here / n) for n in files},
    )
    if value_checkpoint:
        out['value_checkpoint'] = str(value_checkpoint)
        out['value_alpha'] = float(value_alpha)
    return out


if __name__ == '__main__':
    import sys
    from integration.foulplay.serve_v11 import MODELS
    from integration.laya_v10 import serve_v10
    from integration.laya_v11 import render_v11
    from integration.laya_v13 import render_v13

    # Peel off optional 2-B flags before forwarding standard flags to `serve_v10.main`
    argv = list(sys.argv[1:])
    val_ckpt, val_alpha, device = None, 0.50, 'cuda'
    clean_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == '--value-checkpoint' and i + 1 < len(argv):
            val_ckpt = argv[i + 1]
            i += 2
        elif argv[i] == '--value-alpha' and i + 1 < len(argv):
            val_alpha = float(argv[i + 1])
            i += 2
        else:
            if argv[i] == '--device' and i + 1 < len(argv):
                device = argv[i + 1]
            clean_argv.append(argv[i])
            i += 1

    serve_v10.MODELS = serve_v10.MODELS + tuple(m for m in MODELS if m not in serve_v10.MODELS)
    render_v13.install()
    install(value_checkpoint=val_ckpt, value_alpha=val_alpha, value_device=device)
    v13 = render_v13.version()
    record = dict(
        version=render_v13.VERSION,
        judge=render_v11.judge_identity(),
        code=v13['v13']['code'],
        v12_code=v13['v12']['code'],
        v11_code=v13.get('v11_code'),
    )
    sid = search_identity(value_checkpoint=val_ckpt, value_alpha=val_alpha)
    print('[serve] v13 + multi-turn search (%s): %s' % (sid['version'], json.dumps(sid)), flush=True)
    create_server = serve_v10.create_server

    def create_server_with_search(*args, **kwargs):
        server = create_server(*args, **kwargs)
        server.model_identity.update(v11_render=record, v12_render=v13['v12'], v13_render=v13['v13'], search=sid)
        return server

    serve_v10.create_server = create_server_with_search
    serve_v10.main(clean_argv)
