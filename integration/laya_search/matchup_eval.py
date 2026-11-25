"""Search + Future-Value Matchup Assessment (`MCTS 50k` + `EX-221 V_phi v3 2-ply`) replacing calc-based `duel: win/lose`.

Why:
- Deterministic 1v1 damage-calc `duel: me X hits vs opp Y hits -> win|lose` ignores opponent Terastallization,
  setup moves, status, hazards, crits, and switch tempo — causing misleading `win`/`lose` labels.
- Combining `MCTS 50k` (`0.45`) and Future-Aware `V_phi v3 2-ply` (`0.55`) naturally evaluates opponent Tera,
  setup, status, and switch tempo, producing a calibrated graded matchup assessment:
  `very favorable` / `favorable` / `even` / `unfavorable` / `very unfavorable`.

Used consistently across:
1. `EX-226` (Way B) prompt injection: strips calc-based `duel:` and injects `matchup: ...` + `eval: mcts ... || vphi ...`.
2. `Way A v2` (`choose_way_a_v2`): replaces calc-based `duel_lose` flag with search+value `matchup_unfavorable`.
"""
from __future__ import annotations

import math

ALPHA_VPHI = 0.55
ALPHA_MCTS = 0.45

# Calibrated on 2,840 held-out hard turns (Q_comb = 0.45*MCTS50k + 0.55*V_phi3_2ply):
#   very unfavorable (<-0.050): ~12%, unfavorable [-0.050,-0.015): ~15%,
#   even [-0.015,+0.015]: ~15%, favorable (+0.015,+0.050]: ~18%, very favorable (>+0.050): ~40%.
VERY_UNFAV_THRESH = -0.050
UNFAV_THRESH = -0.015
FAV_THRESH = 0.015
VERY_FAV_THRESH = 0.050


def strip_calc_duel(state: str) -> str:
    """Remove deterministic calculator-based `duel: ...` lines from a rendered state prompt."""
    if not state or 'duel:' not in state:
        return state
    lines = [ln for ln in state.splitlines() if not ln.startswith('duel:')]
    return '\n'.join(lines)


def _combined_q(
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    valid_ids: set[str] | None = None,
    absorb_penalties: dict[str, float] | None = None,
) -> dict[str, float]:
    pen = absorb_penalties or {}
    qm = (
        {a: float(v) - float(pen.get(a, 0.0)) for a, v in q_mcts.items() if math.isfinite(v) and (valid_ids is None or a in valid_ids)}
        if q_mcts else {}
    )
    qv = (
        {a: float(v) for a, v in q_vphi.items() if math.isfinite(v) and (valid_ids is None or a in valid_ids)}
        if q_vphi else {}
    )
    if qm and qv:
        common = [a for a in qm if a in qv]
        if common:
            return {a: ALPHA_MCTS * qm[a] + ALPHA_VPHI * qv[a] for a in common}
    return qv or qm


def _label_from_diff(diff: float) -> str:
    if diff < VERY_UNFAV_THRESH:
        return 'very unfavorable'
    if diff < UNFAV_THRESH:
        return 'unfavorable'
    if diff <= FAV_THRESH:
        return 'even'
    if diff <= VERY_FAV_THRESH:
        return 'favorable'
    return 'very favorable'


def _label_from_abs(stay_q: float) -> str:
    if stay_q < 0.30:
        return 'very unfavorable'
    if stay_q < 0.44:
        return 'unfavorable'
    if stay_q <= 0.56:
        return 'even'
    if stay_q <= 0.70:
        return 'favorable'
    return 'very favorable'


def assess_matchup(
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    valid_ids: set[str] | list[str] | None = None,
    absorb_penalties: dict[str, float] | None = None,
) -> dict | None:
    """Compute graded matchup advantage purely from MCTS 50k + V_phi v3 2-ply stay vs switch probabilities."""
    vset = set(valid_ids) if valid_ids is not None else None
    comb = _combined_q(q_mcts, q_vphi, valid_ids=vset, absorb_penalties=absorb_penalties)
    if not comb:
        return None
    stays = [v for a, v in comb.items() if not a.startswith('switch:')]
    switches = [v for a, v in comb.items() if a.startswith('switch:')]
    if not stays:
        # Forced switch (no stay actions available)
        best_sw = max(switches)
        return dict(
            label=_label_from_abs(best_sw),
            stay_q=None,
            switch_q=round(best_sw, 4),
            stay_vs_switch=None,
            is_unfavorable=best_sw < 0.44,
            source='mcts+vphi' if (q_mcts and q_vphi) else ('vphi' if q_vphi else 'mcts'),
        )
    best_stay = max(stays)
    if switches:
        best_sw = max(switches)
        diff = best_stay - best_sw
        label = _label_from_diff(diff)
        return dict(
            label=label,
            stay_q=round(best_stay, 4),
            switch_q=round(best_sw, 4),
            stay_vs_switch=round(diff, 4),
            is_unfavorable=label in ('unfavorable', 'very unfavorable'),
            source='mcts+vphi' if (q_mcts and q_vphi) else ('vphi' if q_vphi else 'mcts'),
        )
    label = _label_from_abs(best_stay)
    return dict(
        label=label,
        stay_q=round(best_stay, 4),
        switch_q=None,
        stay_vs_switch=None,
        is_unfavorable=label in ('unfavorable', 'very unfavorable'),
        source='mcts+vphi' if (q_mcts and q_vphi) else ('vphi' if q_vphi else 'mcts'),
    )


def render_matchup_line(
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    valid_ids: set[str] | list[str] | None = None,
    absorb_penalties: dict[str, float] | None = None,
) -> str:
    """Render compact search+value matchup line replacing calc-based `duel: ... -> win|lose`."""
    info = assess_matchup(q_mcts, q_vphi, valid_ids=valid_ids, absorb_penalties=absorb_penalties)
    if info is None or info['stay_q'] is None:
        return ''
    sq = round(100.0 * info['stay_q'])
    if info['switch_q'] is not None and info['stay_vs_switch'] is not None:
        wq = round(100.0 * info['switch_q'])
        dp = round(100.0 * info['stay_vs_switch'])
        diff_s = '=' if dp == 0 else f'{dp:+d}%'
        return f"matchup: {info['label']} (stay {sq}% vs switch {wq}%, {diff_s})"
    return f"matchup: {info['label']} (stay {sq}%, no switch)"
