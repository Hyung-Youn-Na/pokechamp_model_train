"""합성 EX-072 사본의 원본 무결성과 이동 후 오프라인 확률·리플레이 검사."""

from __future__ import annotations

import json
import shutil

import pytest

from integration.pokechamp.imitation.storage import atomic, sha, write_jsonl
from integration.pokechamp.selfplay import viewer


@pytest.fixture
def source(tmp_path):
    source = tmp_path / "source"
    first = {
        "slot_id": "synthetic-complete",
        "stage": "test",
        "model": "selected",
        "round": 1,
        "pair_id": "synthetic-pair",
        "model_side": "p1",
        "opponent": "initial",
        "simulator_seed": [1, 2, 3, 4],
    }
    second = dict(first, slot_id="synthetic-unattempted", model_side="p2")
    outcomes = [
        dict(first, status="completed", result="win", turns=2),
        dict(second, status="unattempted", result=None, turns=0),
    ]
    atomic(
        source / "manifest.json",
        {"experiment_id": "EX-072", "schedule": [first, second], "synthetic": True},
    )
    atomic(source / "result.json", {"outcomes": outcomes})
    atomic(
        source / "report.md",
        "합성 CPU 검사 전용. 실제 실험 결과가 아닙니다.\n".encode(),
    )
    records, events = [], []
    for key, criteria, automatic in (
        ("automatic", {"move:a": "Tackle"}, True),
        ("model-call", {"move:a": "Tackle", "move:b": "Flamethrower </script>"}, False),
    ):
        body = {
            "state": json.dumps({"snapshot": {"turn": 1, "decision_kind": "move"}}),
            "questions": {"action": {"criteria": criteria}},
        }
        events.append(
            {
                "type": "input",
                "decision": key,
                "body": body,
                "body_json": json.dumps(body),
                "input_sha256": "synthetic-input",
                "boundary": {},
                "observation_identity": {},
                "commands": {},
            }
        )
        if not automatic:
            response = {
                "action_ids": list(criteria),
                "probabilities": {"move:a": 0.25, "move:b": 0.75},
                "wdl_probabilities": [[0.8, 0.1, 0.1], [0.2, 0.3, 0.5]],
            }
            events.append({"type": "response", "decision": key, "body": response})
            records.append(
                {
                    "slot_id": first["slot_id"],
                    "decision_id": first["slot_id"] + ":" + key,
                    "action_ids": list(criteria),
                    "choice": "move:b",
                    "wdl_before": [0.2, 0.3, 0.5],
                    "wdl_after": [0.3, 0.3, 0.4],
                    "outcome": "W",
                    "model_version": "synthetic",
                }
            )
        choice = "move:a" if automatic else "move:b"
        events.append(
            {
                "type": "selection",
                "decision": key,
                "automatic": automatic,
                "choice": choice,
            }
        )
        events.append(
            {
                "type": "wire",
                "decision": key,
                "command": "/choose move " + ("1" if automatic else "2"),
            }
        )
    events.append(
        {
            "type": "protocol",
            "protocol": "|player|p1|Learner\n|player|p2|Opponent\n"
            "|request|private\n|turn|1\n|move|p1a: Test|Tackle|p2a: Test\n"
            "|turn|2\n|move|p1a: Test|Flamethrower|p2a: Test\n|win|Learner\n",
        }
    )
    write_jsonl(source / "games" / first["slot_id"] / "events.jsonl", events)
    write_jsonl(source / "decisions.jsonl", records)
    viewer._seal(source)
    return source


def test_export_preserves_source_seal_and_all_scheduled_slots(source, tmp_path):
    before = viewer.verify_source(source)
    output = tmp_path / "export"
    receipt = viewer.export(source, output)
    assert receipt["planned"] == 2 and receipt["completed"] == 1
    assert viewer.verify_source(source) == before
    data = json.loads((output / "battle-001" / "decisions.json").read_text())
    assert data["decisions"][0]["action_probabilities"] == {}
    selected = data["decisions"][1]
    assert selected["action_probabilities"]["move:b"] == 0.75
    assert selected["wdl_probabilities"]["move:b"] == [0.2, 0.3, 0.5]
    assert selected["recorded_prediction"]["wdl_after"] == [0.3, 0.3, 0.4]
    assert "|request|" not in (output / "battle-001/showdown.log").read_text()
    assert "승리 확률" in (output / "battle-001/index.html").read_text()
    assert (
        "Flamethrower </script>" not in (output / "battle-001/index.html").read_text()
    )
    provenance = json.loads((output / "provenance.json").read_text())
    assert provenance["source_files"] == before
    assert provenance["copied_files"]["result.json"] == sha(source / "result.json")
    with pytest.raises(FileExistsError):
        viewer.export(source, output)
    with pytest.raises(ValueError, match="source tree"):
        viewer.export(source, source / "mutating-export")


def test_viewer_rejects_unsealed_extra_source_file(source, tmp_path):
    (source / "extra.txt").write_text("unsealed")
    with pytest.raises(ValueError, match="complete experiment"):
        viewer.export(source, tmp_path / "bad")


def test_viewer_rejects_tampered_and_missing_normal_game_evidence(source, tmp_path):
    path = source / "games/synthetic-complete/events.jsonl"
    path.write_text("")
    with pytest.raises(ValueError, match="seal entry"):
        viewer.export(source, tmp_path / "tampered")
    (source / "checksums.sha256").unlink()
    viewer._seal(source)
    with pytest.raises(ValueError, match="no stored battle events"):
        viewer.export(source, tmp_path / "missing")


def test_terminal_and_turn_counts_are_checked_against_public_replay():
    protocol = "|player|p1|Left\n|player|p2|Right\n|turn|3\n|win|Left\n"
    outcome = {"status": "completed", "model_side": "p1", "result": "win", "turns": 3}
    viewer._validate_protocol(protocol, outcome)
    with pytest.raises(ValueError, match="turn count"):
        viewer._validate_protocol(protocol, dict(outcome, turns=4))
    with pytest.raises(ValueError, match="result differs"):
        viewer._validate_protocol(protocol, dict(outcome, result="loss"))
    with pytest.raises(ValueError, match="one recorded terminal"):
        viewer._validate_protocol(protocol.replace("|win|Left", ""), outcome)


def test_moved_export_offline_probability_navigation_payloads_and_replay(
    source, tmp_path
):
    playwright = pytest.importorskip("playwright.sync_api")
    original, moved = tmp_path / "original", tmp_path / "independent" / "ex072"
    viewer.export(source, original)
    shutil.copytree(original, moved)
    expected = json.loads((moved / "battle-001/decisions.json").read_text())
    with playwright.sync_playwright() as work:
        browser = work.chromium.launch(headless=True)
        try:
            context = browser.new_context(offline=True)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto((moved / "index.html").as_uri(), wait_until="domcontentloaded")
            assert page.locator("tbody tr").count() == 2
            page.goto(
                (moved / "battle-001/index.html").as_uri(),
                wait_until="domcontentloaded",
            )
            assert "모델 미호출" in page.locator("#mode").inner_text()
            assert "미호출/미수신" in page.locator("#candidates").inner_text()
            page.locator("#next").click()
            assert page.locator("#candidates tr.selected").count() == 1
            columns = page.locator("#candidates tr.selected td").all_text_contents()
            assert columns[2:6] == ["75.000%", "20.000%", "30.000%", "50.000%"]
            assert (
                json.loads(page.locator("#input").inner_text())
                == expected["decisions"][1]["input"]
            )
            assert (
                json.loads(page.locator("#response").inner_text())
                == expected["decisions"][1]["response"]
            )
            assert page.locator("#response .json-number").count() > 0
            with page.expect_download() as download:
                page.locator("#download").click()
            assert download.value.suggested_filename == "decision-2.json"
            page.locator("body").click(position={"x": 2, "y": 2})
            page.keyboard.press("ArrowLeft")
            assert page.locator("#decision").input_value() == "0"
            frame = page.frame_locator("iframe")
            assert "|win|Learner" not in frame.locator("#protocol").inner_text()
            frame.locator("#next-turn").click()
            assert "|turn|1" in frame.locator("#protocol").inner_text()
            frame.locator("#next-turn").click()
            assert "|win|Learner" in frame.locator("#protocol").inner_text()
            frame.locator("#play").click()
            page.wait_for_timeout(1550)
            assert "|win|Learner" in frame.locator("#protocol").inner_text()
            assert not errors
            context.close()
        finally:
            browser.close()


def test_reusable_browser_verifier_checks_all_normal_pages_and_nonargmax(
    source, tmp_path
):
    pytest.importorskip("playwright.sync_api")
    first_events_path = source / "games/synthetic-complete/events.jsonl"
    first_events = [
        json.loads(line) for line in first_events_path.read_text().splitlines()
    ]
    second_events = json.loads(json.dumps(first_events))
    for event in first_events:
        if event.get("decision") == "model-call":
            if event["type"] == "selection":
                event["choice"] = "move:a"
            elif event["type"] == "wire":
                event["command"] = "/choose move 1"
    records = [
        json.loads(line)
        for line in (source / "decisions.jsonl").read_text().splitlines()
    ]
    second_record = dict(
        records[0],
        slot_id="synthetic-unattempted",
        decision_id="synthetic-unattempted:model-call",
        outcome="L",
    )
    records[0].update(choice="move:a", wdl_before=[0.8, 0.1, 0.1])
    records.append(second_record)
    result = json.loads((source / "result.json").read_text())
    result["outcomes"][1].update(status="completed", result="loss", turns=2)
    write_jsonl(first_events_path, first_events)
    write_jsonl(source / "games/synthetic-unattempted/events.jsonl", second_events)
    write_jsonl(source / "decisions.jsonl", records)
    atomic(source / "result.json", result)
    (source / "checksums.sha256").unlink()
    viewer._seal(source)
    before = viewer.verify_source(source)
    output = tmp_path / "actual-export"
    receipt = viewer.export(source, output)
    receipt_path = tmp_path / "export-receipt.json"
    atomic(receipt_path, receipt)
    verification = viewer.verify_browser(source, output, receipt_path)
    assert verification["passed"]
    assert verification["completed"] == verification["checked_completed_pages"] == 2
    assert verification["checked_decisions"] == 4
    assert (
        verification["checked_nonargmax_decisions"]
        == verification["available_nonargmax_decisions"]
        == 1
    )
    assert {row["slot_id"] for row in verification["pages"]} == {
        row["slot_id"] for row in result["outcomes"]
    }
    assert all(
        page["replay"]["timer_playback_verified"] for page in verification["pages"]
    )
    assert verification["source_unchanged"] and verification["export_unchanged"]
    assert verification["moved_copy_verified"] and verification["offline"]
    assert (
        not verification["external_requests"] and not verification["javascript_errors"]
    )
    assert viewer.verify_source(source) == before


def test_reusable_browser_verifier_rejects_wrong_export_receipt_before_launch(
    source, tmp_path
):
    output = tmp_path / "export"
    receipt = viewer.export(source, output)
    receipt["export_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="receipt seal differs"):
        viewer.verify_browser(source, output, receipt)
