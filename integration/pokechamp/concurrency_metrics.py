"""Observed client HTTP overlap and separate admission/HTTP timing metrics."""

from collections import Counter, defaultdict


def request_metrics(calls):
    from .benchmark import percentile

    spans = []
    by_model = defaultdict(list)
    waits, latencies = [], []
    statuses = Counter()
    errors = Counter()
    calls = list(calls)
    logical_statuses = Counter(c.get("status", "unknown") for c in calls)
    individual = []
    for call in calls:
        request = call.get("request", {})
        attempts = request.get("http_attempts")
        if attempts is None:
            individual.append(call)
        else:
            individual.extend(dict(
                request=request, response=a,
                validation={"category": a["category"]} if a.get("category") else {},
            ) for a in attempts)
    for call in individual:
        request, response = call.get("request", {}), call.get("response", {})
        if "permit_wait_ms" in response:
            waits.append(response["permit_wait_ms"])
        if "http_elapsed_ms" in response:
            latencies.append(response["http_elapsed_ms"])
        if response.get("http_status") is not None:
            statuses[str(response["http_status"])] += 1
        category = call.get("validation", {}).get("category")
        if category:
            errors[category] += 1
        if "http_started_at" in response and "http_finished_at" in response:
            span = (response["http_started_at"], response["http_finished_at"])
            spans.append(span)
            by_model[request.get("model", "unknown")].append(span)

    def peak(rows):
        count = maximum = 0
        for _, delta in sorted([(s, 1) for s, _ in rows] + [(e, -1) for _, e in rows]):
            count += delta
            maximum = max(maximum, count)
        return maximum

    return {
        "logical_requests": len(calls),
        "logical_status_counts": dict(logical_statuses),
        "retry_outcome_counts": dict(Counter(c.get("request", {}).get("retry_outcome", "legacy") for c in calls)),
        "retry_reason_counts": dict(Counter(c["response"]["retry_reason"] for c in individual
                                           if c.get("response", {}).get("retry_reason"))),
        "logical_error_counts": dict(Counter(c.get("validation", {}).get("category")
            for c in calls if c.get("validation", {}).get("category"))),
        "http_attempt_count": sum(bool(c.get("response", {}).get("network_called", "http_started_at" in c.get("response", {}))) for c in individual),
        "observed_http_calls": len(spans),
        "maximum_account_http_overlap": peak(spans),
        "maximum_model_http_overlap": {m: peak(rows) for m, rows in by_model.items()},
        "http_status_counts": dict(statuses),
        "error_counts": dict(errors),
        "permit_wait_p50_ms": percentile(waits, 0.5),
        "permit_wait_p95_ms": percentile(waits, 0.95),
        "http_p50_ms": percentile(latencies, 0.5),
        "http_p95_ms": percentile(latencies, 0.95),
        "note": "Client HTTP overlap; provider internal queue/execution timing is unknown.",
    }
