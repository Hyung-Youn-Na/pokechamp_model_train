"""EP-243 / D-219 (2-A): Multi-turn MCTS root-Q evaluation and KL-regularized laya prior fusion.

Pure fusion helpers (`choose_fused`, `served_probs`) run in any Python environment without `poke_engine` so unit
tests and serving (`laya` venv) can import them directly. Engine search (`search_mcts_samples`) imports `poke_engine`
lazily (used inside the `foul-play` venv subprocess worker).
"""
from __future__ import annotations

from collections import defaultdict
import math
import time

VERSION = 'laya-search-2a-v1'
MCTS_ITERATIONS = 5000
MCTS_DURATION_MS = 5000
PRIOR_LAMBDA = 0.03
PRIOR_FLOOR = 1e-4
MARGIN = 0.015
GPU0_UUID = 'GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4'
GPU1_UUID = 'GPU-c7e2d577-573f-0412-1ed6-ad6648efa454'
ALLOWED_GPU_UUIDS = (GPU0_UUID, GPU1_UUID)


def choose_fused(
    p: dict[str, float],
    q_mcts: dict[str, float] | None,
    *,
    lam: float = PRIOR_LAMBDA,
    floor: float = PRIOR_FLOOR,
    margin: float = MARGIN,
) -> tuple[str, dict[str, float], float]:
    """KL-regularized policy improvement over MCTS multi-turn root Q and laya prior p.

    `score(a) = Q_mcts(a) + lam * ln(max(p(a), floor))` for every legal action `a` scored by MCTS.
    Overrides `laya`'s argmax only when `score(best) - score(argmax) > margin` (prevents random noise flips on ties
    while rescuing multi-turn blunders even when `p(best)` is small, e.g., 0.05 on 3v1 Kingambit).

    Returns `(pick, scores, delta)` where `delta = scores[best] - scores[argmax]` (0.0 if fallback).
    """
    if not p:
        raise ValueError('empty action distribution p')
    argmax = max(sorted(p), key=lambda a: p[a])
    if not q_mcts:
        return argmax, {}, 0.0
    scores: dict[str, float] = {}
    for a, q in q_mcts.items():
        if a in p and math.isfinite(q):
            scores[a] = float(q) + float(lam) * math.log(max(float(p[a]), float(floor)))
    if not scores:
        return argmax, {}, 0.0
    best = max(sorted(scores), key=lambda a: (scores[a], p.get(a, 0.0)))
    if argmax not in scores:
        # Rare: argmax had 0 visits or unmapped; only override if best beats conservative neutral Q=0.5 baseline
        ref = 0.5 + float(lam) * math.log(max(float(p[argmax]), float(floor)))
        delta = scores[best] - ref
        return (best if delta > margin else argmax), scores, delta
    delta = scores[best] - scores[argmax]
    pick = best if (best != argmax and delta > margin) else argmax
    return pick, scores, delta


def served_probs(p: dict[str, float], pick: str) -> dict[str, float]:
    """Return `p` with `pick` and `argmax` probabilities swapped so an argmax player executes `pick`."""
    out = {k: float(v) for k, v in p.items()}
    argmax = max(sorted(out), key=lambda a: out[a])
    if pick != argmax and pick in out:
        out[pick], out[argmax] = out[argmax], out[pick]
        if max(sorted(out), key=lambda a: out[a]) != pick:
            out[pick] += 1e-9
            s = sum(out.values())
            out = {k: v / s for k, v in out.items()}
    return out


def search_mcts_samples(
    samples: list[tuple[str, float]],
    mapping: dict[str, str],
    *,
    iterations: int = MCTS_ITERATIONS,
    duration_ms: int = MCTS_DURATION_MS,
) -> dict:
    """Run exact-iteration Rust MCTS across foul-play set samples and aggregate per-action Q and visit share.

    Must be called inside the `foul-play` venv (`poke_engine` available). Any single-sample `poke_engine` panic or
    exception is isolated (counted in `errors`, other samples still used).
    """
    import poke_engine

    inverse: dict[str, list[str]] = defaultdict(list)
    for aid, ch in mapping.items():
        inverse[ch].append(aid)

    started = time.monotonic()
    q_sum: dict[str, float] = defaultdict(float)
    q_w: dict[str, float] = defaultdict(float)
    v_sum: dict[str, float] = defaultdict(float)
    root_num = 0.0
    tot_w = 0.0
    unmapped_w = 0.0
    errors = 0
    visit_counts: list[int] = []

    for text, chance in samples:
        chance = float(chance)
        if chance <= 0.0:
            continue
        try:
            st = poke_engine.State.from_string(text)
            res = poke_engine.monte_carlo_tree_search(st, int(duration_ms), iterations=int(iterations), threads=1)
        except BaseException:
            # Isolate Rust pyo3_runtime.PanicException (inherits BaseException) per sample
            errors += 1
            continue
        total = int(res.total_visits)
        if total <= 0:
            errors += 1
            continue
        visit_counts.append(total)
        sample_score = 0.0
        for o in res.side_one:
            v = int(o.visits)
            if v <= 0:
                continue
            q_val = float(o.total_score) / v
            share = v / total
            sample_score += share * q_val
            aids = inverse.get(o.move_choice)
            if not aids:
                unmapped_w += chance * share
                continue
            for aid in aids:
                q_sum[aid] += chance * q_val
                q_w[aid] += chance
                v_sum[aid] += chance * share / len(aids)
        root_num += chance * sample_score
        tot_w += chance

    if tot_w <= 0.0:
        return dict(
            q_mcts=None, v_mcts=None, root_q=None, unmapped=0.0,
            samples=len(samples), used_samples=0, errors=errors,
            iterations=visit_counts, seconds=round(time.monotonic() - started, 4),
        )

    q_mcts = {a: round(q_sum[a] / q_w[a], 6) for a in sorted(q_w) if q_w[a] > 0.0}
    v_mcts = {a: round(v_sum[a] / tot_w, 6) for a in sorted(v_sum)}
    return dict(
        q_mcts=q_mcts,
        v_mcts=v_mcts,
        root_q=round(root_num / tot_w, 6),
        unmapped=round(unmapped_w / tot_w, 6),
        samples=len(samples),
        used_samples=len(visit_counts),
        errors=errors,
        iterations=visit_counts,
        seconds=round(time.monotonic() - started, 4),
    )
