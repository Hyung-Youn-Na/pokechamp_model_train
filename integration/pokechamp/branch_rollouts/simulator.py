"""Bounded JSONL transport to the pinned local simulator; no network server."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import threading
import time
from pathlib import Path

from ..providers import CREDENTIAL_NAMES


class SimulatorError(RuntimeError):
    """A failed simulator operation invalidates this process."""


class Simulator:
    def __init__(self, *, timeout=30):
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
            raise ValueError("simulator timeout must be in (0, 120] seconds")
        self.timeout = timeout
        self.closed = False
        self._sequence = 0
        self._lock = threading.RLock()
        self._stderr = bytearray()
        environment = {k: v for k, v in os.environ.items()
                       if k not in CREDENTIAL_NAMES and k != "NODE_OPTIONS"}
        self.process = subprocess.Popen(
            ["node", str(Path(__file__).with_suffix(".cjs"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=environment,
        )
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            os.set_blocking(pipe.fileno(), False)

    def _exchange(self, op, **values):
        with self._lock:
            if self.closed:
                raise SimulatorError("simulator is closed")
            self._sequence += 1
            payload = (json.dumps(dict(op=op, id=self._sequence, **values),
                                  ensure_ascii=False) + "\n").encode()
            if len(payload) > 64 * 1024 * 1024:
                self.close()
                raise SimulatorError("simulator input exceeds 64 MiB")
            deadline = time.monotonic() + self.timeout
            output = bytearray()
            written = 0
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(self.process.stdin, selectors.EVENT_WRITE)
                    selector.register(self.process.stdout, selectors.EVENT_READ)
                    selector.register(self.process.stderr, selectors.EVENT_READ)
                    while b"\n" not in output:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise SimulatorError("simulator response deadline exceeded")
                        for key, _ in selector.select(remaining):
                            if key.fileobj is self.process.stdin:
                                written += os.write(key.fd, payload[written:written + 65536])
                                if written == len(payload):
                                    selector.unregister(self.process.stdin)
                            else:
                                chunk = os.read(key.fd, 65536)
                                if key.fileobj is self.process.stderr:
                                    if not chunk:
                                        selector.unregister(self.process.stderr)
                                    self._stderr.extend(chunk)
                                    self._stderr = self._stderr[-65536:]
                                elif not chunk:
                                    raise SimulatorError("simulator exited before a response")
                                else:
                                    output.extend(chunk)
                                    if len(output) > 64 * 1024 * 1024:
                                        raise SimulatorError("simulator response exceeds 64 MiB")
                if output.count(b"\n") != 1 or not output.endswith(b"\n"):
                    raise SimulatorError("simulator response framing mismatch")
                response = json.loads(output)
                if response.get("id") != self._sequence:
                    raise SimulatorError("simulator response ID mismatch")
                if not response.get("ok"):
                    raise SimulatorError("simulator rejected operation: " + json.dumps(response.get("error")))
                if time.monotonic() > deadline:
                    raise SimulatorError("simulator response deadline exceeded")
                return response["result"]
            except BaseException as error:
                diagnostic = self._stderr.decode(errors="replace")[-4000:]
                self.close()
                if isinstance(error, (KeyboardInterrupt, SystemExit, TimeoutError)):
                    raise
                raise SimulatorError(f"{op}: {error}; stderr={diagnostic}") from error

    def init(self, teams, seed, *, player_order=None, formatid="gen9ou"):
        return self._exchange("init", teams=teams, seed=seed, formatid=formatid,
                              player_order=player_order or list(teams))

    def step(self, choices):
        return self._exchange("step", choices=choices)

    def snapshot(self):
        return self._exchange("snapshot")

    def restore(self, snapshot):
        return self._exchange("restore", snapshot=snapshot)

    def reseed(self, seed):
        return self._exchange("reseed", seed=seed)

    def status(self):
        return self._exchange("status")

    def close(self):
        with self._lock:
            if self.closed:
                return
            self.closed = True
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                pipe.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
