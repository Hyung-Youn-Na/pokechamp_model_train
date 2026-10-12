"""Bounded independent request workers with durable intents and response-before-exit seals."""

from __future__ import annotations

import fcntl
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
from ..calibration import Trace
from ..constants import ARTIFACT_ROOT, OLLAMA_MODEL
from ..improved_io.backend import FixedBackend
from ..permits import PermitBroker
from .prepare import MAX_PROFILE, THINKING_PROFILE, verify, verify_files


def clock(directory, *, now=None, manifest=None):
    manifest = manifest or b.read_sealed(Path(directory) / "manifest.json")
    config = manifest["config"]
    path = Path(directory) / "cloud-clock.json"
    if not path.exists():
        start = time.time() if now is None else now
        b.seal_json(
            path,
            {
                "experiment": manifest["experiment"],
                "first_dispatch_at": start,
                "stop_new_work_at": start + config["submission_seconds"],
                "cleanup_deadline": start + config["total_seconds"],
            },
        )
    value = b.read_sealed(path)
    if (
        value["experiment"] != manifest["experiment"]
        or value["stop_new_work_at"] - value["first_dispatch_at"] != config["submission_seconds"]
        or value["cleanup_deadline"] - value["first_dispatch_at"] != config["total_seconds"]
    ):
        raise ValueError("invalid persistent diagnostic clock")
    return value


class FakeClient:
    def __init__(self, text, mode):
        self.text, self.mode = text, mode

    def chat(self, **_):
        if self.mode == "timeout":
            raise TimeoutError("fake provider timeout")
        if self.mode == "hang":
            time.sleep(30)
        return {
            "model": OLLAMA_MODEL,
            "message": {"content": self.text},
            "prompt_eval_count": 12,
            "eval_count": 4,
            "done_reason": "stop",
        }


def fake_text(context):
    from ..improved_io.memory import HEADINGS

    identity = context["identity"]
    return (
        "<summary>\n# Battle Summary\n## "
        + "\n## ".join(HEADINGS)
        + f"\nbattle_id: {identity['battle_id']}\nactor_id: {identity['actor_id']}\n"
        + f"[event:{context['source_event_ids'][0]}] CONFIRMED: fake fixture.\n</summary>"
    )


def worker(directory, item, broker_path, deadline, fake=None):
    # Only the coordinator handles soft interruption; admitted calls retain their
    # full timeout to finish and seal. The coordinator owns a hard cleanup deadline.
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal.SIG_IGN)
    directory = Path(directory)
    trace, category, backend = Trace(), None, None
    started = time.time()
    try:
        input_path = directory / "inputs" / item["input"]
        if b.digest(input_path) != item["input_sha256"]:
            raise ValueError("input hash differs from prepared manifest")
        value = b.read_sealed(input_path)
        context = value["context"]
        maximum = item.get("profile") == MAX_PROFILE
        env = dict(
            os.environ,
            POKECHAMP_PERMIT_SOCKET=broker_path,
            POKECHAMP_BATCH_DEADLINE=str(deadline),
        )
        env.pop("POKECHAMP_CANCEL_PATH", None)
        if fake is None:
            cli._load_cloud_credential()
            env["OLLAMA_API_KEY"] = os.environ["OLLAMA_API_KEY"]
            if maximum:
                from .compat import DiagnosticClient

                factory = DiagnosticClient
            else:
                factory = None
        else:
            env["OLLAMA_API_KEY"] = "fake-offline-only"
            mode = fake.get(item["id"], "success")
            content = "malformed summary" if mode == "format" else fake_text(context)

            def factory(**_):
                return FakeClient(content, mode)

            if maximum:
                from .compat import fake_client_factory

                factory = fake_client_factory(content, mode)

        backend_type = FixedBackend
        if maximum:
            from .compat import DiagnosticBackend

            backend_type = DiagnosticBackend
        env.update(POKECHAMP_TRANSPORT_POLICY="legacy-300-v1", POKECHAMP_PROVIDER="ollama")
        backend = backend_type(
            environ=env,
            client_factory=factory,
            trace_sink=trace,
            summary_thinking_effort=item.get("thinking", "low"),
        )
        backend.role, backend.input_context = item.get("role", "summary"), context
        backend.summary_prompt_identity = value.get("summary_prompt_identity")
        b.seal_json(
            directory / "submitted" / f"{item['id']}.json",
            {
                "id": item["id"],
                "submitted_at": time.time(),
                "pid": os.getpid(),
                "input_sha256": b.digest(directory / "inputs" / item["input"]),
            },
        )
        backend.get_LLM_action(
            system_prompt=value["system_prompt"],
            user_prompt=value["user_prompt"],
            model=OLLAMA_MODEL,
            temperature=0,
            seed=100,
            json_format=False,
            battle=SimpleNamespace(turn=context["identity"]["showdown_turn"]),
        )
    except Exception as exc:
        category = getattr(exc, "category", "environment")
    payload = getattr(trace, "payload", {})
    if item.get("profile") == MAX_PROFILE and payload.get("raw_content") is not None:
        from .maximum import verify_wire

        try:
            verify_wire(payload, value, item["thinking"], item["role"])
        except (ValueError, KeyError, TypeError):
            category = "configuration"
    if payload.get("response", {}).get("reported_model") not in (None, OLLAMA_MODEL):
        category = "configuration"
    if payload and any(
        payload.get("response", {}).get(k) is None for k in ("prompt_tokens", "completion_tokens")
    ):
        category = category or "provider_metadata"
    row = {
        "id": item["id"],
        "input_sha256": item["input_sha256"],
        "trace": payload,
        "category": category,
        "started_at": started,
        "finished_at": time.time(),
        "fake": fake is not None,
        "pid": os.getpid(),
    }
    # This is the source response. Parent exit/IPC failure cannot discard it.
    b.seal_json(directory / "responses" / f"{item['id']}.json", row)
    if backend is not None:
        transport = getattr(backend.client, "_client", None)
        if transport is not None:
            transport.close()


def inventory(directory, manifest):
    directory = Path(directory)
    rows = []
    for item in manifest["schedule"]:
        intent = directory / "intents" / f"{item['id']}.json"
        submitted = directory / "submitted" / f"{item['id']}.json"
        response = directory / "responses" / f"{item['id']}.json"
        row = dict(
            item,
            intended=intent.exists(),
            submitted=submitted.exists(),
            response_record=response.exists(),
            acquired=False,
            failed=False,
            unconfirmed=False,
            unexecuted=not intent.exists(),
        )
        try:
            _inspect_slot(directory, manifest, item, row, intent, submitted, response)
        except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
            # A damaged record must not prevent preserving other in-flight responses.
            row.update(
                failed=True,
                unconfirmed=True,
                category="evidence_integrity",
                integrity_error=type(exc).__name__,
            )
        rows.append(row)
    counts = {
        key: sum(row[key] for row in rows)
        for key in (
            "intended",
            "submitted",
            "response_record",
            "acquired",
            "failed",
            "unconfirmed",
            "unexecuted",
        )
    }
    return {"scheduled": len(rows), **counts, "slots": rows}


def _inspect_slot(directory, manifest, item, row, intent, submitted, response):
    if intent.exists():
        b.read_sealed(intent)
    if submitted.exists():
        b.read_sealed(submitted)
    if response.exists():
        result = b.read_sealed(response)
        row["response_sha256"] = b.digest(response)
        row["category"] = result["category"]
        row["acquired"] = isinstance(result["trace"].get("raw_content"), str)
        if row["acquired"]:
            value = b.read_sealed(directory / "inputs" / item["input"])
            effort = (
                item["condition"]
                if manifest.get("profile") in (THINKING_PROFILE, MAX_PROFILE)
                else "low"
            )
            request = result["trace"]["request"]
            expected = dict(
                thinking_effort=effort,
                model=manifest["config"]["model"],
                seed=manifest["config"]["seed"],
                temperature=manifest["config"]["temperature"],
                requested_output_tokens=manifest["config"]["max_output_tokens"],
                context_window=manifest["config"]["context"],
                call_role=item.get("role", "summary"),
            )
            if (
                any(request.get(k) != v for k, v in expected.items())
                or result["trace"]["system_prompt"] != value["system_prompt"]
                or result["trace"]["user_prompt"] != value["user_prompt"]
                or result["input_sha256"] != b.digest(directory / "inputs" / item["input"])
            ):
                raise ValueError("response request differs from sealed input/condition")
            if manifest.get("profile") == MAX_PROFILE:
                from .maximum import verify_wire

                verify_wire(result["trace"], value, effort, item["role"])
        row["failed"] = result["category"] not in (
            None,
            "output_contract",
            "budget_stop",
        )
        row["unconfirmed"] = (
            result["trace"].get("response", {}).get("network_called", False) and not row["acquired"]
        )
    elif intent.exists():
        row["unconfirmed"] = True


def run(directory, *, fake=None, stop_event=None, _test_deadlines=None):
    directory = Path(directory).resolve()
    if (directory / "halt.json").exists():
        raise ValueError("diagnostic halted: resubmission prohibited")
    manifest = verify(directory)
    if (directory / "collection.json").exists():
        raise ValueError("collection already sealed; no reruns/replacements")
    if fake is None:
        gate = b.read_sealed(directory / "verification.json")
        if gate.get("passed") is not True or gate.get("manifest_sha256") != b.digest(
            directory / "manifest.json"
        ):
            raise ValueError("offline verification receipt required before Cloud")
        if manifest.get("profile") == MAX_PROFILE:
            if (
                not gate.get("evidence_files")
                or gate.get("source_files") != manifest["source_files"]
            ):
                raise ValueError("max diagnostic requires source-bound verification evidence")
            verify_files(gate["evidence_files"])
    stop = stop_event or threading.Event()
    handlers = {}
    if threading.current_thread() is threading.main_thread():
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        for sig in handlers:
            signal.signal(sig, lambda *_: stop.set())
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    processes, reason, killed, broker_snapshot = {}, None, [], None
    started = time.time()
    persistent = None
    try:
        with (ARTIFACT_ROOT / "benchmark-runtime.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for name in ("intents", "submitted", "responses"):
                (directory / name).mkdir(exist_ok=True)
            resumed = (directory / "cloud-clock.json").exists()
            if resumed:
                # A lost coordinator makes admissions uncertain. Preserve and close out;
                # do not launch replacement calls or reset the clock on restart.
                persistent = clock(directory, manifest=manifest)
                reason = "coordinator_restart_no_resubmission"
            elif stop.is_set() or (directory / "STOP").exists():
                reason = "cancelled_before_first_dispatch"
            else:
                persistent = clock(directory, manifest=manifest)
                deadlines = dict(persistent)
                if _test_deadlines is not None:
                    if fake is None:
                        raise ValueError("test deadlines require fake transport")
                    deadlines.update(
                        stop_new_work_at=started + _test_deadlines[0],
                        cleanup_deadline=started + _test_deadlines[1],
                    )
                with tempfile.TemporaryDirectory(prefix="summary-permits-") as temp:
                    with PermitBroker(
                        Path(temp) / "broker.sock",
                        manifest["config"]["account_limit"],
                        {OLLAMA_MODEL: manifest["config"]["model_limit"]},
                        deadline=deadlines["stop_new_work_at"],
                    ) as broker:
                        pending = iter(manifest["schedule"])
                        exhausted = False
                        while processes or not exhausted:
                            if stop.is_set() or (directory / "STOP").exists():
                                reason = reason or "cancelled"
                            if time.time() >= deadlines["stop_new_work_at"]:
                                reason = reason or "submission_deadline"
                            if reason:
                                broker.stop()
                                exhausted = True
                            for slot_id, proc in list(processes.items()):
                                if proc.is_alive():
                                    continue
                                proc.join()
                                del processes[slot_id]
                                path = directory / "responses" / f"{slot_id}.json"
                                if proc.exitcode != 0 or not path.exists():
                                    reason = reason or "worker_lost"
                                else:
                                    try:
                                        result = b.read_sealed(path)
                                        if result["category"] not in (
                                            None,
                                            "output_contract",
                                        ):
                                            reason = reason or result["category"]
                                    except (ValueError, RuntimeError, OSError, KeyError):
                                        reason = reason or "evidence_integrity"
                                proc.close()
                            if reason:
                                broker.stop()
                                exhausted = True
                            if time.time() >= deadlines["cleanup_deadline"]:
                                for slot_id, proc in processes.items():
                                    proc.kill()
                                    proc.join(timeout=5)
                                    killed.append(slot_id)
                                    proc.close()
                                processes.clear()
                                reason = reason or "cleanup_deadline"
                                break
                            if not exhausted:
                                try:
                                    verify_files(manifest["source_files"])
                                    if manifest.get("profile") == MAX_PROFILE:
                                        verify_files(
                                            {
                                                str(directory / p): h
                                                for p, h in manifest["files"].items()
                                            }
                                        )
                                except (ValueError, OSError):
                                    reason = "source_integrity"
                                    exhausted = True
                                    broker.stop()
                            while (
                                not exhausted
                                and len(processes) < manifest["config"]["account_limit"]
                            ):
                                item = next(pending, None)
                                if item is None:
                                    exhausted = True
                                    break
                                if stop.is_set() or time.time() >= deadlines["stop_new_work_at"]:
                                    break
                                item = dict(
                                    item,
                                    input_sha256=manifest["files"]["inputs/" + item["input"]],
                                    thinking=(
                                        item["condition"]
                                        if manifest.get("profile")
                                        in (THINKING_PROFILE, MAX_PROFILE)
                                        else "low"
                                    ),
                                    profile=manifest.get("profile"),
                                )
                                b.seal_json(
                                    directory / "intents" / f"{item['id']}.json",
                                    {
                                        "item": item,
                                        "dispatch_at": time.time(),
                                        "manifest_sha256": b.digest(directory / "manifest.json"),
                                    },
                                )
                                proc = multiprocessing.get_context("spawn").Process(
                                    target=worker,
                                    args=(
                                        directory,
                                        item,
                                        str(broker.path),
                                        deadlines["stop_new_work_at"],
                                        fake,
                                    ),
                                )
                                proc.start()
                                processes[item["id"]] = proc
                            time.sleep(0.05)
                        broker_snapshot = broker.snapshot()
    except BaseException as exc:
        # Stop admissions but allow owned calls their timeout to seal responses.
        cleanup = (
            min(time.time() + 305, persistent["cleanup_deadline"]) if persistent else time.time()
        )
        for proc in processes.values():
            proc.join(timeout=max(0, cleanup - time.time()))
            if proc.is_alive():
                proc.kill()
            proc.join(timeout=5)
            proc.close()
        b.seal_json(
            directory / "coordinator-failure.json",
            {
                "category": "coordinator_failure",
                "error_type": type(exc).__name__,
                "at": time.time(),
                "manifest_sha256": b.digest(directory / "manifest.json"),
                "unconfirmed_policy": "intents without sealed responses remain unknown",
            },
        )
        raise
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    observed = inventory(directory, manifest)
    if any(row.get("integrity_error") for row in observed["slots"]):
        reason = reason or "evidence_integrity"
    result = dict(
        observed,
        reason=reason,
        fake=fake is not None,
        cloud_clock=persistent,
        started_at=started,
        finished_at=time.time(),
        elapsed_seconds=time.time() - started,
        killed=killed,
        broker=broker_snapshot,
        manifest_sha256=b.digest(directory / "manifest.json"),
    )
    b.seal_json(directory / "collection.json", result)
    if reason:
        b.seal_json(
            directory / "halt.json",
            {
                "reason": reason,
                "at": time.time(),
                "experiment": manifest["experiment"],
                "manifest_sha256": b.digest(directory / "manifest.json"),
                "collection_sha256": b.digest(directory / "collection.json"),
            },
        )
    return {key: value for key, value in result.items() if key not in ("slots", "broker")}
