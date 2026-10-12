"""Decision-time public observation and separately labelled marginal set priors."""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from pathlib import Path

from ..benchmark_player import build_candidates, normalize_name
from .protocol import (
    court_change_notifications,
    live_effects,
    observed_state,
    protect_lifetimes,
    protocol_rows,
)

STATS = ("hp", "atk", "def", "spa", "spd", "spe")


def stable_id(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def enum_name(value):
    return value.name if hasattr(value, "name") else value


def public_mon(p, revealed=None, timing=None, protect=None, court_change=None):
    revealed = revealed or {}
    return dict(
        ident=revealed.get("ident"),
        species=p.species,
        active=p.active,
        fainted=p.fainted,
        level=p.level,
        hp=p.current_hp,
        max_hp=p.max_hp,
        hp_precision="rounded_server_fraction",
        types=[enum_name(t) for t in p.types],
        status=enum_name(p.status),
        item=revealed.get("item", p.item),
        ability=revealed.get("ability", p.ability),
        ability_known=(
            revealed["ability"] is not None
            if "ability" in revealed
            else p.ability is not None
        ),
        boosts=dict(p.boosts),
        tera_type=enum_name(p._terastallized_type) if p.terastallized else None,
        moves=list(dict.fromkeys([*p.moves, *revealed.get("moves", [])])),
        parser_effects={enum_name(k): v for k, v in p.effects.items()},
        effects=live_effects(p, revealed.get("ident"), timing or {}, protect, court_change),
    )


def hypotheses(mon, prior):
    species = mon["species"]
    source_species = prior_species(species, prior)
    if source_species not in prior["data"]:
        raise ValueError("missing species in sealed Gen 9 prior")
    data = prior["data"][source_species]
    spreads = sorted(data["spreads"], key=lambda x: -x["percentage"])[:2]
    items = (
        [{"name": mon["item"] or ""}]
        if mon["item"] != "unknown_item"
        else sorted(data["items"], key=lambda x: -x["percentage"])[:2]
    )
    abilities = (
        [{"name": mon["ability"] or ""}]
        if mon.get("ability_known", bool(mon["ability"]))
        else data["abilities"]
    )
    moves = list(mon["moves"])
    for move in data["moves"]:
        name = normalize_name(move["name"])
        if name not in moves and len(moves) < 4:
            moves.append(name)
    if not spreads or not items or not abilities:
        raise ValueError("incomplete prior support")
    return [
        dict(
            spread=spread,
            item=item["name"].strip(),
            ability=ability["name"].strip(),
            moves=moves,
            confirmed_moves=mon["moves"],
            source="fixed_gen9_ou_prior",
            ivs=dict.fromkeys(STATS, 31),
            joint_probability=None,
            coverage=(
                "representative marginal combinations; other sets/moves not covered"
            ),
            **({"prior_species": source_species} if source_species != species else {}),
        )
        for spread, item, ability in itertools.product(spreads, items, abilities)
    ]


def set_forms(species):
    """Only explicit pinned battle-only form ancestry can retain a declared set."""
    from poke_env.data import GenData

    data = GenData.from_gen(9).pokedex
    result = {species}
    pending = [species]
    while pending:
        current = pending.pop()
        parents = data.get(current, {}).get("battleOnly", [])
        if isinstance(parents, str):
            parents = [parents]
        for name in parents:
            parent = normalize_name(name)
            if parent not in result:
                result.add(parent)
                pending.append(parent)
    return result


def prior_species(species, prior):
    if species in prior["data"]:
        return species
    available = set_forms(species) & prior["data"].keys()
    if len(available) != 1:
        raise ValueError("missing or ambiguous battle-form prior")
    return available.pop()


def public_revelations(protocol):
    """Recover public facts omitted by the pinned parser's SPECIAL_MOVES filter.

    Called/copied moves are not evidence of a set slot. Healing attributed to
    another Pokemon is not evidence of the healed Pokemon's ability.
    """
    from ..battle_adapter import identity

    facts, occupants, natural = {}, {}, {}
    changed_form = set()
    for parts, _, _ in protocol_rows(protocol, require_refs=False):
        if len(parts) >= 5 and parts[1] == "-status":
            source = next(
                (p for p in parts[4:] if p.startswith("[from] ability: ")), None
            )
            holder = next((p[5:] for p in parts[4:] if p.startswith("[of] p")), None)
            if source and holder and re.fullmatch(r"p[12][a-z]?: .+", holder):
                # Contact status names the afflicted Pokemon first; only the
                # explicit [of] holder reveals Static/Poison Point/etc.
                _, holder_key = identity(holder)
                fact = facts.setdefault(holder_key, {"moves": []})
                ability = normalize_name(source.split(":", 1)[1])
                natural.setdefault(holder_key, ability)
                fact["ability"] = ability
        if len(parts) >= 5 and parts[1] == "-weather":
            source = next(
                (p for p in parts[3:] if p.startswith("[from] ability: ")), None
            )
            holder = next((p[5:] for p in parts[3:] if p.startswith("[of] p")), None)
            if source and holder and ": " in holder and holder.startswith(("p1", "p2")):
                # Weather names the field in parts[2]; [of] names the revealed holder.
                _, key = identity(holder)
                fact = facts.setdefault(key, {"moves": []})
                ability = normalize_name(source.split(":", 1)[1])
                if "ability" not in fact:
                    natural.setdefault(key, ability)
                fact["ability"] = ability
            continue
        if (
            len(parts) < 3
            or not parts[2].startswith(("p1", "p2"))
            or ": " not in parts[2]
        ):
            continue
        if parts[1] not in (
            "move",
            "-heal",
            "-ability",
            "-endability",
            "-activate",
            "-status",
            "-item",
            "-enditem",
            "switch",
            "drag",
            "detailschange",
        ):
            continue
        _, key = identity(parts[2])
        fact = facts.setdefault(key, {"moves": []})
        kind = parts[1]
        if kind == "detailschange":
            changed_form.add(key)
        elif kind in ("switch", "drag"):
            slot = parts[2].split(":", 1)[0]
            old = occupants.get(slot)
            if old and "ability" in facts[old]:
                facts[old]["ability"] = natural.get(old)
            occupants[slot] = key
            if "ability" in fact:
                fact["ability"] = natural.get(key)
        elif kind == "-item":
            fact["item"] = normalize_name(parts[3])
        elif kind == "-enditem":
            fact["item"] = None
        elif (
            kind == "-status"
            and len(parts) == 5
            and (parts[3], parts[4])
            in (
                ("tox", "[from] item: Toxic Orb"),
                ("brn", "[from] item: Flame Orb"),
            )
        ):
            # The pinned status parser drops self-activating item provenance.
            # An [of] source or an externally inflicted status is not the target's item.
            fact["item"] = normalize_name(parts[4].split(":", 1)[1])
        elif kind == "move" and not any(p.startswith("[from]") for p in parts[4:]):
            move = normalize_name(parts[3])
            if move not in ("struggle", "recharge") and move not in fact["moves"]:
                fact["moves"].append(move)
        elif kind == "-endability":
            fact["ability"] = (
                ""  # Public suppression is known absence, not an unknown prior.
            )
        elif kind == "-ability":
            fact["ability"] = normalize_name(parts[3])
            if not any(p.startswith("[from]") for p in parts[4:]):
                if key in changed_form:
                    natural[key] = fact["ability"]
                    changed_form.discard(key)
                else:
                    natural.setdefault(key, fact["ability"])
        elif kind == "-activate" and parts[3] in (
            "ability: Supreme Overlord",
            "ability: Quark Drive",
            "ability: Protosynthesis",
        ):
            # These pinned signals name the holder in parts[2]. Do not generalize
            # to ability-changing activations (e.g. Wandering Spirit).
            ability = normalize_name(parts[3].split(":", 1)[1])
            if "ability" not in fact:
                natural.setdefault(key, ability)
            fact["ability"] = ability
        elif (
            kind == "-heal"
            and len(parts) == 5
            and parts[4].startswith("[from] ability:")
        ):
            fact["ability"] = normalize_name(parts[4].split(":", 1)[1])
            natural.setdefault(key, fact["ability"])

    return facts


def normalize(
    battle,
    request,
    own_team,
    protocol,
    *,
    battle_id,
    actor_id,
    decision_seq,
    observed_protocol=None,
    semantics_version="calculator-input-v2",
):
    """No opponent team/manifest argument is accepted at this boundary."""
    from poke_env.teambuilder.teambuilder import Teambuilder

    if request.get("wait") or request.get("teamPreview") or battle.finished:
        raise ValueError("non-action request")
    if request["side"]["id"] != actor_id:
        raise ValueError("foreign actor request")
    full_protocol = protocol if observed_protocol is None else observed_protocol
    timing = observed_state(full_protocol)
    protect = protect_lifetimes(full_protocol)
    court_change = court_change_notifications(full_protocol)
    from .lifecycle import VERSION, ability_histories, for_pokemon

    if semantics_version not in (None, VERSION):
        raise ValueError("unknown calculator input semantics")
    if semantics_version:
        rows = list(protocol_rows(full_protocol))
        source_requests = [
            json.loads("|".join(parts[2:]))
            for parts, _, _ in rows
            if parts[1] == "request" and len(parts) > 2 and parts[2]
        ]
        if source_requests and source_requests[-1] != request:
            raise ValueError("request is not the latest public-prefix self request")
        turns = [turn for _, turn, _ in rows if turn is not None]
        if turns and turns[-1] != battle.turn:
            raise ValueError("public prefix and battle decision turn differ")
        sources = {e["event_seq"]: e["protocol"] for e in full_protocol}
        if any(sources.get(e["event_seq"]) != e["protocol"] for e in protocol):
            raise ValueError("recent events differ from observed public prefix")
    histories, history_complete = ability_histories(
        full_protocol, battle_id=battle_id, actor_id=actor_id
    )
    # Showdown exports Markdown hard-break spaces; the pinned parser does not
    # strip the species header and otherwise mistakes a nickname for species.
    sets = Teambuilder.parse_showdown_team(
        "\n".join(line.rstrip() for line in own_team.splitlines())
    )
    own = []
    for raw in request["side"]["pokemon"]:
        species = normalize_name(raw["details"].split(",")[0])
        forms = set_forms(species) if semantics_version else {species}
        matches = [s for s in sets if normalize_name(s.species or s.nickname) in forms]
        if len(matches) != 1:
            raise ValueError("ambiguous self set identity")
        original = matches[0]
        if {normalize_name(m) for m in original.moves} != set(raw["moves"]):
            raise ValueError(
                "self moves differ from original set; unsupported transformation"
            )
        p = battle.team.get(raw["ident"])
        if p is None:
            raise ValueError("self request not reconciled with actor state")
        own.append(
            {
                **raw,
                "species": species,
                "boosts": dict(p.boosts),
                "parser_effects": {enum_name(k): v for k, v in p.effects.items()},
                "effects": live_effects(p, raw["ident"], timing, protect, court_change),
                "original_set": dict(
                    nature=original.nature or "Serious",
                    evs=dict(zip(STATS, original.evs)),
                    ivs=dict(zip(STATS, original.ivs)),
                    level=original.level or 100,
                    tera_type=original.tera_type,
                ),
                "hp_precision": "exact_self_request",
            }
        )
        if semantics_version:
            own[-1]["original_set"]["species"] = normalize_name(
                original.species or original.nickname
            )
            own[-1]["ability_history"] = for_pokemon(
                histories,
                history_complete,
                battle_id=battle_id,
                actor_id=actor_id,
                pokemon_ident=raw["ident"],
            )
            own[-1]["battle_types"] = [
                enum_name(t) for t in (p._type_1, p._type_2) if t
            ]
            own[-1]["effective_types"] = (
                [raw["terastallized"].upper()]
                if raw.get("terastallized") and raw["terastallized"] != "Stellar"
                else own[-1]["battle_types"]
            )
    candidates = build_candidates(battle)
    legal = [entry.record()["action"] for entry in candidates.entries]
    if not legal:
        raise ValueError("empty legal actions")
    force = bool(request.get("forceSwitch", [False])[0])
    cause = "not_forced"
    if force:
        active = battle.active_pokemon
        cause = "faint" if active is None or active.fainted else "UNKNOWN"
        for parts, _, _ in reversed(list(protocol_rows(protocol))):
            if cause != "UNKNOWN" or parts[1] == "turn":
                break
            if len(parts) < 4 or not parts[2].startswith(actor_id):
                continue
            if parts[1] == "-enditem" and parts[3] in ("Eject Button", "Eject Pack"):
                cause = "item"
            elif parts[1] == "move" and parts[3] in (
                "U-turn",
                "Volt Switch",
                "Flip Turn",
                "Parting Shot",
                "Baton Pass",
                "Chilly Reception",
            ):
                cause = "pivot"
    revealed = public_revelations(
        protocol if observed_protocol is None else observed_protocol
    )
    opponent = [
        public_mon(p, {"ident": key, **revealed.get(key, {})}, timing, protect, court_change)
        for key, p in battle.opponent_team.items()
    ]
    if semantics_version:
        for mon, p in zip(opponent, battle.opponent_team.values(), strict=True):
            mon["ability_history"] = for_pokemon(
                histories,
                history_complete,
                battle_id=battle_id,
                actor_id=actor_id,
                pokemon_ident=mon["ident"],
            )
            mon["battle_types"] = [enum_name(t) for t in (p._type_1, p._type_2) if t]
            mon["effective_types"] = (
                [mon["tera_type"]]
                if mon["tera_type"] and mon["tera_type"] != "STELLAR" and not mon["fainted"]
                else mon["battle_types"]
            )
    current = dict(
        protocol_state=timing,
        self_team=own,
        opponent_confirmed=opponent,
        weather={enum_name(k): v for k, v in battle.weather.items()},
        field={enum_name(k): v for k, v in battle.fields.items()},
        self_side_conditions={
            enum_name(k): v for k, v in battle.side_conditions.items()
        },
        opponent_side_conditions={
            enum_name(k): v for k, v in battle.opponent_side_conditions.items()
        },
        order_assessment={
            "relation": "unknown",
            "conditions": [
                "Order depends on priority, speed modifiers, ties and unobserved sets; "
                "raw speed alone does not establish execution order."
            ],
        },
    )
    if semantics_version:
        current["calculator_semantics"] = semantics_version
    active = next((p for p in opponent if p["active"]), None)
    prior = json.loads(Path(__file__).with_name("prior.json").read_text())
    guesses = hypotheses(active, prior) if active and not active["fainted"] else []
    value = dict(
        request={
            "kind": "forced_switch" if force else "turn_action",
            "force_switch_cause": cause,
            "pending_opponent_action": "UNKNOWN",
            "can_tera": bool(battle.can_tera),
            "legal_actions": legal,
        },
        current_observation=current,
        opponent_hypotheses=guesses,
        recent_events=protocol,
        lesson_memory=[],
        battle_summary=None,
        unknowns=[
            "Opponent HP is rounded; prior combinations are not exhaustive.",
            "KO and survival probabilities are not supplied.",
        ],
    )
    value["identity"] = dict(
        battle_id=battle_id,
        actor_id=actor_id,
        decision_seq=decision_seq,
        request_id=request.get("rqid"),
        showdown_turn=battle.turn,
        state_id=stable_id(value),
    )
    if semantics_version:
        value["identity"]["input_version"] = semantics_version
    return value, candidates
