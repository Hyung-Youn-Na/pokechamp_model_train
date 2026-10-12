"""Offline EX-038 recovery and EX-037/038 public-parser comparison only."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from integration.pokechamp import ab_head_to_head as h
from integration.pokechamp.battle_adapter import install_identity_adapter
from integration.pokechamp.diagnostics.input_audit import differences, digest
from integration.pokechamp.diagnostics.protect_expiry import context, old_normalizer, write
from integration.pokechamp.improved_io import battle_prompts, live_delivery
from integration.pokechamp.improved_io.backend import FixedBackend
from integration.pokechamp.improved_io.calculations import compute
from integration.pokechamp.improved_io.calculator import Calculator
from integration.pokechamp.improved_io.gate import validate_input
from integration.pokechamp.improved_io.protocol import observed_state
from integration.pokechamp.improved_io.state import normalize
from integration.pokechamp.observability.recorder import BattleBundleConfig, BattleRecorder

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "project_context/exec-plans/evidence/ep036"
BUNDLES = ROOT / ".pokechamp-data/experiments"
FAILURE = ROOT / ".pokechamp-data/ab-head-to-head32/ex038/attempts/b04-r1-s1-a1/p1.result.json"


def fake_b2_wire(value, output):
    sent = []
    recorder = BattleRecorder.create(
        output,
        BattleBundleConfig(
            experiment_id="ep036-offline",
            battle_id=value["identity"]["battle_id"],
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
        ),
    )
    for _ in range(value["identity"]["decision_seq"]):
        recorder.begin_decision(showdown_turn=16, decision_kind="turn_action", battle_state={})

    def chat(**kwargs):
        sent.append(copy.deepcopy(kwargs))
        return dict(
            model="glm-5.3-flash",
            message=dict(
                content="Offline fixture.\n" + json.dumps(value["request"]["legal_actions"][0])
            ),
            done=True,
            done_reason="stop",
        )

    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "local-fixture"},
        trace_sink=recorder,
        client_factory=lambda **_: SimpleNamespace(chat=chat),
    )
    backend.experiment_policy = h.policy_selection(h.B2)
    backend.runtime_identity = h.runtime_identity()
    backend.io_profile = "io-battle-only-v1"
    backend.battle_prompt_identity = battle_prompts.identity("v1.2.0")
    backend.input_context = value
    backend.delivery = live_delivery.build(value)
    backend.get_LLM_action(
        backend.delivery.system_prompt,
        backend.delivery.user_json,
        "glm-5.3-flash",
        temperature=0,
        json_format=False,
    )
    assert len(sent) == 1
    assert sent[0]["messages"] == [
        dict(role="system", content=backend.delivery.system_prompt),
        dict(role="user", content=backend.delivery.user_json),
    ]
    rows = [json.loads(s) for s in (recorder.bundle_path / "events.jsonl").read_text().splitlines()]
    snapshots = {e["event_seq"]: e for e in rows if e["event_type"] == "input_snapshot"}
    (call,) = [e for e in rows if e["event_type"] == "llm_call"]
    assert live_delivery.original_for_call(call, snapshots) == value
    assert backend.parsed_action.action == value["request"]["legal_actions"][0]
    return dict(
        calls=1,
        provider_calls=0,
        messages=sent[0]["messages"],
        original_link_verified=True,
        parsed_action=backend.parsed_action.action,
    )


def compare_prefixes(before, output):
    results = []
    for study in ("ex037-cloud", "ex038-cloud"):
        counts = Counter()
        for path in sorted((BUNDLES / study / "battles").glob("*/events.jsonl")):
            prefix = []
            for event in map(json.loads, path.open()):
                if event["event_type"] == "protocol_in":
                    prefix.append(event)
                if event["event_type"] != "decision_start":
                    continue
                row = dict(
                    study=study,
                    bundle=path.parent.name,
                    decision=event["decision_seq"],
                    cutoff=event["event_seq"],
                    prefix_sha256=digest(prefix),
                )
                try:
                    old = before(prefix)
                except ValueError as exc:
                    row["before_error"] = str(exc)
                    assert str(exc) == "unsupported delayed effect destination"
                    old = None
                new = observed_state(prefix)
                row["after_sha256"] = digest(new)
                if old is None:
                    row["status"] = "recovered_slotless_target"
                    row["after"] = new
                else:
                    row["before_sha256"] = digest(old)
                    delta = differences(old, new)
                    row["status"] = "identical" if not delta else "changed_doom_desire"
                    if delta:
                        # The only newly accepted start spelling is Doom Desire.
                        assert any("|Doom Desire" in e["protocol"] for e in prefix)
                        assert all(
                            d["path"].startswith(("$.pending_effects", "$.delayed_history"))
                            for d in delta
                        )
                        row["differences"] = delta
                counts[row["status"]] += 1
                results.append(row)
        print(study, dict(counts), flush=True)
    write(output / "prefix-comparison.json", results)
    return dict(Counter((r["study"] + ":" + r["status"]) for r in results))


def run(output, before):
    output.mkdir(parents=True, exist_ok=False)
    install_identity_adapter()
    baseline = old_normalizer(before)
    old_parser = baseline.__globals__["observed_state"]
    args = context(BUNDLES / "ex038-cloud/battles/b04-r1-s1-a1-p1", 20)
    failure = json.loads(FAILURE.read_text())["io_failure"]
    assert args["request"] == failure["request"]
    # The failure record and the decision prefix must carry exactly the same public rows.
    keys = ("event_seq", "protocol")
    assert [{k: e[k] for k in keys} for e in args["observed_protocol"]] == [
        {k: e[k] for k in keys} for e in failure["protocol"]
    ]
    write(output / "failure-prefix.json", failure["protocol"])
    write(output / "failure-request.json", failure["request"])
    for function, params in ((old_parser, dict(events=failure["protocol"])), (baseline, args)):
        try:
            function(**params)
        except ValueError as exc:
            assert str(exc) == "unsupported delayed effect destination"
        else:
            raise AssertionError("Original failure did not reproduce")
    write(
        output / "before-error.json",
        dict(error="unsupported delayed effect destination", parser=True, normalize=True),
    )
    fixed, _ = normalize(**args)
    fixed["condition_id"] = "B"
    with Calculator() as calculator:
        fixed["calculation_bundle"] = compute(fixed, calculator)
        validate_input(fixed)
    (effect,) = fixed["current_observation"]["protocol_state"]["pending_effects"]
    assert effect["target_slot"] == "p2a" and effect["observed_start_turn"] == 16
    write(output / "fixed-input.json", fixed)
    write(output / "fake-wire.json", fake_b2_wire(fixed, output / "transport"))
    print("actual failure: normalize/calculate/validate/B2/backend passed", flush=True)
    summary = compare_prefixes(old_parser, output)
    write(
        output / "summary.json",
        dict(failure_decision=20, provider_calls=0, prefix_counts=summary, recovered_effect=effect),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before", type=Path, default=EVIDENCE / "before")
    args = parser.parse_args()
    run(args.output, args.before)
