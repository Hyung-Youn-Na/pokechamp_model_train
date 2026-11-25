"""EP-245 / D-221 (EX-217): Way A — Laya-Main Consensus Blunder Veto + Walled-Duel Renderer Fix + MCTS 50k.

Architecture (Laya = Primary Decision Maker; MCTS 50k = Tactical Verifier; V_phi v2 = Consensus Auditor):
1. `install_walled_duel()`: non-invasively wraps `integration.laya_v10.strategy.duel` (after `render_v13.install()`)
   so when ALL of our damaging moves fail (`shown_fails` / `0 dmg`, e.g. `Dragonite` vs `Air Balloon Gholdengo`),
   instead of returning `None` (suppressing `duel: ... -> lose`!), it returns an in-distribution losing duel:
   `duel: me 9+ hits (none) vs opp <N> hits (<opp_move>), <side> first -> lose`.
2. `choose_way_a(...)`:
   - Respects Laya's 1st choice `a_laya = argmax(p)` by default (~85-92% of turns).
   - Overrides ONLY when MCTS 50k and Matchup-Aware V_phi v2 reach consensus on a clear blunder (or in high-leverage
     regimes: `walled`, `duel: lose`, endgame `<= 5` alive, severe `>= 0.10` blunder, or `forced_switch`).
   - Prevents single-module bias (e.g. MCTS `evaluate.rs` hallucinating a setup while V_phi v2 sees a 1-turn disaster).
"""
from __future__ import annotations

import math
import re

from . import search_2b_v2 as S2BV2
from . import search_core as SC

VERSION_WAY_A = 'laya-way-a-v1'
MCTS_ITERATIONS_WAY_A = 50000

# Consensus Blunder-Veto Thresholds
STD_MCTS_DELTA = 0.050         # Standard turn: MCTS 50k must see >= +5% winrate gain over Laya argmax
STD_VPHI_FLOOR = -0.015        # V_phi v2 must agree or not object (> -1.5%)
STD_CONSENSUS_MIN = 0.020      # Combined (0.5*dm + 0.5*dv + prior_tie) minimum margin

SEVERE_MCTS_DELTA = 0.100      # Severe tactical blunder (e.g. Kingambit 3v1, Taunt+WaterAbsorb -0.15)
SEVERE_VPHI_FLOOR = -0.030

ENDGAME_ALIVE_MAX = 5          # Total alive Pokemon across both sides (e.g. 3v2, 3v1, 2v2)
ENDGAME_MCTS_DELTA = 0.040
ENDGAME_VPHI_FLOOR = -0.020

WALLED_MCTS_DELTA = 0.010      # Zero damaging moves hit active opponent (e.g. Air Balloon Gholdengo)
WALLED_VPHI_FLOOR = -0.030

LOSE_MCTS_DELTA = 0.035        # Unfavorable duel (`duel: ... -> lose`)
LOSE_VPHI_FLOOR = -0.025
LOSE_VPHI_LEAD_DELTA = 0.045   # Or V_phi v2 flags clear losing trade while MCTS doesn't object
LOSE_MCTS_FLOOR = -0.015

VPHI_ONLY_DELTA = 0.060        # Strong 1-turn blunder caught by V_phi v2 (e.g. Court Change suicide)
VPHI_ONLY_MCTS_FLOOR = -0.010

FORCED_MCTS_DELTA = 0.040      # forced_switch (no V_phi): override only on clear MCTS 50k winrate gain

_BOARD_ALIVE_RE = re.compile(r'^board:\s*me\s+(\d+)\s+alive\b.*\|\s*opp\s+(\d+)\s+alive\b')
_installed_walled = False
_orig_duel = None


def install_walled_duel() -> None:
    """Non-invasively wrap `strategy.duel` so 0-dmg/all-failing matchups emit `duel: me 9+ hits (none) ... -> lose`."""
    global _installed_walled, _orig_duel
    if _installed_walled:
        return
    from integration.laya_v10 import strategy

    _orig_duel = strategy.duel

    def _duel_with_walled(view, facts, shown_fails, likely, first):
        res = _orig_duel(view, facts, shown_fails, likely, first)
        if res is not None:
            return res
        if likely is None:
            return None
        own = {m['slot']: m for m in view['own_team']}
        opp = {m['slot']: m for m in view['opponent_team']}
        me = own.get(view.get('own_active_slot'))
        foe = opp.get(view.get('opponent_active_slot'))
        if me is None or foe is None:
            return None
        theirs = strategy._hits(strategy._hp(me), likely['min'])
        if theirs is None:
            return None
        # Confirm we had at least one normal attacking move candidate in `facts['damage']` that failed or dealt 0
        has_any_normal_attack = any(
            aid.startswith('move:') and aid.endswith(':normal')
            for aid in (facts.get('damage') or {})
        )
        if not has_any_normal_attack:
            return None
        if first is not None:
            me_first = first >= 0.5
        else:
            order = (facts.get('speed') or {}).get('order') or ''
            me_first = 'first' in order and 'second' not in order
        return dict(
            me_hits=99,
            me_move='none',
            opp_hits=theirs,
            opp_move=likely['move'],
            me_first=me_first,
            result='lose',
        )

    strategy.duel = _duel_with_walled
    _installed_walled = True


def is_walled_state(state: str) -> bool:
    for line in state.split('\n'):
        if line.startswith('duel: me 9+ hits (none) ') and line.rstrip().endswith('-> lose'):
            return True
    return False


def total_alive_from_state(state: str) -> int | None:
    for line in state.split('\n'):
        m = _BOARD_ALIVE_RE.match(line)
        if m:
            return int(m.group(1)) + int(m.group(2))
    return None


def choose_way_a(
    p: dict[str, float],
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    *,
    state: str = '',
    decision_kind: str | None = None,
    absorb_penalties: dict[str, float] | None = None,
) -> tuple[str, dict[str, float], float, dict]:
    """Way A: Laya-Main Consensus Blunder Veto.

    Returns `(pick, scores, delta, meta)` where `scores[a]` is the consensus advantage over `a_laya` (0.0 for `a_laya`),
    `delta = scores[pick]` (0.0 if Laya's 1st choice is preserved), and `meta['reason']` logs why any veto fired.
    """
    if not p:
        raise ValueError('empty action distribution p')
    a_laya = max(sorted(p), key=lambda a: p[a])
    pen = absorb_penalties or {}
    duel_lose = S2BV2.is_duel_lose(state)
    walled = is_walled_state(state)
    alive_tot = total_alive_from_state(state)
    endgame = alive_tot is not None and alive_tot <= ENDGAME_ALIVE_MAX

    base_meta = dict(
        mode='way_a',
        duel_lose=duel_lose,
        walled=walled,
        alive_total=alive_tot,
        endgame=endgame,
        absorb_penalties=pen,
        reason='keep_laya',
    )

    qm_adj = None
    if q_mcts:
        qm_adj = {a: float(v) - float(pen.get(a, 0.0)) for a, v in q_mcts.items() if a in p and math.isfinite(v)}
    qv = None
    if q_vphi:
        qv = {a: float(v) for a, v in q_vphi.items() if a in p and math.isfinite(v)}

    if not qm_adj and not qv:
        return a_laya, {}, 0.0, base_meta

    # Case 1: forced_switch or V_phi unavailable -> conservative MCTS-only blunder veto
    if not qv:
        assert qm_adj is not None
        if a_laya not in qm_adj:
            return a_laya, {}, 0.0, base_meta
        q0 = qm_adj[a_laya]
        p0 = max(float(p[a_laya]), 1e-4)
        scores = {}
        eligible = []
        thresh = FORCED_MCTS_DELTA if decision_kind == 'forced_switch' else SEVERE_MCTS_DELTA
        for a, q in qm_adj.items():
            dm = q - q0
            pr = 0.015 * math.log(max(float(p[a]), 1e-4) / p0)
            sc = dm + pr
            scores[a] = sc
            if a != a_laya and dm >= thresh and sc >= thresh * 0.6:
                eligible.append((sc, a))
        if eligible:
            eligible.sort(key=lambda x: (-x[0], x[1]))
            best_sc, best_a = eligible[0]
            base_meta['reason'] = 'forced_mcts_veto' if decision_kind == 'forced_switch' else 'mcts_only_severe_veto'
            return best_a, scores, best_sc, base_meta
        return a_laya, scores, 0.0, base_meta

    # Case 2: MCTS unavailable but V_phi available -> strong V_phi-only blunder veto
    if not qm_adj:
        if a_laya not in qv:
            return a_laya, {}, 0.0, base_meta
        v0 = qv[a_laya]
        scores = {a: v - v0 for a, v in qv.items()}
        cands = [(sc, a) for a, sc in scores.items() if a != a_laya and sc >= VPHI_ONLY_DELTA]
        if cands:
            cands.sort(key=lambda x: (-x[0], x[1]))
            base_meta['reason'] = 'vphi_only_veto'
            return cands[0][1], scores, cands[0][0], base_meta
        return a_laya, scores, 0.0, base_meta

    # Case 3: Full Way A — BOTH MCTS 50k and Matchup-Aware V_phi v2 available
    if a_laya not in qm_adj or a_laya not in qv:
        return a_laya, {}, 0.0, base_meta

    q0 = qm_adj[a_laya]
    v0 = qv[a_laya]
    p0 = max(float(p[a_laya]), 1e-4)

    common = [a for a in p if a in qm_adj and a in qv]
    scores: dict[str, float] = {}
    eligible: list[tuple[float, str, str]] = []

    for a in common:
        dm = qm_adj[a] - q0
        dv = qv[a] - v0
        pr_ratio = math.log(max(float(p[a]), 1e-4) / p0)  # <= 0 for a != a_laya
        # Consensus advantage score (0.0 for a_laya)
        c_score = 0.55 * dm + 0.45 * dv + 0.008 * pr_ratio
        scores[a] = c_score
        if a == a_laya:
            continue

        reason = None
        if dm >= SEVERE_MCTS_DELTA and dv >= SEVERE_VPHI_FLOOR:
            reason = 'severe_mcts_veto'
        elif walled and dm >= WALLED_MCTS_DELTA and dv >= WALLED_VPHI_FLOOR:
            reason = 'walled_veto'
        elif endgame and dm >= ENDGAME_MCTS_DELTA and dv >= ENDGAME_VPHI_FLOOR:
            reason = 'endgame_veto'
        elif duel_lose and dm >= LOSE_MCTS_DELTA and dv >= LOSE_VPHI_FLOOR:
            reason = 'duel_lose_mcts_veto'
        elif duel_lose and dv >= LOSE_VPHI_LEAD_DELTA and dm >= LOSE_MCTS_FLOOR:
            reason = 'duel_lose_vphi_veto'
        elif dv >= VPHI_ONLY_DELTA and dm >= VPHI_ONLY_MCTS_FLOOR:
            reason = 'vphi_blunder_veto'
        elif dm >= STD_MCTS_DELTA and dv >= STD_VPHI_FLOOR and (0.5 * dm + 0.5 * dv + 0.012 * pr_ratio) >= STD_CONSENSUS_MIN:
            reason = 'consensus_veto'

        if reason is not None:
            eligible.append((c_score, a, reason))

    if eligible:
        eligible.sort(key=lambda x: (-x[0], x[1]))
        best_sc, best_a, reason = eligible[0]
        base_meta['reason'] = reason
        base_meta['dm'] = round(qm_adj[best_a] - q0, 5)
        base_meta['dv'] = round(qv[best_a] - v0, 5)
        return best_a, scores, best_sc, base_meta

    return a_laya, scores, 0.0, base_meta
