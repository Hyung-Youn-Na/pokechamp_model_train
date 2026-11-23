"""EP-242: 2b lead selection module (opponent lead prior x 6x6 matchup EV + model prior reweighting + min_p sampling).

Offline diagnostic on all 104 EX-203 ladder games showed that pure argmax locks Raging Bolt at 93.3% (1500+ human
bad-lead rate 42.1%, worst-case MinMax -0.534), whereas naive sampling or pure 6x6 Nash hurts EV on favorable bot
leads. Reweighting the model's lead probabilities by `exp(EV / tau)` against a hazard/Focus-Sash opponent lead prior
and sampling over `min_p`-filtered candidates preserves overall EV (+0.382 -> +0.381) while improving 1500+ human EV
(+0.157 -> +0.190), bad-lead rate (42.1% -> 33.5%), and MinMax (-0.534 -> -0.317).

Pure Python stdlib (no numpy dependency). Designed to be imported standalone, used in `laya-play` / battle runners,
or attached non-invasively to a serving policy via `with_lead_2b(policy_class)` (leaving `probabilities` and `choice`
unchanged while attaching a `lead_2b` advisory payload on `turn 0 | lead` requests).
"""
from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path

from integration.laya_imitation import features, features_v3, features_v5
from integration.laya_threat import spreads
from integration.laya_v10 import strategy

HERE = Path(__file__).resolve().parent
VERSION = 'laya-lead-2b-v1'
DEFAULT_TAU = 0.25
DEFAULT_MIN_P = 0.20
DEFAULT_TEMP = 1.0

HAZARD_MOVES = frozenset(('stealthrock', 'spikes', 'toxicspikes', 'stickyweb'))
COMMON_LEADS = frozenset((
    'glimmora', 'ribombee', 'samurotthisui', 'landorustherian', 'tinglu',
    'irontreads', 'greattusk', 'deoxyspeed', 'ninetalesalola', 'pelipper',
))


def cell_score(cell: dict) -> float:
    """Pairwise lead matchup score in [-1.0, +1.0] from a `strategy.matchup` cell `{out, takes, speed}`."""
    out = float(cell.get('out') or 0.0)
    takes = float(cell.get('takes') or 0.0)
    spd = cell.get('speed')
    my_hits = 99.0 if out <= 1e-6 else float(math.ceil(100.0 / out - 1e-9))
    opp_hits = 99.0 if takes <= 1e-6 else float(math.ceil(100.0 / takes - 1e-9))
    faster = spd == 'faster'
    tie = spd == 'tie'

    trade = (min(out, 100.0) - min(takes, 100.0)) / 100.0
    race = 0.0
    if my_hits < 90.0 or opp_hits < 90.0:
        eff_opp = opp_hits + (0.5 if faster else (-0.5 if not tie else 0.0))
        race = max(-1.0, min(1.0, (eff_opp - my_hits) / 3.0))

    ohko_pen = -0.45 if (takes >= 95.0 and not (faster and out >= 95.0)) else 0.0
    ohko_bon = 0.35 if (out >= 95.0 and faster) else 0.0
    score = 0.55 * race + 0.45 * trade + ohko_pen + ohko_bon
    return max(-1.0, min(1.0, score))


def opp_lead_prior(opp_team, usage_table=None, species_key_fn=None) -> dict[int, float]:
    """Heuristic opponent lead distribution `{opp_slot: prob}` weighting hazard setters, Focus Sash, and common leads."""
    if not opp_team:
        return {}
    if usage_table is None:
        usage_table = features_v3.usage()
    if species_key_fn is None:
        species_key_fn = features_v3.species_key

    raw = {}
    for mon in opp_team:
        w = 1.0
        sp = mon['species']
        key = species_key_fn(sp)
        u = usage_table.get(key) if key else None
        if u:
            moves = u.get('moves') or {}
            items = u.get('items') or {}
            haz_p = max((float(moves.get(hm, 0.0)) for hm in HAZARD_MOVES), default=0.0)
            sash_p = float(items.get('focussash', 0.0))
            w += 2.5 * float(moves.get('stickyweb', 0.0)) + 2.0 * sash_p + 1.2 * haz_p
            if sp in COMMON_LEADS:
                w += 1.0
        raw[mon['slot']] = w

    total = sum(raw.values())
    if total <= 0.0:
        n = len(opp_team)
        return {mon['slot']: 1.0 / n for mon in opp_team}
    return {slot: w / total for slot, w in raw.items()}


def min_p_filter(probs: dict[str, float], min_p: float = DEFAULT_MIN_P, temperature: float = DEFAULT_TEMP) -> dict[str, float]:
    """Filter actions below `min_p * max(probs)`, apply temperature, and renormalize. Always keeps the top action."""
    if not probs:
        return {}
    if temperature <= 0:
        raise ValueError('temperature must be > 0')
    if not 0.0 <= min_p <= 1.0:
        raise ValueError('min_p must be in [0, 1]')
    positive = {k: float(v) for k, v in probs.items() if v > 0.0}
    if not positive:
        keys = sorted(probs)
        return {keys[0]: 1.0}
    top_action = max(sorted(positive), key=lambda k: positive[k])
    cutoff = min_p * positive[top_action]
    kept = {k: v for k, v in positive.items() if v >= cutoff or k == top_action}
    # Log-space temperature scaling for stability
    mx = max(kept.values())
    scaled = {k: (v / mx) ** (1.0 / temperature) for k, v in kept.items()}
    total = sum(scaled.values())
    return {k: v / total for k, v in scaled.items()}


def reweight_lead(
    probabilities: dict[str, float],
    value,
    calc=None,
    *,
    tau: float = DEFAULT_TAU,
    min_p: float = DEFAULT_MIN_P,
    temperature: float = DEFAULT_TEMP,
    matchup_table=None,
    usage_table=None,
    species_key_fn=None,
) -> dict | None:
    """Compute the 2b reweighted lead distribution for a validated `ImitationInput`.

    Returns `None` if `value` is not a `lead` decision. Otherwise returns a JSON-serializable dict:
        {version, tau, min_p, temperature, top, weights, raw_weights, ev, opp_prior}
    """
    if tau <= 0:
        raise ValueError('tau must be > 0')
    _, view = features_v5.resolved(value)
    if view.get('decision_kind') != 'lead':
        return None
    lead_probs = {k: float(v) for k, v in probabilities.items() if k.startswith('lead:')}
    if not lead_probs:
        return None

    own_team = sorted(view['own_team'], key=lambda m: m['slot'])
    opp_team = sorted(view['opponent_team'], key=lambda m: m['slot'])
    if not own_team or not opp_team:
        return None

    own_calc = False
    if matchup_table is None:
        if calc is None:
            calc = features.Calc()
            own_calc = True
        try:
            with spreads.patched():
                matchup_table = strategy.matchup(view, calc)
        finally:
            if own_calc:
                calc.close()

    q_opp = opp_lead_prior(opp_team, usage_table=usage_table, species_key_fn=species_key_fn)
    ev_by_action: dict[str, float] = {}
    for om in own_team:
        aid = f"lead:{om['slot']}"
        if aid not in lead_probs:
            continue
        ev = 0.0
        for pm in opp_team:
            cell = matchup_table.get((om['slot'], pm['slot']))
            if cell is not None:
                ev += q_opp.get(pm['slot'], 0.0) * cell_score(cell)
        ev_by_action[aid] = ev

    if not ev_by_action:
        return None

    # Numerically stable prior * exp(ev / tau)
    max_ev = max(ev_by_action.values())
    unnorm = {
        aid: max(lead_probs.get(aid, 0.0), 0.0) * math.exp((ev - max_ev) / tau)
        for aid, ev in ev_by_action.items()
    }
    total = sum(unnorm.values())
    if total <= 0.0:
        raw_weights = {aid: 1.0 / len(ev_by_action) for aid in ev_by_action}
    else:
        raw_weights = {aid: w / total for aid, w in unnorm.items()}

    weights = min_p_filter(raw_weights, min_p=min_p, temperature=temperature)
    top = max(sorted(weights), key=lambda k: weights[k])
    opp_prior_named = {pm['species']: round(q_opp.get(pm['slot'], 0.0), 6) for pm in opp_team}
    return dict(
        version=VERSION,
        tau=float(tau),
        min_p=float(min_p),
        temperature=float(temperature),
        top=top,
        weights={k: round(v, 6) for k, v in sorted(weights.items())},
        raw_weights={k: round(v, 6) for k, v in sorted(raw_weights.items())},
        ev={k: round(v, 6) for k, v in sorted(ev_by_action.items())},
        opp_prior=opp_prior_named,
    )


class Lead2bSampler:
    """Stateful sampler for 2b lead weights with reproducible RNG seeding."""

    def __init__(self, tau: float = DEFAULT_TAU, min_p: float = DEFAULT_MIN_P,
                 temperature: float = DEFAULT_TEMP, seed: int | None = None):
        if tau <= 0:
            raise ValueError('tau must be > 0')
        if temperature <= 0:
            raise ValueError('temperature must be > 0')
        if not 0.0 <= min_p <= 1.0:
            raise ValueError('min_p must be in [0, 1]')
        self.tau = float(tau)
        self.min_p = float(min_p)
        self.temperature = float(temperature)
        self.seed = seed if seed is not None else random.SystemRandom().randrange(2 ** 32)
        self.rng = random.Random(self.seed)

    def choose_from_weights(self, weights: dict[str, float]) -> str:
        actions = sorted(weights)
        if not actions:
            raise ValueError('empty lead weights')
        return self.rng.choices(actions, weights=[weights[a] for a in actions], k=1)[0]

    def choose(self, probabilities: dict[str, float], value, calc=None, *, matchup_table=None):
        """Return `(choice, info)` for a `lead` decision, or `(argmax, None)` for non-lead decisions."""
        info = reweight_lead(
            probabilities, value, calc=calc,
            tau=self.tau, min_p=self.min_p, temperature=self.temperature,
            matchup_table=matchup_table,
        )
        if info is None:
            argmax = max(sorted(probabilities), key=lambda k: probabilities[k])
            return argmax, None
        choice = self.choose_from_weights(info['weights'])
        return choice, dict(info, choice=choice, seed=self.seed)


def choose_lead(
    probabilities: dict[str, float],
    value,
    calc=None,
    *,
    tau: float = DEFAULT_TAU,
    min_p: float = DEFAULT_MIN_P,
    temperature: float = DEFAULT_TEMP,
    seed: int | None = None,
    matchup_table=None,
):
    """One-shot functional wrapper around `Lead2bSampler.choose`."""
    sampler = Lead2bSampler(tau=tau, min_p=min_p, temperature=temperature, seed=seed)
    return sampler.choose(probabilities, value, calc=calc, matchup_table=matchup_table)


def identity() -> dict:
    return dict(
        version=VERSION,
        tau=DEFAULT_TAU,
        min_p=DEFAULT_MIN_P,
        temperature=DEFAULT_TEMP,
        file='lead_policy.py',
        sha256=hashlib.sha256((HERE / 'lead_policy.py').read_bytes()).hexdigest(),
    )


def with_lead_2b(policy_class, *, calc=None, tau: float = DEFAULT_TAU,
                 min_p: float = DEFAULT_MIN_P, temperature: float = DEFAULT_TEMP):
    """Wrap a `Policy` class so `/evaluate` responses attach a `lead_2b` advisory dict on `lead` decisions.

    `probabilities` and `choice` remain the unchanged model argmax outputs (same contract as `laya_v11.serve.guarded`),
    so callers that ignore `lead_2b` behave identically and callers that opt in can sample from `response['lead_2b']['weights']`.
    """

    class Lead2bPolicy(policy_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._lead_calc = calc
            self._owns_lead_calc = False

        def _get_lead_calc(self):
            if self._lead_calc is None:
                self._lead_calc = features.Calc()
                self._owns_lead_calc = True
            return self._lead_calc

        def predict(self, value):
            out = super().predict(value)
            info = reweight_lead(
                out['probabilities'], value, calc=self._get_lead_calc(),
                tau=tau, min_p=min_p, temperature=temperature,
            )
            if info is not None:
                out = dict(out, lead_2b=info)
            return out

    return Lead2bPolicy
