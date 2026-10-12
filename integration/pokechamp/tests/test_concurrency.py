import concurrent.futures
import json
import multiprocessing
import socket
import threading
import time
from types import SimpleNamespace

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.calibration import select_concurrency
from integration.pokechamp.cloud import CloudRequestError, OllamaCloudBackend
from integration.pokechamp.constants import OLLAMA_MODEL
from integration.pokechamp.execution import (
    estimate_schedule,
    run_parallel,
    validate_execution,
)
from integration.pokechamp.parallel_server import check_ports
from integration.pokechamp.permits import (
    Permit,
    PermitBroker,
    PermitCancelled,
    PermitError,
)


def config(n=2, deadline=None):
    return {
        "version": 1,
        "battle_concurrency": n,
        "account_request_limit": n,
        "model_request_limits": {OLLAMA_MODEL: n},
        "evidence": {"kind": "local_fixture"},
        "stop_new_work_at": deadline,
    }


def request_fixture(path, model):
    with Permit(path, model):
        start = time.time()
        time.sleep(0.08)
        return model, start, time.time()


def peak(intervals):
    events = sorted([(s, 1) for _, s, _ in intervals] + [(e, -1) for _, _, e in intervals])
    current = maximum = 0
    for _, delta in events:
        current += delta
        maximum = max(current, maximum)
    return maximum


def test_multiple_processes_respect_account_and_models(tmp_path):
    path = tmp_path / "p.sock"
    with PermitBroker(path, 3, {"a": 2, "b": 2}) as broker:
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=8, mp_context=multiprocessing.get_context("spawn")
        ) as pool:
            futures = [pool.submit(request_fixture, str(path), m) for m in ["a", "b"] * 8]
            rows = [f.result(timeout=20) for f in futures]
        assert 2 <= peak(rows) <= 3
        assert peak([r for r in rows if r[0] == "a"]) <= 2
        assert peak([r for r in rows if r[0] == "b"]) <= 2
        assert sum(broker.active.values()) == 0
        assert broker.maximum_total <= 3


def test_cancel_waiter_never_granted(tmp_path):
    path = tmp_path / "p.sock"
    cancel = threading.Event()
    with PermitBroker(path, 1, {"a": 1}) as broker, Permit(path, "a"):
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(lambda: Permit(path, "a", cancelled=cancel.is_set).__enter__())
            time.sleep(0.1)
            cancel.set()
            with pytest.raises(PermitCancelled):
                future.result(timeout=1)
        assert len([e for e in broker.events if e["event"] == "grant"]) == 1


def test_orphan_holds_capacity_until_timeout(tmp_path):
    path = tmp_path / "p.sock"
    with PermitBroker(path, 1, {"a": 1}, timeout=0.25) as broker:
        lease = Permit(path, "a").__enter__()
        lease.sock.close()
        start = time.monotonic()
        with Permit(path, "a"):
            assert time.monotonic() - start >= 0.2
        assert any(e["event"] == "orphan" for e in broker.events)
        assert sum(broker.active.values()) == 0


def test_broker_missing_and_stopped_fail_closed(tmp_path):
    with pytest.raises(PermitError):
        with Permit(tmp_path / "missing", "a"):
            pytest.fail("must not admit")
    path = tmp_path / "p.sock"
    with PermitBroker(path, 1, {"a": 1}) as broker:
        broker.stop()
        with pytest.raises(PermitCancelled):
            with Permit(path, "a"):
                pytest.fail("must not admit")


def test_cooldown_applies_across_models(tmp_path):
    path = tmp_path / "p.sock"
    with PermitBroker(path, 2, {"a": 2, "b": 2}):
        with Permit(path, "a") as permit:
            permit.cooldown = 0.2
        started = time.monotonic()
        with Permit(path, "b"):
            assert time.monotonic() - started >= 0.18


@pytest.mark.parametrize("retry_after,expected", [(None, 30), ("0.15", 0.15), ("invalid", 30)])
def test_v1_http_429_records_status_and_shared_cooldown(tmp_path, retry_after, expected):
    path = tmp_path / "p.sock"

    class Error(Exception):
        status_code = 429

    class Client:
        calls = 0

        def chat(self, **kwargs):
            self.calls += 1
            backend._http_response(
                SimpleNamespace(status_code=429, headers={"Retry-After": retry_after})
            )
            raise Error()

    client = Client()
    with PermitBroker(path, 1, {OLLAMA_MODEL: 1}) as broker:
        backend = OllamaCloudBackend(
            environ={"OLLAMA_API_KEY": "fixture", "POKECHAMP_PERMIT_SOCKET": str(path),
                     "POKECHAMP_TRANSPORT_POLICY": "connect-retry-v1"},
            client_factory=lambda **kw: client,
        )
        with pytest.raises(CloudRequestError, match="rate_limit"):
            backend.get_LLM_action("s", "u", OLLAMA_MODEL)
        assert client.calls == 1
        record = backend.call_records[-1]
        assert record["http_status"] == 429
        assert record["retry_after"] == retry_after
        assert record["cooldown_seconds"] == expected
        assert sum(broker.active.values()) == 0
        assert broker.cooldown > time.monotonic()


def test_cancelled_backend_does_not_call_http(tmp_path):
    cancel = tmp_path / "cancel.json"
    cancel.write_text("{}")
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "fixture", "POKECHAMP_CANCEL_PATH": str(cancel)},
        client_factory=lambda **kw: SimpleNamespace(
            chat=lambda **kw: pytest.fail("HTTP after cancel")
        ),
    )
    with pytest.raises(CloudRequestError, match="budget_stop"):
        backend.get_LLM_action("s", "u", OLLAMA_MODEL)
    assert backend.call_records[-1]["network_called"] is False


def test_occupied_port_is_not_killed():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 8109))
        listener.listen()
        with pytest.raises(OSError):
            check_ports([8109])
        with socket.create_connection(("127.0.0.1", 8109)):
            pass


def test_execution_rejects_unknown_models_and_limits():
    for key, value in [
        ("battle_concurrency", 11),
        ("account_request_limit", True),
        ("model_request_limits", {"other": 2}),
        ("evidence", {}),
    ]:
        item = config()
        item[key] = value
        with pytest.raises(ValueError):
            validate_execution(item)


def test_selection_requires_three_repeats_and_chooses_lowest_95pct():
    levels = [
        {
            "concurrency": c,
            "calls": 20,
            "transport_errors": [],
            "http_latencies_ms": [100 * c],
            "json_per_second": rate,
        }
        for c, rate in [(1, 1), (2, 2), (3, 4)]
        for _ in range(3)
    ]
    assert select_concurrency(levels) == 2  # C3 violates latency bound
    assert select_concurrency(levels[1:]) is None
    for row in levels:
        row["http_latencies_ms"] = [100]
        if row["concurrency"] == 2:
            row["json_per_second"] = 3.81
    assert select_concurrency(levels) == 2


def test_schedule_estimate_uses_lanes():
    slots = [{"pair": ["a", "b"]}] * 8
    assert estimate_schedule(slots, {"a-b": 10}, 2) == 40
    assert estimate_schedule(slots, {}, 2) is None


def test_scheduler_isolates_failure_retains_order_and_skips_completed(tmp_path, monkeypatch):
    schedule = [{"slot_id": str(i)} for i in range(4)]
    value = {"execution": config(), "schedule": schedule}
    calls = []

    def fake(root, directory, value, slot, number, **kw):
        calls.append(slot["slot_id"])
        time.sleep(0.03 if slot["slot_id"] == "1" else 0.08)
        category = "output_contract" if slot["slot_id"] == "1" else None
        return {
            "slot_id": slot["slot_id"],
            "number": number,
            "eligible": category is None,
            "category": category,
        }

    monkeypatch.setattr(b, "verify_plan", lambda *a, **kw: value)
    monkeypatch.setattr(b, "run_attempt", fake)
    existing = [{"slot_id": "0", "number": 1, "eligible": True, "category": None}]
    run_parallel(tmp_path, tmp_path, value, existing)
    assert calls == ["1", "2", "3"]
    assert len(existing) == 4
    batch = b.read_sealed(next((tmp_path / "batches").glob("*.json")))
    assert batch["maximum_battles"] == 2
    assert batch["stop_category"] is None


def test_scheduler_expired_budget_preserves_undispatched_denominator(tmp_path, monkeypatch):
    value = {"execution": config(deadline=time.time() - 1), "schedule": [{"slot_id": "a"}]}
    monkeypatch.setattr(b, "run_attempt", lambda *a, **kw: pytest.fail("dispatch after deadline"))
    run_parallel(tmp_path, tmp_path, value, [])
    batch = b.read_sealed(next((tmp_path / "batches").glob("*.json")))
    assert batch["not_dispatched_slots"] == ["a"]
    assert batch["stop_category"] == "budget_stop"


def test_comparison_gate_rejects_provider_and_completion_regressions():
    import copy

    from integration.pokechamp.concurrency_study import comparison_gate

    sequential = {"eligible_slots": 6, "batch_elapsed_seconds": 100}
    parallel = {
        "eligible_slots": 6,
        "batch_elapsed_seconds": 50,
        "batches": [],
        "failures": {},
        "request_concurrency": {"http_status_counts": {}, "error_counts": {}},
    }
    assert comparison_gate(sequential, parallel) == []
    for field, value, reason in [
        ("eligible_slots", 5, "fewer_valid_completions"),
        ("batch_elapsed_seconds", 101, "not_faster"),
        ("failures", {"integrity": 1}, "integrity_or_configuration"),
    ]:
        changed = copy.deepcopy(parallel)
        changed[field] = value
        assert reason in comparison_gate(sequential, changed)
    parallel["request_concurrency"]["http_status_counts"]["429"] = 1
    assert "provider_429_or_timeout" in comparison_gate(sequential, parallel)


def test_actual_http_overlap_not_permit_count():
    from integration.pokechamp.concurrency_metrics import request_metrics

    calls = [
        {
            "request": {"model": "a"},
            "response": {
                "http_started_at": start,
                "http_finished_at": end,
                "permit_wait_ms": 50,
                "http_elapsed_ms": 100,
            },
        }
        for start, end in [(1, 3), (2, 4), (4, 5)]
    ]
    result = request_metrics(calls)
    assert result["maximum_account_http_overlap"] == 2
    assert result["http_p95_ms"] == 100
    assert result["permit_wait_p95_ms"] == 50


def test_hard_stop_cancels_peer_and_prevents_new_slots(tmp_path, monkeypatch):
    value = {"execution": config(), "schedule": [{"slot_id": str(i)} for i in range(3)]}

    def fake(root, directory, value, slot, number, **kw):
        target = directory / "attempts" / f"{slot['slot_id']}-a{number}"
        target.mkdir(parents=True)
        if slot["slot_id"] == "0":
            time.sleep(0.1)
            category = "auth"
        else:
            assert slot["slot_id"] == "1"
            deadline = time.monotonic() + 2
            while not (target / "cancel.json").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert (target / "cancel.json").exists()
            with pytest.raises(PermitCancelled):
                with Permit(kw["broker_path"], OLLAMA_MODEL):
                    pytest.fail("HTTP after hard stop")
            category = "peer_failure"
        return {
            "slot_id": slot["slot_id"],
            "number": number,
            "eligible": False,
            "category": category,
        }

    monkeypatch.setattr(b, "verify_plan", lambda *a, **kw: value)
    monkeypatch.setattr(b, "run_attempt", fake)
    run_parallel(tmp_path, tmp_path, value, [])
    batch = b.read_sealed(next((tmp_path / "batches").glob("*.json")))
    assert batch["not_dispatched_slots"] == ["2"]
    assert batch["stop_category"] == "auth"


def test_paid_response_preserved_when_broker_release_fails(monkeypatch):
    import contextlib

    from integration.pokechamp.calibration import Trace

    trace = Trace()
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "fixture"},
        trace_sink=trace,
        client_factory=lambda **kw: SimpleNamespace(
            chat=lambda **kw: {
                "model": OLLAMA_MODEL,
                "message": {"content": '{"score":42}'},
                "done_reason": "stop",
                "eval_count": 5,
                "prompt_eval_count": 10,
            }
        ),
    )

    @contextlib.contextmanager
    def broken_release():
        yield
        raise PermitError("release failed")

    monkeypatch.setattr(backend, "_admission", broken_release)
    with pytest.raises(CloudRequestError, match="configuration"):
        backend.get_LLM_action("s", "u", OLLAMA_MODEL)
    assert trace.payload["raw_content"] == '{"score":42}'
    assert trace.payload["status"] == "failure"
    assert backend.call_records[-1]["completion_tokens"] == 5


def test_execution_config_sealed_and_cannot_override_at_run(tmp_path, monkeypatch):
    from integration.pokechamp import cli
    from integration.pokechamp.constants import WORKSPACE_ROOT

    monkeypatch.setattr(cli, "_assert_submodule_pins", lambda **kw: None)
    monkeypatch.setattr(cli, "_toolchain_snapshot", lambda: {})
    path = tmp_path / "execution.json"
    path.write_text(json.dumps(config()))
    value = b.plan(
        tmp_path,
        "seal-fixture",
        WORKSPACE_ROOT / "integration/pokechamp/configs/core-smoke.json",
        path,
    )
    path.write_text(json.dumps(config(3)))
    assert b.verify_plan(tmp_path / "benchmarks/seal-fixture")["execution"] == value["execution"]
    assert b.command("run", "seal-fixture", execution_config_path=path) == 2


def test_fatal_actor_signal_stops_account_before_attempt_drain(tmp_path, monkeypatch):
    value = {"execution": config(), "schedule": [{"slot_id": str(i)} for i in range(3)]}

    def fake(root, directory, value, slot, number, **kw):
        target = directory / "attempts" / f"{slot['slot_id']}-a{number}"
        target.mkdir(parents=True)
        if slot["slot_id"] == "0":
            b.signal_cancel(target, "auth")
            # Keep the fatal attempt alive as if its peer were draining a paid HTTP response.
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    with Permit(kw["broker_path"], OLLAMA_MODEL):
                        time.sleep(0.01)
                except PermitCancelled:
                    break
            else:
                pytest.fail("broker did not stop until fatal attempt returned")
            time.sleep(0.1)
            category = "auth"
        else:
            assert slot["slot_id"] == "1"
            deadline = time.monotonic() + 2
            while not (target / "cancel.json").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert (target / "cancel.json").exists()
            category = "peer_failure"
        return {
            "slot_id": slot["slot_id"],
            "number": number,
            "eligible": False,
            "category": category,
        }

    monkeypatch.setattr(b, "verify_plan", lambda *a, **kw: value)
    monkeypatch.setattr(b, "run_attempt", fake)
    run_parallel(tmp_path, tmp_path, value, [])
    batch = b.read_sealed(next((tmp_path / "batches").glob("*.json")))
    assert batch["stop_category"] == "auth"
    assert batch["not_dispatched_slots"] == ["2"]


def test_comparison_ignores_only_free_disk_observation():
    import copy

    from integration.pokechamp.concurrency_study import same_comparison_conditions

    first = {
        "source": {},
        "parent_files": {},
        "schedule": [],
        "teams": {},
        "environment": {"toolchain": {"free_disk_gib": 300, "node": "24"}, "llm": {"model": "a"}},
    }
    second = copy.deepcopy(first)
    second["environment"]["toolchain"]["free_disk_gib"] = 299
    assert same_comparison_conditions(first, second)
    second["environment"]["toolchain"]["node"] = "25"
    assert not same_comparison_conditions(first, second)
    second = copy.deepcopy(first)
    second["environment"]["llm"]["model"] = "b"
    assert not same_comparison_conditions(first, second)


def test_port_probe_permits_time_wait_but_rejects_live_listener():
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 8109))
    listener.listen()
    client = socket.create_connection(("127.0.0.1", 8109))
    peer, _ = listener.accept()
    with pytest.raises(OSError):
        check_ports([8109])
    peer.close()  # Server side initiates close, leaving its accepted socket in TIME_WAIT.
    client.close()
    listener.close()
    check_ports([8109])
