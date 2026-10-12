"""One actual game (worker side, no torch). Models/search never see evidence or the opponent's choice."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import random
import subprocess
import threading
import time

from .config import ACTOR_PYTHON, ASSIGNMENTS, PROTOCOL, ROOT
from .search import matrix_search, root_policy
from .sim import Simulator
from .storage import digest, seed
from .vendor.transport import CREDENTIAL_NAMES, Simulator as Transport

SIDES = ("p1", "p2")


class Cancelled(RuntimeError):
    pass


class OpponentFailure(RuntimeError):
    pass


def draw(probabilities, rng):
    total = sum(probabilities)
    if not probabilities or total <= 0 or any(p < 0 for p in probabilities):
        raise ValueError("invalid probability distribution")
    u, cumulative = rng.random(), 0.0
    for index, p in enumerate(probabilities):
        cumulative += p / total
        if u < cumulative:
            return index
    return len(probabilities) - 1


class Opponent(Transport):
    """Frozen abyssal-tera-v1 in the pinned poke-env interpreter, fed only its own actor stream."""

    def __init__(self, side, team, actor_seed):
        self.timeout, self.closed, self._sequence = 60, False, 0
        self._lock, self._stderr = threading.RLock(), bytearray()
        environment = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_NAMES}
        environment["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "pokechamp")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        self.process = subprocess.Popen(
            [str(ACTOR_PYTHON), "-m", "integration.qwen_mcts.vendor.opponent.actor_rpc"],
            cwd=ROOT / "pokechamp", env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            os.set_blocking(pipe.fileno(), False)
        self._exchange("init", side=side, team=team, seed=actor_seed)
        self.cursor, self.side = 0, side

    def choose(self, evidence, legal):
        logs = evidence["actor_logs"][self.side]
        if self.cursor > len(logs):
            raise OpponentFailure("actor log regressed")
        try:
            result = self._exchange("choose", logs=logs[self.cursor:], request=evidence["requests"][self.side])
        except Exception as error:
            raise OpponentFailure(str(error)) from error
        self.cursor = len(logs)
        command = result["command"]
        if command == "default" and len(legal) == 1:
            return legal[0]["id"], command
        for action in legal:
            if command == action["command"]:
                return action["id"], command
            if command.startswith("team ") and action["command"].startswith("team "):
                if command.split()[1][0] == action["command"].split()[1][0]:
                    return action["id"], command
        raise OpponentFailure("opponent command does not match a legal action")


def play(job, teams, statics, evaluate, tokens, *, nodes=1, stopped=lambda: False, check_resources=lambda: None):
    """job: slot_id, stage, assignment, seed_key, game_seed, players{side: {mode, tag}}.
    Modes: search (matrix search under tag), policy (root prior under tag), uniform, opponent."""
    started = time.monotonic()
    assignment = job["assignment"]
    team_by_side = {side: teams[label] for side, label in ASSIGNMENTS[assignment].items()}
    rngs = {side: random.Random(seed("action", *job["seed_key"], side)) for side in SIDES}
    records, roots = [], []
    metrics = dict(decisions=0, searches=0, children=0, evaluated=0, expand=0.0, evaluate=0.0, solve=0.0, policy_calls=0)
    status, winner, reason, frame, evidence, opponent = "invalid", None, None, None, None, None

    def check():
        if stopped():
            raise Cancelled("cancelled")
        check_resources()

    sims = [Simulator("search") for _ in range(nodes)]
    executor = ThreadPoolExecutor(max_workers=nodes) if nodes > 1 else None
    real = Simulator("real")
    try:
        check()
        frame = real.init(team_by_side, job["game_seed"])
        if digest(frame["static"]) != statics[assignment]["text_sha256"]:
            raise ValueError("static prefix differs from the frozen identity")
        for side, player in job["players"].items():
            if player["mode"] == "opponent":
                if opponent is not None:
                    raise ValueError("only one opponent side is supported")
                opponent = Opponent(side, team_by_side[side], seed("opponent", *job["seed_key"], side))
        decision = 0
        while not frame["ended"]:
            check()
            if frame["turn"] > PROTOCOL["turn_limit"]:
                status, reason = "censored", "turn_limit"
                break
            roots.append(frame["root"])
            candidates = frame["candidates"]
            record = dict(decision=decision, turn=frame["turn"], phase=frame["phase"], root=digest(frame["root"]),
                          dynamic=digest(frame["dynamic"]), candidates={s: [c["id"] for c in candidates[s]] for s in SIDES},
                          modes={}, choices={}, search={}, policy={})
            for side in SIDES:
                player, count = job["players"][side], len(candidates[side])
                if not count:
                    continue
                record["modes"][side] = player["mode"]
                index = SIDES.index(side)
                if player["mode"] == "opponent":
                    evidence = real.evidence()
                    choice, command = opponent.choose(evidence, candidates[side])
                    record["choices"][side], record["opponent_command"] = choice, command
                    continue
                if count == 1:
                    probabilities = [1.0]
                elif player["mode"] == "search":
                    tag = player["tag"]
                    if tag not in record["search"]:
                        result = matrix_search(frame, sims, executor, evaluate, tokens, prefix_id=assignment, tag=tag,
                                               search_seed=seed("matrix", *job["seed_key"], decision, tag))
                        record["search"][tag] = result
                        metrics["searches"] += 1
                        metrics["children"] += result["children"]
                        metrics["evaluated"] += result["evaluated"]
                        for key in ("expand", "evaluate", "solve"):
                            metrics[key] += result["timing"][key]
                    probabilities = record["search"][tag]["pi"][index]
                elif player["mode"] == "policy":
                    tag = player["tag"]
                    if tag not in record["policy"]:
                        record["policy"][tag] = root_policy(frame, evaluate, tokens, prefix_id=assignment, tag=tag)
                        metrics["policy_calls"] += 1
                    probabilities = record["policy"][tag]["rho"][index]
                elif player["mode"] == "uniform":
                    probabilities = [1.0 / count] * count
                else:
                    raise ValueError("unknown player mode")
                if len(probabilities) != count:
                    raise ValueError("policy/candidate misalignment")
                record["choices"][side] = candidates[side][draw(probabilities, rngs[side])]["id"]
            records.append(record)
            frame = real.advance(record["choices"])
            decision += 1
            metrics["decisions"] = decision
        if frame["ended"]:
            status, winner = "completed", frame["winner"]
    except Cancelled as error:
        status, reason = "incomplete", str(error)
    except OpponentFailure as error:
        status, reason = "failed", "opponent:" + str(error)
    except Exception as error:
        status, reason = "invalid", f"{type(error).__name__}: {error}"
    finally:
        try:
            evidence = real.evidence()
        except Exception:
            evidence = None
        for process in [real, *sims, *([opponent] if opponent else [])]:
            try:
                process.close()
            except Exception:
                pass
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
    return dict(job=job, status=status, winner=winner, reason=reason, turns=frame["turn"] if frame else None,
                records=records, roots=roots, evidence=evidence,
                metrics=dict(metrics, seconds=time.monotonic() - started))
