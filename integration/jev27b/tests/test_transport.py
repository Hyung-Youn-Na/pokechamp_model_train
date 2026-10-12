"""CPU-only wire, crash persistence and duplicate-inference boundary tests."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading

import httpx
import pytest

from integration.jev27b import client, server
from integration.jev27b.config import MODEL_ID, REVISION
from integration.jev27b.formatting import InputTooLong

IDENTITY = "1" * 64


def payload():
    return {"model": MODEL_ID, "state": {"turn": 3, "observation": "한글 관측"},
            "questions": {"action": {"type": "choice", "instructions": "Choose one.",
                         "criteria": {"move:2": {"kind": "move", "slot": 2},
                                      "move:1": {"kind": "move", "slot": 1}}}}}


class FakeModel:
    def __init__(self, *, block=None, error=None, illegal=False):
        self.identity = IDENTITY
        self.calls = 0
        self.active = 0
        self.maximum_active = 0
        self.lock = threading.Lock()
        self.entered = threading.Event()
        self.block = block
        self.error = error
        self.illegal = illegal

    def metadata(self):
        return dict(model=MODEL_ID, revision=REVISION, loaded=True,
                    serving_identity=self.identity, serving_config={"max_input_tokens": 32768})

    def evaluate(self, body):
        with self.lock:
            self.calls += 1
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        self.entered.set()
        try:
            if self.block is not None and not self.block.wait(5):
                raise RuntimeError("test model gate did not open")
            if self.error is not None:
                raise self.error
            name, question = next(iter(body["questions"].items()))
            ids = list(question["criteria"])
            return dict(model=MODEL_ID, answers={name: dict(type="choice",
                        choice="unknown" if self.illegal else ids[0],
                        probabilities={key: float(key == ids[0]) for key in ids}, confidence=1)},
                        usage=dict(input_tokens=123, output_tokens=0))
        finally:
            with self.lock:
                self.active -= 1


@contextmanager
def running_server(tmp_path, model=None):
    service = server.LocalService(model or FakeModel(), tmp_path)
    httpd = server.LocalHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield service, f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)
        service.close()


def call_service(service, request_id="request-1", body=None):
    raw = client.request_bytes(payload() if body is None else body)
    return service.evaluate(raw, request_id=request_id, body_sha256=hashlib.sha256(raw).hexdigest(),
                            expected_identity=IDENTITY)


def response_for(request, *, identity=IDENTITY, choice="move:2", status=200):
    digest = hashlib.sha256(request.content).hexdigest()
    request_id = request.headers["X-Request-ID"]
    body = dict(model=MODEL_ID, answers={"action": {"type": "choice", "choice": choice}}, usage={},
                transport=dict(protocol=client.PROTOCOL, request_id=request_id, body_sha256=digest,
                               serving_identity=identity, inference_calls=1,
                               inference_id=hashlib.sha256((identity + "\0" + request_id + "\0" + digest).encode()).hexdigest()))
    return httpx.Response(status, json=body,
                          headers={"X-Request-ID": request_id, "X-Body-SHA256": digest,
                                   "X-Serving-Identity": identity, "X-Cache-Reused": "1"})


def test_wire_bytes_keep_full_order_and_do_not_mutate():
    body = payload()
    original = copy.deepcopy(body)
    raw = client.request_bytes(body)
    assert raw.index(b"move:2") < raw.index(b"move:1")
    assert "한글 관측".encode() in raw
    assert json.loads(raw) == original == body
    del body["model"]
    assert client.request_bytes(body) == raw


@pytest.mark.parametrize("endpoint", ["https://127.0.0.1:18782", "http://localhost:18782",
    "http://8.8.8.8:18782", "http://127.0.0.1:18782/other", "http://user@127.0.0.1:18782",
    "http://127.0.0.1:18782?proxy=yes", "http://127.0.0.1", "http://127.0.0.1:0"])
def test_nonlocal_or_ambiguous_endpoints_refused(endpoint):
    with pytest.raises(ValueError):
        client.LocalClient(endpoint)


def test_concurrent_same_and_different_ids_forward_once_each(tmp_path):
    unblock = threading.Event()
    model = FakeModel(block=unblock)
    service = server.LocalService(model, tmp_path)
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(call_service, service, request_id) for request_id in
                       ("shared", "shared", "second", "shared", "third", "second")]
            assert model.entered.wait(2)
            assert model.calls == model.active == 1
            unblock.set()
            results = [future.result(5) for future in futures]
        assert all(status == 200 for status, _, _ in results)
        assert results[0][1] == results[1][1] == results[3][1]
        assert results[2][1] == results[5][1]
        assert model.calls == 3 and model.maximum_active == 1
        starts = service.registry.db.execute("SELECT request_id,COUNT(*) FROM events WHERE kind='inference_started' GROUP BY request_id").fetchall()
        assert sorted(tuple(row) for row in starts) == [("second", 1), ("shared", 1), ("third", 1)]
        assert sum(reused for _, _, reused in results) == 3
    finally:
        unblock.set()
        service.close()


def test_completion_reused_after_registry_reopen(tmp_path):
    original_model = FakeModel()
    service = server.LocalService(original_model, tmp_path)
    initial = call_service(service)
    service.close()
    reloaded_model = FakeModel()
    reloaded = server.LocalService(reloaded_model, tmp_path)
    try:
        repeated = call_service(reloaded)
        assert repeated[:2] == initial[:2] and repeated[2] is True
        assert original_model.calls == 1 and reloaded_model.calls == 0
        row = reloaded.registry.get("request-1")
        assert row["inference_calls"] == 1
        assert row["response_sha256"] == hashlib.sha256(initial[1]).hexdigest()
    finally:
        reloaded.close()


@pytest.mark.parametrize("started", [False, True])
def test_crashed_process_reservation_is_never_reexecuted(tmp_path, started):
    code = """
import hashlib, os, sys
from pathlib import Path
from integration.jev27b.server import RequestRegistry
raw = b'{"frozen":"input"}'
r = RequestRegistry(Path(sys.argv[1]) / 'server/requests.sqlite3', '1' * 64)
r.accept('crashed', raw, hashlib.sha256(raw).hexdigest(), '2' * 64)
if sys.argv[2] == 'True': r.start('crashed')
os._exit(9)
"""
    completed = subprocess.run([sys.executable, "-c", code, str(tmp_path), str(started)],
                               cwd=Path(__file__).resolve().parents[3], capture_output=True)
    assert completed.returncode == 9, completed.stderr.decode()
    model = FakeModel()
    service = server.LocalService(model, tmp_path)
    try:
        assert service.health()["halt"]["category"] == "interrupted_inference"
        assert service.health()["ready"] is False
        assert call_service(service)[0] == 503 and model.calls == 0
        assert service.registry.get("crashed")["inference_calls"] == int(started)
    finally:
        service.close()


def test_request_journal_has_one_process_owner(tmp_path):
    registry = server.RequestRegistry(tmp_path / "journal.sqlite3", IDENTITY)
    try:
        with pytest.raises(server.RegistryError, match="already owned"):
            server.RequestRegistry(tmp_path / "journal.sqlite3", IDENTITY)
    finally:
        registry.close()


def test_same_id_with_changed_body_409_no_extra_inference(tmp_path):
    model = FakeModel()
    service = server.LocalService(model, tmp_path)
    try:
        assert call_service(service)[0] == 200
        changed = payload()
        changed["state"]["turn"] = 4
        status, raw, reused = call_service(service, body=changed)
        assert status == 409 and not reused
        assert json.loads(raw)["error"]["category"] == "request_id_conflict"
        assert call_service(service)[2] is True
        assert model.calls == 1
    finally:
        service.close()


@pytest.mark.parametrize("damage", ["request_body", "response_body"])
def test_journal_corruption_halts_without_reinference(tmp_path, damage):
    service = server.LocalService(FakeModel(), tmp_path)
    call_service(service)
    path = service.registry.path
    service.close()
    with sqlite3.connect(path) as database:
        database.execute(f"UPDATE requests SET {damage}=?", (b"changed",))
    model = FakeModel()
    reopened = server.LocalService(model, tmp_path)
    try:
        assert reopened.health()["halt"]["category"] == "journal_integrity"
        assert call_service(reopened)[0] == 503 and model.calls == 0
    finally:
        reopened.close()


def test_wire_hash_failure_prevents_any_inference(tmp_path):
    model = FakeModel()
    service = server.LocalService(model, tmp_path)
    try:
        result = service.evaluate(client.request_bytes(payload()), request_id="bad-hash",
                                  body_sha256="0" * 64, expected_identity=IDENTITY)
        assert result[0] == 400 and model.calls == 0
        assert service.health()["halt"]["category"] == "request_integrity"
    finally:
        service.close()


def test_overlimit_halts_durably_and_never_retries(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    model = FakeModel(error=InputTooLong(32769, 32768))
    with running_server(tmp_path, model) as (service, endpoint):
        with client.LocalClient(endpoint, expected_identity=IDENTITY) as local:
            with pytest.raises(client.LocalRequestError) as caught:
                local.evaluate(payload(), request_id="long", retries=3)
            assert caught.value.category == "input_too_long" and not caught.value.retryable
            assert local.last_transport["status_code"] == 422
            assert service.registry.get("long")["inference_calls"] == 1
            with pytest.raises(client.LocalRequestError):
                local.evaluate(payload(), request_id="next")
        assert model.calls == 1 and not sleeps
    reloaded = server.LocalService(FakeModel(), tmp_path)
    try:
        assert reloaded.health()["halt"]["category"] == "input_too_long"
        assert call_service(reloaded)[0] == 503
    finally:
        reloaded.close()


def test_oom_halts_without_repeated_model_call(tmp_path):
    class OutOfMemoryError(RuntimeError):
        pass
    model = FakeModel(error=OutOfMemoryError("fake CUDA OOM"))
    service = server.LocalService(model, tmp_path)
    try:
        assert call_service(service)[0] == 503
        assert service.health()["halt"]["category"] == "out_of_memory"
        assert call_service(service)[0] == 503 and model.calls == 1
    finally:
        service.close()


def test_real_http_identity_raw_records_and_completed_replay(tmp_path):
    with running_server(tmp_path) as (service, endpoint):
        records = []
        with client.LocalClient(endpoint, record=records.append) as local:
            health = local.health()
            assert health["revision"] == REVISION and health["identity"] == IDENTITY
            first = local.evaluate(payload(), request_id="http")
            initial_record = copy.deepcopy(local.last_transport)
            second = local.evaluate(payload(), request_id="http")
            assert first == second
            assert not initial_record["cache_reused"] and local.last_transport["cache_reused"]
            assert initial_record["request_body"].encode() == client.request_bytes(payload())
            assert json.loads(initial_record["raw_body"]) == first
            assert len(records) == 3 and service.model.calls == 1


def test_timed_out_http_request_finishes_once_and_retry_reuses(tmp_path):
    unblock = threading.Event()
    model = FakeModel(block=unblock)
    with running_server(tmp_path, model) as (service, endpoint):
        with client.LocalClient(endpoint, expected_identity=IDENTITY, timeout=0.1) as impatient:
            with pytest.raises(client.LocalRequestError) as caught:
                impatient.evaluate(payload(), request_id="late")
            assert caught.value.category == "timeout"
            assert model.entered.is_set() and model.calls == 1
        with ThreadPoolExecutor(max_workers=1) as pool:
            with client.LocalClient(endpoint, expected_identity=IDENTITY) as reconnect:
                future = pool.submit(reconnect.evaluate, payload(), request_id="late")
                unblock.set()
                assert future.result(5)["transport"]["inference_calls"] == 1
                assert reconnect.last_transport["cache_reused"] is True
        assert model.calls == 1


def test_illegal_model_choice_is_delivered_for_game_isolation(tmp_path):
    with running_server(tmp_path, FakeModel(illegal=True)) as (service, endpoint):
        with client.LocalClient(endpoint, expected_identity=IDENTITY) as local:
            result = local.evaluate(payload(), request_id="illegal")
            assert result["answers"]["action"]["choice"] == "unknown"
            assert service.health()["ready"] is True


def test_health_identity_drift_halts_service_before_new_forward(tmp_path):
    model = FakeModel()
    with running_server(tmp_path, model) as (service, endpoint):
        with client.LocalClient(endpoint, expected_identity=IDENTITY) as local:
            assert local.health()["ready"] is True
            model.identity = "2" * 64
            with pytest.raises(client.LocalRequestError) as caught:
                local.health()
            assert caught.value.category == "halted"
            with pytest.raises(client.LocalRequestError):
                local.evaluate(payload(), request_id="drift")
        assert model.calls == 0
        assert service.registry.halt_state["category"] == "serving_identity"


def test_reloaded_different_identity_cannot_replay_or_infer(tmp_path):
    service = server.LocalService(FakeModel(), tmp_path)
    call_service(service)
    service.close()
    changed = FakeModel()
    changed.identity = "2" * 64
    reloaded = server.LocalService(changed, tmp_path)
    try:
        assert reloaded.health()["ready"] is False
        assert reloaded.health()["halt"]["category"] == "serving_identity"
        assert changed.calls == 0
    finally:
        reloaded.close()


def test_default_600_seconds_and_one_physical_attempt():
    attempts = []
    def transport(request):
        attempts.append(request)
        assert all(value == 600 for value in request.extensions["timeout"].values())
        raise httpx.ReadTimeout("test", request=request)
    with client.LocalClient(expected_identity=IDENTITY, transport=httpx.MockTransport(transport)) as local:
        with pytest.raises(client.LocalRequestError) as caught:
            local.evaluate(payload(), request_id="once")
        assert caught.value.retryable and len(attempts) == 1
        assert local.last_transport["status_code"] is None
        assert local.last_transport["request_id"] == "once"
        assert local.last_transport["elapsed_seconds"] >= 0


def test_three_retries_keep_exact_wire_bytes_and_request_id(monkeypatch):
    attempts, sleeps, records = [], [], []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    def transport(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("test timeout", request=request)
        if len(attempts) == 2:
            raise httpx.ConnectError("test connect", request=request)
        if len(attempts) == 3:
            return httpx.Response(503, content=b"temporarily unavailable")
        return response_for(request)
    with client.LocalClient(expected_identity=IDENTITY, record=records.append,
                            transport=httpx.MockTransport(transport)) as local:
        result = local.evaluate(payload(), request_id="stable-id", retries=3)
        assert result["answers"]["action"]["choice"] == "move:2"
    assert len(attempts) == 4 and sleeps == [10, 30, 60]
    assert len({request.content for request in attempts}) == 1
    assert {request.headers["X-Request-ID"] for request in attempts} == {"stable-id"}
    assert len({request.headers["X-Body-SHA256"] for request in attempts}) == 1
    assert [record["attempt"] for record in records] == [1, 2, 3, 4]


def test_retry_exhaustion_stops_after_four_posts(monkeypatch):
    attempts, sleeps = [], []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    def transport(request):
        attempts.append(request)
        return httpx.Response(429, json={"error": "busy"})
    with client.LocalClient(expected_identity=IDENTITY, transport=httpx.MockTransport(transport)) as local:
        with pytest.raises(client.LocalRequestError) as caught:
            local.evaluate(payload(), request_id="four", retries=3)
    assert caught.value.status_code == 429 and len(attempts) == 4
    assert sleeps == [10, 30, 60]


@pytest.mark.parametrize("status", [301, 400, 401, 403, 409, 422])
def test_permanent_http_failures_never_retry(status, monkeypatch):
    attempts, sleeps = [], []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    def transport(request):
        attempts.append(request)
        return httpx.Response(status, json={"error": "permanent"})
    with client.LocalClient(expected_identity=IDENTITY, transport=httpx.MockTransport(transport)) as local:
        with pytest.raises(client.LocalRequestError) as caught:
            local.evaluate(payload(), request_id="permanent", retries=3)
    assert not caught.value.retryable and len(attempts) == 1 and not sleeps


def test_persisted_halt_503_never_retries(monkeypatch):
    attempts, sleeps = [], []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    def transport(request):
        attempts.append(request)
        return httpx.Response(503, json={"error": {"category": "out_of_memory", "halted": True}})
    with client.LocalClient(expected_identity=IDENTITY, transport=httpx.MockTransport(transport)) as local:
        with pytest.raises(client.LocalRequestError) as caught:
            local.evaluate(payload(), request_id="halted", retries=3)
    assert caught.value.category == "out_of_memory" and len(attempts) == 1 and not sleeps


@pytest.mark.parametrize("part", ["header", "request_id", "body_sha256", "serving_identity", "protocol",
                                  "inference_id", "inference_calls"])
def test_response_identity_tampering_never_retries(part, monkeypatch):
    sleeps = []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    def transport(request):
        response = response_for(request)
        if part == "header":
            response.headers["X-Request-ID"] = "other-id"
            return response
        body = response.json()
        body["transport"][part] = "changed"
        return httpx.Response(200, json=body, headers=response.headers)
    with client.LocalClient(expected_identity=IDENTITY, transport=httpx.MockTransport(transport)) as local:
        with pytest.raises(client.LocalRequestError) as caught:
            local.evaluate(payload(), request_id="identity", retries=3)
    assert caught.value.category == "response_identity" and not caught.value.retryable and not sleeps


def test_malformed_json_rejected_before_model_call(tmp_path):
    model = FakeModel()
    service = server.LocalService(model, tmp_path)
    raw = b'{"model":"autotrust/JEV-27B","model":"other","state":{},"questions":{}}'
    try:
        result = service.evaluate(raw, request_id="duplicate-keys", body_sha256=hashlib.sha256(raw).hexdigest(),
                                  expected_identity=IDENTITY)
        assert result[0] == 503 and model.calls == 0
        assert service.registry.halt_state["category"] == "input_validation"
    finally:
        service.close()


def test_metadata_exception_halts_and_is_reported_in_health(tmp_path):
    model = FakeModel()
    service = server.LocalService(model, tmp_path)
    try:
        def unavailable():
            raise RuntimeError("metadata cannot be read")
        model.metadata = unavailable
        health = service.health()
        assert health["ready"] is False and health["halt"]["category"] == "model_integrity"
        assert model.calls == 0
    finally:
        service.close()


def test_local_protocol_fault_does_not_retry(monkeypatch):
    attempts, sleeps = [], []
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    def transport(request):
        attempts.append(request)
        raise httpx.LocalProtocolError("invalid local request", request=request)
    with client.LocalClient(expected_identity=IDENTITY, transport=httpx.MockTransport(transport)) as local:
        with pytest.raises(client.LocalRequestError) as caught:
            local.evaluate(payload(), request_id="local-protocol", retries=3)
    assert not caught.value.retryable and len(attempts) == 1 and not sleeps
