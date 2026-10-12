"""C-033 local workers, shared ledger, B2 wire and viewer audit; fake models only."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import benchmark as b
from .. import team_preview_study as study
from ..improved_io.live_delivery import original_for_call
from ..observability.render import rebuild_battle
from ..permits import PermitBroker
from ..team_preview import (
    PROMPT,
    build_input,
    command_for_lead,
    parse_lead,
    prompt_identity,
)


def check_request_settings(request, prepared):
    """Compare provider options to the seal, including seed application, not RNG seed."""
    model = prepared["model"]
    expected = dict(
        model=model["model"], thinking_effort=model["thinking_effort"],
        temperature=model["temperature"], seed=model["seed"],
        requested_output_tokens=model["max_output_tokens"], context_window=model["context_window"],
    )
    if "provider_config" in prepared:
        expected.update(prepared["provider_config"])
    if any(request.get(key) != value for key, value in expected.items()):
        raise ValueError("request_provider_options_differ_from_seal")
    if prepared.get("provider_config", {}).get("provider") == "zai":
        expected_format = {"type": "json_object"} if request["json_format"] else None
        if request.get("response_format") != expected_format:
            raise ValueError("request_response_format")


def check_executed_wire(action, selected):
    kind, name = next(iter(action.items()))
    command = "/choose " + ("move" if kind in ("terastallize", "dynamax") else kind) + " " + name
    if kind in ("terastallize", "dynamax"):
        command += " " + kind
    if selected != command:
        raise ValueError("executed_action_selected_wire_mismatch")


def check_decision_resolution(results, resolution):
    assert len(results) == 1
    assert results[0]["canonical_parsed_output"] == resolution["extracted_action"]
    assert results[0]["validation"]["action_resolution"] == resolution


def audit(attempts, prepared, prepared_root=None):
    actors = []
    intents = set()
    original_prepared = prepared
    for attempt in attempts:
        from ..distributed_lead import selected
        prepared = selected(original_prepared, attempt["slot"])
        if not attempt["eligible"] or attempt["category"] is not None:
            raise ValueError(f"local worker failed: {attempt['slot_id']}: {attempt['category']}")
        if prepared_root is not None:
            target = Path(prepared_root) / "attempts" / attempt["attempt_id"]
            request = b.read_sealed(target / "request.json")
            study.verify_actor_request(request)
            normalized = subprocess.run(
                ["node", str(b.WORKSPACE_ROOT / "integration/pokechamp/diagnostic_teams.cjs"),
                 str(target / "request.json"), str(target / "normalized-teams.jsonl")],
                capture_output=True, text=True, timeout=30,
            )
            assert normalized.returncode == 0, "actual simulator team mismatch"
            seed = [json.loads(line) for line in (target / "battle-seed.jsonl").read_text().splitlines()]
            assert len(seed) == 1 and str(seed[0]["seed"]) == attempt["slot"]["battle_seed"]
        for role, record in attempt["actors"].items():
            bundle = Path(record["bundle"])
            if not b.verify_bundle(bundle)["valid"]:
                raise ValueError("local bundle integrity")
            manifest = json.loads((bundle / "manifest.json").read_text())
            assert manifest["source"] == prepared["source"]
            assert manifest["model"]["model"] == prepared["model"]["model"]
            assert manifest["model"]["thinking_effort"] == "low"
            events = [
                json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()
            ]
            public = [event for event in events if event["event_type"] == "protocol_in"]
            snapshots = {e["event_seq"]: e for e in events if e["event_type"] == "input_snapshot"}
            calls = [event for event in events if event["event_type"] == "llm_call"]
            preview = [e for e in calls if e["request"]["call_role"] == "team_preview"]
            setting = study.actor_policy(attempt["slot"], role, prepared)
            assert len(preview) == (1 if setting == "llm_lead" else 0)
            (wire,) = [
                e
                for e in events
                if e["event_type"] == "wire_action" and e["action"].startswith("/team ")
            ]
            assert wire["send_status"] == "sent"
            own = next(t["showdown_team"] for t in manifest["teams"] if t["role"] == "player")
            context = build_input(
                own,
                public,
                battle_id=manifest["battle_id"],
                actor_id=role,
                decision_seq=wire["decision_seq"],
            )
            selection = int(wire["action"][6])
            rng = random.Random(manifest["metadata"]["python_random_seed"])
            # Pinned Player.__init__ selects an avatar from this file before
            # the first preview. Reproduce that existing RNG consumption too.
            avatars = (
                (b.cli.POKECHAMP_ROOT / "poke_env/data/avatar_names.txt").read_text().splitlines()
            )
            rng.choice(avatars)
            order = list(range(1, 7))
            rng.shuffle(order)
            seeded_command = "/team " + "".join(map(str, order))
            if preview:
                (call,) = preview
                assert original_for_call(call, snapshots) == context
                selected = prepared["team_preview_prompt_identity"]
                assert call["request"]["team_preview_prompt_identity"] == selected
                assert selected == prompt_identity(selected)
                if selected["version"] == "v1.0.0":
                    assert call["system_prompt"] == PROMPT.read_text()
                assert call["decision_seq"] == wire["decision_seq"]
                assert parse_lead(call["raw_content"], list(range(1, 7))) == selection
                result = next(
                    e
                    for e in events
                    if e["event_type"] == "decision_result"
                    and e["decision_seq"] == wire["decision_seq"]
                )
                initial = result["validation"]["team_preview"]["seeded_random_command"]
                assert initial == seeded_command
                assert command_for_lead(initial, selection, list(range(1, 7))) == wire["action"]
                assert record["team_preview"]["result"]["status"] == "sent"
            else:
                assert wire["action"] == seeded_command
            side = context["identity"]["side"]
            first = next(
                line
                for event in public
                for line in event["protocol"].splitlines()
                if line.startswith(f"|switch|{side}a:")
            )
            assert first.split("|")[3] == context["self_team"][selection - 1]["details"]
            for call in calls:
                req = call["request"]
                intent_path = req["request_intent"]
                assert intent_path not in intents
                intents.add(intent_path)
                intent = b.read_sealed(intent_path)
                assert intent["actor"].endswith("/" + role)
                assert intent["payload"]["user_prompt"] == call["user_prompt"]
                assert intent["payload"]["system_prompt"] == call["system_prompt"]
                check_request_settings(req, prepared)
                from ..transport_policy import audit_attempts

                for retry_path in audit_attempts(call, actor=intent["actor"]):
                    if retry_path != intent_path:
                        assert retry_path not in intents
                        intents.add(retry_path)
                for key, val in intent["payload"]["request"].items():
                    assert req[key] == val, "ledger/trace request settings mismatch"
                if req["call_role"] == "self_action":
                    from ..improved_io.inputfix32 import verify_runtime
                    from ..improved_io.output import validate_exact_action

                    full = original_for_call(call, snapshots)
                    verify_runtime(req, context=full)
                    assert full["identity"]["actor_id"] == role
                    assert full["condition_id"] == "B" and req["delivery_identity"]
                    resolution = call["validation"]["action_resolution"]
                    action = resolution["executed_action"]
                    validate_exact_action(
                        action, full["request"]["legal_actions"],
                        request_kind=full["request"]["kind"],
                        can_tera=full["request"]["can_tera"],
                    )
                    # C-033 preserves B2's existing output recovery. Raw format
                    # failure is reported, not promoted into a new strategy gate.
                    results = [e for e in events if e["event_type"] == "decision_result"
                               and e["decision_seq"] == call["decision_seq"] and e["success"]]
                    check_decision_resolution(results, resolution)
                    if full["identity"].get("observation_version") == "official-client-v1":
                        from ..observation.normalize import SlotCandidates

                        observed = [e for e in events if e["event_type"] == "observation_snapshot"
                                    and e["decision_seq"] == call["decision_seq"]]
                        assert len(observed) == 1
                        candidates = SlotCandidates(observed[0]["official_state"]["candidates"])
                        assert candidates.order(action).message == results[0]["selected_action"]
                    else:
                        check_executed_wire(action, results[0]["selected_action"])
                    wires = [e for e in events if e["event_type"] == "wire_action"
                             and e["decision_seq"] == call["decision_seq"]]
                    assert len(wires) == 1 and wires[0]["send_status"] == "sent"
                    assert wires[0]["action"] == results[0]["selected_action"]
                else:
                    assert req["call_role"] == "team_preview"
                response_path = Path(intent_path).with_name(
                    Path(intent_path).name.replace("intent-", "response-")
                )
                raw = b.read_sealed(response_path)["response"]
                assert raw["message"]["content"] == call["raw_content"]
                assert raw["message"].get("thinking") == call.get("provider_reasoning")
            rendered = rebuild_battle(bundle)
            assert rendered["integrity_valid"]
            html = (bundle / "report.html").read_text()
            assert wire["action"] in html
            if preview:
                assert "선봉 선택" in html and "team_preview" in html
            actors.append(
                dict(
                    bundle=str(bundle),
                    role=role,
                    policy=setting,
                    lead_slot=selection,
                    wire=wire["action"],
                    first_switch=first,
                    preview_calls=len(preview),
                    battle_calls=len(calls) - len(preview),
                    viewer=str(bundle / "report.html"),
                )
            )
    return dict(
        passed=True,
        provider_calls=0 if prepared["transport"] == "fake" else len(intents),
        local_matches=len(attempts),
        actors=actors,
        ledger_intents=len(intents),
        efficacy_evidence=False,
    )


def run(output, *, experiment_id=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    prepared_root = output / "prepared"
    prepared = study.prepare(prepared_root, transport="fake", concurrency=4 if experiment_id == "EX-041" else 2, experiment_id=experiment_id)
    rows = [row for row in prepared["schedule"] if row["paired_slot_id"] == "b01-r1"]
    assert len(rows) == 2
    b.seal_json(
        output / "local-validation-plan.json",
        dict(
            planned_local_matches=2,
            rows=rows,
            provider_calls=0,
            collected_experiment_matches=0,
            purpose="worker/ledger/transport/B2 regression only; not strategy evaluation",
        ),
    )
    with tempfile.TemporaryDirectory(prefix="lead-permit-") as short:
        socket = str(Path(short) / "permit.sock")
        with PermitBroker(socket, prepared["execution"]["account_request_limit"], prepared["execution"]["model_request_limits"]) as broker:
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = [
                    pool.submit(
                        b.run_attempt,
                        output / "data",
                        prepared_root,
                        prepared,
                        row,
                        1,
                        port=8100 + i,
                        broker_path=socket,
                    )
                    for i, row in enumerate(rows)
                ]
                attempts = [job.result() for job in jobs]
            permits = broker.snapshot()
    b.seal_json(output / "attempts.json", attempts)
    b.seal_json(output / "permits.json", permits)
    assert not sum(permits["active_at_close"].values())
    result = audit(attempts, prepared, prepared_root)
    b.seal_json(output / "verification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", choices=("EX-039", "EX-040", "EX-041"), default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, experiment_id=args.experiment_id), ensure_ascii=False, indent=2))
