"""EP-247 / D-223 (EX-222): Way A v2 — Future-Aware Consensus Blunder Veto with Recovery/Protect Loop Guardrails.

Non-invasive successor to `way_a.py` fixing all 3 rule defects diagnosed in EX-220 / EX-217:
1. `walled_veto` NEVER overrides into `Protect`-class moves or high-HP (>= 70%) recovery moves
   (fixes EX-220 `072713` T22-T23 where `walled_veto` forced `Gliscor` into a 15-turn `Protect` loop).
2. Consecutive `Protect` Guard: when `just_protected=True` (66.7% fail risk), NEVER veto into `Protect`, and
   if Laya picks consecutive `Protect`, allow escape when MCTS + V_phi both prefer a non-Protect alternative.
3. High-HP Recovery Guard: `vphi_blunder_veto` / `duel_lose_vphi_veto` NEVER override a non-heal Laya choice
   into a recovery move when `active_hp_frac >= 0.85` (fixes EX-220 `073833` T23 96% HP `Roost` over `ESpeed` KO).
4. Unanimous MCTS + V_phi Loop Escape: when BOTH `MCTS` (`dm >= 0.035`) AND `V_phi` (`dv >= 0.020`) agree on
   the same non-Laya alternative, fire `unanimous_veto` without letting `pr_ratio` suppress the escape
   (fixes EX-220 `074335` T7-T11 `Dragonite` 8-turn `Roost` loop vs `Araquanid Lunge`).
"""
from __future__ import annotations

import math
import re

from . import featurize as F
from . import featurize_v3 as F3
from . import matchup_eval as ME
from . import search_2b_v2 as S2BV2
from . import way_a as WA

VERSION_WAY_A_V2 = 'laya-way-a-v2'

HIGH_HP_HEAL_BLOCK = 0.85       # Block 1-ply/V_phi-led veto INTO heal when active HP >= 85%
WALLED_HEAL_BLOCK = 0.70        # Block walled_veto INTO heal when active HP >= 70%
UNANIMOUS_MCTS_DELTA = 0.035    # Both MCTS and V_phi clearly agree on same alternative -> escape Laya loops
UNANIMOUS_VPHI_DELTA = 0.020
CONSEC_PROT_MCTS_DELTA = 0.015  # Escape consecutive Protect if MCTS prefers another move and V_phi agrees
CONSEC_PROT_VPHI_FLOOR = -0.005

# Bad-matchup high-HP stay-in protection (diagnosed in EX-224 Ting-Lu vs Ogerpon T2, Samurott vs Ogerpon T2):
# When duel_lose=True and our active mon is healthy (HP >= 70%) and Laya wants to stay in, allow switch veto if
# BOTH MCTS and V_phi v3 agree on switching, OR V_phi v3 sees a large switch gain without strong MCTS objection.
LOSE_SWITCH_HIGH_HP = 0.70
LOSE_SWITCH_MCTS_DELTA = 0.010
LOSE_SWITCH_VPHI_DELTA = 0.025
LOSE_SWITCH_VPHI_STRONG = 0.065
LOSE_SWITCH_MCTS_FLOOR = -0.025

# Plausible unrevealed threat inclusion in strategy.likely_threat (fixes "seen rapidspin/knockoff -> opp 6 hits win" bug)
PLAUSIBLE_THREAT_MIN_P = 0.25
PLAUSIBLE_THREAT_MAX_HIDDEN = 4
CHOICE_ITEMS = frozenset(('choiceband', 'choicespecs', 'choicescarf'))

_ME_HP_RE = re.compile(r'^ME\s+\S+\s+\[[^\]]*\]\s+(\d+(?:\.\d+)?)%', re.M)
_installed_plausible_threat = False
_orig_likely_threat = None


def install_plausible_threat_duel() -> None:
    """Non-invasively wrap `strategy.likely_threat` so revealed utility moves (`Rapid Spin`, `Knock Off`, `U-turn`)
    do NOT hide unrevealed high-usage STAB/coverage threats (`Power Whip`, `Ice Spinner`, etc.) when the foe still
    has unrevealed move slots (< 4 revealed moves and not Choice-locked)."""
    global _installed_plausible_threat, _orig_likely_threat
    WA.install_walled_duel()
    if _installed_plausible_threat:
        return
    from integration.laya_imitation import features, features_v7
    from integration.laya_v10 import strategy

    _orig_likely_threat = strategy.likely_threat

    def _likely_threat_plausible(view, foe, me, calc):
        revealed_all = [m['id'] for m in foe.get('moves') or []]
        revealed = [m for m in revealed_all if strategy._damaging(m)]
        u = strategy._usage(foe)
        hidden = [(m, p) for m, p in features_v7._moves(foe, u) if strategy._damaging(m)] if u else []

        # Respect Choice-lock if the foe is explicitly locked into a revealed move
        locked = foe.get('locked_move')
        if locked and strategy._damaging(locked):
            candidates = [(locked, 1.0)]
        else:
            candidates = [(m, 1.0) for m in revealed]
            # Include plausible unrevealed damaging moves whenever foe still has unknown move slots (< 4 revealed)
            if len(revealed_all) < 4 and hidden:
                seen_set = set(revealed_all)
                plausible = [
                    (m, p) for m, p in hidden
                    if m not in seen_set and p >= PLAUSIBLE_THREAT_MIN_P
                ][:PLAUSIBLE_THREAT_MAX_HIDDEN]
                if plausible:
                    candidates.extend(plausible)
                elif not candidates:
                    candidates = hidden[:1]
            elif not candidates and hidden:
                candidates = hidden[:1]

        if not candidates:
            return None
        attacker = features._opp_spec(foe)[0]
        side = dict(
            weather=view['weather'],
            field=view['field'],
            attacker_side=view['opponent_side_conditions'],
            defender_side=view['own_side_conditions'],
        )
        defender = features._own_spec(me, active=True)
        me_hp = strategy._hp(me)
        moves_dex = strategy.dex_v2.load()['moves']
        results = strategy._run(calc, [dict(attacker=attacker, defender=defender, move=m, **side) for m, _ in candidates])
        ok = []
        for (m, p), r in zip(candidates, results, strict=True):
            if 'error' in r:
                continue
            hits = strategy._hits(me_hp, r['min'])
            # Fewest hits to KO first (None -> inf), then higher move priority (e.g. Thunderclap 2HKO > Draco 2HKO), then max/min dmg
            hits_key = -hits if hits is not None else -999
            prio = moves_dex.get(m, {}).get('priority', 0)
            ok.append((hits_key, prio, r['max'], r['min'], m, p))
        if not ok:
            return None
        _, _, mx, mn, move, p = max(ok)
        return dict(move=move, p=p, min=mn, max=mx)

    strategy.likely_threat = _likely_threat_plausible
    _installed_plausible_threat = True


def _action_base_move(aid: str) -> str:
    if not aid or not aid.startswith('move:'):
        return ''
    parts = aid.split(':')
    return F.norm(parts[1]) if len(parts) >= 2 else ''


def is_heal_action(aid: str) -> bool:
    return _action_base_move(aid) in F3.HEAL_MOVES


def is_protect_action(aid: str) -> bool:
    return _action_base_move(aid) in F3.PROTECT_MOVES


def parse_active_hp_frac(state: str) -> float | None:
    m = _ME_HP_RE.search(state or '')
    if m:
        return max(0.0, min(1.0, float(m.group(1)) / 100.0))
    return None


def choose_way_a_v2(
    p: dict[str, float],
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    *,
    state: str = '',
    decision_kind: str | None = None,
    absorb_penalties: dict[str, float] | None = None,
    active_hp_frac: float | None = None,
    just_protected: bool = False,
) -> tuple[str, dict[str, float], float, dict]:
    """Way A v2: Laya-Main Consensus Blunder Veto with HP-Recovery & Protect-Loop Guardrails."""
    if not p:
        raise ValueError('empty action distribution p')
    a_laya = max(sorted(p), key=lambda a: p[a])
    hp_frac = active_hp_frac if active_hp_frac is not None else parse_active_hp_frac(state)
    pen = absorb_penalties or {}
    walled = WA.is_walled_state(state)
    alive_tot = WA.total_alive_from_state(state)
    endgame = alive_tot is not None and alive_tot <= WA.ENDGAME_ALIVE_MAX

    qm_adj = None
    if q_mcts:
        qm_adj = {a: float(v) - float(pen.get(a, 0.0)) for a, v in q_mcts.items() if a in p and math.isfinite(v)}
    qv = None
    if q_vphi:
        qv = {a: float(v) for a, v in q_vphi.items() if a in p and math.isfinite(v)}

    # Matchup status driven by combined MCTS 50k + V_phi v3 2-ply probabilities (NOT calc-based duel: win/lose!)
    matchup_info = ME.assess_matchup(qm_adj, qv, valid_ids=set(p))
    duel_lose = bool(matchup_info['is_unfavorable']) if matchup_info is not None else S2BV2.is_duel_lose(state)

    base_meta = dict(
        mode='way_a_v2',
        duel_lose=duel_lose,
        matchup=matchup_info,
        walled=walled,
        alive_total=alive_tot,
        endgame=endgame,
        active_hp_frac=round(hp_frac, 4) if hp_frac is not None else None,
        just_protected=bool(just_protected),
        absorb_penalties=pen,
        reason='keep_laya',
    )

    if not qm_adj and not qv:
        return a_laya, {}, 0.0, base_meta

    def _blocked_target(a: str, reason: str) -> bool:
        if just_protected and is_protect_action(a):
            return True
        if reason == 'walled_veto':
            if is_protect_action(a):
                return True
            if is_heal_action(a) and (hp_frac is None or hp_frac >= WALLED_HEAL_BLOCK):
                return True
        if reason in ('vphi_blunder_veto', 'duel_lose_vphi_veto', 'vphi_only_veto'):
            if is_heal_action(a) and not is_heal_action(a_laya) and hp_frac is not None and hp_frac >= HIGH_HP_HEAL_BLOCK:
                return True
        return False

    # Case 1: forced_switch or V_phi unavailable
    if not qv:
        assert qm_adj is not None
        if a_laya not in qm_adj:
            return a_laya, {}, 0.0, base_meta
        q0 = qm_adj[a_laya]
        p0 = max(float(p[a_laya]), 1e-4)
        scores = {}
        eligible = []
        thresh = WA.FORCED_MCTS_DELTA if decision_kind == 'forced_switch' else WA.SEVERE_MCTS_DELTA
        for a, q in qm_adj.items():
            dm = q - q0
            pr = 0.015 * math.log(max(float(p[a]), 1e-4) / p0)
            sc = dm + pr
            scores[a] = sc
            rname = 'forced_mcts_veto' if decision_kind == 'forced_switch' else 'mcts_only_severe_veto'
            if a != a_laya and dm >= thresh and sc >= thresh * 0.6 and not _blocked_target(a, rname):
                eligible.append((sc, a, rname))
        if eligible:
            eligible.sort(key=lambda x: (-x[0], x[1]))
            best_sc, best_a, rname = eligible[0]
            base_meta['reason'] = rname
            return best_a, scores, best_sc, base_meta
        return a_laya, scores, 0.0, base_meta

    # Case 2: MCTS unavailable, V_phi available
    if not qm_adj:
        if a_laya not in qv:
            return a_laya, {}, 0.0, base_meta
        v0 = qv[a_laya]
        scores = {a: v - v0 for a, v in qv.items()}
        cands = [
            (sc, a) for a, sc in scores.items()
            if a != a_laya and sc >= WA.VPHI_ONLY_DELTA and not _blocked_target(a, 'vphi_only_veto')
        ]
        if cands:
            cands.sort(key=lambda x: (-x[0], x[1]))
            base_meta['reason'] = 'vphi_only_veto'
            return cands[0][1], scores, cands[0][0], base_meta
        return a_laya, scores, 0.0, base_meta

    # Case 3: Full Way A v2 — BOTH MCTS and Future-Aware V_phi available
    if a_laya not in qm_adj or a_laya not in qv:
        return a_laya, {}, 0.0, base_meta

    q0 = qm_adj[a_laya]
    v0 = qv[a_laya]
    p0 = max(float(p[a_laya]), 1e-4)
    laya_is_consec_prot = just_protected and is_protect_action(a_laya)

    common = [a for a in p if a in qm_adj and a in qv]
    scores: dict[str, float] = {}
    eligible: list[tuple[float, str, str]] = []

    for a in common:
        dm = qm_adj[a] - q0
        dv = qv[a] - v0
        pr_ratio = math.log(max(float(p[a]), 1e-4) / p0)
        c_score = 0.55 * dm + 0.45 * dv + 0.008 * pr_ratio
        scores[a] = c_score
        if a == a_laya:
            continue

        reason = None
        if dm >= WA.SEVERE_MCTS_DELTA and dv >= WA.SEVERE_VPHI_FLOOR:
            reason = 'severe_mcts_veto'
        elif laya_is_consec_prot and (not is_protect_action(a)) and dm >= CONSEC_PROT_MCTS_DELTA and dv >= CONSEC_PROT_VPHI_FLOOR:
            reason = 'consec_protect_veto'
        elif dm >= UNANIMOUS_MCTS_DELTA and dv >= UNANIMOUS_VPHI_DELTA:
            reason = 'unanimous_veto'
        elif walled and dm >= WA.WALLED_MCTS_DELTA and dv >= WA.WALLED_VPHI_FLOOR:
            reason = 'walled_veto'
        elif endgame and dm >= WA.ENDGAME_MCTS_DELTA and dv >= WA.ENDGAME_VPHI_FLOOR:
            reason = 'endgame_veto'
        elif duel_lose and dm >= WA.LOSE_MCTS_DELTA and dv >= WA.LOSE_VPHI_FLOOR:
            reason = 'duel_lose_mcts_veto'
        elif duel_lose and dv >= WA.LOSE_VPHI_LEAD_DELTA and dm >= WA.LOSE_MCTS_FLOOR:
            reason = 'duel_lose_vphi_veto'
        elif (
            duel_lose
            and not a_laya.startswith('switch:')
            and a.startswith('switch:')
            and hp_frac is not None
            and hp_frac >= LOSE_SWITCH_HIGH_HP
            and dm >= LOSE_SWITCH_MCTS_DELTA
            and dv >= LOSE_SWITCH_VPHI_DELTA
        ):
            reason = 'duel_lose_switch_consensus'
        elif (
            duel_lose
            and not a_laya.startswith('switch:')
            and a.startswith('switch:')
            and hp_frac is not None
            and hp_frac >= LOSE_SWITCH_HIGH_HP
            and dv >= LOSE_SWITCH_VPHI_STRONG
            and dm >= LOSE_SWITCH_MCTS_FLOOR
        ):
            reason = 'duel_lose_vphi_switch_veto'
        elif dv >= WA.VPHI_ONLY_DELTA and dm >= WA.VPHI_ONLY_MCTS_FLOOR:
            reason = 'vphi_blunder_veto'
        elif dm >= WA.STD_MCTS_DELTA and dv >= WA.STD_VPHI_FLOOR and (0.5 * dm + 0.5 * dv + 0.012 * pr_ratio) >= WA.STD_CONSENSUS_MIN:
            reason = 'consensus_veto'

        if reason is not None and not _blocked_target(a, reason):
            # For unanimous/consec_protect escape, rank primarily by consensus (dm, dv) so low Laya prior doesn't lose
            rank_sc = (0.55 * dm + 0.45 * dv) if reason in ('unanimous_veto', 'consec_protect_veto') else c_score
            eligible.append((rank_sc, a, reason))

    if eligible:
        eligible.sort(key=lambda x: (-x[0], x[1]))
        best_sc, best_a, reason = eligible[0]
        base_meta['reason'] = reason
        base_meta['dm'] = round(qm_adj[best_a] - q0, 5)
        base_meta['dv'] = round(qv[best_a] - v0, 5)
        return best_a, scores, best_sc, base_meta

    return a_laya, scores, 0.0, base_meta
