"""Read saved damage audits; no calculator, battle, or model execution."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from integration.jev27b.study import file_hash
from integration.pokechamp.jev_battle import digest

VERSION = "jev-damage-viewer-v1"
CALLBACK = "window.__jevDamageLoaded(JSON.parse("
SUFFIX = "));\n"


def input_events(events):
    result = {}
    for event in events:
        if event.get("type") == "input":
            key = event["decision"]
            if key in result:
                raise ValueError("duplicate input decision: " + key)
            result[key] = event
    return result


def read_packet(source, experiment, entry):
    """The event's hash and payload identity bind this audit to this exact decision."""
    reference = entry.get("input_audit")
    packet = dict(version=VERSION, experiment=experiment, decision_id=entry["decision"],
                  input_audit=reference, damage=None)
    if not reference:
        return dict(packet, status="missing", reason="input_audit_not_recorded")
    source = Path(source).resolve()
    path = (source / reference["path"]).resolve()
    if not path.is_relative_to(source) or not path.is_file():
        raise ValueError("invalid damage audit path: " + reference["path"])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise ValueError("damage audit hash differs: " + entry["decision"])
    audit = json.loads(gzip.decompress(raw))
    if audit.get("live_result_sha256") != digest(entry["payload"]):
        raise ValueError("damage audit belongs to a different input: " + entry["decision"])
    damage = audit.get("damage")
    packet["damage"] = damage
    if damage is None:
        return dict(packet, status="missing", reason="damage_not_recorded")
    if (not isinstance(damage, dict) or damage.get("version") != "jev-damage-sample-v1"
            or not isinstance(damage.get("calculations"), list)):
        return dict(packet, status="unsupported_format", reason="unsupported_saved_damage_format")
    if damage.get("unchanged_reason"):
        return dict(packet, status="not_calculated", reason=damage["unchanged_reason"])
    return dict(packet, status="available", reason=None)


def script_text(packet):
    # Parse JSON rather than an object literal, retaining special keys as data.
    raw = json.dumps(packet, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    encoded = json.dumps(raw, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return CALLBACK + encoded + SUFFIX


def read_script(path):
    text = Path(path).read_text()
    if not text.startswith(CALLBACK) or not text.endswith(SUFFIX):
        raise ValueError("invalid damage local script envelope")
    return json.loads(json.loads(text[len(CALLBACK):-len(SUFFIX)]))


def descriptor(packet, ordinal):
    damage = packet["damage"]
    calculations = damage.get("calculations", []) if isinstance(damage, dict) else []
    return dict(src=f"damage/decision-{ordinal:04d}.js", status=packet["status"],
                reason=packet["reason"], calculations=len(calculations) if isinstance(calculations, list) else 0,
                input_audit=packet["input_audit"])


def export_battle(source, target, data, entries):
    target = Path(target)
    (target / "damage").mkdir()
    index = {}
    for ordinal, decision in enumerate(data["decisions"], 1):
        packet = read_packet(source, data["experiment"], entries[decision["id"]])
        reference = descriptor(packet, ordinal)
        path = target / reference["src"]
        path.write_text(script_text(packet))
        index[decision["id"]] = dict(reference, sha256=file_hash(path))
    data["damage_index"] = index


def verify_battle(source, target, data, entries):
    index = data["damage_index"]
    if set(index) != {d["id"] for d in data["decisions"]}:
        raise ValueError("damage decision coverage differs")
    count = 0
    for ordinal, decision in enumerate(data["decisions"], 1):
        expected = read_packet(source, data["experiment"], entries[decision["id"]])
        reference = descriptor(expected, ordinal)
        actual = index[decision["id"]]
        if {k: v for k, v in actual.items() if k != "sha256"} != reference:
            raise ValueError("damage audit link/count/status differs: " + decision["id"])
        path = Path(target) / reference["src"]
        if read_script(path) != expected or file_hash(path) != actual["sha256"]:
            raise ValueError("saved damage scenarios/conditions/results/order differ: " + decision["id"])
        count += reference["calculations"]
    return count
