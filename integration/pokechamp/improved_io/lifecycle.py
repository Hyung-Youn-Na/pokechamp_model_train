"""Battle-local public activation history, independent of the rolling prompt window."""

from __future__ import annotations

import copy
import json

from .protocol import ident, protocol_rows

VERSION = "calculator-input-v2"
ONCE = {"dauntlessshield", "intrepidsword"}


def ability_histories(events, *, battle_id, actor_id):
    """A complete public prefix proves absence; a truncated prefix never does.

    Pinned Gen9 emits -ability|holder|name|boost for entry activations. Consumption
    belongs to the Pokemon, not its current slot, current ability, or boost stage.
    Suppression/restoration and changing abilities cannot clear these records.
    """
    histories, occupants = {}, {}
    faints = {"p1": 0, "p2": 0}
    complete = False

    def row(key):
        return histories.setdefault(
            key,
            dict(
                battle_id=battle_id,
                actor_id=actor_id,
                pokemon_ident=key,
                history_complete=complete,
                entries=[],
                activations={},
                suppressed=False,
                qp_source=None,
            ),
        )

    for parts, _, ref in protocol_rows(events):
        kind = parts[1]
        if kind == "start":
            complete = True
        if kind == "request" and len(parts) > 2 and parts[2]:
            request = json.loads("|".join(parts[2:]))
            if request.get("side", {}).get("id", actor_id) != actor_id:
                raise ValueError("foreign request in public ability history")
            for pokemon in request.get("side", {}).get("pokemon", []):
                row(pokemon["ident"])
        if (
            len(parts) < 3
            or not parts[2].startswith(("p1", "p2"))
            or ": " not in parts[2]
        ):
            continue
        key = ident(parts[2])
        if kind in ("switch", "drag", "replace"):
            slot = parts[2].split(":", 1)[0]
            previous = occupants.get(slot)
            if previous:
                row(previous)["suppressed"] = False
                row(previous)["qp_source"] = None
            occupants[slot] = key
            current = row(key)
            current["suppressed"] = False
            current["qp_source"] = None
            current["entries"].append(ref)
        elif kind == "-endability":
            row(key)["suppressed"] = True
        elif kind == "faint":
            faints[key[:2]] += 1
        elif (
            kind == "-activate"
            and len(parts) > 3
            and parts[3] in ("ability: Protosynthesis", "ability: Quark Drive")
        ):
            row(key)["qp_source"] = "item" if "[fromitem]" in parts[4:] else "field"
        elif (
            kind == "-end"
            and len(parts) > 3
            and parts[3].lower().replace(" ", "") in ("protosynthesis", "quarkdrive")
        ):
            row(key)["qp_source"] = None
        elif kind == "-ability" and len(parts) > 3:
            current = row(key)
            current["suppressed"] = False
            if "boost" in parts[4:]:
                ability = "".join(c for c in parts[3].lower() if c.isalnum())
                current["activations"].setdefault(ability, []).append(ref)
    for key, history in histories.items():
        history["history_complete"] = complete
        history["team_faints"] = faints[key[:2]] if complete else None
    return histories, complete


def for_pokemon(histories, complete, *, battle_id, actor_id, pokemon_ident):
    return copy.deepcopy(
        histories.get(
            pokemon_ident,
            dict(
                battle_id=battle_id,
                actor_id=actor_id,
                pokemon_ident=pokemon_ident,
                history_complete=complete,
                entries=[],
                activations={},
                suppressed=False,
                qp_source=None,
                team_faints=0 if complete else None,
            ),
        )
    )


def entry_observed(mon):
    """Whether to suppress the calc's one-time entry trigger, not passive effects."""
    from .calculator import CalculationError

    if mon["active"]:
        return True
    ability = "".join(c for c in mon["ability"].lower() if c.isalnum())
    if ability not in ONCE:
        return False
    history = mon.get("ability_history")
    if history is None or not history.get("history_complete"):
        if not history or not history.get("activations", {}).get(ability):
            raise CalculationError(
                "unknown once-per-battle ability consumption history"
            )
    return bool(history["activations"].get(ability))
