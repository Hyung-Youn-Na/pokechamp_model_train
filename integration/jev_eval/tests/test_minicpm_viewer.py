"""EX-091 saved calculations and its shared five-screen offline verification."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from integration.jev27b.study import seal, verify_seal, write_json
from integration.jev_eval import damage_data, viewer
from integration.jev_eval.config import DISK_BYTES
from integration.jev_eval.tests.test_damage_viewer import add_damage
from integration.jev_eval.tests.test_viewer import viewer_collection


def minicpm_collection(path):
    source = viewer_collection(path, experiment="EX-091")
    events = [json.loads(line) for line in (source / "events.jsonl").read_text().splitlines()]
    for event in events:
        body = event.get("payload") if event["type"] == "input" else event.get("body")
        if not isinstance(body, dict) or body.get("state", {}).get("decision_kind") != "turn_action":
            continue
        state = body["state"]
        state["self_team"][0]["current_move_slots"][0]["damage"] = dict(
            target_species="Snorlax", ranges=dict(current=[0, 0], self_tera=[1.25, 2.5],
                opponent_tera=None, both_tera=[10, 20]), reason=dict(opponent_tera="fixture_unknown"))
        state["opponent_team"][1]["moves"][0]["damage"] = dict(
            target_species="Pikachu", ranges=None, reason="fixture_unavailable")
    (source / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    add_damage(source)
    return source


def test_minicpm_export_binds_every_saved_calculation_without_recalculation(tmp_path, monkeypatch):
    from integration.pokechamp.diagnostics import jev_damage
    def forbidden(*args, **kwargs):
        raise AssertionError("viewer must not start a damage calculator")
    monkeypatch.setattr(jev_damage.Engine, "__init__", forbidden)
    source = minicpm_collection(tmp_path / "source")
    original_seal = (source / "checksums.sha256").read_bytes()
    output = tmp_path / "export"
    checked = viewer.export(source, output, compared={"baseline": "EX-089"})
    assert checked["damage_decisions"] == checked["decisions"] == 4
    assert checked["damage_calculations"] == 110
    assert checked["all_originals_compared"] and checked["all_public_rows_and_cutoffs_compared"]
    data = json.loads((output / "battle-1/decisions.json").read_text())
    assert list(data["damage_index"]) == [d["id"] for d in data["decisions"]]
    entries = damage_data.input_events(json.loads(line) for line in (source / "events.jsonl").read_text().splitlines())
    for d in data["decisions"]:
        assert damage_data.read_script(output / "battle-1" / data["damage_index"][d["id"]]["src"]) == (
            damage_data.read_packet(source, "EX-091", entries[d["id"]]))
    assert data["decisions"][2]["automatic"] and data["decisions"][2]["request"] is None
    provenance = json.loads((output / "provenance.json").read_text())
    assert provenance["display_version"] == damage_data.VERSION
    assert provenance["damage"]["saved_only"] and provenance["damage"]["recalculations"] == 0
    assert provenance["damage"]["decisions"] == 4
    index = (output / "index.html").read_text()
    assert "MiniCPM5-2B-Jev" in index and "EX-089" in index and "EX-083" not in index
    assert "18.75%" in index and "모델 전용 입력 형식·GPU 배치" in index
    assert "Damage-calc" in index
    assert (source / "checksums.sha256").read_bytes() == original_seal
    verify_seal(source)


@pytest.mark.parametrize("change", ["provenance", "index", "saved_packet"])
def test_minicpm_verification_rejects_missing_or_changed_saved_damage(tmp_path, change):
    source = minicpm_collection(tmp_path / "source")
    output = tmp_path / "export"
    viewer.export(source, output)
    if change == "provenance":
        target = output / "provenance.json"
        value = json.loads(target.read_text())
        value.pop("display_version")
        write_json(target, value)
    else:
        target = output / "battle-1/decisions.json"
        value = json.loads(target.read_text())
        if change == "index":
            value.pop("damage_index")
            write_json(target, value)
            (target.parent / "index.html").write_text(viewer.render_data(value))
        else:
            packet_path = target.parent / value["damage_index"]["model-2"]["src"]
            packet = damage_data.read_script(packet_path)
            packet["damage"]["calculations"].reverse()
            packet_path.write_text(damage_data.script_text(packet))
    seal(output)
    with pytest.raises(ValueError, match="saved-only|missing a battle|scenarios/conditions/results/order"):
        viewer.verify_data(source, output)


def test_minicpm_browser_checks_saved_damage_within_the_same_five_screens(tmp_path):
    pytest.importorskip("playwright.sync_api")
    source = minicpm_collection(tmp_path / "source")
    output = tmp_path / "export"
    viewer.export(source, output)
    # A measured total over the old limit is valid only for this experiment.
    checked = viewer.verify_browser(output, resource_check=lambda **kwargs: DISK_BYTES + 1)
    assert checked["passed"] and checked["offline_relocated"]
    assert set(checked["representative_screens"]) == {"normal", "automatic", "failure", "public_bench", "turn_log"}
    assert checked["damage_screens_checked"] == 5 and checked["synthetic_failure_fixture"]
    assert checked["disk_limit_bytes"] is None
    assert checked["disk_bytes_with_temporary_copy"] > DISK_BYTES
    assert checked["temporary_filesystem_free_bytes_before_copy"] > 0
    screens = {row["screen"]: row for row in checked["saved_damage_checks"]}
    assert screens["normal"]["calculations"] == 55 and screens["normal"]["filters_checked"]
    assert screens["automatic"]["status"] == "not_calculated"
    assert screens["failure"]["synthetic"] and screens["failure"]["status"] == "available"
    assert all(row["exact_json_copy_download"] for row in screens.values())
    assert not checked["browser_errors"]


def test_minicpm_failure_before_input_has_a_single_empty_damage_screen(tmp_path):
    pytest.importorskip("playwright.sync_api")
    source = viewer_collection(tmp_path / "source", experiment="EX-091", before_input_failure=True)
    output = tmp_path / "export"
    assert viewer.export(source, output)["damage_decisions"] == 0
    checked = viewer.verify_browser(output, resource_check=lambda **kwargs: 0)
    assert checked["representative_screens"] == ["failure"]
    assert checked["saved_damage_checks"][0]["status"] == "no_decision"
    assert not checked["synthetic_failure_fixture"]


@pytest.mark.parametrize("experiment", ["EX-089", "EX-090"])
def test_older_viewer_temporary_copies_keep_the_logical_disk_limit(tmp_path, experiment):
    pytest.importorskip("playwright.sync_api")
    source = viewer_collection(tmp_path / "source", experiment=experiment)
    output = tmp_path / "export"
    viewer.export(source, output)
    with pytest.raises(ValueError, match="would exceed disk budget"):
        viewer.verify_browser(output, resource_check=lambda **kwargs: DISK_BYTES)


def test_minicpm_unlimited_disk_still_rejects_physical_copy_shortage(tmp_path, monkeypatch):
    pytest.importorskip("playwright.sync_api")
    source = minicpm_collection(tmp_path / "source")
    output = tmp_path / "export"
    viewer.export(source, output)
    monkeypatch.setattr(viewer.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(OSError, match="physical free space"):
        viewer.verify_browser(output, resource_check=lambda **kwargs: DISK_BYTES + 1)
