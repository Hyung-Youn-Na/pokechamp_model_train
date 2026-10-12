"""Provider-stratified EX-042 denominators; no cross-provider causal claim."""

from .a_diagnostic_report import summarize
from .concurrency_metrics import request_metrics


def provider_summary(directory, prepared, matches, decisions):
    from .team_preview_report import distribution, paired_scores, usage

    result = {}
    for provider in ("ollama", "zai"):
        rows = [r for r in matches if r["provider_id"] == provider]
        pairs = paired_scores(rows)
        complete = [p["llm_score_mean"] for p in pairs if p["complete"]]
        totals = summarize(rows)
        calls = [
            call
            for d in decisions
            for call in d["calls"]
            if call["request"].get("provider") == provider
        ]
        retried = [c for c in calls if c["request"].get("http_attempt_count", 1) > 1]
        recovered = [
            c for c in calls if c["request"].get("retry_outcome") == "recovered"
        ]
        random_rows = [
            dict(
                r,
                outcome={
                    "player_won": "player_lost",
                    "player_lost": "player_won",
                    "tied": "tied",
                }.get(r["outcome"]),
            )
            for r in rows
        ]
        groups, _ = usage(directory, prepared, decisions, provider_id=provider)
        result[provider] = dict(
            **totals,
            valid_completion_rate=totals["valid_completed"] / 16,
            planned_pairs=8,
            completed_pairs=len(complete),
            pairs=pairs,
            completed_pair_llm_score=sum(complete) / len(complete)
            if complete
            else None,
            conditions=dict(llm_lead=totals, seeded_random=summarize(random_rows)),
            usage=groups,
            request_metrics=request_metrics(calls),
            retried_logical_requests=len(retried),
            recovered_logical_requests=len(recovered),
            retry_recovery_rate=len(recovered) / len(retried) if retried else None,
            match_duration_seconds=distribution([r["duration_seconds"] for r in rows]),
            model=prepared["models"][provider],
        )
    return result


def completion_controls(directory):
    """Counts alone cannot certify completion without the entry gate and cleanup."""
    from pathlib import Path

    from . import benchmark as b
    from .team_preview_study import execution_protocol

    directory = Path(directory)
    records = {}
    for name in ("first-pair-check", "cleanup", "cloud-clock", "run-claim"):
        path = directory / (name + ".json")
        records[name] = b.read_sealed(path) if path.exists() else {}
    gate, cleanup, clock, claim = (
        records[n] for n in ("first-pair-check", "cleanup", "cloud-clock", "run-claim")
    )
    permits = cleanup.get("permits", {})
    prepared = (b.read_sealed(directory / "plan.json") if (directory / "plan.json").exists()
                else dict(registered_experiment="EX-042"))
    controls = dict(
        entry_claim=claim.get("execution_protocol") == execution_protocol(prepared),
        first_four_gate=gate.get("passed") is True and not gate.get("errors"),
        ports_closed=cleanup.get("ports_closed") == list(range(8100, 8108)),
        sockets_removed=cleanup.get("socket_removed") is True,
        permits_returned=cleanup.get("remaining_permits") == 0
        and not sum(permits.get("active_at_close", {}).values())
        and not any(
            e["event"] in ("orphan", "revoke_owned_after_workers_exit")
            for e in permits.get("events", [])
        ),
        cleanup_in_time=bool(clock)
        and cleanup.get("completed_at", float("inf")) <= clock["cleanup_deadline"],
    )

    if prepared.get("registered_experiment") in ("EX-043", "EX-044", "EX-045", "EX-046"):
        receipts = [b.read_sealed(p) for p in (directory / "input-audit-receipts").glob("*.json")]
        controls["input_audits"] = len(receipts) == 32 and all(
            r.get("passed") is True and r.get("audit_version") == execution_protocol(prepared)["input_audit"]
            and b.digest(directory / r["index_relative"]) == r["index_sha256"]
            for r in receipts)
    return controls
