"""D-122 inheritance into a fresh EX-077 identity; no GPU or battle execution."""
from copy import deepcopy
from pathlib import Path
import shutil

from .config import PROTOCOL
from .prepare import prepare
from .storage import atomic, digest, read, sha

PARENT_IDENTITY = "bc5038be863cccabd8d3d6b79f1e7dc161c97fccd147489dbf6d2c53251788b6"


def _file(root, name):
    path = root / name
    if Path(name).is_absolute() or ".." in Path(name).parts or not path.is_file():
        raise ValueError("invalid parent file: " + name)
    if any(p.is_symlink() for p in (path, *path.parents) if p != root.parent):
        raise ValueError("symlink in parent file: " + name)
    return path


def _check(root, name, checksum):
    if sha(_file(root, name)) != checksum:
        raise ValueError("parent checksum mismatch: " + name)


def _seal(parent, name):
    result = {}
    for line in _file(parent, name).read_text().splitlines():
        checksum, relative = line.split("  ", 1)
        if relative in result:
            raise ValueError("duplicate seal entry: " + relative)
        _check(parent, relative, checksum)
        result[relative] = checksum
    if not result:
        raise ValueError("empty parent seal")
    return result


def prepare_day(parent, directory):
    """Copy only uniform32/P0; link the approved failed16 and start no clock."""
    parent, directory = Path(parent).resolve(), Path(directory).resolve()
    if parent == directory or directory.is_relative_to(parent) or parent.is_relative_to(directory):
        raise ValueError("day run requires a separate directory")
    if directory.exists():
        raise FileExistsError("day run requires a new directory")
    manifest = read(parent / "manifest.json")
    if digest({k: v for k, v in manifest.items() if k != "identity"}) != manifest["identity"]:
        raise ValueError("parent identity corrupted")
    if manifest["identity"] != PARENT_IDENTITY:
        raise ValueError("only the approved EX-076 fnt-v2 parent may be inherited")
    old_protocol = deepcopy(PROTOCOL)
    old_protocol.update(experiment="EX-076", total_seconds=43200)
    old_protocol["stage_seconds"]["test"] = 10800
    if (PROTOCOL["experiment"] != "EX-077" or PROTOCOL["total_seconds"] != 86400
            or PROTOCOL["stage_seconds"]["test"] != 54000 or manifest["protocol"] != old_protocol):
        raise ValueError("only the approved day budget may change the protocol")
    for name, checksum in manifest["sources"].items():
        _check(parent, "source/" + name, checksum)
    for name, checksum in manifest["files"].items():
        _check(parent, name, checksum)
    for team in manifest["teams"].values():
        _check(parent, "teams/" + team["file"], team["sha256"])
    sealed = _seal(parent, "evidence.sha256")
    closure = _seal(parent, "closure.sha256")
    if any(name in sealed and sealed[name] != value for name, value in closure.items()):
        raise ValueError("parent seals disagree")
    sealed.update(closure)
    for required in ("manifest.json", "incomplete.json", "models/P0.pt", "models/P0.identity.json"):
        if required not in sealed:
            raise ValueError("parent seal omitted " + required)
    closed = read(parent / "incomplete.json")
    if (closed.get("status") != "incomplete" or not closed.get("gpu_released")
            or closed.get("training_games") != 0 or closed.get("test_games") != 0
            or closed.get("training_updates") != 0):
        raise ValueError("parent must be closed before training/test")
    if list((parent / "checkpoints").glob("*.pt")) or (parent / "evaluation-lock.json").exists():
        raise ValueError("training/test cannot be reset")
    p0_hash = sha(parent / "models/P0.pt")
    if read(parent / "models/P0.identity.json") != dict(identity=manifest["identity"], sha256=p0_hash):
        raise ValueError("parent P0 identity mismatch")
    schedule = read(parent / "schedule.json")
    uniform = {j["slot_id"]: j for j in schedule["pilot"] if j["condition"] == "uniform"}
    policy = {j["slot_id"]: j for j in schedule["pilot"] if j["condition"] == "P0"}
    if len(uniform) != 32 or len(policy) != 32:
        raise ValueError("parent pilot schedule changed")
    results = {p.parent.name: read(p) for p in (parent / "games").glob("*/result.json")}
    claims = {p.stem: read(p) for p in (parent / "claims").glob("*.json")}
    failed = sorted(set(results) - set(uniform))
    if len(failed) != 16 or not set(failed) <= set(policy) or set(claims) != set(results):
        raise ValueError("approved inheritance requires uniform32 and failed P0 sixteen")
    if not set(uniform) <= set(results):
        raise ValueError("missing completed uniform game")
    for slot, row in results.items():
        job = uniform.get(slot, policy.get(slot))
        if row["job"] != job or claims[slot]["job"] != job:
            raise ValueError("parent slot identity mismatch")
        if slot in uniform:
            if row["status"] != "completed" or row.get("model_hashes") != {"P0": p0_hash}:
                raise ValueError("only completed uniform games from the same P0 may be inherited")
        elif row["status"] != "incomplete" or row.get("reason") != "interrupted_reserved_slot":
            raise ValueError("only the approved interrupted P0 games may be retried")
        for name, checksum in row["files"].items():
            _check(parent, f"games/{slot}/{name}", checksum)
        for path in [parent / "claims" / f"{slot}.json", *(parent / "games" / slot).rglob("*")]:
            if path.is_file():
                name = str(path.relative_to(parent))
                if name not in sealed:
                    raise ValueError("parent seal omitted " + name)
                _check(parent, name, sealed[name])
    current = prepare(directory)
    for name in ("catalog.json", "schedule.json"):
        if sha(parent / name) != sha(directory / name):
            raise ValueError("catalog/schedule changed during inheritance")
    if current["teams"] != manifest["teams"]:
        raise ValueError("teams changed during inheritance")
    for team in current["teams"].values():
        _check(directory, "teams/" + team["file"], team["sha256"])
    copied = {}
    for slot in sorted(uniform):
        shutil.copytree(parent / "games" / slot, directory / "games" / slot)
        destination = directory / "claims" / f"{slot}.json"
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(parent / "claims" / f"{slot}.json", destination)
        for path in [destination, *(directory / "games" / slot).rglob("*")]:
            if path.is_file():
                name = str(path.relative_to(directory))
                _check(directory, name, sealed[name])
                copied[name] = sealed[name]
    (directory / "models").mkdir()
    shutil.copy2(parent / "models/P0.pt", directory / "models/P0.pt")
    _check(directory, "models/P0.pt", p0_hash)
    linkage = dict(approval="D-122", parent=str(parent), parent_identity=manifest["identity"],
        parent_manifest_sha256=sha(parent / "manifest.json"),
        parent_seals={name: sha(parent / name) for name in ("evidence.sha256", "closure.sha256")},
        parent_sources=manifest["sources"], parent_files=manifest["files"],
        inherited_games=sorted(uniform), inherited_files=copied, p0_sha256=p0_hash,
        retry_games=failed, retry_limit=1, unattempted_games=sorted(set(policy) - set(failed)),
        failed_evidence={name: checksum for name, checksum in sealed.items()
                         if any(name.startswith(f"games/{slot}/") or name == f"claims/{slot}.json"
                                for slot in failed)},
        clock_policy="new_first_gpu_verification_86400_seconds_no_extension")
    atomic(directory / "day-inheritance.json", linkage, exclusive=True)
    current.pop("identity")
    current["files"].update(copied)
    current["files"].update({"models/P0.pt": p0_hash,
                             "day-inheritance.json": sha(directory / "day-inheritance.json")})
    current["day_inheritance"] = linkage
    current["identity"] = digest(current)
    atomic(directory / "manifest.json", current)
    return current
