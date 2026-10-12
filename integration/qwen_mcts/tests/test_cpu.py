"""EX-080 CPU checks (no GPU). Run: /ref/kev/.venv/bin/python -m pytest integration/qwen_mcts/tests -q"""
import gzip
import inspect
import json
import os
import random
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from integration.qwen_mcts import evaluation as E
from integration.qwen_mcts import replay as R
from integration.qwen_mcts import schedule as S
from integration.qwen_mcts.config import ASSIGNMENTS, PROTOCOL, ROOT
from integration.qwen_mcts.solver import gap, solve
from integration.qwen_mcts.storage import digest, pack_ids, unpack_ids

TOL = dict(tau=0.2, iterations=3000, tolerance=1e-9)


# ---------------- solver ----------------

def test_matching_pennies_is_uniform():
    p1, p2, v, info = solve([[1, -1], [-1, 1]], [.5, .5], [.5, .5], **TOL)
    assert np.allclose(p1, .5) and np.allclose(p2, .5) and abs(v) < 1e-12 and info["converged"]


def test_zero_matrix_returns_prior_and_large_tau_returns_prior():
    p1, p2, *_ = solve(np.zeros((3, 4)), [.2, .3, .5], [.1, .2, .3, .4], **TOL)
    assert np.allclose(p1, [.2, .3, .5]) and np.allclose(p2, [.1, .2, .3, .4])
    q1, q2, *_ = solve(np.array([[1., -.5], [-.5, .5]]), [.8, .2], [.3, .7], tau=1e6, iterations=3000, tolerance=1e-12)
    assert np.allclose(q1, [.8, .2], atol=1e-5) and np.allclose(q2, [.3, .7], atol=1e-5)


def test_small_tau_approaches_nash():
    M = np.array([[1., -.5], [-.5, .5]])          # Nash: both players play the first action with probability 0.4
    distances = []
    for tau in (0.2, 0.1, 0.05, 0.02):
        p1, p2, _, info = solve(M, [.8, .2], [.3, .7], tau=tau, iterations=200000, tolerance=1e-12)
        assert info["converged"]
        distances.append(abs(p1[0] - .4) + abs(p2[0] - .4))
    assert all(a > b for a, b in zip(distances, distances[1:]))


def test_dominance_closed_form_and_one_sided():
    M = np.array([[0.5, 0.5], [-0.5, -0.5]])        # p2 indifferent; p1's regularized response is closed form
    rho1, rho2 = np.array([.5, .5]), np.array([.6, .4])
    p1, p2, *_ = solve(M, rho1, rho2, tau=0.2, iterations=100000, tolerance=1e-14)
    expected = rho1 * np.exp(M @ p2 / 0.2)
    assert np.allclose(p1, expected / expected.sum(), atol=1e-8) and np.allclose(p2, rho2, atol=1e-8)
    p1, p2, v, info = solve([[0.3, -0.2, 0.1]], [1.0], [.2, .5, .3], **TOL)
    expected = np.array([.2, .5, .3]) * np.exp(-np.array([0.3, -0.2, 0.1]) / 0.2)
    assert np.allclose(p2, expected / expected.sum()) and info["gap"] < 1e-12


def test_antisymmetry_permutation_and_gap():
    rng = np.random.default_rng(0)
    M = rng.uniform(-1, 1, (4, 5)); r1 = rng.dirichlet(np.ones(4)); r2 = rng.dirichlet(np.ones(5))
    a1, a2, va, info = solve(M, r1, r2, **TOL)
    b1, b2, vb, _ = solve(-M.T, r2, r1, **TOL)
    assert np.abs(a1 - b2).max() < 1e-9 and np.abs(a2 - b1).max() < 1e-9 and abs(va + vb) < 1e-9
    perm = rng.permutation(4)
    c1, c2, *_ = solve(M[perm], r1[perm], r2, **TOL)
    assert np.abs(c1 - a1[perm]).max() < 1e-9 and np.abs(c2 - a2).max() < 1e-9
    assert -1e-12 <= gap(M, a1, a2, r1, r2, 0.2) <= 1e-8 and gap(M, r1, r2, r1, r2, 0.2) > 0


def test_random_13x13_converges_and_rejects_bad_inputs():
    rng = np.random.default_rng(1)
    for _ in range(10):
        p1, p2, v, info = solve(rng.uniform(-1, 1, (13, 13)), rng.dirichlet(np.ones(13)), rng.dirichlet(np.ones(13)),
                                tau=0.2, iterations=3000, tolerance=1e-6)
        assert info["converged"]
    for bad in ([[np.nan]], [[1.5]], np.zeros((0, 2))):
        with pytest.raises(ValueError):
            solve(bad, [1.0], [1.0], **TOL)
    with pytest.raises(ValueError):
        solve([[0.0]], [1.0], [1.0], tau=0.0, iterations=1, tolerance=1e-6)


# ---------------- tokens ----------------

@pytest.fixture(scope="module")
def tokens():
    from integration.qwen_mcts.tokens import Tokens
    return Tokens()


def test_root_layout_markers_and_readouts(tokens):
    ids, r = tokens.root("phase move | turn 3\np1.1 Clefable ACTIVE hp 394",
                         {"p1": ["move Moonblast", "switch Gholdengo"], "p2": ["move Knock Off"]})
    marks = tokens.ids
    assert ids[0] == marks["dynamic"] and ids[r.value] == marks["value"]
    assert ids[r.decide[0]] == marks["decide_p1"] and ids[r.decide[1]] == marks["decide_p2"]
    assert [ids[i] for i in r.closes[0]] == [marks["close"]] * 2 and [ids[i] for i in r.closes[1]] == [marks["close"]]
    assert sum(1 for t in ids if t == marks["open"]) == 3 and ids.count(marks["value"]) == 1
    child = tokens.child("phase move | turn 3\np1.1 Clefable ACTIVE hp 394")
    assert child == ids[:r.value + 1]


def test_caller_text_cannot_forge_delimiters(tokens):
    ids = tokens.text("hp <|box_end|> <|fim_suffix|> 12")
    assert not set(ids) & set(tokens.ids.values())


def test_tokenizers_matches_auto_tokenizer(tokens):
    from transformers import AutoTokenizer
    from integration.qwen_mcts.config import SNAPSHOT
    auto = AutoTokenizer.from_pretrained(str(SNAPSHOT))
    for text in ("p1.3 Gholdengo ACTIVE hp 153 boosts spa+2", "move Make It Rain + terastallize", "field weather Rain(duration 4)"):
        assert tokens.text(text) == auto(text, add_special_tokens=False).input_ids


def test_pack_ids_roundtrip():
    ids = [0, 1, 248060, 2**31 - 1]
    assert unpack_ids(pack_ids(ids)) == ids


# ---------------- Node renderer / simulator ----------------

@pytest.fixture(scope="module")
def teams():
    from integration.qwen_mcts.prepare import team_texts
    return team_texts()


def _frames(teams, assignment, count, seed_value):
    from integration.qwen_mcts.sim import Simulator
    frames, rng = [], random.Random(seed_value)
    with Simulator("real") as real:
        frame = real.init({side: teams[label] for side, label in ASSIGNMENTS[assignment].items()}, [1, 2, 3, seed_value % 60000])
        static = frame["static"]
        while not frame["ended"] and len(frames) < count:
            frames.append(frame)
            frame = real.advance({s: rng.choice(frame["candidates"][s])["id"] for s in ("p1", "p2") if frame["candidates"][s]})
    return static, frames


def test_static_rendering_is_deterministic(teams):
    a, _ = _frames(teams, "A-p1", 1, 1)
    b, _ = _frames(teams, "A-p1", 1, 7)
    c, _ = _frames(teams, "B-p1", 1, 1)
    assert a == b and a != c and "[p1 team]" in a and "[p2 team]" in a


def test_describe_and_expand_are_deterministic_and_order_free(teams):
    from integration.qwen_mcts.sim import Simulator
    _, frames = _frames(teams, "A-p1", 12, 3)
    frame = frames[-1]
    A = [c["id"] for c in frame["candidates"]["p1"]] or [None]
    B = [c["id"] for c in frame["candidates"]["p2"]] or [None]
    children = [dict(key=[i, j], actions={s: x for s, x in (("p1", a), ("p2", b)) if x is not None}, seed=[1, 2, i, j])
                for i, a in enumerate(A) for j, b in enumerate(B)]
    with Simulator("search") as one, Simulator("search") as two:
        described = one.describe(frame["root"])
        assert described["dynamic"] == frame["dynamic"] and described["candidates"] == frame["candidates"]
        first = one.expand(frame["root"], children)
        again = two.expand(frame["root"], children)
        reverse = two.expand(frame["root"], list(reversed(children)))
    assert first["children"] == again["children"]
    assert sorted(reverse["children"], key=lambda c: c["key"]) == first["children"]
    assert first["root_dynamic"] == frame["dynamic"]


def test_roles_and_illegal_actions_are_refused(teams):
    from integration.qwen_mcts.sim import Simulator
    from integration.qwen_mcts.vendor.transport import SimulatorError
    _, frames = _frames(teams, "A-p1", 2, 5)
    with Simulator("search") as search:
        with pytest.raises(SimulatorError):
            search.init({"p1": teams["A"], "p2": teams["B"]}, [1, 1, 1, 1])
    with Simulator("search") as search:
        with pytest.raises(SimulatorError):
            search.expand(frames[-1]["root"], [dict(key=[0, 0], actions={"p1": "move:9:none:normal"}, seed=[1, 1, 1, 1])])
    with Simulator("real") as real:
        with pytest.raises(SimulatorError):
            real.expand(frames[-1]["root"], [])


# ---------------- schedules ----------------

def test_schedule_sizes_and_namespaces():
    e = PROTOCOL["evaluation"]
    assert len(S.self_play(1)) == 32 and len(S.dev(4, "P0")) == e["previous_games"] == 128
    assert len(S.p0_reference(4)) == e["p0_games"] == 64 and len(S.round_robin([("a", "b")])) == 64
    assert len(S.test()) == PROTOCOL["test"]["games"] == 640 and len(S.smoke()) == PROTOCOL["smoke_games"]
    dev4, dev8 = S.dev(4, "P0"), S.dev(8, "r004")
    assert [j["game_seed"] for j in dev4] == [j["game_seed"] for j in dev8]          # common dev seeds
    test = S.test()
    by_key = {}
    for j in test:
        by_key.setdefault(tuple(j["seed_key"]), set()).add(j["game_seed"][0])
    assert all(len(v) == 1 for v in by_key.values()) and len(by_key) == 128          # CRN across conditions
    for j in S.dev(4, "P0") + test:
        assert j["players"][j.get("first_side", j.get("model_side"))]["mode"] in ("policy", "search")
    groups = dict(train=[j for r in range(1, 101) for j in S.self_play(r)], dev=dev4, p0=S.p0_reference(4),
                  rr=S.round_robin([("a", "b")]), test=test, smoke=S.smoke(), bench=S.bench("x", 50))
    seeds = {k: {tuple(j["game_seed"]) for j in v} for k, v in groups.items()}
    names = list(seeds)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not seeds[a] & seeds[b], (a, b)


def test_seeds_disjoint_from_previous_fixed_matchup_experiments():
    ours = {tuple(j["game_seed"]) for v in S.frozen().values() for j in (v if isinstance(v, list) else [x for l in v.values() for x in l])}
    previous = set()
    for path in (ROOT / ".pokechamp-data/experiments").glob("ex07[6-9]*/schedule.json"):
        def walk(value):
            if isinstance(value, dict):
                if "simulator_seed" in value:
                    previous.add(tuple(value["simulator_seed"]))
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)
        walk(json.loads(path.read_text()))
    assert previous and not ours & previous


# ---------------- evaluation / replay ----------------

def test_stop_rule():
    assert E.stop_reasons([(4, .5), (8, .5)]) == []
    assert E.stop_reasons([(4, .5), (8, .5), (12, .5)]) == ["slowdown"]
    assert E.stop_reasons([(4, .9), (8, .5), (12, .5)]) == []
    assert E.stop_reasons([(4, .9), (8, .5), (12, .5), (16, .54)]) == ["slowdown"]
    assert E.stop_reasons([(96, .9), (100, .9)]) == ["round_cap"]


def test_bradley_terry_selection():
    rng = random.Random(0)
    truth = {"r004": 0.5, "r008": 1.0, "r012": 2.0}
    games = []
    for _ in range(400):
        x, y = rng.sample(list(truth), 2)
        games.append((x, y, 1.0 if rng.random() < truth[x] / (truth[x] + truth[y]) else 0.0))
    best, strength = E.select(list(truth), games)
    assert best == "r012" and strength["r012"] > strength["r008"] > strength["r004"]
    best, _ = E.select(["a", "b"], [("a", "b", 0.5), ("b", "a", 0.5)])
    assert best == "a"                                                   # tie -> earlier
    best, strength = E.select(["a", "b", "c"], [("b", "a", 1.0), ("b", "c", 1.0), ("a", "c", 0.5)])
    assert best == "b" and strength["b"] == float("inf")


def test_scores_and_replay_rows():
    job = dict(slot_id="s", first_side="p2", model_side="p1")
    assert E.score(dict(job=job, status="completed", winner="p2"), "p2") == 1.0
    assert E.score(dict(job=job, status="censored", winner=None), "p1") == 0.5
    assert E.score(dict(job=job, status="invalid", winner=None), "p1") is None
    record = dict(decision=0, candidates={"p1": ["a", "b"], "p2": ["c"]},
                  search={"current": dict(pi=[[.3, .7], [1.0]], row=dict(prefix="A-p1", ids=pack_ids([1, 2]),
                                                                     readout=dict(value=1, decide=[2, 3], closes=[[2], []])))})
    rows = R.rows(dict(job=job, status="completed", winner="p1", records=[record]))
    assert rows[0]["z"] == 1 and rows[0]["pi"] == [[.3, .7], None]
    assert R.rows(dict(job=job, status="censored", winner=None, records=[record]))[0]["z"] is None
    assert R.rows(dict(job=job, status="invalid", winner=None, records=[record])) == []


# ---------------- tiny Qwen3.5 network (exact kernels) ----------------

def _exact_kernels():
    from transformers.models.qwen3_5 import modeling_qwen3_5 as Q
    for name in ("torch_chunk_gated_delta_rule", "torch_recurrent_gated_delta_rule", "causal_conv1d_fn"):
        f = inspect.unwrap(getattr(Q, name)); params = inspect.signature(f).parameters
        setattr(Q, name, lambda *a, f=f, params=params, **kw: f(*a, **{k: v for k, v in kw.items() if k in params}))


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    import torch
    from transformers import Qwen3_5ForCausalLM, Qwen3_5TextConfig
    _exact_kernels()
    root = tmp_path_factory.mktemp("tiny")
    config = Qwen3_5TextConfig(vocab_size=300, hidden_size=32, intermediate_size=64, num_hidden_layers=4, num_attention_heads=2,
                               num_key_value_heads=1, head_dim=16, linear_num_value_heads=2, linear_num_key_heads=1,
                               linear_key_head_dim=8, linear_value_head_dim=8, pad_token_id=1,
                               layer_types=["linear_attention"] * 3 + ["full_attention"])
    torch.manual_seed(0)
    Qwen3_5ForCausalLM(config).save_pretrained(root)
    return root


def _net(tiny):
    import torch
    from integration.qwen_mcts.network import Network
    return Network("cpu", snapshot=tiny, dtype=torch.float32, attn="eager")


def test_p0_outputs_are_exactly_uniform_and_zero(tiny):
    from integration.qwen_mcts.network import TRAIN
    from integration.qwen_mcts.tokens import Readout
    net = _net(tiny)
    net.static = {(TRAIN, "A-p1"): net._static(TRAIN, [5, 6, 7, 8])}
    values, policies, _ = net.evaluate(TRAIN, "A-p1", [[9, 10, 11, 12, 13, 14, 15], [20, 21]],
                                       [Readout(1, (4, 6), ((2, 3), (5,))), None], pad_id=1)
    assert values == [0.0, 0.0] and policies[0] == [[0.5, 0.5], [1.0]]


def test_cache_full_branch_paths_agree(tiny):
    import torch
    from integration.qwen_mcts.network import TRAIN, cache_fingerprint, kev_branch_hidden
    from integration.qwen_mcts.tokens import Readout
    net = _net(tiny)
    torch.manual_seed(1)
    for p in net.adapter_parameters(TRAIN) + list(net.heads[TRAIN].parameters()):
        p.data.normal_(0, 0.05)
    static = {"A-p1": [5, 6, 7, 8, 9, 10, 11, 12], "B-p1": [13, 14, 15, 16, 17, 18, 19]}
    net.static = {(TRAIN, k): net._static(TRAIN, v) for k, v in static.items()}
    before = cache_fingerprint(net.static[TRAIN, "A-p1"][1])
    rows = [[20, 21, 22, 23], [24, 25, 26, 27, 28, 29, 30, 31, 32], [40, 41, 42, 43, 44, 45], [50, 51]]
    readouts = [None, Readout(2, (5, 8), ((3, 4), (6, 7))), None, None]
    v1, p1, _, h1 = net.evaluate(TRAIN, "A-p1", rows, readouts, pad_id=1, rows_per_pass=4, with_hidden=True)
    alone = [net.evaluate(TRAIN, "A-p1", [r], [o], pad_id=1, rows_per_pass=4, with_hidden=True) for r, o in zip(rows, readouts)]
    v2 = [a[0][0] for a in alone]
    assert v1 == v2 and all(torch.equal(h, a[3][0]) for h, a in zip(h1, alone))          # fixed shapes: bitwise
    assert p1[1] == alone[1][1][0]
    vf, pf = net.full_rows(TRAIN, static["A-p1"], rows, readouts, pad_id=1)
    with torch.no_grad():
        vb, pb = net.branch_rows(TRAIN, static, {"A-p1": list(zip(rows, readouts))}, pad_id=1,
                                 branch_hidden=kev_branch_hidden())["A-p1"]
    assert max(abs(a - b) for a, b in zip(v1, vf.tolist())) < 1e-5
    assert max(abs(a - b) for a, b in zip(v1, vb.tolist())) < 1e-5
    assert max(abs(a - b) for s, f in zip(p1[1], pf[1]) for a, b in zip(s, f.tolist())) < 1e-5
    assert cache_fingerprint(net.static[TRAIN, "A-p1"][1]) == before


def test_fixed_shape_pass_plan():
    from integration.qwen_mcts.network import bucket, plan_passes
    buckets = PROTOCOL["serving"]["buckets"]
    assert bucket(1, buckets) == 128 and bucket(129, buckets) == 192 and bucket(896, buckets) == 896
    with pytest.raises(ValueError):
        bucket(897, buckets)
    passes = plan_passes([100, 300, 130, 90, 500, 310], 2, buckets)
    assert passes == [(128, [0, 3]), (192, [2]), (320, [1, 5]), (512, [4])]
    assert all(len(indices) <= 2 for _, indices in plan_passes([50] * 7, 2, buckets))


def test_save_load_and_training_are_reproducible(tiny, tmp_path):
    import torch
    from integration.qwen_mcts import trainer
    from integration.qwen_mcts.network import TRAIN, kev_branch_hidden
    from integration.qwen_mcts.tokens import Readout
    static = {"A-p1": [5, 6, 7, 8, 9], "B-p1": [10, 11, 12, 13]}
    rows = [dict(id=str(i), prefix=["A-p1", "B-p1"][i % 2], ids=[20 + i, 21, 22, 23, 24, 25, 26],
                 readout=Readout(1, (4, 6), ((2, 3), (5,))), pi=[[0.3, 0.7], None], z=[1, -1, None][i % 3]) for i in range(12)]

    def train(net):
        optimizer = trainer.optimizer_for(net)
        out = trainer.train_round(net, optimizer, rows, round_id=1, global_step=0, static_ids=static,
                                  branch_hidden=kev_branch_hidden(), pad_id=1, steps=3)
        return [m["loss"] for m in out["metrics"]], [p.detach().clone() for p in net.adapter_parameters(TRAIN)]

    first = _net(tiny)
    first.save(TRAIN, tmp_path / "p0")
    losses_a, params_a = train(first)
    second = _net(tiny)
    second.load(TRAIN, tmp_path / "p0")
    losses_b, params_b = train(second)
    assert losses_a == losses_b and all(torch.equal(a, b) for a, b in zip(params_a, params_b))
    assert all(np.isfinite(losses_a)) and losses_a[0] > 0


# ---------------- full games on CPU (P0 shortcut, no GPU) ----------------

def _evaluator():
    from integration.qwen_mcts.pool import Evaluator
    return Evaluator(0, [], None, None, "test")


def test_p0_search_self_play_game(teams):
    from integration.qwen_mcts.game import play
    from integration.qwen_mcts.prepare import statics
    from integration.qwen_mcts.tokens import Tokens
    tokens = Tokens()
    static, _ = statics(teams, tokens)
    job = dict(slot_id="t", stage="test-cpu", assignment="A-p1", seed_key=["cpu", 1], game_seed=[3, 1, 4, 1],
               players={"p1": dict(mode="search", tag="P0"), "p2": dict(mode="search", tag="P0")})
    result = play(job, teams, static, _evaluator(), tokens)
    assert result["status"] in ("completed", "censored"), result["reason"]
    searched = [r for r in result["records"] if "P0" in r["search"]]
    assert searched and all(abs(sum(r["search"]["P0"]["pi"][0]) - 1) < 1e-9 for r in searched)
    for record in searched:
        s = record["search"]["P0"]
        terminal = np.array(s["terminal"])
        assert np.all(np.array(s["matrix"])[~terminal] == 0.0)        # P0 values are exactly zero
    rows = R.rows(dict(result, records=result["records"]), tag="P0")
    assert rows and all(row["prefix"] == "A-p1" for row in rows)


def test_opponent_game_runs(teams):
    from integration.qwen_mcts.game import play
    from integration.qwen_mcts.prepare import statics
    from integration.qwen_mcts.tokens import Tokens
    tokens = Tokens()
    static, _ = statics(teams, tokens)
    job = dict(slot_id="o", stage="test-cpu", assignment="B-p1", seed_key=["cpu", 2], game_seed=[2, 7, 1, 8],
               players={"p1": dict(mode="policy", tag="P0"), "p2": dict(mode="opponent")})
    result = play(job, teams, static, _evaluator(), tokens)
    assert result["status"] in ("completed", "censored"), result["reason"]
    assert any("opponent_command" in r for r in result["records"])


def test_evaluator_discards_stale_responses():
    """Response channels outlive a Pool: answers to an earlier Pool or to an abandoned request are dropped, never used."""
    import queue
    import threading
    from integration.qwen_mcts.pool import Evaluator
    server, response = queue.Queue(), queue.Queue()
    evaluate = Evaluator(3, [server], response, threading.Event(), "epoch-b", timeout=5)
    evaluate.sequence = 2                                              # this worker abandoned request 2 earlier
    response.put((("epoch-a", 7), "ok", [0.5], [None], {}))            # earlier Pool, cut off by a deadline
    response.put((("epoch-b", 2), "ok", [0.25], [None], {}))           # the abandoned request of this Pool
    response.put((("epoch-b", 3), "ok", [0.125], [None], {"gpu": 2}))
    values, policies, meta = evaluate("current", "A-p1", [[1, 2]], [None])
    assert (values, policies, meta, evaluate.stale) == ([0.125], [None], {"gpu": 2}, 2)
    worker, identity, *_ = server.get_nowait()
    assert (worker, identity) == (3, ("epoch-b", 3))
    for answered in (("epoch-b", 9), 4, ("epoch-b",)):                 # never a legitimate answer: fail closed
        response.put((answered, "ok", [0.0], [None], {}))
        with pytest.raises(RuntimeError, match="identity changed"):
            evaluate("current", "A-p1", [[1, 2]], [None])


def test_training_stop_is_recorded_as_an_event(tmp_path):
    """EX-080 attempt 3 stopped with a TypeError here: the stop record's own 'at' collided with the event time."""
    from integration.qwen_mcts.run import Controller
    for round_id, score in ((4, 0.5), (8, 0.5), (12, 0.5)):
        (tmp_path / "rounds" / f"{round_id:03d}").mkdir(parents=True)
        (tmp_path / "rounds" / f"{round_id:03d}" / "dev.json").write_text(json.dumps(dict(round=round_id, score=score)))
    record = Controller(tmp_path).stop_training(12, ["slowdown"])
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert json.loads((tmp_path / "train-stop.json").read_text()) == json.loads(json.dumps(record))
    assert [e["event"] for e in events] == ["training_stopped"] and events[0]["reasons"] == ["slowdown"]
    assert events[0]["history"] == [[4, 0.5], [8, 0.5], [12, 0.5]]

