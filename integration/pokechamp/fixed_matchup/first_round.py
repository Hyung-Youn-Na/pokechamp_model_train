"""EX-078: exactly one audited self-play round, one checkpoint, then stop."""
from copy import deepcopy
import math
import os
from pathlib import Path
import shutil
import time

from . import artifacts
from .config import PROTOCOL as PARENT_PROTOCOL, ROOT
from .day import _check, _seal
from .prepare import prepare, verify_identity
from .runner import run_group
from .runtime import Clock, own_gpu, own_run
from .schedule import training
from .storage import atomic, digest, read, seed, sha

PROTOCOL = deepcopy(PARENT_PROTOCOL)
PROTOCOL.update(experiment="EX-078", max_rounds=1, pilot_games=0, dev_games=0,
                test_games=0, test_blocks=0, total_seconds=None, game_seconds=None,
                stage_seconds=dict(verify=None, pilot=None, train=None, test=None, finalize=None))
DEFAULT_OUTPUT = ROOT / ".pokechamp-data/experiments/ex078-fixed-matchup-first-round"
PARENT_IDENTITY = "27c6f836f7974539ed79aa6f46a0a278ecca587f5125e8d2872b7e50ebe332e0"
SETTING = dict(workers=16, batch_size=32)


def schedule():
    return dict(pilot=[], train=[training(1)], dev={}, test=[])


def prepare_first_round(parent, directory):
    """Validate the closed EX-077 parent; inherit P0/settings but no game or clock."""
    parent, directory = Path(parent).resolve(), Path(directory).resolve()
    if parent == directory or directory.is_relative_to(parent) or parent.is_relative_to(directory):
        raise ValueError("first round requires a separate directory")
    if directory.exists():
        raise FileExistsError("first round requires a new directory")
    manifest = read(parent / "manifest.json")
    if (digest({k: v for k, v in manifest.items() if k != "identity"}) != manifest["identity"]
            or manifest["identity"] != PARENT_IDENTITY or manifest["protocol"] != PARENT_PROTOCOL):
        raise ValueError("unapproved or corrupted EX-077 parent identity/protocol")
    for name, checksum in manifest["sources"].items():
        _check(parent, "source/" + name, checksum)
    for name, checksum in manifest["files"].items():
        _check(parent, name, checksum)
    for team in manifest["teams"].values():
        _check(parent, "teams/" + team["file"], team["sha256"])
    sealed, closure = _seal(parent, "evidence.sha256"), _seal(parent, "closure.sha256")
    if any(name in sealed and sealed[name] != value for name, value in closure.items()):
        raise ValueError("parent seals disagree")
    sealed.update(closure)
    required = ("manifest.json", "incomplete.json", "models/P0.pt", "models/P0.identity.json",
                "settings.json", "catalog.json", "schedule.json")
    if any(name not in sealed for name in required):
        raise ValueError("parent seal omitted required inheritance evidence")
    closed = read(parent / "incomplete.json")
    if (closed.get("status") != "incomplete" or closed.get("reason") != "user_requested_stop"
            or not closed.get("gpu_released") or any(closed.get(key) != 0 for key in
                ("training_games", "training_updates", "test_games"))):
        raise ValueError("parent must be user-stopped before training/test")
    if (list((parent / "checkpoints").glob("*.pt")) or (parent / "evaluation-lock.json").exists()
            or any(p.name != "P0.pt" for p in (parent / "models").glob("*.pt"))):
        raise ValueError("cannot inherit trained parent")
    for path in (parent / "games").glob("*/result.json"):
        if read(path)["job"]["stage"] != "pilot":
            raise ValueError("parent contains non-pilot games")
    for path in (parent / "claims").glob("*.json"):
        if read(path)["job"]["stage"] != "pilot":
            raise ValueError("parent contains non-pilot reservations")
    p0_hash = sha(parent / "models/P0.pt")
    if read(parent / "models/P0.identity.json") != dict(identity=manifest["identity"], sha256=p0_hash):
        raise ValueError("parent P0 identity mismatch")
    if read(parent / "settings.json") != SETTING:
        raise ValueError("only approved worker16/batch32 setting may be inherited")
    current = prepare(directory, protocol=PROTOCOL, schedule=schedule())
    if current["teams"] != manifest["teams"] or sha(parent / "catalog.json") != sha(directory / "catalog.json"):
        raise ValueError("inherited model teams/vocabulary changed")
    (directory / "models").mkdir()
    shutil.copy2(parent / "models/P0.pt", directory / "models/P0.pt")
    _check(directory, "models/P0.pt", p0_hash)
    atomic(directory / "settings.json", SETTING, exclusive=True)
    linkage = dict(approval="D-123", parent=str(parent), parent_identity=manifest["identity"],
        parent_manifest_sha256=sha(parent / "manifest.json"), parent_protocol=manifest["protocol"],
        parent_seals={name: sha(parent / name) for name in ("evidence.sha256", "closure.sha256")},
        parent_sources=manifest["sources"], parent_files=manifest["files"], parent_evidence=sealed,
        p0_sha256=p0_hash, settings=SETTING, inherited_games=[], retries=0,
        clock_policy="first_gpu_verification_timestamp_no_wallclock_limit")
    atomic(directory / "first-round-inheritance.json", linkage, exclusive=True)
    current.pop("identity")
    current["files"].update({name: sha(directory / name) for name in
                            ("models/P0.pt", "settings.json", "first-round-inheritance.json")})
    current["first_round_inheritance"] = linkage
    current["identity"] = digest(current)
    atomic(directory / "manifest.json", current)
    return current


def validate_checkpoint(directory, manifest, policy, payload, replay, *, check=lambda: None):
    """Re-read the exported model and compare predictions for every training observation."""
    import torch
    from .model import Policy
    directory = Path(directory)
    if (payload["round"] != 1 or payload["updates"] <= 0 or not payload["optimizer"]["state"]
            or payload["replay_ids"] != [r["id"] for r in replay]
            or len(set(payload["replay_ids"])) != len(replay)
            or payload["clock"] != read(directory / "clock.json")
            or payload["identity"] != manifest["identity"]):
        raise ValueError("round1 checkpoint is incomplete")
    def finite(value):
        if torch.is_tensor(value):
            return bool(torch.isfinite(value).all())
        if isinstance(value, dict):
            return all(finite(v) for v in value.values())
        if isinstance(value, (list, tuple)):
            return all(finite(v) for v in value)
        return not isinstance(value, float) or math.isfinite(value)
    if not finite(payload):
        raise ValueError("nonfinite checkpoint state")
    initial = Policy.load(directory / "models/P0.pt")
    changed = sum(not torch.equal(tensor.detach().cpu(), initial.state_dict()[key])
                  for key, tensor in policy.state_dict().items())
    if not changed:
        raise ValueError("round1 weights did not change")
    fresh = Policy.load(directory / "models/round-001.pt", policy.device)
    maximum = 0.0
    for offset in range(0, len(replay), 32):
        check()
        observations = [r["observation"] for r in replay[offset:offset + 32]]
        expected, actual = policy.evaluate_batch(observations), fresh.evaluate_batch(observations)
        for left, right in zip(expected, actual):
            maximum = max(maximum, abs(left["value"] - right["value"]),
                          *(abs(a - b) for a, b in zip(left["policy"], right["policy"])))
    if maximum > 1e-5:
        raise ValueError("round1 stored-model reload predictions disagree")
    pointer = artifacts.committed_pointer(directory)
    receipt = dict(passed=True, identity=manifest["identity"], round=1, updates=payload["updates"],
        checkpoint=pointer, model_sha256=sha(directory / "models/round-001.pt"),
        p0_sha256=sha(directory / "models/P0.pt"), replay_ids_sha256=digest(payload["replay_ids"]),
        observations=len(replay), changed_tensors=changed, finite=True,
        prediction_max_absolute_error=maximum, tolerance=1e-5,
        optimizer_states=len(payload["optimizer"]["state"]), learning=payload["learning"])
    atomic(directory / "checkpoint-validation.json", receipt)
    return receipt


def train_first_round(directory, manifest, teams, clock, setting):
    import torch
    from .model import Policy, learn
    from .finalize import audit_game
    directory = Path(directory)
    if read(directory / "schedule.json") != schedule() or setting != SETTING:
        raise ValueError("one-round schedule/settings changed")
    clock.enter("train")
    policy = Policy.load(directory / "models/P0.pt", "cuda:0")
    optimizer = torch.optim.AdamW(policy.parameters(), lr=PROTOCOL["lr"], weight_decay=PROTOCOL["weight_decay"])
    generator = torch.Generator().manual_seed(seed("optimizer-shuffle"))
    if artifacts.committed_pointer(directory) is None:
        artifacts.save_checkpoint(directory, 0, policy, optimizer, generator,
                                  identity=manifest["identity"], replay_ids=[], updates=0)
    checkpoint = artifacts.restore_checkpoint(directory, policy, optimizer, generator, identity=manifest["identity"])
    if checkpoint["round"] not in (0, 1):
        raise ValueError("only round0/round1 checkpoints belong to this diagnostic")
    jobs = schedule()["train"][0]
    if checkpoint["round"] == 0:
        rows = run_group(directory, jobs, teams, {"current": policy}, clock, setting,
                         {"current": "models/P0.pt"})
    else:
        rows, pending = artifacts.existing(directory, jobs)
        if pending:
            raise ValueError("committed round1 lacks its training games")
    if (len(rows) != 32 or any(r["status"] != "completed" for r in rows)
            or {r["job"]["slot_id"] for r in rows} != {j["slot_id"] for j in jobs}):
        raise RuntimeError("all 32 normal games required; no retry or partial-round learning")
    for row in rows:
        clock.check()
        if row.get("model_hashes") != {"current": sha(directory / "models/P0.pt")}:
            raise ValueError("round1 game did not use the frozen P0")
        audit_game(directory / "games" / row["job"]["slot_id"])
    replay = artifacts.replay_rows(directory, 1)
    if not replay:
        raise ValueError("empty round1 replay")
    if checkpoint["round"] == 0:
        learning = learn(policy, optimizer, replay, generator=generator, check=clock.check,
                         batch_size=PROTOCOL["batch"], epochs=PROTOCOL["epochs"], max_steps=PROTOCOL["max_steps"])
        if learning["steps"] <= 0:
            raise ValueError("round1 made no learning updates")
        artifacts.save_checkpoint(directory, 1, policy, optimizer, generator, identity=manifest["identity"],
            replay_ids=[r["id"] for r in replay], updates=learning["steps"], learning=learning)
        checkpoint = artifacts.restore_checkpoint(directory, policy, optimizer, generator, identity=manifest["identity"])
    artifacts.publish_round(directory, checkpoint)
    return validate_checkpoint(directory, manifest, policy, checkpoint, replay, check=clock.check)


def run_first_round(directory):
    directory = Path(directory)
    manifest = verify_identity(directory, protocol=PROTOCOL)
    if any((directory / name).exists() for name in ("completed.json", "incomplete.json")):
        raise RuntimeError("diagnostic already closed; no automatic additional cycle")
    if read(directory / "schedule.json") != schedule():
        raise ValueError("diagnostic schedule changed")
    teams = {key: (directory / "teams" / row["file"]).read_text() for key, row in manifest["teams"].items()}
    with own_run(directory), own_gpu(directory):
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        import torch
        from .verification import verify
        from .finalize import finalize
        if torch.cuda.is_initialized():
            raise RuntimeError("CUDA was initialized before owned resource binding")
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.cuda.set_per_process_memory_fraction(PROTOCOL["gpu_bytes"] / torch.cuda.get_device_properties(0).total_memory)
        clock = Clock(directory, protocol=PROTOCOL)
        with clock.signals():
            try:
                if not (directory / "verification.json").exists():
                    clock.enter("verify")
                    verification = verify(device="cuda:0")
                    clock.check()
                    atomic(directory / "verification.json", dict(verification, identity=manifest["identity"]), exclusive=True)
                verification = read(directory / "verification.json")
                if not verification.get("passed") or verification["identity"] != manifest["identity"]:
                    raise ValueError("verification receipt invalid")
                p0 = artifacts.initial_model(directory, read(directory / "catalog.json")["vocabulary"],
                                             manifest["identity"], "cuda:0")
                del p0
                validation = train_first_round(directory, manifest, teams, clock, read(directory / "settings.json"))
                clock.enter("finalize")
                result = finalize(directory, check=clock.check, protocol=PROTOCOL)
                clock.check()
                complete = (validation["passed"] and result["audit"]["passed"]
                            and result["audit"]["normal_games"] == result["audit"]["games"] == 32
                            and result["audit"]["browser"]["passed"])
                result.update(procedure_complete=complete, diagnostic_complete=complete, efficacy_success=False)
                atomic(directory / ("completed.json" if complete else "incomplete.json"),
                       dict(result, identity=manifest["identity"], at=time.time(),
                            elapsed=time.time() - clock.first, peak_rss=clock.peak_rss), exclusive=True)
                return result
            except BaseException as error:
                atomic(directory / "stops" / f"{time.time_ns()}.json", dict(stage=clock.stage,
                    reason=f"{type(error).__name__}: {error}", at=time.time(), first=clock.first,
                    elapsed=time.time() - clock.first), exclusive=True)
                try:
                    artifacts.existing(directory, schedule()["train"][0])
                    if (directory / "games").exists() and not clock.cancelled:
                        clock.enter("finalize")
                        finalize(directory, check=clock.check, protocol=PROTOCOL)
                except Exception as cleanup_error:
                    atomic(directory / "stops" / f"{time.time_ns()}-finalization.json",
                           dict(reason=f"{type(cleanup_error).__name__}: {cleanup_error}"), exclusive=True)
                raise
