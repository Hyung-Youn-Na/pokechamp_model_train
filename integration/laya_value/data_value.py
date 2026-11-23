"""EX-199 (EP-239, D-217): foul-play engine one-turn values of laya's candidates and the soft-target rows.

    infer   --rank R --world 4     laya env, GPU R: EX-196 p (and q when 2+ candidates) on the v12-fresh train
                                   turn_action rows i with i % world == R -> RUN/infer-R.jsonl
    values  [--workers 64]         foul-play venv (PYTHONHASHSEED=0): replays through `laya_fp1.tracker`, the
                                   wanted decisions' foul-play set samples, `value.values` -> RUN/values/part-*.jsonl
    targets                        any python: the gold rows (train / heldout games) and the statistics

Rows: `laya-compact-imitation/v12-fresh/train.jsonl` (EX-195: ladder games outside v12-ladder-merged and outside
the 400 held-out games), turn_action only. HELDOUT_FRACTION of the games (seeded) are kept apart: their gold rows
are written to `heldout.jsonl` for the EX-200 target-agreement check and never trained on.
Candidates: the actions with p >= NEAR * max p, at most MAX_CANDIDATES, by p (EX-197's rule); a decision is used
only with two or more. q: EX-196's answer to the opponent question (`laya_foe.data_foe`) on the same state.
Gold: laya's p outside the candidates; inside, the candidates' total p split by softmax(value / TAU) (engine points).
TAU = 20 points (a fifth of one Pokemon's HP) was fixed after the value scale of three trial decisions (gaps of tens of
points), before the full run.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
import random
import sys
import time
import traceback
from pathlib import Path

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
GEN = SHARED / 'datasets/generated'
SOURCE = GEN / 'laya-compact-imitation/v12-fresh/train.jsonl'
RUN = SHARED / 'runs/model-training/EX-199'
OUT = GEN / 'laya-value/v1'
EX196 = SHARED / 'runs/model-training/EX-196/checkpoints/selected'
SEED = 20261199
HELDOUT_FRACTION = 0.05
NEAR = 0.5
MAX_CANDIDATES = 3
TAU = 20.0


def sample_id_of(line):
    return line[14:line.index('"', 14)]


def game_of(sid):
    return sid.rsplit(':', 3)[0]


def heldout_games():
    games = sorted({game_of(sample_id_of(l)) for l in open(SOURCE)})
    rng = random.Random(SEED)
    return set(rng.sample(games, round(len(games) * HELDOUT_FRACTION)))


# ------------------------------------------------------------------------------------------- infer (laya env, GPU)

def infer(rank, world, limit=None, batch=32):
    from integration.laya_foe.data_foe import INSTRUCTIONS, foe_options
    from integration.laya_imitation.resources import gpu
    from integration.laya_ladder import paths as ladder
    from integration.laya_ladder.train_ddp import UUIDS
    from integration.laya_v10 import training_v10
    RUN.mkdir(parents=True, exist_ok=True)
    out_path = RUN / ('infer-%d.jsonl' % rank)
    done = set()
    if out_path.exists():
        done = {json.loads(l)['sample_id'] for l in open(out_path)}
    training_v10.install(ladder.OPTION_LIMIT)
    import laya.train as LT
    forward = LT._forward                    # fp16 autocast (as in training): 3.4x faster, |dp| < 0.001 (256 rows)
    LT._forward = lambda m, b, d, amp, detach_encoder: forward(m, b, d, True, detach_encoder)
    with gpu(rank, UUIDS[rank]) as (env, _):
        os.environ.update(env)
        policy = training_v10.Policy10(EX196, head_limit=ladder.HEAD_LIMIT)
        rows = []
        with open(SOURCE) as f:
            for i, line in enumerate(f):
                if i % world != rank or not line.rstrip().endswith('}') or ':turn_action"' not in line[:200]:
                    continue
                r = json.loads(line)
                if r['sample_id'] in done:
                    continue
                rows.append(r)
                if limit and len(rows) >= limit:
                    break
        print('[infer %d] %d rows (%d done)' % (rank, len(rows), len(done)), flush=True)
        started = time.time()
        with open(out_path, 'a') as out:
            for start in range(0, len(rows), 512):
                chunk = rows[start:start + 512]
                items = [policy.item(r['state'], r['questions']['action']) for r in chunk]
                logits = policy.logits(items, batch_size=batch)
                ps, foe_items, foe_at = [], [], []
                for j, (r, z) in enumerate(zip(chunk, logits)):
                    ids = list(r['questions']['action']['criteria'])
                    probs, _ = policy.distribution(z, len(ids))
                    p = dict(zip(ids, probs))
                    top = max(p.values())
                    cands = sorted((a for a in ids if p[a] >= NEAR * top), key=p.get, reverse=True)[:MAX_CANDIDATES]
                    ps.append((p, cands))
                    if len(cands) > 1:
                        fq = dict(type='choice', instructions=INSTRUCTIONS, criteria=foe_options(r['state']))
                        foe_items.append(policy.item(r['state'], fq))
                        foe_at.append((j, list(fq['criteria'])))
                qs = {}
                for (j, fids), z in zip(foe_at, policy.logits(foe_items, batch_size=batch)):
                    probs, _ = policy.distribution(z, len(fids))
                    qs[j] = dict(zip(fids, probs))
                for j, r in enumerate(chunk):
                    p, cands = ps[j]
                    out.write(json.dumps(dict(sample_id=r['sample_id'], p=p, candidates=cands, q=qs.get(j),
                                              label=r['expected']['action']), separators=(',', ':')) + '\n')
                out.flush()
                n = start + len(chunk)
                print('[infer %d] %d/%d rows, %.1f rows/s' % (rank, n, len(rows), n / (time.time() - started)),
                      flush=True)
    return dict(rows=len(rows))


# ------------------------------------------------------------------------------------------ values (foul-play venv)

def seed_of(sid):
    return int(hashlib.sha256(('ex199:' + sid).encode()).hexdigest()[:16], 16)


def value_job(job):
    from integration.laya_fp1 import render_fp1 as RF
    from integration.laya_fp1 import tracker as T
    from integration.laya_fp1.data_fp1 import load
    from integration.laya_regret.search import sample_states
    from .value import values
    started = time.time()
    want = job['wanted']                       # sid -> {candidates, q}
    rows, errors = [], []
    recovered = load(job['recovered'])
    raw = load(job['raw'])
    result = recovered['result']
    for side in sorted(result['original_sets']):
        if not any(':%s:' % side in s for s in want):
            continue
        own = result['original_sets'][side]
        try:
            tracker = T.Tracker(raw, side, own)
        except Exception as exc:
            errors.append(dict(side=side, stage='init', error='%s: %s' % (type(exc).__name__, exc)))
            continue
        for record in T.recovered_records(recovered, side):
            sid = '%s:%s:%d:%s' % (job['replay_id'], side, record['cutoff_line'], record['decision_kind'])
            try:
                if record['decision_kind'] != 'lead':
                    tracker.advance(record['cutoff_line'], record['snapshot'], record['decision_kind'])
                    if sid in want:
                        t0 = time.time()
                        view = tracker.view()
                        w = want[sid]
                        mine = {a: RF.engine_choice(a, view, own) for a in w['candidates']}
                        mine = {a: ch for a, ch in mine.items() if ch}
                        samples, _ = sample_states(view, seed_of(sid))
                        vals, errs = values(samples, mine, w['q']) if len(mine) > 1 else (None, 0)
                        rows.append(dict(sample_id=sid, values=vals, choices=mine, samples=len(samples),
                                         errors=errs, seconds=round(time.time() - t0, 3)))
                tracker.chose(record.get('label'))
            except Exception as exc:
                errors.append(dict(side=side, sample_id=sid, stage='decision', wanted=sid in want,
                                   error='%s: %s' % (type(exc).__name__, exc),
                                   trace=traceback.format_exc(limit=3)[-600:]))
                break
    return dict(replay_id=job['replay_id'], rows=rows, errors=errors, seconds=time.time() - started)


def _init():
    from integration.laya_fp1 import tracker
    tracker.setup()


def wanted_decisions():
    out = {}
    for part in sorted(RUN.glob('infer-*.jsonl')):
        for line in open(part):
            r = json.loads(line)
            if len(r['candidates']) > 1 and r['q']:
                out[r['sample_id']] = dict(candidates=r['candidates'], q=r['q'])
    return out


def run_values(workers=64, limit=None):
    from multiprocessing import Pool
    from integration.laya_fp1.data_fp1 import jobs
    if os.environ.get('PYTHONHASHSEED') != '0':
        raise RuntimeError('run with PYTHONHASHSEED=0 (deterministic foul-play set iteration)')
    staging = RUN / 'values'
    staging.mkdir(parents=True, exist_ok=True)
    done = set()
    for part in staging.glob('done-*.txt'):
        done.update(part.read_text().split())
    want = wanted_decisions()
    todo = [j for j in jobs(want, limit) if j['replay_id'] not in done]
    for j in todo:
        j['wanted'] = {s: want[s] for s in j['wanted']}
    print('[values] %d decisions, %d games to do (%d done)' % (len(want), len(todo), len(done)), flush=True)
    tag = '%d-%d' % (int(time.time()), os.getpid())
    started, n, nrows, nerr = time.time(), 0, 0, 0
    with open(staging / ('part-%s.jsonl' % tag), 'a') as out, \
            open(staging / ('errors-%s.jsonl' % tag), 'a') as err, \
            open(staging / ('done-%s.txt' % tag), 'a') as fin, \
            Pool(workers, initializer=_init, maxtasksperchild=100) as pool:
        for result in pool.imap_unordered(value_job, todo, chunksize=1):
            for row in result['rows']:
                out.write(json.dumps(row, separators=(',', ':')) + '\n')
            for e in result['errors']:
                err.write(json.dumps(dict(e, replay_id=result['replay_id'])) + '\n')
            out.flush()
            err.flush()
            fin.write(result['replay_id'] + '\n')
            fin.flush()
            n += 1
            nrows += len(result['rows'])
            nerr += len(result['errors'])
            if n % 100 == 0 or n == len(todo):
                rate = n / max(1e-9, time.time() - started)
                print('[values] %d/%d games, %d rows, %d errors, %.2f games/s, eta %.0f min' % (
                    n, len(todo), nrows, nerr, rate, (len(todo) - n) / max(1e-9, rate) / 60), flush=True)
    return dict(games=n, rows=nrows, errors=nerr)


# ---------------------------------------------------------------------------------------------- targets (any python)

def gold(p, cands, vals):
    """laya's p outside the candidates; the candidates' total p split by softmax(value / TAU) inside."""
    out = dict(p)
    mass = sum(p[a] for a in cands)
    m = max(vals[a] for a in cands)
    e = {a: math.exp((vals[a] - m) / TAU) for a in cands}
    s = sum(e.values())
    for a in cands:
        out[a] = mass * e[a] / s
    return out


def targets():
    held = heldout_games()
    infer_rows = {}
    for part in sorted(RUN.glob('infer-*.jsonl')):
        for line in open(part):
            r = json.loads(line)
            if len(r['candidates']) > 1:
                infer_rows[r['sample_id']] = r
    vals = {}
    for part in sorted((RUN / 'values').glob('part-*.jsonl')):
        for line in open(part):
            r = json.loads(line)
            vals[r['sample_id']] = r
    OUT.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    gaps, moved = [], Counter()
    with open(SOURCE) as f, open(OUT / 'train.jsonl', 'w') as tr, open(OUT / 'heldout.jsonl', 'w') as ho:
        for line in f:
            sid = sample_id_of(line)
            if sid not in infer_rows:
                continue
            v = vals.get(sid)
            stats['candidate decisions'] += 1
            if v is None:
                stats['no value row'] += 1
                continue
            r = infer_rows[sid]
            cands = [a for a in r['candidates'] if v['values'] and a in v['values']]
            if len(cands) < 2:
                stats['fewer than 2 valued candidates'] += 1
                continue
            row = json.loads(line)
            g = gold(r['p'], cands, v['values'])
            argmax_p = max(r['p'], key=r['p'].get)
            argmax_g = max(g, key=g.get)
            best = max(cands, key=lambda a: v['values'][a])
            gaps.append(v['values'][best] - v['values'][cands[0]])
            stats['gold rows'] += 1
            stats['gold argmax changed'] += argmax_g != argmax_p
            stats['human label is laya argmax'] += r['label'] == argmax_p
            stats['human label is gold argmax'] += r['label'] == argmax_g
            stats['human label among candidates'] += r['label'] in cands
            if argmax_g != argmax_p:
                moved[argmax_g.split(':')[0] + ':' + argmax_g.split(':')[1]] += 1
            out = dict(sample_id=sid, input_sha256=row.get('input_sha256'), state=row['state'],
                       questions=dict(action=row['questions']['action']), gold=dict(action=dict(probabilities=g)),
                       meta=dict(row.get('meta') or {}, ex199=dict(candidates=cands, values=v['values'],
                                                                  laya_argmax=argmax_p, label=r['label'])))
            heldout = game_of(sid) in held
            stats['heldout gold rows' if heldout else 'train gold rows'] += 1
            (ho if heldout else tr).write(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')
    gaps.sort()
    q = lambda f: gaps[int(f * (len(gaps) - 1))] if gaps else None
    manifest = dict(source=str(SOURCE), tau=TAU, near=NEAR, max_candidates=MAX_CANDIDATES,
                    heldout_fraction=HELDOUT_FRACTION, heldout_games=len(held), seed=SEED, counts=dict(stats),
                    best_minus_laya_top_points=dict(p10=q(.1), p50=q(.5), p90=q(.9), p99=q(.99)),
                    gold_argmax_moves_by_kind=dict(moved.most_common(20)), at=time.time())
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False), flush=True)
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=('infer', 'values', 'targets'))
    ap.add_argument('--rank', type=int, default=0)
    ap.add_argument('--world', type=int, default=4)
    ap.add_argument('--workers', type=int, default=64)
    ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    if a.command == 'infer':
        print(json.dumps(infer(a.rank, a.world, a.limit)))
    elif a.command == 'values':
        print(json.dumps(run_values(a.workers, a.limit)))
    else:
        targets()
