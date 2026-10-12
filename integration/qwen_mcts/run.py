"""EX-080 controller. Imports no torch: all GPU work happens in the two GPU server processes (server.py).
Every stage is resumable at completed units; reserved-but-unfinished games are recorded incomplete, never replayed."""
from __future__ import annotations

import fcntl
import gzip
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import signal
import time
import uuid

from . import evaluation as E
from . import gates as G
from . import replay as R
from . import schedule as S
from .config import GPUS, PROTOCOL, TRAIN_GPU
from .prepare import team_texts, verify
from .storage import atomic, atomic_bytes, digest, encoded, read, sha, seed

MAX_WORKERS = max(PROTOCOL["benchmark"]["workers"])
TRAINABLE = ("completed", "censored")


class StageStop(RuntimeError):
    """A protocol stop (technical failure, gate failure); recorded, never auto-resumed past."""


class Servers:
    def __init__(self, run, manifest, statics):
        from .server import serve
        ctx = mp.get_context("spawn")
        self.requests = {i: ctx.Queue() for i in GPUS}
        self.control = {i: ctx.Queue() for i in GPUS}
        self.results = {i: ctx.Queue() for i in GPUS}
        self.responses = [ctx.Queue() for _ in range(MAX_WORKERS)]
        static_ids = {k: v["ids"] for k, v in statics.items()}
        self.processes = {}
        for index in sorted(GPUS):
            spec = dict(index=index, run=str(run), train=index == TRAIN_GPU, static_ids=static_ids,
                        pad_id=manifest["pad_id"])
            process = ctx.Process(target=serve, args=(spec, self.control[index], self.results[index],
                                                      self.requests[index], self.responses), daemon=False)
            process.start()
            self.processes[index] = process
        self.ready = {}
        for index in sorted(GPUS):
            self.ready[index] = self._wait(index, "ready", timeout=1800)

    def _wait(self, index, cid, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if not self.processes[index].is_alive():
                raise RuntimeError(f"GPU{index} server exited (code {self.processes[index].exitcode})")
            try:
                item = self.results[index].get(timeout=1)
            except queue.Empty:
                if deadline is not None and time.monotonic() > deadline:
                    raise TimeoutError(f"GPU{index} server did not answer {cid}")
                continue
            if item[0] != cid:
                raise RuntimeError(f"GPU{index} answered {item[0]} while waiting for {cid}")
            if item[1] != "ok":
                raise RuntimeError(f"GPU{index} {cid} failed:\n{item[2][-6000:]}")
            return item[2]

    def call(self, index, op, args=None, timeout=None):
        cid = uuid.uuid4().hex
        self.control[index].put((cid, op, args or {}))
        return self._wait(index, cid, timeout)

    def broadcast(self, op, args=None):
        return {index: self.call(index, op, args) for index in sorted(GPUS)}

    def queues(self):
        return [self.requests[i] for i in sorted(GPUS)]

    def stop(self):
        for index, process in self.processes.items():
            if process.is_alive():
                try:
                    self.call(index, "stop", timeout=120)   # a server blocked on a corrupted queue never answers
                except Exception:
                    pass
        for process in self.processes.values():
            process.join(30)
            if process.is_alive():
                process.terminate()
                process.join(10)


class Controller:
    def __init__(self, run):
        self.run = Path(run)
        self.cancelled = False
        self.peak_rss = 0

    # ---- bookkeeping ----
    def event(self, kind, **details):
        line = encoded(dict(at=time.time(), event=kind, **details)) + b"\n"
        with (self.run / "events.jsonl").open("ab") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())

    def check(self):
        if self.cancelled:
            raise KeyboardInterrupt("cancelled by signal")
        now = time.monotonic()
        if now - getattr(self, "_checked", 0.0) < 5.0:   # the process-tree RSS walk is throttled; cancellation is not
            return
        self._checked = now
        import psutil
        # Proportional set size: shared pages (torch/CUDA libraries, forked compile helpers) are divided among the
        # processes that map them. Summed RSS counted them once per process (29 GiB RSS vs 5.3 GiB PSS measured).
        root = psutil.Process()
        used = 0
        for process in [root, *root.children(recursive=True)]:
            try:
                used += process.memory_full_info().pss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        self.peak_rss = max(self.peak_rss, used)
        if used > PROTOCOL["resources"]["ram_bytes"]:
            raise StageStop(f"RAM limit exceeded (PSS): {used}")

    def disk(self):
        used = sum(p.stat().st_size for p in self.run.rglob("*") if p.is_file())
        if used > PROTOCOL["resources"]["disk_bytes"]:
            raise StageStop(f"disk limit exceeded: {used}")
        return used

    # ---- games ----
    def save_result(self, group, result):
        slot = result["job"]["slot_id"]
        directory = self.run / "games" / group / slot
        atomic_bytes(directory / "decisions.jsonl.gz",
                      gzip.compress(b"".join(encoded(r) + b"\n" for r in result["records"]), mtime=0), exclusive=True)
        atomic_bytes(directory / "roots.jsonl.gz",
                      gzip.compress(b"".join(encoded(r) + b"\n" for r in result["roots"]), mtime=0), exclusive=True)
        atomic_bytes(directory / "evidence.json.gz", gzip.compress(encoded(result["evidence"]), mtime=0), exclusive=True)
        summary = {k: result[k] for k in ("job", "status", "winner", "reason", "turns", "metrics")}
        summary["files"] = {name: sha(directory / name) for name in ("decisions.jsonl.gz", "roots.jsonl.gz", "evidence.json.gz")}
        summary["decisions"] = len(result["records"])
        atomic(directory / "result.json", summary, exclusive=True)
        return summary

    def load_result(self, group, slot, *, records=True):
        directory = self.run / "games" / group / slot
        summary = read(directory / "result.json")
        for name, checksum in summary["files"].items():
            if sha(directory / name) != checksum:
                raise ValueError(f"game artifact changed: {group}/{slot}/{name}")
        if records:
            with gzip.open(directory / "decisions.jsonl.gz", "rt") as stream:
                summary["records"] = [json.loads(line) for line in stream if line.strip()]
        return summary

    def run_group(self, group, jobs, *, records=True):
        settings = read(self.run / "settings.json")
        claims = self.run / "claims" / group
        results, pending = {}, []
        for job in jobs:
            slot = job["slot_id"]
            if (self.run / "games" / group / slot / "result.json").exists():
                results[slot] = self.load_result(group, slot, records=records)
            elif (claims / f"{slot}.json").exists():
                # Reserved before an interruption: recorded incomplete, never replayed (C-018).
                summary = dict(job=job, status="incomplete", winner=None, reason="interrupted before completion",
                               turns=None, metrics={}, records=[], roots=[], evidence=None)
                results[slot] = self.save_result(group, summary)
                results[slot]["records"] = []
            else:
                pending.append(job)
        if pending:
            from .pool import Pool
            statics = {k: dict(text_sha256=v["text_sha256"]) for k, v in self.statics.items()}
            context = dict(teams=self.teams, statics=statics, nodes=settings["nodes"])

            def submit(job):
                atomic(claims / f"{job['slot_id']}.json", dict(job=job, at=time.time()), exclusive=True)

            def receive(result):
                summary = self.save_result(group, result)
                summary["records"] = result["records"] if records else None
                results[result["job"]["slot_id"]] = summary

            with Pool(context, self.servers.queues(), self.servers.responses, workers=settings["workers"]) as pool:
                pool.collect(pending, on_submit=submit, on_result=receive, check=self.check)
        self.disk()
        return [results[job["slot_id"]] for job in jobs]

    # ---- stages ----
    def gates(self):
        path = self.run / "gates.json"
        if path.exists():
            report = read(path)
            if not report["passed"]:
                raise StageStop("GPU gates failed earlier; a new identity is required")
            return report
        from .tokens import Tokens
        directory = self.run / "gates"
        rows, targets = G.gate_inputs(self.teams, Tokens())
        atomic(directory / "inputs.json", dict(rows=rows), exclusive=False)
        atomic_bytes(directory / "replay.jsonl.gz", gzip.compress(b"".join(encoded(t) + b"\n" for t in targets), mtime=0))
        p0 = str(self.run / "models/round-000")
        train, other = TRAIN_GPU, next(i for i in sorted(GPUS) if i != TRAIN_GPU)
        report = dict(env=self.servers.broadcast("gate", dict(name="env")))
        progress = lambda: atomic(directory / "progress.json", report)   # partial results survive a failing gate
        env_ok = all(v["deterministic"] and not any(v["tf32"]) and not v["bf16_reduced"] and v["cublas"] == ":4096:8"
                     for v in report["env"].values())
        # G1: P0 network outputs are exactly uniform / zero (the worker shortcut relies on it).
        self.servers.broadcast("gate", dict(name="load", tag="P0net", directory=p0))
        g1 = {}
        for index in sorted(GPUS):
            out = self.servers.call(index, "gate", dict(name="outputs", tag="P0net", rows=rows))
            values = [v for o in out.values() for v in o["values"]]
            sides = [side for o in out.values() for p in o["policies"] if p for side in p if side]
            # "logit ≡ 0": every candidate of a side gets the bitwise-same float32 probability. Its distance to the
            # float64 1/K of the worker shortcut is float32 representation only (~1e-8) and is reported, not judged.
            equal = all(len(set(side)) == 1 for side in sides)
            deviation = max([0.0] + [abs(x - 1.0 / len(side)) for side in sides for x in side])
            g1[str(index)] = dict(max_value=max(abs(v) for v in values), equal_logits=equal, sides=len(sides),
                             float32_representation_gap=deviation,
                             passed=all(v == 0.0 for v in values) and equal and deviation < 1e-7)
        report["g1"] = g1
        progress()
        self.servers.broadcast("drop", dict(tag="P0net"))
        # Probe model for parity gates (random LoRA B and heads), shared through disk.
        probe = str(directory / "probe")
        report["probe"] = self.servers.call(train, "gate", dict(name="probe_create", p0=p0, directory=probe))
        self.servers.call(other, "gate", dict(name="load", tag="probe", directory=probe))
        base = dict(name="outputs", tag="probe", rows=rows)
        a = self.servers.call(train, "gate", base)
        b = self.servers.call(train, "gate", base)
        c = self.servers.call(other, "gate", base)
        report["g2"] = dict(repeat=G.compare(a, b), cross_gpu=G.compare(a, c))
        report["g2"]["passed"] = all(v == 0.0 for d in report["g2"].values() for v in d.values())
        progress()
        # G3 (D-128): fixed-shape passes make every row's output independent of its batch -> bitwise equality.
        roots = [r for r in rows if r["readout"] is not None]
        children = [r for r in rows if r["readout"] is None]
        sample = roots[:16] + children[::max(1, len(children) // 80)][:80]
        g3 = self.servers.call(train, "gate", dict(name="invariance", tag="probe", rows=sample))
        report["g3"] = dict(g3, passed=g3["bitwise_equal"])
        progress()
        # G4 (D-128): path equivalence judged in an fp32 copy with the registered tolerance; bf16 gaps are recorded.
        subset = roots[:12] + children[:36]
        g4 = self.servers.call(train, "gate", dict(name="paths_fp32", tag="probe", directory=probe, rows=subset))
        report["g4"] = dict(fp32=g4, bf16_record=self.servers.call(train, "gate", dict(name="paths", tag="probe", rows=subset)),
                            passed=all(v <= G.TOL["batch_tolerance"] for d in g4.values() for v in d.values()))
        progress()
        g5 = self.servers.call(train, "gate", dict(name="cache", tag="probe", rows=rows[:64], passes=100))
        report["g5"] = dict(g5, passed=g5["unchanged"])
        progress()
        report["g6"] = dict(cross_gpu_reload=report["g2"]["cross_gpu"], passed=report["g2"]["passed"])
        g7 = self.servers.call(train, "gate", dict(name="train", p0=p0, replay=str(directory / "replay.jsonl.gz"),
                                                   directory=str(directory / "resume")))
        report["g7"] = g7
        progress()
        g8 = {str(train): self.servers.call(train, "gate", dict(name="memory", tag="probe", rows=rows, train=True,
                                                           replay=str(directory / "replay.jsonl.gz"), p0=p0)),
              str(other): self.servers.call(other, "gate", dict(name="memory", tag="probe", rows=rows))}
        report["g8"] = dict(g8, passed=all(v["passed"] for v in g8.values()))
        report["g0"] = dict(passed=env_ok)
        report["passed"] = all(report[g]["passed"] for g in ("g0", "g2", "g3", "g4", "g5", "g6", "g7", "g8")) and \
            all(v["passed"] for v in g1.values())
        report["rows"] = len(rows)
        atomic(path, report, exclusive=True)
        self.event("gates", passed=report["passed"])
        if not report["passed"]:
            raise StageStop("GPU gates failed; criteria are not relaxed")
        return report

    def benchmark(self):
        path = self.run / "settings.json"
        if path.exists():
            return read(path)
        b = PROTOCOL["benchmark"]
        self.servers.broadcast("load", dict(tag="current", directory=str(self.run / "models/round-000")))
        measurements = []
        for workers in b["workers"]:
            for nodes in b["search_nodes"]:
                label = f"w{workers}-n{nodes}"
                target = self.run / "benchmarks" / f"{label}.json"
                if target.exists():
                    measurements.append(read(target))
                    continue
                from .pool import Pool
                statics = {k: dict(text_sha256=v["text_sha256"]) for k, v in self.statics.items()}
                context = dict(teams=self.teams, statics=statics, nodes=nodes)
                jobs = iter(S.bench(label, 10_000))
                finished = []
                with Pool(context, self.servers.queues(), self.servers.responses, workers=workers) as pool:
                    pool.run_until(jobs, time.monotonic() + b["warmup_seconds"], on_result=finished.append, check=self.check)
                    before = self.servers.broadcast("stats")
                    pool.run_until(jobs, time.monotonic() + b["measure_seconds"], on_result=finished.append, check=self.check)
                    after = self.servers.broadcast("stats")
                seconds = max(after[i]["at"] - before[i]["at"] for i in GPUS)
                requests = sum(after[i]["requests"] - before[i]["requests"] for i in GPUS)
                row = dict(workers=workers, nodes=nodes, seconds=seconds, decisions_per_second=requests / seconds,
                           rows_per_second=sum(after[i]["rows"] - before[i]["rows"] for i in GPUS) / seconds,
                           busy={str(i): (after[i]["busy"] - before[i]["busy"]) / seconds for i in GPUS},
                           invalid=sum(1 for r in finished if r["status"] == "invalid"),
                           completed_games=sum(1 for r in finished if r["status"] in TRAINABLE))
                atomic(target, row, exclusive=True)
                measurements.append(row)
                if row["invalid"]:
                    raise StageStop(f"benchmark produced invalid games: {label}")
        best = sorted(measurements, key=lambda r: (-r["decisions_per_second"], r["workers"], r["nodes"]))[0]
        settings = dict(workers=best["workers"], nodes=best["nodes"])
        atomic(path, settings, exclusive=True)
        self.event("benchmark", **settings, decisions_per_second=best["decisions_per_second"])
        return settings

    def smoke(self):
        path = self.run / "smoke.json"
        if path.exists():
            return read(path)
        self.servers.broadcast("load", dict(tag="current", directory=str(self.run / "models/round-000")))
        results = self.run_group("smoke", S.smoke())
        rows = sum(len(R.rows(r)) for r in results)
        report = dict(statuses=[r["status"] for r in results], decisions=sum(r["decisions"] for r in results),
                      replay_rows=rows, seconds=[r["metrics"].get("seconds") for r in results])
        report["passed"] = all(s in TRAINABLE for s in report["statuses"]) and rows > 0
        atomic(path, report, exclusive=True)
        self.event("smoke", passed=report["passed"])
        if not report["passed"]:
            raise StageStop("technical smoke failed")
        return report

    def history(self):
        out = []
        for path in sorted((self.run / "rounds").glob("*/dev.json")):
            record = read(path)
            out.append((record["round"], record["score"]))
        return out

    def dev_evaluation(self, round_id):
        path = self.run / "rounds" / f"{round_id:03d}" / "dev.json"
        interval = PROTOCOL["evaluation"]["interval"]
        if not path.exists():
            previous = round_id - interval
            tag = "P0" if previous == 0 else f"r{previous:03d}"
            if tag != "P0":
                self.servers.broadcast("load", dict(tag=tag, directory=str(self.run / "models" / f"round-{previous:03d}")))
            dev = self.run_group(f"dev-{round_id:03d}", S.dev(round_id, tag), records=False)
            score, scores = E.evaluation_score(dev)
            reference = self.run_group(f"p0ref-{round_id:03d}", S.p0_reference(round_id), records=False)
            p0_score, _ = E.evaluation_score(reference)
            if tag != "P0":
                self.servers.broadcast("drop", dict(tag=tag))
            if score is None or p0_score is None:
                raise StageStop(f"technical failure inside the round-{round_id} evaluation; not judged")
            censored = sum(1 for r in dev if r["status"] == "censored")
            atomic(path, dict(round=round_id, score=score, opponent=tag, games=len(dev), censored=censored,
                              p0_score=p0_score, p0_games=len(reference)), exclusive=True)
        record = read(path)
        reasons = E.stop_reasons(self.history())
        self.event("dev", round=round_id, score=record["score"], p0_score=record["p0_score"], stop=reasons)
        return reasons

    def training(self):
        stop_path = self.run / "train-stop.json"
        if stop_path.exists():
            return read(stop_path)
        e = PROTOCOL["evaluation"]
        committed = sorted(int(p.parent.name) for p in (self.run / "rounds").glob("*/commit.json"))
        last = committed[-1] if committed else 0
        model = self.run / "models" / f"round-{last:03d}"
        state = self.run / "checkpoints" / f"round-{last:03d}.pt"
        self.servers.call(TRAIN_GPU, "restore_learner", dict(directory=str(model), state=str(state) if last else None))
        self.servers.broadcast("load", dict(tag="current", directory=str(model)))
        if last and last % e["interval"] == 0:
            reasons = self.dev_evaluation(last)
            if reasons:
                return self.stop_training(last, reasons)
        for round_id in range(last + 1, e["max_rounds"] + 1):
            self.check()
            results = self.run_group(f"train-{round_id:03d}", S.self_play(round_id))
            technical = [r for r in results if r["status"] not in TRAINABLE]
            if len(technical) > PROTOCOL["failures"]["round_technical_max"]:
                raise StageStop(f"round {round_id}: {len(technical)} technical failures")
            shard = self.run / "replay" / f"round-{round_id:03d}.jsonl.gz"
            if not shard.exists():
                R.write_shard(shard, results)
            shards = [str(self.run / "replay" / f"round-{k:03d}.jsonl.gz")
                      for k in range(max(1, round_id - PROTOCOL["train"]["replay_rounds"] + 1), round_id + 1)]
            out = self.servers.call(TRAIN_GPU, "train", dict(
                round=round_id, replay=shards, model_directory=str(self.run / "models" / f"round-{round_id:03d}"),
                state=str(self.run / "checkpoints" / f"round-{round_id:03d}.pt")))
            directory = self.run / "rounds" / f"{round_id:03d}"
            atomic(directory / "train.json", dict(out, replay=shards, replay_sha256={s: sha(s) for s in shards},
                                                  games={r["job"]["slot_id"]: r["status"] for r in results}))
            self.servers.broadcast("load", dict(tag="current", directory=str(self.run / "models" / f"round-{round_id:03d}")))
            atomic(directory / "commit.json", dict(round=round_id, at=time.time(), hashes=out["hashes"],
                                                   technical=len(technical)), exclusive=True)
            losses = [m["loss"] for m in out["metrics"]]
            self.event("round", round=round_id, technical=len(technical), loss_first=losses[0], loss_last=losses[-1],
                       statuses={s: sum(1 for r in results if r["status"] == s) for s in {r["status"] for r in results}})
            if round_id % e["interval"] == 0:
                reasons = self.dev_evaluation(round_id)
                if reasons:
                    return self.stop_training(round_id, reasons)
        raise StageStop("training loop ended without a recorded stop reason")

    def stop_training(self, round_id, reasons):
        record = dict(round=round_id, reasons=reasons, history=self.history(), at=time.time())
        atomic(self.run / "train-stop.json", record, exclusive=True)
        self.event("training_stopped", **{k: v for k, v in record.items() if k != "at"})   # event() stamps its own time
        return record

    def selection(self):
        path = self.run / "selection.json"
        if path.exists():
            return read(path)
        history = self.history()
        rounds = [r for r, _ in history][-PROTOCOL["evaluation"]["selection_last"]:]
        tags = [f"r{r:03d}" for r in rounds]
        for r, tag in zip(rounds, tags):
            self.servers.broadcast("load", dict(tag=tag, directory=str(self.run / "models" / f"round-{r:03d}")))
        pairs = [(x, y) for i, x in enumerate(tags) for y in tags[i + 1:]]
        results = self.run_group("rr", S.round_robin(pairs), records=False) if pairs else []
        games = []
        for result in results:
            s = E.score(result, result["job"]["first_side"])
            if s is None:
                raise StageStop("technical failure inside the round-robin selection")
            x, y = result["job"]["pair"]
            games.append((x, y, s))
        selected, strength = E.select(tags, games) if pairs else (tags[0], {tags[0]: 1.0})
        round_id = rounds[tags.index(selected)]
        model = self.run / "models" / f"round-{round_id:03d}"
        record = dict(candidates=rounds, strengths={k: (None if v == float("inf") else v) for k, v in strength.items()},
                      perfect=[k for k, v in strength.items() if v == float("inf")], selected=round_id, games=len(games),
                      hashes={n: sha(model / n) for n in ("adapter.safetensors", "heads.safetensors")})
        for tag in tags:
            self.servers.broadcast("drop", dict(tag=tag))
        atomic(path, record, exclusive=True)
        self.event("selection", selected=round_id, strengths=record["strengths"])
        return record

    def test(self):
        summary_path = self.run / "test.json"
        if summary_path.exists():
            return read(summary_path)
        selection = read(self.run / "selection.json")
        model = self.run / "models" / f"round-{selection['selected']:03d}"
        lock = dict(identity=self.manifest["identity"], selected=selection["selected"], hashes=selection["hashes"],
                    settings=read(self.run / "settings.json"), schedule_sha256=sha(self.run / "schedule.json"),
                    p0=self.manifest["p0"])
        lock_path = self.run / "evaluation-lock.json"
        if lock_path.exists() and read(lock_path) != json.loads(json.dumps(lock)):
            raise StageStop("evaluation lock changed")
        if not lock_path.exists():
            atomic(lock_path, lock, exclusive=True)
        self.servers.broadcast("load", dict(tag="P1", directory=str(model)))
        results = self.run_group("test", S.test(), records=False)
        summary = test_summary(results)
        atomic(summary_path, summary, exclusive=True)
        self.event("test", **{k: summary[k] for k in ("complete", "primary")})
        return summary

    # ---- entry ----
    def execute(self):
        self.manifest = verify(self.run)
        self.teams = team_texts()
        self.statics = read(self.run / "static.json")
        handle = (self.run / "controller.lock").open("a+")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = {sig: signal.signal(sig, self._signal) for sig in (signal.SIGTERM, signal.SIGINT)}
        self.event("start", identity=self.manifest["identity"])
        self.servers = Servers(self.run, self.manifest, self.statics)
        try:
            self.gates()
            self.benchmark()
            self.smoke()
            self.training()
            self.selection()
            summary = self.test()
            atomic(self.run / "collection-complete.json", dict(at=time.time(), complete=summary["complete"],
                                                                peak_rss=self.peak_rss, disk=self.disk()))
            self.event("collection_complete", complete=summary["complete"])
            return summary
        except BaseException as error:
            atomic(self.run / "stops" / f"{time.time_ns()}.json", dict(reason=f"{type(error).__name__}: {error}",
                                                                      at=time.time()), exclusive=True)
            self.event("stopped", reason=f"{type(error).__name__}: {str(error)[:500]}")
            raise
        finally:
            self.servers.stop()
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()

    def _signal(self, *_):
        self.cancelled = True


def test_summary(results):
    """Primary: per seed block, P1 minus P0 mean score against the fixed opponent; block bootstrap 95% interval."""
    t = PROTOCOL["test"]
    blocks = {}
    statuses = {}
    for result in results:
        job = result["job"]
        statuses[result["status"]] = statuses.get(result["status"], 0) + 1
        s = E.score(result, job["model_side"])
        blocks.setdefault(job["condition"], {}).setdefault(job["block"], []).append(s)
    complete = all(s is not None for c in blocks.values() for b in c.values() for s in b) and len(results) == t["games"]
    means = {c: {b: (sum(v) / len(v) if all(x is not None for x in v) else None) for b, v in by.items()} for c, by in blocks.items()}
    overall = {c: (sum(v for v in by.values() if v is not None) / len(by) if all(v is not None for v in by.values()) else None)
               for c, by in means.items()}

    def contrast(a, b, label):
        if not complete:
            return None
        differences = [means[a][k] - means[b][k] for k in sorted(means[a])]
        low, high = E.bootstrap(differences, t["bootstrap"], seed("test-bootstrap", label))
        point = sum(differences) / len(differences)
        return dict(point=point, low=low, high=high, blocks=len(differences))

    primary = contrast("P1", "P0", "P1-P0")
    return dict(complete=complete, statuses=statuses, means=overall, primary=primary,
                success=bool(primary and primary["low"] > 0 and primary["point"] > 0),
                secondary={"P1+S-P1": contrast("P1+S", "P1", "P1+S-P1"), "P0+S-P0": contrast("P0+S", "P0", "P0+S-P0"),
                           "P1+S-P0+S": contrast("P1+S", "P0+S", "P1+S-P0+S")},
                direct=overall.get("P1-vs-P0"))
