"""One fail-closed Node process per actor, independent state per battle."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import threading
import time
from pathlib import Path

from . import OFFICIAL
from .build import DEFAULT_BUILD, verify
from ..providers import CREDENTIAL_NAMES


class ObservationError(ValueError):
    """Official observation cannot be used for an action."""


def rows(prefix):
    result = []
    previous = -1
    for event in prefix:
        seq = event["event_seq"]
        if not isinstance(seq, int) or seq <= previous:
            raise ObservationError("non-increasing protocol events")
        previous = seq
        for index, line in enumerate(event["protocol"].splitlines()):
            result.append((seq, index, line))
    return result


class OfficialClient:
    def __init__(self, actor, build=DEFAULT_BUILD, *, timeout=30):
        if actor not in ("p1", "p2"):
            raise ObservationError("invalid actor")
        if timeout <= 0:
            raise ObservationError("invalid official response timeout")
        started = time.monotonic()
        self.identity = verify(build)
        self.build_verification_ms = (time.monotonic() - started) * 1000
        self.actor = actor
        self.timeout = timeout
        self.prefixes = {}
        self.metrics = []
        self.failures = []
        self.lock = threading.RLock()
        self.closed = False
        self.process = subprocess.Popen(
            ["node", "--max-old-space-size=256", str(Path(__file__).with_name("client.cjs")),
             "serve", str(Path(build).resolve()), actor],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={key: value for key, value in os.environ.items() if key not in CREDENTIAL_NAMES},
        )
        os.set_blocking(self.process.stdin.fileno(), False)
        os.set_blocking(self.process.stdout.fileno(), False)

    def _exchange(self, value):
        if self.closed:
            raise ObservationError("official process is closed; no fallback")
        started = time.monotonic()
        value = dict(value, timeout_ms=min(30000, self.timeout * 1000))
        payload = (json.dumps(value, ensure_ascii=False) + "\n").encode()
        if len(payload) > 16 * 1024 * 1024:
            self.close()
            raise ObservationError("official protocol batch exceeds limit")
        deadline = started + self.timeout
        diagnostic = {}
        output = bytearray()
        written = 0
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdin, selectors.EVENT_WRITE)
                selector.register(self.process.stdout, selectors.EVENT_READ)
                while b"\n" not in output:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ObservationError("official response deadline exceeded")
                    for key, _ in selector.select(remaining):
                        if key.fileobj is self.process.stdin:
                            written += os.write(key.fd, payload[written:written + 65536])
                            if written == len(payload):
                                selector.unregister(self.process.stdin)
                        else:
                            chunk = os.read(key.fd, 65536)
                            if not chunk:
                                raise ObservationError("official Node exited")
                            output.extend(chunk)
                            if len(output) > 32 * 1024 * 1024:
                                raise ObservationError("official response exceeds limit")
            if not output.endswith(b"\n") or output.count(b"\n") != 1:
                raise ObservationError("official response framing mismatch")
            response = json.loads(output)
            if time.monotonic() >= deadline:
                raise ObservationError("official response deadline exceeded")
            diagnostic = response.get("diagnostic", {})
            if not response.get("ok"):
                raise ObservationError(response.get("error", "official tracker error"))
            self.metrics.append(dict(operation=value["op"], battle_id=value["battle_id"],
                                     elapsed_ms=(time.monotonic() - started) * 1000,
                                     rss_bytes=response["rss_bytes"]))
            return response["state"]
        except BaseException as error:
            failure = dict(operation=value["op"], battle_id=value["battle_id"],
                           stage="exchange", elapsed_ms=(time.monotonic() - started) * 1000,
                           error=str(error), **{"node": diagnostic})
            self.failures.append(failure)
            self.close()
            if isinstance(error, ObservationError):
                raise ObservationError(str(error) + "; diagnostic=" + json.dumps(failure)) from error
            raise

    def snapshot(self, prefix, battle_id, *, boundary=None, replay=False):
        with self.lock:
            try:
                current = rows(prefix)
                if not current:
                    raise ObservationError("empty official observation prefix")
                end = dict(protocol_event_seq=current[-1][0], line_index=current[-1][1])
                if boundary is not None and any(boundary.get(k) != v for k, v in end.items()):
                    raise ObservationError("decision row boundary mismatch")
                previous = [] if replay else self.prefixes.get(battle_id, [])
                if current[:len(previous)] != previous:
                    raise ObservationError("official prefix changed or moved backwards")
                result = self._exchange(dict(
                    op="replay" if replay else "append", actor=self.actor, battle_id=battle_id,
                    offset=len(previous), lines=[r[2] for r in current[len(previous):]],
                ))
                if result["consumed"] != len(current):
                    raise ObservationError("official consumed-row mismatch")
                if not replay:
                    self.prefixes[battle_id] = current
                return result
            except BaseException:
                self.close()
                raise

    def drop(self, battle_id):
        with self.lock:
            self._exchange(dict(op="drop", actor=self.actor, battle_id=battle_id))
            self.prefixes.pop(battle_id, None)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.process.stdin.close()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
