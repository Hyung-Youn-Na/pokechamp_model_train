"""No-battle fixtures for immutable branch provenance and final export sealing."""
import json
from pathlib import Path

import pytest

from integration.pokechamp.branch_rollouts import audit
from integration.pokechamp.branch_rollouts.common import derive_seed, digest, file_hash, gzwrite, write


def fixture(tmp_path, monkeypatch):
    directory = tmp_path / "data"
    directory.mkdir()
    code = tmp_path / "code.py"
    code.write_text("# frozen fixture\n")
    identity = {"code.py": file_hash(code)}
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "code_identity", lambda: identity)
    monkeypatch.setattr(audit, "verify_source", lambda expected: expected)
    observation = {"state": {"self_team": [], "opponent_team": []}, "questions": {"action": {"criteria": {"a": {}, "b": {}}}}}
    anchor = dict(anchor_id="r", decision_id="old", turn=0, phase="lead", observation=observation,
                  actions=[dict(action_id=k, command="team " + order, description={}) for k, order in [("a", "123456"), ("b", "213456")]],
                  original_action_id="a")
    monkeypatch.setattr(audit, "_original_inputs", lambda manifest, anchors: {"old": {"payload": observation,
                        "commands": {a["action_id"]: "/" + a["command"] for a in anchor["actions"]}}})
    root = dict(anchor_id="r", simulator={"state": "opaque"}, canonical_observation=observation)
    gzwrite(directory / "private/r.json.gz", root)
    receipt = dict(anchor_id="r", root_path="private/r.json.gz", root_sha256=file_hash(directory / "private/r.json.gz"),
                   root_sha256_canonical=digest(root["simulator"]), request_matched=True, protocol_matched=True, candidates_matched=True)
    write(directory / "reconstruction.json", dict(passed=True, source_identity=identity, anchors=[receipt]))
    write(directory / "validation.json", dict(passed=True, source_identity=identity, completed_roots=1,
          reconstruction_sha256=file_hash(directory / "reconstruction.json")))
    write(directory / "manifest.json", dict(experiment_id="EX-060", expected_repetitions=1, planned_rollouts=2,
          source_hashes={"source": "hash"}, collection_source=identity,
          reconstruction_sha256=file_hash(directory / "reconstruction.json"), validation_sha256=file_hash(directory / "validation.json")))
    (directory / "anchors.jsonl").write_text(json.dumps(anchor) + "\n")
    row = dict(anchor_id="r", action_id="a", replicate=0, attempt_id=1, status="win", turns=1, elapsed_seconds=0.1,
               simulator_seed=derive_seed("r", 0, "simulator"), actor_seeds={s: derive_seed("r", 0, s) for s in ("p1", "p2")},
               root_opponent_choice="team 654321", trace_path="traces/one.json.gz")
    trace = dict(public_log=["|player|p1|one|", "|player|p2|two|", "|win|two"],
                 choices=[dict(turn=0, choices={"p1": "team 654321", "p2": "team 123456"})], result=dict(row))
    gzwrite(directory / row["trace_path"], trace)
    row["trace_sha256"] = file_hash(directory / row["trace_path"])
    (directory / "rollouts.jsonl").write_text(json.dumps(row) + "\n")
    (directory / "attempts.jsonl").write_text(json.dumps(dict(number=1, kind="rollout", identity=["r", "a", 0])) + "\n")
    write(directory / "ledger.json", dict(attempts=1, maximum_attempts=6000))
    return directory, row, trace


def test_partial_finalize_seals_sources_and_portable_public_outputs(tmp_path, monkeypatch):
    directory, _, _ = fixture(tmp_path, monkeypatch)
    result = audit.finalize(directory, tmp_path / "viewer")
    assert result["technical_pass"] and not result["collection_complete"] and result["coverage"] == "partial"
    assert result["planned"] == 2 and result["attempted"] == 1 and result["unattempted"] == 1
    for root in (directory, tmp_path / "viewer"):
        for line in (root / "checksums.sha256").read_text().splitlines():
            checksum, name = line.split("  ", 1)
            assert file_hash(root / name) == checksum
    assert (directory / "frozen-source/code.py").read_text() == "# frozen fixture\n"


@pytest.mark.parametrize("defect,match", [("seed", "seed differs"), ("action", "forced p2"), ("private", "private protocol"),
                                         ("root", "root changed"), ("missing", "no outcome")])
def test_audit_rejects_corruption_and_missing_results(tmp_path, monkeypatch, defect, match):
    directory, row, trace = fixture(tmp_path, monkeypatch)
    if defect == "seed":
        row["simulator_seed"] = [0, 0, 0, 0]
    elif defect == "action":
        trace["choices"][0]["choices"]["p2"] = "team 213456"
    elif defect == "private":
        trace["public_log"].append('|request|{"private":true}')
    elif defect == "root":
        (directory / "private/r.json.gz").write_bytes(b"tampered")
    elif defect == "missing":
        (directory / "rollouts.jsonl").write_text("")
    if defect in {"action", "private"}:
        gzwrite(directory / row["trace_path"], trace)
        row["trace_sha256"] = file_hash(directory / row["trace_path"])
    if defect != "missing":
        (directory / "rollouts.jsonl").write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match=match):
        audit.finalize(directory, tmp_path / "viewer")
    assert json.loads((directory / "audit.json").read_text())["technical_pass"] is False
