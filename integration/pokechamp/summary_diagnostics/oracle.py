"""Independent raw-row checks. Never imports the operational protocol/transform code.

The authored reference records pin occurrence turns, row identities, and exact
self request fields. Checks compare each side directly with original protocol,
so agreement between a corrupt annotation and reference cannot qualify a run.
"""

from __future__ import annotations

import json
import re


def raw_index(reference):
    rows, turn = {}, None
    actor = reference["identity"]["actor_id"]
    for event in reference["source_events"]:
        if (
            event.get("battle_id", reference["identity"]["battle_id"])
            != reference["identity"]["battle_id"]
        ):
            raise ValueError("foreign source battle")
        if event["event_seq"] >= reference.get("cutoff", float("inf")):
            raise ValueError("future source event")
        for n, line in enumerate(event["protocol"].splitlines(), 1):
            parts = line.split("|")
            if len(parts) > 1 and parts[1] == "start" and turn is None:
                turn = 0
            if line.startswith("|turn|"):
                turn = int(parts[2])
            if line.startswith("|request|") and line[9:]:
                request = json.loads(line[9:])
                if request.get("side", {}).get("id", actor) != actor:
                    raise ValueError("foreign request actor")
            rows[event["event_seq"], n] = (line, parts, turn)
    return rows


def verify_reference(reference):
    rows = raw_index(reference)
    facts = reference["facts"]
    if len({f["id"] for f in facts}) != len(facts):
        raise ValueError("duplicate fact identity")
    for fact in facts:
        if not fact["expected"] or not fact["evidence"]:
            raise ValueError("fact has no expected content/evidence")
        for evidence in fact["evidence"]:
            line, parts, turn = rows[evidence["event"], evidence["line"]]
            if evidence["quote"] not in line or evidence["turn"] != turn:
                raise ValueError("reference original quote/occurrence turn mismatch")
            if evidence["parts"] != parts:
                raise ValueError("reference original actor/value mismatch")
        if fact.get("identity") and any(
            reference["identity"][k] != v for k, v in fact["identity"].items()
        ):
            raise ValueError("reference identity mismatch")
        assertion = fact.get("self_request")
        if assertion:
            evidence = fact["evidence"][0]
            request = json.loads(rows[evidence["event"], evidence["line"]][0][9:])
            mon = next(m for m in request["side"]["pokemon"] if m["ident"] == assertion["ident"])
            if any(mon[k] != v for k, v in assertion.items()):
                raise ValueError("reference self request mismatch")
            if assertion["condition"] not in fact["expected"]:
                raise ValueError("reference prose HP contradicts explicit self assertion")
    return True


def verify_annotations(context, reference):
    rows = raw_index(reference)
    if context["identity"]["actor_id"] != reference["identity"]["actor_id"]:
        raise ValueError("annotation actor mismatch")
    actor = context["identity"]["actor_id"]
    annotation = context["harness_annotations"]
    for row in annotation["event_annotations"]:
        ref = row["ref"]
        line, parts, turn = rows[ref["event"], ref["line"]]
        if row["turn"] != turn or row["kind"] != parts[1]:
            raise ValueError("annotation occurrence turn/kind mismatch")
        target = re.sub(r"^(p[12])[a-z]:", r"\1:", parts[2]) if len(parts) > 2 else None
        if "target" in row and row["target"] != target:
            raise ValueError("annotation target actor mismatch")
        after = row.get("hp_after")
        if after:
            token = (
                "0 fnt"
                if parts[1] == "faint"
                else parts[4]
                if parts[1] in ("switch", "drag", "replace")
                else parts[3]
            )
            precision = "exact_self" if target.startswith(actor + ":") else "rounded_public"
            if after["raw"] != token or after["current"] != int(token.split("/")[0].split()[0]):
                raise ValueError("annotation observed HP mismatch")
            if after["precision"] != precision:
                raise ValueError("annotation HP precision mismatch")
        before = row.get("hp_before")
        if before and row.get("hp_before_ref"):
            prior = row["hp_before_ref"]
            original = rows[prior["event"], prior["line"]][0]
            if before["raw"] not in original or (prior["event"], prior["line"]) >= (
                ref["event"],
                ref["line"],
            ):
                raise ValueError("annotation preceding HP source mismatch")
            if row["observed_hp_decrease"] != before["current"] - after["current"]:
                raise ValueError("annotation HP decrement mismatch")
        move = row.get("observed_move") or row.get("move_link")
        if move:
            source = rows[move["ref"]["event"], move["ref"]["line"]][1]
            if (
                source[1] != "move"
                or move["move"] != source[3]
                or move["user"] != re.sub(r"^(p[12])[a-z]:", r"\1:", source[2])
            ):
                raise ValueError("annotation move actor mismatch")
    for row in annotation["numeric_state"]:
        path = row["path"]
        raw = context
        for key in path:
            raw = raw[key]
        if raw != row["raw_value"]:
            raise ValueError("numeric raw value mismatch")
        if path[1] == "weather" and row["meaning"] != "last_weather_protocol_turn":
            raise ValueError("weather numeric meaning mismatch")
        if path[1].endswith("side_conditions"):
            meaning = "layers" if path[-1] in ("SPIKES", "TOXIC_SPIKES") else "activation_turn"
            if row["meaning"] != meaning:
                raise ValueError("side numeric meaning mismatch")
        if path[-1] == "FUTURE_SIGHT" and row["meaning"] != "elapsed_turn_counter":
            raise ValueError("Future Sight counter meaning mismatch")
    # Independently verify weather onset vs upkeep from raw rows, not any numeric annotation.
    actual = {}
    for line, parts, turn in rows.values():
        if line.startswith("|-weather|"):
            if parts[2] == "none":
                actual = {}
            else:
                start = actual.get(parts[2], {}).get("start") if "[upkeep]" in parts else turn
                actual = {parts[2]: dict(start=start, last=turn)}
    for name, value in context["current_observation"]["protocol_state"]["weather"].items():
        if actual.get(name) != dict(
            start=value["observed_start_turn"], last=value["last_update_turn"]
        ):
            raise ValueError("weather independent onset/update mismatch")
    return True


def verify_observation(context, reference):
    """Every transmitted self-request field is checked directly against the last request."""
    rows = raw_index(reference)
    requests = [
        json.loads(line[9:])
        for line, _, _ in rows.values()
        if line.startswith("|request|") and line[9:]
    ]
    latest = next(r for r in reversed(requests) if "side" in r)
    actual = context["current_observation"]["self_team"]
    if [m["ident"] for m in actual] != [m["ident"] for m in latest["side"]["pokemon"]]:
        raise ValueError("self observation identity/order differs from request")
    for raw, mon in zip(latest["side"]["pokemon"], actual):
        if any(mon.get(k) != v for k, v in raw.items()):
            raise ValueError("self observation differs from original request field")
        if mon["hp_precision"] != "exact_self_request":
            raise ValueError("self observation precision mismatch")
    # All emitted semantic rows must correspond to all eligible source rows exactly once.
    expected = {
        (event, number)
        for (event, number), (_, parts, _) in rows.items()
        if event in {e["event_seq"] for e in context["source_events"]}
        and len(parts) > 1
        and (
            parts[1].startswith("-")
            or parts[1] in {"turn", "move", "switch", "drag", "replace", "faint"}
        )
    }
    actual_refs = [
        (r["ref"]["event"], r["ref"]["line"])
        for r in context["harness_annotations"]["event_annotations"]
    ]
    if set(actual_refs) != expected or len(actual_refs) != len(expected):
        raise ValueError("annotation source row coverage mismatch")
    verify_public_abilities(context, rows)
    verify_public_items(context, rows)
    return True


def verify_public_abilities(context, rows):
    """Check public activation identities against raw rows, independent of the parser.

    Recognizes the activation forms and explicit weather holders audited for EX-022/025;
    it does not infer an ability from effect markers or the diagnostic annotations.
    """
    current, original, slots = {}, {}, {}
    for _, parts, _ in rows.values():
        if len(parts) > 4 and parts[1] == "-weather":
            sources = [
                p[len("[from] ability: ") :] for p in parts if p.startswith("[from] ability: ")
            ]
            holders = [p[5:] for p in parts if re.match(r"^\[of\] p[12][a-z]?: ", p)]
            if len(sources) == len(holders) == 1:
                who = re.sub(r"^(p[12])[a-z]:", r"\1:", holders[0])
                name = re.sub(r"[^a-z0-9]", "", sources[0].lower())
                if who not in current:
                    original.setdefault(who, name)
                current[who] = name
            continue
        if len(parts) < 3 or not re.match(r"^p[12][a-z]?: ", parts[2]):
            continue
        who = re.sub(r"^(p[12])[a-z]:", r"\1:", parts[2])
        kind = parts[1]
        if kind in ("switch", "drag"):
            slot = parts[2].split(":")[0]
            for mon in (slots.get(slot), who):
                if mon in current:
                    current[mon] = original.get(mon)
            slots[slot] = who
        elif kind == "-endability":
            current[who] = ""
        elif kind == "-ability":
            current[who] = re.sub(r"[^a-z0-9]", "", parts[3].lower())
            if not any(p.startswith("[from]") for p in parts[4:]):
                original.setdefault(who, current[who])
        elif kind == "-activate" and parts[3] in {
            "ability: Supreme Overlord",
            "ability: Quark Drive",
            "ability: Protosynthesis",
        }:
            name = re.sub(r"[^a-z0-9]", "", parts[3][9:].lower())
            if who not in current:
                original.setdefault(who, name)
            current[who] = name
    for mon in context["current_observation"]["opponent_confirmed"]:
        who = mon["ident"]
        if who in current and (
            mon["ability"] != current[who] or mon["ability_known"] is not (current[who] is not None)
        ):
            raise ValueError("public ability observation contradicts original protocol")


def verify_public_items(context, rows):
    """Independently retain public orb activations and later item changes/removal."""
    current = {}
    for _, parts, _ in rows.values():
        if len(parts) < 4 or not re.match(r"^p[12][a-z]?: ", parts[2]):
            continue
        who = re.sub(r"^(p[12])[a-z]:", r"\1:", parts[2])
        if parts[1] == "-item":
            current[who] = re.sub(r"[^a-z0-9]", "", parts[3].lower())
        elif parts[1] == "-enditem":
            current[who] = None
        elif parts[1] == "-status" and len(parts) == 5:
            if parts[3:] == ["tox", "[from] item: Toxic Orb"]:
                current[who] = "toxicorb"
            elif parts[3:] == ["brn", "[from] item: Flame Orb"]:
                current[who] = "flameorb"
    for mon in context["current_observation"]["opponent_confirmed"]:
        if mon["ident"] in current and mon["item"] != current[mon["ident"]]:
            raise ValueError("public item observation contradicts original protocol")
