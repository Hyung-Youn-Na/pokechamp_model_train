"""CPU game workers (no torch, no GPU context) talking to the GPU servers through bounded queues."""
from __future__ import annotations

import os
import queue
import time
import uuid

from .config import PROTOCOL
from .game import Cancelled, play


class Evaluator:
    """The worker's only model capability. P0 is exact by construction (zero-init key projection and value
    layer give uniform policies and v = 0; GPU gate G1 checks the network agrees), so it needs no GPU.

    Response channels outlive a Pool (the servers own them), so a request is identified by (pool epoch, sequence).
    An answer to an earlier Pool's request (a benchmark deadline cancels games that wait on inference) or to an
    abandoned earlier request of this worker is stale: it is discarded and counted. Any other mismatch is an error."""

    def __init__(self, index, servers, response, cancel, epoch, timeout=900):
        self.index, self.servers, self.response, self.cancel, self.timeout = index, servers, response, cancel, timeout
        self.epoch, self.sequence, self.stale = epoch, 0, 0

    def _is_stale(self, identity):
        return (isinstance(identity, tuple) and len(identity) == 2
                and (identity[0] != self.epoch or identity[1] < self.sequence))

    def __call__(self, tag, prefix, rows, readouts):
        if tag == "P0":
            policies = [None if r is None else [[1.0 / len(c)] * len(c) if c else [] for c in r.closes] for r in readouts]
            return [0.0] * len(rows), policies, dict(gpu=None, passes=0)
        self.sequence += 1
        identity = (self.epoch, self.sequence)
        self.servers[self.index % len(self.servers)].put((self.index, identity, tag, prefix, rows, readouts))
        deadline = time.monotonic() + self.timeout
        while True:
            if self.cancel.is_set():
                raise Cancelled("inference cancelled")
            try:
                answered, status, *payload = self.response.get(timeout=0.2)
            except queue.Empty:
                if time.monotonic() > deadline:
                    raise TimeoutError("inference response timeout")
                continue
            if answered != identity:
                if self._is_stale(answered):
                    self.stale += 1
                    continue
                raise RuntimeError("inference response identity changed")
            if status != "ok":
                raise RuntimeError("server error: " + str(payload[0])[-2000:])
            values, policies, meta = payload
            return values, policies, meta


def worker(index, jobs, results, servers, response, cancel, context):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from .tokens import Tokens
    tokens = Tokens()
    evaluate = Evaluator(index, servers, response, cancel, context["epoch"])
    limit = context["worker_ram"]
    try:
        import psutil
        process = psutil.Process()
    except ImportError:
        raise RuntimeError("psutil required for worker memory enforcement") from None

    def memory():
        rss = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                rss += child.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        if rss > limit:
            raise MemoryError("worker resident memory limit")

    while not cancel.is_set():
        try:
            job = jobs.get(timeout=0.2)
        except queue.Empty:
            continue
        if job is None:
            break
        stale = evaluate.stale
        try:
            result = play(job, context["teams"], context["statics"], evaluate, tokens, nodes=context["nodes"],
                          stopped=cancel.is_set, check_resources=memory)
        except Exception as error:
            result = dict(job=job, status="invalid", reason=f"{type(error).__name__}: {error}", records=[], roots=[],
                          evidence=None, winner=None, turns=None, metrics={})
        result["metrics"] = dict(result["metrics"], stale_responses=evaluate.stale - stale)
        results.put((index, result))


class Pool:
    def __init__(self, context, servers, responses, *, workers, grace=300):
        import multiprocessing as mp
        if workers > len(responses):
            raise ValueError("more workers than response channels")
        self.grace = grace
        self.ctx = mp.get_context("spawn")
        self.jobs = self.ctx.Queue(maxsize=workers)
        self.results = self.ctx.Queue()
        self.cancel = self.ctx.Event()
        context = dict(context, worker_ram=PROTOCOL["resources"]["ram_bytes"] // max(workers, 1), epoch=uuid.uuid4().hex)
        self.processes = [self.ctx.Process(target=worker, args=(i, self.jobs, self.results, servers, responses[i],
                                                                self.cancel, context), daemon=False)
                          for i in range(workers)]

    def __enter__(self):
        for process in self.processes:
            process.start()
        return self

    def collect(self, jobs, *, on_submit, on_result, check=lambda: None, stop=lambda: False):
        jobs, pending, exhausted = iter(jobs), 0, False
        while pending or not exhausted:
            check()
            if any(p.exitcode is not None for p in self.processes):
                raise RuntimeError("worker exited; reserved slots cannot be retried")
            while pending < len(self.processes) and not exhausted and not stop():
                try:
                    job = next(jobs)
                except StopIteration:
                    exhausted = True
                    break
                on_submit(job)
                self.jobs.put(job)
                pending += 1
            if stop():
                exhausted = True
            if not pending:
                break
            try:
                _, result = self.results.get(timeout=0.1)
            except queue.Empty:
                continue
            pending -= 1
            on_result(result)

    def run_until(self, jobs, until, *, on_result, check=lambda: None):
        """Benchmark helper: keep every worker busy until `until` (monotonic); running games are then cancelled."""
        jobs, pending = iter(jobs), 0
        while time.monotonic() < until:
            check()
            if any(p.exitcode is not None for p in self.processes):
                raise RuntimeError("worker exited during benchmark")
            while pending < len(self.processes):
                self.jobs.put(next(jobs))
                pending += 1
            try:
                _, result = self.results.get(timeout=0.2)
            except queue.Empty:
                continue
            pending -= 1
            on_result(result)

    def __exit__(self, *_):
        """Cooperative shutdown. Workers write requests into queues the servers own; a worker killed while its feeder
        thread is mid-message leaves a partial message that blocks the reading server forever (seen after a benchmark
        deadline). So a worker is never killed while it can still exit: cancelled games stop at their next check, the
        results are drained (and discarded) so result feeders can flush, and the servers keep reading the requests.
        Only a worker still alive after the grace period is killed, and then the shared queues are suspect: raise."""
        self.cancel.set()
        for _ in self.processes:
            try:
                self.jobs.put_nowait(None)
            except queue.Full:
                break
        end = time.monotonic() + self.grace
        while any(p.is_alive() for p in self.processes) and time.monotonic() < end:
            try:
                self.results.get(timeout=0.2)
            except queue.Empty:
                pass
        survivors = [p for p in self.processes if p.is_alive()]
        import psutil
        for process in survivors:
            if process.is_alive():
                try:
                    descendants = psutil.Process(process.pid).children(recursive=True)
                except psutil.NoSuchProcess:
                    descendants = []
                for child in descendants:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                process.terminate()
                process.join(3)
                if process.is_alive():
                    process.kill()
                    process.join(3)
        for q in (self.jobs, self.results):
            q.cancel_join_thread()
            q.close()
        if survivors:
            raise RuntimeError(f"{len(survivors)} worker(s) killed after the {self.grace} s shutdown grace; "
                               "the shared server queues may be corrupted")
