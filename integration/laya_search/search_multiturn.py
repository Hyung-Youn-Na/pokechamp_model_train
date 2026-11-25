"""EP-247 / D-223 (EX-222): Fast Multi-Turn 2-Ply Top-K Expectiminimax Expansion using V_phi v3 (`foul-play` venv).

Eliminates 1-ply myopia (instant +50% HP / Multiscale reset illusion) by expanding the Top-K candidate actions
from `s_t -> s_{t+1}` ONE additional full turn (`s_{t+1} -> s_{t+2}`) and backing up batched `V_phi v3` leaf
evaluations with soft-minimax (modeling an adversary who punishes passive recovery/Protect with setup, hazards,
or repeated chip/stat drops on turn 2).

Architecture keeps `foul-play` (`poke_engine`) and `laya` (`torch`) decoupled via a plain `score_fn(raw_list)`:
1. Ply-1 expansion (`expand_turn1_v3`): expands all legal `(a, b)` using `featurize_v3.extract_raw_v3` +
   `TAUNT + absorb-heal` workaround, scores all unique `s_1` states in 1 batch -> `q_1ply`.
2. Top-K candidate selection: selects top `K=4` actions (Laya top-2 union 1-ply `V_phi` top-2, plus any top-3
   recovery/Protect action so passive healing is always stress-tested on turn 2!).
3. Ply-2 expansion (`expand_turn2_from_s1`): for top-2 `s_1` opponent replies of each Top-K action, generates
   turn-2 `(a_2, b_2)` branches using fast legal move/switch pruning (max 4 moves + 1 healthy switch per side),
   scores ALL unique depth-2 leaves `s_2` in ONE single batched `score_fn` call, and computes soft-minimax backup:
       V_2ply(s_1) = max_{a_2} [ 0.70 * min_{b_2} V(s_2) + 0.30 * mean_{b_2} V(s_2) ].
4. Returns `q_2ply` (`0.20 * q_1ply + 0.80 * q_2ply_raw` for Top-K; `q_1ply` for pruned actions) alongside
   `q_1ply`, `absorb_penalties`, and timing/leaf diagnostics.
"""
from __future__ import annotations

import time
from typing import Callable

from . import featurize as F
from . import featurize_v3 as F3
from . import search_2b as S2B
from . import search_2b_v2 as S2BV2

TOP_K_ACTIONS = 4
TOP_FOE_PLY1 = 2
MAX_PLY2_UNIQUE = 512
SOFTMIN_ALPHA = 0.70    # Weight on worst-case opp reply at ply-2 (0.70 min + 0.30 mean)
PLY2_BLEND = 0.80       # Weight on 2-ply value vs 1-ply value for Top-K actions


def _fast_side_choices(side, max_moves: int = 4, include_best_switch: bool = True) -> list[str]:
    """Fast legal turn-2 choice list for one side: active legal moves (skipping consecutive Protect) + best bench switch."""
    act_idx = int(side.active_index)
    act = side.pokemon[act_idx]
    choices: list[str] = []
    last_mid = F3._last_move_id(side, act)
    just_prot = last_mid in F3.PROTECT_MOVES

    if act.hp > 0:
        for m in (getattr(act, 'moves', None) or ()):
            if getattr(m, 'disabled', False) or getattr(m, 'pp', 0) <= 0:
                continue
            mid = F.norm(m.id)
            if mid == 'none':
                continue
            # Avoid wasting depth-2 branching on 66.7%-fail consecutive Protect
            if just_prot and mid in F3.PROTECT_MOVES:
                continue
            choices.append(m.id.lower())
            if len(choices) >= max_moves:
                break

    if include_best_switch:
        best_sw = None
        best_hp = -1.0
        for i, p in enumerate(side.pokemon):
            if i == act_idx or p.hp <= 0:
                continue
            hpf = float(p.hp) / max(1.0, float(p.maxhp))
            if hpf > best_hp:
                best_hp = hpf
                best_sw = p.id.lower()
        if best_sw is not None:
            choices.append(best_sw)

    if not choices:
        # Fallback: any alive bench switch or first move
        for i, p in enumerate(side.pokemon):
            if i != act_idx and p.hp > 0:
                choices.append(p.id.lower())
                break
        if not choices and getattr(act, 'moves', None):
            choices.append(act.moves[0].id.lower())
    return choices


def expand_turn1_v3_states(
    samples: list[tuple[str, float]],
    mapping: dict[str, str],
    foe_dist: dict[str, float],
    *,
    foe_floor: float = S2B.FOE_FLOOR,
    max_unique_ply1: int = S2B.MAX_UNIQUE_STATES,
) -> tuple[dict, list[object], bool]:
    """Ply-1 expansion with `featurize_v3.extract_raw_v3`, TAUNT/absorb fix, cached `s1_states`, and `just_protected`."""
    import poke_engine
    from integration.laya_foe.read import foe_choices

    s1_key_to_idx: dict[str, int] = {}
    s1_raws: list[dict] = []
    s1_states: list[object] = []
    branches_1: dict[str, list[tuple[float, int | None, float | None]]] = {a: [] for a in mapping}
    absorb_penalties: dict[str, float] = {}
    sample_w_total = 0.0
    just_protected_w = 0.0
    errors = 0

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
        if F3._last_move_id(st.side_one, me_act) in F3.PROTECT_MOVES:
            just_protected_w += chance
        me_ab = F.norm(getattr(me_act, 'ability', ''))
        me_sp = F.norm(getattr(me_act, 'id', ''))
        opp_ab = F.norm(getattr(opp_act, 'ability', ''))
        opp_hp0 = float(getattr(opp_act, 'hp', 0))
        opp_max0 = max(1.0, float(getattr(opp_act, 'maxhp', 1)))
        opp_hp_frac0 = opp_hp0 / opp_max0
        vols = {F.norm(v) for v in (getattr(st.side_one, 'volatile_statuses', None) or ())}
        me_taunted = 'taunt' in vols
        stay_prob = sum(pb for b, pb in opp_dist.items() if not b.startswith('switch ')) / z

        for aid, ch in mapping.items():
            eng_choice = ch[7:] if ch.startswith('switch ') else ch
            is_move = aid.startswith('move:')
            base_move = aid.split(':')[1] if is_move else ''
            mtype = S2BV2.move_attack_type(base_move, me_sp) if is_move else None
            triggers_heal = (
                is_move and mtype is not None
                and me_ab not in S2BV2.MOLD_BREAKERS and base_move not in S2BV2.IGNORE_ABILITY_MOVES
                and S2BV2.ABSORB_HEAL.get(opp_ab) == mtype
            )
            triggers_boost = (
                is_move and mtype is not None
                and me_ab not in S2BV2.MOLD_BREAKERS and base_move not in S2BV2.IGNORE_ABILITY_MOVES
                and S2BV2.ABSORB_BOOST.get(opp_ab) == mtype
            )
            if triggers_heal and me_taunted and opp_hp_frac0 < 0.99 and stay_prob > 0.0:
                missing_heal = min(0.25, 1.0 - opp_hp_frac0) / 0.25
                absorb_penalties[aid] = absorb_penalties.get(aid, 0.0) + chance * stay_prob * S2BV2.ABSORB_HEAL_PENALTY * missing_heal
            elif triggers_boost and me_taunted and stay_prob > 0.0:
                absorb_penalties[aid] = absorb_penalties.get(aid, 0.0) + chance * stay_prob * S2BV2.ABSORB_BOOST_PENALTY

            for b, pb in opp_dist.items():
                p_norm = pb / z
                opp_stays = not b.startswith('switch ')
                try:
                    insts = poke_engine.generate_instructions(st, eng_choice, b)
                except BaseException:
                    errors += 1
                    continue
                for br in insts:
                    w = chance * p_norm * (float(br.percentage) / 100.0)
                    if w <= 0.0:
                        continue
                    try:
                        nxt = st.apply_instructions(br)
                    except BaseException:
                        errors += 1
                        continue
                    term = F.state_terminal(nxt)
                    if term is not None:
                        branches_1[aid].append((w, None, term))
                    else:
                        need_heal_patch = False
                        if triggers_heal and me_taunted and opp_stays and opp_hp_frac0 < 0.99:
                            opp_nxt = nxt.side_two.pokemon[int(nxt.side_two.active_index)]
                            if F.norm(getattr(opp_nxt, 'id', '')) == F.norm(getattr(opp_act, 'id', '')):
                                if float(opp_nxt.hp) < opp_hp0 + opp_max0 * 0.15:
                                    need_heal_patch = True
                        key = nxt.to_string() + ('#ah25' if need_heal_patch else '')
                        idx = s1_key_to_idx.get(key)
                        if idx is None:
                            if len(s1_raws) >= max_unique_ply1:
                                continue
                            idx = len(s1_raws)
                            s1_key_to_idx[key] = idx
                            raw = F3.extract_raw_v3(nxt)
                            if need_heal_patch:
                                raw = F3.patch_raw_v3_opp_heal(raw, 0.25)
                            s1_raws.append(raw)
                            s1_states.append(nxt)
                        branches_1[aid].append((w, idx, None))

    if sample_w_total > 0.0:
        absorb_penalties = {k: round(v / sample_w_total, 6) for k, v in absorb_penalties.items() if v > 1e-6}
    just_protected = (sample_w_total > 0.0) and (just_protected_w / sample_w_total >= 0.5)
    payload = dict(
        unique_raws=s1_raws,
        branches=branches_1,
        absorb_penalties=absorb_penalties,
        just_protected=just_protected,
        errors=errors,
    )
    return payload, s1_states, just_protected


def select_ply2_targets(
    branches_1: dict,
    q_1ply: dict[str, float],
    laya_p: dict[str, float] | None = None,
    *,
    top_k: int = TOP_K_ACTIONS,
    top_foe_ply1: int = TOP_FOE_PLY1,
) -> tuple[list[str], list[int]]:
    """Select Top-K actions (Laya top-2 U 1-ply top-2 + top-3 heal/Protect) and their top `s1_idx` states."""
    cand_set: list[str] = []
    if laya_p:
        for a, _ in sorted(laya_p.items(), key=lambda kv: -float(kv[1]))[:2]:
            if a in q_1ply and a not in cand_set:
                cand_set.append(a)
    for a, _ in sorted(q_1ply.items(), key=lambda kv: -float(kv[1])):
        if a not in cand_set:
            cand_set.append(a)
        if len(cand_set) >= top_k:
            break
    for a in sorted(q_1ply, key=lambda k: -q_1ply[k])[:3]:
        if a not in cand_set and a.startswith('move:'):
            mid = F.norm(a.split(':')[1])
            if mid in F3.HEAL_MOVES or mid in F3.PROTECT_MOVES:
                cand_set.append(a)

    s1_to_expand: set[int] = set()
    for a in cand_set:
        w_by_idx: dict[int, float] = {}
        for w, idx, _term in branches_1.get(a, ()):
            if idx is not None:
                w_by_idx[idx] = w_by_idx.get(idx, 0.0) + w
        for idx, _ in sorted(w_by_idx.items(), key=lambda kv: -kv[1])[:top_foe_ply1]:
            s1_to_expand.add(idx)
    return cand_set, sorted(s1_to_expand)


def expand_turn2_from_states(
    s1_states: list[object],
    s1_indices: list[int],
    *,
    max_unique_ply2: int = MAX_PLY2_UNIQUE,
) -> dict:
    """Expand ply-2 `(a2, b2)` from cached `s1_states[idx]` and return `(unique_raws, grid)` for batched V_phi v3."""
    import poke_engine

    s2_key_to_idx: dict[str, int] = {}
    s2_raws: list[dict] = []
    # JSON-friendly str(s1_idx) -> {a2: [[idx2_or_None, term2_or_None], ...]}
    s2_grid: dict[str, dict[str, list[list[int | float | None]]]] = {}

    for s1_idx in s1_indices:
        if s1_idx < 0 or s1_idx >= len(s1_states):
            continue
        st1 = s1_states[s1_idx]
        if getattr(st1.side_one, 'force_switch', False) or getattr(st1.side_two, 'force_switch', False):
            continue
        my_c2 = _fast_side_choices(st1.side_one, max_moves=4, include_best_switch=True)
        op_c2 = _fast_side_choices(st1.side_two, max_moves=4, include_best_switch=True)
        if not my_c2 or not op_c2:
            continue
        grid_a: dict[str, list[list[int | float | None]]] = {}
        for a2 in my_c2:
            replies: list[list[int | float | None]] = []
            for b2 in op_c2:
                try:
                    insts2 = poke_engine.generate_instructions(st1, a2, b2)
                except BaseException:
                    continue
                if not insts2:
                    continue
                br2 = max(insts2, key=lambda b: float(b.percentage))
                try:
                    st2 = st1.apply_instructions(br2)
                except BaseException:
                    continue
                term2 = F.state_terminal(st2)
                if term2 is not None:
                    replies.append([None, float(term2)])
                else:
                    k2 = st2.to_string()
                    idx2 = s2_key_to_idx.get(k2)
                    if idx2 is None:
                        if len(s2_raws) >= max_unique_ply2:
                            continue
                        idx2 = len(s2_raws)
                        s2_key_to_idx[k2] = idx2
                        s2_raws.append(F3.extract_raw_v3(st2))
                    replies.append([idx2, None])
            if replies:
                grid_a[a2] = replies
        if grid_a:
            s2_grid[str(s1_idx)] = grid_a

    return dict(unique_raws=s2_raws, grid=s2_grid)


def backup_2ply_q(
    branches_1: dict,
    s1_probs: list[float],
    q_1ply: dict[str, float],
    cand_set: list[str],
    s2_grid: dict,
    s2_probs: list[float],
    *,
    softmin_alpha: float = SOFTMIN_ALPHA,
    ply2_blend: float = PLY2_BLEND,
) -> dict[str, float]:
    """Soft-minimax backup of depth-2 `V_phi v3` evaluations into per-action `q_2ply`."""
    s1_val_2ply: dict[int, float] = {}
    for s1_k, grid_a in (s2_grid or {}).items():
        s1_idx = int(s1_k)
        best_a2_val = -1.0
        for replies in grid_a.values():
            vals = [float(term2) if term2 is not None else float(s2_probs[int(idx2)]) for idx2, term2 in replies]
            if not vals:
                continue
            a2_val = softmin_alpha * min(vals) + (1.0 - softmin_alpha) * (sum(vals) / len(vals))
            if a2_val > best_a2_val:
                best_a2_val = a2_val
        if best_a2_val >= 0.0:
            s1_val_2ply[s1_idx] = best_a2_val

    cand_s = set(cand_set)
    q_2ply: dict[str, float] = {}
    for aid, entries in branches_1.items():
        if aid not in q_1ply:
            continue
        if aid not in cand_s:
            q_2ply[aid] = q_1ply[aid]
            continue
        num, den = 0.0, 0.0
        for w, idx, term in entries:
            if term is not None:
                val = float(term)
            elif idx is not None and idx in s1_val_2ply:
                val = ply2_blend * s1_val_2ply[idx] + (1.0 - ply2_blend) * float(s1_probs[idx])
            elif idx is not None:
                val = float(s1_probs[idx])
            else:
                continue
            num += w * val
            den += w
        q_2ply[aid] = round(num / den, 6) if den > 0.0 else q_1ply[aid]
    return q_2ply


def expand_and_score_2ply(
    samples: list[tuple[str, float]],
    mapping: dict[str, str],
    foe_dist: dict[str, float],
    score_fn: Callable[[list[dict]], list[float]],
    *,
    laya_p: dict[str, float] | None = None,
    foe_floor: float = S2B.FOE_FLOOR,
    top_k: int = TOP_K_ACTIONS,
    top_foe_ply1: int = TOP_FOE_PLY1,
    max_unique_ply1: int = S2B.MAX_UNIQUE_STATES,
    max_unique_ply2: int = MAX_PLY2_UNIQUE,
    softmin_alpha: float = SOFTMIN_ALPHA,
    ply2_blend: float = PLY2_BLEND,
) -> dict:
    """Run full 1-ply + Top-K 2-ply Expectiminimax using `poke_engine` and batched `score_fn` (`ValueScorerV3`)."""
    t0 = time.time()
    exp1, s1_states, just_protected = expand_turn1_v3_states(
        samples, mapping, foe_dist, foe_floor=foe_floor, max_unique_ply1=max_unique_ply1,
    )
    s1_raws = exp1['unique_raws']
    branches_1 = exp1['branches']
    s1_probs = score_fn(s1_raws) if s1_raws else []
    q_1ply = S2B.aggregate_value_2b(exp1, s1_probs)
    if not q_1ply:
        return dict(
            q_1ply={}, q_2ply={}, absorb_penalties=exp1['absorb_penalties'], just_protected=just_protected,
            ply1_states=len(s1_raws), ply2_states=0, expanded_actions=[],
            seconds=round(time.time() - t0, 4), errors=exp1['errors'],
        )
    cand_set, s1_indices = select_ply2_targets(branches_1, q_1ply, laya_p, top_k=top_k, top_foe_ply1=top_foe_ply1)
    exp2 = expand_turn2_from_states(s1_states, s1_indices, max_unique_ply2=max_unique_ply2)
    s2_raws = exp2['unique_raws']
    s2_probs = score_fn(s2_raws) if s2_raws else []
    q_2ply = backup_2ply_q(
        branches_1, s1_probs, q_1ply, cand_set, exp2['grid'], s2_probs,
        softmin_alpha=softmin_alpha, ply2_blend=ply2_blend,
    )
    return dict(
        q_1ply=q_1ply,
        q_2ply=q_2ply,
        absorb_penalties=exp1['absorb_penalties'],
        just_protected=just_protected,
        ply1_states=len(s1_raws),
        ply2_states=len(s2_raws),
        expanded_actions=cand_set,
        seconds=round(time.time() - t0, 4),
        errors=exp1['errors'],
    )
