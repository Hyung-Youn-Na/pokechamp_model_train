"""C-038 transport tests: real SDK serialization with no provider network."""

import json
import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import ollama
import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp import cloud
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.concurrency_metrics import request_metrics
from integration.pokechamp.constants import OLLAMA_MODEL
from integration.pokechamp.permits import PermitBroker
from integration.pokechamp.providers import ZaiChatClient, verify_provider
from integration.pokechamp.transport_policy import CONNECT as CURRENT
from integration.pokechamp.transport_policy import LEGACY, drain_seconds


def make_backend(provider, handler, *, env=None, trace=None):
    environment = dict(
        POKECHAMP_TRANSPORT_POLICY=CURRENT, POKECHAMP_PROVIDER=provider, OLLAMA_API_KEY="test-secret-marker",
        ZAI_API_KEY="test-secret-marker", ZAI_BASE_URL="https://zai.example.test/v4",
    )
    environment.update(env or {})

    def factory(**kw):
        if provider == "zai":
            return ZaiChatClient(**kw, api_key="test-secret-marker", transport=httpx.MockTransport(handler))
        return ollama.Client(**kw, transport=httpx.MockTransport(handler))

    return cloud.OllamaCloudBackend(environ=environment, client_factory=factory, trace_sink=trace)


def response(provider):
    if provider == "zai":
        return httpx.Response(200, json=dict(model=OLLAMA_MODEL, choices=[dict(
            message=dict(content='{"ok":true}', reasoning_content="fixture reasoning"),
            finish_reason="stop")], usage=dict(prompt_tokens=5, completion_tokens=2)))
    return httpx.Response(200, json=dict(model=OLLAMA_MODEL,
        message=dict(role="assistant", content='{"ok":true}', thinking="fixture reasoning"),
        done=True, prompt_eval_count=5, eval_count=2))


def call(llm):
    return llm.get_LLM_action("same system", "same user", OLLAMA_MODEL, temperature=0, seed=100)


@pytest.mark.parametrize("provider", ["ollama", "zai"])
@pytest.mark.parametrize("failures", [0, 1, 2, 3])
def test_recovery_exhaustion_wire_and_logical_trace(provider, failures, monkeypatch):
    sent, traces, waits = [], [], []

    def handler(request):
        sent.append(request)
        if len(sent) <= failures:
            try:
                raise OSError("internal test-secret-marker")
            except OSError as error:
                raise httpx.ConnectError("connection test-secret-marker", request=request) from error
        return response(provider)

    llm = make_backend(provider, handler, trace=SimpleNamespace(record_llm_call=lambda **p: traces.append(p)))
    monkeypatch.setattr(cloud, "wait_retry", lambda backend, delay: waits.append(delay))
    if failures == 3:
        with pytest.raises(cloud.CloudRequestError):
            call(llm)
        assert llm.failure_event.is_set()
    else:
        assert call(llm)[0] == '{"ok":true}'
        assert llm.terminal_error is None and not llm.failure_event.is_set()
    count = min(3, failures + 1)
    assert len(sent) == count and len(traces) == len(llm.call_records) == 1
    assert waits == [1.0, 3.0][:min(failures, 2)]
    assert all(r.content == sent[0].content and r.url == sent[0].url for r in sent)
    assert all(r.extensions["timeout"] == dict(connect=300, read=600, write=300, pool=300) for r in sent)
    request = traces[0]["request"]
    assert request["transport_policy_version"] == CURRENT
    assert request["http_attempt_count"] == count
    assert [a["http_attempt_number"] for a in request["http_attempts"]] == list(range(1, count + 1))
    assert "test-secret-marker" not in json.dumps(traces + llm.call_records)
    if failures:
        assert request["http_attempts"][0]["causes"]
    metrics = request_metrics(traces)
    assert metrics["logical_requests"] == 1 and metrics["observed_http_calls"] == count
    assert metrics["http_attempt_count"] == count
    assert llm.prompt_tokens == (0 if failures == 3 else 5)


@pytest.mark.parametrize("provider", ["ollama", "zai"])
@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout,
                                    httpx.PoolTimeout, httpx.ReadError, ConnectionError, 429, 401, 500])
def test_excluded_failures_have_one_attempt(provider, error):
    sent = []

    def handler(request):
        sent.append(request)
        if isinstance(error, int):
            return httpx.Response(error, json={"error": "fixture"})
        raise error("fixture")

    llm = make_backend(provider, handler)
    with pytest.raises(cloud.CloudRequestError):
        call(llm)
    with pytest.raises(cloud.CloudRequestError):
        call(llm)
    assert len(sent) == 1


@pytest.mark.parametrize("provider", ["ollama", "zai"])
def test_legacy_real_timeout_no_retry(provider):
    sent = []

    def handler(request):
        sent.append(request)
        raise httpx.ConnectError("legacy")

    llm = make_backend(provider, handler, env={"POKECHAMP_TRANSPORT_POLICY": LEGACY})
    with pytest.raises(cloud.CloudRequestError):
        call(llm)
    assert len(sent) == 1
    assert sent[0].extensions["timeout"] == dict.fromkeys(("connect", "read", "write", "pool"), 300)
    assert "transport_policy_version" not in llm.provider_settings
    assert drain_seconds(llm.provider_settings) == 300
    assert verify_provider({"provider_config": llm.provider_settings}, environ=dict(
        POKECHAMP_PROVIDER=provider, ZAI_BASE_URL="https://zai.example.test/v4")) == llm.provider_settings


@pytest.mark.parametrize("version", [CURRENT, "provider-retry-v2"])
@pytest.mark.parametrize("cancel", ["event", "file", "deadline"])
def test_cancel_in_backoff_immediate_and_permit_released(tmp_path, cancel, version):
    first = threading.Event()
    sent = []

    def handler(request):
        sent.append(request)
        first.set()
        raise httpx.ConnectError("fixture")

    with PermitBroker(tmp_path / "p.sock", 1, {OLLAMA_MODEL: 1}) as broker:
        llm = make_backend("ollama", handler, env=dict(
            POKECHAMP_TRANSPORT_POLICY=version, POKECHAMP_PERMIT_SOCKET=str(broker.path),
            POKECHAMP_CANCEL_PATH=str(tmp_path / "cancel.json")))
        errors = []

        def run():
            try:
                call(llm)
            except cloud.CloudRequestError as error:
                errors.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        assert first.wait(2)
        until = time.monotonic() + 2
        while sum(broker.active.values()) and time.monotonic() < until:
            time.sleep(.01)
        assert not sum(broker.active.values())
        started = time.monotonic()
        if cancel == "event":
            llm.failure_event.set()
        elif cancel == "file":
            (tmp_path / "cancel.json").write_text('{}')
        else:
            llm.batch_deadline = time.time() - 1
        worker.join(1)
        assert not worker.is_alive() and time.monotonic() - started < .5
        assert len(sent) == len(errors) == 1
        assert not sum(broker.active.values())


def prepared_backend(tmp_path, monkeypatch, failures=2, version=CURRENT):
    from integration.pokechamp.providers import provider_config
    monkeypatch.setattr(study, "prepared_provider", lambda **_: provider_config({"POKECHAMP_TRANSPORT_POLICY": version}))
    prepared = study.prepare(tmp_path / "prepared", transport="fake")
    root = tmp_path / "prepared"
    actor = prepared["experiment_id"] + "/" + prepared["schedule"][0]["slot_id"] + "-a1/p1"
    sent = []

    def handler(request):
        sent.append(request)
        if len(sent) <= failures:
            raise httpx.ConnectError("fixture")
        return response("ollama")

    llm = make_backend("ollama", handler, env=dict(
        POKECHAMP_LEAD_STUDY_ROOT=str(root), POKECHAMP_IO_ACTOR=actor, POKECHAMP_TRANSPORT_POLICY=version))
    llm._request_context = lambda: dict(call_role="self_action", identity=dict(decision_seq=1))
    monkeypatch.setattr(cloud, "wait_retry", lambda *_: None)
    return prepared, root, actor, llm, sent


@pytest.mark.parametrize("version", [CURRENT, "provider-retry-v2"])
def test_atomic_ledger_trace_attempt_links_and_duplicate_block(tmp_path, monkeypatch, version):
    prepared, root, actor, llm, sent = prepared_backend(tmp_path, monkeypatch, version=version)
    assert call(llm)[1]
    record = llm.call_records[0]
    assert len(sent) == 3
    with sqlite3.connect(root / "ledger.sqlite") as db:
        rows = db.execute("SELECT payload FROM reservations ORDER BY number").fetchall()
    assert len(rows) == 3
    for i, row in enumerate(rows, 1):
        payload = json.loads(row[0])
        assert payload["request"]["http_attempt_number"] == i
        assert payload["request"]["logical_request_id"] == record["logical_request_id"]
        proof = b.read_sealed(root / "requests" / f"attempt-{i:06}.json")
        assert proof["http_attempt_number"] == i
        assert record["http_attempts"][i - 1]["request_intent"].endswith(f"intent-{i:06}.json")
    # A fresh logical request for the exact same decision is still forbidden.
    with pytest.raises(cloud.CloudRequestError, match="duplicate"):
        call(llm)
    assert len(sent) == 3


@pytest.mark.parametrize("stop", ["halt", "deadline", "cap", "input_drift"])
@pytest.mark.parametrize("version", [CURRENT, "provider-retry-v2"])
def test_retry_admission_blocks_extra_transfer(tmp_path, monkeypatch, stop, version):
    _, root, actor, llm, sent = prepared_backend(tmp_path, monkeypatch, version=version)

    def wait(backend, delay):
        if stop == "halt":
            b.seal_json(root / "halt.json", {"reason": "fixture"})
        elif stop == "deadline":
            monkeypatch.setattr(study, "collection_deadline", lambda *_: time.time() - 1)
        elif stop == "input_drift":
            llm.provider_settings["thinking_effort"] = "tampered"
            # Tamper the previous committed input; the retry must fail exact equality.
            with sqlite3.connect(root / "ledger.sqlite") as db:
                raw = json.loads(db.execute("SELECT payload FROM reservations").fetchone()[0])
                raw["user_prompt"] = "changed"
                db.execute("UPDATE reservations SET payload=?", (json.dumps(raw),))
        else:
            with sqlite3.connect(root / "ledger.sqlite") as db:
                raw = db.execute("SELECT actor,reserved_at,payload FROM reservations").fetchone()
                db.executemany("INSERT INTO reservations VALUES (?,?,?,?)", [(i, *raw) for i in range(2, 8001)])
    monkeypatch.setattr(cloud, "wait_retry", wait)
    with pytest.raises(cloud.CloudRequestError):
        call(llm)
    assert len(sent) == 1


def test_new_prepare_and_old_ex_policy_hashes(tmp_path):
    fresh = study.prepare(tmp_path / "new", transport="fake")
    old = study.prepare(tmp_path / "old", transport="fake", experiment_id="EX-041", concurrency=4)
    assert fresh["provider_config"]["request_timeout_seconds"] == 600
    assert old["provider_config"]["request_timeout_seconds"] == 300
    assert old["provider_config"]["provider_retries"] == 0
    assert all(fresh[k] == old[k] for k in study.policy_selection())
    assert study.verify_prepared(tmp_path / "new") == fresh
    assert study.verify_prepared(tmp_path / "old") == old


def test_retry_concurrency_and_each_permit_returned(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(cloud, "wait_retry", lambda *_: time.sleep(.01))
    with PermitBroker(tmp_path / "p.sock", 2, {OLLAMA_MODEL: 2}) as broker:
        assert broker.timeout >= 600

        def run(_):
            count = 0

            def handler(request):
                nonlocal count
                count += 1
                time.sleep(.02)
                if count <= 2:
                    raise httpx.ConnectError("fixture")
                return response("ollama")
            llm = make_backend("ollama", handler,
                               env={"POKECHAMP_PERMIT_SOCKET": str(broker.path)})
            assert drain_seconds(llm.provider_settings) >= 600
            assert call(llm)[1]
            return llm.call_records[0]
        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(run, range(4)))
        assert broker.maximum_total == 2
        assert not sum(broker.active.values())
        assert len([e for e in broker.events if e["event"] == "grant"]) == 12
        assert len([e for e in broker.events if e["event"] == "release"]) == 12
        assert all(r["http_attempt_count"] == 3 for r in records)


def test_retry_forged_success_and_nonsequential_attempt_rejected(tmp_path, monkeypatch):
    prepared, root, actor, llm, _ = prepared_backend(tmp_path, monkeypatch, failures=0)
    assert call(llm)[1]
    original = b.read_sealed(root / "requests/intent-000001.json")["payload"]
    payload = json.loads(json.dumps(original))
    payload["request"].update(http_attempt_number=2,
                             previous_attempt_intent=str(root / "requests/intent-000001.json"))
    with pytest.raises(cloud.CloudRequestError, match="duplicate"):
        study.reserve(root, actor, payload)
    payload["request"]["http_attempt_number"] = 3
    with pytest.raises(cloud.CloudRequestError, match="duplicate"):
        study.reserve(root, actor, payload)
    assert study.shared.usage(root)["reserved_calls"] == 1


def test_sealed_timeout_tamper_rejected_before_network(tmp_path):
    prepared = study.prepare(tmp_path / "prepared", transport="fake")
    prepared["provider_config"]["http_timeout"]["read"] = 42
    path = tmp_path / "prepared/plan.json"
    b.write_json(path, prepared, exclusive=False)
    Path(str(path) + ".sha256").write_text(b.digest(path) + "\n")
    with pytest.raises(cloud.CloudConfigurationError, match="sealed provider"):
        study.verify_prepared(path.parent)


def test_new_timeout_clamp_and_legacy_nonledger_deadline():
    for version, expected_read in [(CURRENT, 10), (LEGACY, 300)]:
        sent = []
        llm = make_backend("zai", lambda req: sent.append(req) or response("zai"), env=dict(
            POKECHAMP_TRANSPORT_POLICY=version, POKECHAMP_BATCH_DEADLINE=str(time.time() + 10)))
        assert call(llm)[1]
        timeout = sent[0].extensions["timeout"]
        assert expected_read - 1 < timeout["read"] <= expected_read
