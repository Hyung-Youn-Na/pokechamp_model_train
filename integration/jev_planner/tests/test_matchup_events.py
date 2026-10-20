"""EX-101 공개 사건 호출 계약을 실제 모델 없이 검증한다."""
import asyncio
import json

import pytest

from integration.jev_planner.config import DEFAULT_TRIGGER, _trigger
from integration.jev_planner.core import DecisionContext, PlanningController
from integration.jev_planner.events import public_events, trigger_events
from integration.jev_planner.planner import MockPlanner
from integration.jev_planner.tests.test_core import Executor, Timeline, config


EVENTS = ["faint", "tera", "forced_switch", "active_change", "form_change"]


def setup():
    settings = config("events")
    settings["trigger"]["events"] = EVENTS[:]
    planner, executor, records = MockPlanner(), Executor(), []
    return PlanningController(settings, planner, executor, records.append), planner, executor, records


def decisions(records):
    return [row for row in records if row["type"] == "planner_decision"]


@pytest.mark.parametrize("side", ["p1", "p2"])
@pytest.mark.parametrize("command,kind,suffix", [
    ("switch", "active_change", "|Pikachu, L50|100/100"),
    ("drag", "active_change", "|Pikachu, L50|100/100"),
    ("replace", "active_change", "|Zoroark, L50|100/100"),
    ("detailschange", "form_change", "|Palafin-Hero, L50"),
    ("-formechange", "form_change", "|Palafin-Hero"),
    ("-transform", "form_change", "|p2a: Target"),
    ("faint", "faint", ""),
    ("-terastallize", "tera", "|Water"),
])
def test_each_side_public_change_calls_at_next_decision(side, command, kind, suffix):
    async def run():
        controller, planner, executor, records = setup()
        timeline = Timeline()
        await controller.decide(timeline.context(1, 0, kind="lead"))
        await controller.decide(timeline.context(2, 1, events=(f"|{command}|{side}a: A{suffix}",)))
        assert len(planner.calls) == len(executor.calls) == 2
        assert decisions(records)[-1]["reasons"] == ["event:" + kind]
        assert len(decisions(records)[-1]["pending_events"]) == 1
    asyncio.run(run())


@pytest.mark.parametrize("command", ["detailschange", "-formechange", "-transform"])
def test_bench_form_changes_do_not_call(command):
    async def run():
        controller, planner, _, records = setup()
        timeline = Timeline()
        await controller.decide(timeline.context(1, 1))
        await controller.decide(timeline.context(2, 2, events=(
            f"|{command}|p1: Bench|Palafin-Hero", f"|{command}|p2: Bench|Palafin-Hero")))
        assert len(planner.calls) == 1
        assert decisions(records)[-1]["reasons"] == ["plan_reuse"]
        assert decisions(records)[-1]["pending_events"] == []
    asyncio.run(run())


def test_initial_lead_then_first_entrants_and_round_trip_each_preserve_rows():
    async def run():
        controller, planner, _, records = setup()
        timeline = Timeline()
        await controller.decide(timeline.context(1, 0, kind="lead"))
        await controller.decide(timeline.context(2, 1, events=(
            "|switch|p1a: A|Pikachu|100/100", "|switch|p2a: B|Eevee|100/100")))
        await controller.decide(timeline.context(3, 1, events=(
            "|switch|p1a: C|Ditto|100/100", "|switch|p1a: A|Pikachu|100/100")))
        assert len(planner.calls) == 3
        assert [row["reasons"] for row in decisions(records)] == [
            ["initial"], ["event:active_change"], ["event:active_change"]]
        assert [len(row["pending_events"]) for row in decisions(records)] == [0, 2, 2]
    asyncio.run(run())


def test_single_candidate_defers_all_reasons_without_either_model_call():
    async def run():
        controller, planner, executor, records = setup()
        timeline = Timeline()
        await controller.decide(timeline.context(1, 1))
        result = await controller.decide(timeline.context(2, 2, single=True, kind="forced_switch", events=(
            "|faint|p1a: A", "|-terastallize|p2a: B|Water",
            "|replace|p2a: Illusion|Zoroark|100/100", "|-formechange|p2a: B|B-Therian")))
        assert result.automatic and len(planner.calls) == len(executor.calls) == 1
        pending = decisions(records)[-1]["pending_events"]
        assert {e["kind"] for e in pending} == set(EVENTS)
        await controller.decide(timeline.context(3, 3, single=True))
        assert len(planner.calls) == len(executor.calls) == 1
        await controller.decide(timeline.context(4, 4))
        assert len(planner.calls) == len(executor.calls) == 2
        assert decisions(records)[-1]["reasons"] == ["event:" + event for event in EVENTS]
        assert decisions(records)[-1]["pending_events"] == pending
        await controller.decide(timeline.context(5, 8))
        assert len(planner.calls) == 2
        assert decisions(records)[-1]["pending_events"] == []
    asyncio.run(run())


def test_forced_choice_then_new_matchup_same_turn_and_duplicate_requests():
    async def run():
        controller, planner, executor, records = setup()
        timeline = Timeline()
        await controller.decide(timeline.context(1, 1))
        forced = timeline.context(2, 2, kind="forced_switch", events=("|faint|p1a: A",))
        await controller.decide(forced)
        assert (await controller.decide(forced)).reused
        await controller.decide(timeline.context(3, 2, events=("|switch|p1a: B|Eevee|100/100",)))
        await controller.decide(timeline.context(4, 2))
        assert len(planner.calls) == 3 and len(executor.calls) == 4
        assert [r["reasons"] for r in decisions(records)] == [
            ["initial"], ["event:faint", "event:forced_switch"], ["event:active_change"], ["plan_reuse"]]
    asyncio.run(run())


def test_future_events_in_same_frame_and_later_frame_stay_outside_cutoff():
    async def run():
        controller, planner, _, records = setup()
        context = Timeline().context(1, 1)
        prefix = context.prefix
        prefix[0]["protocol"] += "\n|switch|p2a: Future|Eevee|100/100"
        prefix.append(dict(event_seq=2, protocol="|-formechange|p1a: Later|Palafin-Hero"))
        clipped = DecisionContext(context.battle, context.actor, context.rqid, context.payload,
                                  context.commands, prefix, context.boundary)
        await controller.decide(clipped)
        assert decisions(records)[-1]["pending_events"] == []
        request = next(row for row in records if row["type"] == "planner_request")
        assert "Future" not in json.dumps(request["messages"])
        assert "Later" not in json.dumps(request["messages"])
        payload = context.payload
        payload["state"]["request_id"] = 2
        visible = DecisionContext(context.battle, context.actor, 2, payload, context.commands,
                                  prefix, dict(protocol_event_seq=2, line_index=0))
        await controller.decide(visible)
        assert decisions(records)[-1]["reasons"] == ["event:active_change", "event:form_change"]
        assert [(e["sequence"], e["line_index"]) for e in decisions(records)[-1]["pending_events"]] == [(1, 3), (2, 0)]
    asyncio.run(run())


def test_event_free_long_plan_retention_and_battle_actor_isolation():
    async def run():
        controller, planner, _, records = setup()
        timeline = Timeline()
        await controller.decide(timeline.context(1, 1))
        for rqid, turn in enumerate((4, 7, 20), 2):
            result = await controller.decide(timeline.context(rqid, turn))
            assert result.plan["age_turns"] == turn - 1
            assert decisions(records)[-1]["reasons"] == ["plan_reuse"]
        assert len(planner.calls) == 1
        await controller.decide(timeline.context(5, 21, single=True, events=("|drag|p2a: A|Ditto|100/100",)))
        for other in (Timeline(actor="p2"), Timeline(battle="battle-other")):
            await controller.decide(other.context(1, 1))
            assert decisions(records)[-1]["reasons"] == ["initial"]
            assert decisions(records)[-1]["pending_events"] == []
        await controller.decide(timeline.context(6, 22))
        assert decisions(records)[-1]["reasons"] == ["event:active_change"]
        assert len(planner.calls) == 4
    asyncio.run(run())


def test_new_events_require_explicit_opt_in_and_old_defaults_are_unchanged():
    assert DEFAULT_TRIGGER == dict(policy="events_or_periodic", interval_turns=3,
                                   events=["faint", "tera", "forced_switch"])
    assert _trigger({}) == DEFAULT_TRIGGER
    assert _trigger(dict(policy="events", events=EVENTS))["events"] == EVENTS
    context = Timeline().context(1, 1, events=("|switch|p1a: A|Ditto|100/100",
                                              "|-formechange|p2a: B|Palafin-Hero"))
    rows = public_events(context.prefix, context.boundary, actor="p1", battle=context.battle)
    assert trigger_events(rows, decision_kind="turn", rqid=1) == []
    assert trigger_events(rows, decision_kind="turn", rqid=1, enabled=[]) == []
    assert [e["kind"] for e in trigger_events(rows, decision_kind="turn", rqid=1,
                                             enabled=["form_change"])] == ["form_change"]
