"""Versioned field guide, closed path coverage and shared prompt assembly."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PROMPTS = Path(__file__).with_name("prompts")
VERSIONS = ("v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0", "v1.4.0")
DEFAULT_VERSION = "v1.3.0"
GUIDE = PROMPTS / "battle-v1.3.0" / "fields.json"


class FieldCoverageError(ValueError):
    """Safe path-only diagnostics retained even when a worker rejects before HTTP."""

    category = "input_contract"

    def __init__(self, paths):
        self.paths = paths
        super().__init__("battle field coverage failed:\n" + "\n".join(paths))


def digest(content):
    return hashlib.sha256(
        content.encode() if isinstance(content, str) else content
    ).hexdigest()


def guide_path(version=DEFAULT_VERSION):
    return (
        GUIDE
        if version == DEFAULT_VERSION
        else PROMPTS / f"battle-{version}" / "fields.json"
    )


def catalog(version=DEFAULT_VERSION):
    return json.loads(guide_path(version).read_text())


def resolve(node, guide):
    if "ref" not in node:
        return node
    target = guide["definitions"][node["ref"]]
    return {
        **target,
        "description": node["description"] + " " + target["description"],
        "type": target["type"] + ("|null" if node.get("nullable") else ""),
    }


def render(guide=None):
    """The JSON catalog is the sole authored manual; preserve its insertion order."""
    guide = catalog() if guide is None else guide
    lines = [guide["title"], "", *guide["rules"], "", "Key rules"]
    for name, rule in guide["key_rules"].items():
        lines.append(f"{{{name}}}: {rule['description']}")
        if "allowed" in rule:
            lines.append("Allowed keys: " + ", ".join(rule["allowed"]) + ".")

    def visit(node, path):
        if guide.get("shared_definitions") and "ref" in node:
            target = guide["definitions"][node["ref"]]
            nullable = "|null" if node.get("nullable") else ""
            lines.append(f"{path} [{target['type']}{nullable}; see {node['ref']}]: "
                         + node["description"])
            return
        node = resolve(node, guide)
        if not node.get("description", "").strip():
            raise ValueError(f"missing field description: {path}")
        description = node["description"]
        if "enum" in node:
            description += " Allowed values: " + json.dumps(node["enum"]) + "."
        lines.append(f"{path} [{node['type']}]: {description}")
        for key, child in node.get("properties", {}).items():
            visit(child, path + "." + key)
        if "keys" in node:
            visit(node["values"], path + ".{" + node["keys"] + "}")
        if "items" in node:
            visit(node["items"], path + "[]")

    for path, node in guide["roots"].items():
        lines.extend(["", "Field paths: " + path])
        visit(node, path)
    if guide.get("shared_definitions"):
        for name, node in guide["definitions"].items():
            lines.extend(["", "Shared type: " + name])
            visit(node, name)
    return "\n".join(lines) + "\n"


def check_fields(context, guide=None):
    """Report every undocumented/type-invalid path, including embedded request JSON.

    This is coverage/type validation, not a substitute for the existing identity,
    phase, calculator and legal-action contracts. Nothing is removed from input.
    """
    guide = catalog() if guide is None else guide
    errors = []

    def visit(value, node, path):
        node = resolve(node, guide)
        if not node.get("description", "").strip():
            errors.append(path + " (missing description)")
        actual = (
            "null"
            if value is None
            else "boolean"
            if isinstance(value, bool)
            else "integer"
            if isinstance(value, int)
            else "number"
            if isinstance(value, float)
            else "string"
            if isinstance(value, str)
            else "array"
            if isinstance(value, list)
            else "object"
            if isinstance(value, dict)
            else "unsupported"
        )
        allowed = node["type"].split("|")
        if actual not in allowed and not (actual == "integer" and "number" in allowed):
            errors.append(f"{path} (expected {node['type']}, got {actual})")
            return
        if "enum" in node and value not in node["enum"]:
            errors.append(path + " (undocumented value)")
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = path + "." + key
                schema = node.get("properties", {}).get(key)
                if schema is None and "keys" in node:
                    rule = guide["key_rules"][node["keys"]]
                    matched = (
                        key in rule["allowed"]
                        if "allowed" in rule
                        else re.fullmatch(rule["pattern"], key) is not None
                    )
                    if matched:
                        schema = node["values"]
                if schema is None:
                    errors.append(child_path + " (undocumented field)")
                else:
                    visit(child, schema, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                if "items" not in node:
                    errors.append(f"{path}[{index}] (undocumented array element)")
                else:
                    visit(child, node["items"], f"{path}[{index}]")

    visit(context, guide["roots"]["$"], "$")
    events = context.get("recent_events", []) if isinstance(context, dict) else []
    for index, event in enumerate(events if isinstance(events, list) else []):
        if not isinstance(event, dict) or not isinstance(event.get("protocol"), str):
            continue  # Already reported by the recursive checker.
        for line_number, line in enumerate(event["protocol"].splitlines(), 1):
            if not line.startswith("|request|") or not line[9:]:
                continue
            path = f"$.recent_events[{index}].protocol:line{line_number}.RequestJSON"
            try:
                request = json.loads(line[9:])
            except ValueError:
                errors.append(path + " (invalid request JSON)")
            else:
                visit(request, guide["roots"]["RequestJSON"], path)
    if errors:
        raise FieldCoverageError(errors)


def identity(version="v1.0.0"):
    if version not in VERSIONS:
        raise ValueError("unsupported battle prompt version")
    base = (PROMPTS / "battle_fixed.txt").read_bytes()
    guide = render(catalog(version)) if version != "v1.0.0" else None
    prompt = base.decode() + ("\n---\n\n" + guide if guide else "")
    value = dict(
        version=version,
        base_sha256=digest(base),
        field_catalog_sha256=digest(guide_path(version).read_bytes())
        if guide
        else None,
        field_guide_sha256=digest(guide) if guide else None,
        prompt_sha256=digest(prompt),
    )
    if version in ("v1.3.0", "v1.4.0"):
        from ..effects import identity as effect_identity

        value["effect_reference_identity"] = effect_identity()
    if version == "v1.0.0":
        original = json.loads((PROMPTS / "provenance.json").read_text())
        if value["base_sha256"] != original["files"]["battle_fixed.txt"]:
            raise ValueError("battle prompt asset/hash mismatch")
        return value
    provenance = json.loads(
        (guide_path(version).parent / "provenance.json").read_text()
    )
    if value != provenance[version]:
        raise ValueError("battle prompt asset/hash mismatch")
    return value


def selected(config):
    """Keep absent historical selection at v1.0.0; seal explicit new versions."""
    config = config or {}
    version = config.get("battle_prompt_version", "v1.0.0")
    expected = identity(version)
    declared = config.get("battle_prompt_identity")
    if (version != "v1.0.0" and declared is None) or (
        declared is not None and declared != expected
    ):
        raise ValueError("battle prompt selection/identity mismatch")
    return expected


def selection(version=DEFAULT_VERSION):
    return dict(battle_prompt_version=version, battle_prompt_identity=identity(version))


def assemble(context=None, *, version="v1.0.0", declared=None):
    actual = identity(version)
    if declared is not None and declared != actual:
        raise ValueError("battle prompt request identity mismatch")
    base = (PROMPTS / "battle_fixed.txt").read_text()
    if version != "v1.0.0":
        guide = catalog(version)
        if context is not None:
            check_fields(context, guide)
        return base + "\n---\n\n" + render(guide)
    return base


def sizes(context, version=DEFAULT_VERSION):
    old, new = assemble(version="v1.0.0"), assemble(context, version=version)
    user = json.dumps(context, ensure_ascii=False)
    if version in ("v1.3.0", "v1.4.0"):
        if version == "v1.4.0":
            from ..observation.delivery import build
        else:
            from ..effects.delivery import build

        user = build(context, kind="battle").user_json
    return dict(
        system_chars=len(new),
        system_bytes=len(new.encode()),
        added_chars=len(new) - len(old),
        added_bytes=len(new.encode()) - len(old.encode()),
        user_chars=len(user),
        user_bytes=len(user.encode()),
        total_chars=len(new) + len(user),
        total_bytes=len(new.encode()) + len(user.encode()),
    )
