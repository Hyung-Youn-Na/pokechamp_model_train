"""D-034 independently qualified repeat, linked to the immutable EX-028 cohort."""

from pathlib import Path

from .. import benchmark as b
from .battle_only_protocol import read_ref, ref
from .receipts import source_identity

ORIGINAL = b.WORKSPACE_ROOT / ".pokechamp-data/battle-guide-direct32/ex028"
ORIGINAL_PREPARED = ORIGINAL.with_name("ex028-prepared")
REQUIRED = {
    "defect_reproduction",
    "showdown_independent_rolls",
    "worker_invariants",
    "ex028_all435_recalculation",
    "integration_regression",
    "changed_file_static",
    "node_syntax",
    "source_config_checks",
}


def verify_qualification(path, *, current=True):
    if path is None:
        raise ValueError("calcfix32 requires sealed independent verification")
    receipt = b.read_sealed(Path(path))
    if (
        receipt.get("qualification") != "calculator-clone-independent-regression-v1"
        or receipt.get("passed") is not True
        or set(receipt.get("checks", {})) != REQUIRED
        or any(v is not True for v in receipt["checks"].values())
        or not receipt.get("evidence_files")
    ):
        raise ValueError("calcfix32 qualification incomplete")
    for name, checksum in receipt["evidence_files"].items():
        if b.digest(Path(name)) != checksum:
            raise ValueError("calcfix32 verification evidence drift")
    if current and receipt.get("source_files") != source_identity():
        raise ValueError("calcfix32 verified source drift")
    return receipt


def preparation_evidence(verification):
    verify_qualification(verification)
    return dict(
        qualification=ref(verification),
        original=dict(
            experiment_id="EX-028",
            manifest=ref(ORIGINAL_PREPARED / "manifest.json"),
            study=ref(ORIGINAL / "study.json"),
            first_clock=ref(ORIGINAL / "cloud-clock.json"),
            report=ref(ORIGINAL / "report-final/report.json"),
            ledger_files={
                str(p): b.digest(p)
                for p in sorted((ORIGINAL / "requests").glob("*.json"))
            },
        ),
    )


def validate_manifest(manifest, *, current=True):
    receipt = read_ref(manifest["qualification"])
    verify_qualification(manifest["qualification"]["path"], current=current)
    if receipt["source_files"] != manifest["source_files"]:
        raise ValueError("calcfix32 qualification source mismatch")
    original = manifest["original"]
    if original["experiment_id"] != "EX-028" or not original["ledger_files"]:
        raise ValueError("calcfix32 original provenance missing")
    prior = read_ref(original["manifest"])
    for key in ("study", "first_clock", "report"):
        read_ref(original[key])
    for path, checksum in original["ledger_files"].items():
        if b.digest(Path(path)) != checksum:
            raise ValueError("calcfix32 original ledger drift")
    for key in (
        "compare_schedule",
        "reference",
        "battle_prompt_identity",
        "prior_sha256",
        "calculation_identity",
        "prompt_sha256",
    ):
        if manifest[key] != prior[key]:
            raise ValueError(f"calcfix32 original {key} mismatch")
    if read_ref(manifest["config"]) != read_ref(prior["config"]):
        raise ValueError("calcfix32 original config mismatch")
    # Both manifests reference the same sealed plan, including team text hashes.
    reference = read_ref(prior["reference"])
    b.verify_plan(Path(prior["reference"]["path"]).parent)
    if len(manifest["compare_schedule"]) != 32 or not reference["development_teams"]:
        raise ValueError("calcfix32 original cohort incomplete")


def cumulative_report(manifest, result):
    original = read_ref(manifest["original"]["report"])
    clock = read_ref(manifest["original"]["first_clock"])
    import time

    return dict(
        original=manifest["original"],
        original_comparison_validity="withdrawn_pending_separate_defect_correction",
        independent_samples_pooled=False,
        cumulative_usage={
            k: original["usage"][k] + result["usage"][k]
            for k in ("reserved_calls", "responses", "uncertain")
        },
        original_uncertain_requests=original["usage"]["uncertain"],
        cumulative_confirmed_tokens={
            k: original["confirmed_tokens"].get(k, 0)
            + result["confirmed_tokens"].get(k, 0)
            for k in original["confirmed_tokens"].keys()
            | result["confirmed_tokens"].keys()
        },
        cumulative_collection_seconds=(
            original["batch_elapsed_seconds"] + result["batch_elapsed_seconds"]
        ),
        elapsed_since_original_first_cloud_seconds=time.time()
        - clock["first_dispatch_at"],
    )


def defect_correction(study, manifest):
    """Read a separate post-stop analysis without rewriting collection evidence."""
    path = Path(study) / "defects/reentry-impact.json"
    if not path.exists():
        return {}
    impact = b.read_sealed(path)
    independent = b.read_sealed(path.with_name("reentry-independent.json"))
    slots = {s["slot_id"] for s in manifest["compare_schedule"]}
    affected = {r["slot_id"] for r in impact["matches"] if r["first_contamination"]}
    if (
        impact["experiment"] != "EX-029"
        or impact["collection_source_files"] != manifest["source_files"]
        or set(impact["invalid_slots"]) != affected
        or not affected <= slots
        or independent.get("passed") is not True
    ):
        raise ValueError("calcfix32 defect correction provenance mismatch")
    return dict(
        impact=ref(path),
        independent=ref(path.with_name("reentry-independent.json")),
        invalid_slots=sorted(affected),
        changed_inputs=impact["changed_inputs"],
        runtime_fix_applied=impact["runtime_fix_applied"],
        collection_halt=ref(Path(study) / "halt-c0.json"),
    )
