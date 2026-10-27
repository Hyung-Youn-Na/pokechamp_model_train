"""CPU-only manifest preparation; never starts a battle or loads a model."""
from __future__ import annotations

from integration.project_context.registry import authority_paths, record_relative, runtime_paths

import platform
import json
import sys
from pathlib import Path
import subprocess

from .config import ACTOR_PYTHON, DEFAULT_TEAMS, PROTOCOL, ROOT, TEAMS
from .schedule import development, pilot_schedule, test_schedule, training
from .simulator import Simulator
from .storage import atomic, atomic_bytes, digest, read, sha


def source_files():
    files = []
    for root in (ROOT / "integration/pokechamp", ROOT / "pokemon-showdown/dist/sim",
                 ROOT / "pokemon-showdown/dist/data", ROOT / "pokemon-showdown/dist/config",
                 ROOT / "pokemon-showdown/dist/lib"):
        files.extend(p for p in root.rglob("*") if p.is_file() and p.suffix in (".py", ".cjs", ".js", ".json"))
    files.extend(ROOT / p for p in ["project_context/CONTRACTS.md", "project_context/RESEARCH_DESIGN.md",
        "project_context/CHARTER.md", record_relative('EX-076', prefix=True),
        record_relative('EX-077', prefix=True),
        record_relative('D-122', prefix=True),
        record_relative('D-123', prefix=True),
        record_relative('D-124', prefix=True),
        record_relative('D-125', prefix=True),
        record_relative('D-126', prefix=True),
        record_relative('EX-079', prefix=True),
        record_relative('EX-078', prefix=True),
        record_relative('D-119', prefix=True),
        record_relative('D-120', prefix=True),
        record_relative('D-121', prefix=True),
        "export/teams/gen9ou_reviewed108_teams.txt", "scripts/pokechamp-fixed-matchup"])
    files.extend(authority_paths(root=ROOT))
    files.extend(runtime_paths(root=ROOT))
    # Canonical opponent code is used through poke-env and must also be pinned.
    for relative in ("pokechamp/poke_env",):
        files.extend(p for p in (ROOT / relative).rglob("*") if p.is_file()
                     and p.suffix in (".py", ".json", ".csv", ".txt"))
    return sorted(set(files))


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in source_files()}


def environment():
    code = ("import json,platform,importlib.metadata as m; "
            "print(json.dumps(dict(python=platform.python_version(),packages="
            "sorted((d.metadata['Name'],d.version) for d in m.distributions()))))")
    return {"model": json.loads(subprocess.check_output([sys.executable, "-c", code], text=True)),
            "actor": json.loads(subprocess.check_output([str(ACTOR_PYTHON), "-c", code], text=True)),
            "node": subprocess.check_output(["node", "--version"], text=True).strip()}


def verify_identity(directory, *, protocol=PROTOCOL):
    directory = Path(directory)
    manifest = read(directory / "manifest.json")
    identity = manifest.pop("identity")
    if digest(manifest) != identity or manifest["protocol"] != protocol:
        raise ValueError("prepared protocol/identity changed")
    if environment() != manifest["environment"]:
        raise ValueError("prepared runtime environment changed")
    if sources() != manifest["sources"]:
        raise ValueError("live source differs from prepared source; do not resume")
    for name, checksum in manifest["sources"].items():
        if sha(directory / "source" / name) != checksum:
            raise ValueError("frozen source changed: " + name)
    for label, info in manifest["teams"].items():
        if sha(directory / "teams" / info["file"]) != info["sha256"]:
            raise ValueError("frozen team changed")
    for name, checksum in manifest["files"].items():
        if sha(directory / name) != checksum:
            raise ValueError("prepared file changed: " + name)
    return dict(manifest, identity=identity)


def prepare(directory, *, team_root=DEFAULT_TEAMS, protocol=PROTOCOL, schedule=None):
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError("prepare needs a new directory; existing artifacts are preserved")
    allowed = set((ROOT / "export/teams/gen9ou_reviewed108_teams.txt").read_text().splitlines())
    teams, information = {}, {}
    for label, (file, expected) in TEAMS.items():
        path = Path(team_root) / file
        if file not in allowed or sha(path) != expected:
            raise ValueError("team whitelist/hash failed")
        teams[label] = path.read_text()
        information[label] = dict(file=file, sha256=expected)
    with Simulator("real") as engine:
        validation = engine.validate(teams)
        if any(validation.values()):
            raise ValueError("team validation failed: " + str(validation))
        catalog = engine.catalog()
    source = sources()
    schedule = schedule if schedule is not None else dict(pilot=pilot_schedule(), test=test_schedule(),
        train=[training(i) for i in range(1, PROTOCOL["max_rounds"] + 1)],
        dev={str(i): development(i) for i in range(PROTOCOL["dev_interval"], PROTOCOL["max_rounds"] + 1,
                                                 PROTOCOL["dev_interval"])})
    directory.mkdir(parents=True, exist_ok=False)
    for label, info in information.items():
        atomic_bytes(directory / "teams" / info["file"], teams[label].encode(), exclusive=True)
    atomic(directory / "catalog.json", catalog, exclusive=True)
    atomic(directory / "schedule.json", schedule, exclusive=True)
    for name in source:
        atomic_bytes(directory / "source" / name, (ROOT / name).read_bytes(), exclusive=True)
    files = {name: sha(directory / name) for name in ("catalog.json", "schedule.json")}
    manifest = dict(protocol=protocol, teams=information, sources=source, files=files,
        environment=environment(),
        status="prepared_not_run", validation=validation)
    manifest["identity"] = digest(manifest)
    atomic(directory / "manifest.json", manifest, exclusive=True)
    return manifest
