import json
from pathlib import Path

import pytest

from integration.pokechamp.observability.recorder import (
    BattleBundleConfig,
    BattleRecorder,
    BundleCollisionError,
    DataRootError,
    data_root_from_environment,
    verify_bundle,
)


def bundle_config(*, battle_id="battle-001", replacement_for=None):
    return BattleBundleConfig(
        experiment_id="experiment-alpha",
        battle_id=battle_id,
        battle_format="gen9ou",
        teams=[
            {"role": "player", "id": 1, "sha256": "a" * 64},
            {"role": "opponent", "id": 2, "sha256": "b" * 64},
        ],
        model={"provider": "ollama", "model": "glm-5.3-flash"},
        source={"workspace_sha": "1" * 40, "pokechamp_sha": "2" * 40},
        replacement_for=replacement_for,
    )


def read_events(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_research_data_root_is_explicit_and_identifiers_are_safe(tmp_path):
    with pytest.raises(DataRootError, match="POKECHAMP_DATA_ROOT"):
        data_root_from_environment({})
    assert data_root_from_environment(
        {"POKECHAMP_DATA_ROOT": str(tmp_path)}
    ) == tmp_path.resolve()
    with pytest.raises(DataRootError, match="absolute"):
        data_root_from_environment({"POKECHAMP_DATA_ROOT": "relative-data"})

    with pytest.raises(DataRootError, match="experiment_id"):
        BattleRecorder.create(tmp_path, bundle_config().__class__(
            experiment_id="../escape",
            battle_id="battle",
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
        ))


def test_event_ids_source_seal_and_collision_policy(tmp_path):
    recorder = BattleRecorder.create(tmp_path, bundle_config())
    recorder.record_protocol(
        ">battle-gen9ou-1\n|turn|7\n|request|{}", showdown_turn=7
    )

    first = recorder.begin_decision(
        showdown_turn=7,
        decision_kind="turn_action",
        battle_state={"active": "Pikachu", "available_moves": ["thunderbolt"]},
    )
    recorder.record_llm_call(
        status="failure",
        system_prompt="system one",
        user_prompt="user one",
        provider_reasoning="reason one",
        raw_content="not-json",
        canonical_parsed_output=None,
        request={"model": "glm-5.3-flash"},
        response={"done_reason": "length"},
        validation={"json_valid": False},
    )
    recorder.record_llm_call(
        status="success",
        system_prompt="system two",
        user_prompt="user two",
        provider_reasoning="reason two",
        raw_content='{"move":"thunderbolt"}',
        canonical_parsed_output={"move": "thunderbolt"},
        request={"model": "glm-5.3-flash"},
        response={"done_reason": "stop", "completion_tokens": 5},
        validation={"json_valid": True, "battle_action_valid": True},
    )
    recorder.record_decision_result(selected_action="/choose move thunderbolt")
    recorder.record_wire_action(
        action="/choose move thunderbolt",
        battle_tag="battle-gen9ou-1",
        send_status="sent",
    )
    recorder.end_decision(first)

    second = recorder.begin_decision(
        showdown_turn=7,
        decision_kind="forced_switch",
        battle_state={"force_switch": True, "available_switches": ["Charizard"]},
    )
    recorder.record_decision_result(
        selected_action="/choose switch Charizard",
        validation={"source": "player_local"},
    )
    recorder.record_wire_action(
        action="/choose switch Charizard",
        battle_tag="battle-gen9ou-1",
        send_status="sent",
    )
    recorder.end_decision(second)
    recorder.finish(
        outcome="player_won",
        battle_tag="battle-gen9ou-1",
        result={"winner": "research-player", "turns": 7},
    )

    bundle = recorder.bundle_path
    events = read_events(bundle / "events.jsonl")
    assert [event["event_seq"] for event in events] == list(range(1, len(events) + 1))
    assert {event["event_type"] for event in events} <= {
        "battle_start",
        "protocol_in",
        "decision_start",
        "llm_call",
        "decision_result",
        "wire_action",
        "battle_end",
        "logging_error",
    }
    assert [e["decision_seq"] for e in events if e["event_type"] == "decision_start"] == [1, 2]
    assert [e["llm_call_seq"] for e in events if e["event_type"] == "llm_call"] == [1, 2]
    assert {e["decision_seq"] for e in events if e["event_type"] == "llm_call"} == {1}
    assert all(
        {"schema_version", "experiment_id", "battle_id", "timestamp_utc", "monotonic_offset_ms"}
        <= event.keys()
        for event in events
    )

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["evidence_complete"] is True
    assert manifest["sealed"] is True
    assert manifest["result"]["outcome"] == "player_won"
    assert manifest["showdown_battle_tag"] == "battle-gen9ou-1"
    assert manifest["classification"] == "research_observability"
    assert manifest["efficacy_evidence"] is False
    assert verify_bundle(bundle)["valid"] is True
    assert (bundle / "checksums.sha256").stat().st_mode & 0o077 == 0
    sealed_source = {
        name: (bundle / name).read_bytes()
        for name in ("manifest.json", "events.jsonl", "checksums.sha256")
    }
    recorder.record_protocol("|turn|999", showdown_turn=999)
    recorder.finish(outcome="player_lost", result={"should_not_replace": True})
    assert sealed_source == {
        name: (bundle / name).read_bytes() for name in sealed_source
    }

    with pytest.raises(BundleCollisionError):
        BattleRecorder.create(tmp_path, bundle_config())


@pytest.mark.parametrize(
    "outcome",
    ["player_won", "player_lost", "tied", "interrupted", "provider_failure"],
)
def test_terminal_outcomes_are_preserved_without_becoming_efficacy(tmp_path, outcome):
    recorder = BattleRecorder.create(tmp_path, bundle_config(battle_id=outcome))
    recorder.finish(outcome=outcome, result={"status": outcome})
    manifest = json.loads(
        (recorder.bundle_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["result"]["outcome"] == outcome
    assert manifest["evidence_complete"] is True
    assert manifest["efficacy_evidence"] is False


def test_mid_battle_write_failure_is_nonfatal_and_marks_incomplete(tmp_path, monkeypatch):
    recorder = BattleRecorder.create(tmp_path, bundle_config())
    original = recorder._append_serialized
    failed = False

    def fail_once(serialized):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated disk fault")
        return original(serialized)

    monkeypatch.setattr(recorder, "_append_serialized", fail_once)
    with pytest.warns(RuntimeWarning, match="evidence is incomplete"):
        recorder.record_protocol("|turn|1", showdown_turn=1)
    recorder.finish(outcome="interrupted", result={"reason": "test"})

    manifest = json.loads(
        (recorder.bundle_path / "manifest.json").read_text(encoding="utf-8")
    )
    events = read_events(recorder.bundle_path / "events.jsonl")
    assert manifest["evidence_complete"] is False
    assert manifest["logging"]["error_count"] == 1
    assert any(event["event_type"] == "logging_error" for event in events)
    assert verify_bundle(recorder.bundle_path)["valid"] is True


def test_checksum_tampering_is_detected(tmp_path):
    recorder = BattleRecorder.create(tmp_path, bundle_config())
    recorder.finish(outcome="tied", result={})
    with (recorder.bundle_path / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{}\n")
    verification = verify_bundle(recorder.bundle_path)
    assert verification["valid"] is False
    assert any("checksum mismatch" in error for error in verification["errors"])


def test_correction_uses_a_new_identity_and_existing_replacement_target(tmp_path):
    with pytest.raises(DataRootError, match="existing bundle"):
        BattleRecorder.create(
            tmp_path,
            bundle_config(battle_id="correction", replacement_for="missing"),
        )
    original = BattleRecorder.create(
        tmp_path, bundle_config(battle_id="original")
    )
    original.finish(outcome="interrupted", result={})
    correction = BattleRecorder.create(
        tmp_path,
        bundle_config(battle_id="correction", replacement_for="original"),
    )
    correction.finish(outcome="tied", result={})
    manifest = json.loads(
        (correction.bundle_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["replacement_for"] == "original"
    assert original.bundle_path.is_dir()


def test_known_cloud_credential_is_never_written_to_research_source(
    tmp_path, monkeypatch
):
    secret = "credential-that-must-never-be-evidence"
    monkeypatch.setenv("OLLAMA_API_KEY", secret)
    recorder = BattleRecorder.create(tmp_path, bundle_config())
    decision = recorder.begin_decision(
        showdown_turn=1,
        decision_kind="turn_action",
        battle_state={"note": secret},
    )
    recorder.record_llm_call(
        status="success",
        system_prompt=f"system {secret}",
        user_prompt=f"user {secret}",
        provider_reasoning=secret,
        raw_content=f'{{"move":"thunderbolt","echo":"{secret}"}}',
        canonical_parsed_output={"move": "thunderbolt", "echo": secret},
        request={},
        response={},
        validation={"json_valid": True},
    )
    recorder.record_decision_result(selected_action="/choose move thunderbolt")
    recorder.end_decision(decision)
    recorder.finish(outcome="player_won", result={})
    source = "".join(
        (recorder.bundle_path / name).read_text(encoding="utf-8")
        for name in ("manifest.json", "events.jsonl", "checksums.sha256")
    )
    assert secret not in source
    assert "[REDACTED]" in source
