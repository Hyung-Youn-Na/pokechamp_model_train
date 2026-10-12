import json
from types import SimpleNamespace

import pytest

from integration.pokechamp import cli
from integration.pokechamp.cloud import (
    CloudConfigurationError,
    CloudRequestError,
    OllamaCloudBackend,
)
from integration.pokechamp.constants import (
    OLLAMA_CONTEXT_WINDOW,
    OLLAMA_HOST,
    OLLAMA_MAX_OUTPUT_TOKENS,
    OLLAMA_MODEL,
    OLLAMA_THINKING_EFFORT,
)


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def fake_response(content='{"status":"ok"}'):
    return SimpleNamespace(
        model=OLLAMA_MODEL,
        message=SimpleNamespace(content=content, thinking="not persisted"),
        prompt_eval_count=11,
        eval_count=4,
        total_duration=123,
        load_duration=12,
        done_reason="stop",
    )


def test_missing_key_fails_before_client_creation():
    created = False

    def factory(**kwargs):
        nonlocal created
        created = True
        return FakeClient()

    with pytest.raises(CloudConfigurationError, match="OLLAMA_API_KEY"):
        OllamaCloudBackend(environ={}, client_factory=factory)
    assert created is False


@pytest.mark.parametrize(
    ("variable", "value"),
    [("OLLAMA_HOST", "http://localhost:11434"), ("POKECHAMP_MODEL", "other")],
)
def test_sealed_configuration_rejects_overrides(variable, value):
    environment = {"OLLAMA_API_KEY": "test-placeholder", variable: value}
    with pytest.raises(CloudConfigurationError):
        OllamaCloudBackend(environ=environment, client_factory=lambda **_: FakeClient())


def test_request_uses_sealed_cloud_contract_and_safe_metadata():
    client = FakeClient(response=fake_response())
    factory_args = {}

    def factory(**kwargs):
        factory_args.update(kwargs)
        return client

    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"}, client_factory=factory
    )
    output, valid, raw = backend.get_LLM_action(
        "system",
        "user",
        f"ollama/{OLLAMA_MODEL}",
        temperature=0.2,
        stop=["stop"],
        max_tokens=999,
    )

    assert factory_args["host"] == OLLAMA_HOST
    assert factory_args["timeout"].as_dict() == dict(connect=300, read=600, write=300, pool=300)
    assert output == '{"status":"ok"}'
    assert valid is True
    assert raw == ""
    assert len(client.calls) == 1
    request = client.calls[0]
    assert request["model"] == OLLAMA_MODEL
    assert request["stream"] is False
    assert request["think"] == OLLAMA_THINKING_EFFORT
    assert request["format"] == "json"
    assert request["options"] == {
        "temperature": 0.2,
        "num_predict": OLLAMA_MAX_OUTPUT_TOKENS,
        "seed": 100,
        "stop": ["stop"],
    }
    assert "num_ctx" not in request["options"]
    assert backend.prompt_tokens == 11
    assert backend.completion_tokens == 4
    assert "system" not in repr(backend.call_records)
    assert "user" not in repr(backend.call_records)
    assert "test-placeholder" not in repr(backend.call_records)
    forbidden = {"system_prompt", "user_prompt", "raw_content", "provider_reasoning"}
    assert forbidden.isdisjoint(backend.call_records[0])


def test_research_trace_receives_effective_wire_prompt_reasoning_and_raw_content():
    class TraceSink:
        def __init__(self):
            self.calls = []

        def record_llm_call(self, **payload):
            self.calls.append(payload)

    trace = TraceSink()
    client = FakeClient(response=fake_response(content='prefix {"move":"Thunder Bolt"}'))
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"},
        client_factory=lambda **_: client,
        trace_sink=trace,
    )
    battle = SimpleNamespace(
        turn=4,
        available_moves=[SimpleNamespace(id="thunderbolt")],
        available_switches=[],
    )
    backend.get_LLM_action("wire-system", "wire-user", OLLAMA_MODEL, battle=battle)

    assert len(trace.calls) == 1
    call = trace.calls[0]
    assert call["system_prompt"] == "wire-system"
    assert call["user_prompt"].startswith("wire-user")
    assert call["user_prompt"].endswith(
        "Do not include reasoning, explanation, or Markdown in message.content."
    )
    assert call["provider_reasoning"] == "not persisted"
    assert call["raw_content"] == 'prefix {"move":"Thunder Bolt"}'
    assert call["canonical_parsed_output"] == {"move": "Thunder Bolt"}
    assert call["validation"] == {
        "json_valid": True,
        "battle_action_valid": True,
        "output_contract_valid": True,
    }
    assert call["request"]["thinking_effort"] == OLLAMA_THINKING_EFFORT
    assert call["response"]["completion_tokens"] == 4
    assert call["showdown_turn"] == 4


def test_research_trace_records_provider_failure_without_changing_failure_semantics():
    class TraceSink:
        def __init__(self):
            self.calls = []

        def record_llm_call(self, **payload):
            self.calls.append(payload)

    trace = TraceSink()
    client = FakeClient(error=TimeoutError())
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"},
        client_factory=lambda **_: client,
        trace_sink=trace,
    )
    with pytest.raises(CloudRequestError) as captured:
        backend.get_LLM_action("s", "u", OLLAMA_MODEL)
    assert captured.value.category == "timeout"
    assert len(client.calls) == 1
    assert trace.calls[0]["status"] == "failure"
    assert trace.calls[0]["validation"]["category"] == "timeout"


def test_qualification_manifest_shape_remains_content_minimized():
    response = fake_response(content='{"status":"ok"}')
    response.message = SimpleNamespace(
        content='{"status":"ok"}', thinking="private-reasoning-marker"
    )
    client = FakeClient(response=response)
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "qualification-secret-marker"},
        client_factory=lambda **_: client,
    )
    backend.get_LLM_action("private-system-marker", "private-user-marker", OLLAMA_MODEL)
    manifest = cli._base_manifest("smoke-cloud")
    manifest["result"] = {"calls": backend.call_records}
    serialized = json.dumps(manifest)
    for forbidden in (
        "private-system-marker",
        "private-user-marker",
        "private-reasoning-marker",
        "qualification-secret-marker",
        "system_prompt",
        "user_prompt",
        "provider_reasoning",
        "raw_content",
    ):
        assert forbidden not in serialized


def test_invalid_json_fails_closed_after_one_provider_call():
    client = FakeClient(response=fake_response(content=""))
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"},
        client_factory=lambda **_: client,
    )

    with pytest.raises(CloudRequestError) as captured:
        backend.get_LLM_action("s", "u", OLLAMA_MODEL, json_format=True)

    assert captured.value.category == "output_contract"
    assert len(client.calls) == 1
    assert backend.failure_event.is_set()
    assert backend.call_records[0]["status"] == "failure"
    assert backend.call_records[0]["json_valid"] is False
    assert backend.call_records[0]["output_contract_valid"] is False


def test_unavailable_battle_action_fails_without_recording_selection():
    client = FakeClient(response=fake_response(content='{"move":"surf"}'))
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"},
        client_factory=lambda **_: client,
    )
    battle = SimpleNamespace(
        available_moves=[SimpleNamespace(id="thunderbolt")],
        available_switches=[],
    )

    with pytest.raises(CloudRequestError) as captured:
        backend.get_LLM_action("s", "u", OLLAMA_MODEL, json_format=True, battle=battle)

    assert captured.value.category == "output_contract"
    assert backend.call_records[0]["battle_action_valid"] is False
    assert "surf" not in repr(backend.call_records)


def test_available_battle_action_satisfies_output_contract():
    client = FakeClient(response=fake_response(content='{"move":"Thunder Bolt"}'))
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"},
        client_factory=lambda **_: client,
    )
    battle = SimpleNamespace(
        available_moves=[SimpleNamespace(id="thunderbolt")],
        available_switches=[],
    )

    output, valid, _ = backend.get_LLM_action(
        "s", "u", OLLAMA_MODEL, json_format=True, battle=battle
    )

    assert output == '{"move":"Thunder Bolt"}'
    assert valid is True
    assert backend.call_records[0]["battle_action_valid"] is True
    assert backend.call_records[0]["output_contract_valid"] is True
    request = client.calls[0]
    assert request["think"] == "low"
    assert request["options"]["num_predict"] == OLLAMA_MAX_OUTPUT_TOKENS
    assert request["messages"][1]["content"].endswith(
        "Do not include reasoning, explanation, or Markdown in message.content."
    )


class ProviderStatusError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (ProviderStatusError(401), "auth"),
        (ProviderStatusError(404), "model"),
        (ProviderStatusError(429), "rate_limit"),
        (TimeoutError(), "timeout"),
        (ConnectionError(), "transport"),
        (RuntimeError(), "provider"),
    ],
)
def test_v1_provider_failure_is_classified_and_never_retried_or_fallbacked(error, category):
    client = FakeClient(error=error)
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder", "POKECHAMP_TRANSPORT_POLICY": "connect-retry-v1"},
        client_factory=lambda **_: client,
    )

    for _ in range(2):
        with pytest.raises(CloudRequestError) as captured:
            backend.get_LLM_action("s", "u", OLLAMA_MODEL)
        assert captured.value.category == category

    assert len(client.calls) == 1
    assert backend.failure_event.is_set()
    assert len(backend.call_records) == 1
    assert backend.call_records[0]["network_called"] is True
    assert backend.call_records[0]["http_elapsed_ms"] >= 0
    assert [
        {
            k: v
            for k, v in backend.call_records[0].items()
            if k
            in {
                "status",
                "category",
                "endpoint",
                "requested_model",
                "elapsed_ms",
                "requested_output_tokens",
                "context_window",
            }
        }
    ] == [
        {
            "status": "failure",
            "category": category,
            "endpoint": OLLAMA_HOST + "/api/chat",
            "requested_model": OLLAMA_MODEL,
            "elapsed_ms": backend.call_records[0]["elapsed_ms"],
            "requested_output_tokens": OLLAMA_MAX_OUTPUT_TOKENS,
            "context_window": OLLAMA_CONTEXT_WINDOW,
        }
    ]


def test_requested_model_cannot_drift():
    client = FakeClient(response=fake_response())
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"},
        client_factory=lambda **_: client,
    )
    with pytest.raises(CloudConfigurationError, match="requested model"):
        backend.get_LLM_action("s", "u", "ollama/other")
    assert client.calls == []
    assert backend.failure_event.is_set()
    assert backend.call_records[0]["network_called"] is False


def test_query_protocol_matches_pokechamp_two_value_unpacking():
    client = FakeClient(response=fake_response())
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"},
        client_factory=lambda **_: client,
    )
    output, valid = backend.get_LLM_query("s", "u", json_format=True)
    assert output == '{"status":"ok"}'
    assert valid is True


@pytest.mark.parametrize("upstream_limit", [20, 64, 100, 500])
def test_upstream_small_limits_do_not_restore_output_cap(upstream_limit):
    content = json.dumps({"numbers": list(range(300))})
    client = FakeClient(response=fake_response(content=content))
    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "test-placeholder"},
        client_factory=lambda **_: client,
    )
    output, valid, _ = backend.get_LLM_action(
        "system", "user", OLLAMA_MODEL, max_tokens=upstream_limit
    )
    assert valid and json.loads(output) == json.loads(content)
    assert client.calls[0]["options"]["num_predict"] == 131072
    assert "num_ctx" not in client.calls[0]["options"]
    assert backend.call_records[0]["requested_output_tokens"] == 131072
    assert backend.call_records[0]["context_window"] is None
