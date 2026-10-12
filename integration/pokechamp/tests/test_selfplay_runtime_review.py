"""Independent CPU regressions for EX-072 phase, snapshot, and resume boundaries."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

import pytest
import torch

from integration.pokechamp.imitation.learning import _same_state
from integration.pokechamp.selfplay import execution, model, runner, serving, trainer
from integration.pokechamp.selfplay.storage import Clock, atomic, read, sha, write_jsonl
from integration.pokechamp.tests.test_imitation_learning import public_input
from integration.pokechamp.tests.test_selfplay_learning import TinyPolicy, bc_records, fake_encode, rollout


class SnapshotTiny(TinyPolicy):
    save_snapshot = model.SelfPlayPolicy.save_snapshot


class RunnerTiny(SnapshotTiny):
    def trainable_fingerprints(self):
        original = super().trainable_fingerprints()
        return {("lora_weight" if key == "lora" else "policy.model.head.weight"
                 if key == "action_head" else key): value for key, value in original.items()}


def bare_runner(directory, *, phase="train", policy=None):
    instance = runner.Runner.__new__(runner.Runner)
    instance.directory = directory
    instance.clock = Clock(directory, start=True)
    instance.policy = policy or SnapshotTiny()
    instance.optimizer = trainer.make_optimizer(instance.policy)
    instance.calibration_optimizer = None
    instance.stop = False
    instance.signal_received = None
    instance.last_save = time.monotonic()
    instance.snapshots = {}
    instance.schedule = []
    instance.bc = bc_records()
    instance.state = dict(phase=phase, round=1, active_model="initial", trainer=None,
                          checks={}, candidates=[], snapshot_paths={}, calibration_complete=False,
                          selected=None, base_fingerprints=instance.policy.base_fingerprints())
    atomic(directory / "manifest.json", {"fixture": "CPU runtime boundary review"})
    atomic(directory / "prepared/schedule.json", [])
    return instance


def test_checkpoint_before_first_update_supports_none_cursor(tmp_path):
    instance = bare_runner(tmp_path, phase="preflight")
    pointer = instance.save()
    assert pointer["global_updates"] == 0
    target = SnapshotTiny()
    optimizer = trainer.make_optimizer(target)
    saved = execution.load_checkpoint(tmp_path, target, optimizer, instance.clock)
    assert saved["state"]["trainer"] is None
    assert saved["clock"] == instance.clock.record
    assert target.trainable_fingerprints() == instance.policy.trainable_fingerprints()


def test_resume_rejects_a_new_clock_and_changed_checkpoint(tmp_path):
    instance = bare_runner(tmp_path)
    pointer = instance.save()
    wrong_clock = copy.copy(instance.clock)
    wrong_clock.record = dict(instance.clock.record, started_at=0)
    target = SnapshotTiny()
    optimizer = trainer.make_optimizer(target)
    with pytest.raises(ValueError, match="different clock"):
        execution.load_checkpoint(tmp_path, target, optimizer, wrong_clock)
    with Path(pointer["path"]).open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        execution.load_checkpoint(tmp_path, target, optimizer, instance.clock)


@pytest.mark.parametrize("phase", ["baseline_dev", "collect", "dev", "calibration_collect",
                                     "calibration_dev", "test_initial", "test_selected"])
def test_signal_during_collection_keeps_phase_for_unattempted_slots(tmp_path, monkeypatch, phase):
    instance = bare_runner(tmp_path, phase=phase)
    weights = instance.policy.snapshot_weights()
    instance.snapshots = {name: dict(weights=copy.deepcopy(weights), identity=name)
                          for name in ("initial", "selected-before", "selected-after", "selected", "final")}
    instance.state["calibration_decision"] = dict(adopt=False)
    instance.rows = lambda *a, **kw: []
    def interrupted_collection(*args):
        instance.stop = True
        return []
    instance.collect = interrupted_collection
    assert instance.execute() == 130
    assert instance.state["phase"] == phase
    assert instance.state["round"] == 1
    assert not (tmp_path / "rounds/round-1-gate.json").exists()
    assert not instance.state["candidates"]


def test_signal_during_feature_extraction_preserves_calibration_stage(tmp_path, monkeypatch):
    instance = bare_runner(tmp_path, phase="calibration_features")
    instance.rows = lambda *a, **kw: []
    def interrupted(*args, **kwargs):
        instance.stop = True
        raise TimeoutError("interrupted")
    monkeypatch.setattr(trainer, "extract_features", interrupted)
    assert instance.execute() == 130
    assert instance.state["phase"] == "calibration_features"
    assert not (tmp_path / "calibration-decision.json").exists()


def test_signal_during_preflight_keeps_uncompleted_preflight_resumable(tmp_path, monkeypatch):
    instance = bare_runner(tmp_path, phase="preflight")
    def interrupted(*args, **kwargs):
        instance.stop = True
        return dict(passed=False, samples=3, optimizer_updates=0)
    monkeypatch.setattr(trainer, "preflight", interrupted)
    assert instance.execute() == 130
    assert instance.state["phase"] == "preflight"
    assert not instance.state["checks"].get("gpu_preflight")


def test_collection_failure_restores_learner_before_checkpoint(tmp_path, monkeypatch):
    from integration.pokechamp.selfplay import battle
    instance = bare_runner(tmp_path, phase="collect")
    instance.store_snapshot("initial")
    before = instance.policy.trainable_fingerprints()
    monkeypatch.setattr(runner, "assert_frozen", lambda _: None)
    monkeypatch.setattr(runner, "outcomes_for", lambda directory, rows:
                        [dict(slot_id=row["slot_id"], status="unattempted") for row in rows])
    class FakeService:
        def __init__(self, *args, **kwargs):
            self.closed = False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.closed = True
    monkeypatch.setattr(serving, "Service", FakeService)
    def failed_match(directory, row, service, *args, **kwargs):
        with torch.no_grad():
            instance.policy.action_head.add_(10)
        return dict(slot_id=row["slot_id"], status="failed", failure_scope="phase")
    monkeypatch.setattr(battle, "match", failed_match)
    rows = [dict(slot_id="failure", model="initial", opponent="initial", model_side="p1",
                 stage="train", round=1)]
    with pytest.raises(RuntimeError, match="shared battle defect"):
        instance.collect(rows, "policy")
    assert instance.policy.trainable_fingerprints() == before
    instance.save()
    reloaded = SnapshotTiny()
    execution.load_checkpoint(tmp_path, reloaded, trainer.make_optimizer(reloaded), instance.clock)
    assert reloaded.trainable_fingerprints() == before


def test_service_exit_joins_inflight_forward_before_weight_restore():
    entered, release, exited = threading.Event(), threading.Event(), threading.Event()
    errors = []
    class SlowPolicy:
        def load_weights(self, weights):
            pass
        def set_stage(self, stage):
            pass
        def predict(self, body, **kwargs):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test did not release the forward")
            return dict(wdl_probabilities={key: [1 / 3] * 3
                        for key in body["questions"]["action"]["criteria"]})
    service = serving.Service(SlowPolicy(), {"initial": dict(weights={}, identity="fixture")}, port=0)
    service.__enter__()
    def request():
        try:
            body = json.dumps(dict(model="initial", input=public_input().body, seed=3)).encode()
            with urllib.request.urlopen(urllib.request.Request(service.endpoint + "/evaluate", body), timeout=5) as response:
                response.read()
        except BaseException as error:
            errors.append(error)
    request_thread = threading.Thread(target=request)
    request_thread.start()
    assert entered.wait(3)
    def close():
        service.__exit__(None, None, None)
        exited.set()
    close_thread = threading.Thread(target=close)
    close_thread.start()
    try:
        # serve_forever shutdown polls at .5s; wait past that to specifically
        # observe that server_close also waits for its request handler.
        assert not exited.wait(.7)
    finally:
        release.set()
        close_thread.join(5)
        request_thread.join(5)
    assert exited.is_set() and not errors


def test_orphan_snapshot_is_reused_only_for_identical_weights(tmp_path):
    instance = bare_runner(tmp_path)
    instance.store_snapshot("round-1")
    identity = instance.state["snapshot_paths"]["round-1"]["sha256"]
    instance.state["snapshot_paths"].clear()
    instance.snapshots.clear()
    instance.store_snapshot("round-1")
    assert instance.state["snapshot_paths"]["round-1"]["sha256"] == identity
    path = tmp_path / "snapshots/round-1.pt"
    saved = torch.load(path, weights_only=True)
    saved["weights"]["action_head"][0] += 1
    torch.save(saved, path)
    with pytest.raises(ValueError, match="tensors differ"):
        instance.store_snapshot("round-1")


@pytest.mark.parametrize("adopt", [False, True])
def test_final_head_is_locked_before_test_and_test_cannot_reselect(tmp_path, monkeypatch, adopt):
    instance = bare_runner(tmp_path, phase="lock")
    instance.state["selected"] = dict(model="round-1", round=1)
    instance.store_snapshot("selected-before")
    before = instance.policy.snapshot_weights()
    with torch.no_grad():
        instance.policy.wdl_head[-1].bias[0] = 1
    instance.store_snapshot("selected-after")
    after = instance.policy.snapshot_weights()
    instance.state["calibration_decision"] = dict(adopt=adopt, head="after" if adopt else "before")
    atomic(tmp_path / "calibration-decision.json", instance.state["calibration_decision"])
    observed = []
    def inspect_collection(rows, budget):
        lock = read(tmp_path / "evaluation-lock.json")
        assert lock["head"] == ("after" if adopt else "before")
        assert sha(lock["final"]["path"]) == lock["final"]["sha256"]
        expected = after if adopt else before
        assert all(torch.equal(value, expected[key]) for key, value in instance.snapshots["selected"]["weights"].items())
        assert instance.snapshots["selected"]["primary_head"] == ("after" if adopt else "before")
        observed.append(instance.state["phase"])
        return []
    instance.collect = inspect_collection
    monkeypatch.setattr(runner.reporting, "select_policy", lambda *_: pytest.fail("test reselected policy"))
    assert instance.execute() == 0
    assert observed == ["test_initial", "test_selected"]
    assert instance.state["phase"] == "finalize"


def test_real_sigterm_and_fresh_process_resume_preserve_adamw_cursor_rng(tmp_path, monkeypatch):
    """Exercise Runner.step's real signal/receipt, then Runner.__init__ in a new PID."""
    script = tmp_path / "resume_probe.py"
    script.write_text('''
import copy, json, os, signal, sys, torch
from pathlib import Path
from integration.pokechamp.selfplay import runner, model, trainer, execution
from integration.pokechamp.selfplay.storage import Clock, atomic, read, jsonl, write_jsonl
from integration.pokechamp.tests.test_selfplay_runtime_review import SnapshotTiny, bare_runner
from integration.pokechamp.tests.test_selfplay_learning import fake_encode, rollout, bc_records

class RootTiny(SnapshotTiny):
    def trainable_fingerprints(self):
        raw=super().trainable_fingerprints()
        return {('lora_weight' if k=='lora' else 'policy.model.head.weight' if k=='action_head' else k):v for k,v in raw.items()}

directory=Path(sys.argv[1]); mode=sys.argv[2]
trainer.encode_input=fake_encode
runner.assert_frozen=lambda _:None
torch.manual_seed(23)
if mode=='first':
    policy=RootTiny()
    r=bare_runner(directory,phase='train',policy=policy)
    records=rollout(policy)
    write_jsonl(directory/'rollout.jsonl',records)
    write_jsonl(directory/'prepared/bc.jsonl',r.bc)
    r.state['before_training_fingerprints']=policy.trainable_fingerprints()
    r.state['restart_pending']=False
    r.rows=lambda *a,**k:[]
    runner.outcomes_for=lambda *a:[]
    runner.decisions_for=lambda *a:records
    signal.signal(signal.SIGTERM,r.signal)
    code=r.execute()
    assert code==75 and r.signal_received==signal.SIGTERM
    assert read(directory/'restart-request.json')['signal_received']
    sys.exit(code)
if mode=='resume':
    model.SelfPlayPolicy=lambda **kwargs:RootTiny()
    r=runner.Runner(directory)
    assert r.state['checks']['resume_validation']
    records=list(jsonl(directory/'rollout.jsonl'))
    result=trainer.train_round(r.policy,records,r.bc,round_id=1,optimizer=r.optimizer,state=r.state['trainer'])
    torch.save(dict(fingerprints=r.policy.trainable_fingerprints(),optimizer=r.optimizer.state_dict(),
                    cursor=result['state'],rng=torch.get_rng_state()),directory/'resumed.pt')
if mode=='reference':
    policy=RootTiny()
    optimizer=trainer.make_optimizer(policy)
    result=trainer.train_round(policy,rollout(policy),bc_records(),round_id=1,optimizer=optimizer)
    torch.save(dict(fingerprints=policy.trainable_fingerprints(),optimizer=optimizer.state_dict(),
                    cursor=result['state'],rng=torch.get_rng_state()),directory/'reference.pt')
''', encoding="utf-8")
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONPATH=str(Path(__file__).resolve().parents[3]))
    first = subprocess.run([sys.executable, str(script), str(tmp_path), "first"], env=environment,
                           capture_output=True, text=True, timeout=30)
    assert first.returncode == 75, first.stdout + first.stderr
    request = read(tmp_path / "restart-request.json")
    resumed = subprocess.run([sys.executable, str(script), str(tmp_path), "resume"], env=environment,
                             capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    receipt = read(tmp_path / "verification/resume.json")
    assert receipt["original_pid"] == request["pid"] != receipt["resumed_pid"]
    reference = subprocess.run([sys.executable, str(script), str(tmp_path), "reference"], env=environment,
                               capture_output=True, text=True, timeout=30)
    assert reference.returncode == 0, reference.stdout + reference.stderr
    expected = torch.load(tmp_path / "reference.pt", weights_only=True)
    actual = torch.load(tmp_path / "resumed.pt", weights_only=True)
    assert _same_state(expected, actual)


def test_four_round_phase_machine_uses_one_optimizer_then_locks_selected_head(tmp_path, monkeypatch):
    """Full 584-slot fixture, real CPU PPO/head optimizers, no battle/model process."""
    from integration.pokechamp.selfplay import battle, prepare
    torch.manual_seed(71)
    instance = bare_runner(tmp_path, phase="preflight", policy=RunnerTiny())
    instance.state["checks"].update(cpu_validation=True, resume_validation=True)
    instance.store_snapshot("initial")
    teams = {split: [dict(signature=f"{split}-{index}", packed=f"team-{index}")
                     for index in range(count)] for split, count in prepare.SPLIT_COUNTS.items()}
    instance.schedule = prepare.make_schedule(teams)
    atomic(tmp_path / "prepared/schedule.json", instance.schedule)
    # The dedicated subprocess test above covers the real planned restart.
    atomic(tmp_path / "restart-request.json", dict(fixture="resume covered independently"))
    monkeypatch.setattr(trainer, "encode_input", fake_encode)
    monkeypatch.setattr(trainer, "preflight", lambda *args, **kwargs: dict(passed=True, optimizer_updates=0))
    original_train = trainer.train_round
    optimizer_identity = id(instance.optimizer)
    visited_rounds, observed_ids, collection_stages = [], set(), []
    def bounded_cpu_round(policy, records, bc, *, round_id, optimizer, state, deadline,
                          should_stop, on_step, on_boundary):
        assert id(optimizer) == optimizer_identity
        assert len(records) == 512 and {record["round_id"] for record in records} == {round_id}
        ids = {record["decision_id"] for record in records}
        assert not ids & observed_ids
        observed_ids.update(ids)
        assert (state or {}).get("global_updates", 0) == 4 * (round_id - 1)
        visited_rounds.append(round_id)
        # Keep real optimizer/cursor behavior while bounding this fixture's
        # CPU workload to two optimizer batches per epoch.
        return original_train(policy, records[:17], bc, round_id=round_id, optimizer=optimizer,
                              state=state, deadline=deadline, should_stop=should_stop,
                              on_step=on_step, on_boundary=on_boundary)
    monkeypatch.setattr(trainer, "train_round", bounded_cpu_round)

    def collect_fixture(rows, budget):
        assert rows
        stage = rows[0]["stage"]
        collection_stages.append((stage, rows[0]["model"]))
        if stage == "test":
            assert (tmp_path / "evaluation-lock.json").exists()
        output = []
        for slot in rows:
            actor = instance.snapshots[slot["model"]]
            # Deliberately model the server's weight-switching behavior.
            instance.policy.load_weights(actor["weights"])
            samples = rollout(instance.policy, 8 if stage == "train" else 1,
                              round_id=slot["round"])
            for index, record in enumerate(samples):
                record.update(decision_id=f'{slot["slot_id"]}:{index}', slot_id=slot["slot_id"],
                              outcome="W", automatic=False)
                chosen = record["action_ids"].index(record["choice"])
                record["wdl_before"] = record["wdl_probabilities"][chosen]
                alternate = actor.get("alternate_head")
                if alternate is not None:
                    with torch.no_grad():
                        features = instance.policy.scores(fake_encode(record["input"])).features[chosen]
                        prediction = torch.func.functional_call(instance.policy.wdl_head, alternate,
                                                                 (features,)).softmax(-1).tolist()
                else:
                    prediction = record["wdl_before"]
                record["wdl_after"] = prediction
                if actor.get("primary_head") == "after":
                    record["wdl_before"], record["wdl_after"] = prediction, record["wdl_before"]
            outcome = battle.base_outcome(slot, "completed")
            outcome.update(result="win", audit_passed=True, actors_cleaned=True, server_cleaned=True)
            directory = tmp_path / "games" / slot["slot_id"]
            atomic(directory / "outcome.json", outcome, immutable=True)
            write_jsonl(directory / "decisions.jsonl", samples, immutable=True)
            output.append(outcome)
        if stage == "train" and rows[0]["round"] == 1:
            instance.state["checks"]["first_eight_audit"] = True
        # Every completed batch restores its active learner, including dev's
        # initial/opponent switches and final-head comparisons.
        instance.activate(instance.state["active_model"])
        return output
    instance.collect = collect_fixture
    assert instance.execute() == 0
    assert visited_rounds == [1, 2, 3, 4]
    assert instance.state["trainer"]["global_updates"] == 16
    assert instance.state["selected"]["model"] == "round-1"  # all dev scores tie
    assert instance.state["calibration_complete"]
    assert instance.state["calibration_decision"]["adopt"]
    assert instance.state["phase"] == "finalize"
    assert collection_stages[-2:] == [("test", "initial"), ("test", "selected")]
    assert sum(1 for _ in (tmp_path / "games").glob("*/outcome.json")) == 584
    assert instance.optimizer.state and all(int(state["step"]) == 16
                                            for state in instance.optimizer.state.values())
