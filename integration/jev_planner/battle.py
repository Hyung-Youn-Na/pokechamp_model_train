"""Fresh, bounded Showdown matches with one synchronous planner/executor actor."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import threading
import time

from integration.pokechamp import jev_battle as j, jev_v6
from integration.jev27b.battle import ensure_current, play_owned
from .core import DecisionContext, PlanOutputError, PlanningController
from .runtime import MockExecutor, OwnedRuntime, child_environment, maybe_await, write_json
from .time_limits import battle_window, deadline_after, remaining_seconds

ROOT = j.ROOT
PORT = 8109


def validate_schedule(config):
    evaluation = config.get("evaluation", {})
    if evaluation.get("kind") != "battle":
        raise ValueError("battle execution requires evaluation.kind=battle")
    document = evaluation.get("schedule", {}).get("data")
    if not isinstance(document, dict):
        raise ValueError("a frozen schedule document is required")
    rows, teams = document.get("schedule"), document.get("teams")
    if not isinstance(rows, list) or not rows or not isinstance(teams, dict):
        raise ValueError("schedule must contain rows and named teams")
    identifiers = set()
    for row in rows:
        name = row.get("slot_id") if isinstance(row, dict) else None
        if (not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name)
                or name in identifiers):
            raise ValueError("invalid or duplicate battle slot_id")
        identifiers.add(name)
        if row.get("jev_actor") not in ("p1", "p2"):
            raise ValueError("schedule actor must be p1 or p2")
        keys = row.get("teams")
        if not isinstance(keys, list) or len(keys) != 2 or any(key not in teams for key in keys):
            raise ValueError("each battle must identify two known teams")
        for key in keys:
            if not isinstance(teams[key], dict) or not str(teams[key].get("showdown_team", "")).strip():
                raise ValueError("schedule has an empty Showdown team")
        seed = row.get("battle_seed")
        if isinstance(seed, list):
            seed = ",".join(str(item) for item in seed)
            row = dict(row, battle_seed=seed)
        if not isinstance(seed, str) or not re.fullmatch(r"\d+,\d+,\d+,\d+", seed):
            raise ValueError("battle_seed must have four comma-separated integers")
        if any(not 0 <= int(item) <= 65535 for item in seed.split(",")):
            raise ValueError("battle_seed components must be uint16")
        actor_seeds = row.get("actor_seeds")
        if (not isinstance(actor_seeds, list) or len(actor_seeds) != 2
                or any(type(seed) is not int or not 0 <= seed < 2**32 for seed in actor_seeds)):
            raise ValueError("actor_seeds must contain two uint32 values")
    limits = evaluation.get("limits", {})
    for name in ("games", "executor_calls", "battle_seconds", "total_seconds"):
        if name in ("battle_seconds", "total_seconds") and limits.get(name) is None and name in limits:
            continue
        if type(limits.get(name)) not in (int, float) or limits[name] <= 0:
            raise ValueError("positive battle limit required: " + name)
    if len(rows) > limits["games"]:
        raise ValueError("schedule exceeds game budget")
    frozen = copy.deepcopy(rows)
    for row in frozen:
        if isinstance(row["battle_seed"], list):
            row["battle_seed"] = ",".join(str(item) for item in row["battle_seed"])
    return frozen, copy.deepcopy(teams)


class Session(j.Session):
    def __init__(self, directory, *, config, mode, planner, executor, record=None,
                 before_executor=None, remaining=None):
        super().__init__(Path(directory), fake=mode == "mock", environ={}, call_limit=None,
                         collection_seconds=1, retry_policy=j.jev_retry.LEGACY)
        self.config = copy.deepcopy(config)
        self.input_version = "jev-choice-v6"
        self.mode = mode
        self.external_record = record
        self.executor = executor
        self.before_executor = before_executor
        self.external_remaining = remaining
        self.started = time.time()
        self.monotonic_started = time.monotonic()
        self.failure_event = threading.Event()
        self._decision_lock = threading.Lock()
        self._decisions = 0
        self._idle = threading.Event()
        self._idle.set()
        self.active_slot = None
        self.controller = PlanningController(config, planner, self.evaluate, self.record)

    def record(self, event):
        if self.active_slot is not None:
            event = dict(event)
            event.setdefault("slot_id", self.active_slot)
        with self.lock:
            super().record(event)
            if self.external_record is not None:
                try:
                    self.external_record(copy.deepcopy(event))
                except Exception as error:
                    self.external_record = None
                    self.fail(error)
                    raise

    def remaining(self):
        local = remaining_seconds(self.config["evaluation"]["limits"]["total_seconds"],
                                  self.monotonic_started)
        return min(local, self.external_remaining()) if self.external_remaining else local

    def begin_decision(self):
        with self._decision_lock:
            self._decisions += 1
            self._idle.clear()

    def end_decision(self):
        with self._decision_lock:
            self._decisions -= 1
            if self._decisions == 0:
                self._idle.set()

    async def evaluate(self, payload, *, decision):
        if self.failure_event.is_set() or self.remaining() <= 0:
            raise TimeoutError("executor collection halted or deadline exhausted")
        if self.calls >= self.config["evaluation"]["limits"]["executor_calls"]:
            raise RuntimeError("executor logical-call budget exhausted")
        if self.before_executor is not None:
            await maybe_await(self.before_executor, decision=decision)
        self.calls += 1
        return await self.executor(payload, decision=decision)

    async def wait_decisions(self):
        await asyncio.to_thread(self._idle.wait)

    async def close(self):
        self.failure_event.set()
        await self.controller.wait_pending()
        await self.wait_decisions()
        adapter = getattr(self, "v6_adapter", None)
        if adapter is not None:
            await asyncio.to_thread(adapter.close)


def forbid_team_substitution(player, session=None):
    """The inherited client retries invalid teams with unrelated static teams."""
    async def rejected(message):
        error = ValueError("declared Showdown team rejected; substitution forbidden")
        player.benchmark_environment_error = error
        if session is not None:
            session.fail(error)
            session.record(dict(type="team_rejection", username=player.username, message=message))
    player.ps_client._handle_team_rejection = rejected


def player_class():
    base = j.player_class()

    class PlannerJevPlayer(base):
        latest_rqid = None
        latest_request = None

        async def _handle_battle_message(self, messages):
            # Capture delivered request identity before the protocol lock. A queued
            # newer request invalidates an in-flight planner even while parsing waits.
            for fields in messages:
                if len(fields) >= 3 and fields[1] == "request":
                    request = json.loads("|".join(fields[2:])) if fields[2] else None
                    self.latest_rqid = request.get("rqid") if request else None
                    self.latest_request = copy.deepcopy(request)
            return await super()._handle_battle_message(messages)

        async def _handle_battle_request(self, battle, from_teampreview_request=False,
                                         maybe_default_order=False):
            self.session.begin_decision()
            try:
                return await self._decide(battle, from_teampreview_request, maybe_default_order)
            except PlanOutputError as error:
                self.output_error = error
                logical = (f"{self.session.active_slot}:{battle.battle_tag}"
                           if self.session.active_slot else battle.battle_tag)
                self.session.record(dict(type="battle_output_failure", username=self.username,
                    battle=logical, protocol_battle=battle.battle_tag,
                    category=error.category, error=str(error)))
            finally:
                self.session.end_decision()

        async def _decide(self, battle, from_teampreview_request=False, maybe_default_order=False):
            if maybe_default_order:
                raise ValueError("automatic default action is forbidden")
            if battle.in_team_preview and from_teampreview_request and not self.request:
                battle.move_on_next_request = True
                return
            if (battle.in_team_preview and not from_teampreview_request
                    and not (self.request or {}).get("teamPreview")):
                return
            if not self.request or self.request.get("wait"):
                return
            request = copy.deepcopy(self.request)
            actor, rqid = request["side"]["id"], request["rqid"]
            if (actor != self.expected_actor or self.latest_rqid != rqid
                    or self.latest_request != request):
                raise ValueError("unexpected actor or stale request before observation")
            if self.official is None:
                from integration.pokechamp.observation.runtime import OfficialClient
                self.official = OfficialClient(actor)
            prefix, boundary = copy.deepcopy(self.prefix), copy.deepcopy(self.boundary)
            started = time.monotonic()
            snapshot = await asyncio.to_thread(self.official.snapshot, prefix,
                                               battle.battle_tag, boundary=boundary)
            payload, commands, input_audit, _ = await jev_v6.generate(
                self.session, snapshot, prefix, self.submitted_team, actor=actor)
            logical_battle = (f"{self.session.active_slot}:{battle.battle_tag}"
                              if self.session.active_slot else battle.battle_tag)
            context = DecisionContext(logical_battle, actor, rqid, payload, commands,
                                      prefix, boundary, protocol_battle=battle.battle_tag)
            if not any(event.get("type") == "observation"
                       and event.get("decision") == context.decision_id
                       for event in self.session.records):
                audit = jev_v6.save_audit(self.session.directory, context.decision_id, input_audit)
                audit["path"] = "collection/" + audit["path"]
                self.session.record(dict(type="observation", decision=context.decision_id,
                    battle=context.battle, protocol_battle=context.protocol_battle,
                    actor=actor, rqid=rqid, boundary=boundary,
                    official=snapshot, observation_identity=self.official.identity,
                    effect_reference_identity=self.session.effect_reference_identity,
                    input_audit=audit, input_generation_seconds=time.monotonic() - started))

            async def current():
                if self.latest_request != request or (self.latest_request or {}).get("wait"):
                    raise ValueError("received request changed or was cancelled; transmission forbidden")
                if self.session.remaining() <= 0:
                    raise TimeoutError("battle collection deadline before transmission")
                latest = await asyncio.to_thread(self.official.snapshot,
                    copy.deepcopy(self.prefix), battle.battle_tag,
                    boundary=copy.deepcopy(self.boundary))
                _, current_commands = j.make_input(latest, self.prefix, actor=actor,
                    dex=self.session.dex, initial_pp_policy=self.session.initial_pp_policy)
                if self.latest_request != request:
                    raise ValueError("received request changed during revalidation; transmission forbidden")
                ensure_current(rqid, self.latest_rqid, self.request, commands,
                               current_commands, self.session.failure_event.is_set())
                return True

            result = await self.session.controller.decide(context, ensure_current=current)
            await current()
            if not self.session.controller.mark_sent(context):
                self.session.record(dict(type="wire_duplicate_skipped", decision=result.decision_id,
                                         battle=context.battle, protocol_battle=context.protocol_battle,
                                         actor=actor, request_id=rqid))
                return
            await self.ps_client.send_message(result.command, battle.battle_tag, str(rqid))
            self.session.record(dict(type="wire", decision=result.decision_id,
                battle=context.battle, protocol_battle=context.protocol_battle,
                actor=actor, command=result.command,
                request_id=rqid, status="sent", mock=self.session.mode == "mock"))

    return PlannerJevPlayer


async def bot_worker(directory):
    """The existing Abyssal opponent runs under its own actor seed/process."""
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from integration.pokechamp import cli
    from integration.pokechamp.battle_adapter import guard_parser, install_identity_adapter
    from integration.pokechamp.jev_study import play
    directory = Path(directory)
    request = json.loads((directory / "request.json").read_text())
    row = request["slot"]
    role = "p2" if row["jev_actor"] == "p1" else "p1"
    index = int(role[-1]) - 1
    seed = row["actor_seeds"][index]
    random.seed(seed)
    np.random.seed(seed)
    install_identity_adapter()
    player = AbyssalPlayer(team=request["teams"][row["teams"][index]]["showdown_team"],
        battle_format="gen9ou", max_concurrent_battles=1, start_timer_on_battle_start=False,
        account_configuration=AccountConfiguration(request["names"][role], None),
        server_configuration=ServerConfiguration(f"localhost:{request['showdown_port']}",
                                                "https://play.pokemonshowdown.com/action.php?"))
    guard_parser(player)
    forbid_team_substitution(player)
    result = dict(completed=False, actor=role, pid=os.getpid(), python_random_seed=seed,
                  numpy_random_seed=seed, python_hash_seed=os.environ.get("PYTHONHASHSEED"),
                  watchdog_seconds=request["watchdog_seconds"])
    try:
        result.update(await play(player, role, request["names"], directory,
            deadline=deadline_after(request["watchdog_seconds"])))
    except BaseException as error:
        result["error"] = dict(type=type(error).__name__, detail=str(error))
    finally:
        await cli._close_players([player])
        write_json(directory / f"{role}.result.json", result)
    return result


async def run_match(session, row, teams, attempt, *, port=PORT):
    if Path.cwd().resolve() != ROOT / "pokechamp":
        raise ValueError("battle actor requires /workspace/pokechamp working directory")
    import numpy as np
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from integration.pokechamp import cli
    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.parallel_server import BattleServer
    from integration.pokechamp.jev_study import play
    install_identity_adapter()
    role = row["jev_actor"]
    other = "p2" if role == "p1" else "p1"
    seed = row["actor_seeds"][int(role[-1]) - 1]
    identity = hashlib.sha256(f"{attempt}:{row['slot_id']}".encode()).hexdigest()[:12]
    names = {role: "jpl" + identity, other: "aby" + identity}
    outcome = dict(row, username=names[role], completed=False, status="failed")
    server = BattleServer(attempt, port, row["battle_seed"])
    process = log = player = None
    technical = None
    try:
        await asyncio.to_thread(server.start)
        seconds = battle_window(session.config["evaluation"]["limits"]["battle_seconds"], session.remaining())
        if seconds is not None and seconds <= 0:
            raise TimeoutError("battle deadline before admission")
        deadline = deadline_after(seconds)
        write_json(attempt / "request.json", dict(slot=row, teams=teams, names=names,
                    watchdog_seconds=seconds, showdown_port=port, mode=session.mode))
        environment = child_environment()
        environment.update(PYTHONHASHSEED=str(row["actor_seeds"][int(other[-1]) - 1]),
                           OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
        log = (attempt / "abyssal.log").open("x")
        process = subprocess.Popen([str(ROOT / "pokechamp/.venv/bin/python"), "-B", "-m",
            "integration.jev_planner.battle", "bot", "--output", str(attempt)],
            cwd=ROOT / "pokechamp", env=environment, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        outcome.update(abyssal_pid=process.pid, jev_pid=os.getpid(),
                       python_random_seed=seed, numpy_random_seed=seed,
                       watchdog_seconds=seconds)
        random.seed(seed)
        np.random.seed(seed)
        player = player_class()(session=session, expected_actor=role,
            team=teams[row["teams"][int(role[-1]) - 1]]["showdown_team"], battle_format="gen9ou",
            max_concurrent_battles=1, start_timer_on_battle_start=False,
            account_configuration=AccountConfiguration(names[role], None),
            server_configuration=ServerConfiguration(f"localhost:{port}",
                                                     "https://play.pokemonshowdown.com/action.php?"))
        forbid_team_substitution(player, session)
        async def bounded_play(*args, **kwargs):
            kwargs["deadline"] = deadline
            return await play(*args, **kwargs)
        outcome.update(await play_owned(player, role, names, attempt, session=session,
            process=process, server=server, play_function=bounded_play))
        await asyncio.to_thread(process.wait, 15)
        peer = json.loads((attempt / f"{other}.result.json").read_text())
        opposite = {"player_won": "player_lost", "player_lost": "player_won", "tied": "tied"}
        if (process.returncode or not peer["completed"] or peer["actor"] != other
                or peer["outcome"] != opposite[outcome["outcome"]]
                or peer["turns"] != outcome["turns"]
                or peer["python_random_seed"] != row["actor_seeds"][int(other[-1]) - 1]):
            raise ValueError("opponent terminal outcome or actor seed mismatch")
        outcome["status"] = "completed"
        outcome["battle"] = f"{row['slot_id']}:{outcome['battle_tag']}"
    except (PlanOutputError, j.UnusableChoice) as error:
        outcome.update(completed=False, outcome="output_failure", failure_scope="battle",
                       error=dict(type=type(error).__name__, detail=str(error)))
    except BaseException as error:
        technical = error
        session.fail(error)
        outcome.update(completed=False, failure_scope="collection",
                       error=dict(type=type(error).__name__, detail=str(error)))
    finally:
        failures = []
        try:
            write_json(attempt / "cancel.json", dict(reason="attempt ended"))
        except BaseException as error:
            failures.append(error)
        if player is not None:
            try:
                await cli._close_players([player])
                for tag in player.battles:
                    logical_battle = f"{row['slot_id']}:{tag}"
                    outcome.setdefault("battle", logical_battle)
                    outcome.setdefault("battle_tag", tag)
                    session.controller.end_battle(logical_battle, role)
                    await session.controller.wait_pending(logical_battle, role)
                await session.wait_decisions()
                if player.official is not None:
                    await asyncio.to_thread(player.official.close)
            except BaseException as error:
                failures.append(error)
        if process is not None and process.poll() is None:
            from integration.pokechamp.benchmark import terminate
            try:
                await asyncio.to_thread(terminate, process)
            except BaseException as error:
                failures.append(error)
        if log is not None:
            try:
                log.close()
            except BaseException as error:
                failures.append(error)
        try:
            await asyncio.to_thread(server.close)
        except BaseException as error:
            failures.append(error)
        if failures:
            technical = technical or failures[0]
            session.fail(technical)
            outcome.update(completed=False, status="failed", failure_scope="collection",
                cleanup_errors=[dict(type=type(e).__name__, detail=str(e)) for e in failures])
        outcome["server_cleaned"] = not server.created and (
            server.process is None or server.process.poll() is not None)
        outcome["opponent_cleaned"] = process is None or process.poll() is not None
        if not outcome["completed"]:
            outcome["status"] = "failed"
        try:
            write_json(attempt / "outcome.json", outcome)
        except BaseException as error:
            technical = technical or error
            session.fail(technical)
            outcome.update(completed=False, status="failed", failure_scope="collection",
                artifact_error=dict(type=type(error).__name__, detail=str(error)))
    return outcome, technical


async def run_condition(directory, config, *, mode, planner, executor=None, record=None,
                        before_executor=None, remaining=None):
    """Attempt every declared slot once; technical failures stop later admission."""
    from .config import validate_mode
    validate_mode(config, mode)
    if mode not in ("mock", "live"):
        raise ValueError("battle mode must be explicitly mock or live")
    schedule, teams = validate_schedule(config)
    directory = Path(directory).resolve()
    collection = directory / "collection"
    collection.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    def time_left():
        local = remaining_seconds(config["evaluation"]["limits"]["total_seconds"], started)
        return min(local, remaining()) if remaining else local
    session = runtime = None
    outcomes, error = [], None
    try:
        session = Session(collection, config=config, mode=mode, planner=planner,
            executor=executor, record=record, before_executor=before_executor, remaining=time_left)
        if executor is None:
            if mode == "mock":
                executor = MockExecutor(session.record)
            else:
                runtime = OwnedRuntime(directory, config, record=session.record, remaining=time_left)
                executor = await runtime.start()
                if config["executor"]["model"] in ("jev35b-nvfp4", "jev-omni", "tacit9b", "tacit9b-vllm"):
                    if config["executor"]["model"] == "tacit9b-vllm":
                        from integration.tacit9b_vllm.preflight import run_preflight
                    elif config["executor"]["model"] == "tacit9b":
                        from integration.tacit9b.preflight import run_preflight
                    elif config["executor"]["model"] == "jev-omni":
                        from integration.jev_omni.preflight import run_preflight
                    else:
                        from integration.jev35b_nvfp4.preflight import run_preflight
                    await run_preflight(config, executor, runtime.directory, before_executor=before_executor)
            session.executor = executor
        write_json(collection / "manifest.json", dict(mode=mode, schedule=schedule, teams=teams,
                                                     config=config))
        for number, row in enumerate(schedule, 1):
            if session.failure_event.is_set() or time_left() <= 0:
                raise TimeoutError("collection halted or total deadline exhausted")
            session.active_slot = row["slot_id"]
            attempt = collection / f"battle-{number}"
            attempt.mkdir()
            outcomes.append(dict(row, slot=number, status="failed", completed=False,
                                 failure_scope="collection"))
            try:
                outcome, technical = await run_match(session, row, teams, attempt,
                    port=config["evaluation"].get("showdown_port", PORT))
            except BaseException as failure:
                outcomes[-1]["error"] = dict(type=type(failure).__name__, detail=str(failure))
                raise
            outcomes[-1] = dict(slot=number, **outcome)
            session.record(dict(type="battle_result", **outcomes[-1]))
            if technical is not None:
                raise technical
    except (Exception, asyncio.CancelledError, KeyboardInterrupt) as failure:
        error = dict(type=type(failure).__name__, detail=str(failure), scope="collection")
        if session is not None:
            session.fail(failure)
            try:
                session.record(dict(type="failure", error=error))
            except BaseException as recording_error:
                error["recording_error"] = dict(type=type(recording_error).__name__,
                                                detail=str(recording_error))
    finally:
        for resource in (session, runtime):
            if resource is not None:
                try:
                    await resource.close()
                except BaseException as failure:
                    error = dict(type=type(failure).__name__, detail=str(failure), scope="collection",
                                 previous_error=error)
                    if session is not None:
                        try:
                            session.record(dict(type="cleanup_failure", error=error))
                        except BaseException as recording_error:
                            error["recording_error"] = dict(type=type(recording_error).__name__,
                                                            detail=str(recording_error))
    attempted = len(outcomes)
    outcomes.extend(dict(row, status="unattempted", completed=False)
                    for row in schedule[attempted:])
    result = dict(mode=mode, kind="battle", planned=len(schedule), attempted=attempted,
        completed=sum(row["status"] == "completed" for row in outcomes),
        failed=sum(row["status"] == "failed" for row in outcomes),
        unattempted=len(schedule) - attempted, outcomes=outcomes, error=error,
        executor_calls=session.calls if session else 0, elapsed_seconds=time.monotonic() - started,
        efficacy_evidence=False, empirical_data=mode == "live", passed=error is None,
        real_model_inferences=0 if mode == "mock" else None,
        external_requests=0 if mode == "mock" else None)
    write_json(collection / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bot",))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(asyncio.run(bot_worker(args.output)), ensure_ascii=False))


if __name__ == "__main__":
    main()
