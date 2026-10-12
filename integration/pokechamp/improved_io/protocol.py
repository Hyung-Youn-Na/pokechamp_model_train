"""Parent-owned public protocol semantics; never reads evaluation facts or private teams."""

from __future__ import annotations

import json
import re

# Pinned Showdown data/moves.ts courtchange.onHitField, singles branch.
# Match IDs rather than display spelling; other side effects stay on their side.
COURT_CHANGE_CONDITIONS = frozenset({
    "mist", "lightscreen", "reflect", "spikes", "safeguard", "tailwind",
    "toxicspikes", "stealthrock", "waterpledge", "firepledge", "grasspledge",
    "stickyweb", "auroraveil", "luckychant", "gmaxsteelsurge", "gmaxcannonade",
    "gmaxvinelash", "gmaxwildfire", "gmaxvolcalith",
})


def court_change_notifications(events):
    """Internal evidence for a move execution notice, not a Pokemon volatile.

    A move attempt alone is insufficient. Identity replacements invalidate the
    evidence instead of transferring it to an unproven holder.
    """
    notices, occupants = {}, {}
    for parts, _, ref in protocol_rows(events):
        if len(parts) < 3 or not re.fullmatch(r"p[12][a-z]?: .+", parts[2]):
            continue
        key, slot = ident(parts[2]), parts[2].split(":", 1)[0]
        kind = parts[1]
        if kind in ("switch", "drag", "replace"):
            notices.pop(occupants.get(slot), None)
            notices.pop(key, None)
            occupants[slot] = key
        elif (kind == "-activate" and len(parts) > 3
              and parts[3] == "move: Court Change"):
            if occupants.get(slot, key) == key:
                notices[key] = ref
                occupants[slot] = key
    return notices


def ident(value):
    return re.sub(r"^(p[12])[a-z]:", r"\1:", value)


def hp(value, actor, target, previous=None):
    token = value.split()[0]
    if "/" in token:
        current, maximum = map(int, token.split("/"))
    elif token == "0":
        current, maximum = 0, (previous or {}).get("maximum")
    else:
        raise ValueError("unsupported observed HP format")
    return {
        "current": current,
        "maximum": maximum,
        "precision": "exact_self" if target.startswith(actor + ":") else "rounded_public",
        "raw": value,
    }


def annotate(context):
    """Protocol-order turn/identity/HP tracking; packet showdown_turn is never consumed."""
    actor = context["identity"]["actor_id"]
    health, health_refs, species = {}, {}, {}
    last_move = None
    delayed_resolution = None
    last_damage = {}
    records = []
    for fields, turn, ref in protocol_rows(context["source_events"]):
        if not fields[1]:
            continue
        kind = fields[1]
        if kind == "turn":
            last_move = None
            delayed_resolution = None
        if kind == "request":
            # Request snapshots are used for self HP only at their original position.
            if fields[2]:
                request = json.loads("|".join(fields[2:]))
                if request.get("side", {}).get("id", actor) != actor:
                    raise ValueError("foreign request in annotation")
                for mon in request.get("side", {}).get("pokemon", []):
                    target = ident(mon["ident"])
                    health[target] = hp(mon["condition"], actor, target, health.get(target))
                    health_refs[target] = ref
                    species[target] = mon["details"]
            continue
        if kind not in {
            "turn",
            "move",
            "switch",
            "drag",
            "replace",
            "faint",
        } and not kind.startswith("-"):
            continue
        row = {"ref": ref, "turn": turn, "kind": kind}
        if len(fields) > 2 and re.match(r"p[12][a-z]?: ", fields[2]):
            target = ident(fields[2])
            row.update(target=target, observed_details=species.get(target))
        else:
            target = None
        if kind in ("switch", "drag", "replace"):
            species[target] = fields[3]
            health[target] = hp(fields[4], actor, target, health.get(target))
            health_refs[target] = ref
            row.update(observed_details=fields[3], hp_after=health[target])
            last_move = None
            delayed_resolution = None
            last_damage.pop(target, None)
        elif kind == "-end" and fields[3] in ("move: Future Sight", "move: Doom Desire"):
            delayed_resolution = {"ref": ref, "effect": fields[3], "target": target}
            last_move = None
        elif kind == "move":
            delayed_resolution = None
            last_move = {
                "ref": ref,
                "turn": turn,
                "user": target,
                "move": fields[3],
                "target": ident(fields[4]) if len(fields) > 4 else None,
            }
            row["observed_move"] = last_move
        elif kind in ("-damage", "-heal", "-sethp"):
            if kind == "-sethp" and len(fields) > 4 and fields[4].startswith(("p1", "p2")):
                raise ValueError("multi-target sethp requires separate annotations")
            before = health.get(target)
            after = hp(fields[3], actor, target, before)
            row.update(hp_before=before, hp_before_ref=health_refs.get(target), hp_after=after)
            same_scale = before and before["maximum"] == after["maximum"]
            row["observed_hp_decrease"] = (
                before["current"] - after["current"] if same_scale else None
            )
            # Uncapped attack damage is unavailable on a KO and public percentages
            # are rounded. Never label the observed decrement as damage-roll truth.
            row["hp_decrease_semantics"] = "observed HP change at supplied precision"
            if kind == "-damage":
                from_tags = [f for f in fields[4:] if f.startswith("[from]")]
                direct = not from_tags and last_move and last_move["target"] == target
                row["move_link"] = last_move if direct else None
                row["delayed_resolution"] = (
                    delayed_resolution
                    if delayed_resolution
                    and delayed_resolution["target"] == target
                    and not from_tags
                    else None
                )
                row["cause_tags"] = fields[4:]
                last_damage[target] = ref
            health[target], health_refs[target] = after, ref
        elif kind == "faint":
            row.update(hp_before=health.get(target), preceding_damage_ref=last_damage.get(target))
            health[target] = hp("0 fnt", actor, target, health.get(target))
            health_refs[target] = ref
            row["hp_after"] = health[target]
        records.append(row)
    observation = context["current_observation"]
    numeric = []
    for key in ("self_side_conditions", "opponent_side_conditions", "weather", "field"):
        for name, value in sorted(observation.get(key, {}).items()):
            meaning = (
                "layers"
                if key.endswith("side_conditions") and name in {"SPIKES", "TOXIC_SPIKES"}
                else ("last_weather_protocol_turn" if key == "weather" else "activation_turn")
            )
            numeric.append(
                {"path": ["current_observation", key, name], "raw_value": value, "meaning": meaning}
            )
    # Effects in poke-env are presence markers or elapsed counters, never remaining turns.
    from poke_env.environment.effect import Effect

    for group in ("self_team", "opponent_confirmed"):
        for i, mon in enumerate(observation.get(group, [])):
            for source_key in ("effects", "parser_effects"):
                for name, value in sorted(mon.get(source_key, {}).items()):
                    effect = Effect[name]
                    meaning = (
                        "elapsed_turn_counter"
                        if effect.is_turn_countable
                        else (
                            "repeated_activation_counter"
                            if effect.is_action_countable
                            else "presence_marker"
                        )
                    )
                    numeric.append(
                        {
                            "path": ["current_observation", group, i, source_key, name],
                            "raw_value": value,
                            "meaning": meaning,
                        }
                    )
    return {"numeric_state": numeric, "event_annotations": records}


def protocol_rows(events, *, require_refs=True):
    """Yield occurrence turns in wire order; packet metadata is not an event clock."""
    turn = None
    previous = -1
    for event in events:
        seq = event["event_seq"] if require_refs else event.get("event_seq")
        if seq is not None:
            if seq <= previous:
                raise ValueError("non-increasing protocol event order")
            previous = seq
        for number, line in enumerate(event["protocol"].splitlines(), 1):
            fields = line.split("|")
            if len(fields) < 2:
                continue
            if fields[1] == "start" and turn is None:
                turn = 0
            elif fields[1] == "turn":
                next_turn = int(fields[2])
                if turn is not None and next_turn < turn:
                    raise ValueError("protocol turn moved backwards")
                turn = next_turn
            yield fields, turn, {"event": seq, "line": number}


def observed_state(events):
    """Track weather/field/side lifetimes and delayed slot effects from public rows.

    A -start Future Sight row names the caster, while -end names the occupant of
    the destination slot. Parser Pokemon.effects counters are neither the slot
    lifetime nor a start turn. Absent start evidence stays unknown.
    """
    weather, fields, sides, pending, history, occupants = {}, {}, {}, {}, [], {}
    identity_slots = {}

    def destination(target):
        slot = target.split(":", 1)[0]
        if re.fullmatch(r"p[12][a-z]", slot):
            return slot
        if re.fullmatch(r"p[12]: .+", target):
            candidates = identity_slots.get(target, set())
            if len(candidates) == 1:
                return next(iter(candidates))
        # Keep unsupported/ambiguous destinations for the delayed-start guard.
        return slot

    last_move = None
    ended_families = {}
    for parts, turn, ref in protocol_rows(events):
        kind = parts[1]
        if kind in ("-start", "-end") and len(parts) > 3:
            family = re.sub(r"[^a-z]", "", parts[3].lower())
            for prefix in ("quarkdrive", "protosynthesis"):
                if family.startswith(prefix):
                    ended_families.setdefault(ident(parts[2]), {})[prefix] = kind == "-end"
        if kind == "turn":
            last_move = None
            for slot, effect in list(pending.items()):
                start = effect["observed_start_turn"]
                # The pinned Gen9 simulator silently expires if the occupant is
                # fainted. The following turn establishes expiry, not hit/damage.
                if start is not None and start < 255 and turn > start + 2:
                    history.append(
                        dict(
                            effect,
                            status="expired_without_public_resolution",
                            end_ref=ref,
                            resolution_turn=None,
                        )
                    )
                    del pending[slot]
        elif kind in ("switch", "drag", "replace", "faint"):
            slot = parts[2].split(":", 1)[0]
            if re.fullmatch(r"p[12][a-z]: .+", parts[2]):
                # Public identity evidence survives fainting and replacement.
                # Multiple observed slots remain ambiguous; never default to a.
                identity_slots.setdefault(ident(parts[2]), set()).add(slot)
            if kind != "faint":
                occupants[slot] = ident(parts[2])
        elif kind == "move":
            last_move = dict(
                user=ident(parts[2]),
                move=parts[3],
                target_slot=destination(parts[4]) if len(parts) > 4 else None,
                ref=ref,
                turn=turn,
            )
        elif kind == "-weather":
            name = parts[2]
            if name == "none":
                weather.clear()
            else:
                upkeep = "[upkeep]" in parts[3:]
                old = weather.get(name, {}) if upkeep else {}
                weather = {
                    name: dict(
                        observed_start_turn=old.get("observed_start_turn") if upkeep else turn,
                        start_ref=old.get("start_ref") if upkeep else ref,
                        last_update_turn=turn,
                        last_update_ref=ref,
                    )
                }
        elif kind in ("-fieldstart", "-fieldend"):
            name = parts[2].removeprefix("move: ")
            if kind == "-fieldend":
                fields.pop(name, None)
            else:
                terrains = {
                    "Electric Terrain",
                    "Grassy Terrain",
                    "Misty Terrain",
                    "Psychic Terrain",
                }
                if name in terrains:
                    fields = {k: v for k, v in fields.items() if k not in terrains}
                fields[name] = dict(observed_start_turn=turn, start_ref=ref)
        elif kind in ("-sidestart", "-sideend"):
            side, name = parts[2][:2], parts[3].removeprefix("move: ")
            current = sides.setdefault(side, {})
            if kind == "-sideend":
                current.pop(name, None)
            else:
                value = current.setdefault(
                    name, dict(observed_start_turn=turn, start_ref=ref, activation_refs=[])
                )
                value["activation_refs"].append(ref)
                if name in ("Spikes", "Toxic Spikes"):
                    value["layers"] = len(value["activation_refs"])
        elif kind == "-swapsideconditions":
            # Move the original records intact: no new installation, layer, or
            # duration clock is created by a swap, including repeated swaps.
            left, right = (sides.setdefault(side, {}) for side in ("p1", "p2"))
            for name in sorted(set(left) | set(right)):
                if re.sub(r"[^a-z0-9]", "", name.lower()) not in COURT_CHANGE_CONDITIONS:
                    continue
                first, second = left.pop(name, None), right.pop(name, None)
                if second is not None:
                    left[name] = second
                if first is not None:
                    right[name] = first
        elif kind == "-start" and parts[3] in (
            "move: Future Sight", "move: Doom Desire", "Doom Desire"
        ):
            move = parts[3].removeprefix("move: ")
            user = ident(parts[2])
            linked = last_move and last_move["user"] == user and last_move["move"] == move
            slot = last_move["target_slot"] if linked else None
            if slot is not None and not re.fullmatch(r"p[12][a-z]", slot):
                raise ValueError("unsupported delayed effect destination")
            key = slot or f"unknown:{ref['event']}:{ref['line']}"
            if key in pending:
                raise ValueError("duplicate successful delayed effect on occupied slot")
            pending[key] = dict(
                effect=move.upper().replace(" ", "_"),
                user=user,
                target_slot=slot,
                observed_start_turn=turn,
                start_ref=ref,
                move_ref=last_move["ref"] if linked else None,
                status="pending",
                immediate_damage=False,
            )
        elif kind == "-end" and parts[3] in ("move: Future Sight", "move: Doom Desire"):
            slot = parts[2].split(":", 1)[0]
            effect = pending.pop(
                slot,
                dict(
                    effect=parts[3][6:].upper().replace(" ", "_"),
                    user=None,
                    target_slot=slot,
                    observed_start_turn=None,
                    start_ref=None,
                ),
            )
            history.append(
                dict(
                    effect,
                    status="resolution_observed",
                    end_ref=ref,
                    resolution_turn=turn,
                    resolution_target=ident(parts[2]),
                )
            )
            last_move = None
        elif kind in ("win", "tie"):
            history.extend(dict(e, status="battle_ended", end_ref=ref) for e in pending.values())
            pending.clear()
    return dict(
        weather=weather,
        field=fields,
        sides=sides,
        pending_effects=[
            dict(
                e,
                current_occupant=occupants.get(e["target_slot"]),
                resolution="future occupant/field and damage unknown",
            )
            for e in pending.values()
        ],
        delayed_history=history,
        ended_ability_effects=ended_families,
    )


def protect_lifetimes(events):
    """Internal Protect evidence, scoped to one actor's ordered public prefix.

    A move attempt is not success. singleturn and activation rows establish
    presence; upkeep is emitted after Residual has removed duration-1 volatiles.
    Neither parser counters nor packet turn metadata establish a lifetime.
    Identity contradictions remain unknown, never permission to drop an effect.
    """
    current, occupants, history = {}, {}, []

    def expire(key, reason, turn, ref):
        effect = current.get(key)
        if effect and effect["status"] == "active":
            effect.update(
                status="expired", end_reason=reason, end_turn=turn, end_ref=ref
            )

    for parts, turn, ref in protocol_rows(events):
        kind = parts[1]
        if kind in ("turn", "upkeep"):
            for key, effect in current.items():
                if (
                    kind == "upkeep"
                    or effect["start_turn"] is None
                    or turn > effect["start_turn"]
                ):
                    expire(key, kind, turn, ref)
            continue
        if len(parts) < 3 or not re.fullmatch(r"p[12][a-z]?: .+", parts[2]):
            continue
        key = ident(parts[2])
        slot = parts[2].split(":", 1)[0]
        old = occupants.get(slot)
        if kind in ("switch", "drag"):
            if old:
                expire(old, kind, turn, ref)
            # Re-entry also clears an earlier occurrence for this individual.
            expire(key, kind, turn, ref)
            occupants[slot] = key
        elif kind == "replace":
            # Illusion reveals an identity without a switch. Do not transfer an
            # old lifetime to the newly named Pokemon or infer an expiration.
            for target in (old, key):
                if target in current:
                    current[target].update(status="unknown", conflict_ref=ref)
            occupants[slot] = key
        elif kind == "faint":
            expire(key, kind, turn, ref)
        elif (
            kind == "-activate"
            and len(parts) > 3
            and (
                parts[3] == "move: Feint"
                or (parts[3].startswith("move: ") and "[broken]" in parts[4:])
            )
        ):
            # Pinned hitStepBreakProtect reports removal with activation, not
            # -end (Feint has no [broken] tag; other breaking moves do).
            expire(key, "protect_broken", turn, ref)
        elif len(parts) > 3 and parts[3] in ("Protect", "move: Protect"):
            if kind in ("-singleturn", "-activate"):
                prior = current.get(key)
                # Repeated block notices belong to the same occurrence; a new
                # singleturn (including in the same turn) starts a new one.
                if kind == "-activate" and prior and prior["status"] == "active":
                    prior["activation_refs"].append(ref)
                else:
                    effect = dict(
                        status="active",
                        start_turn=turn,
                        start_ref=ref,
                        start_kind=kind,
                        activation_refs=[ref],
                        end_reason=None,
                        end_turn=None,
                        end_ref=None,
                    )
                    current[key] = effect
                    history.append(dict(pokemon_ident=key, occurrence=effect))
                if old is not None and old != key:
                    current[key].update(status="unknown", conflict_ref=ref)
                    if old in current:
                        current[old].update(status="unknown", conflict_ref=ref)
                else:
                    occupants[slot] = key
            elif kind == "-end":
                expire(key, kind, turn, ref)
    return dict(current=current, history=history)


def live_effects(pokemon, key, timing, protect=None, court_change=None):
    """Preserve raw parser values separately; project active effects omit stale state."""
    raw = {k.name: v for k, v in pokemon.effects.items()}
    if pokemon.fainted:
        return {}
    ended = timing.get("ended_ability_effects", {}).get(key, {})
    effects = {
        k: v
        for k, v in raw.items()
        if k not in ("FUTURE_SIGHT", "DOOM_DESIRE")
        and not any(
            ended.get(prefix) and k.replace("_", "").lower().startswith(prefix)
            for prefix in ("quarkdrive", "protosynthesis")
        )
    }
    lifetime = (protect or {}).get("current", {}).get(key, {})
    if key in (court_change or {}):
        effects.pop("COURT_CHANGE", None)
    if lifetime.get("status") == "expired":
        effects.pop("PROTECT", None)
    elif lifetime.get("status") in ("active", "unknown"):
        # A presence marker is not a duration. Unknown public activation must
        # also retain the calculator's unsupported-effect failure boundary.
        effects.setdefault("PROTECT", 0)
    return effects
