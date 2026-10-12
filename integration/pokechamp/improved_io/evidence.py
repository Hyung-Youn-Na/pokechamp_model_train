"""Read-only authored rubric validation with an explicit source battle root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..observability.recorder import verify_bundle

PROMPTS = Path(__file__).with_name("prompts")


def load_cases(battle_root, evidence_path):
    battle_root = Path(battle_root).resolve(strict=True)
    evidence = json.loads(Path(evidence_path).read_text())["cases"]
    originals = {(c["battle"], c["llm_event"]["event_seq"]): c for c in evidence}
    cases = json.loads((PROMPTS / "acceptance_cases.json").read_text())["cases"]
    if len(cases) != 15 or len({c["id"] for c in cases}) != 15:
        raise ValueError("expected 15 unique cases")
    if set(originals) != {(c["battle"], c["event_seq"]) for c in cases}:
        raise ValueError("rubric and excerpt identities differ")
    result = []
    for case in cases:
        bundle = (battle_root / case["battle"]).resolve(strict=True)
        if bundle.parent != battle_root:
            raise ValueError("battle outside source root")
        integrity = verify_bundle(bundle)
        if not integrity["valid"]:
            raise ValueError(f"source integrity failure: {case['id']}")
        manifest = json.loads((bundle / "manifest.json").read_text())
        if manifest["model"]["method"] != "io":
            raise ValueError("non-IO source")
        events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
        by_seq = {e["event_seq"]: e for e in events}
        if len(by_seq) != len(events):
            raise ValueError("duplicate source event")
        original = originals[(case["battle"], case["event_seq"])]
        if events[original["source_line"] - 1] != original["llm_event"]:
            raise ValueError("source line mismatch")
        call = by_seq[case["event_seq"]]
        if call["event_type"] != "llm_call" or not set(case["source_events"]) <= set(by_seq):
            raise ValueError("missing rubric evidence")
        starts = [
            e
            for e in events
            if e["event_type"] == "decision_start"
            and e.get("decision_seq") == call.get("decision_seq")
            and e["event_seq"] < call["event_seq"]
        ]
        if len(starts) != 1:
            raise ValueError("ambiguous decision-time cutoff")
        cutoff = starts[0]["event_seq"]
        # Explicitly expose only pre-decision protocol to the action fixture builder.
        observed = [
            e for e in events if e["event_type"] == "protocol_in" and e["event_seq"] < cutoff
        ]
        result.append(
            {
                "case": case,
                "bundle": str(bundle),
                "cutoff": cutoff,
                "protocol": observed,
                "decision": starts[0],
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battle-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    cases = load_cases(args.battle_root, args.evidence)
    print(
        json.dumps(
            {
                "validated_sources": len(cases),
                "calculator_replay": "not_run",
                "cutoffs": {c["case"]["id"]: c["cutoff"] for c in cases},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
