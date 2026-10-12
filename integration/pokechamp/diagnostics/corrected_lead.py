"""EX-043 fail-closed input audit before a completed worker's slot is reused."""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .. import benchmark as b
from .ex042_input_audit import run


def audit_attempt(directory, attempt, *, offline=False):
    directory = Path(directory)
    output = directory / "input-audits" / (attempt["attempt_id"] + ("-offline" if offline else ""))
    if output.exists():
        raise ValueError("input audit already exists; no automatic replay")
    bundles = [Path(record["bundle"]) for record in attempt["actors"].values()
               if record.get("bundle") and (Path(record["bundle"]) / "events.jsonl").exists()]
    if attempt["eligible"] and len(bundles) != 2:
        raise ValueError("input audit requires both actors")
    from ..team_preview_study import execution_protocol
    version = execution_protocol(b.read_sealed(directory / "plan.json")).get("input_audit", "public-cutoff-v1")
    if version == "official-cutoff-v1":
        from .official_cutoff import run as audit_run
    else:
        audit_run = run
    result = audit_run(directory, output, study_root=directory, bundles=bundles)
    totals = result["totals"]
    passed = ((not attempt["eligible"] or (totals.get("actors") == 2 and totals.get("decisions", 0) > 0
                                                  and totals.get("status_not_generated", 0) == 0))
              and totals.get("wire_link_failures", 0) == 0
              and totals.get("status_failure", 0) == 0
              and totals.get("input_differences", 0) == 0
              and totals.get("consistency_issues", 0) == 0)
    receipt = dict(passed=passed, attempt_id=attempt["attempt_id"],
                   audit_version=version, summary=result,
                   eligible_at_worker=attempt["eligible"],
                   absent_actor_bundles=2-len(bundles),
                   original_category=attempt["category"],
                   index_relative=str((output / "index.json").relative_to(directory)),
                   index_sha256=b.digest(output / "index.json"))
    b.seal_json(directory / "input-audit-receipts" / (attempt["attempt_id"] + ".json"), receipt)
    return receipt


def read_receipt(directory, attempt_id):
    directory = Path(directory)
    receipt = b.read_sealed(directory / "input-audit-receipts" / (attempt_id + ".json"))
    from ..team_preview_study import execution_protocol
    plan = directory / "plan.json"
    version = execution_protocol(b.read_sealed(plan)).get("input_audit", "public-cutoff-v1") if plan.exists() else "public-cutoff-v1"
    if (receipt["attempt_id"] != attempt_id or receipt["audit_version"] != version
            or b.digest(directory / receipt["index_relative"]) != receipt["index_sha256"]):
        raise ValueError("input audit receipt drift")
    return receipt


def bounded_process(command, log, *, deadline):
    """Audit and its calculator share a private process group; reserve cleanup time."""
    from ..cloud import CloudRequestError

    env = dict(os.environ, OLLAMA_API_KEY="", ZAI_API_KEY="")
    with Path(log).open("w") as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                   env=env, cwd=b.cli.POKECHAMP_ROOT, start_new_session=True)
        try:
            timeout = None if deadline is None else max(0, deadline - time.time())
            code = process.wait(timeout=timeout)
        except BaseException as exc:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
            if isinstance(exc, subprocess.TimeoutExpired):
                raise CloudRequestError("budget_stop", "input audit reached execution cleanup deadline") from exc
            raise
    if code:
        raise RuntimeError("input audit subprocess failed; see " + str(log))


def before_reuse(directory, attempt):
    directory = Path(directory).resolve()
    clock = directory / "cloud-clock.json"
    deadline = b.read_sealed(clock)["cleanup_deadline"] - 60 if clock.exists() else None
    claim = directory / "run-claim.json"
    if claim.exists():
        local = b.read_sealed(claim)
        if local.get("local_eight"):
            local_deadline = local["started_at"] + 1740
            deadline = min(deadline, local_deadline) if deadline is not None else local_deadline
    logs = directory / "input-audit-logs"
    logs.mkdir(exist_ok=True)
    bounded_process(
        [sys.executable, "-m", "integration.pokechamp.diagnostics.corrected_lead",
         "--directory", str(directory), "--attempt-id", attempt["attempt_id"]],
        logs / (attempt["attempt_id"] + ".log"), deadline=deadline)
    return read_receipt(directory, attempt["attempt_id"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    attempt = b.read_sealed(args.directory / "attempts" / args.attempt_id / "result.json")
    audit_attempt(args.directory, attempt)
