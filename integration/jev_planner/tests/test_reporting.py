"""Accounting, comparison boundaries, and safe portable copies of planner runs."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil

import pytest

from integration.jev_planner import reporting


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def config(name="fixture", policy="events_or_periodic", prompt="A"):
    return dict(name=name, executor=dict(model="jev9b", input_version="jev-choice-v6", revision="pinned"),
        planner=dict(model="glm-5.3-flash", reasoning_effort="low", max_tokens=8192),
        trigger=dict(policy=policy, interval_turns=3, events=["faint", "tera", "forced_switch"]),
        prompts=dict(planner=dict(text=prompt, path="/source/planner.txt", sha256="prompt"),
                     executor=dict(text="Current observation wins.", path="/source/executor.txt", sha256="executor")),
        evaluation=dict(kind="battle", schedule=dict(path="/source/schedule.json", data=dict(
            schedule=[dict(slot_id="a", paired_slot_id="matchup", jev_actor="p1"),
                      dict(slot_id="b", paired_slot_id="matchup", jev_actor="p2")], teams={"one": "team"}))))


def outcomes(values=("player_won", "opponent_won")):
    return [dict(slot_id=slot, paired_slot_id=paired, jev_actor=actor,
                 status="completed" if value is not None else "failed", outcome=value,
                 battle_tag=f"battle-{slot}", username=f"model-{slot}")
            for slot, paired, actor, value in zip(("a", "b"), ("matchup", "matchup"), ("p1", "p2"), values)]


def events():
    result = []
    plan = dict(objective="Win </script><script>alert('bad')</script>", priorities=["Preserve tempo"],
                preserve=[], threats=[], tera_policy="Wait", contingencies=[])
    for request, call in ((1, True), (2, False), (3, False)):
        common = dict(battle="battle-a", actor="p1", rqid=request, decision=f"d{request}", turn=request,
                      boundary=dict(protocol_event_seq=request, line_index=1))
        criteria = {"move:1": dict(kind="move", slot=1)}
        if request != 3:
            criteria["move:2"] = dict(kind="move", slot=2)
        payload = dict(state=dict(turn=request, self_team=[dict(active=True, slot=1, species="Pikachu",
            current_move_slots=[dict(slot=1, name="Thunderbolt"), dict(slot=2, name="Volt Switch")])],
            planner_advice=dict(plan=plan, generated_turn=1, age_turns=request - 1, decision="d1")),
            questions=dict(action=dict(type="choice", instructions="Select one", criteria=criteria)))
        result.append(dict(type="planner_decision", should_call=call,
            reasons=["initial", "event:faint"] if call else ["single_candidate" if request == 3 else "plan_reuse"],
            plan_age=None if call else request - 1, **common))
        if call:
            message = dict(type="planner_request", messages=[dict(role="user", content="Original request")], **common)
            result.extend([message, deepcopy(message)])
            result.extend([
                dict(type="planner_transport", request_id="d1", attempt=1, elapsed_seconds=0.1,
                     status="failure", http_status=503, usage=None),
                dict(type="planner_transport", request_id="d1", attempt=2, elapsed_seconds=0.2,
                     status="success", http_status=200, usage=dict(prompt_tokens=10, completion_tokens=3)),
                dict(type="planner_response", content=json.dumps(plan), reasoning="Original reasoning",
                     plan=plan, usage=dict(prompt_tokens=10, completion_tokens=3), elapsed_seconds=0.5, **common),
            ])
        result.append(dict(type="input", payload=payload, base_payload={"unchanged": True},
            commands={key: f"/choose move {n}" for n, key in enumerate(criteria, 1)}, **common))
        if request == 1:
            result.extend([
                dict(type="executor_http_request", request_id="d1", attempt=1),
                dict(type="executor_transport", request_id="d1", attempt=1, elapsed_seconds=0.4,
                     usage=dict(input_tokens=8, output_tokens=1)),
            ])
        if request != 3:
            result.append(dict(type="response", body=dict(answers=dict(action=dict(choice="move:1")),
                usage=dict(input_tokens=8, output_tokens=1) if request == 1 else None), elapsed_seconds=0.6, **common))
        result.append(dict(type="selection", choice="move:1", command="/choose move 1",
            automatic=request == 3, reused=False, plan_generated_turn=1, plan_age=request - 1, **common))
        result.append(dict(type="wire", command="/choose move 1", status="sent", **common))
        if request == 2:
            result.append(dict(type="selection", choice="move:1", command="/choose move 1",
                automatic=False, reused=True, plan_generated_turn=1, plan_age=1, **common))
    return result


def run(directory: Path, *, configs=None, mode="mock", kind="trace", results=None, recorded=None):
    configs = configs or [config()]
    entries = []
    for number, cfg in enumerate(configs):
        name = cfg["name"]
        entries.append(dict(name=name, config=cfg))
        path = directory / "conditions" / name
        write_json(path / "result.json", dict(mode=mode, kind=kind,
            outcomes=results[number] if results is not None else outcomes()))
        path.joinpath("events.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False)
            for row in (recorded if recorded is not None else events())) + "\n", encoding="utf-8")
    write_json(directory / "manifest.json", dict(schema_version="jev-planner-run-v1", run_id=directory.name,
        mode=mode, kind=kind, config=configs[0], conditions=entries, source={"core.py": "abc"}))
    write_json(directory / "result.json", dict(conditions=[entry["name"] for entry in entries]))
    return directory


def embedded(path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r'<script id="viewer-data" type="application/json">(.*?)</script>', text, re.S)
    assert match is not None
    return json.loads(match.group(1))


def test_logical_calls_and_physical_attempts_are_not_double_counted(tmp_path):
    source = run(tmp_path / "run", mode="live", kind="battle")
    summary = reporting.summarize_condition(source / "conditions/fixture", mode="live", kind="battle")
    assert summary["decisions"] == 3
    assert summary["planner"]["logical_calls"] == 1
    assert summary["planner"]["duplicate_request_records"] == 1
    assert summary["planner"]["http_attempts"] == 2
    assert summary["planner"]["retry_attempts"] == 1
    assert summary["planner"]["call_reasons"] == {"initial": 1, "event:faint": 1}
    assert summary["planner"]["skip_reasons"] == {"plan_reuse": 1, "single_candidate": 1}
    assert summary["executor"]["logical_calls"] == 2
    assert summary["executor"]["http_attempts"] == 1
    assert summary["executor"]["calls_without_http_ledger"] == 1
    assert summary["automatic_selections"] == 1
    assert summary["cached_selection_records"] == 1
    assert summary["planner"]["decisions_reusing_plan"] == 1


def test_unknown_usage_and_cost_are_distinct_from_zero(tmp_path):
    source = run(tmp_path / "run")
    summary = reporting.summarize_condition(source / "conditions/fixture", mode="mock", kind="trace")
    planner = summary["planner"]
    assert planner["tokens"]["input"]["total"] == 10
    assert planner["tokens"]["input"]["unknown_records"] == 1
    assert planner["tokens"]["output"]["total"] == 3
    assert planner["tokens"]["total"]["total"] == 13
    assert planner["cost"]["known_records"] == 0
    assert planner["cost"]["unknown_records"] == 2
    assert summary["executor"]["tokens"]["input"]["unknown_records"] == 1
    assert summary["executor"]["tokens"]["input"]["total"] == 8


def test_mock_http_ledger_is_separate_from_physical_api_cost(tmp_path):
    source = run(tmp_path / "run")
    summary = reporting.summarize_condition(source / "conditions/fixture", mode="mock", kind="trace")
    assert summary["planner"]["http_attempts"] == 0
    assert summary["planner"]["simulated_http_attempts"] == 2
    assert summary["planner"]["retry_attempts"] == 0
    assert summary["planner"]["simulated_retry_attempts"] == 1
    assert summary["executor"]["http_attempts"] == 0
    assert summary["executor"]["simulated_http_attempts"] == 1
    assert summary["planner"]["simulated"] and summary["executor"]["simulated"]


@pytest.mark.parametrize("mode,kind", [("mock", "trace"), ("live", "trace"), ("mock", "battle")])
def test_mock_and_trace_never_report_empirical_battle_score(tmp_path, mode, kind):
    source = run(tmp_path / "run", mode=mode, kind=kind)
    summary = reporting.summarize_condition(source / "conditions/fixture", mode=mode, kind=kind)
    assert summary["battle_score"] is None
    assert summary["efficacy_evidence"] is False
    assert (summary["technical_battle_score"] is not None) == (kind == "battle")


def test_failure_denominators_and_incomplete_pairs_are_explicit(tmp_path):
    left = outcomes(("player_won", None))
    left.append(dict(slot_id="c", paired_slot_id="d", jev_actor="p1", status="unattempted", outcome=None))
    source = run(tmp_path / "run", mode="live", kind="battle", results=[left])
    summary = reporting.summarize_condition(source / "conditions/fixture", mode="live", kind="battle")
    assert summary["failures"] | {"event_counts": {}} == dict(
        planned=3, attempted=2, completed=1, failed=1, unattempted=1, unknown_status=0,
        failure_rate=0.5, event_counts={})
    assert summary["battle_score"]["denominator"] == 1


@pytest.mark.parametrize("axis", ["trigger", "planner_prompt"])
def test_live_contrast_uses_only_common_complete_pair_groups(tmp_path, axis):
    first, second = config("left"), config("right")
    if axis == "trigger":
        second["trigger"]["policy"] = "every_decision"
    else:
        second["prompts"]["planner"]["text"] = "B"
    # Source paths may differ without changing any actual prompt/schedule content.
    second["prompts"]["executor"]["path"] = "/elsewhere/executor.txt"
    second["evaluation"]["schedule"]["path"] = "/elsewhere/schedule.json"
    source = run(tmp_path / "run", configs=[first, second], mode="live", kind="battle",
                 results=[outcomes(("opponent_won", "tied")), outcomes(("player_won", "tied"))])
    contrast = reporting.compare_runs([source])["contrasts"][0]
    assert contrast["status"] == "compatible"
    assert contrast["differences"] == [axis]
    assert contrast["paired"]["common_completed_pairs"] == 1
    assert contrast["paired"]["mean_difference_right_minus_left"] == 0.5
    assert contrast["paired"]["pairs"][0]["paired_slot_id"] == "matchup"
    assert contrast["empirical_data"] is True and contrast["efficacy_evidence"] is False


@pytest.mark.parametrize("change,status", [("model", "incompatible"), ("schedule", "incompatible"),
    ("options", "incompatible"), ("executor_prompt", "incompatible"), ("both_axes", "confounded")])
def test_confounded_or_incompatible_conditions_have_no_paired_effect(tmp_path, change, status):
    first, second = config("left"), config("right", policy="every_decision")
    if change == "model":
        second["executor"]["model"] = "jev27b"
    elif change == "schedule":
        second["evaluation"]["schedule"]["data"]["teams"]["one"] = "different team"
    elif change == "options":
        second["planner"]["reasoning_effort"] = "high"
    elif change == "executor_prompt":
        second["prompts"]["executor"]["text"] = "Different instructions"
    else:
        second["prompts"]["planner"]["text"] = "B"
    source = run(tmp_path / "run", configs=[first, second], mode="live", kind="battle")
    contrast = reporting.compare_runs([source])["contrasts"][0]
    assert contrast["status"] == status
    assert contrast["paired"] is None
    assert contrast["efficacy_evidence"] is False


def test_mock_contrast_and_failed_pair_never_invent_live_effect(tmp_path):
    configs = [config("left"), config("right", policy="every_decision")]
    source = run(tmp_path / "mock", configs=configs)
    contrast = reporting.compare_runs([source])["contrasts"][0]
    assert contrast["status"] == "technical_only" and contrast["paired"] is None
    source = run(tmp_path / "live", configs=configs, mode="live", kind="battle",
                 results=[outcomes(), outcomes(("player_won", None))])
    paired = reporting.compare_runs([source])["contrasts"][0]["paired"]
    assert paired["common_completed_pairs"] == 0
    assert paired["mean_difference_right_minus_left"] is None
    assert paired["excluded_incomplete_pairs"] == 1


def test_same_slot_names_with_changed_actor_are_incompatible(tmp_path):
    right = outcomes()
    right[0]["jev_actor"] = "p2"
    source = run(tmp_path / "live", configs=[config("left"), config("right", policy="every_decision")],
        mode="live", kind="battle", results=[outcomes(), right])
    contrast = reporting.compare_runs([source])["contrasts"][0]
    assert contrast["status"] == "incompatible" and contrast["paired"] is None


def test_different_ex_record_is_provenance_not_a_treatment_axis(tmp_path):
    first, second = config("left"), config("right", policy="every_decision")
    first["evaluation"]["experiment_record"] = dict(path="EX-NEW-A.md", text="Registration A")
    second["evaluation"]["experiment_record"] = dict(path="EX-NEW-B.md", text="Registration B")
    source = run(tmp_path / "live", configs=[first, second], mode="live", kind="battle",
                 results=[outcomes(("player_lost", "tied")), outcomes()])
    contrast = reporting.compare_runs([source])["contrasts"][0]
    assert contrast["status"] == "compatible"
    assert contrast["paired"]["mean_score_left"] == 0.25


def test_outcomes_must_match_the_frozen_schedule_pair_identity(tmp_path):
    values = outcomes()
    for row in values:
        row["paired_slot_id"] = "changed"
    source = run(tmp_path / "live", configs=[config("left"), config("right", policy="every_decision")],
                 mode="live", kind="battle", results=[values, values])
    contrast = reporting.compare_runs([source])["contrasts"][0]
    assert contrast["status"] == "incompatible"
    assert "outcome_schedule_identity_mismatch" in contrast["reasons"]


def test_prepared_run_requires_final_seal_and_rejects_changed_originals(tmp_path):
    from integration.jev27b.study import seal
    source = run(tmp_path / "source")
    manifest = source / "manifest.json"
    (source / "manifest.sha256").write_text(sha256(manifest.read_bytes()).hexdigest() + "\n")
    with pytest.raises(ValueError, match="unfinished"):
        reporting.compare_runs([source])
    seal(source)
    reporting.compare_runs([source])
    output = tmp_path / "export"
    reporting.export_run(source, output)
    assert (output / "raw/checksums.sha256").read_bytes() == (source / "checksums.sha256").read_bytes()
    (source / "conditions/fixture/events.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="seal mismatch"):
        reporting.compare_runs([source])


def test_export_preserves_escaped_originals_and_plan_source_links(tmp_path):
    recorded = events()
    for turn in (1, 2, 3):
        recorded.append(dict(type="protocol", username="model-a", sequence=turn,
            protocol=f">battle-a\n|turn|{turn}\n|move|p1a: Pikachu|Thunderbolt|p2a: Mew\n|request|PRIVATE" +
                     ("\n|win|model-a" if turn == 3 else "")))
    source = run(tmp_path / "source", recorded=recorded)
    before = {str(path.relative_to(source)): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    output = tmp_path / "export"
    receipt = reporting.export_run(source, output)
    assert Path(receipt["index"]).is_file()
    assert receipt["decisions"] == 3
    page = output / "condition-0001/battle-0001.html"
    data = embedded(page)
    assert data["decisions"][1]["applied_plan"]["index"] == 1
    assert "</script><script>" in data["decisions"][1]["applied_plan"]["plan"]["objective"]
    assert "<script>alert('bad')</script>" not in page.read_text()
    assert "PRIVATE" not in "\n".join(row["protocol"] for row in data["public_logs"][0]["rows"])
    assert data["public_logs"][0]["terminal"]["winner"] == "model-a"
    provenance = json.loads((output / "provenance.json").read_text())
    for name, content in before.items():
        assert (source / name).read_bytes() == content
        assert (output / "raw" / name).read_bytes() == content
        assert provenance["original_files"][name]["sha256"] == sha256(content).hexdigest()
    assert not re.search(r'<(?:script|link|img)\b[^>]*(?:src|href)=["\']https?://', page.read_text())
    moved = tmp_path / "moved"
    shutil.move(str(output), moved)
    assert embedded(moved / "condition-0001/battle-0001.html") == data
    for row in embedded(moved / "index.html")["links"]:
        assert (moved / row["href"]).is_file()


def test_export_refuses_existing_or_source_destinations(tmp_path):
    source = run(tmp_path / "source")
    for destination in (source, source / "new-viewer", tmp_path):
        with pytest.raises(FileExistsError):
            reporting.export_run(source, destination)
    destination = tmp_path / "new-viewer"
    reporting.export_run(source, destination)
    with pytest.raises(FileExistsError):
        reporting.export_run(source, destination)


def test_export_rejects_escaping_audit_reference_before_writing(tmp_path):
    source = run(tmp_path / "source", recorded=events() + [dict(type="observation", input_audit=dict(path="../../../outside.json"))])
    write_json(tmp_path / "outside.json", dict(secret="do not copy"))
    output = tmp_path / "export"
    with pytest.raises(ValueError, match="inside the run"):
        reporting.export_run(source, output)
    assert not output.exists()


def test_restarted_physical_room_uses_slot_identity_for_public_logs(tmp_path):
    values, recorded = outcomes(), []
    physical = "battle-gen9ou-1"
    for row in values:
        slot = row["slot_id"]
        logical = f"{slot}:{physical}"
        row.update(battle=logical, battle_tag=physical)
        recorded.append(dict(type="protocol", slot_id=slot, username=row["username"], sequence=1,
            protocol=f">{physical}\n|turn|1\n|move|p1a: {slot}|Tackle|p2a: Mew\n|win|{row['username']}"))
        recorded.append(dict(type="input", slot_id=slot, battle=logical, protocol_battle=physical,
            actor=row["jev_actor"], rqid=1, decision=f"d-{slot}", turn=1,
            payload=dict(state={}, questions={"action": {"criteria": {"move:1": {"kind": "move", "slot": 1}}}})))
        recorded.append(dict(type="selection", slot_id=slot, battle=logical, protocol_battle=physical,
            actor=row["jev_actor"], rqid=1, decision=f"d-{slot}", turn=1,
            choice="move:1", command="/choose move 1", automatic=True, reused=False))
    source = run(tmp_path / "source", kind="battle", recorded=recorded, results=[values])
    output = tmp_path / "export"
    receipt = reporting.export_run(source, output)
    assert receipt["battles"] == 2 and receipt["decisions"] == 2
    condition = embedded(output / "condition-0001/index.html")
    assert {item["label"] for item in condition["links"]} == {f"a:{physical}", f"b:{physical}"}
    for number, slot in enumerate(("a", "b"), 1):
        page = embedded(output / f"condition-0001/battle-{number:04d}.html")
        assert page["battle"] == f"{slot}:{physical}"
        assert len(page["public_logs"]) == len(page["decisions"]) == len(page["outcomes"]) == 1
        assert page["public_logs"][0]["username"] == f"model-{slot}"
