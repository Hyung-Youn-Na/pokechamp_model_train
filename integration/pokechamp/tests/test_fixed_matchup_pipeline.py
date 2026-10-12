"""CPU synthetic integration checks; never collects the experimental A/B matchup."""
import copy
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time

import pytest
import torch

from integration.pokechamp.fixed_matchup import artifacts, reporting
from integration.pokechamp.fixed_matchup.battle import BudgetExpired, play
from integration.pokechamp.fixed_matchup.config import ROOT, SCHEMA, PROTOCOL
from integration.pokechamp.fixed_matchup.finalize import audit_game, finalize
from integration.pokechamp.fixed_matchup.model import Policy, learn
from integration.pokechamp.fixed_matchup.pool import Pool
from integration.pokechamp.fixed_matchup.runtime import Clock
from integration.pokechamp.fixed_matchup.schedule import matchup, players, test_schedule as schedule_test
from integration.pokechamp.fixed_matchup.simulator import Simulator
from integration.pokechamp.fixed_matchup.storage import atomic, digest, read, sha
from integration.pokechamp.fixed_matchup.verification import FIXTURE_TEAMS


TEAMS = {"A": "Gholdengo\nAbility: Good as Gold\n- Make It Rain",
         "B": "Clefable\nAbility: Magic Guard\n- Moonblast"}


@pytest.fixture(scope="module")
def fixture():
    torch.set_num_threads(2)
    with Simulator("real") as sim:
        frame = sim.init({"p1": TEAMS["A"], "p2": TEAMS["B"]}, [1, 2, 3, 4])
        vocabulary = sim.catalog()["vocabulary"]
        frame = sim.advance({"p1": "lead:1", "p2": "lead:1"})
    return vocabulary, frame["observations"]["p1"]


def first_action(observations):
    return [dict(policy=[1.0] + [0.0] * (len(o["actions"]) - 1), value=0.0) for o in observations]


class FirstPolicy:
    def evaluate_batch(self, observations):
        return first_action(observations)


def job(mode="policy", opponent=False, slot=0):
    return matchup("synthetic", "fixture", slot, "A", "p1",
                   [players("P0", mode), players(None, "opponent") if opponent else players("P0", "policy")])


def test_model_padding_reload_and_learn(tmp_path, fixture):
    vocabulary, obs = fixture
    torch.manual_seed(9)
    model = Policy(vocabulary).eval()
    single = model.evaluate_batch([obs])[0]
    other = copy.deepcopy(obs)
    other["tokens"] = other["tokens"][:1]
    other["actions"] = []
    batch = model.evaluate_batch([other, obs])
    assert batch[0]["policy"] == []
    assert batch[1]["policy"] == pytest.approx(single["policy"], abs=1e-6)
    assert batch[1]["value"] == pytest.approx(single["value"], abs=1e-6)
    path = tmp_path / "policy.pt"
    model.save(path)
    atomic(tmp_path / "observation.json", obs)
    code = ("import json,torch; from pathlib import Path; "
            "from integration.pokechamp.fixed_matchup.model import Policy; torch.set_num_threads(2); "
            "import sys; print(json.dumps(Policy.load(sys.argv[1]).evaluate_batch([json.loads(Path(sys.argv[2]).read_text())])))")
    output = subprocess.check_output([sys.executable, "-c", code, str(path), str(tmp_path / "observation.json")], cwd=ROOT)
    assert json.loads(output)[0]["policy"] == pytest.approx(single["policy"], abs=1e-6)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    row = dict(observation=obs, observation_hash=digest(obs), terminal_status="completed", z=1,
               target=[1.] + [0.] * (len(obs["actions"]) - 1))
    result = learn(model, opt, [row] * 8, generator=torch.Generator().manual_seed(4), epochs=8, batch_size=8)
    after = model.evaluate_batch([obs])[0]
    assert result["steps"] == 8
    assert after["policy"][0] > single["policy"][0]
    assert abs(1 - after["value"]) < abs(1 - single["value"])
    broken = copy.deepcopy(row)
    broken["terminal_status"] = "incomplete"
    with pytest.raises(ValueError, match="nonterminal"):
        learn(model, opt, [broken], generator=torch.Generator())


def test_fainted_bench_and_forced_switch_encode_without_unknown(fixture):
    vocabulary, _ = fixture
    with Simulator("real") as sim:
        sim.init(FIXTURE_TEAMS, [1, 2, 3, 4])
        frame = sim.advance({"p1": "lead:1", "p2": "lead:1"})
        frame = sim.advance({side: o["actions"][0]["id"] for side, o in frame["observations"].items()})
        assert not frame["ended"]
        fainted = [p for s in frame["root"]["physical"]["sides"] for p in s["pokemon"] if p["fainted"]]
        assert fainted and any(p["status"] == "fnt" for p in fainted)
        model = Policy(vocabulary).eval()
        observations = list(frame["observations"].values())
        outputs = model.evaluate_batch(observations)
        assert all(torch.isfinite(torch.tensor(o["value"])) for o in outputs)
        for obs in observations:
            assert not any(c in ("status:fnt", "effect:fnt") for t in obs["tokens"] for c in t["categories"])
            assert any(t["numbers"][17] == 1 for t in obs["tokens"] if "pokemon" in t["categories"])


@pytest.mark.parametrize("kind", ["unknown", "private", "nan", "empty", "duplicate"])
def test_model_rejects_bad_observation(fixture, kind):
    vocabulary, original = fixture
    obs = copy.deepcopy(original)
    if kind == "unknown":
        obs["tokens"][0]["categories"] = ["secret:future"]
    elif kind == "private":
        obs["prng"] = [1, 2, 3, 4]
    elif kind == "nan":
        obs["tokens"][0]["numbers"][0] = float("nan")
    elif kind == "empty":
        obs["tokens"] = []
    else:
        obs["actions"].append(obs["actions"][0])
    with pytest.raises(ValueError):
        Policy(vocabulary).evaluate_batch([obs])


def test_checkpoint_commit_recovery_optimizer_rng(tmp_path, fixture):
    vocabulary, obs = fixture
    atomic(tmp_path / "clock.json", dict(start=17, total=PROTOCOL["total_seconds"]))
    model = artifacts.initial_model(tmp_path, vocabulary, "identity", "cpu")
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    gen = torch.Generator().manual_seed(15)
    artifacts.save_checkpoint(tmp_path, 0, model, opt, gen, identity="identity", replay_ids=[], updates=0)
    row = dict(observation=obs, observation_hash=digest(obs), terminal_status="completed", z=1,
               target=[1.] + [0.] * (len(obs["actions"]) - 1))
    metrics = learn(model, opt, [row] * 2, generator=gen, batch_size=2)
    artifacts.save_checkpoint(tmp_path, 1, model, opt, gen, identity="identity", replay_ids=["fixture"], updates=2, learning=metrics)
    expected = (torch.rand(3), torch.rand(3, generator=gen), random.random())
    # Crash between commit and latest-pointer/model export.
    (tmp_path / "latest.json").unlink()
    restored = Policy(vocabulary)
    restored_opt = torch.optim.AdamW(restored.parameters())
    restored_gen = torch.Generator()
    state = artifacts.restore_checkpoint(tmp_path, restored, restored_opt, restored_gen, identity="identity")
    assert read(tmp_path / "latest.json")["round"] == 1
    assert torch.equal(torch.rand(3), expected[0])
    assert torch.equal(torch.rand(3, generator=restored_gen), expected[1])
    assert random.random() == expected[2]
    assert all(torch.equal(v, restored.state_dict()[k]) for k, v in model.state_dict().items())
    for key, value in opt.state_dict()["state"].items():
        for field, tensor in value.items():
            assert torch.equal(tensor, restored_opt.state_dict()["state"][key][field])
    published = artifacts.publish_round(tmp_path, state)
    assert artifacts.publish_round(tmp_path, state) == published
    assert read(tmp_path / "training/round-001.json") == metrics
    atomic(tmp_path / "clock.json", dict(start=18, total=PROTOCOL["total_seconds"]))
    with pytest.raises(ValueError, match="first clock"):
        artifacts.restore_checkpoint(tmp_path, restored, restored_opt, restored_gen, identity="identity")


def test_slots_not_replayed_and_clock_not_renewed(tmp_path):
    planned = job()
    artifacts.claim(tmp_path, dict(planned, deadline=12))
    found, pending = artifacts.existing(tmp_path, [planned])
    assert not pending and found[0]["status"] == "incomplete"
    assert artifacts.existing(tmp_path, [planned])[0] == found
    with pytest.raises(FileExistsError):
        artifacts.claim(tmp_path, planned)
    now = [100.]
    clock = Clock(tmp_path, now=lambda: now[0])
    clock.resources = lambda: None
    end = clock.enter("train")
    now[0] += 10
    resumed = Clock(tmp_path, now=lambda: now[0])
    resumed.resources = lambda: None
    assert resumed.enter("train") == end
    now[0] = end
    with pytest.raises(BudgetExpired):
        resumed.check()


def test_recovery_debits_stage_time_and_preserves_total_deadline(tmp_path):
    atomic(tmp_path / "clock.json", dict(start=100, total=PROTOCOL["total_seconds"]))
    atomic(tmp_path / "stage-spent.json", dict(pilot=20, finalize=12))
    now = [5000.]
    clock = Clock(tmp_path, now=lambda: now[0])
    clock.resources = lambda: None
    assert clock.enter("pilot") == 5000 + 3600 - 20
    assert clock.first == 100
    now[0] += 5
    assert clock.enter("pilot") == 5000 + 3600 - 20
    now[0] = PROTOCOL["total_seconds"] - 200
    assert clock.enter("finalize") == 100 + PROTOCOL["total_seconds"]


def test_actual_sigterm_preserves_clock_and_claim(tmp_path):
    atomic(tmp_path / "job.json", job())
    code = '''import sys,time
from pathlib import Path
from integration.pokechamp.fixed_matchup.runtime import Clock
from integration.pokechamp.fixed_matchup.artifacts import claim
from integration.pokechamp.fixed_matchup.storage import read,atomic
p=Path(sys.argv[1]); clock=Clock(p)
with clock.signals():
 clock.enter("train"); claim(p,read(p/"job.json")); atomic(p/"ready.json",True)
 while not clock.cancelled: time.sleep(.02)
 atomic(p/"stopped.json",dict(first=clock.first,cancelled=clock.cancelled))
'''
    proc = subprocess.Popen([sys.executable, "-c", code, str(tmp_path)], cwd=ROOT)
    try:
        until = time.monotonic() + 15
        while not (tmp_path / "ready.json").exists() and time.monotonic() < until:
            assert proc.poll() is None
            time.sleep(.05)
        assert (tmp_path / "ready.json").exists()
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=10) == 0
        stopped = read(tmp_path / "stopped.json")
        assert stopped["cancelled"] and Clock(tmp_path).first == stopped["first"]
        assert not artifacts.existing(tmp_path, [job()])[1]
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_paired_statistics_fixed_denominator():
    schedule = schedule_test()
    assert len(schedule) == 640 and len({j["slot_id"] for j in schedule}) == 640
    results = [dict(job=j, status="completed", winner=j["model_side"] if j["condition"] != "P0"
                    else ("p2" if j["model_side"] == "p1" else "p1")) for j in schedule]
    result = reporting.report(schedule, results, draws=100)
    assert result["complete"] and result["policy_improved"]
    assert result["contrasts"]["P1-P0"]["ci95"] == [1, 1]
    result = reporting.report(schedule, results[:-1], draws=100)
    assert not result["complete"] and not result["policy_improved"]
    with pytest.raises(ValueError, match="duplicate"):
        reporting.report(schedule, [*results, results[0]], draws=100)


@pytest.mark.parametrize("mode,opponent", [("policy", False), ("search", False), ("policy", True)])
def test_synthetic_game_artifacts_and_wire_audit(tmp_path, mode, opponent):
    result = play(dict(job(mode, opponent), deadline=time.time() + 90), TEAMS,
                  lambda model, observations: first_action(observations))
    assert result["status"] == "completed", result["reason"]
    artifacts.save_result(tmp_path, result)
    audited, evidence = audit_game(tmp_path / "games" / result["job"]["slot_id"])
    assert evidence["ended"] and audited["winner"] == result["winner"]
    if opponent:
        records = [r for r in result["records"] if r["mode"] == "opponent"]
        assert records and all(r["observation"] is None for r in records)
    if mode == "search":
        assert result["metrics"]["simulations"] > 0
    path = tmp_path / "games" / result["job"]["slot_id"] / "decisions.jsonl.gz"
    path.write_bytes(path.read_bytes() + b"corruption")
    with pytest.raises(ValueError, match="checksum"):
        artifacts.load_result(path.parent)


def test_spawn_workers_batch_inference_and_cleanup(tmp_path):
    jobs = [dict(job(slot=i), deadline=time.time() + 60) for i in range(3)]
    received = []
    with Pool(TEAMS, {"P0": FirstPolicy()}, workers=2, batch_size=2) as pool:
        pool.collect(jobs, on_submit=lambda j: artifacts.claim(tmp_path, j),
                     on_result=lambda r: received.append(artifacts.save_result(tmp_path, r)), retain=False)
        assert pool.metrics["observations"] > 0 and pool.metrics["largest_batch"] <= 2
    assert all(not p.is_alive() for p in pool.processes)
    assert len(received) == 3 and all(r["status"] == "completed" for r in received)


def test_offline_export_browser_and_audit(tmp_path, monkeypatch):
    import integration.pokechamp.fixed_matchup.finalize as module
    result = play(dict(job(), deadline=time.time() + 60), TEAMS,
                  lambda model, observations: first_action(observations))
    assert result["status"] == "completed", result["reason"]
    artifacts.save_result(tmp_path, result)
    atomic(tmp_path / "schedule.json", dict(pilot=[job()], train=[], dev={}, test=schedule_test()))
    # Source identity is covered separately; this fixture deliberately is not EX-076.
    monkeypatch.setattr(module, "verify_identity", lambda directory: {"identity": "synthetic-only", "protocol": {"experiment": "SYNTHETIC"}})
    output = finalize(tmp_path, export_root=tmp_path / "viewer")
    assert output["audit"]["passed"] and output["audit"]["browser"]["passed"]
    assert output["audit"]["browser"]["offline"] and output["audit"]["browser"]["moved"]
    assert not output["procedure_complete"] and not output["efficacy_success"]
    for line in (tmp_path / "evidence.sha256").read_text().splitlines():
        checksum, name = line.split("  ", 1)
        assert sha(tmp_path / name) == checksum


def test_preparation_freezes_sources_and_detects_tampering(tmp_path, monkeypatch):
    import integration.pokechamp.fixed_matchup.prepare as module
    monkeypatch.setattr(module, "source_files", lambda: [ROOT / "scripts/pokechamp-fixed-matchup"])
    directory = tmp_path / "prepared"
    manifest = module.prepare(directory)
    assert manifest["validation"] == {"A": None, "B": None}
    assert module.verify_identity(directory)["identity"] == manifest["identity"]
    assert not (directory / "clock.json").exists()
    (directory / "source/scripts/pokechamp-fixed-matchup").write_text("tampered")
    with pytest.raises(ValueError, match="frozen source"):
        module.verify_identity(directory)


def test_resumed_committed_round_finishes_dev_before_selection(tmp_path, fixture, monkeypatch):
    import integration.pokechamp.fixed_matchup.runner as module
    from integration.pokechamp.fixed_matchup.schedule import development
    vocabulary, _ = fixture
    atomic(tmp_path / "clock.json", dict(start=time.time(), total=PROTOCOL["total_seconds"]))
    p0 = artifacts.initial_model(tmp_path, vocabulary, "identity", "cpu")
    opt = torch.optim.AdamW(p0.parameters(), lr=3e-4, weight_decay=1e-4)
    gen = torch.Generator().manual_seed(5)
    # Commit the fourth round but omit its export and dev receipt as if killed there.
    for round_id in range(5):
        artifacts.save_checkpoint(tmp_path, round_id, p0, opt, gen, identity="identity", replay_ids=[], updates=round_id)
    load = Policy.load
    monkeypatch.setattr(Policy, "load", lambda path, device="cpu": load(path, "cpu"))
    monkeypatch.setitem(module.PROTOCOL, "max_rounds", 4)
    called = []
    def run_group(directory, schedule, teams, models, clock, setting, model_files):
        assert schedule == development(4)
        assert (tmp_path / "models/round-004.pt").exists()
        called.append("dev4")
        return [dict(job=j, status="completed", winner="") for j in schedule]
    monkeypatch.setattr(module, "run_group", run_group)
    selection = module.policy_phase(tmp_path, {"identity": "identity"}, TEAMS,
        {"dev": {"4": development(4)}, "train": []}, p0, Clock(tmp_path), {})
    assert called == ["dev4"] and selection["round"] == 4 and selection["score"] == .5


def test_forced_switch_and_preview_audit(tmp_path):
    teams = dict(TEAMS)
    teams["B"] += "\n\nPikachu\nAbility: Static\n- Thunderbolt"
    result = play(dict(job(), deadline=time.time() + 60), teams,
                  lambda model, observations: first_action(observations))
    assert result["status"] == "completed", result["reason"]
    artifacts.save_result(tmp_path, result)
    audit_game(tmp_path / "games" / result["job"]["slot_id"])
    assert any(r["choice"] == "switch:2" for r in result["records"])


def test_pilot_censoring_is_distinct_from_interruption():
    from integration.pokechamp.fixed_matchup.schedule import pilot_schedule
    rows = [dict(job=j, status="completed", winner="p1") for j in pilot_schedule()]
    rows[0].update(status="incomplete", winner=None, reason="turn_limit")
    assert reporting.pilot_gate(rows, projected_test_seconds=100)["passed"]
    rows[0]["reason"] = "interrupted_reserved_slot"
    assert not reporting.pilot_gate(rows, projected_test_seconds=100)["passed"]


def test_completed_benchmark_probes_resume_without_replay(tmp_path, monkeypatch):
    import integration.pokechamp.fixed_matchup.runner as module
    jobs = [dict(kind="probe", slot_id=f"probe-{i}", seed=i, simulations=64,
                 root={"fixture": i}, deadline=time.time() + 60) for i in range(2)]
    first = {k: v for k, v in jobs[0].items() if k not in ("root", "deadline")}
    atomic(tmp_path / "benchmarks/claims/probe-0.json", dict(job=first, root_hash=digest(jobs[0]["root"])))
    atomic(tmp_path / "benchmarks/results/probe-0.json", dict(job=first, status="completed", metrics=dict(transitions=64)))
    seen = []
    class FakePool:
        def __init__(self, *args, **kwargs):
            self.metrics = {}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def collect(self, jobs, on_submit, on_result, **kwargs):
            for job in jobs:
                seen.append(job["slot_id"])
                on_submit(job)
                on_result(dict(job={k: v for k, v in job.items() if k not in ("root", "deadline")},
                               status="completed", metrics=dict(transitions=64)))
    monkeypatch.setattr(module, "Pool", FakePool)
    setting = dict(workers=8, batch_size=16)
    clock = Clock(tmp_path)
    result = module.benchmark_group(tmp_path, "fixture", jobs, TEAMS, None, clock, setting)
    assert result["transitions"] == 128 and seen == ["probe-1"]
    module.benchmark_group(tmp_path, "fixture", jobs, TEAMS, None, clock, setting)
    assert seen == ["probe-1"]
    (tmp_path / "benchmarks/results/probe-1.json").unlink()
    with pytest.raises(RuntimeError, match="unfinished reserved"):
        module.benchmark_group(tmp_path, "fixture", jobs, TEAMS, None, clock, setting)


def test_explicit_short_budget_never_renews_on_resume(tmp_path):
    protocol = copy.deepcopy(PROTOCOL)
    protocol.update(total_seconds=28800)
    protocol["stage_seconds"] = dict(verify=3600, train=21600, finalize=3600)
    now = [100.]
    clock = Clock(tmp_path, now=lambda: now[0], protocol=protocol)
    clock.resources = lambda: None
    assert clock.enter("train") == 21700
    now[0] = 28700
    resumed = Clock(tmp_path, now=lambda: now[0], protocol=protocol)
    resumed.resources = lambda: None
    assert resumed.enter("finalize") == 28900
    with pytest.raises(ValueError, match="total budget"):
        Clock(tmp_path, now=lambda: now[0])
