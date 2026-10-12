"""Owned JSON Lines calculator process; failures cannot produce action inputs."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import selectors
import subprocess
import threading
from pathlib import Path


class CalculationError(RuntimeError):
    pass


def expected_patch():
    raw = (
        Path(__file__)
        .with_name("calculator")
        .joinpath("ruination-v1.json")
        .read_bytes()
    )
    patch = json.loads(raw)
    if patch["patch_id"] != "ruination-v1" or patch["version"] != "0.11.0":
        raise CalculationError("calculator patch manifest drift")
    return {
        "patch_id": patch["patch_id"],
        "patch_sha256": hashlib.sha256(raw).hexdigest(),
        "files": {f["path"]: f["after_sha256"] for f in patch["files"]},
    }


def expected_state_patch():
    raw = (
        Path(__file__)
        .with_name("calculator")
        .joinpath("mechanics-v2.json")
        .read_bytes()
    )
    patch = json.loads(raw)
    if patch["patch_id"] != "mechanics-v2" or patch["version"] != "0.11.0":
        raise CalculationError("calculator state patch manifest drift")
    return dict(
        patch_id=patch["patch_id"],
        patch_sha256=hashlib.sha256(raw).hexdigest(),
        files={f["path"]: f["after_sha256"] for f in patch["files"]},
    )


class Calculator:
    def __init__(self, *, timeout=30):
        self.timeout = timeout
        self.owner_pid = os.getpid()
        self.lock = threading.Lock()
        self.last_request = None
        self.last_response = None
        env = {
            k: v
            for k, v in os.environ.items()
            if not any(
                word in k.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")
            )
        }
        self.process = subprocess.Popen(
            ["node", str(Path(__file__).with_name("calculator") / "worker.cjs")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        try:
            response = self._read_response()
            if response.get("status") != "ready":
                raise CalculationError(
                    response.get("error", "calculator startup failed")
                )
            if response.get("engine_patch") != expected_patch():
                raise CalculationError("calculator patch identity mismatch")
        except (OSError, ValueError, KeyError, CalculationError) as exc:
            self.close()
            raise CalculationError(str(exc)) from exc

    def _read_response(self):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(self.timeout):
                raise CalculationError("calculator timeout")
        line = self.process.stdout.readline()
        if not line:
            raise CalculationError("calculator process exited without response")
        return json.loads(line)

    def calculate(self, identity, scenarios):
        if os.getpid() != self.owner_pid:
            raise CalculationError("calculator cannot be shared across actor processes")
        with self.lock:
            try:
                self.last_request = {"identity": identity, "scenarios": scenarios}
                if identity.get("input_version"):
                    self.last_request["semantics_version"] = identity["input_version"]
                self.last_response = None
                request = json.dumps(self.last_request, allow_nan=False)
                self.process.stdin.write(request.encode() + b"\n")
                self.process.stdin.flush()
                response = self._read_response()
                self.last_response = response
                if response.get("identity") != identity:
                    raise CalculationError("stale or foreign calculator response")
                if response.get("status") != "success":
                    raise CalculationError(response.get("error", "calculator failed"))
                expected = [s["scenario_id"] for s in scenarios]
                if (
                    len(expected) != len(set(expected))
                    or [e["scenario_id"] for e in response["entries"]] != expected
                ):
                    raise CalculationError("calculator coverage mismatch")
                if response.get("engine_version") != "0.11.0":
                    raise CalculationError("calculator version drift")
                if response.get("engine_patch") != expected_patch():
                    raise CalculationError("calculator patch identity mismatch")
                if response.get("semantics_version") != identity.get("input_version"):
                    raise CalculationError("calculator semantics identity mismatch")
                if (
                    identity.get("input_version")
                    and response.get("runtime_patch") != expected_state_patch()
                ):
                    raise CalculationError("calculator state patch identity mismatch")
                return response
            except (OSError, ValueError, KeyError, CalculationError) as exc:
                self.close()
                raise CalculationError(str(exc)) from exc

    def close(self):
        if os.getpid() != self.owner_pid:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            with contextlib.suppress(OSError):
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
