"""CPU evidence/atomic-preservation tests for the one approved UUID tooling defect."""
import copy
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from integration.jev27b import preflight_recovery as recovery
from integration.jev27b import study
from integration.jev27b.storage import file_hash, read, write


def replace_json(path, change):
    value = read(path)
    change(value)
    write(path, value, immutable=False)


def bytes_inventory(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


@pytest.fixture
def attempt(tmp_path, monkeypatch):
    """Independent minimal receipts stand in for the hard-pinned real first run."""
    directory, checkout, parent, diagnostic = (tmp_path / name for name in
                                              ("EX-083", "checkout", "EX-082", "uuid-diagnostic"))
    for path in (directory, checkout, parent, diagnostic):
        path.mkdir()
    (directory / "evidence/final-resources").mkdir(parents=True)
    source_text = {
        recovery.RESOURCE_SOURCE: "def own_gpus():\n    " + recovery.BAD_UUID_GUARD + "\n        raise RuntimeError('UUID')\n",
        "integration/jev27b/continue_execute.py": "# first controller\n",
        "integration/jev27b/tests/test_four_gpu.py": "# first GPU fixture\n",
        **{f"integration/jev27b/{name}.py": f"# unchanged {name}\n" for name in
           ("model", "formatting", "config", "preflight", "battle", "client")},
    }
    before = {}
    for name, text in source_text.items():
        for base in (directory / "source", checkout):
            target = base / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        before[name] = file_hash(directory / "source" / name)
    (checkout / recovery.RESOURCE_SOURCE).write_text(
        "def own_gpus():\n    if canonical_gpu_uuid(properties.uuid) != canonical_gpu_uuid(expected[physical]):\n"
        "        raise RuntimeError('UUID')\n")
    (checkout / "integration/jev27b/preflight_recovery.py").write_text("# narrow recovery\n")
    (checkout / "integration/jev27b/tests/test_preflight_recovery.py").write_text("# recovery regression\n")

    def current_source():
        return {str(path.relative_to(checkout)): file_hash(path) for path in checkout.rglob("*.py")}

    pid = 7301
    gpus = {str(i): dict(uuid="GPU-" + str(UUID(int=i + 1)), memory_used_mib=0,
                         utilization_percent=0) for i in range(4)}
    failure = dict(phase="reload-a", type="RuntimeError", battle_collection_started=False,
                   detail=f"reload-a failed (exit 1); see {directory}/evidence/reload-a.log")
    start = dict(experiment_id="EX-083", profile="ex083", directory=str(directory),
                 parent=str(parent), time_limits=None, at=100.0, source=before)
    parent_info = dict(passed=True, parent=str(parent), parent_seal_sha256=recovery.continuation.PARENT_SEAL)
    evidence = directory / "evidence"
    write(evidence / "execution-start.json", start)
    write(evidence / "source.json", dict(source=before))
    write(evidence / "execution-failure.json", failure)
    write(evidence / "completion.json", dict(
        experiment_id="EX-083", status="Blocked", experiment_target_achieved=False,
        cleanup_passed=True, new_battles_started=False, serving_pid=None, viewer=None,
        parent=str(parent), parent_modified=False, parent_original_status="Blocked",
        execution_started_at=100.0, error=failure))
    write(evidence / "execution-cleanup.json", dict(passed=True, errors=[], server_pid=None,
        server_exit=None, remaining_selected_gpu_processes=[],
        gpu_locks_released={str(i): True for i in range(4)},
        owned_ports_released={"18782": True, "8109": True}, gpus=gpus))
    write(evidence / "clock-link.json", dict(current_execution_at=100.0,
        parent_first_request_at=20.0, parent_execution_start=dict(at=10.0),
        reset_cumulative_resource_limits=False, elapsed_limits=None))
    (evidence / "cpu.log").write_text("186 passed\n")
    write(evidence / "cpu.json", dict(passed=True, source=before,
                                     test_log_sha256=file_hash(evidence / "cpu.log")))
    write(evidence / "cpu-exit.json", dict(exit=0))
    write(evidence / "parent-validation.json", parent_info)
    write(evidence / "reload-a-process.json", dict(pid=pid))
    write(evidence / "reload-a-exit.json", dict(pid=pid, exit=1))
    (evidence / "reload-a.log").write_text(
        'Traceback (most recent call last):\n  with own_gpus(output):\n'
        '  File "resource.py", line 307, in own_gpus\n' + recovery.UUID_ERROR + "\n")
    gate = directory / "gates/reload-a"
    write(gate / f"gpu-acquire-{pid}.json", dict(pid=pid, profile="ex083",
        physical_gpus=[0, 1, 2, 3], gpus=gpus, compute_processes=[],
        allocator_bytes=40 * 1024**3, gpu_bytes=44 * 1024**3))
    write(gate / f"gpu-release-{pid}.json", dict(pid=pid, profile="ex083", physical_gpus=[0, 1, 2, 3]))
    write(gate / f"gpu-settled-{pid}.json", dict(passed=True, previous_pid=pid,
        profile="ex083", physical_gpus=[0, 1, 2, 3], gpus=gpus))
    (gate / f"gpu-release-wait-{pid}.jsonl").write_text('{}\n')
    (directory / "report.md").write_text("Blocked before model loading; zero forwards and battles.\n")
    (parent / "parent-sentinel").write_text("untouched EX-082\n")
    diagnostic_pid = 7302
    rows = [dict(physical_gpu=i, local_gpu=i, nvml_uuid=gpus[str(i)]["uuid"], cuda_uuid=str(UUID(int=i + 1)),
                 cuda_uuid_bytes=list(UUID(int=i + 1).bytes), old_string_gate_passes=False, passed=True,
                 allocated_bytes=0, reserved_bytes=0)
            for i in range(4)]
    write(diagnostic / "result.json", dict(passed=True, pid=diagnostic_pid,
        resource_source_sha256=current_source()[recovery.RESOURCE_SOURCE],
        model_loads=0, gpu_forwards=0, model_inferences=0, battles=0, devices=rows))
    (diagnostic / "resource.py").write_bytes((checkout / recovery.RESOURCE_SOURCE).read_bytes())
    (diagnostic / "diagnostic.py").write_text("# independent fixture: compare the 16 UUID bytes\n")
    write(diagnostic / f"gpu-settled-{diagnostic_pid}.json", dict(passed=True,
        previous_pid=diagnostic_pid, profile="ex083", physical_gpus=[0, 1, 2, 3], gpus=gpus))
    monkeypatch.setattr(recovery, "ROOT", checkout)
    monkeypatch.setattr(study, "source_identity", current_source)
    monkeypatch.setattr(recovery.continuation, "validate_parent", lambda path: copy.deepcopy(parent_info))
    monkeypatch.setattr(recovery, "FIRST_FILE_HASHES", {
        name: file_hash(directory / name) for name in recovery.FIRST_FILE_HASHES})

    def repin():
        # Only tests can pin a manufactured fixture. Production has the one literal seal.
        study.seal(directory)
        monkeypatch.setattr(recovery, "FIRST_ATTEMPT_SEAL", file_hash(directory / "checksums.sha256"))

    repin()
    return SimpleNamespace(directory=directory, checkout=checkout, parent=parent, diagnostic=diagnostic,
        evidence=evidence, pid=pid, source_before=before, repin=repin,
        prepare=lambda: recovery.prepare_uuid_recovery(directory, parent, uuid_diagnostic=diagnostic))


def test_preserves_every_original_byte_and_seal_via_rename_and_keeps_first_clock(attempt):
    old = bytes_inventory(attempt.directory)
    old_inode = attempt.directory.stat().st_ino
    parent_bytes = bytes_inventory(attempt.parent)
    receipt = attempt.prepare()
    archived = attempt.directory / recovery.PRESERVED_NAME
    assert set(attempt.directory.iterdir()) == {archived}
    assert archived.stat().st_ino == old_inode
    assert bytes_inventory(archived) == old
    assert bytes_inventory(attempt.parent) == parent_bytes
    assert receipt["first_execution_at"] == 100.0 and receipt["parent_first_request_at"] == 20.0
    assert receipt["original_clock_link"]["parent_execution_start"]["at"] == 10.0
    assert receipt["original_seal_sha256"] == file_hash(archived / "checksums.sha256")
    assert receipt["source_before"] == attempt.source_before
    assert {row["path"] for row in receipt["source_changes"]} == {
        recovery.RESOURCE_SOURCE, "integration/jev27b/preflight_recovery.py",
        "integration/jev27b/tests/test_preflight_recovery.py"}
    assert receipt["previous_model_loads"] == receipt["previous_gpu_forwards"] == receipt["previous_battles"] == 0
    assert receipt["reset_cumulative_resource_limits"] is False
    assert receipt["battle_attempt_allowance_changed"] is False
    assert receipt["uuid_diagnostic"]["result_sha256"] == file_hash(attempt.diagnostic / "result.json")
    study.verify_seal(archived)


def test_recovery_can_happen_only_once(attempt):
    attempt.prepare()
    old = bytes_inventory(attempt.directory)
    with pytest.raises(ValueError, match="no second recovery"):
        attempt.prepare()
    assert bytes_inventory(attempt.directory) == old


@pytest.mark.parametrize("reseal", [False, True])
def test_original_failure_corruption_or_resealing_is_rejected(attempt, reseal):
    (attempt.evidence / "reload-a.log").write_text("altered failure\n")
    if reseal:
        study.seal(attempt.directory)
    old = bytes_inventory(attempt.directory)
    with pytest.raises(ValueError):
        attempt.prepare()
    assert bytes_inventory(attempt.directory) == old
    assert not (attempt.directory / recovery.PRESERVED_NAME).exists()


def test_unsealed_extra_file_and_unrecorded_empty_directory_are_rejected(attempt):
    extra = attempt.directory / "additional-attempt"
    extra.mkdir()
    with pytest.raises(ValueError, match="inventory"):
        attempt.prepare()
    (extra / "new-response.json").write_text('{}\n')
    with pytest.raises(ValueError, match="unsealed"):
        attempt.prepare()
    assert not (attempt.directory / recovery.PRESERVED_NAME).exists()


@pytest.mark.parametrize("phase", ["reload-comparison", "parent-replay", "continuous-memory", "collection"])
def test_real_numerical_memory_or_collection_failure_is_never_recoverable(attempt, phase):
    replace_json(attempt.evidence / "execution-failure.json", lambda value: value.update(phase=phase))
    replace_json(attempt.evidence / "completion.json", lambda value: value["error"].update(phase=phase))
    attempt.repin()
    with pytest.raises(ValueError, match="numerical, memory, collection"):
        attempt.prepare()
    assert not (attempt.directory / recovery.PRESERVED_NAME).exists()


@pytest.mark.parametrize("artifact", [
    "gates/reload-a/loaded.json", "gates/reload-a/result.json", "gates/reload-a/lead-1.json",
    "gates/reload-b/result.json", "gates/parent-replay/result.json", "gates/memory/result.json",
    "serving/server/requests.sqlite3", "collection/result.json",
])
def test_any_model_result_or_serving_collection_artifact_refuses_recovery(attempt, artifact):
    path = attempt.directory / artifact
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}\n')
    attempt.repin()
    with pytest.raises(ValueError):
        attempt.prepare()
    assert not (attempt.directory / recovery.PRESERVED_NAME).exists()


@pytest.mark.parametrize("source", ["model", "formatting", "config", "preflight", "battle", "client"])
def test_model_input_configuration_and_battle_source_changes_are_refused(attempt, source):
    (attempt.checkout / f"integration/jev27b/{source}.py").write_text("# changed treatment\n")
    with pytest.raises(ValueError, match="source changes exceed"):
        attempt.prepare()
    assert not (attempt.directory / recovery.PRESERVED_NAME).exists()


def test_resource_must_be_corrected_and_no_source_can_be_removed(attempt):
    path = attempt.checkout / recovery.RESOURCE_SOURCE
    path.write_bytes((attempt.directory / "source" / recovery.RESOURCE_SOURCE).read_bytes())
    with pytest.raises(ValueError, match="correction must precede"):
        attempt.prepare()
    path.unlink()
    with pytest.raises(ValueError, match="source changes exceed"):
        attempt.prepare()


def test_changed_parent_and_incomplete_original_cleanup_refuse_recovery(attempt, monkeypatch):
    original = recovery.continuation.validate_parent
    monkeypatch.setattr(recovery.continuation, "validate_parent", lambda path:
                        dict(passed=True, parent=str(path), parent_seal_sha256="0" * 64))
    with pytest.raises(ValueError, match="approved EX-082 parent"):
        attempt.prepare()
    monkeypatch.setattr(recovery.continuation, "validate_parent", original)
    replace_json(attempt.evidence / "execution-cleanup.json",
                 lambda value: value["gpu_locks_released"].update({"3": False}))
    attempt.repin()
    with pytest.raises(ValueError, match="every owned resource"):
        attempt.prepare()


@pytest.mark.parametrize("mutation", [
    "gpu3-bytes", "device-order", "old-string-passed", "forwards", "model-load", "model-inference", "battles",
    "resource-source", "failed-result", "unsettled", "resource-stop",
])
def test_independent_diagnostic_must_prove_all_four_original_uuid_bytes_and_zero_model_work(attempt, mutation):
    path = attempt.diagnostic / "result.json"
    value = read(path)
    if mutation == "gpu3-bytes":
        value["devices"][3]["cuda_uuid_bytes"][0] ^= 1
    elif mutation == "device-order":
        value["devices"].reverse()
    elif mutation == "old-string-passed":
        value["devices"][0]["old_string_gate_passes"] = True
    elif mutation in {"forwards", "model-load", "model-inference", "battles"}:
        value[{"forwards": "gpu_forwards", "model-load": "model_loads",
               "model-inference": "model_inferences", "battles": "battles"}[mutation]] = 1
    elif mutation == "resource-source":
        value["resource_source_sha256"] = "0" * 64
    elif mutation == "failed-result":
        value["passed"] = False
    elif mutation == "unsettled":
        replace_json(attempt.diagnostic / f'gpu-settled-{value["pid"]}.json', lambda record: record.update(passed=False))
    else:
        write(attempt.diagnostic / f'resource-stop-{value["pid"]}.json', dict(errors=["foreign_gpu_compute_process"]))
    write(path, value, immutable=False)
    with pytest.raises(ValueError):
        attempt.prepare()
    assert not (attempt.directory / recovery.PRESERVED_NAME).exists()


def test_atomic_archive_move_failure_rolls_back_without_resealing_or_copying(attempt, monkeypatch):
    before = bytes_inventory(attempt.directory)
    inode = attempt.directory.stat().st_ino
    original_rename = Path.rename

    def fail_once(source, target):
        if Path(target).name == recovery.PRESERVED_NAME:
            raise OSError("injected second atomic rename failure")
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_once)
    with pytest.raises(OSError, match="injected"):
        attempt.prepare()
    assert attempt.directory.stat().st_ino == inode
    assert bytes_inventory(attempt.directory) == before
    assert not list(attempt.directory.parent.glob("*.uuid-preflight-preserving"))
    study.verify_seal(attempt.directory)


def test_source_change_during_validation_prevents_any_move(attempt, monkeypatch):
    source_identity = study.source_identity
    calls = 0

    def moving_source():
        nonlocal calls
        calls += 1
        result = source_identity()
        if calls > 1:
            result[recovery.RESOURCE_SOURCE] = "f" * 64
        return result

    before = bytes_inventory(attempt.directory)
    monkeypatch.setattr(study, "source_identity", moving_source)
    with pytest.raises(ValueError, match="source changed during recovery"):
        attempt.prepare()
    assert bytes_inventory(attempt.directory) == before


def test_preserved_diagnostic_seal_cannot_be_ignored(attempt):
    study.seal(attempt.diagnostic)
    (attempt.diagnostic / "diagnostic.py").write_text("# changed independent check\n")
    with pytest.raises(ValueError, match="seal mismatch"):
        attempt.prepare()
    assert not (attempt.directory / recovery.PRESERVED_NAME).exists()


def test_missing_independent_diagnostic_cannot_start_preservation(attempt):
    with pytest.raises(ValueError, match="independent UUID diagnostic"):
        recovery.prepare_uuid_recovery(attempt.directory, attempt.parent, uuid_diagnostic=None)
    assert not (attempt.directory / recovery.PRESERVED_NAME).exists()
