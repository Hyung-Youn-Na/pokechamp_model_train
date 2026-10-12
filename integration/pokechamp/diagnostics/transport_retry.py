"""C-038 v2: local Showdown per provider, injected 500/timeout/429 per actor."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from .. import benchmark as b
from .. import team_preview_report as report
from .. import team_preview_study as study
from ..concurrency_metrics import request_metrics
from ..permits import PermitBroker
from ..providers import provider_config
from ..transport_policy import drain_seconds
from .team_preview import audit


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for index, provider in enumerate(("ollama", "zai")):
        root = output / provider / "prepared"
        settings = provider_config(dict(POKECHAMP_PROVIDER=provider,
            ZAI_BASE_URL="https://zai.example.test/v4"))
        with patch.object(study, "prepared_provider", lambda **_: settings):
            prepared = study.prepare(root, transport="fake", concurrency=2)
        row = next(r for r in prepared["schedule"] if r["slot_id"] == "b01-r1-s0")
        b.seal_json(root.parent / "local-validation-plan.json", dict(
            matches=1, provider=provider, external_model_calls=0,
            injected_retry_errors_per_actor=[500, "ReadTimeout", 429], slot=row,
        ))
        with tempfile.TemporaryDirectory(prefix="pc-retry-") as temp:
            with PermitBroker(Path(temp) / "p.sock", 2, {"glm-5.3-flash": 2},
                              timeout=drain_seconds(settings)) as broker:
                with patch.dict(os.environ, POKECHAMP_FAKE_CONNECT_FAILURES="0",
                                POKECHAMP_FAKE_RETRY_ERRORS="500,timeout,429"):
                    attempt = b.run_attempt(root.parent / "data", root, prepared, row, 1,
                                            port=8100 + index, broker_path=str(broker.path))
                permits = broker.snapshot()
        b.seal_json(root.parent / "attempts.json", [attempt])
        b.seal_json(root.parent / "permits.json", permits)
        checked = audit([attempt], prepared, root)
        calls, decisions, technical = [], [], []
        for role, actor in attempt["actors"].items():
            found, checks = report.technical_inventory(row, actor, role, prepared)
            assert not checks["errors"], checks
            decisions.extend(found)
            technical.append(checks)
            events = list(map(json.loads, (Path(actor["bundle"]) / "events.jsonl").read_text().splitlines()))
            observed = [e for e in events if e["event_type"] == "llm_call"]
            calls.extend(observed)
            assert observed[0]["request"]["http_attempt_count"] == 4
            first_attempts = observed[0]["request"]["http_attempts"]
            assert first_attempts[1]["http_started_at"] - first_attempts[0]["http_finished_at"] >= 1
            assert first_attempts[2]["http_started_at"] - first_attempts[1]["http_finished_at"] >= 2
            assert first_attempts[3]["http_started_at"] - first_attempts[2]["http_finished_at"] >= 4
            assert observed[0]["status"] == "success"
            assert observed[0]["request"]["retry_outcome"] == "recovered"
            wire = list(map(json.loads, (root / "attempts" / attempt["attempt_id"] / (role + "-mock-http.jsonl")).read_text().splitlines()))
            assert wire[0]["request"] == wire[1]["request"] == wire[2]["request"] == wire[3]["request"]
            assert all(w["timeout"] == dict(connect=300, read=600, write=300, pool=300) for w in wire)
            assert len(wire) == sum(c["request"]["http_attempt_count"] for c in observed)
        assert report.attach_journal(root, prepared, decisions) == []
        assert all(not d["journal_only_requests"] for d in decisions)
        usage, requests = report.usage(root, prepared, decisions)
        metrics = request_metrics(calls)
        assert sum(u["logical_requests"] for u in usage) == len(calls)
        assert sum(u["http_attempted"] for u in usage) == len(calls) + 6
        assert sum(u["known_connection_failures"] for u in usage) == 0
        assert study.shared.usage(root)["known_retryable_failures"] == 6
        assert not (root / "halt.json").exists()
        assert all(r["trace_event_seq"] is not None for r in requests)
        assert not sum(permits["active_at_close"].values())
        assert len([e for e in permits["events"] if e["event"] == "grant"]) == len(calls) + 6
        result = dict(provider=provider, passed=True, local_matches=1, external_model_calls=0,
                      logical_requests=len(calls), http_attempts=len(calls) + 6,
                      metrics=metrics, audit=checked, usage=usage, technical=technical)
        b.seal_json(root.parent / "verification.json", result)
        results.append(result)
    b.seal_json(output / "verification.json", dict(passed=True, providers=results, external_model_calls=0))
    return dict(passed=True, providers=[r["provider"] for r in results], external_model_calls=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False))
