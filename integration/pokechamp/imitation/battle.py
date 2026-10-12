"""EX-071의 동결40경기를 최초6시간 시계에서 한 번씩 실행한다."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import config, reporting
from .player import (
    EventLog,
    FixedSlots,
    PhaseError,
    actions_and_commands,
    compact,
    http_json,
    validate_response,
)
from .schema import ImitationInput, from_snapshot
from .storage import atomic, read, sha

TOTAL_SECONDS = 21600
BATTLE_SECONDS = 1200
CLEANUP_SECONDS = 60
PRECISION = dict(
    base="bfloat16",
    lora="float32",
    head="float32",
    loss="float32",
    forward="bfloat16",
    merged=False,
    cache=False,
    fused=False,
    cuda_graphs=False,
    tf32=False,
)


def validate_schedule(rows):
    if not isinstance(rows, list) or len(rows) != 40:
        raise ValueError("EX-071 requires the frozen forty-slot schedule")
    identities, groups = set(), defaultdict(list)
    for row in rows:
        slot = row["slot_id"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}", slot) or slot in identities:
            raise ValueError("invalid or duplicate battle slot")
        identities.add(slot)
        if (
            row["model"] not in ("initial", "selected")
            or row["model_side"] not in ("p1", "p2")
            or row["opponent"] not in ("abyssal", "abyssal-tera-v1")
        ):
            raise ValueError("unregistered model, side or opponent")
        if set(row["teams"]) != {"p1", "p2"}:
            raise ValueError("both actual side teams must be frozen")
        for team in row["teams"].values():
            if (
                not isinstance(team["packed"], str)
                or not team["packed"]
                or not isinstance(team["text"], str)
                or not team["text"]
                or len(team["species"]) != 6
                or not team["signature"]
            ):
                raise ValueError("incomplete frozen team")
        seed = row["simulator_seed"]
        if (
            not isinstance(seed, list)
            or len(seed) != 4
            or any(type(v) is not int or not 0 <= v < 65536 for v in seed)
        ):
            raise ValueError("invalid simulator seed")
        if any(
            type(row[k]) is not int or not 0 <= row[k] < 2**32
            for k in ("model_seed", "opponent_seed")
        ):
            raise ValueError("invalid actor seed")
        groups[row["pair_id"]].append(row)
    if len(groups) != 5:
        raise ValueError("five team-matchup clusters are required")
    expected = set(
        itertools.product(("initial", "selected"), ("p1", "p2"), ("abyssal", "abyssal-tera-v1"))
    )
    signatures = set()
    for group in groups.values():
        cells = {(r["model"], r["model_side"], r["opponent"]): r for r in group}
        if len(group) != 8 or set(cells) != expected:
            raise ValueError("incomplete model/side/opponent matrix")
        teams = {tuple(sorted(t["species"])) for r in group for t in r["teams"].values()}
        if len(teams) != 2 or signatures & teams:
            raise ValueError("each matchup must own two distinct unused six-species teams")
        signatures.update(teams)
        for side, opponent in itertools.product(("p1", "p2"), ("abyssal", "abyssal-tera-v1")):
            a, b = cells["initial", side, opponent], cells["selected", side, opponent]
            for key in ("teams", "simulator_seed", "opponent_seed", "model_seed"):
                if a[key] != b[key]:
                    raise ValueError("paired initial/selected conditions differ: " + key)
    if [r["model"] for r in rows] != ["initial"] * 20 + ["selected"] * 20:
        raise ValueError("EX-071 order must be initial20 then selected20")
    return rows


def source_identity():
    suffixes = {".py", ".cjs", ".json", ".txt", ".js", ".html"}
    paths = [
        p
        for p in (config.ROOT / "integration/pokechamp").rglob("*")
        if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts
    ]
    wrapper = config.ROOT / "scripts/pokechamp-imitation"
    if wrapper.exists():
        paths.append(wrapper)
    return {str(path.relative_to(config.ROOT)): sha(path) for path in sorted(paths)}


def verify_reference(record):
    path = Path(record["path"]).resolve()
    if sha(path) != record["sha256"]:
        raise PhaseError("frozen readiness reference changed: " + path.name)
    return read(path)


def verify_readiness(path, schedule_path):
    ready = read(path)
    if ready.get("passed") is not True or ready.get("schedule_sha256") != sha(schedule_path):
        raise PhaseError("locked schedule and passing battle readiness receipt required")
    gpu = ready.get("resource", {}).get("gpu_index")
    if type(gpu) is not int or gpu not in config.GPU_ORDER:
        raise PhaseError("battle resource must preserve the selected GPU and exclude GPU1")
    lock = verify_reference(ready["evaluation_lock"])
    parity = verify_reference(ready["serving_parity"])
    if parity.get("passed") is not True:
        raise PhaseError("saved-prediction HTTP parity must pass before battle admission")
    if lock.get("serving_parity_sha256") != ready["serving_parity"]["sha256"]:
        raise PhaseError("serving parity differs from the evaluation lock")
    if set(ready["models"]) != {"initial", "selected"}:
        raise PhaseError("both locked model identities required")
    for model, record in ready["models"].items():
        path = Path(record["checkpoint"]).resolve()
        if (
            str(path) != str(Path(lock["model_checkpoints"][model]).resolve())
            or sha(path / "files.json") != record["checkpoint_sha256"]
            or record["checkpoint_sha256"] != lock["checkpoint_sha256"][model]
        ):
            raise PhaseError("checkpoint differs from the evaluation lock")
    if ready.get("port", 8021) not in range(1024, 65536):
        raise PhaseError("invalid local serving port")
    return ready


class Ledger:
    """배틀별 선예약과 전체 최초 시계. 재시작은 기존 시도를 반복하지 못한다."""

    def __init__(self, directory, schedule, identity, *, now=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.schedule = schedule
        wall = time.time() if now is None else now
        self.admission = dict(
            experiment_id="EX-071",
            started_at=wall,
            deadline_at=wall + TOTAL_SECONDS,
            total_seconds=TOTAL_SECONDS,
            per_game_seconds=BATTLE_SECONDS,
            turn_limit=500,
            cleanup_reserve_seconds=CLEANUP_SECONDS,
            schedule_sha256=identity["schedule_sha256"],
            readiness_sha256=identity["readiness_sha256"],
            retries=0,
            requeries=0,
            fallback=0,
            recollection=0,
        )
        atomic(self.directory / "admission.json", self.admission, immutable=True)
        self.events = EventLog(self.directory / "ledger.jsonl")
        self.claimed = set()
        self.events.record(dict(type="admission", **self.admission))

    def remaining(self):
        return self.admission["deadline_at"] - time.time()

    def claim(self, row):
        if row["slot_id"] in self.claimed:
            raise PhaseError("slot already attempted; replay is forbidden")
        if self.remaining() <= CLEANUP_SECONDS:
            return None
        path = self.directory / "games" / row["slot_id"]
        path.mkdir(parents=True, exist_ok=False)
        self.claimed.add(row["slot_id"])
        deadline = time.monotonic() + min(BATTLE_SECONDS, self.remaining() - CLEANUP_SECONDS)
        self.events.record(
            dict(type="slot_claim", slot_id=row["slot_id"], deadline_monotonic=deadline)
        )
        return path, deadline

    def close(self):
        self.events.close()


class ServingManager:
    def __init__(self, directory, ready, ledger):
        self.directory, self.ready, self.ledger = Path(directory), ready, ledger
        self.process = self.log = self.model = self.identity = None

    def stop(self):
        from ..benchmark import terminate

        if self.process is not None:
            terminate(self.process)
            self.ledger.events.record(
                dict(
                    type="serving_stopped",
                    model=self.model,
                    pid=self.process.pid,
                    returncode=self.process.returncode,
                )
            )
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None
        self.model = self.identity = None

    def load(self, model):
        if self.model == model:
            return self.check()
        self.stop()
        from .. import cli

        checkpoint = self.ready["models"][model]
        gpu = self.ready["resource"]["gpu_index"]
        records = read(Path(checkpoint["checkpoint"]) / "files.json")
        for name, expected in records.items():
            path = (Path(checkpoint["checkpoint"]) / name).resolve()
            if (
                not path.is_relative_to(Path(checkpoint["checkpoint"]).resolve())
                or sha(path) != expected
            ):
                raise PhaseError("checkpoint file changed before serving")
        memory = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader,nounits"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        uuids = {
            int(line.split(",")[0]): line.split(",")[1].strip() for line in memory.splitlines()
        }
        applications = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=gpu_uuid", "--format=csv,noheader,nounits"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        if uuids[gpu] in applications.splitlines():
            raise PhaseError("selected GPU is occupied before owned serving admission")
        port = self.ready.get("port", 8021)
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", port))
        self.log = (self.directory / f"serving-{model}.log").open("xb")
        env = cli._child_environment(
            PYTHONPATH=str(config.ROOT),
            CUDA_VISIBLE_DEVICES=str(gpu),
            TOKENIZERS_PARALLELISM="false",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
        )
        self.process = subprocess.Popen(
            [
                self.ready.get("python", str(config.KEV_PYTHON)),
                "-m",
                "integration.pokechamp.imitation.serving",
                "--output",
                str(self.directory.parent),
                "--checkpoint",
                str(checkpoint["checkpoint"]),
                "--model",
                model,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=config.ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.model = model
        origin = f"http://127.0.0.1:{port}"
        start = time.monotonic()
        startup_seconds = min(240, self.ledger.remaining() - CLEANUP_SECONDS)
        while time.monotonic() - start < startup_seconds:
            if self.process.poll() is not None:
                raise PhaseError("owned serving exited before readiness")
            try:
                health = http_json(origin, "/health", timeout=1)
            except (OSError, TimeoutError):
                time.sleep(0.2)
                continue
            self.identity = dict(
                health, endpoint=origin, pid=self.process.pid, gpu_index=gpu, gpu_uuid=uuids[gpu]
            )
            self.check()
            self.ledger.events.record(dict(type="serving_started", identity=self.identity))
            return self.identity
        raise PhaseError("serving initialization exceeded its bounded deadline")

    def check(self):
        if self.process is None or self.process.poll() is not None:
            raise PhaseError("owned serving is not running")
        current = http_json(self.identity["endpoint"], "/health", timeout=5)
        expected = self.ready["models"][self.model]
        if (
            current.get("ready") is not True
            or current.get("model") != self.model
            or current.get("checkpoint_sha256") != expected["checkpoint_sha256"]
            or current.get("precision") != PRECISION
            or current.get("base") != config.BASE
            or current.get("revision") != config.REVISION
            or current.get("state_token_limit") != config.STATE_TOKENS
        ):
            raise PhaseError("serving identity or unmerged precision mismatch")
        if any(current.get(key) != self.identity.get(key) for key in current):
            raise PhaseError("serving health identity changed")
        return self.identity


def audit_match(directory, outcome):
    """원 HTTP/후보/재검증/실제 전송/terminal을 독립 저장 기록으로 대조한다."""
    directory = Path(directory)
    events = reporting.jsonl(directory / "events.jsonl")
    grouped = defaultdict(list)
    for event in events:
        if event.get("decision"):
            grouped[event["decision"]].append(event)
    errors, latencies, counts = [], [], Counter()
    request = read(directory / "request.json")
    row, serving = request["slot"], request["serving"]
    transmitted = [e for e in events if e["type"] == "ps_send"]
    verified_wires = []
    for decision, records in grouped.items():
        typed = defaultdict(list)
        for event in records:
            typed[event["type"]].append(event)
        try:
            if any(len(v) > 1 for v in typed.values()):
                raise ValueError("duplicate decision event")
            entry = typed["input"][0]
            value = ImitationInput(entry["body_json"])
            if value.body != entry["body"] or value.sha256 != entry["input_sha256"]:
                raise ValueError("input bytes/hash mismatch")
            if from_snapshot(entry["snapshot"], entry["actions"]).body_json != value.body_json:
                raise ValueError("shared snapshot serializer differs from recorded input")
            actions, commands = actions_and_commands(
                entry["official"], FixedSlots(entry["slot_map"])
            )
            if [a["id"] for a in actions] != list(value.action_ids) or commands != entry[
                "commands"
            ]:
                raise ValueError("official candidate to stable ID mapping mismatch")
            counts["inputs"] += 1
            http = typed.get("http_request", [])
            if len(value.action_ids) == 1:
                if http or typed.get("response"):
                    raise ValueError("singleton must not query the model")
            elif http:
                envelope = dict(model=row["model"], input=value.body)
                if http[0]["body"] != envelope or http[0]["body_json"] != compact(envelope):
                    raise ValueError("actual HTTP body differs from immutable input")
                if http[0]["attempt"] != 1:
                    raise ValueError("model requery detected")
                counts["model_requests"] += 1
            if not typed.get("selection"):
                if (
                    outcome["status"] == "completed"
                    or outcome["status"] != "incomplete"
                    and not typed.get("decision_rejected")
                ):
                    raise ValueError("decision has no selection or recorded rejection")
                continue
            selection = typed["selection"][0]
            if len(value.action_ids) == 1:
                if selection["automatic"] is not True or selection["probabilities"] is not None:
                    raise ValueError("automatic decision fabricates inference probabilities")
                choice = value.action_ids[0]
                counts["automatic"] += 1
            else:
                response = typed["response"][0]
                raw = typed["http_response"][0]
                if raw["status_code"] != 200 or json.loads(raw["raw_body"]) != response["body"]:
                    raise ValueError("stored raw HTTP response differs from evaluated response")
                choice, probabilities = validate_response(
                    response["body"],
                    value,
                    model=row["model"],
                    checkpoint_sha256=serving["checkpoint_sha256"],
                )
                if selection["automatic"] or selection["probabilities"] != probabilities:
                    raise ValueError("selected probability differs from received probability")
                latencies.append(response["elapsed_seconds"])
                counts["responses"] += 1
            if choice != selection["choice"] or commands[choice] != selection["command"]:
                raise ValueError("selection/command mismatch")
            revalidation = typed["revalidation"][0]
            rqid = entry["official"]["request"]["rqid"]
            if (
                revalidation["passed"] is not True
                or revalidation["commands"] != commands
                or any(
                    revalidation[k] != rqid
                    for k in ("request_id", "latest_request_id", "current_request_id")
                )
            ):
                raise ValueError("missing or stale transmission revalidation")
            if not typed.get("wire"):
                if outcome["status"] == "completed":
                    raise ValueError("completed game omitted a transmitted action")
                continue
            wire = typed["wire"][0]
            if (
                wire["command"] != commands[choice]
                or wire["request_id"] != rqid
                or wire["status"] != "sent"
            ):
                raise ValueError("wire action differs from validated action")
            verified_wires.append((wire["command"], str(rqid)))
            counts["wires"] += 1
        except (ValueError, KeyError, IndexError, TypeError) as error:
            errors.append(dict(decision=decision, error=str(error)))
    actual = [(event["command"], event["request_id"]) for event in transmitted]
    if actual != verified_wires:
        errors.append(dict(error="independent transport recorder differs from decision wires"))
    for actor, actor_events in (
        (row["model_side"], events),
        (
            "p2" if row["model_side"] == "p1" else "p1",
            reporting.jsonl(directory / "opponent-events.jsonl"),
        ),
    ):
        submissions = [e["packed_team"] for e in actor_events if e["type"] == "team_submission"]
        if (submissions or counts["inputs"] or outcome["status"] == "completed") and (
            submissions != [row["teams"][actor]["packed"]]
        ):
            errors.append(dict(error="actual submitted team differs from frozen team", actor=actor))
    seeds = reporting.jsonl(directory / "battle-seed.jsonl")
    if (seeds or counts["inputs"] or outcome["status"] == "completed") and seeds != [
        dict(seed=",".join(map(str, row["simulator_seed"])), format="gen9ou")
    ]:
        errors.append(dict(error="actual simulator seed differs from the frozen seed"))
    if outcome["status"] == "completed":
        if counts["inputs"] != counts["wires"]:
            errors.append(dict(error="completed game omitted decision evidence"))
        terminal = [
            line
            for event in events
            if event["type"] == "protocol"
            for line in event["protocol"].splitlines()
            if line.startswith("|win|") or line == "|tie|"
        ]
        model_name = request["names"][row["model_side"]]
        expected = (
            "|tie|"
            if outcome["result"] == "draw"
            else "|win|"
            + (
                model_name
                if outcome["result"] == "win"
                else request["names"]["p2" if row["model_side"] == "p1" else "p1"]
            )
        )
        if terminal != [expected]:
            errors.append(dict(error="terminal protocol differs from scored result"))
    return dict(passed=not errors, errors=errors, counts=dict(counts), inference_seconds=latencies)


def _base_outcome(row, status="unattempted", **extra):
    return dict(
        **{key: row[key] for key in ("slot_id", "pair_id", "model", "model_side", "opponent")},
        status=status,
        result=None,
        **extra,
    )


def _match(directory, row, deadline, serving, manifest, manager):
    from .. import cli
    from ..benchmark import terminate
    from ..parallel_server import BattleServer

    directory = Path(directory)
    identity = hashlib.sha256(row["slot_id"].encode()).hexdigest()[:12]
    names = {
        side: ("imi" if side == row["model_side"] else "aby") + identity for side in ("p1", "p2")
    }
    atomic(
        directory / "request.json",
        dict(slot=row, names=names, serving=serving, deadline_monotonic=deadline, port=8109),
        immutable=True,
    )
    server = BattleServer(directory, 8109, ",".join(map(str, row["simulator_seed"])))
    processes, logs, cleanup = {}, [], []
    started = time.monotonic()
    outcome = _base_outcome(row, "failed", failure_scope="phase")
    try:
        if source_identity() != manifest["source"]:
            raise PhaseError("runtime source changed after the battle freeze")
        manager.check()
        server.start()
        for actor in ("p1", "p2"):
            seed = row["model_seed"] if actor == row["model_side"] else row["opponent_seed"]
            stream = (directory / f"{actor}.log").open("xb")
            logs.append(stream)
            env = cli._child_environment(
                PYTHONPATH=f"{config.ROOT}:{config.ROOT / 'pokechamp'}",
                CUDA_VISIBLE_DEVICES="",
                PYTHONHASHSEED=str(seed),
                OMP_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1",
                MKL_NUM_THREADS="1",
                NUMEXPR_NUM_THREADS="1",
            )
            processes[actor] = subprocess.Popen(
                [
                    str(config.ROOT / "pokechamp/.venv/bin/python"),
                    "-m",
                    "integration.pokechamp.imitation.battle",
                    "worker",
                    "--attempt",
                    str(directory),
                    "--role",
                    actor,
                ],
                cwd=config.ROOT / "pokechamp",
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        next_guard = time.monotonic() + 30
        while True:
            if time.monotonic() >= deadline:
                outcome.update(status="incomplete", reason="time_limit", failure_scope="battle")
                break
            if time.monotonic() >= next_guard:
                manager.check()
                if source_identity() != manifest["source"]:
                    raise PhaseError("runtime source changed during a battle")
                next_guard = time.monotonic() + 30
            results = {
                actor: read(directory / f"{actor}.result.json")
                for actor in processes
                if (directory / f"{actor}.result.json").exists()
            }
            stopped = [r for r in results.values() if r["status"] != "completed"]
            if stopped:
                original = next(
                    (r for r in stopped if r.get("failure_scope") == "phase"), stopped[0]
                )
                outcome.update(
                    status=original["status"],
                    failure_scope=original["failure_scope"],
                    reason=original.get("reason"),
                    error=original.get("error"),
                    actor_results=results,
                )
                break
            if len(results) == 2:
                model, opponent = (
                    results[row["model_side"]],
                    results["p2" if row["model_side"] == "p1" else "p1"],
                )
                complement = dict(win="loss", loss="win", draw="draw")
                if (
                    model["result"] != complement[opponent["result"]]
                    or model["turns"] != opponent["turns"]
                ):
                    raise PhaseError("actor terminal results disagree")
                for actor, result in results.items():
                    expected = (
                        row["model_seed"] if actor == row["model_side"] else row["opponent_seed"]
                    )
                    if (
                        result["actor"] != actor
                        or result["seed"] != expected
                        or result["python_hash_seed"] != str(expected)
                    ):
                        raise PhaseError("actor seed or role mismatch")
                outcome.update(
                    status="completed",
                    result=model["result"],
                    turns=model["turns"],
                    battle_tag=model["battle_tag"],
                    actor_results=results,
                    failure_scope=None,
                )
                break
            for actor, process in processes.items():
                if process.poll() is not None and actor not in results:
                    raise PhaseError("actor exited without a result: " + actor)
            time.sleep(0.1)
    except BaseException as error:
        outcome.update(
            status="failed",
            result=None,
            failure_scope="phase",
            error=dict(type=type(error).__name__, detail=str(error)),
        )
    finally:
        atomic(directory / "cancel.json", dict(reason="attempt ended"))
        for process in processes.values():
            try:
                terminate(process)
            except Exception as error:
                cleanup.append(dict(type=type(error).__name__, detail=str(error)))
        for stream in logs:
            stream.close()
        try:
            server.close()
        except Exception as error:
            cleanup.append(dict(type=type(error).__name__, detail=str(error)))
        if cleanup:
            outcome.update(
                status="invalid" if outcome["status"] == "completed" else "failed",
                result=None,
                failure_scope="phase",
                cleanup_errors=cleanup,
            )
        outcome.update(
            elapsed_seconds=time.monotonic() - started,
            actors_cleaned=all(p.poll() is not None for p in processes.values()),
            server_cleaned=not server.created
            and (server.process is None or server.process.poll() is not None),
        )
    try:
        audit = audit_match(directory, outcome)
    except Exception as error:
        audit = dict(
            passed=False,
            errors=[dict(error=str(error), type=type(error).__name__)],
            counts={},
            inference_seconds=[],
        )
    atomic(directory / "audit.json", audit, immutable=True)
    if not audit["passed"]:
        outcome.update(
            status="invalid" if outcome["status"] == "completed" else "failed",
            result=None,
            failure_scope="phase",
            audit_passed=False,
        )
    else:
        outcome["audit_passed"] = True
    atomic(directory / "outcome.json", outcome, immutable=True)
    return outcome, audit


def seal(directory):
    directory = Path(directory)
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.name != "checksums.sha256")
    atomic(
        directory / "checksums.sha256",
        "".join(sha(p) + "  " + str(p.relative_to(directory)) + "\n" for p in files).encode(),
        immutable=True,
    )


def run(output, schedule_path, readiness_path):
    """Readiness는 학습/선택/test lock과 실제 HTTP 재로딩 대조 뒤 root가 작성한다."""
    output = Path(output).resolve()
    schedule_path, readiness_path = Path(schedule_path).resolve(), Path(readiness_path).resolve()
    schedule = validate_schedule(read(schedule_path))
    ready = verify_readiness(readiness_path, schedule_path)
    identity = dict(schedule_sha256=sha(schedule_path), readiness_sha256=sha(readiness_path))
    directory = output / "battle"
    ledger = Ledger(directory, schedule, identity)
    manifest = dict(
        experiment_id="EX-071",
        schedule=schedule,
        readiness=ready,
        **identity,
        source=source_identity(),
        probability_meaning="action_selection_probability",
        limits=ledger.admission,
        order="initial20_then_selected20",
    )
    atomic(directory / "manifest.json", manifest, immutable=True)
    shutil.copyfile(schedule_path, directory / "schedule.json")
    shutil.copyfile(readiness_path, directory / "readiness.json")
    manager = ServingManager(directory, ready, ledger)
    outcomes = [_base_outcome(row) for row in schedule]
    latency = {model: [] for model in ("initial", "selected")}
    error = None
    try:
        for index, row in enumerate(schedule):
            if ledger.remaining() <= CLEANUP_SECONDS:
                ledger.events.record(dict(type="admission_closed", reason="total_time_limit"))
                break
            serving = manager.load(row["model"])
            claimed = ledger.claim(row)
            if claimed is None:
                break
            attempt, deadline = claimed
            outcomes[index] = _base_outcome(
                row, "failed", failure_scope="phase", reason="claimed_slot_interrupted"
            )
            outcome, audit = _match(attempt, row, deadline, serving, manifest, manager)
            outcomes[index] = outcome
            latency[row["model"]].extend(audit["inference_seconds"])
            ledger.events.record(dict(type="slot_finished", outcome=outcome))
            progress = reporting.summarize(schedule, outcomes, inference_latencies=latency, draws=0)
            atomic(directory / "progress.json", dict(progress, outcomes=outcomes))
            if outcome.get("failure_scope") == "phase":
                error = dict(type="phase_halt", slot_id=row["slot_id"], reason=outcome.get("error"))
                break
    except BaseException as caught:
        error = dict(type=type(caught).__name__, detail=str(caught))
        ledger.events.record(dict(type="phase_halt", error=error))
    finally:
        try:
            manager.stop()
        except Exception as caught:
            error = dict(type="cleanup_failure", detail=str(caught), prior=error)
        ledger.events.record(dict(type="closed", remaining_seconds=ledger.remaining(), error=error))
        ledger.close()
    result = reporting.summarize(schedule, outcomes, inference_latencies=latency)
    result.update(
        outcomes=outcomes,
        phase_error=error,
        elapsed_seconds=time.time() - ledger.admission["started_at"],
        all_slots_attempted=all(row["status"] != "unattempted" for row in outcomes),
    )
    atomic(directory / "result.json", result, immutable=True)
    atomic(directory / "report.md", reporting.report_markdown(result).encode(), immutable=True)
    seal(directory)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("worker")
    command.add_argument("--attempt", type=Path, required=True)
    command.add_argument("--role", choices=("p1", "p2"), required=True)
    args = parser.parse_args(argv)
    from .player import worker

    result = asyncio.run(worker(args.attempt, args.role))
    print(compact(result))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
