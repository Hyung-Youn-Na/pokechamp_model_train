"""Archived-game reconstruction, immutable decision roots, and bounded rollouts."""
from __future__ import annotations

import base64
import copy
import json
import os
import multiprocessing
import signal
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

from .common import (ROOT, SOURCE, Budget, append, code_identity, command, derive_seed, digest,
                     file_hash, gameplay_lines, gzread, gzwrite, normalize_request, read, rows,
                     simulator_teams, verify_source, write)


def feed_response(response, actors, histories, cursors):
    """Flush actor-specific public/private HP logs before the next request."""
    for side, actor in actors.items():
        logs = response["actor_logs"][side]
        old = cursors.get(side, 0)
        if old > len(logs):
            raise ValueError("Simulator log moved backwards")
        new = logs[old:]
        actor.feed(new)
        histories[side].extend(new)
        cursors[side] = len(logs)
    requests = {}
    for event in response["messages"]:
        if event["type"] != "sideupdate":
            continue
        side, payload = event["data"].split("\n", 1)
        if "|error|" in payload or "|bigerror|" in payload:
            raise ValueError("Simulator rejected action: " + payload)
        for line in payload.splitlines():
            if line.startswith("|request|"):
                requests[side] = line
    for side, line in requests.items():
        actors[side].feed([line])
        histories[side].append("|request|" + json.dumps(actors[side].request, separators=(",", ":")))
    if response.get("errors"):
        raise ValueError("Simulator error: " + str(response["errors"]))


def expected_prefix(events, original_input):
    result = []
    boundary = original_input["boundary"]
    for event in events:
        if event["type"] != "protocol":
            continue
        if event["sequence"] > boundary["protocol_event_seq"]:
            break
        lines = event["protocol"].splitlines()
        if event["sequence"] == boundary["protocol_event_seq"]:
            lines = lines[:boundary["line_index"] + 1]
        result.extend(lines)
    return gameplay_lines(result)


def assert_equal(actual, expected, label, directory):
    if actual != expected:
        write(Path(directory) / "reconstruction-mismatch.json", dict(label=label, actual=actual, expected=expected))
        raise ValueError("Reconstruction mismatch: " + label)


def _decode_actors(data):
    from .policy import Actor
    return {side: Actor.restore(base64.b64decode(blob)) for side, blob in data.items()}


def reconstruct(directory):
    from .policy import Actor
    from .simulator import Simulator
    from ..observation.runtime import OfficialClient
    directory = Path(directory)
    manifest = read(directory / "manifest.json")
    verify_source(manifest["source_hashes"])
    if (directory / "reconstruction.json").exists():
        raise FileExistsError("Reconstruction receipt already exists")
    if str(os.environ.get("PYTHONHASHSEED")) != "964798779":
        raise ValueError("Reconstruction needs PYTHONHASHSEED=964798779 (sealed opponent process)")
    budget = Budget(directory)
    budget.reserve("reconstruction", "ex058-b19-original")
    events = gzread(directory / "source/selected-events.json.gz")
    validated_teams = simulator_teams(manifest["teams"], events)
    manifest["simulator_teams"] = validated_teams
    manifest["server_validation_reconstruction"] = "public-preview gender assignments; original packed team otherwise preserved"
    write(directory / "manifest.json", manifest)
    inputs = [r for r in events if r["type"] == "input"]
    anchors = rows(directory / "anchors.jsonl")
    original = manifest["original_request"]["slot"]
    actors = {s: Actor(s, manifest["teams"][s]["name"], original["actor_seeds"][int(s[-1]) - 1],
                       team=manifest["teams"][s]["team"]) for s in ("p1", "p2")}
    histories = {s: ["|init|battle"] for s in actors}
    cursors = {s: 0 for s in actors}
    receipts = []
    choices_log = []
    index = 0
    started = time.monotonic()
    identity = code_identity()
    try:
        with Simulator() as sim, OfficialClient("p2") as official:
            response = sim.init(validated_teams, [int(x) for x in original["battle_seed"].split(",")])
            feed_response(response, actors, histories, cursors)
            while not response["ended"]:
                if time.time() >= budget.value["admission_deadline"]:
                    raise TimeoutError("Reconstruction exceeded collection deadline")
                needs = response["needs_choice"]
                if not needs:
                    raise ValueError("Nonterminal simulator has no actionable request")
                if "p2" in needs:
                    if index >= len(inputs):
                        raise ValueError("Reconstruction requested an extra JEV decision")
                    original_input = inputs[index]
                    anchor = anchors[index]
                    assert_equal(normalize_request(response["requests"]["p2"]),
                                 normalize_request(original_input["official"]["request"]),
                                 anchor["anchor_id"] + ":request", directory)
                    assert_equal(gameplay_lines(response["actor_logs"]["p2"]),
                                 expected_prefix(events, original_input), anchor["anchor_id"] + ":protocol", directory)
                    snapshot = official.snapshot([dict(event_seq=1, protocol="\n".join(histories["p2"]))],
                                                  "ex060-" + anchor["anchor_id"], replay=True)
                    assert_equal([c["wire"] for c in snapshot["candidates"]],
                                 [c["wire"] for c in original_input["official"]["candidates"]],
                                 anchor["anchor_id"] + ":candidates", directory)
                    root = dict(anchor_id=anchor["anchor_id"], simulator=sim.snapshot(),
                                actors={s: base64.b64encode(a.snapshot()).decode() for s, a in actors.items()},
                                histories=copy.deepcopy(histories), cursors=dict(cursors),
                                needs_choice=list(needs), original_index=index,
                                actor_logs_sha256={s: digest(response["actor_logs"][s]) for s in actors},
                                own_continuation_initialization="observed-prefix; no preceding Abyssal decisions",
                                canonical_observation=anchor["observation"])
                    rootpath = directory / "private" / (anchor["anchor_id"] + ".json.gz")
                    gzwrite(rootpath, root)
                    receipts.append(dict(anchor_id=anchor["anchor_id"], root_path=str(rootpath.relative_to(directory)),
                                         root_sha256=file_hash(rootpath), request_matched=True, protocol_matched=True,
                                         candidates_matched=True, root_sha256_canonical=digest(root["simulator"])))
                choices = {}
                for side in needs:
                    if side == "p2":
                        anchor = anchors[index]
                        choices[side] = next(a["command"] for a in anchor["actions"] if a["action_id"] == anchor["original_action_id"])
                        index += 1
                    else:
                        choices[side] = actors[side].choose()
                choices_log.append(dict(turn=response["turn"], choices=choices))
                response = sim.step(choices)
                feed_response(response, actors, histories, cursors)
            assert_equal(index, 22, "decision-count", directory)
            assert_equal(response["turn"], 12, "terminal-turn", directory)
            assert_equal(response["winner"], manifest["teams"]["p1"]["name"], "terminal-winner", directory)
            full_archived = [line for event in events if event["type"] == "protocol" for line in event["protocol"].splitlines()]
            assert_equal(gameplay_lines(response["actor_logs"]["p2"]), gameplay_lines(full_archived), "terminal-protocol", directory)
            gzwrite(directory / "reconstruction-trace.json.gz", dict(public_log=response["public_log"], choices=choices_log))
        if identity != code_identity():
            raise ValueError("Source changed during reconstruction")
        receipt = dict(passed=True, anchors=receipts, decisions=index, candidate_count=167,
                       turns=12, outcome="loss", elapsed_seconds=time.monotonic() - started,
                       source_identity=identity, original_source_preserved=True)
        write(directory / "reconstruction.json", receipt)
        manifest.update(status="reconstructed", reconstruction_sha256=file_hash(directory / "reconstruction.json"))
        write(directory / "manifest.json", manifest)
        return {k: v for k, v in receipt.items() if k not in ("anchors", "source_identity")}
    except Exception as error:
        write(directory / f"reconstruction-failure-{time.time_ns()}.json", dict(type=type(error).__name__, error=str(error),
              decisions_matched=index, traceback=traceback.format_exc(), source_identity=identity))
        raise


def rollout_task(task):
    from .simulator import Simulator
    directory = Path(task["directory"])
    anchor, action, replicate = task["anchor"], task["action"], task["replicate"]
    started = time.monotonic()
    seeds = {s: derive_seed(anchor["anchor_id"], replicate, s) for s in ("p1", "p2")}
    simseed = derive_seed(anchor["anchor_id"], replicate, "simulator")
    trace = []
    record = dict(anchor_id=anchor["anchor_id"], action_id=action["action_id"], replicate=replicate,
                  attempt_id=task["attempt_id"], phase=anchor["phase"], simulator_seed=simseed, actor_seeds=seeds,
                  policy="sealed-Abyssal-both-v1", status="error", turns=0, elapsed_seconds=0)
    response = None
    deadline_hit = False
    def expired(*_):
        nonlocal deadline_hit
        deadline_hit = True
        raise TimeoutError("branch wall-clock cap")
    previous_handler = signal.signal(signal.SIGALRM, expired)
    try:
        remaining = min(120, task["deadline"] - time.time())
        if remaining <= 0:
            raise TimeoutError("collection wall-clock cap")
        signal.setitimer(signal.ITIMER_REAL, remaining)
        root = gzread(directory / "private" / (anchor["anchor_id"] + ".json.gz"))
        actors = _decode_actors(root["actors"])
        histories = root["histories"]
        cursors = root["cursors"]
        for side, actor in actors.items():
            actor.reseed(seeds[side])
        with Simulator(timeout=120) as sim:
            response = sim.restore(root["simulator"])
            sim.reseed(simseed)
            if response["needs_choice"] != root["needs_choice"]:
                raise ValueError("Restored request barrier differs")
            choices = {s: actors[s].choose() for s in response["needs_choice"] if s != "p2"}
            record["root_opponent_choice"] = choices.get("p1")
            choices["p2"] = action["command"]
            while True:
                trace.append(dict(turn=response["turn"], choices=choices))
                response = sim.step(choices)
                feed_response(response, actors, histories, cursors)
                record["turns"] = response["turn"] - anchor["turn"]
                if response["ended"]:
                    record["status"] = "draw" if not response["winner"] else "win" if response["winner"] == actors["p2"].username else "loss"
                    break
                if (record["turns"] >= 300 or time.monotonic() - started >= 120 or
                        time.time() >= task["deadline"]):
                    record.update(status="censored", reason="turn_or_time_cap")
                    break
                if not response["needs_choice"]:
                    raise ValueError("Nonterminal branch has no requested action")
                choices = {s: actors[s].choose() for s in response["needs_choice"]}
    except TimeoutError as error:
        record.update(status="censored", reason=str(error))
    except Exception as error:
        if deadline_hit:
            record.update(status="censored", reason="branch wall-clock cap")
        else:
            record.update(status="error", error=dict(type=type(error).__name__, message=str(error)))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
    record["elapsed_seconds"] = time.monotonic() - started
    tracepath = f"traces/{anchor['anchor_id']}/{action['action_id']}/{replicate:02d}-{task['attempt_id']}.json.gz"
    gzwrite(directory / tracepath, dict(public_log=response["public_log"] if response else [],
                                      choices=trace, result=record))
    record["trace_path"] = tracepath
    record["trace_sha256"] = file_hash(directory / tracepath)
    return record


def collect(directory):
    directory = Path(directory)
    manifest = read(directory / "manifest.json")
    reconstruction = read(directory / "reconstruction.json")
    if not reconstruction["passed"]:
        raise ValueError("Reconstruction gate failed")
    validation = read(directory / "validation.json")
    if not validation["passed"]:
        raise ValueError("Root restoration gate failed")
    if (validation.get("completed_roots") != 22 or
            validation.get("reconstruction_sha256") != file_hash(directory / "reconstruction.json") or
            manifest.get("reconstruction_sha256") != file_hash(directory / "reconstruction.json")):
        raise ValueError("Validation/reconstruction provenance differs")
    if validation["source_identity"] != code_identity() or reconstruction["source_identity"] != code_identity():
        raise ValueError("Source changed since reconstruction/validation; new independent validation required")
    verify_source(manifest["source_hashes"])
    for root in reconstruction["anchors"]:
        if file_hash(directory / root["root_path"]) != root["root_sha256"]:
            raise ValueError("Root changed after reconstruction")
    if (directory / "rollouts.jsonl").exists():
        raise FileExistsError("Collection already started; explicit recovery required")
    budget = Budget(directory)
    anchors = rows(directory / "anchors.jsonl")
    if len(anchors) != 22 or sum(len(a["actions"]) for a in anchors) != 167:
        raise ValueError("Collection denominator changed")
    identity = code_identity()
    manifest.update(status="collecting", collection_source=identity)
    write(directory / "manifest.json", manifest)
    tasks = [dict(directory=str(directory), anchor=a, action=act, replicate=r)
             for a in anchors for r in range(32) for act in a["actions"]]
    # Technical gate uses scheduled samples, with no extra or discarded statistical draws.
    gate_anchors = {phase: next(a for a in anchors if a["phase"] == phase)["anchor_id"]
                    for phase in ("lead", "turn_action", "forced_switch")}
    gate = [t for t in tasks if t["anchor"]["anchor_id"] in gate_anchors.values() and t["replicate"] == 0]
    gate_keys = {(t["anchor"]["anchor_id"], t["action"]["action_id"], 0) for t in gate}
    remainder = [t for t in tasks if (t["anchor"]["anchor_id"], t["action"]["action_id"], t["replicate"]) not in gate_keys]
    completed = []
    started = time.monotonic()

    def submit(pool, task):
        task = dict(task, attempt_id=budget.reserve("rollout", [task["anchor"]["anchor_id"], task["action"]["action_id"], task["replicate"]]),
                    deadline=budget.value["deadline"])
        try:
            return pool.submit(rollout_task, task), task
        except Exception as error:
            result = crash_record(task, error)
            append(directory / "rollouts.jsonl", result)
            completed.append(result)
            raise

    def crash_record(task, error):
        return dict(anchor_id=task["anchor"]["anchor_id"], action_id=task["action"]["action_id"],
                    replicate=task["replicate"], attempt_id=task["attempt_id"], status="error", turns=0,
                    elapsed_seconds=None, error=dict(type=type(error).__name__, message=str(error)))

    def consume(pool, work):
        iterator = iter(work)
        pending = {}
        exhausted = False
        failure = None
        while pending or not exhausted:
            while len(pending) < 4 and not exhausted:
                try:
                    task = next(iterator)
                except StopIteration:
                    exhausted = True
                    break
                try:
                    future, admitted = submit(pool, task)
                    pending[future] = admitted
                except Exception as error:
                    failure = error
                    exhausted = True
                    break
            if not pending:
                break
            done, _ = wait(pending, timeout=10, return_when=FIRST_COMPLETED)
            for future in done:
                admitted = pending.pop(future)
                try:
                    result = future.result()
                except Exception as error:
                    result = crash_record(admitted, error)
                append(directory / "rollouts.jsonl", result)
                completed.append(result)
                write(directory / "progress.json", dict(attempted=budget.value["attempts"], recorded=len(completed),
                      planned=5344, errors=sum(r["status"] == "error" for r in completed),
                      elapsed_seconds=time.monotonic() - started, last=result["anchor_id"]))
                if result["status"] == "error":
                    failure = RuntimeError("Branch error: " + str(result.get("error")))
                    exhausted = True
            # Every admitted task is drained into the ledger, including tasks
            # already running when the first error or admission cap occurs.
        if failure is not None:
            raise failure

    try:
        with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
            consume(pool, gate)
            gate_seconds = time.monotonic() - started
            projected_seconds = gate_seconds / len(gate) * len(remainder)
            available_seconds = budget.value["admission_deadline"] - time.time()
            feasible = projected_seconds * 1.25 < available_seconds
            write(directory / "collection-gate.json", dict(passed=True, rows=len(completed),
                  elapsed_seconds=gate_seconds, seed_samples_included=True,
                  projected_remaining_seconds=projected_seconds, throughput_margin=1.25,
                  available_seconds=available_seconds, throughput_feasible=feasible))
            if not feasible:
                raise RuntimeError("Measured gate throughput cannot fit the remaining collection window")
            consume(pool, remainder)
        if identity != code_identity():
            raise RuntimeError("Runner changed during collection")
        verify_source(manifest["source_hashes"])
        manifest.update(status="collected", recorded_rollouts=len(completed))
    except Exception as error:
        manifest.update(status="incomplete", recorded_rollouts=len(completed), error=str(error))
        write(directory / "collection-failure.json", dict(error=str(error), traceback=traceback.format_exc()))
        raise
    finally:
        write(directory / "manifest.json", manifest)
    return dict(recorded=len(completed), elapsed_seconds=time.monotonic() - started)
