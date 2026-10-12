"""Bounded Cloud request gate. Semantic review is explicit, never inferred from JSON validity."""

from __future__ import annotations

import concurrent.futures
import copy
import json
import multiprocessing
import os
import signal
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from .. import benchmark as b
from .. import cli
from ..action_validation import replay
from ..battle_adapter import install_identity_adapter
from ..calibration import Trace
from ..concurrency_metrics import request_metrics
from ..constants import OLLAMA_MODEL, POKECHAMP_ROOT
from ..execution import (
    DEFAULT_CONCURRENCY,
    gate_evidence,
    gate_parallel,
    gate_selection,
)
from ..permits import PermitBroker
from .backend import FixedBackend
from .memory import summary_window
from .receipts import (
    cloud_clock,
    halt_study,
    read_stage,
    require_budget,
    require_not_halted,
    seal_stage,
    source_identity,
)
from .state import normalize

PROMPTS = Path(__file__).with_name("prompts")


class GateTrace(Trace):
    """Seal the unmodified source before transmitting an enriched gate request."""

    def __init__(self, output_path):
        self.output_path = output_path
        self.snapshot = None

    def record_input_snapshot(self, *, original_input, delivery_identity):
        if not self.output_path:
            raise ValueError("enriched gate requires a persistent output path")
        self.snapshot = dict(event_seq=1, original_input=original_input,
                             delivery_identity=delivery_identity)
        b.seal_json(Path(str(self.output_path) + ".input-snapshot.json"), self.snapshot)
        return 1


def call(item, broker_path, deadline):
    trace = GateTrace(item.get("output_path"))
    error = None
    field_errors = None
    battle_identity = None
    try:
        from .prompt_versions import asset, identity

        version = item.get("summary_prompt_version", "v1.0.0")
        battle_only = item.get("profile") == "io-battle-only-v1"
        prompt_identity = None if battle_only else identity(version)
        if item.get("summary_prompt_identity", prompt_identity) != prompt_identity:
            raise ValueError("Cloud summary prompt identity mismatch")
        from .battle_prompts import assemble, selected

        battle_identity = selected(item) if battle_only else None
        action_prompt = assemble(
            item["context"], version=battle_identity["version"], declared=battle_identity
        ) if battle_only else assemble()
        cli._load_cloud_credential()
        env = dict(os.environ, POKECHAMP_PERMIT_SOCKET=broker_path)
        env.pop("POKECHAMP_BATCH_DEADLINE", None)
        if deadline is not None:
            env["POKECHAMP_BATCH_DEADLINE"] = str(deadline)
        env.pop("POKECHAMP_CANCEL_PATH", None)
        if battle_only:
            from . import experiment_policy as policy
            from .battle_only_budget import require_cohort
            from .battle_only_protocol import validate_context

            if policy.selected(item):
                policy.same(item, require_cohort(Path(item["study_root"]), item["cohort"]))

            validate_context(item["context"], role=item["role"])
            env.update(POKECHAMP_IO_STUDY_ROOT=item["study_root"],
                       POKECHAMP_IO_COHORT=item["cohort"], POKECHAMP_IO_STAGE="cloud_gate",
                       POKECHAMP_IO_ACTOR=item["id"])
        env.update(POKECHAMP_TRANSPORT_POLICY="legacy-300-v1", POKECHAMP_PROVIDER="ollama")
        backend = FixedBackend(environ=env, trace_sink=trace)
        if battle_only:
            backend.io_profile = "io-battle-only-v1"
            backend.battle_prompt_identity = battle_identity
        backend.role = item["role"]
        backend.summary_prompt_identity = prompt_identity
        backend.input_context = item["context"]
        from ..observation import validate_selection

        backend.observation_backend = validate_selection(item)
        user_prompt = json.dumps(item["context"], ensure_ascii=False)
        if battle_only and battle_identity["version"] in ("v1.3.0", "v1.4.0"):
            if battle_identity["version"] == "v1.4.0":
                from ..observation.delivery import build
            else:
                from ..effects.delivery import build

            backend.delivery = build(item["context"], kind="battle")
            action_prompt, user_prompt = backend.delivery.system_prompt, backend.delivery.user_json
        backend.get_LLM_action(
            system_prompt=action_prompt
            if item["role"] == "self_action"
            else asset(item["role"], version)[0],
            user_prompt=user_prompt,
            model=OLLAMA_MODEL,
            temperature=0.0,
            json_format=False,
            battle=SimpleNamespace(turn=item["context"]["identity"]["showdown_turn"]),
        )
    except Exception as exc:
        from ..effects import EffectReferenceError
        from .battle_prompts import FieldCoverageError

        error = getattr(exc, "category", "configuration")
        if isinstance(exc, FieldCoverageError):
            field_errors = exc.paths
        elif isinstance(exc, EffectReferenceError):
            field_errors = [str(exc)]
    payload = getattr(trace, "payload", {})
    from .experiment_policy import selected as selected_policy

    row = dict(
        **selected_policy(item),
        item_id=item["id"],
        role=item["role"],
        context=item["context"],
        **({"battle_prompt_identity": battle_identity} if battle_identity is not None else {}),
        **({"input_field_errors": field_errors} if field_errors is not None else {}),
        trace=payload,
        **({"input_snapshot": trace.snapshot} if trace.snapshot is not None else {}),
        category=error,
        valid=error is None and payload.get("validation", {}).get("output_contract_valid") is True,
        **item.get("metadata", {}),
    )
    # Seal in the worker before IPC so coordinator interruption cannot discard
    # an already completed provider response.
    if item.get("output_path"):
        b.seal_json(Path(item["output_path"]), row)
    return row


def summary_context(bundle, cutoff, previous=None):
    events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
    protocol = [e for e in events if e["event_type"] == "protocol_in" and e["event_seq"] < cutoff]
    requests = [
        json.loads(line[9:])
        for e in protocol
        for line in e["protocol"].splitlines()
        if line.startswith("|request|") and line[9:]
    ]
    manifest = json.loads((bundle / "manifest.json").read_text())
    own = next(t["showdown_team"] for t in manifest["teams"] if t["role"] == "player")
    cwd = Path.cwd()
    try:
        os.chdir(POKECHAMP_ROOT)
        install_identity_adapter()
        battle, _ = replay(bundle / "events.jsonl", through=cutoff)
        decision = next(e for e in events if e["event_seq"] == cutoff)
        value, _ = normalize(
            battle,
            requests[-1],
            own,
            protocol,
            battle_id=bundle.name,
            actor_id=manifest["metadata"]["actor_id"],
            decision_seq=decision["decision_seq"],
        )
    finally:
        os.chdir(cwd)
    from .memory import summary_context as build_summary_context

    return build_summary_context(value, protocol, previous=previous)


def summary_boundaries(bundle, *, through=None):
    events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
    sent = sorted(
        {
            e["decision_seq"]
            for e in events
            if e["event_type"] == "wire_action"
            and e.get("send_status") == "sent"
            and e.get("action", "").startswith("/choose")
        }
    )
    starts = {
        e["decision_seq"]: e["event_seq"] for e in events if e["event_type"] == "decision_start"
    }
    return [
        starts[sent[i]]
        for i in range(10, len(sent), 10)
        if through is None or starts[sent[i]] <= through
    ]


def text_of(row):
    return row["trace"].get("raw_content", row["trace"].get("content", ""))


def prepare_inputs(offline, battle_root, *, concurrency=DEFAULT_CONCURRENCY):
    """Construct the complete declared corpus without spending the Cloud budget."""
    gate_selection(concurrency)
    if concurrency == 1:
        raise ValueError("comparison gate requires parallel concurrency 2..10")
    read_stage(offline, "offline")
    # All inputs are selected and sealed before the first Cloud request.
    scenes = [b.read_sealed(Path(offline).parent / f"IO-C{i:02}.json") for i in range(1, 16)]
    candidates = []
    for bundle in sorted(Path(battle_root).glob("io-*-p*")):
        if not b.verify_bundle(bundle)["valid"]:
            raise ValueError("summary source integrity")
        if len(summary_boundaries(bundle)) >= 3:
            candidates.append(bundle)
    if len(candidates) < 4:
        raise ValueError("missing four 30-action summary sources")
    fixtures = [
        {
            "bundle": str(p),
            "sha256": b.digest(p / "events.jsonl"),
            "cutoffs": summary_boundaries(p)[:3],
            "source_actor_method": json.loads((p / "manifest.json").read_text())["model"]["method"],
        }
        for p in candidates[:4]
    ]
    templates = {}
    for scene in scenes:
        bundle = Path(battle_root) / scene["identity"]["battle_id"]
        cutoff = max(e["event_seq"] for e in scene["recent_events"]) + 1
        for boundary in summary_boundaries(bundle, through=cutoff):
            key = (str(bundle), boundary)
            if key not in templates:
                templates[key] = summary_context(bundle, boundary)
    for fixture in fixtures:
        for cutoff in fixture["cutoffs"]:
            key = (fixture["bundle"], cutoff)
            if key not in templates:
                templates[key] = summary_context(Path(fixture["bundle"]), cutoff)
    return dict(
        **gate_selection(concurrency),
        scenes=scenes,
        summary_fixtures=fixtures,
        source_files=source_identity(),
        summary_templates=[
            {"bundle": k[0], "cutoff": k[1], "context": v} for k, v in templates.items()
        ],
    )


def _collect(
    root, directory, offline, local, study_root, battle_root, stop,
    *, concurrency=DEFAULT_CONCURRENCY,
):
    def stopped():
        return stop.is_set() or (directory / "STOP").exists()

    read_stage(local, "fake12")
    directory.mkdir(parents=True, exist_ok=False)
    inputs = prepare_inputs(offline, battle_root, concurrency=concurrency)
    parallel = gate_parallel(inputs)
    scenes = inputs["scenes"]
    fixtures = inputs["summary_fixtures"]
    templates = {
        (row["bundle"], row["cutoff"]): row["context"] for row in inputs["summary_templates"]
    }
    b.seal_json(directory / "inputs.json", inputs)
    if stopped():
        raise ValueError("interrupted")
    clock = cloud_clock(study_root)
    require_budget(clock)
    rows = []
    failed = False
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="pc-io-gate-") as temp:
        with PermitBroker(
            Path(temp) / "broker.sock", parallel, {OLLAMA_MODEL: parallel}, deadline=clock["stop_new_work_at"]
        ) as broker:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=parallel, mp_context=multiprocessing.get_context("spawn")
            ) as pool:

                def submit(item, denominator, **metadata):
                    if stopped():
                        broker.stop()
                        raise ValueError("interrupted")
                    require_budget(clock)
                    item = dict(
                        item,
                        metadata=dict(denominator=denominator, **metadata),
                        output_path=str(directory / f"{item['id']}.json"),
                    )
                    b.seal_json(
                        directory / f"intent-{item['id']}.json",
                        dict(item, submitted_at=time.time()),
                    )
                    return pool.submit(call, item, str(broker.path), clock["stop_new_work_at"])

                def drain(future):
                    while True:
                        if stopped():
                            broker.stop()
                        try:
                            return future.result(timeout=0.2)
                        except concurrent.futures.TimeoutError:
                            continue

                def one(item, denominator):
                    nonlocal failed
                    row = drain(submit(item, denominator))
                    rows.append(row)
                    failed |= not row["valid"] or stopped()
                    if failed:
                        broker.stop()
                    return row

                # C's historical memory is generated with the runtime's 10/3 cadence.
                cache = {}
                for scene in scenes:
                    bundle = Path(battle_root) / scene["identity"]["battle_id"]
                    case_cutoff = max(e["event_seq"] for e in scene["recent_events"]) + 1
                    summaries, consolidated, previous_cutoff = [], None, 0
                    for cutoff in summary_boundaries(bundle, through=case_cutoff):
                        key = (bundle.name, cutoff)
                        if key in cache:
                            summaries, consolidated, previous_cutoff = copy.deepcopy(cache[key])
                            continue
                        context = summary_window(
                            templates[str(bundle), cutoff],
                            previous_cutoff,
                            previous=summaries[-1] if summaries else consolidated,
                        )
                        item = dict(
                            id=f"c-input-{bundle.name}-{cutoff}", role="summary", context=context
                        )
                        row = one(item, "c_input_summary")
                        if failed:
                            break
                        summaries.append(text_of(row))
                        previous_cutoff = cutoff
                        if len(summaries) == 3:
                            context["summaries"] = summaries
                            row = one(
                                dict(
                                    id=item["id"] + "-rollup",
                                    role="summary_rollup",
                                    context=context,
                                ),
                                "c_input_summary",
                            )
                            if failed or stopped():
                                failed = True
                                broker.stop()
                                break
                            consolidated, summaries = text_of(row), []
                        cache[key] = copy.deepcopy((summaries, consolidated, previous_cutoff))
                    scene["condition_id"] = "C"
                    if summaries or consolidated:
                        scene["battle_summary"] = dict(
                            battle_id=scene["identity"]["battle_id"],
                            actor_id=scene["identity"]["actor_id"],
                            text=summaries[-1] if summaries else consolidated,
                        )
                    if failed:
                        break
                for concurrency in (1, parallel):
                    for repeat in range(3):
                        if failed:
                            break
                        items = []
                        for i, scene in enumerate(scenes, 1):
                            for condition in ("B", "C"):
                                context = copy.deepcopy(scene)
                                context["condition_id"] = condition
                                if condition == "B":
                                    context["battle_summary"] = None
                                items.append(
                                    dict(
                                        id=f"action-c{concurrency}-r{repeat}-{condition}-{i}",
                                        role="self_action",
                                        context=context,
                                    )
                                )
                        # Bounded submission prevents queued calls after a terminal failure.
                        for offset in range(0, len(items), concurrency):
                            if failed:
                                break
                            require_budget(clock)
                            futures = {
                                submit(
                                    item, "action180", concurrency=concurrency, repeat=repeat
                                ): item
                                for item in items[offset : offset + concurrency]
                            }
                            for future in concurrent.futures.as_completed(futures):
                                row = drain(future)
                                rows.append(row)
                                if not row["valid"] or stopped():
                                    failed = True
                                    broker.stop()
                for repeat in range(3):
                    for i, fixture in enumerate(fixtures):
                        if failed:
                            break
                        summaries, previous_cutoff = [], 0
                        for j, cutoff in enumerate(fixture["cutoffs"]):
                            context = summary_window(
                                templates[fixture["bundle"], cutoff],
                                previous_cutoff,
                                previous=summaries[-1] if summaries else None,
                            )
                            row = one(
                                dict(
                                    id=f"summary-r{repeat}-f{i}-s{j}",
                                    role="summary",
                                    context=context,
                                ),
                                "summary48",
                            )
                            if failed:
                                break
                            summaries.append(text_of(row))
                            previous_cutoff = cutoff
                        if not failed:
                            context["summaries"] = summaries
                            one(
                                dict(
                                    id=f"summary-r{repeat}-f{i}-rollup",
                                    role="summary_rollup",
                                    context=context,
                                ),
                                "summary48",
                            )
            snapshot = broker.snapshot()
    actions = [r for r in rows if r["denominator"] == "action180"]
    first = request_metrics([r["trace"] for r in actions if r["concurrency"] == 1])
    second = request_metrics([r["trace"] for r in actions if r["concurrency"] == parallel])
    counts = {
        name: sum(r["denominator"] == name for r in rows)
        for name in ("action180", "summary48", "c_input_summary")
    }
    technical = (
        not failed
        and not stopped()
        and counts["action180"] == 180
        and counts["summary48"] == 48
        and second["maximum_account_http_overlap"] == parallel
        and first["http_p95_ms"] is not None
        and second["http_p95_ms"] is not None
        and second["http_p95_ms"] <= 2 * first["http_p95_ms"]
    )
    result = dict(
        **gate_evidence(inputs),
        passed=False,
        technical_passed=technical,
        semantic_review="pending",
        stop_requested=stopped(),
        study_root=str(study_root),
        counts=counts,
        failures=sum(not r["valid"] for r in rows),
        sequential=first,
        parallel=second,
        broker=snapshot,
        elapsed_seconds=time.time() - started,
        cloud_clock=clock,
        call_outputs={
            r["item_id"] + ".json": b.digest(directory / (r["item_id"] + ".json")) for r in rows
        },
    )
    b.seal_json(directory / "collection.json", result)
    if not technical:
        return seal_stage(
            directory / "result.json",
            "cloud_gate",
            local,
            result,
            [directory / "collection.json", directory / "inputs.json"],
        )
    return result


def finish(directory, local, review):
    """The reviewer records each factual/temporal/identity check with cited input evidence."""
    collection = b.read_sealed(directory / "collection.json")
    audit = b.read_sealed(Path(review))
    outputs = collection["call_outputs"]
    if not collection["technical_passed"] or audit.get("collection_sha256") != b.digest(
        directory / "collection.json"
    ):
        raise ValueError("invalid Cloud review predecessor")
    expected = set(outputs)
    if set(audit.get("calls", {})) != expected:
        raise ValueError("semantic review denominator mismatch")
    for name, digest in outputs.items():
        if b.digest(directory / name) != digest:
            raise ValueError("Cloud output drift")
        row = b.read_sealed(directory / name)
        check = audit["calls"][name]
        if (
            not row["valid"]
            or not check.get("evidence")
            or any(
                check.get(k) is not True
                for k in ("facts", "timing", "identity", "expected", "must_not")
            )
        ):
            raise ValueError("semantic review failed")
    # Copy as a sealed component in the stage directory so the chain verifies it.
    b.seal_json(directory / "semantic-review.json", audit)
    return seal_stage(
        directory / "result.json",
        "cloud_gate",
        local,
        dict(collection, passed=True, semantic_review="passed"),
        [
            directory / "collection.json",
            directory / "inputs.json",
            directory / "semantic-review.json",
        ],
    )


def collect(
    root, directory, offline, local, study_root, battle_root,
    *, concurrency=DEFAULT_CONCURRENCY,
):
    require_not_halted(study_root)
    if directory.exists():
        raise FileExistsError("Cloud stage output already exists; preserve it")
    stop = threading.Event()
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in handlers:
        signal.signal(sig, lambda *_: stop.set())
    try:
        result = _collect(
            root, directory, offline, local, study_root, battle_root, stop, concurrency=concurrency
        )
        if not result.get("technical_passed"):
            halt_study(study_root, "cloud_gate", directory / "result.json")
        return result
    except Exception as exc:
        directory.mkdir(parents=True, exist_ok=True)
        calls = []
        for path in directory.glob("*.json"):
            row = b.read_sealed(path)
            if isinstance(row, dict) and "item_id" in row:
                calls.append(row)
        category = getattr(exc, "category", "configuration")
        if str(exc) in ("budget_stop", "interrupted"):
            category = str(exc)
        failure = dict(
            passed=False,
            stage="cloud_gate",
            category=category,
            error_type=type(exc).__name__,
            error=str(exc),
            counts={
                name: sum(r["denominator"] == name for r in calls)
                for name in ("action180", "summary48", "c_input_summary")
            },
            submitted_intents=len(list(directory.glob("intent-*.json"))),
            source_files=source_identity(),
            outputs={p.name: b.digest(p) for p in directory.glob("*.json")},
        )
        b.seal_json(directory / "result.json", failure)
        halt_study(study_root, category, directory / "result.json")
        return failure
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
