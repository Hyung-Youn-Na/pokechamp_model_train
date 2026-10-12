"""EX-071 live actor: 고정 자기 슬롯, 같은 snapshot serializer, 재질의 없는 전송."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import os
import random
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import jev_battle as legacy
from .schema import from_snapshot

ROOT = Path(__file__).resolve().parents[3]
MAX_TURNS = 500


class BattleLimit(legacy.UnusableChoice):
    """평가 상한 종료는 미완료이며 모델 실패/상대 승리가 아니다."""


class PhaseError(ValueError):
    """공유 입력·서빙·수집 결함: 후속 단계 admission을 막는다."""


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(compact(value).encode()).hexdigest()


def endpoint(value):
    url = urllib.parse.urlsplit(value)
    if (
        url.scheme != "http"
        or url.hostname not in ("127.0.0.1", "localhost", "::1")
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("", "/")
        or url.port is None
    ):
        raise ValueError("imitation serving must use a loopback HTTP origin")
    return value.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(origin, path, *, body=None, timeout=10, capture=None):
    """일회 전송만 수행한다. 환경 proxy와 HTTP redirect는 사용하지 않는다."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    data = compact(body).encode() if body is not None else None
    request = urllib.request.Request(
        endpoint(origin) + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        raw = error.read(16 * 1024 * 1024 + 1)
        if capture:
            capture(error.code, raw)
        if error.code == 413:
            raise legacy.UnusableChoice("live state exceeds the frozen token limit") from error
        raise PhaseError(f"imitation serving returned HTTP {error.code}") from error
    with response:
        raw = response.read(16 * 1024 * 1024 + 1)
        if capture:
            capture(response.status, raw)
        if len(raw) > 16 * 1024 * 1024:
            raise legacy.UnusableChoice("model response exceeds recording limit")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise legacy.UnusableChoice("malformed model response") from error


def validate_response(response, value, *, model, checkpoint_sha256):
    if not isinstance(response, dict):
        raise legacy.UnusableChoice("model response is not an object")
    if (
        response.get("model") != model
        or response.get("checkpoint_sha256") != checkpoint_sha256
        or response.get("input_sha256") != value.sha256
    ):
        raise PhaseError("model, checkpoint or model-input identity mismatch")
    if response.get("action_ids") != list(value.action_ids):
        raise legacy.UnusableChoice("model action coverage/order differs from request")
    probabilities = response.get("probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != set(value.action_ids):
        raise legacy.UnusableChoice("model probabilities omit or invent an action")
    values = [probabilities[key] for key in value.action_ids]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
        raise legacy.UnusableChoice("invalid model probability")
    if not math.isclose(sum(values), 1, abs_tol=1e-5):
        raise legacy.UnusableChoice("model probabilities do not form a choice distribution")
    choice = max(value.action_ids, key=lambda key: probabilities[key])
    if response.get("choice") != choice:
        raise legacy.UnusableChoice("model choice differs from the registered argmax policy")
    return choice, {key: probabilities[key] for key in value.action_ids}


class FixedSlots:
    def __init__(self, mapping=None):
        self.mapping = dict(mapping or {})

    def observe(self, request):
        mons = request.get("side", {}).get("pokemon", [])
        idents = [mon.get("ident") for mon in mons]
        if len(idents) != 6 or not all(idents) or len(set(idents)) != 6:
            raise PhaseError("own request has ambiguous team identities")
        if not self.mapping:
            if not request.get("teamPreview"):
                raise PhaseError("original slots require the initial own team preview")
            self.mapping = {ident: slot for slot, ident in enumerate(idents, 1)}
        if set(idents) != set(self.mapping) or set(self.mapping.values()) != set(range(1, 7)):
            raise PhaseError("request changed the frozen six own identities")
        return {slot: self.mapping[ident] for slot, ident in enumerate(idents, 1)}


def decision_kind(request):
    if request.get("teamPreview"):
        return "lead"
    if any(request.get("forceSwitch", [])):
        active = [p for p in request["side"]["pokemon"] if p.get("active")]
        if len(active) != 1:
            raise PhaseError("forced request lacks one active own Pokemon")
        condition = active[0].get("condition", "")
        fainted = condition.split(" ")[0].split("/")[0] == "0" or condition.endswith(" fnt")
        return "forced_switch" if fainted else "pivot_switch"
    return "turn_action"


def actions_and_commands(official, slots):
    """공식 합법 wire 슬롯을 학습과 같은 원팀/기술 ID에 연결한다."""
    request = official.get("request")
    if not request or request.get("wait"):
        raise PhaseError("a wait or absent request has no decision")
    mapping = slots.observe(request)
    active = request.get("active", [{}])[0]
    moves = active.get("moves", [])
    mons = request["side"]["pokemon"]
    actions, commands = [], {}
    for candidate in official.get("candidates", []):
        parts = candidate["wire"].split()
        if len(parts) not in (2, 3) or not parts[1].isdigit():
            raise PhaseError("unsupported official action wire")
        kind, request_slot = parts[0], int(parts[1])
        if kind == "move":
            if (
                not 1 <= request_slot <= len(moves)
                or len(parts) == 3
                and parts[2] != "terastallize"
            ):
                raise PhaseError("invalid official move slot")
            move = moves[request_slot - 1]
            move_id = "".join(c for c in move["id"].lower() if c.isalnum())
            tera = len(parts) == 3
            aid = f"move:{move_id}:{'tera' if tera else 'normal'}"
            description = "Use " + move.get("move", move_id) + (" and Terastallize" if tera else "")
            action = dict(id=aid, kind="move", move_id=move_id, tera=tera, description=description)
            command = "/choose " + candidate["wire"]
        elif kind in ("team", "switch"):
            if len(parts) != 2 or request_slot not in mapping:
                raise PhaseError("invalid official switch or lead slot")
            original = mapping[request_slot]
            species = mons[request_slot - 1]["details"].split(",")[0]
            name = "lead" if kind == "team" else "switch"
            aid = f"{name}:{original}"
            description = ("Lead with " if name == "lead" else "Switch to ") + species
            action = dict(id=aid, kind=name, slot=original, description=description)
            if kind == "team":
                order = [request_slot] + [i for i in range(1, 7) if i != request_slot]
                command = "/team " + "".join(map(str, order))
            else:
                command = "/choose " + candidate["wire"]
        else:
            raise PhaseError("unsupported official candidate")
        if aid in commands:
            raise PhaseError("ambiguous action identity")
        actions.append(action)
        commands[aid] = command
    if not actions:
        raise PhaseError("empty legal action list")
    return actions, commands


def public_prefix(prefix):
    # The shared bridge projects only public facts. Requests and submitted sets
    # must never accidentally enter that parser as spectator events.
    excluded = ("|request|", "|sentchoice|", "|c|", "|c:|", "|chat|", "|pm|", "|raw|")
    return [
        line
        for frame in prefix
        for line in frame["protocol"].splitlines()
        if line.startswith("|") and not line.startswith(excluded)
    ]


def ensure_current(
    rqid, latest_rqid, request, current, commands, current_commands, *, remaining, failed
):
    if (
        rqid is None
        or latest_rqid != rqid
        or request.get("rqid") != rqid
        or (current.get("request") or {}).get("rqid") != rqid
        or failed
    ):
        raise PhaseError("stale request: transmission forbidden")
    if list(commands.items()) != list(current_commands.items()):
        raise PhaseError("legal actions changed: transmission forbidden")
    if remaining <= 0:
        raise BattleLimit("time_limit")


class EventLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("x")
        self.records, self.lock = [], threading.RLock()

    def record(self, event):
        with self.lock:
            event = dict(event, event_seq=len(self.records) + 1, recorded_at=time.time())
            self.stream.write(compact(event) + "\n")
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.records.append(event)

    def close(self):
        with self.lock:
            if not self.stream.closed:
                self.stream.close()


class Session(EventLog):
    def __init__(self, directory, *, model, serving, own_sets, deadline, bridge=None):
        super().__init__(Path(directory) / "events.jsonl")
        self.model, self.serving = model, serving
        self.own_sets, self.deadline = copy.deepcopy(own_sets), deadline
        self.bridge = bridge
        self.calls = 0
        self.failure_event, self.terminal_error = asyncio.Event(), None
        self.closed = False

    def remaining(self):
        return self.deadline - time.monotonic()

    def fail(self, error):
        self.terminal_error = error
        self.failure_event.set()
        self.record(
            dict(type="phase_failure", error=dict(type=type(error).__name__, detail=str(error)))
        )

    def generate(self, official, prefix, actions, *, actor):
        if self.bridge is None:
            from .metamon_bridge import BridgeClient

            self.bridge = BridgeClient()
        snapshot = self.bridge.snapshot(
            public_prefix(prefix), self.own_sets, actor, decision_kind(official["request"])
        )
        return from_snapshot(snapshot, actions), snapshot

    async def evaluate(self, value, decision):
        if self.remaining() <= 0:
            raise BattleLimit("time_limit")
        self.calls += 1
        number, started = self.calls, time.monotonic()
        body = dict(model=self.model, input=value.body)
        self.record(
            dict(
                type="http_request",
                decision=decision,
                request_number=number,
                endpoint=endpoint(self.serving["endpoint"]) + "/evaluate",
                body=body,
                body_json=compact(body),
                attempt=1,
            )
        )

        def capture(status, raw):
            self.record(
                dict(
                    type="http_response",
                    decision=decision,
                    request_number=number,
                    status_code=status,
                    raw_body=raw.decode("utf8", errors="replace"),
                    raw_sha256=hashlib.sha256(raw).hexdigest(),
                    elapsed_seconds=time.monotonic() - started,
                )
            )

        task = asyncio.create_task(
            asyncio.to_thread(
                http_json,
                self.serving["endpoint"],
                "/evaluate",
                body=body,
                timeout=self.remaining(),
                capture=capture,
            )
        )
        try:
            response = await asyncio.wait_for(asyncio.shield(task), timeout=self.remaining())
        except (TimeoutError, asyncio.CancelledError):
            self.record(dict(type="request_expired", decision=decision, request_number=number))
            # The owned worker may be terminated at its bound. A late response is
            # retained if it arrives, but can never become a transmitted choice.
            await asyncio.gather(task, return_exceptions=True)
            raise BattleLimit("time_limit") from None
        except Exception:
            if self.remaining() <= 0:
                raise BattleLimit("time_limit") from None
            raise
        choice, probabilities = validate_response(
            response, value, model=self.model, checkpoint_sha256=self.serving["checkpoint_sha256"]
        )
        self.record(
            dict(
                type="response",
                decision=decision,
                body=response,
                probabilities=probabilities,
                elapsed_seconds=time.monotonic() - started,
            )
        )
        return choice, probabilities

    def close(self):
        if not self.closed:
            if self.bridge is not None:
                self.bridge.close()
            self.closed = True
        super().close()


def player_class():
    base = legacy.player_class()

    class ImitationPlayer(base):
        def __init__(self, *args, **kwargs):
            self.fixed_slots, self.latest_rqid = FixedSlots(), None
            self.claimed_requests = set()
            super().__init__(*args, **kwargs)

        async def _handle_battle_message(self, messages):
            for fields in messages:
                if len(fields) > 1 and fields[1] == "request":
                    raw = "|".join(fields[2:])
                    self.latest_rqid = (json.loads(raw) if raw else {}).get("rqid")
            return await super()._handle_battle_message(messages)

        async def _handle_battle_request(
            self, battle, from_teampreview_request=False, maybe_default_order=False
        ):
            if maybe_default_order:
                raise PhaseError("automatic fallback/default action forbidden")
            if battle.in_team_preview and from_teampreview_request and not self.request:
                battle.move_on_next_request = True
                return
            if (
                battle.in_team_preview
                and not from_teampreview_request
                and not (self.request or {}).get("teamPreview")
            ):
                return
            if not self.request or self.request.get("wait"):
                return
            actor, rqid = self.request["side"]["id"], self.request.get("rqid")
            if actor != self.expected_actor:
                raise PhaseError("scheduled actor mismatch")
            if rqid is None:
                raise PhaseError("missing request identity")
            claim = (battle.battle_tag, rqid)
            if not hasattr(self, "claimed_requests"):
                self.claimed_requests = set()
            if claim in self.claimed_requests:
                raise PhaseError("duplicate request; model requery forbidden")
            self.claimed_requests.add(claim)
            if self.session.remaining() <= 0:
                raise BattleLimit("time_limit")
            if self.official is None:
                from ..observation.runtime import OfficialClient

                self.official = OfficialClient(actor)
            started = time.monotonic()
            official = await asyncio.to_thread(
                self.official.snapshot,
                copy.deepcopy(self.prefix),
                battle.battle_tag,
                boundary=copy.deepcopy(self.boundary),
            )
            if official["turn"] > MAX_TURNS:
                raise BattleLimit("turn_limit")
            actions, commands = actions_and_commands(official, self.fixed_slots)
            value, snapshot = await asyncio.to_thread(
                self.session.generate, official, copy.deepcopy(self.prefix), actions, actor=actor
            )
            decision = f"{self.username}-{rqid}-{len(self.session.records)}"
            self.session.record(
                dict(
                    type="input",
                    decision=decision,
                    actor=actor,
                    battle=battle.battle_tag,
                    body=value.body,
                    body_json=value.body_json,
                    input_sha256=value.sha256,
                    snapshot=snapshot,
                    actions=actions,
                    commands=commands,
                    official=official,
                    slot_map=self.fixed_slots.mapping,
                    boundary=copy.deepcopy(self.boundary),
                    observation_identity=self.official.identity,
                    input_seconds=time.monotonic() - started,
                )
            )
            try:
                if len(value.action_ids) == 1:
                    choice, probabilities = value.action_ids[0], None
                else:
                    choice, probabilities = await self.session.evaluate(value, decision)
                current = await asyncio.to_thread(
                    self.official.snapshot,
                    copy.deepcopy(self.prefix),
                    battle.battle_tag,
                    boundary=copy.deepcopy(self.boundary),
                )
                _, current_commands = actions_and_commands(current, self.fixed_slots)
                ensure_current(
                    rqid,
                    self.latest_rqid,
                    self.request,
                    current,
                    commands,
                    current_commands,
                    remaining=self.session.remaining(),
                    failed=self.session.failure_event.is_set(),
                )
                self.session.record(
                    dict(
                        type="revalidation",
                        decision=decision,
                        passed=True,
                        request_id=rqid,
                        latest_request_id=self.latest_rqid,
                        current_request_id=current["request"]["rqid"],
                        commands=current_commands,
                    )
                )
                command = commands[choice]
                self.session.record(
                    dict(
                        type="selection",
                        decision=decision,
                        choice=choice,
                        command=command,
                        probabilities=probabilities,
                        automatic=probabilities is None,
                        elapsed_seconds=time.monotonic() - started,
                    )
                )
                # No await lies between the last delivered-rqid/deadline check and send.
                ensure_current(
                    rqid,
                    self.latest_rqid,
                    self.request,
                    current,
                    commands,
                    current_commands,
                    remaining=self.session.remaining(),
                    failed=self.session.failure_event.is_set(),
                )
                await self.ps_client.send_message(command, battle.battle_tag, str(rqid))
                self.session.record(
                    dict(
                        type="wire",
                        decision=decision,
                        command=command,
                        request_id=rqid,
                        status="sent",
                        elapsed_seconds=time.monotonic() - started,
                    )
                )
            except (Exception, asyncio.CancelledError) as error:
                self.session.record(
                    dict(
                        type="decision_rejected",
                        decision=decision,
                        error=dict(type=type(error).__name__, detail=str(error)),
                        transmission="forbidden",
                    )
                )
                raise

    return ImitationPlayer


def opponent_class(policy, log):
    from poke_env.player.baselines import AbyssalPlayer

    from ..observation.cursor import CursorMessages

    if policy == "abyssal-tera-v1":
        from ..abyssal_tera import AbyssalTeraPlayer

        base = AbyssalTeraPlayer
    elif policy == "abyssal":
        base = AbyssalPlayer
    else:
        raise PhaseError("unregistered opponent")

    class ObservedOpponent(base):
        async def _handle_battle_message(self, messages):
            lines = ["|".join(fields) for fields in messages]
            log.record(dict(type="protocol", username=self.username, protocol="\n".join(lines)))

            def mark(index):
                observer = getattr(self, "observe_public_line", None)
                if observer is not None and (
                    lines[index].startswith("|move|") or lines[index].startswith("|-transform|")
                ):
                    observer(lines[index])

            return await super()._handle_battle_message(CursorMessages(messages, mark))

    return ObservedOpponent


def record_sends(player, log):
    original = player.ps_client.send_message

    async def send(message, room="", message_2=None):
        result = await original(message, room, message_2)
        if message.startswith(("/choose ", "/team ")):
            log.record(
                dict(
                    type="ps_send",
                    username=player.username,
                    battle=room,
                    command=message,
                    request_id=message_2,
                )
            )
        elif message.startswith("/utm "):
            log.record(
                dict(
                    type="team_submission",
                    username=player.username,
                    packed_team=message.removeprefix("/utm "),
                )
            )
        return result

    player.ps_client.send_message = send


def submitted_sets(team):
    if isinstance(team.get("sets"), list) and len(team["sets"]) == 6:
        return copy.deepcopy(team["sets"])
    script = (
        "const fs=require('fs'); const {Teams}=require('./pokemon-showdown/dist/sim/teams.js');"
        "const x=JSON.parse(fs.readFileSync(0,'utf8'));"
        "process.stdout.write(JSON.stringify(Teams.unpack(x.packed)));"
    )
    result = subprocess.run(
        ["node", "-e", script],
        input=compact(team),
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )
    sets = json.loads(result.stdout)
    if not isinstance(sets, list) or len(sets) != 6:
        raise PhaseError("frozen packed team did not unpack into six sets")
    return sets


async def play(player, role, request, attempt, *, session=None):
    from poke_env.concurrency import handle_threaded_coroutines

    deadline = request["deadline_monotonic"]
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BattleLimit("time_limit")
    await asyncio.wait_for(
        handle_threaded_coroutines(player.ps_client.logged_in.wait()), timeout=min(60, remaining)
    )
    _atomic_json(attempt / f"{role}.ready.json", dict(ready=True, actor=role, pid=os.getpid()))
    other = "p2" if role == "p1" else "p1"

    def check():
        if session and session.terminal_error:
            raise session.terminal_error
        if getattr(player, "output_error", None):
            raise player.output_error
        if getattr(player, "benchmark_environment_error", None):
            raise player.benchmark_environment_error
        if time.monotonic() >= deadline:
            raise BattleLimit("time_limit")
        if any(battle.turn > MAX_TURNS for battle in player.battles.values()):
            raise BattleLimit("turn_limit")
        if (attempt / "cancel.json").exists():
            raise BattleLimit("peer_cancelled")

    task = None
    try:
        while not (attempt / f"{other}.ready.json").exists():
            check()
            await asyncio.sleep(0.1)
        names = request["names"]
        task = asyncio.create_task(
            player.send_challenges(names[other], 1)
            if role == "p1"
            else player.accept_challenges(names[other], 1)
        )
        while not task.done():
            check()
            await asyncio.sleep(0.1)
        await task
        battles = list(player.battles.values())
        if len(battles) != 1 or player.n_finished_battles != 1:
            raise PhaseError("missing terminal battle")
        battle = battles[0]
        if battle.player_role != role or battle.turn > MAX_TURNS:
            raise PhaseError("unexpected role or late terminal battle")
        return dict(
            status="completed",
            result="win" if battle.won else "loss" if battle.lost else "draw",
            turns=battle.turn,
            battle_tag=battle.battle_tag,
        )
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def _atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("x") as stream:
        stream.write(compact(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


async def worker(attempt, role):
    import numpy as np
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration

    from .. import cli
    from ..battle_adapter import guard_parser, install_identity_adapter

    attempt = Path(attempt)
    request = json.loads((attempt / "request.json").read_text())
    row = request["slot"]
    is_model = role == row["model_side"]
    seed = row["model_seed"] if is_model else row["opponent_seed"]
    random.seed(seed)
    np.random.seed(seed)
    install_identity_adapter()
    player = session = log = None
    result = dict(
        actor=role,
        status="failed",
        result=None,
        pid=os.getpid(),
        policy=row["model"] if is_model else row["opponent"],
        seed=seed,
        python_hash_seed=os.environ.get("PYTHONHASHSEED"),
    )
    try:
        team = row["teams"][role]
        if is_model:
            session = Session(
                attempt,
                model=row["model"],
                serving=request["serving"],
                own_sets=submitted_sets(team),
                deadline=request["deadline_monotonic"],
            )
            log = session
        else:
            log = EventLog(attempt / "opponent-events.jsonl")
        common = dict(
            team=team["packed"],
            battle_format="gen9ou",
            max_concurrent_battles=1,
            start_timer_on_battle_start=False,
            account_configuration=AccountConfiguration(request["names"][role], None),
            server_configuration=ServerConfiguration(
                f"localhost:{request['port']}", "https://play.pokemonshowdown.com/action.php?"
            ),
        )
        player = (
            player_class()(session=session, expected_actor=role, **common)
            if is_model
            else opponent_class(row["opponent"], log)(**common)
        )
        if not is_model:
            guard_parser(player)
        record_sends(player, log)
        result.update(await play(player, role, request, attempt, session=session))
    except BattleLimit as error:
        result.update(status="incomplete", reason=str(error), failure_scope="battle")
    except legacy.UnusableChoice as error:
        result.update(
            status="failed",
            error=dict(type=type(error).__name__, detail=str(error)),
            failure_scope="battle",
        )
    except BaseException as error:
        result.update(
            status="failed",
            error=dict(type=type(error).__name__, detail=str(error)),
            failure_scope="phase",
        )
    finally:
        if player is not None:
            result["observed_turn"] = max((b.turn for b in player.battles.values()), default=0)
            try:
                await cli._close_players([player])
                if getattr(player, "official", None):
                    player.official.close()
            except BaseException as error:
                result.update(
                    status="failed",
                    result=None,
                    failure_scope="phase",
                    cleanup_error=dict(type=type(error).__name__, detail=str(error)),
                )
        if log is not None:
            try:
                log.close()
            except BaseException as error:
                result.update(
                    status="failed",
                    result=None,
                    failure_scope="phase",
                    cleanup_error=dict(type=type(error).__name__, detail=str(error)),
                )
        _atomic_json(attempt / f"{role}.result.json", result)
    return result
