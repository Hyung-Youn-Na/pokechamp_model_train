"""EP-247 / D-223 (EX-222): Controlled Offline A/B Benchmark — EX-216 V_phi v2 (1-ply) vs EX-221 V_phi v3 (1-ply & 2-ply) + Way A v2.

Two modes to keep `laya` (torch/GPU 0) and `foul-play` (poke_engine) cleanly decoupled:
1. `serve-scorers` (`laya` venv, physical GPU 0 ONLY): hosts BOTH `EX-216 ValueScorerV2` (`/score_v2`) and
   `EX-221 ValueScorerV3` (`/score_v3`) on localhost HTTP (< 300 MiB GPU 0).
2. `run-ab` (`foul-play` venv, `PYTHONHASHSEED=0`): replays exact `poke_engine` states from:
   - Testbed A: EX-220 diagnosed failure scenes (`073833` T20-26, `074335` T4-11, `072713` T22-36, `075028` T5-18),
   - Testbed B: Stratified 240 legal recovery/Protect turns from `EX-217` Blim 128 across HP buckets & opp setup turns,
   comparing `V_phi v2 (1-ply) + Way A v1` vs `V_phi v3 (1-ply) + Way A v2` vs `V_phi v3 (2-ply Top-K) + Way A v2`.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import glob
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import random
import re
import threading
import time
from urllib.request import Request, urlopen

from . import featurize as F
from . import featurize_v3 as F3
from . import search_2b as S2B
from . import search_2b_v2 as S2BV2
from . import search_core as SC
from . import search_multiturn as SMT
from . import way_a as WA1
from . import way_a_v2 as WA2

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
EX216_CKPT = SHARED / 'runs/model-training/EX-216/checkpoints/selected'
EX221_CKPT = SHARED / 'runs/model-training/EX-221/checkpoints/selected'
EX217_GAMES = SHARED / 'runs/model-training/EX-217/games'
EX220_GAMES = Path('/workspace/exports/laya-play/games')
OUT_DIR = SHARED / 'runs/model-training/EX-222'


def serve_scorers(ready_file: Path, v3_ckpt: Path = EX221_CKPT, port: int = 0):
    from integration.laya_imitation.resources import gpu
    from . import value_model_v2 as VM2
    from . import value_model_v3 as VM3

    with gpu(0, SC.GPU0_UUID) as (env, _):
        os.environ.update(env)
        s2 = VM2.ValueScorerV2(EX216_CKPT, device='cuda')
        s3 = VM3.ValueScorerV3(v3_ckpt, device='cuda')
        lock = threading.Lock()
        _ = s2.score_raw_batch([])
        _ = s3.score_raw_batch([])

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                if self.path == '/health':
                    body = json.dumps({'ok': True, 'v2': s2.cfg['arch'], 'v3': s3.cfg['arch']}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if self.path not in ('/score_v2', '/score_v3'):
                    self.send_response(404)
                    self.end_headers()
                    return
                n = int(self.headers.get('Content-Length', '0'))
                req = json.loads(self.rfile.read(n))
                raws = req.get('raws') or []
                with lock:
                    probs = (s2 if self.path == '/score_v2' else s3).score_raw_batch(raws) if raws else []
                body = json.dumps({'probs': probs}, separators=(',', ':')).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        actual_port = server.server_address[1]
        ready_file.parent.mkdir(parents=True, exist_ok=True)
        ready_file.write_text(json.dumps({'endpoint': f'http://127.0.0.1:{actual_port}', 'pid': os.getpid()}))
        print(f'[ex222-srv] hosting EX-216 v2 + EX-221 v3 on GPU 0 at http://127.0.0.1:{actual_port}', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()


def _http_scorer(endpoint: str, route: str):
    url = endpoint.rstrip('/') + route

    def _fn(raws: list[dict]) -> list[float]:
        if not raws:
            return []
        data = json.dumps({'raws': raws}, separators=(',', ':')).encode()
        req = Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())['probs']

    return _fn


def _as_dict(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, str) and x.strip().startswith('{'):
        try:
            return json.loads(x)
        except Exception:
            return {}
    return {}


def _top1(d: dict[str, float] | None) -> str | None:
    if not d:
        return None
    return max(sorted(d), key=lambda k: float(d[k]))


def _hp_bucket(hp: float | None) -> str:
    if hp is None:
        return 'unk'
    if hp >= 90.0:
        return '>=90%'
    if hp >= 70.0:
        return '70-89%'
    if hp >= 40.0:
        return '40-69%'
    return '<40%'


def _eval_decision_from_event(inp: dict, resp_body: dict, score_v2, score_v3, just_prot: bool = False) -> dict | None:
    from integration.laya_distill.data_distill import choice_map, restrict
    from integration.laya_fp1 import tracker as T
    from integration.laya_regret.search import sample_states
    from . import search_worker as SW

    bj = _as_dict(inp.get('body')) or _as_dict(inp.get('body_json'))
    fp1 = bj.get('fp1') if isinstance(bj.get('fp1'), dict) else None
    if not isinstance(fp1, dict):
        st_obj = _as_dict(bj.get('state'))
        fp1 = st_obj.get('fp1') if isinstance(st_obj, dict) else None
    if not isinstance(fp1, dict):
        return None
    snap = fp1.get('snapshot') or inp.get('snapshot') or {}
    if snap.get('decision_kind') != 'turn_action':
        return None

    search = _as_dict(resp_body.get('search'))
    p_laya = search.get('laya') or {}
    foe_q = search.get('foe') or {}
    q_mcts = search.get('q_mcts') or {}
    q_v2_logged = search.get('q_vphi') or {}
    if not p_laya or not foe_q or not q_mcts:
        return None

    # Reconstruct exact poke_engine samples via Tracker (identical to search_worker.py)
    raw_log = dict(log='\n'.join(fp1['lines']))
    tr = T.Tracker(raw_log, fp1['side'], fp1['own_sets'])
    tr.advance(len(fp1['lines']), snap, 'turn_action')
    view = tr.view()
    sid = '%s:%s:%d:turn_action' % (fp1['game'], fp1['side'], len(fp1['lines']))
    mapping = choice_map(view, [{'id': a} for a in p_laya.keys()], fp1['own_sets'])
    mapping = {a: ch for a, ch in mapping.items() if ch}
    if len(mapping) < 2:
        return None
    restrict(view, mapping)
    samples, _ = sample_states(view, SW.seed_of(sid))
    if not samples:
        return None

    # Active HP%
    own_team = snap.get('own_team') or []
    aslot = snap.get('own_active_slot')
    my_sp, my_hp = '?', None
    for m in own_team:
        if isinstance(m, dict) and (m.get('slot') == aslot or m.get('active')):
            my_sp = m.get('species') or m.get('name') or '?'
            my_hp = m.get('hp_percent')
            if my_hp is None and m.get('max_hp'):
                my_hp = 100.0 * m.get('hp', 0) / m['max_hp']
            break
    opp_team = snap.get('opponent_team') or []
    oslot = snap.get('opponent_active_slot')
    opp_sp, opp_hp = '?', None
    for m in opp_team:
        if isinstance(m, dict) and (m.get('slot') == oslot or m.get('active')):
            opp_sp = m.get('species') or m.get('name') or '?'
            opp_hp = m.get('hp_percent')
            if opp_hp is None and m.get('max_hp'):
                opp_hp = 100.0 * m.get('hp', 0) / m['max_hp']
            break

    # 1. Re-score 1-ply with EX-216 V_phi v2 (sanity parity with logged q_vphi)
    exp1 = S2BV2.expand_turn1_features_v2(samples, mapping, foe_q)
    raws1 = exp1.get('unique_raws') or []
    q_v2 = S2B.aggregate_value_2b(exp1, score_v2(raws1)) if raws1 else q_v2_logged

    # 2. Score 1-ply & 2-ply Top-K with EX-221 V_phi v3!
    res3 = SMT.expand_and_score_2ply(samples, mapping, foe_q, score_v3, laya_p=p_laya)
    q_v3_1 = res3['q_1ply']
    q_v3_2 = res3['q_2ply']
    abs_pen = res3['absorb_penalties']

    # Reconstruct minimal state flags (`walled`, `duel: lose`, `board:`) from logged way_a_meta
    wm_old = _as_dict(search.get('way_a_meta'))
    fake_lines = []
    if wm_old.get('alive_total') is not None:
        a1 = wm_old['alive_total'] // 2
        a2 = wm_old['alive_total'] - a1
        fake_lines.append(f'board: me {a1} alive 300% | opp {a2} alive 300%')
    if wm_old.get('walled'):
        fake_lines.append('duel: me 9+ hits (none) vs opp 3 hits (x), opp first -> lose')
    elif wm_old.get('duel_lose'):
        fake_lines.append('duel: me 4 hits (x) vs opp 2 hits (y), opp first -> lose')
    if my_hp is not None:
        fake_lines.append(f'ME {my_sp} [normal] {round(my_hp)}%')
    fake_state = '\n'.join(fake_lines)

    pick_v2_w1, _, _, meta_v2_w1 = WA1.choose_way_a(p_laya, q_mcts, q_v2, state=fake_state, absorb_penalties=abs_pen)
    pick_v3_1_w2, _, _, meta_v3_1_w2 = WA2.choose_way_a_v2(
        p_laya, q_mcts, q_v3_1, state=fake_state, absorb_penalties=abs_pen,
        active_hp_frac=(my_hp / 100.0 if my_hp is not None else None), just_protected=just_prot,
    )
    pick_v3_2_w2, _, _, meta_v3_2_w2 = WA2.choose_way_a_v2(
        p_laya, q_mcts, q_v3_2, state=fake_state, absorb_penalties=abs_pen,
        active_hp_frac=(my_hp / 100.0 if my_hp is not None else None), just_protected=just_prot,
    )

    return dict(
        my_sp=my_sp, my_hp=my_hp, opp_sp=opp_sp, opp_hp=opp_hp,
        walled=bool(wm_old.get('walled')), duel_lose=bool(wm_old.get('duel_lose')), just_prot=just_prot,
        actions=list(p_laya.keys()),
        laya_top=_top1(p_laya), mcts_top=_top1(q_mcts),
        v2_1ply_top=_top1(q_v2), v3_1ply_top=_top1(q_v3_1), v3_2ply_top=_top1(q_v3_2),
        pick_v2_w1=pick_v2_w1, reason_v2_w1=meta_v2_w1['reason'],
        pick_v3_1_w2=pick_v3_1_w2, reason_v3_1_w2=meta_v3_1_w2['reason'],
        pick_v3_2_w2=pick_v3_2_w2, reason_v3_2_w2=meta_v3_2_w2['reason'],
        q_mcts=q_mcts, q_v2=q_v2, q_v3_1=q_v3_1, q_v3_2=q_v3_2,
        ply1_states=res3['ply1_states'], ply2_states=res3['ply2_states'],
        sec_2ply=res3['seconds'],
    )


def _iter_game_turn_events(ev_path: Path, actor_filter: str | None = None):
    inputs, responses, selections = {}, {}, {}
    cur_turn = 0
    with open(ev_path) as f:
        for line in f:
            r = json.loads(line)
            t = r.get('type')
            if t == 'protocol':
                for pl in (r.get('protocol') or '').split('\n'):
                    if pl.startswith('|turn|'):
                        try:
                            cur_turn = int(pl.split('|')[2])
                        except Exception:
                            pass
            elif t == 'input':
                if actor_filter and r.get('actor') != actor_filter:
                    continue
                inputs[r.get('decision')] = (cur_turn, r)
            elif t == 'response':
                if actor_filter and r.get('actor') and r.get('actor') != actor_filter:
                    continue
                responses[r.get('decision')] = r
            elif t == 'selection':
                if actor_filter and r.get('actor') and r.get('actor') != actor_filter:
                    continue
                selections[r.get('decision')] = r

    prev_prot_sp = None
    prev_turn = -99
    for d, (turn, inp) in sorted(inputs.items(), key=lambda kv: kv[1][1].get('event_seq', 0)):
        resp = responses.get(d)
        if not resp:
            continue
        snap = inp.get('snapshot') or {}
        if snap.get('decision_kind') != 'turn_action':
            if snap.get('decision_kind') == 'forced_switch':
                prev_prot_sp = None
            continue
        aslot = snap.get('own_active_slot')
        sp = None
        for m in (snap.get('own_team') or []):
            if isinstance(m, dict) and (m.get('slot') == aslot or m.get('active')):
                sp = m.get('species') or m.get('name')
                break
        just_prot = (turn == prev_turn + 1 and prev_prot_sp == sp)
        body = _as_dict(resp.get('body'))
        sel = selections.get(d) or {}
        chosen = sel.get('choice') or _as_dict(body.get('search')).get('pick') or body.get('choice')
        yield turn, inp, body, just_prot
        prev_prot_sp = sp if (chosen and WA2.is_protect_action(chosen)) else None
        prev_turn = turn


def run_ab(endpoint: str, blim_limit: int = 240):
    from integration.laya_fp1 import tracker as T
    T.setup()
    score_v2 = _http_scorer(endpoint, '/score_v2')
    score_v3 = _http_scorer(endpoint, '/score_v3')
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Testbed A: EX-220 4 Diagnosed Failure Games ---
    scenes = [
        ('20261124-073833-nhy_test1629-laya-waya-001', {20, 21, 22, 23, 24, 25, 26}, 'Dragonite 96%/100% Roost vs 1% Garchomp & Gholdengo'),
        ('20261124-074335-nhy_test1629-laya-waya-001', {4, 5, 6, 7, 8, 9, 10, 11}, 'Dragonite 8x Roost vs Araquanid Lunge'),
        ('20261124-072713-nhy_test1629-laya-waya-001', {22, 23, 24, 25, 26, 28, 30, 32}, 'Gliscor 100% Protect loop vs +6 Corviknight'),
        ('20261124-075028-nhy_test1629-laya-waya-001', {5, 7, 8, 15, 17, 18}, 'Dragonite/Gliscor vs Moltres-Galar setup'),
    ]
    ex220_audit = []
    print('=== TESTBED A: EX-220 DIAGNOSED FAILURE SCENES ===', flush=True)
    for gdir, tset, desc in scenes:
        evp = EX220_GAMES / gdir / 'events.jsonl'
        if not evp.exists():
            continue
        print(f'\n-- {gdir[:15]} ({desc}) --', flush=True)
        for turn, inp, body, just_prot in _iter_game_turn_events(evp):
            if turn not in tset:
                continue
            res = _eval_decision_from_event(inp, body, score_v2, score_v3, just_prot=just_prot)
            if not res:
                continue
            ex220_audit.append(dict(game=gdir[:15], desc=desc, turn=turn, **{k: v for k, v in res.items() if not k.startswith('q_')}))
            print(
                f'  T{turn:2d} {res["my_sp"]}({res["my_hp"]:.0f}%) vs {res["opp_sp"]}({res["opp_hp"]:.0f}%) '
                f'| L={res["laya_top"]} | V2_1p={res["v2_1ply_top"]} -> W1={res["pick_v2_w1"]}[{res["reason_v2_w1"]}] '
                f'| V3_1p={res["v3_1ply_top"]} -> W2={res["pick_v3_1_w2"]}[{res["reason_v3_1_w2"]}] '
                f'| V3_2p={res["v3_2ply_top"]} -> W2={res["pick_v3_2_w2"]}[{res["reason_v3_2_w2"]}] ({res["sec_2ply"]*1000:.0f}ms)',
                flush=True,
            )

    # --- Testbed B: Stratified EX-217 Blim Turns with Legal Recovery or Protect ---
    print(f'\n=== TESTBED B: STRATIFIED EX-217 BLIM TURNS (target={blim_limit}) ===', flush=True)
    rng = random.Random(20261222)
    cands_heal = defaultdict(list)
    cands_prot = []
    for gd in sorted(EX217_GAMES.glob('fp-*')):
        evp = gd / 'events.jsonl'
        reqp = gd / 'request.json'
        if not evp.exists() or not reqp.exists():
            continue
        req = json.loads(reqp.read_text())
        names = req.get('names') or {}
        side = 'p1' if str(names.get('p1', '')).startswith('lay') else 'p2'
        for turn, inp, body, just_prot in _iter_game_turn_events(evp, actor_filter=side):
            p_laya = _as_dict(_as_dict(body.get('search')).get('laya'))
            if not p_laya:
                continue
            has_h = any(WA2.is_heal_action(a) for a in p_laya)
            has_p = any(WA2.is_protect_action(a) for a in p_laya)
            if not (has_h or has_p):
                continue
            snap = inp.get('snapshot') or {}
            aslot = snap.get('own_active_slot')
            hp = None
            for m in (snap.get('own_team') or []):
                if isinstance(m, dict) and (m.get('slot') == aslot or m.get('active')):
                    hp = m.get('hp_percent')
                    break
            b = _hp_bucket(hp)
            if has_h:
                cands_heal[b].append((gd.name, turn, inp, body, just_prot))
            if has_p:
                cands_prot.append((gd.name, turn, inp, body, just_prot))

    selected = []
    per_b = max(1, (blim_limit - 40) // 4)
    for b in ('>=90%', '70-89%', '40-69%', '<40%'):
        pool = cands_heal[b]
        rng.shuffle(pool)
        selected.extend(('heal', b, x) for x in pool[:per_b])
    rng.shuffle(cands_prot)
    selected.extend(('protect', _hp_bucket(None), x) for x in cands_prot[:40])

    stats = {
        'heal': defaultdict(lambda: Counter()),
        'protect': defaultdict(lambda: Counter()),
    }
    latencies = []
    for idx, (cat, b_tag, (gname, turn, inp, body, just_prot)) in enumerate(selected, 1):
        res = _eval_decision_from_event(inp, body, score_v2, score_v3, just_prot=just_prot)
        if not res:
            continue
        latencies.append(res['sec_2ply'])
        b = _hp_bucket(res['my_hp'])
        fn = WA2.is_heal_action if cat == 'heal' else WA2.is_protect_action
        for bucket_key in ('ALL', b):
            c = stats[cat][bucket_key]
            c['n'] += 1
            if fn(res['laya_top']): c['laya'] += 1
            if fn(res['mcts_top']): c['mcts'] += 1
            if fn(res['v2_1ply_top']): c['v2_1ply'] += 1
            if fn(res['v3_1ply_top']): c['v3_1ply'] += 1
            if fn(res['v3_2ply_top']): c['v3_2ply'] += 1
            if fn(res['pick_v2_w1']): c['final_v2_w1'] += 1
            if fn(res['pick_v3_1_w2']): c['final_v3_1_w2'] += 1
            if fn(res['pick_v3_2_w2']): c['final_v3_2_w2'] += 1
            # Veto into / away
            l_is = fn(res['laya_top'])
            if (not l_is) and fn(res['pick_v2_w1']): c['v2_w1_into'] += 1
            if l_is and (not fn(res['pick_v2_w1'])): c['v2_w1_away'] += 1
            if (not l_is) and fn(res['pick_v3_2_w2']): c['v3_2_w2_into'] += 1
            if l_is and (not fn(res['pick_v3_2_w2'])): c['v3_2_w2_away'] += 1
        if idx % 60 == 0 or idx == len(selected):
            print(f'  processed {idx}/{len(selected)} (mean 2-ply {1000*sum(latencies)/len(latencies):.1f}ms)', flush=True)

    summary = dict(
        experiment='EX-222',
        decision='D-223',
        n_evaluated=len(latencies),
        latency_2ply_ms=dict(
            mean=round(1000 * sum(latencies) / max(1, len(latencies)), 1),
            p50=round(1000 * sorted(latencies)[len(latencies) // 2], 1) if latencies else None,
            p95=round(1000 * sorted(latencies)[int(0.95 * len(latencies))], 1) if latencies else None,
        ),
        blim_ab={cat: {bk: dict(c) for bk, c in mp.items()} for cat, mp in stats.items()},
        ex220_audit_count=len(ex220_audit),
    )
    (OUT_DIR / 'ab_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    (OUT_DIR / 'ex220_replay_audit.json').write_text(json.dumps(ex220_audit, ensure_ascii=False, indent=1))

    print('\n=== EX-222 BLIM A/B SUMMARY ===')
    for cat in ('heal', 'protect'):
        print(f'\n[{cat.upper()}]')
        for bk in ('ALL', '>=90%', '70-89%', '40-69%', '<40%'):
            c = stats[cat].get(bk)
            if not c or not c['n']:
                continue
            n = c['n']
            print(
                f'  {bk:6s} (n={n:3d}): Laya={100*c["laya"]/n:5.1f}% | MCTS={100*c["mcts"]/n:5.1f}% '
                f'| V2_1p={100*c["v2_1ply"]/n:5.1f}% -> V3_1p={100*c["v3_1ply"]/n:5.1f}% -> V3_2p={100*c["v3_2ply"]/n:5.1f}% '
                f'| Final W1={100*c["final_v2_w1"]/n:5.1f}% -> W2+V3_2p={100*c["final_v3_2_w2"]/n:5.1f}% '
                f'(veto into/away: W1={c["v2_w1_into"]}/{c["v2_w1_away"]} -> W2={c["v3_2_w2_into"]}/{c["v3_2_w2_away"]})'
            )
    print('\n2-ply latency (ms):', summary['latency_2ply_ms'])
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('serve-scorers', 'run-ab'))
    ap.add_argument('--ready-file', type=Path, default=OUT_DIR / 'scorers.ready.json')
    ap.add_argument('--v3-ckpt', type=Path, default=EX221_CKPT)
    ap.add_argument('--endpoint')
    ap.add_argument('--blim-limit', type=int, default=240)
    args = ap.parse_args()
    if args.cmd == 'serve-scorers':
        serve_scorers(args.ready_file, args.v3_ckpt)
    else:
        run_ab(args.endpoint, args.blim_limit)
