"""Physical GPU ownership and a non-renewable stage clock."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import signal
import time

from ..imitation.resource import gpu_facts
from .battle import BudgetExpired
from .config import PROTOCOL, ROOT
from .storage import atomic, read


@contextmanager
def own_run(directory):
    directory = Path(directory)
    with (directory / "controller.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def own_gpu(directory):
    path = Path(directory) / "resource.json"
    saved = read(path) if path.exists() else None
    selected, handle = None, None
    try:
        facts = gpu_facts()
        for index in ([saved["index"]] if saved else sorted(facts)):
            lock = ROOT / f".pokechamp-data/locks/gpu{index}.lock"
            lock.parent.mkdir(parents=True, exist_ok=True)
            candidate = lock.open("a+")
            try:
                fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                candidate.close()
                continue
            fact = gpu_facts()[index]
            if fact["memory_used_mib"] > 256 or fact["utilization_percent"] > 5:
                candidate.close()
                continue
            selected, handle = fact, candidate
            break
        if handle is None:
            raise RuntimeError("no unoccupied GPU; no resource takeover")
        if saved and saved["uuid"] != selected["uuid"]:
            raise RuntimeError("physical GPU identity changed")
        if not saved:
            atomic(path, selected, exclusive=True)
        os.environ["CUDA_VISIBLE_DEVICES"] = selected["uuid"]
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        yield selected
    finally:
        if handle is not None:
            atomic(Path(directory) / "resource-events" / f"{time.time_ns()}-release.json",
                   dict(uuid=selected["uuid"], at=time.time()), exclusive=True)
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()


class Clock:
    def __init__(self, directory, *, now=time.time, protocol=PROTOCOL):
        self.protocol = protocol
        self.directory, self.now = Path(directory), now
        path = self.directory / "clock.json"
        if not path.exists():
            atomic(path, dict(start=now(), total=self.protocol["total_seconds"]), exclusive=True)
        record = read(path)
        if record["total"] != self.protocol["total_seconds"]:
            raise ValueError("saved total budget differs from execution protocol")
        self.first = record["start"]
        self.cancelled, self.stage, self.stage_end = False, None, self._end(self.first, self.protocol["total_seconds"])
        self.last_resource_check = 0
        self.peak_rss = 0

    @staticmethod
    def _end(start, limit):
        return None if limit is None else start + limit

    def enter(self, stage, *, check_deadline=True):
        path = self.directory / "stages" / f"{stage}.json"
        if path.exists():
            state = read(path)
        else:
            credits = self.directory / "stage-spent.json"
            spent = read(credits).get(stage, 0) if credits.exists() else 0
            limit = self.protocol["stage_seconds"][stage]
            if not isinstance(spent, (int, float)) or spent < 0 or (limit is not None and spent > limit):
                raise ValueError("invalid inherited stage expenditure")
            state = dict(stage=stage, start=self.now(), limit=None if limit is None else limit - spent,
                         inherited_spent=spent)
            atomic(path, state, exclusive=True)
        self.stage = stage
        ends = [self._end(state["start"], state["limit"]),
                self._end(self.first, self.protocol["total_seconds"])]
        finite_ends = [end for end in ends if end is not None]
        self.stage_end = min(finite_ends) if finite_ends else None
        if check_deadline:
            self.check()
        return self.stage_end

    def check(self):
        if self.cancelled or (self.stage_end is not None and self.now() >= self.stage_end):
            raise BudgetExpired("fixed stage/total deadline or SIGTERM")
        if self.now() - self.last_resource_check >= 2:
            self.resources()
            self.last_resource_check = self.now()

    def resources(self):
        import psutil
        process = psutil.Process()
        rss = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                rss += child.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        self.peak_rss = max(self.peak_rss, rss)
        if rss > self.protocol["ram_bytes"]:
            raise MemoryError("experiment RAM limit")
        used = sum(p.stat().st_size for p in self.directory.rglob("*") if p.is_file())
        inherited = self.directory / "inherited-disk.json"
        if inherited.exists():
            used += read(inherited)["bytes"]
        if (self.directory / "exports.json").exists():
            for name in read(self.directory / "exports.json"):
                export = Path(name).resolve()
                if not export.is_relative_to(ROOT / "exports/battle_viewers"):
                    raise ValueError("export path outside owned viewer tree")
                used += sum(p.stat().st_size for p in export.rglob("*") if p.is_file())
        if used > self.protocol["disk_bytes"]:
            raise OSError("experiment disk limit")
        # Importing torch occurs only after GPU ownership in run().
        import sys
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_initialized():
            if torch.cuda.memory_reserved() > self.protocol["gpu_bytes"]:
                raise MemoryError("experiment GPU allocation limit")

    @contextmanager
    def signals(self):
        previous = {}
        def stop(signum, frame):
            self.cancelled = True
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, stop)
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
