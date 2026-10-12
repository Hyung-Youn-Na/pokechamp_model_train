"""CPU-only identity preparation and verification. Never starts a game on a GPU.

Live re-verification scope (EX-080): this package except tests/ and finalize/, the pinned Showdown dist,
poke_env, the pinned Kev files, the model snapshot, the team whitelist and the launcher. Governance documents
are copied into <run>/docs and only their copies are checked, so editing them elsewhere never blocks this run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from .config import (ACTOR_PYTHON, ASSIGNMENTS, DEFAULT_TEAMS, KEV_FILES, KEV_ROOT, MODEL_PYTHON, PACKAGE, PROTOCOL,
                     ROOT, SNAPSHOT, TEAMS)
from .storage import atomic, atomic_bytes, digest, read, sha, showdown_seed

EXCLUDED = ("tests", "finalize", "__pycache__")
SNAPSHOT_FILES = ("config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors.index.json",
                  "model.safetensors-00001-of-00001.safetensors")
DOCUMENTS = ("project_context/RESEARCH_DESIGN.md", "project_context/CONTRACTS.md", "project_context/CHARTER.md",
             "project_context/decisions/D-127-qwen-matrix-selfplay.md",
             "project_context/decisions/D-128-qwen-fixed-shape-serving.md",
             "project_context/experiments/EX-080-qwen-matrix-selfplay.md",
             "project_context/exec-plans/active/EP-132-qwen-matrix-selfplay.md")


def source_files():
    files = [p for p in PACKAGE.rglob("*") if p.is_file() and p.suffix in (".py", ".cjs", ".json")
             and not set(p.relative_to(PACKAGE).parts) & set(EXCLUDED)]
    for name in ("sim", "data", "config", "lib"):
        files += [p for p in (ROOT / "pokemon-showdown/dist" / name).rglob("*") if p.is_file() and p.suffix in (".js", ".json")]
    files += [p for p in (ROOT / "pokechamp/poke_env").rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".csv", ".txt")]
    files += [ROOT / "export/teams/gen9ou_reviewed108_teams.txt", ROOT / "scripts/qwen-mcts"]
    return sorted(set(files))


def sources():
    named = {str(p.relative_to(ROOT)): sha(p) for p in source_files()}
    named.update({f"kev:{name}": sha(KEV_ROOT / name) for name in KEV_FILES})
    named.update({f"snapshot:{name}": sha(SNAPSHOT / name) for name in SNAPSHOT_FILES})
    return named


def environment():
    code = ("import json,platform,importlib.metadata as m; print(json.dumps(dict(python=platform.python_version(),"
            "packages=sorted((d.metadata['Name'],d.version) for d in m.distributions()))))")
    kev = subprocess.check_output(["git", "-C", str(KEV_ROOT), "rev-parse", "HEAD"], text=True).strip()
    return {"model": json.loads(subprocess.check_output([str(MODEL_PYTHON), "-c", code], text=True)),
            "actor": json.loads(subprocess.check_output([str(ACTOR_PYTHON), "-c", code], text=True)),
            "node": subprocess.check_output(["node", "--version"], text=True).strip(), "kev_commit": kev}


def team_texts(team_root=DEFAULT_TEAMS):
    allowed = set((ROOT / "export/teams/gen9ou_reviewed108_teams.txt").read_text().splitlines())
    texts = {}
    for label, (file, expected) in TEAMS.items():
        path = Path(team_root) / file
        if file not in allowed or sha(path) != expected:
            raise ValueError("team whitelist/hash failed")
        texts[label] = path.read_text()
    return texts


def statics(teams, tokens):
    from .sim import Simulator
    out = {}
    with Simulator("real") as engine:
        validation = engine.validate(teams)
        if any(validation.values()):
            raise ValueError("team validation failed: " + str(validation))
        for assignment, sides in ASSIGNMENTS.items():
            frame = engine.init({side: teams[label] for side, label in sides.items()}, showdown_seed("static", assignment))
            ids = tokens.static(frame["static"])
            out[assignment] = dict(text=frame["static"], text_sha256=digest(frame["static"]), ids=ids,
                                   ids_sha256=digest(ids), length=len(ids))
    return out, validation


def initial_model(directory):
    """P0 = the seeded learner adapter (B = 0) and zero-initialized key/value-output head layers, on CPU."""
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from .network import Network, TRAIN
    net = Network("cpu")
    return net.save(TRAIN, Path(directory))


def prepare(directory, *, team_root=DEFAULT_TEAMS):
    from .schedule import frozen
    from .tokens import Tokens
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError("prepare needs a new directory; existing artifacts are preserved")
    teams = team_texts(team_root)
    tokens = Tokens()
    static, validation = statics(teams, tokens)
    directory.mkdir(parents=True)
    for label, (file, _) in TEAMS.items():
        atomic_bytes(directory / "teams" / file, teams[label].encode(), exclusive=True)
    atomic(directory / "static.json", static, exclusive=True)
    atomic(directory / "schedule.json", frozen(), exclusive=True)
    p0 = initial_model(directory / "models/round-000")
    for name in DOCUMENTS:
        atomic_bytes(directory / "docs" / name, (ROOT / name).read_bytes(), exclusive=True)
    files = {name: sha(directory / name) for name in ("static.json", "schedule.json", "models/round-000/adapter.safetensors",
                                                       "models/round-000/heads.safetensors")}
    files.update({f"teams/{file}": sha(directory / "teams" / file) for file, _ in TEAMS.values()})
    manifest = dict(protocol=PROTOCOL, sources=sources(), environment=environment(), files=files,
                    documents={name: sha(directory / "docs" / name) for name in DOCUMENTS},
                    statics={k: dict(text_sha256=v["text_sha256"], ids_sha256=v["ids_sha256"], length=v["length"])
                             for k, v in static.items()},
                    pad_id=tokens.pad_id, validation=validation, p0=p0, status="prepared_not_run")
    manifest = json.loads(json.dumps(manifest))
    manifest["identity"] = digest(manifest)
    atomic(directory / "manifest.json", manifest, exclusive=True)
    return manifest


def verify(directory):
    directory = Path(directory)
    manifest = read(directory / "manifest.json")
    identity = manifest.pop("identity")
    if digest(manifest) != identity:
        raise ValueError("manifest identity changed")
    if manifest["protocol"] != json.loads(json.dumps(PROTOCOL)):
        raise ValueError("protocol changed since prepare")
    live = sources()
    if live != manifest["sources"]:
        changed = sorted(set(live.items()) ^ set(manifest["sources"].items()))[:6]
        raise ValueError(f"live source differs from the prepared identity: {changed}")
    if environment() != manifest["environment"]:
        raise ValueError("runtime environment changed since prepare")
    for name, checksum in {**manifest["files"], **{f"docs/{k}": v for k, v in manifest["documents"].items()}}.items():
        if sha(directory / name) != checksum:
            raise ValueError("frozen file changed: " + name)
    return dict(manifest, identity=identity)


if __name__ == "__main__":
    print(json.dumps(prepare(sys.argv[1])["identity"]))
