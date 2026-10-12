"""Read-only EX-036 Protect replay; writes new, separately identified evidence."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from integration.pokechamp.action_validation import replay
from integration.pokechamp.battle_adapter import install_identity_adapter
from integration.pokechamp.diagnostics.input_audit import differences, digest
from integration.pokechamp.improved_io.battle_only_protocol import replay_window
from integration.pokechamp.improved_io.battle_prompts import assemble
from integration.pokechamp.improved_io.calculations import compute
from integration.pokechamp.improved_io.calculator import CalculationError, Calculator
from integration.pokechamp.improved_io.gate import validate_input
from integration.pokechamp.improved_io.protocol import protect_lifetimes
from integration.pokechamp.improved_io.state import normalize

ROOT = Path(__file__).resolve().parents[3]
VERSION = "protect-expiry-v1"
BUNDLES = ROOT / ".pokechamp-data/experiments/ex036-cloud/battles"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def context(bundle, decision):
    rows = [json.loads(s) for s in (bundle / "events.jsonl").read_text().splitlines()]
    manifest = json.loads((bundle / "manifest.json").read_text())
    (start,) = [
        e
        for e in rows
        if e["event_type"] == "decision_start" and e["decision_seq"] == decision
    ]
    cutoff = start["event_seq"]
    prefix = [
        e for e in rows if e["event_type"] == "protocol_in" and e["event_seq"] < cutoff
    ]
    requests = [
        json.loads(line[9:])
        for e in prefix
        for line in e["protocol"].splitlines()
        if line.startswith("|request|") and line[9:]
    ]
    (own,) = [t["showdown_team"] for t in manifest["teams"] if t["role"] == "player"]
    recent = [
        {k: e[k] for k in ("event_seq", "protocol")}
        for e in replay_window(bundle, cutoff, prefix)
    ]
    battle, _ = replay(bundle / "events.jsonl", through=cutoff)
    return dict(
        battle=battle,
        request=requests[-1],
        own_team=own,
        protocol=recent,
        observed_protocol=prefix,
        battle_id=manifest["battle_id"],
        actor_id=manifest["metadata"]["actor_id"],
        decision_seq=decision,
    )


def old_normalizer(directory):
    def load(name):
        spec = importlib.util.spec_from_file_location(
            "integration.pokechamp.improved_io._protect_before_" + name,
            directory / (name + ".py"),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    protocol, state = load("protocol"), load("state")
    for name in ("live_effects", "observed_state", "protocol_rows"):
        setattr(state, name, getattr(protocol, name))
    return state.normalize


def fake_wire(value):
    # Production backend/serialization with a local transport. No provider call.
    from integration.pokechamp.constants import OLLAMA_MODEL
    from integration.pokechamp.improved_io import experiment_policy as policy
    from integration.pokechamp.improved_io.backend import FixedBackend
    from integration.pokechamp.improved_io.battle_prompts import identity
    from integration.pokechamp.improved_io.inputfix32 import runtime_identity

    delivered = []

    def chat(**kwargs):
        delivered.append(copy.deepcopy(kwargs))
        assert json.loads(kwargs["messages"][-1]["content"]) == value
        return SimpleNamespace(
            model=OLLAMA_MODEL,
            message=SimpleNamespace(
                content="Local offline response.\n"
                + json.dumps(value["request"]["legal_actions"][0]),
                thinking="",
            ),
            prompt_eval_count=0,
            eval_count=0,
            total_duration=0,
            load_duration=0,
            done_reason="stop",
        )

    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "local-fixture"},
        client_factory=lambda **_: SimpleNamespace(chat=chat),
    )
    backend.experiment_policy = policy.selection(policy.HEAD_TO_HEAD)
    backend.runtime_identity = runtime_identity()
    backend.io_profile = "io-battle-only-v1"
    backend.battle_prompt_identity = identity("v1.2.0")
    backend.input_context = value
    backend.get_LLM_action(
        assemble(value, version="v1.2.0"),
        json.dumps(value),
        OLLAMA_MODEL,
        json_format=False,
    )
    assert len(delivered) == 1 and backend.parsed_action is not None
    return dict(
        messages=delivered[0]["messages"],
        request_context=backend._request_context(),
        parsed_action=backend.parsed_action.action,
        calls=len(delivered),
        provider_calls=0,
    )


def comparable(value):
    result = copy.deepcopy(value)
    result.get("calculation_bundle", {}).pop("elapsed_ms", None)
    return result


def run(output, before):
    output.mkdir(parents=True, exist_ok=False)
    install_identity_adapter()
    baseline = old_normalizer(before)
    args = context(BUNDLES / "b01-r2-s0-a1-p2", 29)
    old, _ = baseline(**args)
    old["condition_id"] = "B"
    write(output / "failure-before-input.json", old)
    try:
        with Calculator() as calc:
            compute(old, calc)
    except CalculationError as exc:
        assert str(exc) == "unsupported active effects: ['PROTECT']"
        error = str(exc)
    else:
        raise AssertionError("Original failure did not reproduce")
    fixed, _ = normalize(**args)
    fixed["condition_id"] = "B"
    delta = differences(old, fixed)
    assert [d["path"] for d in delta] == [
        "$.current_observation.opponent_confirmed[5].effects.PROTECT",
        "$.identity.state_id",
    ]
    target = fixed["current_observation"]["opponent_confirmed"][5]
    assert (
        target["parser_effects"]["PROTECT"] == 0 and "PROTECT" not in target["effects"]
    )
    write(
        output / "failure-lifetimes.json", protect_lifetimes(args["observed_protocol"])
    )
    write(output / "failure-prefix.json", args["observed_protocol"])
    with Calculator() as calc:
        fixed["calculation_bundle"] = compute(fixed, calc)
        validate_input(fixed)
        write(
            output / "failure-worker.json",
            dict(request=calc.last_request, response=calc.last_response),
        )
    write(output / "failure-fixed-input.json", fixed)
    write(output / "failure-fake-wire.json", fake_wire(fixed))
    # The same public scene from the other actor exercises the own-team branch.
    paired_args = context(BUNDLES / "b01-r2-s0-a1-p1", 30)
    paired_old, _ = baseline(**paired_args)
    paired, _ = normalize(**paired_args)
    paired_delta = differences(paired_old, paired)
    assert len(paired_delta) == 2 and any(
        ".self_team[" in d["path"] and d["path"].endswith(".effects.PROTECT")
        for d in paired_delta
    )
    write(
        output / "paired-self-normalization.json",
        dict(
            differences=paired_delta,
            lifetimes=protect_lifetimes(paired_args["observed_protocol"]),
        ),
    )
    regression = []
    with Calculator() as calc:
        for bundle in sorted(BUNDLES.iterdir()):
            manifest = json.loads((bundle / "manifest.json").read_text())
            if manifest["metadata"]["condition_id"] != "B":
                continue
            for e in map(
                json.loads, (bundle / "events.jsonl").read_text().splitlines()
            ):
                if e["event_type"] != "llm_call":
                    continue
                original = json.loads(e["user_prompt"])
                params = context(bundle, e["decision_seq"])
                value, _ = normalize(**params)
                value["condition_id"] = "B"
                value["calculation_bundle"] = compute(value, calc)
                validate_input(value)
                diffs = differences(comparable(original), comparable(value))
                regression.append(
                    dict(
                        battle_id=manifest["battle_id"],
                        decision_seq=e["decision_seq"],
                        original_sha256=digest(comparable(original)),
                        replay_sha256=digest(comparable(value)),
                        differences=diffs,
                    )
                )
                if len(regression) % 25 == 0:
                    print("replayed", len(regression), flush=True)
    write(output / "regression.json", regression)
    assert len(regression) == 269, len(regression)
    assert not any(r["differences"] for r in regression), "Unexplained input changes"
    summary = dict(
        version=VERSION,
        original_error=error,
        failure_differences=delta,
        restored=True,
        parser_effects_preserved=True,
        fake_wire_calls=1,
        paired_self_verified=True,
        replayed=269,
        identical_inputs=269,
        provider_calls=0,
    )
    write(output / "result.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.before), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
