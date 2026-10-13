"""CPU-only admission, immutable parent, unique-slot accounting and portable history."""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from integration.jev27b import audit, battle, continuation as c, study
from integration.jev27b.tests.test_transport import IDENTITY


@pytest.fixture(scope="module")
def parent_info():
    return c.validate_parent(study.LIVE)


def segment(info, count=9, *, failed=None):
    outcomes = [dict(copy.deepcopy(row), slot=24 + i, username=f"new{i}", completed=True,
        audit_passed=True, server_cleaned=True, opponent_cleaned=True,
        outcome="player_won", turns=1, requests=0)
        for i, row in enumerate(info["continuation_schedule"][:count])]
    if failed is not None:
        outcomes[-1].update(completed=False, failure_scope="collection",
                            error=dict(type="RuntimeError", detail=failed))
        outcomes[-1].pop("outcome", None)
    session = SimpleNamespace(records=[], calls=0, started=123, monotonic_started=None)
    result = study.summarize(session, outcomes, info["continuation_schedule"],
        error=dict(type="RuntimeError", detail=failed) if failed else None,
        expected_games=9, expected_pairs=None)
    result["final_audit_passed"] = True
    return result


def manifest(info):
    value = copy.deepcopy(info["manifest"])
    value.update(experiment_id="EX-083", execution_profile=c.PROFILE,
        runtime=c.runtime_settings(),
        parent=dict(directory=info["parent"], seal_sha256=c.PARENT_SEAL),
        collection_schedule=copy.deepcopy(info["continuation_schedule"]),
        inherited_outcomes=copy.deepcopy(info["inherited_outcomes"]),
        attempt_plan=c.attempt_plan(info), source={},
        continuation_policy=dict(inherited_valid_games=23, retry_slot=c.RETRY_SLOT,
            additional_attempts_for_retry_slot=1, new_unattempted_games=8,
            total_unique_slots=32, maximum_total_battle_attempts=33,
            additional_recollections=0, automatic_resume=False))
    return value


def test_real_parent_is_pinned_and_all_591_include_partial_failure(parent_info):
    info = parent_info
    assert info["passed"] and len(info["inherited_outcomes"]) == 23
    assert info["continuation_schedule"] == info["schedule"][23:]
    assert info["continuation_schedule"][0]["slot_id"] == "b04-r2-s0"
    pairs = list(c.iter_parent_responses(info["parent"]))
    assert len(pairs) == 591
    assert all(pair["input"]["decision"] == pair["response"]["decision"] for pair in pairs)
    assert [p["response"]["event_seq"] for p in pairs] == sorted(p["response"]["event_seq"] for p in pairs)
    assert info["failed_attempt_partial_responses"] == 10
    assert info["failed_input"]["decision"] in info["unanswered_decisions"]
    assert info["result"]["tokens"] is None


@pytest.mark.parametrize("mutation", ["wrong_parent", "counts", "other_failed", "duplicate", "seed", "lost_usage"])
def test_parent_record_drift_is_rejected(parent_info, mutation):
    old = copy.deepcopy(parent_info)
    m, r = old["manifest"], old["result"]
    if mutation == "wrong_parent":
        m["experiment_id"] = "EX-083"
    elif mutation == "counts":
        r["completed"] = 24
    elif mutation == "other_failed":
        r["outcomes"][0]["completed"] = False
    elif mutation == "duplicate":
        r["outcomes"][-1] = copy.deepcopy(r["outcomes"][0])
    elif mutation == "seed":
        r["outcomes"][-1]["battle_seed"] = "1,2,3,4"
    elif mutation == "lost_usage":
        r["tokens"] = r["received_usage"]
    with pytest.raises(ValueError):
        c.validate_parent_records(m, r, c.read_json(study.LIVE / "final-audit.json"), study.load_baseline())


def test_parent_corruption_and_resealed_parent_are_rejected(tmp_path, monkeypatch):
    source = tmp_path / "parent"
    source.mkdir()
    item = source / "history.json"
    item.write_text('{"attempts":24}')
    study.seal(source)
    pinned = study.file_hash(source / "checksums.sha256")
    monkeypatch.setattr(c, "PARENT_SEAL", pinned)
    item.write_text('{"attempts":25}')
    with pytest.raises(ValueError, match="seal mismatch"):
        c.validate_parent(source)
    study.seal(source)
    with pytest.raises(ValueError, match="approved.*seal"):
        c.validate_parent(source)


def test_unsealed_extra_attempt_is_rejected(tmp_path):
    (tmp_path / "original").write_text("keep")
    study.seal(tmp_path)
    (tmp_path / "battle-25").mkdir()
    (tmp_path / "battle-25/outcome.json").write_text("{}")
    with pytest.raises(ValueError, match="unsealed"):
        c.strict_seal(tmp_path)


def test_attempt_plan_has_32_slots_and_only_one_second_attempt(parent_info):
    plan = c.attempt_plan(parent_info)
    assert len(plan) == 32 and sum(len(row["attempts"]) for row in plan) == 33
    assert [row["slot_id"] for row in plan if len(row["attempts"]) == 2] == [c.RETRY_SLOT]
    assert [row["slot"] for row in plan if not row["inherited"]] == list(range(24, 33))
    c.validate_manifest(manifest(parent_info))


@pytest.mark.parametrize("mutation", ["completed", "third_attempt", "other_retry", "order", "parent", "runtime"])
def test_manifest_cannot_admit_extra_or_completed_games(parent_info, mutation):
    value = manifest(parent_info)
    if mutation == "completed":
        value["collection_schedule"].insert(0, value["schedule"][0])
    elif mutation == "third_attempt":
        value["attempt_plan"][23]["attempts"].append(dict(experiment="EX-083", attempt=3, status="planned"))
    elif mutation == "other_retry":
        value["continuation_policy"]["retry_slot"] = value["schedule"][0]["slot_id"]
    elif mutation == "order":
        value["collection_schedule"].reverse()
    elif mutation == "parent":
        value["parent"]["seal_sha256"] = "changed"
    else:
        value["runtime"]["allocator_bytes_per_gpu"] += 1
    with pytest.raises(ValueError):
        c.validate_manifest(value)


def test_gate_identity_requires_replay_and_memory(parent_info, monkeypatch):
    monkeypatch.setattr(study, "prepare_manifest", lambda *_args, **_kwargs: copy.deepcopy(parent_info["manifest"]))
    gates = dict(replay_passed=True, memory_passed=True, parent_seal_sha256=c.PARENT_SEAL)
    value = c.prepare_manifest(parent_info, IDENTITY, gates, endpoint=battle.ENDPOINT)
    assert value["experiment_id"] == "EX-083"
    assert value["limits"]["total_battle_attempts"] == 33
    for key in gates:
        with pytest.raises(ValueError):
            c.prepare_manifest(parent_info, IDENTITY, dict(gates, **{key: False}), endpoint=battle.ENDPOINT)


def test_combined_success_is_32_unique_games_but_33_attempts(parent_info):
    new = segment(parent_info)
    combined = c.combine(parent_info, new)
    assert combined["passed"] and combined["completed"] == combined["attempted"] == 32
    assert combined["completed_pairs"] == 16 and combined["total_battle_attempts"] == 33
    assert combined["failed"] == 0 and combined["all_failed_attempts"] == 1
    assert combined["tokens"] is None and combined["usage_unknown_requests"] == 1
    assert combined["received_usage"] == parent_info["result"]["received_usage"]
    assert combined["outcomes"][:23] == parent_info["inherited_outcomes"]
    assert combined["segments"]["EX-082_2GPU"] == parent_info["result"]
    assert combined["segments"]["EX-083_4GPU"] == new
    assert combined["latency_seconds"] is None
    assert combined["original_failure"] == parent_info["failed_attempt"]
    history = c.actual_attempts(parent_info, new)
    assert history["actual_battle_attempts"] == 33
    assert [x["status"] for x in history["slots"][23]["attempts"]] == ["failed", "valid"]


def test_new_failure_uses_actual_denominators_and_no_imputed_loss(parent_info):
    combined = c.combine(parent_info, segment(parent_info, 2, failed="GPU resource exceeded"))
    assert not combined["passed"]
    assert (combined["attempted"], combined["completed"], combined["failed"], combined["unattempted"]) == (25, 24, 1, 7)
    assert combined["total_battle_attempts"] == 26
    assert combined["actual_losses"] == parent_info["result"]["actual_losses"]
    assert combined["all_failed_attempts"] == 2
    before = c.combine(parent_info, segment(parent_info, 0))
    assert (before["attempted"], before["completed"], before["failed"], before["unattempted"]) == (24, 23, 1, 8)
    assert before["total_battle_attempts"] == 24


def test_ex058_comparison_scores_unique_slots_and_common_pairs(parent_info):
    baseline = study.load_baseline()
    previous = c.read_json(study.BASELINE / "result.json")
    completed = c.combine(parent_info, segment(parent_info))
    result = study.compare_data((baseline, previous, []), (manifest(parent_info), completed, []))
    assert result["after_experiment"] == "EX-083"
    assert result["comparable_games"] == 32 and result["common_completed_pairs"] == 16
    # The preserved failure is a 33rd attempt, not a second scored slot or loss.
    assert result["mean_pair_score_delta"] == pytest.approx((12 + 9 - 11) / 32)
    partial = c.combine(parent_info, segment(parent_info, 1, failed="resource limit"))
    result = study.compare_data((baseline, previous, []), (manifest(parent_info), partial, []))
    assert result["comparable_games"] == 23 and result["common_completed_pairs"] == 9


@pytest.mark.parametrize("mutation", ["completed", "duplicate", "third_retry", "identity", "seed"])
def test_result_cannot_hide_extra_attempt_or_seed_change(parent_info, mutation):
    new = segment(parent_info)
    outcomes = new["outcomes"]
    if mutation == "completed":
        outcomes[0] = copy.deepcopy(parent_info["inherited_outcomes"][0])
    elif mutation == "duplicate":
        outcomes[1] = copy.deepcopy(outcomes[0])
    elif mutation == "third_retry":
        outcomes.append(copy.deepcopy(outcomes[0]))
    elif mutation == "identity":
        outcomes[0]["username"] = parent_info["failed_attempt"]["username"]
    else:
        outcomes[0]["actor_seeds"][0] += 1
    with pytest.raises(ValueError):
        c.combine(parent_info, new)


def test_continue_existing_output_is_rejected_before_parent_read(tmp_path, monkeypatch):
    sentinel = tmp_path / "result.json"
    sentinel.write_text("original")
    monkeypatch.setattr(c, "validate_parent", lambda *_args: pytest.fail("parent accessed before overwrite refusal"))
    with pytest.raises(FileExistsError, match="cannot resume"):
        asyncio.run(c.run(tmp_path, parent=study.LIVE, expected_identity=IDENTITY, gate_receipt={}))
    assert sentinel.read_text() == "original"


def test_collection_artifacts_reject_unreported_extra_trial(parent_info, tmp_path):
    new = segment(parent_info, 1, failed="stopped before request")
    attempt = tmp_path / "battle-24"
    attempt.mkdir()
    study.write_json(attempt / "outcome.json", new["outcomes"][0])
    c.validate_collection_artifacts(tmp_path, parent_info, new)
    (tmp_path / "battle-24-retry").mkdir()
    with pytest.raises(ValueError, match="unreported or extra"):
        c.validate_collection_artifacts(tmp_path, parent_info, new)


@pytest.mark.parametrize("fail_after", [None, 0, "cancel", "interrupt"])
def test_new_runner_admits_only_nine_original_slots_and_stops_on_failure(parent_info, tmp_path, monkeypatch, fail_after):
    from integration.pokechamp import cli, parallel_server, benchmark
    # Complete imports before replacing Popen; mcp annotates Popen[bytes] at import.
    from poke_env.ps_client.account_configuration import AccountConfiguration
    monkeypatch.chdir(battle.ROOT / "pokechamp")
    monkeypatch.setattr(study, "verify_live_identity", lambda *_args: None)
    monkeypatch.setattr(study, "snapshot_sources", lambda *_args: None)
    monkeypatch.setattr(audit, "audit", lambda *_args, **_kwargs: dict(passed=True, errors=[]))
    admitted, closed = [], []

    class Session:
        def __init__(self, directory, **kwargs):
            assert kwargs["request_namespace"] == "ex083"
            self.directory, self.records = directory, []
            self.calls, self.started, self.monotonic_started = 0, None, None
            self.failure_event = asyncio.Event()
            (directory / "events.jsonl").touch()

        def record(self, event):
            self.records.append(event)

        def fail(self, _error):
            self.failure_event.set()

        async def health(self):
            return {}

        async def close(self):
            closed.append("session")

        async def wait_decisions(self):
            return

    class Process:
        pid = 1
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, _timeout):
            self.returncode = 0

    class Server:
        def __init__(self, *_args):
            self.created = False
            self.process = Process()

        def start(self):
            self.created = True

        def close(self):
            self.created = False
            self.process.returncode = 0
            closed.append("showdown")

    class Player:
        official = None

        def __init__(self, **_kwargs):
            pass

    async def play(_player, role, _names, attempt, **_kwargs):
        request = c.read_json(attempt / "request.json")
        admitted.append(request["slot"])
        if fail_after == "cancel":
            raise asyncio.CancelledError("operator cancelled")
        if fail_after == "interrupt":
            raise KeyboardInterrupt("owned controller received SIGTERM")
        if isinstance(fail_after, int) and len(admitted) > fail_after:
            raise RuntimeError("owned resource limit")
        other = "p2" if role == "p1" else "p1"
        study.write_json(attempt / f"{other}.result.json", dict(completed=True,
            outcome="player_lost", turns=1, actor=other,
            python_random_seed=request["slot"]["actor_seeds"][int(other[-1]) - 1]))
        return dict(completed=True, outcome="player_won", turns=1, actor=role)

    async def close_players(_players):
        closed.append("player")

    monkeypatch.setattr(battle, "Session", Session)
    monkeypatch.setattr(battle, "player_class", lambda: Player)
    monkeypatch.setattr(battle, "play_owned", play)
    monkeypatch.setattr(parallel_server, "BattleServer", Server)
    monkeypatch.setattr(battle.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(benchmark, "terminate", lambda process: setattr(process, "returncode", 0))
    monkeypatch.setattr(cli, "_close_players", close_players)
    target = tmp_path / "new"
    result = asyncio.run(battle._run_frozen(target, manifest=manifest(parent_info),
        expected_identity=IDENTITY, gate_receipt={}, endpoint=battle.ENDPOINT))
    expected = 9 if fail_after is None else 1
    assert admitted == parent_info["continuation_schedule"][:expected]
    assert [o["slot"] for o in result["outcomes"]] == list(range(24, 24 + expected))
    assert result["attempted"] == expected and result["passed"] == (fail_after is None)
    assert closed.count("showdown") == expected and closed.count("session") == 1
    assert all(o["server_cleaned"] and o["opponent_cleaned"] for o in result["outcomes"])
    assert c.read_json(target / "result.json") == result
    assert c.read_json(target / "final-audit.json")["passed"]
    study.verify_seal(target)
    if fail_after in ("cancel", "interrupt"):
        assert result["error"]["type"] == ("CancelledError" if fail_after == "cancel" else "KeyboardInterrupt")
        assert result["completed"] == 0 and result["unattempted"] == 8


def test_portable_export_retains_original_failed_response_and_links(parent_info, tmp_path):
    # Small event streams retain actual parent outcomes, and test relocation with
    # the real renderer without copying 140 MB or invoking a battle/model.
    info = copy.deepcopy(parent_info)
    parent = tmp_path / "parent"
    parent.mkdir()
    study.write_json(parent / "manifest.json", dict(experiment_id="EX-082"))
    study.write_json(parent / "result.json", info["result"])
    failed = info["failed_attempt"]["username"]
    old_events = [dict(type="input", decision=failed + "-1",
        payload=dict(state=dict(turn=7, decision_kind="turn")), boundary={}, observation_identity={}),
        dict(type="http_request", decision=failed + "-1", body=dict(model=battle.MODEL, original=True)),
        dict(type="response", decision=failed + "-1", body=dict(original_partial=True), elapsed_seconds=1)]
    (parent / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in old_events))
    study.seal(parent)
    info["parent"] = str(parent)
    source = tmp_path / "collection"
    source.mkdir()
    new = segment(info)
    study.write_json(source / "manifest.json", manifest(info))
    study.write_json(source / "result.json", new)
    (source / "events.jsonl").write_text("")
    study.seal(source)
    combined = c.combine(info, new)
    output = tmp_path / "export"
    result = c.export(source, info, combined, output=output, derived=tmp_path / "derived", compared={})
    assert result["passed"]
    moved = tmp_path / "moved"
    shutil.move(output, moved)
    assert 'href="parent-ex082/battle-24/index.html"' in (moved / "index.html").read_text()
    data = c.read_json(moved / "parent-ex082/battle-24/decisions.json")
    assert data["outcome"] == info["failed_attempt"]
    assert data["decisions"][0]["response"] == dict(original_partial=True)
    assert c.read_json(moved / "attempts.json")["actual_battle_attempts"] == 33
    study.verify_seal(moved)
    study.verify_viewer(tmp_path / "derived", moved)
    study.verify_viewer(parent, moved / "parent-ex082")
