"""D-027 resumable collection: a sealed semantic review gates every dependency."""

from __future__ import annotations

import concurrent.futures
import copy
import fcntl
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
from ..execution import DEFAULT_CONCURRENCY, gate_evidence, gate_parallel
from ..permits import PermitBroker
from ..summary_diagnostics.oracle import (
    verify_annotations,
    verify_observation,
    verify_reference,
)
from .cloud_gate import call, prepare_inputs, summary_boundaries, text_of
from .memory import summary_window
from .prompt_versions import PROMPTS, asset, identity
from .receipts import (
    cloud_clock,
    halt_study,
    read_stage,
    require_budget,
    require_not_halted,
    seal_stage,
    source_identity,
)

CHECKS = ("facts", "sides", "timing", "identity", "format", "expected", "must_not")
TOTALS = {"c_input_summary": 8, "summary48": 48, "action180": 180}


def graph(inputs, battle_root):
    """Stable call IDs and dependencies; no model text is needed to plan the corpus."""
    nodes, scene_dependencies = {}, {}
    for i, scene in enumerate(inputs["scenes"], 1):
        bundle = Path(battle_root) / scene["identity"]["battle_id"]
        cutoff = max(e["event_seq"] for e in scene["recent_events"]) + 1
        previous, previous_cutoff, summaries = None, 0, []
        for boundary in summary_boundaries(bundle, through=cutoff):
            key = f"c-input-{bundle.name}-{boundary}"
            nodes[key] = dict(
                id=key,
                role="summary",
                denominator="c_input_summary",
                bundle=str(bundle),
                cutoff=boundary,
                previous_cutoff=previous_cutoff,
                dependencies=[previous] if previous else [],
                previous=previous,
            )
            previous, previous_cutoff = key, boundary
            summaries.append(key)
            if len(summaries) == 3:
                rollup = key + "-rollup"
                nodes[rollup] = dict(
                    nodes[key],
                    id=rollup,
                    role="summary_rollup",
                    dependencies=summaries[:],
                    summaries=summaries[:],
                    previous=nodes[key]["previous"],
                )
                previous, summaries = rollup, []
        scene_dependencies[i] = previous
    for repeat in range(3):
        for i, fixture in enumerate(inputs["summary_fixtures"]):
            previous, previous_cutoff, summaries = None, 0, []
            for j, cutoff in enumerate(fixture["cutoffs"]):
                key = f"summary-r{repeat}-f{i}-s{j}"
                nodes[key] = dict(
                    id=key,
                    role="summary",
                    denominator="summary48",
                    repeat=repeat,
                    bundle=fixture["bundle"],
                    cutoff=cutoff,
                    previous_cutoff=previous_cutoff,
                    dependencies=[previous] if previous else [],
                    previous=previous,
                )
                previous, previous_cutoff = key, cutoff
                summaries.append(key)
            key = f"summary-r{repeat}-f{i}-rollup"
            nodes[key] = dict(
                nodes[previous],
                id=key,
                role="summary_rollup",
                dependencies=summaries,
                summaries=summaries,
                previous=nodes[previous]["previous"],
            )
    for concurrency in (1, gate_parallel(inputs)):
        for repeat in range(3):
            for i in range(1, 16):
                for condition in ("B", "C"):
                    key = f"action-c{concurrency}-r{repeat}-{condition}-{i}"
                    previous = scene_dependencies[i] if condition == "C" else None
                    nodes[key] = dict(
                        id=key,
                        role="self_action",
                        denominator="action180",
                        scene=i,
                        condition=condition,
                        concurrency=concurrency,
                        repeat=repeat,
                        dependencies=[previous] if previous else [],
                        previous=previous,
                    )
    if {k: sum(n["denominator"] == k for n in nodes.values()) for k in TOTALS} != TOTALS:
        raise ValueError("D-027 corpus denominator mismatch")
    return list(nodes.values())


def reference_key(node):
    return f"{Path(node['bundle']).name}@{node['cutoff']}"


def prepare(
    directory, offline, local, study_root, battle_root, version, criteria_path,
    *, concurrency=DEFAULT_CONCURRENCY,
):
    require_not_halted(study_root)
    read_stage(local, "fake12")
    local_value = b.read_sealed(Path(local))
    prompt_identity = identity(version)
    if local_value.get("summary_prompt_identity") != prompt_identity:
        raise ValueError("local/Cloud prompt version mismatch")
    directory.mkdir(parents=True, exist_ok=False)
    inputs = prepare_inputs(offline, battle_root, concurrency=concurrency)
    criteria = b.read_sealed(Path(criteria_path))
    templates = inputs["summary_templates"]
    keys = {f"{Path(t['bundle']).name}@{t['cutoff']}" for t in templates}
    if set(criteria.get("references", {})) != keys or criteria.get("decision") != "D-027":
        raise ValueError("independent criteria denominator mismatch")
    for template in templates:
        key = f"{Path(template['bundle']).name}@{template['cutoff']}"
        reference = criteria["references"][key]
        if reference["source_events"] != template["context"]["source_events"]:
            raise ValueError("independent criterion source mismatch")
        verify_reference(reference)
        verify_annotations(template["context"], reference)
        verify_observation(template["context"], reference)
    b.seal_json(directory / "inputs.json", inputs)
    b.seal_json(directory / "criteria.json", criteria)
    manifest = dict(
        **gate_evidence(inputs),
        decision="D-027",
        experiment="EX-024",
        summary_prompt_identity=prompt_identity,
        study_root=str(study_root),
        local=str(local),
        offline=str(offline),
        predecessors={str(p): b.digest(p) for p in (Path(local), Path(offline))},
        source_files=source_identity(),
        nodes=graph(inputs, battle_root),
        inputs_sha256=b.digest(directory / "inputs.json"),
        criteria_sha256=b.digest(directory / "criteria.json"),
        prepared_at=time.time(),
    )
    b.seal_json(directory / "manifest.json", manifest)
    (directory / "calls").mkdir()
    (directory / "reviews").mkdir()
    (directory / "batches").mkdir()
    return dict(passed=False, state="prepared", planned=TOTALS)


def verify(directory):
    value = b.read_sealed(directory / "manifest.json")
    require_not_halted(Path(value["study_root"]))
    require_not_halted(directory)
    if (directory / "STOP").exists():
        raise ValueError("interrupted")
    if value["source_files"] != source_identity():
        raise ValueError("source drift")
    if identity(value["summary_prompt_identity"]["version"]) != value["summary_prompt_identity"]:
        raise ValueError("summary prompt version drift")
    for key in ("inputs", "criteria"):
        if b.digest(directory / f"{key}.json") != value[f"{key}_sha256"]:
            raise ValueError("prepared input/criterion drift")
        b.read_sealed(directory / f"{key}.json")
    for path, digest in value["predecessors"].items():
        if b.digest(path) != digest:
            raise ValueError("predecessor drift")
    inputs = b.read_sealed(directory / "inputs.json")
    if gate_evidence(value) != gate_evidence(inputs):
        raise ValueError("gate concurrency declaration mismatch")
    expected_levels = {1, gate_parallel(value)}
    if {n["concurrency"] for n in value["nodes"] if n["role"] == "self_action"} != expected_levels:
        raise ValueError("gate graph concurrency mismatch")
    read_stage(value["local"], "fake12")
    return value


def register_dispatch(directory, manifest):
    """Immutable paid-combination entries anchor one shared clock across all versions."""
    root = Path(manifest["study_root"])
    require_not_halted(root)
    entries = sorted(root.glob("dispatch-v*.json"))
    wanted = dict(
        directory=str(directory.resolve()),
        manifest_sha256=b.digest(directory / "manifest.json"),
        source_files=manifest["source_files"],
        summary_prompt_identity=manifest["summary_prompt_identity"],
    )
    clock_path = root / "cloud-clock.json"
    for path in entries:
        old = b.read_sealed(path)
        if not clock_path.exists() or old["clock_sha256"] != b.digest(clock_path):
            raise ValueError("shared Cloud clock missing/reset")
        if old["directory"] == wanted["directory"]:
            if any(old[k] != v for k, v in wanted.items()):
                raise ValueError("paid source/prompt combination drift")
            return cloud_clock(root)
        previous = Path(old["directory"])
        stopped = b.read_sealed(previous / "halt.json")
        if stopped["category"] not in (
            "summary_semantics",
            "summary_format",
            "input",
            "calculation",
        ):
            raise ValueError("previous version cannot be replaced")
    if len(entries) >= 3:
        raise ValueError("paid combination limit")
    expected = f"v1.1.{len(entries)}"
    if wanted["summary_prompt_identity"]["version"] != expected:
        raise ValueError("versions must be used once in order")
    clock = cloud_clock(root)
    require_budget(clock)
    b.seal_json(
        root / f"dispatch-{expected}.json",
        dict(
            wanted,
            clock_sha256=b.digest(clock_path),
            registered_at=time.time(),
        ),
    )
    return clock


def reviewed(directory, node, manifest):
    path = directory / "reviews" / (node["id"] + ".json")
    if not path.exists():
        return False
    audit = b.read_sealed(path)
    response = directory / "calls" / (node["id"] + ".json")
    if (
        audit["response_sha256"] != b.digest(response)
        or audit["manifest_sha256"] != b.digest(directory / "manifest.json")
        or audit["criteria_sha256"] != manifest["criteria_sha256"]
        or any(audit.get(k) is not True for k in CHECKS)
        or audit.get("errors")
    ):
        raise ValueError("review integrity/failure")
    verify_response(directory, node, manifest)
    return True


def verify_response(directory, node, manifest):
    path = directory / "calls" / (node["id"] + ".json")
    row = b.read_sealed(path)
    intent = b.read_sealed(path.parent / ("intent-" + path.name))
    trace = row["trace"]
    prompt = (
        (PROMPTS / "battle_fixed.txt").read_text()
        if node["role"] == "self_action"
        else asset(node["role"], manifest["summary_prompt_identity"]["version"])[0]
    )
    request = trace.get("request", {})
    if (
        row["item_id"] != node["id"]
        or row["role"] != node["role"]
        or row["context"] != intent["context"]
        or trace.get("system_prompt") != prompt
        or json.loads(trace.get("user_prompt", "null")) != intent["context"]
        or request.get("summary_prompt_identity") != manifest["summary_prompt_identity"]
        or request.get("thinking_effort") != "low"
        or request.get("model") != OLLAMA_MODEL
        or request.get("seed") != 100
        or request.get("temperature") != 0
        or request.get("requested_output_tokens") != 131072
        or request.get("context_window") is not None
        or intent.get("manifest_sha256") != b.digest(directory / "manifest.json")
    ):
        raise ValueError("actual Cloud input/configuration identity mismatch")
    return row


def ready_nodes(directory, manifest):
    """A phase and every direct dependency must pass review before data can flow."""
    nodes = {n["id"]: n for n in manifest["nodes"]}
    for denominator in TOTALS:
        selected = [n for n in nodes.values() if n["denominator"] == denominator]
        if all(reviewed(directory, n, manifest) for n in selected):
            continue
        ready = []
        for node in selected:
            output = directory / "calls" / (node["id"] + ".json")
            intent = directory / "calls" / ("intent-" + node["id"] + ".json")
            if output.exists():
                if not intent.exists():
                    raise ValueError("response without submission intent")
                verify_response(directory, node, manifest)
                continue
            if intent.exists():
                raise ValueError("unresolved submission; resubmission forbidden")
            if all(reviewed(directory, nodes[k], manifest) for k in node["dependencies"]):
                ready.append(node)
        return ready
    return []


def materialize(directory, node, manifest):
    nodes = {n["id"]: n for n in manifest["nodes"]}
    for dependency in node["dependencies"]:
        if not reviewed(directory, nodes[dependency], manifest):
            raise ValueError("unreviewed summary dependency")

    def previous(key):
        return text_of(b.read_sealed(directory / "calls" / (key + ".json"))) if key else None

    inputs = b.read_sealed(directory / "inputs.json")
    if node["role"] == "self_action":
        context = copy.deepcopy(inputs["scenes"][node["scene"] - 1])
        context["condition_id"] = node["condition"]
        context["battle_summary"] = None
        if node["previous"]:
            context["battle_summary"] = dict(
                battle_id=context["identity"]["battle_id"],
                actor_id=context["identity"]["actor_id"],
                text=previous(node["previous"]),
            )
    else:
        template = next(
            t["context"]
            for t in inputs["summary_templates"]
            if (t["bundle"], t["cutoff"]) == (node["bundle"], node["cutoff"])
        )
        context = summary_window(
            template,
            node["previous_cutoff"],
            previous=previous(node["previous"]),
        )
        if node["role"] == "summary_rollup":
            context["summaries"] = [previous(k) for k in node["summaries"]]
    return dict(
        id=node["id"],
        role=node["role"],
        context=context,
        summary_prompt_version=manifest["summary_prompt_identity"]["version"],
        summary_prompt_identity=manifest["summary_prompt_identity"],
        metadata={k: node[k] for k in ("denominator", "concurrency", "repeat") if k in node},
        dependency_reviews={
            k: b.digest(directory / "reviews" / (k + ".json")) for k in node["dependencies"]
        },
        output_path=str(directory / "calls" / (node["id"] + ".json")),
    )


def stop_version(directory, category, evidence):
    manifest = b.read_sealed(directory / "manifest.json")
    halt_study(directory, category, evidence)
    if category not in ("summary_semantics", "summary_format", "input", "calculation"):
        halt_study(Path(manifest["study_root"]), category, evidence)


def status(directory):
    manifest = b.read_sealed(directory / "manifest.json")
    counts = {}
    pending = []
    for denominator, total in TOTALS.items():
        nodes = [n for n in manifest["nodes"] if n["denominator"] == denominator]
        submitted = responses = failed = reviews = 0
        for node in nodes:
            path = directory / "calls" / (node["id"] + ".json")
            submitted += (path.parent / ("intent-" + path.name)).exists()
            if path.exists():
                row = b.read_sealed(path)
                responses += 1
                failed += not row["valid"]
                if (directory / "reviews" / path.name).exists():
                    audit = b.read_sealed(directory / "reviews" / path.name)
                    reviews += 1
                    failed += bool(audit.get("errors")) or any(
                        audit.get(k) is not True for k in CHECKS
                    )
                else:
                    pending.append(node["id"])
        counts[denominator] = dict(
            planned=total,
            submitted=submitted,
            responses=responses,
            failed=failed,
            reviewed=reviews,
            unexecuted=total - submitted,
            unresolved=submitted - responses,
        )
    return dict(
        passed=False,
        state="review_pending" if pending else "ready",
        counts=counts,
        pending=pending,
        halted=(directory / "halt.json").exists(),
    )


def collect(directory):
    """One reviewable wave; repeated entry cannot recall a completed provider response."""
    directory = Path(directory).resolve()
    manifest = verify(directory)
    parallel = gate_parallel(manifest)
    started = time.time()
    stop = threading.Event()
    handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    for sig in handlers:
        signal.signal(sig, lambda *_: stop.set())
    batches = directory / "batches"
    batch_path = batches / f"{time.time_ns()}.json"
    dispatched = []
    error = None
    try:
        runtime_lock = b.cli.ARTIFACT_ROOT / "benchmark-runtime.lock"
        runtime_lock.parent.mkdir(parents=True, exist_ok=True)
        with (
            runtime_lock.open("a") as shared_lock,
            (Path(manifest["study_root"]) / "dispatch.lock").open("a") as lock,
        ):
            fcntl.flock(shared_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ready = ready_nodes(directory, manifest)
            if not ready:
                return status(directory)
            clock = register_dispatch(directory, manifest)
            with tempfile.TemporaryDirectory(prefix="pc-review-gate-") as temp:
                with PermitBroker(
                    Path(temp) / "broker.sock",
                    parallel,
                    {OLLAMA_MODEL: parallel},
                    deadline=clock["stop_new_work_at"],
                ) as broker:
                    with concurrent.futures.ProcessPoolExecutor(
                        max_workers=parallel, mp_context=multiprocessing.get_context("spawn")
                    ) as pool:
                        while ready and not error:
                            if stop.is_set() or (directory / "STOP").exists():
                                raise ValueError("interrupted")
                            require_budget(clock)
                            concurrency = ready[0].get("concurrency", parallel)
                            group = []
                            while (
                                ready
                                and len(group) < concurrency
                                and (ready[0].get("concurrency", parallel) == concurrency)
                            ):
                                group.append(ready.pop(0))
                            futures = []
                            for node in group:
                                item = materialize(directory, node, manifest)
                                require_budget(clock)
                                path = directory / "calls" / ("intent-" + node["id"] + ".json")
                                b.seal_json(
                                    path,
                                    dict(
                                        item,
                                        submitted_at=time.time(),
                                        manifest_sha256=b.digest(directory / "manifest.json"),
                                    ),
                                )
                                dispatched.append(node["id"])
                                futures.append(
                                    pool.submit(
                                        call, item, str(broker.path), clock["stop_new_work_at"]
                                    )
                                )
                            for future in futures:
                                while True:
                                    if stop.is_set() or (directory / "STOP").exists():
                                        broker.stop()
                                    try:
                                        row = future.result(timeout=0.2)
                                        break
                                    except concurrent.futures.TimeoutError:
                                        continue
                                if not row["valid"]:
                                    category = row["category"] or "output_contract"
                                    if (
                                        category == "output_contract"
                                        and row["role"] != "self_action"
                                    ):
                                        category = "summary_format"
                                    error = error or category
                                    stop_version(
                                        directory,
                                        category,
                                        directory / "calls" / (row["item_id"] + ".json"),
                                    )
                                    broker.stop()
                            if stop.is_set() or (directory / "STOP").exists():
                                raise ValueError("interrupted")
    except Exception as exc:
        error = str(exc)
        failure = directory / f"failure-{time.time_ns()}.json"
        b.seal_json(failure, dict(error=error, type=type(exc).__name__, dispatched=dispatched))
        stop_version(
            directory, "budget_stop" if error == "budget_stop" else "integrity_or_runtime", failure
        )
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        b.seal_json(
            batch_path,
            dict(
                started_at=started,
                finished_at=time.time(),
                elapsed_seconds=time.time() - started,
                dispatched=dispatched,
                error=error,
            ),
        )
    return status(directory)


def review(directory, audit_path):
    directory = Path(directory).resolve()
    manifest = verify(directory)
    audit = b.read_sealed(Path(audit_path))
    if audit.get("manifest_sha256") != b.digest(directory / "manifest.json"):
        raise ValueError("review manifest mismatch")
    criteria = b.read_sealed(directory / "criteria.json")
    nodes = {n["id"]: n for n in manifest["nodes"]}
    if not audit.get("reviewer") or not audit.get("calls"):
        raise ValueError("empty semantic review")
    # Validate the complete file before installing any reviewed dependency.
    records = []
    for key, check in audit["calls"].items():
        node = nodes[key]
        path = directory / "calls" / (key + ".json")
        row = verify_response(directory, node, manifest)
        text = text_of(row)
        if (directory / "reviews" / path.name).exists():
            raise ValueError("review already sealed")
        if check.get("response_sha256") != b.digest(path) or not check.get("evidence"):
            raise ValueError("review response/evidence mismatch")
        if any(type(check.get(k)) is not bool for k in CHECKS):
            raise ValueError("incomplete semantic review")
        if node["role"] != "self_action":
            reference = criteria["references"][reference_key(node)]
            facts = {f["id"] for f in reference["facts"]}
            if set(check.get("required_facts", {})) != facts:
                raise ValueError("required fact review denominator mismatch")
            for fact in check["required_facts"].values():
                if fact["status"] not in ("retained", "incorrect", "omitted"):
                    raise ValueError("invalid required fact verdict")
                if fact["status"] == "retained" and (
                    not fact.get("quote") or fact["quote"] not in text
                ):
                    raise ValueError("required fact quote absent from response")
            if check["expected"] and any(
                f["status"] != "retained" for f in check["required_facts"].values()
            ):
                raise ValueError("missing fact cannot pass review")
        for error in check.get("errors", []):
            if not error.get("evidence") or not error.get("explanation"):
                raise ValueError("unsupported reviewer error")
            if error.get("quote") and error["quote"] not in text:
                raise ValueError("error quote absent from response")
        records.append(
            (
                node,
                dict(
                    check,
                    reviewer=audit["reviewer"],
                    reviewed_at=time.time(),
                    manifest_sha256=audit["manifest_sha256"],
                    criteria_sha256=manifest["criteria_sha256"],
                ),
            )
        )
    for node, record in records:
        path = directory / "reviews" / (node["id"] + ".json")
        b.seal_json(path, record)
        if any(record[k] is not True for k in CHECKS) or record.get("errors"):
            stop_version(
                directory,
                "summary_semantics" if node["role"] != "self_action" else "action_semantics",
                path,
            )
    return status(directory)


def finish(directory):
    directory = Path(directory).resolve()
    manifest = verify(directory)
    parallel = gate_parallel(manifest)
    if not all(reviewed(directory, n, manifest) for n in manifest["nodes"]):
        raise ValueError("semantic review incomplete")
    rows = [b.read_sealed(directory / "calls" / (n["id"] + ".json")) for n in manifest["nodes"]]
    actions = [r for r in rows if r["role"] == "self_action"]
    metrics = [
        request_metrics([r["trace"] for r in actions if r["concurrency"] == c]) for c in (1, parallel)
    ]
    technical = (
        all(r["valid"] for r in rows)
        and metrics[1]["maximum_account_http_overlap"] == parallel
        and metrics[0]["http_p95_ms"] is not None
        and metrics[1]["http_p95_ms"] is not None
        and metrics[1]["http_p95_ms"] <= 2 * metrics[0]["http_p95_ms"]
    )
    # A flat final call index remains compatible with the existing receipt reader.
    outputs = {}
    for row in rows:
        path = directory / (row["item_id"] + ".json")
        b.seal_json(path, row)
        outputs[path.name] = b.digest(path)
    collection = dict(
        **gate_evidence(manifest),
        passed=technical,
        technical_passed=technical,
        semantic_review="passed",
        summary_prompt_identity=manifest["summary_prompt_identity"],
        counts=TOTALS,
        sequential=metrics[0],
        parallel=metrics[1],
        call_outputs=outputs,
        cloud_clock=cloud_clock(Path(manifest["study_root"])),
        elapsed_seconds=sum(
            b.read_sealed(p)["elapsed_seconds"] for p in (directory / "batches").glob("*.json")
        ),
    )
    b.seal_json(directory / "collection.json", collection)
    reviews = {
        n["id"]: b.read_sealed(directory / "reviews" / (n["id"] + ".json"))
        for n in manifest["nodes"]
    }
    b.seal_json(directory / "semantic-review.json", reviews)
    result = seal_stage(
        directory / "result.json",
        "cloud_gate",
        manifest["local"],
        collection,
        [
            directory / p
            for p in (
                "collection.json",
                "inputs.json",
                "criteria.json",
                "manifest.json",
                "semantic-review.json",
            )
        ],
    )
    if not technical:
        stop_version(directory, "http_gate", directory / "result.json")
    return result


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "collect", "review", "status", "finish"))
    parser.add_argument("--output", type=Path, required=True)
    for name in ("offline", "local", "study-root", "battle-root", "criteria", "audit"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--version", default="v1.1.0")
    parser.add_argument("--concurrency", type=int, choices=range(2, 11))
    args = parser.parse_args()
    if args.concurrency is not None and args.command != "prepare":
        parser.error("concurrency is selected only during prepare")
    directory = args.output.resolve()
    if args.command == "prepare":
        result = prepare(
            directory,
            args.offline.resolve(),
            args.local.resolve(),
            args.study_root.resolve(),
            args.battle_root.resolve(),
            args.version,
            args.criteria.resolve(),
            concurrency=args.concurrency if args.concurrency is not None else DEFAULT_CONCURRENCY,
        )
    elif args.command == "review":
        result = review(directory, args.audit.resolve())
    else:
        result = {"collect": collect, "status": status, "finish": finish}[args.command](directory)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
