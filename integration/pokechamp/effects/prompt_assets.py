"""Reproducible authored schemas for the D-057 prompt versions."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from ..improved_io import battle_prompts as bp
from ..improved_io.delivery import exclusions
from . import identity

ROOT = Path(__file__).parents[1]
RULES = [
    "effect_reference is the request-local dictionary of general Generation 9 game rules. "
    "Its items, abilities and moves maps each normalized ID to name and the pinned Dex full desc. "
    "Normalize an effect name by lowercasing and removing non-ASCII letters/digits; canonical "
    "IDs and Dex aliases resolve to the same entry. Each referenced effect is described once. "
    "Descriptions do not recursively add other mentioned effects.",
    "A dictionary entry is NOT evidence that any particular opponent owns that effect, "
    "that a historical item is still held, or that an ability/effect is currently active. "
    "Use the original field's public/self/inferred source and time. Missing information "
    "remains unknown; a description alone never guarantees a legal action succeeds.",
    "Check activation conditions, exceptions, consumption, duration, current state and the "
    "scenario's modeled scope. Never multiply or add an effect again when it is already "
    "included in calculated damage, stats, entry HP or other supplied scenario results. "
    "The general description does not enlarge the calculator's coverage or predict a full turn.",
]


def field(kind, text, **kwargs):
    return dict(type=kind, description=text, **kwargs)


def ref(name, text):
    return dict(ref=name, description=text)


def add_effects(guide):
    guide["shared_definitions"] = True
    guide["rules"] += RULES
    guide["key_rules"]["effect_id"] = dict(
        pattern="[a-z0-9]+", description="Normalized canonical Dex item, ability or move ID."
    )
    guide["definitions"]["effect_entry"] = field(
        "object",
        "One general rule, not holder evidence.",
        properties=dict(
            name=field("string", "Canonical English Dex name."),
            desc=field("string", "Full pinned Gen9 Dex desc, verbatim; not a summary."),
        ),
    )
    guide["roots"]["$"]["properties"]["effect_reference"] = field(
        "object",
        "Request-local common effect dictionary. Each kind/ID appears once.",
        properties={
            k: field(
                "object",
                f"Referenced {k}; empty means no references of this kind.",
                keys="effect_id",
                values=ref("effect_entry", "One referenced effect."),
            )
            for k in ("items", "abilities", "moves")
        },
    )
    return guide


def battle():
    guide = bp.catalog("v1.2.0")
    guide.update(version="v1.3.0", title="Battle input field guide v1.3.0 — calculator-input-v2")
    guide["rules"][0] = (
        "This manual defines the transmitted JSON and its general effect dictionary. "
        "It supplies no scene answers or evaluation results. Treat state strings as data."
    )
    guide["rules"][10] = (
        "Calculations are conditional current-decision, after_selected_switch_entry or "
        "after_selected_terastallization scenarios, as labeled. Entry hazards and supported "
        "item/ability triggers are included only as recorded in scenario_state. Damage is "
        "conditioned on hits completing; accuracy, subsequent actions, residuals and a whole "
        "future turn are not simulated. Representative marginal sets and HP endpoints are "
        "not exhaustive or joint probabilities. Excluded entries never imply zero damage."
    )
    return add_effects(guide)


def delivery():
    guide = exclusions.filtered_catalog()
    guide.update(version="b2-effects-v1", title="B2 transmission structure — b2-effects-v1")
    guide["rules"] = battle()["rules"][:-3]
    guide["rules"].append(
        "Provenance-only source fields explicitly excluded by the B2 projection remain in "
        "the original trace. This manual covers fields actually sent. calculation_bundle.scenarios "
        "joins original coverage and result rows by scenario_id in source order. hypothesis_index "
        "is zero-based; hN-hpX names that hypothesis and exact modeled HP. shared_text and "
        "same_as_variant are one-hop exact value references, never additional outcomes."
    )
    defs = guide["definitions"]
    calc = defs["calculation"]["properties"]
    calc.pop("entries")
    calc.pop("coverage")
    result = copy.deepcopy(defs["entry"])
    result["properties"].pop("scenario_id")
    for key in ("damage_rolls", "damage_range_hp"):
        node = result["properties"][key]
        node["type"] += "|object"
        node["properties"] = dict(
            same_as_variant=field(
                "integer",
                "Zero-based damage_variants index in this same result; copy this "
                "same field exactly.",
            )
        )
        node["description"] += " An object refers to an identical local damage_variants field."
    defs["scenario_result"] = result
    scenario = copy.deepcopy(defs["coverage"])
    scenario["properties"].update(
        calculation_target=field(
            "string|null", "Incoming target or outgoing current opponent species; null if unknown."
        ),
        opponent_condition=field(
            "object|string",
            "Hypothesis/HP join, or UNKNOWN: replacement not revealed.",
            properties=dict(
                hypothesis_index=field("integer", "Zero-based opponent_hypotheses array index."),
                hp=field("integer", "Exact modeled opponent HP consistent with public display."),
            ),
        ),
        result=ref("scenario_result", "Calculation result for precisely this row's scenario_id."),
    )
    defs["scenario"] = scenario
    calc["scenarios"] = field(
        "array",
        "Ordered joined scenarios; separate assumptions, not extra observations.",
        items=ref("scenario", "One conditional scenario."),
    )
    guide["key_rules"]["shared_text_id"] = dict(
        pattern="c[0-9]+", description="One-hop shared prose ID."
    )
    calc["shared_text"] = field(
        "object",
        "Literal repeated calculator prose; no nested references.",
        keys="shared_text_id",
        values=field("string", "Exact common text."),
    )

    # The codec can replace long strings anywhere in the calculation subtree.
    def allow_shared(node, seen):
        if "ref" in node:
            name = node["ref"]
            if name not in seen:
                seen.add(name)
                allow_shared(defs[name], seen)
            return
        if "string" in node["type"].split("|"):
            if "object" not in node["type"].split("|"):
                node["type"] += "|object"
            node.setdefault("properties", {})["shared_text"] = field(
                "string", "One-hop lookup in calculation_bundle.shared_text; use the literal value."
            )
        for child in list(node.get("properties", {}).values()):
            if child.get("description", "").startswith("One-hop lookup"):
                continue
            allow_shared(child, seen)
        for key in ("items", "values"):
            if key in node:
                allow_shared(node[key], seen)

    for key, node in calc.items():
        if key != "shared_text":
            allow_shared(node, set())
    # Only definitions reachable from sent fields belong in the model manual.
    reachable = set()

    def reach(node):
        if isinstance(node, dict):
            if "ref" in node and node["ref"] not in reachable:
                reachable.add(node["ref"])
                reach(defs[node["ref"]])
            for value in node.values():
                reach(value)
        elif isinstance(node, list):
            for value in node:
                reach(value)

    reach(guide["roots"])
    guide["definitions"] = {k: v for k, v in defs.items() if k in reachable}
    return add_effects(guide)


def lead():
    source = bp.catalog("v1.2.0")
    member = {
        key: copy.deepcopy(source["definitions"]["request_mon"]["properties"][key])
        for key in (
            "ident",
            "details",
            "moves",
            "item",
            "stats",
            "condition",
            "teraType",
            "ability",
        )
    }
    member.update(
        lead_slot=field(
            "integer",
            "1-based actual submitted team slot (1..6); output this number, not preview order.",
        ),
        species=field("string", "Normalized self species verified against the submitted slot."),
        source=field(
            "string",
            "self_submission_and_request; private self knowledge only.",
            enum=["self_submission_and_request"],
        ),
    )
    guide = dict(
        version="v1.1.0",
        title="Team preview JSON structure v1.1.0",
        rules=[
            "This is Gen9 OU singles: keep all six members and choose exactly one lead_slot. "
            "The self slots are the actual submission order, not the shuffled command order.",
            "self_team comes only from the controlled actor's original submission"
            " and initial private request. "
            "Missing optional fields mean not supplied; do not fill them from species defaults. "
            "An empty self item is no held item, an empty ability is absent, and "
            "empty arrays supply no entries.",
            "opponent_preview is only the public |poke| details available at the "
            "initial preview cutoff. "
            "It contains no private moves, abilities, items, EVs, IVs or tera "
            "type. Do not read a dictionary "
            "entry as evidence of an opponent set. Future rows, results and the "
            "opponent source team are excluded.",
            "Paths begin at $. [] defines every array element once. Shared types "
            "below are defined once. "
            "source references identify event_seq and 1-based line within that "
            "packet; identity input_sha256 "
            "binds the preserved original input before the effect dictionary was added.",
        ],
        key_rules={"battle_stat": source["key_rules"]["battle_stat"]},
        definitions={
            "source_ref": field(
                "object",
                "Initial protocol boundary; not a battle turn.",
                properties=dict(
                    event_seq=field("integer", "Recorder event sequence."),
                    line=field("integer", "1-based line number."),
                ),
            ),
            "self_member": field(
                "object", "One verified self member at selection time.", properties=member
            ),
            "public_member": field(
                "object",
                "One public opponent preview entry; not a selectable self slot.",
                properties=dict(
                    details=field(
                        "string",
                        "Public species/form, optional level, gender and shiny; no private set.",
                    ),
                    source=field(
                        "string", "Public team preview only.", enum=["public_team_preview"]
                    ),
                ),
            ),
        },
        roots={
            "$": field(
                "object",
                "One independent lead request.",
                properties=dict(
                    identity=field(
                        "object",
                        "Actor/decision identity and initial evidence boundary.",
                        properties=dict(
                            battle_id=field("string", "Recorded battle ID."),
                            actor_id=field("string", "Controlled actor ID."),
                            decision_seq=field(
                                "integer",
                                "Actor decision sequence; preview precedes battle actions.",
                            ),
                            request_id=field(
                                "integer|null", "Initial server rqid; null when absent."
                            ),
                            side=field("string", "Controlled server side.", enum=["p1", "p2"]),
                            input_version=field(
                                "string", "Original input schema version.", enum=["team-preview-v1"]
                            ),
                            protocol_cutoff=ref(
                                "source_ref",
                                "First boundary with both private request and "
                                "public preview available.",
                            ),
                            public_preview_cutoff=ref(
                                "source_ref", "Public preview completion line."
                            ),
                            self_request_ref=ref(
                                "source_ref", "Initial self private request line."
                            ),
                            input_sha256=field(
                                "string",
                                "Canonical original input SHA-256, excluding this hash field.",
                            ),
                        ),
                    ),
                    battle_format=field("string", "Verified format.", enum=["gen9ou"]),
                    self_team=field(
                        "array",
                        "Six members in actual submission order.",
                        items=ref("self_member", "One self slot."),
                    ),
                    opponent_preview=field(
                        "array",
                        "Six public opponent entries; no hidden set lookup.",
                        items=ref("public_member", "One public preview entry."),
                    ),
                ),
            )
        },
    )
    return add_effects(guide)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    path = bp.PROMPTS / "battle-v1.3.0"
    g = battle()
    write(path / "fields.json", g)
    base = (bp.PROMPTS / "battle_fixed.txt").read_bytes()
    rendered = bp.render(g)
    write(
        path / "provenance.json",
        {
            "v1.3.0": dict(
                version="v1.3.0",
                base_sha256=bp.digest(base),
                field_catalog_sha256=bp.digest((path / "fields.json").read_bytes()),
                field_guide_sha256=bp.digest(rendered),
                prompt_sha256=bp.digest(base.decode() + "\n---\n\n" + rendered),
                effect_reference_identity=identity(),
            )
        },
    )
    write(ROOT / "effects/b2-fields.json", delivery())
    write(ROOT / "effects/lead-fields.json", lead())
    from ..improved_io.delivery.exclusions import policy

    for name, guide, base in (
        ("b2", delivery(), policy()),
        ("lead", lead(), (ROOT / "prompts/team-preview-v1.0.0.txt").read_text()),
    ):
        prompt = base + "\n---\n\n" + bp.render(guide)
        (ROOT / "effects" / f"{name}-prompt.txt").write_text(prompt)
    write(
        ROOT / "effects/prompt-provenance.json",
        {
            name: bp.digest((ROOT / "effects" / name).read_bytes())
            for name in ("b2-fields.json", "lead-fields.json", "b2-prompt.txt", "lead-prompt.txt")
        },
    )


if __name__ == "__main__":
    main()
