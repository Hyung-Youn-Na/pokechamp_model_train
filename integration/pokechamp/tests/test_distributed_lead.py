"""EX-042 routing, admission, staged collection and historical compatibility."""

import json
import sqlite3
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import httpx
import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp import cloud
from integration.pokechamp import distributed_lead as d
from integration.pokechamp import team_preview_run as run
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.tests.test_transport_retry import (
    call,
    make_backend,
    response,
)


def prepare(tmp_path):
    root = tmp_path / "prepared"
    return root, study.prepare(root, experiment_id="EX-042")


def test_sealed_allocation_and_legacy_schedule(tmp_path):
    root, v = prepare(tmp_path)
    assert study.verify_prepared(root) == v
    assert [
        {k: x for k, x in r.items() if k != "provider_id"} for r in v["schedule"]
    ] == study.schedule()
    expected = {"b01": {2, 3}, "b02": {2, 3}, "b03": {2, 4}, "b04": {1, 2}}
    for block, repeats in expected.items():
        rows = [r for r in v["schedule"] if r["block_id"] == block]
        assert Counter(r["provider_id"] for r in rows) == {"ollama": 4, "zai": 4}
        assert {
            r["repetition"] for r in rows if r["provider_id"] == "ollama"
        } == repeats
    first, rest = run.staged_schedule(v["schedule"])
    assert len(first) == 4 and len(rest) == 28
    assert {(r["provider_id"], r["paired_slot_id"]) for r in first} == {
        ("ollama", "b02-r2"),
        ("zai", "b03-r3"),
    }
    for provider in d.PROVIDERS:
        assert [r for r in rest if r["provider_id"] == provider] == [
            r for r in v["schedule"] if r["provider_id"] == provider and r not in first
        ]
    assert study.execution_protocol(v)["call_limit"] is None
    assert v["config"]["battle_watchdog_seconds"] is None
    assert (
        study.POLICY["call_limit"] == 8000
        and study.EXECUTION_PROTOCOL["stop_new_work_seconds"] == 20700
    )


def backend(v, root, row, handler, broker=None, role="p1"):
    actor = "/".join((v["experiment_id"], row["slot_id"] + "-a1", role))
    llm = make_backend(
        row["provider_id"],
        handler,
        env=dict(
            POKECHAMP_LEAD_STUDY_ROOT=str(root),
            POKECHAMP_IO_ACTOR=actor,
            **(
                {"POKECHAMP_PERMIT_SOCKET": str(broker.path_for(row))} if broker else {}
            ),
        ),
    )
    llm._request_context = lambda: dict(
        call_role="self_action", identity=dict(decision_seq=1)
    )
    return llm


def test_real_mock_http_4_plus_4_keys_retries_and_permit_release(tmp_path, monkeypatch):
    root, v = prepare(tmp_path)
    lock = threading.Lock()
    active = Counter()
    maximum = Counter()
    total = 0
    wires = []
    # Hold the first eight calls until all eight have actually entered HTTP.
    barrier = threading.Barrier(8)
    monkeypatch.setattr(cloud, "wait_retry", lambda llm, delay: time.sleep(0.02))
    with ExitStack() as stack:
        brokers = d.Brokers(stack, tmp_path, v)

        def task(item):
            nonlocal total
            row, index = item
            count = 0

            def handler(request):
                nonlocal count, total
                count += 1
                wire = json.loads(request.content)
                assert request.headers["authorization"] == "Bearer test-secret-marker"
                if row["provider_id"] == "zai":
                    assert (
                        str(request.url)
                        == "https://zai.example.test/v4/chat/completions"
                    )
                    assert "seed" not in wire and wire["temperature"] == 0
                else:
                    assert str(request.url) == "https://ollama.com/api/chat"
                    assert wire["options"]["seed"] == 100
                with lock:
                    active[row["provider_id"]] += 1
                    maximum[row["provider_id"]] = max(
                        maximum[row["provider_id"]], active[row["provider_id"]]
                    )
                    total = max(total, sum(active.values()))
                    wires.append((row["slot_id"], wire))
                if count == 1:
                    barrier.wait(timeout=20)
                time.sleep(0.02)
                with lock:
                    active[row["provider_id"]] -= 1
                if count == 1:
                    raise httpx.ConnectError("fixture")
                return response(row["provider_id"])

            llm = backend(v, root, row, handler, brokers)
            assert call(llm)[1]
            assert llm.call_records[0]["retry_outcome"] == "recovered"
            return llm.call_records[0]

        rows = [
            r
            for p in d.PROVIDERS
            for r in [x for x in v["schedule"] if x["provider_id"] == p][:4]
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(task, enumerate_rows(rows)))
        snapshot = brokers.snapshot()
        assert maximum == {"ollama": 4, "zai": 4} and total == 8
        assert not sum(snapshot["active_at_close"].values())
        assert all(
            s["maximum_account_permits"] == 4 for s in snapshot["providers"].values()
        )
        assert len([e for e in snapshot["events"] if e["event"] == "grant"]) == 16
    usage = study.shared.usage(root)
    assert usage["reserved_calls"] == 16 and usage["known_connection_failures"] == 8
    assert usage["logical_requests"] == 8 and usage["remaining_calls"] is None
    clock = b.read_sealed(root / "cloud-clock.json")
    assert clock["stop_new_work_at"] - clock["first_dispatch_at"] == 20100
    for row in rows:
        pair = [wire for slot, wire in wires if slot == row["slot_id"]]
        assert len(pair) == 2 and pair[0] == pair[1]
    assert len(records) == 8


def enumerate_rows(rows):
    return [(row, i) for i, row in enumerate(rows)]


@pytest.mark.parametrize("provider", d.PROVIDERS)
def test_first_429_blocks_both_providers(tmp_path, provider):
    root, v = prepare(tmp_path)
    sent = []
    row = next(r for r in v["schedule"] if r["provider_id"] == provider)

    def handler(request):
        sent.append(request)
        return httpx.Response(429, json={"error": "rate limited"})

    with pytest.raises(cloud.CloudRequestError):
        call(backend(v, root, row, handler))
    assert b.read_sealed(root / "halt.json")["http_status"] == 429
    for p in d.PROVIDERS:
        row = next(r for r in v["schedule"] if r["provider_id"] == p)
        with pytest.raises(cloud.CloudRequestError):
            call(backend(v, root, row, handler))
    assert len(sent) == 1


def test_unlimited_8001_deadline_halt_and_clock_reset(tmp_path, monkeypatch):
    root, v = prepare(tmp_path)
    row = v["schedule"][0]
    actor = "/".join((v["experiment_id"], row["slot_id"] + "-a1", "p1"))
    settings = v["provider_configs"][row["provider_id"]]
    payload = dict(
        request=dict(settings, call_role="self_action", identity=dict(decision_seq=1))
    )
    now = time.time()
    study.reserve(root, actor, payload, now=now)
    # Exercise the actual SQLite count branch without producing 8,000 large prompt files.
    with sqlite3.connect(root / "ledger.sqlite") as db:
        db.executemany(
            "INSERT INTO reservations VALUES (?,?,?,?)",
            [
                (
                    i,
                    actor,
                    now,
                    json.dumps(
                        dict(
                            request=dict(
                                settings,
                                call_role="self_action",
                                identity=dict(decision_seq=i),
                            )
                        )
                    ),
                )
                for i in range(2, 8001)
            ],
        )
    payload["request"]["identity"]["decision_seq"] = 8001
    path = study.reserve(root, actor, payload, now=now + 1)
    assert b.read_sealed(path)["number"] == 8001
    payload["request"]["identity"]["decision_seq"] = 8002
    with pytest.raises(cloud.CloudRequestError, match="deadline"):
        study.reserve(root, actor, payload, now=now + 20100)
    original = (root / "cloud-clock.json").read_bytes()
    (root / "cloud-clock.json").unlink()
    with pytest.raises(cloud.CloudRequestError, match="clock removed"):
        study.reserve(root, actor, payload, now=now + 2)
    (root / "cloud-clock.json").write_bytes(original)
    study.halt_on_429(root)
    with pytest.raises(cloud.CloudRequestError, match="halted"):
        study.reserve(root, actor, payload, now=now + 2)


@pytest.mark.parametrize("gate_passed,expected", [(True, 32), (False, 4)])
def test_four_game_barrier_provider_queues_and_no_transfer(
    tmp_path, monkeypatch, gate_passed, expected
):
    root, v = prepare(tmp_path)
    observed = []
    gate_done = False
    monkeypatch.setattr(study, "verify_prepared", lambda _: v)
    monkeypatch.setattr(study, "collection_deadline", lambda _: None)
    first, _ = run.staged_schedule(v["schedule"])

    def worker(data, directory, value, slot, number, **kw):
        assert slot in first or gate_done
        assert (kw["port"] < 8104) == (slot["provider_id"] == "ollama")
        observed.append(slot)
        return dict(slot=slot, slot_id=slot["slot_id"], eligible=True, category=None)

    def gate(*args):
        nonlocal gate_done
        assert len(observed) == 4
        gate_done = True
        return dict(passed=gate_passed)

    with ExitStack() as stack:
        brokers = d.Brokers(stack, tmp_path, v)
        attempts = run.execute_schedule(
            root, tmp_path / "data", v, brokers, worker=worker, gate_check=gate
        )
    assert len(attempts) == expected
    assert len({r["slot_id"] for r in observed}) == expected


def test_gate_accepts_recovered_connection_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "audit", lambda *a: dict(ledger_intents=6))
    monkeypatch.setattr(
        study.shared,
        "usage",
        lambda _: dict(uncertain=2, known_connection_failures=2, reserved_calls=6),
    )
    attempts = [dict(eligible=True) for _ in range(4)]
    result = run.inspect_pair(
        tmp_path,
        attempts,
        dict(registered_experiment="EX-042"),
        dict(active_at_close={}, events=[]),
    )
    assert result["passed"]


def test_provider_projection_rejects_wrong_actor_and_settings(tmp_path):
    root, v = prepare(tmp_path)
    row = next(r for r in v["schedule"] if r["provider_id"] == "ollama")
    actor = "/".join((v["experiment_id"], row["slot_id"] + "-a1", "p1"))
    with pytest.raises(ValueError):
        d.for_actor(v, actor + "/wrong")
    bad = dict(
        request=dict(
            v["provider_configs"]["zai"],
            call_role="self_action",
            identity=dict(decision_seq=1),
        )
    )
    with pytest.raises(cloud.CloudRequestError, match="provider mismatch"):
        study.reserve(root, actor, bad)
    env = dict(
        POKECHAMP_PROVIDER="zai",
        ZAI_BASE_URL=v["provider_configs"]["zai"]["base_url"],
        OLLAMA_API_KEY="ollama-key",
        ZAI_API_KEY="zai-key",
    )
    before = dict(env)
    for p in d.PROVIDERS:
        selected = d.environment(
            v["provider_configs"][p], require_key=True, environ=env
        )
        assert selected["POKECHAMP_PROVIDER"] == p
        assert selected["ZAI_API_KEY" if p == "ollama" else "OLLAMA_API_KEY"] == ""
    assert env == before


def test_execution_registration_binding_duplicate_and_clock_limits(
    tmp_path, monkeypatch
):
    root, value = prepare(tmp_path)
    # Use the cloud registration path with local-only, explicitly stubbed credentials.
    value = dict(
        value,
        transport="cloud",
        experiment_id="ex042-cloud",
        execution_authorized=False,
    )
    for p in d.PROVIDERS:
        value["provider_executions"][p] = study.execution(
            "cloud", 4, provider=p, enriched=True
        )
    value["execution"] = study.execution("cloud", 8, enriched=True)
    monkeypatch.setattr(study, "verify_prepared", lambda _: value)
    monkeypatch.setattr(d, "STUDY_LINK", tmp_path / "binding.json")
    approval = tmp_path / "approval.md"
    approval.write_text("Local registration fixture; external model calls prohibited.")
    reg = study.register_execution(root, approval_record=approval)
    assert reg["call_limit"] is None and reg["stop_new_work_seconds"] == 20100
    assert reg["cleanup_seconds"] == 21600
    with pytest.raises(FileExistsError):
        study.register_execution(root, approval_record=approval)
    other = tmp_path / "other"
    other.mkdir()
    b.seal_json(other / "plan.json", value)
    with pytest.raises(ValueError, match="already bound"):
        study.register_execution(other, approval_record=approval)


def test_final_cleanup_revokes_owned_orphan_without_claiming_response(tmp_path):
    import socket

    from integration.pokechamp.permits import PermitBroker

    with PermitBroker(
        tmp_path / "orphan.sock", 4, {"glm-5.3-flash": 4}, revoke_on_close=True
    ) as broker:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(broker.path))
        sock.sendall(b'{"model":"glm-5.3-flash"}\n')
        assert json.loads(sock.recv(4096))["granted"]
        sock.close()
        limit = time.monotonic() + 2
        while not any(e["event"] == "orphan" for e in broker.snapshot()["events"]):
            assert time.monotonic() < limit
            time.sleep(0.01)
    snapshot = broker.snapshot()
    assert not sum(snapshot["active_at_close"].values())
    assert snapshot["events"][-1]["remote_outcome"] == "unconfirmed"
    assert not broker.path.exists()


def test_time_expiry_prevents_both_provider_http(tmp_path, monkeypatch):
    root, value = prepare(tmp_path)
    row = value["schedule"][0]
    first = backend(value, root, row, lambda _: response(row["provider_id"]))
    assert call(first)[1]
    clock = b.read_sealed(root / "cloud-clock.json")
    sent = []
    monkeypatch.setattr(time, "time", lambda: clock["stop_new_work_at"])
    for provider in d.PROVIDERS:
        row = next(r for r in value["schedule"] if r["provider_id"] == provider)
        with pytest.raises(cloud.CloudRequestError):
            call(backend(value, root, row, lambda request: sent.append(request)))
    assert sent == []


def test_cloud_worker_verification_needs_only_assigned_key(tmp_path, monkeypatch):
    root, value = prepare(tmp_path)
    # Fresh cloud preparation from a local settings dictionary, with no HTTP.
    from integration.pokechamp import dotenv

    monkeypatch.setattr(dotenv, "load_workspace_credential", lambda **kwargs: None)
    monkeypatch.setenv("ZAI_BASE_URL", "https://zai.example.test/v4")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-fixture")
    monkeypatch.setenv("ZAI_API_KEY", "zai-fixture")
    target = tmp_path / "cloud-prepared"
    study.prepare(target, transport="cloud", experiment_id="EX-042")
    assert study.verify_prepared(target)
    for provider in d.PROVIDERS:
        other = "ZAI_API_KEY" if provider == "ollama" else "OLLAMA_API_KEY"
        with monkeypatch.context() as patcher:
            patcher.setenv(other, "")
            assert study.verify_prepared(target, provider_id=provider)
            with pytest.raises(cloud.CloudConfigurationError):
                study.verify_prepared(target)


def test_first_failed_gate_game_stops_peer_requests_before_other_games_finish(
    tmp_path, monkeypatch
):
    root, value = prepare(tmp_path)
    monkeypatch.setattr(study, "verify_prepared", lambda _: value)
    monkeypatch.setattr(study, "collection_deadline", lambda _: None)
    first, _ = run.staged_schedule(value["schedule"])
    failed = first[0]["slot_id"]
    observed = []

    def worker(data, directory, prepared, row, number, **kwargs):
        assert row in first
        if row["slot_id"] != failed:
            limit = time.monotonic() + 5
            while not (root / "halt.json").exists():
                assert time.monotonic() < limit
                time.sleep(0.01)
            observed.append(row["provider_id"])
        return dict(
            slot=row, slot_id=row["slot_id"], eligible=False, category="timeout"
        )

    with ExitStack() as stack:
        brokers = d.Brokers(stack, tmp_path, value)
        attempts = run.execute_schedule(
            root,
            tmp_path / "data",
            value,
            brokers,
            worker=worker,
            gate_check=lambda *args: dict(passed=False),
        )
    assert len(attempts) == 4 and len(observed) == 3
    assert set(observed) == set(d.PROVIDERS)
    assert b.read_sealed(root / "halt.json")["category"] == "first_pair_failed"


def test_completion_requires_gate_and_timely_cleanup(tmp_path):
    from integration.pokechamp.distributed_lead_report import completion_controls

    assert not any(completion_controls(tmp_path).values())
    b.seal_json(tmp_path / "run-claim.json", dict(execution_protocol=d.PROTOCOL))
    b.seal_json(tmp_path / "first-pair-check.json", dict(passed=True, errors=[]))
    b.seal_json(tmp_path / "cloud-clock.json", dict(cleanup_deadline=21600))
    cleanup = dict(
        ports_closed=list(range(8100, 8108)),
        socket_removed=True,
        remaining_permits=0,
        permits=dict(active_at_close={}, events=[]),
        completed_at=21600,
    )
    b.seal_json(tmp_path / "cleanup.json", cleanup)
    assert all(completion_controls(tmp_path).values())
    # The same 32 valid match results cannot hide a cleanup deadline overrun.
    for name in ("cleanup.json", "cleanup.json.sha256"):
        (tmp_path / name).unlink()
    b.seal_json(tmp_path / "cleanup.json", dict(cleanup, completed_at=21601))
    assert not completion_controls(tmp_path)["cleanup_in_time"]
