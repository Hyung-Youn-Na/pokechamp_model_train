"""EX-067의 관측 전용·결정론적 Abyssal Tera 휴리스틱.

수치는 EX-067에서 사전 고정한 근사이며 완전한 damage calculator가 아니다.
상대 실제 세트/요청·추측 DB·simulator·미래 RNG를 읽지 않는다. 원타입과 현재
방어 타입은 따로 투영하여 pinned Pokemon.types/damage_multiplier를 사용하지 않는다.
지원하지 않는 피해 계산은 None으로 남기고 안전성의 근거로 사용하지 않는다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from functools import lru_cache
import hashlib
import json
import math

from poke_env.data import GenData, to_id_str
from poke_env.environment.double_battle import DoubleBattle
from poke_env.environment.move import Move
from poke_env.player.baselines import AbyssalPlayer


POLICY_ID = "abyssal-tera-v1"


@dataclass(frozen=True)
class TeraPolicyConfig:
    opponent_iv: int = 31
    opponent_ev_each: int = 84
    average_damage_roll: float = 0.925
    unrevealed_stab_power: int = 80
    finish_normal_cap: float = 0.9
    finish_tera_floor: float = 1.1
    finish_accuracy: float = 0.9
    speed_margin: float = 1.1
    finish_incoming_cap: float = 0.6
    defensive_incoming_floor: float = 0.4
    defensive_ratio_cap: float = 0.55
    defensive_incoming_cap: float = 0.6
    defensive_absolute_reduction: float = 0.05
    defensive_relative_reduction: float = 0.15
    boosted_stage: int = 2
    endgame_survivors: int = 2
    offensive_ratio_floor: float = 1.3
    offensive_absolute_gain: float = 0.1
    offensive_incoming_cap: float = 0.5
    safe_switch_hp_floor: float = 0.5
    safe_switch_incoming_cap: float = 0.4

    def as_dict(self):
        return asdict(self)


DEFAULT_CONFIG = TeraPolicyConfig()


def _config_dict(config=None):
    value = DEFAULT_CONFIG.as_dict() if config is None else (
        config.as_dict() if isinstance(config, TeraPolicyConfig) else dict(config)
    )
    if value != DEFAULT_CONFIG.as_dict():
        raise ValueError("abyssal-tera-v1 configuration is frozen; use a new policy version")
    return value


def policy_config_hash(config=None):
    payload = dict(policy_id=POLICY_ID, config=_config_dict(config))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


POLICY_CONFIG_HASH = policy_config_hash()


def _name(value):
    return to_id_str(getattr(value, "name", value) or "")


def _names(values):
    return frozenset(_name(v) for v in values)


def _stage(value):
    value = max(-6, min(6, value))
    return (2 + value) / 2 if value >= 0 else 2 / (2 - value)


@dataclass(frozen=True)
class MonProjection:
    species: str
    level: int
    stats: dict
    boosts: dict
    hp: float
    max_hp: float
    original_types: tuple[str, ...]
    defensive_types: tuple[str, ...]
    tera_type: str
    terastallized: bool
    ability: str
    item: str
    status: str
    effects: frozenset[str]
    weight: float


def project_mon(mon, *, own: bool, tera_type=None):
    """관측의 복사본만 반환하며 상대 stats/실제 HP/설정 Tera는 읽지 않는다."""
    level = mon.level
    base = mon.base_stats
    assumed = {key: math.floor((2 * value + DEFAULT_CONFIG.opponent_iv
                               + DEFAULT_CONFIG.opponent_ev_each // 4) * level / 100)
               + (level + 10 if key == "hp" else 5) for key, value in base.items()}
    if mon.species == "shedinja":
        assumed["hp"] = 1
    stats = dict(mon.stats or {}) if own else assumed
    max_hp = mon.max_hp if own else assumed["hp"]
    if not max_hp or any(not isinstance(stats.get(k), (int, float)) or stats[k] <= 0
                         for k in ("atk", "def", "spa", "spd", "spe")):
        raise ValueError("missing own request stats or maximum HP")
    # These fields store publicly observed original typing, not hidden team data.
    originals = tuple(_name(t) for t in (mon._type_1, mon._type_2) if t is not None)
    already = bool(mon.terastallized)
    actual_tera = _name(mon._terastallized_type) if already else ""
    target_tera = _name(tera_type) or actual_tera
    applying = bool(target_tera) and not already
    ability, boosts = _name(mon.ability), dict(mon.boosts)
    species = _name(mon.species)
    if applying and species.startswith("ogerpon"):
        form, stat = ("wellspring", "spd") if "wellspring" in species else (
            ("hearthflame", "atk") if "hearthflame" in species else (
                ("cornerstone", "def") if "cornerstone" in species else ("teal", "spe")))
        ability = "embodyaspect" + form
        boosts[stat] = min(6, boosts.get(stat, 0) + 1)
    return MonProjection(
        species, level, stats, boosts, float(mon.current_hp_fraction), float(max_hp),
        originals, (target_tera,) if target_tera and target_tera != "stellar" else originals,
        target_tera, already or applying, ability, _name(mon.item), _name(mon.status),
        _names(mon.effects), float(mon.weight),
    )


@dataclass(frozen=True)
class Context:
    weather: str = ""
    fields: frozenset[str] = frozenset()
    self_conditions: frozenset[str] = frozenset()
    opponent_conditions: frozenset[str] = frozenset()

    @classmethod
    def from_battle(cls, battle, own, opponent):
        weather = next(iter(sorted(_names(battle.weather))), "")
        if {own.ability, opponent.ability} & {"airlock", "cloudnine"}:
            weather = ""
        return cls(weather, _names(battle.fields), _names(battle.side_conditions),
                   _names(battle.opponent_side_conditions))


@lru_cache(maxsize=1)
def _chart():
    return GenData.from_gen(9).type_chart


def type_multiplier(move_type, types):
    result = 1.0
    for typ in types:
        result *= _chart()[typ.upper()][move_type.upper()]
    return result


def stab_multiplier(mon, move_type):
    original = move_type in mon.original_types
    tera = mon.terastallized and move_type == mon.tera_type
    result = 2.0 if original and tera else 1.5 if original or tera else 1.0
    if mon.ability == "adaptability" and (not mon.terastallized or tera):
        result = 2.25 if result == 2 else 2.0 if result == 1.5 else result
    return result


def grounded(mon, context):
    if "gravity" in context.fields or mon.item == "ironball" or mon.effects & {"smackdown", "ingrain"}:
        return True
    return not ("flying" in mon.defensive_types or mon.ability == "levitate"
                or mon.item == "airballoon" or mon.effects & {"magnetrise", "telekinesis"})


def effective_stat(mon, stat, context, *, ignore_boost=False, ignore_modifiers=False):
    value = mon.stats[stat] * (1 if ignore_boost else _stage(mon.boosts.get(stat, 0)))
    if ignore_modifiers:
        return value
    ability, item, weather = mon.ability, mon.item, context.weather
    if stat == "atk":
        if ability in {"hugepower", "purepower"}:
            value *= 2
        if ability == "hustle" or ability == "guts" and mon.status:
            value *= 1.5
        if item == "choiceband":
            value *= 1.5
    if stat == "spa":
        if item == "choicespecs":
            value *= 1.5
        if ability == "solarpower" and weather in {"sunnyday", "desolateland"}:
            value *= 1.5
    if stat == "spd":
        if item == "assaultvest":
            value *= 1.5
        if weather == "sandstorm" and "rock" in mon.defensive_types:
            value *= 1.5
    if stat == "def":
        if ability == "furcoat":
            value *= 2
        if weather in {"snow", "snowscape"} and "ice" in mon.defensive_types:
            value *= 1.5
        if ability == "marvelscale" and mon.status:
            value *= 1.5
    if stat in {"def", "spd"} and item == "eviolite":
        if GenData.from_gen(9).pokedex.get(mon.species, {}).get("evos"):
            value *= 1.5
    if item == "lightball" and mon.species == "pikachu" and stat in {"atk", "spa"}:
        value *= 2
    if ability == "defeatist" and mon.hp <= 0.5 and stat in {"atk", "spa"}:
        value *= 0.5
    if ability == "slowstart" and "slowstart" in mon.effects and stat in {"atk", "spe"}:
        value *= 0.5
    if stat == "spe":
        if mon.status == "par" and ability != "quickfeet":
            value *= 0.5
        if item == "choicescarf":
            value *= 1.5
        if item in {"ironball", "machobrace", "powerweight", "powerbracer", "powerbelt",
                    "powerlens", "powerband", "poweranklet"}:
            value *= 0.5
        speed_weather = {"chlorophyll": {"sunnyday", "desolateland"},
                         "swiftswim": {"raindance", "primordialsea"},
                         "sandrush": {"sandstorm"}, "slushrush": {"snow", "snowscape", "hail"}}
        if weather in speed_weather.get(ability, set()):
            value *= 2
        if ability == "surgesurfer" and "electricterrain" in context.fields:
            value *= 2
        if ability == "quickfeet" and mon.status:
            value *= 1.5
        if ability == "unburden" and "unburden" in mon.effects:
            value *= 2
    for ability_name, effect_prefix in (("protosynthesis", "protosynthesis"), ("quarkdrive", "quarkdrive")):
        if ability == ability_name and effect_prefix + stat in mon.effects:
            value *= 1.5 if stat == "spe" else 1.3
    return value


_CONDITIONAL_PRIORITY = frozenset({"suckerpunch", "thunderclap", "fakeout", "firstimpression"})
_SUPPORTED_DYNAMIC = frozenset({"terablast", "bodypress", "weatherball", "heavyslam", "heatcrash",
    "lowkick", "grassknot", "ivycudgel", "freezedry", "facade", "hex", "venoshock", "brine",
    "acrobatics", "eruption", "waterspout", "dragonenergy", "electroball", "gyroball", "knockoff",
    "foulplay", "ruination", "superfang", "naturesmadness", "suckerpunch", "thunderclap"})
_DAMAGE_CALLBACKS = frozenset({"basePowerCallback", "damageCallback", "onBasePower", "onModifyType",
                              "onEffectiveness", "onModifyMove"})
_UNSUPPORTED_MOVES = frozenset({"counter", "mirrorcoat", "metalburst", "bide", "endeavor",
    "finalgambit", "fissure", "guillotine", "horndrill", "sheercold", "present", "magnitude",
    "naturalgift", "beatup", "ragefist", "lastrespects", "rollout", "iceball", "furycutter",
    "storedpower", "powertrip", "assurance", "revenge", "avalanche", "pursuit", "retaliate",
    "reversal", "flail", "trumpcard", "spitup", "return", "frustration", "painsplit", "struggle",
    "futuresight", "doomdesire", "shellsidearm", "photongeyser", "terastarstorm", "flyingpress",
    "thousandarrows", "expandingforce", "terrainpulse", "risingvoltage", "mistyexplosion",
    "populationbomb", "tripleaxel", "triplekick"})
_UNSUPPORTED_EFFECTS = frozenset({"transform", "powertrick", "powersplit", "guardsplit", "gastroacid",
                                "typechange", "typeadd", "powershift"})


@dataclass(frozen=True)
class Attack:
    move_id: str
    type: str
    category: str
    power: float
    accuracy: float
    priority: int
    entry: dict
    source: str = "revealed_move"

    @classmethod
    def from_move(cls, move):
        entry = move.entry
        return cls(move.id, _name(move.type), _name(move.category), float(move.base_power),
                   float(move.accuracy), move.priority, entry)


@dataclass(frozen=True)
class DamageEstimate:
    move_id: str
    damage: float | None
    accuracy: float
    priority: int
    type: str
    category: str
    offensive_stat: str
    source: str
    conditional: bool = False
    unsupported: str | None = None

    @property
    def score(self):
        return (self.damage or 0) * self.accuracy


def estimate_damage(attack, attacker, defender, context, *, attacking_own=True):
    """대상 최대 HP 대비 비급소·평균 난수 근사. None은 피해 0과 다르다."""
    if isinstance(attack, Move):
        attack = Attack.from_move(attack)
    mid, entry = attack.move_id, attack.entry
    typ, category, power = attack.type, attack.category, attack.power
    atkstat = entry.get("overrideOffensiveStat", "atk" if category == "physical" else "spa")
    conditional = mid in _CONDITIONAL_PRIORITY
    accuracy = attack.accuracy
    delta = max(-6, min(6, attacker.boosts.get("accuracy", 0) - defender.boosts.get("evasion", 0)))
    if entry.get("accuracy") is not True:
        accuracy *= (3 + delta) / 3 if delta >= 0 else 3 / (3 - delta)
        if attacker.ability == "compoundeyes":
            accuracy *= 1.3
        if attacker.item == "widelens":
            accuracy *= 1.1
        if attacker.ability == "hustle" and category == "physical":
            accuracy *= 0.8
    if "gravity" in context.fields:
        accuracy *= 5 / 3
    if mid in {"thunder", "hurricane"}:
        if context.weather in {"raindance", "primordialsea"}:
            accuracy = 1.0
        elif context.weather in {"sunnyday", "desolateland"}:
            accuracy = 0.5
    if mid == "blizzard" and context.weather in {"hail", "snow", "snowscape"}:
        accuracy = 1.0
    if "noguard" in {attacker.ability, defender.ability}:
        accuracy = 1.0
    priority = attack.priority
    if attacker.ability == "galewings" and typ == "flying" and attacker.hp == 1:
        priority += 1
    if mid == "grassyglide" and grounded(attacker, context) and "grassyterrain" in context.fields:
        priority += 1

    def result(damage=None, unsupported=None):
        return DamageEstimate(mid, damage, min(1.0, accuracy), priority, typ, category, atkstat,
                              attack.source, conditional, unsupported)

    if category == "status":
        return result(0)
    if attacker.tera_type == "stellar" or defender.tera_type == "stellar":
        return result(unsupported="stellar")
    if (attacker.effects | defender.effects) & _UNSUPPORTED_EFFECTS:
        return result(unsupported="unsupported_stat_or_ability_effect")
    if context.fields & {"magicroom", "wonderroom", "watersport", "mudsport"} or context.weather == "unknown":
        return result(unsupported="unsupported_field")
    if "neutralizinggas" in {attacker.ability, defender.ability}:
        return result(unsupported="unsupported_ability_suppression")
    if attacker.ability in {"analytic", "parentalbond", "stakeout", "rivalry", "sandforce", "reckless", "gorillatactics"}:
        return result(unsupported="unsupported_damage_ability")
    if defender.ability == "disguise" and "busted" not in defender.species or defender.ability == "iceface" and defender.species == "eiscue":
        return result(unsupported="unbroken_damage_shield")
    if "substitute" in defender.effects:
        return result(unsupported="substitute")
    if mid in _UNSUPPORTED_MOVES or entry.get("ohko") or entry.get("willCrit"):
        return result(unsupported="unsupported_move")
    if _DAMAGE_CALLBACKS & entry.keys() and mid not in _SUPPORTED_DYNAMIC:
        return result(unsupported="unsupported_move_callback")
    if entry.get("flags", {}).get("charge") or entry.get("selfdestruct") or entry.get("multiaccuracy"):
        return result(unsupported="non_immediate_or_conditional_move")
    if attacker.ability in {"protean", "libero", "normalize", "aerilate", "pixilate", "refrigerate", "galvanize"}:
        if not attacker.terastallized:
            return result(unsupported="unsupported_type_changing_ability")
    if mid == "terablast" and attacker.terastallized:
        typ = attacker.tera_type
        if effective_stat(attacker, "atk", context, ignore_modifiers=True) > effective_stat(attacker, "spa", context, ignore_modifiers=True):
            category = "physical"
            if attacker.ability == "hustle" and "noguard" not in {attacker.ability, defender.ability}:
                accuracy *= 0.8
        atkstat = "atk" if category == "physical" else "spa"
    elif mid == "weatherball" and context.weather:
        typ = {"sunnyday": "fire", "desolateland": "fire", "raindance": "water",
               "primordialsea": "water", "sandstorm": "rock", "hail": "ice",
               "snow": "ice", "snowscape": "ice"}.get(context.weather, "normal")
        power = 100 if typ != "normal" else 50
    elif mid == "ivycudgel":
        typ = next((t for form, t in (("wellspring", "water"), ("hearthflame", "fire"),
                                     ("cornerstone", "rock")) if form in attacker.species), "grass")
    elif mid in {"heavyslam", "heatcrash", "lowkick", "grassknot"}:
        def weight(mon):
            value = mon.weight * (2 if mon.ability == "heavymetal" else 0.5 if mon.ability == "lightmetal" else 1)
            return value * (0.5 if mon.item == "floatstone" else 1)
        target_weight = weight(defender)
        if target_weight <= 0 or attacker.effects & {"autotomize"} or defender.effects & {"autotomize"}:
            return result(unsupported="unknown_modified_weight")
        if mid in {"heavyslam", "heatcrash"}:
            ratio = weight(attacker) / target_weight
            power = 120 if ratio >= 5 else 100 if ratio >= 4 else 80 if ratio >= 3 else 60 if ratio >= 2 else 40
        else:
            power = 120 if target_weight >= 200 else 100 if target_weight >= 100 else 80 if target_weight >= 50 else 60 if target_weight >= 25 else 40 if target_weight >= 10 else 20
    elif mid in {"eruption", "waterspout", "dragonenergy"}:
        power = max(1, math.floor(150 * attacker.hp))
    elif mid == "electroball":
        ratio = effective_stat(attacker, "spe", context) / effective_stat(defender, "spe", context)
        power = 150 if ratio >= 4 else 120 if ratio >= 3 else 80 if ratio >= 2 else 60 if ratio >= 1 else 40
    elif mid == "gyroball":
        power = min(150, math.floor(25 * effective_stat(defender, "spe", context) / effective_stat(attacker, "spe", context)) + 1)
    elif mid == "acrobatics":
        if attacker.item == "unknownitem":
            return result(unsupported="unknown_item_for_acrobatics")
        power *= 2 if not attacker.item else 1
    elif mid == "knockoff":
        if defender.item == "unknownitem":
            return result(unsupported="unknown_item_for_knockoff")
        if defender.item and not (defender.item.endswith("mask") or defender.item in {"griseouscore", "adamantcrystal", "lustrousglobe"}):
            power *= 1.5
    elif mid == "facade" and attacker.status in {"brn", "par", "psn", "tox"}:
        power *= 2
    elif mid == "hex" and defender.status or mid == "venoshock" and defender.status in {"psn", "tox"} or mid == "brine" and defender.hp <= 0.5:
        power *= 2

    ignore_ability = bool(entry.get("ignoreAbility")) or attacker.ability in {"moldbreaker", "teravolt", "turboblaze"}
    defending_ability = "" if ignore_ability and defender.ability not in {"shadowshield", "prismarmor"} else defender.ability
    effectiveness = 1.0
    for dtype in defender.defensive_types:
        multiplier = type_multiplier(typ, (dtype,))
        if mid == "freezedry" and dtype == "water":
            multiplier = 2
        if multiplier == 0 and (defender.item == "ringtarget" or
                dtype == "ghost" and typ in {"normal", "fighting"} and attacker.ability in {"scrappy", "mindseye"} or
                dtype == "flying" and typ == "ground" and grounded(defender, context)):
            multiplier = 1
        if context.weather == "deltastream" and dtype == "flying" and multiplier > 1:
            multiplier = 1
        effectiveness *= multiplier
    immunity = {"electric": {"voltabsorb", "lightningrod", "motordrive"},
                "water": {"waterabsorb", "stormdrain", "dryskin"},
                "fire": {"flashfire", "wellbakedbody"}, "grass": {"sapsipper"},
                "ground": {"eartheater"}}
    flags = entry.get("flags", {})
    if defending_ability in immunity.get(typ, set()) or (
            typ == "ground" and not grounded(defender, context) and
            (defender.item == "airballoon" or defender.effects & {"magnetrise", "telekinesis"} or defending_ability == "levitate")):
        return result(0)
    if defending_ability == "wonderguard" and effectiveness <= 1 or (
            defending_ability == "bulletproof" and flags.get("bullet") or
            defending_ability == "soundproof" and flags.get("sound")):
        return result(0)
    if priority > 0 and (defending_ability in {"dazzling", "queenlymajesty", "armortail"} or
                        "psychicterrain" in context.fields and grounded(defender, context)):
        return result(0)
    if effectiveness == 0 or context.weather == "desolateland" and typ == "water" or context.weather == "primordialsea" and typ == "fire":
        return result(0)
    fixed = entry.get("damage")
    if fixed:
        return result((attacker.level if fixed == "level" else float(fixed)) / defender.max_hp)
    if mid in {"ruination", "superfang", "naturesmadness"}:
        return result(defender.hp / 2)
    if power <= 0:
        return result(unsupported="unknown_power")
    if attacker.terastallized and typ == attacker.tera_type and power < 60 and attack.priority <= 0 and not entry.get("multihit") and not entry.get("basePowerCallback"):
        power = 60
    if attacker.ability == "technician" and power <= 60:
        power *= 1.5
    if attacker.ability == "sharpness" and flags.get("slicing") or attacker.ability == "strongjaw" and flags.get("bite"):
        power *= 1.5
    if attacker.ability == "ironfist" and flags.get("punch"):
        power *= 1.2
    if attacker.ability == "toughclaws" and flags.get("contact"):
        power *= 1.3
    if attacker.ability == "sheerforce" and entry.get("secondary"):
        power *= 1.3
    if attacker.ability in {"blaze", "torrent", "overgrow", "swarm"} and attacker.hp <= 1 / 3:
        if typ == {"blaze": "fire", "torrent": "water", "overgrow": "grass", "swarm": "bug"}[attacker.ability]:
            power *= 1.5
    if attacker.ability in {"waterbubble", "steelworker", "dragonsmaw", "transistor"}:
        boost_type, factor = {"waterbubble": ("water", 2), "steelworker": ("steel", 1.5),
                             "dragonsmaw": ("dragon", 1.5), "transistor": ("electric", 1.3)}[attacker.ability]
        if typ == boost_type:
            power *= factor
    if attacker.item.endswith("mask") and attacker.species.startswith("ogerpon"):
        power *= 1.2
    if attacker.ability == "supremeoverlord":
        fallen = max((int(e[-1]) for e in attacker.effects if len(e) == 7 and e.startswith("fallen") and e[-1] in "12345"), default=0)
        if "fallen" in attacker.effects:
            return result(unsupported="unknown_supreme_overlord_count")
        power *= 1 + 0.1 * fallen
    if "charge" in attacker.effects and typ == "electric":
        power *= 2
    if attacker.ability == "flashfire" and "flashfire" in attacker.effects and typ == "fire":
        power *= 1.5
    stat_owner = defender if mid == "foulplay" else attacker
    defense_stat = entry.get("overrideDefensiveStat", "def" if category == "physical" else "spd")
    # Showdown first selects the raw offensive stat and its stages, then runs
    # ModifyAtk/ModifySpA for the move category on the actual move user. Body
    # Press therefore gets Choice Band/Guts, but not Eviolite/Fur Coat/snow.
    offense = effective_stat(stat_owner, atkstat, context, ignore_boost=defending_ability == "unaware", ignore_modifiers=True)
    modifier_stat = "atk" if category == "physical" else "spa"
    offense *= effective_stat(attacker, modifier_stat, context, ignore_boost=True) / attacker.stats[modifier_stat]
    defense = effective_stat(replace(defender, ability=defending_ability), defense_stat, context,
                             ignore_boost=bool(entry.get("ignoreDefensive")) or attacker.ability == "unaware")
    # Public Ruin holders affect the other active Pokemon. These field abilities
    # are not breakable by Mold Breaker, and a holder is exempt from its own Ruin.
    offensive_ruin = "tabletsofruin" if category == "physical" else "vesselofruin"
    defensive_ruin = "swordofruin" if defense_stat == "def" else "beadsofruin"
    if defender.ability == offensive_ruin and attacker.ability != offensive_ruin:
        offense *= 0.75
    if attacker.ability == defensive_ruin and defender.ability != defensive_ruin:
        defense *= 0.75
    damage = ((2 * attacker.level / 5 + 2) * power * offense / defense / 50 + 2)
    damage *= DEFAULT_CONFIG.average_damage_roll * stab_multiplier(attacker, typ) * effectiveness
    if category == "physical" and attacker.status == "brn" and attacker.ability != "guts" and mid != "facade":
        damage *= 0.5
    if context.weather in {"sunnyday", "desolateland"}:
        damage *= 1.5 if typ == "fire" else 0.5 if typ == "water" else 1
    elif context.weather in {"raindance", "primordialsea"}:
        damage *= 1.5 if typ == "water" else 0.5 if typ == "fire" else 1
    if grounded(attacker, context) and {"electric": "electricterrain", "grass": "grassyterrain", "psychic": "psychicterrain"}.get(typ) in context.fields:
        damage *= 1.3
    if grounded(defender, context):
        if "mistyterrain" in context.fields and typ == "dragon" or "grassyterrain" in context.fields and mid in {"earthquake", "bulldoze", "magnitude"}:
            damage *= 0.5
    target_conditions = context.opponent_conditions if attacking_own else context.self_conditions
    if "auroraveil" in target_conditions or ("reflect" if category == "physical" else "lightscreen") in target_conditions:
        if attacker.ability != "infiltrator" and mid not in {"brickbreak", "psychicfangs", "ragingbull"}:
            damage *= 0.5
    first_hit_multiplier = 0.5 if defending_ability in {"multiscale", "shadowshield"} and defender.hp == 1 else 1.0
    if defending_ability in {"filter", "solidrock", "prismarmor"} and effectiveness > 1:
        damage *= 0.75
    if defending_ability == "thickfat" and typ in {"fire", "ice"} or defending_ability == "heatproof" and typ == "fire" or defending_ability == "waterbubble" and typ == "fire":
        damage *= 0.5
    if defending_ability == "fluffy":
        damage *= (0.5 if flags.get("contact") and attacker.ability != "longreach" else 1) * (2 if typ == "fire" else 1)
    if defending_ability == "purifyingsalt" and typ == "ghost" or defending_ability == "icescales" and category == "special":
        damage *= 0.5
    if defending_ability == "dryskin" and typ == "fire":
        damage *= 1.25
    if attacker.ability == "tintedlens" and effectiveness < 1:
        damage *= 2
    if attacker.item == "lifeorb":
        damage *= 1.3
    if attacker.item == "expertbelt" and effectiveness > 1:
        damage *= 1.2
    if attacker.item == "muscleband" and category == "physical" or attacker.item == "wiseglasses" and category == "special":
        damage *= 1.1
    hits = entry.get("multihit", 1)
    if isinstance(hits, (tuple, list)):
        if list(hits) != [2, 5]:
            return result(unsupported="unsupported_multi_hit")
        hits = 5 if attacker.ability == "skilllink" else 4.5 if attacker.item == "loadeddice" else 3.1
    damage *= hits - 1 + first_hit_multiplier
    if defender.hp == 1 and (defending_ability == "sturdy" or defender.item == "focussash") and hits == 1:
        damage = min(damage, defender.max_hp - 1)
    return result(max(0.0, damage / defender.max_hp))


class AbyssalTeraPlayer(AbyssalPlayer):
    policy_id = POLICY_ID

    def __init__(self, *args, policy_config=None, **kwargs):
        self.policy_config = _config_dict(policy_config)
        self.policy_config_hash = policy_config_hash(self.policy_config)
        self.last_policy_audit = None
        self._tera_public_moves = {}
        self._tera_non_slot_moves = {}
        self._tera_transformed = set()
        super().__init__(*args, **kwargs)

    @staticmethod
    def _identifier(identifier):
        role, name = identifier.split(":", 1)
        return role[:2] + ":" + name

    def observe_public_move(self, identifier, move_id):
        """Actor가 공개 프로토콜에서 호출한다. 요청/숨은 기술을 전달하지 않는다."""
        key = self._identifier(identifier)
        mid = Move.retrieve_id(move_id)
        if mid != "struggle":
            self._tera_public_moves.setdefault(key, set()).add(mid)

    def observe_public_line(self, line):
        parts = line.split("|")
        if len(parts) < 3:
            return
        kind, identifier = parts[1:3]
        if kind == "move" and len(parts) >= 4:
            origins = [p.removeprefix("[from]").strip() for p in parts[4:] if p.startswith("[from]")]
            called = next((p.split(":", 1)[1].strip() for p in origins if p.startswith("move:")), None)
            via_ability = any(p.startswith("ability:") for p in origins)
            key, mid = self._identifier(identifier), Move.retrieve_id(parts[3])
            if via_ability or mid == "struggle" or called and to_id_str(called) != "sleeptalk":
                self._tera_non_slot_moves.setdefault(key, set()).add(mid)
            if via_ability or mid == "struggle":
                return
            if called:
                self.observe_public_move(identifier, called)
            if not called or to_id_str(called) == "sleeptalk":
                self.observe_public_move(identifier, parts[3])
        elif kind == "-transform":
            self._tera_transformed.add(self._identifier(identifier))
        # A transformed Pokemon remains unsupported after switching: the pinned
        # observer does not prove restoration of its original type/stat fields.

    def _incoming_attacks(self, battle, opponent):
        mon = battle.opponent_active_pokemon
        key = next((k for k, p in battle.opponent_team.items() if p is mon), None)
        # The pinned parser can store bounced/copied attacks as real moves. A
        # public non-slot event cannot fill a hidden slot; a genuine use of the
        # same move still provides positive evidence that it belongs to the set.
        known = ((set(mon.moves) - self._tera_non_slot_moves.get(key, set()))
                 | self._tera_public_moves.get(key, set())) - {"struggle"}
        attacks = []
        for mid in sorted(known):
            attack = Attack.from_move(Move(mid, gen=9))
            if attack.category != "status":
                attacks.append(attack)
        if len(known) < 4:
            for typ in sorted(set(opponent.original_types) | set(opponent.defensive_types)):
                for category in ("physical", "special"):
                    attacks.append(Attack("assumed-stab-" + typ + "-" + category, typ, category,
                        DEFAULT_CONFIG.unrevealed_stab_power, 1.0, 0,
                        dict(accuracy=100), "unrevealed_stab_assumption"))
        return attacks

    @staticmethod
    def _risk(attacks, opponent, defender, context):
        values = [estimate_damage(a, opponent, defender, context, attacking_own=False) for a in attacks]
        complete = all(v.damage is not None for v in values)
        return (max((v.damage for v in values), default=0.0) if complete else None), values

    @staticmethod
    def _best(values):
        supported = [v for v in values if v.damage is not None and v.damage > 0 and not v.conditional]
        return max(supported, key=lambda v: v.score, default=None)

    def _safe_switch(self, battle, opponent, attacks, context):
        for mon in battle.available_switches:
            switch = project_mon(mon, own=True)
            if switch.hp < DEFAULT_CONFIG.safe_switch_hp_floor:
                continue
            if switch.item != "heavydutyboots" and switch.ability != "magicguard":
                if "stealthrock" in context.self_conditions or "spikes" in context.self_conditions and grounded(switch, context):
                    continue
            matchup = max(type_multiplier(t, opponent.defensive_types) for t in switch.defensive_types)
            matchup -= max(type_multiplier(t, switch.defensive_types) for t in opponent.defensive_types)
            matchup += (0.1 if switch.stats["spe"] > opponent.stats["spe"] else -0.1 if switch.stats["spe"] < opponent.stats["spe"] else 0)
            matchup += 0.4 * (switch.hp - opponent.hp)
            risk, _ = self._risk(attacks, opponent, switch, context)
            if matchup > 0 and risk is not None and risk <= DEFAULT_CONFIG.safe_switch_incoming_cap * switch.hp:
                return True
        return False

    @staticmethod
    def _first(attack, incoming, own, opponent, context):
        if attack.conditional or own.item in {"laggingtail", "fullincense"} or own.ability == "stall":
            return False
        if opponent.item in {"quickclaw", "custapberry"} or opponent.ability in {"quickdraw"}:
            return False
        priority = max((a.priority for a in incoming), default=0)
        if attack.priority != priority:
            return attack.priority > priority
        own_speed = effective_stat(own, "spe", context) * (2 if "tailwind" in context.self_conditions else 1)
        opp_speed = effective_stat(opponent, "spe", context) * (2 if "tailwind" in context.opponent_conditions else 1)
        return opp_speed >= DEFAULT_CONFIG.speed_margin * own_speed if "trickroom" in context.fields else own_speed >= DEFAULT_CONFIG.speed_margin * opp_speed

    @staticmethod
    def _utility(move, own, context):
        entry = move.entry
        if entry.get("selfSwitch") or move.is_protect_move or move.side_condition:
            return False
        if _name(move.category) != "status" or own.status in {"slp", "frz"} or "taunt" in own.effects:
            return False
        if move.target == "self" and move.boosts and any(
                amount * (-1 if own.ability == "contrary" else 1) > 0 and own.boosts.get(stat, 0) < 6
                for stat, amount in move.boosts.items()):
            return True
        healing = move.heal > 0 or move.id in {"synthesis", "moonlight", "morningsun", "shoreup", "rest"}
        if not healing or move.target not in {"self", "allies"} or own.hp >= 1 or "healblock" in own.effects:
            return False
        if move.id == "rest" and (own.ability in {"insomnia", "vitalspirit", "comatose"} or
                grounded(own, context) and context.fields & {"electricterrain", "mistyterrain"}):
            return False
        return True

    def choose_move(self, battle):
        # Exactly one canonical call, even for forced switches/unsupported states.
        baseline = super().choose_move(battle)
        audit = dict(policy_id=POLICY_ID, config_hash=self.policy_config_hash,
                     turn=battle.turn, reason="baseline_preserved", used_tera=False,
                     terastallize=False, already_tera=bool(getattr(battle.active_pokemon, "terastallized", False)),
                     baseline_command=getattr(baseline, "message", None))
        self.last_policy_audit = audit
        if isinstance(battle, DoubleBattle) or battle.force_switch or not battle.available_moves:
            audit["reason"] = "forced_or_unsupported_battle"
            return baseline
        if self._tera_transformed:
            active_keys = {k for team in (battle.team, battle.opponent_team) for k, p in team.items()
                           if p is battle.active_pokemon or p is battle.opponent_active_pokemon}
            if active_keys & self._tera_transformed:
                audit["reason"] = "unsupported_transform"
                return baseline
        try:
            own = project_mon(battle.active_pokemon, own=True)
            opponent = project_mon(battle.opponent_active_pokemon, own=False)
        except ValueError as error:
            audit.update(reason="unsupported_projection", unsupported=str(error))
            return baseline
        context = Context.from_battle(battle, own, opponent)
        moves = {m.id: m for m in battle.available_moves}
        attacks = [replace(Attack.from_move(m), source="own_move") for m in moves.values()
                   if _name(m.category) != "status" and not m.self_switch]
        ordinary = [estimate_damage(a, own, opponent, context) for a in attacks]
        best0 = self._best(ordinary)
        if own.status in {"slp", "frz"}:
            audit["reason"] = "cannot_confirm_immediate_action"
            return baseline
        eligible = bool(battle.can_tera) and not own.terastallized and _name(battle.can_tera) != "stellar"
        if eligible:
            tera = project_mon(battle.active_pokemon, own=True, tera_type=battle.can_tera)
            tera_context = Context.from_battle(battle, tera, opponent)
            upgraded = [estimate_damage(a, tera, opponent, tera_context) for a in attacks]
            best_t = self._best(upgraded)
            incoming = self._incoming_attacks(battle, opponent)
            i0, threats0 = self._risk(incoming, opponent, own, context)
            it, threats_t = self._risk(incoming, opponent, tera, tera_context)
            ordinary_complete = bool(ordinary) and all(v.damage is not None for v in ordinary)
            # A known immune attack can be zero; an unsupported normal attack
            # cannot be turned into a zero baseline to manufacture Tera gain.
            ordinary_best = max(ordinary, key=lambda v: v.score, default=None) if ordinary_complete else None
            o0 = ordinary_best.damage if ordinary_best else 0 if ordinary_complete else None
            ot = best_t.damage if best_t else None
            audit.update(metrics=dict(h=own.hp, e=opponent.hp, I0=i0, IT=it, O0=o0, OT=ot),
                         incoming_sources=[dict(move_id=a.move_id, source=a.source) for a in incoming],
                         unsupported=sorted({v.unsupported + ":" + v.move_id for v in ordinary + upgraded + threats0 + threats_t if v.unsupported}))
            selected, reason = None, None
            cfg = DEFAULT_CONFIG
            if best_t and o0 is not None and o0 <= cfg.finish_normal_cap * opponent.hp and ot >= cfg.finish_tera_floor * opponent.hp and best_t.accuracy >= cfg.finish_accuracy:
                first = self._first(best_t, threats_t, tera, opponent, tera_context)
                audit["expected_first"] = first
                if first or it is not None and it <= cfg.finish_incoming_cap * own.hp:
                    selected, reason = moves[best_t.move_id], "offensive_finish"
            if selected is None and i0 is not None and it is not None and (
                    i0 >= cfg.defensive_incoming_floor * own.hp and it <= cfg.defensive_ratio_cap * i0
                    and it <= cfg.defensive_incoming_cap * own.hp
                    and i0 - it >= max(cfg.defensive_absolute_reduction, cfg.defensive_relative_reduction * own.hp)):
                safe_switch = self._safe_switch(battle, opponent, incoming, context)
                preserve_boost = any(own.boosts.get(s, 0) >= cfg.boosted_stage for s in ("atk", "def", "spa", "spd", "spe"))
                audit.update(safe_switch=safe_switch, preserve_boost=preserve_boost)
                if not safe_switch or preserve_boost:
                    baseline_move = getattr(baseline, "order", None)
                    if isinstance(baseline_move, Move) and self._utility(baseline_move, tera, tera_context):
                        selected = baseline_move
                    elif best_t:
                        selected = moves[best_t.move_id]
                    else:
                        selected = next((m for m in moves.values() if self._utility(m, tera, tera_context)), None)
                    if selected:
                        reason = "defensive_stabilization"
            if selected is None and best_t and o0 is not None and it is not None:
                survivors = sum(not mon.fainted for mon in battle.team.values())
                boosted = own.boosts.get(best_t.offensive_stat, 0) >= cfg.boosted_stage
                if ((boosted or survivors <= cfg.endgame_survivors) and ot >= cfg.offensive_ratio_floor * o0
                        and ot - o0 >= cfg.offensive_absolute_gain and it <= cfg.offensive_incoming_cap * own.hp):
                    selected, reason = moves[best_t.move_id], "boosted_or_endgame_offense"
            if selected is not None:
                audit.update(reason=reason, used_tera=True, terastallize=True, selected_move=selected.id)
                return self.create_order(selected, terastallize=True)
        else:
            audit["reason"] = "tera_unavailable_or_stellar"
        # Keep utility and switch decisions. Correct attack scores after either
        # active has Tera, including original STAB and Tera Blast's actual type.
        baseline_move = getattr(baseline, "order", None)
        baseline_supported = isinstance(baseline_move, Move) and any(v.move_id == baseline_move.id and v.damage is not None for v in ordinary)
        current_best = max((v for v in ordinary if v.damage is not None and v.damage > 0),
                           key=lambda v: v.score, default=None)
        if (own.terastallized or opponent.terastallized) and current_best and baseline_supported:
            if current_best.move_id != baseline_move.id:
                audit.update(reason="post_tera_attack_rescore", selected_move=current_best.move_id)
                return self.create_order(moves[current_best.move_id])
        return baseline
