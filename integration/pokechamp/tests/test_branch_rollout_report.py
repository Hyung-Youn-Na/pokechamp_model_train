"""독립 분모·복구·대응 통계와 학습/뷰어 정보 경계 검증."""
import gzip
import json
import re

import pytest

from integration.pokechamp.branch_rollouts.report import export_report, summarize, training_rows, wilson_interval


def data(repetitions=32):
    manifest = {"experiment_id": "EX060", "expected_repetitions": repetitions, "planned_rollouts": 2 * repetitions,
                "source_refs": ["EX-058/battle-19"], "private_snapshot": "never-export"}
    anchors = [{"anchor_id": "root1", "decision_id": "decision1", "turn": 1, "phase": "turn_action",
                "observation": {"state": {"self_team": [{"item": "Choice Specs"}], "opponent_team": [{"item": "unknown"}]},
                                "questions": {"action": {"type": "choice"}}},
                "actions": [{"action_id": "a", "command": "/choose move 1", "description": {"slot": 1}},
                            {"action_id": "b", "command": "/choose move 2", "private_snapshot": "never-export"}],
                "original_action_id": "a", "private_snapshot": "never-export", "seed": 42}]
    rows = [{"anchor_id": "root1", "action_id": action, "replicate": rep, "attempt_id": f"{action}-{rep}",
             "status": status, "turns": 10, "elapsed_seconds": 0.1, "seed": 123}
            for action, status in [("a", "loss"), ("b", "win")] for rep in range(repetitions)]
    return manifest, anchors, rows


def test_complete_values_wilson_and_paired_original_delta():
    manifest, anchors, rows = data()
    rows[0]["status"] = "draw"
    summary = summarize(manifest, anchors, list(reversed(rows)))
    assert summary["planned"] == summary["attempted"] == summary["terminal"] == 64
    assert summary["collection_complete"]
    root = summary["roots"][0]
    a, b = root["values"]
    assert a["p_win"] == 0 and a["q_score"] == 0.5 / 32
    assert a["delta_original_q"] == 0 and b["delta_original_q"] == 1 - 0.5 / 32
    assert b["paired_repetitions"] == 32
    assert b["p_win_wilson95"][0] == pytest.approx(0.8928208017)
    assert root["empirical_best_action_ids"] == ["b"] and root["certified_best_action_id"] is None


def test_incomplete_no_scores_no_root_ranking_and_no_failure_as_loss():
    manifest, anchors, rows = data()
    rows[0]["status"] = "censored"
    rows[1]["status"] = "error"
    rows[2]["status"] = "aborted"
    rows.pop(3)
    summary = summarize(manifest, anchors, rows)
    a, b = summary["roots"][0]["values"]
    assert summary["unattempted"] == 1 and summary["terminal"] == 60
    assert a["loss"] == 28 and a["censored"] == a["error"] == a["aborted"] == 1
    assert a["p_win"] is a["q_score"] is a["p_win_wilson95"] is None
    assert b["p_win"] == 1 and b["delta_original_q"] is None
    assert summary["roots"][0]["empirical_best_action_ids"] == []
    assert not summary["collection_complete"]


def test_explicit_supersession_preserves_physical_attempts_and_statuses():
    manifest, anchors, rows = data(1)
    rows[0]["status"] = "error"
    replacement = dict(rows[0], attempt_id="a-replacement", status="win", supersedes_attempt_id="a-0")
    summary = summarize(manifest, anchors, rows + [replacement])
    assert summary["physical_attempts"] == 3 and summary["attempted"] == 2
    assert summary["physical_status_counts"]["error"] == 1 and summary["status_counts"]["error"] == 0
    assert summary["superseded_attempt_ids"] == ["a-0"]
    assert summary["roots"][0]["empirical_best_action_ids"] == ["a", "b"]
    bad = dict(replacement)
    bad.pop("supersedes_attempt_id")
    with pytest.raises(ValueError, match="duplicate rollout"):
        summarize(manifest, anchors, rows + [bad])
    with pytest.raises(ValueError, match="current attempt"):
        summarize(manifest, anchors, [replacement])


@pytest.mark.parametrize("change,error", [
    ({"replicate": 32}, "replicate"), ({"replicate": True}, "replicate"),
    ({"action_id": "unknown"}, "unknown anchor"), ({"status": "timeout"}, "unknown rollout"),
    ({"attempt_id": ""}, "attempt_id"),
])
def test_invalid_census_rejected(change, error):
    manifest, anchors, rows = data()
    rows[0].update(change)
    with pytest.raises(ValueError, match=error):
        summarize(manifest, anchors, rows)


def test_duplicate_anchor_and_manifest_mismatch_rejected():
    manifest, anchors, rows = data()
    with pytest.raises(ValueError, match="anchor_id"):
        summarize(manifest, anchors + anchors, rows)
    manifest["planned_rollouts"] += 1
    with pytest.raises(ValueError, match="coverage"):
        summarize(manifest, anchors, rows)


def test_training_export_whitelist_and_observation_privacy_guard():
    manifest, anchors, rows = data()
    result = training_rows(manifest, anchors, summarize(manifest, anchors, rows))
    text = json.dumps(result)
    assert "never-export" not in text and '"seed"' not in text and "trace_path" not in text
    assert result[0]["observation"]["state"]["self_team"][0]["item"] == "Choice Specs"
    anchors[0]["observation"]["state"]["nested"] = [{"future_seed": 123}]
    with pytest.raises(ValueError, match="privileged field"):
        training_rows(manifest, anchors, summarize(manifest, anchors, rows))


def write_collection(path, manifest, anchors, rows):
    path.mkdir()
    (path / "manifest.json").write_text(json.dumps(manifest))
    for name, values in [("anchors.jsonl", anchors), ("rollouts.jsonl", rows)]:
        (path / name).write_text(''.join(json.dumps(v) + '\n' for v in values))


def test_export_portable_escaped_viewer_only_public_trace(tmp_path):
    manifest, anchors, rows = data(1)
    unsafe = '<script>alert("unsafe")</script>'
    anchors[0]["observation"]["state"]["public_text"] = unsafe
    rows[0].update(trace_path="branch.json.gz", elapsed_seconds=unsafe)
    source, viewer = tmp_path / "source", tmp_path / "viewer"
    write_collection(source, manifest, anchors, rows)
    with gzip.open(source / "branch.json.gz", "wt") as stream:
        json.dump({"public_log": ["|player|p1|one|", "|player|p2|two|", "|turn|1", "|win|one"],
                   "choices": ["hidden-choice"], "private_snapshot": "SECRET_INTERNAL"}, stream)
    result = export_report(source, viewer_directory=viewer)
    assert result["viewer_export"]["replays"] == 1
    anchor_html = next((viewer / "anchors").glob("*.html")).read_text()
    assert unsafe not in anchor_html and "&lt;script&gt;" in anchor_html
    replay_html = next((viewer / "replays").glob("*.html")).read_text()
    assert "SECRET_INTERNAL" not in replay_html and "hidden-choice" not in replay_html
    assert "|win|one" in replay_html and "오프라인" in replay_html
    assert "수집 완료" in (source / "report.md").read_text()
    assert not list(viewer.rglob("*.gz"))
    copied = tmp_path / "moved"
    viewer.rename(copied)
    assert (copied / "index.html").exists()
    for page in [copied / "index.html", *list((copied / "anchors").glob("*.html"))]:
        for href in re.findall(r'href="([^"]+)"', page.read_text()):
            assert (page.parent / href).exists()


@pytest.mark.parametrize("trace,match", [("../outside.json", "escapes"), ("private.json", "private protocol")])
def test_replay_rejects_external_path_and_private_protocol(tmp_path, trace, match):
    manifest, anchors, rows = data(1)
    rows[0]["trace_path"] = trace
    source = tmp_path / "source"
    write_collection(source, manifest, anchors, rows)
    (source / "private.json").write_text(json.dumps({"public_log": ["|request|{secret}"]}))
    with pytest.raises(ValueError, match=match):
        export_report(source, viewer_directory=tmp_path / "viewer")


def test_wilson_all_losses_and_no_attempts():
    interval = wilson_interval(0, 32)
    assert interval[0] == 0 and interval[1] == pytest.approx(0.1071791983)
    manifest, anchors, _ = data()
    summary = summarize(manifest, anchors, [])
    assert summary["physical_attempts"] == 0 and summary["unattempted"] == 64
    assert not summary["collection_complete"]


def test_integer_attempt_ids_and_prepared_source_reference():
    manifest, anchors, rows = data(1)
    rows[0]["attempt_id"], rows[1]["attempt_id"] = 2, 3
    manifest.pop("source_refs")
    manifest.update(source_experiment="EX-058", source_slot="b02-r3-s0", source_directory="archive",
                    source_hashes={"events.jsonl": "abcdef", "private/state": "not-exported"})
    summary = summarize(manifest, anchors, rows)
    refs = training_rows(manifest, anchors, summary)[0]["provenance"]["source_refs"]
    assert refs[0]["source_files"] == {"events.jsonl": "abcdef"}
    assert refs[0]["slot"] == "b02-r3-s0"


def test_reserved_missing_outcomes_not_silently_unattempted():
    manifest, anchors, rows = data(1)
    rows[0]["attempt_id"], rows[1]["attempt_id"] = 2, 3
    reservations = [{"number": 1, "kind": "reconstruct", "identity": "gate"},
                    {"number": 2, "kind": "rollout", "identity": ["root1", "a", 0]},
                    {"number": 3, "kind": "rollout", "identity": ["root1", "b", 0]}]
    summary = summarize(manifest, anchors, rows[:1], attempts=reservations)
    assert summary["physical_attempts"] == summary["attempted"] == 2
    assert summary["recorded_attempts"] == 1 and summary["unattempted"] == 0
    assert summary["missing_result_attempt_ids"] == ["3"]
    assert summary["roots"][0]["values"][1]["missing_result_branches"] == 1
    assert not summary["collection_complete"]
    with pytest.raises(ValueError, match="matching reservation"):
        summarize(manifest, anchors, rows, attempts=reservations[:-1])
