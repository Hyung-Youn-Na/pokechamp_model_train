"""Persistent CPU workers plus one bounded batched inference thread on the owned GPU."""
from __future__ import annotations

from collections import defaultdict, deque
import multiprocessing as mp
import os
import queue
import threading
import time

from .battle import BudgetExpired, play, probe
from .config import PROTOCOL


def worker(index, jobs, results, requests, response, cancel, teams, game_seconds):
    # Worker imports no torch and owns no GPU context.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    sequence = 0
    def evaluate(model, observations):
        nonlocal sequence
        sequence += 1
        requests.put((index, sequence, model, observations))
        while not cancel.is_set():
            try:
                rid, value, error = response.get(timeout=0.2)
            except queue.Empty:
                continue
            if rid != sequence:
                raise RuntimeError("inference response identity changed")
            if error:
                raise RuntimeError(error)
            return value
        raise BudgetExpired("inference cancelled")
    try:
        import psutil
        process = psutil.Process()
        def memory():
            rss = process.memory_info().rss
            for child in process.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            if rss > PROTOCOL["ram_bytes"] // 16:
                raise MemoryError("worker resident memory limit")
    except ImportError:
        raise RuntimeError("psutil required for worker memory enforcement") from None
    while not cancel.is_set():
        try:
            job = jobs.get(timeout=0.2)
        except queue.Empty:
            continue
        if job is None:
            break
        try:
            function = probe if job.get("kind") == "probe" else play
            args = (job, evaluate) if function is probe else (job, teams, evaluate)
            options = {} if function is probe else {"game_seconds": game_seconds}
            result = function(*args, stopped=cancel.is_set, check_resources=memory, **options)
        except Exception as error:
            result = dict(job={k: v for k, v in job.items() if k not in ("deadline", "root")},
                          status="invalid", reason=f"{type(error).__name__}: {error}", metrics={})
        results.put((index, result))


class Pool:
    def __init__(self, teams, models, *, workers=8, batch_size=32, game_seconds=PROTOCOL["game_seconds"]):
        self.context = mp.get_context("spawn")
        self.jobs = self.context.Queue(maxsize=workers)
        self.results = self.context.Queue()
        self.requests = self.context.Queue(maxsize=workers)
        self.responses = [self.context.Queue(maxsize=1) for _ in range(workers)]
        self.cancel = self.context.Event()
        self.models, self.batch_size = models, batch_size
        self.threads_stop = threading.Event()
        self.failure, self.metrics = None, dict(batches=0, observations=0, seconds=0.0, largest_batch=0)
        self.processes = [self.context.Process(target=worker, args=(i, self.jobs, self.results,
            self.requests, self.responses[i], self.cancel, teams, game_seconds), daemon=False) for i in range(workers)]
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self):
        pending = deque()
        try:
            while not self.threads_stop.is_set():
                if not pending:
                    try:
                        pending.append(self.requests.get(timeout=0.05))
                    except queue.Empty:
                        continue
                until = time.monotonic() + PROTOCOL["batch_wait_seconds"]
                while time.monotonic() < until:
                    try:
                        pending.append(self.requests.get(timeout=max(0.00001, until - time.monotonic())))
                    except queue.Empty:
                        break
                group = defaultdict(list)
                while pending:
                    request = pending.popleft()
                    group[request[2]].append(request)
                for model, calls in group.items():
                    flat = [obs for _, _, _, observations in calls for obs in observations]
                    output = []
                    start = time.monotonic()
                    for offset in range(0, len(flat), self.batch_size):
                        batch = flat[offset:offset + self.batch_size]
                        output.extend(self.models[model].evaluate_batch(batch))
                        self.metrics["batches"] += 1
                        self.metrics["observations"] += len(batch)
                        self.metrics["largest_batch"] = max(self.metrics["largest_batch"], len(batch))
                    self.metrics["seconds"] += time.monotonic() - start
                    offset = 0
                    for index, sequence, _, observations in calls:
                        self.responses[index].put((sequence, output[offset:offset + len(observations)], None))
                        offset += len(observations)
        except BaseException as error:
            self.failure = f"{type(error).__name__}: {error}"
            self.cancel.set()

    def __enter__(self):
        for process in self.processes:
            process.start()
        self.thread.start()
        return self

    def collect(self, jobs, *, on_submit, on_result, check=lambda: None, retain=True):
        jobs = iter(jobs)
        pending, finished, exhausted = 0, [], False
        while pending or not exhausted:
            check()
            if self.failure:
                raise RuntimeError("inference failed: " + self.failure)
            if any(p.exitcode is not None for p in self.processes):
                raise RuntimeError("worker exited; reserved slots cannot be retried")
            while pending < len(self.processes) and not exhausted:
                try:
                    job = next(jobs)
                except StopIteration:
                    exhausted = True
                    break
                on_submit(job)
                self.jobs.put(job)
                pending += 1
            if not pending:
                break
            try:
                _, result = self.results.get(timeout=0.1)
            except queue.Empty:
                continue
            pending -= 1
            on_result(result)
            if retain:
                finished.append(result)
            if result["status"] == "invalid":
                raise RuntimeError("shared pipeline failure: " + str(result["reason"]))
        return finished

    def __exit__(self, *_):
        self.cancel.set()
        end = time.monotonic() + 3
        for process in self.processes:
            process.join(max(0, end - time.monotonic()))
        # Kill only our descendants, including Node/actor grandchildren on forced shutdown.
        import psutil
        for process in self.processes:
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
                process.join(2)
                if process.is_alive():
                    process.kill()
                    process.join(2)
                for child in descendants:
                    try:
                        if child.is_running():
                            child.kill()
                    except psutil.NoSuchProcess:
                        pass
        self.threads_stop.set()
        self.thread.join(5)
        for q in [self.jobs, self.results, self.requests, *self.responses]:
            q.cancel_join_thread()
            q.close()
