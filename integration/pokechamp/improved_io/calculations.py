"""Explicit scenario coverage from normalized observations, never opponent truth."""

from __future__ import annotations

import copy
import math
import time

from .calculator import CalculationError
from .state import STATS

WEATHER = {
    "SUNNYDAY": "Sun",
    "RAINDANCE": "Rain",
    "SANDSTORM": "Sand",
    "SNOWSCAPE": "Snow",
    "HAIL": "Hail",
    "DESOLATELAND": "Harsh Sunshine",
    "PRIMORDIALSEA": "Heavy Rain",
    "DELTASTREAM": "Strong Winds",
}
TERRAIN = {
    "ELECTRIC_TERRAIN": "Electric",
    "GRASSY_TERRAIN": "Grassy",
    "MISTY_TERRAIN": "Misty",
    "PSYCHIC_TERRAIN": "Psychic",
}
SIDES = {
    "STEALTH_ROCK": "isSR",
    "SPIKES": "spikes",
    "REFLECT": "isReflect",
    "LIGHT_SCREEN": "isLightScreen",
    "AURORA_VEIL": "isAuroraVeil",
    "TAILWIND": "isTailwind",
}
# These effects do not change single-hit damage; residual/status application remains
# visible in the observation and is not presented as computed by the damage engine.
NON_DAMAGE = {
    "TAUNT",
    "ENCORE",
    "DISABLE",
    "HEAL_BLOCK",
    "CONFUSION",
    "FLINCH",
    "LEECH_SEED",
    "SUBSTITUTE",
    "YAWN",
    "PROTECT",
    "ROOST",
    "FUTURE_SIGHT",
    "STICKY_WEB",  # Parser activation marker; the observed speed stage carries it.
}


def field_for(observation):
    field = {}
    weather = observation["weather"]
    if len(weather) > 1:
        raise CalculationError("ambiguous weather")
    for name in weather:
        if name not in WEATHER:
            raise CalculationError(f"unsupported weather: {name}")
        field["weather"] = WEATHER[name]
    for name in observation["field"]:
        if name in TERRAIN:
            field["terrain"] = TERRAIN[name]
        elif name in ("TRICK_ROOM",):
            continue  # Execution order, not the damage formula.
        elif name in ("GRAVITY", "MAGIC_ROOM", "WONDER_ROOM"):
            field[
                {
                    "GRAVITY": "isGravity",
                    "MAGIC_ROOM": "isMagicRoom",
                    "WONDER_ROOM": "isWonderRoom",
                }[name]
            ] = True
        else:
            raise CalculationError(f"unsupported field: {name}")
    for key, source in [
        ("attackerSide", "self_side_conditions"),
        ("defenderSide", "opponent_side_conditions"),
    ]:
        field[key] = {}
        for name, count in observation[source].items():
            if name in SIDES:
                field[key][SIDES[name]] = count if name == "SPIKES" else True
            elif observation.get("calculator_semantics") and name in (
                "TOXIC_SPIKES",
                "STICKY_WEB",
            ):
                field[key][
                    "toxicSpikes" if name == "TOXIC_SPIKES" else "isStickyWeb"
                ] = count if name == "TOXIC_SPIKES" else True
            elif name not in ("TOXIC_SPIKES", "STICKY_WEB", "WISH", "HEALING_WISH"):
                raise CalculationError(f"unsupported side effect: {name}")
    return field


def check_effects(mon):
    # Protect, Substitute and Roost cannot safely be ignored: the snapshot must
    # first establish their relevance to this decision phase.
    supported = NON_DAMAGE - {"SUBSTITUTE", "PROTECT", "ROOST"}
    supported |= {"PROTOSYNTHESIS", "QUARKDRIVE"}
    supported |= {"QUARK_DRIVE", "SUPREME_OVERLORD"}
    supported |= {f"FALLEN{n}" for n in range(1, 6)}
    supported |= {
        prefix + stat
        for prefix in ("PROTOSYNTHESIS", "QUARKDRIVE")
        for stat in ("ATK", "DEF", "SPA", "SPD", "SPE")
    }
    unsupported = set(mon["effects"]) - supported
    if unsupported:
        raise CalculationError(f"unsupported active effects: {sorted(unsupported)}")


def ability_effects(mon):
    result = {}
    fallen = [
        int(e[-1]) for e in mon["effects"] if e in {f"FALLEN{n}" for n in range(1, 6)}
    ]
    if "SUPREME_OVERLORD" in mon["effects"]:
        if len(fallen) != 1:
            raise CalculationError("missing or ambiguous public Supreme Overlord count")
        result["alliesFainted"] = fallen[0]
    elif fallen:
        raise CalculationError("public fallen count without Supreme Overlord effect")
    boosted = [
        effect[len(prefix) :].lower()
        for effect in mon["effects"]
        for prefix in ("PROTOSYNTHESIS", "QUARKDRIVE")
        if effect.startswith(prefix) and effect != prefix
    ]
    if len(boosted) > 1:
        raise CalculationError("ambiguous public boosted stat")
    if boosted:
        result.update(abilityOn=True, boostedStat=boosted[0])
    return result


def own_spec(mon):
    check_effects(mon)
    hp_part, *status = mon["condition"].split()
    if "/" not in hp_part:
        raise CalculationError("cannot calculate a fainted self target")
    hp, maximum = map(int, hp_part.split("/"))
    original = mon["original_set"]
    options = dict(
        level=original["level"],
        ability=""
        if mon.get("ability_history", {}).get("suppressed")
        else mon["ability"],
        item=mon["item"],
        nature=original["nature"],
        ivs=original["ivs"],
        evs=original["evs"],
        boosts={k: v for k, v in mon["boosts"].items() if k != "hp"},
        curHP=hp,
        status=status[0] if status else "",
    )
    options.update(ability_effects(mon))
    if mon.get("terastallized"):
        options["teraType"] = mon["terastallized"]
    from .lifecycle import entry_observed

    spec = {
        "name": mon["species"],
        "options": options,
        "expectedStats": {**mon["stats"], "hp": maximum},
        "entry_effects_observed": entry_observed(mon)
        if "ability_history" in mon
        else mon["active"],
    }
    if "battle_types" in mon:
        spec["battle_types"] = [t.title() for t in mon["battle_types"]]
        spec["projected_entry"] = not mon["active"]
        gender = next(
            (
                part.strip()
                for part in mon["details"].split(",")
                if part.strip() in ("M", "F")
            ),
            "N",
        )
        spec["options"]["gender"] = gender
        spec["qp_source"] = mon["ability_history"].get("qp_source")
        if not mon["active"] and mon["ability"] == "supremeoverlord":
            count = mon["ability_history"].get("team_faints")
            if count is None:
                raise CalculationError("unknown Supreme Overlord faint history")
            spec["options"]["alliesFainted"] = min(5, count)
    return spec


def public_hp_bounds(current, scale, maximum):
    """Pinned Gen9 getHealth: ceil percentages, except injured 100 is shown as 99."""
    if scale != 100 or not 1 <= current <= 100 or maximum < 1:
        raise CalculationError("unsupported public HP scale or living HP")
    # Match the server's floating-point evaluation order as well as its 99 cap.
    # At some exact percentages (e.g. HP7/max100), IEEE rounding precedes ceil.
    candidates = []
    for hp in range(1, maximum + 1):
        percentage = math.ceil((hp / maximum) * 100)
        if percentage == 100 and hp < maximum:
            percentage = 99
        if percentage == current:
            candidates.append(hp)
    if not candidates:
        raise CalculationError(
            "public HP has no possible integer value for this hypothesis"
        )
    return min(candidates), max(candidates)


def opponent_specs(mon, guesses):
    from poke_env.data import GenData

    check_effects(mon)
    base_hp = GenData.from_gen(9).pokedex[mon["species"]]["baseStats"]["hp"]
    for index, guess in enumerate(guesses):
        evs = dict(zip(STATS, guess["spread"]["stats"]))
        level = mon["level"]
        maximum = (
            math.floor((2 * base_hp + 31 + evs["hp"] // 4) * level / 100) + level + 10
        )
        if base_hp == 1:
            maximum = 1
        low, high = public_hp_bounds(mon["hp"], mon["max_hp"], maximum)
        for hp in sorted({low, high}):
            options = dict(
                level=level,
                ability=guess["ability"],
                item=guess["item"],
                nature=guess["spread"]["nature"],
                ivs=guess["ivs"],
                evs=evs,
                boosts={k: v for k, v in mon["boosts"].items() if k != "hp"},
                curHP=hp,
                status=(mon["status"] or "").lower(),
            )

            options.update(ability_effects(mon))
            if mon["tera_type"]:
                options["teraType"] = mon["tera_type"].title()
            spec = {
                "name": mon["species"],
                "options": options,
                "entry_effects_observed": True,
            }
            if "battle_types" in mon:
                spec["battle_types"] = [t.title() for t in mon["battle_types"]]
                spec["projected_entry"] = False
                spec["qp_source"] = mon["ability_history"].get("qp_source")
                if (
                    guess["ability"].lower().replace(" ", "") == "supremeoverlord"
                    and "alliesFainted" not in options
                ):
                    count = mon["ability_history"].get("team_faints")
                    if count is not None:
                        options["alliesFainted"] = min(5, count)
            yield (
                f"h{index}-hp{hp}",
                spec,
                guess,
            )


def tera_spec(mon, spec):
    """Selected tera happens before either move; it can also change form/ability."""
    spec = copy.deepcopy(spec)
    spec["options"]["teraType"] = mon["teraType"]
    forms = {
        "ogerpon": ("ogerpontealtera", "embodyaspectteal"),
        "ogerponhearthflame": ("ogerponhearthflametera", "embodyaspecthearthflame"),
        "ogerponwellspring": ("ogerponwellspringtera", "embodyaspectwellspring"),
        "ogerponcornerstone": ("ogerponcornerstonetera", "embodyaspectcornerstone"),
    }
    if mon["species"] in forms:
        spec["name"], spec["options"]["ability"] = forms[mon["species"]]
        spec["entry_effects_observed"] = False
    spec["tera_projection"] = dict(
        from_species=mon["species"],
        to_species=spec["name"],
        tera_type=mon["teraType"],
        ability=spec["options"]["ability"],
        phase="after selected terastallization, before either move's effects",
    )
    return spec


def _compute(value, calculator):
    started = time.monotonic()
    observation = value["current_observation"]
    field = field_for(observation)
    own = observation["self_team"]
    active = next((p for p in own if p["active"]), None)
    opponent = next((p for p in observation["opponent_confirmed"] if p["active"]), None)
    if opponent is None or opponent["fainted"]:
        if (
            (opponent is not None or (
                observation.get("observation_source", {}).get("version") == "official-client-v1"
                and observation.get("official_environment", {}).get("active_slots", {}).get(
                    "p2" if value["identity"]["actor_id"] == "p1" else "p1"
                ) == [None]
                and any(p["fainted"] for p in observation["opponent_confirmed"])
            ))
            and value["request"]["kind"] == "forced_switch"
            and all(
                set(action) == {"switch"}
                for action in value["request"]["legal_actions"]
            )
        ):
            # Simultaneous fainting legitimately requests a choice before the new
            # opponent is revealed. No hidden replacement or attack may fill it.
            result = calculator.calculate(value["identity"], [])
            coverage = [
                {
                    "scenario_id": f"switch-{action['switch']}-unknown-opponent",
                    "direction": "incoming",
                    "action": action,
                }
                for action in value["request"]["legal_actions"]
            ]
            return {
                **result,
                "coverage": coverage,
                "entries": [
                    {
                        "scenario_id": row["scenario_id"],
                        "excluded_with_reason": (
                            "opponent replacement not yet revealed; "
                            "incoming move, damage and execution UNKNOWN"
                        ),
                    }
                    for row in coverage
                ],
                "elapsed_ms": (time.monotonic() - started) * 1000,
                "uncertainty": "No living active opponent at forced replacement. "
                "No damage calculated; does not establish KO, survival "
                "or action execution.",
            }
        raise CalculationError("opponent active missing; damage phase unsupported")
    variants = list(opponent_specs(opponent, value["opponent_hypotheses"]))
    if not variants:
        raise CalculationError("empty opponent hypotheses")
    scenarios, coverage = [], []
    for action in value["request"]["legal_actions"]:
        kind, move = next(iter(action.items()))
        if kind == "switch":
            continue
        attacker = own_spec(active)
        if kind == "terastallize":
            if observation.get("calculator_semantics"):
                attacker = tera_spec(active, attacker)
            else:
                attacker = copy.deepcopy(attacker)
                attacker["options"]["teraType"] = active["teraType"]
        for name, defender, _ in variants:
            scenario_id = f"out-{kind}-{move}-{name}"
            scenarios.append(
                dict(
                    scenario_id=scenario_id,
                    attacker=attacker,
                    defender=defender,
                    move=move,
                    field=field,
                )
            )
            coverage.append(
                {
                    "scenario_id": scenario_id,
                    "direction": "outgoing",
                    "action": action,
                    "execution": (
                        "Future Sight is delayed until end of selection turn + 2 "
                        "if set successfully; range uses current "
                        "hypothetical target/field, "
                        "not future state or immediate damage"
                        if move == "futuresight"
                        else "conditional on hit; execution is not predicted"
                    ),
                }
            )
    targets = [p for p in own if p["active"] and "fnt" not in p["condition"]]
    switches = {a["switch"] for a in value["request"]["legal_actions"] if "switch" in a}
    targets += [p for p in own if p["species"] in switches]
    target_specs = [(target, own_spec(target), "") for target in targets]
    if (
        observation.get("calculator_semantics")
        and active in targets
        and any(
            "terastallize" in action for action in value["request"]["legal_actions"]
        )
    ):
        target_specs.append((active, tera_spec(active, own_spec(active)), "tera-"))
    for target, defender, mode in target_specs:
        for name, attacker, guess in variants:
            incoming = {
                **field,
                "attackerSide": field["defenderSide"],
                "defenderSide": field["attackerSide"],
            }
            for move in guess["moves"]:
                scenario_id = f"in-{mode}{target['species']}-{move}-{name}"
                scenarios.append(
                    dict(
                        scenario_id=scenario_id,
                        attacker=attacker,
                        defender=defender,
                        move=move,
                        field=incoming,
                    )
                )
                coverage.append(
                    {
                        "scenario_id": scenario_id,
                        "direction": "incoming",
                        "target": target["species"],
                        "move": move,
                        **(
                            {
                                "target_mode": (
                                    "after_terastallization_before_move_effects"
                                )
                            }
                            if mode
                            else {}
                        ),
                        "execution": (
                            "Future Sight is delayed; current hypothetical "
                            "target/field only; "
                            "future target, field and execution unknown"
                            if move == "futuresight"
                            else "conditional on hit; execution is not predicted"
                        ),
                    }
                )
    result = calculator.calculate(value["identity"], scenarios)
    return {
        **result,
        "coverage": coverage,
        "elapsed_ms": (time.monotonic() - started) * 1000,
        "pending_effects": copy.deepcopy(
            observation.get("protocol_state", {}).get("pending_effects", [])
        ),
        "uncertainty": (
            "Marginal prior combinations and rounded HP bounds, "
            "not exhaustive. "
            "Damage given hit does not establish KO, survival or action execution."
        ),
    }


def compute(value, calculator):
    from .lifecycle import VERSION
    from .state import stable_id

    result = _compute(value, calculator)
    if value["identity"].get("input_version") == VERSION:
        result["semantics_version"] = VERSION
        result["request_sha256"] = stable_id(calculator.last_request)
        result["bundle_sha256"] = stable_id(
            {k: v for k, v in result.items() if k != "elapsed_ms"}
        )
    return result
