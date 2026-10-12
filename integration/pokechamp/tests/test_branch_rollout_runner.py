"""Admission/error accounting without executing the archived game."""
import json
import time
from concurrent.futures import Future

import pytest

from integration.pokechamp.branch_rollouts import runner
from integration.pokechamp.branch_rollouts.common import file_hash, read, rows, write


def test_collection_drains_all_admitted_results_after_error(tmp_path, monkeypatch):
    identity = {"fixture": "unchanged"}
    write(tmp_path / "reconstruction.json", {"passed": True, "source_identity": identity, "anchors": []})
    reconstruction_hash = file_hash(tmp_path / "reconstruction.json")
    write(tmp_path / "manifest.json", {"source_hashes": {}, "reconstruction_sha256": reconstruction_hash})
    write(tmp_path / "validation.json", {"passed": True, "source_identity": identity,
                                         "completed_roots": 22, "reconstruction_sha256": reconstruction_hash})
    anchors = [dict(anchor_id=f"a{i:03}", phase=phase, actions=[dict(action_id="x", command="move 1")])
               for i, phase in enumerate(("lead", "turn_action", "forced_switch") + ("turn_action",) * 19)]
    anchors[-1]["actions"] += [dict(action_id=f"x{i}", command="move 1") for i in range(145)]
    (tmp_path / "anchors.jsonl").write_text("\n".join(map(json.dumps, anchors)) + "\n")
    monkeypatch.setattr(runner, "code_identity", lambda: identity)
    monkeypatch.setattr(runner, "verify_source", lambda *_: {})

    class Pool:
        def __init__(self, **kwargs):
            assert kwargs["max_workers"] == 4

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def submit(self, function, task):
            f = Future()
            if task["anchor"]["anchor_id"] == "a000":
                f.set_exception(RuntimeError("worker crashed"))
            else:
                f.set_result(dict(anchor_id=task["anchor"]["anchor_id"], action_id="x", replicate=0,
                                  attempt_id=task["attempt_id"], status="win"))
            return f

    monkeypatch.setattr(runner, "ProcessPoolExecutor", Pool)
    with pytest.raises(RuntimeError, match="Branch error"):
        runner.collect(tmp_path)
    records = rows(tmp_path / "rollouts.jsonl")
    assert len(records) == read(tmp_path / "ledger.json")["attempts"] == 3
    assert sorted(r["status"] for r in records) == ["error", "win", "win"]
    assert read(tmp_path / "manifest.json")["status"] == "incomplete"
    assert not (tmp_path / "collection-gate.json").exists()


@pytest.mark.parametrize("expired", [False, True])
def test_setup_failure_and_expired_deadline_have_rows_and_traces(tmp_path, expired):
    record = runner.rollout_task(dict(directory=str(tmp_path), anchor={"anchor_id": "a000", "phase": "lead"},
                                      action={"action_id": "x", "command": "team 123456"}, replicate=0,
                                      attempt_id=1, deadline=time.time() + (-1 if expired else 100)))
    assert record["status"] == ("censored" if expired else "error")
    assert (tmp_path / record["trace_path"]).is_file()
    assert record["elapsed_seconds"] >= 0
