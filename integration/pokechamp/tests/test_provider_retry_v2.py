"""New provider policy, real SDK serialization, no external requests."""
import json
from types import SimpleNamespace

import httpx
import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp import cloud
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.providers import provider_config
from integration.pokechamp.tests.test_transport_retry import (
    call,
    make_backend,
    response,
)
from integration.pokechamp.transport_policy import CURRENT, audit_attempts


@pytest.mark.parametrize("unknown_failures", [0, 1])
def test_recovered_errors_pass_gate_but_unknown_requests_do_not(tmp_path, monkeypatch, unknown_failures):
    from integration.pokechamp import team_preview_run as runner
    monkeypatch.setattr(runner, "audit", lambda *_: {"ledger_intents": 8})
    monkeypatch.setattr(runner.shared, "usage", lambda *_: dict(
        reserved_calls=8, uncertain=6 + unknown_failures,
        known_connection_failures=0, known_retryable_failures=6))
    result = runner.inspect_pair(tmp_path, [{"eligible": True}] * 2, {},
                                 {"active_at_close": {"model": 0}, "events": []})
    assert result["passed"] is (unknown_failures == 0)
    assert result["errors"] == (["gate_uncertain_request"] if unknown_failures else [])


def backend(provider, handler, **kwargs):
    return make_backend(provider, handler, env={"POKECHAMP_TRANSPORT_POLICY": CURRENT,
                                               **kwargs.pop("env", {})}, **kwargs)


@pytest.mark.parametrize("provider", ["ollama", "zai"])
@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
                                  httpx.WriteTimeout, httpx.PoolTimeout, 500, 503, 599, 429])
@pytest.mark.parametrize("failures", [3, 4])
def test_recovery_and_exhaustion(provider, error, failures, monkeypatch):
    sent, waits, traces = [], [], []

    def handler(request):
        sent.append(request)
        if len(sent) <= failures:
            if isinstance(error, int):
                return httpx.Response(error, json={"error": "fixture"}, headers={"Retry-After": "60"})
            raise error("fixture", request=request)
        return response(provider)

    llm = backend(provider, handler, trace=SimpleNamespace(record_llm_call=lambda **v: traces.append(v)))
    monkeypatch.setattr(cloud, "wait_retry", lambda _, delay: waits.append(delay))
    if failures == 4:
        with pytest.raises(cloud.CloudRequestError):
            call(llm)
    else:
        assert call(llm)[1]
    assert len(sent) == 4 and waits == [1, 2, 4]
    assert all(r.content == sent[0].content for r in sent)
    assert len(traces) == 1
    record = traces[0]["request"]
    assert record["retry_outcome"] == ("exhausted" if failures == 4 else "recovered")
    assert record["http_attempt_count"] == 4
    assert not any(a.get("cooldown_seconds") for a in record["http_attempts"])
    assert all(a["retryable"] for a in record["http_attempts"][:3])


@pytest.mark.parametrize("provider", ["ollama", "zai"])
@pytest.mark.parametrize("error", [400, 401, 403, 404, 422, httpx.ReadError, ValueError])
def test_excluded(provider, error):
    sent = []

    def handler(request):
        sent.append(request)
        if isinstance(error, int):
            return httpx.Response(error, json={"error": "fixture"})
        raise error("fixture")

    with pytest.raises(cloud.CloudRequestError):
        call(backend(provider, handler))
    assert len(sent) == 1


@pytest.mark.parametrize("provider", ["ollama", "zai"])
@pytest.mark.parametrize("exhaust", [False, True])
def test_ledger_429_halt_only_on_final_failure(tmp_path, monkeypatch, provider, exhaust):
    settings = provider_config(dict(POKECHAMP_PROVIDER=provider, ZAI_BASE_URL="https://zai.example.test/v4"))
    monkeypatch.setattr(study, "prepared_provider", lambda **_: settings)
    root = tmp_path / "prepared"
    plan = study.prepare(root, transport="fake")
    actor = plan["experiment_id"] + "/" + plan["schedule"][0]["slot_id"] + "-a1/p1"
    sent, waits, traces = [], [], []

    def handler(request):
        assert not (root / "halt.json").exists()
        sent.append(request)
        if len(sent) <= (4 if exhaust else 3):
            return httpx.Response(429, json={"error": "fixture"}, headers={"Retry-After": "99"})
        return response(provider)

    def wait(_, delay):
        assert not (root / "halt.json").exists()
        waits.append(delay)

    monkeypatch.setattr(cloud, "wait_retry", wait)
    llm = backend(provider, handler, env=dict(POKECHAMP_LEAD_STUDY_ROOT=str(root), POKECHAMP_IO_ACTOR=actor),
                  trace=SimpleNamespace(record_llm_call=lambda **v: traces.append(v)))
    llm._request_context = lambda: dict(call_role="self_action", identity=dict(decision_seq=1))
    if exhaust:
        with pytest.raises(cloud.CloudRequestError):
            call(llm)
        assert b.read_sealed(root / "halt.json")["retry_exhausted"]
        with pytest.raises(cloud.CloudRequestError, match="halt"):
            study.check_admission(root)
    else:
        assert call(llm)[1]
        assert not (root / "halt.json").exists()
    assert waits == [1, 2, 4] and len(sent) == 4
    assert len(audit_attempts(traces[0], actor=actor)) == 4
    usage = study.shared.usage(root)
    assert usage["reserved_calls"] == 4 and usage["logical_requests"] == 1
    assert usage["known_connection_failures"] == 0
    assert usage["known_retryable_failures"] == (4 if exhaust else 3)
    for n in range(1, 5):
        intent = b.read_sealed(root / "requests" / f"intent-{n:06}.json")
        assert intent["payload"]["request"]["transport_policy_version"] == CURRENT
    assert len({json.dumps(json.loads(r.content), sort_keys=True) for r in sent}) == 1
