"""EX-042 qualification: fake32 and extra provider pairs using actual local workers."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from .. import benchmark as b
from .. import distributed_lead as d
from .. import team_preview_run as runner
from .. import team_preview_study as study
from ..parallel_server import check_ports
from .team_preview import audit


def run(output, experiment_id="EX-042"):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = output / "fake32"
    value = study.prepare(root, experiment_id=experiment_id)
    # Synthetic receipt authorizes only the fake transport; final paid entry uses
    # the completed regression, fake32 and separate-pair evidence below.
    b.seal_json(
        output / "local-purpose.json",
        dict(external_model_calls=0, purpose="EX-042 local qualification"),
    )
    receipt = output / "fake-entry.json"
    b.seal_json(
        receipt,
        dict(
            source_files=value["parent_files"],
            local_passed=True,
            wire_passed=True,
            execution_protocol=study.execution_protocol(value),
            evidence=[
                dict(
                    path=str(output / "local-purpose.json"),
                    sha256=b.digest(output / "local-purpose.json"),
                )
            ],
        ),
    )
    result = runner.run(root, output / "fake-data", verification=receipt)
    b.seal_json(output / "fake32-result.json", result)
    if not result["collection_complete"]:
        raise ValueError("fake32 failed: " + str(result))
    extra = output / "extra-pairs"
    prepared = study.prepare(extra, experiment_id=experiment_id)
    rows, _ = runner.staged_schedule(prepared["schedule"])
    ports = list(range(8100, 8108))
    check_ports(ports)
    with tempfile.TemporaryDirectory(prefix="pc-ex042-local-") as temp:
        with ExitStack() as stack:
            brokers = d.Brokers(stack, temp, prepared)
            with patch.dict(os.environ, POKECHAMP_FAKE_CONNECT_FAILURES="2"):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    jobs = [
                        pool.submit(
                            b.run_attempt,
                            output / "pair-data",
                            extra,
                            prepared,
                            row,
                            1,
                            port=(8100 if row["provider_id"] == "ollama" else 8104)
                            + row["swap"],
                            broker_path=str(brokers.path_for(row)),
                        )
                        for row in rows
                    ]
                    attempts = [job.result() for job in jobs]
            if experiment_id == "EX-043":
                from .corrected_lead import audit_attempt
                for attempt in attempts:
                    assert audit_attempt(extra, attempt)["passed"]
            checked = runner.inspect_pair(extra, attempts, prepared, brokers.snapshot())
        snapshot = brokers.snapshot()
    b.seal_json(output / "extra-pair-gate.json", checked)
    if not checked["passed"]:
        raise ValueError("extra pair gate failed: " + str(checked["errors"]))
    assert not sum(snapshot["active_at_close"].values())
    check_ports(ports)
    b.seal_json(output / "extra-pair-permits.json", snapshot)
    technical = audit(attempts, prepared, extra)
    from ..team_preview_report import build_report

    extra_report = build_report(extra)
    assert not extra_report["technical_errors"]
    b.seal_json(output / "extra-pair-report.json", extra_report)
    final = dict(
        passed=True,
        external_model_calls=0,
        source_files=value["parent_files"],
        fake32=result,
        extra_pairs=technical,
        extra_pair_report=extra_report,
        ports_closed=ports,
    )
    b.seal_json(output / "verification.json", final)
    return dict(
        passed=True,
        external_model_calls=0,
        fake32=result,
        extra_pair_report=extra_report,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--experiment-id", choices=["EX-042", "EX-043"], default="EX-042")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.experiment_id), ensure_ascii=False))
