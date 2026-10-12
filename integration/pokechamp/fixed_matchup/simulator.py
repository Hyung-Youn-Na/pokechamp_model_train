"""Capability-separated Node workers over the existing bounded JSONL transport."""
import os
from pathlib import Path
import subprocess
import threading

from ..branch_rollouts.simulator import Simulator as Transport
from ..providers import CREDENTIAL_NAMES


class Simulator(Transport):
    def __init__(self, role, *, timeout=30):
        if role not in ("real", "search") or not 0 < timeout <= 120:
            raise ValueError("explicit role and bounded timeout required")
        self.role, self.timeout = role, timeout
        self.closed, self._sequence = False, 0
        self._lock, self._stderr = threading.RLock(), bytearray()
        environment = {k: v for k, v in os.environ.items()
                       if k not in CREDENTIAL_NAMES and k != "NODE_OPTIONS"}
        self.process = subprocess.Popen(
            ["node", str(Path(__file__).with_suffix(".cjs")), role],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
        )
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            os.set_blocking(pipe.fileno(), False)

    def init(self, teams, seed):
        return self._exchange("init", teams=teams, seed=seed)

    def restore(self, root, seed):
        return self._exchange("restore", root=root, seed=seed)

    def advance(self, actions):
        return self._exchange("advance", actions=actions)

    def evidence(self):
        return self._exchange("evidence")

    def catalog(self):
        return self._exchange("catalog")

    def validate(self, teams):
        return self._exchange("validate", teams=teams)

    def snapshot(self):
        raise PermissionError("use public roots; private snapshots only through real evidence")

    def reseed(self, seed):
        raise PermissionError("actual RNG immutable; search receives an independent seed at restore")

    def step(self, choices):
        raise PermissionError("only atomic advance(joint_actions) is supported")
