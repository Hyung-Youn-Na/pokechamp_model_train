"""JEV-native choice battle profile, independent of the B/B2 calculator pipeline."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import html
import json
import math
import os
import random
import re
import threading
import time
from pathlib import Path

from .jev import JevClient, JevRequestError
from . import effects, jev_effects, jev_retry
from .observation.build import DEFAULT_BUILD, verify
from .observation.normalize import _knowledge
from .providers import redact

ROOT = Path(__file__).resolve().parents[2]
VERSION = "jev-choice-v3"
V2_INPUT_VERSION = "jev-choice-v2"
LEGACY_INPUT_VERSION = "jev-choice-v1"
INITIAL_PP_POLICY = "showdown-gen9-max-pp-v1"
VALIDATION_VERSION = "choice-action-v3"
VALUES_VALIDATION_VERSION = "choice-values-v2"
LEGACY_VALIDATION_VERSION = "choice-sum-v1"
PROMPT = Path(__file__).with_name("prompts") / (VERSION + ".txt")
LIVE_EXPERIMENT = "EX-051"
LIVE = ROOT / ".pokechamp-data/jev/ex051-live"
VERIFICATION = ROOT / "project_context/exec-plans/evidence/ep071/verification-live.json"
SEED = "18280,52471,51036,2470"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(redact(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def recent_events(prefix, turn):
    # Public battle facts only. Requests, chat, ratings and future/incomplete turns are excluded.
    allowed = {"move", "switch", "drag", "replace", "faint", "cant", "detailschange"}
    current = 0
    result = []
    for event in prefix:
        for line in event["protocol"].splitlines():
            parts = line.split("|")
            if len(parts) < 2:
                continue
            kind = parts[1]
            if kind == "turn":
                current = int(parts[2])
            if max(1, turn - 3) <= current < turn and (kind in allowed or kind.startswith("-")):
                result.append(dict(turn=current, protocol=line))
    return result


def make_input(official, prefix, *, actor, dex, version=VERSION, initial_pp_policy=None):
    """Project a single bounded official snapshot, without opponent set guesses."""
    if version not in (VERSION, V2_INPUT_VERSION, LEGACY_INPUT_VERSION):
        raise ValueError("unknown JEV input version")
    if initial_pp_policy not in (None, INITIAL_PP_POLICY):
        raise ValueError("unknown initial PP policy")
    legacy = version == LEGACY_INPUT_VERSION
    request = official.get("request")
    if not request or request.get("wait"):
        return None
    if request.get("side", {}).get("id") != actor:
        raise ValueError("foreign request")
    if official["gen"] != 9 or official["game_type"] != "singles":
        raise ValueError("unsupported battle format")
    if official["consumed"] != sum(len(e["protocol"].splitlines()) for e in prefix):
        raise ValueError("observation cutoff mismatch")
    sides = {side["id"]: side for side in official["sides"]}
    opponent = "p2" if actor == "p1" else "p1"
    facts = _knowledge(prefix)
    initial = not legacy and bool(request.get("teamPreview"))
    lines = [line for event in prefix for line in event["protocol"].splitlines()]
    if initial:
        # No preview-object join: request slots already identify the owned sets.
        # Turn zero alone is insufficient (switch-in effects also occur there).
        battle_events = {"start", "turn", "switch", "drag", "replace", "move", "cant", "faint"}
        if (official["turn"] != 0 or "|init|battle" not in lines
                or not any(line.startswith("|teampreview") for line in lines)
                or any(line.startswith("|-") or (line.split("|") + [""])[1] in battle_events
                       for line in lines)):
            raise ValueError("unproven initial team preview boundary")
    request_mons = request["side"]["pokemon"]
    if not legacy and not initial:
        idents = [raw["ident"] for raw in request_mons]
        if len(set(idents)) != len(idents) or not all(idents):
            raise ValueError("ambiguous own request identity")

    def token(value):
        return "".join(c for c in value.lower() if c.isalnum())

    def move(name):
        key = token(name)
        entry = dex["BattleMovedex"].get(key, {})
        return dict(id=key, type=entry.get("type", "unknown"), category=entry.get("category", "unknown"),
                    power=entry.get("basePower", "unknown"), accuracy=entry.get("accuracy", "unknown"),
                    priority=entry.get("priority", "unknown"))

    def shared(mon):
        return {key: copy.deepcopy(mon.get(key, "unknown")) for key in
                ("types", "boosts", "status", "volatiles", "turnstatuses", "movestatuses", "status_data", "tera_type")}

    own = []
    for slot, raw in enumerate(request["side"]["pokemon"], 1):
        species = raw["details"].split(",")[0]
        matches = [] if initial else [m for m in sides[actor]["pokemon"] if m["ident"] == raw["ident"]]
        if len(matches) > 1:
            raise ValueError("ambiguous own identity")
        mon = matches[0] if matches else {}
        types = dex["BattlePokedex"].get(token(species), {}).get("types", [])
        own.append(dict(slot=slot, species=species, ident=raw["ident"],
                        **{k: copy.deepcopy(raw.get(k, "unknown")) for k in
                           ("condition", "active", "stats", "item", "ability", "baseAbility", "teraType", "terastallized")},
                        **shared(mon), moves=[dict(**move(m), current_pp="unknown") for m in raw["moves"]]))
        if not mon:
            own[-1]["types"] = types
        if initial:
            own[-1]["types"] = types or "unknown"
            condition = re.fullmatch(r"\d+/\d+(?: (brn|par|slp|frz|psn|tox))?", raw.get("condition", ""))
            status = (condition.group(1) or "") if condition else "unknown"
            own[-1].update(boosts={}, status=status, volatiles={}, turnstatuses={}, movestatuses={},
                           status_data={"sleepTurns": 0, "toxicTurns": 0} if status == "" else "unknown",
                           tera_type="", initial_state_source="own_request_and_prebattle_boundary")
        if not legacy:
            if initial and "terastallized" in raw:
                own[-1]["tera_type"] = copy.deepcopy(raw["terastallized"])
            for owned_move in own[-1]["moves"]:
                entry = dex["BattleMovedex"].get(owned_move["id"], {})
                pp = entry.get("pp")
                if (initial and initial_pp_policy == INITIAL_PP_POLICY
                        and "|tier|Gen 9 OU" in lines and type(pp) is int and pp > 0):
                    initial_pp = pp if entry.get("noPPBoosts") else pp * 8 / 5
                    owned_move["current_pp"] = int(initial_pp) if initial_pp == int(initial_pp) else initial_pp
                    owned_move["current_pp_source"] = INITIAL_PP_POLICY
                else:
                    owned_move["current_pp_reason"] = (
                        "initial_pp_rule_or_move_data_unverified" if initial else "not_in_active_request")
    active = request.get("active", [{}])[0]
    current_moves = active.get("moves", [])
    for mon in own:
        if mon["active"]:
            mon["current_move_slots"] = [dict(slot=i, **m) for i, m in enumerate(current_moves, 1)]
            for owned_move in mon["moves"]:
                matching = [m for m in current_moves if m["id"] == owned_move["id"]]
                if matching:
                    owned_move["current_pp"] = matching[0].get("pp", "unknown")
                    if not legacy:
                        owned_move.pop("current_pp_source", None)
                        owned_move.pop("current_pp_reason", None)
                        if "pp" in matching[0]:
                            owned_move["current_pp_source"] = "request.active.moves"
                        else:
                            owned_move["current_pp_reason"] = "active_request_omits_pp"
    seen = []
    for slot, mon in enumerate(sides[opponent]["pokemon"], 1):
        key = mon["ident"]
        known = facts.get(key, {})
        ability = token(mon.get("ability", ""))
        item_known = bool(mon.get("item") or mon.get("prevItem") or known.get("item", {}).get("absent"))
        seen.append(dict(preview_slot=slot, ident=key or None, species=mon["species"],
                         active=mon["active"], fainted=mon["fainted"], **shared(mon),
                         hp=dict(current=mon["hp"], maximum=mon["max_hp"], precision="rounded_public_fraction") if known.get("hp") else "unknown",
                         ability=mon["ability"] if known.get("ability", {}).get(ability) else "unknown",
                         item=(mon["item"] or None) if item_known else "unknown",
                         moves=[move(m[0]) for m in mon["moves"] if not m[0].startswith("*") and token(m[0]) not in ("struggle", "recharge")]))
    kind = "lead" if request.get("teamPreview") else "forced_switch" if any(request.get("forceSwitch", [])) else "turn_action"
    criteria, commands = {}, {}
    for candidate in official["candidates"]:
        wire = candidate["wire"]
        parts = wire.split()
        key = wire.replace(" ", "_")
        if key in commands:
            raise ValueError("duplicate candidate")
        slot = int(parts[1])
        entry = dict(kind=parts[0], slot=slot)
        if parts[0] in ("team", "switch"):
            entry["pokemon"] = own[slot - 1]["species"]
        elif parts[0] == "move":
            entry.update(move=move(current_moves[slot - 1]["id"]), terastallize="terastallize" in parts)
        else:
            raise ValueError("unsupported candidate")
        if kind == "forced_switch" and parts[0] != "switch":
            raise ValueError("move in forced switch")
        criteria[key] = entry
        if parts[0] == "team":
            commands[key] = "/team " + "".join(str(i) for i in [slot] + [i for i in range(1, len(own) + 1) if i != slot])
        else:
            commands[key] = "/choose " + wire
    if not criteria:
        raise ValueError("empty candidates")
    state = dict(version=version, format="gen9ou singles", turn=official["turn"], actor=actor,
                 request_id=request.get("rqid"), decision_kind=kind, self_team=own, opponent_team=seen,
                 weather=official["weather"], weather_duration=official["weather_duration"], field=official["field"],
                 side_conditions={s: sides[s]["side_conditions"] for s in sides},
                 recent_completed_turn_events=recent_events(prefix, official["turn"]),
                 information_rules="Opponent sets and pending action are unknown. Move power is base power, not calculated damage. Public HP is rounded. Effect counters are official client data, not guaranteed remaining durations.")
    if version == VERSION:
        state = jev_effects.without_pp_source(state)
        criteria = jev_effects.without_pp_source(criteria)
        state["effect_reference"] = jev_effects.build(state, criteria)
    instructions = PROMPT.with_name(version + ".txt").read_text()
    if kind == "lead":
        instructions += "\nChoose the lead Pokemon using your own team and the opponent's public team preview. Other team slots keep their original relative order."
    return dict(state=state, questions=dict(action=dict(type="choice", instructions=instructions, criteria=criteria))), commands


class UnusableChoice(ValueError):
    """Provider output cannot be executed; isolate to the current battle."""


def judgment_diagnostics(answer, criteria):
    diagnostics = []
    probabilities = answer.get("probabilities")
    def number(value):
        return type(value) in (float, int) and math.isfinite(value) and 0 <= value <= 1
    if (not isinstance(probabilities, dict) or probabilities.keys() != criteria.keys()
            or not all(number(p) for p in probabilities.values())):
        diagnostics.append("invalid_auxiliary_probabilities")
    else:
        if not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-4):
            diagnostics.append("probability_sum")
        if probabilities[answer["choice"]] < max(probabilities.values()) - 1e-8:
            diagnostics.append("choice_not_maximum")
    if not number(answer.get("confidence")):
        diagnostics.append("invalid_auxiliary_confidence")
    return diagnostics


def validate_answer(body, criteria, *, version=VALIDATION_VERSION):
    if version not in (VALIDATION_VERSION, VALUES_VALIDATION_VERSION, LEGACY_VALIDATION_VERSION):
        raise ValueError("unknown choice validation version")
    if version == VALIDATION_VERSION:
        answers = body.get("answers") if isinstance(body, dict) else None
        answer = answers.get("action") if isinstance(answers, dict) else None
        if (not isinstance(answer, dict) or answer.get("type") != "choice"
                or not isinstance(answer.get("choice"), str) or answer["choice"] not in criteria):
            raise UnusableChoice("missing, malformed or illegal choice")
        return answer["choice"]
    answer = body["answers"]["action"]
    probabilities = answer.get("probabilities")
    def number(value):
        return type(value) in (float, int) and math.isfinite(value) and 0 <= value <= 1
    if (answer.get("type") != "choice" or not isinstance(probabilities, dict)
            or probabilities.keys() != criteria.keys() or not all(number(p) for p in probabilities.values())
            or not number(answer.get("confidence")) or answer.get("choice") not in criteria):
        raise ValueError("invalid choice response")
    # Only historical audits retain the old strict normalization requirement.
    # Rounded provider values are kept verbatim; their sum does not gate actions.
    if version == LEGACY_VALIDATION_VERSION and not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-4):
        raise ValueError("invalid choice response")
    choice = answer["choice"]
    if probabilities[choice] < max(probabilities.values()) - 1e-8:
        raise ValueError("choice is not a maximum probability option")
    return choice


class Session:
    def __init__(self, directory, *, fake=False, environ=None, call_limit=300, collection_seconds=1800, retry_policy=jev_retry.CURRENT):
        self.directory, self.fake = directory, fake
        if call_limit is not None and (type(call_limit) is not int or call_limit < 1):
            raise ValueError("invalid JEV call limit")
        if type(collection_seconds) is not int or collection_seconds < 1:
            raise ValueError("invalid JEV collection duration")
        jev_retry.delays_for(retry_policy)
        self.retry_policy = retry_policy
        self.capture_request_body = retry_policy in jev_retry.RETRY_POLICIES
        self.http_attempt = 1
        self.call_limit = call_limit
        self.collection_seconds = collection_seconds
        self.environ = dict(os.environ if environ is None else environ)
        self.started = None
        self.monotonic_started = None
        self.calls = 0
        self.terminal_error = None
        self.failure_event = asyncio.Event()
        self.records = []
        self.lock = threading.RLock()
        # Establish the pinned server/Dex provenance before opting into its PP rule.
        verify()
        self.dex = json.loads((DEFAULT_BUILD / "dex.json").read_text())
        self.initial_pp_policy = INITIAL_PP_POLICY
        self.effect_reference_identity = effects.identity()

    def fail(self, error):
        self.terminal_error = error
        self.failure_event.set()

    def remaining(self):
        return self.collection_seconds if self.monotonic_started is None else self.collection_seconds - (time.monotonic() - self.monotonic_started)

    def record(self, event):
        with self.lock:
            event = redact(dict(at=time.time(), event_seq=len(self.records) + 1, **event), self.environ)
            with (self.directory / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self.records.append(event)

    async def evaluate(self, payload, *, decision=None):
        payload = copy.deepcopy(payload)
        delays = jev_retry.delays_for(self.retry_policy)
        for attempt in range(len(delays) + 1):
            self.http_attempt = attempt + 1
            failure = None
            try:
                return await self._evaluate_once(payload, decision=decision)
            except JevRequestError as error:
                failure = error
            except asyncio.TimeoutError:
                failure = JevRequestError("timeout")
            if self.retry_policy in jev_retry.RETRY_POLICIES:
                self.record(dict(type="attempt_failure", decision=decision, request_number=self.calls,
                                 attempt=attempt + 1, category=failure.category, status_code=failure.status_code))
            if attempt == len(delays) or not jev_retry.retryable(failure):
                raise failure
            delay = delays[attempt]
            if (self.remaining() <= delay or self.failure_event.is_set() or
                    self.call_limit is not None and self.calls >= self.call_limit):
                raise failure
            self.record(dict(type="provider_retry", decision=decision, request_number=self.calls,
                             next_attempt=attempt + 2, delay_seconds=delay))
            try:
                await asyncio.wait_for(self.failure_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                continue
            raise RuntimeError("JEV collection cancelled during retry wait")

    async def _evaluate_once(self, payload, *, decision=None):
        if (self.call_limit is not None and self.calls >= self.call_limit) or self.remaining() <= 0 or self.failure_event.is_set():
            raise RuntimeError("JEV collection stopped or budget exhausted")
        if self.started is None:
            self.started = time.time()
            self.monotonic_started = time.monotonic()
        self.calls += 1
        write(self.directory / "ledger.json", dict(first_request_at=self.started, requests=self.calls,
              limit=self.call_limit, deadline=self.started + self.collection_seconds))
        criteria = payload["questions"]["action"]["criteria"]
        if self.fake:
            if self.retry_policy in jev_retry.RETRY_POLICIES:
                self.record(dict(type="transport", endpoint="mock://local/systemone", model="jev-latest",
                                 decision=decision, request_number=self.calls, attempt=self.http_attempt,
                                 timeout=min(60, self.remaining())))
            # Exercise the real HTTP serialization/validation without external traffic.
            import httpx
            await asyncio.sleep(.01)
            moves = [(k, c) for k, c in criteria.items() if c["kind"] == "move"]
            key = max(moves, key=lambda kv: (kv[1].get("move", {}).get("power", 0), kv[1]["terastallize"]))[0] if moves else next(iter(criteria))
            body = dict(model="mock-jev", answers=dict(action=dict(type="choice", choice=key,
                        probabilities={k: float(k == key) for k in criteria}, confidence=1)), usage=dict(input_tokens=0, output_tokens=0))
            def respond(request):
                assert json.loads(request.content) == dict(model="jev-latest", **payload)
                return httpx.Response(200, json=body)
            with JevClient(api_key="local-test-key", transport=httpx.MockTransport(respond), retry_policy=jev_retry.LEGACY) as client:
                attempt_started = time.monotonic()
                if getattr(self, "capture_request_body", False):
                    def capture_request(request):
                        self.record(dict(type="http_request", decision=decision, request_number=self.calls,
                                         body=json.loads(request.content)))
                    client._client.event_hooks["request"] = [capture_request]
                if self.retry_policy in jev_retry.RETRY_POLICIES:
                    def capture_response(response):
                        response.read()
                        self.record(dict(type="http_response", decision=decision, request_number=self.calls,
                                         status_code=response.status_code, raw_body=response.text,
                                         elapsed_seconds=time.monotonic() - attempt_started))
                    client._client.event_hooks["response"] = [capture_response]
                return client.evaluate(**payload)
        timeout = min(60, self.remaining())
        request_number = self.calls
        def call():
            with JevClient.from_env(environ=self.environ, timeout=timeout, retry_policy=jev_retry.LEGACY) as client:
                attempt_started = time.monotonic()
                def capture(response):
                    response.read()
                    self.record(dict(type="http_response", request_number=request_number,
                                     decision=decision, status_code=response.status_code, raw_body=response.text,
                                     elapsed_seconds=time.monotonic() - attempt_started))
                client._client.event_hooks["response"] = [capture]
                if getattr(self, "capture_request_body", False):
                    def capture_request(request):
                        self.record(dict(type="http_request", decision=decision, request_number=request_number,
                                         body=json.loads(request.content)))
                    client._client.event_hooks["request"] = [capture_request]
                self.record(dict(type="transport", endpoint=client.endpoint, model=client.model,
                                 decision=decision, request_number=request_number, timeout=timeout, attempt=self.http_attempt))
                return client.evaluate(**payload)
        task = asyncio.create_task(asyncio.to_thread(call))
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            # HTTP has its own bounded timeout. Preserve any late response before
            # sealing the bundle; it cannot become a battle action after expiry.
            await asyncio.gather(task, return_exceptions=True)
            raise


def player_class():
    from poke_env.player.player import Player
    from .observation.cursor import CursorMessages
    from .observation.runtime import OfficialClient

    class JevPlayer(Player):
        def __init__(self, *args, session, expected_actor, **kwargs):
            self.session = session
            self.submitted_team = kwargs.get("team", "")
            self.expected_actor = expected_actor
            self.prefix = []
            self.sequence = 0
            self.official = None
            self.request = None
            self.boundary = None
            self.protocol_lock = asyncio.Lock()
            self.output_error = None
            super().__init__(*args, **kwargs)

        def choose_move(self, battle):
            raise RuntimeError("JEV decisions must use native request handler")

        async def _handle_battle_message(self, messages):
            # WebSocket frames are scheduled as separate tasks by poke-env. A
            # provider await must not let a later frame overtake its predecessor.
            async with self.protocol_lock:
                return await self._process_battle_message(messages)

        async def _process_battle_message(self, messages):
            if self.output_error is not None:
                return
            self.sequence += 1
            sequence = self.sequence
            lines = ["|".join(fields) for fields in messages]
            self.session.record(dict(type="protocol", username=self.username, sequence=sequence, protocol="\n".join(lines)))
            def mark(index):
                event = dict(event_seq=sequence, protocol="\n".join(lines[:index + 1]))
                if self.prefix and self.prefix[-1]["event_seq"] == sequence:
                    self.prefix[-1] = event
                else:
                    self.prefix.append(event)
                self.boundary = dict(protocol_event_seq=sequence, line_index=index)
                if lines[index].startswith("|request|"):
                    self.request = json.loads(lines[index][9:]) if lines[index][9:] else None
                if lines[index].startswith(("|error|", "|bigerror|")):
                    raise ValueError("Showdown rejected battle action")
            try:
                return await super()._handle_battle_message(CursorMessages(messages, mark))
            except UnusableChoice as error:
                self.output_error = error
                self.session.record(dict(type="battle_output_failure", username=self.username,
                                         error=str(error)))
            except Exception as error:
                self.session.fail(error)
                raise

        async def _handle_battle_request(self, battle, from_teampreview_request=False, maybe_default_order=False):
            if maybe_default_order:
                raise ValueError("automatic default forbidden")
            if battle.in_team_preview and from_teampreview_request and not self.request:
                battle.move_on_next_request = True
                return
            if battle.in_team_preview and not from_teampreview_request and not (self.request or {}).get("teamPreview"):
                return
            if not self.request or self.request.get("wait"):
                return
            actor = self.request["side"]["id"]
            if actor != self.expected_actor:
                raise ValueError("unexpected scheduled actor")
            if self.official is None:
                self.official = OfficialClient(actor)
            snapshot = await asyncio.to_thread(self.official.snapshot, copy.deepcopy(self.prefix), battle.battle_tag, boundary=self.boundary)
            input_started = time.monotonic()
            input_audit = None
            if getattr(self.session, "input_version", VERSION) in ("jev-choice-v4", "jev-choice-v5"):
                if self.session.input_version == "jev-choice-v5":
                    from .jev_v5 import generate
                else:
                    from .jev_v4 import generate
                payload, commands, input_audit, _ = await generate(
                    self.session, snapshot, self.prefix, self.submitted_team, actor=actor)
            else:
                payload, commands = make_input(snapshot, self.prefix, actor=actor, dex=self.session.dex,
                                               initial_pp_policy=self.session.initial_pp_policy,
                                               version=getattr(self.session, "input_version", VERSION))
            input_seconds = time.monotonic() - input_started
            criteria = payload["questions"]["action"]["criteria"]
            rqid = self.request.get("rqid")
            decision = f"{self.username}-{rqid}-{len(self.session.records)}"
            extra = {}
            if input_audit is not None:
                from .jev_v4 import save_audit
                extra = dict(input_audit=save_audit(self.session.directory, decision, input_audit),
                             input_generation_seconds=input_seconds)
            self.session.record(dict(type="input", decision=decision, battle=battle.battle_tag, actor=actor,
                                     payload=payload, commands=commands, boundary=self.boundary, official=snapshot,
                                     observation_identity=self.official.identity,
                                     effect_reference_identity=self.session.effect_reference_identity, **extra))
            started = time.monotonic()
            body = None
            if len(criteria) == 1:
                choice = next(iter(criteria))
            else:
                try:
                    body = await self.session.evaluate(payload, decision=decision)
                except JevRequestError as error:
                    if error.category == "invalid_response":
                        raise UnusableChoice("malformed provider response") from None
                    raise
                self.session.record(dict(type="response", decision=decision, body=body, elapsed_seconds=time.monotonic() - started))
                choice = validate_answer(body, criteria)
                self.session.record(dict(type="judgment_diagnostics", decision=decision,
                    diagnostics=judgment_diagnostics(body["answers"]["action"], criteria)))
            if self.request.get("rqid") != rqid or self.session.remaining() <= 0 or self.session.failure_event.is_set():
                raise ValueError("stale request or collection deadline")
            current = await asyncio.to_thread(self.official.snapshot, copy.deepcopy(self.prefix), battle.battle_tag, boundary=self.boundary)
            _, current_commands = make_input(current, self.prefix, actor=actor, dex=self.session.dex,
                                             initial_pp_policy=self.session.initial_pp_policy)
            if current_commands != commands:
                raise ValueError("changed legal actions")
            command = commands[choice]
            self.session.record(dict(type="selection", decision=decision, choice=choice, command=command,
                                     automatic=body is None, elapsed_seconds=time.monotonic() - started))
            await self.ps_client.send_message(command, battle.battle_tag, str(rqid))
            self.session.record(dict(type="wire", decision=decision, command=command, request_id=rqid, status="sent"))

    return JevPlayer


def source_identity():
    paths = sorted(p for p in (ROOT / "integration/pokechamp").rglob("*")
                   if p.is_file() and p.suffix in (".py", ".cjs", ".json", ".txt"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def report(directory, session, outcomes, error):
    inputs = {e["decision"]: e for e in session.records if e["type"] == "input"}
    selections = {e["decision"]: e for e in session.records if e["type"] == "selection"}
    wires = [e for e in session.records if e["type"] == "wire"]
    audit = all(w["decision"] in selections and w["command"] == selections[w["decision"]]["command"]
                == inputs[w["decision"]]["commands"][selections[w["decision"]]["choice"]] for w in wires)
    responses = [e for e in session.records if e["type"] == "response"]
    result = dict(planned=2, attempted=len(outcomes), completed=sum(o.get("completed", False) for o in outcomes),
                  outcomes=outcomes, requests=session.calls, external_requests=0 if session.fake else session.calls,
                  received_responses=len(responses), sent_actions=len(wires), action_audit_passed=audit,
                  automatic_actions=sum(e["automatic"] for e in selections.values()),
                  tokens={k: sum(r["body"].get("usage", {}).get(k, 0) for r in responses) for k in ("input_tokens", "output_tokens")},
                  latency_seconds=[r["elapsed_seconds"] for r in responses],
                  actual_models=sorted({r["body"]["model"] for r in responses}), error=error,
                  efficacy_evidence=False, explanation_review="미평가(기본 제외)")
    result["judgment_diagnostics"] = [e for e in session.records
        if e["type"] == "judgment_diagnostics" and e["diagnostics"]]
    result.update(failed=result["attempted"] - result["completed"], unattempted=2 - result["attempted"],
                  unanswered_requests=session.calls - len(responses),
                  actual_wins=sum(o.get("outcome") == "player_won" for o in outcomes),
                  actual_losses=sum(o.get("outcome") == "player_lost" for o in outcomes),
                  elapsed_collection_seconds=0 if session.started is None else 1800 - session.remaining())
    result["passed"] = result["completed"] == 2 and audit and not error and len(wires) == len(inputs)
    write(directory / "result.json", result)
    parts = ["<!doctype html><html lang=ko><meta charset=utf-8><title>JEV 배틀 진단</title><style>body{max-width:1100px;margin:30px auto;font-family:system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #aaa;padding:12px}nav a{margin-right:12px}</style><h1>JEV 배틀 진단</h1>",
             "<p>확률은 행동 선택 분포이며 배틀 승률이 아닙니다.</p>", "<pre>" + html.escape(json.dumps(result, ensure_ascii=False, indent=2)) + "</pre><nav>"]
    for d, event in inputs.items():
        parts.append(f'<a href="#{html.escape(d)}">{html.escape(event["actor"])} 턴 {event["payload"]["state"]["turn"]}</a>')
    parts.append("</nav>")
    for d, event in inputs.items():
        records = [e for e in session.records if e.get("decision") == d]
        parts.append(f'<article id="{html.escape(d)}"><h2>{html.escape(d)}</h2>')
        for e in records:
            content = html.escape(json.dumps(e, ensure_ascii=False, indent=2))
            parts.append(("<details><summary>실제 입력·관측·후보</summary><pre>" + content + "</pre></details>") if e["type"] == "input" else "<pre>" + content + "</pre>")
        parts.append("</article>")
    (directory / "report.html").write_text("\n".join(parts) + "</html>")
    (directory / "report.md").write_text(f'# JEV 배틀 진단\n\n예정2경기, 시도{result["attempted"]}, 정상완료{result["completed"]}.\nAPI 요청{result["external_requests"]}, 응답{len(responses)}, 전송 행동{len(wires)}, 자동선택{result["automatic_actions"]}.\n전송 감사: {audit}. 결과: {"완료" if result["passed"] else "미완료"}.\n\n오류: {error or "없음"}\n\n[턴별 viewer](report.html), [상세 결과](result.json), [원문](events.jsonl).\n확률은 승률이 아니며 성능 우위·L1-L5 효능을 판단하지 않는다. 설명 정확성은 미평가(기본 제외).\n')
    return result


async def run(directory, *, fake):
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from .battle_adapter import install_identity_adapter, guard_parser
    from .parallel_server import BattleServer
    from . import cli
    from .dotenv import load_workspace_credential
    directory = directory.resolve()
    if not fake and directory != LIVE:
        raise ValueError(f"{LIVE_EXPERIMENT} live output is fixed to prevent resetting the budget")
    sources = source_identity()
    env = dict(os.environ)
    if not fake:
        receipt = json.loads(VERIFICATION.read_text())
        if not receipt["passed"] or receipt["source"] != sources:
            raise ValueError("missing or stale offline verification")
        load_workspace_credential(environ=env)
        with JevClient.from_env(environ=env) as client:
            model_config = dict(model=client.model, endpoint=client.endpoint)
            env["TYPESAFE_MODEL"] = client.model
            env["TYPESAFE_BASE_URL"] = client.endpoint.removesuffix("/systemone")
    else:
        model_config = dict(model="mock-jev")
    directory.mkdir(parents=True, exist_ok=False)
    session = Session(directory, fake=fake, environ=env,
                      retry_policy=jev_retry.CURRENT if fake else jev_retry.LEGACY)
    for relative in sources:
        target = directory / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    install_identity_adapter()
    random.seed(100)
    np.random.seed(100)
    write(directory / "manifest.json", dict(version=VERSION, source=sources, model=model_config, fake=fake,
            validation_version=VALIDATION_VERSION,
            transport_policy=session.retry_policy, provider_retries=len(jev_retry.delays_for(session.retry_policy)),
            initial_pp_policy=session.initial_pp_policy,
            effect_reference_identity=session.effect_reference_identity,
            seed=SEED, actor_rng_seed=100, teams={str(i): cli._team_path(i).read_text() for i in (1, 2)},
            limits=dict(games=2, calls=300, seconds=1800), prompt=PROMPT.read_text(),
            experiment_id=LIVE_EXPERIMENT if not fake else "EP-071-local", schema_version=VERSION,
            efficacy_evidence=False, timer_enabled=False, created_at=time.time(),
            submodules={name: dict(sha=config["sha"]) for name, config in cli.SUBMODULES.items()},
            observation_build=json.loads((Path(__file__).with_name("observation") / "build-identity.json").read_text())))
    outcomes, error = [], None
    try:
        for swap in (0, 1):
            if session.remaining() <= 0 or session.calls >= 300:
                raise RuntimeError("collection budget exhausted")
            attempt = directory / f"battle-{swap + 1}"
            attempt.mkdir()
            server = BattleServer(attempt, 8109, SEED)
            players = []
            outcome = dict(slot=swap + 1, completed=False)
            outcomes.append(outcome)
            try:
                await asyncio.to_thread(server.start)
                config = ServerConfiguration("localhost:8109", "https://play.pokemonshowdown.com/action.php?")
                common = dict(battle_format="gen9ou", server_configuration=config, max_concurrent_battles=1)
                suffix = str(int(time.time()))[-7:]
                jev = player_class()(session=session, expected_actor="p1" if swap == 0 else "p2", team=cli._team_path(1 + swap).read_text(),
                          account_configuration=AccountConfiguration("jev" + suffix + str(swap), None), **common)
                bot = AbyssalPlayer(team=cli._team_path(2 - swap).read_text(),
                          account_configuration=AccountConfiguration("aby" + suffix + str(swap), None), **common)
                players = [jev, bot]
                guard_parser(bot)
                challenger, challenged = (jev, bot) if swap == 0 else (bot, jev)
                task = asyncio.create_task(challenger.battle_against(challenged, n_battles=1))
                local_deadline = time.monotonic() + (900 if fake else session.remaining())
                try:
                    while not task.done():
                        if session.terminal_error:
                            raise session.terminal_error
                        if jev.output_error:
                            raise jev.output_error
                        if bot.benchmark_environment_error:
                            raise bot.benchmark_environment_error
                        if session.remaining() <= 0 or time.monotonic() > local_deadline:
                            raise TimeoutError("battle or collection deadline")
                        await asyncio.sleep(.1)
                    await task
                    if jev.output_error:
                        raise jev.output_error
                    outcome.update(cli._battle_outcome(jev, bot), completed=True,
                                   jev_actor=next(iter(jev.battles.values())).player_role)
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            except UnusableChoice as exc:
                outcome.update(error=dict(type=type(exc).__name__, detail=str(exc)),
                               failure_scope="battle", outcome="output_failure")
            finally:
                await cli._close_players(players)
                for player in players:
                    if getattr(player, "official", None):
                        player.official.close()
                await asyncio.to_thread(server.close)
                outcome["server_cleaned"] = not server.created and (server.process is None or server.process.poll() is not None)
                write(attempt / "outcome.json", outcome)
    except (Exception, asyncio.CancelledError) as exc:
        error = dict(type=type(exc).__name__, detail=redact(str(exc), session.environ))
        session.record(dict(type="failure", error=error))
    if source_identity() != sources:
        error = dict(type="SourceChanged", detail="source changed during collection")
    result = report(directory, session, outcomes, error)
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.name != "checksums.sha256")
    (directory / "checksums.sha256").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + str(p.relative_to(directory)) + "\n" for p in files))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("local", "live"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "local" and args.output is None:
        parser.error("local requires --output")
    result = asyncio.run(run(args.output or LIVE, fake=args.mode == "local"))
    print(json.dumps({k: result[k] for k in ("passed", "completed", "external_requests", "error")}, ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
