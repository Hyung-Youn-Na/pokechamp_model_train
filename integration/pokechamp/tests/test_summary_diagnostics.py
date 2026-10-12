"""EX-021 lossless transforms, original-event checks, and bounded worker lifecycle."""

import copy
import json
import threading
import time
from collections import Counter

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.summary_diagnostics.prepare import prepare, schedule, verify
from integration.pokechamp.summary_diagnostics.report import (
    aggregate,
    check_review,
    report,
)
from integration.pokechamp.summary_diagnostics.runner import clock, run
from integration.pokechamp.summary_diagnostics.transforms import (
    annotate,
    apply_delta,
    canonical_events,
    delta,
    reduce_requests,
    request_values,
    restore_requests,
    transform,
    verify_equivalence,
)


@pytest.mark.parametrize(
    "before,after",
    [
        ({"a": 1, "gone": 2}, {"a": 2, "new": 3}),
        ({"a": [1, {"b": 2}]}, {"a": [1, {"b": None}]}),
        ({"a": [1, 2]}, {"a": []}),
        ({"a": False}, {"a": 0}),
        ({"a": None}, {"a": ""}),
        ({"a/b": {"~": 1}}, {"a/b": {}}),
        ({}, []),
        ([], {}),
        ([1, 2], [3]),
        (None, {}),
    ],
)
def test_delta_roundtrip(before, after):
    frozen = copy.deepcopy(before)
    assert apply_delta(before, delta(before, after)) == after
    assert before == frozen


def test_protocol_order_empty_requests_and_actor_isolation():
    original = [
        {"event_seq": 1, "protocol": '|request|{"side":{"id":"p1"},"a":1}\n|turn|2\n'},
        {"event_seq": 2, "protocol": "|request|\n|request|{}\n|move|p1a: X|Y|p2a: Z\n"},
    ]
    reduced = reduce_requests(original, "p1")
    restored = restore_requests(reduced, "p1")
    assert canonical_events(restored, "p1") == canonical_events(original, "p1")
    assert request_values(restored, "p1") == [{"side": {"id": "p1"}, "a": 1}, {}]
    assert "|request|\n" in reduced[1]["protocol"]
    with pytest.raises(ValueError, match="foreign"):
        reduce_requests(original, "p2")
    with pytest.raises(ValueError, match="actor/order"):
        restore_requests(reduced, "p2")
    reduced[1]["protocol"] = reduced[1]["protocol"].replace('"index":1', '"index":4')
    with pytest.raises(ValueError, match="actor/order"):
        restore_requests(reduced, "p1")


def context(protocols):
    return {
        "identity": {"actor_id": "p2"},
        "source_events": [
            {"event_seq": i, "showdown_turn": 99, "protocol": p} for i, p in enumerate(protocols)
        ],
        "current_observation": {
            "self_side_conditions": {"SPIKES": 3},
            "opponent_side_conditions": {"STEALTH_ROCK": 2},
        },
    }


def test_exact_two_hits_ko_decrement_and_packet_turn():
    value = context(
        [
            "|turn|8\n|switch|p2a: Fox|Ninetales, M|349/349\n|turn|9",
            "|move|p1a: K|Kowtow Cleave|p2a: Fox\n|-damage|p2a: Fox|64/349\n|turn|10",
            "|move|p1a: K|Kowtow Cleave|p2a: Fox\n|-damage|p2a: Fox|0 fnt\n|faint|p2a: Fox",
        ]
    )
    result = annotate(value)
    damage = [a for a in result["event_annotations"] if a["kind"] == "-damage"]
    assert [r["turn"] for r in damage] == [9, 10]
    assert [r["observed_hp_decrease"] for r in damage] == [285, 64]
    assert [r["hp_before"]["current"] for r in damage] == [349, 64]
    assert all("attack_damage" not in r for r in damage)
    assert damage[1]["move_link"]["ref"] == {"event": 2, "line": 1}
    assert result["event_annotations"][-1]["preceding_damage_ref"] == {"event": 2, "line": 2}
    assert [x["meaning"] for x in result["numeric_state"]] == ["layers", "activation_turn"]


def test_delayed_hit_not_attributed_to_last_attack_and_public_precision():
    value = context(
        [
            "|turn|5\n|switch|p2a: Slowking|Slowking-Galar|393/393\n"
            "|move|p1a: Iron Valiant|Moonblast|p2a: Slowking\n"
            "|-damage|p2a: Slowking|346/393\n"
            "|-end|p2a: Slowking|move: Future Sight\n|-damage|p2a: Slowking|244/393\n"
            "|switch|p1a: Slowking|Slowking-Galar|100/100\n"
            "|-damage|p1a: Slowking|44/100"
        ]
    )
    rows = [a for a in annotate(value)["event_annotations"] if a["kind"] == "-damage"]
    assert rows[0]["move_link"]["move"] == "Moonblast"
    assert rows[1]["move_link"] is None
    assert rows[1]["delayed_resolution"]["effect"] == "move: Future Sight"
    assert rows[1]["observed_hp_decrease"] == 102
    assert rows[2]["hp_after"]["precision"] == "rounded_public"
    assert rows[2]["hp_before"]["current"] == 100


def test_transform_information_equivalence_and_no_future_annotations():
    value = context(
        [
            '|turn|2\n|switch|p2a: X|X|200/200\n|request|{"side":{"id":"p2"}}',
            "|move|p1a: X|Hit|p2a: X\n|-damage|p2a: X|100/200\n|turn|3",
        ]
    )
    values = {c: transform(value, c) for c in ("H0", "H1", "H2", "H3")}
    for c, transformed in values.items():
        verify_equivalence(value, transformed, c)
    assert values["H1"]["harness_annotations"] == values["H3"]["harness_annotations"]
    assert "OHKO" not in json.dumps(values)
    values["H3"]["opponent_private_set"] = {"secret": True}
    with pytest.raises(ValueError, match="information"):
        verify_equivalence(value, values["H3"], "H3")
    assert {r["turn"] for r in annotate(value)["event_annotations"]} == {2, 3}


def test_schedule_counterbalanced_and_repeats_not_new_scenes():
    rows = schedule()
    assert len(rows) == len({s["id"] for s in rows}) == len({s["blind_id"] for s in rows}) == 144
    assert set(Counter((r["scene"], r["condition"]) for r in rows).values()) == {3}
    for repeat in range(3):
        counts = Counter((r["condition"], r["order"] % 4) for r in rows if r["repeat"] == repeat)
        assert set(counts.values()) == {3}


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    directory = tmp_path_factory.mktemp("summary") / "prepared"
    assert prepare(directory)["scheduled"] == 144
    return directory


def test_real_prepare_frozen_byte_matches_and_integrity(prepared):
    manifest = verify(prepared)
    assert manifest["preflight"]["h0_byte_matches"] == 4
    for i in range(12):
        original = b.read_sealed(prepared / "inputs" / f"s{i:02}-H0.json")
        assert original["context"]["previous_summary"] is None
        for c in ("H1", "H2", "H3"):
            value = b.read_sealed(prepared / "inputs" / f"s{i:02}-{c}.json")
            verify_equivalence(original["context"], value["context"], c)
    first = prepared / "inputs/s00-H0.json"
    data = first.read_bytes()
    try:
        first.write_bytes(data + b" ")
        with pytest.raises(ValueError, match="drift"):
            verify(prepared)
    finally:
        first.write_bytes(data)


def test_original_references_and_delayed_annotations(prepared):
    h1 = b.read_sealed(prepared / "inputs/s01-H1.json")
    rows = h1["context"]["harness_annotations"]["event_annotations"]
    fox = [r for r in rows if r["kind"] == "-damage" and r["target"] == "p2: Kurama Chakra Mode"]
    assert [(r["turn"], r["hp_before"]["current"], r["hp_after"]["current"]) for r in fox] == [
        (9, 349, 64),
        (10, 64, 0),
    ]
    h1 = b.read_sealed(prepared / "inputs/s02-H1.json")
    delayed = next(
        r
        for r in h1["context"]["harness_annotations"]["event_annotations"]
        if r["ref"] == {"event": 45, "line": 10}
    )
    assert delayed["move_link"] is None and delayed["delayed_resolution"] is not None


def clone(prepared, tmp_path):
    import shutil

    directory = tmp_path / "run"
    shutil.copytree(prepared, directory)
    return directory


def test_fake_144_independent_workers_format_errors_continue_and_blind(prepared, tmp_path):
    directory = clone(prepared, tmp_path)
    bad = schedule()[0]["id"]
    result = run(directory, fake={bad: "format"})
    assert result["acquired"] == result["submitted"] == result["scheduled"] == 144
    assert result["failed"] == result["unconfirmed"] == result["unexecuted"] == 0
    assert result["reason"] is None
    rows = [b.read_sealed(p) for p in (directory / "responses").glob("*.json")]
    assert len({r["pid"] for r in rows}) == 144
    assert all(r["finished_at"] >= r["started_at"] for r in rows)
    assert next(r for r in rows if r["id"] == bad)["category"] == "output_contract"
    collection = b.read_sealed(directory / "collection.json")
    assert not any(collection["broker"]["active_at_close"].values())
    assert report(directory)["acquired"] == 144
    package = b.read_sealed(directory / "blind.json")
    assert all(
        set(r) == {"blind_id", "scene", "text", "response_sha256"} for r in package["responses"]
    )
    with pytest.raises(ValueError, match="already sealed"):
        run(directory, fake={})
    with pytest.raises(ValueError, match="collection mismatch"):
        check_review(package, {})
    audit = {
        "collection_sha256": package["collection_sha256"],
        "manifest_sha256": package["manifest_sha256"],
        "calls": {},
    }
    for response in package["responses"]:
        facts = package["references"][str(response["scene"])]["facts"]
        audit["calls"][response["blind_id"]] = {
            "response_sha256": response["response_sha256"],
            "facts": {f["id"]: {"retained": False, "quote": ""} for f in facts},
            "errors": [],
            "factual_claims": 1,
            "erroneous_claims": 0,
            "notes": "Synthetic fake text omits the actual facts; schema/aggregation fixture.",
        }
    check = check_review(package, audit)
    assert sum(c["format"] for c in check.values()) == 1
    assert sum(c["primary"] for c in check.values()) == 144
    audit_path = directory / "test-review.json"
    b.seal_json(audit_path, audit)
    assert report(directory, audit_path)["complete"]
    final = b.read_sealed(directory / "report.json")
    assert final["fake"] and final["reviewed"] == 144
    assert final["metrics"]["strata"]["existing"]["conditions"]["H0"]["complete_scenes"] == 4
    tampered = copy.deepcopy(audit)
    response = package["responses"][0]
    fact = next(iter(tampered["calls"][response["blind_id"]]["facts"].values()))
    fact.update(retained=True, quote="not present in the raw model response")
    with pytest.raises(ValueError, match="exact response quotation"):
        check_review(package, tampered)


def test_provider_failure_stops_and_keeps_worker_responses(prepared, tmp_path):
    directory = clone(prepared, tmp_path)
    result = run(directory, fake={schedule()[0]["id"]: "timeout"})
    assert result["reason"] is not None
    assert result["submitted"] < 144 and result["failed"] >= 1
    assert result["response_record"] == result["intended"]
    assert result["unexecuted"] + result["intended"] == 144
    before = (directory / "cloud-clock.json").read_bytes()
    assert clock(directory, now=time.time() + 10000)["first_dispatch_at"] < time.time()
    assert (directory / "cloud-clock.json").read_bytes() == before


def test_cancel_cleanup_kills_only_owned_workers_and_preserves_uncertainty(prepared, tmp_path):
    directory = clone(prepared, tmp_path)
    stop = threading.Event()

    def cancel():
        until = time.time() + 20
        while not list((directory / "submitted").glob("*.json")) and time.time() < until:
            time.sleep(0.02)
        stop.set()

    thread = threading.Thread(target=cancel)
    thread.start()
    result = run(
        directory,
        fake={r["id"]: "hang" for r in schedule()},
        stop_event=stop,
        _test_deadlines=(20, 5),
    )
    thread.join()
    assert result["killed"]
    assert result["unconfirmed"] > 0 and result["acquired"] == 0
    assert result["unexecuted"] > 0
    assert not __import__("multiprocessing").active_children()


def test_restart_does_not_resubmit_or_reset_clock(prepared, tmp_path):
    directory = clone(prepared, tmp_path)
    first = clock(directory, now=1)
    result = run(directory, fake={})
    assert result["submitted"] == result["acquired"] == 0
    assert result["unexecuted"] == 144
    assert result["cloud_clock"] == first
    assert result["reason"] == "coordinator_restart_no_resubmission"


def test_aggregation_pairs_scenes_and_marks_missing_repeats():
    slots = [
        dict(r, submitted=False, acquired=False, failed=False, unexecuted=True, unconfirmed=False)
        for r in schedule()
    ]
    manifest = {
        "scenes": [
            {"scene": i, "stratum": "existing" if i < 4 else "additional"} for i in range(12)
        ]
    }
    checked = {}
    for slot in slots:
        if slot["scene"] == 0 and slot["condition"] in ("H0", "H1"):
            value = int(slot["condition"] == "H0")
            checked[slot["blind_id"]] = {
                "primary": value,
                "critical": value,
                "omission": 0,
                "format": 0,
                "retention": 1,
                "factual_claims": 10,
                "erroneous_claims": value,
                "unsupported": 0,
                "contradictions": 0,
            }
    result = aggregate(manifest, {"slots": slots}, checked, {})
    pair = result["strata"]["existing"]["contrasts"]["H0->H1"]
    assert pair["paired_scenes"] == 1 and pair["missing_pairs"] == 3
    assert pair["primary_difference"] == -1
    del checked[next(s["blind_id"] for s in slots if s["scene"] == 0 and s["condition"] == "H1")]
    pair = aggregate(manifest, {"slots": slots}, checked, {})["strata"]["existing"]["contrasts"][
        "H0->H1"
    ]
    assert pair["paired_scenes"] == 0 and pair["primary_difference"] is None


def test_all_annotations_agree_with_independently_read_original_lines(prepared):
    for i in range(12):
        raw = b.read_sealed(prepared / "references" / f"s{i:02}.json")
        value = b.read_sealed(prepared / "inputs" / f"s{i:02}-H1.json")
        original, turn = {}, 0
        for event in raw["source_events"]:
            for number, line in enumerate(event["protocol"].splitlines(), 1):
                if line.startswith("|turn|"):
                    turn = int(line.split("|")[2])
                original[event["event_seq"], number] = (line, turn)
        for row in value["context"]["harness_annotations"]["event_annotations"]:
            ref = row["ref"]
            line, expected_turn = original[ref["event"], ref["line"]]
            assert row["turn"] == expected_turn
            assert row["kind"] == line.split("|")[1]
            if row.get("hp_after") and row["kind"] != "faint":
                assert row["hp_after"]["raw"] in line
            if row.get("hp_before_ref") and row.get("hp_before"):
                before = row["hp_before_ref"]
                previous_line = original[before["event"], before["line"]][0]
                assert row["hp_before"]["raw"] in previous_line
                assert (before["event"], before["line"]) < (ref["event"], ref["line"])


def test_cloud_requires_manifest_bound_offline_receipt(prepared, tmp_path):
    directory = clone(prepared, tmp_path)
    with pytest.raises(FileNotFoundError):
        run(directory)
    assert not (directory / "cloud-clock.json").exists()


@pytest.mark.parametrize("status,expected", [("incorrect", 0), ("omitted", 1)])
def test_false_required_fact_is_not_conflated_with_omission(status, expected):
    from integration.pokechamp.improved_io.memory import HEADINGS

    text = (
        "<summary>\n# Battle Summary\n"
        + "".join("## " + h + "\n" for h in HEADINGS)
        + "battle_id: b\nactor_id: p1\n[event:1] X fainted.\n</summary>"
    )
    package = {
        "collection_sha256": "c",
        "manifest_sha256": "m",
        "responses": [{"blind_id": "R0", "scene": 0, "text": text, "response_sha256": "r"}],
        "references": {
            "0": {
                "identity": {"battle_id": "b", "actor_id": "p1"},
                "source_events": [{"event_seq": 1, "protocol": "|-damage|p1a: X|1/100"}],
                "facts": [{"id": "alive"}],
            }
        },
    }
    audit = {
        "collection_sha256": "c",
        "manifest_sha256": "m",
        "calls": {
            "R0": {
                "response_sha256": "r",
                "facts": {"alive": {"retained": False, "status": status, "quote": ""}},
                "errors": [
                    {
                        "kind": "critical_fact",
                        "quote": "X fainted.",
                        "evidence": [{"event": 1, "line": 1}],
                        "fact_ids": ["alive"],
                        "explanation": "X is alive at HP 1.",
                    }
                ],
                "factual_claims": 1,
                "erroneous_claims": 1,
            }
        },
    }
    result = check_review(package, audit)["R0"]
    assert result["omission"] == expected
    assert result["critical"] == result["primary"] == 1
    assert result["retention"] == 0


def test_weather_upkeep_parser_value_is_not_activation_turn():
    import logging

    from poke_env.environment.battle import Battle
    from poke_env.environment.weather import Weather

    battle = Battle("weather-diagnostic", "p2", logging.getLogger(__name__), 9)
    battle.parse_message("|turn|3".split("|"))
    battle.parse_message("|-weather|SunnyDay|[from] ability: Drought".split("|"))
    assert battle.weather[Weather.SUNNYDAY] == 3
    battle.parse_message("|turn|9".split("|"))
    battle.parse_message("|-weather|SunnyDay|[upkeep]".split("|"))
    assert battle.weather[Weather.SUNNYDAY] == 9
    raw = context(["|turn|3\n|-weather|SunnyDay|[from] ability: Drought\n|turn|4"])
    raw["current_observation"]["weather"] = {k.name: v for k, v in battle.weather.items()}
    numeric = annotate(raw)["numeric_state"]
    weather = next(r for r in numeric if r["path"][1] == "weather")
    assert weather == {
        "path": ["current_observation", "weather", "SUNNYDAY"],
        "raw_value": 9,
        "meaning": "last_weather_protocol_turn",
    }
    battle.parse_message("|-weather|none".split("|"))
    assert battle.weather == {}


@pytest.mark.parametrize("scene,start,last", [(1, 8, 10), (3, 3, 9)])
def test_weather_truth_and_numeric_meaning_against_original_protocol(prepared, scene, start, last):
    reference = b.read_sealed(prepared / "references" / f"s{scene:02}.json")
    events, turn = [], 0
    for event in reference["source_events"]:
        for line in event["protocol"].splitlines():
            if line.startswith("|turn|"):
                turn = int(line.split("|")[2])
            if line.startswith("|-weather|SunnyDay"):
                events.append((turn, "[upkeep]" in line))
    assert events[0] == (start, False) and events[-1] == (last, True)
    fact = next(f for f in reference["facts"] if f["id"] == "sun")
    assert f"sun on turn {start}" in fact["expected"]
    assert f"raw weather value {last}" in fact["expected"]
    for condition in ("H1", "H3"):
        value = b.read_sealed(prepared / "inputs" / f"s{scene:02}-{condition}.json")
        row = next(
            r
            for r in value["context"]["harness_annotations"]["numeric_state"]
            if r["path"][1] == "weather"
        )
        assert row["raw_value"] == last
        assert row["meaning"] == "last_weather_protocol_turn"


def test_invalidated_input_blocks_review_and_resubmission(prepared, tmp_path):
    from integration.pokechamp.summary_diagnostics.runner import inventory

    directory = clone(prepared, tmp_path)
    manifest = verify(directory)
    collection = {**inventory(directory, manifest), "fake": True, "elapsed_seconds": 0}
    b.seal_json(directory / "collection.json", collection)
    failure = {
        "manifest_sha256": b.digest(directory / "manifest.json"),
        "collection_sha256": b.digest(directory / "collection.json"),
        "reviewed_draft": 0,
        "review_pending": 144,
    }
    b.seal_json(directory / "input-transform-failure.json", failure)
    b.seal_json(
        directory / "halt.json",
        {
            "reason": "input_transform_error",
            "evidence": "input-transform-failure.json",
            "evidence_sha256": b.digest(directory / "input-transform-failure.json"),
        },
    )
    with pytest.raises(ValueError, match="halted"):
        run(directory, fake={})
    with pytest.raises(ValueError, match="cannot restore"):
        report(directory, directory / "anything.json")
    result = report(directory)
    assert result["status"] == "invalidated" and not result["complete"]
    assert report(directory) == result
    final = b.read_sealed(directory / "report.json")
    assert final["effect_estimates"] is None and final["valid_reviewed"] == 0
    assert final["paired_scenes"]["additional"]["missing"] == 8
    path = directory / "input-transform-failure.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="evidence mismatch"):
        report(directory)
