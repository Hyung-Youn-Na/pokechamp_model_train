"""EP-243 / D-219 (2-B): q-weighted child-state expansion (`foul-play` venv) + V_phi batched fusion (`laya` venv).

Architecture split keeps both venvs cleanly decoupled:
1. In `foul-play` venv (`expand_turn1_features`): for each sample state `s_k` (`chance_k`), each candidate action `a`,
   and each opponent action `b` with `q(b|s_k) >= FOE_FLOOR`:
   - expands `generate_instructions(s_k, a, b)`;
   - checks exact terminal outcome (`state_terminal(s')`) first;
   - deduplicates non-terminal child states by `s'.to_string()`, extracts compact `featurize.extract_raw(s')`, and
     returns `(unique_raws, action_branches)` where each action maps to `[(weight, state_idx_or_None, terminal_val)]`.
2. In `laya` venv (`aggregate_value_2b`, `choose_fused_2b`):
   - scores all `unique_raws` in ONE single GPU 0 forward pass via `ValueScorer.score_raw_batch` (`< 2 ms`!);
   - computes expected win probability `Q_vphi(a)` for each action;
   - fuses `score_2b(a) = (1 - alpha) * Q_mcts(a) + alpha * Q_vphi(a) + lam * ln(max(p(a), floor))`.
"""
from __future__ import annotations

import math

from . import featurize as F
from . import search_core as SC

VERSION_2B = 'laya-search-2b-v1'
VALUE_ALPHA = 0.50
FOE_FLOOR = 0.03
MAX_UNIQUE_STATES = 512


def expand_turn1_features(
    samples: list[tuple[str, float]],
    mapping: dict[str, str],
    foe_dist: dict[str, float],
    *,
    foe_floor: float = FOE_FLOOR,
    max_unique: int = MAX_UNIQUE_STATES,
) -> dict:
    """Expand ply-1 `(mine, foe)` branches in `poke_engine` and return compact unique child features + branch weights.

    Must run inside `foul-play` venv (`poke_engine` and `laya_foe.read.foe_choices` available).
    """
    import poke_engine
    from integration.laya_foe.read import foe_choices

    state_to_idx: dict[str, int] = {}
    unique_raws: list[dict] = []
    # action_id -> list of (weight, idx_or_None, terminal_val_or_None)
    branches: dict[str, list[tuple[float, int | None, float | None]]] = {a: [] for a in mapping}
    action_weight: dict[str, float] = {a: 0.0 for a in mapping}
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
        opp = {b: p for b, p in foe_choices(st, foe_dist).items() if p >= foe_floor}
        z = sum(opp.values())
        if not opp or z <= 0.0:
            continue

        for aid, ch in mapping.items():
            # `choice_map` prefixes switches with `'switch '`, whereas `generate_instructions` expects plain name
            eng_choice = ch[7:] if ch.startswith('switch ') else ch
            sample_a_w = 0.0
            sample_entries = []
            ok = True
            for b, pb in opp.items():
                p_norm = pb / z
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
                        key = nxt.to_string()
                        idx = state_to_idx.get(key)
                        if idx is None:
                            if len(unique_raws) >= max_unique:
                                capped = True
                                continue
                            idx = len(unique_raws)
                            state_to_idx[key] = idx
                            unique_raws.append(F.extract_raw(nxt))
                        sample_entries.append((w, idx, None))
                        sample_a_w += w
                if not ok:
                    break
            if ok and sample_a_w > 0.0:
                branches[aid].extend(sample_entries)
                action_weight[aid] += sample_a_w

    return dict(
        unique_raws=unique_raws,
        branches=branches,
        action_weight=action_weight,
        errors=errors,
        capped=capped,
    )


def aggregate_value_2b(expansion: dict, state_probs: list[float]) -> dict[str, float]:
    """Compute per-action expected win probability `Q_vphi(a)` from `expansion` and batched `V_phi` probabilities."""
    q_vphi: dict[str, float] = {}
    branches = expansion.get('branches') or {}
    for aid, entries in branches.items():
        num, den = 0.0, 0.0
        for w, idx, term in entries:
            if term is not None:
                val = float(term)
            elif idx is not None and 0 <= idx < len(state_probs):
                val = float(state_probs[idx])
            else:
                continue
            num += w * val
            den += w
        if den > 0.0:
            q_vphi[aid] = round(num / den, 6)
    return q_vphi


def choose_fused_2b(
    p: dict[str, float],
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    *,
    alpha: float = VALUE_ALPHA,
    lam: float = SC.PRIOR_LAMBDA,
    floor: float = SC.PRIOR_FLOOR,
    margin: float = SC.MARGIN,
) -> tuple[str, dict[str, float], float]:
    """Hybrid 2-B fusion: `(1 - alpha) * Q_mcts(a) + alpha * Q_vphi(a) + lam * ln(max(p(a), floor))`.

    Falls back gracefully to pure `Q_mcts` (if `q_vphi` absent, e.g., forced_switch) or pure `Q_vphi` (if `q_mcts`
    absent), or `laya` argmax if neither is available.
    """
    if not q_mcts and not q_vphi:
        return SC.choose_fused(p, None, lam=lam, floor=floor, margin=margin)
    if not q_vphi:
        return SC.choose_fused(p, q_mcts, lam=lam, floor=floor, margin=margin)
    if not q_mcts:
        return SC.choose_fused(p, q_vphi, lam=lam, floor=floor, margin=margin)

    combined_q: dict[str, float] = {}
    for a in set(q_mcts) | set(q_vphi):
        if a not in p:
            continue
        qm = q_mcts.get(a)
        qv = q_vphi.get(a)
        if qm is not None and qv is not None and math.isfinite(qm) and math.isfinite(qv):
            combined_q[a] = (1.0 - alpha) * float(qm) + alpha * float(qv)
        elif qv is not None and math.isfinite(qv):
            combined_q[a] = float(qv)
        elif qm is not None and math.isfinite(qm):
            combined_q[a] = float(qm)
    return SC.choose_fused(p, combined_q, lam=lam, floor=floor, margin=margin)
