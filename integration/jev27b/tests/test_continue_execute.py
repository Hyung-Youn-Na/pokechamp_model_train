"""CPU controller tests: failed gates never admit collection or retain a server."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.jev27b import client, continuation, continuation_gates, resource, study
from integration.jev27b import continue_execute as controller
from integration.jev27b.storage import file_hash, read, write


@pytest.fixture
def execution(tmp_path, monkeypatch):
    """Run the real controller with every process/GPU/network boundary replaced."""
    root = tmp_path / "workspace"
    (root / "pokechamp").mkdir(parents=True)
    parent = root / "parent"
    preserved = root / "preserved-evidence"
    baseline = root / "baseline"
    parent.mkdir()
    preserved.mkdir()
    baseline.mkdir()
    write(parent / "result.json", dict(first_request_at=10.0))
    study.seal(parent)
    write(preserved / "execution-start.json", dict(at=9.0))
    study.seal(preserved)
    write(baseline / "manifest.json", dict(experiment_id="EX-058"))
    state = SimpleNamespace(
        parent=parent, directory=root / "new-run", export=root / "viewer",
        events=[], processes=[], clients=[], active_monitors=[], source={"stub": "a" * 64},
        fail_stage=None, failure_type=RuntimeError, injected=False,
        collection_calls=0, final_calls=0, final_passed=True, export_passed=True,
        browser_passed=True, cleanup_failure=False, health_count=597,
        identity="d" * 64,
    )

    def step(name):
        state.events.append(name)
        if state.fail_stage == name and not state.injected:
            state.injected = True
            raise state.failure_type("injected " + name)

    class Monitor:
        def __init__(self, directory, *, profile, budget_root):
            assert profile == "ex083" and Path(budget_root) == state.directory
            self.directory = Path(directory)

        def __enter__(self):
            state.active_monitors.append(self.directory)
            return self

        def __exit__(self, *_args):
            state.active_monitors.remove(self.directory)

    class Process:
        pid = 45831
        returncode = None

        def __init__(self, command, **kwargs):
            assert command[command.index("-m") + 1] == "integration.jev27b.server"
            assert command[command.index("--profile") + 1] == "ex083"
            assert Path(command[command.index("--budget-root") + 1]) == state.directory
            assert kwargs["start_new_session"] is True
            self.stdout = kwargs["stdout"]
            self.stops = 0
            self.releases = 0
            state.processes.append(self)
            step("server-created")
            serving = Path(command[command.index("--run-dir") + 1])
            write(serving / f"gpu-acquire-{self.pid}.json",
                  dict(pid=self.pid, gpus={i: dict(uuid=f"gpu-{i}") for i in range(4)}))
            journal = serving / "server/requests.sqlite3"
            journal.parent.mkdir()
            journal.touch()

        def poll(self):
            return self.returncode

    class Client:
        def __init__(self, endpoint, *, expected_identity):
            assert expected_identity == state.identity
            self.closed = False
            self.health_calls = 0
            state.clients.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

        def health(self):
            self.health_calls += 1
            if self.health_calls == 1:
                step("serving-load")
            return dict(server_pid=state.processes[0].pid,
                        requests={"completed": state.health_count})

    def stop(process):
        step("server-stopped")
        process.stops += 1
        process.returncode = -15

    def release(directory, pid, *, profile):
        assert profile == "ex083"
        process = state.processes[0]
        assert process.pid == pid and process.returncode is not None
        assert (Path(directory) / f"gpu-acquire-{pid}.json").is_file()
        step("gpu-released")
        process.releases += 1
        if state.cleanup_failure:
            raise RuntimeError("injected release verification failure")

    def closure():
        assert all(process.returncode is not None for process in state.processes)
        step("resource-closure")
        return dict(passed=True, gpus={i: dict(memory_used_mib=0) for i in range(4)})

    def disk_bytes(*, profile, budget_root):
        assert profile == "ex083" and Path(budget_root) == state.directory
        return 1024

    def validate_parent(path):
        assert Path(path) == parent
        step("parent-validation")
        return dict(passed=True, parent=str(parent), parent_seal_sha256=file_hash(parent / "checksums.sha256"))

    def preparation():
        step("preserved-preparation")
        return dict(passed=True)

    def run_stage(command, name, evidence, *, gpu_directory=None, extra_env=None):
        step(name)
        (Path(evidence) / (name + ".log")).write_text("CPU stub\n")
        if name.startswith("reload-"):
            assert command[command.index("--profile") + 1] == "ex083"
            assert Path(command[command.index("--evidence") + 1]) == preserved
            Path(gpu_directory).mkdir()
        if name == "viewer-browser":
            assert extra_env == {"TMPDIR": str(state.directory / "browser-temp")}
            write(Path(evidence) / "viewer-browser.json", dict(passed=state.browser_passed))
        return 45829 if name == "reload-a" else 45830

    def compare(directory):
        step("reload-comparison")
        result = dict(passed=True, serving_identity=state.identity)
        write(Path(directory) / "reload-comparison.json", result)
        return result

    def replay(active_client, path, directory, journal):
        assert active_client is state.clients[0] and Path(path) == parent
        step("parent-replay")
        result = dict(passed=True, completed=591)
        write(Path(directory) / "result.json", result)
        return result, {"decision": "stopped"}, {"decision": "shortest"}

    def memory(active_client, stopped, shortest, directory, journal, *, server_pid, expected_gpus):
        assert active_client is state.clients[0] and server_pid == state.processes[0].pid
        assert set(expected_gpus) == set(range(4))
        assert stopped == {"decision": "stopped"} and shortest == {"decision": "shortest"}
        step("continuous-memory")
        result = dict(passed=True)
        write(Path(directory) / "result.json", result)
        return result

    def ordinary(active_client, directory, journal):
        assert active_client is state.clients[0]
        step("ordinary-preflight")
        result = dict(passed=True)
        write(Path(directory) / "ordinary-preflight.json", result)
        return result

    async def collect(directory, *, parent, expected_identity, gate_receipt, endpoint):
        state.collection_calls += 1
        step("collection")
        assert Path.cwd() == root / "pokechamp"
        assert expected_identity == state.identity
        assert all(gate_receipt[key] is True for key in (
            "passed", "cpu_passed", "reload_passed", "replay_passed", "memory_passed", "preflight_passed"))
        result = dict(passed=True, completed=32, completed_pairs=16,
                      total_battle_attempts=33, new_attempted=9, new_completed=9)
        write(Path(directory) / "result.json", result)
        return result

    def finalize(directory, *, parent, output, evidence, browser):
        state.final_calls += 1
        step("finalization")
        assert state.processes[0].returncode is not None
        assert Path(evidence) / "final-resources" in state.active_monitors
        assert browser is False
        Path(output).mkdir()
        (Path(output) / "index.html").write_text("CPU viewer stub")
        return dict(passed=state.final_passed, result=read(Path(directory) / "result.json"),
                    export=dict(passed=state.export_passed))

    monkeypatch.setattr(controller, "ROOT", root)
    monkeypatch.setattr(controller, "EVIDENCE", preserved)
    monkeypatch.setattr(controller, "BASELINE", baseline)
    monkeypatch.setattr(controller, "EXPORT", state.export)
    monkeypatch.setattr(controller, "_source_receipt", lambda *_args: None)
    monkeypatch.setattr(controller, "final_report", lambda directory, completion: (
        Path(directory) / "report.md").write_text("CPU report stub\n"))
    monkeypatch.setattr(controller, "update_viewer_catalog", lambda _combined: step("viewer-catalog"))
    monkeypatch.setattr(controller, "child_environment", lambda: {})
    monkeypatch.setattr(controller, "run_stage", run_stage)
    monkeypatch.setattr(controller, "stop_owned_process", stop)
    monkeypatch.setattr(controller, "resource_closure", closure)
    monkeypatch.setattr(controller, "assert_free_port", lambda *_args: None)
    monkeypatch.setattr(controller.subprocess, "Popen", Process)
    monkeypatch.setattr(controller.socket, "create_connection", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(client, "LocalClient", Client)
    monkeypatch.setattr(resource, "ResourceMonitor", Monitor)
    monkeypatch.setattr(resource, "wait_owned_gpu_release", release)
    monkeypatch.setattr(resource, "disk_bytes", disk_bytes)
    monkeypatch.setattr(resource, "gpu_facts", lambda: pytest.fail("controller tests must never inspect GPUs"))
    monkeypatch.setattr(study, "source_identity", lambda: dict(state.source))
    monkeypatch.setattr(study, "snapshot_sources", lambda *_args: None)
    monkeypatch.setattr(study, "load_baseline", lambda **_kwargs: dict(input_data_identity="frozen"))
    monkeypatch.setattr(continuation, "validate_parent", validate_parent)
    monkeypatch.setattr(continuation, "attempt_plan", lambda _parent_info: [])
    monkeypatch.setattr(continuation, "run", collect)
    monkeypatch.setattr(continuation, "finalize", finalize)
    monkeypatch.setattr(continuation_gates, "preserved_preparation", preparation)
    monkeypatch.setattr(continuation_gates, "PARENT_EVIDENCE_SEAL", file_hash(preserved / "checksums.sha256"))
    monkeypatch.setattr(continuation_gates, "compare_reloads", compare)
    monkeypatch.setattr(continuation_gates, "replay_parent", replay)
    monkeypatch.setattr(continuation_gates, "memory_gate", memory)
    monkeypatch.setattr(continuation_gates, "ordinary_gate", ordinary)
    state.execute = lambda: controller.execute(state.parent, state.directory)
    return state


@pytest.mark.parametrize("failed", [
    "parent-validation", "preserved-preparation", "cpu", "reload-a", "reload-b",
    "reload-comparison", "serving-load", "parent-replay", "continuous-memory", "ordinary-preflight",
])
def test_any_failed_gate_prevents_collection_and_seals_failure(execution, failed):
    execution.fail_stage = failed
    completion = execution.execute()
    assert execution.injected
    assert completion["status"] == "Blocked" and completion["experiment_target_achieved"] is False
    assert completion["new_battles_started"] is False
    assert execution.collection_calls == execution.final_calls == 0
    assert not (execution.directory / "collection").exists()
    assert read(execution.directory / "evidence/execution-failure.json")["type"] == "RuntimeError"
    assert read(execution.directory / "evidence/execution-cleanup.json")["passed"] is True
    if failed in {"serving-load", "parent-replay", "continuous-memory", "ordinary-preflight"}:
        assert len(execution.processes) == 1
        assert execution.processes[0].stops == execution.processes[0].releases == 1
        assert execution.processes[0].stdout.closed
        assert execution.clients[0].closed
    else:
        assert execution.processes == []
    sealed = study.verify_seal(execution.directory)
    assert "evidence/execution-failure.json" in sealed and "evidence/completion.json" in sealed


@pytest.mark.parametrize("failed", ["serving-load", "parent-replay", "continuous-memory", "ordinary-preflight"])
def test_cancellation_after_server_creation_stops_owned_server_without_collection(execution, failed):
    execution.fail_stage, execution.failure_type = failed, KeyboardInterrupt
    completion = execution.execute()
    assert completion["status"] == "Blocked" and completion["cleanup_passed"] is True
    assert completion["error"]["type"] == "KeyboardInterrupt"
    assert execution.collection_calls == 0
    assert execution.processes[0].stops == execution.processes[0].releases == 1
    assert execution.processes[0].stdout.closed and execution.clients[0].closed
    study.verify_seal(execution.directory)


def test_success_uses_one_continuous_server_and_releases_it_before_finalization(execution):
    completion = execution.execute()
    assert completion["status"] == "Completed" and completion["experiment_target_achieved"] is True
    assert execution.collection_calls == execution.final_calls == len(execution.processes) == len(execution.clients) == 1
    ordered = ["cpu", "reload-a", "reload-b", "reload-comparison", "server-created",
               "parent-replay", "continuous-memory", "ordinary-preflight", "collection",
               "server-stopped", "gpu-released", "finalization", "viewer-browser"]
    assert [event for event in execution.events if event in ordered] == ordered
    assert execution.processes[0].stdout.closed and execution.clients[0].closed
    assert execution.active_monitors == []
    study.verify_seal(execution.directory)


def test_post_gate_request_count_mismatch_cannot_start_collection(execution):
    execution.health_count = 596
    completion = execution.execute()
    assert completion["status"] == "Blocked"
    assert "denominator" in completion["error"]["detail"]
    assert execution.collection_calls == 0
    assert execution.processes[0].stops == execution.processes[0].releases == 1


@pytest.mark.parametrize("failed", ["final_passed", "export_passed", "browser_passed"])
def test_failed_final_audit_export_or_browser_cannot_mark_completed(execution, failed):
    setattr(execution, failed, False)
    completion = execution.execute()
    assert execution.collection_calls == execution.final_calls == 1
    assert read(execution.directory / "collection/result.json")["passed"] is True
    assert completion["status"] == "Blocked" and completion["experiment_target_achieved"] is False
    assert read(execution.directory / "evidence/completion.json")["status"] == "Blocked"


def test_resource_release_failure_prevents_completion_even_after_valid_collection(execution):
    execution.cleanup_failure = True
    completion = execution.execute()
    assert execution.collection_calls == execution.final_calls == 1
    assert completion["status"] == "Blocked" and completion["cleanup_passed"] is False
    assert read(execution.directory / "evidence/execution-cleanup.json")["errors"]
