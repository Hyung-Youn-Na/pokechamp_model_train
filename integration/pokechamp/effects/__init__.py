"""Pinned game rules, collected only from fields in this request's visible input."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).parent
VERSION = "gen9-effects-v1"
KINDS = ("items", "abilities", "moves")
# These are producer states, not Dex entries. Recharge is a server action marker.
SENTINELS = {"", "unknown", "unknownitem", "none", "null", "noability", "noitem"}
FIELDS = {
    "item": "items",
    "prev_item": "items",
    "last_item": "items",
    "ability": "abilities",
    "baseAbility": "abilities",
    "base_ability": "abilities",
    "move": "moves",
    "moves": "moves",
    "confirmed_moves": "moves",
    "terastallize": "moves",
    "dynamax": "moves",
    "last_move": "moves",
}
# Positional public effect arguments in the pinned data/{moves,abilities,items}.ts.
# These are protocol fields, not names inferred from free text or a Pokemon species.
ACTIVATION_ARGUMENTS = {
    "skillswap": ("abilities", (4, 5)),
    "wanderingspirit": ("abilities", (4, 5)),
    "mummy": ("abilities", (4,)),
    "lingeringaroma": ("abilities", (4,)),
    "forewarn": ("moves", (4,)),
    "leppaberry": ("moves", (4,)),
    "mysteryberry": ("moves", (4,)),
    "safetygoggles": ("moves", (4,)),
    "eeriespell": ("moves", (4,)),
    "grudge": ("moves", (4,)),
    "matblock": ("moves", (4,)),
    "sketch": ("moves", (4,)),
    "poltergeist": ("items", (4,)),
    "symbiosis": ("items", (4,)),
}


class EffectReferenceError(ValueError):
    category = "input_contract"

    def __init__(self, path, kind, value):
        self.path, self.kind, self.reference_id = path, kind, value
        super().__init__(f"effect reference unresolved: {path}: {kind}/{value}")

    def as_dict(self):
        return dict(path=self.path, kind=self.kind, reference_id=self.reference_id)


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _asset():
    data = (ASSETS / f"{VERSION}.json").read_bytes()
    return _decode(data, (ASSETS / "provenance.json").read_bytes())


@lru_cache(maxsize=1)
def _decode(data, metadata):
    provenance = json.loads(metadata)
    if hashlib.sha256(data).hexdigest() != provenance["asset_sha256"]:
        raise ValueError("effect asset hash mismatch")
    value = json.loads(data)
    if value["version"] != VERSION or provenance["version"] != VERSION:
        raise ValueError("effect asset version mismatch")
    return value, provenance


def identity():
    _, source = _asset()
    return {k: source[k] for k in ("version", "source_commit", "asset_sha256", "license_sha256")}


def references(value):
    """Yield typed references and their source paths, never search free-form prose.

    The caller passes the transmitted projection, before adding a dictionary.
    Protocol references are historical facts, not claims about current possession.
    """
    asset, _ = _asset()

    def emit(kind, raw, path):
        if raw is None:
            return
        if not isinstance(raw, str):
            raise EffectReferenceError(path, kind, repr(raw))
        key = normalize(raw)
        if raw.strip() == "" or key in SENTINELS - {""} or (kind == "moves" and key == "recharge"):
            return
        key = asset["aliases"][kind].get(key, key)
        if key not in asset[kind] or not asset[kind][key].get("desc"):
            raise EffectReferenceError(path, kind, raw)
        yield kind, key, path

    def condition(raw, path):
        # Untyped status/volatile names are not necessarily a move or ability.
        # Only exact Dex names/IDs are looked up; no species or text inference.
        key = normalize(raw)
        for kind in KINDS:
            if key in asset[kind]:
                yield from emit(kind, raw, path)

    def typed(raw, path):
        match = re.fullmatch(r"(?:\[from\] )?(item|ability|move): (.+)", raw)
        match = match or re.fullmatch(r"\[(item|ability|move)\] (.+)", raw)
        if match:
            yield from emit(
                {"item": "items", "ability": "abilities", "move": "moves"}[match[1]], match[2], path
            )

    def protocol(text, path):
        for number, line in enumerate(text.splitlines(), 1):
            row = f"{path}:line{number}"
            if line.startswith("|request|"):
                if line[9:]:
                    yield from walk(json.loads(line[9:]), row + ".RequestJSON")
                continue
            parts = line.split("|")
            if len(parts) < 3:
                continue
            kind = parts[1]
            if kind == "move" and len(parts) > 3:
                yield from emit("moves", parts[3], row)
            elif kind in ("-item", "-enditem", "-ability", "-endability") and len(parts) > 3:
                yield from emit("items" if "item" in kind else "abilities", parts[3], row)
            # Ignore chat, nicknames, details and presentation records entirely.
            if kind.startswith("-") or kind in ("move", "cant", "damage", "heal"):
                for index, part in enumerate(parts[2:], 2):
                    yield from typed(part, row + f"[{index}]")
                if kind in (
                    "-start",
                    "-end",
                    "-activate",
                    "-sidestart",
                    "-sideend",
                    "-singleturn",
                    "-singlemove",
                ):
                    if len(parts) > 3:
                        yield from condition(parts[3], row)
                elif kind in ("-fieldstart", "-fieldend", "-weather"):
                    yield from condition(parts[2], row)
                elif kind == "cant" and len(parts) > 4:
                    yield from emit("moves", parts[4], row)
                if kind == "-activate" and len(parts) > 3:
                    effect = normalize(parts[3].split(": ")[-1])
                    if effect in ACTIVATION_ARGUMENTS:
                        category, positions = ACTIVATION_ARGUMENTS[effect]
                        for position in positions:
                            if position < len(parts):
                                yield from emit(category, parts[position], row + f"[{position}]")

    def walk(node, path):
        if isinstance(node, list):
            for index, child in enumerate(node):
                yield from walk(child, f"{path}[{index}]")
        elif isinstance(node, dict):
            for key, child in node.items():
                here = path + "." + key
                if key == "effect_reference":
                    raise ValueError("effect dictionary must be built from an original projection")
                if key == "protocol" and isinstance(child, str):
                    yield from protocol(child, here)
                elif key in FIELDS:
                    kind = FIELDS[key]
                    if isinstance(child, list):
                        for index, entry in enumerate(child):
                            if isinstance(entry, dict):
                                # Active request slots have a stable ID even when
                                # their display name contains dynamic power/type.
                                if "id" in entry:
                                    yield from emit(kind, entry["id"], f"{here}[{index}].id")
                                    yield from walk(
                                        {k: v for k, v in entry.items() if k not in ("id", "move")},
                                        f"{here}[{index}]",
                                    )
                                else:
                                    yield from walk(entry, f"{here}[{index}]")
                            else:
                                yield from emit(kind, entry, f"{here}[{index}]")
                    elif isinstance(child, dict):
                        if key == "move" and "name" in child:
                            yield from emit(kind, child["name"], here + ".name")
                        else:
                            yield from walk(child, here)
                    else:
                        yield from emit(kind, child, here)
                elif key == "activations" and isinstance(child, dict):
                    for name in child:
                        yield from emit("abilities", name, here + "." + name)
                elif key in (
                    "effects",
                    "parser_effects",
                    "side_conditions",
                    "fields",
                    "field",
                    "weather",
                ):
                    if isinstance(child, dict):
                        for name in child:
                            yield from condition(name, here + "." + name)
                        yield from walk(child, here)
                elif key == "ended_ability_effects" and isinstance(child, dict):
                    for holder, families in child.items():
                        for name in families:
                            yield from emit("abilities", name, here + "." + holder + "." + name)
                elif key == "sides" and isinstance(child, dict):
                    for side, conditions in child.items():
                        for name in conditions:
                            yield from condition(name, here + "." + side + "." + name)
                elif key == "disabledSource" and isinstance(child, str):
                    yield from typed(child, here)
                elif key == "effect" and isinstance(child, str):
                    yield from condition(child, here)
                else:
                    yield from walk(child, here)

    yield from walk(value, "$")


def build(value):
    asset, _ = _asset()
    keys = {kind: set() for kind in KINDS}
    for kind, key, _ in references(value):
        keys[kind].add(key)
    return {
        kind: {key: copy.deepcopy(asset[kind][key]) for key in sorted(keys[kind])} for kind in KINDS
    }


def augment(value):
    return {**copy.deepcopy(value), "effect_reference": build(value)}
