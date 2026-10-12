"""One long-lived process per physical GPU: owns that GPU's lock, a Network replica, batched inference passes,
and (train GPU only) the learner's optimizer. Errors are reported, never silently retried."""
from __future__ import annotations

import fcntl
import gzip
import json
import os
from pathlib import Path
import queue
import subprocess
import time
import traceback

from .config import GPUS, PROTOCOL, ROOT


def gpu_facts():
    raw = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid,memory.used,utilization.gpu,memory.total",
                                   "--format=csv,noheader,nounits"], text=True)
    facts = {}
    for line in raw.strip().splitlines():
        index, uuid, used, utilization, total = (x.strip() for x in line.split(","))
        facts[int(index)] = dict(index=int(index), uuid=uuid, memory_used_mib=int(used),
                                 utilization_percent=int(utilization), memory_total_mib=int(total))
    return facts


def acquire(index):
    """Shared lock protocol of .pokechamp-data/locks; refuses a busy or different GPU (no takeover)."""
    if index not in GPUS:
        raise ValueError("only the approved GPUs may be used")
    path = ROOT / ".pokechamp-data/locks" / f"gpu{index}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError(f"GPU{index} lock is held by another run") from None
    fact = gpu_facts()[index]
    limits = PROTOCOL["resources"]
    if (fact["uuid"] != GPUS[index] or fact["memory_used_mib"] > limits["gpu_idle_memory_mib"]
            or fact["utilization_percent"] > limits["gpu_idle_utilization"]):
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
        raise RuntimeError(f"GPU{index} is not idle or its identity changed: {fact}")
    return handle, fact


def load_rows(paths):
    from .storage import unpack_ids
    from .tokens import Readout
    rows = []
    for path in paths:
        with gzip.open(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                r = row["readout"]
                rows.append(dict(id=row["id"], prefix=row["prefix"], ids=unpack_ids(row["ids"]), pi=row["pi"], z=row["z"],
                                 readout=Readout(r["value"], tuple(r["decide"]), tuple(tuple(c) for c in r["closes"]))))
    return rows


def serve(spec, control, results, requests, responses):
    index = spec["index"]
    handle, fact = acquire(index)
    run = Path(spec["run"])
    os.environ.update(CUDA_VISIBLE_DEVICES=fact["uuid"], CUDA_DEVICE_ORDER="PCI_BUS_ID",
                      CUBLAS_WORKSPACE_CONFIG=":4096:8", PYTHONDONTWRITEBYTECODE="1",
                      TORCHINDUCTOR_COMPILE_THREADS="1",   # fla's torch.compile helpers: no 32-process compile pool
                      TRITON_CACHE_DIR=str(run / "cache" / f"triton-gpu{index}"))
    import torch
    if torch.cuda.is_initialized():
        raise RuntimeError("CUDA initialized before GPU ownership")
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction = False
    total = torch.cuda.get_device_properties(0).total_memory
    torch.cuda.set_per_process_memory_fraction(min(1.0, PROTOCOL["resources"]["gpu_reserved_bytes"] / total))
    from .network import Network, TRAIN, deterministic_autotune, kev_branch_hidden
    from . import trainer
    deterministic_autotune()
    net = Network("cuda:0", gradient_checkpointing=spec["train"])
    static_ids, pad_id = spec["static_ids"], spec["pad_id"]
    # Rows gathered per inference round: fixed-shape passes are filled per length bucket, so gathering many
    # concurrent requests (up to 16 passes / 15 ms) lets root and child rows of different decisions share passes.
    cap = 16 * PROTOCOL["serving"]["rows_per_pass"]
    learner = dict(optimizer=None, global_step=0)
    branch_hidden = kev_branch_hidden()
    results.put(("ready", "ok", dict(index=index, fact=fact, pid=os.getpid())))
    parent = os.getppid()
    wait = 0.015
    stats = dict(requests=0, rows=0, passes=0, busy=0.0)

    def command(op, args):
        if op == "load":
            return net.load(args["tag"], args["directory"], static_ids)
        if op == "drop":
            return net.drop(args["tag"])
        if op == "restore_learner":
            hashes = net.load(TRAIN, args["directory"])
            learner["optimizer"] = trainer.optimizer_for(net)
            if args.get("state"):
                state = torch.load(args["state"], map_location="cuda:0", weights_only=False)
                learner["optimizer"].load_state_dict(state["optimizer"])
                learner["global_step"] = state["global_step"]
                trainer.set_rng_state(state["rng"])
            else:
                learner["global_step"] = 0
            return dict(hashes=hashes, global_step=learner["global_step"])
        if op == "train":
            if not spec["train"] or learner["optimizer"] is None:
                raise RuntimeError("training needs the train GPU and a restored learner")
            rows = load_rows(args["replay"])
            out = trainer.train_round(net, learner["optimizer"], rows, round_id=args["round"],
                                      global_step=learner["global_step"], static_ids=static_ids,
                                      branch_hidden=branch_hidden, pad_id=pad_id, steps=args.get("steps"))
            learner["global_step"] = out["global_step"]
            hashes = net.save(TRAIN, args["model_directory"])
            Path(args["state"]).parent.mkdir(parents=True, exist_ok=True)
            torch.save(dict(optimizer=learner["optimizer"].state_dict(), global_step=learner["global_step"],
                            rng=trainer.rng_state()), args["state"])
            return dict(out, hashes=hashes, peak_reserved=torch.cuda.max_memory_reserved())
        if op == "gate":
            from . import gates
            return gates.run_server(args["name"], net, args, static_ids=static_ids, pad_id=pad_id,
                                    branch_hidden=branch_hidden, learner=learner)
        if op == "stats":
            return dict(stats, at=time.monotonic())
        if op == "memory":
            return dict(reserved=torch.cuda.memory_reserved(), peak_reserved=torch.cuda.max_memory_reserved())
        if op == "stop":
            return "stopping"
        raise ValueError(f"unknown command {op}")

    try:
        while True:
            if os.getppid() != parent:
                break
            try:
                cid, op, args = control.get_nowait()
            except queue.Empty:
                cid = None
            if cid is not None:
                try:
                    results.put((cid, "ok", command(op, args)))
                except Exception:
                    results.put((cid, "error", traceback.format_exc()))
                if op == "stop":
                    break
                continue
            try:
                batch = [requests.get(timeout=0.01)]
            except queue.Empty:
                continue
            rows_count, until = len(batch[0][4]), time.monotonic() + wait
            while rows_count < cap:
                remaining = until - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    item = requests.get(timeout=remaining)
                except queue.Empty:
                    break
                batch.append(item)
                rows_count += len(item[4])
            groups = {}
            for item in batch:
                groups.setdefault((item[2], item[3]), []).append(item)
            for (tag, prefix), items in groups.items():
                rows = [row for item in items for row in item[4]]
                readouts = [r for item in items for r in item[5]]
                began = time.monotonic()
                try:
                    values, policies, passes = net.evaluate(tag, prefix, rows, readouts, pad_id=pad_id)
                    stats["requests"] += len(items)
                    stats["rows"] += len(rows)
                    stats["passes"] += passes
                    stats["busy"] += time.monotonic() - began
                except Exception:
                    message = traceback.format_exc()
                    for worker, seq, *_ in items:
                        responses[worker].put((seq, "error", message))
                    continue
                offset = 0
                for worker, seq, _, _, item_rows, _ in items:
                    n = len(item_rows)
                    responses[worker].put((seq, "ok", values[offset:offset + n], policies[offset:offset + n],
                                           dict(gpu=index, passes=passes, group_rows=len(rows))))
                    offset += n
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
