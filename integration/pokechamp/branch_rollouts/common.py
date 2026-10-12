"""Immutable source preparation and cumulative collection accounting."""
from __future__ import annotations

import gzip
import copy
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / ".pokechamp-data/jev/ex058-live"
DEFAULT_OUTPUT = ROOT / ".pokechamp-data/rollouts/ex058-b19-rollout-v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    os.replace(temp, path)


def append(path, value):
    with Path(path).open("a") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()


def gzwrite(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)


def gzread(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def command(wire):
    if wire.startswith("/choose "):
        return wire[8:]
    if wire.startswith("/team "):
        return wire[1:]
    raise ValueError(f"Unsupported archived command: {wire}")


def normalize_request(request):
    # rqid is assigned by the WebSocket room, not the underlying simulator.
    return {k: v for k, v in request.items() if k not in ("rqid", "noCancel")}


def gameplay_lines(lines):
    """Remove transport-only lines; retain every gameplay event and its order."""
    excluded = {"", "init", "title", "t:", "request", "sentchoice", "l", "L"}
    return [line for line in lines if line.startswith("|") and
            (line.split("|") + [""])[1] not in excluded]


def derive_seed(anchor_id, replicate, namespace):
    raw = hashlib.sha256(f"20260928:{anchor_id}:{replicate}:{namespace}".encode()).digest()
    if namespace == "simulator":
        return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, 8, 2)]
    return int.from_bytes(raw[:4], "big")


def code_identity():
    folder = Path(__file__).parent
    paths = list(folder.glob("*.py")) + list(folder.glob("*.cjs"))
    paths += [ROOT / "integration/pokechamp/battle_adapter.py", ROOT / "pokechamp/poke_env/player/baselines.py",
              ROOT / "pokechamp/poke_env/player/player.py"]
    return {str(p.relative_to(ROOT)): file_hash(p) for p in sorted(paths)}


def simulator_teams(teams, events):
    """Restore server-validation gender assignments from the public preview.

    TeamValidator assigns unspecified genders using its own Math.random before
    Battle construction. Feeding the unvalidated wire directly would consume
    battle PRNG instead and silently change every later draw.
    """
    details = {s: [] for s in ("p1", "p2")}
    for event in events:
        if event["type"] != "protocol":
            continue
        for line in event["protocol"].splitlines():
            parts = line.split("|")
            if len(parts) >= 4 and parts[1] == "poke" and parts[2] in details:
                details[parts[2]].append(parts[3])
    result = copy.deepcopy(teams)
    for side, player in result.items():
        packed = player["team"].split("]")
        if len(details[side]) != len(packed):
            raise ValueError("Public preview does not cover original team slots")
        updated = []
        for pokemon, detail in zip(packed, details[side]):
            fields = pokemon.split("|")
            gender = next((x for x in detail.split(", ")[1:] if x in ("M", "F")), None)
            if gender:
                if fields[7] and fields[7] != gender:
                    raise ValueError("Explicit team gender conflicts with archived preview")
                fields[7] = gender
            updated.append("|".join(fields))
        player["team"] = "]".join(updated)
    return result


def verify_source(expected=None):
    seals = {}
    for line in (SOURCE / "checksums.sha256").read_text().splitlines():
        h, name = line.split("  ", 1)
        if name in ("manifest.json", "events.jsonl", "result.json") or name.startswith(("battle-19/", "source/")):
            if file_hash(SOURCE / name) != h:
                raise ValueError("Original source checksum mismatch: " + name)
            seals[name] = h
    if expected is not None and expected != seals:
        raise ValueError("Original source manifest changed")
    manifest = read(SOURCE / "manifest.json")
    for name, info in manifest["submodules"].items():
        current = subprocess.check_output(["git", "-C", str(ROOT / name), "rev-parse", "HEAD"], text=True).strip()
        if current != info["sha"]:
            raise ValueError("Pinned submodule drift: " + name)
        dirty = subprocess.check_output(["git", "-C", str(ROOT / name), "status", "--porcelain", "--untracked-files=no"], text=True)
        if dirty:
            raise ValueError("Pinned submodule has tracked modifications: " + name)
    # This adapter is part of the original Abyssal semantics, not a new policy.
    adapter = "integration/pokechamp/battle_adapter.py"
    if file_hash(ROOT / adapter) != manifest["source"][adapter]:
        raise ValueError("Actor identity adapter differs from sealed original")
    return seals


def prepare(output):
    from poke_env.teambuilder.constant_teambuilder import ConstantTeambuilder
    output = Path(output)
    if output.exists():
        raise FileExistsError("Output already exists; original data is never overwritten")
    source_hashes = verify_source()
    request = read(SOURCE / "battle-19/request.json")
    source_manifest = read(SOURCE / "manifest.json")
    outcome = read(SOURCE / "battle-19/outcome.json")
    username = outcome["username"]
    selected = []
    with (SOURCE / "events.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("username") == username or row.get("decision", "").startswith(username + "-"):
                if row["type"] in ("protocol", "input", "selection", "wire"):
                    selected.append(row)
    inputs = [r for r in selected if r["type"] == "input"]
    selections = {r["decision"]: r for r in selected if r["type"] == "selection"}
    wires = {r["decision"]: r for r in selected if r["type"] == "wire"}
    anchors = []
    for index, row in enumerate(inputs):
        choice = selections[row["decision"]]["choice"]
        if wires[row["decision"]]["command"] != row["commands"][choice]:
            raise ValueError("Original wire/selection mismatch")
        anchors.append(dict(anchor_id=f"a{index:03d}", decision_id=row["decision"],
                            turn=row["payload"]["state"]["turn"], phase=row["payload"]["state"]["decision_kind"],
                            observation=row["payload"], original_action_id=choice,
                            actions=[dict(action_id=k, command=command(v), description=row["payload"]["questions"]["action"]["criteria"][k])
                                     for k, v in row["commands"].items()],
                            original_event_seq=row["event_seq"], original_request=row["official"]["request"]))
    if len(anchors) != 22 or sum(len(a["actions"]) for a in anchors) != 167:
        raise ValueError("Historical anchor/candidate denominator mismatch")
    avatars = {}
    for row in selected:
        if row["type"] == "protocol":
            for line in row["protocol"].splitlines():
                parts = line.split("|")
                if len(parts) >= 5 and parts[1] == "player":
                    avatars[parts[2]] = parts[4]
    teams = {side: dict(name=request["names"][side], avatar=avatars[side],
                       team=ConstantTeambuilder(request["teams"][request["slot"]["teams"][int(side[-1]) - 1]]["showdown_team"]).yield_team())
             for side in ("p1", "p2")}
    manifest = dict(dataset_version="ex058-b19-rollout-v1", experiment_id="EX-060", source_experiment="EX-058",
                    source_slot="b02-r3-s0", source_directory=str(SOURCE), source_hashes=source_hashes,
                    source_submodules=source_manifest["submodules"], original_request=request, teams=teams,
                    original_outcome=outcome, actor="p2", policy="sealed-Abyssal-both-v1",
                    expected_repetitions=32, replicate_start=0, planned_rollouts=5344, master_seed=20260928,
                    limits=dict(workers=4, total_seconds=14400, cleanup_seconds=900, attempts=6000,
                                branch_seconds=120, additional_turns=300),
                    target="Q(actual_hidden_state, action | both_sides_Abyssal)",
                    split="development_only", api_calls=0, model_training=False, status="prepared")
    output.mkdir(parents=True)
    write(output / "manifest.json", manifest)
    for row in anchors:
        append(output / "anchors.jsonl", row)
    gzwrite(output / "source/selected-events.json.gz", selected)
    write(output / "source/original-manifest.json", source_manifest)
    return dict(anchors=len(anchors), candidates=sum(len(a["actions"]) for a in anchors), output=str(output))


class Budget:
    """Parent-owned durable accounting; never reset by reconstruction or recovery."""
    def __init__(self, directory):
        self.path = Path(directory) / "ledger.json"
        if self.path.exists():
            self.value = read(self.path)
        else:
            now = time.time()
            self.value = dict(started_at=now, admission_deadline=now + 13500, deadline=now + 14400,
                              attempts=0, maximum_attempts=6000)
            write(self.path, self.value)

    def reserve(self, kind, identity):
        if time.time() >= self.value["admission_deadline"]:
            raise RuntimeError("Collection admission deadline reached")
        if self.value["attempts"] >= self.value["maximum_attempts"]:
            raise RuntimeError("Collection attempt cap reached")
        self.value["attempts"] += 1
        write(self.path, self.value)
        record = dict(number=self.value["attempts"], at=time.time(), kind=kind, identity=identity)
        append(self.path.with_name("attempts.jsonl"), record)
        return record["number"]
