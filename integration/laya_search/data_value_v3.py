"""EP-247 / D-223 (EX-221): Extract future-horizon trajectories & counterfactual recovery/Protect pairs (`foul-play` venv).

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python \
        -m integration.laya_search.data_value_v3 extract --workers 36
    python3 -m integration.laya_search.data_value_v3 build

Strictly preserves EX-207 / EX-216's leakage-free game split (`SEED = 20261207`, 90% train / 5% calib / 5% val,
excluding EX-199 held-out games and all 64 sealed Blim evaluation teams) while enriching every state with:
1. `v3_mon (12x4)` & `v3_glob (8)` (remaining heal PP, min PP, `just_used_heal`, `just_used_protect`, `just_used_setup`),
2. Exact multi-horizon future targets computed over the FULL chronological game trajectory (before capping):
   - `fut_adv_3`, `fut_adv_5`, `fut_adv_10` (future board advantage at t+3, t+5, t+10; terminal ±1.0 if game ended),
   - `fut_delta_5` (`fut_adv_5 - cur_adv`, 5-turn momentum),
   - `fut_boost_diff_3` (net 3-turn future boost accumulation diff, punishing passive healing into setup sweepers),
3. Counterfactual `(s'_pos, s'_neg)` child-state pairs (`train_cf.npz`, `calib_cf.npz`, `val_cf.npz`, zero game leakage):
   - `reject_heal` / `reject_protect`: turns where a high-Elo human pro had a legal recovery/`Protect` move and
     REJECTED it for an attack/switch/setup (at high HP >= 72%, against opp setup/hazard, or in a won game),
   - `accept_heal`: balanced low/mid-HP (<= 65%) turns where a winning human pro genuinely CHOSE recovery over attack.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import time
import traceback

from . import data_value_2b as DV1
from . import featurize as F
from . import featurize_v3 as F3

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
SOURCE = DV1.SOURCE
RUN = SHARED / 'runs/model-training/EX-221'
OUT = SHARED / 'datasets/generated/laya-state-value/v3'
SEED = DV1.SEED          # 20261207 — exact same game-level split as EX-207 & EX-216!
VAL_FRAC = DV1.VAL_FRAC
CALIB_FRAC = DV1.CALIB_FRAC
MAX_PER_SIDE_GAME = DV1.MAX_PER_SIDE_GAME
MAX_CF_PER_SIDE_GAME = 12

HAZARD_MOVES = frozenset(('stealthrock', 'spikes', 'toxicspikes', 'stickyweb', 'ceaselessedge', 'stoneaxe'))


def _seed(sid: str) -> int:
    return int(hashlib.sha256(('ex221:' + sid).encode()).hexdigest()[:16], 16)


def _init():
    from integration.laya_fp1 import tracker
    tracker.setup()


def _label_to_eng_choice(label: str | None, side_obj, own_team: list[dict] | None = None) -> str | None:
    """Convert recovered action label (`move:<id>:<normal|tera>` or `switch:<slot>`) to `poke_engine` choice string."""
    if not label:
        return None
    if label.startswith('move:'):
        parts = label.split(':')
        if len(parts) < 2:
            return None
        mid = F.norm(parts[1])
        is_tera = len(parts) >= 3 and parts[2] == 'tera'
        act = side_obj.pokemon[int(side_obj.active_index)]
        avail = {F.norm(m.id): m.id.lower() for m in (getattr(act, 'moves', None) or ()) if getattr(m, 'pp', 0) > 0}
        eng = avail.get(mid)
        if not eng:
            return None
        return (eng + '-tera') if is_tera else eng
    if label.startswith('switch:'):
        try:
            slot = int(label.split(':', 1)[1])
        except Exception:
            return None
        if own_team:
            for m in own_team:
                if m.get('slot') == slot:
                    sp = F.norm(m.get('species'))
                    for p in side_obj.pokemon:
                        if F.norm(p.id) == sp and p.hp > 0:
                            return p.id.lower()
        return None
    return None


def _step_top_branch(poke_engine, st, my_choice: str, opp_choice: str):
    """Apply highest-probability instruction branch of `(my_choice, opp_choice)`."""
    try:
        insts = poke_engine.generate_instructions(st, my_choice, opp_choice)
    except BaseException:
        return None
    if not insts:
        return None
    br = max(insts, key=lambda b: float(b.percentage))
    try:
        return st.apply_instructions(br)
    except BaseException:
        return None


def extract_job(job: dict) -> dict:
    from integration.laya_fp1 import data_fp1 as DF
    from integration.laya_fp1 import tracker as T
    from integration.laya_regret.search import sample_states
    from integration.laya_value.evaluate import evaluate
    import poke_engine

    blim_sets: set[frozenset[str]] = job['blim_sets']
    rows, cf_rows, errors = [], [], []
    try:
        recovered = DF.load(job['recovered'])
        raw = DF.load(job['raw'])
    except Exception as exc:
        return dict(replay_id=job['replay_id'], rows=[], cf_rows=[], skipped='load_error', errors=[repr(exc)])

    log_text = raw['log'] if isinstance(raw, dict) else '\n'.join(raw)
    winner = DV1.parse_winner_side(log_text)
    if winner not in ('p1', 'p2'):
        return dict(replay_id=job['replay_id'], rows=[], cf_rows=[], skipped='no_winner', errors=[])

    result = recovered['result']
    orig_sets = result.get('original_sets') or {}
    for side_sets in orig_sets.values():
        sp_set = frozenset(F.norm(m.get('species')) for m in side_sets)
        if sp_set in blim_sets:
            return dict(replay_id=job['replay_id'], rows=[], cf_rows=[], skipped='blim_eval_team', errors=[])

    # Pre-index opponent turn_action labels by turn so we know the real opponent action for counterfactual simulation
    opp_turn_actions: dict[str, dict[int, tuple[str, list[dict]]]] = {}
    for s in sorted(orig_sets):
        tmap: dict[int, tuple[str, list[dict]]] = {}
        for rec in T.recovered_records(recovered, s):
            if rec.get('decision_kind') == 'turn_action' and rec.get('label'):
                snap = rec.get('snapshot') or {}
                tnum = int(snap.get('turn') or 0)
                if tnum > 0 and tnum not in tmap:
                    tmap[tnum] = (str(rec['label']), snap.get('own_team') or [])
        opp_turn_actions[s] = tmap

    for side in sorted(orig_sets):
        own = orig_sets[side]
        opp_side = 'p2' if side == 'p1' else 'p1'
        win_label = 1 if side == winner else 0
        term_adv = 1.0 if win_label == 1 else -1.0
        try:
            tracker = T.Tracker(raw, side, own)
        except Exception as exc:
            errors.append(dict(side=side, stage='init', error='%s: %s' % (type(exc).__name__, exc)))
            continue

        side_rows = []
        side_cf = []
        turn_idx = 0
        for record in T.recovered_records(recovered, side):
            kind = record['decision_kind']
            sid = '%s:%s:%d:%s' % (job['replay_id'], side, record['cutoff_line'], kind)
            try:
                if kind != 'lead':
                    tracker.advance(record['cutoff_line'], record['snapshot'], kind)
                    snap = record.get('snapshot') or {}
                    turn_idx = int(snap.get('turn') or turn_idx)
                    if kind in ('turn_action', 'forced_switch'):
                        view = tracker.view()
                        # Keep EXACT EX-207 sample seed for state alignment
                        samples, _ = sample_states(view, DV1._seed(sid))
                        if samples:
                            best_text = max(samples, key=lambda kv: kv[1])[0]
                            st = poke_engine.State.from_string(best_text)
                            if F.state_terminal(st) is None:
                                feat = F3.extract_raw_v3(st)
                                eval_rs = float(evaluate(st))
                                cur_adv = F3.board_advantage(feat)
                                cur_bdiff = F3.active_boost_diff(feat)
                                side_rows.append(dict(
                                    sample_id=sid,
                                    game=job['replay_id'],
                                    side=side,
                                    turn=turn_idx,
                                    kind=kind,
                                    win=win_label,
                                    eval_rs=round(eval_rs, 3),
                                    cur_adv=round(cur_adv, 5),
                                    cur_bdiff=round(cur_bdiff, 5),
                                    mon_num=feat['mon_num'],
                                    mon_cat=feat['mon_cat'],
                                    global_num=feat['global_num'],
                                    v3_mon=feat['v3_mon'],
                                    v3_glob=feat['v3_glob'],
                                ))

                                # Counterfactual recovery / Protect pair extraction on turn_action
                                lbl = record.get('label')
                                if kind == 'turn_action' and lbl and turn_idx in opp_turn_actions.get(opp_side, {}):
                                    opp_lbl, opp_team = opp_turn_actions[opp_side][turn_idx]
                                    act_p = st.side_one.pokemon[int(st.side_one.active_index)]
                                    hp_frac = float(act_p.hp) / max(1.0, float(act_p.maxhp))
                                    avail_moves = [
                                        (F.norm(m.id), m.id.lower())
                                        for m in (getattr(act_p, 'moves', None) or ())
                                        if getattr(m, 'pp', 0) > 0
                                    ]
                                    heal_eng = [eng for mid, eng in avail_moves if mid in F3.HEAL_MOVES]
                                    prot_eng = [eng for mid, eng in avail_moves if mid in F3.PROTECT_MOVES]
                                    if heal_eng or prot_eng:
                                        my_eng = _label_to_eng_choice(lbl, st.side_one, snap.get('own_team'))
                                        opp_eng = _label_to_eng_choice(opp_lbl, st.side_two, opp_team)
                                        if my_eng and opp_eng:
                                            my_mid = F.norm(lbl.split(':')[1]) if lbl.startswith('move:') else ''
                                            opp_mid = F.norm(opp_lbl.split(':')[1]) if opp_lbl.startswith('move:') else ''
                                            opp_setup_or_haz = (opp_mid in F3.SETUP_MOVES) or (opp_mid in HAZARD_MOVES)

                                            # Case 1: Human pro REJECTED legal heal/protect for a different action
                                            if my_mid not in F3.HEAL_MOVES and my_mid not in F3.PROTECT_MOVES:
                                                targets = []
                                                if heal_eng and (hp_frac >= 0.72 or opp_setup_or_haz or win_label == 1):
                                                    targets.append(('reject_heal', heal_eng[0]))
                                                if prot_eng and (hp_frac >= 0.72 or opp_setup_or_haz or win_label == 1):
                                                    targets.append(('reject_protect', prot_eng[0]))
                                                if targets:
                                                    s_pos = _step_top_branch(poke_engine, st, my_eng, opp_eng)
                                                    if s_pos is not None and F.state_terminal(s_pos) is None:
                                                        f_pos = F3.extract_raw_v3(s_pos)
                                                        for cf_kind, alt_eng in targets:
                                                            s_neg = _step_top_branch(poke_engine, st, alt_eng, opp_eng)
                                                            if s_neg is not None and F.state_terminal(s_neg) is None:
                                                                if s_pos.to_string() != s_neg.to_string():
                                                                    w_cf = 1.5 if (hp_frac >= 0.75 or opp_setup_or_haz) else 1.0
                                                                    side_cf.append(dict(
                                                                        sample_id=sid + ':' + cf_kind,
                                                                        game=job['replay_id'],
                                                                        side=side,
                                                                        turn=turn_idx,
                                                                        cf_kind=cf_kind,
                                                                        hp_frac=round(hp_frac, 4),
                                                                        opp_setup=int(opp_setup_or_haz),
                                                                        weight=w_cf,
                                                                        pos=f_pos,
                                                                        neg=F3.extract_raw_v3(s_neg),
                                                                    ))

                                            # Case 2: Balanced positive — winning human genuinely CHOSE heal at <= 65% HP
                                            elif my_mid in F3.HEAL_MOVES and hp_frac <= 0.65 and win_label == 1:
                                                non_hp = [eng for mid, eng in avail_moves if mid not in F3.HEAL_MOVES and mid not in F3.PROTECT_MOVES]
                                                if non_hp:
                                                    s_pos = _step_top_branch(poke_engine, st, my_eng, opp_eng)
                                                    s_neg = _step_top_branch(poke_engine, st, non_hp[0], opp_eng)
                                                    if (s_pos is not None and s_neg is not None
                                                            and F.state_terminal(s_pos) is None
                                                            and F.state_terminal(s_neg) is None
                                                            and s_pos.to_string() != s_neg.to_string()):
                                                        side_cf.append(dict(
                                                            sample_id=sid + ':accept_heal',
                                                            game=job['replay_id'],
                                                            side=side,
                                                            turn=turn_idx,
                                                            cf_kind='accept_heal',
                                                            hp_frac=round(hp_frac, 4),
                                                            opp_setup=int(opp_setup_or_haz),
                                                            weight=0.75,
                                                            pos=F3.extract_raw_v3(s_pos),
                                                            neg=F3.extract_raw_v3(s_neg),
                                                        ))
                tracker.chose(record.get('label'))
            except Exception as exc:
                errors.append(dict(side=side, sample_id=sid, stage='decision', error='%s: %s' % (type(exc).__name__, exc),
                                   trace=traceback.format_exc(limit=2)[-400:]))
                break

        # Compute exact multi-horizon future targets OVER THE FULL CHRONOLOGICAL TRAJECTORY before capping!
        if side_rows:
            # Map each turn to the latest state observed on that turn
            turn_vals: dict[int, tuple[float, float]] = {}
            for r in side_rows:
                turn_vals[int(r['turn'])] = (float(r['cur_adv']), float(r['cur_bdiff']))
            sorted_turns = sorted(turn_vals.keys())
            max_turn = sorted_turns[-1]

            def _future_at(t0: int, dt: int) -> tuple[float, float]:
                target = t0 + dt
                if target > max_turn:
                    return term_adv, 0.0
                # Find first recorded turn >= target
                for t in sorted_turns:
                    if t >= target:
                        return turn_vals[t]
                return term_adv, 0.0

            for r in side_rows:
                t0 = int(r['turn'])
                a3, b3 = _future_at(t0, 3)
                a5, _ = _future_at(t0, 5)
                a10, _ = _future_at(t0, 10)
                r['fut_adv_3'] = round(a3, 5)
                r['fut_adv_5'] = round(a5, 5)
                r['fut_adv_10'] = round(a10, 5)
                r['fut_delta_5'] = round(max(-1.0, min(1.0, a5 - float(r['cur_adv']))), 5)
                r['fut_boost_diff_3'] = round(max(-1.0, min(1.0, b3 - float(r['cur_bdiff']))), 5)

        if len(side_rows) > MAX_PER_SIDE_GAME:
            rng = random.Random(DV1._seed(job['replay_id'] + ':' + side))
            side_rows = rng.sample(side_rows, MAX_PER_SIDE_GAME)
        if len(side_cf) > MAX_CF_PER_SIDE_GAME:
            rng = random.Random(_seed(job['replay_id'] + ':' + side + ':cf'))
            side_cf = rng.sample(side_cf, MAX_CF_PER_SIDE_GAME)

        rows.extend(side_rows)
        cf_rows.extend(side_cf)
    return dict(replay_id=job['replay_id'], rows=rows, cf_rows=cf_rows, skipped=None, errors=errors)


def extract(workers: int = 36, limit: int | None = None):
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
    print('[ex221-extract] %d games to do (%d done, %d ex199 excl, %d blim excl), workers=%d' % (
        len(todo), len(done), len(ex199_held), len(blim_sets), workers), flush=True)

    tag = '%d-%d' % (int(time.time()), os.getpid())
    started, n, nrows, ncf, nerr = time.time(), 0, 0, 0, 0
    skips = Counter()
    with open(staging / ('part-%s.jsonl' % tag), 'a') as out, \
            open(staging / ('cf-%s.jsonl' % tag), 'a') as cf_out, \
            open(staging / ('errors-%s.jsonl' % tag), 'a') as err, \
            open(staging / ('done-%s.txt' % tag), 'a') as fin, \
            Pool(workers, initializer=_init, maxtasksperchild=100) as pool:
        for res in pool.imap_unordered(extract_job, todo, chunksize=1):
            if res['skipped']:
                skips[res['skipped']] += 1
            for r in res['rows']:
                out.write(json.dumps(r, separators=(',', ':')) + '\n')
            for r in res['cf_rows']:
                cf_out.write(json.dumps(r, separators=(',', ':')) + '\n')
            for e in res['errors']:
                err.write(json.dumps(dict(replay_id=res['replay_id'], error=e), separators=(',', ':')) + '\n')
            out.flush()
            cf_out.flush()
            err.flush()
            fin.write(res['replay_id'] + '\n')
            fin.flush()
            n += 1
            nrows += len(res['rows'])
            ncf += len(res['cf_rows'])
            nerr += len(res['errors'])
            if n % 200 == 0 or n == len(todo):
                rate = n / max(1e-9, time.time() - started)
                print('[ex221-extract] %d/%d games, %d rows, %d cf_pairs, %d errs, skips=%s, %.2f g/s, eta %.1f min' % (
                    n, len(todo), nrows, ncf, nerr, dict(skips), rate, (len(todo) - n) / max(1e-9, rate) / 60), flush=True)
    return dict(games=n, rows=nrows, cf_pairs=ncf, errors=nerr, skips=dict(skips))


def _save_cf_npz(path: Path, rows: list[dict], vocab: F.Vocab) -> dict:
    import numpy as np
    kind_to_id = {'reject_heal': 0, 'reject_protect': 1, 'accept_heal': 2}
    n = len(rows)
    if n == 0:
        np.savez_compressed(path, n=np.array([0]))
        return dict(pairs=0, by_kind={})
    pos_mn = np.asarray([r['pos']['mon_num'] for r in rows], dtype=np.float32)
    pos_mc = np.asarray([vocab.encode_cat(r['pos']['mon_cat']) for r in rows], dtype=np.int32)
    pos_gn = np.asarray([r['pos']['global_num'] for r in rows], dtype=np.float32)
    pos_v3m = np.asarray([r['pos']['v3_mon'] for r in rows], dtype=np.float32)
    pos_v3g = np.asarray([r['pos']['v3_glob'] for r in rows], dtype=np.float32)

    neg_mn = np.asarray([r['neg']['mon_num'] for r in rows], dtype=np.float32)
    neg_mc = np.asarray([vocab.encode_cat(r['neg']['mon_cat']) for r in rows], dtype=np.int32)
    neg_gn = np.asarray([r['neg']['global_num'] for r in rows], dtype=np.float32)
    neg_v3m = np.asarray([r['neg']['v3_mon'] for r in rows], dtype=np.float32)
    neg_v3g = np.asarray([r['neg']['v3_glob'] for r in rows], dtype=np.float32)

    kind_id = np.asarray([kind_to_id.get(r['cf_kind'], 0) for r in rows], dtype=np.int8)
    hp_frac = np.asarray([r['hp_frac'] for r in rows], dtype=np.float32)
    opp_setup = np.asarray([r['opp_setup'] for r in rows], dtype=np.int8)
    weight = np.asarray([r['weight'] for r in rows], dtype=np.float32)

    np.savez_compressed(
        path,
        pos_mon_num=pos_mn, pos_mon_cat=pos_mc, pos_global_num=pos_gn, pos_v3_mon=pos_v3m, pos_v3_glob=pos_v3g,
        neg_mon_num=neg_mn, neg_mon_cat=neg_mc, neg_global_num=neg_gn, neg_v3_mon=neg_v3m, neg_v3_glob=neg_v3g,
        kind_id=kind_id, hp_frac=hp_frac, opp_setup=opp_setup, weight=weight,
    )
    by_kind = dict(Counter(r['cf_kind'] for r in rows))
    return dict(pairs=n, games=len({r['game'] for r in rows}), by_kind=by_kind)


def build():
    """Deduplicate staged rows & CF pairs, apply EXACT EX-207 game split, save `.npz` splits."""
    import numpy as np
    staging = RUN / 'staging'
    by_sid = {}
    for p in sorted(staging.glob('part-*.jsonl')):
        with open(p) as f:
            for line in f:
                if line.strip():
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
        v3m = np.asarray([r['v3_mon'] for r in rows], dtype=np.float32)
        v3g = np.asarray([r['v3_glob'] for r in rows], dtype=np.float32)
        y = np.asarray([r['win'] for r in rows], dtype=np.float32)
        er = np.asarray([r['eval_rs'] for r in rows], dtype=np.float32)
        tn = np.asarray([r['turn'] for r in rows], dtype=np.int16)
        # Multi-horizon future targets [N, 5]: [fut_adv_3, fut_adv_5, fut_adv_10, fut_delta_5, fut_boost_diff_3]
        fut = np.asarray([
            [r['fut_adv_3'], r['fut_adv_5'], r['fut_adv_10'], r['fut_delta_5'], r['fut_boost_diff_3']]
            for r in rows
        ], dtype=np.float32)
        np.savez_compressed(
            OUT / f'{name}.npz',
            mon_num=mn, mon_cat=mc, global_num=gn, v3_mon=v3m, v3_glob=v3g,
            win=y, eval_rs=er, turn=tn, fut=fut,
        )
        counts[name] = dict(rows=len(rows), games=len({r['game'] for r in rows}),
                            win_rate=round(float(y.mean()), 4) if len(y) else None)

    # Counterfactual pairs — strictly split by the EXACT SAME game sets!
    cf_by_sid = {}
    for p in sorted(staging.glob('cf-*.jsonl')):
        with open(p) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    cf_by_sid[r['sample_id']] = r
    cf_splits = {'train': [], 'calib': [], 'val': []}
    for r in cf_by_sid.values():
        g = r['game']
        if g in val_games:
            cf_splits['val'].append(r)
        elif g in cal_games:
            cf_splits['calib'].append(r)
        elif g in tr_games:
            cf_splits['train'].append(r)

    cf_counts = {}
    for name, rows in cf_splits.items():
        cf_counts[name] = _save_cf_npz(OUT / f'{name}_cf.npz', rows, vocab)

    manifest = dict(
        experiment='EX-221',
        decision='D-223',
        source=str(SOURCE),
        seed=SEED,
        val_frac=VAL_FRAC,
        calib_frac=CALIB_FRAC,
        max_per_side_game=MAX_PER_SIDE_GAME,
        max_cf_per_side_game=MAX_CF_PER_SIDE_GAME,
        vocab_sizes=vocab.sizes(),
        splits=counts,
        cf_splits=cf_counts,
        fut_cols=['fut_adv_3', 'fut_adv_5', 'fut_adv_10', 'fut_delta_5', 'fut_boost_diff_3'],
        at=time.time(),
    )
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('extract', 'build'))
    ap.add_argument('--workers', type=int, default=36)
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    if args.cmd == 'extract':
        print(json.dumps(extract(args.workers, args.limit)))
    else:
        build()
