"""Pure protocol filtering, common-random-number identity, and durable caps."""
import copy

import pytest

from integration.pokechamp.branch_rollouts import common


def test_future_seeds_are_shared_across_actions_but_not_replicates_or_actors():
    actions = ("move-1", "move-1-tera", "switch-3")
    actual = {
        action: {
            ns: [common.derive_seed("a007", r, ns) for r in range(32)]
            for ns in ("simulator", "p1", "p2")
        }
        for action in actions
    }
    assert actual[actions[0]] == actual[actions[1]] == actual[actions[2]]
    seeds = actual[actions[0]]
    assert len({tuple(seed) for seed in seeds["simulator"]}) == 32
    assert all(len(seed) == 4 and all(type(x) is int and 0 <= x < 65536 for x in seed)
               for seed in seeds["simulator"])
    assert all(type(x) is int and 0 <= x < 2**32 for x in seeds["p1"] + seeds["p2"])
    assert set(seeds["p1"]).isdisjoint(seeds["p2"])
    assert common.derive_seed("a007", 0, "simulator") != common.derive_seed("a008", 0, "simulator")


def test_gameplay_filter_removes_only_transport_and_keeps_event_order():
    gameplay = [
        "|player|p1|Alice|1|", "|player|p2|Bob|2|", "|clearpoke",
        "|poke|p1|Pikachu, M|", "|teampreview", "|start",
        "|switch|p1a: Spark|Pikachu, M|211/211", "|turn|1",
        "|move|p1a: Spark|Thunderbolt|p2a: Shell", "|-damage|p2a: Shell|50/100",
        "|upkeep", "|win|Alice",
    ]
    lines = [">battle-gen9ou-1", "|init|battle", "|title|Alice vs Bob", "", "|"]
    for i, line in enumerate(gameplay):
        lines.extend([f"|t:|{i}", line, '|request|{"private":"do not compare as gameplay"}',
                      "|sentchoice|move 1"])
    untouched = copy.deepcopy(lines)
    assert common.gameplay_lines(lines) == gameplay
    assert lines == untouched
    assert common.gameplay_lines(gameplay) == gameplay


def test_request_normalization_preserves_gameplay_restrictions_and_input():
    req = {
        "rqid": 23, "noCancel": True, "wait": False, "forceSwitch": [False],
        "active": [{"trapped": True, "canTerastallize": "Ghost", "moves": [
            {"id": "thunderbolt", "pp": 0, "disabled": True},
        ]}],
        "side": {"id": "p2", "pokemon": [{"ident": "p2: Spark", "condition": "9/211 par"}]},
    }
    original = copy.deepcopy(req)
    result = common.normalize_request(req)
    assert set(result) == {"wait", "forceSwitch", "active", "side"}
    assert result["active"][0]["trapped"] is True
    assert result["active"][0]["moves"][0] == original["active"][0]["moves"][0]
    assert req == original
    another = copy.deepcopy(req)
    another["rqid"] = 99
    another["noCancel"] = False
    assert common.normalize_request(another) == result
    another["active"][0]["moves"][0]["disabled"] = False
    assert common.normalize_request(another) != result


@pytest.mark.parametrize("wire, expected", [
    ("/choose move 2 terastallize", "move 2 terastallize"),
    ("/choose switch 5", "switch 5"),
    ("/team 312456", "team 312456"),
])
def test_archived_wire_command_retains_choice_semantics(wire, expected):
    assert common.command(wire) == expected


def test_unsupported_archived_command_is_not_guessed():
    with pytest.raises(ValueError, match="Unsupported"):
        common.command("move 2")


def test_budget_reopen_keeps_first_clock_and_cumulative_attempts(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(common.time, "time", lambda: now[0])
    initial = common.Budget(tmp_path)
    assert initial.reserve("reconstruction", "historical") == 1
    now[0] += 200
    reopened = common.Budget(tmp_path)
    assert reopened.value["started_at"] == 1000
    assert reopened.value["admission_deadline"] == 14500
    assert reopened.value["deadline"] == 15400
    assert reopened.reserve("rollout", ["a000", "move-1", 0]) == 2
    now[0] += 300
    recovery = common.Budget(tmp_path)
    assert recovery.reserve("recovery", ["a000", "move-1", 0]) == 3
    assert common.read(tmp_path / "ledger.json")["started_at"] == 1000
    records = common.rows(tmp_path / "attempts.jsonl")
    assert [row["number"] for row in records] == [1, 2, 3]
    assert [row["kind"] for row in records] == ["reconstruction", "rollout", "recovery"]


def test_budget_attempt_cap_applies_after_reopen_and_does_not_add_failed_reservation(tmp_path, monkeypatch):
    monkeypatch.setattr(common.time, "time", lambda: 1000.0)
    budget = common.Budget(tmp_path)
    budget.value["attempts"] = 5999
    common.write(tmp_path / "ledger.json", budget.value)
    resumed = common.Budget(tmp_path)
    assert resumed.reserve("rollout", "last") == 6000
    at_limit = common.Budget(tmp_path)
    with pytest.raises(RuntimeError, match="attempt cap"):
        at_limit.reserve("rollout", "forbidden")
    assert common.read(tmp_path / "ledger.json")["attempts"] == 6000
    assert [row["identity"] for row in common.rows(tmp_path / "attempts.jsonl")] == ["last"]


def test_budget_admission_stops_at_cleanup_boundary_without_reset(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(common.time, "time", lambda: now[0])
    budget = common.Budget(tmp_path)
    now[0] = budget.value["admission_deadline"]
    reopened = common.Budget(tmp_path)
    with pytest.raises(RuntimeError, match="admission deadline"):
        reopened.reserve("rollout", "too-late")
    assert reopened.value["attempts"] == 0
    assert reopened.value["deadline"] - now[0] == 900
    assert not (tmp_path / "attempts.jsonl").exists()
def test_preview_restores_server_gender_without_changing_raw_team():
    from integration.pokechamp.branch_rollouts.common import simulator_teams
    packed = "Hydrapple||boots|regenerator|earthpower|Modest|1,2,3|||||"
    teams = {s: {"name": s, "team": packed} for s in ("p1", "p2")}
    events = [{"type": "protocol", "protocol": "|poke|p1|Hydrapple, M|\n|poke|p2|Hydrapple, F|"}]
    restored = simulator_teams(teams, events)
    assert restored["p1"]["team"].split("|")[7] == "M"
    assert restored["p2"]["team"].split("|")[7] == "F"
    assert teams["p1"]["team"] == packed
    assert restored["p1"]["team"].replace("|M|", "||") == packed


def test_room_departure_is_transport_while_terminal_gameplay_is_preserved():
    from integration.pokechamp.branch_rollouts.common import gameplay_lines
    lines = ["|faint|p2a: Zapdos", "|win|opponent", "|L|☆opponent"]
    assert gameplay_lines(lines) == lines[:2]
