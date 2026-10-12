"""Fail-closed multi-provider cloud backend for the pinned PokéChamp interface."""

from __future__ import annotations

import contextlib
import copy
import json
import os
import re
import threading
import time
import uuid
import warnings
from collections.abc import Callable, Mapping, Sequence
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .constants import (
    OLLAMA_CONTEXT_WINDOW,
    OLLAMA_MAX_OUTPUT_TOKENS,
    OLLAMA_MODEL,
    OLLAMA_THINKING_EFFORT,
    RANDOM_SEED,
)
from .providers import CloudConfigurationError, ZaiChatClient, provider_config, redact
from .transport_policy import (
    CURRENT,
    connection_failure,
    error_details,
    retry_reason,
    timeout_for,
    version_of,
    wait_retry,
)


class CloudRequestError(RuntimeError):
    """A classified cloud request failure with no provider/model fallback."""

    def __init__(self, category: str, detail: str) -> None:
        self.category = category
        super().__init__(f"Cloud request failed ({category}): {detail}")


def _default_client_factory(*, host: str, timeout: float) -> Any:
    import ollama

    return ollama.Client(host=host, timeout=timeout)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _token_count(response, name):
    value = _field(response, name)
    return value if type(value) is int and value >= 0 else None


def _extract_json(text: str) -> tuple[str, bool]:
    """Return canonical JSON from a response without accepting Python literals."""

    stripped = text.strip()
    candidates = [stripped]
    for marker in ("{", "["):
        start = stripped.find(marker)
        if start >= 0 and stripped[start:] not in candidates:
            candidates.append(stripped[start:])

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue
        return json.dumps(parsed, ensure_ascii=False, separators=(",", ":")), True
    return text, False


def _extract_upstream(text):
    # Pinned OllamaPlayer extraction; its success flag is not a JSON validity check.
    start = text.find('{"')
    if start >= 0:
        part = text[start:]
        end = part.find("}")
        if end > 0:
            return part[: end + 1]
    elif text.startswith('"'):
        part = '{"' + text
        end = part.find("}")
        if end > 0:
            return part[: end + 1]
    else:
        match = re.search(r"\{[^}]*\}", text)
        if match:
            return match.group(0)
    return text


class OllamaCloudBackend:
    """Shared battle adapter; historical class name retained for imports/subclasses.

    The API key is received through the resolved process environment. The parent CLI
    may populate it from the ignored workspace ``.env`` file. This object records
    only whether a credential was present and non-secret request/response metadata.
    """

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        client_factory: Callable[..., Any] | None = None,
        trace_sink: Any | None = None,
        transport_policy_version: str | None = None,
    ) -> None:
        env = dict(os.environ if environ is None else environ)
        from .providers import verify_provider
        from .transport_policy import ENV_NAME, LEGACY, version_of

        if transport_policy_version is not None:
            env[ENV_NAME] = transport_policy_version

        root = (env.get("POKECHAMP_LEAD_STUDY_ROOT") or env.get("POKECHAMP_AB_HEAD_TO_HEAD_ROOT")
                or env.get("POKECHAMP_A_DIAGNOSTIC_ROOT"))
        if root and (Path(root) / "plan.json").exists():
            from .benchmark import read_sealed

            sealed = read_sealed(Path(root) / "plan.json")
            if sealed.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
                from .distributed_lead import for_actor
                sealed = for_actor(sealed, env.get("POKECHAMP_IO_ACTOR"))
            settings = verify_provider(sealed, environ=env)
            env[ENV_NAME] = version_of(settings)
        elif env.get("POKECHAMP_IO_STUDY_ROOT"):
            # This legacy journal has no versioned provider configuration.
            env[ENV_NAME] = LEGACY
        self.provider_settings = provider_config(env, require_key=True)
        self.provider = self.provider_settings["provider"]
        self.host = self.provider_settings["base_url"]
        self.endpoint = self.provider_settings["endpoint"]
        self._secret_environment = {k: env.get(k, "") for k in ("OLLAMA_API_KEY", "ZAI_API_KEY")}
        self.model = OLLAMA_MODEL
        self.request_timeout = self.provider_settings["request_timeout_seconds"]
        self.max_output_tokens = OLLAMA_MAX_OUTPUT_TOKENS
        self.context_window = OLLAMA_CONTEXT_WINDOW
        self.credential_present = True
        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.call_records: list[dict[str, Any]] = []
        self.terminal_error: CloudRequestError | CloudConfigurationError | None = None
        self.failure_event = threading.Event()
        self.trace_sink = trace_sink
        factory = _default_client_factory if client_factory is None else client_factory
        if self.provider == "zai" and client_factory is None:
            self.client = ZaiChatClient(
                host=self.host, timeout=timeout_for(self.provider_settings), api_key=env["ZAI_API_KEY"]
            )
        else:
            self.client = factory(host=self.host, timeout=timeout_for(self.provider_settings))
            transport = getattr(self.client, "_client", None)
            if transport is not None and hasattr(transport, "headers"):
                name = "ZAI_API_KEY" if self.provider == "zai" else "OLLAMA_API_KEY"
                transport.headers["Authorization"] = "Bearer " + env[name]
        self.permit_socket = env.get("POKECHAMP_PERMIT_SOCKET")
        self.cancel_path = env.get("POKECHAMP_CANCEL_PATH")
        self.batch_deadline = float(env.get("POKECHAMP_BATCH_DEADLINE", "0"))
        self.http_metadata = {}
        self.head_to_head_root = env.get("POKECHAMP_AB_HEAD_TO_HEAD_ROOT")
        self.lead_study_root = env.get("POKECHAMP_LEAD_STUDY_ROOT")
        self.diagnostic_root = self.lead_study_root or self.head_to_head_root or env.get("POKECHAMP_A_DIAGNOSTIC_ROOT")
        from . import a_diagnostic, ab_head_to_head

        self.request_ledger = ab_head_to_head if self.head_to_head_root else a_diagnostic
        if self.lead_study_root:
            from . import team_preview_study

            self.request_ledger = team_preview_study
        self.diagnostic_actor = env.get("POKECHAMP_IO_ACTOR")
        self.io_journal = {
            "root": env.get("POKECHAMP_IO_STUDY_ROOT"),
            "cohort": env.get("POKECHAMP_IO_COHORT"),
            "stage": env.get("POKECHAMP_IO_STAGE"),
            "actor": env.get("POKECHAMP_IO_ACTOR"),
        }
        if self.diagnostic_root:
            self.io_journal = dict.fromkeys(self.io_journal)
        if any(self.io_journal.values()) and not all(self.io_journal.values()):
            raise CloudConfigurationError("incomplete battle-only request journal")
        transport = getattr(self.client, "_client", None)
        if transport is not None and hasattr(transport, "event_hooks"):
            transport.event_hooks["response"].append(self._http_response)
            if self.lead_study_root:
                transport.event_hooks["request"].append(self._http_request)

    def _http_request(self, request):
        try:
            self.request_ledger.check_admission(self.lead_study_root)
        except Exception:
            self.http_metadata["network_called"] = False
            self.http_metadata.pop("http_started_at", None)
            raise

    def _http_response(self, response):
        if (response.status_code == 429 and self.lead_study_root
                and version_of(self.provider_settings) != CURRENT):
            self.request_ledger.halt_on_429(self.lead_study_root)
        self.http_metadata["http_status"] = response.status_code
        self.http_metadata["retry_after"] = response.headers.get("Retry-After")

    def _halt_exhausted_429(self):
        from . import a_diagnostic
        from .benchmark import seal_json

        if self.diagnostic_root:
            root = Path(self.diagnostic_root)
            with a_diagnostic.locked(root):
                if not (root / "halt.json").exists():
                    seal_json(root / "halt.json", dict(
                        category="rate_limit", http_status=429, at=time.time(),
                        transport_policy_version=CURRENT, retry_exhausted=True,
                    ))
        elif self.io_journal["root"]:
            from .improved_io.battle_only_budget import halt
            halt(Path(self.io_journal["root"]), self.io_journal["cohort"],
                 "rate_limit", {"retry_exhausted": True, "transport_policy_version": CURRENT})

    def _cancelled(self):
        if (version_of(self.provider_settings) == CURRENT and self.io_journal["root"]
                and (Path(self.io_journal["root"]) / f"halt-{self.io_journal['cohort']}.json").exists()):
            return True
        if self.diagnostic_root:
            collection_deadline = self.request_ledger.collection_deadline

            self.batch_deadline = collection_deadline(self.diagnostic_root) or 0
            if (Path(self.diagnostic_root) / "halt.json").exists():
                return True
        return (
            self.failure_event.is_set()
            or bool(self.cancel_path and Path(self.cancel_path).exists())
            or bool(self.batch_deadline and time.time() >= self.batch_deadline)
        )

    @contextlib.contextmanager
    def _admission(self, *, before=None):
        from .permits import Permit, PermitCancelled

        self.http_metadata = {
            "permit_wait_ms": 0, "network_called": False,
            "http_timeout_seconds": self.request_timeout,
        }
        if self._cancelled():
            raise PermitCancelled("cancelled before HTTP")
        permit = (
            Permit(self.permit_socket, self.model, cancelled=self._cancelled)
            if self.permit_socket
            else contextlib.nullcontext()
        )
        with permit as lease:
            if self._cancelled():
                raise PermitCancelled("cancelled before HTTP")
            self.http_metadata["permit_wait_ms"] = lease.wait_ms if lease else 0
            if before is not None:
                before()
            if self.lead_study_root:
                self.request_ledger.check_admission(self.lead_study_root)
            if self._cancelled():
                raise PermitCancelled("cancelled after reservation")
            transport = getattr(self.client, "_client", None)
            if transport is not None:
                remaining = self.batch_deadline - time.time() if self.batch_deadline else None
                if "transport_policy_version" not in self.provider_settings and not self.diagnostic_root:
                    remaining = None  # Preserve the legacy non-ledger transport exactly.
                transport.timeout = timeout_for(self.provider_settings, remaining)
                self.http_metadata["effective_http_timeout"] = transport.timeout.as_dict()
                self.http_metadata["http_timeout_seconds"] = transport.timeout.read
            self.http_metadata["network_called"] = True
            self.http_metadata["http_started_at"] = time.time()
            started = time.monotonic()
            try:
                yield
            except Exception as error:
                status = getattr(error, "status_code", self.http_metadata.get("http_status"))
                self.http_metadata["http_status"] = status
                if status == 429 and version_of(self.provider_settings) != CURRENT:
                    if self.lead_study_root:
                        self.request_ledger.halt_on_429(self.lead_study_root)
                    raw = self.http_metadata.get("retry_after")
                    try:
                        delay = max(0, float(raw))
                    except (TypeError, ValueError):
                        try:
                            delay = max(0, parsedate_to_datetime(raw).timestamp() - time.time())
                        except (TypeError, ValueError, AttributeError):
                            delay = 30
                    if not 0 <= delay < float("inf"):
                        delay = 30
                    self.http_metadata["cooldown_seconds"] = delay
                    if lease:
                        lease.cooldown = delay
                raise
            finally:
                self.http_metadata["http_elapsed_ms"] = round((time.monotonic() - started) * 1000)
                self.http_metadata["http_finished_at"] = time.time()

    def _trace_llm_call(self, **payload: Any) -> None:
        if self.trace_sink is None:
            return
        try:
            self.trace_sink.record_llm_call(**redact(payload, self._secret_environment))
        except Exception as error:
            try:
                self.trace_sink.record_logging_error(
                    operation="backend_hook.record_llm_call",
                    error_type=type(error).__name__,
                )
            except Exception:
                pass
            # Observability failure must never change provider or gameplay semantics.
            warnings.warn(
                f"research LLM trace failed; gameplay continues ({type(error).__name__})",
                RuntimeWarning,
                stacklevel=2,
            )

    @staticmethod
    def _normalize_requested_model(model: str) -> str:
        return model.removeprefix("ollama/").removeprefix("zai/")

    @staticmethod
    def _classify_error(error: Exception) -> str:
        if getattr(error, "category", None):
            return error.category
        status = getattr(error, "status_code", None) or getattr(
            getattr(error, "response", None), "status_code", None
        )
        if status in {401, 403}:
            return "auth"
        if status == 404:
            return "model"
        if status == 429:
            return "rate_limit"
        name = type(error).__name__.lower()
        if isinstance(error, TimeoutError) or "timeout" in name:
            return "timeout"
        if "connect" in name or "network" in name:
            return "transport"
        return "provider"

    def _record_response(
        self,
        response: Any,
        *,
        elapsed_ms: int,
        requested_tokens: int,
        json_valid: bool,
        battle_action_valid: bool | None,
        output_contract_valid: bool,
    ) -> None:
        prompt_tokens = _token_count(response, "prompt_eval_count")
        completion_tokens = _token_count(response, "eval_count")
        self.prompt_tokens += prompt_tokens if prompt_tokens is not None else 0
        self.completion_tokens += completion_tokens if completion_tokens is not None else 0
        record = {
            "status": "success" if output_contract_valid else "failure",
            "endpoint": self.endpoint,
            "provider": self.provider,
            "requested_model": self.model,
            "reported_model": _field(response, "model"),
            "elapsed_ms": elapsed_ms,
            "requested_output_tokens": requested_tokens,
            "context_window": self.context_window,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_duration_ns": _field(response, "total_duration"),
            "load_duration_ns": _field(response, "load_duration"),
            "done_reason": _field(response, "done_reason"),
            "usage": _field(response, "usage"),
            "json_valid": json_valid,
            "output_contract_valid": output_contract_valid,
        }
        if battle_action_valid is not None:
            record["battle_action_valid"] = battle_action_valid
        if not output_contract_valid:
            record["category"] = "output_contract"
        record.update(self.provider_settings)
        record.update(self.http_metadata)
        if self.terminal_error is not None:
            record.update(
                status="failure",
                category=getattr(self.terminal_error, "category", "configuration"),
            )
        self.call_records.append(record)

    @staticmethod
    def _battle_action_valid(output: str, battle: Any) -> bool:
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return False
        if not isinstance(parsed, dict):
            return False

        action_keys = [
            key for key in ("move", "dynamax", "terastallize", "switch") if key in parsed
        ]
        if len(action_keys) != 1:
            return False
        action = action_keys[0]
        selection = parsed[action]
        if not isinstance(selection, str) or not selection.strip():
            return False

        normalized = selection.lower().replace(" ", "")
        if action == "switch":
            available = {
                str(getattr(pokemon, "species", "")).lower().replace(" ", "")
                for pokemon in getattr(battle, "available_switches", ())
            }
        else:
            available = {
                str(getattr(move, "id", "")).lower().replace(" ", "")
                for move in getattr(battle, "available_moves", ())
            }
        return normalized in available

    def _json_instruction(self) -> str:
        return (
            "Return exactly one compact JSON object selecting an available action. "
            "Do not include reasoning, explanation, or Markdown in message.content."
        )

    def _request_context(self) -> dict[str, Any]:
        return {}

    def _thinking_effort(self):
        return OLLAMA_THINKING_EFFORT

    def get_LLM_action(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.7,
        json_format: bool = True,
        seed: int | None = None,
        stop: Sequence[str] | None = None,
        max_tokens: int = 20,
        actions: Any = None,
        think: bool = True,
        battle: Any = None,
        ps_client: Any = None,
    ) -> tuple[str, bool, str]:
        del actions, think, ps_client
        if self.terminal_error is not None:
            raise self.terminal_error
        thinking_effort = "low" if self.provider == "zai" else self._thinking_effort()
        effective_user_prompt = user_prompt
        if json_format and getattr(self, "action_policy", "strict") == "upstream":
            effective_user_prompt = user_prompt + '\n{"'
        elif json_format and battle is not None:
            effective_user_prompt = f"{user_prompt}\n\n{self._json_instruction()}"
        if self._normalize_requested_model(model) != self.model:
            self.terminal_error = CloudConfigurationError(
                f"requested model must remain {self.model}"
            )
            self.call_records.append(
                {
                    "status": "failure",
                    "category": "configuration",
                    "endpoint": self.endpoint,
                    "provider": self.provider,
                    "requested_model": model,
                    "expected_model": self.model,
                    "network_called": False,
                }
            )
            self._trace_llm_call(
                status="failure",
                system_prompt=system_prompt,
                user_prompt=effective_user_prompt,
                provider_reasoning=None,
                raw_content=None,
                canonical_parsed_output=None,
                request={
                    "endpoint": self.endpoint,
                    "provider": self.provider,
                    "requested_model": model,
                    "expected_model": self.model,
                    "network_called": False,
                },
                response={"error_type": type(self.terminal_error).__name__},
                validation={"category": "configuration"},
                showdown_turn=getattr(battle, "turn", None),
            )
            self.failure_event.set()
            raise self.terminal_error

        # Upstream's small action budgets must not truncate reasoning/final JSON.
        requested_tokens = self.max_output_tokens
        options: dict[str, Any] = {
            "temperature": temperature,
            "num_predict": requested_tokens,
        }
        if self.context_window is not None:
            options["num_ctx"] = self.context_window
        if seed is not None:
            options["seed"] = seed
        else:
            options["seed"] = RANDOM_SEED
        if stop:
            options["stop"] = list(stop)
        request_metadata = {
            "endpoint": self.endpoint,
            "provider": self.provider,
            "requested_model": model,
            "model": self.model,
            "temperature": temperature,
            "json_format": json_format,
            "seed": options["seed"],
            "stop": list(stop) if stop else [],
            "requested_output_tokens": requested_tokens,
            "context_window": self.context_window,
            "thinking_effort": thinking_effort,
        }

        request_metadata.update(self.provider_settings)
        request_metadata["thinking_effort"] = thinking_effort
        request_metadata["seed_requested"] = options["seed"]
        if self.provider == "zai":
            request_metadata["seed"] = None
            request_metadata["response_format"] = {"type": "json_object"} if json_format else None
        request_metadata.update(self._request_context())
        request_metadata["logical_request_id"] = uuid.uuid4().hex
        started = time.monotonic()
        response = None
        journal_intent = None
        attempts = []

        def reserve_request():
            nonlocal journal_intent
            if self.diagnostic_root:
                reserve = self.request_ledger.reserve

                journal_intent = reserve(self.diagnostic_root, self.diagnostic_actor,
                    redact(dict(request=request_metadata, system_prompt=system_prompt,
                         user_prompt=effective_user_prompt), self._secret_environment))
                request_metadata["request_intent"] = str(journal_intent)
                collection_deadline = self.request_ledger.collection_deadline

                remaining = collection_deadline(self.diagnostic_root) - time.time()
                if remaining <= 0:
                    raise CloudRequestError("budget_stop", "collection deadline")
            elif self.io_journal["root"]:
                from .improved_io.battle_only_budget import reserve

                journal_intent = reserve(
                    Path(self.io_journal["root"]), self.io_journal["cohort"],
                    self.io_journal["stage"], self.io_journal["actor"],
                    redact(dict(request=request_metadata, system_prompt=system_prompt,
                         user_prompt=effective_user_prompt), self._secret_environment),
                )
                request_metadata["request_intent"] = str(journal_intent)

        try:
            for attempt_number in range(1, self.provider_settings["provider_retries"] + 2):
                if journal_intent is not None:
                    request_metadata["previous_attempt_intent"] = str(journal_intent)
                journal_intent = None
                request_metadata.pop("request_intent", None)
                request_metadata.pop("worker_response", None)
                request_metadata["http_attempt_number"] = attempt_number
                attempt_error = None
                try:
                    admission = (self._admission(before=reserve_request)
                                 if self.diagnostic_root or self.io_journal["root"]
                                 else self._admission())
                    with admission:
                        response = self.client.chat(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": effective_user_prompt},
                            ],
                            stream=False,
                            think=thinking_effort,
                            format="json" if json_format else None,
                            options=copy.deepcopy(options),
                        )
                        if journal_intent is not None:
                            from .improved_io.battle_only_budget import (
                                preserve_response,
                            )

                            request_metadata["worker_response"] = str(
                                preserve_response(journal_intent, redact(
                                    response.model_dump() if hasattr(response, "model_dump") else response,
                                    self._secret_environment,
                                ))
                            )
                except Exception as error:
                    attempt_error = error
                reason = (retry_reason(self.provider_settings, attempt_error, self.http_metadata)
                          if response is None else None)
                retryable = reason is not None
                retry = retryable and attempt_number <= self.provider_settings["provider_retries"]
                attempt = dict(
                    **self.http_metadata,
                    logical_request_id=request_metadata["logical_request_id"],
                    http_attempt_number=attempt_number,
                    request_intent=str(journal_intent) if journal_intent else None,
                    status="failure" if attempt_error else "success",
                    connection_retryable=bool(retryable and connection_failure(attempt_error)),
                    retry_outcome="scheduled" if retry else ("exhausted" if retryable else "not_retried"),
                )
                if version_of(self.provider_settings) == CURRENT:
                    attempt.update(retryable=retryable, retry_reason=reason)
                if attempt_error is not None:
                    attempt.update(error_details(
                        attempt_error, lambda v: redact(v, self._secret_environment)
                    ))
                    attempt["category"] = self._classify_error(attempt_error)
                if attempts and attempts[-1]["retry_outcome"] == "wait_completed":
                    attempts[-1]["retry_outcome"] = (
                        "retried" if attempt.get("network_called") else "blocked_before_retry"
                    )
                attempts.append(attempt)
                if journal_intent is not None:
                    from .benchmark import seal_json

                    seal_json(journal_intent.with_name(journal_intent.name.replace("intent-", "attempt-")), attempt)
                if attempt_error is None:
                    break
                if not retry:
                    if (version_of(self.provider_settings) == CURRENT
                            and self.http_metadata.get("http_status") == 429):
                        self._halt_exhausted_429()
                    raise attempt_error
                delay = self.provider_settings["retry_delays_seconds"][attempt_number - 1]
                attempt["retry_delay_seconds"] = delay
                try:
                    wait_retry(self, delay)
                except Exception:
                    attempt["retry_outcome"] = "cancelled_before_retry"
                    if journal_intent is not None:
                        seal_json(journal_intent.with_name(journal_intent.name.replace("intent-", "retry-")), attempt)
                    raise
                attempt["retry_outcome"] = "wait_completed"
                if journal_intent is not None:
                    seal_json(journal_intent.with_name(journal_intent.name.replace("intent-", "retry-")), attempt)
            request_metadata["http_attempts"] = attempts
            request_metadata["http_attempt_count"] = sum(bool(a.get("network_called")) for a in attempts)
            request_metadata["retry_outcome"] = "recovered" if len(attempts) > 1 else "not_needed"
        except Exception as error:
            request_metadata["http_attempts"] = attempts
            request_metadata["http_attempt_count"] = sum(bool(a.get("network_called")) for a in attempts)
            request_metadata["retry_outcome"] = (
                "exhausted" if attempts and attempts[-1]["retry_outcome"] == "exhausted"
                else "failed"
            )
            detail = error_details(error, lambda v: redact(v, self._secret_environment))
            request_metadata.update(detail)
            if response is not None:
                # Preserve a paid response even if the broker fails during release.
                self.terminal_error = CloudRequestError("configuration", "permit release failed")
                self.failure_event.set()
            else:
                category = self._classify_error(error)
                if self.diagnostic_root:
                    from .permits import PermitCancelled

                    if isinstance(error, PermitCancelled):
                        if self.terminal_error is not None:
                            category = getattr(self.terminal_error, "category", category)
                        elif self.cancel_path and Path(self.cancel_path).exists():
                            category = json.loads(Path(self.cancel_path).read_text()).get("category", "peer_failure")
                elapsed_ms = round((time.monotonic() - started) * 1000)
                self.call_records.append(
                    {
                        "status": "failure",
                        "category": category,
                        "endpoint": self.endpoint,
                        "provider": self.provider,
                        "requested_model": self.model,
                        "elapsed_ms": elapsed_ms,
                        **self.http_metadata,
                        "requested_output_tokens": requested_tokens,
                        "context_window": self.context_window,
                        **request_metadata,
                    }
                )
                self.terminal_error = CloudRequestError(category, detail["error_message"])
                self._trace_llm_call(
                    status="failure",
                    system_prompt=system_prompt,
                    user_prompt=effective_user_prompt,
                    provider_reasoning=None,
                    raw_content=None,
                    canonical_parsed_output=None,
                    request=request_metadata,
                    response={
                        "elapsed_ms": elapsed_ms,
                        "error_type": type(error).__name__,
                        **self.http_metadata,
                    },
                    validation={"category": category, "output_contract_valid": False},
                    showdown_turn=getattr(battle, "turn", None),
                )
                self.failure_event.set()
                raise self.terminal_error from None
        elapsed_ms = round((time.monotonic() - started) * 1000)
        # Remove echoed keys before any parser, recorder, or caller can persist them.
        response = redact(
            response.model_dump() if hasattr(response, "model_dump") else response,
            self._secret_environment,
        )
        if self.lead_study_root:
            if self.request_ledger.response_model_mismatch(self.lead_study_root, _field(response, "model")):
                self.terminal_error = CloudRequestError("model", "lead study provider returned a different model")
                self.failure_event.set()
        message = _field(response, "message", {})
        content = _field(message, "content", "") or ""
        if not isinstance(content, str):
            content = str(content)
        content = redact(content, self._secret_environment)
        reasoning = _field(message, "thinking")
        if reasoning is not None and not isinstance(reasoning, str):
            reasoning = str(reasoning)
        reasoning = redact(reasoning, self._secret_environment)
        output, json_valid = _extract_json(content) if json_format else (content, False)
        if json_format and getattr(self, "action_policy", "strict") == "upstream":
            output = _extract_upstream(content)
            try:
                json.loads(output)
                json_valid = True
            except (ValueError, TypeError):
                json_valid = False
        battle_action_valid = (
            self._battle_action_valid(output, battle)
            if json_format and json_valid and battle is not None
            else None
        )
        output_contract_valid = not json_format or (json_valid and battle_action_valid is not False)
        text_validator = getattr(self, "_text_output_valid", None)
        if not json_format and text_validator is not None:
            output_contract_valid = text_validator(content)
        self._record_response(
            response,
            elapsed_ms=elapsed_ms,
            requested_tokens=requested_tokens,
            json_valid=json_valid,
            battle_action_valid=battle_action_valid,
            output_contract_valid=output_contract_valid,
        )
        self.call_records[-1].update(request_metadata)
        self.call_records[-1]["thinking_effort"] = thinking_effort
        canonical_parsed_output = None
        if json_valid:
            try:
                canonical_parsed_output = json.loads(output)
            except json.JSONDecodeError:
                canonical_parsed_output = None
        self._trace_llm_call(
            status="success"
            if output_contract_valid and self.terminal_error is None
            else "failure",
            system_prompt=system_prompt,
            user_prompt=effective_user_prompt,
            provider_reasoning=reasoning,
            raw_content=content,
            canonical_parsed_output=canonical_parsed_output,
            request=request_metadata,
            response={
                "reported_model": _field(response, "model"),
                **self.http_metadata,
                "elapsed_ms": elapsed_ms,
                "prompt_tokens": _token_count(response, "prompt_eval_count"),
                "completion_tokens": _token_count(response, "eval_count"),
                "total_duration_ns": _field(response, "total_duration"),
                "load_duration_ns": _field(response, "load_duration"),
                "done_reason": _field(response, "done_reason"),
                "usage": _field(response, "usage"),
            },
            validation={
                **(
                    {"category": getattr(self.terminal_error, "category", "configuration")}
                    if self.terminal_error is not None
                    else {}
                ),
                "json_valid": json_valid,
                "battle_action_valid": battle_action_valid,
                "output_contract_valid": output_contract_valid,
            },
            showdown_turn=getattr(battle, "turn", None),
        )
        if self.terminal_error is not None:
            raise self.terminal_error
        if (not output_contract_valid and getattr(self, "action_policy", "strict") != "upstream"
            and not getattr(self, "_output_failure_recovered", lambda: False)()):
            self.terminal_error = CloudRequestError(
                "output_contract",
                "response did not satisfy the required JSON action contract",
            )
            self.failure_event.set()
            raise self.terminal_error
        # Suppress provider reasoning/content from PokéChamp's public battle chat.
        return output, json_valid, ""

    def get_LLM_query(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        model: str = OLLAMA_MODEL,
        json_format: bool = False,
        seed: int | None = None,
        stop: Sequence[str] | None = None,
        max_tokens: int = 200,
    ) -> tuple[str, bool]:
        output, valid, _ = self.get_LLM_action(
            system_prompt,
            user_prompt,
            model,
            temperature,
            json_format,
            seed,
            stop,
            max_tokens,
            think=True,
        )
        return output, valid
