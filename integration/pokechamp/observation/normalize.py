"""Normalize official state + same-prefix history; never accepts a poke-env Battle."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from ..benchmark_player import ActionCandidate, ActionCandidates, normalize_name as token
from ..improved_io.lifecycle import VERSION, ability_histories, for_pokemon
from ..improved_io.protocol import ident, observed_state, protect_lifetimes, protocol_rows
from ..improved_io.state import STATS, hypotheses, set_forms, stable_id
from . import OFFICIAL
from .runtime import ObservationError, rows


class SlotCandidates(ActionCandidates):
    """Resolve a model name once, then submit the exact official request slot."""

    def __init__(self, candidates):
        super().__init__([ActionCandidate(next(iter(c["action"])),
                                         token(next(iter(c["action"].values()))),
                                         c["wire"], "official_self_request_slot")
                          for c in candidates if "team" not in c["action"]])
        keys = [(c.kind, c.name) for c in self.entries]
        if len(set(keys)) != len(keys):
            raise ObservationError("ambiguous request action names")

    def order(self, value, create_order=None):
        from poke_env.player.battle_order import BattleOrder

        entry = self.resolve(value)

        class SlotOrder(BattleOrder):
            @property
            def message(self):
                return "/choose " + self.order

        return SlotOrder(entry.target)


def _names(enum):
    return {token(member.name): member.name for member in enum}


def _effect_map(mon, history, protect, supplements):
    from poke_env.environment.effect import Effect

    names = _names(Effect)
    effects = {}
    if mon["fainted"]:
        return effects
    for family in ("volatiles", "turnstatuses", "movestatuses"):
        for name, value in mon[family].items():
            # These official display flags are represented elsewhere, with all
            # values preserved in official_effects. No calculator state is lost.
            if name in ("formechange", "typechange", "typeadd", "airballoon", "itemremoved"):
                continue
            if name in ("futuresight", "doomdesire"):
                continue  # Caster/target-slot history, not a live target modifier.
            if name == "gastroacid":
                if not history["suppressed"]:
                    raise ObservationError("unrepresented ability suppression")
                continue
            if name not in names:
                raise ObservationError("unsupported official effect: " + name)
            effects[names[name]] = 0  # Explicit presence marker, not a duration.
    life = protect["current"].get(mon["ident"], {})
    if life.get("status") == "expired":
        effects.pop("PROTECT", None)
        supplements.append(dict(field=mon["ident"] + ".effects.PROTECT", rule="public_protect_expiry",
                                evidence=[life["start_ref"], life["end_ref"]]))
    elif life.get("status") in ("active", "unknown"):
        effects.setdefault("PROTECT", 0)
    # Official UI records the revealed ability but not Supreme Overlord's count.
    if token(mon["ability"]) == "supremeoverlord" and mon["active"]:
        count = history["team_faints"]
        if count is None:
            raise ObservationError("unknown Supreme Overlord faint history")
        if count:
            effects.update(SUPREME_OVERLORD=0)
            effects["FALLEN" + str(min(5, count))] = 0
            supplements.append(dict(field=mon["ident"] + ".effects", rule="public_supreme_overlord_and_same_prefix_team_faints", evidence=history["entries"]))
    return effects


def _knowledge(prefix):
    """Evidence of disclosure, distinct from the official UI's inferred defaults."""
    evidence = {}
    for parts, _, ref in protocol_rows(prefix):
        kind = parts[1]
        target = ident(parts[2]) if len(parts) > 2 and re.fullmatch(r"p[12][a-z]?: .+", parts[2]) else None
        holder = next((ident(p[5:]) for p in parts if p.startswith("[of] p")), target)
        for field in ("ability", "item"):
            named = []
            if target and kind == "-" + field and len(parts) > 3:
                named.append((target, token(parts[3])))
            if holder:
                named.extend((holder, token(p.split(":", 1)[1])) for p in parts
                             if p.startswith("[from] " + field + ": "))
            if target and kind in ("-activate", "-start", "-end", "-immune") and len(parts) > 3 and parts[3].startswith(field + ": "):
                named.append((target, token(parts[3].split(":", 1)[1])))
            for key, name in named:
                evidence.setdefault(key, {}).setdefault(field, {}).setdefault(name, []).append(ref)
        if target and kind == "-enditem":
            evidence.setdefault(target, {}).setdefault("item", {}).setdefault("absent", []).append(ref)
        if target and kind in ("switch", "drag", "replace", "-damage", "-heal", "-sethp", "faint"):
            evidence.setdefault(target, {}).setdefault("hp", []).append(ref)
    return evidence


def normalize(official, own_team, recent, prefix, *, battle_id, actor_id, decision_seq,
              build_identity, boundary=None):
    """A single observation feeds both prior/scenarios and the final B/B2 prompt."""
    from poke_env.environment.field import Field
    from poke_env.environment.side_condition import SideCondition
    from poke_env.environment.weather import Weather
    from poke_env.teambuilder.teambuilder import Teambuilder

    if official.get("gen") != 9 or official.get("game_type") != "singles":
        raise ObservationError("official observation requires Gen9 singles")
    request = official["request"]
    if not request or request.get("wait") or request.get("teamPreview"):
        raise ObservationError("non-action official request")
    if request.get("side", {}).get("id") != actor_id:
        raise ObservationError("foreign actor request")
    raw_rows = rows(prefix)
    if official["consumed"] != len(raw_rows):
        raise ObservationError("official prefix length mismatch")
    endpoint = dict(protocol_event_seq=raw_rows[-1][0], line_index=raw_rows[-1][1],
                    turn=official["turn"], request_id=request.get("rqid"), decision_seq=decision_seq)
    if boundary is not None and any(boundary.get(k) != v for k, v in endpoint.items()):
        raise ObservationError("official decision boundary mismatch")
    parsed = list(protocol_rows(prefix))
    requests = [json.loads("|".join(p[2:])) for p, _, _ in parsed if p[1] == "request" and len(p) > 2 and p[2]]
    if not requests or requests[-1] != request:
        raise ObservationError("official request differs from bounded raw request")
    if any(r and r.get("side", {}).get("id", actor_id) != actor_id for r in requests):
        raise ObservationError("foreign request in prefix")
    turns = [t for _, t, _ in parsed if t is not None]
    if not turns or turns[-1] != official["turn"]:
        raise ObservationError("official turn differs from prefix")
    sources = {e["event_seq"]: e["protocol"] for e in prefix}
    for index, event in enumerate(recent):
        original = sources.get(event["event_seq"])
        offset = event.get("line_offset", 0)
        if (original is None or type(offset) is not int or offset < 0 or index and offset):
            raise ObservationError("invalid recent event source offset")
        expected = "\n".join(original.splitlines()[offset:]) if offset else original
        if event["protocol"] != expected:
            raise ObservationError("recent events differ from bounded prefix")
    if any(p[1] == "-transform" for p, _, _ in parsed):
        raise ObservationError("unsupported transformation in official observation")
    timing = observed_state(prefix)
    protect = protect_lifetimes(prefix)
    histories, complete = ability_histories(prefix, battle_id=battle_id, actor_id=actor_id)
    knowledge = _knowledge(prefix)
    supplements = [dict(field="protocol_state", rule="same_received_protocol_lifetimes",
                        evidence=[ref for p, _, ref in parsed if p[1] in (
                            "-weather", "-fieldstart", "-fieldend", "-sidestart", "-sideend",
                            "-swapsideconditions", "-start", "-end")]),
                   dict(field="ability_history", rule="same_received_protocol_activation_consumption",
                        evidence=[ref for p, _, ref in parsed if p[1] in (
                            "start", "switch", "drag", "faint", "-ability", "-endability", "-activate")])]
    sides = {s["id"]: s for s in official["sides"]}
    if set(sides) != {"p1", "p2"}:
        raise ObservationError("official side identity mismatch")
    opponent_id = "p2" if actor_id == "p1" else "p1"

    def history_for(key):
        return for_pokemon(histories, complete, battle_id=battle_id, actor_id=actor_id, pokemon_ident=key)

    def shared(mon, key):
        history = history_for(key)
        mon = {**mon, "ident": key}
        if "gastroacid" in mon["volatiles"]:
            history["suppressed"] = True
            supplements.append(dict(field=key + ".ability_history.suppressed", rule="official_gastro_acid_volatile",
                                    evidence=[ref for p, _, ref in parsed if len(p) > 3 and ident(p[2]) == key
                                              and p[1] == "-start" and token(p[3]) == "gastroacid"]))
        return dict(boosts=dict(mon["boosts"]) if not mon["fainted"] else {},
                    effects=_effect_map(mon, history, protect, supplements),
                    official_effects={k: copy.deepcopy(mon[k]) for k in (
                        "volatiles", "turnstatuses", "movestatuses", "status_data")},
                    ability_history=history, battle_types=[t.upper() for t in mon["battle_types"]],
                    effective_types=[t.upper() for t in mon["types"]])

    sets = Teambuilder.parse_showdown_team("\n".join(line.rstrip() for line in own_team.splitlines()))
    own = []
    for raw in request["side"]["pokemon"]:
        species = token(raw["details"].split(",")[0])
        matches = [s for s in sets if token(s.species or s.nickname) in set_forms(species)]
        if len(matches) != 1:
            raise ObservationError("ambiguous self set identity")
        original = matches[0]
        if {token(m) for m in original.moves} != set(raw["moves"]):
            raise ObservationError("self moves differ from submitted set; unsupported transformation")
        matches = [p for p in sides[actor_id]["pokemon"] if p["ident"] == raw["ident"]]
        if not matches:
            matches = [p for p in sides[actor_id]["pokemon"] if not p["ident"] and token(p["species"]) == species]
        if len(matches) != 1:
            raise ObservationError("self request cannot be reconciled with official identity")
        mon = matches[0]
        own.append({**copy.deepcopy(raw), "species": species, **shared(mon, raw["ident"]),
                    "original_set": dict(nature=original.nature or "Serious", evs=dict(zip(STATS, original.evs)),
                                         ivs=dict(zip(STATS, original.ivs)), level=original.level or 100,
                                         tera_type=original.tera_type, species=token(original.species or original.nickname)),
                    "hp_precision": "exact_self_request"})
    opponent = []
    for mon in sides[opponent_id]["pokemon"]:
        if not mon["ident"]:
            continue  # Preview placeholders are retained separately, never public HP facts.
        key = ident(mon["ident"])
        facts = knowledge.get(key, {})
        ability = token(mon["ability"])
        suppressed = (mon["ability"] == "(suppressed)" or history_for(key)["suppressed"]
                      or "gastroacid" in mon["volatiles"])
        known_ability = suppressed or bool(ability and facts.get("ability", {}).get(ability))
        item = token(mon["item"])
        known_item = bool(item or mon["prevItem"] or facts.get("item", {}).get("absent"))
        if not facts.get("hp"):
            raise ObservationError("unconfirmed official HP placeholder")
        opponent.append(dict(
            ident=key, species=token(mon["species"]), active=bool(mon["active"] and not mon["fainted"]),
            fainted=mon["fainted"], level=mon["level"], hp=mon["hp"], max_hp=mon["max_hp"],
            hp_precision="rounded_server_fraction", types=[t.upper() for t in mon["types"]],
            status=mon["status"].upper() or None,
            item=(item or None) if known_item else "unknown_item",
            ability=("" if suppressed else ability) if known_ability else None, ability_known=known_ability,
            tera_type=mon["tera_type"].upper() or None,
            moves=list(dict.fromkeys(token(m[0]) for m in mon["moves"] if not m[0].startswith("*") and token(m[0]) not in ("struggle", "recharge"))),
            knowledge=dict(ability_source="confirmed_protocol" if known_ability else "unknown",
                           item_source="confirmed_protocol" if known_item else "unknown", types="public_species_dex_and_type_events",
                           evidence=facts),
            **shared(mon, key),
        ))
    candidates = SlotCandidates(official["candidates"])
    legal = [entry.record()["action"] for entry in candidates.entries]
    if not legal:
        raise ObservationError("empty official legal actions")

    def environment(active, evidence, enum, *, weather=False):
        names = _names(enum)
        result = {}
        for name in active:
            normalized = token(name)
            if normalized not in names:
                raise ObservationError("unsupported official environment: " + name)
            matching = [v for k, v in evidence.items() if token(k) == normalized]
            if len(matching) != 1:
                raise ObservationError("official effect has no same-prefix timing: " + name)
            result[names[normalized]] = matching[0]["last_update_turn" if weather else "observed_start_turn"]
        return result

    weather = environment([official["weather"]] if official["weather"] else [], timing["weather"], Weather, weather=True)
    field = environment([p[0] for p in official["field"]], timing["field"], Field)

    def side_conditions(side):
        active = sides[side]["side_conditions"]
        values = {k: v for k, v in active.items() if token(k) not in ("futuresight", "doomdesire")}
        result = environment(values, timing["sides"].get(side, {}), SideCondition)
        for k, v in values.items():
            if token(k) in ("spikes", "toxicspikes"):
                name = _names(SideCondition)[token(k)]
                result[name] = v[1]
                expected = next(e["layers"] for n, e in timing["sides"][side].items() if token(n) == token(k))
                if v[1] != expected:
                    raise ObservationError("official hazard layer mismatch")
        return result

    force = bool(request.get("forceSwitch", [False])[0])
    cause = "not_forced"
    if force:
        current = next((p for p in own if p["active"]), None)
        cause = "faint" if current is None or "fnt" in current["condition"] else "UNKNOWN"
        for p, _, _ in reversed(list(protocol_rows(recent))):
            if cause != "UNKNOWN" or p[1] == "turn":
                break
            if len(p) < 4 or not p[2].startswith(actor_id):
                continue
            if p[1] == "-enditem" and p[3] in ("Eject Button", "Eject Pack"):
                cause = "item"
            elif p[1] == "move" and p[3] in ("U-turn", "Volt Switch", "Flip Turn", "Parting Shot", "Baton Pass", "Chilly Reception"):
                cause = "pivot"
    active = next((p for p in opponent if p["active"]), None)
    prior = json.loads((Path(__file__).parents[1] / "improved_io/prior.json").read_text())
    current = dict(
        protocol_state=timing, self_team=own, opponent_confirmed=opponent,
        weather=weather, field=field, self_side_conditions=side_conditions(actor_id),
        opponent_side_conditions=side_conditions(opponent_id), calculator_semantics=VERSION,
        order_assessment=dict(relation="unknown", conditions=["Order depends on priority, speed modifiers, ties and unobserved sets; raw speed alone does not establish execution order."]),
        observation_source=dict(version=OFFICIAL, build_identity=build_identity, boundary=endpoint,
                                prefix_sha256=stable_id(prefix), official_state_sha256=stable_id(official),
                                supplements=supplements),
        official_environment=dict(weather_duration=official["weather_duration"], field=official["field"],
                                  sides={k: s["side_conditions"] for k, s in sides.items()},
                                  active_slots={k: s["active"] for k, s in sides.items()}),
    )
    value = dict(request=dict(kind="forced_switch" if force else "turn_action", force_switch_cause=cause,
                              pending_opponent_action="UNKNOWN", can_tera=any(c.kind == "terastallize" for c in candidates.entries),
                              legal_actions=legal), current_observation=current,
                 opponent_hypotheses=hypotheses(active, prior) if active else [], recent_events=copy.deepcopy(recent),
                 lesson_memory=[], battle_summary=None,
                 unknowns=["Opponent HP is rounded; prior combinations are not exhaustive.",
                           "KO and survival probabilities are not supplied.",
                           "Official client initial display values are not observations. Unrevealed abilities/items remain unknown; species/Dex deductions and priors are separate."])
    value["identity"] = dict(battle_id=battle_id, actor_id=actor_id, decision_seq=decision_seq,
                            request_id=request.get("rqid"), showdown_turn=official["turn"],
                            state_id=stable_id(value), input_version=VERSION, observation_version=OFFICIAL)
    return value, candidates
