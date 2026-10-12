"""One bounded real game. Models/search never receive evidence or opponent choices."""
from __future__ import annotations

import os
import random
import subprocess
import threading
import time

from ..branch_rollouts.simulator import Simulator as Transport
from ..providers import CREDENTIAL_NAMES
from .config import ACTOR_PYTHON, PROTOCOL, ROOT
from .search import draw, search
from .simulator import Simulator
from .storage import digest, seed, showdown_seed


class BudgetExpired(TimeoutError):
    pass


class OpponentFailure(RuntimeError):
    pass


class Opponent(Transport):
    def __init__(self, side, team, actor_seed):
        self.timeout, self.closed, self._sequence = 30, False, 0
        self._lock, self._stderr = threading.RLock(), bytearray()
        environment = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_NAMES}
        environment["PYTHONPATH"] = str(ROOT) + os.pathsep + str(ROOT / "pokechamp")
        self.process = subprocess.Popen(
            [str(ACTOR_PYTHON), "-m", "integration.pokechamp.fixed_matchup.actor_rpc"],
            cwd=ROOT / "pokechamp", env=environment, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
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


def play(job, teams, evaluate, *, stopped=lambda: False, check_resources=lambda: None,
         game_seconds=PROTOCOL["game_seconds"]):
    """evaluate(checkpoint_name, observations) is the worker's only model capability."""
    started = time.monotonic()
    ends = [job["deadline"], None if game_seconds is None else time.time() + game_seconds]
    finite_ends = [end for end in ends if end is not None]
    deadline = min(finite_ends) if finite_ends else None
    records, roots, metrics = [], [], dict(search_seconds=0.0, simulations=0, transitions=0, inference_observations=0)
    rngs = {side: random.Random(seed("action", job["seed_key"], side)) for side in ("p1", "p2")}
    team_by_side = {side: teams[label] for side, label in job["teams"].items()}
    status, winner, reason, opponent = "failed", None, None, None
    frame, evidence = None, None
    def check():
        if stopped() or (deadline is not None and time.time() >= deadline):
            raise BudgetExpired("game/stage deadline or cancellation")
        check_resources()

    def infer(model, observations):
        check()
        metrics["inference_observations"] += len(observations)
        return evaluate(model, observations)

    with Simulator("real") as actual, Simulator("search") as branch:
        try:
            check()
            frame = actual.init(team_by_side, showdown_seed("game", job["seed_key"]))
            for side, descriptor in job["players"].items():
                if descriptor["mode"] == "opponent":
                    if opponent is not None:
                        raise ValueError("only one evaluation opponent is supported")
                    opponent = Opponent(side, team_by_side[side], seed("opponent", job["seed_key"], side))
            decision = 0
            while not frame["ended"]:
                check()
                if frame["turn"] > PROTOCOL["turn_limit"]:
                    status, reason = "incomplete", "turn_limit"
                    break
                if len(roots) < 4:
                    roots.append(frame["root"])
                joint, searched, first_record = {}, {}, len(records)
                for side in ("p1", "p2"):
                    observation = frame["observations"][side]
                    actions = observation["actions"]
                    if not actions:
                        continue
                    descriptor = job["players"][side]
                    mode, model = descriptor["mode"], descriptor.get("model")
                    detail = {}
                    if mode == "opponent":
                        evidence = actual.evidence()
                        choice, command = opponent.choose(evidence, actions)
                        probabilities = None
                        detail["opponent_command"] = command
                    else:
                        if len(actions) == 1:
                            probabilities = [1.0]
                            detail["automatic"] = True
                        elif mode == "uniform":
                            probabilities = [1 / len(actions)] * len(actions)
                        elif mode == "policy":
                            output = infer(model, [observation])[0]
                            probabilities = output["policy"]
                            detail["value"] = output["value"]
                        elif mode == "search":
                            # A shared tree is valid only for the same frozen network/budget.
                            key = model, descriptor.get("simulations", PROTOCOL["simulations"])
                            if key not in searched:
                                searched[key] = search(frame["root"], branch, lambda obs: infer(model, obs),
                                    search_seed=seed("search", job["seed_key"], decision, model),
                                    simulations=key[1], depth=PROTOCOL["depth"], check=check)
                                result = searched[key]
                                metrics["search_seconds"] += result["seconds"]
                                metrics["simulations"] += result["simulations"]
                                metrics["transitions"] += result["transitions"]
                            result = searched[key]
                            detail["search"] = {k: v for k, v in result.items() if k != "sides"}
                            own = result["sides"][side]
                            if own["action_ids"] != [a["id"] for a in actions]:
                                raise ValueError("search candidate order changed")
                            detail["visits"] = own["visits"]
                            probabilities = own["policy"]
                        else:
                            raise ValueError("unknown policy mode")
                        choice = actions[draw(probabilities, rngs[side])]["id"]
                    joint[side] = choice
                    records.append(dict(id=f"{job['slot_id']}:{decision}:{side}", decision=decision,
                        turn=frame["turn"], side=side, team=job["teams"][side], model=model, mode=mode,
                        observation=observation if mode != "opponent" else None,
                        observation_hash=digest(observation) if mode != "opponent" else None,
                        action_ids=[a["id"] for a in actions], choice=choice,
                        command=next(a["command"] for a in actions if a["id"] == choice),
                        target=probabilities, **detail))
                check()
                frame = actual.advance(joint)
                for record in records[first_record:]:
                    record["submitted"] = True
                decision += 1
            if frame["ended"]:
                status, winner = "completed", frame["winner"]
            evidence = actual.evidence()
        except BudgetExpired as error:
            status, reason = "incomplete", str(error)
        except OpponentFailure as error:
            status, reason = "failed", "opponent:" + str(error)
        except Exception as error:
            status, reason = "invalid", f"{type(error).__name__}: {error}"
        finally:
            if opponent is not None:
                opponent.close()
            if evidence is None:
                try:
                    evidence = actual.evidence()
                except Exception:
                    evidence = None
    for record in records:
        record["terminal_status"] = status
        record["z"] = (0 if not winner else 1 if winner == record["side"] else -1) if status == "completed" else None
    return dict(job={k: v for k, v in job.items() if k != "deadline"}, status=status, winner=winner,
                reason=reason, turns=frame["turn"] if frame else None, records=records, evidence=evidence, roots=roots,
                metrics=dict(metrics, seconds=time.monotonic() - started))


def probe(job, evaluate, *, stopped=lambda: False, check_resources=lambda: None):
    def check():
        if stopped() or (job["deadline"] is not None and time.time() >= job["deadline"]):
            raise BudgetExpired("probe deadline")
        check_resources()
    with Simulator("search") as branch:
        result = search(job["root"], branch, lambda obs: evaluate("P0", obs),
                        search_seed=job["seed"], simulations=job["simulations"], check=check)
    return dict(job={k: v for k, v in job.items() if k not in ("deadline", "root")},
                status="completed", metrics=result)
