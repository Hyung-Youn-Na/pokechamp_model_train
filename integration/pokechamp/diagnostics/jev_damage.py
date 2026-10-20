"""Offline active-versus-active damage envelopes; no model or battle runner.

Only the caller's submitted team and one bounded actor observation can enter.
The returned audit, unlike the compact payload, retains every candidate/scenario.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

from .damage_sets import candidates, digest, public_history, token
from ..improved_io.calculator import CalculationError, Calculator, expected_patch, expected_state_patch
from ..improved_io.calculations import (ability_effects, check_effects, field_for,
                                        own_spec, public_hp_bounds, tera_spec)
from ..improved_io.lifecycle import ability_histories, for_pokemon
from ..improved_io.protocol import protect_lifetimes, protocol_rows
from ..improved_io.state import STATS, set_forms
from ..observation.normalize import _effect_map, _knowledge
from ..observation.runtime import ObservationError
from .. import jev_effects
from ..jev_battle import INITIAL_PP_POLICY, VERSION as JEV_VERSION, make_input

VERSION = "jev-damage-sample-v1"
RULES = (
    "Offline damage sample. damage_pct gives [minimum, maximum] percent of the defender's "
    "maximum HP, conditional on all accuracy checks succeeding in the current state. Each branch "
    "unions compatible recommended sets, damage rolls, public HP uncertainty and move-specific "
    "hit counts. self/opponent always refer to the controlled/opposing side, including incoming "
    "attacks. current includes already applied Tera; self_tera/opponent_tera/both_tera apply "
    "new Tera only when available. Omitted branches are unavailable. Ranges are rounded outward "
    "to 0.1%, may exceed 100%, and are not probabilities. Null means status move, no compatible "
    "recommended set or unsupported calculation (damage_reason); [0,0] is a computed zero, "
    "including immunity, not missing data. "
    "Opponent knowledge=observed/hypothesized distinguishes public moves from recommended "
    "moves, not confirmed possession. Hypothesized PP is not supplied. These are ranges over "
    "the fixed recommended support, not all legal sets. Ordinary critical-hit chance, misses, "
    "unknown opponent actions, switching and future action-order state changes are excluded. "
    "Move success requirements (for example Sucker Punch) remain conditional. Bench power is "
    "base power. Displayed type/category/accuracy/priority are base Dex metadata; damage uses "
    "the dynamic move rules in each branch. Public HP is rounded; effect counters are not guaranteed remaining durations."
)
# Calc has no supplied history/other-move argument for these variable-power rules.
# Do not present its default base power as a complete envelope.
UNSUPPORTED_MOVES = {
    "counter", "mirrorcoat", "metalburst", "comeuppance", "bide", "lastrespects", "ragefist",
    "beatup", "spitup", "furycutter", "rollout", "iceball", "echoedvoice", "trumpcard",
    "magnitude", "present", "naturalgift", "pursuit", "assurance", "payback", "revenge",
    "avalanche", "lashout", "temperflare", "round", "retaliate",
}
# Fixed Gen9 move metadata (pokemon-showdown/data/moves.ts). Random 2..5 hit
# counts are different from terminating on a failed per-hit accuracy check.
MULTIACCURACY_HITS = {"tripleaxel": 3, "triplekick": 3, "populationbomb": 10}


def calculator_identity():
    directory = Path(__file__).parents[1] / "improved_io/calculator"
    return dict(name="@smogon/calc", version="0.11.0", patch=expected_patch(),
                state_patch=expected_state_patch(), source_sha256={
                    name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                    for name in ("worker.cjs", "scenarios-v2.cjs", "patch.cjs", "state-patch.cjs", "package-lock.json")})


def active_context(official, prefix, own_team, dex, actor, *, public_facts=None):
    """Use the project's observation/state adapters, only for the two active mons."""
    from poke_env.environment.field import Field
    from poke_env.environment.side_condition import SideCondition
    from poke_env.environment.weather import Weather
    from poke_env.teambuilder.teambuilder import Teambuilder

    request = official["request"]
    if request["side"]["id"] != actor or official["gen"] != 9 or official["game_type"] != "singles":
        raise ValueError("foreign actor or unsupported format")
    if official["consumed"] != sum(len(p["protocol"].splitlines()) for p in prefix):
        raise ValueError("observation cutoff mismatch")
    parsed = list(protocol_rows(prefix))
    requests = [json.loads("|".join(p[2:])) for p, _, _ in parsed if p[1] == "request" and p[2]]
    if not requests or requests[-1] != request or any(r.get("side", {}).get("id", actor) != actor for r in requests):
        raise ValueError("foreign or stale request in prefix")
    sides = {s["id"]: s for s in official["sides"]}
    other = "p2" if actor == "p1" else "p1"
    self_raw = [p for p in request["side"]["pokemon"] if p["active"]]
    enemy = [p for p in sides[other]["pokemon"] if p["active"] and not p["fainted"]]
    if len(self_raw) != 1 or len(enemy) != 1:
        raise ValueError("need one living active Pokemon per side")
    self_raw, enemy = self_raw[0], enemy[0]
    owned = [p for p in sides[actor]["pokemon"] if p["ident"] == self_raw["ident"]]
    if len(owned) != 1:
        raise ValueError("ambiguous own active identity")
    owned = owned[0]
    histories, complete = ability_histories(prefix, battle_id="offline", actor_id=actor)
    if not complete:
        raise ValueError("incomplete public battle prefix")
    protect = protect_lifetimes(prefix)
    knowledge = _knowledge(prefix)

    def shared(mon):
        history = for_pokemon(histories, complete, battle_id="offline", actor_id=actor,
                              pokemon_ident=mon["ident"])
        if public_facts is not None:
            mon = copy.deepcopy(mon)
            current = public_facts['pokemon'].get(mon['ident'], {})
            history['suppressed'] = current.get('suppressed') is True
            if mon['ident'].startswith(other + ':'):
                mon['ability'] = '' if history['suppressed'] else current.get('ability', '')
        elif "gastroacid" in mon["volatiles"]:
            history["suppressed"] = True
        supplements = []
        try:
            effects = _effect_map(mon, history, protect, supplements)
        except ObservationError as error:
            if not str(error).startswith("unsupported official effect:"):
                raise
            effects = {"UNSUPPORTED_" + str(error): 0}
        return dict(boosts=copy.deepcopy(mon["boosts"]),
                    effects=effects,
                    ability_history=history, battle_types=mon["battle_types"],
                    details=mon["details"])

    species = token(self_raw["details"].split(",")[0])
    declared = [s for s in Teambuilder.parse_showdown_team(own_team)
                if token(s.species or s.nickname) in set_forms(species)]
    if len(declared) != 1:
        raise ValueError("ambiguous own submitted set")
    declared = declared[0]
    own = dict(copy.deepcopy(self_raw), species=species, **shared(owned))
    own["original_set"] = dict(nature=declared.nature or "Serious", evs=dict(zip(STATS, declared.evs)),
                               ivs=dict(zip(STATS, declared.ivs)), level=declared.level or 100,
                               tera_type=declared.tera_type)
    facts = knowledge.get(enemy["ident"], {})
    if not facts.get("hp"):
        raise ValueError("opponent HP has no public evidence")
    suppression = (shared(enemy)["ability_history"]["suppressed"] or enemy["ability"] == "(suppressed)")
    ability_known = suppression or token(enemy["ability"]) in facts.get("ability", {})
    item_known = bool(enemy["item"] or enemy["prevItem"] or facts.get("item", {}).get("absent"))
    opponent = dict(ident=enemy["ident"], species=token(enemy["species"]), active=True,
                    level=enemy["level"], hp=enemy["hp"], max_hp=enemy["max_hp"],
                    status=enemy["status"], tera_type=enemy["tera_type"],
                    item=(token(enemy["item"]) or None) if item_known else "unknown_item",
                    ability=("" if suppression else enemy["ability"]) if ability_known else None,
                    ability_known=ability_known,
                    moves=list(dict.fromkeys(token(m[0]) for m in enemy["moves"]
                               if not m[0].startswith("*") and token(m[0]) not in ("struggle", "recharge"))),
                    **shared(enemy))
    if public_facts is not None:
        current = public_facts['pokemon'][enemy['ident']]
        hp = current['hp']
        if not isinstance(hp, dict):
            raise ValueError('opponent HP has no v6 public evidence')
        suppressed = current['suppressed'] is True
        opponent.update(hp=hp['current'], max_hp=hp['maximum'], status=current['status'],
                        item='unknown_item' if current['item'] == 'unknown' else current['item'],
                        ability='' if suppressed else (None if current['ability'] == 'unknown' else current['ability']),
                        ability_known=suppressed or current['ability'] != 'unknown', moves=current['moves'][:])

    def enum_id(value, enum):
        names = {token(e.name): e.name for e in enum}
        if token(value) not in names:
            raise CalculationError("unsupported environment: " + str(value))
        return names[token(value)]

    def conditions(side):
        return {enum_id(k, SideCondition): (v[1] if token(k) in ("spikes", "toxicspikes") else 1)
                for k, v in sides[side]["side_conditions"].items()
                if token(k) not in ("futuresight", "doomdesire")}

    try:
        observation = dict(weather={enum_id(official["weather"], Weather): 1} if official["weather"] else {},
                           field={enum_id(f[0], Field): 1 for f in official["field"]},
                           self_side_conditions=conditions(actor), opponent_side_conditions=conditions(other),
                           calculator_semantics="calculator-input-v2")
        field = field_for(observation)
    except CalculationError as error:
        field = {"unsupported_reason": str(error)}
    consumed = {p[2][:2] for p, _, _ in parsed if p[1] == "-terastallize"}
    self_can = bool(request.get("active", [{}])[0].get("canTerastallize")) and actor not in consumed
    other_can = other not in consumed and not enemy["tera_type"]
    return own, opponent, field, self_can, other_can


def opponent_specs(mon, candidate, dex):
    check_effects(mon)
    base = dex["BattlePokedex"][mon["species"]]["baseStats"]["hp"]
    maximum = (math.floor((2 * base + candidate["ivs"]["hp"] + candidate["evs"]["hp"] // 4)
                          * mon["level"] / 100) + mon["level"] + 10) if base != 1 else 1
    low, high = public_hp_bounds(mon["hp"], mon["max_hp"], maximum)
    # Enumerate every feasible HP integer: thresholds and fixed/fractional damage
    # cannot assume that endpoint calculations always suffice.
    for hp in range(low, high + 1):
        options = dict(level=mon["level"], ability=candidate["current_ability"],
                       item=candidate["current_item"], nature=candidate["nature"],
                       evs=candidate["evs"], ivs=candidate["ivs"], boosts=mon["boosts"],
                       curHP=hp, status=mon["status"], **ability_effects(mon))
        options["gender"] = next((p.strip() for p in mon["details"].split(",") if p.strip() in ("M", "F")), "N")
        if mon["tera_type"]:
            options["teraType"] = mon["tera_type"]
        if token(options["ability"]) == "supremeoverlord" and "alliesFainted" not in options:
            options["alliesFainted"] = min(5, mon["ability_history"]["team_faints"])
        yield dict(name=mon["species"], options=options, expectedStats={"hp": maximum},
                   entry_effects_observed=True, battle_types=mon["battle_types"], projected_entry=False,
                   qp_source=mon["ability_history"]["qp_source"])


def percentage_range(entries):
    """Divide each raw candidate by its own defender max HP before union/rounding."""
    if not entries or any("damage_range_hp" not in entry for entry in entries):
        raise ValueError("incomplete calculated range")
    low = min(Fraction(e["damage_range_hp"][0] * 100, e["defender_max_hp"]) for e in entries)
    high = max(Fraction(e["damage_range_hp"][1] * 100, e["defender_max_hp"]) for e in entries)
    return [math.floor(low * 10) / 10, math.ceil(high * 10) / 10]


class Engine:
    """One worker, restarting only after a recorded diagnostic calculation failure."""
    def __init__(self):
        self.calculator = None

    def calculate(self, scenario):
        attacker = scenario["attacker"]["options"]
        if token(attacker["item"]) == "loadeddice" and (
                scenario["field"].get("isMagicRoom") or token(attacker["ability"]) == "klutz"):
            return dict(scenario_id=scenario["scenario_id"],
                        excluded_with_reason="unsupported_inactive_loaded_dice_hit_count")
        try:
            if self.calculator is None:
                self.calculator = Calculator()
            reply = self.calculator.calculate(
                {"input_version": "calculator-input-v2", "state_id": digest(scenario)}, [scenario])
            entry = reply["entries"][0]
            key = token(scenario["move"])
            if key in MULTIACCURACY_HITS and "damage_variants" in entry:
                maximum = MULTIACCURACY_HITS[key]
                counts = (set(range(4, 11)) if key == "populationbomb" and token(attacker["item"]) == "loadeddice"
                          else {maximum})
                variants = [v for v in entry["damage_variants"] if v["hits"] in counts]
                if {v["hits"] for v in variants} != counts:
                    return dict(scenario_id=scenario["scenario_id"],
                                excluded_with_reason="incomplete_conditional_hit_count_support", worker_result=entry)
                entry = dict(entry, worker_damage_range_hp=entry["damage_range_hp"],
                             worker_damage_variants=entry["damage_variants"], damage_variants=variants,
                             hit_conditioning="all accuracy checks succeed; random hit counts retained",
                             damage_range_hp=[min(v["damage_range_hp"][0] for v in variants),
                                              max(v["damage_range_hp"][1] for v in variants)])
            return entry
        except CalculationError as error:
            self.close()
            return dict(scenario_id=scenario["scenario_id"], excluded_with_reason=str(error))

    def close(self):
        if self.calculator:
            self.calculator.close()
            self.calculator = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def move_record(move, dex):
    entry = dex["BattleMovedex"].get(token(move))
    if entry is None:
        raise ValueError("missing pinned move metadata: " + move)
    return {"id": token(move), **{k: entry.get(k, 0) for k in ("type", "category", "accuracy", "priority")}}


def prepare_matchup(payload, official, prefix, own_team, dex, snapshot, *, request_moves=False,
                    observed_only=False, public_facts=None):
    """Normalize the matchup, public move slots and recommended support without calculations."""
    result = copy.deepcopy(payload)
    audit = dict(version=VERSION, source_payload_sha256=digest(payload), prefix_sha256=digest(prefix),
                 official_sha256=digest(official), own_team_sha256=hashlib.sha256(own_team.encode()).hexdigest(),
                 engine=calculator_identity(), calculations=[])
    if payload["state"]["decision_kind"] != "turn_action":
        audit["unchanged_reason"] = "lead_or_forced_switch_out_of_scope"
        return result, audit
    actor = payload["state"]["actor"]
    original, _ = make_input(official, prefix, actor=actor, dex=dex, version=JEV_VERSION,
                             initial_pp_policy=INITIAL_PP_POLICY)
    if public_facts is not None:
        from .public_facts_v6 import apply, history as public_fact_history
        original, _ = apply(original, public_facts, dex)
    if original != payload:
        raise ValueError("payload differs from bounded JEV observation")
    own, opponent, field, self_can, other_can = active_context(official, prefix, own_team, dex, actor,
                                                             public_facts=public_facts)
    history = (public_fact_history(public_facts, opponent['ident']) if public_facts is not None
               else public_history(prefix, opponent["ident"]))
    if public_facts is not None:
        history['unsupported'].extend(public_facts['pokemon'].get(own['ident'], {}).get('unsupported', []))
    sets, source = snapshot.load(opponent["species"])
    supported, excluded = candidates(sets, opponent, history, public_facts=public_facts is not None)
    audit.update(source=source, history=history, candidates=supported, excluded_candidates=excluded,
                 self_can_tera=self_can, opponent_can_tera=other_can,
                 normalized_active={"self": own, "opponent": opponent}, field=field)
    self_target = next(m for m in result["state"]["self_team"] if m["active"])
    other_target = next(m for m in result["state"]["opponent_team"] if m["active"])
    if request_moves:
        # Opt-in successor projection: Struggle/copied/current request moves may
        # differ from the stored owned set. Slots remain authoritative.
        self_target["moves"] = [dict(
            dict(id="recharge", type="not_applicable", category="Status", accuracy="not_applicable", priority="not_applicable")
            if m["id"] == "recharge" else move_record(m["id"], dex), current_pp=m.get("pp", "unknown"))
            for m in self_target.get("current_move_slots", [])]
    # A publicly copied move replaces its original slot; historical knowledge
    # of Mimic/Sketch does not make that original slot currently available.
    replacements = history["replacements"]
    other_target["moves"] = [move_record(replacements[m["id"]], dex) if m["id"] in replacements else m
                              for m in other_target["moves"]]
    for copied in replacements.values():
        if copied not in {m["id"] for m in other_target["moves"]}:
            other_target["moves"].append(move_record(copied, dex))
    observed = {m["id"] for m in other_target["moves"]}
    expected_moves = sorted({m for c in supported for m in c["moves"]} - observed)
    if not observed_only:
        other_target["moves"].extend(move_record(m, dex) for m in expected_moves)
    for move in other_target["moves"]:
        move["knowledge"] = "observed" if move["id"] in observed else "hypothesized"
    return result, audit


def transform(payload, official, prefix, own_team, dex, snapshot, engine, *, request_moves=False, observed_only=False,
              public_facts=None):
    """Return a new payload and audit; never mutate the archived input."""
    result, audit = prepare_matchup(payload, official, prefix, own_team, dex, snapshot,
        request_moves=request_moves, observed_only=observed_only, public_facts=public_facts)
    if 'normalized_active' not in audit:
        return result, audit
    own, opponent = audit['normalized_active']['self'], audit['normalized_active']['opponent']
    field, history, supported = audit['field'], audit['history'], audit['candidates']
    self_can, other_can = audit['self_can_tera'], audit['opponent_can_tera']
    self_target = next(m for m in result['state']['self_team'] if m['active'])
    other_target = next(m for m in result['state']['opponent_team'] if m['active'])
    branches = [("current", False, False)]
    if self_can:
        branches.append(("self_tera", True, False))
    if other_can:
        branches.append(("opponent_tera", False, True))
    if self_can and other_can:
        branches.append(("both_tera", True, True))
    audit["branches"] = [b[0] for b in branches]
    self_error = None
    try:
        self_spec = own_spec(own)
    except CalculationError as error:
        self_error = str(error)
    for direction, moves in (("outgoing", self_target["moves"]), ("incoming", other_target["moves"])):
        for move in moves:
            move.pop("power", None)
            move["damage_pct"] = None
            if move["category"] == "Status":
                move["damage_reason"] = "recharge_action" if move["id"] == "recharge" else "status_move"
                continue
            relevant = [c for c in supported if direction == "outgoing" or move["id"] in c["moves"]]
            if not relevant:
                move["damage_reason"] = "no_compatible_recommended_set"
                continue
            problem = self_error or field.get("unsupported_reason") or (", ".join(history["unsupported"]) if history["unsupported"] else None)
            if move["id"] in UNSUPPORTED_MOVES:
                problem = "move_requires_unrepresented_history_or_action"
            if problem:
                move["damage_reason"] = problem
                continue
            ranges, reasons = {}, {}
            for branch, new_self, new_opponent in branches:
                entries, failures = [], []
                for candidate in relevant:
                    tera_types = candidate["tera_types"] if new_opponent else [None]
                    if not tera_types:
                        failures.append("missing_recommended_tera_type")
                        audit["calculations"].append(dict(direction=direction, move=move["id"], branch=branch,
                            candidate_id=candidate["candidate_id"], error="missing_recommended_tera_type"))
                    try:
                        specs = list(opponent_specs(opponent, candidate, dex))
                    except CalculationError as error:
                        failures.append(str(error))
                        audit["calculations"].append(dict(direction=direction, move=move["id"], branch=branch,
                            candidate_id=candidate["candidate_id"], error=str(error)))
                        continue
                    for opp_spec in specs:
                        for tera in tera_types:
                            a = tera_spec(own, self_spec) if new_self else copy.deepcopy(self_spec)
                            b = tera_spec(dict(opponent, teraType=tera), opp_spec) if new_opponent else copy.deepcopy(opp_spec)
                            current_field = copy.deepcopy(field)
                            if direction == "incoming":
                                a, b = b, a
                                current_field["attackerSide"], current_field["defenderSide"] = current_field["defenderSide"], current_field["attackerSide"]
                            sid = f"{direction}/{move['id']}/{branch}/{candidate['candidate_id']}/hp{opp_spec['options']['curHP']}/{tera or 'current'}"
                            scenario = dict(scenario_id=sid, attacker=a, defender=b, move=move["id"], field=current_field)
                            entry = engine.calculate(scenario)
                            audit["calculations"].append(dict(direction=direction, move=move["id"], branch=branch,
                                candidate_id=candidate["candidate_id"], opponent_new_tera=tera, scenario=scenario, result=entry))
                            if "damage_range_hp" in entry:
                                entries.append(entry)
                            else:
                                failures.append(entry.get("excluded_with_reason", "unsupported_calculation"))
                if failures:
                    ranges[branch] = None
                    reasons[branch] = "; ".join(sorted(set(failures)))
                elif entries:
                    ranges[branch] = percentage_range(entries)
                else:
                    ranges[branch] = None
                    reasons[branch] = "no_calculated_candidates"
            move["damage_pct"] = ranges
            if reasons:
                move["damage_reason"] = reasons
    by_id = {m["id"]: m for m in self_target["moves"]}
    for candidate in result["questions"]["action"]["criteria"].values():
        if "move" in candidate:
            move = candidate["move"]
            move.pop("power", None)
            reference = by_id.get(move["id"])
            if reference is None:
                move.update(damage_pct=None, damage_reason="request_move_not_in_owned_moves")
            else:
                move["damage_pct"] = copy.deepcopy(reference["damage_pct"])
                if "damage_reason" in reference:
                    move["damage_reason"] = copy.deepcopy(reference["damage_reason"])
    result["state"]["version"] = VERSION
    result["state"]["information_rules"] = RULES
    result["questions"]["action"]["instructions"] += "\n\n" + RULES
    # Keep v3's dictionary complete for newly supplied hypothetical move IDs.
    # These are rule descriptions, not extra opponent item/ability hypotheses.
    reference_state = result['state']
    if public_facts is not None:
        reference_state = copy.deepcopy(reference_state)
        for mon in reference_state['opponent_team']:
            if mon.get('ability') == '(suppressed)':
                mon['ability'] = public_facts['pokemon'][mon['ident']]['ability']
    result["state"]["effect_reference"] = jev_effects.build(
        reference_state, result["questions"]["action"]["criteria"])
    audit["result_payload_sha256"] = digest(result)
    return result, audit
