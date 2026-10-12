"""GPU gates G0-G8 (EX-080). Server-side checks run inside a GPU server; the controller builds inputs from real
public states, compares outputs across calls/GPUs and records gates.json. A failed gate is never relaxed."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import random

from .config import ASSIGNMENTS, PROTOCOL
from .storage import pack_ids, seed, showdown_seed, unpack_ids

TOL = PROTOCOL["gates"]


def _tensor_hash(tensors):
    import torch
    h = hashlib.sha256()
    for tensor in tensors:
        h.update(tensor.detach().float().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def _rows(args):
    from .tokens import Readout
    groups = {}
    for row in args["rows"]:
        r = row["readout"]
        readout = None if r is None else Readout(r["value"], tuple(r["decide"]), tuple(tuple(c) for c in r["closes"]))
        groups.setdefault(row["prefix"], []).append((unpack_ids(row["ids"]), readout))
    return groups


def _outputs(net, tag, groups, *, pad_id, hidden=False, buckets=None):
    out = {}
    for prefix, items in sorted(groups.items()):
        rows, readouts = [i for i, _ in items], [r for _, r in items]
        result = net.evaluate(tag, prefix, rows, readouts, pad_id=pad_id, buckets=buckets, with_hidden=hidden)
        out[prefix] = dict(values=result[0], policies=result[1])
        if hidden:
            out[prefix]["hidden"] = [h.numpy().tolist() for h in result[3]]
    return out


def _policy_gap(a, b):
    import torch
    gaps = [0.0]
    for x, y in zip(a, b):
        if x is None:
            continue
        for sx, sy in zip(x, y):
            sy = sy.tolist() if torch.is_tensor(sy) else sy
            gaps += [abs(u - v) for u, v in zip(sx, sy)]
    return max(gaps)


def _paths(net, tag, groups, *, static_ids, pad_id, branch_hidden):
    """Cache path vs the cache-free reference row vs Kev branch_hidden, and root VALUE vs the same state's
    value-only row (the root row's prefix up to its VALUE marker)."""
    import torch
    report = {}
    for prefix, items in sorted(groups.items()):
        rows, readouts = [i for i, _ in items], [r for _, r in items]
        cache_v, cache_p, _ = net.evaluate(tag, prefix, rows, readouts, pad_id=pad_id)
        full_v, full_p = net.full_rows(tag, static_ids[prefix], rows, readouts, pad_id=pad_id)
        with torch.no_grad():
            branch_v, branch_p = net.branch_rows(tag, static_ids, {prefix: items}, pad_id=pad_id,
                                                 branch_hidden=branch_hidden)[prefix]
        roots = [(i, r) for i, r in zip(rows, readouts) if r is not None]
        only, _, _ = net.evaluate(tag, prefix, [i[:r.value + 1] for i, r in roots], [None] * len(roots), pad_id=pad_id)
        root_values = [cache_v[k] for k, r in enumerate(readouts) if r is not None]
        report[prefix] = dict(
            value_cache_full=max(abs(a - b) for a, b in zip(cache_v, full_v.tolist())),
            value_cache_branch=max(abs(a - b) for a, b in zip(cache_v, branch_v.tolist())),
            policy_cache_full=_policy_gap(cache_p, full_p), policy_cache_branch=_policy_gap(cache_p, branch_p),
            value_root_vs_value_only=max([0.0] + [abs(a - b) for a, b in zip(root_values, only)]))
    return report


class exact_kernels:
    """Temporarily route Qwen3.5's Gated DeltaNet rule and short convolution through transformers' PyTorch reference
    code (fp32-exact; fla's Triton kernels round fp32 dots like TF32). Used only by the fp32 path-equivalence gate."""
    NAMES = ("torch_chunk_gated_delta_rule", "torch_recurrent_gated_delta_rule", "causal_conv1d_fn", "causal_conv1d_update")

    def __enter__(self):
        import inspect
        from transformers.models.qwen3_5 import modeling_qwen3_5 as Q
        self.module, self.saved = Q, {}
        for name in self.NAMES:
            if not hasattr(Q, name):
                continue
            self.saved[name] = getattr(Q, name)
            f = inspect.unwrap(self.saved[name])
            params = inspect.signature(f).parameters
            setattr(Q, name, lambda *a, f=f, params=params, **kw: f(*a, **{k: v for k, v in kw.items() if k in params}))
        return self

    def __exit__(self, *_):
        for name, original in self.saved.items():
            setattr(self.module, name, original)


def run_server(name, net, args, *, static_ids, pad_id, branch_hidden, learner):
    import torch
    from .network import TRAIN, cache_fingerprint
    from . import trainer
    if name == "env":
        import os
        return dict(deterministic=torch.are_deterministic_algorithms_enabled(),
                    tf32=[torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32],
                    bf16_reduced=torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction,
                    cublas=os.environ.get("CUBLAS_WORKSPACE_CONFIG"), triton=os.environ.get("TRITON_CACHE_DIR"),
                    device=torch.cuda.get_device_name(0))
    if name == "load":
        return net.load(args["tag"], args["directory"], static_ids)
    if name == "probe_create":
        net.load("probe", args["p0"], static_ids)
        generator = torch.Generator().manual_seed(seed("gate-probe"))
        with torch.no_grad():
            for parameter_name, parameter in net.lm.named_parameters():
                if "lora_B" in parameter_name and ".probe." in parameter_name:
                    parameter.copy_(torch.randn(parameter.shape, generator=generator) * 1e-3)
            for parameter in net.heads["probe"].parameters():
                parameter.copy_(torch.randn(parameter.shape, generator=generator) * 0.05)
        hashes = net.save("probe", args["directory"])
        net.load("probe", args["directory"], static_ids)
        return hashes
    if name == "outputs":
        return _outputs(net, args["tag"], _rows(args), pad_id=pad_id, hidden=args.get("hidden", False))
    if name == "invariance":
        # G3 (D-128): every row alone (its pass filled with copies of itself) vs mixed with the others vs reversed order
        groups = _rows(args)
        mixed = _outputs(net, args["tag"], groups, pad_id=pad_id, hidden=True)
        reverse = _outputs(net, args["tag"], {k: list(reversed(v)) for k, v in groups.items()}, pad_id=pad_id, hidden=True)
        alone = {prefix: dict(values=[], policies=[], hidden=[]) for prefix in groups}
        for prefix, items in groups.items():
            for item in items:
                one = _outputs(net, args["tag"], {prefix: [item]}, pad_id=pad_id, hidden=True)[prefix]
                for key in ("values", "policies", "hidden"):
                    alone[prefix][key].append(one[key][0])
        reverse = {k: {key: list(reversed(v[key])) for key in v} for k, v in reverse.items()}
        equal = mixed == alone == reverse
        return dict(rows=sum(len(v) for v in groups.values()), bitwise_equal=equal,
                    max_value_gap=max(abs(a - b) for p in groups for a, b in zip(mixed[p]["values"], alone[p]["values"])))
    if name == "paths":
        return _paths(net, args["tag"], _rows(args), static_ids=static_ids, pad_id=pad_id, branch_hidden=branch_hidden)
    if name == "paths_fp32":
        # G4 (D-128): the same comparison in an fp32 copy of the model on this GPU, judged with the registered tolerance.
        from .network import Network
        with exact_kernels():
            exact = Network("cuda:0", dtype=torch.float32)
            try:
                exact.load(args["tag"], args["directory"], static_ids)
                return _paths(exact, args["tag"], _rows(args), static_ids=static_ids, pad_id=pad_id,
                              branch_hidden=branch_hidden)
            finally:
                del exact
                torch.cuda.empty_cache()
    if name == "cache":
        before = {key: cache_fingerprint(cache) for key, (_, cache) in net.static.items() if key[0] == args["tag"]}
        groups = _rows(args)
        for _ in range(args["passes"]):
            _outputs(net, args["tag"], groups, pad_id=pad_id)
        after = {key: cache_fingerprint(cache) for key, (_, cache) in net.static.items() if key[0] == args["tag"]}
        return dict(unchanged=before == after, caches=len(before))
    if name == "train":
        return _gate_train(net, args, static_ids=static_ids, pad_id=pad_id, branch_hidden=branch_hidden)
    if name == "memory":
        torch.cuda.reset_peak_memory_stats()
        groups = _rows(args)
        longest = max((row for items in groups.values() for row in items), key=lambda r: len(r[0]))
        prefix = next(p for p, items in groups.items() if longest in items)
        largest = PROTOCOL["serving"]["buckets"][-1]
        rows_per_pass = PROTOCOL["serving"]["rows_per_pass"]
        _outputs(net, args["tag"], {prefix: [longest] * rows_per_pass}, pad_id=pad_id, buckets=[largest])
        evaluation_peak = torch.cuda.max_memory_reserved()
        training_peak = None
        if args.get("train"):
            from .server import load_rows
            rows = load_rows([args["replay"]])
            longest_rows = sorted(rows, key=lambda r: -len(r["ids"]))[:1] * PROTOCOL["train"]["batch"]
            net.load(TRAIN, args["p0"])
            optimizer = trainer.optimizer_for(net)
            trainer.train_round(net, optimizer, longest_rows, round_id="gate-memory", global_step=0,
                                static_ids=static_ids, branch_hidden=branch_hidden, pad_id=pad_id, steps=1)
            training_peak = torch.cuda.max_memory_reserved()
        limit = PROTOCOL["resources"]["gpu_reserved_bytes"]
        return dict(evaluation_peak=evaluation_peak, training_peak=training_peak, bucket=largest,
                    passed=max(evaluation_peak, training_peak or 0) <= limit)
    raise ValueError(f"unknown gate {name}")


def _gate_train(net, args, *, static_ids, pad_id, branch_hidden):
    import torch
    from .network import TRAIN
    from . import trainer
    from .server import load_rows
    rows = load_rows([args["replay"]])
    base = [p for n, p in net.lm.named_parameters() if "lora_" not in n]

    def state_hash(optimizer):
        params = net.adapter_parameters(TRAIN) + list(net.heads[TRAIN].parameters())
        moments = [s[k] for s in optimizer.state.values() for k in ("exp_avg", "exp_avg_sq") if k in s]
        return _tensor_hash(params), _tensor_hash(moments)

    def fresh():
        net.load(TRAIN, args["p0"])
        torch.manual_seed(seed("gate-train"))
        return trainer.optimizer_for(net)

    base_before = _tensor_hash(base)
    runs = []
    for _ in range(2):
        optimizer = fresh()
        a = trainer.train_round(net, optimizer, rows, round_id="gate-1", global_step=0, static_ids=static_ids,
                                branch_hidden=branch_hidden, pad_id=pad_id, steps=3)
        b = trainer.train_round(net, optimizer, rows, round_id="gate-2", global_step=a["global_step"], static_ids=static_ids,
                                branch_hidden=branch_hidden, pad_id=pad_id, steps=3)
        runs.append(dict(hashes=state_hash(optimizer), losses=[m["loss"] for m in a["metrics"] + b["metrics"]]))
    optimizer = fresh()
    a = trainer.train_round(net, optimizer, rows, round_id="gate-1", global_step=0, static_ids=static_ids,
                            branch_hidden=branch_hidden, pad_id=pad_id, steps=3)
    directory = Path(args["directory"])
    net.save(TRAIN, directory)
    torch.save(dict(optimizer=optimizer.state_dict(), global_step=a["global_step"], rng=trainer.rng_state()),
               directory / "state.pt")
    net.load(TRAIN, directory)
    optimizer = trainer.optimizer_for(net)
    state = torch.load(directory / "state.pt", map_location="cuda:0", weights_only=False)
    optimizer.load_state_dict(state["optimizer"])
    trainer.set_rng_state(state["rng"])
    b = trainer.train_round(net, optimizer, rows, round_id="gate-2", global_step=state["global_step"], static_ids=static_ids,
                            branch_hidden=branch_hidden, pad_id=pad_id, steps=3)
    resumed = dict(hashes=state_hash(optimizer), losses=[m["loss"] for m in a["metrics"] + b["metrics"]])
    base_after = _tensor_hash(base)
    finite = all(math.isfinite(x) for run in runs + [resumed] for x in run["losses"])
    return dict(repeat_equal=runs[0] == runs[1], resume_equal=runs[0] == resumed, base_unchanged=base_before == base_after,
                finite=finite, losses=runs[0]["losses"],
                passed=runs[0] == runs[1] == resumed and base_before == base_after and finite)


# ---- controller side: inputs from real public states (CPU only) ----

def gate_inputs(teams, tokens, *, frames_per_assignment=8):
    """Public decision states from uniform games (gate namespace) plus all their matrix-search children."""
    from .game import draw
    from .sim import Simulator
    rows, targets = [], []
    for assignment, sides in ASSIGNMENTS.items():
        with Simulator("real") as real, Simulator("search") as search:
            frame = real.init({side: teams[label] for side, label in sides.items()}, showdown_seed("gate-game", assignment))
            rng = random.Random(seed("gate-actions", assignment))
            collected, decision = 0, 0
            while not frame["ended"] and collected < frames_per_assignment:
                candidates = frame["candidates"]
                if decision % 3 == 0 and (len(candidates["p1"]) > 1 or len(candidates["p2"]) > 1):
                    root_ids, readout = tokens.root(frame["dynamic"], {s: [c["text"] for c in candidates[s]] for s in ("p1", "p2")})
                    rows.append(dict(prefix=assignment, ids=pack_ids(root_ids), readout=dict(
                        value=readout.value, decide=list(readout.decide), closes=[list(c) for c in readout.closes])))
                    A = [c["id"] for c in candidates["p1"]] or [None]
                    B = [c["id"] for c in candidates["p2"]] or [None]
                    children = [dict(key=[i, j], actions={s: x for s, x in (("p1", a), ("p2", b)) if x is not None},
                                     seed=showdown_seed("gate-child", assignment, decision, i, j))
                                for i, a in enumerate(A) for j, b in enumerate(B)]
                    for child in search.expand(frame["root"], children)["children"]:
                        if not child["ended"]:
                            rows.append(dict(prefix=assignment, ids=pack_ids(tokens.child(child["dynamic"])), readout=None))
                    k = [len(candidates["p1"]), len(candidates["p2"])]
                    pi = [[x / sum(w) for x in w] if n >= 2 else None
                          for n, w in ((n, [rng.random() + 0.1 for _ in range(n)]) for n in k)]
                    targets.append(dict(id=f"gate:{assignment}:{decision}", prefix=assignment, ids=pack_ids(root_ids),
                                        readout=dict(value=readout.value, decide=list(readout.decide),
                                                     closes=[list(c) for c in readout.closes]),
                                        pi=pi, z=rng.choice([-1, 1])))
                    collected += 1
                actions = {s: candidates[s][draw([1.0] * len(candidates[s]), rng)]["id"] for s in ("p1", "p2") if candidates[s]}
                frame = real.advance(actions)
                decision += 1
    return rows, targets


def compare(a, b):
    """Max absolute differences between two `outputs` results (same rows, same order)."""
    value, policy, hidden = 0.0, 0.0, 0.0
    for prefix in a:
        va, vb = a[prefix]["values"], b[prefix]["values"]
        value = max([value] + [abs(x - y) for x, y in zip(va, vb)])
        for pa, pb in zip(a[prefix]["policies"], b[prefix]["policies"]):
            if pa is None:
                continue
            for sa, sb in zip(pa, pb):
                policy = max([policy] + [abs(x - y) for x, y in zip(sa, sb)])
        if "hidden" in a[prefix] and "hidden" in b[prefix]:
            for ha, hb in zip(a[prefix]["hidden"], b[prefix]["hidden"]):
                num = math.sqrt(sum((x - y) ** 2 for x, y in zip(ha, hb)))
                den = math.sqrt(sum(x * x for x in ha)) or 1.0
                hidden = max(hidden, num / den)
    return dict(value=value, policy=policy, hidden_relative_l2=hidden)
