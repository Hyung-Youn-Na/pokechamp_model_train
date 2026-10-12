"""Capability-separated Node workers for sim.cjs over the vendored bounded JSONL transport."""
import os
from pathlib import Path
import subprocess
import threading

from .vendor.transport import CREDENTIAL_NAMES, Simulator as Transport


class Simulator(Transport):
    def __init__(self, role, *, timeout=60):
        if role not in ("real", "search") or not 0 < timeout <= 120:
            raise ValueError("explicit role and bounded timeout required")
        self.role, self.timeout = role, timeout
        self.closed, self._sequence = False, 0
        self._lock, self._stderr = threading.RLock(), bytearray()
        environment = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_NAMES and k != "NODE_OPTIONS"}
        self.process = subprocess.Popen(
            ["node", str(Path(__file__).with_name("sim.cjs")), role],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            os.set_blocking(pipe.fileno(), False)

    def validate(self, teams):
        return self._exchange("validate", teams=teams)

    def init(self, teams, seed):
        return self._exchange("init", teams=teams, seed=seed)

    def advance(self, actions):
        return self._exchange("advance", actions=actions)

    def evidence(self):
        return self._exchange("evidence")

    def expand(self, root, children):
        return self._exchange("expand", root=root, children=children)

    def describe(self, root):
        return self._exchange("describe", root=root)

    def step(self, choices):
        raise PermissionError("only atomic advance(joint_actions) is supported")

    def snapshot(self):
        raise PermissionError("private snapshots only through real evidence")

    def restore(self, snapshot):
        raise PermissionError("search expands public roots; no private restore")

    def reseed(self, seed):
        raise PermissionError("actual RNG is immutable")
