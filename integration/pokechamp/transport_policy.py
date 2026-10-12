"""Versioned HTTP policy; absence on a sealed artifact means the legacy policy."""

from __future__ import annotations

import time

LEGACY = "legacy-300-v1"
CONNECT = "connect-retry-v1"
CURRENT = "provider-retry-v2"
ENV_NAME = "POKECHAMP_TRANSPORT_POLICY"


def policy_fields(version):
    if version == LEGACY:
        return dict(request_timeout_seconds=300.0, provider_retries=0)
    if version not in (CONNECT, CURRENT):
        raise ValueError("unknown transport policy")
    return dict(
        transport_policy_version=version,
        request_timeout_seconds=600.0,
        provider_retries=3 if version == CURRENT else 2,
        retry_delays_seconds=[1.0, 2.0, 4.0] if version == CURRENT else [1.0, 3.0],
        http_timeout=dict(connect=300.0, read=600.0, write=300.0, pool=300.0),
    )


def version_of(settings):
    return settings.get("transport_policy_version", LEGACY)


def timeout_for(settings, remaining=None):
    import httpx

    values = settings.get("http_timeout", dict.fromkeys(("connect", "read", "write", "pool"), 300.0))
    if remaining is not None:
        values = {k: min(v, max(0.001, remaining)) for k, v in values.items()}
    return httpx.Timeout(**values)


def drain_seconds(settings):
    # A non-streaming attempt can spend time in all four HTTP phases. A retry
    # is blocked once cancellation begins, so only one active attempt is drained.
    if version_of(settings) == LEGACY:
        return 300.0
    return sum(settings["http_timeout"].values())


def connection_failure(error):
    import httpx

    if isinstance(error, httpx.ConnectError):
        return True
    # Pinned Ollama catches ConnectError and raises built-in ConnectionError
    # from None: __context__ still retains the original exception.
    return type(error) is ConnectionError and isinstance(error.__context__, httpx.ConnectError)


def error_details(error, redact):
    chain, seen = [], set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(dict(error_type=type(current).__name__, error_message=str(current)))
        current = current.__cause__ or current.__context__
    return redact(dict(error_type=type(error).__name__, error_message=str(error), causes=chain[1:]))


def retry_reason(settings, error, metadata):
    """Classify transport failures only, before response/output processing."""
    import httpx

    version = version_of(settings)
    if version == LEGACY or error is None or not metadata.get("network_called"):
        return None
    if connection_failure(error):
        return "connection"
    if version == CURRENT:
        if isinstance(error, httpx.TimeoutException):
            return "timeout"
        status = metadata.get("http_status")
        if status == 429:
            return "rate_limit"
        if isinstance(status, int) and 500 <= status <= 599:
            return "server"
    return None


def retryable_proof(proof):
    return (proof.get("status") == "failure" and proof.get("network_called") is True
            and (proof.get("retryable") is True or proof.get("connection_retryable") is True))


def wait_retry(backend, delay):
    from .permits import PermitCancelled

    end = time.monotonic() + delay
    while True:
        if backend._cancelled():
            raise PermitCancelled("cancelled during provider retry wait")
        if backend.lead_study_root:
            backend.request_ledger.check_admission(backend.lead_study_root)
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        backend.failure_event.wait(min(0.05, remaining))


def validate_retry(db, value, actor, payload, matches):
    """Allow only the next attempt with the exact same request and sealed failure."""
    from pathlib import Path

    from .benchmark import read_sealed
    from .cloud import CloudRequestError

    request = payload.get("request", {})
    number = request.get("http_attempt_number", 1)
    settings = value.get("provider_config", {})
    version = version_of(settings)
    maximum = policy_fields(version)["provider_retries"] + 1
    valid = type(number) is int and number == len(matches) + 1 and 2 <= number <= maximum
    ignored = {"http_attempt_number", "request_intent", "worker_response", "previous_attempt_intent"}
    def stable(p):
        return {**p, "request": {k: v for k, v in p["request"].items() if k not in ignored}}
    if valid:
        for index, (reservation, previous) in enumerate(matches, 1):
            if (
                previous["request"].get("http_attempt_number") != index
                or not request.get("logical_request_id")
                or stable(previous) != stable(payload)
            ):
                valid = False
        previous_intent = request.get("previous_attempt_intent")
        if previous_intent:
            # The pointer itself is not authority; match it to the last committed row.
            path = Path(previous_intent)
            previous = read_sealed(path)
            proof = read_sealed(path.with_name(path.name.replace("intent-", "attempt-")))
            valid = valid and previous["number"] == matches[-1][0] and previous["actor"] == actor
            valid = valid and previous["payload"] == matches[-1][1]
            valid = valid and (retryable_proof(proof) if version == CURRENT
                               else proof.get("connection_retryable") is True)
            valid = valid and proof.get("status") == "failure" and proof.get("network_called") is True
            valid = valid and proof.get("http_attempt_number") == number - 1
            valid = valid and proof.get("logical_request_id") == request.get("logical_request_id")
        else:
            valid = False
    if not valid:
        raise CloudRequestError("integrity", "duplicate lead-study request")


def audit_attempts(call, *, actor=None):
    """Verify every attempt-to-ledger link, including recovered connection failures."""
    from pathlib import Path

    from .benchmark import read_sealed

    request = call.get("request", {})
    attempts = request.get("http_attempts")
    if attempts is None:
        return []
    if request.get("http_attempt_count") != sum(bool(a.get("network_called")) for a in attempts):
        raise ValueError("HTTP attempt denominator mismatch")
    paths = []
    for number, attempt in enumerate(attempts, 1):
        if attempt["http_attempt_number"] != number or attempt["logical_request_id"] != request["logical_request_id"]:
            raise ValueError("HTTP attempt identity mismatch")
        path = attempt.get("request_intent")
        if path is None:
            if actor and attempt.get("network_called"):
                raise ValueError("HTTP attempt missing intent")
            continue
        intent = read_sealed(path)
        if actor and intent["actor"] != actor:
            raise ValueError("cross actor HTTP attempt")
        payload = intent["payload"]
        if any(payload[key] != call[key] for key in ("system_prompt", "user_prompt")):
            raise ValueError("HTTP retry input drift")
        ignored = {"request_intent", "worker_response", "previous_attempt_intent", "http_attempt_number"}
        if any(request.get(k) != v for k, v in payload["request"].items() if k not in ignored):
            raise ValueError("HTTP retry settings drift")
        if payload["request"]["http_attempt_number"] != number:
            raise ValueError("ledger HTTP attempt number mismatch")
        path = Path(path)
        proof = read_sealed(path.with_name(path.name.replace("intent-", "attempt-")))
        for key in ("http_attempt_number", "logical_request_id", "network_called", "status", "error_type", "http_elapsed_ms"):
            if proof.get(key) != attempt.get(key):
                raise ValueError("HTTP attempt proof mismatch")
        paths.append(str(path))
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate HTTP attempt reference")
    return paths
