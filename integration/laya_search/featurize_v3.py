"""EP-247 / D-223 (EX-221): V_phi v3 dynamic future-relevant features (pure stdlib, non-invasive over `featurize.py`).

Extracts all `featurize.extract_raw(state)` tensors PLUS exact zero-sum antisymmetric v3 dynamic channels that
`featurize.py` omitted:
- `v3_mon` (`12 x 4` floats, active-first per side):
    0: `heal_pp_frac`      — max remaining PP fraction across recovery moves (pp / 8.0 clipped [0,1]; 0 if no heal or 0 PP)
    1: `min_pp_frac`       — min remaining PP fraction across known moves (pp / 8.0 clipped [0,1]; captures PP exhaustion)
    2: `just_used_heal`    — 1.0 iff active mon and `side.last_used_move` points to a recovery move
    3: `just_used_protect` — 1.0 iff active mon and (`side.last_used_move` points to Protect-class OR 'protect' volatile)
- `v3_glob` (`8` floats = side_one[4] + side_two[4], exact mirror involution under side swap):
    0 / 4: `act_just_healed`    — 1.0 if side active just used a recovery move
    1 / 5: `act_just_protected` — 1.0 if side active just used a Protect-class move (consecutive Protect 66.7% fail risk!)
    2 / 6: `act_just_setup`     — 1.0 if side active just used a setup/boosting move
    3 / 7: `team_heal_pp`       — mean `heal_pp_frac` across alive Pokemon on that side
"""
from __future__ import annotations

import copy

from . import featurize as F

V3_MON_DIM = 4
V3_GLOB_DIM = 8

HEAL_MOVES = frozenset((
    'roost', 'recover', 'rest', 'softboiled', 'slackoff', 'synthesis',
    'moonlight', 'morningsun', 'shoreup', 'strengthsap', 'wish',
    'milkdrink', 'healorder', 'lifedew', 'junglehealing', 'lunarblessing',
))
PROTECT_MOVES = frozenset((
    'protect', 'detect', 'spikyshield', 'banefulbunker', 'kingsshield',
    'obstruct', 'silktrap', 'burningbulwark',
))
SETUP_MOVES = frozenset((
    'swordsdance', 'nastyplot', 'calmmind', 'dragondance', 'quiverdance',
    'bulkup', 'irondefense', 'curse', 'shellsmash', 'agility', 'rockpolish',
    'autotomize', 'shiftgear', 'victorydance', 'tidyup', 'coil', 'cosmicpower',
    'bellydrum', 'tailglow', 'clangoroussoul', 'filletaway', 'growth', 'workup',
    'honeclaws', 'amnesia', 'acidarmor', 'barrier', 'shelter', 'takeheart',
))


def _last_move_id(side, active_pokemon) -> str:
    """Resolve `side.last_used_move` (e.g. `'move:2'` or `'protect'`) to normalized move ID, or `'none'`."""
    lm = getattr(side, 'last_used_move', None)
    if not lm:
        return 'none'
    s = str(lm).strip().lower()
    if s.startswith('move:'):
        try:
            idx = int(s.split(':', 1)[1])
            moves = list(getattr(active_pokemon, 'moves', None) or ())
            if 0 <= idx < len(moves):
                return F.norm(getattr(moves[idx], 'id', None))
        except Exception:
            return 'none'
        return 'none'
    if s.startswith('switch:'):
        return 'none'
    return F.norm(s)


def _side_v3_features(side) -> tuple[list[list[float]], list[float]]:
    ordered = F._ordered_pokemon(side)
    vols = {F.norm(v) for v in (getattr(side, 'volatile_statuses', None) or ())}
    act_mon = ordered[0][0] if ordered else None
    last_mid = _last_move_id(side, act_mon) if act_mon is not None else 'none'

    act_just_healed = 1.0 if last_mid in HEAL_MOVES else 0.0
    act_just_protected = 1.0 if (last_mid in PROTECT_MOVES or 'protect' in vols) else 0.0
    act_just_setup = 1.0 if last_mid in SETUP_MOVES else 0.0

    mon_rows: list[list[float]] = []
    alive_cnt = 0.0
    heal_pp_sum = 0.0

    for p, is_active in ordered:
        if p is None or float(getattr(p, 'hp', 0)) <= 0.0:
            mon_rows.append([0.0] * V3_MON_DIM)
            continue
        alive_cnt += 1.0
        moves = list(getattr(p, 'moves', None) or ())
        heal_pps = []
        all_pps = []
        for m in moves:
            mid = F.norm(getattr(m, 'id', None))
            if mid == 'none':
                continue
            pp = max(0.0, float(getattr(m, 'pp', 0)))
            all_pps.append(min(1.0, pp / 8.0))
            if mid in HEAL_MOVES:
                heal_pps.append(min(1.0, pp / 8.0))
        heal_pp_frac = max(heal_pps) if heal_pps else 0.0
        min_pp_frac = min(all_pps) if all_pps else 1.0
        heal_pp_sum += heal_pp_frac
        mon_rows.append([
            heal_pp_frac,
            min_pp_frac,
            act_just_healed if is_active else 0.0,
            act_just_protected if is_active else 0.0,
        ])

    team_heal_pp = heal_pp_sum / max(1.0, alive_cnt)
    side_glob = [act_just_healed, act_just_protected, act_just_setup, team_heal_pp]
    return mon_rows, side_glob


def extract_raw_v3(state) -> dict:
    """Extract base `featurize.extract_raw(state)` + v3 dynamic PP & recent-move channels."""
    base = F.extract_raw(state)
    m1, g1 = _side_v3_features(state.side_one)
    m2, g2 = _side_v3_features(state.side_two)
    base['v3_mon'] = m1 + m2       # 12 x 4
    base['v3_glob'] = g1 + g2      # 8
    return base


def default_v3_arrays() -> tuple[list[list[float]], list[float]]:
    return [[0.0] * V3_MON_DIM for _ in range(F.NUM_SLOTS)], [0.0] * V3_GLOB_DIM


def swap_raw_v3(raw: dict) -> dict:
    """Exact side_one <-> side_two involution for `extract_raw_v3` dicts."""
    out = F.swap_raw(raw)
    v3m = raw.get('v3_mon')
    v3g = raw.get('v3_glob')
    if v3m is not None:
        out['v3_mon'] = [list(r) for r in v3m[6:12]] + [list(r) for r in v3m[0:6]]
    if v3g is not None:
        out['v3_glob'] = list(v3g[4:8]) + list(v3g[0:4])
    return out


def board_advantage(raw: dict) -> float:
    """Exact antisymmetric scalar board advantage in `[-1, 1]`: `0.6 * alive_diff + 0.4 * hp_sum_diff`."""
    gn = raw['global_num']
    # global_num[22] = (s1_alive - s2_alive) / 6.0, global_num[23] = (s1_hp_sum - s2_hp_sum) / 6.0
    val = 0.6 * float(gn[22]) + 0.4 * float(gn[23])
    return max(-1.0, min(1.0, val))


def active_boost_diff(raw: dict) -> float:
    """Exact antisymmetric active net positive boost advantage in `[-1, 1]`."""
    mn = raw['mon_num']
    # indices 21..25 are [atk, def, spa, spd, spe] / 6.0 for active mon (slot 0 = s1, slot 6 = s2)
    s1_pos = sum(max(0.0, float(mn[0][i])) for i in range(21, 26))
    s2_pos = sum(max(0.0, float(mn[6][i])) for i in range(21, 26))
    return max(-1.0, min(1.0, (s1_pos - s2_pos) / 2.0))


def patch_raw_v3_opp_heal(raw: dict, heal_frac: float = 0.25) -> dict:
    """Apply +25% opp active heal while preserving v3 fields."""
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
