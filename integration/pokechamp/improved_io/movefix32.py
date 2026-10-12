"""D-038 repeat qualified by immutable EP-025 baseline plus explicit wiring delta."""

from __future__ import annotations

import time
from pathlib import Path

from .. import benchmark as b
from . import experiment_policy as policy
from .battle_only_protocol import read_ref, ref
from .inputfix32 import (
    ORIGINAL,
    ORIGINAL_PREPARED,
    PREVIOUS,
    predecessor,
    runtime_identity,
    verify_runtime,
)
from .receipts import source_identity

BASELINE = b.WORKSPACE_ROOT / "project_context/exec-plans/evidence/ep025"
INPUTFIX_RUN = b.WORKSPACE_ROOT / ".pokechamp-data/battle-guide-inputfix32/ex031"
MOVEFIX_RUN = b.WORKSPACE_ROOT / ".pokechamp-data/battle-guide-movefix32/ex032"
REPEAT_AUTHORIZATION = (
    b.WORKSPACE_ROOT / "project_context/exec-plans/evidence/ep027/authorization.json"
)
QUALIFICATION = "calculator-move-name-independent-regression-v1"
REQUIRED = {
    "baseline_seals_source_match",
    "old_policy_hashes_preserved",
    "policy_runtime_delivery",
    "tamper_version_source_rejection",
    "schedule_config_isolation",
    "predecessor_usage_once",
    "changed_file_static",
    "final_source_manifest_integrity",
}


def verify_qualification(path, *, current=True):
    if path is None:
        raise ValueError("movefix32 requires sealed baseline and delta verification")
    receipt = b.read_sealed(Path(path))
    baseline = b.read_sealed(BASELINE / "final-verification.json")
    if (
        receipt.get("qualification") != QUALIFICATION
        or receipt.get("passed") is not True
        or set(receipt.get("checks", {})) != REQUIRED
        or any(v is not True for v in receipt["checks"].values())
        or not receipt.get("evidence_files")
        or receipt.get("baseline") != ref(BASELINE / "final-verification.json")
        or receipt.get("baseline_source_files") != baseline["source_files"]
        or receipt.get("runtime_identity") != runtime_identity()
        or receipt.get("verification_scope") != "baseline_plus_wiring_delta"
        or receipt.get("full_final_source_regression_rerun") is not False
    ):
        raise ValueError("movefix32 qualification incomplete")
    for name, checksum in receipt["evidence_files"].items():
        if b.digest(Path(name)) != checksum:
            raise ValueError("movefix32 verification evidence drift")
    for name, checksum in baseline["files"].items():
        if b.digest(BASELINE / name) != checksum:
            raise ValueError("movefix32 baseline evidence drift")
    sources = receipt["source_files"]
    delta = {
        name: dict(before=baseline["source_files"].get(name), after=checksum)
        for name, checksum in sources.items()
        if baseline["source_files"].get(name) != checksum
    }
    if (
        not set(baseline["source_files"]) <= set(sources)
        or receipt.get("source_delta") != delta
    ):
        raise ValueError("movefix32 baseline delta mismatch")
    if current and sources != source_identity():
        raise ValueError("movefix32 verified source drift")
    return receipt


def preparation_evidence(verification, *, selection=None):
    verify_qualification(verification)
    repeat = {}
    if policy.is_external_repeat(selection or {}):
        repeat = dict(
            movefix=predecessor(
                MOVEFIX_RUN, "EX-032", MOVEFIX_RUN.with_name("ex032-prepared")
            ),
            repeat_authorization=ref(REPEAT_AUTHORIZATION),
        )
    return dict(
        **repeat,
        **runtime_identity(),
        qualification=ref(verification),
        bugfix_verification=ref(BASELINE / "final-verification.json"),
        original=predecessor(ORIGINAL, "EX-028", ORIGINAL_PREPARED),
        preceding=predecessor(PREVIOUS, "EX-029", PREVIOUS.with_name("ex029-prepared")),
        inputfix=predecessor(
            INPUTFIX_RUN, "EX-031", INPUTFIX_RUN.with_name("ex031-prepared")
        ),
    )


def validate_manifest(manifest, *, current=True):
    if not policy.is_movefix(manifest):
        raise ValueError("movefix32 policy missing")
    receipt = verify_qualification(manifest["qualification"]["path"], current=current)
    read_ref(manifest["qualification"])
    if receipt["source_files"] != manifest["source_files"]:
        raise ValueError("movefix32 qualification source mismatch")
    verify_runtime(manifest)
    if manifest["bugfix_verification"] != ref(BASELINE / "final-verification.json"):
        raise ValueError("movefix32 bugfix identity mismatch")
    read_ref(manifest["bugfix_verification"])
    ledgers = set()
    predecessors = [("original", "EX-028"), ("preceding", "EX-029"), ("inputfix", "EX-031")]
    if policy.is_external_repeat(manifest):
        predecessors.append(("movefix", "EX-032"))
        authorization = read_ref(manifest["repeat_authorization"])
        previous = read_ref(manifest["movefix"]["manifest"])
        if (
            manifest["repeat_authorization"] != ref(REPEAT_AUTHORIZATION)
            or authorization.get("decision") != "D-039"
            or authorization.get("experiment_id") != "EX-033"
            or authorization.get("user_authorized") is not True
            or authorization.get("repeat_scope") != "fresh_all_32_same_conditions_once"
            or authorization.get("environment_recovered_reported_by_user") is not True
            or authorization.get("external_cause_independently_confirmed") is not False
            or authorization.get("reason") != "external_host_memory_pressure_reported_by_user"
            or authorization.get("permit_timeout_changed") is not False
            or authorization.get("provider_retry") != 0
            or authorization.get("additional_recollection") != 0
            or authorization.get("source_before") != previous["source_files"]
            or authorization.get("previous_report") != manifest["movefix"]["report"]
            or authorization.get("previous_halt") != ref(MOVEFIX_RUN / "halt-c0.json")
        ):
            raise ValueError("external repeat authorization or predecessor mismatch")
        read_ref(authorization["previous_halt"])
        for key in (
            "compare_schedule", "reference", "prior_sha256", "calculation_identity",
            "battle_prompt_identity", "calculator_semantics_version", "runtime_patch_identity",
        ):
            if manifest[key] != previous[key]:
                raise ValueError(f"external repeat previous {key} mismatch")
        if read_ref(manifest["config"]) != read_ref(previous["config"]):
            raise ValueError("external repeat previous config mismatch")
    for key, ex in predecessors:
        prior = manifest[key]
        if prior["experiment_id"] != ex or not prior["ledger_files"]:
            raise ValueError("movefix32 predecessor missing")
        for name in ("manifest", "study", "first_clock", "report"):
            read_ref(prior[name])
        for name, checksum in prior["ledger_files"].items():
            if name in ledgers or b.digest(Path(name)) != checksum:
                raise ValueError("movefix32 predecessor ledger drift or duplicate")
            ledgers.add(name)
    original = read_ref(manifest["original"]["manifest"])
    for key in ("compare_schedule", "reference", "prior_sha256", "calculation_identity"):
        if manifest[key] != original[key]:
            raise ValueError(f"movefix32 original {key} mismatch")
    if read_ref(manifest["config"]) != read_ref(original["config"]):
        raise ValueError("movefix32 original config mismatch")
    if len(manifest["compare_schedule"]) != 32:
        raise ValueError("movefix32 original cohort incomplete")


def cumulative_report(manifest, result):
    keys = ["original", "preceding", "inputfix"]
    experiments = ["EX-028", "EX-029", "EX-031", "EX-032"]
    references = [*keys, "bugfix_verification"]
    if policy.is_external_repeat(manifest):
        keys.append("movefix")
        experiments.append("EX-033")
        references.extend(("movefix", "repeat_authorization"))
    previous = [read_ref(manifest[k]["report"]) for k in keys]
    rows = previous + [result]
    return dict(
        **{k: manifest[k] for k in references},
        original_comparison_validity="prior_invalid_performance_not_pooled",
        independent_samples_pooled=False,
        usage_experiments_counted_once=experiments,
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
