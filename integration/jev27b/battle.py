"""EX-082 local Choice transport and the unchanged EX-058 battle input."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import threading
import time

from integration.pokechamp import jev_battle as j, jev_v4

ROOT = j.ROOT
MODEL = "autotrust/JEV-27B"
REVISION = "51740a8891c2a8baefd969237fd44187b3e3a115"
ENDPOINT = "http://127.0.0.1:18782"
TIMEOUT = 600.0
RETRY_DELAYS = (10.0, 30.0, 60.0)
TRANSPORT_POLICY = "jev27b-local-idempotent-v1"
PORT = 8109


def ensure_current(rqid, latest_rqid, request, commands, current_commands, failed):
    """Validate the request delivered before the protocol lock as well as its state."""
    if failed or latest_rqid != rqid or request.get("rqid") != rqid:
        raise ValueError("stale request; transmission forbidden")
    if commands != current_commands:
        raise ValueError("changed legal actions; transmission forbidden")


def validate_health(health, expected_identity):
    if not isinstance(health, dict) or health.get("ready") is not True:
        raise ValueError("local JEV server is not ready")
    if health.get("identity", health.get("serving_identity")) != expected_identity:
        raise ValueError("local JEV serving identity changed")
    if health.get("revision") != REVISION:
        raise ValueError("local JEV model revision changed")
    if health.get("model", MODEL) != MODEL:
        raise ValueError("local JEV model changed")
    return health


class Session(j.Session):
    """One logical decision, at most four HTTP attempts, and no elapsed-time cap."""

    def __init__(self, directory, *, expected_identity, endpoint=ENDPOINT,
                 client_factory=None):
        # Preserve the old Session's observation setup and fsync event recording.
        # Its historical budget implementation is not used by this profile.
        super().__init__(Path(directory), environ={}, call_limit=None,
                         collection_seconds=1, retry_policy=j.jev_retry.LEGACY)
        if not isinstance(expected_identity, str) or not expected_identity:
            raise ValueError("a frozen serving identity is required")
        self.expected_identity = expected_identity
        from .client import base_url
        self.endpoint = base_url(endpoint)
        self.input_version = jev_v4.VERSION
        self.retry_policy = TRANSPORT_POLICY
        self.capture_request_body = True
        self.collection_seconds = None
        self.logical_calls = 0
        # poke-env handles protocol frames on its own event-loop thread. The
        # collector/liveness monitor may halt it from the main loop.
        self.failure_event = threading.Event()
        self._decision_lock = threading.Lock()
        self._decision_count = 0
        self._decisions_idle = threading.Event()
        self._decisions_idle.set()
        self._inference_lock = asyncio.Lock()
        self._request_ids = set()
        if client_factory is None:
            from .client import LocalClient
            client_factory = LocalClient
        self.client = client_factory(endpoint=self.endpoint,
                                     expected_identity=expected_identity, timeout=TIMEOUT)
        self._ledger()

    def remaining(self):
        return float("inf")

    def _ledger(self):
        from .study import write_json
        write_json(self.directory / "ledger.json", dict(
            first_request_at=self.started, requests=self.calls,
            logical_requests=self.logical_calls, limit=None, deadline=None,
            transport_policy=TRANSPORT_POLICY, serving_identity=self.expected_identity))

    async def health(self):
        result = await asyncio.to_thread(self.client.health)
        return validate_health(result, self.expected_identity)

    async def _backoff(self, seconds):
        end = time.monotonic() + seconds
        while True:
            if self.failure_event.is_set():
                raise RuntimeError("local JEV collection cancelled during retry wait")
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            await asyncio.sleep(min(0.1, remaining))

    def begin_decision(self):
        with self._decision_lock:
            self._decision_count += 1
            self._decisions_idle.clear()

    def end_decision(self):
        with self._decision_lock:
            self._decision_count -= 1
            if self._decision_count == 0:
                self._decisions_idle.set()

    async def evaluate(self, payload, *, decision=None):
        from .client import LocalRequestError, request_bytes
        if not decision or decision in self._request_ids:
            raise ValueError("missing or duplicate logical decision")
        body = dict(model=MODEL, **copy.deepcopy(payload))
        encoded = request_bytes(body)
        body_sha256 = hashlib.sha256(encoded).hexdigest()
        request_id = "ex082-" + hashlib.sha256(
            (str(self.directory.resolve()) + ":" + decision).encode()).hexdigest()
        async with self._inference_lock:
            if decision in self._request_ids:
                raise ValueError("duplicate logical decision")
            if self.failure_event.is_set():
                raise RuntimeError("local JEV collection halted")
            self._request_ids.add(decision)
            await self.health()
            if self.started is None:
                self.started, self.monotonic_started = time.time(), time.monotonic()
            self.logical_calls += 1
            for attempt in range(1, len(RETRY_DELAYS) + 2):
                if self.failure_event.is_set():
                    raise RuntimeError("local JEV collection halted")
                self.calls += 1
                number = self.calls
                self._ledger()
                common = dict(decision=decision, request_number=number, attempt=attempt,
                              request_id=request_id, body_sha256=body_sha256)
                self.record(dict(type="transport", endpoint=self.endpoint + "/v1/systemone",
                    model=MODEL, timeout=TIMEOUT, serving_identity=self.expected_identity, **common))
                self.record(dict(type="http_request", body=body,
                                 raw_body=encoded.decode("utf-8"), **common))
                started = time.monotonic()
                failure = None

                def call():
                    try:
                        return self.client.evaluate(body, request_id=request_id, retries=0)
                    finally:
                        metadata = copy.deepcopy(getattr(self.client, "last_transport", None))
                        if metadata is not None:
                            self.record(dict(type="local_transport", metadata=metadata, **common))
                            if metadata.get("status_code") is not None:
                                self.record(dict(type="http_response", **common,
                                    status_code=metadata["status_code"],
                                    raw_body=metadata.get("raw_body", ""),
                                    elapsed_seconds=metadata.get("elapsed_seconds",
                                        time.monotonic() - started),
                                    cache_reused=metadata.get("cache_reused")))

                task = asyncio.create_task(asyncio.to_thread(call))
                try:
                    # The client's 600-second socket timeout owns each attempt. Shielding
                    # preserves a late response if the outer collection is cancelled.
                    response = await asyncio.shield(task)
                    return response
                except asyncio.CancelledError:
                    self.record(dict(type="request_cancelled", **common))
                    await asyncio.gather(task, return_exceptions=True)
                    raise
                except LocalRequestError as exc:
                    failure = exc
                self.record(dict(type="attempt_failure", category=failure.category,
                    status_code=failure.status_code, retryable=failure.retryable,
                    elapsed_seconds=time.monotonic() - started, **common))
                if not failure.retryable or attempt > len(RETRY_DELAYS):
                    raise failure
                delay = RETRY_DELAYS[attempt - 1]
                self.record(dict(type="provider_retry", next_attempt=attempt + 1,
                                 delay_seconds=delay, **common))
                await self._backoff(delay)

    async def wait_decisions(self):
        # Preserve late HTTP evidence before the source bundle is sealed. HTTP
        # attempts have their own 600-second communication timeout.
        await asyncio.to_thread(self._decisions_idle.wait)

    async def close(self):
        self.failure_event.set()
        await self.wait_decisions()
        if getattr(self, "v4_adapter", None) is not None:
            await asyncio.to_thread(self.v4_adapter.close)
        if callable(getattr(self.client, "close", None)):
            await asyncio.to_thread(self.client.close)


def player_class():
    base = j.player_class()

    class LocalJevPlayer(base):
        latest_rqid = None

        async def _handle_battle_message(self, messages):
            for fields in messages:
                if len(fields) >= 3 and fields[1] == "request":
                    request = json.loads("|".join(fields[2:])) if fields[2] else None
                    self.latest_rqid = request.get("rqid") if request else None
            return await super()._handle_battle_message(messages)

        async def _handle_battle_request(self, battle, from_teampreview_request=False,
                                         maybe_default_order=False):
            self.session.begin_decision()
            try:
                return await self._decide(battle, from_teampreview_request,
                                          maybe_default_order)
            finally:
                self.session.end_decision()

        async def _decide(self, battle, from_teampreview_request=False,
                          maybe_default_order=False):
            if maybe_default_order:
                raise ValueError("automatic default forbidden")
            if battle.in_team_preview and from_teampreview_request and not self.request:
                battle.move_on_next_request = True
                return
            if (battle.in_team_preview and not from_teampreview_request
                    and not (self.request or {}).get("teamPreview")):
                return
            if not self.request or self.request.get("wait"):
                return
            actor = self.request["side"]["id"]
            if actor != self.expected_actor:
                raise ValueError("unexpected scheduled actor")
            rqid = self.request.get("rqid")
            if self.latest_rqid != rqid:
                raise ValueError("stale request before input generation")
            if self.official is None:
                from integration.pokechamp.observation.runtime import OfficialClient
                self.official = OfficialClient(actor)
            started = time.monotonic()
            snapshot = await asyncio.to_thread(self.official.snapshot,
                copy.deepcopy(self.prefix), battle.battle_tag, boundary=self.boundary)
            input_started = time.monotonic()
            payload, commands, input_audit, _ = await jev_v4.generate(
                self.session, snapshot, self.prefix, self.submitted_team, actor=actor)
            criteria = payload["questions"]["action"]["criteria"]
            if list(criteria) != list(commands):
                raise ValueError("candidate order and command order differ")
            decision = f"{self.username}-{rqid}-{len(self.session.records)}"
            self.session.record(dict(type="input", decision=decision,
                battle=battle.battle_tag, actor=actor, payload=payload, commands=commands,
                boundary=self.boundary, official=snapshot,
                observation_identity=self.official.identity,
                effect_reference_identity=self.session.effect_reference_identity,
                input_audit=jev_v4.save_audit(self.session.directory, decision, input_audit),
                input_generation_seconds=time.monotonic() - input_started))
            inference_started = time.monotonic()
            body = None
            if len(criteria) == 1:
                choice = next(iter(criteria))
            else:
                body = await self.session.evaluate(payload, decision=decision)
                self.session.record(dict(type="response", decision=decision, body=body,
                    elapsed_seconds=time.monotonic() - inference_started))
                choice = j.validate_answer(body, criteria, version=j.VALIDATION_VERSION)
                self.session.record(dict(type="judgment_diagnostics", decision=decision,
                    diagnostics=j.judgment_diagnostics(body["answers"]["action"], criteria)))
            current = await asyncio.to_thread(self.official.snapshot,
                copy.deepcopy(self.prefix), battle.battle_tag, boundary=self.boundary)
            _, current_commands = j.make_input(current, self.prefix, actor=actor,
                dex=self.session.dex, initial_pp_policy=self.session.initial_pp_policy)
            ensure_current(rqid, self.latest_rqid, self.request, commands,
                           current_commands, self.session.failure_event.is_set())
            command = commands[choice]
            self.session.record(dict(type="selection", decision=decision, choice=choice,
                command=command, automatic=body is None,
                elapsed_seconds=time.monotonic() - inference_started,
                decision_seconds=time.monotonic() - started,
                revalidated_request_id=rqid, latest_request_id=self.latest_rqid,
                revalidated_commands=current_commands))
            await self.ps_client.send_message(command, battle.battle_tag, str(rqid))
            self.session.record(dict(type="wire", decision=decision, command=command,
                                    request_id=rqid, status="sent"))

    return LocalJevPlayer


async def play_owned(player, role, names, attempt, *, session, process, server,
                     play_function=None):
    """Wait indefinitely for play, while detecting an owned process that died."""
    if play_function is None:
        from integration.pokechamp.jev_study import play as play_function
    task = asyncio.create_task(play_function(player, role, names, attempt,
        session=session, deadline=float("inf")))
    other = "p2" if role == "p1" else "p1"
    try:
        while not task.done():
            if server.process is None or server.process.poll() is not None:
                error = RuntimeError("owned Showdown process exited during battle")
                session.fail(error)
                raise error
            code = process.poll()
            if code is not None:
                peer_path = Path(attempt) / f"{other}.result.json"
                peer = json.loads(peer_path.read_text()) if peer_path.is_file() else None
                if code != 0 or not peer or peer.get("completed") is not True or peer.get("error"):
                    error = RuntimeError("owned Abyssal process exited without a normal result")
                    session.fail(error)
                    raise error
            await asyncio.wait({task}, timeout=0.1)
        return await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def bot_worker(attempt):
    """The historical Abyssal actor, in its own process and RNG namespace."""
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from integration.pokechamp import cli
    from integration.pokechamp.battle_adapter import guard_parser, install_identity_adapter
    from integration.pokechamp.jev_study import play
    from .study import write_json

    install_identity_adapter()
    attempt = Path(attempt)
    request = json.loads((attempt / "request.json").read_text())
    row = request["slot"]
    role = "p2" if row["jev_actor"] == "p1" else "p1"
    index = int(role[-1]) - 1
    seed = row["actor_seeds"][index]
    random.seed(seed)
    np.random.seed(seed)
    player = AbyssalPlayer(
        team=request["teams"][row["teams"][index]]["showdown_team"],
        battle_format="gen9ou", max_concurrent_battles=1,
        start_timer_on_battle_start=False,
        account_configuration=AccountConfiguration(request["names"][role], None),
        server_configuration=ServerConfiguration(
            f"localhost:{PORT}", "https://play.pokemonshowdown.com/action.php?"))
    guard_parser(player)
    result = dict(completed=False, pid=os.getpid(), actor=role,
        python_random_seed=seed, numpy_random_seed=seed,
        python_hash_seed=os.environ.get("PYTHONHASHSEED"))
    try:
        result.update(await play(player, role, request["names"], attempt,
                                 deadline=float("inf")))
    except BaseException as exc:
        result["error"] = dict(type=type(exc).__name__, detail=str(exc))
    finally:
        await cli._close_players([player])
        write_json(attempt / f"{role}.result.json", result)
    return result


async def run(directory, *, expected_identity, gate_receipt, endpoint=ENDPOINT):
    """Attempt every frozen slot once; a technical failure prevents later admission."""
    import numpy as np
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from integration.pokechamp import cli
    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.parallel_server import BattleServer
    from . import audit, study

    directory = Path(directory).resolve()
    if directory != study.LIVE:
        raise ValueError("EX-082 live output is fixed")
    if directory.exists():
        raise FileExistsError("EX-082 cannot resume or overwrite an existing attempt")
    if Path.cwd().resolve() != ROOT / "pokechamp":
        raise ValueError("EX-082 battle actor requires /workspace/pokechamp working directory")
    manifest = study.prepare_manifest(expected_identity, gate_receipt, endpoint=endpoint)
    directory.mkdir(parents=True, exist_ok=False)
    session = Session(directory, expected_identity=expected_identity, endpoint=endpoint)
    outcomes, error = [], None
    try:
        study.write_json(directory / "manifest.json", manifest)
        study.write_json(directory / "entry-gates.json", gate_receipt)
        study.snapshot_sources(directory, manifest["source"])
        install_identity_adapter()
        for number, row in enumerate(manifest["schedule"], 1):
            if session.failure_event.is_set():
                raise RuntimeError("local JEV collection halted")
            study.verify_live_identity(manifest)
            await session.health()
            attempt = directory / f"battle-{number}"
            attempt.mkdir()
            role = row["jev_actor"]
            other = "p2" if role == "p1" else "p1"
            seed = row["actor_seeds"][int(role[-1]) - 1]
            identity = hashlib.sha256(f"{directory}:{row['slot_id']}".encode()).hexdigest()[:12]
            names = {role: "jev" + identity, other: "aby" + identity}
            outcome = dict(slot=number, **row, username=names[role], completed=False,
                audit_passed=False, jev_pid=os.getpid(), python_random_seed=seed,
                numpy_random_seed=seed)
            outcomes.append(outcome)
            start_event, start_calls = len(session.records), session.calls
            server = BattleServer(attempt, PORT, row["battle_seed"])
            process = log = player = None
            technical = None
            try:
                await asyncio.to_thread(server.start)
                study.write_json(attempt / "request.json", dict(slot=row,
                    teams=manifest["teams"], names=names, watchdog_seconds=None))
                child_env = cli._child_environment(
                    PYTHONPATH=f"{ROOT}:{ROOT / 'pokechamp'}",
                    PYTHONHASHSEED=str(row["actor_seeds"][int(other[-1]) - 1]),
                    OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
                log = (attempt / "abyssal.log").open("xb")
                process = subprocess.Popen([
                    str(ROOT / "pokechamp/.venv/bin/python"), "-m",
                    "integration.jev27b.battle", "bot", "--output", str(attempt)],
                    cwd=ROOT / "pokechamp", env=child_env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                outcome["abyssal_pid"] = process.pid
                random.seed(seed)
                np.random.seed(seed)
                player = player_class()(session=session, expected_actor=role,
                    team=manifest["teams"][row["teams"][int(role[-1]) - 1]]["showdown_team"],
                    battle_format="gen9ou", max_concurrent_battles=1,
                    start_timer_on_battle_start=False,
                    account_configuration=AccountConfiguration(names[role], None),
                    server_configuration=ServerConfiguration(
                        f"localhost:{PORT}", "https://play.pokemonshowdown.com/action.php?"))
                outcome.update(await play_owned(player, role, names, attempt,
                    session=session, process=process, server=server))
                await asyncio.to_thread(process.wait, 15)
                peer = json.loads((attempt / f"{other}.result.json").read_text())
                complement = {"player_won": "player_lost", "player_lost": "player_won", "tied": "tied"}
                if (process.returncode or not peer["completed"]
                        or peer["outcome"] != complement[outcome["outcome"]]
                        or peer["turns"] != outcome["turns"] or peer["actor"] != other
                        or peer["python_random_seed"] != row["actor_seeds"][int(other[-1]) - 1]):
                    raise ValueError("opponent terminal or seed mismatch")
            except j.UnusableChoice as exc:
                outcome.update(completed=False, outcome="output_failure", failure_scope="battle",
                    error=dict(type=type(exc).__name__, detail=str(exc)))
            except BaseException as exc:
                technical = exc
                session.fail(exc)
                outcome.update(failure_scope="collection",
                    error=dict(type=type(exc).__name__, detail=str(exc)))
            finally:
                study.write_json(attempt / "cancel.json", dict(reason="attempt ended"))
                cleanup_errors = []
                if player is not None:
                    try:
                        await cli._close_players([player])
                    except BaseException as exc:
                        cleanup_errors.append(exc)
                    try:
                        await session.wait_decisions()
                    except BaseException as exc:
                        cleanup_errors.append(exc)
                    try:
                        if player.official is not None:
                            player.official.close()
                    except BaseException as exc:
                        cleanup_errors.append(exc)
                if process is not None and process.poll() is None:
                    try:
                        from integration.pokechamp.benchmark import terminate
                        await asyncio.to_thread(terminate, process)
                    except BaseException as exc:
                        cleanup_errors.append(exc)
                if log is not None:
                    try:
                        log.close()
                    except BaseException as exc:
                        cleanup_errors.append(exc)
                try:
                    await asyncio.to_thread(server.close)
                except BaseException as exc:
                    cleanup_errors.append(exc)
                if cleanup_errors:
                    technical = technical or cleanup_errors[0]
                    session.fail(technical)
                    outcome["cleanup_errors"] = [dict(type=type(exc).__name__, detail=str(exc))
                                                 for exc in cleanup_errors]
                    outcome.setdefault("error", dict(type=type(technical).__name__, detail=str(technical)))
                    outcome["failure_scope"] = "collection"
                outcome["server_cleaned"] = not server.created and (
                    server.process is None or server.process.poll() is not None)
                outcome["opponent_cleaned"] = process is None or process.poll() is not None
                outcome["requests"] = session.calls - start_calls
                study.write_json(attempt / "outcome.json", outcome)
            partial = study.summarize(session, [outcome], manifest["schedule"], error=None)
            partial["requests"] = outcome["requests"]
            partial["sent_actions"] = sum(e["type"] == "wire" for e in session.records[start_event:])
            check = await asyncio.to_thread(audit.audit, directory, checkpoint=True,
                events=session.records[start_event:], result=partial)
            outcome["audit_passed"] = check["passed"]
            study.write_json(attempt / "audit.json", check)
            study.write_json(attempt / "outcome.json", outcome)
            if not check["passed"]:
                raise ValueError("per-match technical audit failed: " + repr(check["errors"]))
            if technical is not None:
                raise technical
            progress = study.summarize(session, outcomes, manifest["schedule"])
            study.write_json(directory / "progress.json", progress)
            print(json.dumps(dict(slot=number, slot_id=row["slot_id"],
                completed=progress["completed"], outcome=outcome.get("outcome"),
                requests=session.calls, elapsed=progress["elapsed_collection_seconds"])), flush=True)
    except (Exception, asyncio.CancelledError) as exc:
        error = dict(type=type(exc).__name__, detail=str(exc))
        session.fail(exc)
        session.record(dict(type="failure", error=error))
    finally:
        await session.close()
    try:
        study.verify_live_identity(manifest)
    except Exception as exc:
        error = dict(type=type(exc).__name__, detail=str(exc))
    result = study.summarize(session, outcomes, manifest["schedule"], error=error)
    study.write_json(directory / "result.json", result)
    study.seal(directory)
    checked = await asyncio.to_thread(audit.audit, directory)
    study.write_json(directory / "final-audit.json", checked)
    result["final_audit_passed"] = checked["passed"]
    if not checked["passed"]:
        result["passed"] = False
        result["validity"] = "withheld_pending_final_audit"
        result["error"] = result["error"] or dict(type="FinalAuditFailure", detail=repr(checked["errors"]))
    study.write_json(directory / "result.json", result)
    study.seal(directory)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bot", "run"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gates", type=Path)
    parser.add_argument("--identity")
    parser.add_argument("--endpoint", default=ENDPOINT)
    args = parser.parse_args()
    if args.command == "bot":
        result = asyncio.run(bot_worker(args.output))
    else:
        if args.gates is None or not args.identity:
            parser.error("run requires --gates and --identity")
        result = asyncio.run(run(args.output, expected_identity=args.identity,
            gate_receipt=json.loads(args.gates.read_text()), endpoint=args.endpoint))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
