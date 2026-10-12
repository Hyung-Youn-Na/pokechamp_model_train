"""EX-073 synchronous stage machine; all four ranks follow one policy timeline."""

from __future__ import annotations

import json
import os
import signal
import time
import traceback
from collections import Counter
from pathlib import Path

from . import config, reporting, distributed as dd
from .execution import assert_frozen, load_checkpoint, save_checkpoint
from .storage import Clock, append as _append, atomic as _atomic, jsonl, read, sha


def atomic(*args, **kwargs):
    if dd.rank() == 0:
        _atomic(*args, **kwargs)


def append(*args, **kwargs):
    if dd.rank() == 0:
        _append(*args, **kwargs)


def shared(value):
    return dd.gather(value)[0]


def synchronize():
    dd.assert_same(True, "stage barrier")



def round_gate(outcomes, decisions):
    attempted = sum(row["status"] != "unattempted" for row in outcomes)
    completed = sum(row["status"] == "completed" for row in outcomes)
    valid_slots = {row["slot_id"] for row in outcomes if row["status"] == "completed"}
    valid = [
        r
        for r in decisions
        if r["slot_id"] in valid_slots
        and r.get("terminal_status") == "completed"
        and len(r.get("action_ids", [])) > 1
        and not r.get("automatic", False)
    ]
    return {
        "passed": len(outcomes) == 64
        and attempted == 64
        and completed >= 48
        and len(valid) >= 512,
        "planned": 64,
        "attempted": attempted,
        "completed": completed,
        "valid_decisions": len(valid),
    }


def outcomes_for(directory, schedule):
    from .battle import base_outcome

    rows = []
    for slot in schedule:
        attempt = Path(directory) / "games" / slot["slot_id"]
        if (attempt / "outcome.json").exists():
            outcome = read(attempt / "outcome.json")
        elif attempt.exists():
            # A claimed slot survives SIGTERM/crash and can never be replayed.
            outcome = base_outcome(
                slot, "incomplete", reason="interrupted_claim", failure_scope="battle"
            )
            atomic(attempt / "outcome.json", outcome, immutable=True)
        else:
            outcome = base_outcome(slot)
        rows.append(outcome)
    return rows


def decisions_for(directory, outcomes):
    result = []
    for row in outcomes:
        path = Path(directory) / "games" / row["slot_id"] / "decisions.jsonl"
        if row["status"] == "completed" and path.exists():
            result.extend(jsonl(path))
    return result


def receipt(path, value):
    """A committed boundary may be adopted after a crash, never overwritten."""
    if dd.rank() != 0:
        return
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError(
                "existing stage receipt differs from restored evidence: " + str(path)
            )
    else:
        atomic(path, value, immutable=True)


class Runner:
    def __init__(self, directory):
        import torch

        from ..imitation.model import seed_all
        from .model import Policy
        from .trainer import make_optimizer

        self.directory = Path(directory)
        self.clock = Clock(directory)
        self.stop = False
        self.signal_received = None
        signal.signal(signal.SIGTERM, self.signal)
        signal.signal(signal.SIGINT, self.signal)
        assert_frozen(directory)
        seed_all(config.SEED)
        self.policy = Policy(device=f"cuda:{dd.rank()}", checkpoint=config.INITIAL)
        self.optimizer = make_optimizer(self.policy)
        self.calibration_optimizer = None
        self.snapshots = {}
        self.buffer = []
        self.schedule = read(self.directory / "prepared/schedule.json")
        self.bc = list(jsonl(self.directory / "prepared/bc.jsonl"))
        self.state = {
            "phase": "preflight",
            "round": 1,
            "active_model": "initial",
            "trainer": None,
            "checks": {"cpu_validation": True},
            "candidates": [],
            "dev_attempted": [],
            "last_completed_round": 0,
            "snapshot_paths": {},
            "calibration_complete": False,
            "selected": None,
        }
        self.last_save = time.monotonic()
        if shared((self.directory / "latest.json").exists()):
            payload = load_checkpoint(
                directory, self.policy, self.optimizer, self.clock
            )
            self.state = payload["state"]
            self.buffer = payload.get("frozen_buffer", [])
            if payload.get("calibration_optimizer") is not None:
                self.calibration_optimizer = make_optimizer(
                    self.policy, calibration=True
                )
                self.calibration_optimizer.load_state_dict(
                    payload["calibration_optimizer"]
                )
            if self.state.get("restart_pending"):
                proof = read(self.directory / "restart-complete.json")
                prior = read(self.directory / f"restart-rank-{dd.rank()}.json")
                if prior["pid"] == os.getpid() or not prior["signal_received"]:
                    raise ValueError("restart must restore all ranks in new processes")
                if prior["checkpoint_sha256"] != read(self.directory / "latest.json")["sha256"]:
                    raise ValueError("restart checkpoint changed")
                self.state["checks"]["resume_validation"] = True
                self.state["restart_pending"] = False
                ranks = dd.gather({"rank": dd.rank(), "previous_pid": prior["pid"], "pid": os.getpid()})
                atomic(self.directory / "verification/resume.json", {
                    "passed": True, "ranks": ranks, "checkpoint": read(self.directory / "latest.json"),
                    "clock": self.clock.record, "completed_updates": self.state["trainer"]["global_updates"],
                    "optimizer_states": len(self.optimizer.state), "supervisor": proof,
                }, immutable=True)
        else:
            self.state["base_fingerprints"] = self.policy.base_fingerprints()
            self.store_snapshot("initial")
            self.save()
        for name, item in self.state["snapshot_paths"].items():
            if name not in {"initial", self.state["active_model"], "selected", "selected-before", "selected-after", "final"}:
                continue
            if sha(item["path"]) != item["sha256"]:
                raise ValueError("frozen snapshot changed: " + name)
            saved = torch.load(item["path"], map_location="cpu", weights_only=True)
            self.snapshots[name] = {
                "weights": saved["weights"],
                "identity": item["sha256"],
            }
        if self.policy.base_fingerprints() != self.state["base_fingerprints"]:
            raise ValueError("frozen Base differs on process entry")
        self.progress()

    def signal(self, number, frame):
        self.stop = True
        self.signal_received = number

    def progress(self, **extra):
        if dd.rank() != 0:
            return
        atomic(self.directory / "state.json", self.state)
        atomic(
            self.directory / "progress.json",
            dict(
                at=time.time(),
                pid=os.getpid(),
                phase=self.state["phase"],
                round=self.state["round"],
                global_updates=(self.state.get("trainer") or {}).get(
                    "global_updates", 0
                ),
                remaining_seconds=self.clock.remaining(),
                checks=self.state["checks"],
                **extra,
            ),
        )

    def save(self, weights=None):
        result = save_checkpoint(
            self.directory,
            self.policy,
            self.optimizer,
            self.state,
            self.clock,
            weights=weights,
            calibration_optimizer=self.calibration_optimizer,
            frozen_buffer=self.buffer,
        )
        self.last_save = time.monotonic()
        self.progress()
        return result

    def store_snapshot(self, name):
        import torch
        path = self.directory / "snapshots" / f"{name}.pt"
        dd.assert_same(self.policy.trainable_fingerprints(), "snapshot weights")
        metadata = {"name": name, "clock": self.clock.record,
            "global_updates": (self.state.get("trainer") or {}).get("global_updates", 0)}
        record = None
        if dd.rank() == 0:
            if path.exists():
                saved = torch.load(path, map_location="cpu", weights_only=True)
                if saved["metadata"] != metadata or saved["fingerprints"] != self.policy.trainable_fingerprints():
                    raise ValueError("existing snapshot identity differs: " + name)
                if any(not torch.equal(saved["weights"][k], v) for k,v in self.policy.snapshot_weights().items()):
                    raise ValueError("snapshot tensors differ")
                record = {"path": str(path), "sha256": sha(path), "fingerprints": saved["fingerprints"]}
            else:
                record = self.policy.save_snapshot(path, metadata=metadata)
        record = shared(record)
        self.state["snapshot_paths"][name] = record
        self.snapshots[name] = {"weights": self.policy.snapshot_weights(), "identity": record["sha256"]}
        self.prune_snapshots(name)

    def prune_snapshots(self, active):
        # Every candidate stays on disk; serving needs only the current policy.
        for key in list(self.snapshots):
            if key.startswith("round-") and key != active:
                del self.snapshots[key]

    def activate(self, name):
        if name not in self.snapshots:
            import torch
            item = self.state["snapshot_paths"][name]
            if sha(item["path"]) != item["sha256"]:
                raise ValueError("stored candidate snapshot changed")
            saved = torch.load(item["path"], map_location="cpu", weights_only=True)
            self.snapshots[name] = {"weights": saved["weights"], "identity": item["sha256"]}
        self.prune_snapshots(name)
        self.policy.load_weights(self.snapshots[name]["weights"])
        self.state["active_model"] = name

    def transition(self, phase):
        before = self.state["phase"]
        self.state["phase"] = phase
        append(
            self.directory / "stage-events.jsonl",
            {
                "at": time.time(),
                "previous": before,
                "phase": phase,
                "round": self.state["round"],
                "global_updates": (self.state.get("trainer") or {}).get(
                    "global_updates", 0
                ),
            },
        )
        print(
            json.dumps(
                {"event": "stage", "phase": phase, "round": self.state["round"]},
                ensure_ascii=False,
            ),
            flush=True,
        )
        self.save()

    def rows(self, stage, *, model=None, round_id=None):
        return [
            r
            for r in self.schedule
            if r["stage"] == stage
            and (model is None or r["model"] == model)
            and (round_id is None or r["round"] == round_id)
        ]

    def collect(self, rows, budget):
        from .battle import collect
        assert_frozen(self.directory)
        active = self.state["active_model"]
        def tick():
            self.stop = dd.any_rank(self.stop)
            if shared(time.monotonic() - self.last_save >= 900):
                self.save(weights=self.snapshots[active]["weights"])
        def batch(values):
            return collect(self.directory, values, self.policy, self.snapshots,
                rank=dd.rank(), deadline=self.clock.deadline(budget),
                should_stop=lambda: self.stop, tick=tick,
                checkpoint_tick=lambda: self.save(weights=self.snapshots[active]["weights"]),
                global_update=(self.state.get("trainer") or {}).get("global_updates", 0))
        try:
            if rows and rows[0]["stage"] == "train" and rows[0]["round"] == 1 and not self.state["checks"].get("first_eight_audit"):
                first = batch(rows[:8])
                passed = len(first) == 8 and all(r.get("audit_passed") is True for r in first)
                receipt(self.directory / "verification/first-eight.json", {
                    "passed": passed, "outcomes": first,
                    "completed": sum(r["status"] == "completed" for r in first),
                    "decisions": len(decisions_for(self.directory, first))})
                if not passed:
                    raise ValueError("first eight integration audit failed")
                self.state["checks"]["first_eight_audit"] = True
                outcomes = first + batch(rows[8:])
            else:
                outcomes = batch(rows)
            self.stop = dd.any_rank(self.stop)
            self.progress(collection={"counts": dict(Counter(r["status"] for r in outcomes)),
                "stage": rows[0]["stage"] if rows else None})
            return outcomes
        finally:
            self.activate(active)

    def boundary(self, policy, optimizer, cursor):
        self.state["trainer"] = cursor
        if shared(time.monotonic() - self.last_save >= 900):
            self.save()
        return not self.stop

    def step(self, policy, optimizer, cursor, metrics):
        self.state["trainer"] = cursor
        append(
            self.directory / "updates.jsonl",
            dict(round=self.state["round"], at=time.time(), **metrics),
        )
        self.progress()
        if (
            cursor["global_updates"] == 1
            and not (self.directory / "verification/first-update.json").exists()
        ):
            current = policy.trainable_fingerprints()
            initial = self.state["before_training_fingerprints"]
            changed = {
                kind: any(current[n] != initial[n] for n in current if predicate(n))
                for kind, predicate in (
                    ("lora", lambda n: "lora_" in n),
                    ("action_head", lambda n: n.startswith("policy.model.head.")),
                    ("wdl_head", lambda n: n.startswith("wdl_head.")),
                )
            }
            base_ok = policy.base_fingerprints() == self.state["base_fingerprints"]
            if not base_ok or not all(changed.values()):
                raise ValueError(
                    "first optimizer update violated base/LoRA/head trainability"
                )
            atomic(
                self.directory / "verification/first-update.json",
                {
                    "passed": True,
                    "base_unchanged": True,
                    "changed": changed,
                    "metrics": metrics,
                },
                immutable=True,
            )
        if cursor["global_updates"] == 1 and not self.state["checks"].get("resume_validation"):
            self.state["restart_pending"] = True
            pointer = self.save()
            atomic(self.directory / "restart-pending.json", {"checkpoint_sha256": pointer["sha256"]}, immutable=True)
            synchronize()
            until = time.monotonic() + 60
            while not self.stop and time.monotonic() < until:
                time.sleep(.1)
            if not self.stop or self.signal_received != signal.SIGTERM:
                raise RuntimeError("supervisor did not deliver planned SIGTERM")
            _atomic(self.directory / f"restart-rank-{dd.rank()}.json", {
                "pid": os.getpid(), "rank": dd.rank(), "signal_received": True,
                "checkpoint_sha256": pointer["sha256"],
            }, immutable=True)
            return False
        self.boundary(policy, optimizer, cursor)
        return not self.stop

    def calibration_step(self, policy, optimizer, cursor, metrics):
        self.state["calibration_trainer"] = cursor
        append(
            self.directory / "calibration-updates.jsonl",
            dict(at=time.time(), **metrics),
        )
        if shared(time.monotonic() - self.last_save >= 900):
            self.save()
        return not self.stop

    def execute(self):
        import torch

        from . import trainer

        while not self.stop and self.state["phase"] != "finalize":
            phase = self.state["phase"]
            r = self.state["round"]
            if phase == "preflight":
                path = self.directory / "verification/preflight.json"
                report = (
                    read(path)
                    if shared(path.exists())
                    else trainer.preflight(
                        self.policy,
                        self.bc,
                            deadline=self.clock.deadline("policy"),
                        should_stop=lambda: self.stop,
                    )
                )
                if self.stop:
                    atomic(
                        self.directory
                        / f"verification/preflight-interrupted-{time.time_ns()}.json",
                        report,
                        immutable=True,
                    )
                    break
                receipt(path, report)
                if not report["passed"]:
                    raise RuntimeError("GPU preflight did not complete")
                self.state["checks"]["gpu_preflight"] = True
                self.transition("baseline_dev")
            elif phase == "baseline_dev":
                outcomes = self.collect(self.rows("dev", model="initial"), "policy")
                self.stop = dd.any_rank(self.stop)
                if self.stop:
                    break
                self.state["dev_attempted"].append(0)
                self.state["candidates"].append({"model": "initial", "round": 0, "outcomes": outcomes})
                self.transition("collect")
            elif phase == "collect":
                if not shared(self.clock.may_start("new_round")):
                    self.transition("select")
                    continue
                rows = self.rows("train", round_id=r)
                outcomes = self.collect(rows, "policy")
                self.stop = dd.any_rank(self.stop)
                if self.stop:
                    break
                gate = round_gate(outcomes, decisions_for(self.directory, outcomes))
                receipt(self.directory / f"rounds/round-{r}-gate.json", gate)
                if not gate["passed"] or not shared(self.clock.may_start("policy")):
                    self.transition("select")
                    continue
                self.state["before_training_fingerprints"] = (
                    self.policy.trainable_fingerprints()
                )
                from ..selfplay.objectives import eligible_decisions
                self.buffer = trainer.seeded_selection(
                    eligible_decisions(decisions_for(self.directory, outcomes), round_id=r),
                    config.PROTOCOL["round_samples"], namespace=f"rl-round-{r}")
                self.transition("train")
            elif phase == "train":
                rows = self.rows("train", round_id=r)
                outcomes = outcomes_for(self.directory, rows)
                result = trainer.train_round(
                    self.policy,
                    self.buffer,
                    self.bc,
                    round_id=r,
                    optimizer=self.optimizer,
                    state=self.state.get("trainer"),
                    deadline=self.clock.deadline("policy"),
                    should_stop=lambda: self.stop,
                    on_step=self.step,
                    on_boundary=self.boundary,
                )
                self.state["trainer"] = result["state"]
                self.stop = dd.any_rank(self.stop)
                if self.stop:
                    break
                receipt(
                    self.directory / f"rounds/round-{r}-training.json",
                    {"status": result["status"], "state": result["state"]},
                )
                if (
                    not result["state"]["complete"]
                    or result["state"]["round_updates"] == 0
                ):
                    self.transition("select")
                    continue
                if self.policy.base_fingerprints() != self.state["base_fingerprints"]:
                    raise ValueError("policy training changed frozen Base")
                name = f"round-{r}"
                self.store_snapshot(name)
                self.state["active_model"] = name
                self.state["checks"]["training"] = True
                self.state["last_completed_round"] = r
                if r == 1 or r % 4 == 0 or r == 128 or not shared(self.clock.may_start("new_round")):
                    self.transition("dev")
                else:
                    self.state["round"] += 1
                    self.transition("collect")
            elif phase == "dev":
                name = f"round-{r}"
                if r in self.state["dev_attempted"]:
                    raise ValueError("duplicate dev candidate attempt")
                if len(self.state["dev_attempted"]) >= 34:
                    raise ValueError("dev evaluation cap exceeded")
                outcomes = self.collect(self.rows("dev", model=name), "calibration")
                self.stop = dd.any_rank(self.stop)
                if self.stop:
                    break
                self.state["dev_attempted"].append(r)
                self.state["candidates"].append(
                    {"model": name, "round": r, "outcomes": outcomes}
                )
                if reporting.evaluation_complete(outcomes, expected_pairs=16):
                    self.state["checks"]["trained_candidate_dev"] = True
                if not self.state.get("finishing") and r < 128 and shared(self.clock.may_start("new_round")):
                    self.state["round"] += 1
                    self.transition("collect")
                else:
                    self.transition("select")
            elif phase == "select":
                self.state["finishing"] = True
                last = self.state["last_completed_round"]
                if last and last not in self.state["dev_attempted"] and shared(self.clock.may_start("calibration")):
                    self.state["round"] = last
                    self.activate(f"round-{last}")
                    self.transition("dev")
                    continue
                if not self.state["checks"].get("trained_candidate_dev"):
                    self.state["reason"] = "no_dev_completed_trained_candidate"
                    self.transition("finalize")
                    continue
                selected = reporting.select_policy(self.state["candidates"])
                receipt(self.directory / "selection.json", {"selection": selected})
                if selected is None:
                    self.state["reason"] = "no_dev_completed_trained_candidate"
                    self.transition("finalize")
                    continue
                self.state["selected"] = selected
                self.state["checks"]["policy_selection"] = True
                self.activate(selected["model"])
                # A selected alias is an immutable identity, not another trained candidate.
                self.store_snapshot("selected-before")
                self.state["selected_policy_fingerprints"] = self.policy.policy_fingerprints()
                self.snapshots["selected"] = dict(self.snapshots["selected-before"])
                self.state["snapshot_paths"]["selected"] = self.state["snapshot_paths"][
                    "selected-before"
                ]
                self.state["active_model"] = "selected"
                self.transition("calibration_collect")
            elif phase == "calibration_collect":
                outcomes = self.collect(self.rows("calibration"), "calibration")
                self.stop = dd.any_rank(self.stop)
                if self.stop:
                    break
                attempted = len(outcomes) == 64 and all(row["status"] == "completed" for row in outcomes)
                records = decisions_for(self.directory, outcomes)
                if (
                    not attempted
                    or not records
                    or not shared(self.clock.may_start("calibration"))
                ):
                    self.state["calibration_reason"] = "collection_incomplete"
                    self.transition("lock")
                    continue
                self.transition("calibration_features")
            elif phase == "calibration_features":
                outcomes = outcomes_for(self.directory, self.rows("calibration"))
                try:
                    records = trainer.extract_features(
                        self.policy,
                        decisions_for(self.directory, outcomes),
                        deadline=self.clock.deadline("calibration"),
                        should_stop=lambda: self.stop,
                    )
                except TimeoutError:
                    if self.stop:
                        break
                    self.state["calibration_reason"] = "features_incomplete"
                    self.transition("lock")
                    continue
                path = self.directory / "calibration-features.pt"
                if dd.rank() == 0:
                    import tempfile
                    fd, temporary = tempfile.mkstemp(prefix=".features-", dir=self.directory)
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            torch.save(records, stream)
                            stream.flush()
                            os.fsync(stream.fileno())
                        if path.exists():
                            # Never overwrite a prior feature cache, even one whose
                            # checkpoint pointer was not committed before a crash.
                            if trainer._feature_digest(torch.load(path, map_location="cpu", weights_only=True)) != trainer._feature_digest(records):
                                raise ValueError("preserved calibration cache differs")
                        else:
                            os.replace(temporary, path)
                    finally:
                        if os.path.exists(temporary):
                            os.unlink(temporary)
                synchronize()
                self.state["features_sha256"] = sha(path)
                self.calibration_optimizer = trainer.make_optimizer(
                    self.policy, calibration=True
                )
                self.transition("calibration_train")
            elif phase == "calibration_train":
                path = self.directory / "calibration-features.pt"
                if sha(path) != self.state["features_sha256"]:
                    raise ValueError("cached representation identity changed")
                records = torch.load(path, map_location="cpu", weights_only=True)
                if self.calibration_optimizer is None:
                    self.calibration_optimizer = trainer.make_optimizer(
                        self.policy, calibration=True
                    )
                result = trainer.train_head(
                    self.policy,
                    records,
                    optimizer=self.calibration_optimizer,
                    state=self.state.get("calibration_trainer"),
                    deadline=self.clock.deadline("calibration"),
                    should_stop=lambda: self.stop,
                    on_step=self.calibration_step,
                )
                self.state["calibration_trainer"] = result["state"]
                self.stop = dd.any_rank(self.stop)
                if self.stop:
                    break
                self.state["calibration_complete"] = result["state"]["complete"]
                if self.state["calibration_complete"]:
                    self.store_snapshot("selected-after")
                    receipt(
                        self.directory / "verification/calibration-policy.json",
                        {
                            "passed": True,
                            "policy_unchanged": result["policy_unchanged"],
                            "state": result["state"],
                        },
                    )
                    self.transition("calibration_dev")
                else:
                    self.state["calibration_reason"] = "training_incomplete"
                    self.transition("lock")
            elif phase == "calibration_dev":
                self.activate("selected-before")
                alternate = {
                    k.removeprefix("wdl_head."): v
                    for k, v in self.snapshots["selected-after"]["weights"].items()
                    if k.startswith("wdl_head.")
                }
                self.snapshots["selected"] = dict(
                    self.snapshots["selected-before"], alternate_head=alternate
                )
                self.state["active_model"] = "selected"
                outcomes = self.collect(self.rows("calibration_dev"), "calibration")
                self.stop = dd.any_rank(self.stop)
                if self.stop:
                    break
                decision = reporting.calibration_decision(
                    outcomes,
                    decisions_for(self.directory, outcomes),
                    training_complete=self.state["calibration_complete"],
                )
                self.state["calibration_decision"] = decision
                receipt(self.directory / "calibration-decision.json", decision)
                self.state["checks"]["calibration_decision"] = True
                self.state["checks"]["head_action_invariance"] = True
                self.transition("lock")
            elif phase == "lock":
                if not shared((self.directory / "calibration-decision.json").exists()):
                    decision = {
                        "adopt": False,
                        "head": "before",
                        "reason": self.state.get("calibration_reason", "incomplete"),
                    }
                    self.state["calibration_decision"] = decision
                    atomic(
                        self.directory / "calibration-decision.json",
                        decision,
                        immutable=True,
                    )
                synchronize()
                self.state["calibration_decision"] = read(self.directory / "calibration-decision.json")
                self.state["checks"]["calibration_decision"] = True
                self.state["checks"]["head_action_invariance"] = True
                adopt = self.state["calibration_decision"]["adopt"]
                self.activate("selected-after" if adopt else "selected-before")
                self.store_snapshot("final")
                if self.policy.policy_fingerprints() != self.state["selected_policy_fingerprints"]:
                    raise ValueError("head choice changed the action policy")
                receipt(
                    self.directory / "evaluation-lock.json",
                    {
                        "selected": self.state["selected"],
                        "final": self.state["snapshot_paths"]["final"],
                        "head": "after" if adopt else "before",
                        "clock": self.clock.record,
                        "schedule_sha256": sha(
                            self.directory / "prepared/schedule.json"
                        ),
                    },
                )
                self.transition("test_initial")
            elif phase in ("test_initial", "test_selected"):
                adopt = self.state["calibration_decision"]["adopt"]
                alternate_name = "selected-before" if adopt else "selected-after"
                alternate = (
                    {
                        k.removeprefix("wdl_head."): v
                        for k, v in self.snapshots[alternate_name]["weights"].items()
                        if k.startswith("wdl_head.")
                    }
                    if alternate_name in self.snapshots
                    else None
                )
                self.snapshots["selected"] = dict(
                    self.snapshots["final"],
                    primary_head="after" if adopt else "before",
                    alternate_head=alternate,
                )
                self.activate("final")
                model = "initial" if phase == "test_initial" else "selected"
                self.collect(self.rows("test", model=model), "test")
                self.stop = dd.any_rank(self.stop)
                if self.stop:
                    break
                self.transition(
                    "test_selected" if phase == "test_initial" else "finalize"
                )
            else:
                raise ValueError("unknown execution phase: " + phase)
        if self.stop:
            if self.state.get("restart_pending"):
                return 75
            self.save()
            return 130
        return 0


def run_worker(directory):
    dd.initialize(int(os.environ["LOCAL_RANK"]))
    try:
        runner = Runner(directory)
        return runner.execute()
    except BaseException as error:
        # Do not save a possibly partial collective update. The supervisor
        # stops every worker; only the last atomically committed step can resume.
        _atomic(Path(directory) / f"failure-rank-{dd.rank()}.json", {
            "at": time.time(), "rank": dd.rank(), "type": type(error).__name__,
            "detail": str(error), "traceback": traceback.format_exc(),
        })
        traceback.print_exc()
        return 1
    finally:
        dd.close()
