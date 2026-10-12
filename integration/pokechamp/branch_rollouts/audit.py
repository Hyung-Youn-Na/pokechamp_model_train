"""EX-060 분기 원장·정보 경계·보존을 감사하고 최종 산출물을 봉인한다."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .common import ROOT, SOURCE, code_identity, derive_seed, digest, file_hash, gzread, read, rows, verify_source, write
from .report import _assert_model_boundary, _public_log, export_report, summarize, training_rows


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _inside(directory, relative):
    path = (directory / relative).resolve()
    _require(path.is_relative_to(directory.resolve()), "artifact path escapes dataset")
    _require(path.is_file() and not (directory / relative).is_symlink(), "artifact missing or symlinked")
    return path


def _original_inputs(manifest, anchors):
    """Inspect sealed historical inputs, never a privately reconstructed substitute."""
    decisions = {anchor["decision_id"] for anchor in anchors}
    result = {}
    with (SOURCE / "events.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("type") == "input" and row.get("decision") in decisions:
                _require(row["decision"] not in result, "duplicate original decision")
                result[row["decision"]] = row
    _require(set(result) == decisions, "original decisions missing")
    return result


def audit_dataset(directory):
    """Read-only audit, including partial collection; no simulator or model calls."""
    directory = Path(directory)
    manifest = read(directory / "manifest.json")
    source_preserved = verify_source(manifest["source_hashes"])
    identity = code_identity()
    _require(manifest.get("collection_source") == identity, "collection source identity differs")
    reconstruction = read(directory / "reconstruction.json")
    validation = read(directory / "validation.json")
    _require(reconstruction.get("passed") is True, "reconstruction did not pass")
    _require(validation.get("passed") is True, "validation did not pass")
    for name, receipt in (("reconstruction", reconstruction), ("validation", validation)):
        _require(receipt.get("source_identity") == identity, f"{name} source identity differs")
        expected = manifest.get(name + "_sha256")
        if name == "reconstruction":
            _require(bool(expected), "reconstruction receipt hash missing")
        if expected:
            _require(file_hash(directory / f"{name}.json") == expected, f"{name} receipt hash differs")
    anchors = rows(directory / "anchors.jsonl")
    _require(validation.get("completed_roots") == len(anchors), "validation root coverage differs")
    _require(validation.get("reconstruction_sha256") == file_hash(directory / "reconstruction.json"),
             "validation references a different reconstruction")
    anchor_map = {anchor["anchor_id"]: anchor for anchor in anchors}
    root_receipts = reconstruction["anchors"]
    _require(len(root_receipts) == len(anchors), "root receipt coverage differs")
    _require({r["anchor_id"] for r in root_receipts} == set(anchor_map), "root receipt identity differs")
    for receipt in root_receipts:
        path = _inside(directory, receipt["root_path"])
        _require(file_hash(path) == receipt["root_sha256"], "private root changed")
        root = gzread(path)
        _require(root["anchor_id"] == receipt["anchor_id"], "private root anchor differs")
        _require(digest(root["simulator"]) == receipt["root_sha256_canonical"], "canonical simulator root differs")
        _require(root["canonical_observation"] == anchor_map[receipt["anchor_id"]]["observation"], "root observation differs")
        _require(all(receipt.get(k) is True for k in ("request_matched", "protocol_matched", "candidates_matched")),
                 "reconstruction boundary checks missing")
    original = _original_inputs(manifest, anchors)
    for anchor in anchors:
        archived = original[anchor["decision_id"]]
        _require(anchor["observation"] == archived["payload"], "anchor observation differs from original")
        archived_commands = {key: value.removeprefix("/choose ").removeprefix("/")
                             for key, value in archived["commands"].items()}
        _require({a["action_id"]: a["command"] for a in anchor["actions"]} == archived_commands,
                 "anchor action mapping differs from original")
        for action in anchor["actions"]:
            _require(action.get("description") == archived["payload"]["questions"]["action"]["criteria"][action["action_id"]],
                     "anchor action description differs")
        _assert_model_boundary(anchor["observation"])
    rollouts = rows(directory / "rollouts.jsonl") if (directory / "rollouts.jsonl").exists() else []
    attempts = rows(directory / "attempts.jsonl")
    ledger = read(directory / "ledger.json")
    numbers = [attempt["number"] for attempt in attempts]
    _require(len(numbers) == len(set(numbers)) == ledger["attempts"], "cumulative attempt ledger differs")
    _require(sorted(numbers) == list(range(1, ledger["attempts"] + 1)), "attempt numbering has a gap")
    _require(ledger["attempts"] <= min(6000, ledger["maximum_attempts"]), "attempt cap exceeded")
    summary = summarize(manifest, anchors, rollouts, attempts=attempts)
    _require(summary["missing_result_attempts"] == 0, "reserved rollout has no outcome record")
    opponents, trace_count, no_choice = {}, 0, 0
    for row in rollouts:
        anchor = anchor_map[row["anchor_id"]]
        action = next(a for a in anchor["actions"] if a["action_id"] == row["action_id"])
        expected_actors = {side: derive_seed(row["anchor_id"], row["replicate"], side) for side in ("p1", "p2")}
        _require(row.get("actor_seeds") == expected_actors, "actor seed differs")
        _require(row.get("simulator_seed") == derive_seed(row["anchor_id"], row["replicate"], "simulator"), "simulator seed differs")
        path = _inside(directory, row["trace_path"])
        _require(file_hash(path) == row["trace_sha256"], "trace checksum differs")
        trace = gzread(path)
        _public_log(directory, row["trace_path"])
        trace_count += 1
        choices = trace.get("choices", [])
        if not choices:
            _require(row["status"] in {"error", "censored", "aborted"}, "terminal rollout has no forced root action")
            no_choice += 1
            continue
        first = choices[0]["choices"]
        _require(first.get("p2") == action["command"], "first forced p2 action differs")
        _require(first.get("p1") == row.get("root_opponent_choice"), "root opponent choice record differs")
        key = (row["anchor_id"], row["replicate"])
        if key in opponents:
            _require(opponents[key] == first.get("p1"), "opponent responded differently to root candidates")
        else:
            opponents[key] = first.get("p1")
        recorded = trace.get("result")
        if recorded is not None:
            for name in ("anchor_id", "action_id", "replicate", "attempt_id", "status"):
                _require(recorded.get(name) == row.get(name), "trace result identity differs")
    training = training_rows(manifest, anchors, summary)
    for anchor, exported in zip(anchors, training):
        _require(exported["observation"] == anchor["observation"], "training observation differs")
        _require(not ({"original_request", "private_snapshot", "seed", "master_seed", "trace_path", "teams"} & set(exported)),
                 "private metadata in training row")
    preview_ids = {a["anchor_id"] for a in anchors if a["phase"] == "lead"}
    preview_groups = len([key for key in opponents if key[0] in preview_ids])
    return dict(
        schema_version="branch-rollout-audit-v1", technical_pass=True, passed=True,
        collection_complete=summary["collection_complete"], coverage="complete" if summary["collection_complete"] else "partial",
        anchors=len(anchors), actions=summary["actions"], planned=summary["planned"], attempted=summary["attempted"],
        physical_attempts=summary["physical_attempts"], terminal=summary["terminal"], unattempted=summary["unattempted"],
        status_counts=summary["status_counts"], traces=trace_count, traces_without_root_action=no_choice,
        opponent_choice_groups=len(opponents), preview_replicate_groups=preview_groups,
        expected_preview_replicate_groups=len(preview_ids) * manifest["expected_repetitions"],
        source_identity=identity, original_source_files=len(source_preserved),
        reconstruction_sha256=file_hash(directory / "reconstruction.json"), validation_sha256=file_hash(directory / "validation.json"),
        validation_hash_predeclared=bool(manifest.get("validation_sha256")),
        anchor_sha256=file_hash(directory / "anchors.jsonl"), training_boundary_passed=True,
        limitation="부분 수집의 기술 감사 통과는 예정 분기의 완료나 확정 최선 판정이 아니다.",
    )


def _seal(directory):
    files = sorted(path for path in directory.rglob("*") if path.is_file() and path != directory / "checksums.sha256")
    _require(not any(path.is_symlink() for path in files), "cannot seal symlinked artifacts")
    lines = [f"{file_hash(path)}  {path.relative_to(directory).as_posix()}\n" for path in files]
    (directory / "checksums.sha256").write_text("".join(lines))
    return len(files)


def finalize(directory, viewer_directory):
    """Audit then export and seal; no gameplay, source edits, or model calls."""
    directory, viewer_directory = Path(directory), Path(viewer_directory)
    try:
        audit = audit_dataset(directory)
        summary = export_report(directory, viewer_directory=viewer_directory)
        exported = rows(directory / "training.jsonl")
        expected = training_rows(read(directory / "manifest.json"), rows(directory / "anchors.jsonl"), summary)
        _require(exported == expected, "written training export differs")
        _require(rows(viewer_directory / "training.jsonl") == expected, "viewer training copy differs")
        _require(audit["source_identity"] == code_identity(), "source changed during final audit")
        copies = {}
        for relative, checksum in audit["source_identity"].items():
            original = ROOT / relative
            _require(file_hash(original) == checksum, "run source changed before preservation")
            target = directory / "frozen-source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                _require(file_hash(target) == checksum, "preserved source differs")
            else:
                shutil.copyfile(original, target)
            _require(file_hash(target) == checksum, "source copy checksum differs")
            copies[relative] = checksum
        audit.update(source_copies=copies, viewer=str(viewer_directory / "index.html"),
                     training_sha256=file_hash(directory / "training.jsonl"))
        write(directory / "audit.json", audit)
        write(viewer_directory / "audit.json", {k: v for k, v in audit.items() if k not in ("source_identity", "source_copies")})
        viewer_files = _seal(viewer_directory)
        dataset_files = _seal(directory)
        return dict(technical_pass=True, collection_complete=audit["collection_complete"], coverage=audit["coverage"],
                    planned=audit["planned"], attempted=audit["attempted"], terminal=audit["terminal"],
                    unattempted=audit["unattempted"], status_counts=audit["status_counts"],
                    dataset_sealed_files=dataset_files, viewer_sealed_files=viewer_files,
                    viewer=str(viewer_directory / "index.html"))
    except Exception as error:
        write(directory / "audit.json", dict(technical_pass=False, passed=False, collection_complete=False,
                                             error={"type": type(error).__name__, "message": str(error)}))
        raise
