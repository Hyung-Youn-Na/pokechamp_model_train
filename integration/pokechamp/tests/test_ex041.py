"""EX-041 binding, admission and evaluation regressions; MockTransport only."""
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest

from integration.pokechamp import a_diagnostic as shared, benchmark as b, cloud
from integration.pokechamp import team_preview_run as runner, team_preview_study as study
from integration.pokechamp.diagnostics.team_preview import (
    check_decision_resolution, check_executed_wire, check_request_settings,
)
from integration.pokechamp.providers import CloudConfigurationError, ZaiChatClient
from integration.pokechamp.tests.test_zai import ENV, response


@pytest.fixture
def registered(tmp_path, monkeypatch):
    for key, val in ENV.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setattr(study, "ZAI4_STUDY_LINK", tmp_path / "ex041-binding.json")
    root = tmp_path / "prepared"
    value = study.prepare(root, transport="cloud", experiment_id="EX-041")
    approval = tmp_path / "approval.txt"
    approval.write_text("local test approval fixture; no provider network")
    study.register_execution(root, approval_record=approval)
    return root, value, approval


def actor(value, role="p2"):
    return "/".join((value["experiment_id"], value["schedule"][0]["slot_id"] + "-a1", role))


def payload(seq=1):
    return dict(request=dict(call_role="self_action", identity=dict(decision_seq=seq)))


def test_binding_original_clock_duplicate_registration_and_moved_folder(registered, tmp_path):
    root, value, approval = registered
    assert study.execution_protocol(value)["experiment"] == "EX-041"
    assert value["experiment_id"] == "ex041-zai"
    assert value["execution"]["battle_concurrency"] == 4
    assert value["execution"]["evidence"]["concurrency_policy"] == "zai-default4-v1"
    assert study.ZAI_EXECUTION_PROTOCOL["experiment"] == "EX-040"
    assert study.EXECUTION_PROTOCOL["experiment"] == "EX-039"
    intent = study.reserve(root, actor(value), payload())
    clock_hash = b.digest(root / "cloud-clock.json")
    assert b.read_sealed(intent)["clock_sha256"] == clock_hash
    with pytest.raises(FileExistsError):
        study.register_execution(root, approval_record=approval)
    other = tmp_path / "other"
    study.prepare(other, transport="cloud", experiment_id="EX-041")
    with pytest.raises(ValueError, match="already bound"):
        study.register_execution(other, approval_record=approval)
    moved = tmp_path / "moved"
    shutil.copytree(root, moved)
    with pytest.raises(cloud.CloudRequestError, match="not registered"):
        study.reserve(moved, actor(value), payload(2))
    assert b.digest(root / "cloud-clock.json") == clock_hash
    approval.write_text("altered approval")
    with pytest.raises(cloud.CloudRequestError, match="not registered"):
        study.reserve(root, actor(value), payload(2))


def test_provider_drift_blocks_reservation(registered, monkeypatch):
    root, value, _ = registered
    monkeypatch.setenv("ZAI_BASE_URL", "https://different.example.test/v4")
    with pytest.raises(CloudConfigurationError):
        study.reserve(root, actor(value), payload())
    assert shared.usage(root)["reserved_calls"] == 0


def test_reject_ollama_and_concurrency_other_than_four(tmp_path, monkeypatch):
    monkeypatch.setenv("POKECHAMP_PROVIDER", "ollama")
    with pytest.raises(ValueError, match="requires Z.ai"):
        study.prepare(tmp_path / "wrong", transport="cloud", experiment_id="EX-041")
    with pytest.raises(ValueError, match="requires concurrency 4"):
        study.prepare(tmp_path / "over", concurrency=9, experiment_id="EX-041")


def backend(root, value, handler, role="p2", seq=1):
    instance = cloud.OllamaCloudBackend(
        environ={**ENV, "POKECHAMP_LEAD_STUDY_ROOT": str(root), "POKECHAMP_IO_ACTOR": actor(value, role)},
        client_factory=lambda **kw: ZaiChatClient(**kw, api_key="local-test", transport=httpx.MockTransport(handler)),
    )
    instance._request_context = lambda: payload(seq)["request"]
    return instance


def invoke(instance):
    return instance.get_LLM_action("system", "user", "glm-5.3-flash", temperature=0)


def test_first_429_blocks_peer_but_preserves_inflight_response(registered):
    root, value, _ = registered
    started, finish = threading.Event(), threading.Event()
    sent = []
    def slow(req):
        sent.append("inflight")
        started.set()
        assert finish.wait(10)
        return httpx.Response(200, json=response(usage=dict(prompt_tokens=3, completion_tokens=2)))
    slow_backend = backend(root, value, slow, "p1")
    limited = backend(root, value, lambda r: sent.append("429") or httpx.Response(429))
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(invoke, slow_backend)
        assert started.wait(10)
        try:
            with pytest.raises(cloud.CloudRequestError) as error:
                invoke(limited)
            assert error.value.category == "rate_limit"
            assert b.read_sealed(root / "halt.json")["http_status"] == 429
            late = backend(root, value, lambda r: sent.append("forbidden"), seq=2)
            with pytest.raises(cloud.CloudRequestError):
                invoke(late)
        finally:
            finish.set()
        assert running.result()[1] is True
    assert sent == ["inflight", "429"]
    assert shared.usage(root)["reserved_calls"] == 2
    assert shared.usage(root)["uncertain"] == 1
    before = b.digest(root / "halt.json")
    study.halt_on_429(root)
    assert b.digest(root / "halt.json") == before
    with pytest.raises(cloud.CloudRequestError, match="halted"):
        study.check_admission(root)


def test_429_leaves_ex039_policy_unchanged(tmp_path):
    root = tmp_path / "old"
    study.prepare(root)
    study.halt_on_429(root)
    study.check_admission(root)
    assert not (root / "halt.json").exists()


def test_timeout_and_missing_usage_counted_without_retry(registered):
    root, value, _ = registered
    def timeout(request):
        raise httpx.ReadTimeout("local timeout")
    instance = backend(root, value, timeout)
    with pytest.raises(cloud.CloudRequestError) as error:
        invoke(instance)
    assert error.value.category == "timeout"
    assert shared.usage(root)["uncertain"] == 1
    assert not (root / "halt.json").exists()
    other = backend(root, value, lambda r: httpx.Response(200, json=response()), "p1")
    invoke(other)
    assert other.call_records[-1]["prompt_tokens"] is None
    assert other.call_records[-1]["completion_tokens"] is None
    assert shared.usage(root)["reserved_calls"] == 2


def test_coordinator_rejects_dispatch_after_persistent_halt(tmp_path, monkeypatch):
    value = dict(registered_experiment="EX-041", schedule=study.schedule(), execution=study.execution("fake"))
    monkeypatch.setattr(study, "verify_prepared", lambda root: value)
    monkeypatch.setattr(study, "collection_deadline", lambda root: None)
    b.seal_json(tmp_path / "plan.json", value)
    b.seal_json(tmp_path / "halt.json", dict(category="rate_limit"))
    broker = SimpleNamespace(path=tmp_path / "broker", stop=lambda: None, snapshot=lambda: dict(active_at_close={}, events=[]))
    attempted = runner.execute_schedule(tmp_path, tmp_path / "data", value, broker,
        worker=lambda *a, **kw: pytest.fail("halted experiment dispatched"),
        gate_check=lambda *args: dict(passed=False))
    assert attempted == []
    assert b.read_sealed(tmp_path / "halt.json")["category"] == "rate_limit"


def test_provider_evaluator_checks_sealed_seed_and_endpoint(tmp_path):
    value = study.prepare(tmp_path / "fake", experiment_id="EX-041")
    request = dict(value["provider_config"], temperature=0, seed=None, json_format=False,
                   requested_output_tokens=131072, call_role="team_preview", response_format=None)
    check_request_settings(request, value)
    for key, val in [("seed", 100), ("seed_applied", True), ("endpoint", "https://wrong.test"),
                     ("thinking", {"type": "disabled"}), ("provider", "ollama")]:
        with pytest.raises(ValueError):
            check_request_settings(dict(request, **{key: val}), value)


@pytest.mark.parametrize("kind,name", [("move", "tackle"), ("switch", "hatterene"), ("terastallize", "moonblast")])
def test_recovery_null_extraction_legal_execution_and_wire(kind, name):
    resolution = dict(extracted_action=None, executed_action={kind: name}, selection_source="first_legal_fallback")
    result = dict(canonical_parsed_output=None, validation=dict(action_resolution=resolution))
    check_decision_resolution([result], resolution)
    wire = f"/choose {'move' if kind == 'terastallize' else kind} {name}" + (" terastallize" if kind == "terastallize" else "")
    check_executed_wire(resolution["executed_action"], wire)
    with pytest.raises(ValueError):
        check_executed_wire(resolution["executed_action"], "/choose move wrong")
    with pytest.raises(AssertionError):
        check_decision_resolution([dict(result, canonical_parsed_output={kind: name})], resolution)


def test_removed_original_clock_cannot_restart_collection(registered):
    root, value, _ = registered
    study.reserve(root, actor(value), payload())
    (root / "cloud-clock.json").unlink()
    with pytest.raises(cloud.CloudRequestError, match="original clock removed"):
        study.collection_deadline(root)


def test_effective_http_timeout_uses_remaining_original_clock(registered):
    import time
    root, value, _ = registered
    study.reserve(root, actor(value), payload(), now=time.time() - 20650)
    seen = []
    instance = backend(root, value, lambda r: seen.append(r.extensions["timeout"]["read"])
                       or httpx.Response(200, json=response()), "p1")
    invoke(instance)
    assert len(seen) == 1 and 0 < seen[0] <= 50


def test_wrong_response_model_is_preserved_and_stops_new_requests(registered):
    root, value, _ = registered
    instance = backend(root, value, lambda r: httpx.Response(200, json=dict(response(), model="different-model")))
    with pytest.raises(cloud.CloudRequestError) as error:
        invoke(instance)
    assert error.value.category == "model"
    assert b.read_sealed(root / "halt.json")["category"] == "model"
    assert len(list((root / "requests").glob("response-*.json"))) == 1
