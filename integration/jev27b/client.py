"""Loopback-only, identity-bound transport for the EX-082 Choice service."""
from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
import math
import re
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

from .config import MODEL_ID, REVISION

PROTOCOL = "jev27b-local-v1"
TIMEOUT = 600.0
RETRY_DELAYS = (10.0, 30.0, 60.0)
DEFAULT_ENDPOINT = "http://127.0.0.1:18782"
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,200}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class LocalRequestError(RuntimeError):
    """A transport/integrity failure, distinct from an illegal model choice."""

    def __init__(self, category, *, status_code=None, retryable=False, metadata=None):
        self.category = category
        self.status_code = status_code
        self.retryable = bool(retryable)
        self.metadata = dict(metadata or {})
        suffix = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"Local JEV request failed: {category}{suffix}")


def base_url(value):
    """Accept numeric loopback hosts only; bypass DNS, proxies and redirects."""
    try:
        parsed = urlsplit(value)
        valid = (
            isinstance(value, str)
            and parsed.scheme == "http"
            and ipaddress.ip_address(parsed.hostname).is_loopback
            and parsed.port is not None
            and 0 < parsed.port < 65536
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path.rstrip("/") in ("", "/v1/systemone")
            and not any(c.isspace() or ord(c) < 32 for c in value)
            and not any(c in value for c in ("\\", "@", "%"))
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("JEV-27B endpoint must be an HTTP numeric loopback URL with a port")
    return f"{parsed.scheme}://{parsed.netloc}"


def request_bytes(payload):
    """Preserve insertion order, including candidate order, in exact wire bytes."""
    if not isinstance(payload, dict):
        raise ValueError("JEV-27B payload must be an object")
    if payload.get("model", MODEL_ID) != MODEL_ID:
        raise ValueError("unexpected JEV-27B model")
    body = copy.deepcopy(payload)
    if "model" not in body:
        body = dict(model=MODEL_ID, **body)
    if set(body) != {"model", "state", "questions"}:
        raise ValueError("JEV-27B request requires model, state and questions only")
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError("nonfinite JSON number: " + value)


def _parse(raw):
    return json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_number)


def _transient_transport(error):
    # Decoding/local-protocol/configuration faults are not temporary connections.
    return isinstance(error, (httpx.NetworkError, httpx.RemoteProtocolError))


class LocalClient:
    """One physical attempt by default; the battle Session owns its retry ledger."""

    def __init__(self, endpoint=DEFAULT_ENDPOINT, *, expected_identity=None,
                 timeout=TIMEOUT, record: Callable | None = None, transport=None):
        self.base_url = base_url(endpoint)
        self.endpoint = self.base_url + "/v1/systemone"
        if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                or not 0 < timeout <= TIMEOUT):
            raise ValueError("invalid local JEV timeout")
        if expected_identity is not None and (not isinstance(expected_identity, str)
                                             or not SHA256_PATTERN.fullmatch(expected_identity)):
            raise ValueError("expected_identity must be a serving identity SHA256")
        self.expected_identity = expected_identity
        self.timeout = float(timeout)
        self.record = record
        self.last_transport = None
        self._client = httpx.Client(timeout=self.timeout, transport=transport,
                                    trust_env=False, follow_redirects=False)

    request_bytes = staticmethod(request_bytes)

    def _save(self, metadata):
        self.last_transport = copy.deepcopy(metadata)
        if self.record is not None:
            self.record(copy.deepcopy(metadata))

    def _failure(self, category, metadata, *, retryable=False):
        metadata["category"] = category
        self._save(metadata)
        return LocalRequestError(category, status_code=metadata.get("status_code"),
                                 retryable=retryable, metadata=metadata)

    def health(self):
        """Check revision/config identity and pin identity on the first healthy call."""
        started = time.monotonic()
        metadata = dict(type="health", endpoint=self.base_url + "/health", model=MODEL_ID,
                        status_code=None, raw_body=None, timeout=self.timeout)
        try:
            response = self._client.get(self.base_url + "/health")
        except httpx.TimeoutException:
            metadata["elapsed_seconds"] = time.monotonic() - started
            raise self._failure("timeout", metadata, retryable=True) from None
        except httpx.RequestError as error:
            metadata["elapsed_seconds"] = time.monotonic() - started
            raise self._failure("transport", metadata, retryable=_transient_transport(error)) from None
        metadata.update(status_code=response.status_code, raw_body=response.text,
                        elapsed_seconds=time.monotonic() - started)
        try:
            body = _parse(response.content)
        except (ValueError, UnicodeError):
            raise self._failure("invalid_health", metadata) from None
        if not isinstance(body, dict):
            raise self._failure("invalid_health", metadata)
        identity = body.get("identity")
        if (body.get("model") != MODEL_ID or body.get("revision") != REVISION
                or body.get("protocol") != PROTOCOL or not isinstance(identity, str)
                or not SHA256_PATTERN.fullmatch(identity)
                or body.get("serving_identity") != identity
                or (self.expected_identity is not None and identity != self.expected_identity)):
            raise self._failure("serving_identity", metadata)
        if (response.status_code != 200 or body.get("ready") is not True
                or body.get("halt") is not None):
            raise self._failure("halted", metadata)
        self.expected_identity = identity
        metadata.update(serving_identity=identity, category=None)
        self._save(metadata)
        return body

    def evaluate(self, payload, *, request_id, retries=0):
        """Retry only transient transport errors, retaining the exact bytes and ID."""
        if not isinstance(request_id, str) or not REQUEST_ID_PATTERN.fullmatch(request_id):
            raise ValueError("invalid local JEV request ID")
        if type(retries) is not int or not 0 <= retries <= 3:
            raise ValueError("local JEV retries must be between zero and three")
        raw = request_bytes(payload)
        if self.expected_identity is None:
            self.health()
        for attempt in range(retries + 1):
            try:
                return self._evaluate_once(raw, request_id=request_id, attempt=attempt + 1)
            except LocalRequestError as error:
                if not error.retryable or attempt == retries:
                    raise
            time.sleep(RETRY_DELAYS[attempt])
        raise AssertionError("unreachable retry boundary")

    def _evaluate_once(self, raw, *, request_id, attempt):
        digest = hashlib.sha256(raw).hexdigest()
        headers = {"Content-Type": "application/json", "X-Request-ID": request_id,
                   "X-Body-SHA256": digest, "X-Serving-Identity": self.expected_identity}
        metadata = dict(type="transport", endpoint=self.endpoint, model=MODEL_ID,
                        request_id=request_id, body_sha256=digest,
                        request_body=raw.decode("utf-8"), serving_identity=self.expected_identity,
                        status_code=None, raw_body=None, attempt=attempt, timeout=self.timeout)
        started = time.monotonic()
        try:
            response = self._client.post(self.endpoint, content=raw, headers=headers)
        except httpx.TimeoutException:
            metadata["elapsed_seconds"] = time.monotonic() - started
            raise self._failure("timeout", metadata, retryable=True) from None
        except httpx.RequestError as error:
            metadata["elapsed_seconds"] = time.monotonic() - started
            raise self._failure("transport", metadata, retryable=_transient_transport(error)) from None
        metadata.update(status_code=response.status_code, raw_body=response.text,
                        elapsed_seconds=time.monotonic() - started,
                        cache_reused=response.headers.get("X-Cache-Reused") == "1")
        try:
            body = _parse(response.content)
        except (ValueError, UnicodeError):
            body = None
        # A persisted halt is final even when delivered with a retryable HTTP code.
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            if body["error"].get("halted") is True:
                raise self._failure(body["error"].get("category", "halted"), metadata)
        if response.status_code != 200:
            transient = response.status_code == 429 or 500 <= response.status_code <= 599
            raise self._failure("http", metadata, retryable=transient)
        expected = dict(request_id=request_id, body_sha256=digest,
                        serving_identity=self.expected_identity, inference_calls=1,
                        inference_id=hashlib.sha256((self.expected_identity + "\0" + request_id
                                                    + "\0" + digest).encode("utf-8")).hexdigest())
        if (not isinstance(body, dict) or body.get("model") != MODEL_ID
                or not isinstance(body.get("transport"), dict)
                or body["transport"].get("protocol") != PROTOCOL
                or any(body["transport"].get(key) != value for key, value in expected.items())
                or response.headers.get("X-Request-ID") != request_id
                or response.headers.get("X-Body-SHA256") != digest
                or response.headers.get("X-Serving-Identity") != self.expected_identity
                or response.headers.get("X-Cache-Reused") not in ("0", "1")):
            raise self._failure("response_identity", metadata)
        metadata.update(inference_id=body["transport"].get("inference_id"),
                        inference_calls=body["transport"].get("inference_calls"), category=None)
        self._save(metadata)
        # Choice legality and auxiliary scores belong to choice-action-v3 in the actor.
        return body

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
