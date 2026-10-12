"""Preserved D-019 decision-time replay, with explicit input and evidence roots."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from .. import benchmark as b
from ..action_validation import replay
from ..battle_adapter import install_identity_adapter
from ..constants import POKECHAMP_ROOT
from .calculations import compute
from .calculator import Calculator
from .evidence import load_cases
from .gate import validate_input
from .semantics import audit
from .state import normalize


def run(
    battle_root, evidence_path, output, *, runtime_window=False, semantics_version=None,
    observation_backend="legacy-poke-env",
):
    from ..observation import OFFICIAL, selected

    backend = selected({"observation_backend": observation_backend})
    if backend == OFFICIAL and (not runtime_window or semantics_version != "calculator-input-v2"):
        raise ValueError("official offline input requires the B runtime window and calculator-input-v2")
    cases = load_cases(battle_root, evidence_path)
    output.mkdir(parents=True, exist_ok=False)
    source_files = {
        str(p.relative_to(b.WORKSPACE_ROOT)): b.digest(p) for p in b.source_files()
    }
    for name in source_files:
        target = output / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(b.WORKSPACE_ROOT / name, target)
    records = []
    semantic = []
    previous_cwd = Path.cwd()
    try:
        os.chdir(POKECHAMP_ROOT)
        install_identity_adapter()
        for case in cases:
            record = {"case": case["case"]["id"], "cutoff": case["cutoff"]}
            try:
                bundle = Path(case["bundle"])
                if backend == OFFICIAL:
                    from ..diagnostics.observation_compare import bounded_prefix

                    events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
                    prefix, _ = bounded_prefix(events, case["decision"])
                    case = {**case, "protocol": prefix}
                else:
                    battle, _ = replay(bundle / "events.jsonl", through=case["cutoff"])
                requests = [
                    json.loads(line[9:])
                    for event in case["protocol"]
                    for line in event["protocol"].splitlines()
                    if line.startswith("|request|") and line[9:]
                ]
                manifest = json.loads((bundle / "manifest.json").read_text())
                own = next(
                    t["showdown_team"]
                    for t in manifest["teams"]
                    if t["role"] == "player"
                )
                recent = case["protocol"]
                if runtime_window:
                    from .battle_only_protocol import replay_window

                    recent = replay_window(bundle, case["cutoff"], case["protocol"])
                if backend == OFFICIAL:
                    from ..observation.normalize import normalize as official_normalize
                    from ..observation.runtime import OfficialClient

                    with OfficialClient(manifest["metadata"]["actor_id"]) as client:
                        state = client.snapshot(case["protocol"], case["case"]["battle"])
                        value, _ = official_normalize(
                            state, own, recent, case["protocol"], battle_id=case["case"]["battle"],
                            actor_id=manifest["metadata"]["actor_id"],
                            decision_seq=case["decision"]["decision_seq"], build_identity=client.identity,
                        )
                else:
                    value, _ = normalize(
                        battle,
                        requests[-1],
                        own,
                        recent,
                        battle_id=case["case"]["battle"],
                        actor_id=manifest["metadata"]["actor_id"],
                        decision_seq=case["decision"]["decision_seq"],
                        observed_protocol=case["protocol"] if runtime_window else None,
                        semantics_version=semantics_version,
                    )
                if runtime_window:
                    value["condition_id"] = "B"
                with Calculator() as calculator:
                    value["calculation_bundle"] = compute(value, calculator)
                validate_input(value)
                assert all(
                    e["event_seq"] < case["cutoff"] for e in value["recent_events"]
                )
                assert (
                    value["current_observation"]["self_team"][0]["moves"]
                    == requests[-1]["side"]["pokemon"][0]["moves"]
                )
                if case["case"]["id"] == "IO-C02":
                    entries = [
                        e
                        for e in value["calculation_bundle"]["entries"]
                        if e["scenario_id"].startswith("out-move-earthquake-")
                    ]
                    assert entries and all(
                        e["damage_range_hp"] == [0, 0] for e in entries
                    )
                b.seal_json(output / f"{record['case']}.json", value)
                semantic.append(
                    audit(case, value, recent=recent if runtime_window else None)
                )
                record.update(
                    status="success",
                    entries=len(value["calculation_bundle"]["entries"]),
                )
            except Exception as error:
                record.update(
                    status="failure", error_type=type(error).__name__, error=str(error)
                )
            records.append(record)
            if record["status"] == "failure":
                break
    finally:
        os.chdir(previous_cwd)
    from .posthoc import validate

    structural = len(records) == 15 and all(r["status"] == "success" for r in records)
    semantic_passed = len(semantic) == 15 and all(r["passed"] for r in semantic)
    posthoc = validate(battle_root, output) if structural else []
    posthoc_passed = len(posthoc) == 3 and all(r["valid"] for r in posthoc)
    b.seal_json(output / "semantic.json", semantic)
    b.seal_json(output / "posthoc.json", posthoc)
    if source_files != {
        str(p.relative_to(b.WORKSPACE_ROOT)): b.digest(p) for p in b.source_files()
    }:
        raise ValueError("source changed during offline validation")
    result = {
        "cases": records,
        "source_checks": "15 matched sealed sources",
        "structural_replay_passed": structural,
        "semantic_rubric": "passed" if semantic_passed else "failed",
        "posthoc_truth_damage_validation": "passed" if posthoc_passed else "failed",
        "offline_gate_passed": structural and semantic_passed and posthoc_passed,
        "outputs": {p.name: b.digest(p) for p in output.glob("*.json")},
        "source_files": source_files,
    }
    if backend == OFFICIAL:
        from ..observation import selection

        result.update(selection(backend))
    if runtime_window:
        result["input_profile"] = "io-battle-only-v1"
    b.seal_json(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battle-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        args.battle_root.resolve(), args.evidence.resolve(), args.output.resolve()
    )
    print(
        json.dumps({k: v for k, v in result.items() if k != "source_files"}, indent=2)
    )
    return 0 if result["offline_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
