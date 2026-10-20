"""Z.ai planner transport and a deterministic, network-free planner double."""
from __future__ import annotations

import asyncio
import copy
import inspect
import json
import os
import re
import time

import httpx

from integration.pokechamp.dotenv import DOTENV_PATH, load_workspace_credential
from integration.pokechamp.providers import CloudConfigurationError, provider_config, redact
from integration.pokechamp.transport_policy import (
    CURRENT, error_details, policy_fields, retry_reason, timeout_for,
)
from .core import PlanOutputError, parse_plan


class PlannerTransportError(RuntimeError):
    scope = "collection"

    def __init__(self, category, *, status_code=None, metadata=None):
        self.category = category
        self.status_code = status_code
        self.metadata = copy.deepcopy(metadata or {})
        suffix = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"Z.ai planner request failed: {category}{suffix}")


class ZaiPlannerClient:
    """Construction is network-free; each physical attempt is separately recorded."""
    def __init__(self, config, *, api_key, base_url, record=None, transport=None,
                 before_attempt=None, remaining=None, cancelled=None, sleep=asyncio.sleep,
                 environ=None):
        self.config = copy.deepcopy(config)
        env = dict(os.environ if environ is None else environ)
        env.update(POKECHAMP_PROVIDER="zai", ZAI_BASE_URL=base_url, ZAI_API_KEY=api_key)
        # Reuse the credential/HTTPS validator while keeping legacy generation
        # defaults untouched. Planner options are owned only by this new config.
        settings = provider_config(env, require_key=True)
        if config.get("provider", "zai") != "zai":
            raise CloudConfigurationError("planner provider must be zai")
        model = config.get("model")
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model):
            raise CloudConfigurationError("invalid planner model")
        self.policy = copy.deepcopy(config.get("transport", policy_fields(CURRENT)))
        if self.policy != policy_fields(CURRENT):
            raise CloudConfigurationError("planner requires the frozen provider-retry-v2 policy")
        self.endpoint = settings["endpoint"]
        self._env = env
        self.record = record or (lambda event: None)
        self.before_attempt = before_attempt
        self.remaining = remaining
        self.cancelled = cancelled
        self.sleep = sleep
        self._loop = None
        self._closed = False
        self._client = httpx.AsyncClient(
            timeout=timeout_for(self.policy), transport=transport, follow_redirects=False,
            headers={"Authorization": "Bearer " + api_key}, trust_env=False)

    @classmethod
    def from_env(cls, config, *, environ=None, path=DOTENV_PATH, **kwargs):
        env = dict(os.environ if environ is None else environ)
        load_workspace_credential(environ=env, path=path)
        return cls(config, api_key=env.get("ZAI_API_KEY", ""),
                   base_url=env.get("ZAI_BASE_URL", ""), environ=env, **kwargs)

    def _save(self, event):
        self.record(redact(copy.deepcopy(event), self._env))

    def _check_admission(self):
        if self._closed:
            raise PlannerTransportError("client_closed")
        if self.cancelled is not None and self.cancelled():
            raise asyncio.CancelledError("planner collection cancelled")
        remaining = self.remaining() if self.remaining is not None else None
        if remaining is not None and remaining <= 0:
            raise PlannerTransportError("deadline")
        return remaining

    def _request(self, messages):
        config = self.config
        if (not isinstance(messages, list) or not messages
                or any(not isinstance(m, dict) or set(m) != {"role", "content"}
                       or m["role"] not in ("system", "user", "assistant")
                       or not isinstance(m["content"], str) for m in messages)):
            raise CloudConfigurationError("invalid planner messages")
        return dict(model=config["model"], messages=copy.deepcopy(messages), stream=False,
                    thinking=copy.deepcopy(config["thinking"]),
                    reasoning_effort=config["reasoning_effort"], temperature=config["temperature"],
                    top_p=config["top_p"], max_tokens=config["max_tokens"],
                    response_format={"type": "json_object"})

    async def plan(self, messages, *, request_id):
        # An absent field belongs to a legacy frozen run and retains zero retries.
        retries = self.config.get("json_retries", 0)
        if type(retries) is not int or not 0 <= retries <= 5:
            raise CloudConfigurationError("planner.json_retries must be an integer from 0 to 5")
        scope = self.config.get("retry_scope", "json_syntax")
        if scope not in ("json_syntax", "response_format"):
            raise CloudConfigurationError("invalid planner.retry_scope")
        started, physical = time.monotonic(), 0
        for generation in range(1, retries + 2):
            self._check_admission()
            value = await self._plan_generation(messages, request_id=request_id,
                physical_start=physical, json_attempt=generation)
            physical = value["http_attempts"]
            syntax_error = None
            if value.get("envelope_error") is None:
                try:
                    json.loads(value["content"])
                except json.JSONDecodeError as error:
                    syntax_error = str(error)
            format_error = value.get("envelope_error")
            if format_error is None:
                try:
                    parse_plan(value["content"], finish_reason=value["finish_reason"])
                except PlanOutputError as error:
                    format_error = str(error)
            output_error = format_error if scope == "response_format" else syntax_error
            if retries or scope == "response_format":
                self._save(dict(type="planner_output_attempt", request_id=request_id,
                    decision=request_id, json_attempt=generation, json_valid=syntax_error is None,
                    json_error=syntax_error, format_valid=format_error is None,
                    format_error=format_error, retry_scope=scope, **value))
            if output_error is None or generation > retries:
                if value.get("envelope_error"):
                    raise PlanOutputError(value["envelope_error"])
                value["elapsed_seconds"] = time.monotonic() - started
                if retries or scope == "response_format":
                    value["json_attempts"] = generation
                    value["retry_scope"] = scope
                return value
            self._save(dict(type="planner_json_retry" if syntax_error else "planner_format_retry",
                request_id=request_id, decision=request_id, json_attempt=generation,
                next_json_attempt=generation + 1, json_retries_limit=retries,
                retry_scope=scope, reason="content_json_syntax" if syntax_error else "response_format",
                error=output_error))

    async def _plan_generation(self, messages, *, request_id, physical_start=0, json_attempt=1):

        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise PlannerTransportError("client_event_loop_changed")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", request_id):
            raise CloudConfigurationError("invalid planner logical request ID")
        payload = self._request(messages)
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        started = time.monotonic()
        last = None
        for attempt in range(1, self.policy["provider_retries"] + 2):
            remaining = self._check_admission()
            if self.before_attempt is not None:
                admitted = self.before_attempt(request_id=request_id, attempt=physical_start + attempt)
                if inspect.isawaitable(admitted):
                    await admitted
            # Admission hooks may wait on permits; recheck the remaining clock.
            remaining = self._check_admission()
            metadata = dict(type="planner_transport", request_id=request_id, decision=request_id,
                            model=payload["model"], endpoint=self.endpoint, attempt=physical_start + attempt,
                            transport_attempt=attempt, json_attempt=json_attempt,
                            network_called=True, status="failure", http_status=None,
                            request_body=raw, response_body=None, usage=None, cost=None,
                            transport_policy_version=CURRENT, retry_after=None)
            attempt_started = time.monotonic()
            error = None
            response = None
            try:
                response = await self._client.post(
                    self.endpoint, content=raw.encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    timeout=timeout_for(self.policy, remaining))
                metadata.update(http_status=response.status_code, response_body=response.text,
                                retry_after=response.headers.get("retry-after"))
                response.raise_for_status()
            except httpx.HTTPError as failure:
                error = failure
            except asyncio.CancelledError:
                metadata.update(error_type="CancelledError", error_message="planner request cancelled",
                                retryable=False, elapsed_seconds=time.monotonic() - attempt_started)
                self._save(metadata)
                raise
            metadata["elapsed_seconds"] = time.monotonic() - attempt_started
            if error is not None:
                reason = retry_reason(self.policy, error, metadata)
                retryable = reason is not None and attempt <= self.policy["provider_retries"]
                metadata.update(error_details(error, lambda value: redact(value, self._env)))
                metadata.update(retry_reason=reason, retryable=retryable)
                status = metadata["http_status"]
                category = ("rate_limit" if status == 429 else "http" if status is not None
                            else "timeout" if isinstance(error, httpx.TimeoutException) else "transport")
                metadata["category"] = category
                self._save(metadata)
                last = PlannerTransportError(category, status_code=status,
                    metadata=redact(metadata, self._env))
                if not retryable:
                    raise last from None
                delay = self.policy["retry_delays_seconds"][attempt - 1]
                self._save(dict(type="planner_retry", request_id=request_id, decision=request_id,
                                attempt=physical_start + attempt, next_attempt=physical_start + attempt + 1,
                                transport_attempt=attempt, json_attempt=json_attempt, delay_seconds=delay,
                                retry_reason=reason))
                # asyncio.sleep is cancellation-aware. Small slices also observe
                # a coordinator cancellation flag without holding an HTTP client.
                remaining_delay = delay
                while remaining_delay > 0:
                    self._check_admission()
                    step = min(0.1, remaining_delay) if self.cancelled is not None else remaining_delay
                    await self.sleep(step)
                    remaining_delay = max(0.0, remaining_delay - step)
                continue
            # HTTP recovery ends here; public plan() separately handles content JSON syntax.
            metadata.update(status="success", retryable=False, retry_reason=None)
            try:
                body = response.json()
                if isinstance(body, dict) and isinstance(body.get("usage"), dict):
                    metadata["usage"] = copy.deepcopy(body["usage"])
                normalized = self._normalize(body)
                metadata["usage"] = normalized["usage"]
            except (ValueError, KeyError, TypeError) as failure:
                metadata.update(output_error=True, error_type=type(failure).__name__,
                                error_message="invalid planner response envelope")
                self._save(metadata)
                if self.config.get("retry_scope") != "response_format":
                    raise PlanOutputError("invalid planner response envelope") from None
                return redact(dict(content=None, reasoning=None, plan=None,
                    usage=metadata["usage"], model=self.config["model"], finish_reason=None,
                    envelope_error="invalid planner response envelope",
                    elapsed_seconds=time.monotonic() - started,
                    http_attempts=physical_start + attempt), self._env)
            self._save(metadata)
            normalized["elapsed_seconds"] = time.monotonic() - started
            normalized["http_attempts"] = physical_start + attempt
            normalized = redact(normalized, self._env)
            # Parse here only to supply the normalized plan; core repeats the shape
            # check at its trust boundary. Preserve bad content for core recording.
            try:
                normalized["plan"] = parse_plan(normalized["content"],
                    finish_reason=normalized["finish_reason"])
            except PlanOutputError:
                normalized["plan"] = None
            return normalized
        raise last  # pragma: no cover - loop always returns or raises

    @staticmethod
    def _normalize(body):
        if not isinstance(body, dict) or not isinstance(body.get("choices"), list):
            raise ValueError("missing choices")
        choices = body["choices"]
        if len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("expected one planner choice")
        message = choices[0].get("message")
        if (not isinstance(message, dict) or not isinstance(message.get("content"), str)
                or message.get("reasoning_content") is not None
                and not isinstance(message["reasoning_content"], str)
                or not isinstance(choices[0].get("finish_reason"), str)):
            raise ValueError("invalid planner message")
        usage = body.get("usage")
        if usage is not None and not isinstance(usage, dict):
            raise ValueError("invalid planner usage")
        return dict(content=message["content"], reasoning=message.get("reasoning_content"),
                    usage=copy.deepcopy(usage), model=body.get("model"),
                    finish_reason=choices[0]["finish_reason"])

    async def aclose(self):
        self._closed = True
        loop = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not loop:
            if not self._loop.is_running():
                raise PlannerTransportError("client_owner_loop_stopped_before_cleanup")
            future = asyncio.run_coroutine_threadsafe(self._client.aclose(), self._loop)
            await asyncio.wrap_future(future)
        else:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()


class MockPlanner:
    """Deterministic output double; bad_response injects raw malformed content."""
    def __init__(self, bad_response=None):
        self.bad_response = bad_response
        self.calls = []

    async def plan(self, messages, *, request_id):
        self.calls.append(dict(request_id=request_id, messages=copy.deepcopy(messages)))
        plan = dict(objective="Preserve a route to victory while improving the current position.",
                    priorities=["Use current public evidence to compare safe pressure and positioning."],
                    preserve=[], threats=[], tera_policy="Use Tera when its supported benefit justifies the resource.",
                    contingencies=[{"if": "A public event changes the active threat.",
                                    "then": "Reassess the route to victory against the current observation."}])
        content = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
        if self.bad_response is not None:
            content = self.bad_response
            plan = None
        return dict(plan=plan, content=content, reasoning="Mock planner; no model was called.",
                    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    model="mock-glm-planner", elapsed_seconds=0.0, finish_reason="stop", http_attempts=0)

    async def aclose(self):
        return None
