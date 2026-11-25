"""EP-248 / D-224 (EX-225, Way C-1 Clean): Re-score EX-218's 28k hard turns with EX-221 V_phi v3 + 2-ply Top-K
and build purified Way C-1 teacher targets (`datasets/generated/laya-v14w-c1v3/v1/`).

Reuses EX-218's existing `v14w_*_base.jsonl`, `infer-hard.jsonl` (EX-200 p/foe), and `search50k/part-*.jsonl`
(MCTS 50,000 iterations already computed — saves ~2 hours!), replacing ONLY the biased EX-216 V_phi v2 1-ply
scores with EX-221 Future-Aware V_phi v3 + 2-ply Top-K Expectiminimax:
1. `vphi3-server` (`laya` venv, physical GPU 1 ONLY, <300 MiB): serves EX-221 `ValueScorerV3`.
2. `rescore-2ply` (`foul-play` venv, CPU 32w `nice 19`, `PYTHONHASHSEED=0`): runs `search_multiturn.expand_and_score_2ply`
   on all ~28k hard turns (~12-18 min) -> `runs/model-training/EX-225/vphi3_2ply/part-*.jsonl`.
3. `build-targets` (`laya` venv): builds `Q_teacher = 0.45*Q_mcts50_adj + 0.55*Q_vphi3_2ply` with Way A v2
   recovery/Protect rescue guardrails (never rescue-promote Protect or HP>=85% heal), writes purified
   `datasets/generated/laya-v14w-c1v3/v1/`, and logs an automatic HP-recovery purity audit vs Human & EX-218!
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from multiprocessing import Pool
import os
from pathlib import Path
import re
import threading
import time
import traceback
from urllib.request import Request, urlopen

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic
from integration.laya_search import featurize as F
from integration.laya_search import featurize_v3 as F3
from integration.laya_search import search_core as SC
from integration.laya_search import search_multiturn as SMT
from integration.laya_search import way_a as WA
from integration.laya_search import way_a_v2 as WA2

EX218_RUN = c.SHARED / 'runs/model-training/EX-218'
EX218_DATA = c.SHARED / 'datasets/generated/laya-v14w-c1/v1'
EX221_CKPT = c.SHARED / 'runs/model-training/EX-221/checkpoints/selected'

RUN = c.SHARED / 'runs/model-training/EX-225'
OUT = c.SHARED / 'datasets/generated/laya-v14w-c1v3/v1'

# Clean teacher weights: give future-aware 2-ply V_phi v3 majority weight (0.55) over evaluate.rs MCTS 50k (0.45)
TEACHER_ALPHA_VPHI3 = 0.55
TAU_TEACHER = 0.025
RESCUE_GAP = 0.06
WALLED_RESCUE_GAP = 0.015
NEAR_CAND = 0.15
MAX_CANDS = 4

_ME_HP_RE = re.compile(r'^ME\s+\S+\s+\[[^\]]*\]\s+(\d+(?:\.\d+)?)%', re.M)


def _search_seed(sid: str) -> int:
    return int(hashlib.sha256(('ex218:' + sid).encode()).hexdigest()[:16], 16)


# ---------------------------------------------------------------------------------------------- 1. vphi3-server (GPU 1 ONLY)

def serve_vphi3(ready_file: Path, ckpt: Path = EX221_CKPT, port: int = 0):
    """Lightweight HTTP server hosting EX-221 Future-Aware `ValueScorerV3` on physical GPU 1 ONLY (<300 MiB)."""
    from integration.laya_imitation.resources import gpu
    from integration.laya_search import value_model_v3 as VM3

    with gpu(1, SC.GPU1_UUID) as (env, _):
        os.environ.update(env)
        scorer = VM3.ValueScorerV3(ckpt, device='cuda')
        lock = threading.Lock()
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
        print(f'[c1v3-vphi3] serving EX-221 ValueScorerV3 on GPU 1 at http://127.0.0.1:{actual_port}', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()


# ---------------------------------------------------------------------------------------------- 2. rescore-2ply (foul-play venv, CPU nice 19)

_vphi_endpoint = None


def _rescore_init(endpoint: str):
    global _vphi_endpoint
    from integration.laya_fp1 import tracker
    tracker.setup()
    _vphi_endpoint = endpoint


def _score_vphi3_remote(unique_raws: list[dict]) -> list[float]:
    if not unique_raws or not _vphi_endpoint:
        return []
    payload = json.dumps({'unique_raws': unique_raws}, separators=(',', ':')).encode()
    req = Request(_vphi_endpoint + '/score', data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())['probs']


def _rescore_job(job: dict) -> dict:
    from integration.laya_distill.data_distill import choice_map, restrict
    from integration.laya_fp1 import data_fp1 as DF
    from integration.laya_fp1 import tracker as T
    from integration.laya_regret.search import sample_states

    want = job['wanted']  # sid -> {'p': {...}, 'foe': {...}}
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
                    if sid in want and kind == 'turn_action':
                        info = want[sid]
                        if info.get('foe'):
                            view = tracker.view()
                            mapping = choice_map(view, [{'id': a} for a in info['p']], own)
                            mapping = {a: ch for a, ch in mapping.items() if ch}
                            if len(mapping) >= 2:
                                restrict(view, mapping)
                                samples, _ = sample_states(view, _search_seed(sid))
                                res2 = SMT.expand_and_score_2ply(
                                    samples, mapping, info['foe'], _score_vphi3_remote, laya_p=info['p'],
                                )
                                rows.append(dict(
                                    sample_id=sid,
                                    q_vphi3_1ply=res2['q_1ply'],
                                    q_vphi3_2ply=res2['q_2ply'],
                                    absorb_penalties=res2['absorb_penalties'],
                                    just_protected=bool(res2.get('just_protected', False)),
                                    ply1_states=res2['ply1_states'],
                                    ply2_states=res2['ply2_states'],
                                    seconds=res2['seconds'],
                                ))
                tracker.chose(record.get('label'))
            except Exception as exc:
                errors.append(dict(side=side, sample_id=sid, stage='decision', error='%s: %s' % (type(exc).__name__, exc),
                                   trace=traceback.format_exc(limit=2)[-400:]))
                break
    return dict(replay_id=job['replay_id'], rows=rows, skipped=None, errors=errors)


def rescore_2ply(workers: int = 32, endpoint: str = '') -> dict:
    from integration.laya_fp1.data_fp1 import jobs

    if os.environ.get('PYTHONHASHSEED') != '0':
        raise RuntimeError('run with PYTHONHASHSEED=0')
    staging = RUN / 'vphi3_2ply'
    staging.mkdir(parents=True, exist_ok=True)
    done = set()
    for p in staging.glob('done-*.txt'):
        done.update(p.read_text().split())

    want: dict[str, dict] = {}
    with open(EX218_RUN / 'infer-hard.jsonl') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if ':turn_action' in r['sample_id'] and len(r['p']) >= 2 and r.get('foe'):
                want[r['sample_id']] = dict(p=r['p'], foe=r['foe'])

    blim_sets = F.blim_eval_team_sets()
    all_jobs = jobs({sid: True for sid in want})
    todo = [
        dict(j, wanted={s: want[s] for s in j['wanted']}, blim_sets=blim_sets)
        for j in all_jobs if j['replay_id'] not in done
    ]
    print(f'[c1v3-rescore] {len(want)} turn_actions across {len(todo)} games ({len(done)} done), workers={workers}, vphi3={endpoint}', flush=True)
    if not todo:
        return dict(games=0, rows=0, errors=0)

    tag = '%d-%d' % (int(time.time()), os.getpid())
    started, n, nrows, nerr = time.time(), 0, 0, 0
    with open(staging / f'part-{tag}.jsonl', 'a') as out, \
            open(staging / f'errors-{tag}.jsonl', 'a') as err, \
            open(staging / f'done-{tag}.txt', 'a') as fin, \
            Pool(workers, initializer=_rescore_init, initargs=(endpoint,), maxtasksperchild=40) as pool:
        for res in pool.imap_unordered(_rescore_job, todo, chunksize=1):
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
                print(f'[c1v3-rescore] {n}/{len(todo)} games, {nrows} rows, {nerr} errs, {rate:.2f} g/s, eta {(len(todo)-n)/max(1e-9,rate)/60:.1f} min', flush=True)
    return dict(games=n, rows=nrows, errors=nerr)


# ---------------------------------------------------------------------------------------------- 3. build-targets (purified C-1)

def gold_way_c1_clean(
    p: dict[str, float],
    q_mcts50: dict[str, float] | None,
    q_vphi3: dict[str, float] | None,
    *,
    state: str = '',
    absorb_penalties: dict[str, float] | None = None,
    just_protected: bool = False,
    alpha_vphi: float = TEACHER_ALPHA_VPHI3,
    tau: float = TAU_TEACHER,
) -> tuple[dict[str, float] | None, list[str], dict[str, float]]:
    """Build purified KL-regularized teacher target from MCTS 50k + EX-221 V_phi v3 2-ply + recovery guardrails."""
    if not p:
        return None, [], {}
    pen = absorb_penalties or {}
    qm = {a: float(v) - float(pen.get(a, 0.0)) for a, v in (q_mcts50 or {}).items() if a in p and math.isfinite(v)}
    qv = {a: float(v) for a, v in (q_vphi3 or {}).items() if a in p and math.isfinite(v)}
    if not qm and not qv:
        return None, [], {}

    q_teacher: dict[str, float] = {}
    for a in set(qm) | set(qv):
        m_val = qm.get(a)
        v_val = qv.get(a)
        if m_val is not None and v_val is not None:
            q_teacher[a] = (1.0 - alpha_vphi) * m_val + alpha_vphi * v_val
        elif v_val is not None:
            q_teacher[a] = v_val
        elif m_val is not None:
            q_teacher[a] = m_val

    if len(q_teacher) < 2:
        return None, [], q_teacher

    hp_frac = WA2.parse_active_hp_frac(state)
    walled = WA.is_walled_state(state)

    # Mild anti-contamination safeguard: never let evaluate.rs inflate high-HP heal or consecutive Protect in q_teacher
    q_eff = dict(q_teacher)
    for a in list(q_eff):
        if just_protected and WA2.is_protect_action(a):
            q_eff[a] -= 0.04
        elif walled and WA2.is_protect_action(a):
            q_eff[a] -= 0.02

    ranked = sorted(sorted(p), key=lambda a: p[a], reverse=True)
    argmax = ranked[0]
    top_p = p[argmax]
    cands = [a for a in ranked if p[a] >= NEAR_CAND * top_p and a in q_eff][:MAX_CANDS]
    if len(cands) < 2:
        cands = [a for a in ranked if a in q_eff][:2]

    # Automatic rescue promotion WITH Way A v2 recovery/Protect guardrails!
    def _rescue_allowed(a: str) -> bool:
        if just_protected and WA2.is_protect_action(a):
            return False
        if walled and WA2.is_protect_action(a):
            return False
        if WA2.is_heal_action(a) and hp_frac is not None and hp_frac >= WA2.HIGH_HP_HEAL_BLOCK:
            return False
        return True

    best_q_act = max(sorted(q_eff), key=lambda a: (q_eff[a], p.get(a, 0.0)))
    ref_q = q_eff.get(argmax)
    gap_req = WALLED_RESCUE_GAP if walled else RESCUE_GAP
    if best_q_act not in cands and ref_q is not None and (q_eff[best_q_act] - ref_q) >= gap_req and _rescue_allowed(best_q_act):
        cands.append(best_q_act)
    if walled and qm and argmax in qm:
        best_m = max(sorted(qm), key=lambda a: (qm[a], p.get(a, 0.0)))
        if best_m not in cands and (qm[best_m] - qm[argmax]) >= WA.WALLED_MCTS_DELTA and _rescue_allowed(best_m):
            cands.append(best_m)

    if len(cands) < 2:
        return None, cands, q_teacher

    out = {k: float(v) for k, v in p.items()}
    mass = sum(out[a] for a in cands)
    if mass <= 0.0:
        return None, cands, q_teacher

    eff_tau = tau * 0.7 if walled else tau
    floor = 1e-3 if walled else SC.PRIOR_FLOOR
    log_w = {a: math.log(max(out[a], floor)) + float(q_eff[a]) / float(eff_tau) for a in cands}
    mx = max(log_w.values())
    unnorm = {a: math.exp(log_w[a] - mx) for a in cands}
    z = sum(unnorm.values())
    for a in cands:
        out[a] = mass * unnorm[a] / z
    tot = sum(out.values())
    if tot > 0.0:
        out = {k: v / tot for k, v in out.items()}
    return out, cands, {k: round(v, 6) for k, v in q_teacher.items()}


def audit_recovery_rates(jsonl_path: Path, meta_key: str = 'ex225') -> dict:
    """Measure HP-recovery & Protect teacher rates vs Human Pro by HP% bucket."""
    out = {}
    for cat_name, fn in (('heal', WA2.is_heal_action), ('protect', WA2.is_protect_action)):
        by_hp = defaultdict(Counter)
        with open(jsonl_path) as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                if ':turn_action' not in r.get('sample_id', ''):
                    continue
                crit = (r.get('questions') or {}).get('action', {}).get('criteria') or {}
                if not any(fn(a) for a in crit):
                    continue
                hp = WA2.parse_active_hp_frac(r.get('state', ''))
                bk = 'unk' if hp is None else ('>=90%' if hp >= 0.9 else ('70-89%' if hp >= 0.7 else ('40-69%' if hp >= 0.4 else '<40%')))
                g = (r.get('gold') or {}).get('action', {}).get('probabilities') or {}
                t_act = max(g, key=g.get) if g else None
                m = (r.get('meta') or {}).get(meta_key) or {}
                h_act = m.get('label')
                l_act = m.get('laya_argmax')
                for k in ('ALL', bk):
                    by_hp[k]['n'] += 1
                    if t_act and fn(t_act): by_hp[k]['teacher'] += 1
                    if h_act and fn(h_act): by_hp[k]['human'] += 1
                    if l_act and fn(l_act): by_hp[k]['laya'] += 1
        out[cat_name] = {
            k: dict(
                n=c['n'],
                human=round(c['human'] / max(1, c['n']), 4),
                laya=round(c['laya'] / max(1, c['n']), 4),
                teacher=round(c['teacher'] / max(1, c['n']), 4),
            )
            for k, c in by_hp.items()
        }
    return out


def build_targets() -> dict:
    """Assemble purified `datasets/generated/laya-v14w-c1v3/v1/` reusing EX-218 MCTS 50k + EX-221 V_phi v3 2-ply."""
    if (OUT / 'manifest.json').exists():
        print('[c1v3-targets] already built:', OUT / 'manifest.json', flush=True)
        return json.loads((OUT / 'manifest.json').read_text())

    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    # Symlink unchanged v14+walled_duel anchor & foe-anchor from EX-218 (zero disk duplication!)
    for rel in ('anchor', 'foe-anchor.jsonl'):
        dst = OUT / rel
        if not dst.exists():
            os.symlink(EX218_DATA / rel, dst)

    infer_map = {}
    with open(EX218_RUN / 'infer-hard.jsonl') as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                infer_map[r['sample_id']] = r

    mcts_map = {}
    for p in sorted((EX218_RUN / 'search50k').glob('part-*.jsonl')):
        with open(p) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    mcts_map[r['sample_id']] = r

    v3_map = {}
    for p in sorted((RUN / 'vphi3_2ply').glob('part-*.jsonl')):
        with open(p) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    v3_map[r['sample_id']] = r

    stats = Counter()
    for split, src_p, hard_dst, gen_dst in (
        ('train', EX218_DATA / 'v14w_train_base.jsonl', OUT / 'hard_train.jsonl', OUT / 'general_train.jsonl'),
        ('heldout', EX218_DATA / 'v14w_heldout_base.jsonl', OUT / 'hard_heldout.jsonl', OUT / 'heldout.jsonl'),
    ):
        with open(src_p) as fin, open(hard_dst, 'w') as fh, open(gen_dst, 'w') as fg:
            for line in fin:
                if not line.strip():
                    continue
                r = json.loads(line)
                sid = r['sample_id']
                m_rec = mcts_map.get(sid)
                i_rec = infer_map.get(sid)
                v_rec = v3_map.get(sid)
                upgraded = False
                if m_rec is not None and i_rec is not None:
                    q_v3 = v_rec.get('q_vphi3_2ply') if v_rec else None
                    abs_pen = (v_rec.get('absorb_penalties') if v_rec else None) or m_rec.get('absorb_penalties')
                    just_prot = bool(v_rec.get('just_protected', False)) if v_rec else False
                    g, cands, qt = gold_way_c1_clean(
                        i_rec['p'], m_rec.get('q_mcts50'), q_v3,
                        state=r['state'], absorb_penalties=abs_pen, just_protected=just_prot,
                    )
                    if g is not None:
                        laya_arg = max(i_rec['p'], key=i_rec['p'].get)
                        gold_arg = max(g, key=g.get)
                        r['gold'] = dict(action=dict(probabilities=g))
                        r.setdefault('meta', {})['ex225'] = dict(
                            candidates=cands, q_teacher=qt,
                            q_mcts50=m_rec.get('q_mcts50'),
                            q_vphi3_2ply=q_v3,
                            q_vphi3_1ply=(v_rec.get('q_vphi3_1ply') if v_rec else None),
                            laya_argmax=laya_arg, gold_argmax=gold_arg,
                            label=i_rec.get('label'),
                            walled=WA.is_walled_state(r['state']),
                            just_protected=just_prot,
                            absorb_penalties=abs_pen or {},
                        )
                        fh.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
                        stats[f'{split}_hard'] += 1
                        if gold_arg != laya_arg:
                            stats[f'{split}_hard_changed'] += 1
                        if q_v3:
                            stats[f'{split}_hard_with_vphi3_2ply'] += 1
                        if WA.is_walled_state(r['state']):
                            stats[f'{split}_hard_walled'] += 1
                            if gold_arg != laya_arg:
                                stats[f'{split}_hard_walled_changed'] += 1
                        upgraded = True
                if split == 'heldout' or not upgraded:
                    fg.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
                    stats[f'{split}_general'] += 1

    if stats['train_hard'] < 1000 or stats['heldout_hard'] < 100:
        raise RuntimeError(f'EX-225 build_targets got too few hard rows: {dict(stats)}')

    purity = audit_recovery_rates(OUT / 'hard_train.jsonl', meta_key='ex225')
    manifest = dict(
        experiment='EX-225',
        decision='D-224',
        way='C-1 Clean (v14+walled_duel + MCTS 50k + EX-221 V_phi v3 2-ply purified teacher)',
        alpha_vphi3=TEACHER_ALPHA_VPHI3,
        tau_teacher=TAU_TEACHER,
        stats=dict(stats),
        recovery_purity_audit=purity,
        seconds=round(time.time() - started, 1),
        at=time.time(),
    )
    atomic(OUT / 'manifest.json', manifest)
    print('[c1v3-targets] COMPLETE:', json.dumps(manifest, indent=1), flush=True)
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('vphi3-server', 'rescore-2ply', 'build-targets'))
    ap.add_argument('--workers', type=int, default=32)
    ap.add_argument('--ready-file', type=Path, default=RUN / 'vphi3.ready.json')
    ap.add_argument('--endpoint', default='')
    args = ap.parse_args()
    if args.cmd == 'vphi3-server':
        serve_vphi3(ready_file=args.ready_file)
    elif args.cmd == 'rescore-2ply':
        ep = args.endpoint
        if not ep and args.ready_file.exists():
            ep = json.loads(args.ready_file.read_text())['endpoint']
        rescore_2ply(workers=args.workers, endpoint=ep)
    elif args.cmd == 'build-targets':
        build_targets()
