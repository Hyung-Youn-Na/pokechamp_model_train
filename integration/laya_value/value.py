"""EP-239 EX-199: one-turn value of laya's candidates in foul-play engine points (foul-play venv; `poke_engine` only).

`values(samples, mine, foe)` is `laya_foe.read.values` with the score replaced by the engine's own evaluation:
value(mine) = sum over samples of chance * sum over foe actions (q >= FOE_FLOOR, renormalised) of q * sum over
branches of percentage * (evaluate(after) - evaluate(before)), divided by the total chance; `evaluate` is
`laya_value.evaluate` (poke-engine 0.0.48 `genx/evaluate.rs`). The opponent distribution is mapped onto each sample
by `laya_foe.read.foe_choices` (unchanged).
"""
from __future__ import annotations

from integration.laya_foe.read import FOE_FLOOR, foe_choices

from .evaluate import evaluate


def values(samples, mine, foe):
    from poke_engine import State, generate_instructions
    acc = {a: 0.0 for a in mine}
    weight = 0.0
    errors = 0
    for text, chance in samples:
        state = State.from_string(text)
        base = evaluate(state)
        dist = {b: p for b, p in foe_choices(state, foe).items() if p >= FOE_FLOOR}
        z = sum(dist.values())
        if not dist or z <= 0:
            continue
        row = {}
        try:
            for a, choice in mine.items():
                v = 0.0
                for b, p in dist.items():
                    for br in generate_instructions(state, choice, b):
                        v += p / z * br.percentage / 100.0 * (evaluate(state.apply_instructions(br)) - base)
                row[a] = v
        except Exception:
            errors += 1
            continue
        for a, v in row.items():
            acc[a] += chance * v
        weight += chance
    if weight <= 0:
        return None, errors
    return {a: v / weight for a, v in acc.items()}, errors
