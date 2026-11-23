"""EX-181 (EP-235): foul-play's search on one decision, split into sample preparation and per-sample MCTS.

`sample_states` is `fp.search.main.find_best_move` up to the MCTS calls (team-preview actives, `search_params`,
`prepare_battles`, `battle_to_poke_engine_state`), with the sampling RNG seeded per decision. `mcts` is
`get_result_from_mcts` with an exact iteration budget (`paths.ITERATIONS`) instead of a time budget. `aggregate`
is `select_move_from_mcts_results` (sample-chance-weighted visit share, the 75% consideration set) plus the
visit-weighted mean score of every root option.
"""
from __future__ import annotations

import copy
import hashlib
import random
import time

from integration.laya_regret import paths as P


def seed_of(slot, rqid, round_):
    digest = hashlib.sha256(('%d:%s:%d:%d' % (P.SEED, slot, rqid, round_)).encode()).hexdigest()
    return int(digest[:16], 16)


def in_repeat(slot, rqid):
    """About `REPEAT_FRACTION` of decisions, chosen by hash (independent of outcome or content)."""
    digest = hashlib.sha256(('repeat:%d:%s:%d' % (P.SEED, slot, rqid)).encode()).hexdigest()
    return int(digest[:16], 16) < int(P.REPEAT_FRACTION * 2 ** 64)


def sample_states(view, seed):
    """[(poke-engine state string, sample chance)] exactly as foul-play would sample them for this battle."""
    from fp.search.poke_engine_helpers import battle_to_poke_engine_state
    random.seed(seed)
    battle = copy.deepcopy(view)
    if battle.team_preview:
        battle.user.active = battle.user.reserve.pop(0)
        battle.opponent.active = battle.opponent.reserve.pop(0)
    num_battles, search_time = battle.mode.search_params(battle)
    battles = battle.mode.prepare_battles(battle, num_battles)
    return [(battle_to_poke_engine_state(b).to_string(), float(chance)) for b, chance in battles], int(search_time)


def mcts(job):
    """One sample: {id, total_visits, seconds, s1: [[choice, visits, total_score]], s2: [...]}."""
    from poke_engine import State, monte_carlo_tree_search
    started = time.monotonic()
    result = monte_carlo_tree_search(State.from_string(job['state']), job.get('ms', P.SEARCH_TIME_MS),
                                     iterations=job['iterations'], threads=1)
    return dict(id=job['id'], total_visits=int(result.total_visits), seconds=round(time.monotonic() - started, 3),
                s1=[[o.move_choice, int(o.visits), float(o.total_score)] for o in result.side_one],
                s2=[[o.move_choice, int(o.visits), float(o.total_score)] for o in result.side_two])


def aggregate(samples):
    """samples: [(chance, mcts result)] -> share (sums to 1), q (mean score), best, considered (foul-play's set)."""
    weighted, score, visits = {}, {}, {}
    total_chance = sum(chance for chance, _ in samples)
    for chance, result in samples:
        total = result['total_visits']
        if total <= 0:
            continue
        for choice, v, s in result['s1']:
            weighted[choice] = weighted.get(choice, 0.0) + chance * v / total
            score[choice] = score.get(choice, 0.0) + chance * s
            visits[choice] = visits.get(choice, 0.0) + chance * v
    if not weighted or total_chance <= 0:
        return None
    share = {c: w / total_chance for c, w in weighted.items()}
    q = {c: score[c] / visits[c] for c in visits if visits[c] > 0}
    best = max(share, key=lambda c: (share[c], c))
    considered = sorted(c for c in share if share[c] >= share[best] * P.CONSIDER)
    root = sum(share[c] * q[c] for c in q)
    return dict(share=share, q=q, best=best, considered=considered, root=root)
