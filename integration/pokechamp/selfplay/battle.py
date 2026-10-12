"""Attempt-once live matches, independently audited sampled trajectories."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

from ..imitation.player import FixedSlots, actions_and_commands, compact
from ..imitation.schema import ImitationInput, from_snapshot
from . import config
from .player import PhaseError, sampling_seed, validate_response
from .storage import atomic, jsonl, read, write_jsonl


def events(path):
    return list(jsonl(path)) if Path(path).exists() else []


def audit_match(directory, outcome):
    directory = Path(directory)
    request = read(directory / "request.json")
    row = request["slot"]
    errors = []
    counts = Counter()
    trajectories = []
    if (
        outcome["status"] == "completed"
        and outcome.get("result") not in ("win", "draw", "loss")
        or outcome["status"] != "completed"
        and outcome.get("result") is not None
    ):
        errors.append({"error": "nonterminal outcome cannot carry a win/draw/loss"})
    for side in ("p1", "p2"):
        actor = request["actors"][side]
        learner = side == row["model_side"]
        records = events(
            directory / ("events.jsonl" if learner else "opponent-events.jsonl")
        )
        submissions = [
            e["packed_team"] for e in records if e["type"] == "team_submission"
        ]
        if (submissions or outcome["status"] == "completed") and submissions != [
            row["teams"][side]["packed"]
        ]:
            errors.append({"side": side, "error": "submitted team mismatch"})
        if outcome["status"] == "completed":
            terminal = [
                line
                for e in records
                if e["type"] == "protocol"
                for line in e["protocol"].splitlines()
                if line.startswith("|win|") or line == "|tie|"
            ]
            winner_side = (
                row["model_side"]
                if outcome["result"] == "win"
                else "p2"
                if row["model_side"] == "p1"
                else "p1"
            )
            expected = (
                "|tie|"
                if outcome["result"] == "draw"
                else "|win|" + request["names"][winner_side]
            )
            if terminal != [expected]:
                errors.append({"side": side, "error": "terminal protocol mismatch"})
        if actor["kind"] != "model":
            continue
        grouped = defaultdict(list)
        for event in records:
            if event.get("decision"):
                grouped[event["decision"]].append(event)
        verified = []
        call = 0
        for decision, group in grouped.items():
            typed = {}
            try:
                for event in group:
                    if event["type"] in typed:
                        raise ValueError("duplicate decision event")
                    typed[event["type"]] = event
                entry = typed["input"]
                value = ImitationInput(entry["body_json"])
                if value.body != entry["body"] or value.sha256 != entry["input_sha256"]:
                    raise ValueError("input bytes or hash mismatch")
                if (
                    from_snapshot(entry["snapshot"], entry["actions"]).body_json
                    != value.body_json
                ):
                    raise ValueError("snapshot serialization mismatch")
                actions, commands = actions_and_commands(
                    entry["official"], FixedSlots(entry["slot_map"])
                )
                if [a["id"] for a in actions] != list(
                    value.action_ids
                ) or commands != entry["commands"]:
                    raise ValueError("official candidates/order differ")
                counts["inputs"] += int(learner)
                response = None
                if len(value.action_ids) == 1:
                    if "http_request" in typed or "response" in typed:
                        raise ValueError("automatic choice invoked model")
                    choice = value.action_ids[0]
                    probabilities = None
                else:
                    if "http_request" in typed:
                        call += 1
                        seed = sampling_seed(
                            row["model_seed"] if learner else row["opponent_seed"], call
                        )
                        envelope = {
                            "model": actor["policy"],
                            "input": value.body,
                            "seed": seed,
                        }
                        http = typed["http_request"]
                        if (
                            http["body"] != envelope
                            or http["body_json"] != compact(envelope)
                            or http["attempt"] != 1
                        ):
                            raise ValueError("request bytes or RNG sequence differs")
                    if "response" not in typed:
                        if outcome["status"] == "completed":
                            raise ValueError("completed game lacks model response")
                        continue
                    if "http_request" not in typed:
                        raise ValueError("response has no matching sampling request")
                    response = typed["response"]["body"]
                    raw = typed["http_response"]
                    if (
                        raw["status_code"] != 200
                        or json.loads(raw["raw_body"]) != response
                        or hashlib.sha256(raw["raw_body"].encode()).hexdigest()
                        != raw["raw_sha256"]
                    ):
                        raise ValueError("raw model response mismatch")
                    choice, probabilities = validate_response(
                        response,
                        value,
                        model=actor["policy"],
                        checkpoint_sha256=actor["serving"]["checkpoint_sha256"],
                        seed=seed,
                    )
                if "selection" not in typed or "wire" not in typed:
                    if outcome["status"] == "completed":
                        raise ValueError("completed decision lacks selection/wire")
                    continue
                selection, wire, revalidation = (
                    typed["selection"],
                    typed["wire"],
                    typed["revalidation"],
                )
                rqid = entry["official"]["request"]["rqid"]
                if (
                    selection["choice"] != choice
                    or selection["probabilities"] != probabilities
                    or selection["automatic"] != (len(value.action_ids) == 1)
                    or selection["command"] != commands[choice]
                    or wire["command"] != commands[choice]
                    or wire["request_id"] != rqid
                    or wire["status"] != "sent"
                ):
                    raise ValueError("selected action differs from actual wire")
                if (
                    not revalidation["passed"]
                    or revalidation["commands"] != commands
                    or any(
                        revalidation[k] != rqid
                        for k in (
                            "request_id",
                            "latest_request_id",
                            "current_request_id",
                        )
                    )
                ):
                    raise ValueError("stale or missing final revalidation")
                verified.append((wire["command"], str(rqid)))
                counts["wires"] += int(learner)
                if learner and response and outcome["status"] == "completed":
                    ids = list(value.action_ids)

                    def ordered(x, ids=ids):
                        return [x[k] for k in ids] if isinstance(x, dict) else x

                    wdl = ordered(response["wdl_probabilities"])
                    before = ordered(
                        response.get(
                            "wdl_probabilities_before", response["wdl_probabilities"]
                        )
                    )
                    after = ordered(
                        response.get(
                            "wdl_probabilities_after", response["wdl_probabilities"]
                        )
                    )
                    trajectories.append(
                        {
                            "decision_id": row["slot_id"] + ":" + decision,
                            "slot_id": row["slot_id"],
                            "input": value.body,
                            "input_sha256": value.sha256,
                            "action_ids": ids,
                            "choice": choice,
                            "log_probabilities": ordered(response["log_probabilities"]),
                            "wdl_probabilities": wdl,
                            "baseline": response["baseline"],
                            "wdl_before": before[ids.index(choice)],
                            "wdl_after": after[ids.index(choice)],
                            "outcome": {"win": "W", "draw": "D", "loss": "L"}[
                                outcome["result"]
                            ],
                            "terminal_status": "completed",
                            "round_id": row["round"],
                            "automatic": False,
                            "model_version": actor["serving"]["checkpoint_sha256"],
                            "rng_seed": seed,
                            "wire": wire["command"],
                        }
                    )
            except (KeyError, ValueError, TypeError, IndexError) as error:
                errors.append({"side": side, "decision": decision, "error": str(error)})
        actual = [
            (e["command"], e["request_id"]) for e in records if e["type"] == "ps_send"
        ]
        if actual != verified:
            errors.append(
                {"side": side, "error": "transport log differs from audited wires"}
            )
    seeds = events(directory / "battle-seed.jsonl")
    if (seeds or counts["inputs"] or outcome["status"] == "completed") and seeds != [
        {"seed": ",".join(map(str, row["simulator_seed"])), "format": "gen9ou"}
    ]:
        errors.append({"error": "simulator seed differs"})
    if outcome["status"] == "completed" and counts["inputs"] != counts["wires"]:
        errors.append({"error": "normal terminal trajectory has missing decisions"})
    return {
        "passed": not errors,
        "errors": errors,
        "counts": dict(counts),
        "valid_decisions": len(trajectories),
    }, trajectories


def base_outcome(row, status="unattempted", **extra):
    return dict(
        **{
            key: row[key]
            for key in (
                "slot_id",
                "stage",
                "round",
                "model",
                "pair_id",
                "model_side",
                "opponent",
                "simulator_seed",
            )
        },
        status=status,
        result=None,
        **extra,
    )


def match(
    directory,
    row,
    service,
    models,
    *,
    deadline,
    should_stop=lambda: False,
    tick=lambda: None,
):
    """A directory is an immutable claim; even interrupted claims cannot be replayed."""
    from .. import cli
    from ..benchmark import terminate
    from ..parallel_server import BattleServer

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    limit = time.monotonic() + min(1200, max(0, deadline - time.time()))
    ident = hashlib.sha256(row["slot_id"].encode()).hexdigest()[:12]
    names = {side: "sp" + side + ident for side in ("p1", "p2")}
    actors = {}
    for side in ("p1", "p2"):
        kind, model = models[side]
        actors[side] = {"kind": kind, "policy": model}
        if kind == "model":
            actors[side]["serving"] = {
                "endpoint": service.endpoint,
                "checkpoint_sha256": service.snapshots[model]["identity"],
            }
    atomic(
        directory / "request.json",
        {
            "slot": row,
            "names": names,
            "actors": actors,
            "deadline_monotonic": limit,
            "port": config.SHOWDOWN_PORT,
        },
        immutable=True,
    )
    server = BattleServer(
        directory, config.SHOWDOWN_PORT, ",".join(map(str, row["simulator_seed"]))
    )
    processes = {}
    streams = []
    cleanup = []
    outcome = base_outcome(row, "failed", failure_scope="phase")
    start = time.monotonic()
    try:
        if time.monotonic() >= limit or should_stop():
            outcome.update(
                status="incomplete", reason="deadline_or_signal", failure_scope="battle"
            )
        else:
            server.start()
            owned = {
                "server": {
                    "pid": server.process.pid,
                    "start_ticks": Path(f"/proc/{server.process.pid}/stat")
                    .read_text()
                    .split()[21],
                }
            }
            atomic(directory / "processes.json", owned)
            for side in ("p1", "p2"):
                seed = (
                    row["model_seed"]
                    if side == row["model_side"]
                    else row["opponent_seed"]
                )
                stream = (directory / f"{side}.log").open("xb")
                streams.append(stream)
                env = cli._child_environment(
                    PYTHONPATH=f"{config.ROOT}:{config.ROOT / 'pokechamp'}",
                    CUDA_VISIBLE_DEVICES="",
                    PYTHONHASHSEED=str(seed),
                    OMP_NUM_THREADS="1",
                    OPENBLAS_NUM_THREADS="1",
                    MKL_NUM_THREADS="1",
                    NUMEXPR_NUM_THREADS="1",
                )
                processes[side] = subprocess.Popen(
                    [
                        str(config.ACTOR_PYTHON),
                        "-m",
                        "integration.pokechamp.selfplay",
                        "actor",
                        "--attempt",
                        str(directory),
                        "--role",
                        side,
                    ],
                    cwd=config.ROOT / "pokechamp",
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                process = processes[side]
                owned[side] = {
                    "pid": process.pid,
                    "start_ticks": Path(f"/proc/{process.pid}/stat")
                    .read_text()
                    .split()[21],
                }
                atomic(directory / "processes.json", owned)
            while True:
                tick()
                if should_stop() or time.monotonic() >= limit:
                    outcome.update(
                        status="incomplete",
                        reason="signal" if should_stop() else "time_limit",
                        failure_scope="battle",
                    )
                    break
                if service.failure:
                    raise PhaseError("shared inference error: " + str(service.failure))
                results = {
                    side: read(directory / f"{side}.result.json")
                    for side in processes
                    if (directory / f"{side}.result.json").exists()
                }
                stopped = [r for r in results.values() if r["status"] != "completed"]
                if stopped:
                    original = next(
                        (r for r in stopped if r.get("failure_scope") == "phase"),
                        stopped[0],
                    )
                    outcome.update(
                        status=original["status"],
                        reason=original.get("reason"),
                        error=original.get("error"),
                        failure_scope=original["failure_scope"],
                        actor_results=results,
                    )
                    break
                if len(results) == 2:
                    own = results[row["model_side"]]
                    other = results["p2" if row["model_side"] == "p1" else "p1"]
                    if (
                        own["result"]
                        != {"win": "loss", "loss": "win", "draw": "draw"}[
                            other["result"]
                        ]
                        or own["turns"] != other["turns"]
                    ):
                        raise PhaseError("actor terminal results disagree")
                    for side, r in results.items():
                        expected = (
                            row["model_seed"]
                            if side == row["model_side"]
                            else row["opponent_seed"]
                        )
                        if (
                            r["actor"] != side
                            or r["seed"] != expected
                            or r["python_hash_seed"] != str(expected)
                        ):
                            raise PhaseError("actor RNG/role mismatch")
                    outcome.update(
                        status="completed",
                        result=own["result"],
                        turns=own["turns"],
                        battle_tag=own["battle_tag"],
                        actor_results=results,
                        failure_scope=None,
                    )
                    break
                if any(
                    p.poll() is not None and side not in results
                    for side, p in processes.items()
                ):
                    raise PhaseError("actor exited without outcome")
                time.sleep(0.1)
    except BaseException as error:  # noqa: BLE001 -- record boundary failure before owned-resource cleanup
        outcome.update(
            status="failed",
            result=None,
            error={"type": type(error).__name__, "detail": str(error)},
            failure_scope="phase",
        )
    finally:
        atomic(directory / "cancel.json", {"reason": "attempt ended"})
        for process in processes.values():
            try:
                terminate(process)
            except Exception as error:  # noqa: BLE001 -- preserve failure evidence at the execution boundary
                cleanup.append(str(error))
        for stream in streams:
            stream.close()
        try:
            server.close()
        except Exception as error:  # noqa: BLE001 -- preserve failure evidence at the execution boundary
            cleanup.append(str(error))
        if cleanup:
            outcome.update(
                status="invalid" if outcome["status"] == "completed" else "failed",
                result=None,
                failure_scope="phase",
                cleanup_errors=cleanup,
            )
        outcome.update(
            elapsed_seconds=time.monotonic() - start,
            actors_cleaned=all(p.poll() is not None for p in processes.values()),
            server_cleaned=not server.created
            and (server.process is None or server.process.poll() is not None),
        )
    try:
        audit, decisions = audit_match(directory, outcome)
    except Exception as error:  # noqa: BLE001 -- preserve failure evidence at the execution boundary
        audit, decisions = {"passed": False, "errors": [str(error)]}, []
    if not audit["passed"]:
        outcome.update(
            status="invalid" if outcome["status"] == "completed" else "failed",
            result=None,
            failure_scope="phase",
            audit_passed=False,
        )
        decisions = []
    else:
        outcome["audit_passed"] = True
    atomic(directory / "audit.json", audit, immutable=True)
    write_jsonl(directory / "decisions.jsonl", decisions, immutable=True)
    atomic(directory / "outcome.json", outcome, immutable=True)
    return outcome
