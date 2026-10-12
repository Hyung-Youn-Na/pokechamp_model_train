"""D-125: preserve 31 audited games and checkpoint state; admit one failed slot once."""
from copy import deepcopy
import io
from pathlib import Path
import shutil

from . import first_round
from .config import ROOT
from .day import _check, _seal
from .finalize import audit_game
from .prepare import prepare
from .storage import atomic, atomic_bytes, digest, read, sha

PARENT_IDENTITY = "5cae56015b43256e6adcc7d7d3f49216ff3b118a6e7d526e4046adddcc774000"
PARENT_DIRECTORY = ROOT / ".pokechamp-data/experiments/ex078-fixed-matchup-first-round"
FAILED_SLOT = "train-1-selfplay-001-B-p2"
CRITICAL_SOURCES = tuple("integration/pokechamp/fixed_matchup/" + name for name in
    ("model.py", "search.py", "simulator.py", "simulator.cjs", "observation.cjs", "public_state.cjs"))


def _same(left, right):
    """Exact recursive comparison, including optimizer and all RNG tensors."""
    import torch
    if torch.is_tensor(left):
        return torch.is_tensor(right) and left.dtype == right.dtype and left.shape == right.shape and torch.equal(left, right)
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def prepare_single_retry(parent, directory):
    """Validate the immutable parent before preparing a separate one-slot continuation."""
    import torch
    parent, directory = Path(parent).resolve(), Path(directory).resolve()
    if parent != PARENT_DIRECTORY.resolve():
        raise ValueError("only the approved EX-078 parent directory may be inherited")
    if parent == directory or directory.is_relative_to(parent) or parent.is_relative_to(directory):
        raise ValueError("recovery requires a separate directory")
    if directory.exists():
        raise FileExistsError("recovery requires a new directory")
    manifest = read(parent / "manifest.json")
    old_protocol = deepcopy(first_round.PROTOCOL)
    old_protocol.update(game_seconds=1200, total_seconds=28800,
        stage_seconds=dict(verify=3600, pilot=0, train=21600, test=0, finalize=3600))
    if (manifest["identity"] != PARENT_IDENTITY
            or digest({k: v for k, v in manifest.items() if k != "identity"}) != PARENT_IDENTITY
            or manifest["protocol"] != old_protocol):
        raise ValueError("unapproved parent identity/protocol")
    for name, checksum in manifest["sources"].items():
        _check(parent, "source/" + name, checksum)
    for name, checksum in manifest["files"].items():
        _check(parent, name, checksum)
    for team in manifest["teams"].values():
        _check(parent, "teams/" + team["file"], team["sha256"])
    for name in CRITICAL_SOURCES:
        if name not in manifest["sources"] or sha(ROOT / name) != manifest["sources"][name]:
            raise ValueError("model/search/state implementation changed: " + name)
    for name, checksum in manifest["sources"].items():
        if name.startswith("pokemon-showdown/") and sha(ROOT / name) != checksum:
            raise ValueError("battle simulator implementation changed: " + name)
    sealed, closure = _seal(parent, "evidence.sha256"), _seal(parent, "closure.sha256")
    if any(name in sealed and sealed[name] != value for name, value in closure.items()):
        raise ValueError("parent seals disagree")
    sealed.update(closure)
    required = {"manifest.json", "incomplete.json", "catalog.json", "schedule.json", "clock.json",
        "settings.json", "models/P0.pt", "models/P0.identity.json", "latest.json",
        "checkpoints/round-000.pt", "checkpoints/round-000.json"}
    closed = read(parent / "incomplete.json")
    if (closed.get("status") != "incomplete" or closed.get("reason") != "one_game_wallclock_timeout_before_learning"
            or closed.get("normal_games") != 31 or closed.get("incomplete_games") != 1
            or closed.get("training_updates") != 0 or closed.get("checkpoint_round") != 0
            or closed.get("original_identity") != PARENT_IDENTITY or not closed.get("gpu_released")):
        raise ValueError("parent must be the closed 31-normal/one-timeout prelearning run")
    if (read(parent / "schedule.json") != first_round.schedule()
            or read(parent / "settings.json") != first_round.SETTING):
        raise ValueError("parent schedule/settings changed")
    if (sorted(p.name for p in (parent / "checkpoints").iterdir()) != ["round-000.json", "round-000.pt"]
            or sorted(p.name for p in (parent / "models").glob("*.pt")) != ["P0.pt"]
            or (parent / "evaluation-lock.json").exists() or (parent / "completed.json").exists()):
        raise ValueError("parent contains trained or unexpected checkpoints")
    p0_hash = sha(parent / "models/P0.pt")
    if read(parent / "models/P0.identity.json") != dict(identity=PARENT_IDENTITY, sha256=p0_hash):
        raise ValueError("parent P0 identity mismatch")
    pointer = dict(file="checkpoints/round-000.pt", round=0, sha256=sha(parent / "checkpoints/round-000.pt"))
    if read(parent / "latest.json") != pointer or read(parent / "checkpoints/round-000.json") != pointer:
        raise ValueError("parent checkpoint pointer changed")
    payload = torch.load(parent / pointer["file"], map_location="cpu", weights_only=True)
    clock = read(parent / "clock.json")
    p0 = torch.load(parent / "models/P0.pt", map_location="cpu", weights_only=True)
    if (payload["round"] != 0 or payload["updates"] != 0 or payload["replay_ids"] != []
            or payload["optimizer"]["state"] or payload["identity"] != PARENT_IDENTITY
            or payload["clock"] != clock or clock.get("total") != 28800
            or not _same(payload["model"], p0)):
        raise ValueError("parent checkpoint is not the complete untrained P0 state")
    if not {"generator", "torch_rng", "python_rng", "cuda_rng", "learning"} <= payload.keys():
        raise ValueError("parent checkpoint lacks complete RNG/state")
    jobs = first_round.schedule()["train"][0]
    slots = {j["slot_id"] for j in jobs}
    if ({p.name for p in (parent / "games").iterdir()} != slots
            or {p.name for p in (parent / "claims").iterdir()} != {s + ".json" for s in slots}):
        raise ValueError("parent must contain exactly the original 32 game/claim slots")
    inherited, copied = [], []
    for job in jobs:
        slot = job["slot_id"]
        base = parent / "games" / slot
        row = read(base / "result.json")
        claim_name = "claims/" + slot + ".json"
        if (row["job"] != job or read(parent / claim_name)["job"] != job
                or row.get("model_hashes") != {"current": p0_hash}):
            raise ValueError("parent game/claim/model mismatch: " + slot)
        names = [str(p.relative_to(parent)) for p in base.rglob("*") if p.is_file()]
        required.update(names + [claim_name])
        if slot == FAILED_SLOT:
            if (row.get("status") != "incomplete" or row.get("reason") != "game/stage deadline or cancellation"
                    or row.get("turns") != 143 or row.get("metrics", {}).get("seconds", 0) < 1200):
                raise ValueError("only the original 143-turn timeout may be retried")
            from .artifacts import load_result
            load_result(base)
        else:
            if row.get("status") != "completed":
                raise ValueError("all other 31 games must be completed")
            audit_game(base)
            inherited.append(slot)
            copied.extend(names + [claim_name])
    if not required <= sealed.keys():
        raise ValueError("parent seal omitted required inheritance evidence")
    if len(inherited) != 31:
        raise ValueError("exactly 31 games must be inherited")
    current = prepare(directory, protocol=first_round.PROTOCOL, schedule=first_round.schedule())
    if current["teams"] != manifest["teams"] or sha(directory / "catalog.json") != sha(parent / "catalog.json"):
        raise ValueError("inherited teams/vocabulary changed")
    copied += ["models/P0.pt", "settings.json"]
    if (parent / "resource.json").exists():
        if "resource.json" not in sealed or read(parent / "resource.json").get("index") != 0:
            raise ValueError("parent resource must be the sealed physical GPU0")
        copied.append("resource.json")
    for name in copied:
        destination = directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(parent / name, destination)
        _check(directory, name, sealed[name])
    new_clock = dict(clock, total=None)
    atomic(directory / "clock.json", new_clock, exclusive=True)
    linkage = dict(approval="D-125", parent=str(parent), parent_identity=PARENT_IDENTITY,
        parent_manifest_sha256=sha(parent / "manifest.json"), parent_sources=manifest["sources"],
        parent_files=manifest["files"], parent_evidence=sealed,
        parent_seals={n: sha(parent / n) for n in ("evidence.sha256", "closure.sha256")},
        parent_checkpoint=pointer, parent_clock=clock, inherited_games=sorted(inherited),
        failed_slot=FAILED_SLOT, retry_limit=1, retries=1, p0_sha256=p0_hash,
        clock_policy="preserve_original_start_remove_wallclock_limits",
        checkpoint_changes=["identity", "clock"], parent_protocol=old_protocol)
    atomic(directory / "first-round-recovery.json", linkage, exclusive=True)
    current.pop("identity")
    current["files"].update({n: sha(directory / n) for n in copied + ["clock.json", "first-round-recovery.json"]})
    current["first_round_recovery"] = linkage
    current["identity"] = digest(current)
    atomic(directory / "manifest.json", current)
    rebound = dict(payload, identity=current["identity"], clock=new_clock)
    stream = io.BytesIO()
    torch.save(rebound, stream)
    atomic_bytes(directory / pointer["file"], stream.getvalue(), exclusive=True)
    restored = torch.load(directory / pointer["file"], map_location="cpu", weights_only=True)
    if not _same(restored, rebound):
        raise ValueError("rebound checkpoint state changed on serialization")
    new_pointer = dict(pointer, sha256=sha(directory / pointer["file"]))
    atomic(directory / "checkpoints/round-000.json", new_pointer, exclusive=True)
    atomic(directory / "latest.json", new_pointer, exclusive=True)
    atomic(directory / "models/P0.identity.json", dict(identity=current["identity"], sha256=p0_hash), exclusive=True)
    atomic(directory / "checkpoint-inheritance.json", dict(parent=pointer, rebound=new_pointer,
        identity=current["identity"], preserved_all_other_state=True), exclusive=True)
    return current
