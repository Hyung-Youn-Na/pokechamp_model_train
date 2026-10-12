"""Frozen EX-072 stage machine; collection and learning share one owned GPU."""

from __future__ import annotations

import json
import os
import signal
import time
import traceback
from collections import Counter
from pathlib import Path

from . import config, reporting
from .execution import assert_frozen, load_checkpoint, save_checkpoint
from .storage import Clock, append, atomic, jsonl, read, sha


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
        from .model import SelfPlayPolicy
        from .trainer import make_optimizer

        self.directory = Path(directory)
        self.clock = Clock(directory, start=True)
        self.stop = False
        self.signal_received = None
        signal.signal(signal.SIGTERM, self.signal)
        signal.signal(signal.SIGINT, self.signal)
        assert_frozen(directory)
        seed_all(config.SEED)
        self.policy = SelfPlayPolicy(checkpoint=config.INITIAL)
        self.optimizer = make_optimizer(self.policy)
        self.calibration_optimizer = None
        self.snapshots = {}
        self.schedule = read(self.directory / "prepared/schedule.json")
        self.bc = list(jsonl(self.directory / "prepared/bc.jsonl"))
        self.state = {
            "phase": "preflight",
            "round": 1,
            "active_model": "initial",
            "trainer": None,
            "checks": {"cpu_validation": True},
            "candidates": [],
            "snapshot_paths": {},
            "calibration_complete": False,
            "selected": None,
        }
        self.last_save = time.monotonic()
        if (self.directory / "latest.json").exists():
            payload = load_checkpoint(
                directory, self.policy, self.optimizer, self.clock
            )
            self.state = payload["state"]
            if payload.get("calibration_optimizer") is not None:
                self.calibration_optimizer = make_optimizer(
                    self.policy, calibration=True
                )
                self.calibration_optimizer.load_state_dict(
                    payload["calibration_optimizer"]
                )
            proof = self.directory / "restart-request.json"
            if self.state.get("restart_pending"):
                request = read(proof)
                pointer = read(self.directory / "latest.json")
                if (
                    request["pid"] == os.getpid()
                    or not request["signal_received"]
                    or request["checkpoint_sha256"] != pointer["sha256"]
                ):
                    raise ValueError(
                        "restart does not identify a new process and original checkpoint"
                    )
                self.state["checks"]["resume_validation"] = True
                self.state["restart_pending"] = False
                atomic(
                    self.directory / "verification/resume.json",
                    {
                        "passed": True,
                        "original_pid": request["pid"],
                        "resumed_pid": os.getpid(),
                        "checkpoint": pointer,
                        "clock": self.clock.record,
                        "completed_updates": self.state["trainer"]["global_updates"],
                        "optimizer_states": len(self.optimizer.state),
                    },
                    immutable=True,
                )
        else:
            self.state["base_fingerprints"] = self.policy.base_fingerprints()
            self.store_snapshot("initial")
            self.save()
        for name, item in self.state["snapshot_paths"].items():
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
        )
        self.last_save = time.monotonic()
        self.progress()
        return result

    def store_snapshot(self, name):
        import torch

        from .model import MODEL_CONFIG

        path = self.directory / "snapshots" / f"{name}.pt"
        metadata = {
            "name": name,
            "clock": self.clock.record,
            "global_updates": (self.state.get("trainer") or {}).get(
                "global_updates", 0
            ),
        }
        if path.exists():
            saved = torch.load(path, map_location="cpu", weights_only=True)
            if (
                saved["model_config"] != MODEL_CONFIG
                or saved["metadata"] != metadata
                or saved["fingerprints"] != self.policy.trainable_fingerprints()
            ):
                raise ValueError(
                    "existing snapshot has a different completed state: " + name
                )
            current = self.policy.snapshot_weights()
            if set(saved["weights"]) != set(current) or any(
                not torch.equal(saved["weights"][k], v) for k, v in current.items()
            ):
                raise ValueError("existing snapshot tensors differ: " + name)
            record = {
                "path": str(path),
                "sha256": sha(path),
                "fingerprints": saved["fingerprints"],
            }
        else:
            record = self.policy.save_snapshot(path, metadata=metadata)
        self.state["snapshot_paths"][name] = record
        self.snapshots[name] = {
            "weights": self.policy.snapshot_weights(),
            "identity": record["sha256"],
        }

    def activate(self, name):
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
        from .battle import match
        from .serving import Service

        assert_frozen(self.directory)
        active = self.state["active_model"]
        existing = {r["slot_id"]: r for r in outcomes_for(self.directory, rows)}
        try:
            with Service(self.policy, self.snapshots, port=config.PORT) as service:

                def tick():
                    if time.monotonic() - self.last_save >= 900:
                        # The serving module may temporarily hold an opponent's
                        # weights. Checkpoint the immutable learner instead.
                        self.save(weights=self.snapshots[active]["weights"])

                for row in rows:
                    if existing[row["slot_id"]]["status"] != "unattempted":
                        continue
                    if self.stop or not self.clock.may_start(budget):
                        break
                    own = row["model"]
                    opponent = row["opponent"]
                    if opponent in ("current", "snapshot"):
                        index = row["opponent_snapshot_index"]
                        other = "initial" if index == 0 else f"round-{index}"
                        opponent_actor = ("model", other)
                    elif opponent == "initial":
                        opponent_actor = ("model", "initial")
                    else:
                        opponent_actor = ("bot", opponent)
                    models = {
                        row["model_side"]: ("model", own),
                        ("p2" if row["model_side"] == "p1" else "p1"): opponent_actor,
                    }
                    outcome = match(
                        self.directory / "games" / row["slot_id"],
                        row,
                        service,
                        models,
                        deadline=self.clock.deadline(budget),
                        should_stop=lambda: self.stop,
                        tick=tick,
                    )
                    existing[row["slot_id"]] = outcome
                    append(
                        self.directory / "battle-events.jsonl",
                        {"at": time.time(), "outcome": outcome},
                    )
                    self.progress(
                        collection={
                            "stage": row["stage"],
                            "round": row["round"],
                            "model": row["model"],
                            "counts": dict(
                                Counter(r["status"] for r in existing.values())
                            ),
                        }
                    )
                    if outcome.get("failure_scope") == "phase":
                        raise RuntimeError(
                            "shared battle defect: "
                            + row["slot_id"]
                            + " "
                            + str(outcome)
                        )
                    if row["stage"] == "train" and row["round"] == 1:
                        first = rows[:8]
                        first_results = [existing[r["slot_id"]] for r in first]
                        if all(
                            r["status"] != "unattempted" for r in first_results
                        ) and not self.state["checks"].get("first_eight_audit"):
                            normal = [
                                r for r in first_results if r["status"] == "completed"
                            ]
                            passed = bool(normal) and all(
                                r.get("audit_passed") is True for r in first_results
                            )
                            proof = {
                                "passed": passed,
                                "outcomes": first_results,
                                "completed": len(normal),
                                "failed_or_incomplete": 8 - len(normal),
                                "decisions": len(
                                    decisions_for(self.directory, first_results)
                                ),
                            }
                            receipt(
                                self.directory / "verification/first-eight.json", proof
                            )
                            if not passed:
                                self.state["reason"] = (
                                    "first_eight_trace_validation_incomplete"
                                )
                                break
                            self.state["checks"]["first_eight_audit"] = True
                            print(
                                json.dumps(
                                    {
                                        "event": "first_eight_audit",
                                        "passed": True,
                                        "decisions": proof["decisions"],
                                    }
                                ),
                                flush=True,
                            )
                    tick()
        finally:
            self.activate(active)
        return [existing[r["slot_id"]] for r in rows]

    def boundary(self, policy, optimizer, cursor):
        self.state["trainer"] = cursor
        if time.monotonic() - self.last_save >= 900:
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
        request = self.directory / "restart-request.json"
        if cursor["global_updates"] == 1 and not request.exists():
            self.state["restart_pending"] = True
            self.save()
            os.kill(os.getpid(), signal.SIGTERM)
            atomic(
                request,
                {
                    "pid": os.getpid(),
                    "at": time.time(),
                    "signal_received": self.signal_received == signal.SIGTERM,
                    "checkpoint_sha256": read(self.directory / "latest.json")["sha256"],
                },
                immutable=True,
            )
            return False
        self.boundary(policy, optimizer, cursor)
        return not self.stop

    def calibration_step(self, policy, optimizer, cursor, metrics):
        self.state["calibration_trainer"] = cursor
        append(
            self.directory / "calibration-updates.jsonl",
            dict(at=time.time(), **metrics),
        )
        if time.monotonic() - self.last_save >= 900:
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
                    if path.exists()
                    else trainer.preflight(
                        self.policy,
                        self.bc,
                        max_samples=32,
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
                self.collect(self.rows("dev", model="initial"), "policy")
                if self.stop:
                    break
                self.transition("collect")
            elif phase == "collect":
                rows = self.rows("train", round_id=r)
                outcomes = self.collect(rows, "policy")
                if self.stop:
                    break
                gate = round_gate(outcomes, decisions_for(self.directory, outcomes))
                receipt(self.directory / f"rounds/round-{r}-gate.json", gate)
                if not gate["passed"] or not self.clock.may_start("policy"):
                    self.transition("select")
                    continue
                self.state["before_training_fingerprints"] = (
                    self.policy.trainable_fingerprints()
                )
                self.transition("train")
            elif phase == "train":
                rows = self.rows("train", round_id=r)
                outcomes = outcomes_for(self.directory, rows)
                result = trainer.train_round(
                    self.policy,
                    decisions_for(self.directory, outcomes),
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
                self.transition("dev")
            elif phase == "dev":
                name = f"round-{r}"
                outcomes = self.collect(self.rows("dev", model=name), "policy")
                if self.stop:
                    break
                self.state["candidates"].append(
                    {"model": name, "round": r, "outcomes": outcomes}
                )
                if r < 4 and self.clock.may_start("policy"):
                    self.state["round"] += 1
                    self.transition("collect")
                else:
                    self.transition("select")
            elif phase == "select":
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
                self.snapshots["selected"] = dict(self.snapshots["selected-before"])
                self.state["snapshot_paths"]["selected"] = self.state["snapshot_paths"][
                    "selected-before"
                ]
                self.state["active_model"] = "selected"
                self.transition("calibration_collect")
            elif phase == "calibration_collect":
                outcomes = self.collect(self.rows("calibration"), "calibration")
                if self.stop:
                    break
                attempted = all(row["status"] != "unattempted" for row in outcomes)
                records = decisions_for(self.directory, outcomes)
                if (
                    not attempted
                    or not records
                    or not self.clock.may_start("calibration")
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
                torch.save(records, path)
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
                if self.stop:
                    break
                decision = reporting.calibration_decision(
                    outcomes,
                    decisions_for(self.directory, outcomes),
                    training_complete=self.state["calibration_complete"],
                )
                self.state["calibration_decision"] = decision
                receipt(self.directory / "calibration-decision.json", decision)
                self.state["checks"]["calibration_decision"] = (
                    reporting.evaluation_complete(outcomes, expected_pairs=4)
                )
                self.transition("lock")
            elif phase == "lock":
                if not (self.directory / "calibration-decision.json").exists():
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
                adopt = self.state["calibration_decision"]["adopt"]
                self.activate("selected-after" if adopt else "selected-before")
                self.store_snapshot("final")
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
                if self.stop:
                    break
                self.transition(
                    "test_selected" if phase == "test_initial" else "finalize"
                )
            else:
                raise ValueError("unknown execution phase: " + phase)
        if self.stop:
            pointer = self.save()
            if self.state.get("restart_pending"):
                request = read(self.directory / "restart-request.json")
                request.update(
                    checkpoint_sha256=pointer["sha256"],
                    signal_received=self.signal_received == signal.SIGTERM,
                )
                atomic(self.directory / "restart-request.json", request)
                print(
                    json.dumps({"event": "planned_sigterm", "checkpoint": pointer}),
                    flush=True,
                )
                return 75
            return 130
        return 0


def run_worker(directory):
    runner = None
    try:
        runner = Runner(directory)
        code = runner.execute()
        if code:
            return code
    except BaseException as error:  # noqa: BLE001 -- record boundary failure before owned-resource cleanup
        atomic(
            Path(directory) / "failure.json",
            {
                "at": time.time(),
                "type": type(error).__name__,
                "detail": str(error),
                "traceback": traceback.format_exc(),
            },
        )
        if runner is not None:
            runner.state["failure"] = {
                "type": type(error).__name__,
                "detail": str(error),
            }
            try:
                if all(p.grad is None for p in runner.policy.parameters()):
                    runner.save()
                else:
                    runner.progress(
                        checkpoint_deferred="unfinished gradient calculation"
                    )
            except Exception as checkpoint_error:  # noqa: BLE001 -- preserve the original and checkpoint failures
                atomic(
                    Path(directory) / "checkpoint-failure.json",
                    {
                        "original": str(error),
                        "checkpoint_error": str(checkpoint_error),
                        "at": time.time(),
                    },
                )
        traceback.print_exc()
        return 1
    return 0
