"""EX-083: preserve EX-082's 23 valid games and admit only its final nine slots."""
from __future__ import annotations

import argparse
import asyncio
import copy
import html
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from . import battle, study

PROFILE = "jev27b-ex082-four-gpu-continuation-v1"
EXPORT = study.ROOT / "exports/battle_viewers/ex083"
PARENT_SEAL = "8eca312fb6666a2dba6a60f16929b9490c1db6fe1efe60fadab87603f5ac24a8"
PARENT_JOURNAL = "4fa5bd7ed0d8b2c30c766960819ec99583e3a28ffbdf2f6fe28c8df75b9d3f30"
RETRY_SLOT = "b04-r2-s0"
PARENT_COUNTERS = dict(planned=32, attempted=24, completed=23, failed=1, invalid=0,
    unattempted=8, requests=595, logical_requests=592, received_responses=591,
    sent_actions=607, automatic_actions=16, unanswered_requests=1,
    usage_unknown_requests=1, retry_attempts=3)
ADDITIVE_COUNTERS = (
    "requests", "external_requests", "local_http_requests", "logical_requests",
    "received_responses", "unanswered_requests", "sent_actions", "automatic_actions",
    "missing_usage_responses", "usage_unknown_requests", "retry_attempts", "http_responses",
    "http_errors", "http_no_response", "provider_failed_attempts", "recovered_requests",
    "exhausted_requests")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def valid(outcome):
    return (outcome.get("completed") is True and outcome.get("audit_passed") is True
            and not outcome.get("error"))


def runtime_settings():
    from .config import runtime_profile
    from .model import fixed_device_map
    profile = runtime_profile("ex083")
    return dict(profile=profile.name, physical_gpus=list(profile.physical_gpus),
        allocator_bytes_per_gpu=profile.allocator_bytes,
        total_device_bytes_limit_per_gpu=profile.gpu_bytes,
        host_bytes_limit=profile.host_bytes, disk_bytes_limit=profile.disk_bytes,
        device_map=fixed_device_map("ex083"), backbone_dtype="bfloat16", head_dtype="float32",
        model_instances=1, inference_concurrency=1, battle_concurrency=1, offload=False,
        quantization=False, extra_training=False)


def strict_seal(directory):
    """A sealed parent cannot gain extra attempts through unlisted files."""
    directory = Path(directory).resolve()
    seals = study.verify_seal(directory)
    actual = {str(path.relative_to(directory)) for path in directory.rglob("*")
              if path.is_file() and path != directory / "checksums.sha256"}
    require(actual == set(seals), "unsealed or missing files in parent")
    return seals


def validate_parent_records(manifest, result, final_audit, baseline):
    """Pure schedule/denominator validation, separate from the pinned artifact check."""
    require(manifest.get("experiment_id") == "EX-082"
            and manifest.get("execution_profile") == study.PROFILE, "wrong continuation parent")
    require(manifest.get("schema_version") == "jev-choice-v4", "parent input version differs")
    require(manifest.get("model", {}).get("model") == battle.MODEL
            and manifest["model"].get("revision") == battle.REVISION, "parent model changed")
    for key in ("schedule", "schedule_sha256", "teams", "prompt", "input_data_identity",
                "observation_build"):
        require(manifest[key] == baseline[key], "parent EX-058 identity differs: " + key)
    require(len(manifest["schedule"]) == 32
            and manifest["schedule"][23]["slot_id"] == RETRY_SLOT, "wrong approved retry slot")
    require(study.j.digest(manifest["schedule"]) == manifest["schedule_sha256"],
            "parent schedule hash differs")
    for key, expected in PARENT_COUNTERS.items():
        require(result.get(key) == expected, "parent denominator differs: " + key)
    require(result.get("passed") is False and result.get("final_audit_passed") is True
            and result.get("tokens") is None and result.get("error"),
            "parent failure/unknown usage was not preserved")
    require(final_audit.get("passed") is True and final_audit.get("errors") == []
            and final_audit.get("valid_responses") == 591
            and final_audit.get("inputs") == 608 and final_audit.get("wires") == 607,
            "parent final audit differs")
    outcomes = result["outcomes"]
    require(len(outcomes) == 24 and len({row["slot_id"] for row in outcomes}) == 24,
            "parent attempt history is duplicated or incomplete")
    for index, outcome in enumerate(outcomes):
        row = manifest["schedule"][index]
        require(outcome.get("slot") == index + 1, "parent slot number differs")
        require(all(outcome.get(key) == value for key, value in row.items()),
                "parent schedule/seed/actor order differs")
        require(outcome.get("audit_passed") is True and outcome.get("server_cleaned") is True
                and outcome.get("opponent_cleaned") is True, "parent attempt was not audited/closed")
        if index < 23:
            require(valid(outcome) and outcome.get("outcome") in study.POINTS,
                    "only the original 23 completed games can be inherited")
        else:
            require(outcome.get("completed") is False
                    and outcome.get("failure_scope") == "collection" and outcome.get("error"),
                    "only the original failed slot may receive one additional attempt")
    return copy.deepcopy(outcomes[:23]), copy.deepcopy(manifest["schedule"][23:])


def validate_parent(parent):
    """Read only: pin the approved seal, all artifacts, accounting, and failed input."""
    parent = Path(parent).resolve()
    require(study.file_hash(parent / "checksums.sha256") == PARENT_SEAL,
            "approved EX-082 parent seal differs")
    seals = strict_seal(parent)
    manifest, result, final_audit = (read_json(parent / name) for name in
                                    ("manifest.json", "result.json", "final-audit.json"))
    baseline = study.load_baseline(full_seal=True)
    inherited, remaining = validate_parent_records(manifest, result, final_audit, baseline)
    require(study.file_hash(manifest["server_journal"]) == PARENT_JOURNAL,
            "parent server journal changed")
    for outcome in result["outcomes"]:
        attempt = parent / f"battle-{outcome['slot']}"
        require(read_json(attempt / "outcome.json") == outcome, "parent saved outcome differs")
        require(read_json(attempt / "audit.json").get("passed") is True,
                "parent saved per-game audit failed")
        request = read_json(attempt / "request.json")
        require(request["slot"] == manifest["schedule"][outcome["slot"] - 1]
                and request["teams"] == manifest["teams"], "parent attempted another matchup")
    inputs, responses, logical, request_ids = set(), set(), set(), set()
    counts, last_input, failure_input = {}, None, None
    failed_user = result["outcomes"][-1]["username"]
    partial_responses = 0
    usage = dict(input_tokens=0, output_tokens=0)
    sequence = 0
    for event in study.event_rows(parent):
        sequence += 1
        require(event.get("event_seq") == sequence, "parent event sequence differs")
        kind, decision = event["type"], event.get("decision")
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "input":
            require(decision not in inputs, "duplicate parent input")
            inputs.add(decision)
            last_input = event
            if decision.split("-")[0] == failed_user:
                failure_input = event
        elif kind == "transport":
            require(decision in inputs, "parent transport without input")
            logical.add(decision)
            request_ids.add(event["request_id"])
        elif kind == "response":
            require(decision in inputs and decision not in responses, "duplicate/unlinked parent response")
            responses.add(decision)
            for key in usage:
                usage[key] += event["body"]["usage"][key]
            partial_responses += decision.split("-")[0] == failed_user
    require(counts.get("input") == 608 and counts.get("response") == 591
            and counts.get("wire") == 607 and counts.get("transport") == 595
            and len(logical) == len(request_ids) == 592, "parent raw event denominator differs")
    unanswered = logical - responses
    require(len(unanswered) == 1 and failure_input == last_input
            and failure_input["decision"] in unanswered, "parent failed request differs")
    require(partial_responses == 10 and usage == result["received_usage"],
            "parent partial response/usage history differs")
    return dict(passed=True, parent=str(parent), parent_seal_sha256=PARENT_SEAL,
        sealed_files=len(seals), parent_manifest_sha256=seals["manifest.json"],
        parent_result_sha256=seals["result.json"], parent_events_sha256=seals["events.jsonl"],
        parent_journal_sha256=PARENT_JOURNAL, manifest=manifest, result=result,
        inherited_outcomes=inherited, schedule=copy.deepcopy(manifest["schedule"]),
        continuation_schedule=remaining, successful_responses=591,
        failed_attempt=copy.deepcopy(result["outcomes"][-1]),
        failed_attempt_partial_responses=partial_responses,
        unanswered_decisions=sorted(unanswered), failed_input=failure_input,
        first_request_at=result["first_request_at"])


def iter_parent_responses(parent):
    """Yield original input/response pairs in recorded response order, including partial play."""
    pending = {}
    for event in study.event_rows(parent):
        if event["type"] == "input":
            require(event["decision"] not in pending, "duplicate parent input")
            pending[event["decision"]] = event
        elif event["type"] == "response":
            require(event["decision"] in pending, "parent response has no input")
            yield dict(input=pending.pop(event["decision"]), response=event)


def attempt_plan(parent_info):
    outcomes = {outcome["slot_id"]: outcome for outcome in parent_info["result"]["outcomes"]}
    records = []
    for number, row in enumerate(parent_info["schedule"], 1):
        old = outcomes.get(row["slot_id"])
        attempts = []
        if old is not None:
            attempts.append(dict(experiment="EX-082", attempt=1, gpus=[0, 1],
                status="valid" if valid(old) else "failed", outcome=copy.deepcopy(old)))
        if number >= 24:
            attempts.append(dict(experiment="EX-083", attempt=2 if number == 24 else 1,
                                 gpus=[0, 1, 2, 3], status="planned"))
        records.append(dict(slot=number, slot_id=row["slot_id"], schedule=copy.deepcopy(row),
            inherited=number <= 23, attempts=attempts))
    return records


def validate_manifest(manifest):
    require(manifest.get("experiment_id") == "EX-083"
            and manifest.get("execution_profile") == PROFILE, "wrong continuation manifest")
    require(manifest.get("parent", {}).get("seal_sha256") == PARENT_SEAL,
            "continuation parent seal changed")
    require(manifest.get("runtime") == runtime_settings(), "continuation runtime settings differ")
    require(len(manifest["schedule"]) == 32
            and manifest["collection_schedule"] == manifest["schedule"][23:]
            and manifest["collection_schedule"][0]["slot_id"] == RETRY_SLOT,
            "continuation must execute only original slots 24 through 32")
    policy = manifest.get("continuation_policy", {})
    require(policy == dict(inherited_valid_games=23, retry_slot=RETRY_SLOT,
        additional_attempts_for_retry_slot=1, new_unattempted_games=8,
        total_unique_slots=32, maximum_total_battle_attempts=33,
        additional_recollections=0, automatic_resume=False), "continuation attempt policy changed")
    planned = manifest["attempt_plan"]
    require(len(planned) == 32, "full attempt plan is missing")
    for number, (entry, row) in enumerate(zip(planned, manifest["schedule"]), 1):
        require(entry["slot"] == number and entry["slot_id"] == row["slot_id"]
                and entry["schedule"] == row and entry["inherited"] == (number <= 23),
                "attempt plan schedule differs")
        trials = entry["attempts"]
        expected = ([('EX-082', 1, 'valid')] if number <= 23 else
                    [('EX-082', 1, 'failed'), ('EX-083', 2, 'planned')] if number == 24 else
                    [('EX-083', 1, 'planned')])
        require([(x["experiment"], x["attempt"], x["status"]) for x in trials] == expected,
                "completed slot repeated or extra battle retry planned")
        require(all(trial["gpus"] == ([0, 1] if trial["experiment"] == "EX-082" else [0, 1, 2, 3])
                    for trial in trials), "attempt GPU segment differs")
    require(manifest["inherited_outcomes"] == [entry["attempts"][0]["outcome"] for entry in planned[:23]]
            and all(valid(outcome) for outcome in manifest["inherited_outcomes"]),
            "inherited outcome provenance differs")


def prepare_manifest(parent_info, expected_identity, gate_receipt, *, endpoint):
    for key in ("replay_passed", "memory_passed"):
        require(gate_receipt.get(key) is True, "continuation gate missing: " + key)
    require(gate_receipt.get("parent_seal_sha256") == parent_info["parent_seal_sha256"] == PARENT_SEAL,
            "continuation gate parent differs")
    manifest = study.prepare_manifest(expected_identity, gate_receipt, endpoint=endpoint)
    manifest.update(experiment_id="EX-083", execution_profile=PROFILE,
        runtime=runtime_settings(),
        parent=dict(experiment="EX-082", directory=parent_info["parent"], seal_sha256=PARENT_SEAL,
            manifest_sha256=parent_info["parent_manifest_sha256"],
            result_sha256=parent_info["parent_result_sha256"],
            events_sha256=parent_info["parent_events_sha256"],
            first_request_at=parent_info["first_request_at"], preserved_status="Blocked"),
        collection_schedule=copy.deepcopy(parent_info["continuation_schedule"]),
        inherited_outcomes=copy.deepcopy(parent_info["inherited_outcomes"]),
        attempt_plan=attempt_plan(parent_info),
        continuation_policy=dict(inherited_valid_games=23, retry_slot=RETRY_SLOT,
            additional_attempts_for_retry_slot=1, new_unattempted_games=8,
            total_unique_slots=32, maximum_total_battle_attempts=33,
            additional_recollections=0, automatic_resume=False),
        interpretation="2GPU 완료23경기와4GPU 완료9경기를 수치 검증 후 계승한 평가")
    manifest["limits"].update(games=9, inherited_games=23, unique_games=32,
                              total_battle_attempts=33, recollection=1)
    validate_manifest(manifest)
    return manifest


def validate_new_outcomes(parent_info, outcomes):
    expected = parent_info["continuation_schedule"]
    require(len(outcomes) <= 9 and len({o["slot_id"] for o in outcomes}) == len(outcomes),
            "duplicate completed slot or additional retry")
    old_users = {outcome["username"] for outcome in parent_info["result"]["outcomes"]}
    new_users = []
    for index, outcome in enumerate(outcomes):
        row = expected[index]
        require(outcome.get("slot") == index + 24
                and all(outcome.get(key) == value for key, value in row.items()),
                "continuation order/seed differs or completed slot repeated")
        require(outcome.get("username") not in old_users, "parent battle identity reused")
        new_users.append(outcome.get("username"))
    require(None not in new_users and len(set(new_users)) == len(new_users),
            "duplicate continuation battle identity")


def validate_collection_artifacts(directory, parent_info, result):
    """No unreported or second attempt can hide in a successfully sealed collection."""
    directory = Path(directory)
    validate_new_outcomes(parent_info, result["outcomes"])
    expected_dirs = {f"battle-{outcome['slot']}" for outcome in result["outcomes"]}
    require({path.name for path in directory.glob("battle-*")} == expected_dirs,
            "unreported or extra continuation battle attempt")
    for outcome in result["outcomes"]:
        attempt = directory / f"battle-{outcome['slot']}"
        require(read_json(attempt / "outcome.json") == outcome,
                "new saved outcome differs from final accounting")
        request = read_json(attempt / "request.json") if (attempt / "request.json").exists() else None
        if request is None:
            require(not outcome.get("completed") and outcome.get("error"),
                    "completed continuation attempt has no original request")
        else:
            require(request["slot"] == parent_info["schedule"][outcome["slot"] - 1]
                    and request["teams"] == parent_info["manifest"]["teams"],
                    "new attempted matchup differs")


def combine(parent_info, new_result):
    """Keep unique-slot scores separate from all 33 possible battle attempts."""
    previous = parent_info["result"]
    new = new_result["outcomes"]
    validate_new_outcomes(parent_info, new)
    selected = copy.deepcopy(parent_info["inherited_outcomes"] +
                             (new if new else [parent_info["failed_attempt"]]))
    empty = SimpleNamespace(records=[], calls=0, started=None, monotonic_started=None)
    result = study.summarize(empty, selected, parent_info["schedule"], error=new_result.get("error"))
    for key in ADDITIVE_COUNTERS:
        result[key] = previous.get(key, 0) + new_result.get(key, 0)
    result["received_usage"] = {key: previous["received_usage"].get(key, 0)
        + new_result.get("received_usage", {}).get(key, 0) for key in ("input_tokens", "output_tokens")}
    result["tokens"] = None if result["usage_unknown_requests"] else result["received_usage"]
    result["actual_models"] = sorted(set(previous["actual_models"]) | set(new_result.get("actual_models", [])))
    result["action_audit_passed"] = previous["action_audit_passed"] and new_result.get("action_audit_passed", False)
    result["final_audit_passed"] = previous["final_audit_passed"] and new_result.get("final_audit_passed", False)
    result.update(experiment_id="EX-083", inherited_completed=23, new_planned=9,
        new_attempted=len(new), new_completed=sum(valid(o) for o in new),
        total_battle_attempts=24 + len(new), maximum_total_battle_attempts=33,
        original_failed_attempts=1,
        all_failed_attempts=1 + sum(not o.get("completed") for o in new),
        all_invalid_attempts=sum(o.get("completed", False) and not valid(o) for o in new),
        preserved_parent_status="Blocked", parent_seal_sha256=PARENT_SEAL,
        first_request_at=previous["first_request_at"],
        elapsed_collection_seconds=None,
        latency_seconds=None, http_latency_seconds=None, input_generation_seconds=None,
        input_tokens=None, judgment_diagnostics=None,
        segments={"EX-082_2GPU": copy.deepcopy(previous), "EX-083_4GPU": copy.deepcopy(new_result)},
        original_failure=copy.deepcopy(parent_info["failed_attempt"]),
        original_failed_partial_responses=parent_info["failed_attempt_partial_responses"],
        original_unanswered_decisions=parent_info["unanswered_decisions"],
        interpretation=f"2GPU 완료23경기와4GPU 완료{sum(valid(o) for o in new)}경기를 수치 검증 후 계승한 평가")
    result["passed"] = (new_result.get("passed") is True and result["final_audit_passed"] is True
                        and result["completed"] == 32 and result["completed_pairs"] == 16
                        and result["total_battle_attempts"] == 33 and not result["error"])
    return result


def actual_attempts(parent_info, new_result):
    validate_new_outcomes(parent_info, new_result["outcomes"])
    plan = attempt_plan(parent_info)
    by_slot = {o["slot_id"]: o for o in new_result["outcomes"]}
    for row in plan:
        for trial in row["attempts"]:
            if trial["experiment"] == "EX-083":
                outcome = by_slot.get(row["slot_id"])
                trial["status"] = ("unattempted" if outcome is None else "valid" if valid(outcome)
                                   else "invalid" if outcome.get("completed") else "failed")
                if outcome is not None:
                    trial["outcome"] = copy.deepcopy(outcome)
    return dict(planned_unique_games=32, maximum_battle_attempts=33,
                actual_battle_attempts=24 + len(new_result["outcomes"]), slots=plan)


async def run(directory, *, parent, expected_identity, gate_receipt, endpoint=battle.ENDPOINT):
    directory, parent = Path(directory).resolve(), Path(parent).resolve()
    if directory.exists():
        raise FileExistsError("EX-083 cannot resume or overwrite an existing attempt")
    require(not directory.is_relative_to(parent) and not parent.is_relative_to(directory),
            "continuation output overlaps the preserved parent")
    parent_info = await asyncio.to_thread(validate_parent, parent)
    manifest = prepare_manifest(parent_info, expected_identity, gate_receipt, endpoint=endpoint)
    result = await battle._run_frozen(directory, manifest=manifest,
        expected_identity=expected_identity, gate_receipt=gate_receipt, endpoint=endpoint)
    # No parent write occurs, including for failure, cancellation, or final reporting.
    await asyncio.to_thread(validate_parent, parent)
    validate_collection_artifacts(directory, parent_info, result)
    study.write_json(directory / "parent-validation.json", parent_info)
    study.write_json(directory / "combined-result.json", combine(parent_info, result))
    study.write_json(directory / "attempts.json", actual_attempts(parent_info, result))
    study.seal(directory)
    return read_json(directory / "combined-result.json")


def comparison(parent_info, directory, combined):
    require(combined.get("final_audit_passed") is True, "comparison requires both segment audits")
    # Original and new usernames are distinct; match_metrics selects only each
    # chosen outcome's events, excluding the old failed retry from final scores.
    events = list(study.event_rows(parent_info["parent"])) + list(study.event_rows(directory))
    compared = study.compare_data(
        (study.load_baseline(full_seal=True), read_json(study.BASELINE / "result.json"),
         list(study.event_rows(study.BASELINE))),
        (read_json(Path(directory) / "manifest.json"), combined, events))
    compared.update(interpretation=combined["interpretation"], mixed_gpu_segments=True,
                    latency_comparison_is_segmented=True)
    new_slots = {row["slot_id"] for row in combined["segments"]["EX-083_4GPU"]["outcomes"]}
    old_slots = {row["slot_id"] for row in parent_info["result"]["outcomes"]}
    for row in compared["matches"]:
        row["after_segment"] = ("EX-083_4GPU" if row["slot_id"] in new_slots else
                                "EX-082_2GPU" if row["slot_id"] in old_slots else None)
    return compared


def composite_source(directory, parent_info, combined, destination):
    """A sealed derived export source, with both original event streams unmodified."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = read_json(Path(directory) / "manifest.json")
    manifest["derived_export_source"] = dict(parent=parent_info["parent"], continuation=str(directory),
        parent_seal_sha256=PARENT_SEAL,
        continuation_seal_sha256=study.file_hash(Path(directory) / "checksums.sha256"),
        events_concatenated=True, source_events_rewritten=False)
    study.write_json(destination / "manifest.json", manifest)
    study.write_json(destination / "result.json", combined)
    with (destination / "events.jsonl").open("xb") as target:
        for segment in (Path(parent_info["parent"]), Path(directory)):
            with (segment / "events.jsonl").open("rb") as source:
                shutil.copyfileobj(source, target)
    study.seal(destination)
    return destination


def export(directory, parent_info, combined, *, output=EXPORT, derived, compared):
    output = Path(output)
    source = composite_source(directory, parent_info, combined, derived)
    exported = study.export(source, output, compared=compared)
    # Copy the old attempt history into the portable tree. Its relative link
    # remains usable without the parent raw-data directory after relocation.
    parent_export = study.export(parent_info["parent"], output / "parent-ex082")
    study.write_json(output / "attempts.json", actual_attempts(parent_info, combined["segments"]["EX-083_4GPU"]))
    page = (output / "index.html").read_text()
    notice = (f'<p>{html.escape(combined["interpretation"])}. 총 배틀 시도 '
        f'{combined["total_battle_attempts"]}/33회 · 고유 시도 {combined["attempted"]}/32경기.</p>'
        '<p><a href="parent-ex082/battle-24/index.html">원 EX-082 24번째 실패 시도·부분 응답</a>'
        ' · <a href="parent-ex082/index.html">원 EX-082 전체 시도 이력</a>'
        ' · <a href="attempts.json">전체 슬롯·시도 연결</a></p>')
    page = page.replace('<div class="scroll">', notice + '<div class="scroll">', 1)
    (output / "index.html").write_text(page)
    study.seal(output)
    verified = study.verify_viewer(source, output)
    parent_verified = study.verify_viewer(parent_info["parent"], output / "parent-ex082")
    return dict(passed=verified["passed"] and parent_verified["passed"], source=str(source),
        export=exported, parent_export=parent_export, viewer=verified,
        parent_viewer=parent_verified, export_seal=study.file_hash(output / "checksums.sha256"))


def verify_browser(output):
    output = Path(output)
    current = study.verify_browser(output)
    parent = study.verify_browser(output / "parent-ex082")
    require('href="parent-ex082/battle-24/index.html"' in (output / "index.html").read_text()
            and (output / "parent-ex082/battle-24/index.html").is_file(),
            "portable original failure link is missing")
    return dict(passed=True, continuation=current, parent_history=parent,
                original_failure_link=True, offline_relocated=True)


def finalize(directory, *, parent, output=EXPORT, evidence=None, browser=False):
    """Re-audit both source segments, score unique slots, and export all trial history."""
    from .audit import audit
    directory, parent = Path(directory).resolve(), Path(parent).resolve()
    evidence = Path(evidence) if evidence is not None else directory.parent / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    parent_info = validate_parent(parent)
    strict_seal(directory)
    manifest = read_json(directory / "manifest.json")
    validate_manifest(manifest)
    require(manifest["parent"]["directory"] == str(parent), "finalization parent path differs")
    require(manifest["attempt_plan"] == attempt_plan(parent_info)
            and manifest["inherited_outcomes"] == parent_info["inherited_outcomes"],
            "finalization inherited outcomes differ from the sealed parent")
    checks = dict(parent=audit(parent, immutable_journal=True), continuation=audit(directory))
    study.write_json(evidence / "continuation-audit.json", checks)
    segment = read_json(directory / "result.json")
    validate_collection_artifacts(directory, parent_info, segment)
    combined = combine(parent_info, segment)
    if not all(check["passed"] for check in checks.values()):
        combined.update(passed=False, final_audit_passed=False,
            validity="withheld_pending_final_audit",
            error=dict(type="FinalAuditFailure", detail=repr(checks)))
    compared = (comparison(parent_info, directory, combined) if combined["final_audit_passed"] else
                dict(available=False, reason="부모 또는 신규 구간의 최종 기술 감사 미통과"))
    study.write_json(evidence / "combined-result.json", combined)
    study.write_json(evidence / "comparison.json", compared)
    study.write_json(evidence / "attempts.json", actual_attempts(parent_info, segment))
    exported = export(directory, parent_info, combined, output=output,
                      derived=evidence / "viewer-source", compared=compared)
    study.write_json(evidence / "viewer-verification.json", exported)
    browser_result = verify_browser(output) if browser else None
    if browser_result is not None:
        study.write_json(evidence / "viewer-browser.json", browser_result)
    # Pin/seal and unknown usage remain identical even after SQLite and exports.
    validate_parent(parent)
    return dict(passed=combined["passed"], result=combined, audit=checks,
                comparison=compared, export=exported, browser=browser_result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "finalize", "verify-browser", "validate-parent"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--parent", type=Path, default=study.LIVE)
    parser.add_argument("--output", type=Path, default=EXPORT)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--gates", type=Path)
    parser.add_argument("--identity")
    parser.add_argument("--endpoint", default=battle.ENDPOINT)
    args = parser.parse_args()
    if args.command == "run":
        result = asyncio.run(run(args.directory, parent=args.parent,
            expected_identity=args.identity, gate_receipt=read_json(args.gates), endpoint=args.endpoint))
    elif args.command == "finalize":
        result = finalize(args.directory, parent=args.parent, output=args.output, evidence=args.evidence)
    elif args.command == "verify-browser":
        result = verify_browser(args.output)
        if args.evidence is not None:
            study.write_json(args.evidence / "viewer-browser.json", result)
    else:
        result = validate_parent(args.parent)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if result.get("passed") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
