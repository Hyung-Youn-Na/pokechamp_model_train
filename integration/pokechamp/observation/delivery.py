"""Versioned B/B2 official observations, exact-string verification before dispatch."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from ..effects import augment, identity as effect_identity
from ..improved_io import battle_prompts
from ..improved_io.battle_only_protocol import validate_context
from ..improved_io.delivery import Delivery, digest, dumps, parse_json
from ..improved_io.delivery import calculations, exclusions, preservation
from . import OFFICIAL

ASSETS = Path(__file__).parent
FORMAT = "official-observation-delivery-v1"
BATTLE_VERSION = "v1.4.0"


def asset(name):
    content = (ASSETS / name).read_text()
    manifest = json.loads((ASSETS / "prompt-provenance.json").read_text())
    if digest(content) != manifest[name]:
        raise ValueError("official observation prompt asset mismatch")
    return content


def prompt_identity(kind="b2"):
    if kind == "battle":
        return battle_prompts.identity(BATTLE_VERSION)
    if kind != "b2":
        raise ValueError("unknown official delivery kind")
    return dict(version="b2-official-v1", sha256=digest(asset("b2-prompt.txt")),
                field_catalog_sha256=digest(asset("b2-fields.json")),
                observation_version=OFFICIAL, effect_reference_identity=effect_identity())


def system_prompt(kind="b2"):
    return asset("b2-prompt.txt") if kind == "b2" else battle_prompts.assemble(version=BATTLE_VERSION)


def build(full, *, kind):
    if kind not in ("battle", "b2"):
        raise ValueError("unknown official delivery kind")
    validate_context(full)
    if (full["identity"].get("observation_version") != OFFICIAL
            or full["current_observation"].get("observation_source", {}).get("version") != OFFICIAL):
        raise ValueError("official delivery observation identity missing")
    battle_prompts.check_fields(full, battle_prompts.catalog(BATTLE_VERSION))
    # Scope validation still rejects active unused mechanics/foreign allies.
    pruned, ledger = exclusions.prune(full)
    if kind == "b2":
        value = pruned
        value["calculation_bundle"] = calculations.encode(
            value["calculation_bundle"], value["current_observation"], value["opponent_hypotheses"])
        restored = copy.deepcopy(value)
        restored["calculation_bundle"] = calculations.decode(restored["calculation_bundle"])
        preservation.check_source(full, restored, ledger)
        guide = parse_json(asset("b2-fields.json"))
    else:
        value = copy.deepcopy(full)
        ledger = []
        guide = battle_prompts.catalog(BATTLE_VERSION)
    wire = augment(value)
    battle_prompts.check_fields(wire, guide)
    system, user = system_prompt(kind), dumps(wire)
    link = dict(format_version=FORMAT, kind=kind, candidate_version="B2" if kind == "b2" else "B",
                prompt_identity=prompt_identity(kind), identity=full["identity"],
                observation_source=full["current_observation"]["observation_source"],
                effect_reference_identity=effect_identity(),
                original_user_sha256=digest(json.dumps(full, ensure_ascii=False, allow_nan=False)),
                system_sha256=digest(system), user_sha256=digest(user), exclusions=ledger)
    return Delivery(link["candidate_version"], "calculator-input-v2", system, user, dumps(link))


def validate(full, delivery, system, user, *, kind):
    expected = build(full, kind=kind)
    if delivery != expected or system != expected.system_prompt or user != expected.user_json:
        raise ValueError("official observation original/version/wire mismatch")
    return parse_json(expected.source_link_json)
