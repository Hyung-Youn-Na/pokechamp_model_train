"""EP-243 / D-219 (2-B): Pure-stdlib feature extractor for `poke_engine.State` -> numeric + entity tensors.

Zero dependency on `torch` or `poke_engine` at import time so both the `foul-play` venv (data extraction and online
search worker) and the `laya` venv (GPU training and serving) can import and share identical feature semantics.

Layout per state:
- `mon_num`: 12 x 29 floats (slots 0..5 = side_one with active at index 0; slots 6..11 = side_two with active at index 6)
- `mon_cat`: 12 x 10 string tokens (or int IDs after `Vocab.encode_cat`):
    [species, ability, item, type1, type2, tera_type, move1, move2, move3, move4]
- `global_num`: 35 floats (side_one 11 + side_two 11 + diffs 4 + field 9)

Exact side-swap involution (`swap_raw` / `swap_arrays`) enables exact zero-sum antisymmetry:
    V_sym(s) = sigmoid(0.5 * (f(s) - f(swap(s))))   ==>   V_sym(swap(s)) == 1 - V_sym(s).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MON_NUM_DIM = 29
MON_CAT_DIM = 10
GLOBAL_NUM_DIM = 35
NUM_SLOTS = 12

TYPES = (
    'none', 'normal', 'fire', 'water', 'electric', 'grass', 'ice', 'fighting', 'poison',
    'ground', 'flying', 'psychic', 'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy', 'stellar',
)
TYPE_TO_ID = {t: i for i, t in enumerate(TYPES)}

STATUS_KEYS = ('burn', 'paralyze', 'sleep', 'freeze', 'toxic', 'poison')
CHOICE_ITEMS = frozenset(('choiceband', 'choicespecs', 'choicescarf'))
LEFTOVERS_ITEMS = frozenset(('leftovers', 'blacksludge'))
WEATHERS = ('sun', 'rain', 'sand', 'snow')
TERRAINS = ('electric', 'grassy', 'psychic', 'misty')

_EX174_MANIFEST = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-174/manifest.json')


def norm(value) -> str:
    if value is None:
        return 'none'
    s = str(value).lower()
    if '.' in s:
        s = s.rsplit('.', 1)[-1]
    s = re.sub(r'[^a-z0-9]', '', s)
    return s or 'none'


def state_terminal(state) -> float | None:
    """Return 1.0 if side_one won, 0.0 if side_two won, 0.5 on simultaneous wipe, or None if non-terminal."""
    s1_alive = any(p.hp > 0 for p in state.side_one.pokemon)
    s2_alive = any(p.hp > 0 for p in state.side_two.pokemon)
    if s1_alive and s2_alive:
        return None
    if s1_alive and not s2_alive:
        return 1.0
    if s2_alive and not s1_alive:
        return 0.0
    return 0.5


def _ordered_pokemon(side):
    """Return 6 (pokemon, is_active) pairs with the active Pokemon ALWAYS first (index 0)."""
    active_idx = int(str(side.active_index))
    mons = list(side.pokemon)
    ordered = []
    if 0 <= active_idx < len(mons):
        ordered.append((mons[active_idx], True))
    for i, p in enumerate(mons):
        if i != active_idx:
            ordered.append((p, False))
    while len(ordered) < 6:
        ordered.append((None, False))
    return ordered[:6]


def _mon_features(p, *, is_side_one: bool, is_active: bool, side) -> tuple[list[float], list[str]]:
    if p is None:
        return [0.0] * MON_NUM_DIM, ['none'] * MON_CAT_DIM

    maxhp = max(1.0, float(p.maxhp))
    hp = max(0.0, float(p.hp))
    alive = 1.0 if hp > 0.0 else 0.0
    hp_frac = min(1.0, hp / maxhp) if alive else 0.0
    item = norm(p.item)
    status = norm(p.status)
    tera = 1.0 if bool(p.terastallized) else 0.0

    status_vec = [1.0 if status == k else 0.0 for k in STATUS_KEYS]

    if is_active and alive:
        boosts = [
            float(getattr(side, 'attack_boost', 0)) / 6.0,
            float(getattr(side, 'defense_boost', 0)) / 6.0,
            float(getattr(side, 'special_attack_boost', 0)) / 6.0,
            float(getattr(side, 'special_defense_boost', 0)) / 6.0,
            float(getattr(side, 'speed_boost', 0)) / 6.0,
        ]
        vols = {norm(v) for v in (getattr(side, 'volatile_statuses', None) or ())}
        vol_vec = [
            1.0 if 'substitute' in vols else 0.0,
            1.0 if 'leechseed' in vols else 0.0,
            1.0 if any(k in vols for k in ('taunt', 'encore', 'confusion', 'trapped', 'partiallytrapped')) else 0.0,
        ]
    else:
        boosts = [0.0] * 5
        vol_vec = [0.0] * 3

    num = [
        1.0 if is_side_one else 0.0,
        1.0 if is_active else 0.0,
        alive,
        hp_frac,
        min(maxhp / 500.0, 2.0),
        min(float(p.attack) / 500.0, 2.0),
        min(float(p.defense) / 500.0, 2.0),
        min(float(p.special_attack) / 500.0, 2.0),
        min(float(p.special_defense) / 500.0, 2.0),
        min(float(p.speed) / 500.0, 2.0),
        1.0 if item != 'none' else 0.0,
        1.0 if item == 'heavydutyboots' else 0.0,
        1.0 if item in CHOICE_ITEMS else 0.0,
        1.0 if item in LEFTOVERS_ITEMS else 0.0,
        tera,
        *status_vec,
        *boosts,
        *vol_vec,
    ]
    assert len(num) == MON_NUM_DIM

    types = list(getattr(p, 'types', ()) or ())
    t1 = norm(types[0]) if len(types) > 0 else 'none'
    t2 = norm(types[1]) if len(types) > 1 else 'none'
    tera_t = norm(getattr(p, 'tera_type', 'none'))
    raw_moves = [norm(m.id) for m in (getattr(p, 'moves', None) or ()) if getattr(m, 'id', None)]
    moves = (raw_moves + ['none'] * 4)[:4]
    cat = [norm(p.id), norm(p.ability), item, t1, t2, tera_t, *moves]
    assert len(cat) == MON_CAT_DIM
    return num, cat


def _side_global(side) -> tuple[list[float], float, float, float, float]:
    alive_cnt = 0.0
    hp_sum = 0.0
    tera_used = 0.0
    active_idx = int(str(side.active_index))
    active_spe = 100.0
    for i, p in enumerate(side.pokemon):
        if p.hp > 0:
            alive_cnt += 1.0
            hp_sum += min(1.0, float(p.hp) / max(1.0, float(p.maxhp)))
            if i == active_idx:
                active_spe = max(1.0, float(p.speed))
        if bool(p.terastallized):
            tera_used = 1.0
    sc = side.side_conditions
    vec = [
        alive_cnt / 6.0,
        hp_sum / 6.0,
        tera_used,
        min(1.0, float(getattr(sc, 'stealth_rock', 0))),
        min(3.0, float(getattr(sc, 'spikes', 0))) / 3.0,
        min(2.0, float(getattr(sc, 'toxic_spikes', 0))) / 2.0,
        min(1.0, float(getattr(sc, 'sticky_web', 0))),
        1.0 if float(getattr(sc, 'reflect', 0)) > 0 else 0.0,
        1.0 if float(getattr(sc, 'light_screen', 0)) > 0 else 0.0,
        1.0 if float(getattr(sc, 'aurora_veil', 0)) > 0 else 0.0,
        1.0 if float(getattr(sc, 'tailwind', 0)) > 0 else 0.0,
    ]
    return vec, alive_cnt / 6.0, hp_sum / 6.0, tera_used, active_spe


def extract_raw(state) -> dict:
    """Extract JSON-serializable raw features `{mon_num, mon_cat, global_num}` from a `poke_engine.State`."""
    mon_num: list[list[float]] = []
    mon_cat: list[list[str]] = []
    for p, act in _ordered_pokemon(state.side_one):
        n, c = _mon_features(p, is_side_one=True, is_active=act, side=state.side_one)
        mon_num.append(n)
        mon_cat.append(c)
    for p, act in _ordered_pokemon(state.side_two):
        n, c = _mon_features(p, is_side_one=False, is_active=act, side=state.side_two)
        mon_num.append(n)
        mon_cat.append(c)

    s1_vec, s1_alive, s1_hp, s1_tera, s1_spe = _side_global(state.side_one)
    s2_vec, s2_alive, s2_hp, s2_tera, s2_spe = _side_global(state.side_two)
    diffs = [
        s1_alive - s2_alive,
        s1_hp - s2_hp,
        s1_tera - s2_tera,
        s1_spe / max(1.0, s1_spe + s2_spe) - 0.5,
    ]
    weather = norm(getattr(state, 'weather', 'none'))
    terrain = norm(getattr(state, 'terrain', 'none'))
    tr = 1.0 if bool(getattr(state, 'trick_room', False)) else 0.0
    field = [
        *[1.0 if w in weather else 0.0 for w in WEATHERS],
        *[1.0 if t in terrain else 0.0 for t in TERRAINS],
        tr,
    ]
    global_num = s1_vec + s2_vec + diffs + field
    assert len(global_num) == GLOBAL_NUM_DIM
    return dict(mon_num=mon_num, mon_cat=mon_cat, global_num=global_num)


def swap_raw(raw: dict) -> dict:
    """Exact side_one <-> side_two involution on extracted raw features."""
    mn = raw['mon_num']
    mc = raw['mon_cat']
    gn = raw['global_num']
    new_mn = []
    for row in mn[6:12]:
        r = list(row)
        r[0] = 1.0
        new_mn.append(r)
    for row in mn[0:6]:
        r = list(row)
        r[0] = 0.0
        new_mn.append(r)
    new_mc = [list(r) for r in mc[6:12]] + [list(r) for r in mc[0:6]]
    s1 = list(gn[0:11])
    s2 = list(gn[11:22])
    diffs = [-gn[22], -gn[23], -gn[24], -gn[25]]
    field = list(gn[26:35])
    return dict(mon_num=new_mn, mon_cat=new_mc, global_num=s2 + s1 + diffs + field)


class Vocab:
    """Fixed token->id vocabulary for categorical Pokemon features (0 = <UNK/none>)."""

    def __init__(self, species: dict[str, int], ability: dict[str, int], item: dict[str, int], move: dict[str, int]):
        self.species = dict(species)
        self.ability = dict(ability)
        self.item = dict(item)
        self.move = dict(move)

    @classmethod
    def build(cls, raw_cats_iter, *, min_freq: int = 2) -> 'Vocab':
        from collections import Counter
        sp, ab, it, mv = Counter(), Counter(), Counter(), Counter()
        for mon_cat in raw_cats_iter:
            for row in mon_cat:
                if row[0] != 'none':
                    sp[row[0]] += 1
                if row[1] != 'none':
                    ab[row[1]] += 1
                if row[2] != 'none':
                    it[row[2]] += 1
                for m in row[6:10]:
                    if m != 'none':
                        mv[m] += 1

        def _index(cnt: Counter) -> dict[str, int]:
            out = {'none': 0}
            for k, v in sorted(cnt.items()):
                if v >= min_freq and k != 'none':
                    out[k] = len(out)
            return out

        return cls(_index(sp), _index(ab), _index(it), _index(mv))

    def sizes(self) -> dict[str, int]:
        return dict(
            species=len(self.species),
            ability=len(self.ability),
            item=len(self.item),
            type=len(TYPES),
            move=len(self.move),
        )

    def encode_cat(self, mon_cat: list[list[str]]) -> list[list[int]]:
        out = []
        sp, ab, it, mv = self.species, self.ability, self.item, self.move
        for row in mon_cat:
            out.append([
                sp.get(row[0], 0),
                ab.get(row[1], 0),
                it.get(row[2], 0),
                TYPE_TO_ID.get(row[3], 0),
                TYPE_TO_ID.get(row[4], 0),
                TYPE_TO_ID.get(row[5], 0),
                mv.get(row[6], 0),
                mv.get(row[7], 0),
                mv.get(row[8], 0),
                mv.get(row[9], 0),
            ])
        return out

    def to_dict(self) -> dict:
        return dict(species=self.species, ability=self.ability, item=self.item, move=self.move)

    @classmethod
    def from_dict(cls, d: dict) -> 'Vocab':
        return cls(d['species'], d['ability'], d['item'], d['move'])

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1))

    @classmethod
    def load(cls, path: Path) -> 'Vocab':
        return cls.from_dict(json.loads(Path(path).read_text()))


def parse_packed_team_species(packed: str) -> frozenset[str]:
    """Extract normalized 6-species frozenset from a Showdown packed team string."""
    species = []
    for mon in str(packed).split(']'):
        if not mon.strip():
            continue
        fields = mon.split('|')
        sp = fields[1] if len(fields) > 1 and fields[1].strip() else fields[0]
        species.append(norm(sp))
    return frozenset(species)


def blim_eval_team_sets(manifest_path: Path = _EX174_MANIFEST) -> set[frozenset[str]]:
    """Return the set of 6-species frozensets for all 64 sealed Blim evaluation teams in EX-174."""
    d = json.loads(Path(manifest_path).read_text())
    out: set[frozenset[str]] = set()
    for slot in d.get('schedule', []):
        for side in ('p1', 'p2'):
            packed = (slot.get('teams', {}).get(side) or {}).get('packed')
            if packed:
                out.add(parse_packed_team_species(packed))
    return out
