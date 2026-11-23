"""EP-238 EX-197: one-turn read on poke-engine states (foul-play venv; `poke_engine` only).

`values(samples, mine, foe)`:
- samples: [(poke-engine state string, chance)] — foul-play's own set samples of the decision (`laya_regret.search
  .sample_states`), side one = the bot;
- mine: {laya action id: engine choice} for the candidate actions (`move` / `move-tera` / the Pokemon name for a
  switch, as `render_fp1.engine_choice` gives them);
- foe: {opponent option id: probability} from the opponent question (`foe:move:<m>`, `foe:switch:<species>`,
  `foe:move:other`).
Per sample, the opponent distribution is mapped onto that sample's active moves and live reserves: a listed move the
sample's set lacks, and "other", share their mass equally over the sample's moves not listed; switches match by
id; the rest is renormalised. Each (mine, foe) pair with foe probability >= FOE_FLOOR is expanded one turn with
`generate_instructions`; every branch is applied (`apply_instructions` returns a new state) and scored with
`score` (side one minus side two).
value(mine) = sum over samples of chance * sum over foe actions of p * sum over branches of percentage * score,
divided by the total chance. `score`: per Pokemon hp fraction + ALIVE if not fainted - STATUS if statused; active
boosts (atk, def, spa, spd, spe) * BOOST each, capped at 6 stages.
"""
from __future__ import annotations

ALIVE = 0.25
STATUS = 0.1
BOOST = 0.04
FOE_FLOOR = 0.02
BOOSTS = ('attack_boost', 'defense_boost', 'special_attack_boost', 'special_defense_boost', 'speed_boost')


def _side_score(side):
    total = 0.0
    for i, p in enumerate(side.pokemon):
        if p.maxhp <= 0:
            continue
        if p.hp > 0:
            total += p.hp / p.maxhp + ALIVE
            if str(p.status).lower() not in ('none', 'pokemonstatus.none', ''):
                total -= STATUS
    for b in BOOSTS:
        total += BOOST * max(-6, min(6, getattr(side, b)))
    return total


def score(state):
    return _side_score(state.side_one) - _side_score(state.side_two)


def _active(side):
    return side.pokemon[int(side.active_index)]


def foe_choices(state, foe):
    """{engine choice: probability} for side two of this sample."""
    side = state.side_two
    active = _active(side)
    moves = [m.id for m in active.moves if m.id and m.id.lower() not in ('none', '')]
    by_name = {m.lower(): m for m in moves}
    listed = {k.split(':', 2)[2] for k in foe if k.startswith('foe:move:') and k != 'foe:move:other'}
    unlisted = [m for m in moves if m.lower() not in listed]
    out, spill = {}, 0.0
    for key, p in foe.items():
        if key == 'foe:move:other':
            spill += p
        elif key.startswith('foe:move:'):
            m = by_name.get(key.split(':', 2)[2])
            if m is not None:
                out[m] = out.get(m, 0.0) + p
            else:
                spill += p
        elif key.startswith('foe:switch:'):
            sp = key.split(':', 2)[2]
            for i, mon in enumerate(side.pokemon):
                if i != int(side.active_index) and mon.hp > 0 and mon.id.lower() == sp:
                    out[mon.id] = out.get(mon.id, 0.0) + p
                    break
    targets = unlisted or moves
    for m in targets:
        out[m] = out.get(m, 0.0) + spill / len(targets)
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total > 0 else {}


def values(samples, mine, foe):
    from poke_engine import State, generate_instructions
    acc = {a: 0.0 for a in mine}
    weight = 0.0
    errors = 0
    for text, chance in samples:
        state = State.from_string(text)
        dist = {b: p for b, p in foe_choices(state, foe).items() if p >= FOE_FLOOR}
        z = sum(dist.values())
        if not dist or z <= 0:
            continue
        ok = True
        row = {}
        for a, choice in mine.items():
            v = 0.0
            for b, p in dist.items():
                try:
                    branches = generate_instructions(state, choice, b)
                except Exception:
                    errors += 1
                    ok = False
                    break
                for br in branches:
                    v += p / z * br.percentage / 100.0 * score(state.apply_instructions(br))
            if not ok:
                break
            row[a] = v
        if not ok:
            continue
        for a, v in row.items():
            acc[a] += chance * v
        weight += chance
    if weight <= 0:
        return None, errors
    return {a: v / weight for a, v in acc.items()}, errors
