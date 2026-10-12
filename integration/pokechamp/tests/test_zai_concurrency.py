"""D-056 new preparation defaults and immutable historical declarations."""
import pytest

from integration.pokechamp import a_diagnostic as d, ab_head_to_head as h
from integration.pokechamp import benchmark as b, team_preview_study as study
from integration.pokechamp.execution import (
    resolve_concurrency, concurrency_fields, gate_evidence, gate_parallel,
    sealed_concurrency_provider,
)
from integration.pokechamp.tests.test_zai import ENV


@pytest.mark.parametrize("provider,default", [("zai", 4), ("ollama", 8)])
def test_new_defaults_explicit_override_and_invalid_limits(provider, default):
    assert resolve_concurrency(provider=provider) == default
    for limit in (1, 4, 8, 9, 10):
        assert resolve_concurrency(limit, provider=provider) == limit
    for bad in (0, 11, True, 4.0, "4"):
        with pytest.raises(ValueError):
            resolve_concurrency(bad, provider=provider)
    with pytest.raises(ValueError):
        resolve_concurrency(provider="unknown")


@pytest.mark.parametrize("module", [d, h, study])
def test_cloud_prepare_uses_provider_after_environment_resolution(tmp_path, monkeypatch, module):
    for key, val in ENV.items():
        monkeypatch.setenv(key, val)
    root = tmp_path / "prepared"
    value = module.prepare(root, transport="cloud")
    assert all(value["execution"][k] == v for k, v in concurrency_fields(4).items())
    assert value["execution"]["evidence"]["concurrency_policy"] == "zai-default4-v1"
    assert module.verify_prepared(root) == value
    monkeypatch.setenv("POKECHAMP_PROVIDER", "ollama")
    assert module.verify_prepared(root, current=False) == value
    assert sealed_concurrency_provider(value) == "zai"
    value["provider_config"]["provider"] = "ollama"
    with pytest.raises(ValueError, match="requires sealed"):
        sealed_concurrency_provider(value)


def test_historical_ex040_and_ex039_seals_remain_readable():
    for name in ("ex039", "ex040-zai"):
        root = b.WORKSPACE_ROOT / ".pokechamp-data/b2-lead" / name
        before = b.digest(root / "plan.json")
        value = study.verify_prepared(root, current=False)
        assert value["execution"]["battle_concurrency"] == 8
        assert value["execution"]["evidence"]["concurrency_policy"] == "cloud-default8-v1"
        assert b.digest(root / "plan.json") == before


def test_gate_declaration_preserves_provider_policy():
    declared = dict(concurrency_policy="zai-default4-v1", parallel_concurrency=4)
    assert gate_parallel(declared) == 4
    assert gate_evidence(declared) == declared


def test_ex041_explicit_four_and_reject_other_limits(tmp_path):
    for limit in (1, 2, 8, 9, 10):
        with pytest.raises(ValueError, match="requires concurrency 4"):
            study.prepare(tmp_path / str(limit), experiment_id="EX-041", concurrency=limit)
    value = study.prepare(tmp_path / "four", experiment_id="EX-041", concurrency=4)
    assert study.verify_prepared(tmp_path / "four") == value
    assert all(value["execution"][k] == v for k, v in concurrency_fields(4).items())


def test_actual_mock_http_overlap_cannot_exceed_four(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import httpx
    from integration.pokechamp.cloud import OllamaCloudBackend
    from integration.pokechamp.permits import PermitBroker
    from integration.pokechamp.providers import ZaiChatClient
    from integration.pokechamp.tests.test_zai import response

    barrier = threading.Barrier(4, timeout=10)
    lock = threading.Lock()
    active = maximum = calls = 0

    def handler(request):
        nonlocal active, maximum, calls
        with lock:
            active += 1
            maximum = max(maximum, active)
            calls += 1
        try:
            barrier.wait()
            return httpx.Response(200, json=response())
        finally:
            with lock:
                active -= 1

    with PermitBroker(tmp_path / "broker.sock", 4, {"glm-5.3-flash": 4}) as broker:
        def invoke(_):
            backend = OllamaCloudBackend(
                environ={**ENV, "POKECHAMP_PERMIT_SOCKET": str(broker.path)},
                client_factory=lambda **kw: ZaiChatClient(
                    **kw, api_key="local-test", transport=httpx.MockTransport(handler)),
            )
            return backend.get_LLM_action("system", "user", "glm-5.3-flash", temperature=0)
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert all(result[1] for result in pool.map(invoke, range(8)))
    snapshot = broker.snapshot()
    assert maximum == 4 and active == 0 and calls == 8
    assert snapshot["maximum_account_permits"] == 4
    assert snapshot["maximum_model_permits"] == {"glm-5.3-flash": 4}
    assert not sum(snapshot["active_at_close"].values())
    assert not any(e["event"] == "orphan" for e in snapshot["events"])
