"""Versioned model-only projection; original observations remain untouched."""

from __future__ import annotations

import json
from pathlib import Path

from ..improved_io import battle_prompts as bp
from ..improved_io.delivery import Delivery, digest, dumps, generate, parse_json
from . import augment, identity

ASSETS = Path(__file__).parent
BATTLE_VERSION = "v1.3.0"
LEAD_VERSION = "v1.1.0"
FORMAT_VERSION = "effect-delivery-v1"


def asset(name):
    value = (ASSETS / name).read_text()
    sealed = json.loads((ASSETS / "prompt-provenance.json").read_text())
    if digest(value) != sealed[name]:
        raise ValueError("effect prompt asset hash mismatch")
    return value


def prompt_identity(kind):
    prompt = asset(kind + "-prompt.txt")
    return dict(
        version="b2-effects-v1" if kind == "b2" else LEAD_VERSION,
        sha256=digest(prompt),
        field_catalog_sha256=digest(asset(kind + "-fields.json")),
        effect_reference_identity=identity(),
    )


def build(full, *, kind):
    if kind == "b2":
        original = generate(full, "B2", battle_format="gen9ou")
        value = parse_json(original.user_json)
        source = parse_json(original.source_link_json)
        system = asset("b2-prompt.txt")
        candidate = "B2"
        selected = prompt_identity("b2")
    elif kind == "battle":
        from ..improved_io.battle_only_protocol import validate_context

        bp.check_fields(full, bp.catalog("v1.2.0"))
        validate_context(full)
        if full["identity"]["input_version"] != "calculator-input-v2":
            raise ValueError("effect battle input requires calculator-input-v2")
        value = full
        source = {}
        system = bp.assemble(version=BATTLE_VERSION)
        candidate = "B"
        selected = bp.identity(BATTLE_VERSION)
    elif kind == "lead":
        from ..team_preview import digest as input_digest

        unsigned = {**full, "identity": dict(full["identity"])}
        checksum = unsigned["identity"].pop("input_sha256")
        if (
            input_digest(unsigned) != checksum
            or full["battle_format"] != "gen9ou"
            or [p["lead_slot"] for p in full["self_team"]] != list(range(1, 7))
            or len(full["opponent_preview"]) != 6
        ):
            raise ValueError("effect lead original input identity mismatch")
        value = full
        source = {}
        system = asset("lead-prompt.txt")
        candidate = "team_preview"
        selected = prompt_identity("lead")
    else:
        raise ValueError("unknown effect delivery kind")
    wire = augment(value)
    guide = (
        bp.catalog(BATTLE_VERSION) if kind == "battle" else json.loads(asset(kind + "-fields.json"))
    )
    bp.check_fields(wire, guide)
    user = dumps(wire)
    link = {
        **source,
        "format_version": FORMAT_VERSION,
        "kind": kind,
        "candidate_version": candidate,
        "prompt_identity": selected,
        "effect_reference_identity": identity(),
        "identity": full["identity"],
        "original_user_sha256": digest(json.dumps(full, ensure_ascii=False, allow_nan=False)),
        "system_sha256": digest(system),
        "user_sha256": digest(user),
    }
    return Delivery(
        candidate,
        "team-preview-v1" if kind == "lead" else "calculator-input-v2",
        system,
        user,
        dumps(link),
    )


def validate(full, delivery, system, user, *, kind):
    expected = build(full, kind=kind)
    if delivery != expected or system != expected.system_prompt or user != expected.user_json:
        raise ValueError("effect delivery original/version/wire mismatch")
    return parse_json(expected.source_link_json)
