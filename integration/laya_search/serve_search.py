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
            value_checkpoint: str | None = None, value_alpha: float = 0.50, value_device: str = 'cuda',
            v2: bool = False, way_a: bool = False, way_a_v2: bool = False, way_b: bool = False,
            two_ply: bool = False, no_calc_duel: bool = False, no_search: bool = False):
    from integration.laya_foe.data_foe import INSTRUCTIONS, foe_options
    from integration.laya_imitation import serving
    from integration.laya_v10 import training_v10
    from integration.pokechamp.imitation.schema import ImitationInput

    if v2 or way_a or way_a_v2 or way_b:
        from . import search_2b_v2 as S2BV2
        foe_opt_fn = S2BV2.foe_options_clean
    else:
        foe_opt_fn = foe_options

    value_scorer = None
    is_v3_scorer = False
    if value_checkpoint and not no_search:
        from . import value_model_v3 as VM3
        value_scorer = VM3.load_any_scorer_v3(value_checkpoint, device=value_device)
        is_v3_scorer = (getattr(value_scorer, 'cfg', {}) or {}).get('arch') == 'future_deepsets_v3'

    class Input:
        @staticmethod
        def from_body(body):
            body = dict(body)
            _local.fp1 = body.pop('fp1', None)
            return ImitationInput.from_body(body)

    serving.ImitationInput = Input
    base = training_v10.Policy10
    pool = None if no_search else WorkerPool(size=workers)
    infer_lock = threading.Lock()

    class SearchPolicy(base):
        def predict(self, value):
            fp1 = getattr(_local, 'fp1', None)
            state_raw, question = self.renderer(value)
            if no_calc_duel:
                from . import matchup_eval as ME
                state = ME.strip_calc_duel(state_raw)
            else:
                state = state_raw
            ids = list(question['criteria'])
            kind = (fp1 or {}).get('decision_kind')
            items = [self.item(state, question)]
            foe_q = None
            if (not no_search) and kind == 'turn_action' and len(ids) > 1:
                foe_q = dict(type='choice', instructions=INSTRUCTIONS, criteria=foe_opt_fn(state))
                items.append(self.item(state, foe_q))
            with infer_lock:
                rows = self.logits(items)
            probs, _ = self.distribution(rows[0], len(ids))
            p = dict(zip(ids, probs))
            argmax = max(sorted(p), key=lambda a: p[a])

            if no_search:
                info = dict(
                    version='laya-standalone',
                    laya=p, foe=None, q_mcts=None, v_mcts=None, q_vphi=None, root_q=None,
                    scores=None, delta=0.0, pick=argmax, overridden=False, no_search=True,
                )
                return dict(
                    input_sha256=value.sha256,
                    action_ids=ids,
                    probabilities=p,
                    choice=argmax,
                    search=info,
                )

            q = None
            if foe_q is not None:
                fids = list(foe_q['criteria'])
                fprobs, _ = self.distribution(rows[1], len(fids))
                q = dict(zip(fids, fprobs))

            use_2b = value_scorer is not None
            if way_b:
                ver = 'laya-way-b' + ('+2ply' if two_ply else '')
            elif way_a_v2:
                from . import way_a_v2 as WA2
                ver = WA2.VERSION_WAY_A_V2 + ('+2ply' if two_ply else '')
            elif way_a:
                from . import way_a as WA
                ver = WA.VERSION_WAY_A
            else:
                ver = ('laya-search-2b-v2' if v2 else 'laya-search-2b-v1') if use_2b else SC.VERSION
            info = dict(
                version=ver,
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
                    if is_v3_scorer or way_a_v2 or way_b or two_ply:
                        req['v3'] = True
                        if two_ply:
                            req['cache_2ply'] = True
                    elif v2 or way_a:
                        req['v2'] = True
                reply = pool.call(req)
                expand_payload = reply.pop('expand_2b', None)
                for k in ('q_mcts', 'v_mcts', 'root_q', 'unmapped', 'samples', 'used_samples',
                          'errors', 'seconds', 'worker_seconds', 'error', 'choices', 'iterations'):
                    if k in reply:
                        info[k] = reply[k]

            q_vphi = None
            if use_2b and expand_payload is not None:
                from . import search_2b as S2B
                raws = expand_payload.get('unique_raws') or []
                with infer_lock:
                    state_probs = value_scorer.score_raw_batch(raws) if raws else []
                q_1ply = S2B.aggregate_value_2b(expand_payload, state_probs)
                q_vphi = q_1ply
                info['vphi_states'] = len(raws)
                if two_ply and fp1 is not None and q_1ply:
                    from . import search_multiturn as SMT
                    cand_set, s1_indices = SMT.select_ply2_targets(expand_payload.get('branches') or {}, q_1ply, p)
                    if s1_indices:
                        rep2 = pool.call(dict(op='expand_2ply', game=fp1['game'], s1_indices=s1_indices))
                        s2_raws = rep2.get('unique_raws') or []
                        with infer_lock:
                            s2_probs = value_scorer.score_raw_batch(s2_raws) if s2_raws else []
                        q_vphi = SMT.backup_2ply_q(
                            expand_payload.get('branches') or {}, state_probs, q_1ply,
                            cand_set, rep2.get('grid') or {}, s2_probs,
                        )
                        info['q_vphi_1ply'] = q_1ply
                        info['vphi_ply2_states'] = len(s2_raws)
                        info['vphi_ply2_actions'] = cand_set
                info['q_vphi'] = q_vphi

            if way_b:
                from integration.laya_v14 import data_way_b as DWB
                from . import matchup_eval as ME
                absorb_pen = (expand_payload or {}).get('absorb_penalties')
                active_turn = (kind in ('turn_action', 'forced_switch') and len(ids) >= 2)
                tool_lines = DWB.render_tool_lines(
                    info.get('q_mcts'), q_vphi, ids, absorb_penalties=absorb_pen,
                ) if active_turn else ''
                matchup_info = ME.assess_matchup(
                    info.get('q_mcts'), q_vphi, valid_ids=set(ids), absorb_penalties=absorb_pen,
                ) if active_turn else None
                info['laya_base'] = p
                info['tool_lines'] = tool_lines
                info['matchup'] = matchup_info
                if tool_lines:
                    state_tool = state.rstrip('\n') + '\n' + tool_lines
                    with infer_lock:
                        rows2 = self.logits([self.item(state_tool, question)])
                    probs2, _ = self.distribution(rows2[0], len(ids))
                    p_final = dict(zip(ids, probs2))
                else:
                    p_final = p
                pick = max(sorted(p_final), key=lambda a: p_final[a])
                scores = p_final
                delta = float(p_final[pick] - p_final.get(argmax, 0.0))
                info['laya'] = p_final
                info['way_b_meta'] = dict(
                    used_tool=bool(tool_lines),
                    base_pick=argmax,
                    final_pick=pick,
                    base_p_pick=round(float(p.get(pick, 0.0)), 6),
                    final_p_pick=round(float(p_final[pick]), 6),
                    final_p_base=round(float(p_final.get(argmax, 0.0)), 6),
                    matchup_label=(matchup_info or {}).get('label'),
                )
                info['scores'] = {k: round(v, 6) for k, v in scores.items()} if scores else None
                info['delta'] = round(delta, 6)
                info['pick'] = pick
                info['overridden'] = bool(pick != argmax)
                return dict(
                    input_sha256=value.sha256,
                    action_ids=ids,
                    probabilities=p_final,
                    choice=pick,
                    search=info,
                )

            if way_a_v2:
                from . import way_a_v2 as WA2
                pick, scores, delta, wa_meta = WA2.choose_way_a_v2(
                    p, info.get('q_mcts'), q_vphi, state=state_raw, decision_kind=kind,
                    absorb_penalties=(expand_payload or {}).get('absorb_penalties'),
                    just_protected=bool((expand_payload or {}).get('just_protected', False)),
                )
                info['way_a_meta'] = wa_meta
            elif way_a:
                from . import way_a as WA
                pick, scores, delta, wa_meta = WA.choose_way_a(
                    p, info.get('q_mcts'), q_vphi, state=state, decision_kind=kind,
                    absorb_penalties=(expand_payload or {}).get('absorb_penalties'),
                )
                info['way_a_meta'] = wa_meta
            elif use_2b and q_vphi is not None:
                if v2:
                    from . import search_2b_v2 as S2BV2
                    pick, scores, delta, v2_meta = S2BV2.choose_fused_2b_v2(
                        p, info.get('q_mcts'), q_vphi, state=state,
                        absorb_penalties=(expand_payload or {}).get('absorb_penalties'),
                        alpha=value_alpha, lam=lam, floor=floor, margin=margin,
                    )
                    info['v2_meta'] = v2_meta
                else:
                    from . import search_2b as S2B
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
                    value_checkpoint: str | None = None, value_alpha: float = 0.50, v2: bool = False,
                    way_a: bool = False, way_a_v2: bool = False, way_b: bool = False, two_ply: bool = False,
                    walled_duel: bool = False, no_calc_duel: bool = False, no_search: bool = False) -> dict:
    here = c.ROOT / 'integration/laya_search'
    files = ['search_core.py', 'search_worker.py', 'serve_search.py']
    if value_checkpoint and not no_search:
        files += ['featurize.py', 'value_model.py', 'search_2b.py']
        if v2 or way_a or way_a_v2 or way_b:
            files.append('search_2b_v2.py')
        if way_a or way_a_v2:
            files += ['matchup_features.py', 'value_model_v2.py', 'way_a.py']
        if way_a_v2 or way_b or two_ply:
            files += ['featurize_v3.py', 'value_model_v3.py', 'way_a_v2.py', 'matchup_eval.py', 'search_multiturn.py']
    if no_search:
        ver = 'laya-standalone'
    elif way_b:
        ver = 'laya-way-b' + ('+2ply' if two_ply else '')
    elif way_a_v2:
        from . import way_a_v2 as WA2
        ver = WA2.VERSION_WAY_A_V2 + ('+2ply' if two_ply else '')
    elif way_a:
        from . import way_a as WA
        ver = WA.VERSION_WAY_A
    else:
        ver = ('laya-search-2b-v2' if v2 else 'laya-search-2b-v1') if value_checkpoint else SC.VERSION
    code_map = {n: sha(here / n) for n in files if (here / n).exists()}
    if way_b:
        dwb = c.ROOT / 'integration/laya_v14/data_way_b.py'
        if dwb.exists():
            code_map['data_way_b.py'] = sha(dwb)
    out = dict(
        version=ver,
        iterations=0 if no_search else iterations,
        prior_lambda=lam,
        prior_floor=floor,
        margin=margin,
        workers=0 if no_search else workers,
        decision_kinds=['turn_action', 'forced_switch'],
        code=code_map,
    )
    if no_search:
        out['no_search'] = True
    elif value_checkpoint:
        out['value_checkpoint'] = str(value_checkpoint)
        out['value_alpha'] = float(value_alpha)
        if v2:
            out['v2'] = True
        if way_a:
            out['way_a'] = True
        if way_a_v2:
            out['way_a_v2'] = True
        if way_b:
            out['way_b'] = True
        if two_ply:
            out['two_ply'] = True
    if walled_duel:
        out['walled_duel'] = True
    if no_calc_duel:
        out['no_calc_duel'] = True
    return out


if __name__ == '__main__':
    import sys
    from integration.foulplay.serve_v11 import MODELS
    from integration.laya_v10 import serve_v10
    from integration.laya_v11 import render_v11
    from integration.laya_v13 import render_v13

    # Peel off optional 2-B / v2 / way-a / way-a-v2 / way-b / two-ply / no-search / iterations / worker / renderer flags
    argv = list(sys.argv[1:])
    val_ckpt, val_alpha, device, workers, v2, use_v14 = None, None, 'cuda', DEFAULT_WORKERS, False, False
    way_a, way_a_v2, way_b, two_ply, walled_duel, no_calc_duel, no_search, iterations = (
        False, False, False, False, False, False, False, SC.MCTS_ITERATIONS
    )
    clean_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == '--value-checkpoint' and i + 1 < len(argv):
            val_ckpt = argv[i + 1]
            i += 2
        elif argv[i] == '--value-alpha' and i + 1 < len(argv):
            val_alpha = float(argv[i + 1])
            i += 2
        elif argv[i] == '--workers' and i + 1 < len(argv):
            workers = int(argv[i + 1])
            i += 2
        elif argv[i] == '--iterations' and i + 1 < len(argv):
            iterations = int(argv[i + 1])
            i += 2
        elif argv[i] == '--v2':
            v2 = True
            i += 1
        elif argv[i] == '--way-a':
            way_a = True
            i += 1
        elif argv[i] == '--way-a-v2':
            way_a_v2 = True
            i += 1
        elif argv[i] == '--way-b':
            way_b = True
            i += 1
        elif argv[i] == '--two-ply':
            two_ply = True
            i += 1
        elif argv[i] == '--walled-duel':
            walled_duel = True
            i += 1
        elif argv[i] == '--no-calc-duel':
            no_calc_duel = True
            i += 1
        elif argv[i] == '--no-search':
            no_search = True
            i += 1
        elif argv[i] == '--v14':
            use_v14 = True
            i += 1
        else:
            if argv[i] == '--device' and i + 1 < len(argv):
                device = argv[i + 1]
            clean_argv.append(argv[i])
            i += 1

    if val_alpha is None:
        val_alpha = 0.65 if v2 else 0.50

    extra_models = tuple(MODELS) + (
        'laya-search2b', 'laya-search2bv2', 'laya-waya', 'laya-waya-v2',
        'laya-ex225-waya-v2', 'laya-ex226-wayb',
    )
    serve_v10.MODELS = serve_v10.MODELS + tuple(m for m in extra_models if m not in serve_v10.MODELS)
    if use_v14:
        from integration.laya_v14 import render_v14
        render_v14.install()
        v_info = render_v14.version()
        r_ver = render_v14.VERSION
    else:
        render_v13.install()
        v_info = render_v13.version()
        r_ver = render_v13.VERSION
    if way_a_v2:
        from . import way_a_v2 as WA2
        WA2.install_plausible_threat_duel()
        r_ver = r_ver.rstrip(']') + (',noduel,matchup_eval]' if no_calc_duel else ',walled_duel,plausible_threat]')
    elif way_b:
        if walled_duel and not no_calc_duel:
            from . import way_a as WA
            WA.install_walled_duel()
        r_ver = r_ver.rstrip(']') + (',noduel,wayb]' if no_calc_duel else ',walled_duel,wayb]')
    elif walled_duel:
        from . import way_a as WA
        WA.install_walled_duel()
        r_ver = r_ver.rstrip(']') + ',walled_duel]'
    install(iterations=iterations, workers=workers, value_checkpoint=val_ckpt, value_alpha=val_alpha,
            value_device=device, v2=v2, way_a=way_a, way_a_v2=way_a_v2, way_b=way_b, two_ply=two_ply,
            no_calc_duel=no_calc_duel, no_search=no_search)
    record = dict(
        version=r_ver,
        judge=render_v11.judge_identity(),
        code=v_info.get('v14', v_info['v13'])['code'],
        v12_code=v_info['v12']['code'],
        v11_code=v_info.get('v11_code'),
    )
    sid = search_identity(iterations=iterations, workers=workers, value_checkpoint=val_ckpt,
                          value_alpha=val_alpha, v2=v2, way_a=way_a, way_a_v2=way_a_v2, way_b=way_b,
                          two_ply=two_ply, walled_duel=walled_duel, no_calc_duel=no_calc_duel,
                          no_search=no_search)
    print('[serve] %s + multi-turn search (%s, iters=%d): %s' % (
        'v14' if use_v14 else 'v13', sid['version'], sid['iterations'], json.dumps(sid)), flush=True)
    create_server = serve_v10.create_server

    def create_server_with_search(*args, **kwargs):
        server = create_server(*args, **kwargs)
        upd = dict(v11_render=record, v12_render=v_info['v12'], v13_render=v_info['v13'], search=sid)
        if use_v14:
            upd['v14_render'] = v_info['v14']
        server.model_identity.update(**upd)
        return server

    serve_v10.create_server = create_server_with_search
    serve_v10.main(clean_argv)
