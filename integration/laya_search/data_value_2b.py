"""EP-243 / D-219 (EX-207): Extract `(poke_engine.State features, actual game winner)` from replays (foul-play venv).

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python \
        -m integration.laya_search.data_value_2b extract --workers 48
    python3 -m integration.laya_search.data_value_2b build

Strict leakage controls:
- Source games: `v12-fresh/train.jsonl` (6,707 high-Elo Showdown games), excluding:
  1. All EX-199 held-out games (`data_value.heldout_games()`),
  2. Any game where EITHER side matches one of the 64 sealed Blim evaluation teams (EX-174 manifest, 6-species set),
  3. Ties or logs without an unambiguous `|win|<player>` line.
- Game-level split (`SEED = 20261207`): 90% train / 5% calibration / 5% held-out validation (zero game overlap).
- Also records `evaluate.rs` score (`eval_rs`) for every extracted state so `train_value_2b.py` can directly compare
  `V_phi(s)` vs `sigmoid(evaluate(s))` on identical held-out games.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import re
import time
import traceback

from . import featurize as F

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
SOURCE = SHARED / 'datasets/generated/laya-compact-imitation/v12-fresh/train.jsonl'
RUN = SHARED / 'runs/model-training/EX-207'
OUT = SHARED / 'datasets/generated/laya-state-value/v1'
SEED = 20261207
VAL_FRAC = 0.05
CALIB_FRAC = 0.05
MAX_PER_SIDE_GAME = 40  # cap long stall games so they don't dominate loss


def _norm_user(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def parse_winner_side(log_text: str) -> str | None:
    """Return `'p1'` or `'p2'` from Showdown replay log, or `None` on tie/missing."""
    players: dict[str, str] = {}
    winner_name: str | None = None
    for line in log_text.splitlines():
        parts = line.split('|')
        if len(parts) >= 4 and parts[1] == 'player' and parts[2] in ('p1', 'p2') and parts[3].strip():
            players[parts[2]] = _norm_user(parts[3])
        elif len(parts) >= 3 and parts[1] == 'win' and parts[2].strip():
            winner_name = _norm_user(parts[2])
        elif len(parts) >= 2 and parts[1] == 'tie':
            return None
    if not winner_name:
        return None
    p1, p2 = players.get('p1'), players.get('p2')
    if winner_name == p1 and winner_name != p2:
        return 'p1'
    if winner_name == p2 and winner_name != p1:
        return 'p2'
    return None


def _seed(sid: str) -> int:
    return int(hashlib.sha256(('ex207:' + sid).encode()).hexdigest()[:16], 16)


def _init():
    from integration.laya_fp1 import tracker
    tracker.setup()


def extract_job(job: dict) -> dict:
    from integration.laya_fp1 import data_fp1 as DF
    from integration.laya_fp1 import tracker as T
    from integration.laya_regret.search import sample_states
    from integration.laya_value.evaluate import evaluate
    import poke_engine

    blim_sets: set[frozenset[str]] = job['blim_sets']
    rows, errors = [], []
    try:
        recovered = DF.load(job['recovered'])
        raw = DF.load(job['raw'])
    except Exception as exc:
        return dict(replay_id=job['replay_id'], rows=[], skipped='load_error', errors=[repr(exc)])

    log_text = raw['log'] if isinstance(raw, dict) else '\n'.join(raw)
    winner = parse_winner_side(log_text)
    if winner not in ('p1', 'p2'):
        return dict(replay_id=job['replay_id'], rows=[], skipped='no_winner', errors=[])

    result = recovered['result']
    orig_sets = result.get('original_sets') or {}
    # Exclude if EITHER side uses one of the 64 Blim evaluation teams
    for side_sets in orig_sets.values():
        sp_set = frozenset(F.norm(m.get('species')) for m in side_sets)
        if sp_set in blim_sets:
            return dict(replay_id=job['replay_id'], rows=[], skipped='blim_eval_team', errors=[])

    for side in sorted(orig_sets):
        own = orig_sets[side]
        win_label = 1 if side == winner else 0
        try:
            tracker = T.Tracker(raw, side, own)
        except Exception as exc:
            errors.append(dict(side=side, stage='init', error='%s: %s' % (type(exc).__name__, exc)))
            continue
        side_rows = []
        turn_idx = 0
        for record in T.recovered_records(recovered, side):
            kind = record['decision_kind']
            sid = '%s:%s:%d:%s' % (job['replay_id'], side, record['cutoff_line'], kind)
            try:
                if kind != 'lead':
                    tracker.advance(record['cutoff_line'], record['snapshot'], kind)
                    turn_idx = int((record.get('snapshot') or {}).get('turn') or turn_idx)
                    if kind in ('turn_action', 'forced_switch'):
                        view = tracker.view()
                        samples, _ = sample_states(view, _seed(sid))
                        if samples:
                            # Take highest-probability representative set sample for fast, clean state extraction
                            best_text = max(samples, key=lambda kv: kv[1])[0]
                            st = poke_engine.State.from_string(best_text)
                            if F.state_terminal(st) is None:
                                feat = F.extract_raw(st)
                                eval_rs = float(evaluate(st))
                                side_rows.append(dict(
                                    sample_id=sid,
                                    game=job['replay_id'],
                                    side=side,
                                    turn=turn_idx,
                                    kind=kind,
                                    win=win_label,
                                    eval_rs=round(eval_rs, 3),
                                    mon_num=feat['mon_num'],
                                    mon_cat=feat['mon_cat'],
                                    global_num=feat['global_num'],
                                ))
                tracker.chose(record.get('label'))
            except Exception as exc:
                errors.append(dict(side=side, sample_id=sid, stage='decision', error='%s: %s' % (type(exc).__name__, exc),
                                   trace=traceback.format_exc(limit=2)[-400:]))
                break
        if len(side_rows) > MAX_PER_SIDE_GAME:
            rng = random.Random(_seed(job['replay_id'] + ':' + side))
            side_rows = rng.sample(side_rows, MAX_PER_SIDE_GAME)
        rows.extend(side_rows)
    return dict(replay_id=job['replay_id'], rows=rows, skipped=None, errors=errors)


def extract(workers: int = 48, limit: int | None = None):
    from multiprocessing import Pool
    from integration.laya_fp1.data_fp1 import jobs
    from integration.laya_value.data_value import game_of, heldout_games, sample_id_of

    if os.environ.get('PYTHONHASHSEED') != '0':
        raise RuntimeError('run with PYTHONHASHSEED=0')
    staging = RUN / 'staging'
    staging.mkdir(parents=True, exist_ok=True)
    done = set()
    for p in staging.glob('done-*.txt'):
        done.update(p.read_text().split())

    ex199_held = heldout_games()
    want_sids = {}
    with open(SOURCE) as f:
        for line in f:
            sid = sample_id_of(line)
            g = game_of(sid)
            if g not in ex199_held:
                want_sids[sid] = True

    blim_sets = F.blim_eval_team_sets()
    todo = [dict(j, blim_sets=blim_sets) for j in jobs(want_sids, limit) if j['replay_id'] not in done]
    print('[ex207-extract] %d games to do (%d done, %d ex199 heldout excl, %d blim teams excl), workers=%d' % (
        len(todo), len(done), len(ex199_held), len(blim_sets), workers), flush=True)

    tag = '%d-%d' % (int(time.time()), os.getpid())
    started, n, nrows, nerr = time.time(), 0, 0, 0
    skips = Counter()
    with open(staging / ('part-%s.jsonl' % tag), 'a') as out, \
            open(staging / ('errors-%s.jsonl' % tag), 'a') as err, \
            open(staging / ('done-%s.txt' % tag), 'a') as fin, \
            Pool(workers, initializer=_init, maxtasksperchild=100) as pool:
        for res in pool.imap_unordered(extract_job, todo, chunksize=1):
            if res['skipped']:
                skips[res['skipped']] += 1
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
            if n % 100 == 0 or n == len(todo):
                rate = n / max(1e-9, time.time() - started)
                print('[ex207-extract] %d/%d games, %d rows, %d errs, skips=%s, %.2f g/s, eta %.1f min' % (
                    n, len(todo), nrows, nerr, dict(skips), rate, (len(todo) - n) / max(1e-9, rate) / 60), flush=True)
    return dict(games=n, rows=nrows, errors=nerr, skips=dict(skips))


def build():
    """Deduplicate staged rows, split strictly by game ID (train/calib/val), build train-only Vocab, save `.npz`."""
    import numpy as np
    staging = RUN / 'staging'
    by_sid = {}
    for p in sorted(staging.glob('part-*.jsonl')):
        with open(p) as f:
            for line in f:
                r = json.loads(line)
                by_sid[r['sample_id']] = r

    games = sorted({r['game'] for r in by_sid.values()})
    rng = random.Random(SEED)
    shuffled = list(games)
    rng.shuffle(shuffled)
    n_val = max(1, round(len(shuffled) * VAL_FRAC))
    n_cal = max(1, round(len(shuffled) * CALIB_FRAC))
    val_games = set(shuffled[:n_val])
    cal_games = set(shuffled[n_val:n_val + n_cal])
    tr_games = set(shuffled[n_val + n_cal:])
    assert not (val_games & cal_games) and not (val_games & tr_games) and not (cal_games & tr_games)

    splits = {'train': [], 'calib': [], 'val': []}
    for r in by_sid.values():
        g = r['game']
        sp = 'val' if g in val_games else ('calib' if g in cal_games else 'train')
        splits[sp].append(r)

    # Fit vocab on TRAIN split only (zero leakage)
    vocab = F.Vocab.build((r['mon_cat'] for r in splits['train']), min_freq=2)
    OUT.mkdir(parents=True, exist_ok=True)
    vocab.save(OUT / 'vocab.json')

    counts = {}
    for name, rows in splits.items():
        mn = np.asarray([r['mon_num'] for r in rows], dtype=np.float32)
        mc = np.asarray([vocab.encode_cat(r['mon_cat']) for r in rows], dtype=np.int32)
        gn = np.asarray([r['global_num'] for r in rows], dtype=np.float32)
        y = np.asarray([r['win'] for r in rows], dtype=np.float32)
        er = np.asarray([r['eval_rs'] for r in rows], dtype=np.float32)
        tn = np.asarray([r['turn'] for r in rows], dtype=np.int16)
        np.savez_compressed(OUT / f'{name}.npz', mon_num=mn, mon_cat=mc, global_num=gn, win=y, eval_rs=er, turn=tn)
        counts[name] = dict(rows=len(rows), games=len({r['game'] for r in rows}),
                            win_rate=round(float(y.mean()), 4) if len(y) else None)

    manifest = dict(
        source=str(SOURCE),
        seed=SEED,
        val_frac=VAL_FRAC,
        calib_frac=CALIB_FRAC,
        max_per_side_game=MAX_PER_SIDE_GAME,
        vocab_sizes=vocab.sizes(),
        splits=counts,
        at=time.time(),
    )
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('extract', 'build'))
    ap.add_argument('--workers', type=int, default=48)
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    if args.cmd == 'extract':
        print(json.dumps(extract(args.workers, args.limit)))
    else:
        build()
