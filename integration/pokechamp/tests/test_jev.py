"""JEV tests use injected transports and temporary credentials only."""

import json
import traceback

import httpx
import pytest

from integration.pokechamp import cli
from integration.pokechamp.dotenv import DotenvConfigurationError
from integration.pokechamp.jev import JevClient, JevRequestError
from integration.pokechamp.providers import CloudConfigurationError, provider_config, redact

KEY = "synthetic-jev-test-key"
QUESTIONS = {
    "route": {"type": "choice", "instructions": "Pick a route", "criteria": {"a": None, "b": "B"}},
    "score": {"type": "score", "instructions": {"task": "Rate"}, "criteria": ["Low", "High"]},
    "urgent": {"type": "noul", "instructions": ["Is it urgent?"]},
}
BODY = {
    "model": "jev-1.13.0",
    "answers": {
        "route": {
            "type": "choice",
            "choice": "a",
            "probabilities": {"a": 0.9, "b": 0.1},
            "confidence": 0.8,
        },
        "score": {
            "type": "score",
            "score": 0.7,
            "legend": {"0": "Low", "1": "High"},
            "probabilities": {"0": 0.3, "1": 0.7},
            "confidence": 0.4,
        },
        "urgent": {"type": "noul", "noul": 0.85},
    },
    "usage": {"input_tokens": 100, "output_tokens": 20},
    "additional_metadata": {"preserved": True},
}


def private_env(tmp_path, content):
    path = tmp_path / ".env"
    path.write_text(content)
    path.chmod(0o600)
    return path


def test_wire_response_and_context_cleanup(tmp_path):
    sent = []
    path = private_env(tmp_path, f"TYPESAFE_API_KEY={KEY}\n")
    with JevClient.from_env(
        environ={},
        path=path,
        transport=httpx.MockTransport(
            lambda req: sent.append(req) or httpx.Response(200, json=BODY)
        ),
    ) as client:
        assert sent == []
        assert client.evaluate(state={"ticket": "urgent"}, questions=QUESTIONS) == BODY
    assert client._client.is_closed
    assert len(sent) == 1
    req = sent[0]
    assert req.method == "POST"
    assert str(req.url) == "https://api.typesafe.ai/v1/systemone"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert req.headers["content-type"] == "application/json"
    assert req.extensions["timeout"] == dict(connect=60, read=60, write=60, pool=60)
    assert json.loads(req.content) == dict(
        model="jev-latest", state={"ticket": "urgent"}, questions=QUESTIONS
    )


def test_process_overrides_file_without_mutating_environment(tmp_path):
    path = private_env(
        tmp_path,
        f"TYPESAFE_API_KEY={KEY}\nTYPESAFE_BASE_URL=https://file.test/v1\nTYPESAFE_MODEL=file-model\nPOKECHAMP_PROVIDER=zai\n",
    )
    env = dict(
        TYPESAFE_API_KEY="process-key",
        TYPESAFE_BASE_URL="https://process.test/custom/",
        TYPESAFE_MODEL="pinned-model",
    )
    before = dict(env)
    sent = []
    with JevClient.from_env(
        environ=env,
        path=path,
        transport=httpx.MockTransport(
            lambda req: sent.append(req) or httpx.Response(200, json=BODY)
        ),
    ) as client:
        client.evaluate(state="ticket", questions=QUESTIONS)
    assert env == before
    assert str(sent[0].url) == "https://process.test/custom/systemone"
    assert sent[0].headers["authorization"] == "Bearer process-key"
    assert json.loads(sent[0].content)["model"] == "pinned-model"
    assert provider_config({})["provider"] == "ollama"


@pytest.mark.parametrize("name", ["TYPESAFE_API_KEY", "TYPESAFE_BASE_URL", "TYPESAFE_MODEL"])
def test_explicit_empty_process_value_fails_before_http(tmp_path, name):
    path = private_env(
        tmp_path,
        f"TYPESAFE_API_KEY={KEY}\nTYPESAFE_BASE_URL=https://file.test/v1\nTYPESAFE_MODEL=jev-latest\n",
    )
    with pytest.raises(CloudConfigurationError, match=name):
        JevClient.from_env(environ={name: ""}, path=path)


def test_missing_key_and_process_only_config(tmp_path):
    with pytest.raises(CloudConfigurationError, match="TYPESAFE_API_KEY"):
        JevClient.from_env(environ={}, path=tmp_path / "absent")
    with JevClient.from_env(environ={"TYPESAFE_API_KEY": KEY}, path=tmp_path / "absent") as client:
        assert client.model == "jev-latest"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://api.test/v1",
        "https://",
        "https://a:999999/v1",
        "https://a:0/v1",
        "https://u:p@a/v1",
        "https://a/v1?key=x",
        "https://a/v1#x",
        "https://a/v1?",
        "https://a/v1/systemone/",
        "https://a/a b",
        "https://a\\b/v1",
        "https://a/%xy",
        f"https://a/{KEY}",
    ],
)
def test_invalid_urls(url):
    with pytest.raises(CloudConfigurationError, match="TYPESAFE_BASE_URL") as error:
        JevClient(api_key=KEY, base_url=url)
    assert KEY not in str(error.value)


@pytest.mark.parametrize("key", ["", " ", "key\nsecret", "key secret", "키"])
def test_invalid_key(key):
    with pytest.raises(CloudConfigurationError, match="TYPESAFE_API_KEY"):
        JevClient(api_key=key)


def test_private_file_permission_symlink_and_duplicate_rules(tmp_path):
    path = private_env(tmp_path, f"TYPESAFE_API_KEY={KEY}\n")
    path.chmod(0o644)
    with pytest.raises(DotenvConfigurationError, match="chmod 600"):
        JevClient.from_env(environ={}, path=path)
    path.chmod(0o600)
    link = tmp_path / "linked"
    link.symlink_to(path)
    with pytest.raises(DotenvConfigurationError, match="symlink"):
        JevClient.from_env(environ={}, path=link)
    path.write_text(f"TYPESAFE_API_KEY={KEY}\nTYPESAFE_API_KEY=duplicate\n")
    with pytest.raises(DotenvConfigurationError, match="more than once"):
        JevClient.from_env(environ={}, path=path)


@pytest.mark.parametrize("failure", [401, 403, 429, 500, 302, "timeout", "transport", "json"])
def test_legacy_failures_are_sanitized_and_never_retried(failure):
    sent = []

    def handler(req):
        sent.append(req)
        if failure == "timeout":
            raise httpx.ReadTimeout(KEY, request=req)
        if failure == "transport":
            raise httpx.ConnectError(KEY, request=req)
        if failure == "json":
            return httpx.Response(200, text=KEY)
        return httpx.Response(failure, text=KEY, headers={"location": "https://other.test"})

    with JevClient(api_key=KEY, transport=httpx.MockTransport(handler), retry_policy="jev-no-retry-v1") as client:
        with pytest.raises(JevRequestError) as error:
            client.evaluate(state="ticket", questions=QUESTIONS)
    assert len(sent) == 1
    assert KEY not in "".join(traceback.format_exception(error.value))
    assert error.value.__context__ is None
    expected = (
        failure
        if failure in ("timeout", "transport")
        else "invalid_response"
        if failure == "json"
        else "http"
    )
    assert error.value.category == expected
    assert error.value.status_code == (failure if isinstance(failure, int) else None)
    assert client._client.is_closed


@pytest.mark.parametrize(
    "update",
    [
        None,
        {"model": None},
        {"answers": {}},
        {"answers": {"route": {"type": "noul"}}},
        {"usage": None},
    ],
)
def test_invalid_response_shape(update):
    body = [] if update is None else {**BODY, **update}
    with JevClient(
        api_key=KEY, transport=httpx.MockTransport(lambda req: httpx.Response(200, json=body))
    ) as client:
        with pytest.raises(JevRequestError, match="invalid_response"):
            client.evaluate(state=[], questions=QUESTIONS)


def test_shared_redaction_and_child_environment(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", KEY)
    assert redact({"nested": [KEY]}) == {"nested": ["[REDACTED]"]}
    assert KEY not in str(cli._safe_error(ValueError(KEY)))
    assert "TYPESAFE_API_KEY" not in cli._child_environment()
