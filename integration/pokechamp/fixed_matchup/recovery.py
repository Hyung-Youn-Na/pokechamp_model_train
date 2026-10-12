"""D-121: one approved source correction, preserving completed uniform games and first clock."""
from pathlib import Path
import shutil
import time

from .config import PROTOCOL
from .prepare import prepare
from .storage import atomic, digest, read, sha


def prepare_fnt_recovery(parent, directory):
    parent, directory = Path(parent).resolve(), Path(directory).resolve()
    if parent == directory or directory.is_relative_to(parent):
        raise ValueError("recovery requires a separate sibling directory")
    manifest = read(parent / "manifest.json")
    if digest({k: v for k, v in manifest.items() if k != "identity"}) != manifest["identity"]:
        raise ValueError("parent identity corrupted")
    if manifest["protocol"] != PROTOCOL:
        raise ValueError("recovery cannot change protocol")
    if not (parent / "incomplete.json").exists():
        raise ValueError("parent must be closed before recovery")
    clock = read(parent / "clock.json")
    if time.time() >= clock["start"] + PROTOCOL["total_seconds"]:
        raise TimeoutError("original total budget expired")
    for line in (parent / "evidence.sha256").read_text().splitlines():
        checksum, name = line.split("  ", 1)
        if sha(parent / name) != checksum:
            raise ValueError("parent evidence corrupted: " + name)
    games = [read(p) for p in sorted((parent / "games").glob("*/result.json"))]
    if len(games) != 32 or any(r["status"] != "completed" or r["job"]["stage"] != "pilot"
                             or r["job"]["condition"] != "uniform" for r in games):
        raise ValueError("only 32 completed uniform games may be inherited")
    claims = sorted((parent / "benchmarks/claims").glob("*.json"))
    if [p.stem for p in claims] != [f"w8-b16-n64-{i}" for i in range(8)]:
        raise ValueError("approved retry set differs from eight failed probes")
    if list((parent / "benchmarks/results").glob("*.json")):
        raise ValueError("unexpected completed benchmark results")
    if list((parent / "checkpoints").glob("*.pt")) or (parent / "evaluation-lock.json").exists():
        raise ValueError("training/test cannot be reset by this recovery")
    stops = [read(p) for p in (parent / "stops").glob("*.json")]
    stop = next(s for s in stops if "status:fnt" in s["reason"])
    stages = {p.stem: read(p) for p in (parent / "stages").glob("*.json")}
    releases = sorted(read(p)["at"] for p in (parent / "resource-events").glob("*.json"))
    # Conservative debit for verification includes all time through the last
    # independent correction verification. Approval waiting remains on total wall time.
    spent = dict(verify=releases[-1] - clock["start"],
                 pilot=stop["at"] - stages["pilot"]["start"],
                 finalize=releases[0] - stages["finalize"]["start"])
    if any(not 0 <= value < PROTOCOL["stage_seconds"][stage] for stage, value in spent.items()):
        raise ValueError("inherited stage expenditure exhausted")
    current = prepare(directory)
    for name in ("catalog.json", "schedule.json"):
        if sha(parent / name) != sha(directory / name):
            raise ValueError("catalog/schedule changed during recovery")
    for folder in ("games", "claims"):
        shutil.copytree(parent / folder, directory / folder)
    (directory / "models").mkdir()
    shutil.copy2(parent / "models/P0.pt", directory / "models/P0.pt")
    shutil.copy2(parent / "clock.json", directory / "clock.json")
    shutil.copy2(parent / "resource.json", directory / "resource.json")
    atomic(directory / "stage-spent.json", spent, exclusive=True)
    inherited_disk = sum(p.stat().st_size for p in parent.rglob("*") if p.is_file())
    for name in read(parent / "exports.json"):
        inherited_disk += sum(p.stat().st_size for p in Path(name).rglob("*") if p.is_file())
    atomic(directory / "inherited-disk.json", dict(bytes=inherited_disk), exclusive=True)
    linkage = dict(approval="D-121", parent=str(parent), parent_identity=manifest["identity"],
                   parent_seal=sha(parent / "evidence.sha256"), first_clock=clock,
                   inherited_games=[r["job"]["slot_id"] for r in games],
                   retry_probes=[p.stem for p in claims], retry_limit=1,
                   p0_sha256=sha(parent / "models/P0.pt"), stage_spent=spent)
    atomic(directory / "recovery.json", linkage, exclusive=True)
    current.pop("identity")
    for name in ("clock.json", "stage-spent.json", "inherited-disk.json", "recovery.json"):
        current["files"][name] = sha(directory / name)
    current["recovery"] = linkage
    current["identity"] = digest(current)
    atomic(directory / "manifest.json", current)
    return current
