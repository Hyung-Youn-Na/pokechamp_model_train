"""Synthetic simulator fixtures only; no archived game or experiment collection."""

import copy
import json
import selectors

import pytest

from integration.pokechamp.branch_rollouts.simulator import Simulator, SimulatorError


TEAMS = {
    "p1": {"name": "fixture-one", "avatar": "1", "team": """Dragapult
Ability: Clear Body
Tera Type: Ghost
EVs: 252 Spe / 252 SpA
Timid Nature
- U-turn
- Shadow Ball

Corviknight
Ability: Pressure
- Roost
- Brave Bird
"""},
    "p2": {"name": "fixture-two", "avatar": "2", "team": """Blissey
Ability: Natural Cure
Tera Type: Fairy
- Soft-Boiled
- Seismic Toss

Corviknight
Ability: Pressure
- Roost
- Brave Bird
"""},
}


def clean(value):
    value = copy.deepcopy(value)
    for key in ("public_log",):
        if key in value:
            value[key] = ["|t:|" if s.startswith("|t:|") else s for s in value[key]]
    if "log" in value:
        value["log"] = ["|t:|" if s.startswith("|t:|") else s for s in value["log"]]
    value.pop("messages", None)
    return value


def start(sim):
    preview = sim.init(TEAMS, [1, 2, 3, 4], player_order=["p2", "p1"])
    assert preview["needs_choice"] == ["p1", "p2"]
    assert all("rqid" not in r for r in preview["requests"].values())
    return sim.step({"p1": "team 12", "p2": "team 12"})


def test_round_trip_retains_submitted_choice_and_private_channels():
    with Simulator() as sim:
        initial = start(sim)
        assert initial["turn"] == 1
        partial = sim.step({"p1": "move 2"})
        assert partial["needs_choice"] == ["p2"]
        assert partial["choices_done"] == {"p1": True, "p2": False}
        snapshot = sim.snapshot()
        serialized = json.dumps(snapshot, sort_keys=True)
        expected = sim.step({"p2": "move 2"})
        restored = sim.restore(snapshot)
        assert restored["messages"] == []
        assert restored["needs_choice"] == ["p2"]
        actual = sim.step({"p2": "move 2"})
        assert clean(actual) == clean(expected)
        assert json.dumps(snapshot, sort_keys=True) == serialized
        assert not any(line.startswith("|split|") for line in actual["public_log"])
        assert actual["actor_logs"]["p1"] != actual["actor_logs"]["p2"]


def test_midturn_switch_queue_survives_restore():
    with Simulator() as sim:
        start(sim)
        middle = sim.step({"p1": "move 1", "p2": "move 2"})
        assert middle["request_state"] == "switch"
        assert middle["needs_choice"] == ["p1"]
        assert middle["requests"]["p2"]["wait"] is True
        assert middle["queue_length"] > 0
        snapshot = sim.snapshot()
        expected = sim.step({"p1": "switch 2"})
        sim.restore(snapshot)
        actual = sim.step({"p1": "switch 2"})
        assert clean(actual) == clean(expected)
        assert actual["turn"] == 2
        assert any("|Seismic Toss|p1a: Corviknight" in line for line in actual["public_log"])


def test_reseed_repeats_are_independent_and_tera_is_a_distinct_action():
    with Simulator() as sim:
        start(sim)
        root = sim.snapshot()
        outcomes = {}
        for action in ["move 2", "move 2 terastallize", "move 2"]:
            restored = sim.restore(root)
            reseeded = sim.reseed([5, 6, 7, 8])
            assert reseeded["messages"] == []
            assert reseeded["public_log"] == restored["public_log"]
            assert reseeded["actor_logs"] == restored["actor_logs"]
            result = sim.step({"p1": action, "p2": "move 2"})
            if action in outcomes:
                assert clean(result) == clean(outcomes[action])
            outcomes[action] = result
        assert any("|-terastallize|" in s for s in outcomes["move 2 terastallize"]["public_log"])
        assert not any("|-terastallize|" in s for s in outcomes["move 2"]["public_log"])


def test_illegal_choice_fails_closed_without_default_action():
    with Simulator() as sim:
        start(sim)
        with pytest.raises(SimulatorError, match="rejected operation"):
            sim.step({"p1": "move 99"})
        assert sim.closed
        assert sim.process.poll() is not None


def test_wait_side_cannot_consume_a_new_request_from_same_step():
    with Simulator() as sim:
        start(sim)
        sim.step({"p1": "move 1", "p2": "move 2"})
        with pytest.raises(SimulatorError, match="does not need a choice"):
            sim.step({"p1": "switch 2", "p2": "move 2"})


def test_close_cleans_process_and_timeout_is_bounded():
    sim = Simulator()
    sim.close()
    sim.close()
    assert sim.process.poll() is not None
    with pytest.raises(ValueError):
        Simulator(timeout=121)


def test_poke_env_packed_team_and_player_metadata_are_preserved():
    from poke_env.teambuilder.constant_teambuilder import ConstantTeambuilder

    teams = copy.deepcopy(TEAMS)
    for player in teams.values():
        player["team"] = ConstantTeambuilder(player["team"]).yield_team()
    with Simulator() as sim:
        result = sim.init(teams, [1, 2, 3, 4], player_order=["p2", "p1"])
        snapshot = sim.snapshot()
        players = [line for line in snapshot["inputLog"] if line.startswith(">player ")]
        assert players[0].startswith(">player p2 ")
        for line in players:
            _, side, raw = line.split(" ", 2)
            payload = json.loads(raw)
            assert payload["team"] == teams[side]["team"]
            assert payload["avatar"] == teams[side]["avatar"]
        assert "|player|p1|fixture-one|1|" in result["public_log"]


def test_original_default_command_is_submitted_to_simulator():
    with Simulator() as sim:
        start(sim)
        result = sim.step({"p1": "default", "p2": "default"})
        assert result["errors"] == []
        assert any(line.startswith("|move|p1a: Dragapult|U-turn|")
                   for line in result["public_log"])


def test_external_deadline_remains_timeout_and_cleans_process(monkeypatch):
    class ExpiredSelector(selectors.DefaultSelector):
        def select(self, timeout=None):
            raise TimeoutError("fixture branch deadline")

    sim = Simulator()
    monkeypatch.setattr(selectors, "DefaultSelector", ExpiredSelector)
    with pytest.raises(TimeoutError, match="fixture branch deadline"):
        sim.status()
    assert sim.closed
    assert sim.process.poll() is not None
