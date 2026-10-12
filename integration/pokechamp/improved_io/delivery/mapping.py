"""Validator-only field map from the preserved full catalog to each candidate."""

from __future__ import annotations

from .. import battle_prompts
from .exclusions import RAW, TOP


def catalog():
    guide = battle_prompts.catalog("v1.2.0")
    rows = []

    def visit(node, parts):
        node = battle_prompts.resolve(node, guide)
        path = ".".join(parts)
        rules = RAW if parts[0] == "RequestJSON" else TOP
        relative = tuple(parts[1:])
        removal = next(
            (reason for prefix, reason in rules.items() if relative[: len(prefix)] == prefix), None
        )
        b1 = "excluded_to_source_log" if removal else "retained"
        b2 = b3 = b1
        target = path
        if not removal:
            if path in ("$.calculation_bundle.entries", "$.calculation_bundle.entries.*"):
                target = path.replace("calculation_bundle.entries", "calculation_bundle.scenarios")
                b2 = "scenario_join container; scenario_id stays on row, other fields under result"
            elif path in ("$.calculation_bundle.coverage", "$.calculation_bundle.coverage.*"):
                target = path.replace("calculation_bundle.coverage", "calculation_bundle.scenarios")
                b2 = "scenario_join container; coverage fields stay directly on row"
            elif path.startswith("$.calculation_bundle.entries.*."):
                suffix = path.removeprefix("$.calculation_bundle.entries.*.")
                target = "$.calculation_bundle.scenarios.*." + (
                    "scenario_id" if suffix == "scenario_id" else "result." + suffix
                )
                b2 = "scenario_join; retained"
                if suffix in ("damage_rolls", "damage_range_hp"):
                    b2 += " or one-hop same_as_variant when exactly identical"
            elif path.startswith("$.calculation_bundle.coverage.*."):
                target = path.replace("calculation_bundle.coverage", "calculation_bundle.scenarios")
                b2 = "scenario_join; retained"
            if path.startswith("$.calculation_bundle.") and "string" in node["type"].split("|"):
                b2 += "; repeated >=80-character prose may use one-hop shared_text"
            b3 = b2
            if parts[0] == "RequestJSON":
                b3 = "request_base then deterministic request_delta; arrays replace atomically"
            elif path == "$.recent_events.*.protocol":
                b1 = b2 = "raw lines retained; only explicitly excluded RequestJSON fields removed"
                b3 = "lines: verbatim non-request strings; ordered request_base/request_delta"
                target = "$.recent_events.*.lines"
        rows.append(
            dict(
                source_path=path,
                validator_type=node["type"],
                validator_enum=node.get("enum"),
                B0="retained",
                B1=b1,
                B2=b2,
                B3=b3,
                target_path=target,
                exclusion_reason=removal,
            )
        )
        for key, child in node.get("properties", {}).items():
            visit(child, parts + (key,))
        if "keys" in node:
            visit(node["values"], parts + ("{" + node["keys"] + "}",))
        if "items" in node:
            visit(node["items"], parts + ("*",))

    for root, node in guide["roots"].items():
        visit(node, (root,))
    return dict(
        source_catalog_identity=battle_prompts.identity("v1.2.0"),
        notation="* is an array element; {name} is a validated dynamic key.",
        fields=rows,
        added_fields={
            "$.calculation_bundle.scenarios.*.calculation_target": (
                "incoming coverage target/switch; outgoing current observed opponent species"
            ),
            "$.calculation_bundle.scenarios.*.opponent_condition": (
                "exact hN-hpX ID parse; zero-based hypothesis index and modeled opponent HP"
            ),
            "$.calculation_bundle.shared_text": "literal common prose, no nested references",
            "$.recent_events.*.lines": "B3 ordered structural request codec and verbatim raw rows",
        },
    )
