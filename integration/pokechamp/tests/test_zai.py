"""Z.ai contracts using MockTransport only; never contact a provider."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from integration.pokechamp import benchmark, cli, cloud, team_preview_study
from integration.pokechamp.constants import OLLAMA_MODEL
from integration.pokechamp.dotenv import (
    DotenvConfigurationError,
    load_workspace_credential,
)
from integration.pokechamp.providers import (
    CloudConfigurationError,
    ZaiChatClient,
    provider_config,
    redact,
    verify_provider,
)

ENV = dict(
    POKECHAMP_PROVIDER="zai",
    POKECHAMP_MODEL=OLLAMA_MODEL,
    ZAI_BASE_URL="https://zai.example.test/api/paas/v4/",
    ZAI_API_KEY="zai-test-key-marker",
    OLLAMA_API_KEY="ollama-test-key-marker",
)


def response(content='{"move":"tackle"}', **updates):
    return dict(
        model=OLLAMA_MODEL,
        choices=[
            dict(
                message=dict(content=content, reasoning_content="reasoning fixture"),
                finish_reason="stop",
            )
        ],
        **updates,
    )


def backend(handler, *, trace=None, cls=cloud.OllamaCloudBackend, policy=None):
    return cls(
        environ={**ENV, **({"POKECHAMP_TRANSPORT_POLICY": policy} if policy else {})},
        trace_sink=trace,
        client_factory=lambda **kwargs: ZaiChatClient(
            **kwargs, api_key=ENV["ZAI_API_KEY"], transport=httpx.MockTransport(handler)
        ),
    )


def call(llm, **kwargs):
    return llm.get_LLM_action("system", "user", "zai/" + OLLAMA_MODEL, **kwargs)


def test_actual_http_contract_trace_and_missing_usage():
    sent, traced = [], []
    llm = backend(
        lambda req: sent.append(req)
        or httpx.Response(200, json=response(usage={"prompt_tokens": 17})),
        trace=SimpleNamespace(record_llm_call=lambda **p: traced.append(p)),
    )
    assert call(llm, seed=123, temperature=0, max_tokens=20) == ('{"move":"tackle"}', True, "")
    request = sent[0]
    assert str(request.url) == "https://zai.example.test/api/paas/v4/chat/completions"
    assert request.headers["Authorization"] == "Bearer " + ENV["ZAI_API_KEY"]
    assert request.extensions["timeout"] == dict(connect=300.0, read=600.0, write=300.0, pool=300.0)
    assert json.loads(request.content) == dict(
        model=OLLAMA_MODEL,
        messages=[dict(role="system", content="system"), dict(role="user", content="user")],
        stream=False,
        thinking={"type": "enabled"},
        reasoning_effort="low",
        max_tokens=131072,
        temperature=0,
        response_format={"type": "json_object"},
    )
    record = llm.call_records[0]
    assert record["provider"] == "zai" and record["endpoint"] == str(request.url)
    assert record["seed"] is None and record["seed_requested"] == 123
    assert record["seed_applied"] is False
    assert record["prompt_tokens"] == 17 and record["completion_tokens"] is None
    assert record["done_reason"] == "stop"
    assert traced[0]["provider_reasoning"] == "reasoning fixture"
    assert traced[0]["raw_content"] == '{"move":"tackle"}'
    assert traced[0]["response"]["usage"] == {"prompt_tokens": 17}
    assert ENV["ZAI_API_KEY"] not in repr(traced + llm.call_records)


def test_text_stop_and_usage():
    sent = []
    llm = backend(
        lambda req: sent.append(json.loads(req.content))
        or httpx.Response(
            200, json=response("plain text", usage=dict(prompt_tokens=21, completion_tokens=8))
        )
    )
    assert call(llm, json_format=False, stop=["END"])[0] == "plain text"
    assert "response_format" not in sent[0] and "seed" not in sent[0]
    assert sent[0]["stop"] == ["END"]
    assert llm.prompt_tokens == 21 and llm.completion_tokens == 8


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {"choices": []},
        {"choices": [None]},
        {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": "x"}}]},
        response(usage=[1]),
    ],
)
def test_malformed_response_stops(body):
    sent = []
    llm = backend(lambda req: sent.append(req) or httpx.Response(200, json=body))
    for _ in range(2):
        with pytest.raises(cloud.CloudRequestError):
            call(llm)
    assert len(sent) == 1


@pytest.mark.parametrize(
    "failure, category",
    [
        (401, "auth"),
        (403, "auth"),
        (404, "model"),
        (429, "rate_limit"),
        (500, "provider"),
        (307, "provider"),
        ("timeout", "timeout"),
        ("network", "transport"),
        ("bad-json", "provider"),
        ("bad-action", "output_contract"),
    ],
)
def test_v1_failure_terminal_bounded_retry_no_redirect(failure, category):
    sent = []

    def handler(request):
        sent.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout(ENV["ZAI_API_KEY"], request=request)
        if failure == "network":
            raise httpx.ConnectError(ENV["OLLAMA_API_KEY"], request=request)
        if failure == "bad-json":
            return httpx.Response(200, text="not JSON")
        if failure == "bad-action":
            return httpx.Response(200, json=response("not an action"))
        return httpx.Response(
            failure,
            text=ENV["ZAI_API_KEY"],
            headers={"Retry-After": "2", "Location": "https://elsewhere.example.test/"},
        )

    llm = backend(handler, policy="connect-retry-v1")
    for _ in range(2):
        with pytest.raises(cloud.CloudRequestError) as captured:
            call(llm)
        assert captured.value.category == category
        assert "key-marker" not in str(captured.value)
    assert len(sent) == (3 if failure == "network" else 1) and llm.failure_event.is_set()
    assert llm.call_records[0]["provider"] == "zai"
    if failure == 429:
        assert llm.call_records[0]["cooldown_seconds"] == 2


@pytest.mark.parametrize(
    "update, name",
    [
        ({"POKECHAMP_PROVIDER": "unknown"}, "POKECHAMP_PROVIDER"),
        ({"POKECHAMP_PROVIDER": ""}, "POKECHAMP_PROVIDER"),
        ({"POKECHAMP_MODEL": "different"}, "POKECHAMP_MODEL"),
        ({"ZAI_API_KEY": ""}, "ZAI_API_KEY"),
        ({"ZAI_API_KEY": "key\ninvalid"}, "ZAI_API_KEY"),
        *[
            ({"ZAI_BASE_URL": url}, "ZAI_BASE_URL")
            for url in [
                "",
                "http://api.example/v4",
                "no-scheme",
                "https://",
                "https://a:999999/v4",
                "https://user:password@api.example/v4",
                "https://a/v4?api_key=secret",
                "https://a/v4#x",
                "https://a/v4/chat/completions/",
                "https://a/white space",
                "https://a\\b/v4",
            ]
        ],
    ],
)
def test_invalid_config_before_client_creation(update, name):
    with pytest.raises(CloudConfigurationError, match=name):
        cloud.OllamaCloudBackend(
            environ={**ENV, **update}, client_factory=lambda **_: pytest.fail("client created")
        )


def test_default_factory_selects_zai(monkeypatch):
    created, sent = [], []

    def factory(**kwargs):
        created.append(kwargs)
        return ZaiChatClient(
            **kwargs,
            transport=httpx.MockTransport(
                lambda req: sent.append(req) or httpx.Response(200, json=response())
            ),
        )

    monkeypatch.setattr(cloud, "ZaiChatClient", factory)
    call(cloud.OllamaCloudBackend(environ=ENV))
    assert created[0]["api_key"] == ENV["ZAI_API_KEY"] and len(sent) == 1


def test_dotenv_all_settings_and_explicit_empty_process_precedence(tmp_path):
    path = tmp_path / ".env"
    path.write_text("\n".join(f"{k}={v}" for k, v in ENV.items()) + "\nUNRELATED=value\n")
    path.chmod(0o600)
    env = {"ZAI_API_KEY": "process-key", "ZAI_BASE_URL": ""}
    assert load_workspace_credential(environ=env, path=path) == "process_environment"
    assert env["POKECHAMP_PROVIDER"] == "zai" and env["ZAI_BASE_URL"] == ""
    assert env["ZAI_API_KEY"] == "process-key" and "UNRELATED" not in env
    empty = {}
    assert load_workspace_credential(environ=empty, path=path) == "workspace_dotenv"
    assert empty == ENV
    with path.open("a") as out:
        out.write("ZAI_API_KEY=duplicate\n")
    with pytest.raises(DotenvConfigurationError, match="more than once"):
        load_workspace_credential(environ={}, path=path)
    linked = tmp_path / "linked"
    linked.symlink_to(path)
    with pytest.raises(DotenvConfigurationError, match="symlink"):
        load_workspace_credential(environ={}, path=linked)


def test_both_keys_redacted_from_errors_trace_and_response(monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    from integration.pokechamp.observability.player import _safe_error
    from integration.pokechamp.observability.recorder import _redact_known_credentials

    text = ENV["ZAI_API_KEY"] + " " + ENV["OLLAMA_API_KEY"]
    assert cli._safe_error(ValueError(text))["detail"] == "[REDACTED] [REDACTED]"
    assert _safe_error(ValueError(text))["detail"] == "[REDACTED] [REDACTED]"
    assert _redact_known_credentials({"nested": [text]}) == {"nested": ["[REDACTED] [REDACTED]"]}
    child = cli._child_environment()
    assert "ZAI_API_KEY" not in child and "OLLAMA_API_KEY" not in child
    traced = []
    llm = backend(
        lambda r: httpx.Response(200, json=response(text)),
        trace=SimpleNamespace(record_llm_call=lambda **p: traced.append(p)),
    )
    assert call(llm, json_format=False)[0] == "[REDACTED] [REDACTED]"
    assert redact(traced) == traced


def test_legacy_ollama_and_sealed_settings():
    assert verify_provider({}, environ={})["provider"] == "ollama"
    with pytest.raises(CloudConfigurationError, match="differs"):
        verify_provider({}, environ=ENV)
    sealed = {"provider_config": provider_config(ENV)}
    assert verify_provider(sealed, environ=ENV) == sealed["provider_config"]
    for update in ({"POKECHAMP_PROVIDER": "ollama"}, {"ZAI_BASE_URL": "https://other.test/v4"}):
        with pytest.raises(CloudConfigurationError, match="differs"):
            verify_provider(sealed, environ={**ENV, **update})


@pytest.mark.parametrize("prepare_kind", ["benchmark", "b2"])
def test_new_plans_seal_provider(tmp_path, monkeypatch, prepare_kind):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    if prepare_kind == "benchmark":
        directory = tmp_path / "benchmarks/unit"
        value = benchmark.plan(tmp_path, "unit")
        verify = benchmark.verify_plan
    else:
        directory = tmp_path / "prepared"
        value = team_preview_study.prepare(directory, transport="cloud")
        verify = team_preview_study.verify_prepared
        assert value["model"]["seed"] is None and value["model"]["seed_applied"] is False
    assert value["provider_config"] == provider_config(ENV)
    assert verify(directory, current=True) == value
    monkeypatch.setenv("ZAI_BASE_URL", "https://other.test/v4")
    with pytest.raises(CloudConfigurationError, match="differs"):
        verify(directory, current=True)
    assert verify(directory, current=False) == value
    assert "key-marker" not in (directory / "plan.json").read_text()


def test_b2_http_and_viewer_keep_original_and_reasoning(tmp_path):
    from integration.pokechamp import ab_head_to_head as h
    from integration.pokechamp.improved_io import battle_prompts, live_delivery
    from integration.pokechamp.improved_io.backend import FixedBackend
    from integration.pokechamp.observability.recorder import (
        BattleBundleConfig,
        BattleRecorder,
    )
    from integration.pokechamp.observability.render import (
        _decision_card,
        _group_decisions,
    )

    path = Path(
        "/workspace/.pokechamp-data/experiments/ex037-cloud/battles/b01-r1-s0-a1-p2/events.jsonl"
    )
    event = next(e for e in map(json.loads, path.open()) if e["event_type"] == "llm_call")
    full = json.loads(event["user_prompt"])
    recorder = BattleRecorder.create(
        tmp_path,
        BattleBundleConfig(
            experiment_id="unit",
            battle_id="unit",
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
        ),
    )
    for _ in range(full["identity"]["decision_seq"]):
        recorder.begin_decision(showdown_turn=1, decision_kind="turn_action", battle_state={})
    sent = []
    action = json.dumps(full["request"]["legal_actions"][0])
    llm = backend(
        lambda r: sent.append(json.loads(r.content))
        or httpx.Response(
            200,
            json=response("reason\n" + action, usage=dict(prompt_tokens=500, completion_tokens=30)),
        ),
        trace=recorder,
        cls=FixedBackend,
    )
    llm.experiment_policy = h.policy_selection(h.B2)
    llm.runtime_identity = h.runtime_identity()
    llm.io_profile = "io-battle-only-v1"
    llm.battle_prompt_identity = battle_prompts.identity("v1.2.0")
    llm.input_context = full
    llm.delivery = live_delivery.build(full)
    llm.get_LLM_action(
        llm.delivery.system_prompt,
        llm.delivery.user_json,
        OLLAMA_MODEL,
        temperature=0,
        json_format=False,
    )
    assert llm.parsed_action.action == full["request"]["legal_actions"][0]
    assert sent[0]["messages"][1]["content"] == llm.delivery.user_json
    assert "seed" not in sent[0] and "response_format" not in sent[0]
    events = list(map(json.loads, (recorder.bundle_path / "events.jsonl").read_text().splitlines()))
    snapshots = {e["event_seq"]: e for e in events if e["event_type"] == "input_snapshot"}
    trace = next(e for e in events if e["event_type"] == "llm_call")
    assert live_delivery.original_for_call(trace, snapshots) == full
    assert trace["request"]["provider"] == "zai" and trace["response"]["completion_tokens"] == 30
    decisions, _ = _group_decisions(events)
    assert "reasoning fixture" in _decision_card(decisions[-1])


def test_cli_probe_uses_mock_zai_and_records_provider(tmp_path, monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "_print_manifest", lambda path: None)
    requests = []
    monkeypatch.setattr(
        cloud,
        "ZaiChatClient",
        lambda **kwargs: ZaiChatClient(
            **kwargs,
            transport=httpx.MockTransport(
                lambda req: requests.append(req)
                or httpx.Response(200, json=response('{"status":"ok"}'))
            ),
        ),
    )
    assert cli.command_probe() == 0
    artifact = json.loads(next(tmp_path.rglob("manifest.json")).read_text())
    assert artifact["configuration"]["provider"] == "zai"
    assert artifact["credential"]["name"] == "ZAI_API_KEY"
    assert artifact["result"]["calls"][0]["endpoint"] == str(requests[0].url)
    assert "key-marker" not in json.dumps(artifact)
    assert len(requests) == 1


def test_ollama_mock_http_honors_injected_key_and_thinking_override(monkeypatch):
    import ollama

    class HighBackend(cloud.OllamaCloudBackend):
        def _thinking_effort(self):
            return "high"

    sent, traced = [], []
    monkeypatch.setenv("OLLAMA_API_KEY", "incorrect-process-test-key")
    env = {"OLLAMA_API_KEY": "correct-injected-test-key"}
    llm = HighBackend(
        environ=env,
        trace_sink=SimpleNamespace(record_llm_call=lambda **p: traced.append(p)),
        client_factory=lambda **kw: ollama.Client(
            **kw,
            transport=httpx.MockTransport(
                lambda req: sent.append(req)
                or httpx.Response(
                    200,
                    json=dict(
                        model=OLLAMA_MODEL,
                        message=dict(role="assistant", content='{"move":"tackle"}'),
                        done=True,
                        done_reason="stop",
                        prompt_eval_count=11,
                        eval_count=4,
                    ),
                )
            ),
        ),
    )
    llm.get_LLM_action("s", "u", OLLAMA_MODEL)
    assert sent[0].headers["Authorization"] == "Bearer correct-injected-test-key"
    assert str(sent[0].url) == "https://ollama.com/api/chat"
    assert json.loads(sent[0].content)["think"] == "high"
    assert traced[0]["request"]["thinking_effort"] == "high"
    assert llm.call_records[0]["seed_applied"] is True


def test_partial_usage_stays_unknown_in_shared_and_b2_totals(tmp_path):
    from integration.pokechamp import a_diagnostic, team_preview_report

    root = tmp_path / "prepared"
    prepared = team_preview_study.prepare(root, transport="fake")
    row = prepared["schedule"][0]
    actor = "/".join((prepared["experiment_id"], row["slot_id"] + "-a1", "p1"))
    team_preview_study.reserve(
        root, actor, dict(request=dict(call_role="self_action", identity=dict(decision_seq=1)))
    )
    benchmark.seal_json(
        root / "requests/response-000001.json",
        dict(response=dict(prompt_eval_count=17, eval_count=None)),
    )
    totals = a_diagnostic.usage(root)
    assert totals["responses"] == 1 and totals["uncertain"] == 0
    assert totals["input_tokens"] == 17 and totals["token_usage_unconfirmed"] == 1
    # Synthetic reporting configuration only; no Cloud registration or execution.
    prepared.update(transport="cloud", provider_config=provider_config(ENV))
    groups, _ = team_preview_report.usage(root, prepared, [])
    assert sum(g["input_tokens"] for g in groups) == 17
    assert sum(g["token_usage_unconfirmed"] for g in groups) == 1
    assert all(g["cost_basis"] is None and g["listed_token_cost_usd_range"] is None for g in groups)


def test_actor_rejects_sealed_provider_mismatch_before_backend(tmp_path, monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli, "OllamaCloudBackend", lambda **_: pytest.fail("backend created"))
    benchmark.seal_json(
        tmp_path / "request.json",
        dict(
            data_root=str(tmp_path),
            slot=dict(methods=["io", "io"]),
            provider_config=provider_config({}),
        ),
    )
    with pytest.raises(CloudConfigurationError, match="differs"):
        benchmark.worker(tmp_path, "p1")
