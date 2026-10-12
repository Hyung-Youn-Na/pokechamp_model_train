"""Symmetric evaluation correction reuses intact responses and submits only unexecuted IDs."""

from __future__ import annotations

import copy
from pathlib import Path

from .. import benchmark as b
from ..execution import gate_parallel
from . import experiment_policy as policy
from .battle_only_protocol import PROFILE, read_ref, ref
from .output import parse_action
from .receipts import require_budget, source_identity


def reevaluate(row):
    """Derived assessment; original trace, payload, request intent and response remain unchanged."""
    request = row["context"]["request"]
    if row["trace"].get("response", {}).get("http_status") != 200 or row.get("category") not in (
        None,
        "output_contract",
    ):
        raise ValueError("provider failures or uncertain responses cannot be reevaluated as intact")
    parsed = parse_action(
        row["trace"]["raw_content"],
        request["legal_actions"],
        request_kind=request["kind"],
        can_tera=request["can_tera"],
        english_typography=True,
    )
    return dict(
        row,
        valid=True,
        category=None,
        corrected_evaluation=dict(
            original_valid=row["valid"],
            original_category=row["category"],
            action=parsed.action,
            source_files=source_identity(),
        ),
    )


def equivalent_inputs(old_scenes, manifest):
    current = {s["case"]: read_ref(s["input"]) for s in manifest["scenes"]}
    if set(old_scenes) != set(current):
        raise ValueError("evaluation correction changed input denominator")
    for key, original in old_scenes.items():
        old, new = copy.deepcopy(original), copy.deepcopy(current[key])
        # This measured calculator wall-time is provenance, not a treatment parameter.
        # The actual original value is retained in every resumed wire request.
        old["calculation_bundle"].pop("elapsed_ms", None)
        new["calculation_bundle"].pop("elapsed_ms", None)
        if old != new:
            raise ValueError("input/treatment drift cannot use evaluation-only recovery")
    return old_scenes


def register_evaluation_resume(root, record, prepared, analysis):
    from . import battle_only_budget as budget
    from .battle_only_gate import schedule

    if record["kind"] != "evaluation" or record["recollect"]:
        raise ValueError("evaluation resume cannot recollect completed calls")
    root = Path(root)
    with budget.locked(root):
        require_budget(budget.clock(root))
        if not (root / "halt-c0.json").exists():
            raise ValueError("original cohort must be halted before evaluation correction")
        collection = read_ref(record["collection"])
        inputs = read_ref(record["inputs"])
        original_dir = Path(record["collection"]["path"]).parent
        manifest = b.read_sealed(Path(prepared).parent / "manifest.json")
        old_manifest = b.read_sealed(Path(record["original"]["path"]).parent / "manifest.json")
        policy.same(manifest, old_manifest, inputs, collection, b.read_sealed(root / "study.json"))
        if gate_parallel(inputs) != gate_parallel(manifest):
            raise ValueError("evaluation resume cannot change concurrency")
        for key in ("prompt_sha256", "prior_sha256", "calculation_identity", "criteria"):
            old, new = old_manifest[key], manifest[key]
            if key == "criteria":
                old, new = old["sha256"], new["sha256"]
            if old != new:
                raise ValueError("evaluation resume cannot change treatment or rubric")
        equivalent_inputs(inputs["scenes"], manifest)
        submitted = {
            p.name.removeprefix("intent-").removesuffix(".json")
            for p in original_dir.glob("intent-action-*.json")
        }
        obtained = {name.removesuffix(".json") for name in collection["call_outputs"]}
        if submitted != obtained or collection["uncertain"]:
            raise ValueError("uncertain requests cannot be silently resubmitted")
        if set(record["symmetric_response_ids"]) != set(collection["call_outputs"]):
            raise ValueError("all collected responses need the same corrected evaluation")
        for name, digest in collection["call_outputs"].items():
            path = original_dir / name
            if b.digest(path) != digest:
                raise ValueError("intact response drift")
            reevaluate(b.read_sealed(path))
        remaining = [
            s["id"] for s in schedule(gate_parallel(inputs))
            if s["id"] not in submitted
        ]
        value = dict(
            record,
            **policy.selected(manifest),
            profile=PROFILE,
            resume_schedule=remaining,
            reused_ids=sorted(obtained),
            paid_recollection=False,
            clock=ref(root / "cloud-clock.json"),
            usage_before=budget.usage(root),
            analysis=ref(analysis),
        )
        target = root / "evaluation-e1.json"
        b.seal_json(target, value)
        b.seal_json(
            root / "cohorts/e1.json",
            dict(
                profile=PROFILE,
                **policy.selected(manifest),
                cohort="e1",
                prepared=ref(prepared),
                recovery=ref(target),
                source_files=source_identity(),
            ),
        )
        return value


def evaluation_inputs(root, prepared):
    record = b.read_sealed(Path(root) / "evaluation-e1.json")
    original = read_ref(record["inputs"])
    collection = read_ref(record["collection"])
    manifest = b.read_sealed(Path(prepared).parent / "manifest.json")
    scenes = equivalent_inputs(original["scenes"], manifest)
    directory = Path(record["collection"]["path"]).parent
    rows = []
    for name, digest in collection["call_outputs"].items():
        path = directory / name
        if b.digest(path) != digest:
            raise ValueError("original response drift")
        rows.append(dict(reevaluate(b.read_sealed(path)), original_response=ref(path)))
    return scenes, rows, record["inputs"]
