"""EP-243 / D-219 (2-A): Multi-turn MCTS search worker (foul-play venv, line-delimited JSON on stdin/stdout).

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_search.search_worker

Keeps an LRU-bounded map of `laya_fp1.tracker.Tracker` instances (one per active game), feeds every decision
(`lead`, `turn_action`, `forced_switch`) identically to `laya_foe.read_worker`, restricts legal moves via
`laya_distill.data_distill.{choice_map,restrict}` so unmapped share is 0, samples opponent sets with
`laya_regret.search.sample_states`, and computes multi-turn Rust MCTS root Q via `search_core.search_mcts_samples`.

Covers BOTH `turn_action` AND `forced_switch` whenever `len(action_ids) >= 2`.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import sys
import time
import traceback

from integration.laya_distill.data_distill import choice_map, restrict
from integration.laya_fp1 import tracker as T
from integration.laya_regret.search import sample_states

from . import search_core as SC

MAX_OPEN_GAMES = 64


def seed_of(sample_id: str) -> int:
    return int(hashlib.sha256(('ex206:' + sample_id).encode()).hexdigest()[:16], 16)


def main():
    T.setup()
    games: OrderedDict[str, T.Tracker] = OrderedDict()
    ply1_cache: dict[str, list[object]] = {}
    sys.stdout.write(json.dumps(dict(status='ready', version=SC.VERSION)) + '\n')
    sys.stdout.flush()

    for line in sys.stdin:
        started = time.monotonic()
        try:
            req = json.loads(line)
            op = req.get('op', 'search')
            if op == 'close':
                gid = req['game']
                games.pop(gid, None)
                ply1_cache.pop(gid, None)
                out = dict(closed=gid)
            elif op == 'expand_2ply':
                from . import search_multiturn as SMT
                gid = req['game']
                s1_states = ply1_cache.get(gid) or []
                s1_indices = [int(i) for i in (req.get('s1_indices') or [])]
                out = SMT.expand_turn2_from_states(s1_states, s1_indices)
            else:
                gid = req['game']
                game = games.get(gid)
                raw = dict(log='\n'.join(req['lines']))
                if game is None:
                    game = T.Tracker(raw, req['side'], req['own_sets'])
                    games[gid] = game
                    while len(games) > MAX_OPEN_GAMES:
                        old_g, _ = games.popitem(last=False)
                        ply1_cache.pop(old_g, None)
                else:
                    games.move_to_end(gid)
                    game.lines = T.lines_of(raw)
                    game.chose(req.get('previous'))

                kind = req['decision_kind']
                if kind == 'lead':
                    game.lead_view()
                    out = dict(q_mcts=None, v_mcts=None, root_q=None, samples=0, used_samples=0, errors=0, choices={})
                else:
                    game.advance(len(game.lines), req['snapshot'], kind)
                    view = game.view()
                    action_ids = list(req.get('action_ids') or [])
                    if kind in ('turn_action', 'forced_switch') and len(action_ids) >= 2:
                        mapping = choice_map(view, [{'id': a} for a in action_ids], req['own_sets'])
                        mapping = {a: ch for a, ch in mapping.items() if ch}
                        if len(mapping) >= 2:
                            restrict(view, mapping)
                            samples, _ = sample_states(view, seed_of(req['sample_id']))
                            iters = int(req.get('iterations') or SC.MCTS_ITERATIONS)
                            out = SC.search_mcts_samples(samples, mapping, iterations=iters)
                            out['choices'] = mapping
                            if req.get('expand_2b') and kind == 'turn_action' and req.get('foe'):
                                if req.get('v3'):
                                    from . import search_multiturn as SMT
                                    exp1, s1_states, _ = SMT.expand_turn1_v3_states(samples, mapping, req['foe'])
                                    out['expand_2b'] = exp1
                                    if req.get('cache_2ply'):
                                        ply1_cache[gid] = s1_states
                                elif req.get('v2'):
                                    from . import search_2b_v2 as S2BV2
                                    out['expand_2b'] = S2BV2.expand_turn1_features_v2(samples, mapping, req['foe'])
                                else:
                                    from . import search_2b as S2B
                                    out['expand_2b'] = S2B.expand_turn1_features(samples, mapping, req['foe'])
                        else:
                            out = dict(q_mcts=None, v_mcts=None, root_q=None, samples=0, used_samples=0, errors=0,
                                       choices=mapping)
                    else:
                        out = dict(q_mcts=None, v_mcts=None, root_q=None, samples=0, used_samples=0, errors=0,
                                   choices={})
            out['worker_seconds'] = round(time.monotonic() - started, 4)
        except BaseException as exc:
            out = dict(error='%s: %s' % (type(exc).__name__, exc), trace=traceback.format_exc(limit=4)[-800:])
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
