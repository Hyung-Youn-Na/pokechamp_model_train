"""Preserve the single pinned EX-083 UUID guard failure before new qualification.

This is deliberately not a resume facility. Only the known failure before model
construction is eligible; the first attempt, its seal, clocks and source survive
unchanged under ``preflight-attempt1``. All numerical and collection gates rerun.
"""
from __future__ import annotations

import os
from pathlib import Path
import time
from uuid import UUID

from . import continuation, study
from .config import ROOT
from .storage import file_hash, read


FIRST_ATTEMPT_SEAL = "8c877db9451b2ac75bc46a0d8a09b21972750fd49fe033ad3e1545c9b2980b45"
FIRST_FILE_HASHES = {
    "evidence/execution-start.json": "6b490e597d19c7ba35a5b8cd399cae8cc95ed38525fefb6fb001eeb0bc4c0260",
    "evidence/reload-a.log": "65f2c6fdc8593c553b6a80688eb7f9c6c94d1b07a05024bb61e9b0287284e381",
    "source/integration/jev27b/resource.py": "6e05a8f64c4b63e3ccc0e907f9fa2b1f546c0e0e3a48fdec9d6117aaa1d338e5",
}
RESOURCE_SOURCE = "integration/jev27b/resource.py"
BAD_UUID_GUARD = "if str(properties.uuid).lower() != expected[physical].lower():"
UUID_ERROR = "RuntimeError: CUDA device 0 does not match physical GPU0 UUID"
PRESERVED_NAME = "preflight-attempt1"
ALLOWED_SOURCE_CHANGES = frozenset({
    RESOURCE_SOURCE,
    "integration/jev27b/continue_execute.py",
    "integration/jev27b/tests/test_four_gpu.py",
    "integration/jev27b/preflight_recovery.py",
    "integration/jev27b/tests/test_preflight_recovery.py",
})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _inventory(directory):
    files, directories = set(), set()
    for path in directory.rglob("*"):
        require(not path.is_symlink(), "preflight preservation refuses symbolic links")
        name = str(path.relative_to(directory))
        if path.is_dir():
            directories.add(name)
        else:
            require(path.is_file(), "preflight preservation requires regular files")
            files.add(name)
    return files, directories


def _strict_original_seal(directory):
    require(file_hash(directory / "checksums.sha256") == FIRST_ATTEMPT_SEAL,
            "only the pinned first EX-083 preflight failure can be recovered")
    seals = study.verify_seal(directory)
    files, directories = _inventory(directory)
    require(files == set(seals) | {"checksums.sha256"},
            "first preflight has unsealed or missing files")
    expected_directories = {str(parent) for name in seals for parent in Path(name).parents
                            if str(parent) != "."}
    # This empty monitor directory exists in the pinned failure and has no files.
    expected_directories.add("evidence/final-resources")
    require(directories == expected_directories, "first preflight directory inventory changed")
    for name, expected in FIRST_FILE_HASHES.items():
        require(seals.get(name) == expected, "first UUID failure evidence changed: " + name)
    return seals


def _validate_original(directory, parent):
    seals = _strict_original_seal(directory)
    evidence = directory / "evidence"
    start, source, cpu, completion, failure, cleanup, clock = (
        read(evidence / name) for name in (
            "execution-start.json", "source.json", "cpu.json", "completion.json",
            "execution-failure.json", "execution-cleanup.json", "clock-link.json"))
    require(start["experiment_id"] == "EX-083" and start["profile"] == "ex083"
            and start["directory"] == str(directory) and start["parent"] == str(parent)
            and start["time_limits"] is None, "first execution identity or parent changed")
    require(completion["experiment_id"] == "EX-083" and completion["status"] == "Blocked"
            and completion["experiment_target_achieved"] is False
            and completion["cleanup_passed"] is True and completion["new_battles_started"] is False
            and completion["serving_pid"] is None and completion["viewer"] is None
            and completion["parent"] == str(parent) and completion["parent_modified"] is False
            and completion["parent_original_status"] == "Blocked"
            and completion["execution_started_at"] == start["at"],
            "only a closed pre-model EX-083 failure is eligible")
    require(completion["error"] == failure and failure["phase"] == "reload-a"
            and failure["type"] == "RuntimeError" and failure["battle_collection_started"] is False
            and failure["detail"] == f"reload-a failed (exit 1); see {directory}/evidence/reload-a.log",
            "numerical, memory, collection, or another preflight failure cannot be recovered")
    require(cleanup["passed"] is True and cleanup["errors"] == []
            and cleanup["server_pid"] is None and cleanup["server_exit"] is None
            and cleanup["remaining_selected_gpu_processes"] == []
            and cleanup["gpu_locks_released"] == {str(i): True for i in range(4)}
            and cleanup["owned_ports_released"] == {"18782": True, "8109": True},
            "first preflight did not return every owned resource")
    require(clock["current_execution_at"] == start["at"]
            and clock["reset_cumulative_resource_limits"] is False
            and clock["elapsed_limits"] is None, "first cumulative clock link changed")
    before = start["source"]
    require(source["source"] == before == cpu["source"] and cpu["passed"] is True
            and cpu["test_log_sha256"] == seals["evidence/cpu.log"]
            and read(evidence / "cpu-exit.json")["exit"] == 0,
            "first CPU gate and frozen source do not agree")
    for name, checksum in before.items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts
                and seals.get("source/" + name) == checksum,
                "first source snapshot differs: " + name)
    old_resource = (directory / "source" / RESOURCE_SOURCE).read_text()
    require(old_resource.count(BAD_UUID_GUARD) == 1,
            "the first source does not contain the exact UUID representation defect")
    log = (evidence / "reload-a.log").read_text()
    require(log.startswith("Traceback (most recent call last):") and log.rstrip().endswith(UUID_ERROR)
            and "in own_gpus" in log and "with own_gpus(" in log,
            "first traceback is not the pre-model UUID guard failure")
    process, exited = (read(evidence / name) for name in ("reload-a-process.json", "reload-a-exit.json"))
    pid = process["pid"]
    require(type(pid) is int and pid > 0 and exited["pid"] == pid and exited["exit"] == 1,
            "first reload process was not reaped after the UUID failure")
    prefix = f"gates/reload-a/"
    expected_gate_files = {prefix + f"{name}-{pid}.{suffix}" for name, suffix in (
        ("gpu-acquire", "json"), ("gpu-release", "json"),
        ("gpu-settled", "json"), ("gpu-release-wait", "jsonl"))}
    require({name for name in seals if name.startswith("gates/")} == expected_gate_files,
            "model loading, inference, numerical, or memory gate artifacts are not recoverable")
    require(not any((directory / name).exists() for name in
                    ("serving", "collection", PRESERVED_NAME)),
            "server, collection, or a previous recovery already exists")
    require(not any(name.startswith("evidence/serving") or name in {
        "evidence/server-process.json", "evidence/entry-gates.json", "evidence/post-gates-health.json",
        "evidence/finalization.json", "evidence/combined-result.json", "evidence/preflight-recovery.json",
    } for name in seals), "first attempt contains serving, collection, or recovery evidence")
    acquired, released, settled = (read(directory / prefix / f"{name}-{pid}.json") for name in
                                  ("gpu-acquire", "gpu-release", "gpu-settled"))
    for receipt in (acquired, released, settled):
        require(receipt["profile"] == "ex083" and receipt["physical_gpus"] == [0, 1, 2, 3],
                "first GPU ownership scope changed")
    require(acquired["pid"] == released["pid"] == settled["previous_pid"] == pid
            and settled["passed"] is True and acquired["compute_processes"] == []
            and acquired["allocator_bytes"] == 40 * 1024**3
            and acquired["gpu_bytes"] == 44 * 1024**3, "first GPU ownership or release is incomplete")
    for i in range(4):
        key = str(i)
        require(acquired["gpus"][key]["uuid"] == settled["gpus"][key]["uuid"] == cleanup["gpus"][key]["uuid"]
                and settled["gpus"][key]["memory_used_mib"] <= 256
                and settled["gpus"][key]["utilization_percent"] <= 5
                and cleanup["gpus"][key]["memory_used_mib"] <= 256,
                "first physical GPU identity or release differs")
    parent_info = continuation.validate_parent(parent)
    original_parent = read(evidence / "parent-validation.json")
    require(parent_info["passed"] is True and original_parent["passed"] is True
            and parent_info["parent"] == original_parent["parent"] == str(parent)
            and parent_info["parent_seal_sha256"] == original_parent["parent_seal_sha256"] == continuation.PARENT_SEAL,
            "recovery must retain the approved EX-082 parent")
    return dict(seals=seals, start=start, source=before, clock=clock, acquired=acquired,
                parent_seal_sha256=parent_info["parent_seal_sha256"])


def _source_changes(before):
    after = study.source_identity()
    changes = [dict(path=name, before_sha256=before.get(name), after_sha256=after.get(name))
               for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]
    require(changes and RESOURCE_SOURCE in {row["path"] for row in changes},
            "the UUID guard correction must precede recovery")
    require(all(row["path"] in ALLOWED_SOURCE_CHANGES and row["after_sha256"] is not None for row in changes),
            "source changes exceed the narrow UUID tooling recovery scope")
    require(BAD_UUID_GUARD not in (ROOT / RESOURCE_SOURCE).read_text(),
            "the incorrect UUID representation guard is still active")
    return after, changes


def _validate_diagnostic(directory, original, after):
    """Check the independent 128-bit comparison without invoking CUDA or its helper."""
    directory = Path(directory).resolve()
    require(directory.is_dir(), "a completed independent UUID diagnostic is required")
    files, _ = _inventory(directory)
    if "checksums.sha256" in files:
        seals = study.verify_seal(directory)
        require(files == set(seals) | {"checksums.sha256"}, "UUID diagnostic seal inventory differs")
    require(not any(Path(name).name.startswith("resource-stop-") for name in files),
            "UUID diagnostic had a resource/ownership stop")
    result = read(directory / "result.json")
    require(result["passed"] is True
            and all(type(result[name]) is int and result[name] == 0
                    for name in ("model_loads", "gpu_forwards", "model_inferences", "battles")),
            "UUID diagnostic must have zero model loading, forwards, and battles")
    require({"resource.py", "diagnostic.py"}.issubset(files)
            and result["resource_source_sha256"] == after[RESOURCE_SOURCE]
            == file_hash(directory / "resource.py"),
            "UUID diagnostic belongs to a different resource implementation")
    pid = result["pid"]
    require(type(pid) is int and pid > 0, "UUID diagnostic has no process identity")
    settled = read(directory / f"gpu-settled-{pid}.json")
    require(settled["passed"] is True and settled["previous_pid"] == pid
            and settled["profile"] == "ex083" and settled["physical_gpus"] == [0, 1, 2, 3],
            "independent UUID diagnostic has not returned its four GPUs")
    rows = result["devices"]
    require(len(rows) == 4 and [row["physical_gpu"] for row in rows] == [0, 1, 2, 3],
            "independent UUID diagnostic must cover all four physical GPUs in order")
    for row in rows:
        i = row["physical_gpu"]
        raw = row["cuda_uuid_bytes"]
        require(isinstance(raw, list) and len(raw) == 16
                and all(type(value) is int and 0 <= value <= 255 for value in raw),
                "UUID diagnostic lacks the original 16 CUDA UUID bytes")
        nvml = row["nvml_uuid"]
        require(isinstance(nvml, str) and nvml.startswith("GPU-") and len(nvml) == 40,
                "UUID diagnostic NVML identifier is malformed")
        expected = UUID(nvml[4:])
        require(row["passed"] is True and row["old_string_gate_passes"] is False
                and row["local_gpu"] == i
                and all(type(row[name]) is int and row[name] == 0
                        for name in ("allocated_bytes", "reserved_bytes"))
                and UUID(bytes=bytes(raw)) == expected and UUID(row["cuda_uuid"]) == expected
                and row["cuda_uuid"].lower() != nvml.lower()
                and nvml == original["acquired"]["gpus"][str(i)]["uuid"]
                == settled["gpus"][str(i)]["uuid"]
                and settled["gpus"][str(i)]["memory_used_mib"] <= 256
                and settled["gpus"][str(i)]["utilization_percent"] <= 5,
                "independent UUID bytes, device mapping, defect reproduction, or release differs")
    return dict(passed=True, directory=str(directory), result_sha256=file_hash(directory / "result.json"),
                files={name: file_hash(directory / name) for name in sorted(files)},
                pid=pid, model_loads=0, gpu_forwards=0, model_inferences=0, battles=0,
                method="CUDA UUID.bytes compared independently with UUID(NVML[4:]).bytes")


def _fsync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _restore_original(directory, temporary, archive):
    """Roll back only our own empty wrapper; never delete preserved evidence."""
    if archive.is_dir() and not temporary.exists() and set(directory.iterdir()) == {archive}:
        archive.rename(temporary)
    if temporary.is_dir():
        if directory.exists():
            directory.rmdir()  # Refuse to remove any unexpected files.
        temporary.rename(directory)
        _fsync_directory(directory.parent)


def prepare_uuid_recovery(directory, parent, *, uuid_diagnostic):
    """Atomically preserve the known first failure and return its recovery receipt.

    The caller must record the receipt in fresh evidence and run every CPU/GPU
    gate again. This function performs no model loading, GPU calls, or battles.
    """
    raw_directory = Path(directory)
    require(uuid_diagnostic is not None, "a completed independent UUID diagnostic is required")
    require(not raw_directory.is_symlink(), "recovery output must not be a symbolic link")
    directory, parent = raw_directory.resolve(), Path(parent).resolve()
    require(directory.is_dir(), "the pinned first preflight directory must exist")
    require(not (directory / PRESERVED_NAME).exists(), "a first attempt is already preserved; no second recovery")
    require(not directory.is_relative_to(parent) and not parent.is_relative_to(directory),
            "recovery output and the preserved parent must be disjoint")
    temporary = directory.with_name("." + directory.name + ".uuid-preflight-preserving")
    require(not temporary.exists(), "an unfinished preservation already exists; refuse another recovery")
    original = _validate_original(directory, parent)
    after, changes = _source_changes(original["source"])
    diagnostic = _validate_diagnostic(uuid_diagnostic, original, after)
    require(not Path(diagnostic["directory"]).is_relative_to(directory),
            "the independent diagnostic must be outside the immutable first attempt")
    require(study.source_identity() == after, "source changed during recovery validation")
    _strict_original_seal(directory)
    archive = directory / PRESERVED_NAME
    receipt = dict(
        passed=True, schema_version="jev27b-ex083-uuid-preflight-recovery-v1", experiment_id="EX-083",
        at=time.time(), recovery_attempt=1, allowed_scope="UUID pre-load tooling only; rerun all qualification gates",
        first_execution_at=original["start"]["at"], parent_first_request_at=original["clock"]["parent_first_request_at"],
        original_clock_link=original["clock"], original_execution_start_sha256=FIRST_FILE_HASHES["evidence/execution-start.json"],
        original_seal_sha256=FIRST_ATTEMPT_SEAL, original_file_hashes=dict(FIRST_FILE_HASHES),
        original_directory=str(directory), preserved_directory=str(archive), preserved_relative_path=PRESERVED_NAME,
        original_status="Blocked", original_bytes_unchanged=True, source_before=original["source"],
        source_after=after, source_changes=changes, allowed_source_changes=sorted(ALLOWED_SOURCE_CHANGES),
        parent=str(parent), parent_seal_sha256=original["parent_seal_sha256"],
        previous_model_loads=0, previous_gpu_forwards=0, previous_gpu_gate_calls=0, previous_battles=0,
        reset_cumulative_resource_limits=False, elapsed_limits=None, battle_attempt_allowance_changed=False,
        uuid_diagnostic=diagnostic,
    )
    try:
        directory.rename(temporary)
        _fsync_directory(directory.parent)
        directory.mkdir(exist_ok=False)
        temporary.rename(archive)
        _fsync_directory(directory)
        _fsync_directory(directory.parent)
        _strict_original_seal(archive)
        require(set(directory.iterdir()) == {archive}, "fresh recovery directory gained unexpected content")
    except BaseException:
        _restore_original(directory, temporary, archive)
        raise
    return receipt
