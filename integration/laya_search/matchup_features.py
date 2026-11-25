"""EP-245 / D-221 (EX-216): Gen 9 team-agnostic mechanical matchup features from `poke_engine.State` tensors.

Computes exact zero-sum antisymmetric per-Pokemon kit/hazard flags, 6x6 pairwise damage/effectiveness matrices
(incorporating type chart, Tera types/STAB, Air Balloon/Levitate/Absorb immunities, items, abilities, moves,
boosts, status, screens, weather, terrain, recovery/drain, and speed), and global active/team matchup diffs.

Crucially, raw species/item/ability/move IDs and raw stat fingerprints are NEVER fed directly to the neural net
(avoiding the game-signature memorization diagnosed in EX-207), while giving V_phi full mechanical visibility into
type matchups, Air Balloon, Water Absorb, Draining Kiss, Recover walls, hazards, and team wincon coverage.
"""
from __future__ import annotations

from functools import lru_cache
import torch

from integration.laya_imitation import dex_v2
from . import featurize as F

TYPE_TO_ID = F.TYPE_TO_ID
NUM_TYPES = len(F.TYPES)  # 20

# Move / item / ability functional sets (normalized lowercase alphanumeric)
DRAIN_RATIO: dict[str, float] = {
    'drainingkiss': 0.75,
    'oblivionwing': 0.75,
    'gigadrain': 0.50,
    'hornleech': 0.50,
    'drainpunch': 0.50,
    'bitterblade': 0.50,
    'matchagotcha': 0.50,
    'leechlife': 0.50,
    'paraboliccharge': 0.50,
    'megadrain': 0.50,
    'absorb': 0.50,
}
RECOVERY_50 = frozenset((
    'recover', 'roost', 'slackoff', 'softboiled', 'moonlight', 'synthesis', 'morningsun',
    'shoreup', 'milkdrink', 'healorder', 'strengthsap', 'wish', 'rest', 'synthesis',
))
SETUP_MOVES = frozenset((
    'swordsdance', 'nastyplot', 'calmmind', 'dragondance', 'quiverdance', 'bulkup', 'irondefense',
    'curse', 'shellsmash', 'agility', 'rockpolish', 'autotomize', 'shiftgear', 'victorydance',
    'tidyup', 'coil', 'cosmicpower', 'bellydrum', 'tailglow', 'clangoroussoul', 'filletaway',
    'growth', 'workup', 'honeclaws', 'amnesia', 'acidarmor', 'barrier', 'shelter', 'takeheart',
))
PIVOT_MOVES = frozenset((
    'uturn', 'voltswitch', 'flipturn', 'partingshot', 'chillyreception', 'teleport', 'shedtail', 'batonpass',
))
HAZARD_SET_MOVES = frozenset(('stealthrock', 'spikes', 'toxicspikes', 'stickyweb', 'ceaselessedge', 'stoneaxe'))
HAZARD_REMOVE_MOVES = frozenset(('rapidspin', 'defog', 'mortalspin', 'courtchange', 'tidyup'))
DISRUPT_MOVES = frozenset((
    'taunt', 'encore', 'knockoff', 'willowisp', 'thunderwave', 'toxic', 'spore', 'sleeppowder',
    'glare', 'nuzzle', 'yawn', 'whirlwind', 'roar', 'dragontail', 'circlethrow', 'trick', 'switcheroo',
    'haze', 'clearsmog', 'perishsong', 'leechseed', 'substitute',
))
IGNORE_ABILITY_MOVES = frozenset(('sunsteelstrike', 'moongeistbeam', 'photongeyser'))
DEF_TARGET_MOVES = frozenset(('psyshock', 'psystrike', 'secretsword'))
FIXED_100_MOVES = frozenset(('seismictoss', 'nightshade'))
HALF_HP_MOVES = frozenset(('ruination', 'superfang', 'naturesmadness'))
MULTI_HIT_POWER: dict[str, int] = {
    'tripleaxel': 120,
    'surgingstrikes': 113,  # 3 x 25 x 1.5 crit
    'wickedblow': 113,      # 75 x 1.5 crit
    'flowertrick': 105,     # 70 x 1.5 crit
    'populationbomb': 180,
    'scaleshot': 75,
    'iciclespear': 75,
    'rockblast': 75,
    'bulletseed': 75,
    'pinmissile': 75,
    'watershuriken': 45,
    'dragondarts': 100,
    'doubleironbash': 120,
    'dualwingbeat': 80,
    'bonemerang': 100,
    'tachyoncutter': 100,
    'twinbeam': 80,
    'lowkick': 80,
    'grassknot': 80,
    'heavyslam': 80,
    'heatcrash': 80,
    'gyroball': 75,
    'electroball': 75,
    'eruption': 120,
    'waterspout': 120,
    'dragonenergy': 120,
}

# Ability mechanics
GROUND_IMMUNE_AB = frozenset(('levitate', 'eartheater'))
ABSORB_HEAL_TYPE: dict[str, str] = {
    'waterabsorb': 'water',
    'dryskin': 'water',
    'voltabsorb': 'electric',
    'eartheater': 'ground',
}
ABSORB_BOOST_TYPE: dict[str, str] = {
    'flashfire': 'fire',
    'sapsipper': 'grass',
    'stormdrain': 'water',
    'lightningrod': 'electric',
    'motordrive': 'electric',
    'wellbakedbody': 'fire',
}
MOLD_BREAKER_AB = frozenset(('moldbreaker', 'teravolt', 'turboblaze'))
MULTISCALE_AB = frozenset(('multiscale', 'shadowshield'))
FILTER_AB = frozenset(('filter', 'solidrock', 'prismarmor'))
DEFENSIVE_SPECIAL_AB = frozenset((
    'unaware', 'goodasgold', 'magicguard', 'purifyingsalt', 'furcoat', 'icescales', 'thickfat',
    'regenerator', 'poisonheal', 'multiscale', 'shadowshield',
))
SCRAPPY_AB = frozenset(('scrappy', 'mindseye'))

# Type-boosting items (1.2x)
TYPE_BOOST_ITEMS: dict[str, str] = {
    'charcoal': 'fire', 'flameplate': 'fire', 'hearthflamemask': 'fire',
    'mysticwater': 'water', 'splashplate': 'water', 'wellspringmask': 'water',
    'miracleseed': 'grass', 'meadowplate': 'grass',
    'magnet': 'electric', 'zapplate': 'electric',
    'nevermeltice': 'ice', 'icicleplate': 'ice',
    'blackbelt': 'fighting', 'fistplate': 'fighting',
    'poisonbarb': 'poison', 'toxicplate': 'poison',
    'softsand': 'ground', 'earthplate': 'ground',
    'sharpbeak': 'flying', 'skyplate': 'flying',
    'twistedspoon': 'psychic', 'mindplate': 'psychic',
    'silverpowder': 'bug', 'insectplate': 'bug',
    'hardstone': 'rock', 'stoneplate': 'rock', 'cornerstonemask': 'rock',
    'spelltag': 'ghost', 'spookyplate': 'ghost',
    'dragonfang': 'dragon', 'dracoplate': 'dragon',
    'blackglasses': 'dark', 'dreadplate': 'dark',
    'metalcoat': 'steel', 'ironplate': 'steel',
    'pixieplate': 'fairy', 'fairyfeather': 'fairy',
    'silkscarf': 'normal', 'punchingglove': 'fighting',
}
NFE_EVIOLITE_SPECIES = frozenset((
    'gligar', 'chansey', 'porygon2', 'dusclops', 'clefairy', 'dipplin', 'duraludon', 'bisharp',
    'scyther', 'qwilfishhisui', 'sneasel', 'sneaselhisui', 'magneton', 'primeape', 'girafarig',
    'stantler', 'ursaring', 'murkrow', 'misdreavus', 'rhydon', 'electabuzz', 'magmar', 'vullaby',
    'pawniard', 'haunter', 'kadabra', 'gurdurr', 'ferroseed', 'mareanie', 'corsolagalar',
))

MON_KIT_DIM = 23
MON_PAIR_DIM = 14
MON_MATCHUP_DIM = MON_KIT_DIM + MON_PAIR_DIM  # 37
GLOBAL_MATCHUP_DIM = 12


@lru_cache(maxsize=1)
def _type_chart_tensor() -> torch.Tensor:
    """[20, 20] Gen 9 type effectiveness matrix indexed by `F.TYPES` (`0='none'` -> 1.0)."""
    chart = torch.ones((NUM_TYPES, NUM_TYPES), dtype=torch.float32)
    atk_map = dex_v2.load()['attack']
    for atk_name, row in atk_map.items():
        ai = TYPE_TO_ID.get(atk_name)
        if ai is None:
            continue
        for def_name, mult in row.items():
            di = TYPE_TO_ID.get(def_name)
            if di is not None:
                chart[ai, di] = float(mult)
    return chart


class MatchupTables:
    """Canonical Gen 9 lookup tables supporting BOTH offline `Vocab` int IDs and live string `mon_cat`."""

    def __init__(self):
        dex = dex_v2.load()
        self.move_to_idx: dict[str, int] = {'none': 0}
        self.item_to_idx: dict[str, int] = {'none': 0}
        self.ab_to_idx: dict[str, int] = {'none': 0}
        self.sp_to_idx: dict[str, int] = {'none': 0}

        for m in sorted(dex['moves']):
            self.move_to_idx.setdefault(m, len(self.move_to_idx))
        for m in sorted(set(DRAIN_RATIO) | RECOVERY_50 | SETUP_MOVES | PIVOT_MOVES | HAZARD_SET_MOVES | HAZARD_REMOVE_MOVES | DISRUPT_MOVES | set(MULTI_HIT_POWER)):
            self.move_to_idx.setdefault(m, len(self.move_to_idx))

        all_items = set(TYPE_BOOST_ITEMS) | {
            'airballoon', 'choicescarf', 'choiceband', 'choicespecs', 'lifeorb', 'assaultvest',
            'focussash', 'heavydutyboots', 'leftovers', 'blacksludge', 'eviolite', 'rockyhelmet',
            'boosterenergy', 'expertbelt', 'loadeddice', 'toxicorb', 'flameorb', 'clearamulet',
        }
        for it in sorted(all_items):
            self.item_to_idx.setdefault(it, len(self.item_to_idx))

        all_abs = (
            set(GROUND_IMMUNE_AB) | set(ABSORB_HEAL_TYPE) | set(ABSORB_BOOST_TYPE) | set(MOLD_BREAKER_AB)
            | set(MULTISCALE_AB) | set(FILTER_AB) | set(DEFENSIVE_SPECIAL_AB) | set(SCRAPPY_AB)
            | {
                'thickfat', 'purifyingsalt', 'heatproof', 'fluffy', 'furcoat', 'icescales', 'waterbubble',
                'hugepower', 'purepower', 'technician', 'sharpness', 'toughclaws', 'sheerforce', 'guts',
                'adaptability', 'tintedlens', 'supremeoverlord', 'soundproof', 'bulletproof',
                'swiftswim', 'chlorophyll', 'sandrush', 'slushrush', 'vesselofruin', 'tabletsofruin',
                'swordofruin', 'beadsofruin', 'unaware', 'goodasgold', 'magicguard', 'regenerator',
                'poisonheal', 'protosynthesis', 'quarkdrive',
            }
        )
        for ab in sorted(all_abs):
            self.ab_to_idx.setdefault(ab, len(self.ab_to_idx))

        for sp in sorted(NFE_EVIOLITE_SPECIES | {'ogerponwellspring', 'ogerponhearthflame', 'ogerponcornerstone', 'ogerpon'}):
            self.sp_to_idx.setdefault(sp, len(self.sp_to_idx))

        nm = len(self.move_to_idx)
        self.m_power = torch.zeros(nm, dtype=torch.float32)
        self.m_cat = torch.zeros(nm, dtype=torch.long)     # 0=status, 1=physical, 2=special
        self.m_type = torch.zeros(nm, dtype=torch.long)    # 0..19
        self.m_prio = torch.zeros(nm, dtype=torch.float32)
        self.m_drain = torch.zeros(nm, dtype=torch.float32)
        # Bit flags per move: [contact, slicing, sound, bullet, ignore_ab, def_target, fixed100, halfhp,
        #                      bodypress, foulplay, facade, hex, acrobatics, knockoff, terablast, freezedry,
        #                      hydrosteam, ivycudgel, storedpower, earthquake,
        #                      rec50, setup, pivot, haz_set, haz_rem, disrupt, multihit]
        self.m_flags = torch.zeros((nm, 27), dtype=torch.float32)

        for name, idx in self.move_to_idx.items():
            if idx == 0:
                continue
            info = dex['moves'].get(name, {})
            pw = MULTI_HIT_POWER.get(name, int(info.get('power') or 0))
            self.m_power[idx] = float(pw)
            cat_s = info.get('category', 'status')
            self.m_cat[idx] = 1 if cat_s == 'physical' else (2 if cat_s == 'special' else 0)
            self.m_type[idx] = TYPE_TO_ID.get(info.get('type', 'none'), 0)
            self.m_prio[idx] = 1.0 if int(info.get('priority') or 0) > 0 and self.m_cat[idx] > 0 else 0.0
            self.m_drain[idx] = DRAIN_RATIO.get(name, 0.0)
            fl = set(info.get('flags') or ())
            f = self.m_flags[idx]
            f[0] = 1.0 if 'contact' in fl else 0.0
            f[1] = 1.0 if 'slicing' in fl else 0.0
            f[2] = 1.0 if 'sound' in fl else 0.0
            f[3] = 1.0 if 'bullet' in fl else 0.0
            f[4] = 1.0 if name in IGNORE_ABILITY_MOVES else 0.0
            f[5] = 1.0 if name in DEF_TARGET_MOVES else 0.0
            f[6] = 1.0 if name in FIXED_100_MOVES else 0.0
            f[7] = 1.0 if name in HALF_HP_MOVES else 0.0
            f[8] = 1.0 if name == 'bodypress' else 0.0
            f[9] = 1.0 if name == 'foulplay' else 0.0
            f[10] = 1.0 if name == 'facade' else 0.0
            f[11] = 1.0 if name == 'hex' else 0.0
            f[12] = 1.0 if name == 'acrobatics' else 0.0
            f[13] = 1.0 if name == 'knockoff' else 0.0
            f[14] = 1.0 if name == 'terablast' else 0.0
            f[15] = 1.0 if name == 'freezedry' else 0.0
            f[16] = 1.0 if name == 'hydrosteam' else 0.0
            f[17] = 1.0 if name == 'ivycudgel' else 0.0
            f[18] = 1.0 if name in ('storedpower', 'powertrip') else 0.0
            f[19] = 1.0 if name == 'earthquake' else 0.0
            f[20] = 1.0 if name in RECOVERY_50 else 0.0
            f[21] = 1.0 if name in SETUP_MOVES else 0.0
            f[22] = 1.0 if name in PIVOT_MOVES else 0.0
            f[23] = 1.0 if name in HAZARD_SET_MOVES else 0.0
            f[24] = 1.0 if name in HAZARD_REMOVE_MOVES else 0.0
            f[25] = 1.0 if name in DISRUPT_MOVES else 0.0
            f[26] = 1.0 if name in ('scaleshot', 'iciclespear', 'rockblast', 'bulletseed', 'pinmissile') else 0.0

        ni = len(self.item_to_idx)
        # Item flags: [airballoon, scarf, band, specs, lifeorb, av, sash, hdb, leftovers, eviolite,
        #              helmet_or_booster, expertbelt, loadeddice]
        self.i_flags = torch.zeros((ni, 13), dtype=torch.float32)
        self.i_boost_type = torch.zeros(ni, dtype=torch.long)
        for name, idx in self.item_to_idx.items():
            f = self.i_flags[idx]
            f[0] = 1.0 if name == 'airballoon' else 0.0
            f[1] = 1.0 if name == 'choicescarf' else 0.0
            f[2] = 1.0 if name == 'choiceband' else 0.0
            f[3] = 1.0 if name == 'choicespecs' else 0.0
            f[4] = 1.0 if name == 'lifeorb' else 0.0
            f[5] = 1.0 if name == 'assaultvest' else 0.0
            f[6] = 1.0 if name == 'focussash' else 0.0
            f[7] = 1.0 if name == 'heavydutyboots' else 0.0
            f[8] = 1.0 if name in ('leftovers', 'blacksludge') else 0.0
            f[9] = 1.0 if name == 'eviolite' else 0.0
            f[10] = 1.0 if name in ('rockyhelmet', 'boosterenergy') else 0.0
            f[11] = 1.0 if name == 'expertbelt' else 0.0
            f[12] = 1.0 if name == 'loadeddice' else 0.0
            if name in TYPE_BOOST_ITEMS:
                self.i_boost_type[idx] = TYPE_TO_ID[TYPE_BOOST_ITEMS[name]]

        na = len(self.ab_to_idx)
        # Ability flags:
        # 0:ground_imm 1:absorb_heal 2:absorb_boost 3:mold_breaker 4:multiscale 5:regenerator 6:poison_heal
        # 7:unaware 8:goodasgold 9:magicguard 10:thickfat 11:purifyingsalt 12:dryskin 13:fluffy 14:heatproof
        # 15:filter 16:furcoat 17:icescales 18:waterbubble 19:hugepower 20:technician 21:sharpness
        # 22:toughclaws 23:sheerforce 24:guts 25:adaptability 26:tintedlens 27:scrappy 28:supremeoverlord
        # 29:soundproof 30:bulletproof 31:swiftswim 32:chlorophyll 33:sandrush 34:slushrush
        # 35:vessel_ruin 36:tablets_ruin 37:sword_ruin 38:beads_ruin 39:defensive_any
        self.a_flags = torch.zeros((na, 40), dtype=torch.float32)
        self.a_imm_type = torch.zeros(na, dtype=torch.long)  # immune type (0 if none)
        for name, idx in self.ab_to_idx.items():
            f = self.a_flags[idx]
            f[0] = 1.0 if name in GROUND_IMMUNE_AB else 0.0
            f[1] = 1.0 if name in ABSORB_HEAL_TYPE else 0.0
            f[2] = 1.0 if name in ABSORB_BOOST_TYPE else 0.0
            f[3] = 1.0 if name in MOLD_BREAKER_AB else 0.0
            f[4] = 1.0 if name in MULTISCALE_AB else 0.0
            f[5] = 1.0 if name == 'regenerator' else 0.0
            f[6] = 1.0 if name == 'poisonheal' else 0.0
            f[7] = 1.0 if name == 'unaware' else 0.0
            f[8] = 1.0 if name == 'goodasgold' else 0.0
            f[9] = 1.0 if name == 'magicguard' else 0.0
            f[10] = 1.0 if name == 'thickfat' else 0.0
            f[11] = 1.0 if name == 'purifyingsalt' else 0.0
            f[12] = 1.0 if name == 'dryskin' else 0.0
            f[13] = 1.0 if name == 'fluffy' else 0.0
            f[14] = 1.0 if name == 'heatproof' else 0.0
            f[15] = 1.0 if name in FILTER_AB else 0.0
            f[16] = 1.0 if name == 'furcoat' else 0.0
            f[17] = 1.0 if name == 'icescales' else 0.0
            f[18] = 1.0 if name == 'waterbubble' else 0.0
            f[19] = 1.0 if name in ('hugepower', 'purepower') else 0.0
            f[20] = 1.0 if name == 'technician' else 0.0
            f[21] = 1.0 if name == 'sharpness' else 0.0
            f[22] = 1.0 if name == 'toughclaws' else 0.0
            f[23] = 1.0 if name == 'sheerforce' else 0.0
            f[24] = 1.0 if name == 'guts' else 0.0
            f[25] = 1.0 if name == 'adaptability' else 0.0
            f[26] = 1.0 if name == 'tintedlens' else 0.0
            f[27] = 1.0 if name in SCRAPPY_AB else 0.0
            f[28] = 1.0 if name == 'supremeoverlord' else 0.0
            f[29] = 1.0 if name == 'soundproof' else 0.0
            f[30] = 1.0 if name == 'bulletproof' else 0.0
            f[31] = 1.0 if name == 'swiftswim' else 0.0
            f[32] = 1.0 if name == 'chlorophyll' else 0.0
            f[33] = 1.0 if name == 'sandrush' else 0.0
            f[34] = 1.0 if name == 'slushrush' else 0.0
            f[35] = 1.0 if name == 'vesselofruin' else 0.0
            f[36] = 1.0 if name == 'tabletsofruin' else 0.0
            f[37] = 1.0 if name == 'swordofruin' else 0.0
            f[38] = 1.0 if name == 'beadsofruin' else 0.0
            f[39] = 1.0 if name in DEFENSIVE_SPECIAL_AB else 0.0
            if name in ABSORB_HEAL_TYPE:
                self.a_imm_type[idx] = TYPE_TO_ID[ABSORB_HEAL_TYPE[name]]
            elif name in ABSORB_BOOST_TYPE:
                self.a_imm_type[idx] = TYPE_TO_ID[ABSORB_BOOST_TYPE[name]]
            elif name == 'levitate':
                self.a_imm_type[idx] = TYPE_TO_ID['ground']

        ns = len(self.sp_to_idx)
        self.s_eviolite_ok = torch.zeros(ns, dtype=torch.float32)
        self.s_cudgel_type = torch.full((ns,), TYPE_TO_ID['grass'], dtype=torch.long)
        for name, idx in self.sp_to_idx.items():
            if name in NFE_EVIOLITE_SPECIES:
                self.s_eviolite_ok[idx] = 1.0
            if 'wellspring' in name:
                self.s_cudgel_type[idx] = TYPE_TO_ID['water']
            elif 'hearthflame' in name:
                self.s_cudgel_type[idx] = TYPE_TO_ID['fire']
            elif 'cornerstone' in name:
                self.s_cudgel_type[idx] = TYPE_TO_ID['rock']

        self.type_chart = _type_chart_tensor()

    def to(self, device: torch.device) -> 'MatchupTables':
        out = object.__new__(MatchupTables)
        out.move_to_idx = self.move_to_idx
        out.item_to_idx = self.item_to_idx
        out.ab_to_idx = self.ab_to_idx
        out.sp_to_idx = self.sp_to_idx
        for attr in ('m_power', 'm_cat', 'm_type', 'm_prio', 'm_drain', 'm_flags',
                     'i_flags', 'i_boost_type', 'a_flags', 'a_imm_type',
                     's_eviolite_ok', 's_cudgel_type', 'type_chart'):
            setattr(out, attr, getattr(self, attr).to(device))
        return out

    def encode_raw_mon_cat(self, raw_mon_cat_batch: list[list[list[str]]], device: torch.device) -> torch.Tensor:
        """Encode list of `[12][10]` string arrays directly to canonical physics IDs `[B, 12, 10]`."""
        sp, ab, it, mv = self.sp_to_idx, self.ab_to_idx, self.item_to_idx, self.move_to_idx
        rows = []
        for mon_cat in raw_mon_cat_batch:
            mrows = []
            for r in mon_cat:
                mrows.append([
                    sp.get(r[0], 0),
                    ab.get(r[1], 0),
                    it.get(r[2], 0),
                    TYPE_TO_ID.get(r[3], 0),
                    TYPE_TO_ID.get(r[4], 0),
                    TYPE_TO_ID.get(r[5], 0),
                    mv.get(r[6], 0),
                    mv.get(r[7], 0),
                    mv.get(r[8], 0),
                    mv.get(r[9], 0),
                ])
            rows.append(mrows)
        return torch.tensor(rows, dtype=torch.long, device=device)

    def remap_vocab_mon_cat(self, mc_vocab: torch.Tensor, vocab: F.Vocab) -> torch.Tensor:
        """Remap `[B, 12, 10]` vocab-indexed IDs (from `.npz`) to canonical physics IDs."""
        dev = mc_vocab.device

        def _map(v_dict: dict[str, int], target: dict[str, int]) -> torch.Tensor:
            n = max(v_dict.values(), default=0) + 1
            lut = torch.zeros(n, dtype=torch.long, device=dev)
            for k, old_i in v_dict.items():
                lut[old_i] = target.get(k, 0)
            return lut

        sp_lut = _map(vocab.species, self.sp_to_idx)
        ab_lut = _map(vocab.ability, self.ab_to_idx)
        it_lut = _map(vocab.item, self.item_to_idx)
        mv_lut = _map(vocab.move, self.move_to_idx)

        out = mc_vocab.clone()
        out[:, :, 0] = sp_lut[mc_vocab[:, :, 0].clamp(0, len(sp_lut) - 1)]
        out[:, :, 1] = ab_lut[mc_vocab[:, :, 1].clamp(0, len(ab_lut) - 1)]
        out[:, :, 2] = it_lut[mc_vocab[:, :, 2].clamp(0, len(it_lut) - 1)]
        # columns 3,4,5 are already F.TYPE_TO_ID
        for col in (6, 7, 8, 9):
            out[:, :, col] = mv_lut[mc_vocab[:, :, col].clamp(0, len(mv_lut) - 1)]
        return out


@lru_cache(maxsize=1)
def default_tables() -> MatchupTables:
    return MatchupTables()


def _stage_mult(boost_div6: torch.Tensor) -> torch.Tensor:
    b = (boost_div6 * 6.0).clamp(-6.0, 6.0)
    return torch.where(b >= 0.0, (2.0 + b) / 2.0, 2.0 / (2.0 - b))


def _effective_speed(
    mn: torch.Tensor,
    mc: torch.Tensor,
    sc_side: torch.Tensor,
    field: torch.Tensor,
    tables: MatchupTables,
) -> torch.Tensor:
    """Effective speed `[B, 6]` for one side (active boosts, Choice Scarf, paralysis, Tailwind, weather abilities)."""
    spe = (mn[:, :, 9] * 500.0).clamp(min=1.0)
    active = mn[:, :, 1] > 0.5
    spe_b = torch.where(active, _stage_mult(mn[:, :, 25]), torch.ones_like(spe))
    it_f = tables.i_flags[mc[:, :, 2]]   # [B, 6, 13]
    ab_f = tables.a_flags[mc[:, :, 1]]   # [B, 6, 40]
    scarf = torch.where(it_f[:, :, 1] > 0.5, 1.5, 1.0)
    para = torch.where(mn[:, :, 16] > 0.5, 0.5, 1.0)
    tw = torch.where(sc_side[:, 10:11] > 0.5, 2.0, 1.0)
    sun = field[:, 0:1] > 0.5
    rain = field[:, 1:2] > 0.5
    sand = field[:, 2:3] > 0.5
    snow = field[:, 3:4] > 0.5
    w_boost = torch.where(
        (rain & (ab_f[:, :, 31] > 0.5))
        | (sun & (ab_f[:, :, 32] > 0.5))
        | (sand & (ab_f[:, :, 33] > 0.5))
        | (snow & (ab_f[:, :, 34] > 0.5)),
        2.0, 1.0,
    )
    return spe * spe_b * scarf * para * tw * w_boost


def _passive_recovery_and_hazards(
    mn: torch.Tensor,
    mc: torch.Tensor,
    own_sc: torch.Tensor,
    field: torch.Tensor,
    tables: MatchupTables,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return `(net_passive_heal[B,6], entry_hazard_dmg[B,6], grounded[B,6])`."""
    it_f = tables.i_flags[mc[:, :, 2]]
    ab_f = tables.a_flags[mc[:, :, 1]]
    tera = mn[:, :, 14] > 0.5
    t1 = mc[:, :, 3]
    t2 = mc[:, :, 4]
    tt = mc[:, :, 5]
    use_tera = tera & (tt > 0) & (tt != TYPE_TO_ID['stellar'])
    def_t1 = torch.where(use_tera, tt, t1)
    def_t2 = torch.where(use_tera, torch.zeros_like(t2), t2)

    is_flying = (def_t1 == TYPE_TO_ID['flying']) | (def_t2 == TYPE_TO_ID['flying'])
    grounded = (~is_flying) & (it_f[:, :, 0] < 0.5) & (ab_f[:, :, 0] < 0.5)

    # Passive net heal per turn
    lefties = it_f[:, :, 8] * 0.0625
    grassy = torch.where(grounded & (field[:, 5:6] > 0.5), 0.0625, 0.0)
    poisoned = (mn[:, :, 19] > 0.5) | (mn[:, :, 20] > 0.5)
    pheal = torch.where((ab_f[:, :, 6] > 0.5) & poisoned, 0.125, 0.0)
    magic_guard = ab_f[:, :, 9] > 0.5
    burn_chip = torch.where((mn[:, :, 15] > 0.5) & (~magic_guard), 0.0625, 0.0)
    psn_chip = torch.where(poisoned & (ab_f[:, :, 6] < 0.5) & (~magic_guard), 0.125, 0.0)
    net_passive = lefties + grassy + pheal - burn_chip - psn_chip

    # Entry hazard damage fraction
    rock_id = TYPE_TO_ID['rock']
    sr_eff = tables.type_chart[rock_id, def_t1] * tables.type_chart[rock_id, def_t2]
    sr_dmg = (own_sc[:, 3:4] > 0.5).float() * 0.125 * sr_eff
    sp_layers = (own_sc[:, 4:5] * 3.0).round().clamp(0.0, 3.0)
    sp_frac = torch.where(sp_layers >= 3, 0.25, torch.where(sp_layers >= 2, 1.0 / 6.0, torch.where(sp_layers >= 1, 0.125, 0.0)))
    sp_dmg = torch.where(grounded, sp_frac, torch.zeros_like(sp_frac))
    immune_haz = (it_f[:, :, 7] > 0.5) | magic_guard
    entry_dmg = torch.where(immune_haz, torch.zeros_like(sr_dmg), (sr_dmg + sp_dmg).clamp(0.0, 1.0))
    return net_passive, entry_dmg, grounded


def _pairwise_damage(
    atk_mn: torch.Tensor,
    atk_mc: torch.Tensor,
    def_mn: torch.Tensor,
    def_mc: torch.Tensor,
    def_sc: torch.Tensor,
    field: torch.Tensor,
    atk_grounded: torch.Tensor,
    tables: MatchupTables,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Compute exact Gen 9 `[B, 6, 4, 6]` damage fraction (of def maxHP), priority mask `[B, 6, 4]`, and drain heal `[B, 6, 4, 6]`."""
    # Attacker: [B, 6, 1, 1] or [B, 6, 4, 1]; Defender: [B, 1, 1, 6]
    moves = atk_mc[:, :, 6:10]                # [B, 6, 4]
    mpow = tables.m_power[moves]              # [B, 6, 4]
    mcat = tables.m_cat[moves]                # [B, 6, 4]  0=stat, 1=phys, 2=spec
    mtype = tables.m_type[moves]              # [B, 6, 4]
    mprio = tables.m_prio[moves]              # [B, 6, 4]
    mdrain = tables.m_drain[moves]            # [B, 6, 4]
    mf = tables.m_flags[moves]                # [B, 6, 4, 27]

    atk_it = tables.i_flags[atk_mc[:, :, 2]]  # [B, 6, 13]
    atk_ab = tables.a_flags[atk_mc[:, :, 1]]  # [B, 6, 40]
    def_it = tables.i_flags[def_mc[:, :, 2]]  # [B, 6, 13]
    def_ab = tables.a_flags[def_mc[:, :, 1]]  # [B, 6, 40]

    # Dynamic move types: Ivy Cudgel & Tera Blast
    atk_tera = atk_mn[:, :, 14] > 0.5         # [B, 6]
    atk_tt = atk_mc[:, :, 5]                  # [B, 6]
    cudgel_t = tables.s_cudgel_type[atk_mc[:, :, 0]].unsqueeze(2)  # [B, 6, 1]
    mtype = torch.where(mf[:, :, :, 17] > 0.5, cudgel_t, mtype)
    tb_use = (mf[:, :, :, 14] > 0.5) & atk_tera.unsqueeze(2) & (atk_tt.unsqueeze(2) > 0) & (atk_tt.unsqueeze(2) != TYPE_TO_ID['stellar'])
    mtype = torch.where(tb_use, atk_tt.unsqueeze(2).expand_as(mtype), mtype)

    # Dynamic power adjustments (Loaded Dice, Facade, Hex, Acrobatics, Knock Off, Stored Power)
    pow_eff = mpow.unsqueeze(3).expand(-1, -1, -1, 6).clone()  # [B, 6, 4, 6]
    # Loaded dice multi-hit -> 100
    ld_mask = (mf[:, :, :, 26] > 0.5) & (atk_it[:, :, 12:13] > 0.5)
    pow_eff = torch.where(ld_mask.unsqueeze(3), torch.full_like(pow_eff, 100.0), pow_eff)
    # Facade 2x if attacker statused
    atk_statused = (atk_mn[:, :, 15:21].sum(dim=-1) > 0.5).unsqueeze(2).unsqueeze(3)
    pow_eff = torch.where((mf[:, :, :, 10:11] > 0.5) & atk_statused, pow_eff * 2.0, pow_eff)
    # Hex 2x if defender statused
    def_statused = (def_mn[:, :, 15:21].sum(dim=-1) > 0.5).unsqueeze(1).unsqueeze(2)
    pow_eff = torch.where((mf[:, :, :, 11:12] > 0.5) & def_statused, pow_eff * 2.0, pow_eff)
    # Acrobatics 2x if attacker has no item
    atk_no_item = (atk_mn[:, :, 10] < 0.5).unsqueeze(2).unsqueeze(3)
    pow_eff = torch.where((mf[:, :, :, 12:13] > 0.5) & atk_no_item, pow_eff * 2.0, pow_eff)
    # Knock Off 1.5x if defender has item
    def_has_item = (def_mn[:, :, 10] > 0.5).unsqueeze(1).unsqueeze(2)
    pow_eff = torch.where((mf[:, :, :, 13:14] > 0.5) & def_has_item, pow_eff * 1.5, pow_eff)
    # Stored Power / Power Trip
    pos_boosts = (atk_mn[:, :, 21:26].clamp(min=0.0) * 6.0).sum(dim=-1)  # [B, 6]
    sp_pow = (20.0 + 20.0 * pos_boosts).unsqueeze(2).unsqueeze(3)
    pow_eff = torch.where(mf[:, :, :, 18:19] > 0.5, sp_pow.expand_as(pow_eff), pow_eff)

    # Effective attacker/defender stats [B, 6, 4, 6]
    atk_act = (atk_mn[:, :, 1] > 0.5).unsqueeze(2).unsqueeze(3)
    def_act = (def_mn[:, :, 1] > 0.5).unsqueeze(1).unsqueeze(2)
    atk_unaware = (atk_ab[:, :, 7] > 0.5).unsqueeze(2).unsqueeze(3)
    def_unaware = (def_ab[:, :, 7] > 0.5).unsqueeze(1).unsqueeze(2)

    atk_raw_a = (atk_mn[:, :, 5] * 500.0).clamp(min=10.0).unsqueeze(2).unsqueeze(3)
    atk_raw_d = (atk_mn[:, :, 6] * 500.0).clamp(min=10.0).unsqueeze(2).unsqueeze(3)
    atk_raw_sa = (atk_mn[:, :, 7] * 500.0).clamp(min=10.0).unsqueeze(2).unsqueeze(3)
    def_raw_a = (def_mn[:, :, 5] * 500.0).clamp(min=10.0).unsqueeze(1).unsqueeze(2)
    def_raw_d = (def_mn[:, :, 6] * 500.0).clamp(min=10.0).unsqueeze(1).unsqueeze(2)
    def_raw_sd = (def_mn[:, :, 8] * 500.0).clamp(min=10.0).unsqueeze(1).unsqueeze(2)

    atk_bm_a = torch.where(atk_act & (~def_unaware), _stage_mult(atk_mn[:, :, 21]).unsqueeze(2).unsqueeze(3), torch.ones_like(atk_raw_a))
    atk_bm_d = torch.where(atk_act & (~def_unaware), _stage_mult(atk_mn[:, :, 22]).unsqueeze(2).unsqueeze(3), torch.ones_like(atk_raw_d))
    atk_bm_sa = torch.where(atk_act & (~def_unaware), _stage_mult(atk_mn[:, :, 23]).unsqueeze(2).unsqueeze(3), torch.ones_like(atk_raw_sa))
    def_bm_a = torch.where(def_act & (~atk_unaware), _stage_mult(def_mn[:, :, 21]).unsqueeze(1).unsqueeze(2), torch.ones_like(def_raw_a))
    def_bm_d = torch.where(def_act & (~atk_unaware), _stage_mult(def_mn[:, :, 22]).unsqueeze(1).unsqueeze(2), torch.ones_like(def_raw_d))
    def_bm_sd = torch.where(def_act & (~atk_unaware), _stage_mult(def_mn[:, :, 24]).unsqueeze(1).unsqueeze(2), torch.ones_like(def_raw_sd))

    eff_atk_a = atk_raw_a * atk_bm_a
    eff_atk_d = atk_raw_d * atk_bm_d
    eff_atk_sa = atk_raw_sa * atk_bm_sa
    eff_def_a = def_raw_a * def_bm_a
    eff_def_d = def_raw_d * def_bm_d
    eff_def_sd = def_raw_sd * def_bm_sd

    # Physical vs Special selection (handling Tera Blast, Body Press, Foul Play, Psyshock)
    is_phys = (mcat == 1).unsqueeze(3)
    # Tera Blast uses physical if eff_atk_a > eff_atk_sa when terastallized
    is_phys = torch.where(tb_use.unsqueeze(3), eff_atk_a > eff_atk_sa, is_phys)
    off_stat = torch.where(is_phys, eff_atk_a, eff_atk_sa)
    off_stat = torch.where(mf[:, :, :, 8:9] > 0.5, eff_atk_d, off_stat)   # Body Press
    off_stat = torch.where(mf[:, :, :, 9:10] > 0.5, eff_def_a, off_stat)  # Foul Play

    use_phys_def = is_phys | (mf[:, :, :, 5:6] > 0.5)  # Psyshock / Psystrike / Secret Sword
    def_stat = torch.where(use_phys_def, eff_def_d, eff_def_sd)

    # Stat multipliers from items/abilities/weather
    # Choice Band / Specs, Huge Power, Guts, Assault Vest, Eviolite, Fur Coat, Ice Scales, Ruin, Sand/Snow
    off_stat = off_stat * torch.where(is_phys & (atk_it[:, :, 2:3].unsqueeze(3) > 0.5), 1.5, 1.0)
    off_stat = off_stat * torch.where((~is_phys) & (atk_it[:, :, 3:4].unsqueeze(3) > 0.5), 1.5, 1.0)
    off_stat = off_stat * torch.where(is_phys & (atk_ab[:, :, 19:20].unsqueeze(3) > 0.5), 2.0, 1.0)
    off_stat = off_stat * torch.where(is_phys & (atk_ab[:, :, 24:25].unsqueeze(3) > 0.5) & atk_statused, 1.5, 1.0)
    # Defender Tablets/Vessel of Ruin (when active or in pair)
    off_stat = off_stat * torch.where(is_phys & (def_ab[:, :, 36].unsqueeze(1).unsqueeze(2) > 0.5), 0.75, 1.0)
    off_stat = off_stat * torch.where((~is_phys) & (def_ab[:, :, 35].unsqueeze(1).unsqueeze(2) > 0.5), 0.75, 1.0)
    # Attacker Sword/Beads of Ruin
    def_stat = def_stat * torch.where(use_phys_def & (atk_ab[:, :, 37:38].unsqueeze(3) > 0.5), 0.75, 1.0)
    def_stat = def_stat * torch.where((~use_phys_def) & (atk_ab[:, :, 38:39].unsqueeze(3) > 0.5), 0.75, 1.0)
    # Assault Vest / Eviolite / Fur Coat / Ice Scales
    def_stat = def_stat * torch.where((~use_phys_def) & (def_it[:, :, 5].unsqueeze(1).unsqueeze(2) > 0.5), 1.5, 1.0)
    evio_ok = (def_it[:, :, 9] > 0.5) & (tables.s_eviolite_ok[def_mc[:, :, 0]] > 0.5)
    def_stat = def_stat * torch.where(evio_ok.unsqueeze(1).unsqueeze(2), 1.5, 1.0)

    ignore_def_ab = (atk_ab[:, :, 3:4].unsqueeze(3) > 0.5) | (mf[:, :, :, 4:5] > 0.5)
    def_stat = def_stat * torch.where(use_phys_def & (~ignore_def_ab) & (def_ab[:, :, 16].unsqueeze(1).unsqueeze(2) > 0.5), 2.0, 1.0)
    def_stat = def_stat * torch.where((~use_phys_def) & (~ignore_def_ab) & (def_ab[:, :, 17].unsqueeze(1).unsqueeze(2) > 0.5), 2.0, 1.0)

    # Defender effective types (handling Terastallization!)
    def_tera = def_mn[:, :, 14] > 0.5
    def_tt = def_mc[:, :, 5]
    def_use_tera = def_tera & (def_tt > 0) & (def_tt != TYPE_TO_ID['stellar'])
    dt1 = torch.where(def_use_tera, def_tt, def_mc[:, :, 3])  # [B, 6]
    dt2 = torch.where(def_use_tera, torch.zeros_like(def_mc[:, :, 4]), def_mc[:, :, 4])  # [B, 6]

    # Sandstorm Rock SpD & Snow Ice Def
    sand = (field[:, 2] > 0.5).view(-1, 1, 1, 1)
    snow = (field[:, 3] > 0.5).view(-1, 1, 1, 1)
    def_is_rock = ((dt1 == TYPE_TO_ID['rock']) | (dt2 == TYPE_TO_ID['rock'])).unsqueeze(1).unsqueeze(2)
    def_is_ice = ((dt1 == TYPE_TO_ID['ice']) | (dt2 == TYPE_TO_ID['ice'])).unsqueeze(1).unsqueeze(2)
    def_stat = def_stat * torch.where((~use_phys_def) & sand & def_is_rock, 1.5, 1.0)
    def_stat = def_stat * torch.where(use_phys_def & snow & def_is_ice, 1.5, 1.0)

    # Type effectiveness [B, 6, 4, 6]
    mt_exp = mtype.unsqueeze(3).expand(-1, -1, -1, 6)
    dt1_exp = dt1.unsqueeze(1).unsqueeze(2).expand_as(mt_exp)
    dt2_exp = dt2.unsqueeze(1).unsqueeze(2).expand_as(mt_exp)
    eff = tables.type_chart[mt_exp, dt1_exp] * tables.type_chart[mt_exp, dt2_exp]

    # Freeze-Dry hits Water 2x instead of 0.5x
    def_is_water = ((dt1 == TYPE_TO_ID['water']) | (dt2 == TYPE_TO_ID['water'])).unsqueeze(1).unsqueeze(2)
    eff = torch.where((mf[:, :, :, 15:16] > 0.5) & def_is_water, eff * 4.0, eff)
    # Scrappy / Mind's Eye hits Ghost with Normal/Fighting
    def_is_ghost = ((dt1 == TYPE_TO_ID['ghost']) | (dt2 == TYPE_TO_ID['ghost'])).unsqueeze(1).unsqueeze(2)
    norm_fight = (mt_exp == TYPE_TO_ID['normal']) | (mt_exp == TYPE_TO_ID['fighting'])
    eff = torch.where((atk_ab[:, :, 27:28].unsqueeze(3) > 0.5) & norm_fight & def_is_ghost,
                      torch.where(eff == 0.0, torch.ones_like(eff), eff), eff)
    # Tinted Lens 2x resisted
    eff = torch.where((atk_ab[:, :, 26:27].unsqueeze(3) > 0.5) & (eff > 0.0) & (eff < 1.0), eff * 2.0, eff)

    # Item & Ability Immunities (CRITICAL: Air Balloon, Levitate, Earth Eater, Water/Volt Absorb, Dry Skin, Flash Fire, Sap Sipper, Storm Drain, Lightning Rod, Motor Drive, Well-Baked Body, Soundproof, Bulletproof)
    balloon_imm = (mt_exp == TYPE_TO_ID['ground']) & (def_it[:, :, 0].unsqueeze(1).unsqueeze(2) > 0.5)
    def_imm_t = tables.a_imm_type[def_mc[:, :, 1]].unsqueeze(1).unsqueeze(2)  # [B, 1, 1, 6]
    ab_type_imm = (~ignore_def_ab) & (def_imm_t > 0) & (mt_exp == def_imm_t)
    sound_imm = (~ignore_def_ab) & (mf[:, :, :, 2:3] > 0.5) & (def_ab[:, :, 29].unsqueeze(1).unsqueeze(2) > 0.5)
    bullet_imm = (~ignore_def_ab) & (mf[:, :, :, 3:4] > 0.5) & (def_ab[:, :, 30].unsqueeze(1).unsqueeze(2) > 0.5)
    eff = torch.where(balloon_imm | ab_type_imm | sound_imm | bullet_imm, torch.zeros_like(eff), eff)

    # STAB (including Tera STAB & Adaptability)
    at1 = atk_mc[:, :, 3].unsqueeze(2)
    at2 = atk_mc[:, :, 4].unsqueeze(2)
    base_stab = (mtype > 0) & ((mtype == at1) | (mtype == at2))
    tera_stab = atk_tera.unsqueeze(2) & (atk_tt.unsqueeze(2) > 0) & (mtype == atk_tt.unsqueeze(2))
    adapt = atk_ab[:, :, 25:26] > 0.5
    stab = torch.where(
        base_stab & tera_stab,
        torch.where(adapt, 2.25, 2.0),
        torch.where(base_stab | tera_stab, torch.where(adapt, 2.0, 1.5), 1.0),
    ).unsqueeze(3)

    # General multipliers: Burn, Life Orb, Expert Belt, Type-boost item, Attacker & Defender abilities, Weather, Terrain, Screens
    mult = stab * eff
    # Burn halves physical unless Guts or Facade
    atk_burn = (atk_mn[:, :, 15] > 0.5).unsqueeze(2).unsqueeze(3)
    mult = mult * torch.where(is_phys & atk_burn & (atk_ab[:, :, 24:25].unsqueeze(3) < 0.5) & (mf[:, :, :, 10:11] < 0.5), 0.5, 1.0)
    # Attacker items
    mult = mult * torch.where(atk_it[:, :, 4:5].unsqueeze(3) > 0.5, 1.3, 1.0)
    mult = mult * torch.where((atk_it[:, :, 11:12].unsqueeze(3) > 0.5) & (eff > 1.0), 1.2, 1.0)
    atk_tb_t = tables.i_boost_type[atk_mc[:, :, 2]].unsqueeze(2).unsqueeze(3)
    mult = mult * torch.where((atk_tb_t > 0) & (mt_exp == atk_tb_t), 1.2, 1.0)
    # Attacker abilities
    mult = mult * torch.where((atk_ab[:, :, 20:21].unsqueeze(3) > 0.5) & (pow_eff > 0.0) & (pow_eff <= 60.0), 1.5, 1.0)
    mult = mult * torch.where((atk_ab[:, :, 21:22].unsqueeze(3) > 0.5) & (mf[:, :, :, 1:2] > 0.5), 1.5, 1.0)
    mult = mult * torch.where((atk_ab[:, :, 22:23].unsqueeze(3) > 0.5) & (mf[:, :, :, 0:1] > 0.5), 1.3, 1.0)
    mult = mult * torch.where(atk_ab[:, :, 23:24].unsqueeze(3) > 0.5, 1.15, 1.0)  # conservative Sheer Force avg
    mult = mult * torch.where((atk_ab[:, :, 18:19].unsqueeze(3) > 0.5) & (mt_exp == TYPE_TO_ID['water']), 2.0, 1.0)
    fainted_allies = (1.0 - atk_mn[:, :, 2]).sum(dim=1).clamp(0.0, 5.0).view(-1, 1, 1, 1)
    mult = mult * torch.where(atk_ab[:, :, 28:29].unsqueeze(3) > 0.5, 1.0 + 0.1 * fainted_allies, 1.0)
    # Defender abilities (unless ignored)
    def_full_hp = (def_mn[:, :, 3] >= 0.999).unsqueeze(1).unsqueeze(2)
    mult = mult * torch.where((~ignore_def_ab) & def_full_hp & (def_ab[:, :, 4].unsqueeze(1).unsqueeze(2) > 0.5), 0.5, 1.0)
    mult = mult * torch.where((~ignore_def_ab) & (def_ab[:, :, 10].unsqueeze(1).unsqueeze(2) > 0.5) & ((mt_exp == TYPE_TO_ID['fire']) | (mt_exp == TYPE_TO_ID['ice'])), 0.5, 1.0)
    mult = mult * torch.where((~ignore_def_ab) & (def_ab[:, :, 11].unsqueeze(1).unsqueeze(2) > 0.5) & (mt_exp == TYPE_TO_ID['ghost']), 0.5, 1.0)
    mult = mult * torch.where((~ignore_def_ab) & (def_ab[:, :, 12].unsqueeze(1).unsqueeze(2) > 0.5) & (mt_exp == TYPE_TO_ID['fire']), 1.25, 1.0)
    mult = mult * torch.where((~ignore_def_ab) & (def_ab[:, :, 13].unsqueeze(1).unsqueeze(2) > 0.5) & (mt_exp == TYPE_TO_ID['fire']), 2.0, 1.0)
    mult = mult * torch.where((~ignore_def_ab) & (def_ab[:, :, 13].unsqueeze(1).unsqueeze(2) > 0.5) & (mf[:, :, :, 0:1] > 0.5), 0.5, 1.0)
    mult = mult * torch.where((~ignore_def_ab) & (def_ab[:, :, 14].unsqueeze(1).unsqueeze(2) > 0.5) & (mt_exp == TYPE_TO_ID['fire']), 0.5, 1.0)
    mult = mult * torch.where((~ignore_def_ab) & (def_ab[:, :, 15].unsqueeze(1).unsqueeze(2) > 0.5) & (eff > 1.0), 0.75, 1.0)
    mult = mult * torch.where((~ignore_def_ab) & (def_ab[:, :, 18].unsqueeze(1).unsqueeze(2) > 0.5) & (mt_exp == TYPE_TO_ID['fire']), 0.5, 1.0)
    # Weather / Terrain / Screens
    sun = (field[:, 0] > 0.5).view(-1, 1, 1, 1)
    rain = (field[:, 1] > 0.5).view(-1, 1, 1, 1)
    eterr = (field[:, 4] > 0.5).view(-1, 1, 1, 1)
    gterr = (field[:, 5] > 0.5).view(-1, 1, 1, 1)
    pterr = (field[:, 6] > 0.5).view(-1, 1, 1, 1)
    mterr = (field[:, 7] > 0.5).view(-1, 1, 1, 1)
    ag = atk_grounded.unsqueeze(2).unsqueeze(3)
    mult = mult * torch.where(sun & (mt_exp == TYPE_TO_ID['fire']), 1.5, 1.0)
    mult = mult * torch.where(sun & (mt_exp == TYPE_TO_ID['water']) & (mf[:, :, :, 16:17] < 0.5), 0.5, 1.0)
    mult = mult * torch.where(sun & (mf[:, :, :, 16:17] > 0.5), 1.5, 1.0)
    mult = mult * torch.where(rain & (mt_exp == TYPE_TO_ID['water']), 1.5, 1.0)
    mult = mult * torch.where(rain & (mt_exp == TYPE_TO_ID['fire']), 0.5, 1.0)
    mult = mult * torch.where(eterr & ag & (mt_exp == TYPE_TO_ID['electric']), 1.3, 1.0)
    mult = mult * torch.where(gterr & ag & (mt_exp == TYPE_TO_ID['grass']), 1.3, 1.0)
    mult = mult * torch.where(gterr & (mf[:, :, :, 19:20] > 0.5), 0.5, 1.0)
    mult = mult * torch.where(pterr & ag & (mt_exp == TYPE_TO_ID['psychic']), 1.3, 1.0)
    mult = mult * torch.where(mterr & (mt_exp == TYPE_TO_ID['dragon']), 0.5, 1.0)
    reflect = (def_sc[:, 7] > 0.5).view(-1, 1, 1, 1)
    lscreen = (def_sc[:, 8] > 0.5).view(-1, 1, 1, 1)
    aveil = (def_sc[:, 9] > 0.5).view(-1, 1, 1, 1)
    mult = mult * torch.where(is_phys & (reflect | aveil), 0.5, 1.0)
    mult = mult * torch.where((~is_phys) & (lscreen | aveil), 0.5, 1.0)

    # Gen 9 damage formula (average roll 0.925)
    base_dmg = ((42.0 * pow_eff * (off_stat / def_stat.clamp(min=1.0))) / 50.0 + 2.0) * 0.925 * mult
    def_maxhp = (def_mn[:, :, 4] * 500.0).clamp(min=1.0).unsqueeze(1).unsqueeze(2)
    dmg_frac = base_dmg / def_maxhp
    dmg_frac = torch.where((mcat > 0).unsqueeze(3) & (pow_eff > 0.0), dmg_frac, torch.zeros_like(dmg_frac))

    # Fixed-damage moves (Seismic Toss / Night Shade / Ruination / Super Fang) respecting type immunity
    fixed100 = (mf[:, :, :, 6:7] > 0.5) & (eff > 0.0)
    halfhp = (mf[:, :, :, 7:8] > 0.5) & (eff > 0.0)
    dmg_frac = torch.where(fixed100, 100.0 / def_maxhp, dmg_frac)
    def_cur_hp_frac = def_mn[:, :, 3].unsqueeze(1).unsqueeze(2).expand_as(dmg_frac)
    dmg_frac = torch.where(halfhp, 0.5 * def_cur_hp_frac, dmg_frac)

    # Mask dead attackers or dead defenders
    atk_alive = (atk_mn[:, :, 2] > 0.5).unsqueeze(2).unsqueeze(3)
    def_alive = (def_mn[:, :, 2] > 0.5).unsqueeze(1).unsqueeze(2)
    dmg_frac = torch.where(atk_alive & def_alive, dmg_frac.clamp(0.0, 2.0), torch.zeros_like(dmg_frac))

    # Drain heal fraction of attacker max HP
    atk_maxhp = (atk_mn[:, :, 4] * 500.0).clamp(min=1.0).unsqueeze(2).unsqueeze(3)
    dealt_frac_of_def = torch.minimum(dmg_frac, def_cur_hp_frac)
    drain_heal = (dealt_frac_of_def * mdrain.unsqueeze(3) * (def_maxhp / atk_maxhp)).clamp(0.0, 1.0)
    return dmg_frac, mprio, drain_heal


def _side_mon_features(
    own_mn: torch.Tensor,
    own_mc: torch.Tensor,
    opp_mn: torch.Tensor,
    opp_mc: torch.Tensor,
    own_sc: torch.Tensor,
    opp_sc: torch.Tensor,
    field: torch.Tensor,
    dmg_me_to_opp: torch.Tensor,   # [B, 6, 4, 6]
    prio_me: torch.Tensor,         # [B, 6, 4]
    drain_me: torch.Tensor,        # [B, 6, 4, 6]
    dmg_opp_to_me: torch.Tensor,   # [B, 6, 4, 6]
    drain_opp: torch.Tensor,       # [B, 6, 4, 6]
    own_spe: torch.Tensor,         # [B, 6]
    opp_spe: torch.Tensor,         # [B, 6]
    own_passive: torch.Tensor,     # [B, 6]
    opp_passive: torch.Tensor,     # [B, 6]
    own_entry: torch.Tensor,       # [B, 6]
    tables: MatchupTables,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Build `[B, 6, 37]` mechanical kit + matchup features for one side + active/team summaries for global diffs."""
    alive = (own_mn[:, :, 2] > 0.5).float()         # [B, 6]
    opp_alive = (opp_mn[:, :, 2] > 0.5).float()     # [B, 6]
    opp_alive_cnt = opp_alive.sum(dim=1, keepdim=True).clamp(min=1.0)  # [B, 1]

    it_f = tables.i_flags[own_mc[:, :, 2]]          # [B, 6, 13]
    ab_f = tables.a_flags[own_mc[:, :, 1]]          # [B, 6, 40]
    mf = tables.m_flags[own_mc[:, :, 6:10]]         # [B, 6, 4, 27]
    mdrain = tables.m_drain[own_mc[:, :, 6:10]]     # [B, 6, 4]
    opp_mf = tables.m_flags[opp_mc[:, :, 6:10]]

    # 23 mechanical kit & hazard flags per mon
    has_rec50 = (mf[:, :, :, 20].max(dim=2).values > 0.5).float()
    opp_has_rec50 = (opp_mf[:, :, :, 20].max(dim=2).values > 0.5).float()
    has_drain = (mdrain.max(dim=2).values > 0.0).float()
    has_setup = (mf[:, :, :, 21].max(dim=2).values > 0.5).float()
    has_prio = (prio_me.max(dim=2).values > 0.5).float()
    has_pivot = (mf[:, :, :, 22].max(dim=2).values > 0.5).float()
    has_haz_set = (mf[:, :, :, 23].max(dim=2).values > 0.5).float()
    has_haz_rem = (mf[:, :, :, 24].max(dim=2).values > 0.5).float()
    has_disrupt = (mf[:, :, :, 25].max(dim=2).values > 0.5).float()

    full_hp = (own_mn[:, :, 3] >= 0.999).float()
    poisoned = ((own_mn[:, :, 19] > 0.5) | (own_mn[:, :, 20] > 0.5)).float()

    kit = torch.stack([
        it_f[:, :, 0],                                               # air_balloon
        it_f[:, :, 1],                                               # choice_scarf
        ((it_f[:, :, 2] > 0.5) | (it_f[:, :, 3] > 0.5)).float(),     # choice_band_specs
        it_f[:, :, 4],                                               # life_orb
        it_f[:, :, 5],                                               # assault_vest
        it_f[:, :, 6] * full_hp,                                     # sash_intact
        ((it_f[:, :, 9] > 0.5) | (it_f[:, :, 10] > 0.5)).float(),    # eviolite/helmet/booster
        ab_f[:, :, 0],                                               # ground_immune_ab
        ab_f[:, :, 1],                                               # absorb_heal_ab
        ab_f[:, :, 2],                                               # absorb_boost_ab
        ab_f[:, :, 4] * full_hp,                                     # multiscale_intact
        ab_f[:, :, 5],                                               # regenerator
        ab_f[:, :, 6] * poisoned,                                    # poison_heal_active
        ab_f[:, :, 39],                                              # defensive_special_ab
        has_rec50,
        has_drain,
        has_setup,
        has_prio,
        has_pivot,
        has_haz_set,
        has_haz_rem,
        has_disrupt,
        own_entry,
    ], dim=-1) * alive.unsqueeze(-1)                                 # [B, 6, 23]

    # Best damage matrices [B, 6, 6]
    best_dmg = dmg_me_to_opp.max(dim=2).values                       # [B, 6, 6]
    best_drain = drain_me.max(dim=2).values                          # [B, 6, 6]
    opp_best_dmg = dmg_opp_to_me.max(dim=2).values                   # [B, 6(opp), 6(me)]
    opp_best_drain = drain_opp.max(dim=2).values                     # [B, 6(opp), 6(me)]

    # Matchup vs opposing active (index 0 of opp!)
    opp_act_hp = opp_mn[:, 0:1, 3].clamp(min=0.01)                   # [B, 1]
    my_hp = own_mn[:, :, 3].clamp(min=0.01)                          # [B, 6]

    dmg_vs_oa = best_dmg[:, :, 0]                                    # [B, 6]
    dmg_vs_oa_cur = (dmg_vs_oa / opp_act_hp).clamp(0.0, 2.0)         # [B, 6]
    prio_dmg_vs_oa = (dmg_me_to_opp[:, :, :, 0] * prio_me).max(dim=2).values
    prio_vs_oa_cur = (prio_dmg_vs_oa / opp_act_hp).clamp(0.0, 2.0)   # [B, 6]
    walled_by_oa = ((dmg_vs_oa < 0.05) & (own_mn[:, :, 2] > 0.5) & (opp_mn[:, 0:1, 2] > 0.5)).float()

    # Recovery-aware 2HKO vs opposing active
    oa_rec1 = opp_passive[:, 0:1].clamp(min=0.0) + opp_best_drain[:, 0, :]  # [B, 6]
    hp_after_2 = (opp_act_hp - dmg_vs_oa + oa_rec1).clamp(max=1.0) - dmg_vs_oa
    oa_rec50_blocks = (opp_has_rec50[:, 0:1] > 0.5) & (dmg_vs_oa < 0.52)
    net_2hko_oa = ((dmg_vs_oa >= opp_act_hp) | ((hp_after_2 <= 0.0) & (~oa_rec50_blocks))).float() * alive

    drain_vs_oa = best_drain[:, :, 0]                                # [B, 6]
    oa_dmg_to_me = opp_best_dmg[:, 0, :]                             # [B, 6]
    oa_dmg_to_my_cur = (oa_dmg_to_me / my_hp).clamp(0.0, 2.0)        # [B, 6]
    oa_walled_by_me = ((oa_dmg_to_me < 0.05) & (own_mn[:, :, 2] > 0.5) & (opp_mn[:, 0:1, 2] > 0.5)).float()

    tr = (field[:, 8:9] > 0.5)                                       # [B, 1]
    oa_spe = opp_spe[:, 0:1]                                         # [B, 1]
    raw_faster = torch.where(own_spe > oa_spe + 1e-3, 1.0, torch.where(own_spe < oa_spe - 1e-3, 0.0, 0.5))
    faster_oa = torch.where(tr, 1.0 - raw_faster, raw_faster) * alive

    # 6x6 Team coverage summaries against all alive opponents
    opp_mask = opp_alive.unsqueeze(1)                                # [B, 1, 6]
    mean_dmg_alive = (best_dmg * opp_mask).sum(dim=2) / opp_alive_cnt
    frac_2hko_alive = ((best_dmg >= 0.50).float() * opp_mask).sum(dim=2) / opp_alive_cnt
    frac_walled_alive = ((best_dmg < 0.15).float() * opp_mask).sum(dim=2) / opp_alive_cnt
    # Threat from alive opponents to each of my 6 mons
    opp_to_me_T = opp_best_dmg.transpose(1, 2)                       # [B, 6(me), 6(opp)]
    frac_threat_alive = ((opp_to_me_T >= 0.50).float() * opp_mask).sum(dim=2) / opp_alive_cnt

    pair = torch.stack([
        dmg_vs_oa.clamp(0.0, 2.0),
        dmg_vs_oa_cur,
        prio_vs_oa_cur,
        walled_by_oa,
        net_2hko_oa,
        drain_vs_oa,
        oa_dmg_to_me.clamp(0.0, 2.0),
        oa_dmg_to_my_cur,
        oa_walled_by_me,
        faster_oa,
        mean_dmg_alive.clamp(0.0, 2.0),
        frac_2hko_alive,
        frac_walled_alive,
        frac_threat_alive,
    ], dim=-1) * alive.unsqueeze(-1)                                 # [B, 6, 14]

    # Active & team scalars for exact antisymmetric global diffs
    act_off_boost = (own_mn[:, 0, 21].clamp(min=0.0) + own_mn[:, 0, 23].clamp(min=0.0) + own_mn[:, 0, 25].clamp(min=0.0))
    act_usable_boost = act_off_boost * (1.0 - walled_by_oa[:, 0])
    act_rec_power = own_passive[:, 0].clamp(min=0.0) + drain_vs_oa[:, 0] + 0.25 * has_rec50[:, 0] * (oa_dmg_to_me[:, 0] < 0.52).float()
    alive_cnt = alive.sum(dim=1).clamp(min=1.0)
    bench_alive = alive[:, 1:]
    bench_haz_sum = (own_entry[:, 1:] * bench_alive).sum(dim=1) / 5.0

    summary = dict(
        act_dmg=dmg_vs_oa[:, 0].clamp(0.0, 2.0),
        act_cur_dmg=dmg_vs_oa_cur[:, 0],
        act_walled=walled_by_oa[:, 0],
        act_net_2hko=net_2hko_oa[:, 0],
        act_faster=faster_oa[:, 0],
        act_prio_ko=(prio_vs_oa_cur[:, 0] >= 1.0).float(),
        act_rec_power=act_rec_power,
        act_usable_boost=act_usable_boost,
        team_mean_dmg=(mean_dmg_alive * alive).sum(dim=1) / alive_cnt,
        team_2hko_cov=(frac_2hko_alive * alive).sum(dim=1) / alive_cnt,
        team_walled=(frac_walled_alive * alive).sum(dim=1) / alive_cnt,
        bench_haz=bench_haz_sum,
    )
    return torch.cat([kit, pair], dim=-1), summary


def compute_matchup_features(
    mon_num: torch.Tensor,
    mon_cat_canon: torch.Tensor,
    global_num: torch.Tensor,
    tables: MatchupTables,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Compute `(mon_matchup[B, 12, 37], global_matchup[B, 12])` with EXACT zero-sum antisymmetry under side swap."""
    s1_mn, s2_mn = mon_num[:, 0:6, :], mon_num[:, 6:12, :]
    s1_mc, s2_mc = mon_cat_canon[:, 0:6, :], mon_cat_canon[:, 6:12, :]
    s1_sc, s2_sc = global_num[:, 0:11], global_num[:, 11:22]
    field = global_num[:, 26:35]

    s1_spe = _effective_speed(s1_mn, s1_mc, s1_sc, field, tables)
    s2_spe = _effective_speed(s2_mn, s2_mc, s2_sc, field, tables)
    s1_pass, s1_entry, s1_gnd = _passive_recovery_and_hazards(s1_mn, s1_mc, s1_sc, field, tables)
    s2_pass, s2_entry, s2_gnd = _passive_recovery_and_hazards(s2_mn, s2_mc, s2_sc, field, tables)

    dmg_12, prio_1, drain_12 = _pairwise_damage(s1_mn, s1_mc, s2_mn, s2_mc, s2_sc, field, s1_gnd, tables)
    dmg_21, prio_2, drain_21 = _pairwise_damage(s2_mn, s2_mc, s1_mn, s1_mc, s1_sc, field, s2_gnd, tables)

    f1, sum1 = _side_mon_features(
        s1_mn, s1_mc, s2_mn, s2_mc, s1_sc, s2_sc, field,
        dmg_12, prio_1, drain_12, dmg_21, drain_21,
        s1_spe, s2_spe, s1_pass, s2_pass, s1_entry, tables,
    )
    f2, sum2 = _side_mon_features(
        s2_mn, s2_mc, s1_mn, s1_mc, s2_sc, s1_sc, field,
        dmg_21, prio_2, drain_21, dmg_12, drain_12,
        s2_spe, s1_spe, s2_pass, s1_pass, s2_entry, tables,
    )

    mon_matchup = torch.cat([f1, f2], dim=1)  # [B, 12, 37]
    # Exact antisymmetric global matchup diffs (flipping s1 <-> s2 negates EVERY single one!)
    global_matchup = torch.stack([
        sum1['act_dmg'] - sum2['act_dmg'],
        sum1['act_cur_dmg'] - sum2['act_cur_dmg'],
        sum2['act_walled'] - sum1['act_walled'],          # positive = opp walled, negative = I am walled!
        sum1['act_net_2hko'] - sum2['act_net_2hko'],
        sum1['act_faster'] - sum2['act_faster'],
        sum1['act_prio_ko'] - sum2['act_prio_ko'],
        sum1['act_rec_power'] - sum2['act_rec_power'],
        sum1['act_usable_boost'] - sum2['act_usable_boost'],
        sum1['team_mean_dmg'] - sum2['team_mean_dmg'],
        sum1['team_2hko_cov'] - sum2['team_2hko_cov'],
        sum2['team_walled'] - sum1['team_walled'],
        sum2['bench_haz'] - sum1['bench_haz'],            # positive = opp takes more entry hazard damage
    ], dim=-1)                                            # [B, 12]
    return mon_matchup, global_matchup
