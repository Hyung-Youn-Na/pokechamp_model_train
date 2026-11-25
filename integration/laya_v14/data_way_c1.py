"""EP-246 / D-222 (EX-218, Way C-1): v14+walled_duel upgrade + Hard-Example MCTS 50k + EX-216 V_phi v2 teacher targets.

Pipeline (runs safely in parallel with EX-217 on GPU 0 using CPU `nice 19` + physical GPU 1 ONLY):
1. `upgrade-walled`: incrementally re-renders only `turn_action` rows lacking `duel:` from `laya-v14-mcts5k-q/v1`
   using `render_v14 + way_a.install_walled_duel()`, writing byte-accurate `v14+walled_duel` base files (~2-3 min).
2. `select-hard`: picks 25,000 hard train + 3,000 hard held-out turns (100% of `walled` & `absorb`, plus top
   `duel: lose` / `opp heals:` / endgame / MCTS-disagreement turns).
3. `infer-hard`: runs EX-200 on physical GPU 1 ONLY to compute `p(a)` + `foe q(b)` (`foe_options_clean`) for hard turns.
4. `vphi-server`: lightweight local HTTP scorer hosting EX-216 `ValueScorerV2` on physical GPU 1 ONLY (<300 MiB).
5. `search-hard`: 28-worker `nice 19` CPU pool (`foul-play` venv, `PYTHONHASHSEED=0`) running `MCTS 50,000 iterations`
   + `expand_turn1_features_v2` and querying `vphi-server` for `Q_vphi_v2`, writing compact JSONL (~15 MB total).
6. `build-targets`: builds KL-regularized teacher soft targets (`Q_teacher = 0.55*Q_mcts50k_adj + 0.45*Q_vphi2`,
   `tau=0.025`, automatic rescue/walled promotion) and finalizes `datasets/generated/laya-v14w-c1/v1/`.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from multiprocessing import Pool
import os
from pathlib import Path
import random
import re
import time
import traceback
from urllib.request import Request, urlopen

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic
from integration.laya_search import featurize as F
from integration.laya_search import search_2b as S2B
from integration.laya_search import search_2b_v2 as S2BV2
from integration.laya_search import search_core as SC
from integration.laya_search import way_a as WA

SRC_V14 = c.SHARED / 'datasets/generated/laya-v14-mcts5k-q/v1'
OUT = c.SHARED / 'datasets/generated/laya-v14w-c1/v1'
ANCHOR = OUT / 'anchor'
FOE = OUT / 'foe-anchor.jsonl'
RUN = c.SHARED / 'runs/model-training/EX-218'
EX200_CKPT = c.SHARED / 'runs/model-training/EX-200/checkpoints/selected'
EX216_CKPT = c.SHARED / 'runs/model-training/EX-216/checkpoints/selected'

SEED = 20261218
HARD_TRAIN_TARGET = 25000
HARD_HELDOUT_TARGET = 3000
MCTS_ITERS_C1 = 50000
TEACHER_ALPHA_VPHI = 0.45
TAU_TEACHER = 0.025
RESCUE_GAP_C1 = 0.06
WALLED_RESCUE_GAP = 0.015
NEAR_CAND = 0.15
MAX_CANDS = 4

_BOARD_RE = re.compile(r'^board:\s*me\s+(\d+)\s+alive\b.*\|\s*opp\s+(\d+)\s+alive\b')


def _sid(line: str) -> str:
    return line[14:line.index('"', 14)]


def _game_of(sid: str) -> str:
    return sid.rsplit(':', 3)[0]


def _needs_walled_rerender(row: dict) -> bool:
    """True iff `row` is a `turn_action` without a `duel:` line (only rows where `install_walled_duel` can fire)."""
    if ':turn_action' not in row.get('sample_id', ''):
        return False
    st = row.get('state', '')
    return ('\nduel: ' not in st) and (not st.startswith('duel: '))


# ---------------------------------------------------------------------------------------------- 1. upgrade-walled

def _walled_worker_init(source_name: str):
    from integration.laya_v14 import data_v14
    data_v14._worker_init(source_name)
    WA.install_walled_duel()


def upgrade_walled(workers: int = 16) -> dict:
    """Incrementally re-render only `turn_action` rows lacking `duel:` with `render_v14 + walled_duel`."""
    from integration.laya_foe import data_foe
    from integration.laya_ladder import paths as ladder
    from integration.laya_v14 import data_v14, render_v14

    if (OUT / 'v14w_train_base.jsonl').exists() and (ANCHOR / 'validation.jsonl').exists() and FOE.exists():
        print('[c1-walled] already upgraded:', OUT, flush=True)
        return json.loads((OUT / 'walled-upgrade.json').read_text())

    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    ANCHOR.mkdir(parents=True, exist_ok=True)

    # Scan all 5 v14 files to collect exact unique sample_ids lacking `duel:`
    cand_ids: set[str] = set()
    for rel in ('train.jsonl', 'heldout.jsonl', 'anchor/train.jsonl', 'anchor/validation.jsonl', 'foe-anchor.jsonl'):
        with open(SRC_V14 / rel) as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                sid = r['sample_id']
                base_sid = sid[:-4] if sid.endswith(':foe') else sid
                if ':turn_action' in base_sid and '\nduel: ' not in r['state'] and not r['state'].startswith('duel: '):
                    cand_ids.add(base_sid)

    print(f'[c1-walled] unique turn_action sample_ids without duel line: {len(cand_ids)}', flush=True)

    # Re-render only `cand_ids` with `render_v14 + install_walled_duel()`
    rerendered: dict[str, dict] = {}
    walled_added = 0
    for source_name, splits in (('tour', ('train', 'validation')), ('ladder', ('train', 'validation'))):
        remaining = cand_ids - set(rerendered)
        if not remaining:
            break
        print(f'[c1-walled] scanning source={source_name} ({len(remaining)} remaining)...', flush=True)
        with Pool(workers, initializer=_walled_worker_init, initargs=(source_name,)) as pool:
            for split in splits:
                remaining = cand_ids - set(rerendered)
                if not remaining:
                    break
                for sid, sha_v, state, question, flags in pool.imap_unordered(
                    data_v14._render_job, data_v14._filtered_rows(source_name, split, remaining), chunksize=16
                ):
                    if WA.is_walled_state(state) and flags.get('fits'):
                        rerendered[sid] = dict(input_sha256=sha_v, state=state, question=question)
                        walled_added += 1
                    else:
                        rerendered[sid] = None
        print(f'[c1-walled] after {source_name}: checked={len(rerendered)}/{len(cand_ids)}, walled_added={walled_added}', flush=True)

    counts = Counter()
    upgraded = Counter()
    file_map = (
        ('train_base', SRC_V14 / 'train.jsonl', OUT / 'v14w_train_base.jsonl'),
        ('heldout_base', SRC_V14 / 'heldout.jsonl', OUT / 'v14w_heldout_base.jsonl'),
        ('anchor_train', SRC_V14 / 'anchor/train.jsonl', ANCHOR / 'train.jsonl'),
        ('anchor_val', SRC_V14 / 'anchor/validation.jsonl', ANCHOR / 'validation.jsonl'),
    )
    for tag, src_p, dst_p in file_map:
        with open(src_p) as fin, open(dst_p, 'w') as fout:
            for line in fin:
                if not line.strip():
                    continue
                r = json.loads(line)
                upd = rerendered.get(r['sample_id'])
                if upd is not None and list(r['questions']['action']['criteria']) == list(upd['question']['criteria']):
                    r['state'] = upd['state']
                    r['input_sha256'] = upd['input_sha256']
                    r['questions']['action'] = upd['question']
                    upgraded[tag] += 1
                fout.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
                counts[tag] += 1

    # Foe anchor
    with open(SRC_V14 / 'foe-anchor.jsonl') as fin, open(FOE, 'w') as fout:
        for line in fin:
            if not line.strip():
                continue
            r = json.loads(line)
            sid = r['sample_id']
            base_sid = sid[:-4] if sid.endswith(':foe') else sid
            upd = rerendered.get(base_sid)
            if upd is not None:
                r['state'] = upd['state']
                r['input_sha256'] = upd['input_sha256']
                # Criteria unaffected by duel line, keep existing clean criteria
                upgraded['foe'] += 1
            fout.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
            counts['foe'] += 1

    render_v14.install()
    WA.install_walled_duel()
    anc_manifest = dict(
        source=str(SRC_V14 / 'anchor'),
        render=render_v14.VERSION.rstrip(']') + ',walled_duel]',
        rows=counts['anchor_train'],
        validation_rows=counts['anchor_val'],
        foe=dict(source=str(FOE), rows=counts['foe']),
        at=time.time(),
    )
    atomic(ANCHOR / 'manifest.json', anc_manifest)
    summary = dict(
        candidates_checked=len(rerendered),
        unique_walled_added=walled_added,
        counts=dict(counts),
        upgraded_rows=dict(upgraded),
        seconds=round(time.time() - started, 1),
        at=time.time(),
    )
    atomic(OUT / 'walled-upgrade.json', summary)
    print('[c1-walled] DONE:', json.dumps(summary, indent=1), flush=True)
    return summary


# ---------------------------------------------------------------------------------------------- 2. select-hard

def _hard_priority(row: dict) -> tuple[int, float]:
    """Priority tier (higher = harder/higher-leverage) for selecting Hard-Example 50k+V_phi2 turns."""
    st = row['state']
    crit = row['questions']['action']['criteria']
    walled = WA.is_walled_state(st)
    absorb = any('; heals opp 25%' in v or '; boosts opp' in v for v in crit.values())
    duel_lose = S2BV2.is_duel_lose(st)
    heals = '\nopp heals: ' in st
    alive_tot = WA.total_alive_from_state(st)
    endgame = alive_tot is not None and alive_tot <= 5
    forced = ':forced_switch' in row['sample_id']

    gold_p = (row.get('gold') or {}).get('action', {}).get('probabilities') or {}
    ex209 = (row.get('meta') or {}).get('ex209') or {}
    laya_arg = ex209.get('laya_argmax')
    gold_arg = max(gold_p, key=gold_p.get) if gold_p else None
    changed = (laya_arg is not None and gold_arg is not None and laya_arg != gold_arg)
    qm = ex209.get('q_mcts') or {}
    q_spread = (max(qm.values()) - min(qm.values())) if len(qm) >= 2 else 0.0

    # Tier 4: ALL walled & absorb (100% included!)
    if walled or absorb:
        return (4, 1.0 + q_spread)
    # Tier 3: MCTS-5k disagreed with EX-196 on losing/healing/endgame/forced turns
    if changed and (duel_lose or heals or endgame or forced):
        return (3, q_spread + (0.2 if duel_lose else 0.0) + (0.15 if endgame else 0.0))
    # Tier 2: duel: lose + opp heals (Draining Kiss / Recover walls!) or endgame
    if (duel_lose and heals) or endgame:
        return (2, q_spread + (0.2 if duel_lose else 0.0))
    # Tier 1: any MCTS-5k argmax flip or duel: lose or forced_switch
    if changed or duel_lose or forced:
        return (1, q_spread)
    return (0, q_spread)


def select_hard(train_target: int = HARD_TRAIN_TARGET, held_target: int = HARD_HELDOUT_TARGET) -> dict:
    """Deterministically select hard train & held-out sample_ids + action lists for 50k + V_phi v2 teacher."""
    sel_path = RUN / 'hard-selection.json'
    if sel_path.exists():
        print('[c1-select] already exists:', sel_path, flush=True)
        return json.loads(sel_path.read_text())

    RUN.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    out = {}
    stats = {}
    for split, src_p, target in (
        ('train', OUT / 'v14w_train_base.jsonl', train_target),
        ('heldout', OUT / 'v14w_heldout_base.jsonl', held_target),
    ):
        scored = []
        tier_avail = Counter()
        with open(src_p) as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                cands = list(r['questions']['action']['criteria'])
                if len(cands) < 2:
                    continue
                tier, tie = _hard_priority(r)
                tier_avail[tier] += 1
                scored.append((tier, tie + rng.random() * 1e-4, r['sample_id'], cands))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        chosen = scored[:target]
        tier_pick = Counter(x[0] for x in chosen)
        out[split] = {sid: cands for _, _, sid, cands in chosen}
        stats[split] = dict(available=len(scored), selected=len(chosen),
                            tier_avail=dict(sorted(tier_avail.items())),
                            tier_selected=dict(sorted(tier_pick.items())))

    payload = dict(seed=SEED, stats=stats, splits=out, at=time.time())
    atomic(sel_path, payload)
    print('[c1-select] DONE:', json.dumps(stats, indent=1), flush=True)
    return payload


# ---------------------------------------------------------------------------------------------- 3. infer-hard (GPU 1 ONLY)

def infer_hard(batch_size: int = 32) -> dict:
    """Run EX-200 on physical GPU 1 ONLY to compute `p(a)` + `foe q(b)` (`foe_options_clean`) for all hard turns."""
    from integration.laya_foe.data_foe import INSTRUCTIONS
    from integration.laya_imitation.resources import gpu
    from integration.laya_ladder import paths as ladder
    from integration.laya_v10 import training_v10

    out_path = RUN / 'infer-hard.jsonl'
    sel = json.loads((RUN / 'hard-selection.json').read_text())
    wanted = set(sel['splits']['train']) | set(sel['splits']['heldout'])
    done = set()
    if out_path.exists():
        with open(out_path) as f:
            for line in f:
                if line.strip():
                    done.add(_sid(line))
    remaining = wanted - done
    if not remaining:
        print(f'[c1-infer] already done ({len(done)}/{len(wanted)})', flush=True)
        return dict(done=len(done), total=len(wanted))

    rows = []
    for src_p in (OUT / 'v14w_train_base.jsonl', OUT / 'v14w_heldout_base.jsonl'):
        with open(src_p) as f:
            for line in f:
                if not line.strip():
                    continue
                sid = _sid(line)
                if sid in remaining:
                    rows.append(json.loads(line))

    training_v10.install(ladder.OPTION_LIMIT)
    import laya.train as LT
    orig_fwd = LT._forward
    LT._forward = lambda m, b, d, amp, detach_encoder: orig_fwd(m, b, d, True, detach_encoder)

    # Strictly pin physical GPU 1 ONLY (EX-217 runs on GPU 0; GPUs 2 & 3 never touched!)
    with gpu(1, SC.GPU1_UUID) as (env, _):
        os.environ.update(env)
        policy = training_v10.Policy10(EX200_CKPT, head_limit=ladder.HEAD_LIMIT)
        print(f'[c1-infer] scoring {len(rows)} hard rows on physical GPU 1 ({SC.GPU1_UUID})...', flush=True)
        started = time.time()
        with open(out_path, 'a') as out_f:
            for start in range(0, len(rows), 256):
                chunk = rows[start:start + 256]
                items = []
                meta_idx = []
                for r in chunk:
                    q_act = r['questions']['action']
                    act_idx = len(items)
                    items.append(policy.item(r['state'], q_act))
                    foe_idx = None
                    foe_ids = None
                    if ':turn_action' in r['sample_id']:
                        fc = S2BV2.foe_options_clean(r['state'])
                        if fc:
                            foe_q = dict(type='choice', instructions=INSTRUCTIONS, criteria=fc)
                            foe_idx = len(items)
                            foe_ids = list(fc)
                            items.append(policy.item(r['state'], foe_q))
                    meta_idx.append((r, list(q_act['criteria']), act_idx, foe_idx, foe_ids))
                logits = policy.logits(items, batch_size=batch_size)
                for r, aids, ai, fi, fids in meta_idx:
                    ap, _ = policy.distribution(logits[ai], len(aids))
                    p = {k: round(float(v), 6) for k, v in zip(aids, ap)}
                    q = None
                    if fi is not None and fids:
                        fp, _ = policy.distribution(logits[fi], len(fids))
                        q = {k: round(float(v), 6) for k, v in zip(fids, fp)}
                    lbl = (r.get('expected') or {}).get('action') or ((r.get('meta') or {}).get('ex209') or {}).get('label')
                    out_f.write(json.dumps(dict(
                        sample_id=r['sample_id'], p=p, foe=q, label=lbl,
                    ), separators=(',', ':')) + '\n')
                out_f.flush()
                done_n = start + len(chunk)
                if done_n % 2560 == 0 or done_n == len(rows):
                    rate = done_n / max(1e-9, time.time() - started)
                    print(f'[c1-infer] {done_n}/{len(rows)} ({rate:.1f} rows/s)', flush=True)
    return dict(done=len(done) + len(rows), total=len(wanted))


# ---------------------------------------------------------------------------------------------- 4. vphi-server (GPU 1 ONLY)

def serve_vphi2(ready_file: Path, port: int = 0):
    """Lightweight HTTP server hosting EX-216 Matchup-Aware `ValueScorerV2` on physical GPU 1 ONLY."""
    import threading
    from integration.laya_imitation.resources import gpu
    from integration.laya_search import value_model_v2 as VM2

    with gpu(1, SC.GPU1_UUID) as (env, _):
        os.environ.update(env)
        scorer = VM2.ValueScorerV2(EX216_CKPT, device='cuda')
        lock = threading.Lock()
        # Warm up CUDA allocator once
        _ = scorer.score_raw_batch([])

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                if self.path == '/health':
                    body = json.dumps({'ok': True, 'arch': scorer.cfg['arch']}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if self.path != '/score':
                    self.send_response(404)
                    self.end_headers()
                    return
                n = int(self.headers.get('Content-Length', '0'))
                req = json.loads(self.rfile.read(n))
                raws = req.get('unique_raws') or []
                with lock:
                    probs = scorer.score_raw_batch(raws) if raws else []
                body = json.dumps({'probs': probs}, separators=(',', ':')).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        actual_port = server.server_address[1]
        ready_file.parent.mkdir(parents=True, exist_ok=True)
        ready_file.write_text(json.dumps(dict(endpoint=f'http://127.0.0.1:{actual_port}', pid=os.getpid())))
        print(f'[c1-vphi2] serving EX-216 ValueScorerV2 on GPU 1 at http://127.0.0.1:{actual_port}', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()


# ---------------------------------------------------------------------------------------------- 5. search-hard (foul-play venv, CPU nice 19)

_vphi_endpoint = None


def _search_seed(sid: str) -> int:
    return int(hashlib.sha256(('ex218:' + sid).encode()).hexdigest()[:16], 16)


def _search_init(endpoint: str):
    global _vphi_endpoint
    from integration.laya_fp1 import tracker
    tracker.setup()
    _vphi_endpoint = endpoint


def _score_vphi2_remote(unique_raws: list[dict]) -> list[float]:
    if not unique_raws or not _vphi_endpoint:
        return []
    payload = json.dumps({'unique_raws': unique_raws}, separators=(',', ':')).encode()
    req = Request(_vphi_endpoint + '/score', data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())['probs']


def _search_job(job: dict) -> dict:
    from integration.laya_distill.data_distill import choice_map, restrict
    from integration.laya_fp1 import data_fp1 as DF
    from integration.laya_fp1 import tracker as T
    from integration.laya_regret.search import sample_states

    want = job['wanted']  # sid -> {'aids': [...], 'foe': {...} or None}
    blim_sets: set[frozenset[str]] = job['blim_sets']
    iters = int(job['iterations'])
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
        if not any(f':{side}:' in s for s in want):
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
                        info = want[sid]
                        view = tracker.view()
                        mapping = choice_map(view, [{'id': a} for a in info['aids']], own)
                        mapping = {a: ch for a, ch in mapping.items() if ch}
                        if len(mapping) >= 2:
                            restrict(view, mapping)
                            samples, _ = sample_states(view, _search_seed(sid))
                            res = SC.search_mcts_samples(samples, mapping, iterations=iters)
                            q_vphi2 = None
                            absorb_pen = {}
                            if kind == 'turn_action' and info.get('foe'):
                                exp = S2BV2.expand_turn1_features_v2(samples, mapping, info['foe'])
                                absorb_pen = exp.get('absorb_penalties') or {}
                                raws = exp.get('unique_raws') or []
                                if raws:
                                    probs = _score_vphi2_remote(raws)
                                    q_vphi2 = S2B.aggregate_value_2b(exp, probs)
                            rows.append(dict(
                                sample_id=sid, kind=kind,
                                q_mcts50=res['q_mcts'], root_q=res['root_q'],
                                q_vphi2=q_vphi2, absorb_penalties=absorb_pen,
                                samples=res['samples'], errors=res['errors'], seconds=res['seconds'],
                            ))
                tracker.chose(record.get('label'))
            except Exception as exc:
                errors.append(dict(side=side, sample_id=sid, stage='decision', error='%s: %s' % (type(exc).__name__, exc),
                                   trace=traceback.format_exc(limit=2)[-400:]))
                break
    return dict(replay_id=job['replay_id'], rows=rows, skipped=None, errors=errors)


def search_hard(workers: int = 28, iterations: int = MCTS_ITERS_C1, endpoint: str = '') -> dict:
    from integration.laya_fp1.data_fp1 import jobs

    if os.environ.get('PYTHONHASHSEED') != '0':
        raise RuntimeError('run with PYTHONHASHSEED=0')
    staging = RUN / 'search50k'
    staging.mkdir(parents=True, exist_ok=True)
    done = set()
    for p in staging.glob('done-*.txt'):
        done.update(p.read_text().split())

    want: dict[str, dict] = {}
    with open(RUN / 'infer-hard.jsonl') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if len(r['p']) >= 2:
                want[r['sample_id']] = dict(aids=list(r['p']), foe=r.get('foe'))

    blim_sets = F.blim_eval_team_sets()
    all_jobs = jobs({sid: True for sid in want})
    todo = [
        dict(j, wanted={s: want[s] for s in j['wanted']}, blim_sets=blim_sets, iterations=iterations)
        for j in all_jobs if j['replay_id'] not in done
    ]
    print(f'[c1-search50k] {len(want)} hard turns across {len(todo)} games to do ({len(done)} done), workers={workers}, iters={iterations}, vphi={endpoint}', flush=True)
    if not todo:
        return dict(games=0, rows=0, errors=0)

    tag = '%d-%d' % (int(time.time()), os.getpid())
    started, n, nrows, nerr = time.time(), 0, 0, 0
    with open(staging / f'part-{tag}.jsonl', 'a') as out, \
            open(staging / f'errors-{tag}.jsonl', 'a') as err, \
            open(staging / f'done-{tag}.txt', 'a') as fin, \
            Pool(workers, initializer=_search_init, initargs=(endpoint,), maxtasksperchild=40) as pool:
        for res in pool.imap_unordered(_search_job, todo, chunksize=1):
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
                print(f'[c1-search50k] {n}/{len(todo)} games, {nrows} rows, {nerr} errs, {rate:.2f} g/s, eta {(len(todo)-n)/max(1e-9,rate)/60:.1f} min', flush=True)
    return dict(games=n, rows=nrows, errors=nerr)


# ---------------------------------------------------------------------------------------------- 6. build-targets

def gold_way_c1(
    p: dict[str, float],
    q_mcts50: dict[str, float] | None,
    q_vphi2: dict[str, float] | None,
    *,
    state: str = '',
    absorb_penalties: dict[str, float] | None = None,
    alpha_vphi: float = TEACHER_ALPHA_VPHI,
    tau: float = TAU_TEACHER,
) -> tuple[dict[str, float] | None, list[str], dict[str, float]]:
    """Build KL-regularized Way C-1 teacher soft target from MCTS 50k + EX-216 V_phi v2.

    Returns `(gold_probs_or_None, selected_candidates, q_teacher)`.
    """
    if not p:
        return None, [], {}
    pen = absorb_penalties or {}
    qm = {a: float(v) - float(pen.get(a, 0.0)) for a, v in (q_mcts50 or {}).items() if a in p and math.isfinite(v)}
    qv = {a: float(v) for a, v in (q_vphi2 or {}).items() if a in p and math.isfinite(v)}
    if not qm and not qv:
        return None, [], {}

    q_teacher: dict[str, float] = {}
    for a in set(qm) | set(qv):
        m_val = qm.get(a)
        v_val = qv.get(a)
        if m_val is not None and v_val is not None:
            q_teacher[a] = (1.0 - alpha_vphi) * m_val + alpha_vphi * v_val
        elif m_val is not None:
            q_teacher[a] = m_val
        elif v_val is not None:
            q_teacher[a] = v_val

    if len(q_teacher) < 2:
        return None, [], q_teacher

    ranked = sorted(sorted(p), key=lambda a: p[a], reverse=True)
    argmax = ranked[0]
    top_p = p[argmax]
    cands = [a for a in ranked if p[a] >= NEAR_CAND * top_p and a in q_teacher][:MAX_CANDS]
    if len(cands) < 2:
        cands = [a for a in ranked if a in q_teacher][:2]

    # Automatic rescue promotion: promote decisive MCTS-50k+V_phi2 rescue (lower threshold on walled turns!)
    best_q_act = max(sorted(q_teacher), key=lambda a: (q_teacher[a], p.get(a, 0.0)))
    ref_q = q_teacher.get(argmax)
    walled = WA.is_walled_state(state)
    gap_req = WALLED_RESCUE_GAP if walled else RESCUE_GAP_C1
    if best_q_act not in cands and ref_q is not None and (q_teacher[best_q_act] - ref_q) >= gap_req:
        cands.append(best_q_act)
    # Also on walled turns, if MCTS 50k itself clearly prefers a switch (`dm >= 0.01`) promote it!
    if walled and qm and argmax in qm:
        best_m = max(sorted(qm), key=lambda a: (qm[a], p.get(a, 0.0)))
        if best_m not in cands and (qm[best_m] - qm[argmax]) >= WA.WALLED_MCTS_DELTA:
            cands.append(best_m)

    if len(cands) < 2:
        return None, cands, q_teacher

    out = {k: float(v) for k, v in p.items()}
    mass = sum(out[a] for a in cands)
    if mass <= 0.0:
        return None, cands, q_teacher

    # On walled turns, relax prior slightly (floor 1e-3, effective tau sharper) so MCTS 50k switch rescues imprint cleanly
    eff_tau = tau * 0.7 if walled else tau
    floor = 1e-3 if walled else SC.PRIOR_FLOOR
    log_w = {a: math.log(max(out[a], floor)) + float(q_teacher[a]) / float(eff_tau) for a in cands}
    mx = max(log_w.values())
    unnorm = {a: math.exp(log_w[a] - mx) for a in cands}
    z = sum(unnorm.values())
    for a in cands:
        out[a] = mass * unnorm[a] / z
    tot = sum(out.values())
    if tot > 0.0:
        out = {k: v / tot for k, v in out.items()}
    return out, cands, {k: round(v, 6) for k, v in q_teacher.items()}


def build_targets() -> dict:
    """Assemble `hard_train.jsonl`, `general_train.jsonl`, `hard_heldout.jsonl`, `heldout.jsonl`, and `manifest.json`."""
    if (OUT / 'manifest.json').exists():
        print('[c1-targets] already built:', OUT / 'manifest.json', flush=True)
        return json.loads((OUT / 'manifest.json').read_text())

    started = time.time()
    infer_map = {}
    with open(RUN / 'infer-hard.jsonl') as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                infer_map[r['sample_id']] = r

    search_map = {}
    for p in sorted((RUN / 'search50k').glob('part-*.jsonl')):
        with open(p) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    search_map[r['sample_id']] = r

    stats = Counter()
    for split, src_p, hard_dst, gen_dst in (
        ('train', OUT / 'v14w_train_base.jsonl', OUT / 'hard_train.jsonl', OUT / 'general_train.jsonl'),
        ('heldout', OUT / 'v14w_heldout_base.jsonl', OUT / 'hard_heldout.jsonl', OUT / 'heldout.jsonl'),
    ):
        with open(src_p) as fin, open(hard_dst, 'w') as fh, open(gen_dst, 'w') as fg:
            for line in fin:
                if not line.strip():
                    continue
                r = json.loads(line)
                sid = r['sample_id']
                s_rec = search_map.get(sid)
                i_rec = infer_map.get(sid)
                upgraded = False
                if s_rec is not None and i_rec is not None:
                    g, cands, qt = gold_way_c1(
                        i_rec['p'], s_rec.get('q_mcts50'), s_rec.get('q_vphi2'),
                        state=r['state'], absorb_penalties=s_rec.get('absorb_penalties'),
                    )
                    if g is not None:
                        laya_arg = max(i_rec['p'], key=i_rec['p'].get)
                        gold_arg = max(g, key=g.get)
                        r['gold'] = dict(action=dict(probabilities=g))
                        r.setdefault('meta', {})['ex218'] = dict(
                            candidates=cands, q_teacher=qt,
                            q_mcts50=s_rec.get('q_mcts50'), q_vphi2=s_rec.get('q_vphi2'),
                            laya_argmax=laya_arg, gold_argmax=gold_arg,
                            label=i_rec.get('label'),
                            walled=WA.is_walled_state(r['state']),
                            absorb_penalties=s_rec.get('absorb_penalties') or {},
                        )
                        fh.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
                        stats[f'{split}_hard'] += 1
                        if gold_arg != laya_arg:
                            stats[f'{split}_hard_changed'] += 1
                        if s_rec.get('q_vphi2'):
                            stats[f'{split}_hard_with_vphi2'] += 1
                        if WA.is_walled_state(r['state']):
                            stats[f'{split}_hard_walled'] += 1
                            if gold_arg != laya_arg:
                                stats[f'{split}_hard_walled_changed'] += 1
                        upgraded = True
                if split == 'heldout' or not upgraded:
                    fg.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
                    stats[f'{split}_general'] += 1

    if stats['train_hard'] < 1000 or stats['heldout_hard'] < 100:
        raise RuntimeError(f'Way C-1 build_targets got too few hard rows: {dict(stats)}')
    walled_info = json.loads((OUT / 'walled-upgrade.json').read_text())
    manifest = dict(
        experiment='EX-218',
        decision='D-222',
        way='C-1 (v14+walled_duel + Hard-Example MCTS 50k + EX-216 V_phi v2 teacher)',
        mcts_iterations=MCTS_ITERS_C1,
        teacher_alpha_vphi=TEACHER_ALPHA_VPHI,
        tau_teacher=TAU_TEACHER,
        walled_upgrade=walled_info,
        stats=dict(stats),
        seconds=round(time.time() - started, 1),
        at=time.time(),
    )
    atomic(OUT / 'manifest.json', manifest)
    print('[c1-targets] COMPLETE:', json.dumps(manifest, indent=1), flush=True)
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('upgrade-walled', 'select-hard', 'infer-hard', 'vphi-server', 'search-hard', 'build-targets'))
    ap.add_argument('--workers', type=int, default=16)
    ap.add_argument('--iterations', type=int, default=MCTS_ITERS_C1)
    ap.add_argument('--ready-file', type=Path, default=RUN / 'vphi2.ready.json')
    ap.add_argument('--endpoint', default='')
    ap.add_argument('--train-target', type=int, default=HARD_TRAIN_TARGET)
    ap.add_argument('--held-target', type=int, default=HARD_HELDOUT_TARGET)
    args = ap.parse_args()
    if args.cmd == 'upgrade-walled':
        upgrade_walled(workers=args.workers)
    elif args.cmd == 'select-hard':
        select_hard(train_target=args.train_target, held_target=args.held_target)
    elif args.cmd == 'infer-hard':
        infer_hard()
    elif args.cmd == 'vphi-server':
        serve_vphi2(ready_file=args.ready_file)
    elif args.cmd == 'search-hard':
        ep = args.endpoint
        if not ep and args.ready_file.exists():
            ep = json.loads(args.ready_file.read_text())['endpoint']
        search_hard(workers=args.workers, iterations=args.iterations, endpoint=ep)
    elif args.cmd == 'build-targets':
        build_targets()
