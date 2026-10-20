import asyncio
import copy
import json
from pathlib import Path
import threading

import pytest

from integration.jev_planner.core import (
    DecisionContext, DecisionConsistencyError, PlanOutputError, PlanningController,
    StaleDecisionError, build_planner_messages, parse_plan,
)
from integration.jev_planner.planner import MockPlanner
from integration.pokechamp.jev_battle import UnusableChoice

ROOT = Path(__file__).resolve().parents[2]
PROMPT = (ROOT / "pokechamp/prompts/jev-choice-v6.txt").read_text()


def config(policy="events_or_periodic", interval=3):
    return dict(trigger=dict(policy=policy, interval_turns=interval,
                             events=["faint", "tera", "forced_switch"]),
                prompts={name: {"text": (Path(__file__).resolve().parents[1] / "prompts" / filename).read_text()}
                         for name, filename in (("planner", "strategy-compact.txt"), ("executor", "executor-guidance.txt"))})


class Timeline:
    def __init__(self, battle="battle-unit", actor="p1"):
        self.lines = ["|init|battle"]
        self.turn = 0
        self.battle, self.actor = battle, actor

    def context(self, rqid, turn, *, single=False, events=(), kind="turn"):
        if turn > self.turn:
            self.lines.append(f"|turn|{turn}")
            self.turn = turn
        self.lines.extend(events)
        self.lines.append("|request|" + json.dumps({"rqid": rqid, "side": {"id": self.actor}}))
        keys = ["move_2"] if single else ["move_2", "move_1"]
        payload = dict(state=dict(version="jev-choice-v6", turn=turn, actor=self.actor,
                                  request_id=rqid, decision_kind=kind),
                       questions={"action": {"type": "choice", "instructions": PROMPT,
                                              "criteria": {key: {"kind": "move"} for key in keys}}})
        return DecisionContext(self.battle, self.actor, rqid, payload,
                               {key: "/choose " + key.replace("_", " ") for key in keys},
                               [dict(event_seq=1, protocol="\n".join(self.lines))],
                               dict(protocol_event_seq=1, line_index=len(self.lines) - 1))


class Executor:
    def __init__(self):
        self.calls = []

    async def __call__(self, payload, *, decision):
        self.calls.append((copy.deepcopy(payload), decision))
        return {"answers": {"action": {"type": "choice", "choice": next(iter(payload["questions"]["action"]["criteria"]))}}}


@pytest.mark.parametrize("policy,expected", [
    ("off", []), ("initial_only", [1]), ("every_decision", [1, 3, 5, 6]),
    ("periodic", [1, 5]), ("events", [1, 3]), ("events_or_periodic", [1, 3, 6]),
])
def test_policies_and_single_candidate_event_retention(policy, expected):
    async def run():
        timeline, planner, executor, records = Timeline(), MockPlanner(), Executor(), []
        controller = PlanningController(config(policy), planner, executor, records.append)
        for rqid, turn, single, events, kind in [
            (1, 1, False, (), "turn"),
            (2, 2, True, ("|faint|p1a: Test", "|-terastallize|p2a: Opp|Water"), "forced_switch"),
            (3, 3, False, (), "turn"), (4, 5, False, (), "turn"), (5, 6, False, (), "turn"),
        ]:
            result = await controller.decide(timeline.context(rqid, turn, single=single, events=events, kind=kind))
            assert result.automatic is single
        assert [row["turn"] for row in records if row["type"] == "planner_request"] == expected
        assert len(executor.calls) == 4
        if policy == "events_or_periodic":
            row = next(r for r in records if r["type"] == "planner_decision" and r["turn"] == 3)
            assert row["reasons"] == ["event:faint", "event:tera", "event:forced_switch"]
            assert len(row["pending_events"]) == 3
            assert next(r for r in records if r["type"] == "planner_decision" and r["turn"] == 6)["reasons"] == ["periodic"]
    asyncio.run(run())


def test_initial_waits_for_multiple_candidates_and_first_plan_has_pending_events():
    async def run():
        timeline, planner, executor, records = Timeline(), MockPlanner(), Executor(), []
        controller = PlanningController(config(), planner, executor, records.append)
        first = await controller.decide(timeline.context(1, 0, single=True, kind="forced_switch"))
        assert first.plan is None and not planner.calls and not executor.calls
        second = await controller.decide(timeline.context(2, 0))
        assert second.plan["generated_turn"] == 0
        assert [r for r in records if r["type"] == "planner_decision"][-1]["reasons"] == ["initial", "event:forced_switch"]
    asyncio.run(run())


def test_overlapping_periodic_and_event_reasons_are_one_call():
    async def run():
        timeline, planner, executor, records = Timeline(), MockPlanner(), Executor(), []
        controller = PlanningController(config(), planner, executor, records.append)
        await controller.decide(timeline.context(1, 1))
        await controller.decide(timeline.context(2, 4, events=("|faint|p2a: Opp",)))
        assert len(planner.calls) == 2
        assert [r for r in records if r["type"] == "planner_decision"][-1]["reasons"] == ["periodic", "event:faint"]
    asyncio.run(run())


def test_duplicate_request_singleflight_and_send_reservation():
    async def run():
        timeline, executor, records = Timeline(), Executor(), []
        entered, release = asyncio.Event(), asyncio.Event()
        class Delayed(MockPlanner):
            async def plan(self, *args, **kwargs):
                entered.set()
                await release.wait()
                return await super().plan(*args, **kwargs)
        planner = Delayed()
        controller = PlanningController(config(), planner, executor, records.append)
        context = timeline.context(1, 1)
        first = asyncio.create_task(controller.decide(context))
        await entered.wait()
        second = asyncio.create_task(controller.decide(context))
        release.set()
        results = await asyncio.gather(first, second)
        assert [r.reused for r in results] == [False, True]
        assert len(planner.calls) == len(executor.calls) == 1
        assert not controller.was_sent(context)
        assert controller.mark_sent(context) and not controller.mark_sent(context)
        assert controller.was_sent(context)
        duplicate = await controller.decide(context)
        assert duplicate.reused
        duplicate.payload["state"]["turn"] = 100
        assert (await controller.decide(context)).payload["state"]["turn"] == 1
        changed = context.payload
        changed["state"]["new"] = True
        conflicting = DecisionContext(context.battle, context.actor, context.rqid, changed,
                                      context.commands, context.prefix, context.boundary)
        with pytest.raises(DecisionConsistencyError, match="same rqid"):
            await controller.decide(conflicting)
    asyncio.run(run())


def test_same_turn_different_requests_and_battle_actor_isolation():
    async def run():
        planner, executor, records = MockPlanner(), Executor(), []
        controller = PlanningController(config(), planner, executor, records.append)
        first = Timeline()
        await controller.decide(first.context(1, 1))
        await controller.decide(first.context(2, 1, kind="forced_switch"))
        await controller.decide(first.context(3, 1))
        assert len(planner.calls) == 2
        other = await controller.decide(Timeline(actor="p2").context(1, 1))
        battle = await controller.decide(Timeline(battle="battle-other").context(1, 1))
        assert other.plan["age_turns"] == battle.plan["age_turns"] == 0
        assert len(planner.calls) == 4
        controller.end_battle("battle-unit", "p1")
        assert ("battle-unit", "p1") not in controller._states
        with pytest.raises(DecisionConsistencyError, match="ended"):
            await controller.decide(first.context(4, 2))
    asyncio.run(run())


def test_private_request_retransmit_reuses_but_changed_public_evidence_is_inconsistent():
    async def run():
        context, planner, executor = Timeline().context(1, 1), MockPlanner(), Executor()
        controller = PlanningController(config(), planner, executor, lambda _: None)
        await controller.decide(context)
        prefix = context.prefix
        prefix.append(dict(event_seq=2, protocol='|request|{"rqid":1,"side":{"id":"p1"}}'))
        repeated = DecisionContext(context.battle, context.actor, 1, context.payload,
                                   context.commands, prefix, dict(protocol_event_seq=2, line_index=0))
        assert (await controller.decide(repeated)).reused
        assert len(planner.calls) == len(executor.calls) == 1
        prefix[-1]["protocol"] = '|-ability|p2a: Opp|Levitate\n' + prefix[-1]["protocol"]
        changed = DecisionContext(context.battle, context.actor, 1, context.payload,
                                  context.commands, prefix, dict(protocol_event_seq=2, line_index=1))
        with pytest.raises(DecisionConsistencyError, match="same rqid"):
            await controller.decide(changed)
    asyncio.run(run())


def test_owned_server_room_reuse_keeps_same_actor_games_separate():
    async def run():
        physical = Timeline(battle="battle-gen9ou-1").context(1, 1)
        prefix = physical.prefix
        prefix[0]["protocol"] = ">battle-gen9ou-1\n" + prefix[0]["protocol"]
        boundary = {**physical.boundary, "line_index": physical.boundary["line_index"] + 1}
        planner, executor, records = MockPlanner(), Executor(), []
        controller = PlanningController(config(), planner, executor, records.append)
        results = []
        for slot in ("slot-a", "slot-b"):
            context = DecisionContext(slot + ":" + physical.battle, "p1", 1,
                physical.payload, physical.commands, prefix, boundary,
                protocol_battle=physical.battle)
            results.append(await controller.decide(context))
            assert controller.mark_sent(context)
            controller.end_battle(context.battle, context.actor)
            await controller.wait_pending(context.battle, context.actor)
        assert len(planner.calls) == len(executor.calls) == 2
        assert results[0].decision_id != results[1].decision_id
        selections = [row for row in records if row["type"] == "selection"]
        assert [row["battle"] for row in selections] == ["slot-a:battle-gen9ou-1", "slot-b:battle-gen9ou-1"]
        assert all(row["protocol_battle"] == "battle-gen9ou-1" for row in selections)
        with pytest.raises(DecisionConsistencyError, match="foreign battle room"):
            DecisionContext("slot-c:battle-gen9ou-1", "p1", 1, physical.payload,
                physical.commands, prefix, boundary, protocol_battle="battle-wrong")
    asyncio.run(run())


def test_off_preserves_exact_input_and_needs_no_planner_or_prompt():
    async def run():
        context, executor = Timeline().context(1, 1), Executor()
        controller = PlanningController({"trigger": {"policy": "off"}}, None, executor, lambda _: None)
        result = await controller.decide(context)
        assert json.dumps(result.payload, ensure_ascii=False) == json.dumps(context.payload, ensure_ascii=False)
        assert executor.calls[0][0] == context.payload and result.plan is None
        assert list(result.payload["questions"]["action"]["criteria"]) == list(context.commands)
    asyncio.run(run())


def test_context_freezes_observation_and_prefix_and_omits_private_and_future_rows():
    context = Timeline().context(1, 1, events=("|c|person|private chat", "|move|p2a: Opp|Surf|p1a: Test"))
    payload, prefix = context.payload, context.prefix
    payload["state"]["turn"] = 999
    prefix[-1]["protocol"] += "\n|turn|2\n|faint|future"
    assert context.payload["state"]["turn"] == 1
    messages = build_planner_messages(context, config())
    data = json.loads(messages[1]["content"])
    public = json.dumps(data["public_events_since_plan"])
    assert "private chat" not in public and "request" not in public and "future" not in public
    assert "Surf" in public
    assert messages[0]["content"].endswith(PROMPT.split("\n\n", 1)[1])
    assert "Choose exactly one supplied legal candidate" not in messages[0]["content"]


def test_snapshot_does_not_change_when_logs_arrive_during_planner_wait():
    async def run():
        timeline, executor = Timeline(), Executor()
        context = timeline.context(1, 1)
        class Appending(MockPlanner):
            async def plan(self, *args, **kwargs):
                timeline.lines.extend(["|turn|2", "|faint|future"])
                return await super().plan(*args, **kwargs)
        planner = Appending()
        result = await PlanningController(config(), planner, executor, lambda _: None).decide(context)
        assert result.payload["state"]["turn"] == 1
        assert "future" not in planner.calls[0]["messages"][1]["content"]
        assert "|faint|future" not in json.dumps(executor.calls)
    asyncio.run(run())


def test_only_public_rows_after_previous_success_are_in_next_plan():
    async def run():
        timeline, planner, executor = Timeline(), MockPlanner(), Executor()
        controller = PlanningController(config("every_decision"), planner, executor, lambda _: None)
        await controller.decide(timeline.context(1, 1, events=("|move|old",)))
        await controller.decide(timeline.context(2, 2, single=True, events=("|move|new",)))
        await controller.decide(timeline.context(3, 3))
        body = json.loads(planner.calls[-1]["messages"][1]["content"])
        rows = json.dumps(body["public_events_since_plan"])
        assert "old" not in rows and "new" in rows
        assert body["previous_plan"]["generated_turn"] == 1
    asyncio.run(run())


def test_stale_planner_response_does_not_reach_executor():
    async def run():
        planner, executor = MockPlanner(), Executor()
        checks = []
        async def check():
            checks.append(True)
            return len(checks) < 2
        controller = PlanningController(config(), planner, executor, lambda _: None)
        with pytest.raises(StaleDecisionError):
            await controller.decide(Timeline().context(1, 1), ensure_current=check)
        assert len(planner.calls) == 1 and not executor.calls
        assert controller._states[("battle-unit", "p1")].plan is None
    asyncio.run(run())


@pytest.mark.parametrize("bad", ["", "not json", "{}", '{"objective":"a","objective":"b"}', '{"x":NaN}'])
def test_unusable_plan_fails_battle_without_fallback_or_requery(bad):
    async def run():
        planner, executor, records = MockPlanner(bad_response=bad), Executor(), []
        controller = PlanningController(config(), planner, executor, records.append)
        context = Timeline().context(1, 1)
        for _ in range(2):
            with pytest.raises(PlanOutputError) as error:
                await controller.decide(context)
            assert error.value.scope == "battle"
        assert len(planner.calls) == 1 and not executor.calls
        assert [r for r in records if r["type"] == "planner_response"][0]["content"] == bad
    asyncio.run(run())


def test_valid_poor_strategy_and_auxiliary_bad_scores_are_not_execution_gates():
    async def run():
        class Poor(MockPlanner):
            async def plan(self, *args, **kwargs):
                result = await super().plan(*args, **kwargs)
                result["plan"]["objective"] = "Deliberately lose every Pokemon."
                result["content"] = json.dumps(result["plan"])
                return result
        records = []
        result = await PlanningController(config(), Poor(), Executor(), records.append).decide(Timeline().context(1, 1))
        assert result.choice == "move_2"
        assert next(r for r in records if r["type"] == "judgment_diagnostics")["diagnostics"]
        assert "reasoning" not in result.payload["state"]["planner_advice"]
    asyncio.run(run())


def test_illegal_executor_choice_and_token_limit_are_not_retried():
    async def bad_executor(payload, *, decision):
        return {"answers": {"action": {"type": "choice", "choice": "missing"}}}
    async def run():
        with pytest.raises(UnusableChoice):
            await PlanningController(config(), MockPlanner(), bad_executor, lambda _: None).decide(Timeline().context(1, 1))
        executor = Executor()
        def guard(payload):
            assert "planner_advice" in payload["state"]
            raise ValueError("full input exceeds 32768 tokens")
        with pytest.raises(ValueError, match="32768"):
            await PlanningController(config(), MockPlanner(), executor, lambda _: None, token_guard=guard).decide(Timeline().context(1, 1))
        assert not executor.calls
    asyncio.run(run())


def test_valid_json_truncation_is_still_rejected():
    result = asyncio.run(MockPlanner().plan([], request_id="test"))
    with pytest.raises(PlanOutputError, match="truncated"):
        parse_plan(result["content"], finish_reason="length")


def test_main_loop_battle_end_cancels_pending_actor_loop_decision():
    owner = asyncio.new_event_loop()
    owner.set_debug(True)  # A direct cross-thread Task.cancel raises in debug mode.
    thread = threading.Thread(target=owner.run_forever, daemon=True)
    thread.start()
    entered = threading.Event()
    class Waiting(MockPlanner):
        async def plan(self, *args, **kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                # Simulate a cancellation cleanup write on the actor loop.
                await asyncio.sleep(.01)
                entered.clear()
    async def run():
        executor = Executor()
        controller = PlanningController(config(), Waiting(), executor, lambda _: None)
        future = asyncio.run_coroutine_threadsafe(controller.decide(Timeline().context(1, 1)), owner)
        assert await asyncio.to_thread(entered.wait, 2)
        controller.end_battle("battle-unit", "p1")
        await controller.wait_pending("battle-unit", "p1")
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wrap_future(future)
        assert not executor.calls and not controller._tasks and not controller._pending_cleanup
        assert not entered.is_set()
    try:
        asyncio.run(run())
    finally:
        owner.call_soon_threadsafe(owner.stop)
        thread.join(timeout=3)
        owner.close()
