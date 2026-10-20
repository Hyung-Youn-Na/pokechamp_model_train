"""Owned local executor lifecycle and bounded, idempotent transport for new runs."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = "jev-planner-local-v1"
RETRY_DELAYS = (10.0, 30.0, 60.0)
MODEL_PYTHON = ROOT / ".pokechamp-data/jev27b-runtime/.venv/bin/python"


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def model_settings(config):
    from .config import model_spec
    return model_spec(config["executor"]["model"])


def validate_resources(config):
    """An experiment declares these limits; changing placement needs a new profile."""
    from integration.jev27b.config import runtime_profile
    spec = model_settings(config)
    profile = runtime_profile(spec["runtime_name"])
    expected = dict(gpu_indices=list(profile.physical_gpus),
                    allocator_bytes=profile.allocator_bytes, gpu_bytes=profile.gpu_bytes,
                    host_bytes=profile.host_bytes, disk_bytes=profile.disk_bytes)
    if config.get("evaluation", {}).get("resources") != expected:
        raise ValueError("executor resources must equal the pinned model runtime profile")
    return spec


def create_model(config):
    """Construct the preserved loader without entering an old experiment runner."""
    if config["executor"]["model"] == "tacit9b-vllm":
        from integration.tacit9b_vllm.model import OfficialModel
        return OfficialModel()
    if config["executor"]["model"] == "tacit9b":
        from integration.tacit9b.model import OfficialModel
        return OfficialModel()
    if config["executor"]["model"] == "jev-omni":
        from integration.jev_omni.model import OfficialModel
        return OfficialModel()
    if config["executor"]["model"] == "jev35b-nvfp4":
        from integration.jev35b_nvfp4.model import OfficialModel
        return OfficialModel()
    from integration.jev_eval.model import Evaluation27B, Evaluation9B, EvaluationMiniCPM
    spec = validate_resources(config)
    options = dict(profile=spec["model_runtime_name"])
    if config["executor"]["model"] == "jev27b":
        model = Evaluation27B(spec["model_dir"], **options)
    else:
        options["evidence_dir"] = Path(spec["evidence_dir"])
        cls = Evaluation9B if config["executor"]["model"] == "jev9b" else EvaluationMiniCPM
        model = cls(spec["model_dir"], **options)
    # Keep the loader's pinned placement identity; metadata reflects the new disk policy.
    model.profile = replace(model.profile, disk_bytes=spec["disk_bytes"])
    return model


def resource_roots(config, directory):
    from integration.jev_eval.resource import shared_roots
    spec = model_settings(config)
    directory = Path(directory).resolve()
    run_root = directory
    for parent in (directory, *directory.parents):
        manifest = parent / "manifest.json"
        if manifest.is_file():
            try:
                if json.loads(manifest.read_text()).get("schema_version") == "jev-planner-run-v1":
                    run_root = parent
                    break
            except (ValueError, OSError):
                pass
    return (*shared_roots(), Path(spec["model_dir"]).parent,
            Path(spec["evidence_dir"]), run_root)


def child_environment():
    from integration.jev27b.execute import child_environment as base_environment
    return base_environment()


async def maybe_await(callback, **kwargs):
    result = callback(**kwargs)
    return await result if inspect.isawaitable(result) else result


class MockExecutor:
    """Deterministic legal actions for plumbing checks; never a model result."""
    def __init__(self, record=None):
        self.record = record or (lambda _event: None)
        self.calls = 0

    async def __call__(self, payload, *, decision):
        self.calls += 1
        criteria = payload["questions"]["action"]["criteria"]
        moves = [(key, row) for key, row in criteria.items() if row.get("kind") == "move"]
        def power(item):
            value = item[1].get("move", {}).get("power", 0)
            return (value if isinstance(value, (int, float)) else 0,
                    bool(item[1].get("terastallize")))
        choice = max(moves, key=power)[0] if moves else next(iter(criteria))
        body = dict(model="mock-jev", answers=dict(action=dict(type="choice", choice=choice,
                    probabilities={key: float(key == choice) for key in criteria}, confidence=1)),
                    usage=dict(input_tokens=0, output_tokens=0), mock=True)
        common = dict(decision=decision, request_id=decision, attempt=1, mock=True)
        self.record(dict(type="executor_http_request", body=copy.deepcopy(payload),
                         raw_body=json.dumps(payload, ensure_ascii=False), **common))
        self.record(dict(type="executor_transport", status_code=200, elapsed_seconds=0,
                         raw_body=json.dumps(body), usage=body["usage"], **common))
        return body


class LocalExecutor:
    """Reuse exact bytes/request ID across retries of a single logical inference."""
    def __init__(self, config, *, endpoint, expected_identity, directory, record=None,
                 remaining=None, client_factory=None):
        from integration.jev27b.client import LocalClient
        self.spec = model_settings(config)
        self.directory = Path(directory)
        self.record = record or (lambda _event: None)
        self.remaining = remaining or (lambda: 600.0)
        self.client = (client_factory or LocalClient)(endpoint=endpoint,
            expected_identity=expected_identity, model_id=self.spec["model_id"],
            revision=self.spec["revision"], protocol=PROTOCOL, timeout=600)
        self.lock = asyncio.Lock()
        self.request_ids = set()
        self.calls = 0

    async def __call__(self, payload, *, decision):
        from integration.jev27b.client import LocalRequestError, request_bytes
        async with self.lock:
            if not decision or decision in self.request_ids:
                raise ValueError("missing or duplicate executor logical request")
            if self.remaining() <= 0:
                raise TimeoutError("executor collection deadline")
            self.request_ids.add(decision)
            request_id = "jp-" + hashlib.sha256(
                f"{self.directory.resolve()}:{decision}".encode()).hexdigest()
            body = dict(model=self.spec["model_id"], **copy.deepcopy(payload))
            raw = request_bytes(body, model_id=self.spec["model_id"])
            digest = hashlib.sha256(raw).hexdigest()
            self.client.timeout = min(600.0, self.remaining())
            if self.client.timeout <= 0:
                raise TimeoutError("executor deadline before health check")
            self.client._client.timeout = self.client.timeout
            await asyncio.to_thread(self.client.health)
            for attempt in range(1, len(RETRY_DELAYS) + 2):
                left = self.remaining()
                if left <= 0:
                    raise TimeoutError("executor collection deadline")
                self.client.timeout = min(600.0, left)
                self.client._client.timeout = self.client.timeout
                self.calls += 1
                common = dict(decision=decision, request_id=request_id, attempt=attempt,
                              body_sha256=digest, mock=False)
                self.record(dict(type="executor_http_request", body=body,
                                 raw_body=raw.decode(), **common))
                started = time.monotonic()
                def call():
                    try:
                        return self.client.evaluate(body, request_id=request_id, retries=0)
                    finally:
                        metadata = copy.deepcopy(self.client.last_transport or {})
                        metadata.pop("type", None)
                        usage = None
                        try:
                            usage = json.loads(metadata.get("raw_body", "")).get("usage")
                        except (ValueError, TypeError, AttributeError):
                            pass
                        metadata.update(common)
                        metadata.setdefault("elapsed_seconds", time.monotonic() - started)
                        self.record(dict(type="executor_transport", **metadata,
                                         **({"usage": usage} if usage is not None else {})))
                task = asyncio.create_task(asyncio.to_thread(call))
                try:
                    return await asyncio.shield(task)
                except asyncio.CancelledError:
                    await asyncio.gather(task, return_exceptions=True)
                    raise
                except LocalRequestError as error:
                    if not error.retryable or attempt > len(RETRY_DELAYS):
                        raise
                    delay = RETRY_DELAYS[attempt - 1]
                    if self.remaining() <= delay:
                        raise TimeoutError("executor deadline before retry") from error
                    self.record(dict(type="executor_retry", delay_seconds=delay,
                                     next_attempt=attempt + 1, **common))
                    await asyncio.sleep(delay)

    async def close(self):
        await asyncio.to_thread(self.client.close)


class OwnedRuntime:
    """One new server process, output journal and pinned identity per condition."""
    def __init__(self, directory, config, *, record=None, remaining=None):
        self.directory = Path(directory).resolve() / "serving"
        self.config = copy.deepcopy(config)
        self.spec = validate_resources(config)
        self.record = record or (lambda _event: None)
        self.remaining = remaining or (lambda: float("inf"))
        self.process = self.log = self.executor = self.monitor = None
        self.endpoint = None
        self.created = False

    async def start(self):
        from integration.jev27b.client import LocalClient, LocalRequestError
        from integration.jev27b.resource import ResourceMonitor
        from .config import validate_mode
        validate_mode(self.config, "live")
        self.directory.mkdir(parents=True, exist_ok=False)
        self.created = True
        write_json(self.directory / "config.json", self.config)
        with socket.socket() as port_probe:
            port = self.config["evaluation"].get("server_port", 18845)
            port_probe.bind(("127.0.0.1", port))
        if "engine_port" in self.spec:
            with socket.socket() as engine_probe:
                engine_probe.bind(("127.0.0.1", self.spec["engine_port"]))
        self.endpoint = f"http://127.0.0.1:{port}"
        self.log = (self.directory / "server.log").open("x")
        if self.spec.get("external_server"):
            from .external_runtime import ExternalMonitor, capture_identity
            receipt = capture_identity()
            expected = json.loads((Path(self.spec["evidence_dir"]) / "external-identity.json").read_text())
            if receipt != expected:
                raise ValueError("external server changed after preflight review")
            write_json(self.directory / "external-identity.json", receipt)
            self.monitor = ExternalMonitor(self.directory, receipt, budget_root=self.directory.parent)
        else:
            self.monitor = ResourceMonitor(self.directory, profile=self.spec["runtime_name"],
                budget_root=self.directory.parent, extra_roots=resource_roots(self.config,
                                                                           self.directory.parent))
        self.monitor.__enter__()
        self.process = subprocess.Popen([self.spec.get("python", str(MODEL_PYTHON)), "-B", "-m",
            "integration.jev_planner.server", "--config", str(self.directory / "config.json"),
            "--directory", str(self.directory), "--port", str(port)], cwd=ROOT,
            env=child_environment(), stdin=subprocess.DEVNULL, stdout=self.log,
            stderr=subprocess.STDOUT, start_new_session=True)
        write_json(self.directory / "process.json", dict(pid=self.process.pid,
            endpoint=self.endpoint, model=self.spec["model_id"], revision=self.spec["revision"]))
        probe = LocalClient(endpoint=self.endpoint, model_id=self.spec["model_id"],
            revision=self.spec["revision"], protocol=PROTOCOL, timeout=1)
        try:
            while True:
                if self.process.poll() is not None:
                    raise RuntimeError("owned executor exited before becoming ready")
                if self.remaining() <= 0:
                    raise TimeoutError("executor loading exceeded total deadline")
                try:
                    health = await asyncio.to_thread(probe.health)
                except LocalRequestError as error:
                    if error.category not in ("timeout", "transport"):
                        raise
                    await asyncio.sleep(0.2)
                    continue
                if health["server_pid"] != self.process.pid:
                    raise ValueError("executor listener belongs to another process")
                write_json(self.directory / "health.json", health)
                self.executor = LocalExecutor(self.config, endpoint=self.endpoint,
                    expected_identity=health["identity"], directory=self.directory,
                    remaining=self.remaining, record=self.record)
                self.record(dict(type="executor_ready", pid=self.process.pid,
                                 serving_identity=health["identity"], model=self.spec["model_id"]))
                return self.executor
        finally:
            probe.close()

    async def close(self):
        from integration.jev27b.execute import stop_owned_process
        from integration.jev27b.resource import wait_owned_gpu_release
        failures = []
        if self.executor is not None:
            try:
                await self.executor.close()
            except Exception as error:
                failures.append(error)
        if self.process is not None:
            try:
                await asyncio.to_thread(stop_owned_process, self.process)
            except Exception as error:
                failures.append(error)
        if self.monitor is not None:
            try:
                self.monitor.__exit__(None, None, None)
            except Exception as error:
                failures.append(error)
        if self.log is not None:
            self.log.close()
        if self.process is not None and (self.directory / f"gpu-acquire-{self.process.pid}.json").exists():
            try:
                await asyncio.to_thread(wait_owned_gpu_release, self.directory, self.process.pid,
                                        profile=self.spec["runtime_name"])
            except Exception as error:
                failures.append(error)
        if self.created and self.spec.get("external_server"):
            try:
                from .external_runtime import verify_identity
                receipt = json.loads((self.directory / "external-identity.json").read_text())
                verify_identity(receipt)
                write_json(self.directory / "external-preserved.json", dict(passed=True, receipt=receipt))
            except Exception as error:
                failures.append(error)
        if self.created:
            write_json(self.directory / "cleanup.json", dict(
                server_pid=self.process.pid if self.process is not None else None,
                server_exit=self.process.returncode if self.process is not None else None,
                passed=not failures, errors=[dict(type=type(e).__name__, detail=str(e))
                                            for e in failures]))
        if failures:
            raise RuntimeError("owned executor cleanup failed: " + str(failures[0]))
