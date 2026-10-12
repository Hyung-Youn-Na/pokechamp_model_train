"""EX-030 read-only replay of every recorded B input, including unanswered calls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from integration.pokechamp.action_validation import replay
from integration.pokechamp.battle_adapter import install_identity_adapter
from integration.pokechamp.improved_io.battle_only_protocol import replay_window
from integration.pokechamp.improved_io.calculations import compute
from integration.pokechamp.improved_io.calculator import Calculator
from integration.pokechamp.improved_io.gate import validate_input
from integration.pokechamp.improved_io.state import normalize

ROOT = Path(__file__).resolve().parents[3]
COHORTS = {"EX-028": "ex028-c0-compare32", "EX-029": "ex-029-c0-compare32"}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def differences(before, after, path="$"):
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        return [
            row
            for key in sorted(before.keys() | after.keys())
            for row in (
                [
                    {
                        "path": path + "." + key,
                        "before": before.get(key),
                        "after": after.get(key),
                    }
                ]
                if key not in before or key not in after
                else differences(before[key], after[key], path + "." + key)
            )
        ]
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path, "before": before, "after": after}]
        return [
            row
            for i, (a, b) in enumerate(zip(before, after, strict=True))
            for row in differences(a, b, f"{path}[{i}]")
        ]
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def inputs():
    for experiment, directory in COHORTS.items():
        for path in sorted(
            (ROOT / ".pokechamp-data/benchmarks" / directory / "attempts").glob(
                "B-*/result.json"
            )
        ):
            attempt = json.loads(path.read_text())
            for actor, record in attempt["actors"].items():
                if attempt["slot"]["methods"][int(actor[-1]) - 1] != "io":
                    continue
                bundle = Path(record["bundle"])
                events = [
                    json.loads(s)
                    for s in (bundle / "events.jsonl").read_text().splitlines()
                ]
                manifest = json.loads((bundle / "manifest.json").read_text())
                # Opponent team data is never passed to normalize or compute.
                own = next(
                    t["showdown_team"]
                    for t in manifest["teams"]
                    if t["role"] == "player"
                )
                for event in events:
                    if event["event_type"] != "llm_call":
                        continue
                    original = json.loads(event["user_prompt"])
                    starts = [
                        e
                        for e in events
                        if e["event_type"] == "decision_start"
                        and e.get("decision_seq") == event["decision_seq"]
                        and e["event_seq"] < event["event_seq"]
                    ]
                    if len(starts) != 1:
                        raise ValueError("ambiguous decision cutoff")
                    cutoff = starts[0]["event_seq"]
                    prefix = [
                        e
                        for e in events
                        if e["event_type"] == "protocol_in" and e["event_seq"] < cutoff
                    ]
                    requests = [
                        json.loads(line[9:])
                        for e in prefix
                        for line in e["protocol"].splitlines()
                        if line.startswith("|request|") and line[9:]
                    ]
                    yield dict(
                        experiment=experiment,
                        slot=attempt["slot_id"],
                        bundle=bundle,
                        event=event,
                        original=original,
                        cutoff=cutoff,
                        prefix=prefix,
                        request=requests[-1],
                        own=own,
                    )


def run(output, *, baseline=None):
    output.mkdir(parents=True, exist_ok=False)
    install_identity_adapter()
    rows = []
    calculator = Calculator()
    try:
        for item in inputs():
            old = item["original"]
            identity = old["identity"]
            key = f"{item['experiment']}-{item['slot']}-{item['event']['event_seq']}"
            row = dict(
                key=key,
                experiment=item["experiment"],
                slot=item["slot"],
                bundle=str(item["bundle"]),
                event_seq=item["event"]["event_seq"],
                decision_seq=identity["decision_seq"],
                turn=identity["showdown_turn"],
                cutoff=item["cutoff"],
                response=item["event"].get("raw_content") is not None,
                original_input_sha256=digest(old),
                prefix_sha256=digest(item["prefix"]),
            )
            try:
                battle, _ = replay(
                    item["bundle"] / "events.jsonl", through=item["cutoff"]
                )
                recent = [
                    {k: e[k] for k in ("event_seq", "protocol")}
                    for e in replay_window(
                        item["bundle"], item["cutoff"], item["prefix"]
                    )
                ]
                value, _ = normalize(
                    battle,
                    item["request"],
                    item["own"],
                    recent,
                    battle_id=identity["battle_id"],
                    actor_id=identity["actor_id"],
                    decision_seq=identity["decision_seq"],
                    observed_protocol=item["prefix"],
                )
                value["condition_id"] = "B"
                value["calculation_bundle"] = compute(value, calculator)
                validate_input(value)
                request = copy.deepcopy(calculator.last_request)
                value["calculation_bundle"].pop("elapsed_ms", None)
                comparable = copy.deepcopy(old)
                comparable["calculation_bundle"].pop("elapsed_ms", None)
                row.update(
                    status="success",
                    differences=differences(comparable, value),
                    input_sha256=digest(value),
                    worker_request_sha256=digest(request),
                )
                artifact = dict(
                    input=value,
                    worker_request=request,
                    worker_response=calculator.last_response,
                )
                (output / (key + ".json")).write_text(
                    json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
                )
                if baseline:
                    before = json.loads((baseline / (key + ".json")).read_text())
                    row["baseline_differences"] = differences(before["input"], value)
                print(key, len(row["differences"]), flush=True)
            except Exception as error:
                row.update(
                    status="failure", error_type=type(error).__name__, error=str(error)
                )
                print(key, row["error"], flush=True)
                if calculator.process.poll() is not None:
                    calculator.close()
                    calculator = Calculator()
            rows.append(row)
    finally:
        calculator.close()
    counts = {name: sum(r["experiment"] == name for r in rows) for name in COHORTS}
    if counts != {"EX-028": 435, "EX-029": 201}:
        raise ValueError(f"input denominator drift: {counts}")
    result = dict(
        counts=counts,
        rows=rows,
        succeeded=sum(r["status"] == "success" for r in rows),
        failed=sum(r["status"] == "failure" for r in rows),
    )
    (output / "index.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print({k: v for k, v in result.items() if k != "rows"}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    run(args.output, baseline=args.baseline)


if __name__ == "__main__":
    main()
