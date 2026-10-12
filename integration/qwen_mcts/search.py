"""Matrix search (worker side, no torch): one expand RPC per search node and one batched evaluation per decision."""
from __future__ import annotations

import time

import numpy as np

from .config import PROTOCOL
from .solver import solve
from .storage import pack_ids, showdown_seed

SIDES = ("p1", "p2")


def candidate_texts(frame):
    return {side: [c["text"] for c in frame["candidates"][side]] for side in SIDES}


def readout_record(readout):
    return dict(value=readout.value, decide=list(readout.decide), closes=[list(c) for c in readout.closes])


def root_policy(frame, evaluate, tokens, *, prefix_id, tag):
    ids, readout = tokens.root(frame["dynamic"], candidate_texts(frame))
    values, policies, meta = evaluate(tag, prefix_id, [ids], [readout])
    return dict(rho=[policies[0][0] or [1.0], policies[0][1] or [1.0]], root_value=values[0], meta=meta)


def expand(sims, executor, root, children):
    """Split the children over the search Node processes (deterministic: results are re-keyed)."""
    if len(sims) == 1 or len(children) < 2:
        return sims[0].expand(root, children)["children"], sims[0]
    parts = [children[i::len(sims)] for i in range(len(sims))]
    futures = [executor.submit(sim.expand, root, part) for sim, part in zip(sims, parts) if part]
    results = [f.result() for f in futures]
    merged = sorted((c for r in results for c in r["children"]), key=lambda c: tuple(c["key"]))
    return merged, None


def matrix_search(frame, sims, executor, evaluate, tokens, *, prefix_id, tag, search_seed, config=PROTOCOL["search"]):
    started = time.monotonic()
    A = [c["id"] for c in frame["candidates"]["p1"]] or [None]
    B = [c["id"] for c in frame["candidates"]["p2"]] or [None]
    children = []
    for i, a in enumerate(A):
        for j, b in enumerate(B):
            actions = {side: action for side, action in (("p1", a), ("p2", b)) if action is not None}
            children.append(dict(key=[i, j], actions=actions,
                                 seed=showdown_seed("matrix-child", search_seed, 0, a or "-", b or "-")))
    expanded, _ = expand(sims, executor, frame["root"], children)
    if [c["key"] for c in expanded] != [c["key"] for c in children]:
        raise ValueError("expand lost or reordered children")
    expanded_at = time.monotonic()
    root_ids, readout = tokens.root(frame["dynamic"], candidate_texts(frame))
    rows, readouts, cells = [root_ids], [readout], []
    M = np.zeros((len(A), len(B)))
    terminal = np.zeros((len(A), len(B)), dtype=bool)
    for child in expanded:
        i, j = child["key"]
        if child["ended"]:
            M[i, j] = 1.0 if child["winner"] == "p1" else -1.0 if child["winner"] == "p2" else 0.0
            terminal[i, j] = True
        else:
            rows.append(tokens.child(child["dynamic"]))
            readouts.append(None)
            cells.append((i, j))
    values, policies, meta = evaluate(tag, prefix_id, rows, readouts)
    evaluated_at = time.monotonic()
    for (i, j), value in zip(cells, values[1:]):
        M[i, j] = value
    rho1 = policies[0][0] or [1.0]
    rho2 = policies[0][1] or [1.0]
    pi1, pi2, q, info = solve(M, rho1, rho2, tau=config["tau"], iterations=config["iterations"],
                              tolerance=config["gap_tolerance"])
    if not info["converged"]:
        raise ArithmeticError(f"matrix solver did not converge: gap {info['gap']}")
    return dict(tag=tag, rho=[list(map(float, rho1)), list(map(float, rho2))], pi=[pi1.tolist(), pi2.tolist()],
                matrix=M.tolist(), terminal=terminal.tolist(), q=q, root_value=values[0], info=info,
                row=dict(prefix=prefix_id, ids=pack_ids(root_ids), readout=readout_record(readout)),
                children=len(children), evaluated=len(rows) - 1, meta=meta,
                timing=dict(expand=expanded_at - started, evaluate=evaluated_at - expanded_at,
                            solve=time.monotonic() - evaluated_at))
