"""CPU boundary checks for planner integration and per-battle failure isolation."""
from __future__ import annotations

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from integration.jev_planner import battle
from integration.jev_planner.core import PlanOutputError
from integration.jev_planner.planner import MockPlanner
from integration.jev_planner.runtime import MockExecutor
from integration.pokechamp import jev_v6


def configuration(policy="off", games=3):
    return dict(executor=dict(model="jev9b", input_version="jev-choice-v6"),
        trigger=dict(policy=policy, interval_turns=3, events=["faint", "tera", "forced_switch"]),
        planner={}, prompts=dict(planner={"text": "Return a strategic plan."},
                                  executor={"text": "Current observations and legality take priority."}),
        evaluation=dict(kind="battle", showdown_port=8109,
            limits=dict(games=games, executor_calls=100, battle_seconds=30, total_seconds=90),
            schedule={"data": dict(teams={"a": {"showdown_team": "Pikachu\n- Thunderbolt"}},
                schedule=[dict(slot_id=f"test-{i}", paired_slot_id="pair", jev_actor="p1",
                    teams=["a", "a"], battle_seed="1,2,3,4", actor_seeds=[11, 12])
                    for i in range(games)])}))


def player_fixture(tmp_path, monkeypatch, *, policy="off", single=False, behavior=None):
    request = dict(rqid=1, side={"id": "p1"})
    prefix = [dict(event_seq=1, protocol=">fixture\n|init|battle\n|turn|1\n|request|" + json.dumps(request))]
    criteria = {"move_1": {"kind": "move", "move": {"power": 40}, "terastallize": False}}
    if not single:
        criteria["move_2"] = {"kind": "move", "move": {"power": 60}, "terastallize": False}
    commands = {key: "/choose " + key.replace("_", " ") for key in criteria}
    payload = dict(state=dict(version="jev-choice-v6", actor="p1", request_id=1, turn=1,
                              decision_kind="turn_action"),
                   questions={"action": dict(type="choice", criteria=criteria,
                                              instructions=jev_v6.PROMPT.read_text())})
    records, sent, evaluated = [], [], []
    session = battle.Session(tmp_path, config=configuration(policy), mode="mock",
        planner=MockPlanner(), executor=None, record=records.append)
    player = object.__new__(battle.player_class())
    player.session = session
    player.request, player.latest_rqid, player.expected_actor = request, 1, "p1"
    player.latest_request = copy.deepcopy(request)
    player.prefix, player.boundary = prefix, {"protocol_event_seq": 1, "line_index": 3}
    player.submitted_team, player.output_error = "fixture", None
    player.official = SimpleNamespace(snapshot=lambda *_args, **_kwargs: {}, identity={})
    async def send(*args):
        sent.append(args)
    player.ps_client = SimpleNamespace(username="fixture", send_message=send)
    async def evaluate(body, *, decision):
        evaluated.append(body)
        if behavior == "stale":
            player.latest_rqid = 2
        elif behavior == "cancelled":
            session.failure_event.set()
        elif behavior == "wait":
            player.latest_request["wait"] = True
        elif behavior == "received_change":
            player.latest_request["active"] = [{"moves": [{"id": "changed"}]}]
        return await MockExecutor()(body, decision=decision)
    session.executor = evaluate
    async def generate(*_args, **_kwargs):
        return copy.deepcopy(payload), dict(commands), {}, 0
    monkeypatch.setattr(jev_v6, "generate", generate)
    current = dict(commands)
    if behavior == "changed":
        current.pop(next(iter(current)))
    monkeypatch.setattr(battle.j, "make_input", lambda *_args, **_kwargs: ({}, current))
    return player, SimpleNamespace(in_team_preview=False, battle_tag="fixture"), records, sent, evaluated


@pytest.mark.parametrize("behavior", ["stale", "cancelled", "changed", "wait", "received_change"])
def test_stale_cancelled_or_changed_request_never_sends(tmp_path, monkeypatch, behavior):
    player, game, records, sent, _ = player_fixture(tmp_path, monkeypatch, behavior=behavior)
    with pytest.raises((ValueError, TimeoutError)):
        asyncio.run(player._handle_battle_request(game))
    assert not sent
    assert not any(row["type"] == "wire" for row in records)


@pytest.mark.parametrize("single", [False, True])
def test_duplicate_request_reuses_choice_and_single_candidate_calls_neither_model(
        tmp_path, monkeypatch, single):
    player, game, records, sent, evaluated = player_fixture(tmp_path, monkeypatch, single=single)
    async def twice():
        await player._handle_battle_request(game)
        await player._handle_battle_request(game)
    asyncio.run(twice())
    assert len(sent) == 1 and len(evaluated) == (0 if single else 1)
    assert len([r for r in records if r["type"] == "observation"]) == 1
    assert records[-1]["type"] == "wire_duplicate_skipped"
    assert not player.session.controller.planner.calls


def test_planner_output_error_is_not_a_shared_session_halt(tmp_path, monkeypatch):
    player, game, _, sent, evaluated = player_fixture(tmp_path, monkeypatch, policy="initial_only")
    player.session.controller.planner = MockPlanner(bad_response="not-json")
    asyncio.run(player._handle_battle_request(game))
    assert isinstance(player.output_error, PlanOutputError)
    assert not player.session.failure_event.is_set()
    assert not sent and not evaluated


def test_collection_continues_after_output_failure_then_halts_technical(tmp_path, monkeypatch):
    admitted = []
    async def run_match(session, row, _teams, _attempt, **_kwargs):
        admitted.append(row["slot_id"])
        if len(admitted) == 1:
            return dict(row, status="failed", completed=False, outcome="output_failure",
                        failure_scope="battle"), None
        return dict(row, status="failed", completed=False,
                    failure_scope="collection"), RuntimeError("owned peer failure")
    monkeypatch.setattr(battle, "run_match", run_match)
    result = asyncio.run(battle.run_condition(tmp_path, configuration(), mode="mock",
                                             planner=MockPlanner()))
    assert admitted == ["test-0", "test-1"]
    assert (result["attempted"], result["failed"], result["unattempted"]) == (2, 2, 1)
    assert result["outcomes"][-1]["status"] == "unattempted"
    assert result["error"]["type"] == "RuntimeError"
    assert result["efficacy_evidence"] is False
    with pytest.raises(FileExistsError):
        asyncio.run(battle.run_condition(tmp_path, configuration(), mode="mock", planner=MockPlanner()))


def test_global_executor_budget_callback_counts_only_inferences(tmp_path, monkeypatch):
    player, game, _, sent, evaluated = player_fixture(tmp_path, monkeypatch)
    reserved = []
    player.session.before_executor = lambda *, decision: reserved.append(decision)
    async def twice():
        await player._handle_battle_request(game)
        await player._handle_battle_request(game)
    asyncio.run(twice())
    assert len(reserved) == len(evaluated) == len(sent) == 1


def test_schedule_uint16_and_uint32_bounds():
    config = configuration(games=1)
    row = config["evaluation"]["schedule"]["data"]["schedule"][0]
    row["battle_seed"] = [1, 2, 3, 4]
    assert battle.validate_schedule(config)[0][0]["battle_seed"] == "1,2,3,4"
    row["actor_seeds"] = [0, 2**32]
    with pytest.raises(ValueError, match="uint32"):
        battle.validate_schedule(config)


def test_declared_team_rejection_cannot_load_a_substitute(tmp_path):
    session = battle.Session(tmp_path, config=configuration(), mode="mock",
                             planner=MockPlanner(), executor=MockExecutor())
    original = object()
    player = SimpleNamespace(ps_client=SimpleNamespace(_handle_team_rejection=original),
                             username="fixture")
    battle.forbid_team_substitution(player, session)
    asyncio.run(player.ps_client._handle_team_rejection("Your team was rejected"))
    assert isinstance(player.benchmark_environment_error, ValueError)
    assert session.failure_event.is_set()
    assert session.records[-1]["type"] == "team_rejection"


def test_external_recorder_failure_halts_but_can_preserve_internal_error(tmp_path):
    def fail_record(_event):
        raise OSError("fixture evidence failure")
    session = battle.Session(tmp_path, config=configuration(), mode="mock", planner=MockPlanner(),
                             executor=MockExecutor(), record=fail_record)
    with pytest.raises(OSError, match="evidence"):
        session.record({"type": "protocol", "sequence": 1, "protocol": "|turn|1"})
    assert session.failure_event.is_set()
    session.record({"type": "failure", "error": "preserved after callback failure"})
    assert session.records[-1]["type"] == "failure"


def test_admitted_battle_stays_attempted_if_its_artifact_write_raises(tmp_path, monkeypatch):
    async def run_match(*_args, **_kwargs):
        raise OSError("fixture artifact failure after admission")
    monkeypatch.setattr(battle, "run_match", run_match)
    result = asyncio.run(battle.run_condition(tmp_path, configuration(), mode="mock",
                                             planner=MockPlanner()))
    assert result["attempted"] == result["failed"] == 1
    assert result["unattempted"] == 2
    assert result["outcomes"][0]["error"]["type"] == "OSError"


def test_same_rqid_cancellation_arriving_during_last_revalidation_never_sends(tmp_path, monkeypatch):
    player, game, _, sent, evaluated = player_fixture(tmp_path, monkeypatch)
    calls = []
    def snapshot(*_args, **_kwargs):
        calls.append(None)
        if len(calls) == 4:
            player.latest_request = dict(player.latest_request, wait=True)
        return {}
    player.official.snapshot = snapshot
    with pytest.raises(ValueError, match="during revalidation"):
        asyncio.run(player._handle_battle_request(game))
    assert len(calls) == 4 and len(evaluated) == 1 and not sent
