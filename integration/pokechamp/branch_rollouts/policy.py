"""Offline, actor-local adapter for the unchanged canonical Abyssal policy.

Snapshots are trusted internal pickle artifacts, never model inputs.  Only the
battle observer and policy state are serialized; clients, sockets and event-loop
primitives are deliberately excluded.  Import/run with the pinned pokechamp
environment, its source directory as the working directory (canonical data
loaders use relative paths), and that directory on PYTHONPATH.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
import json
import logging
import pickle
import random
import threading
from types import SimpleNamespace

import numpy as np

from poke_env.environment.battle import Battle
from poke_env.environment.move import Move
from poke_env.environment.pokemon import Pokemon
from poke_env.player.baselines import AbyssalPlayer
from poke_env.player.player import Player
from poke_env.ps_client.account_configuration import AccountConfiguration

from integration.pokechamp.battle_adapter import (
    BattleEnvironmentError,
    exact_get_pokemon,
    identity,
    update_team_from_request,
)


_RNG_LOCK = threading.RLock()
_SNAPSHOT_VERSION = 1
_LIFECYCLE_FIELDS = frozenset({
    "ps_client", "_battles", "_battle_semaphore", "_battle_start_condition",
    "_battle_count_queue", "_battle_end_condition", "_challenge_queue",
})
_CACHE_FIELDS = ("gen", "move_effect", "ability_effect", "item_effect")


class _ActorBattle(Battle):
    """Apply the same identity adapter without mutating the canonical classes."""

    get_pokemon = exact_get_pokemon
    _update_team_from_request = update_team_from_request


class Actor:
    """One Abyssal policy, private protocol observer, and independent RNG streams."""

    def __init__(self, side: str, username: str, seed: int, team=None):
        if side not in {"p1", "p2"}:
            raise ValueError("actor side must be p1 or p2")
        self.side = side
        self.username = username
        self.request: dict | None = None
        self._rqid = 0
        self.reseed(seed)
        with self._rng():
            # Preserve Player's normal random-avatar draw before any preview
            # shuffle.  An explicit avatar would change the historical RNG path.
            self.player = AbyssalPlayer(
                account_configuration=AccountConfiguration(username, None),
                battle_format="gen9ou", max_concurrent_battles=1,
                start_listening=False, team=team,
            )
        policy = self._policy_state()
        self._set_policy(policy)
        self.battle = _ActorBattle(
            battle_tag="battle-gen9ou-branch", username=username,
            logger=self.player.logger, gen=9,
        )
        self.battle._format = "gen9ou"
        # The constructor knows which private stream it is being given.  The
        # normal player line will confirm this before preview/request parsing.
        self.battle._player_role = side

    def reseed(self, seed: int) -> None:
        """Replace future policy randomness without consuming an avatar draw."""
        self._python_rng = random.Random(int(seed)).getstate()
        self._numpy_rng = np.random.RandomState(int(seed) % (2**32)).get_state()

    @contextmanager
    def _rng(self):
        # Canonical code uses module RNGs; serialize access and restore the host
        # states even when parsing/choosing raises.  Worker processes remain
        # independent and candidate execution order cannot advance another actor.
        with _RNG_LOCK:
            host_python, host_numpy = random.getstate(), np.random.get_state()
            random.setstate(self._python_rng)
            np.random.set_state(self._numpy_rng)
            try:
                yield
            finally:
                self._python_rng = random.getstate()
                self._numpy_rng = np.random.get_state()
                random.setstate(host_python)
                np.random.set_state(host_numpy)

    def _policy_state(self):
        return copy.deepcopy({
            key: value for key, value in self.player.__dict__.items()
            if key not in _LIFECYCLE_FIELDS
        })

    def _set_policy(self, state):
        self.player = object.__new__(AbyssalPlayer)
        self.player.__dict__.update(copy.deepcopy(state))
        self.player.ps_client = SimpleNamespace(
            username=self.username, logger=logging.getLogger(self.username),
        )
        self.player._battles = {}
        self._private_caches = {
            name: self.player.__dict__[name] for name in _CACHE_FIELDS
            if name in self.player.__dict__
        }

    def _isolate_policy_caches(self):
        # Abyssal assigns cached read-only lookup dictionaries on every choose.
        # Retain equivalent actor-local copies rather than exposing mutable
        # module-cache references through the actor or its snapshot.
        for name in _CACHE_FIELDS:
            if name not in self.player.__dict__:
                continue
            if name not in self._private_caches:
                self._private_caches[name] = copy.deepcopy(self.player.__dict__[name])
            self.player.__dict__[name] = self._private_caches[name]

    def feed(self, protocol_lines: list[str]) -> None:
        """Consume this actor's public stream and its own private requests.

        The runner is responsible for Showdown's split-message visibility.  Raw
        split blocks are rejected because feeding both payloads would leak the
        other actor's exact HP and other private information.
        """
        with self._rng():
            for line in protocol_lines:
                try:
                    self._feed_line(line)
                except Exception as error:
                    # Same fail-closed error boundary as battle_adapter.guard_parser.
                    if getattr(error, "category", None) not in (None, "environment"):
                        raise
                    wrapped = BattleEnvironmentError(f"{type(error).__name__}: {error}")
                    self.player.benchmark_environment_error = wrapped
                    raise wrapped from error

    def _feed_line(self, line: str) -> None:
        if not isinstance(line, str):
            raise TypeError("protocol lines must be strings")
        if not line or line.startswith(">battle-"):
            return
        if "\n" in line:
            raise ValueError("feed expects one protocol message per list entry")
        parts = line.split("|")
        if len(parts) <= 1:
            return
        kind = parts[1]
        if kind == "split":
            raise ValueError("feed requires an actor-filtered stream, not raw split blocks")
        if kind in Player.MESSAGES_TO_IGNORE:
            return
        if kind == "request":
            body = line.partition("|request|")[2]
            if not body:
                self.request = None
                return
            request = json.loads(body)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            if "side" in request and request["side"].get("id") != self.side:
                raise ValueError("request belongs to the other actor")
            if "rqid" not in request:
                request["rqid"] = self._rqid + 1
            if type(request["rqid"]) is not int or request["rqid"] < self._rqid:
                raise ValueError("request rqid regressed or is not an integer")
            self._rqid = request["rqid"]
            self.request = copy.deepcopy(request)
            # The simulator's waiting player request can be just {wait:true};
            # the websocket server normally supplies side/rqid around it.
            if request.get("wait") and "side" not in request:
                self.battle._wait = True
                return
            self.battle.parse_request(request)
            return
        if kind == "win":
            self.battle.won_by(parts[2])
            return
        if kind == "tie":
            self.battle.tied()
            return
        if kind in {"error", "bigerror"}:
            raise ValueError(f"simulator reported {line}")
        if kind == "uhtml" and len(parts) > 2 and "otsrequest" in parts[2]:
            raise ValueError("open team sheets are outside the frozen battle format")
        if kind == "player" and len(parts) > 3:
            if parts[2] == self.side and parts[3] != self.username:
                raise ValueError("player line disagrees with actor identity")
            if parts[3] == self.username and parts[2] != self.side:
                raise ValueError("actor username appears on the other side")
        self.battle.parse_message(parts)
        if kind == "turn":
            self.battle.move_on_next_request = True

    def choose(self) -> str:
        """Return a simulator command with unambiguous request slot indices."""
        if self.request is None:
            raise BattleEnvironmentError("cannot choose without a current request")
        if self.request.get("wait") or self.battle.finished:
            raise BattleEnvironmentError("cannot choose for a waiting or terminal actor")
        with self._rng():
            if self.request.get("teamPreview"):
                result = self.player.teampreview(self.battle)
                if not result.startswith("/team "):
                    raise BattleEnvironmentError("unexpected preview command")
                command = "team " + result.removeprefix("/team ")
            else:
                try:
                    order = self.player.choose_move(self.battle)
                    command = self._command(order)
                finally:
                    self._isolate_policy_caches()
        self.battle.move_on_next_request = False
        return command

    def _command(self, order) -> str:
        if order is None or isinstance(order, str):
            # Match Player._handle_battle_request's canonical default handling.
            return "default"
        message = order.message.removeprefix("/choose ")
        if message == "default":
            return message
        if isinstance(order.order, Move):
            active = self.request.get("active", [])
            if len(active) != 1:
                raise BattleEnvironmentError("move requires exactly one active request")
            move_id = order.order.id
            slots = [
                index for index, entry in enumerate(active[0].get("moves", []), 1)
                if Move.retrieve_id(entry.get("id", entry.get("move", ""))) == move_id
                and not entry.get("disabled", False)
            ]
            if len(slots) != 1:
                raise BattleEnvironmentError(f"move {move_id} has {len(slots)} request slots")
            suffix = message.split()[2:]
            return " ".join(["move", str(slots[0]), *suffix])
        if isinstance(order.order, Pokemon):
            slots = []
            for index, entry in enumerate(self.request["side"]["pokemon"], 1):
                _, key = identity(entry["ident"])
                if self.battle.team.get(key) is order.order:
                    slots.append(index)
            if len(slots) != 1:
                raise BattleEnvironmentError("switch Pokemon does not map to one request slot")
            return f"switch {slots[0]}"
        raise BattleEnvironmentError(f"unsupported Abyssal order {message!r}")

    def snapshot(self) -> bytes:
        """Serialize a trusted internal snapshot without event loops or clients."""
        return pickle.dumps({
            "version": _SNAPSHOT_VERSION, "side": self.side, "username": self.username,
            "battle": self.battle, "request": self.request, "rqid": self._rqid,
            "policy": self._policy_state(), "python_rng": self._python_rng,
            "numpy_rng": self._numpy_rng,
        }, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def restore(cls, snapshot: bytes) -> "Actor":
        """Restore only trusted snapshots produced by this adapter."""
        state = pickle.loads(snapshot)
        if state["version"] != _SNAPSHOT_VERSION:
            raise ValueError("unsupported actor snapshot version")
        actor = object.__new__(cls)
        actor.side, actor.username = state["side"], state["username"]
        actor.battle, actor.request = state["battle"], state["request"]
        actor._rqid = state["rqid"]
        actor._python_rng, actor._numpy_rng = state["python_rng"], state["numpy_rng"]
        actor._set_policy(state["policy"])
        return actor
