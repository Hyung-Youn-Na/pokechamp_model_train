"""Standalone TypeSafe JEV HTTP client; no battle-provider integration."""

from __future__ import annotations

import copy
import time
import os
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from . import jev_retry
from .dotenv import DOTENV_PATH, load_workspace_credential
from .providers import CREDENTIAL_NAMES, CloudConfigurationError

DEFAULT_BASE_URL = "https://api.typesafe.ai/v1"
DEFAULT_MODEL = "jev-latest"


class JevRequestError(RuntimeError):
    """Sanitized failure without the underlying request, headers, or response body."""

    def __init__(self, category: str, *, status_code: int | None = None):
        self.category = category
        self.status_code = status_code
        suffix = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"JEV request failed: {category}{suffix}")


def _base_url(value: str, secrets: list[str]) -> str:
    try:
        parsed = urlsplit(value)
        url = httpx.URL(value)
        valid = (
            parsed.scheme == "https"
            and bool(url.host)
            and parsed.port != 0
            and not parsed.username
            and not parsed.password
            and not any(c.isspace() or ord(c) < 32 for c in value)
            and not any(c in value for c in ("\\", "?", "#", "@"))
            and not re.search(r"%(?![a-fA-F0-9]{2})", value)
            and not parsed.path.rstrip("/").endswith("/systemone")
            and not any(secret and secret in value for secret in secrets)
        )
    except (ValueError, httpx.InvalidURL):
        valid = False
    if not valid:
        raise CloudConfigurationError(
            "TYPESAFE_BASE_URL must be an HTTPS base URL before /systemone "
            "without credentials, query, or fragment"
        )
    return str(url).rstrip("/")


class JevClient:
    """Call evaluate explicitly; construction never sends an HTTP request."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        retry_policy: str = jev_retry.CURRENT,
    ):
        if not api_key.strip() or any(ord(c) < 33 or ord(c) > 126 for c in api_key):
            raise CloudConfigurationError("TYPESAFE_API_KEY must be a nonempty valid API key")
        if not model.strip() or any(c.isspace() or ord(c) < 32 for c in model):
            raise CloudConfigurationError("TYPESAFE_MODEL must be a nonempty model ID")
        self.endpoint = _base_url(base_url, [api_key]) + "/systemone"
        self.model = model
        jev_retry.delays_for(retry_policy)
        self.retry_policy = retry_policy
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @classmethod
    def from_env(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        path: Path = DOTENV_PATH,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        retry_policy: str = jev_retry.CURRENT,
    ) -> JevClient:
        # Keep the caller's mapping and the battle-provider selection untouched.
        env = dict(os.environ if environ is None else environ)
        load_workspace_credential(environ=env, path=path)
        base = _base_url(
            env.get("TYPESAFE_BASE_URL", DEFAULT_BASE_URL),
            [env.get(name, "") for name in CREDENTIAL_NAMES],
        )
        return cls(
            api_key=env.get("TYPESAFE_API_KEY", ""),
            base_url=base,
            model=env.get("TYPESAFE_MODEL", DEFAULT_MODEL),
            timeout=timeout,
            transport=transport,
            retry_policy=retry_policy,
        )

    def evaluate(self, *, state: str | dict | list, questions: dict) -> dict:
        # Freeze one logical request across physical attempts.
        payload = copy.deepcopy(dict(state=state, questions=questions))
        delays = jev_retry.delays_for(self.retry_policy)
        for attempt in range(len(delays) + 1):
            failure = None
            try:
                return self._evaluate_once(**payload)
            except JevRequestError as error:
                failure = error
            if attempt == len(delays) or not jev_retry.retryable(failure):
                raise failure
            time.sleep(delays[attempt])

    def _evaluate_once(self, *, state: str | dict | list, questions: dict) -> dict:
        """Send native question dictionaries and return the native JSON response."""
        if not isinstance(state, (str, dict, list)):
            raise ValueError("JEV state must be a string, object, or array")
        if not isinstance(questions, dict) or not questions:
            raise ValueError("JEV questions must be a nonempty object")
        for name, question in questions.items():
            if (
                not isinstance(name, str)
                or not isinstance(question, dict)
                or question.get("type") not in ("choice", "score", "noul")
                or not isinstance(question.get("instructions"), (str, dict, list))
            ):
                raise ValueError("Invalid JEV question type or instructions")
        # Raise outside exception handlers so even exception context cannot retain a key.
        failure = None
        try:
            response = self._client.post(
                self.endpoint,
                json=dict(model=self.model, state=state, questions=questions),
            )
        except httpx.TimeoutException:
            failure = JevRequestError("timeout")
        except httpx.RequestError:
            failure = JevRequestError("transport")
        except (TypeError, ValueError):
            failure = JevRequestError("invalid_request")
        if failure is not None:
            raise failure
        if not response.is_success:
            raise JevRequestError("http", status_code=response.status_code)
        try:
            body = response.json()
        except ValueError:
            failure = JevRequestError("invalid_response")
        if failure is not None:
            raise failure
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("model"), str)
            or not isinstance(body.get("answers"), dict)
            or not isinstance(body.get("usage"), dict)
            or body["answers"].keys() != questions.keys()
            or any(
                not isinstance(answer, dict) or answer.get("type") != questions[name]["type"]
                for name, answer in body["answers"].items()
            )
        ):
            raise JevRequestError("invalid_response")
        return body

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> JevClient:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
