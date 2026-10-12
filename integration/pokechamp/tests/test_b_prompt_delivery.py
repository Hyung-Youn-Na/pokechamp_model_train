"""B0–B3 information preservation and the offline final-message boundary."""

from __future__ import annotations

import copy
import json
import socket
from dataclasses import replace
from pathlib import Path

import pytest

from integration.pokechamp.improved_io import battle_prompts
from integration.pokechamp.improved_io.delivery import (
    CALCULATOR_VERSION,
    VERSIONS,
    calculations,
    capture_request,
    digest,
    dumps,
    exclusions,
    generate,
    generate_all,
    history,
    parse_json,
    restore_projection,
)
from integration.pokechamp.improved_io.delivery.preservation import (
    check_source,
    restore_source,
)
from integration.pokechamp.improved_io.delivery.report import statistics_for

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def original_event():
    path = ROOT / ".pokechamp-data/experiments/ex037-cloud/battles/b01-r1-s0-a1-p2/events.jsonl"
    return next(e for e in map(json.loads, path.open()) if e["event_type"] == "llm_call")


@pytest.fixture(scope="module")
def full(original_event):
    return parse_json(original_event["user_prompt"])


@pytest.fixture(scope="module")
def quartet(full):
    return generate_all(full, battle_format="gen9ou")


@pytest.mark.parametrize("version", VERSIONS)
def test_complete_source_recovery_and_networkless_final_request(
    full, quartet, version, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("offline candidate attempted network IO")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    before = dumps(full)
    delivery = quartet[version]
    restored = check_source(
        full, restore_projection(delivery), parse_json(delivery.source_link_json)["exclusions"]
    )
    assert history.comparable(restored) == history.comparable(full)
    wire = capture_request(full, delivery, battle_format="gen9ou")
    assert wire["payload"]["messages"] == [
        {"role": "system", "content": delivery.system_prompt},
        {"role": "user", "content": delivery.user_json},
    ]
    assert wire["candidate_version"] == version
    assert wire["calculator_semantics_version"] == CALCULATOR_VERSION
    assert wire["source_link"]["original_user_sha256"] == digest(
        json.dumps(full, ensure_ascii=False)
    )
    assert dumps(full) == before


def test_b0_original_strings_and_historical_selection_are_preserved(original_event, quartet):
    assert quartet["B0"].system_prompt == original_event["system_prompt"]
    assert quartet["B0"].user_json == original_event["user_prompt"]
    assert battle_prompts.DEFAULT_VERSION == "v1.3.0"  # D-057 changes only new prepares.
    assert all(version not in battle_prompts.VERSIONS for version in VERSIONS)
    for version in VERSIONS[1:]:
        tactical = (
            quartet[version].system_prompt.split("Decision procedure\n")[1].split("\n---\n")[0]
        )
        baseline = quartet["B0"].system_prompt.split("Decision procedure\n")[1].split("\n---\n")[0]
        assert tactical.rstrip() == baseline.rstrip()
        assert len(quartet[version].system_prompt) + len(quartet[version].user_json) < (
            len(quartet["B0"].system_prompt) + len(quartet["B0"].user_json)
        )


def test_excluded_data_remains_in_log_and_tactical_identity_stays_visible(full, quartet):
    projected = parse_json(quartet["B1"].user_json)
    assert "battle_summary" not in projected and "lesson_memory" not in projected
    assert projected["identity"]["actor_id"] == full["identity"]["actor_id"]
    assert projected["request"]["legal_actions"] == full["request"]["legal_actions"]
    assert "bundle_sha256" not in projected["calculation_bundle"]
    log = parse_json(quartet["B1"].source_link_json)
    assert any(
        r["path"] == ["calculation_bundle", "bundle_sha256"]
        and r["value"] == full["calculation_bundle"]["bundle_sha256"]
        for r in log["exclusions"]
    )
    assert any(r["path"][-1] == "pokeball" for r in log["exclusions"])


@pytest.mark.parametrize(
    "mutation",
    [
        "system",
        "whitespace",
        "user_scalar",
        "missing_field",
        "action_order",
        "candidate",
        "semantics",
        "origin",
        "rehash_tampered",
        "derived_target",
    ],
)
def test_final_boundary_rejects_tampering(full, quartet, mutation):
    original = quartet["B2"]
    user = parse_json(original.user_json)
    if mutation == "system":
        corrupt = replace(original, system_prompt=original.system_prompt + " ")
    elif mutation == "whitespace":
        corrupt = replace(original, user_json=original.user_json + "\n")
    elif mutation == "candidate":
        corrupt = replace(original, candidate_version="B3")
    elif mutation == "semantics":
        corrupt = replace(original, calculator_semantics_version="calculator-input-v1")
    elif mutation == "origin":
        link = parse_json(original.source_link_json)
        link["origin"] = {"event_seq": 999999}
        corrupt = replace(original, source_link_json=dumps(link))
    else:
        if mutation == "missing_field":
            del user["unknowns"]
        elif mutation == "action_order":
            user["request"]["legal_actions"].reverse()
        elif mutation == "derived_target":
            user["calculation_bundle"]["scenarios"][0]["calculation_target"] = "wrong-target"
        else:
            user["calculation_bundle"]["scenarios"][0]["result"]["defender_max_hp"] += 1
        corrupt = replace(original, user_json=dumps(user))
        if mutation == "rehash_tampered":
            link = parse_json(corrupt.source_link_json)
            link["user_sha256"] = digest(corrupt.user_json)
            corrupt = replace(corrupt, source_link_json=dumps(link))
    with pytest.raises(ValueError):
        capture_request(full, corrupt, battle_format="gen9ou")


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("memory", ["summary", "lesson"])
def test_every_version_rejects_unexpected_memory(full, version, memory):
    changed = copy.deepcopy(full)
    changed["battle_summary" if memory == "summary" else "lesson_memory"] = {"unexpected": "memory"}
    with pytest.raises(ValueError):
        generate(changed, version, battle_format="gen9ou")


@pytest.mark.parametrize(
    "mutation",
    [
        "semantics",
        "bundle_hash",
        "patch",
        "missing_history",
        "unknown_field",
        "missing_calc",
        "missing_memory",
    ],
)
def test_original_validation_is_required_before_projection(full, mutation):
    changed = copy.deepcopy(full)
    if mutation == "semantics":
        del changed["identity"]["input_version"]
    elif mutation == "bundle_hash":
        changed["calculation_bundle"]["bundle_sha256"] = "0" * 64
    elif mutation == "patch":
        changed["calculation_bundle"]["runtime_patch"]["patch_id"] = "unverified"
    elif mutation == "missing_history":
        del changed["current_observation"]["self_team"][0]["ability_history"]
    elif mutation == "unknown_field":
        changed["current_observation"]["self_team"][0]["unclassified_tactical_value"] = 5
    elif mutation == "missing_memory":
        del changed["battle_summary"]
    else:
        del changed["calculation_bundle"]["entries"]
    with pytest.raises((ValueError, KeyError)):
        generate(changed, "B3", battle_format="gen9ou")


def test_scope_and_version_are_explicit(full):
    with pytest.raises(ValueError, match="scope"):
        generate(full, "B1", battle_format="gen9doublesou")
    with pytest.raises(ValueError, match="unsupported"):
        generate(full, "B4", battle_format="gen9ou")


@pytest.mark.parametrize(
    "key,value",
    [("canDynamax", True), ("canZMove", [{"move": "Z"}]), ("maxMoves", {"maxMoves": ["attack"]})],
)
def test_b1_rejects_active_legacy_mechanic_instead_of_hiding_it(full, key, value):
    changed = copy.deepcopy(full)
    changed["recent_events"] = [
        dict(event_seq=1, protocol="|request|" + dumps({"active": [{key: value}]}))
    ]
    with pytest.raises(ValueError, match="out-of-scope"):
        exclusions.prune(changed)


def test_object_delta_null_delete_and_atomic_party_arrays():
    old = {
        "rqid": 7,
        "item": "berry",
        "remove": None,
        "side": {"pokemon": [1, 2]},
        "active": [{"moves": [{"id": "protect", "pp": 3}]}],
    }
    new = {
        "rqid": 8,
        "item": None,
        "side": {"pokemon": [2, 1]},
        "active": [{"moves": [{"id": "protect", "pp": 2}]}],
        "new": [],
    }
    change = history.delta(old, new)
    assert change["delete"] == ["remove"]
    assert change["patch"]["item"] == {"replace": None}
    assert change["patch"]["side"]["patch"]["pokemon"] == {"replace": [2, 1]}
    assert change["patch"]["active"] == {"replace": new["active"]}
    assert history.apply_delta(old, change) == new
    assert old["item"] == "berry"


def test_history_keeps_order_line_endings_items_hp_pp_restrictions_and_unknown_rows():
    requests = [
        dict(
            rqid=10,
            side={"id": "p1", "pokemon": [{"condition": "50/100", "item": "berry"}]},
            active=[{"moves": [{"id": "protect", "pp": 2}], "trapped": False}],
        ),
        dict(
            rqid=11,
            side={"id": "p1", "pokemon": [{"condition": "65/100", "item": ""}]},
            active=[{"moves": [{"id": "protect", "pp": 1}], "trapped": True}],
        ),
    ]
    events = [
        dict(event_seq=10, protocol=">room\r\n|turn|5\r\n|request|" + dumps(requests[0]) + "\r\n"),
        dict(
            event_seq=12,
            protocol="|-enditem|p1a: 이름|berry\n|unknown|a|b||\n"
            "|request|" + dumps(requests[1]) + "\n|raw-final|literal",
        ),
    ]
    encoded = history.encode(events)
    assert [e["event_seq"] for e in encoded] == [10, 12]
    assert encoded[1]["lines"][0] == "|-enditem|p1a: 이름|berry\n"
    assert encoded[1]["lines"][1] == "|unknown|a|b||\n"
    assert history.decode(encoded) == events


def test_history_is_self_contained_at_ten_decision_boundary():
    all_events = [
        dict(
            event_seq=i,
            protocol="|turn|"
            + str(i)
            + "\n|request|"
            + dumps(
                {
                    "rqid": i,
                    "side": {"id": "p2", "pokemon": [{"ident": "p2: data|only"}]},
                    "active": [{"moves": [{"id": "recover", "pp": 20 - i}]}],
                }
            ),
        )
        for i in range(1, 12)
    ]
    window = all_events[1:]
    encoded = history.encode(window)
    assert len(encoded) == 10
    assert encoded[0]["lines"][1]["request_base"]["rqid"] == 2
    assert encoded[0]["lines"][1]["request_index"] == 0
    assert history.decode(encoded) == window
    assert "side" not in encoded[1]["lines"][1]["request_delta"]["patch"]


@pytest.mark.parametrize(
    "change",
    [
        {"delete": ["missing"], "set": {}, "patch": {}},
        {"delete": ["x"], "set": {}, "patch": {"x": {"replace": None}}},
        {"delete": [], "set": {"x": 2}, "patch": {}},
        {"replace": 1, "delete": []},
    ],
)
def test_invalid_delta_operations_fail(change):
    with pytest.raises(ValueError):
        history.apply_delta({"x": 1}, change)


def test_missing_history_reference_and_null_request():
    events = [dict(event_seq=1, protocol="|request|null\n|request|{}\n")]
    encoded = history.encode(events)
    assert history.decode(encoded) == events
    encoded[0]["lines"][1]["base_request"] = 44
    with pytest.raises(ValueError, match="reference"):
        history.decode(encoded)


def synthetic_bundle():
    rows = []
    for index in range(2):
        sid = f"out-move-iciclespear-h{index}-hp100"
        variants = [
            dict(
                label="2-hit",
                hits=2,
                damage_range_hp=[18, 22],
                damage_rolls=[[9, 9, 10, 11], [9, 9, 10, 11]],
            ),
            dict(
                label="3-hit", hits=3, damage_range_hp=[27, 33], damage_rolls=[[9, 9, 10, 11]] * 3
            ),
        ]
        rows.append(
            dict(
                scenario_id=sid,
                damage_range_hp=[18, 22],
                damage_rolls=variants[0]["damage_rolls"],
                damage_variants=variants,
                conditional_order={"conditions": "conditional uncertainty " * 8},
                scenario_state={"phase": "after_selected_switch_entry", "weather": None},
                ko_chance_given_hit=None,
            )
        )
    return dict(
        entries=rows,
        coverage=[
            dict(scenario_id=r["scenario_id"], direction="outgoing", action={"move": "iciclespear"})
            for r in rows
        ],
    )


def test_multihit_scenarios_roll_order_multiplicity_and_branches_are_not_merged():
    source = synthetic_bundle()
    compact = calculations.encode(
        source, {"opponent_confirmed": [dict(active=True, species="target")]}, [{}, {}]
    )
    assert len(compact["scenarios"]) == 2
    for i, row in enumerate(compact["scenarios"]):
        assert row["opponent_condition"] == {"hypothesis_index": i, "hp": 100}
        assert row["calculation_target"] == "target"
        assert row["result"]["damage_rolls"] == {"same_as_variant": 0}
        assert row["result"]["damage_variants"] == source["entries"][i]["damage_variants"]
    assert calculations.decode(compact) == source


def test_forced_switch_unrevealed_opponent_exclusion_stays_unknown():
    source = dict(
        entries=[
            dict(
                scenario_id="switch-blissey-unknown-opponent",
                excluded_with_reason="opponent replacement not yet revealed",
            )
        ],
        coverage=[
            dict(
                scenario_id="switch-blissey-unknown-opponent",
                direction="incoming",
                action={"switch": "blissey"},
            )
        ],
    )
    compact = calculations.encode(source, {"opponent_confirmed": []}, [])
    row = compact["scenarios"][0]
    assert row["calculation_target"] == "blissey"
    assert row["opponent_condition"].startswith("UNKNOWN")
    assert "damage_range_hp" not in row["result"]
    assert calculations.decode(compact) == source


@pytest.mark.parametrize(
    "kind", ["missing_text", "chained_text", "variant", "chained_variant", "duplicate_scenario"]
)
def test_bad_common_damage_and_scenario_references_fail(kind):
    compact = calculations.encode(
        synthetic_bundle(), {"opponent_confirmed": [dict(active=True, species="target")]}, [{}, {}]
    )
    if kind == "missing_text":
        compact["shared_text"].clear()
    elif kind == "chained_text":
        compact["shared_text"]["c0"] = {"shared_text": "c1"}
    elif kind == "variant":
        compact["scenarios"][0]["result"]["damage_rolls"] = {"same_as_variant": 99}
    elif kind == "chained_variant":
        compact["scenarios"][0]["result"]["damage_variants"][0]["damage_rolls"] = {
            "same_as_variant": 0
        }
    else:
        compact["scenarios"][1]["scenario_id"] = compact["scenarios"][0]["scenario_id"]
    with pytest.raises(ValueError):
        calculations.decode(compact)


def test_unclassified_loss_cannot_be_hidden_in_exclusion_log(quartet):
    with pytest.raises(ValueError, match="unclassified"):
        restore_source(
            restore_projection(quartet["B1"]),
            [dict(path=["request", "legal_actions"], value=[], reason="optimization")],
        )


def test_duplicate_json_nonfinite_and_percentile_contract():
    for text in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}'):
        with pytest.raises(ValueError):
            parse_json(text)
    assert statistics_for(list(range(1, 21))) == dict(
        mean=10.5, median=10.5, p95=19, maximum=20, sum=210, n=20
    )


def test_nested_json_type_changes_are_not_erased():
    old = {"a": [{"x": False}], "b": {"x": 1}}
    new = {"a": [{"x": 0}], "b": {"x": 1.0}}
    result = history.apply_delta(old, history.delta(old, new))
    assert type(result["a"][0]["x"]) is int
    assert type(result["b"]["x"]) is float


def test_duplicate_embedded_request_key_is_rejected(full):
    changed = copy.deepcopy(full)
    changed["recent_events"][0]["protocol"] = '|request|{"rqid":1,"rqid":2}'
    with pytest.raises(ValueError, match="duplicate"):
        generate(changed, "B3", battle_format="gen9ou")


def test_complete_validator_mapping_preserves_exclusions_and_new_references():
    from integration.pokechamp.improved_io.delivery.mapping import catalog

    rows = {r["source_path"]: r for r in catalog()["fields"]}
    assert rows["$.request.legal_actions.*"]["B3"] == "retained"
    assert rows["$.calculation_bundle.entries"]["target_path"] == "$.calculation_bundle.scenarios"
    assert (
        rows["$.calculation_bundle.coverage.*"]["target_path"] == "$.calculation_bundle.scenarios.*"
    )
    assert rows["$.calculation_bundle.engine_patch.patch_id"]["B1"] == "excluded_to_source_log"
    assert "same_as_variant" in rows["$.calculation_bundle.entries.*.damage_rolls"]["B2"]
    assert "request_delta" in rows["RequestJSON.side.pokemon.*.item"]["B3"]
    assert rows["RequestJSON.side.pokemon.*.pokeball"]["B3"] == "excluded_to_source_log"
