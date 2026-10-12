"""D-036 qualified v2 repeat, retaining both immutable predecessor ledgers."""

from __future__ import annotations

import time
from pathlib import Path

from .. import benchmark as b
from . import battle_prompts
from . import experiment_policy as policy
from .battle_only_protocol import read_ref, ref
from .calcfix32 import ORIGINAL, ORIGINAL_PREPARED
from .calculator import expected_patch, expected_state_patch
from .receipts import source_identity

AUDIT = b.WORKSPACE_ROOT / "project_context/exec-plans/evidence/ep023"
PREVIOUS = b.WORKSPACE_ROOT / ".pokechamp-data/battle-guide-calcfix32/ex029"
QUALIFICATION = "calculator-input-audit-independent-regression-v1"
REQUIRED = {
    "ex030_independent_evidence",
    "ex030_replay636_evidence",
    "policy_runtime_delivery",
    "isolation_concurrency",
    "tamper_version_source_rejection",
    "integration_regression",
    "changed_file_static",
    "node_syntax",
    "source_config_teams_library_checks",
}


def runtime_identity():
    return dict(
        calculator_semantics_version="calculator-input-v2",
        runtime_patch_identity=expected_state_patch(),
    )


def verify_runtime(value, *, manifest=None, context=None, prompt_identity=None):
    if not policy.is_v2_repeat(value):
        raise ValueError("inputfix32 policy missing")
    expected = runtime_identity()
    if any(value.get(k) != v for k, v in expected.items()):
        raise ValueError("inputfix32 runtime identity mismatch")
    if manifest is not None:
        policy.same(value, manifest)
        if any(manifest.get(k) != v for k, v in expected.items()):
            raise ValueError("inputfix32 manifest runtime mismatch")
        if value.get("battle_prompt_identity") != manifest["battle_prompt_identity"]:
            raise ValueError("inputfix32 execution prompt mismatch")
    declared = prompt_identity or value.get("battle_prompt_identity")
    allowed = [battle_prompts.identity("v1.2.0")]
    if ((declared or {}).get("version") == "v1.3.0"
            and value.get("experiment_policy") in (policy.LEAD, policy.B2)):
        allowed.append(battle_prompts.identity("v1.3.0"))
    if (value.get("observation_backend") == "official-client-v1"
            and (declared or {}).get("version") == "v1.4.0"):
        allowed.append(battle_prompts.identity("v1.4.0"))
    if declared not in allowed:
        raise ValueError("inputfix32 requires sealed battle prompt v1.2.0")
    if context is not None:
        calc = context.get("calculation_bundle", {})
        if (
            context.get("identity", {}).get("input_version")
            != expected["calculator_semantics_version"]
            or context.get("current_observation", {}).get("calculator_semantics")
            != expected["calculator_semantics_version"]
            or calc.get("semantics_version") != expected["calculator_semantics_version"]
            or calc.get("runtime_patch") != expected["runtime_patch_identity"]
            or calc.get("engine_patch") != expected_patch()
        ):
            raise ValueError("inputfix32 actual calculator input/runtime mismatch")
    return expected


def verify_qualification(path, *, current=True):
    if path is None:
        raise ValueError("inputfix32 requires sealed independent verification")
    receipt = b.read_sealed(Path(path))
    if (
        receipt.get("qualification") != QUALIFICATION
        or receipt.get("passed") is not True
        or set(receipt.get("checks", {})) != REQUIRED
        or any(v is not True for v in receipt["checks"].values())
        or not receipt.get("evidence_files")
        or receipt.get("audit") != ref(AUDIT / "final-verification.json")
        or receipt.get("runtime_identity") != runtime_identity()
    ):
        raise ValueError("inputfix32 qualification incomplete")
    for name, checksum in receipt["evidence_files"].items():
        if b.digest(Path(name)) != checksum:
            raise ValueError("inputfix32 verification evidence drift")
    if current and receipt.get("source_files") != source_identity():
        raise ValueError("inputfix32 verified source drift")
    return receipt


def predecessor(directory, experiment_id, prepared):
    return dict(
        experiment_id=experiment_id,
        manifest=ref(prepared / "manifest.json"),
        study=ref(directory / "study.json"),
        first_clock=ref(directory / "cloud-clock.json"),
        report=ref(directory / "report-final/report.json"),
        ledger_files={
            str(p): b.digest(p) for p in sorted((directory / "requests").glob("*.json"))
        },
    )


def preparation_evidence(verification):
    verify_qualification(verification)
    return dict(
        **runtime_identity(),
        qualification=ref(verification),
        audit=ref(AUDIT / "final-verification.json"),
        original=predecessor(ORIGINAL, "EX-028", ORIGINAL_PREPARED),
        preceding=predecessor(PREVIOUS, "EX-029", PREVIOUS.with_name("ex029-prepared")),
    )


def validate_manifest(manifest, *, current=True):
    receipt = verify_qualification(manifest["qualification"]["path"], current=current)
    read_ref(manifest["qualification"])
    if receipt["source_files"] != manifest["source_files"]:
        raise ValueError("inputfix32 qualification source mismatch")
    verify_runtime(manifest)
    if manifest["audit"] != ref(AUDIT / "final-verification.json"):
        raise ValueError("inputfix32 audit identity mismatch")
    read_ref(manifest["audit"])
    for key, ex in (("original", "EX-028"), ("preceding", "EX-029")):
        prior = manifest[key]
        if prior["experiment_id"] != ex or not prior["ledger_files"]:
            raise ValueError("inputfix32 predecessor missing")
        for name in ("manifest", "study", "first_clock", "report"):
            read_ref(prior[name])
        for name, checksum in prior["ledger_files"].items():
            if b.digest(Path(name)) != checksum:
                raise ValueError("inputfix32 predecessor ledger drift")
    original = read_ref(manifest["original"]["manifest"])
    for key in (
        "compare_schedule",
        "reference",
        "prior_sha256",
        "calculation_identity",
    ):
        if manifest[key] != original[key]:
            raise ValueError(f"inputfix32 original {key} mismatch")
    if read_ref(manifest["config"]) != read_ref(original["config"]):
        raise ValueError("inputfix32 original config mismatch")
    reference = b.verify_plan(Path(original["reference"]["path"]).parent)
    if len(manifest["compare_schedule"]) != 32 or not reference["development_teams"]:
        raise ValueError("inputfix32 original cohort incomplete")


def cumulative_report(manifest, result):
    # Read each experiment's own usage, never EX-029's already cumulative view.
    previous = [read_ref(manifest[k]["report"]) for k in ("original", "preceding")]
    rows = previous + [result]
    return dict(
        original=manifest["original"],
        preceding=manifest["preceding"],
        audit=manifest["audit"],
        original_comparison_validity="invalidated_by_EX030_separate_analysis",
        independent_samples_pooled=False,
        usage_experiments_counted_once=["EX-028", "EX-029", "EX-031"],
        cumulative_usage={
            k: sum(r["usage"][k] for r in rows)
            for k in ("reserved_calls", "responses", "uncertain")
        },
        original_uncertain_requests=sum(r["usage"]["uncertain"] for r in previous),
        cumulative_confirmed_tokens={
            k: sum(r["confirmed_tokens"].get(k, 0) for r in rows)
            for k in set().union(*(r["confirmed_tokens"] for r in rows))
        },
        cumulative_collection_seconds=sum(r["batch_elapsed_seconds"] for r in rows),
        elapsed_since_original_first_cloud_seconds=time.time()
        - read_ref(manifest["original"]["first_clock"])["first_dispatch_at"],
    )
