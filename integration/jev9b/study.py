"""EX-085 fresh single-Choice accounting and the audited EX-083 reference."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import time

from integration.jev27b import study as inherited
from integration.jev27b.study import (
    event_rows, file_hash, seal, snapshot_sources, verify_seal, write_json,
)
from integration.pokechamp import jev_battle as j, jev_v4

from .config import BASELINE, MODEL_ID, REVISION, ROOT, RUN

LIVE = RUN / "collection"
PROFILE = "jev9b-ex083-single-choice-v1"
POINTS = inherited.POINTS
INTERPRETATION = (
    "동일 입력·단일 선택 정책에서 공식 JEV-9B와 JEV-27B 패키지를 비교한 고정 대진 탐색 평가"
)
REFERENCE_INTERPRETATION = "EX-083은 2GPU 완료23경기와 4GPU 완료9경기를 계승한 평가"


def sealed_document(directory, filename):
    directory = Path(directory)
    entries = dict(line.split("  ", 1)[::-1] for line in
                   (directory / "checksums.sha256").read_text().splitlines())
    if entries.get(filename) != file_hash(directory / filename):
        raise ValueError("baseline document seal differs: " + filename)
    return json.loads((directory / filename).read_text())


def load_baseline():
    """Read frozen unique outcomes without replaying or re-auditing parent games."""
    from integration.pokechamp.jev_study import validate_schedule
    directory = BASELINE / "collection"
    manifest = sealed_document(directory, "manifest.json")
    result = sealed_document(directory, "combined-result.json")
    validate_schedule(manifest["schedule"])
    if (manifest["experiment_id"] != "EX-083" or result["experiment_id"] != "EX-083"
            or result["completed"] != 32 or result["completed_pairs"] != 16
            or result.get("passed") is not True or result.get("final_audit_passed") is not True):
        raise ValueError("EX-083 audited unique completed reference is required")
    if [o["slot_id"] for o in result["outcomes"]] != [r["slot_id"] for r in manifest["schedule"]]:
        raise ValueError("EX-083 unique outcome coverage/order differs")
    if len({o["slot_id"] for o in result["outcomes"]}) != 32:
        raise ValueError("EX-083 reference has duplicate slots")
    if j.digest(manifest["schedule"]) != manifest["schedule_sha256"]:
        raise ValueError("reference schedule hash differs")
    if manifest["input_data_identity"] != jev_v4.data_identity():
        raise ValueError("reference input data changed")
    if manifest["prompt"] != (ROOT / "integration/pokechamp/prompts/jev-choice-v4.txt").read_text():
        raise ValueError("reference prompt differs")
    for team in manifest["teams"].values():
        if hashlib.sha256(team["showdown_team"].encode()).hexdigest() != team["sha256"]:
            raise ValueError("reference team text differs")
    return manifest, result


def source_identity():
    source = j.source_identity()
    for directory in ("integration/jev9b", "integration/jev27b"):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and path.suffix in (".py", ".html", ".json", ".txt"):
                source[str(path.relative_to(ROOT))] = file_hash(path)
    for name in ("scripts/jev9b", "scripts/jev27b"):
        if (ROOT / name).is_file():
            source[name] = file_hash(ROOT / name)
    return source


def prepare_manifest(expected_identity, gate_receipt, *, endpoint):
    from integration.pokechamp import cli
    from .battle import RETRY_DELAYS, TIMEOUT, TRANSPORT_POLICY
    from .client import base_url
    baseline, _ = load_baseline()
    sources = source_identity()
    inferences = gate_receipt.get("inferences")
    if (gate_receipt.get("passed") is not True
            or gate_receipt.get("serving_identity") != expected_identity
            or gate_receipt.get("source") != sources
            or type(inferences) is not int or not 1 <= inferences <= 8
            or gate_receipt.get("server_loads") != 1):
        raise ValueError("same-server CPU/GPU gate receipt within eight inferences required")
    journal = gate_receipt.get("server_journal")
    if not isinstance(journal, str) or not Path(journal).is_file():
        raise ValueError("the serving process request journal is required")
    return dict(experiment_id="EX-085", execution_profile=PROFILE, policy_version=PROFILE,
        version=jev_v4.VERSION, schema_version=jev_v4.VERSION,
        validation_version=j.VALIDATION_VERSION, initial_pp_policy=j.INITIAL_PP_POLICY,
        effect_reference_identity=j.effects.identity(), input_data_identity=jev_v4.data_identity(),
        schedule=copy.deepcopy(baseline["schedule"]), teams=copy.deepcopy(baseline["teams"]),
        schedule_sha256=baseline["schedule_sha256"], prompt=baseline["prompt"], source=sources,
        baseline=dict(experiment="EX-083", directory=str(BASELINE / "collection"),
            manifest_sha256=file_hash(BASELINE / "collection/manifest.json"),
            result_sha256=file_hash(BASELINE / "collection/combined-result.json"),
            interpretation=REFERENCE_INTERPRETATION, inherited_new_outcomes=0),
        model=dict(model=MODEL_ID, revision=REVISION,
            endpoint=base_url(endpoint) + "/v1/systemone", serving_identity=expected_identity),
        server_journal=str(Path(journal).resolve()), fake=False, timer_enabled=False,
        transport_policy=TRANSPORT_POLICY, provider_retries=3, retry_delays_seconds=list(RETRY_DELAYS),
        limits=dict(games=32, calls=None, collection_seconds=None, total_seconds=None,
            stage_seconds=None, battle_seconds=None, concurrency=1, inference_concurrency=1,
            request_timeout_seconds=TIMEOUT, input_tokens=32768, options=16, retries=3, recollection=0),
        submodules={name: dict(sha=c["sha"]) for name, c in cli.SUBMODULES.items()},
        observation_build=baseline["observation_build"], gate_receipt_sha256=j.digest(gate_receipt),
        rng_isolation="separate-processes", created_at=time.time(), efficacy_evidence=False,
        interpretation=INTERPRETATION)


def verify_live_identity(manifest):
    if manifest["source"] != source_identity():
        raise ValueError("source changed during collection")
    baseline, _ = load_baseline()
    for key in ("schedule", "teams", "prompt", "input_data_identity", "observation_build"):
        if manifest[key] != baseline[key]:
            raise ValueError("frozen identity changed: " + key)
    if manifest["model"]["model"] != MODEL_ID or manifest["model"]["revision"] != REVISION:
        raise ValueError("JEV-9B model identity changed")


def valid(outcome):
    return bool(outcome.get("completed") and outcome.get("audit_passed") and not outcome.get("error"))


def outcome_scores(outcomes, schedule):
    slots = {r["slot_id"]: r for r in schedule}
    if len(slots) != len(schedule) or len({o["slot_id"] for o in outcomes}) != len(outcomes):
        raise ValueError("duplicate scheduled/outcome slot")
    for outcome in outcomes:
        row = slots.get(outcome["slot_id"])
        if row is None or any(outcome[k] != row[k] for k in ("paired_slot_id", "jev_actor")):
            raise ValueError("outcome slot/side differs from schedule")
    good = [o for o in outcomes if valid(o)]
    members = {}
    for outcome in good:
        members.setdefault(outcome["paired_slot_id"], []).append(outcome)
    pairs = {key: sum(POINTS[o["outcome"]] for o in values) / 2 for key, values in members.items()
             if len(values) == 2 and {o["jev_actor"] for o in values} == {"p1", "p2"}}
    return dict(planned=len(schedule), attempted=len(outcomes), completed=len(good),
        failed=sum(not o.get("completed") for o in outcomes),
        invalid=sum(bool(o.get("completed")) and not valid(o) for o in outcomes),
        unattempted=len(schedule) - len(outcomes), completed_pairs=len(pairs), pair_scores=pairs,
        completion_rate=len(good) / len(schedule) if schedule else 0,
        overall=dict(games=len(good), wins=sum(o["outcome"] == "player_won" for o in good),
            draws=sum(o["outcome"] == "tied" for o in good), losses=sum(o["outcome"] == "player_lost" for o in good),
            score=sum(POINTS[o["outcome"]] for o in good) / len(good) if good else None))


def summarize(session, outcomes, schedule, error=None):
    result = inherited.summarize(session, outcomes, schedule, error)
    result.update(outcome_scores(outcomes, schedule), experiment_id="EX-085", interpretation=INTERPRETATION)
    records = session.records
    result.update(decisions=sum(e["type"] == "input" for e in records),
        http_attempt_scope="inference_POST_only",
        inference_latency_seconds=sum(e["body"].get("metadata", {}).get("elapsed_seconds", 0)
                                      for e in records if e["type"] == "response"),
        decision_latency_seconds=sum(e.get("decision_seconds", 0) for e in records
                                     if e["type"] == "selection"))
    return result


def comparison(manifest, result):
    before_manifest, before = load_baseline()
    for key in ("schema_version", "schedule", "teams", "prompt", "input_data_identity"):
        if manifest[key] != before_manifest[key]:
            raise ValueError("comparison treatment drift: " + key)
    if result.get("final_audit_passed") is not True:
        return dict(available=False, reason="최종 기술 감사 미통과로 성적 비교 보류")
    return compare_outcomes(before["outcomes"], result["outcomes"], manifest["schedule"])


def compare_outcomes(before, after, schedule):
    # Validate identities on both sides before selecting the common paired denominator.
    before_scores = outcome_scores(before, schedule)
    after_scores = outcome_scores(after, schedule)
    old, new = {o["slot_id"]: o for o in before}, {o["slot_id"]: o for o in after}
    rows, groups = [], {}
    for row in schedule:
        a, b = old.get(row["slot_id"]), new.get(row["slot_id"])
        common = a is not None and b is not None and valid(a) and valid(b)
        value = dict(slot_id=row["slot_id"], paired_slot_id=row["paired_slot_id"], actor=row["jev_actor"],
            comparable=common, before=POINTS[a["outcome"]] if a and valid(a) else None,
            after=POINTS[b["outcome"]] if b and valid(b) else None)
        rows.append(value)
        groups.setdefault(row["paired_slot_id"], []).append(value)
    pairs = {key: dict(before=sum(r["before"] for r in group) / 2,
        after=sum(r["after"] for r in group) / 2,
        delta=sum(r["after"] - r["before"] for r in group) / 2)
        for key, group in groups.items() if len(group) == 2 and all(r["comparable"] for r in group)
        and {r["actor"] for r in group} == {"p1", "p2"}}
    return dict(available=True, before_experiment="EX-083", after_experiment="EX-085", matches=rows,
        before_denominators=before_scores, after_denominators=after_scores,
        common_completed_pairs=len(pairs), pairs=pairs,
        missing_common_pairs=sorted(set(groups) - set(pairs)),
        mean_pair_score_delta=sum(p["delta"] for p in pairs.values()) / len(pairs) if pairs else None,
        before_pair_score=sum(p["before"] for p in pairs.values()) / len(pairs) if pairs else None,
        after_pair_score=sum(p["after"] for p in pairs.values()) / len(pairs) if pairs else None,
        interpretation=INTERPRETATION, baseline_interpretation=REFERENCE_INTERPRETATION,
        causal_model_size_effect=False, general_performance_claim=False)
