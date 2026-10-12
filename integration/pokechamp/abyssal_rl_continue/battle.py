"""EX-074 attempt-once matches and synchronous four-rank collection."""
from __future__ import annotations
import hashlib
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from ..selfplay.battle import audit_match
from ..selfplay.player import PhaseError
from . import config
from .storage import atomic, read, write_jsonl, sha
from .serving import Service

def base_outcome(row, status="unattempted", **extra):
    """Retain every frozen seed/team/evaluation assignment for independent audit."""
    return dict(row, status=status, result=None, **extra)


def match(
    directory,
    row,
    service,
    models,
    *,
    deadline,
    port,
    rank,
    global_update=0,
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
            "port": port,
            "rank": rank,
            "global_update": global_update,
        },
        immutable=True,
    )
    server = BattleServer(
        directory, port, ",".join(map(str, row["simulator_seed"]))
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


def partition_rows(rows, rank, world_size=4):
    if world_size != 4 or rank not in range(4):
        raise ValueError('EX-074 requires exactly four ranks')
    ids = [row['slot_id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate battle slot')
    return list(rows)[rank::world_size]


def _collect_wave(directory, rows, policy, snapshots, *, rank, deadline,
            should_stop=lambda: False, global_update=0, checkpoint_tick=None):
    """Collect two matches per rank; close/join every HTTP request before returning."""
    import torch.distributed as dist
    from .execution import weights_digest
    requested = {row['model'] for row in rows}
    identities = {key: {'identity': snapshots[key]['identity'],
                        'weights_sha256': weights_digest(snapshots[key]['weights'])}
                  for key in requested}
    gathered = [None] * 4
    dist.all_gather_object(gathered, identities)
    if any(value != identities for value in gathered):
        raise ValueError('collection snapshot identities differ between ranks')
    local = partition_rows(rows, rank)
    directory = Path(directory)
    stop = threading.Event()
    results = []
    def stopped():
        return stop.is_set() or should_stop()
    with Service(policy, snapshots, port=8030 + rank) as service:
        def lane(lane_id):
            values = []
            for row in local[lane_id::2]:
                game = directory / 'games' / row['slot_id']
                if game.exists():
                    if (game / 'outcome.json').exists():
                        values.append(read(game / 'outcome.json'))
                        continue
                    # An interrupted immutable claim is never retried.
                    value = base_outcome(row, 'incomplete', reason='interrupted_claim', failure_scope='battle')
                    atomic(game / 'outcome.json', value, immutable=True)
                    values.append(value)
                    continue
                if stopped() or time.time() >= deadline:
                    values.append(base_outcome(row, 'unattempted', reason='deadline_or_signal'))
                    continue
                other = 'p2' if row['model_side'] == 'p1' else 'p1'
                models = {row['model_side']: ('model', row['model']), other: ('opponent', 'abyssal')}
                result = match(game, row, service, models, deadline=deadline,
                               port=8100 + rank * 2 + lane_id, rank=rank,
                               global_update=global_update, should_stop=stopped)
                values.append(result)
                if result.get('failure_scope') == 'phase':
                    stop.set()
            return values
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(lane, i) for i in range(2)]
            last_checkpoint = (read(directory / 'latest.json')['saved_at']
                               if (directory / 'latest.json').exists() else time.time())
            while True:
                progress = [None] * 4
                local_error = next((repr(f.exception()) for f in futures
                                    if f.done() and f.exception() is not None), None)
                dist.all_gather_object(progress, {
                    'done': all(f.done() for f in futures),
                    'error': local_error,
                    'stop': stopped(),
                    'checkpoint_due': checkpoint_tick is not None and time.time() - last_checkpoint >= 900})
                if any(item['stop'] for item in progress):
                    stop.set()
                if any(item['error'] is not None for item in progress):
                    stop.set()
                    raise PhaseError('collection worker failed: ' + repr(progress))
                if any(item['checkpoint_due'] for item in progress):
                    # HTTP handlers finish their current forward first. Every rank
                    # holds its serial-inference lock through the collective save.
                    with service.lock:
                        checkpoint_tick()
                    last_checkpoint = time.time()
                if all(item['done'] for item in progress):
                    break
                time.sleep(1)
            for future in futures:
                results.extend(future.result())
    # Service.__exit__ has joined all HTTP handlers and their GPU forwards.
    dist.all_gather_object(gathered, results)
    by_id = {result['slot_id']: result for group in gathered for result in group}
    return [by_id[row['slot_id']] for row in rows]


def collect(directory, rows, policy, snapshots, *, rank, deadline,
            should_stop=lambda: False, global_update=0, tick=lambda: None, checkpoint_tick=None):
    """Eight-game synchronous waves give every rank the same safe checkpoint boundary."""
    rows = list(rows)
    partition_rows(rows, rank)  # Validate uniqueness before any immutable claims.
    if any(row.get('stage') == 'test' for row in rows):
        directory = Path(directory)
        lock = read(directory / 'evaluation-lock.json')
        if (sha(directory / 'prepared/schedule.json') != lock['schedule_sha256'] or
                sha(lock['final']['path']) != lock['final']['sha256'] or
                snapshots['selected']['identity'] != lock['final']['sha256']):
            raise ValueError('test policy or schedule differs from evaluation lock')
    results = []
    for start in range(0, len(rows), 8):
        wave = _collect_wave(directory, rows[start:start + 8], policy, snapshots,
                             rank=rank, deadline=deadline, should_stop=should_stop,
                             global_update=global_update, checkpoint_tick=checkpoint_tick)
        results.extend(wave)
        tick()  # collective checkpoints are safe: no service or GPU request remains
        if any(result.get('failure_scope') == 'phase' for result in wave):
            raise PhaseError('shared collection defect; preserve completed attempts and stop dependent stages')
    return results
