"""EX-114 순차32경기: 기존 소유 프로세스 lifecycle을 독립 연결한다."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

from integration.pokechamp import jev_battle as j
from .core import ROOT, PORT

async def run(directory, *, manifest, key, first_request_at, prior_calls=0, fake=False,
              session_factory=None, player_factory=None):
    """Shared owned battle lifecycle; public entry points authorize the schedule."""
    import numpy as np
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from integration.pokechamp import cli
    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.parallel_server import BattleServer
    from . import audit, study
    from .session import Session, player_class, BattleLimit
    from integration.jev27b.battle import play_owned
    SharedFailure = RuntimeError
    def error_record(exc):
        return dict(type=type(exc).__name__, detail=str(exc))

    directory = Path(directory).resolve()
    if directory.exists():
        raise FileExistsError("local JEV cannot resume or overwrite an existing attempt")
    if Path.cwd().resolve() != ROOT / "pokechamp":
        raise ValueError("local JEV battle actor requires /workspace/pokechamp working directory")
    schedule = manifest["schedule"]
    directory.mkdir(parents=True, exist_ok=False)
    session_factory=session_factory or Session
    player_factory=player_factory or player_class
    session = session_factory(directory, key=key, first_request_at=first_request_at, prior_calls=prior_calls, fake=fake)
    outcomes, error = [], None
    try:
        study.write_json(directory / "manifest.json", manifest)
        install_identity_adapter()
        for number, row in enumerate(schedule, 1):
            if session.failure_event.is_set():
                raise RuntimeError("local JEV collection halted")
            study.verify_live_identity(manifest)
            if session.remaining() <= 0:
                raise RuntimeError("collection deadline reached")
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
                    "integration.jevk5_ruleqa_battle.bot", "--output", str(attempt)],
                    cwd=ROOT / "pokechamp", env=child_env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                outcome["abyssal_pid"] = process.pid
                random.seed(seed)
                np.random.seed(seed)
                player = player_factory()(session=session, expected_actor=role,
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
                outcome.update(completed=False, outcome="incomplete" if isinstance(exc, BattleLimit) else "output_failure", failure_scope="battle",
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
            partial = study.summarize(session, [outcome], schedule, error=None)
            partial["requests"] = outcome["requests"]
            partial["sent_actions"] = sum(e["type"] == "wire" for e in session.records[start_event:])
            check = await asyncio.to_thread(audit.audit, directory,
                session.records[start_event:], outcome, manifest)
            outcome["audit_passed"] = check["passed"]
            study.write_json(attempt / "audit.json", check)
            study.write_json(attempt / "outcome.json", outcome)
            if not check["passed"]:
                raise SharedFailure("per-match technical audit failed: " + repr(check["errors"]))
            if technical is not None:
                raise technical
            progress = study.summarize(session, outcomes, schedule)
            study.write_json(directory / "progress.json", progress)
            print(json.dumps(dict(slot=number, slot_id=row["slot_id"],
                completed=progress["completed"], outcome=outcome.get("outcome"),
                requests=session.calls, elapsed=progress["elapsed_collection_seconds"])), flush=True)
    except (Exception, asyncio.CancelledError, KeyboardInterrupt) as exc:
        error = error_record(exc)
        session.fail(exc)
        session.record(dict(type="failure", error=error))
    finally:
        try:
            await session.close()
        except BaseException as exc:
            error = dict(error_record(exc), previous_error=error)
            session.record(dict(type="cleanup_failure",
                error=dict(type=type(exc).__name__, detail=str(exc))))
    try:
        study.verify_live_identity(manifest)
    except Exception as exc:
        error = error_record(exc)
    result = study.summarize(session, outcomes, schedule, error=error)
    study.write_json(directory / "result.json", result)
    checked = study.final_check(directory, result)
    study.write_json(directory / "final-audit.json", checked)
    result["final_audit_passed"] = checked["passed"]
    if not checked["passed"]:
        result["passed"] = False
        result["validity"] = "withheld_pending_final_audit"
        result["error"] = dict(type="FinalAuditFailure", detail=repr(checked["errors"]),
                               scope="shared", previous_error=result["error"])
    study.write_json(directory / "result.json", result)
    study.seal(directory)
    return result


