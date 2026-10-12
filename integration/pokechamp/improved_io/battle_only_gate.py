"""B-only90 Cloud qualification with explicit fact review and worker response seals."""

from __future__ import annotations

import concurrent.futures
import fcntl
import hashlib
import json
import multiprocessing
import signal
import tempfile
import threading
import time
from pathlib import Path

from .. import benchmark as b
from ..concurrency_metrics import request_metrics
from ..constants import OLLAMA_MODEL
from ..execution import (
    DEFAULT_CONCURRENCY,
    concurrency_fields,
    gate_evidence,
    gate_parallel,
    has_concurrency_policy,
)
from ..permits import PermitBroker
from . import battle_only_budget as budget
from . import experiment_policy as policy
from .battle_only_protocol import (
    PROFILE,
    read_ref,
    read_stage,
    ref,
    seal_stage,
    validate_context,
)
from .battle_prompts import selected
from .cloud_gate import call
from .receipts import require_budget


def schedule(parallel=DEFAULT_CONCURRENCY):
    concurrency_fields(parallel)
    if parallel == 1:
        raise ValueError("comparison gate requires parallel concurrency 2..10")
    return [
        dict(id=f"action-c{c}-r{r}-B-{i}", case=f"IO-C{i:02}", concurrency=c, repeat=r)
        for c in (1, parallel)
        for r in range(3)
        for i in range(1, 16)
    ]


def collect(study, prepared, local, directory, *, cohort="c0", worker=call):
    read_stage(prepared, "prepare")
    read_stage(local, "fake32")
    value = budget.require_cohort(study, cohort)
    if value["prepared"] != ref(prepared):
        raise ValueError("Cloud preparation differs from registered cohort")
    manifest = b.read_sealed(Path(prepared).parent / "manifest.json")
    selection = policy.same(manifest, value, b.read_sealed(local))
    from ..observation import OFFICIAL, selection as observation_selection, validate_selection

    observation = observation_selection(OFFICIAL, check_build=False) if validate_selection(manifest) == OFFICIAL else {}
    prompt_identity = selected(manifest)
    scenes = {s["case"]: read_ref(s["input"]) for s in manifest["scenes"]}
    parallel = gate_parallel(manifest)
    concurrency = gate_evidence(manifest)
    items = schedule(parallel)
    inherited = []
    input_origin = None
    if cohort == "e1":
        from .battle_only_recovery import evaluation_inputs

        scenes, inherited, input_origin = evaluation_inputs(study, prepared)
        resume = read_ref(value["recovery"])["resume_schedule"]
        items = [item for item in items if item["id"] in resume]
    directory.mkdir(parents=True, exist_ok=False)
    budget.claim_stage(study, cohort, "cloud_gate", [i["id"] for i in items], directory)
    for row in inherited:
        b.seal_json(directory / (row["item_id"] + ".json"), row)
    b.seal_json(
        directory / "inputs.json",
        dict(
            **selection,
            **concurrency,
            **observation,
            profile=PROFILE,
            battle_prompt_version=prompt_identity["version"],
            battle_prompt_identity=prompt_identity,
            prepared=ref(prepared),
            scenes=scenes,
            schedule=items,
            local=ref(local),
            input_origin=input_origin,
        ),
    )
    stop = threading.Event()
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in handlers:
        signal.signal(sig, lambda *_: stop.set())
    started, error, snapshot = time.time(), None, {}
    rows = []
    b.cli.ARTIFACT_ROOT.mkdir(exist_ok=True, parents=True)
    try:
        with (b.cli.ARTIFACT_ROOT / "benchmark-runtime.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with budget.locked(study):
                clock = budget.clock(study, create=True)
            require_budget(clock)
            with tempfile.TemporaryDirectory(prefix="pc-ab-") as tmp:
                with PermitBroker(
                    Path(tmp) / "p.sock", parallel, {OLLAMA_MODEL: parallel}, deadline=clock["stop_new_work_at"]
                ) as broker:
                    with concurrent.futures.ProcessPoolExecutor(
                        max_workers=parallel, mp_context=multiprocessing.get_context("spawn")
                    ) as pool:
                        # Each sequential/parallel x repeat cell contains15 inputs; no queued work after failure.
                        for c in (1, parallel):
                            for repeat in range(3):
                                cell = [
                                    i
                                    for i in items
                                    if i["concurrency"] == c and i["repeat"] == repeat
                                ]
                                for offset in range(0, len(cell), c):
                                    if error or stop.is_set() or (directory / "STOP").exists():
                                        error = error or "interrupted"
                                        broker.stop()
                                        break
                                    require_budget(clock)
                                    budget.require_cohort(study, cohort)
                                    futures = []
                                    for slot in cell[offset : offset + c]:
                                        context = scenes[slot["case"]]
                                        validate_context(context)
                                        item = dict(
                                            **selection,
                                            **observation,
                                            id=slot["id"],
                                            profile=PROFILE,
                                            role="self_action",
                                            battle_prompt_version=prompt_identity["version"],
                                            battle_prompt_identity=prompt_identity,
                                            context=context,
                                            cohort=cohort,
                                            study_root=str(Path(study).resolve()),
                                            output_path=str(directory / (slot["id"] + ".json")),
                                            metadata=dict(
                                                case=slot["case"],
                                                concurrency=c,
                                                repeat=repeat,
                                                denominator="action90",
                                            ),
                                        )
                                        b.seal_json(
                                            directory / ("intent-" + slot["id"] + ".json"),
                                            dict(
                                                item,
                                                submitted_at=time.time(),
                                                prepared=ref(prepared),
                                            ),
                                        )
                                        futures.append(
                                            pool.submit(
                                                worker,
                                                item,
                                                str(broker.path),
                                                clock["stop_new_work_at"],
                                            )
                                        )
                                    pending = set(futures)
                                    while pending:
                                        if stop.is_set() or (directory / "STOP").exists():
                                            error = "interrupted"
                                            broker.stop()
                                        done, pending = concurrent.futures.wait(
                                            pending,
                                            timeout=0.2,
                                            return_when=concurrent.futures.FIRST_COMPLETED,
                                        )
                                        for future in done:
                                            row = future.result()
                                            rows.append(row)
                                            if not row["valid"]:
                                                error = row["category"] or "output_contract"
                                                broker.stop()
                    snapshot = broker.snapshot()
    except Exception as exc:
        error = str(exc) if str(exc) in ("budget_stop", "interrupted") else type(exc).__name__
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    # Discover worker seals even when IPC was interrupted; never resubmit uncertain intents.
    rows = [
        b.read_sealed(directory / (i["id"] + ".json"))
        for i in schedule(parallel)
        if (directory / (i["id"] + ".json")).exists()
    ]
    first = request_metrics([r["trace"] for r in rows if r["concurrency"] == 1])
    second = request_metrics([r["trace"] for r in rows if r["concurrency"] == parallel])
    technical = (
        not error
        and len(rows) == 90
        and all(r["valid"] for r in rows)
        and first["observed_http_calls"] == 45
        and second["observed_http_calls"] == 45
        and first["maximum_account_http_overlap"] == 1
        and second["maximum_account_http_overlap"] == parallel
        and first["http_p95_ms"] is not None
        and second["http_p95_ms"] is not None
        and second["http_p95_ms"] <= 2 * first["http_p95_ms"]
    )
    intents = len(list(directory.glob("intent-action-*.json")))
    result = dict(
        **selection,
        **concurrency,
        profile=PROFILE,
        technical_passed=technical,
        semantic_review="pending",
        passed=False,
        cohort=cohort,
        prepared=ref(prepared),
        local=ref(local),
        planned=90,
        attempted=intents + len(inherited),
        responses=len(rows),
        new_attempted=intents,
        new_responses=len(rows) - len(inherited),
        inherited_responses=len(inherited),
        input_origin=input_origin,
        valid_outputs=sum(r["valid"] for r in rows),
        failures=sum(not r["valid"] for r in rows),
        uncertain=intents + len(inherited) - len(rows),
        unexecuted=90 - intents - len(inherited),
        error=error,
        sequential=first,
        parallel=second,
        summary_calls=0,
        elapsed_seconds=time.time() - started,
        broker=snapshot,
        usage=budget.usage(study),
        call_outputs={
            r["item_id"] + ".json": b.digest(directory / (r["item_id"] + ".json")) for r in rows
        },
    )
    b.seal_json(directory / "collection.json", result)
    if not technical:
        budget.halt(study, cohort, error or "cloud_technical_gate", directory / "collection.json")
    return result


def validate_review(rows, audit, *, collection_hash):
    if audit.get("collection_sha256") != collection_hash or set(audit.get("calls", {})) != set(
        rows
    ):
        raise ValueError("review identity or denominator mismatch")
    errors = []
    dimensions = ("facts", "identity", "timing", "calculation", "action_contract")
    for name, row in rows.items():
        check = audit["calls"][name]
        if check.get("response_sha256") != row["sha256"]:
            raise ValueError("review response seal mismatch")
        if not isinstance(check.get("evidence"), str) or len(check["evidence"].strip()) < 20:
            raise ValueError("review needs explicit claim/source/input/calculation evidence")
        if not all(type(check.get(d)) is bool for d in dimensions):
            raise ValueError("review dimensions incomplete")
        if not all(check[d] for d in dimensions):
            errors.append(
                dict(
                    item=name,
                    dimensions=[d for d in dimensions if not check[d]],
                    evidence=check["evidence"],
                )
            )
    return errors


def validate_live_collection(directory, collection, rows):
    """Verify actual paid inputs and raw responses independently of the review verdict."""
    if not policy.selected(collection) and not has_concurrency_policy(collection):
        return
    inputs = b.read_sealed(directory / "inputs.json")
    prepared = read_ref(inputs["prepared"])
    manifest = b.read_sealed(Path(inputs["prepared"]["path"]).parent / "manifest.json")
    policy.same(collection, inputs, prepared, manifest)
    identity = manifest["battle_prompt_identity"]
    concurrency = gate_evidence(manifest)
    if gate_evidence(collection) != concurrency or gate_evidence(inputs) != concurrency:
        raise ValueError("Cloud concurrency declaration mismatch")
    if not policy.selected(collection):
        return
    expected = {item["id"] + ".json": item for item in schedule(gate_parallel(manifest))}
    if set(rows) != set(expected) or collection["uncertain"] or collection["failures"]:
        raise ValueError("live Cloud denominator or technical failure")
    for name, row in rows.items():
        policy.same(collection, row)
        item = expected[name]
        trace = row["trace"]
        request = trace["request"]
        context = inputs["scenes"][item["case"]]
        if (row["context"] != context or row["item_id"] != item["id"]
            or row["role"] != "self_action" or row["category"] is not None
            or not row["valid"] or trace["response"].get("http_status") != 200
            or any(row[k] != item[k] for k in ("case", "concurrency", "repeat"))
            or json.loads(trace["user_prompt"]) != context
            or row.get("battle_prompt_identity") != identity
            or request.get("battle_prompt_identity") != identity
            or hashlib.sha256(trace["system_prompt"].encode()).hexdigest()
            != identity["prompt_sha256"]):
            raise ValueError("live Cloud input, prompt or response mismatch")
        validate_context(context)
        from .output import parse_action

        action_request = context["request"]
        parse_action(trace["raw_content"], action_request["legal_actions"],
                     request_kind=action_request["kind"], can_tera=action_request["can_tera"],
                     english_typography=True)
        intent_path = Path(request["request_intent"])
        response_path = Path(request["worker_response"])
        intent, response = b.read_sealed(intent_path), b.read_sealed(response_path)
        policy.same(collection, intent)
        if (intent["actor"] != item["id"] or intent["stage"] != "cloud_gate"
            or response["intent"] != ref(intent_path)
            or response["response"]["message"]["content"] != trace["raw_content"]
            or any(intent["payload"][k] != trace[k] for k in ("system_prompt", "user_prompt"))):
            raise ValueError("live Cloud request journal mismatch")
        read_ref(intent["clock"])
        read_ref(intent["cohort_identity"])


def finish(study, directory, review, *, cohort="c0"):
    collection = b.read_sealed(directory / "collection.json")
    audit = b.read_sealed(review)
    rows = {}
    for name, digest in collection["call_outputs"].items():
        if b.digest(directory / name) != digest:
            raise ValueError("Cloud response drift")
        rows[name] = dict(b.read_sealed(directory / name), sha256=digest)
    errors = validate_review(rows, audit, collection_hash=b.digest(directory / "collection.json"))
    if collection["technical_passed"]:
        validate_live_collection(directory, collection, rows)
    b.seal_json(directory / "semantic-review.json", audit)
    policy.same(collection, b.read_sealed(Path(study) / "study.json"))
    passed = collection["technical_passed"] and not policy.review_blocks(collection, errors)
    result = dict(
        collection,
        passed=passed,
        semantic_review="passed" if not errors else "failed",
        semantic_errors=errors,
    )
    result = seal_stage(
        directory / "result.json",
        "cloud_gate",
        collection["local"]["path"],
        result,
        [
            directory / "collection.json",
            directory / "inputs.json",
            directory / "semantic-review.json",
        ],
    )
    if not passed:
        budget.halt(study, cohort, "cloud_semantic_gate", directory / "result.json")
    return result
