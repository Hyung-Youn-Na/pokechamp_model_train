"""Provider configuration, secret handling, and Z.ai Chat Completions transport."""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Mapping
from urllib.parse import quote, urlsplit, urlunsplit

from .constants import (
    OLLAMA_HOST,
    OLLAMA_MAX_OUTPUT_TOKENS,
    OLLAMA_MODEL,
)
from .transport_policy import CURRENT, ENV_NAME, LEGACY, policy_fields, version_of

CREDENTIAL_NAMES = ("OLLAMA_API_KEY", "ZAI_API_KEY", "TYPESAFE_API_KEY")


class CloudConfigurationError(RuntimeError):
    """Invalid configuration; no HTTP request is permitted."""

    category = "configuration"


def redact(value, environ=None):
    env = os.environ if environ is None else environ
    if isinstance(value, str):
        for name in CREDENTIAL_NAMES:
            secret = env.get(name, "")
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, Mapping):
        return {redact(key, env): redact(item, env) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, env) for item in value]
    return value


def credential_name(environ=None):
    env = os.environ if environ is None else environ
    return "ZAI_API_KEY" if env.get("POKECHAMP_PROVIDER", "ollama") == "zai" else "OLLAMA_API_KEY"


def provider_config(environ=None, *, require_key=False, legacy=False):
    """Resolve only non-secret settings; never instantiate a network client."""
    env = os.environ if environ is None else environ
    provider = env.get("POKECHAMP_PROVIDER", "ollama")
    if provider not in ("ollama", "zai"):
        raise CloudConfigurationError("POKECHAMP_PROVIDER must be ollama or zai")
    if env.get("POKECHAMP_MODEL", OLLAMA_MODEL) != OLLAMA_MODEL:
        raise CloudConfigurationError(f"POKECHAMP_MODEL must be the sealed model {OLLAMA_MODEL}")
    if provider == "ollama":
        base = env.get("OLLAMA_HOST", OLLAMA_HOST).rstrip("/")
        if base != OLLAMA_HOST:
            raise CloudConfigurationError(f"OLLAMA_HOST must be the sealed endpoint {OLLAMA_HOST}")
        endpoint = base + "/api/chat"
    else:
        base = env.get("ZAI_BASE_URL", "").rstrip("/")
        try:
            parsed = urlsplit(base)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname
                and parsed.port != 0
                and not parsed.username
                and not parsed.password
                and not parsed.query
                and not parsed.fragment
                and not any(c.isspace() or ord(c) < 32 for c in base)
                and not any(c in base for c in ("\\", "?", "#", "@"))
                and not parsed.path.endswith("/chat/completions")
            )
            hostname = parsed.hostname or ""
            if ":" in hostname:
                ipaddress.IPv6Address(hostname)
                hostname = "[" + hostname + "]"
            else:
                hostname = hostname.encode("idna").decode("ascii")
                valid = valid and all(
                    re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                    for label in hostname.rstrip(".").split(".")
                )
            if parsed.port and parsed.port != 443:
                hostname += ":" + str(parsed.port)
            valid = valid and not re.search(r"%(?![a-fA-F0-9]{2})", parsed.path)
            base = urlunsplit(
                ("https", hostname, quote(parsed.path, safe="/%:@-._~!$&'()*+,;="), "", "")
            )
        except (ValueError, UnicodeError):
            valid = False
        if not valid:
            raise CloudConfigurationError(
                "ZAI_BASE_URL must be an HTTPS API base URL before /chat/completions "
                "without credentials, query, or fragment"
            )
        endpoint = base + "/chat/completions"
    if require_key:
        name = credential_name(env)
        key = env.get(name, "")
        if not key.strip() or any(ord(c) < 32 or ord(c) > 126 for c in key):
            raise CloudConfigurationError(
                f"{name} is required as a valid API key in process or root .env"
            )
    if redact(endpoint, env) != endpoint:
        raise CloudConfigurationError("provider URL must not contain an API key")
    version = LEGACY if legacy else env.get(ENV_NAME, CURRENT)
    try:
        policy = policy_fields(version)
    except ValueError as error:
        raise CloudConfigurationError(str(error)) from error
    return dict(
        **policy,
        provider=provider,
        endpoint=endpoint,
        base_url=base,
        model=OLLAMA_MODEL,
        max_output_tokens=OLLAMA_MAX_OUTPUT_TOKENS,
        context_window=None,
        context_window_policy="provider_default",
        thinking_effort="low",
        stream=False,
        seed_applied=provider == "ollama",
        provider_fallback=False,
        **(dict(thinking={"type": "enabled"}, reasoning_effort="low") if provider == "zai" else {}),
    )


def prepared_provider(*, fake=False, legacy=False):
    if fake:
        return provider_config({}, legacy=legacy)
    from .dotenv import load_workspace_credential

    load_workspace_credential()
    return provider_config(legacy=legacy)


def sealed_provider(value):
    """Validate a stored configuration without consulting credentials or live defaults."""
    expected = value.get("provider_config", provider_config({}, legacy=True))
    env = dict(POKECHAMP_PROVIDER=expected.get("provider", "ollama"),
               ZAI_BASE_URL=expected.get("base_url", ""),
               POKECHAMP_TRANSPORT_POLICY=version_of(expected))
    if expected != provider_config(env):
        raise CloudConfigurationError("invalid sealed provider configuration")
    return expected


def verify_provider(value, *, environ=None):
    """Legacy plans without provider_config are sealed to Ollama, never auto-migrated."""
    expected = sealed_provider(value)
    env = dict(os.environ if environ is None else environ)
    env[ENV_NAME] = version_of(expected)
    if expected != provider_config(env):
        raise CloudConfigurationError(
            "sealed provider configuration differs from execution settings"
        )
    return expected


class ZaiChatClient:
    """Ollama-shaped internal response lets all battle validation share one boundary."""

    def __init__(self, *, host, timeout, api_key, transport=None):
        import httpx

        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self.endpoint = host + "/chat/completions"

    def chat(self, *, model, messages, stream, think, format, options):
        payload = dict(
            model=model,
            messages=messages,
            stream=False,
            thinking={"type": "enabled"},
            reasoning_effort="low",
            max_tokens=options["num_predict"],
            temperature=options["temperature"],
        )
        if format:
            payload["response_format"] = {"type": "json_object"}
        if options.get("stop"):
            payload["stop"] = options["stop"]
        response = self._client.post(self.endpoint, json=payload)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("choices"), list):
            raise ValueError("invalid Chat Completions response")
        choices = body["choices"]
        if len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("expected one Chat Completions choice")
        choice = choices[0]
        message = choice.get("message")
        if (
            not isinstance(message, dict)
            or not isinstance(message.get("content"), str)
            or not isinstance(choice.get("finish_reason"), str)
            or (
                message.get("reasoning_content") is not None
                and not isinstance(message["reasoning_content"], str)
            )
        ):
            raise ValueError("invalid Chat Completions message")
        usage = body.get("usage")
        if usage is None:
            usage = {}
        if not isinstance(usage, dict):
            raise ValueError("invalid Chat Completions usage")
        counts = {
            key: value if type(value) is int and value >= 0 else None
            for key, value in (
                ("prompt_tokens", usage.get("prompt_tokens")),
                ("completion_tokens", usage.get("completion_tokens")),
            )
        }
        return dict(
            model=body.get("model"),
            message=dict(content=message["content"], thinking=message.get("reasoning_content")),
            prompt_eval_count=counts["prompt_tokens"],
            eval_count=counts["completion_tokens"],
            done_reason=choice["finish_reason"],
            usage=usage,
        )
