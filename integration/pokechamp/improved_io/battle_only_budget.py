"""Append-only D-030 request journal, common clock and one paid recovery cohort."""

from __future__ import annotations

import contextlib
import fcntl
import time
from pathlib import Path

from .. import benchmark as b
from . import experiment_policy as policy
from .battle_only_protocol import PROFILE, read_ref, ref
from .receipts import require_budget, source_identity

CAPS = {"cloud_gate": 180, "smoke8": 16, "compare32": 64}
NORMAL = {"cloud_gate": 90, "smoke8": 8, "compare32": 32}


@contextlib.contextmanager
def locked(root):
    with (Path(root) / "ledger.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def definition(selection):
    if selection.get("experiment_policy") in (policy.DIAGNOSTIC, policy.HEAD_TO_HEAD, policy.PROTECTFIX, policy.B2, policy.LEAD):
        raise ValueError("A diagnostic uses its own bounded ledger")
    direct = policy.is_direct(selection)
    return dict(
        **selection,
        profile=PROFILE,
        decision=selection["experiment_policy_identity"]["decision"]
        if selection
        else "D-030",
        call_limit=None if selection else 4000,
        stage_caps={"compare32": 32} if direct else CAPS,
        paid_recovery_limit=0 if direct else 1,
    )


def register(root, prepared):
    root = Path(root)
    prepared_value = b.read_sealed(prepared)
    selection = policy.selected(prepared_value)
    root.mkdir(parents=True, exist_ok=False)
    # A second execution identity cannot bind this prepared cohort to a fresh clock.
    b.seal_json(
        Path(prepared).parent / "study-link.json", dict(study_root=str(root.resolve()))
    )
    b.seal_json(
        root / "study.json",
        definition(selection),
    )
    (root / "requests").mkdir()
    (root / "cohorts").mkdir()
    b.seal_json(
        root / "cohorts" / "c0.json",
        dict(
            **selection,
            cohort="c0",
            profile=PROFILE,
            prepared=ref(prepared),
            source_files=source_identity(),
            recovery=None,
        ),
    )
    return b.read_sealed(root / "study.json")


def clock(root, *, create=False, now=None):
    path = Path(root) / "cloud-clock.json"
    study = b.read_sealed(Path(root) / "study.json")
    selection = policy.selected(study)
    if study != definition(selection):
        raise ValueError("battle-only budget definition drift")
    if not path.exists():
        if not create:
            raise ValueError("Cloud clock missing")
        if any((Path(root) / "requests").glob("intent-*.json")):
            raise ValueError("Cloud clock removed after dispatch")
        started = time.time() if now is None else now
        original = {}
        if policy.is_linked_repeat(selection):
            cohort = b.read_sealed(Path(root) / "cohorts/c0.json")
            manifest = b.read_sealed(
                Path(cohort["prepared"]["path"]).parent / "manifest.json"
            )
            original = dict(original_first_clock=manifest["original"]["first_clock"])
        b.seal_json(
            path,
            dict(
                profile=PROFILE,
                **selection,
                **original,
                first_dispatch_at=started,
                stop_new_work_at=None if selection else started + 13500,
                cleanup_deadline=None if selection else started + 14400,
                study=ref(Path(root) / "study.json"),
            ),
        )
    value = b.read_sealed(path)
    if value["study"] != ref(Path(root) / "study.json"):
        raise ValueError("clock study reference mismatch")
    policy.same(value, read_ref(value["study"]))
    if (
        value.get("profile") != PROFILE
        or type(value["first_dispatch_at"]) not in (int, float)
        or not 0 < value["first_dispatch_at"] < float("inf")
        or value["stop_new_work_at"]
        != (None if selection else value["first_dispatch_at"] + 13500)
        or value["cleanup_deadline"]
        != (None if selection else value["first_dispatch_at"] + 14400)
    ):
        raise ValueError("invalid battle-only clock")
    if policy.is_linked_repeat(selection):
        read_ref(value["original_first_clock"])
    return value


def require_cohort(root, cohort, *, current=True):
    if policy.is_direct(b.read_sealed(Path(root) / "study.json")) and cohort != "c0":
        raise ValueError("direct32 has no recovery cohort")
    if cohort not in ("c0", "c1", "e1"):
        raise ValueError("unknown recovery cohort")
    value = b.read_sealed(Path(root) / "cohorts" / f"{cohort}.json")
    if value["profile"] != PROFILE or value["cohort"] != cohort:
        raise ValueError("cohort identity drift")
    if (Path(root) / f"halt-{cohort}.json").exists():
        raise ValueError("cohort halted")
    prepared = read_ref(value["prepared"])
    policy.same(value, prepared, b.read_sealed(Path(root) / "study.json"))
    if value["source_files"] != prepared["source_files"]:
        raise ValueError("cohort/preparation source mismatch")
    if current and value["source_files"] != source_identity():
        raise ValueError("source changed during collection")
    if cohort in ("c1", "e1"):
        recovery = read_ref(value["recovery"])
        if cohort == "c1" and recovery["kind"] not in (
            "input",
            "treatment",
            "collection",
        ):
            raise ValueError("paid recovery only for collection-affecting defects")
        if cohort == "e1" and (
            recovery["kind"] != "evaluation"
            or recovery.get("resume_unexecuted") is not True
        ):
            raise ValueError("evaluation resume requires intact-response provenance")
        if recovery["clock"] != ref(Path(root) / "cloud-clock.json"):
            raise ValueError("recovery clock mismatch")
        read_ref(recovery["original"])
        read_ref(recovery["verification"])
    return value


def halt(root, cohort, category, evidence):
    path = Path(root) / f"halt-{cohort}.json"
    if not path.exists():
        b.seal_json(
            path,
            dict(
                profile=PROFILE,
                cohort=cohort,
                category=category,
                evidence=ref(evidence),
                stopped_at=time.time(),
            ),
        )
    return b.read_sealed(path)


def claim_stage(root, cohort, stage, schedule, output):
    """Reserve the entire stage once; new directories cannot reset denominators."""
    root = Path(root)
    with locked(root):
        value = require_cohort(root, cohort)
        if stage not in NORMAL or len(schedule) != len(set(schedule)):
            raise ValueError("invalid stage schedule")
        caps = b.read_sealed(root / "study.json")["stage_caps"]
        if stage not in caps or (policy.is_direct(value) and cohort != "c0"):
            raise ValueError("stage or recovery not authorized")
        wanted = NORMAL[stage]
        if cohort == "c1":
            recovery = read_ref(value["recovery"])
            allowed = recovery["recollect"].get(stage, [])
            if set(schedule) != set(allowed):
                raise ValueError(
                    "recovery schedule differs from affected comparison units"
                )
        elif cohort == "e1" and stage == "cloud_gate":
            recovery = read_ref(value["recovery"])
            if set(schedule) != set(recovery["resume_schedule"]):
                raise ValueError("only previously unexecuted requests may be submitted")
        elif len(schedule) != wanted:
            raise ValueError("initial stage denominator mismatch")
        previous = [
            b.read_sealed(p) for p in (root / "cohorts").glob(f"*-{stage}.json")
        ]
        reserved = 0
        for prior in previous:
            if (
                stage == "cloud_gate"
                and (root / f"halt-{prior['cohort']}.json").exists()
            ):
                # Closed cohorts release only never-dispatched request reservations.
                # Their original planned/attempted denominators remain in the claim.
                reserved += sum(
                    b.read_sealed(p)["cohort"] == prior["cohort"]
                    and b.read_sealed(p)["stage"] == stage
                    for p in (root / "requests").glob("intent-*.json")
                )
            else:
                reserved += len(prior["schedule"])
        if reserved + len(schedule) > caps[stage]:
            raise ValueError("stage collection cap exhausted")
        b.seal_json(
            root / "cohorts" / f"{cohort}-{stage}.json",
            dict(
                cohort=cohort,
                stage=stage,
                schedule=schedule,
                output=str(Path(output).resolve()),
                cohort_identity=ref(root / "cohorts" / f"{cohort}.json"),
            ),
        )


def reserve(root, cohort, stage, actor, payload):
    """Reserve every HTTP, including failures, uncertain and upstream calls."""
    root = Path(root)
    with locked(root):
        value = require_cohort(root, cohort)
        claim = b.read_sealed(root / "cohorts" / f"{cohort}-{stage}.json")
        read_ref(claim["cohort_identity"])
        if stage == "cloud_gate" and actor not in claim["schedule"]:
            raise ValueError("unregistered gate request")
        if stage != "cloud_gate" and not any(
            f"/{s}-a1/" in actor for s in claim["schedule"]
        ):
            raise ValueError("unregistered battle request")
        current = clock(root, create=True)
        require_budget(current)
        intents = sorted((root / "requests").glob("intent-*.json"))
        limit = b.read_sealed(root / "study.json")["call_limit"]
        if limit is not None and len(intents) >= limit:
            raise ValueError("call budget exhausted")
        number = len(intents) + 1
        path = root / "requests" / f"intent-{number:06}.json"
        gate_marker = (
            root / "requests" / f"gate-{cohort}-{actor}.json"
            if stage == "cloud_gate"
            else None
        )
        if gate_marker is not None and gate_marker.exists():
            raise ValueError("duplicate gate submission")
        b.seal_json(
            path,
            dict(
                profile=PROFILE,
                **policy.selected(current),
                number=number,
                cohort=cohort,
                stage=stage,
                actor=actor,
                reserved_at=time.time(),
                clock=ref(root / "cloud-clock.json"),
                cohort_identity=ref(root / "cohorts" / f"{cohort}.json"),
                prepared=value["prepared"],
                payload=payload,
            ),
        )
        if gate_marker is not None:
            b.seal_json(gate_marker, ref(path))
        return path


def preserve_response(intent, response):
    if hasattr(response, "model_dump"):
        response = response.model_dump(mode="json")
    path = Path(intent).with_name(Path(intent).name.replace("intent-", "response-"))
    b.seal_json(
        path, dict(intent=ref(intent), received_at=time.time(), response=response)
    )
    return path


def usage(root):
    root = Path(root)
    rows = []
    for path in sorted((root / "requests").glob("intent-*.json")):
        value = b.read_sealed(path)
        read_ref(value["clock"])
        response = path.with_name(path.name.replace("intent-", "response-"))
        rows.append(
            dict(
                number=value["number"],
                cohort=value["cohort"],
                stage=value["stage"],
                actor=value["actor"],
                response=response.exists(),
            )
        )
    registration = b.read_sealed(root / "study.json")
    selection = policy.selected(registration)
    limit = None if selection else 4000
    if registration["call_limit"] != limit:
        raise ValueError("request limit drift")
    return dict(
        **selection,
        call_limit=limit,
        reserved_calls=len(rows),
        responses=sum(r["response"] for r in rows),
        uncertain=sum(not r["response"] for r in rows),
        remaining_calls=None if limit is None else limit - len(rows),
        rows=rows,
    )


def recover(root, defect, prepared):
    """Require independent evidence of every affected pair before recollection."""
    root = Path(root)
    if policy.is_direct(b.read_sealed(root / "study.json")):
        raise ValueError("direct32 prohibits recovery/recollection")
    record = b.read_sealed(defect)
    from .battle_only_protocol import read_stage

    new = read_stage(prepared, "prepare")
    policy.same(new, b.read_sealed(root / "study.json"))
    required = {
        "kind",
        "discovered_at_stage",
        "symptom",
        "original",
        "verification",
        "source_before",
        "source_after",
        "impact",
        "recollect",
        "evidence",
        "scope_proven",
        "model_error_reclassified",
    }
    if not required <= set(record) or record["kind"] not in (
        "test",
        "evaluation",
        "rubric",
        "input",
        "treatment",
        "collection",
    ):
        raise ValueError("incomplete defect record")
    if (
        record["scope_proven"] is not True
        or record["model_error_reclassified"] is not False
        or not record["impact"]
        or not record["evidence"]
    ):
        raise ValueError("unproven impact or model error is not recoverable")
    old = read_ref(record["original"])
    verification = read_ref(record["verification"])
    if not all(
        verification.get(k) is True
        for k in ("independent", "reproduced", "regressions")
    ):
        raise ValueError("independent reproduction and regressions required")
    if record["source_after"] != new["source_files"]:
        raise ValueError("recovery source mismatch")
    if record["source_before"] != old["source_files"]:
        raise ValueError("original source mismatch")
    if record["kind"] in ("test", "evaluation", "rubric"):
        if record["recollect"]:
            raise ValueError(
                "intact responses must be symmetrically reevaluated "
                "without recollection"
            )
        if record.get("symmetric_response_ids") != record["impact"]:
            raise ValueError("all impacted responses require symmetric review")
        if record["kind"] == "rubric" and record.get("posthoc_disclosure") is not True:
            raise ValueError("rubric correction needs explicit posthoc disclosure")
        target = root / "analyses" / (Path(defect).stem + ".json")
        b.seal_json(target, dict(record, defect=ref(defect), prepared=ref(prepared)))
        if record.get("resume_unexecuted"):
            from .battle_only_recovery import register_evaluation_resume

            return register_evaluation_resume(root, record, prepared, target)
        return b.read_sealed(target)
    with locked(root):
        current = clock(root, create=False)
        require_budget(current)
        remaining = usage(root)["remaining_calls"]
        if remaining is not None and remaining <= 0:
            raise ValueError("call budget exhausted")
        if not (root / "halt-c0.json").exists():
            raise ValueError(
                "original collection must be halted before source recovery"
            )
        requalification = record.get("requalification", {})
        if set(requalification) - {"cloud_gate", "smoke8"}:
            raise ValueError(
                "main comparison cannot be recollected as mere requalification"
            )
        for stage, slots in record["recollect"].items():
            if stage not in NORMAL or not slots or len(slots) != len(set(slots)):
                raise ValueError("invalid recollection unit")
            if stage == "cloud_gate":
                if len(slots) != 90:
                    raise ValueError("shared gate input repair requires full90 gate")
            else:
                for slot in slots:
                    if slot[:2] not in ("A-", "B-") or (
                        ("B-" if slot.startswith("A-") else "A-") + slot[2:]
                        not in slots
                    ):
                        raise ValueError(
                            "recollection must include both A/B paired sides"
                        )
            affected = set(record["impact"].get(stage, []))
            qualification = set(requalification.get(stage, []))
            if affected & qualification or set(slots) != affected | qualification:
                raise ValueError(
                    "recollection omits impacted units or qualification provenance"
                )
            if qualification:
                if len(slots) != NORMAL[stage] or not record.get(
                    "requalification_reason"
                ):
                    raise ValueError(
                        "source requalification needs full gate and explicit reason"
                    )
                original_claim = b.read_sealed(root / "cohorts" / f"c0-{stage}.json")
                original_result = b.read_sealed(
                    Path(original_claim["output"]) / "result.json"
                )
                if original_result.get("passed") is not True:
                    raise ValueError(
                        "failed model gate cannot be reclassified as requalification"
                    )
        if not set(record["impact"]) <= set(record["recollect"]):
            raise ValueError("recollection omits affected stages")
        target = root / "recovery-c1.json"
        b.seal_json(
            target,
            dict(
                record,
                clock=ref(root / "cloud-clock.json"),
                usage_before=usage(root),
                defect=ref(defect),
            ),
        )
        b.seal_json(
            root / "cohorts" / "c1.json",
            dict(
                profile=PROFILE,
                **policy.selected(new),
                cohort="c1",
                prepared=ref(prepared),
                source_files=new["source_files"],
                recovery=ref(target),
            ),
        )
        return b.read_sealed(target)
