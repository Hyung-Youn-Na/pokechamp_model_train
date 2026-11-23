"""EP-243 / D-219 (EX-209, 1-B): Offline MCTS-5k root-Q candidate-internal rerank target generator.

    # Step 1: GPU 0 & GPU 1 candidate inference (2 processes, strictly GPU 0 & 1 ONLY)
    python -m integration.laya_search.data_mcts_1b infer --rank 0 --world 2
    python -m integration.laya_search.data_mcts_1b infer --rank 1 --world 2

    # Step 2: CPU 48-worker MCTS 5k root-Q computation (foul-play venv, PYTHONHASHSEED=0, non-overlapping with battles)
    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python \
        -m integration.laya_search.data_mcts_1b mcts --workers 48

    # Step 3: Build KL-regularized soft targets (any python)
    python3 -m integration.laya_search.data_mcts_1b targets

Design (controlled A/B vs EX-199/200):
- Starts from EX-196 `p` over `v12-fresh/train.jsonl` (excluding EX-199 heldout games & Blim 64 evaluation teams).
- Subsamples `TRAIN_GAMES = 2200` (~60k multi-option decisions across `turn_action` and `forced_switch`) plus
  `EX-199` held-out games for target-agreement evaluation.
- Candidate set: top actions with `p >= NEAR * max_p` (up to `MAX_CANDIDATES = 4`, at least 2), PLUS automatic
  promotion of any decisive MCTS tactical rescue (`Q_mcts(best) - Q_mcts(argmax) >= RESCUE_GAP`).
- Gold target inside candidate set C: `g(a) ∝ p(a) * exp(Q_mcts(a) / TAU_Q)` preserving total candidate mass
  (exact KL-regularized policy improvement, avoiding EX-185's raw-visit-share distortion and EX-199's 1-turn bias).
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
import traceback

from . import featurize as F
from . import search_core as SC

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
GEN = SHARED / 'datasets/generated'
SOURCE = GEN / 'laya-compact-imitation/v12-fresh/train.jsonl'
RUN = SHARED / 'runs/model-training/EX-209'
OUT = GEN / 'laya-mcts5k-q/v1'
INIT_CKPT = SHARED / 'runs/model-training/EX-196/checkpoints/selected'

SEED = 20261209
TRAIN_GAMES = 2200
NEAR = 0.15
MAX_CANDIDATES = 4
RESCUE_GAP = 0.08
TAU_Q = SC.PRIOR_LAMBDA          # 0.03: exact soft-target counterpart of 2-A KL-regularized policy
MCTS_ITERS = SC.MCTS_ITERATIONS  # 5000


def sample_id_of(line: str) -> str:
    return line[14:line.index('"', 14)]


def game_of(sid: str) -> str:
    return sid.rsplit(':', 3)[0]


def select_candidates(p: dict[str, float], q_mcts: dict[str, float] | None = None) -> list[str]:
    """Select candidate actions for trust-region reranking, promoting decisive MCTS tactical rescues."""
    if not p:
        return []
    ranked = sorted(sorted(p), key=lambda a: p[a], reverse=True)
    top_p = p[ranked[0]]
    cands = [a for a in ranked if p[a] >= NEAR * top_p][:MAX_CANDIDATES]
    if len(cands) < 2 and len(ranked) >= 2:
        cands = ranked[:2]
    if q_mcts:
        argmax = ranked[0]
        scored = [a for a in q_mcts if a in p and math.isfinite(q_mcts[a])]
        if scored:
            best_q = max(sorted(scored), key=lambda a: (q_mcts[a], p[a]))
            ref_q = q_mcts.get(argmax)
            if best_q not in cands and ref_q is not None and (q_mcts[best_q] - ref_q) >= RESCUE_GAP:
                cands.append(best_q)
    return cands


def gold_mcts_q(
    p: dict[str, float],
    q_mcts: dict[str, float],
    *,
    tau_q: float = TAU_Q,
) -> tuple[dict[str, float], list[str]] | tuple[None, list[str]]:
    """KL-regularized soft target inside candidates: `g(a) ∝ p(a) * exp(Q_mcts(a) / tau_q)`."""
    cands = [a for a in select_candidates(p, q_mcts) if a in q_mcts and math.isfinite(q_mcts[a])]
    if len(cands) < 2:
        return None, cands
    out = {k: float(v) for k, v in p.items()}
    mass = sum(out[a] for a in cands)
    if mass <= 0.0:
        return None, cands
    # Log-space stable `p(a) * exp(Q / tau_q)` (with tiny floor so promoted rescues get non-zero mass)
    log_w = {a: math.log(max(out[a], SC.PRIOR_FLOOR)) + float(q_mcts[a]) / float(tau_q) for a in cands}
    mx = max(log_w.values())
    unnorm = {a: math.exp(log_w[a] - mx) for a in cands}
    z = sum(unnorm.values())
    for a in cands:
        out[a] = mass * unnorm[a] / z
    # Renormalize minor float drift
    tot = sum(out.values())
    if tot > 0.0:
        out = {k: v / tot for k, v in out.items()}
    return out, cands


def selected_games() -> dict[str, list[str]]:
    """Deterministic game selection: `TRAIN_GAMES` from non-heldout train + EX-199 heldout games (cached)."""
    sel_path = RUN / 'selection.json'
    if sel_path.exists():
        return json.loads(sel_path.read_text())
    from integration.laya_value.data_value import heldout_games
    held = heldout_games()
    all_games = sorted({game_of(sample_id_of(l)) for l in open(SOURCE)})
    train_pool = [g for g in all_games if g not in held]
    rng = random.Random(SEED)
    chosen_train = sorted(rng.sample(train_pool, min(TRAIN_GAMES, len(train_pool))))
    sel = dict(seed=SEED, train=chosen_train, heldout=sorted(held))
    RUN.mkdir(parents=True, exist_ok=True)
    sel_path.write_text(json.dumps(sel, indent=1))
    return sel


# ---------------------------------------------------------------------------------------------- infer (GPU 0 & 1 ONLY)

def infer(rank: int, world: int = 2, limit: int | None = None, batch: int = 32):
    if world != 2 or rank not in (0, 1):
        raise ValueError('EP-243 strictly allocates GPU 0 and GPU 1 only (world=2, rank in {0, 1})')
    from integration.laya_imitation.resources import gpu
    from integration.laya_ladder import paths as ladder
    from integration.laya_v10 import training_v10

    uuid = SC.ALLOWED_GPU_UUIDS[rank]
    sel = selected_games()
    wanted_games = set(sel['train']) | set(sel['heldout'])

    RUN.mkdir(parents=True, exist_ok=True)
    out_path = RUN / ('infer-%d.jsonl' % rank)
    done = {json.loads(l)['sample_id'] for l in open(out_path)} if out_path.exists() else set()

    training_v10.install(ladder.OPTION_LIMIT)
    import laya.train as LT
    orig_fwd = LT._forward
    LT._forward = lambda m, b, d, amp, detach_encoder: orig_fwd(m, b, d, True, detach_encoder)

    with gpu(rank, uuid) as (env, _):
        os.environ.update(env)
        policy = training_v10.Policy10(INIT_CKPT, head_limit=ladder.HEAD_LIMIT)
        rows = []
        with open(SOURCE) as f:
            for i, line in enumerate(f):
                if i % world != rank or not line.rstrip().endswith('}'):
                    continue
                if ':turn_action"' not in line[:200] and ':forced_switch"' not in line[:200]:
                    continue
                sid = sample_id_of(line)
                if game_of(sid) not in wanted_games or sid in done:
                    continue
                r = json.loads(line)
                if len(r['questions']['action']['criteria']) < 2:
                    continue
                rows.append(r)
                if limit and len(rows) >= limit:
                    break

        print('[ex209-infer %d] %d rows (%d done, gpu=%s)' % (rank, len(rows), len(done), uuid), flush=True)
        started = time.time()
        with open(out_path, 'a') as out:
            for start in range(0, len(rows), 512):
                chunk = rows[start:start + 512]
                items = [policy.item(r['state'], r['questions']['action']) for r in chunk]
                logits = policy.logits(items, batch_size=batch)
                for r, z in zip(chunk, logits):
                    ids = list(r['questions']['action']['criteria'])
                    probs, _ = policy.distribution(z, len(ids))
                    p = dict(zip(ids, probs))
                    out.write(json.dumps(dict(
                        sample_id=r['sample_id'], p=p, label=r['expected']['action'],
                    ), separators=(',', ':')) + '\n')
                out.flush()
                n = start + len(chunk)
                print('[ex209-infer %d] %d/%d rows, %.1f rows/s' % (rank, n, len(rows), n / max(1e-9, time.time() - started)),
                      flush=True)
    return dict(rank=rank, rows=len(rows))


# ---------------------------------------------------------------------------------------------- mcts (foul-play venv)

def _seed(sid: str) -> int:
    return int(hashlib.sha256(('ex209:' + sid).encode()).hexdigest()[:16], 16)


def _init():
    from integration.laya_fp1 import tracker
    tracker.setup()


def mcts_job(job: dict) -> dict:
    from integration.laya_distill.data_distill import choice_map, restrict
    from integration.laya_fp1 import data_fp1 as DF
    from integration.laya_fp1 import tracker as T
    from integration.laya_regret.search import sample_states

    want = job['wanted']  # sid -> list[action_id]
    blim_sets: set[frozenset[str]] = job['blim_sets']
    rows, errors = [], []
    try:
        recovered = DF.load(job['recovered'])
        raw = DF.load(job['raw'])
    except Exception as exc:
        return dict(replay_id=job['replay_id'], rows=[], skipped='load_error', errors=[repr(exc)])

    orig_sets = recovered['result'].get('original_sets') or {}
    for side_sets in orig_sets.values():
        if frozenset(F.norm(m.get('species')) for m in side_sets) in blim_sets:
            return dict(replay_id=job['replay_id'], rows=[], skipped='blim_eval_team', errors=[])

    for side in sorted(orig_sets):
        if not any(':%s:' % side in s for s in want):
            continue
        own = orig_sets[side]
        try:
            tracker = T.Tracker(raw, side, own)
        except Exception as exc:
            errors.append(dict(side=side, stage='init', error='%s: %s' % (type(exc).__name__, exc)))
            continue
        for record in T.recovered_records(recovered, side):
            kind = record['decision_kind']
            sid = '%s:%s:%d:%s' % (job['replay_id'], side, record['cutoff_line'], kind)
            try:
                if kind != 'lead':
                    tracker.advance(record['cutoff_line'], record['snapshot'], kind)
                    if sid in want:
                        view = tracker.view()
                        aids = want[sid]
                        mapping = choice_map(view, [{'id': a} for a in aids], own)
                        mapping = {a: ch for a, ch in mapping.items() if ch}
                        if len(mapping) >= 2:
                            restrict(view, mapping)
                            samples, _ = sample_states(view, _seed(sid))
                            res = SC.search_mcts_samples(samples, mapping, iterations=MCTS_ITERS)
                            rows.append(dict(
                                sample_id=sid, kind=kind, q_mcts=res['q_mcts'], v_mcts=res['v_mcts'],
                                root_q=res['root_q'], unmapped=res['unmapped'],
                                samples=res['samples'], errors=res['errors'], seconds=res['seconds'],
                            ))
                tracker.chose(record.get('label'))
            except Exception as exc:
                errors.append(dict(side=side, sample_id=sid, stage='decision', error='%s: %s' % (type(exc).__name__, exc),
                                   trace=traceback.format_exc(limit=2)[-400:]))
                break
    return dict(replay_id=job['replay_id'], rows=rows, skipped=None, errors=errors)


def run_mcts(workers: int = 48, limit: int | None = None):
    from multiprocessing import Pool
    from integration.laya_fp1.data_fp1 import jobs

    if os.environ.get('PYTHONHASHSEED') != '0':
        raise RuntimeError('run with PYTHONHASHSEED=0')
    staging = RUN / 'mcts'
    staging.mkdir(parents=True, exist_ok=True)
    done = set()
    for p in staging.glob('done-*.txt'):
        done.update(p.read_text().split())

    want = {}
    for part in sorted(RUN.glob('infer-*.jsonl')):
        for line in open(part):
            r = json.loads(line)
            if len(r['p']) >= 2:
                want[r['sample_id']] = list(r['p'].keys())

    blim_sets = F.blim_eval_team_sets()
    todo = [dict(j, wanted={s: want[s] for s in j['wanted']}, blim_sets=blim_sets)
            for j in jobs(want, limit) if j['replay_id'] not in done]
    print('[ex209-mcts] %d decisions, %d games to do (%d done), workers=%d, iters=%d' % (
        len(want), len(todo), len(done), workers, MCTS_ITERS), flush=True)

    tag = '%d-%d' % (int(time.time()), os.getpid())
    started, n, nrows, nerr = time.time(), 0, 0, 0
    with open(staging / ('part-%s.jsonl' % tag), 'a') as out, \
            open(staging / ('errors-%s.jsonl' % tag), 'a') as err, \
            open(staging / ('done-%s.txt' % tag), 'a') as fin, \
            Pool(workers, initializer=_init, maxtasksperchild=50) as pool:
        for res in pool.imap_unordered(mcts_job, todo, chunksize=1):
            for r in res['rows']:
                out.write(json.dumps(r, separators=(',', ':')) + '\n')
            for e in res['errors']:
                err.write(json.dumps(dict(replay_id=res['replay_id'], error=e), separators=(',', ':')) + '\n')
            out.flush()
            err.flush()
            fin.write(res['replay_id'] + '\n')
            fin.flush()
            n += 1
            nrows += len(res['rows'])
            nerr += len(res['errors'])
            if n % 50 == 0 or n == len(todo):
                rate = n / max(1e-9, time.time() - started)
                print('[ex209-mcts] %d/%d games, %d rows, %d errs, %.2f g/s, eta %.1f min' % (
                    n, len(todo), nrows, nerr, rate, (len(todo) - n) / max(1e-9, rate) / 60), flush=True)
    return dict(games=n, rows=nrows, errors=nerr)


# ---------------------------------------------------------------------------------------------- targets (any python)

def targets():
    sel = selected_games()
    held = set(sel['heldout'])
    infer_rows = {}
    for part in sorted(RUN.glob('infer-*.jsonl')):
        for line in open(part):
            r = json.loads(line)
            infer_rows[r['sample_id']] = r
    mcts_rows = {}
    for part in sorted((RUN / 'mcts').glob('part-*.jsonl')):
        for line in open(part):
            r = json.loads(line)
            if r.get('q_mcts') and float(r.get('unmapped') or 0.0) <= 0.05:
                mcts_rows[r['sample_id']] = r

    OUT.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    moved = Counter()
    with open(SOURCE) as f, open(OUT / 'train.jsonl', 'w') as tr, open(OUT / 'heldout.jsonl', 'w') as ho:
        for line in f:
            sid = sample_id_of(line)
            if sid not in infer_rows or sid not in mcts_rows:
                continue
            r = infer_rows[sid]
            m = mcts_rows[sid]
            g, cands = gold_mcts_q(r['p'], m['q_mcts'])
            if g is None:
                stats['skipped_few_cands'] += 1
                continue
            row = json.loads(line)
            argmax_p = max(sorted(r['p']), key=lambda a: r['p'][a])
            argmax_g = max(sorted(g), key=lambda a: g[a])
            stats['gold_rows'] += 1
            stats['gold_argmax_changed'] += int(argmax_g != argmax_p)
            stats['human_is_laya_argmax'] += int(r['label'] == argmax_p)
            stats['human_is_gold_argmax'] += int(r['label'] == argmax_g)
            stats['forced_switch_rows'] += int(m.get('kind') == 'forced_switch')
            if argmax_g != argmax_p:
                parts = argmax_g.split(':')
                moved[parts[0] + ':' + (parts[1] if len(parts) > 1 else '')] += 1
            out = dict(
                sample_id=sid,
                input_sha256=row.get('input_sha256'),
                state=row['state'],
                questions=dict(action=row['questions']['action']),
                gold=dict(action=dict(probabilities=g)),
                meta=dict(
                    row.get('meta') or {},
                    ex209=dict(candidates=cands, q_mcts=m['q_mcts'], laya_argmax=argmax_p, label=r['label']),
                ),
            )
            is_held = game_of(sid) in held
            stats['heldout_gold_rows' if is_held else 'train_gold_rows'] += 1
            (ho if is_held else tr).write(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')

    manifest = dict(
        source=str(SOURCE), init_checkpoint=str(INIT_CKPT), iterations=MCTS_ITERS,
        tau_q=TAU_Q, near=NEAR, max_candidates=MAX_CANDIDATES, rescue_gap=RESCUE_GAP,
        seed=SEED, train_games=len(sel['train']), heldout_games=len(held),
        counts=dict(stats), gold_argmax_moves_by_kind=dict(moved.most_common(20)), at=time.time(),
    )
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('infer', 'mcts', 'targets'))
    ap.add_argument('--rank', type=int, default=0)
    ap.add_argument('--world', type=int, default=2)
    ap.add_argument('--workers', type=int, default=48)
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    if args.cmd == 'infer':
        print(json.dumps(infer(args.rank, args.world, args.limit)))
    elif args.cmd == 'mcts':
        print(json.dumps(run_mcts(args.workers, args.limit)))
    else:
        targets()
