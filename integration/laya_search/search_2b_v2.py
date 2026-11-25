"""EP-244 / D-220 (2-B v2): Recovery- and absorb-aware 2-B search improvements (non-invasive over `search_2b.py`).

Fixes three root causes diagnosed in `EX-208` (6,410 decisions) and `EX-211` (311 live ladder decisions):
1. `foe_options_clean(state)`: strips PP annotations like `(13/16 used)` from `OPP ... | seen ...` before splitting,
   fixing the `laya_foe.data_foe.foe_options` parsing bug that dropped high-PP-usage moves (e.g. `drainingkiss`) into
   `foe:move:other` (`>= 0.30` in ~16% of turns).
2. `choose_fused_2b_v2`: scale-matches `Q_vphi` relative differences to `Q_mcts` (clipped `1.0..2.5x`, `alpha=0.55`)
   and relaxes `prior_lambda` (`0.03 -> 0.015`, `floor 1e-4 -> 1e-3`) when `duel: ... -> lose` is present so `V_phi`'s
   unfavorable-matchup switch warnings are no longer drowned out by `Q_mcts` (1.8-2.0x wider) or `EX-200` prior bias.
3. `expand_turn1_features_v2`: works around `poke-engine v0.0.48`'s `TAUNT + Water/Volt/Earth/DrySkin Absorb` bug
   (where `Heal SideTwo` +25% vanishes when `side_one` has `TAUNT`), patching child-state HP in `raw` AND returning
   per-action `absorb_penalties` to correct `Q_mcts`.
"""
from __future__ import annotations

import copy
import math
import re

from . import featurize as F
from . import search_2b as S2B
from . import search_core as SC

VERSION_2B_V2 = 'laya-search-2b-v2'
VALUE_ALPHA_V2 = 0.65
PRIOR_LAMBDA_LOSE = 0.012
PRIOR_FLOOR_LOSE = 1e-3
SCALE_MIN = 1.0
SCALE_MAX = 3.0
SPREAD_FLOOR_V = 0.015
SPREAD_ACTIVE_V = 0.008
ABSORB_HEAL_PENALTY = 0.15
ABSORB_BOOST_PENALTY = 0.06

ABSORB_HEAL = {
    'waterabsorb': 'water',
    'dryskin': 'water',
    'voltabsorb': 'electric',
    'eartheater': 'ground',
}
ABSORB_BOOST = {
    'flashfire': 'fire',
    'sapsipper': 'grass',
    'stormdrain': 'water',
    'lightningrod': 'electric',
    'motordrive': 'electric',
    'wellbakedbody': 'fire',
}
MOLD_BREAKERS = frozenset(('moldbreaker', 'teravolt', 'turboblaze'))
IGNORE_ABILITY_MOVES = frozenset(('sunsteelstrike', 'moongeistbeam', 'photongeyser'))
_PP_PAREN_RE = re.compile(r'\([^)]*\)')
_OTHER = 'foe:move:other'

# Static move-type cache (lazy loaded from dex_v2 in laya env or fp.data in foul-play env)
_MOVE_TYPES: dict[str, str] | None = None


def _load_move_types() -> dict[str, str]:
    global _MOVE_TYPES
    if _MOVE_TYPES is not None:
        return _MOVE_TYPES
    out: dict[str, str] = {}
    try:
        from integration.laya_imitation import dex_v2
        for mid, info in dex_v2.load()['moves'].items():
            if info.get('category') != 'status' and info.get('type'):
                out[mid] = info['type'].lower()
    except Exception:
        pass
    if not out:
        try:
            from data import all_move_json
            for mid, info in all_move_json.items():
                if info.get('category', '').lower() != 'status' and info.get('type'):
                    out[mid.lower()] = info['type'].lower()
        except Exception:
            pass
    _MOVE_TYPES = out
    return out


def move_attack_type(move_id: str, attacker_species: str = '') -> str | None:
    mid = F.norm(move_id)
    if mid == 'ivycudgel':
        sp = F.norm(attacker_species)
        if 'wellspring' in sp:
            return 'water'
        if 'hearthflame' in sp:
            return 'fire'
        if 'cornerstone' in sp:
            return 'rock'
        return 'grass'
    return _load_move_types().get(mid)


def foe_options_clean(state: str) -> dict[str, str]:
    """Fixed `laya_foe.data_foe.foe_options`: strips PP annotations like `(13/16 used)` before tokenizing `seen`."""
    lines = state.split('\n')
    seen: list[str] = []
    likely: list[tuple[str, str]] = []
    bench: list[tuple[str, str]] = []
    for line in lines:
        if line.startswith('OPP '):
            for seg in (s.strip() for s in line.split(' | ')):
                if seg.startswith('seen '):
                    cleaned = _PP_PAREN_RE.sub('', seg[5:])
                    seen = [tok for tok in cleaned.split() if tok and tok.isalnum()]
        elif line.startswith('opp set:'):
            for part in line[len('opp set:'):].split(';'):
                part = part.strip()
                if part.startswith('likely moves '):
                    for item in part[len('likely moves '):].split(','):
                        bits = item.split()
                        if bits:
                            likely.append((bits[0], bits[1] if len(bits) > 1 else ''))
        elif line.startswith('opp team:'):
            for entry in line[len('opp team:'):].split('||'):
                segs = [s.strip() for s in entry.strip().split(' | ')]
                if not segs or not segs[0] or ' fainted' in segs[0] or segs[0].endswith('fainted'):
                    continue
                answer = [s for s in segs if s.startswith('answer ')]
                bench.append((segs[0].split(' ', 1)[0], ' | '.join([segs[0]] + answer[:1])))
    criteria: dict[str, str] = {}
    for m in seen:
        criteria['foe:move:' + m] = '%s (seen)' % m
    for m, p in likely:
        criteria.setdefault('foe:move:' + m, '%s (likely %s)' % (m, p) if p else '%s (likely)' % m)
    criteria[_OTHER] = 'another move not yet seen'
    for species, text in bench:
        criteria.setdefault('foe:switch:' + species, 'switch to ' + text[:220])
    return criteria


def is_duel_lose(state: str) -> bool:
    for line in state.split('\n'):
        if line.startswith('duel: ') and line.rstrip().endswith('-> lose'):
            return True
    return False


def _patch_raw_opp_heal(raw: dict, heal_frac: float = 0.25) -> dict:
    """Apply missing +25% active opponent heal to extracted `featurize.extract_raw` dict (exact antisymmetry)."""
    out = copy.deepcopy(raw)
    old_hp = float(out['mon_num'][6][3])
    if old_hp <= 0.0 or old_hp >= 1.0:
        return out
    new_hp = min(1.0, old_hp + heal_frac)
    delta = new_hp - old_hp
    out['mon_num'][6][3] = new_hp
    out['global_num'][12] = float(out['global_num'][12]) + delta / 6.0
    out['global_num'][23] = float(out['global_num'][23]) - delta / 6.0
    return out


def expand_turn1_features_v2(
    samples: list[tuple[str, float]],
    mapping: dict[str, str],
    foe_dist: dict[str, float],
    *,
    foe_floor: float = S2B.FOE_FLOOR,
    max_unique: int = S2B.MAX_UNIQUE_STATES,
) -> dict:
    """Ply-1 expansion with `poke-engine v0.0.48` `TAUNT + absorb-heal` workaround and per-action absorb penalties."""
    import poke_engine
    from integration.laya_foe.read import foe_choices

    state_to_idx: dict[str, int] = {}
    unique_raws: list[dict] = []
    branches: dict[str, list[tuple[float, int | None, float | None]]] = {a: [] for a in mapping}
    action_weight: dict[str, float] = {a: 0.0 for a in mapping}
    absorb_penalties: dict[str, float] = {}
    sample_w_total = 0.0
    errors = 0
    capped = False

    for text, chance in sorted(samples, key=lambda kv: -float(kv[1])):
        chance = float(chance)
        if chance <= 0.0:
            continue
        try:
            st = poke_engine.State.from_string(text)
        except BaseException:
            errors += 1
            continue
        opp_dist = {b: p for b, p in foe_choices(st, foe_dist).items() if p >= foe_floor}
        z = sum(opp_dist.values())
        if not opp_dist or z <= 0.0:
            continue
        sample_w_total += chance

        me_act = st.side_one.pokemon[int(st.side_one.active_index)]
        opp_act = st.side_two.pokemon[int(st.side_two.active_index)]
        me_ab = F.norm(getattr(me_act, 'ability', ''))
        me_sp = F.norm(getattr(me_act, 'id', ''))
        opp_ab = F.norm(getattr(opp_act, 'ability', ''))
        opp_hp0 = float(getattr(opp_act, 'hp', 0))
        opp_max0 = max(1.0, float(getattr(opp_act, 'maxhp', 1)))
        opp_hp_frac0 = opp_hp0 / opp_max0
        vols = {F.norm(v) for v in (getattr(st.side_one, 'volatile_statuses', None) or ())}
        me_taunted = 'taunt' in vols

        # Probability opponent stays active (doesn't switch out)
        stay_prob = sum(pb for b, pb in opp_dist.items() if not b.startswith('switch ')) / z

        for aid, ch in mapping.items():
            eng_choice = ch[7:] if ch.startswith('switch ') else ch
            is_move = aid.startswith('move:')
            base_move = aid.split(':')[1] if is_move else ''
            mtype = move_attack_type(base_move, me_sp) if is_move else None
            triggers_heal = (
                is_move and mtype is not None
                and me_ab not in MOLD_BREAKERS and base_move not in IGNORE_ABILITY_MOVES
                and ABSORB_HEAL.get(opp_ab) == mtype
            )
            triggers_boost = (
                is_move and mtype is not None
                and me_ab not in MOLD_BREAKERS and base_move not in IGNORE_ABILITY_MOVES
                and ABSORB_BOOST.get(opp_ab) == mtype
            )

            # Record Q_mcts correction for TAUNT+WaterAbsorb bug (and boost-absorb under TAUNT)
            if triggers_heal and me_taunted and opp_hp_frac0 < 0.99 and stay_prob > 0.0:
                missing_heal = min(0.25, 1.0 - opp_hp_frac0) / 0.25
                absorb_penalties[aid] = absorb_penalties.get(aid, 0.0) + chance * stay_prob * ABSORB_HEAL_PENALTY * missing_heal
            elif triggers_boost and me_taunted and stay_prob > 0.0:
                absorb_penalties[aid] = absorb_penalties.get(aid, 0.0) + chance * stay_prob * ABSORB_BOOST_PENALTY

            sample_a_w = 0.0
            sample_entries = []
            ok = True
            for b, pb in opp_dist.items():
                p_norm = pb / z
                opp_stays = not b.startswith('switch ')
                try:
                    insts = poke_engine.generate_instructions(st, eng_choice, b)
                except BaseException:
                    errors += 1
                    ok = False
                    break
                for br in insts:
                    w = chance * p_norm * (float(br.percentage) / 100.0)
                    if w <= 0.0:
                        continue
                    try:
                        nxt = st.apply_instructions(br)
                    except BaseException:
                        errors += 1
                        ok = False
                        break
                    term = F.state_terminal(nxt)
                    if term is not None:
                        sample_entries.append((w, None, term))
                        sample_a_w += w
                    else:
                        # Check if TAUNT erased the +25% absorb heal on nxt
                        need_heal_patch = False
                        if triggers_heal and me_taunted and opp_stays and opp_hp_frac0 < 0.99:
                            opp_nxt = nxt.side_two.pokemon[int(nxt.side_two.active_index)]
                            if F.norm(getattr(opp_nxt, 'id', '')) == F.norm(getattr(opp_act, 'id', '')):
                                if float(opp_nxt.hp) < opp_hp0 + opp_max0 * 0.15:
                                    need_heal_patch = True
                        key = nxt.to_string() + ('#ah25' if need_heal_patch else '')
                        idx = state_to_idx.get(key)
                        if idx is None:
                            if len(unique_raws) >= max_unique:
                                capped = True
                                continue
                            idx = len(unique_raws)
                            state_to_idx[key] = idx
                            raw = F.extract_raw(nxt)
                            if need_heal_patch:
                                raw = _patch_raw_opp_heal(raw, 0.25)
                            unique_raws.append(raw)
                        sample_entries.append((w, idx, None))
                        sample_a_w += w
                if not ok:
                    break
            if ok and sample_a_w > 0.0:
                branches[aid].extend(sample_entries)
                action_weight[aid] += sample_a_w

    if sample_w_total > 0.0:
        absorb_penalties = {k: round(v / sample_w_total, 6) for k, v in absorb_penalties.items() if v > 1e-6}
    return dict(
        unique_raws=unique_raws,
        branches=branches,
        action_weight=action_weight,
        absorb_penalties=absorb_penalties,
        errors=errors,
        capped=capped,
    )


def choose_fused_2b_v2(
    p: dict[str, float],
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    *,
    state: str = '',
    absorb_penalties: dict[str, float] | None = None,
    alpha: float = VALUE_ALPHA_V2,
    lam: float = SC.PRIOR_LAMBDA,
    lam_lose: float = PRIOR_LAMBDA_LOSE,
    floor: float = SC.PRIOR_FLOOR,
    floor_lose: float = PRIOR_FLOOR_LOSE,
    margin: float = SC.MARGIN,
) -> tuple[str, dict[str, float], float, dict]:
    """Scale-matched 2-B v2 fusion with `duel: lose` prior relaxation and absorb-heal Q_mcts correction."""
    duel_lose = is_duel_lose(state)
    eff_lam = lam_lose if duel_lose else lam
    eff_floor = floor_lose if duel_lose else floor
    pen = absorb_penalties or {}

    if not q_mcts and not q_vphi:
        pick, scores, delta = SC.choose_fused(p, None, lam=eff_lam, floor=eff_floor, margin=margin)
        return pick, scores, delta, dict(duel_lose=duel_lose, eff_lam=eff_lam, scale_v=1.0, absorb_penalties=pen)

    qm_adj = None
    if q_mcts:
        qm_adj = {a: float(v) - float(pen.get(a, 0.0)) for a, v in q_mcts.items() if math.isfinite(v)}

    if not q_vphi:
        pick, scores, delta = SC.choose_fused(p, qm_adj, lam=eff_lam, floor=eff_floor, margin=margin)
        return pick, scores, delta, dict(duel_lose=duel_lose, eff_lam=eff_lam, scale_v=1.0, absorb_penalties=pen)
    if not qm_adj:
        pick, scores, delta = SC.choose_fused(p, q_vphi, lam=eff_lam, floor=eff_floor, margin=margin)
        return pick, scores, delta, dict(duel_lose=duel_lose, eff_lam=eff_lam, scale_v=1.0, absorb_penalties=pen)

    common = [a for a in p if a in qm_adj and a in q_vphi and math.isfinite(q_vphi[a])]
    scale_v = 1.0
    qv_mean = 0.0
    if len(common) >= 2:
        mvals = [qm_adj[a] for a in common]
        vvals = [float(q_vphi[a]) for a in common]
        spread_m = max(mvals) - min(mvals)
        spread_v = max(vvals) - min(vvals)
        qv_mean = sum(vvals) / len(vvals)
        if spread_v >= SPREAD_ACTIVE_V and spread_m > 0.0:
            scale_v = min(SCALE_MAX, max(SCALE_MIN, spread_m / max(spread_v, SPREAD_FLOOR_V)))

    combined_q: dict[str, float] = {}
    for a in set(qm_adj) | set(q_vphi):
        if a not in p:
            continue
        qm = qm_adj.get(a)
        qv = q_vphi.get(a)
        if qm is not None and qv is not None and math.isfinite(qv):
            qv_scaled = qv_mean + (float(qv) - qv_mean) * scale_v
            combined_q[a] = (1.0 - alpha) * float(qm) + alpha * qv_scaled
        elif qv is not None and math.isfinite(qv):
            combined_q[a] = float(qv)
        elif qm is not None:
            combined_q[a] = float(qm)

    pick, scores, delta = SC.choose_fused(p, combined_q, lam=eff_lam, floor=eff_floor, margin=margin)
    meta = dict(
        duel_lose=duel_lose,
        eff_lam=eff_lam,
        scale_v=round(scale_v, 4),
        absorb_penalties=pen,
    )
    return pick, scores, delta, meta
