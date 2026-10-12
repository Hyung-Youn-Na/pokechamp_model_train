"""Offline B0–B3 delivery representations, separate from live prompt selection.

Full observations, priors, calculator semantics and recovery stay in their existing
modules. Nothing in this package calls a model, starts a battle or changes defaults.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .. import battle_prompts
from ..battle_only_protocol import validate_context
from . import calculations, exclusions, history, preservation

ASSETS = Path(__file__).parent
VERSIONS = ("B0", "B1", "B2", "B3")
FORMAT_VERSION = "b-delivery-v1"
CALCULATOR_VERSION = "calculator-input-v2"


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("nonfinite JSON value: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def validate_original(full, *, battle_format):
    """Always validate original content/hashes, never the lossy display projection."""
    if battle_format != "gen9ou":
        raise ValueError("delivery candidates require verified Gen9 OU singles scope")
    if full.get("identity", {}).get("input_version") != CALCULATOR_VERSION:
        raise ValueError("delivery version does not replace required calculator-input-v2")
    if "battle_summary" not in full or full["battle_summary"] is not None:
        raise ValueError("unexpected or missing battle memory")
    dumps(full)  # Reject nonfinite values before any hashing or projection.
    for event in full.get("recent_events", []):
        for line in event.get("protocol", "").splitlines():
            if line.startswith("|request|") and line[9:].strip():
                parse_json(line[9:])  # Embedded duplicate keys must not disappear.
    # Closed paths/types/enums also cover every historical embedded RequestJSON.
    battle_prompts.check_fields(full, battle_prompts.catalog("v1.2.0"))
    validate_context(full)
    # Scope checks apply to B0 too, without removing or mutating any source field.
    exclusions.prune(full)


def system_prompt(version):
    if version not in VERSIONS:
        raise ValueError("unsupported offline delivery candidate")
    provenance = parse_json((ASSETS / "provenance.json").read_text())
    for name, expected in provenance["assets"].items():
        if digest((ASSETS / name).read_text()) != expected:
            raise ValueError("delivery prompt asset hash mismatch")
    baseline = (ASSETS / "B0.txt").read_text()
    if digest(baseline) != battle_prompts.identity("v1.2.0")["prompt_sha256"]:
        raise ValueError("B0 no longer matches preserved battle-v1.2.0")
    if version == "B0":
        result = baseline
    elif version == "B1":
        result = (
            exclusions.policy() + "\n---\n\n" + battle_prompts.render(exclusions.filtered_catalog())
        )
    else:
        result = exclusions.policy() + "\n---\n\n" + (ASSETS / "guide.txt").read_text()
        if version == "B3":
            result += (ASSETS / "history-guide.txt").read_text()
    if digest(result) != provenance["system_prompts"][version]:
        raise ValueError("delivery assembled prompt hash mismatch")
    return result


@dataclass(frozen=True)
class Delivery:
    candidate_version: str
    calculator_semantics_version: str
    system_prompt: str
    user_json: str
    source_link_json: str

    def as_dict(self):
        return asdict(self)


def _generate_validated(full, version, *, battle_format, origin):
    prompt = system_prompt(version)
    if version == "B0":
        value, excluded = copy.deepcopy(full), []
    else:
        value, excluded = exclusions.prune(full)
        if version in ("B2", "B3"):
            value["calculation_bundle"] = calculations.encode(
                value["calculation_bundle"],
                value["current_observation"],
                value["opponent_hypotheses"],
            )
        if version == "B3":
            value["recent_events"] = history.encode(value["recent_events"])
    # B0/B1 retain the original serializer: B2 starts compact structural encoding.
    original_user = json.dumps(full, ensure_ascii=False, allow_nan=False)
    user = (
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        if version in ("B0", "B1")
        else dumps(value)
    )
    link = dict(
        format_version=FORMAT_VERSION,
        candidate_version=version,
        calculator_semantics_version=CALCULATOR_VERSION,
        battle_format=battle_format,
        identity=copy.deepcopy(full["identity"]),
        origin=copy.deepcopy(origin),
        original_user_sha256=digest(original_user),
        original_system_sha256=battle_prompts.identity("v1.2.0")["prompt_sha256"],
        system_sha256=digest(prompt),
        user_sha256=digest(user),
        exclusions=excluded,
    )
    return Delivery(version, CALCULATOR_VERSION, prompt, user, dumps(link))


def generate(full, version, *, battle_format, origin=None):
    """Full validated input + candidate → system/user strings + original linkage."""
    validate_original(full, battle_format=battle_format)
    return _generate_validated(full, version, battle_format=battle_format, origin=origin)


def generate_all(full, *, battle_format, origin=None):
    """One original validation for a reproducible paired B0–B3 offline comparison."""
    validate_original(full, battle_format=battle_format)
    return {
        version: _generate_validated(full, version, battle_format=battle_format, origin=origin)
        for version in VERSIONS
    }


def restore_projection(delivery):
    """Recover B1's full structure from B2/B3; B1 exclusions stay in the source log."""
    if (
        delivery.candidate_version not in VERSIONS
        or delivery.calculator_semantics_version != CALCULATOR_VERSION
    ):
        raise ValueError("delivery candidate or calculator semantics mismatch")
    value = parse_json(delivery.user_json)
    if delivery.candidate_version == "B3":
        value["recent_events"] = history.decode(value["recent_events"])
    if delivery.candidate_version in ("B2", "B3"):
        value["calculation_bundle"] = calculations.decode(value["calculation_bundle"])
    return value


def validate_delivery(full, delivery, *, battle_format, origin=None):
    """Original gates first, then exact generated strings/versions/references.

    Recomputing a hash over a tampered display is insufficient to pass this gate.
    """
    expected = generate(
        full, delivery.candidate_version, battle_format=battle_format, origin=origin
    )
    if delivery != expected:
        raise ValueError("delivery strings, version or original linkage mismatch")
    restored = restore_projection(delivery)
    preservation.check_source(full, restored, parse_json(delivery.source_link_json)["exclusions"])
    return delivery


def capture_request(full, delivery, *, battle_format, origin=None):
    """Serialize and capture the final offline request, with no network transport.

    A future live adapter must call this validation boundary before provider IO.
    This intentionally does not add candidates to FixedBackend/live CLI selection.
    """
    validate_delivery(full, delivery, battle_format=battle_format, origin=origin)
    payload = dict(
        messages=[
            dict(role="system", content=delivery.system_prompt),
            dict(role="user", content=delivery.user_json),
        ]
    )
    wire = dumps(payload).encode("utf-8")
    captured = parse_json(wire.decode("utf-8"))
    if captured != payload:
        raise ValueError("offline request serialization mismatch")
    return dict(
        wire_sha256=hashlib.sha256(wire).hexdigest(),
        wire_utf8_bytes=len(wire),
        payload=captured,
        candidate_version=delivery.candidate_version,
        calculator_semantics_version=delivery.calculator_semantics_version,
        source_link=parse_json(delivery.source_link_json),
    )
