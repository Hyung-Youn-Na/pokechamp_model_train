"""D-030 A/B-only identity and immutable stage chain, independent of summary gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import benchmark as b
from ..execution import concurrency_fields, gate_evidence, gate_parallel
from . import experiment_policy as policy
from .conditions import CONDITIONS, require_parallel
from .gate import validate_input
from .receipts import offline_receipt, source_identity, verify_outputs

PROFILE = "io-battle-only-v1"
CONDITIONS_AB = {k: CONDITIONS[k] for k in ("A", "B")}
STAGES = ("prepare", "fake32", "cloud_gate", "smoke8", "compare32")


def is_profile(config):
    return config.get("profile") == PROFILE


def validate_context(context, *, role="self_action"):
    if (
        role != "self_action"
        or context.get("condition_id") != "B"
        or context.get("battle_summary") is not None
        or context.get("lesson_memory") != []
    ):
        raise ValueError("battle-only role, condition or memory contamination")
    return validate_input(context)


def replay_window(bundle, cutoff, prefix):
    """Match live boundaries: exclude protocol consumed at the tenth prior sent decision."""
    events = [json.loads(s) for s in (Path(bundle) / "events.jsonl").read_text().splitlines()]
    sent = {
        e["decision_seq"]
        for e in events
        if e["event_type"] == "wire_action"
        and e["event_seq"] < cutoff
        and e.get("send_status") == "sent"
        and e.get("action", "").startswith("/choose")
    }
    starts = sorted(
        e["event_seq"]
        for e in events
        if e["event_type"] == "decision_start" and e.get("decision_seq") in sent
    )
    boundary = starts[-10] if len(starts) >= 10 else 0
    return [e for e in prefix if boundary < e["event_seq"] < cutoff]


def ref(path):
    return {"path": str(Path(path).resolve()), "sha256": b.digest(path)}


def read_ref(reference):
    path = Path(reference["path"])
    if b.digest(path) != reference["sha256"]:
        raise ValueError("reference drift")
    return b.read_sealed(path)


def read_stage(path, stage, *, current=True):
    path = Path(path)
    value = b.read_sealed(path)
    if (
        value.get("profile") != PROFILE
        or value.get("stage") != stage
        or value.get("passed") is not True
        or value.get("conditions") != CONDITIONS_AB
    ):
        raise ValueError(f"battle-only {stage} gate did not pass")
    policy.selected(value)
    if policy.is_direct(value):
        from .direct32 import read_stage as read_direct

        return read_direct(path, stage, current=current)
    if current and value.get("source_files") != source_identity():
        raise ValueError("battle-only source drift")
    verify_outputs(path, value)
    from ..observation import OFFICIAL, selection as observation_selection, validate_selection

    observation_backend = validate_selection(value)
    if stage == "prepare":
        offline = path.parent / "offline" / "result.json"
        if b.digest(offline) != value["offline"]["sha256"]:
            raise ValueError("offline reference drift")
        receipt = offline_receipt(offline, current=current)
        if receipt.get("input_profile") != PROFILE:
            raise ValueError("full-prefix offline input is not operational input")
        manifest = b.read_sealed(path.parent / "manifest.json")
        policy.same(value, manifest)
        if validate_selection(manifest) != observation_backend:
            raise ValueError("preparation observation source mismatch")
        if observation_backend == OFFICIAL and any(manifest.get(k) != value.get(k) for k in observation_selection(OFFICIAL, check_build=False)):
            raise ValueError("preparation observation identity mismatch")
        if gate_evidence(value) != gate_evidence(manifest):
            raise ValueError("preparation concurrency declaration mismatch")
        if policy.selected(manifest) and manifest.get("battle_prompt_version") != "v1.1.0":
            raise ValueError("live policy requires battle prompt v1.1.0")
        from .battle_prompts import assemble, selected

        prompt_identity = selected(manifest) if current else manifest.get("battle_prompt_identity")
        if "battle_prompt_identity" in manifest:
            prompt_record = read_ref(manifest["battle_prompt"])
            if (prompt_record["battle_prompt_identity"] != prompt_identity
                or prompt_record["battle_prompt_version"] != manifest["battle_prompt_version"]
                or hashlib.sha256(prompt_record["system_prompt"].encode()).hexdigest()
                != manifest["prompt_sha256"]
                or manifest["prompt_sha256"] != prompt_identity["prompt_sha256"]):
                raise ValueError("prepared battle prompt mismatch")
            if current and prompt_record["system_prompt"] != assemble(
                version=prompt_identity["version"], declared=prompt_identity
            ):
                raise ValueError("prepared battle system prompt mismatch")
        if manifest["source_files"] != value["source_files"]:
            raise ValueError("prepare source mismatch")
        if len(manifest["scenes"]) != 15 or {s["case"] for s in manifest["scenes"]} != {
            f"IO-C{i:02}" for i in range(1, 16)
        }:
            raise ValueError("prepared scene denominator mismatch")
        audit = b.read_sealed(path.parent / "input-audit.json")
        if (
            audit.get("passed") is not True
            or len(audit["cases"]) != 15
            or not all(c["passed"] and c["actual_input_reachability"] for c in audit["cases"])
        ):
            raise ValueError("actual input reachability gate missing")
        for scene in manifest["scenes"]:
            context = read_ref(scene["input"])
            validate_context(context)
            if current:
                assemble(context, version=prompt_identity["version"], declared=prompt_identity)
            read_ref(scene["evidence"])
        read_ref(manifest["criteria"])
    else:
        previous = value["previous"]
        read_ref(previous)
        parent = read_stage(previous["path"], STAGES[STAGES.index(stage) - 1], current=current)
        policy.same(value, parent)
    if stage in ("fake32", "smoke8", "compare32"):
        plan = read_ref(value["benchmark"])
        if not is_profile(plan["config"]) or plan["conditions"] != CONDITIONS_AB:
            raise ValueError("foreign benchmark in battle-only receipt")
        policy.same(value, plan["execution"]["evidence"])
        directory = Path(value["benchmark"]["path"]).parent
        plan = b.verify_plan(directory)
        attempts = b.load_attempts(directory)
        b.validate_attempts(plan, attempts)
        expected = len(plan["schedule"])
        if (
            value["completed"] != expected
            or value["planned"] != expected
            or value["maximum_observed_battles"] != min(plan["execution"]["battle_concurrency"], expected)
            or value["summary_calls"] != 0
            or value["rollup_calls"] != 0
        ):
            raise ValueError("battle-only stage qualification mismatch")
        if stage == "fake32":
            memory = b.read_sealed(path.parent / "no-memory.json")
            if (
                expected != 32
                or memory.get("passed") is not True
                or memory["actions"] != 31
                or memory["summaries"] != 0
                or memory["rollups"] != 0
                or memory["memory_archive"]
            ):
                raise ValueError("B31 no-memory evidence missing")
        if len(attempts) != value["completed"] or not all(a["eligible"] for a in attempts):
            raise ValueError("battle-only completed denominator drift")
        for attempt in attempts:
            for actor in attempt["actors"].values():
                if not actor.get("bundle") or not b.verify_bundle(Path(actor["bundle"]))["valid"]:
                    raise ValueError("actor bundle drift")
    if stage == "cloud_gate":
        collection = b.read_sealed(path.parent / "collection.json")
        if (
            collection.get("technical_passed") is not True
            or len(collection["call_outputs"]) != 90
            or value.get("semantic_review") not in ("passed", "failed")
            or policy.review_blocks(value, value.get("semantic_errors", []))
        ):
            raise ValueError("battle-only Cloud denominator or review gate mismatch")
        inputs = b.read_sealed(path.parent / "inputs.json")
        policy.same(value, collection, inputs)
        from .battle_only_gate import validate_live_collection, validate_review

        rows = {}
        for name, digest in collection["call_outputs"].items():
            if Path(name).name != name or b.digest(path.parent / name) != digest:
                raise ValueError("battle-only Cloud response drift")
            row = b.read_sealed(path.parent / name)
            policy.same(value, row)
            if not row["valid"]:
                raise ValueError("invalid action response in passed gate")
            validate_context(row["context"], role=row["role"])
            rows[name] = dict(row, sha256=digest)
        validate_live_collection(path.parent, collection, rows)
        audit = b.read_sealed(path.parent / "semantic-review.json")
        errors = validate_review(rows, audit, collection_hash=b.digest(path.parent / "collection.json"))
        if (errors != value.get("semantic_errors")
            or value["semantic_review"] != ("failed" if errors else "passed")
            or policy.review_blocks(value, errors)):
            raise ValueError("semantic review contains errors or assessment drift")
    return value


def seal_stage(path, stage, previous, result, outputs):
    selection = policy.selected(result)
    if stage != "prepare":
        parent = read_stage(previous, STAGES[STAGES.index(stage) - 1])
        selection = dict(policy.selected(parent), **gate_evidence(parent))
        from ..observation import OFFICIAL, selection as observation_selection, validate_selection

        if validate_selection(parent) == OFFICIAL:
            selection.update(observation_selection(OFFICIAL, check_build=False))
        if policy.selected(result) and policy.selected(result) != policy.selected(parent):
            raise ValueError("stage policy mismatch")
    value = dict(
        dict(result, **selection),
        profile=PROFILE,
        stage=stage,
        conditions=CONDITIONS_AB,
        source_files=source_identity(),
        outputs={Path(p).name: b.digest(p) for p in outputs},
    )
    if previous:
        value["previous"] = ref(previous)
    b.seal_json(path, value)
    return value


def require_offline(execution):
    require_parallel(execution)
    evidence = execution["evidence"]
    if evidence.get("profile") != PROFILE or any("summary" in k for k in evidence):
        raise ValueError("battle-only execution profile or summary contamination")
    from .battle_prompts import selected

    result = read_stage(evidence["io_offline_gate"], "prepare")
    manifest = b.read_sealed(Path(evidence["io_offline_gate"]).parent / "manifest.json")
    policy.same(evidence, manifest, result)
    if gate_evidence(evidence) != gate_evidence(manifest) or any(
        execution[key] != limit
        for key, limit in concurrency_fields(gate_parallel(manifest)).items()
    ):
        raise ValueError("execution/preparation concurrency mismatch")
    from ..observation import validate_selection

    if validate_selection(evidence) != validate_selection(manifest):
        raise ValueError("execution/preparation observation mismatch")
    if selected(evidence) != selected(manifest):
        raise ValueError("execution/preparation battle prompt mismatch")
    return result


def require_entry(config, execution):
    require_offline(execution)
    evidence = execution["evidence"]
    if policy.is_direct(evidence) and evidence.get("io_transport") != "cloud":
        raise ValueError("direct32 permits only Cloud main comparison")
    if evidence.get("io_transport") == "fake":
        if config != b.BATTLE_ONLY_COMPARE_CONFIG:
            raise ValueError("battle-only fake qualification requires32")
        return
    if evidence.get("io_transport") != "cloud":
        raise ValueError("explicit battle-only transport required")
    if policy.is_direct(evidence):
        from .direct32 import require_entry as require_direct

        return require_direct(config, execution)
    stage = "smoke8" if config == b.BATTLE_ONLY_COMPARE_CONFIG else "cloud_gate"
    gate = read_stage(evidence["io_stage_gate"], stage)
    policy.same(evidence, gate)
    from .battle_only_budget import clock, require_cohort

    cohort = require_cohort(Path(evidence["io_study_root"]), evidence["io_cohort"])
    if cohort["prepared"] != ref(evidence["io_offline_gate"]):
        raise ValueError("battle preparation differs from registered cohort")
    if evidence["io_cohort"] == "c1" and evidence.get("io_recovery") != cohort["recovery"]:
        raise ValueError("battle recovery differs from registered cohort")
    value = clock(Path(evidence["io_study_root"]), create=False)
    if execution["stop_new_work_at"] != value["stop_new_work_at"]:
        raise ValueError("battle-only clock mismatch")
    from .receipts import require_budget

    require_budget(value)


def restrict_schedule(schedule, execution):
    evidence = execution.get("evidence", {})
    if evidence.get("io_transport") == "fake" or evidence.get("io_cohort") != "c1":
        return schedule
    recovery = read_ref(evidence["io_recovery"])
    selected = recovery["recollect"].get(evidence["io_stage"], [])
    if not selected or not set(selected) <= {s["slot_id"] for s in schedule}:
        raise ValueError("recovery outside original schedule")
    for slot in selected:
        if (("B-" if slot.startswith("A-") else "A-") + slot[2:]) not in selected:
            raise ValueError("recovery schedule must preserve A/B pairs")
    return [s for s in schedule if s["slot_id"] in selected]
