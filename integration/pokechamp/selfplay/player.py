"""EX-071 official input/wire boundary with EX-072 seeded categorical responses."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import time
from pathlib import Path

from ..imitation import player as base
from ..imitation.player import BattleLimit, EventLog, PhaseError, compact


def sampling_seed(seed, call):
    return int.from_bytes(
        hashlib.sha256(f"{seed}:categorical:{call}".encode()).digest()[:8], "big"
    )


def validate_response(response, value, *, model, checkpoint_sha256, seed):
    if not isinstance(response, dict):
        raise base.legacy.UnusableChoice("response must be an object")
    if (
        response.get("model") != model
        or response.get("checkpoint_sha256") != checkpoint_sha256
        or response.get("input_sha256") != value.sha256
        or response.get("rng_seed") != seed
    ):
        raise PhaseError("model/input/RNG identity differs from the frozen request")
    ids = list(value.action_ids)
    if response.get("action_ids") != ids:
        raise PhaseError("candidate order changed")
    ps = response.get("probabilities")
    if not isinstance(ps, dict) or set(ps) != set(ids):
        raise PhaseError("probability candidates differ")
    if any(
        type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
        for p in ps.values()
    ):
        raise PhaseError("invalid policy probabilities")
    if not math.isclose(sum(ps.values()), 1.0, abs_tol=1e-5):
        raise PhaseError("policy probabilities are not normalized")
    logs = response.get("log_probabilities")
    wdl = response.get("wdl_probabilities")

    def ordered(values):
        if isinstance(values, dict):
            if set(values) != set(ids):
                raise PhaseError("candidate prediction coverage differs")
            return [values[k] for k in ids]
        if not isinstance(values, list) or len(values) != len(ids):
            raise PhaseError("candidate prediction length differs")
        return values

    logs, wdl = ordered(logs), ordered(wdl)
    for p, lp, probs in zip([ps[k] for k in ids], logs, wdl, strict=True):
        if not math.isfinite(lp) or abs(math.exp(lp) - p) > 1e-5:
            raise PhaseError("recorded log probability differs from policy")
        if (
            not isinstance(probs, list)
            or len(probs) != 3
            or any(not math.isfinite(x) or not 0 <= x <= 1 for x in probs)
            or not math.isclose(sum(probs), 1.0, abs_tol=1e-5)
        ):
            raise PhaseError("invalid W/D/L prediction")
    for field in ("wdl_probabilities_before", "wdl_probabilities_after"):
        if field not in response:
            continue
        for probs in ordered(response[field]):
            if (
                not isinstance(probs, list)
                or len(probs) != 3
                or any(not math.isfinite(x) or not 0 <= x <= 1 for x in probs)
                or not math.isclose(sum(probs), 1.0, abs_tol=1e-5)
            ):
                raise PhaseError("invalid alternate W/D/L prediction")
    baseline = sum(
        ps[k] * (probs[0] + 0.5 * probs[1]) for k, probs in zip(ids, wdl, strict=True)
    )
    if not math.isclose(baseline, response.get("baseline", float("nan")), abs_tol=1e-5):
        raise PhaseError("old baseline differs from full action distribution")
    choice = response.get("choice")
    if choice not in ids:
        raise base.legacy.UnusableChoice("sampled action is not a candidate")
    u = random.Random(seed).random()
    cumulative = 0.0
    sampled = ids[-1]
    total = sum(ps.values())
    for key in ids:
        cumulative += ps[key] / total
        if u < cumulative:
            sampled = key
            break
    if choice != sampled:
        raise PhaseError("sampled action differs from the recorded categorical RNG")
    return choice, {key: ps[key] for key in ids}


class Session(base.Session):
    def __init__(
        self, directory, *, model, serving, own_sets, deadline, seed, learner=True
    ):
        EventLog.__init__(
            self,
            Path(directory) / ("events.jsonl" if learner else "opponent-events.jsonl"),
        )
        self.model, self.serving, self.own_sets, self.deadline = (
            model,
            serving,
            own_sets,
            deadline,
        )
        self.seed = seed
        self.bridge = None
        self.calls = 0
        self.failure_event, self.terminal_error = asyncio.Event(), None
        self.closed = False

    async def evaluate(self, value, decision):
        if self.remaining() <= 0:
            raise BattleLimit("time_limit")
        self.calls += 1
        seed = sampling_seed(self.seed, self.calls)
        started = time.monotonic()
        body = {"model": self.model, "input": value.body, "seed": seed}
        self.record(
            {
                "type": "http_request",
                "decision": decision,
                "request_number": self.calls,
                "body": body,
                "body_json": compact(body),
                "attempt": 1,
            }
        )

        def capture(status, raw):
            self.record(
                {
                    "type": "http_response",
                    "decision": decision,
                    "request_number": self.calls,
                    "status_code": status,
                    "raw_body": raw.decode("utf8", errors="replace"),
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )

        response = await asyncio.to_thread(
            base.http_json,
            self.serving["endpoint"],
            "/evaluate",
            body=body,
            timeout=self.remaining(),
            capture=capture,
        )
        choice, ps = validate_response(
            response,
            value,
            model=self.model,
            checkpoint_sha256=self.serving["checkpoint_sha256"],
            seed=seed,
        )
        self.record(
            {
                "type": "response",
                "decision": decision,
                "body": response,
                "probabilities": ps,
                "elapsed_seconds": time.monotonic() - started,
            }
        )
        return choice, ps


async def worker(attempt, role):
    import numpy as np
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration

    from .. import cli
    from ..battle_adapter import guard_parser, install_identity_adapter

    attempt = Path(attempt)
    request = json.loads((attempt / "request.json").read_text())
    row = request["slot"]
    learner = role == row["model_side"]
    actor = request["actors"][role]
    seed = row["model_seed"] if learner else row["opponent_seed"]
    random.seed(seed)
    np.random.seed(seed)
    install_identity_adapter()
    player = session = log = None
    result = {
        "actor": role,
        "status": "failed",
        "result": None,
        "pid": os.getpid(),
        "seed": seed,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "policy": actor["policy"],
    }
    try:
        team = row["teams"][role]
        if actor["kind"] == "model":
            session = Session(
                attempt,
                model=actor["policy"],
                serving=actor["serving"],
                own_sets=base.submitted_sets(team),
                deadline=request["deadline_monotonic"],
                seed=seed,
                learner=learner,
            )
            log = session
        else:
            log = EventLog(attempt / "opponent-events.jsonl")
        common = {
            "team": team["packed"],
            "battle_format": "gen9ou",
            "max_concurrent_battles": 1,
            "start_timer_on_battle_start": False,
            "account_configuration": AccountConfiguration(request["names"][role], None),
            "server_configuration": ServerConfiguration(
                f"localhost:{request['port']}",
                "https://play.pokemonshowdown.com/action.php?",
            ),
        }
        player = (
            base.player_class()(session=session, expected_actor=role, **common)
            if session
            else base.opponent_class(actor["policy"], log)(**common)
        )
        if not session:
            guard_parser(player)
        base.record_sends(player, log)
        result.update(await base.play(player, role, request, attempt, session=session))
    except BattleLimit as error:
        result.update(status="incomplete", reason=str(error), failure_scope="battle")
    except (
        base.legacy.UnusableChoice,
        TimeoutError,
        ConnectionError,
        OSError,
    ) as error:
        result.update(
            status="failed",
            error={"type": type(error).__name__, "detail": str(error)},
            failure_scope="battle",
        )
    except BaseException as error:  # noqa: BLE001 -- record boundary failure before owned-resource cleanup
        result.update(
            status="failed",
            error={"type": type(error).__name__, "detail": str(error)},
            failure_scope="phase",
        )
    finally:
        if player is not None:
            result["observed_turn"] = max(
                (b.turn for b in player.battles.values()), default=0
            )
            try:
                await cli._close_players([player])
                if getattr(player, "official", None):
                    player.official.close()
            except BaseException as error:  # noqa: BLE001 -- record boundary failure before owned-resource cleanup
                result.update(
                    status="failed",
                    result=None,
                    failure_scope="phase",
                    cleanup_error=str(error),
                )
        if log:
            log.close()
        base._atomic_json(attempt / f"{role}.result.json", result)
    return result
