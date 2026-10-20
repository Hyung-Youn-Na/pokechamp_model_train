"""Synchronous strategic planning over one immutable JEV decision snapshot."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field, replace
import hashlib
import json
import time

from integration.pokechamp.jev_battle import judgment_diagnostics, validate_answer
from integration.pokechamp.providers import redact
from .events import bounded_prefix, coordinates, event_identity, public_events, trigger_events
from .candidate_labels import candidate_input


class DecisionConsistencyError(ValueError):
    category = "integrity"
    scope = "collection"


class StaleDecisionError(DecisionConsistencyError):
    category = "stale_request"


class PlanOutputError(ValueError):
    """Unusable model output; isolate to this battle, without planner fallback."""
    category = "planner_output"
    scope = "battle"


def _json(value):
    # Insertion order is part of the candidate/command contract, including off.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, init=False)
class DecisionContext:
    battle: str
    protocol_battle: str
    actor: str
    rqid: int
    turn: int
    _payload: str = field(repr=False)
    _commands: str = field(repr=False)
    _prefix: str = field(repr=False)
    _boundary: str = field(repr=False)
    fingerprint: str

    def __init__(self, battle, actor, rqid, payload, commands, prefix, boundary,
                 protocol_battle=None):
        protocol_battle = battle if protocol_battle is None else protocol_battle
        if (not isinstance(battle, str) or not battle or actor not in ("p1", "p2")
                or type(rqid) is not int or rqid < 0
                or not isinstance(protocol_battle, str) or not protocol_battle):
            raise DecisionConsistencyError("invalid battle decision identity")
        try:
            snapshot = json.loads(_json(payload))
            frozen_commands = json.loads(_json(commands))
            state = snapshot["state"]
            action = snapshot["questions"]["action"]
            criteria = action["criteria"]
            turn = state["turn"]
            valid = (isinstance(state, dict) and state.get("actor") == actor
                     and state.get("request_id") == rqid and type(turn) is int and turn >= 0
                     and action.get("type") == "choice" and isinstance(action.get("instructions"), str)
                     and isinstance(criteria, dict) and 1 <= len(criteria) <= 16
                     and isinstance(frozen_commands, dict) and list(criteria) == list(frozen_commands)
                     and all(isinstance(k, str) and k and isinstance(v, str) and v
                             for k, v in frozen_commands.items()))
            if not valid:
                raise ValueError("invalid observation or candidate/command correspondence")
            frozen_prefix = bounded_prefix(prefix, boundary, actor=actor, battle=protocol_battle)
            rows = public_events(frozen_prefix, boundary, actor=actor, battle=protocol_battle)
            public_turn = max((row["turn"] for row in rows), default=0)
            if public_turn != turn:
                raise ValueError("observation and public cutoff turn differ")
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise DecisionConsistencyError(str(error)) from error
        values = dict(battle=battle, protocol_battle=protocol_battle, actor=actor, rqid=rqid, turn=turn,
                      _payload=_json(snapshot), _commands=_json(frozen_commands),
                      _prefix=_json(frozen_prefix), _boundary=_json(boundary))
        values["fingerprint"] = hashlib.sha256(
            _json([snapshot, frozen_commands, rows, protocol_battle]).encode("utf-8")).hexdigest()
        for key, value in values.items():
            object.__setattr__(self, key, value)

    @property
    def key(self):
        return self.battle, self.actor, self.rqid

    @property
    def payload(self):
        return json.loads(self._payload)

    @property
    def commands(self):
        return json.loads(self._commands)

    @property
    def prefix(self):
        return json.loads(self._prefix)

    @property
    def boundary(self):
        return json.loads(self._boundary)

    @property
    def decision_id(self):
        battle_id = hashlib.sha256(self.battle.encode("utf-8")).hexdigest()[:20]
        return f"planner-{battle_id}-{self.actor}-{self.rqid}"


@dataclass(frozen=True)
class DecisionResult:
    decision_id: str
    payload: dict
    choice: str
    command: str
    automatic: bool
    reused: bool
    plan: dict | None


def validate_plan(plan):
    """Validate shape only: a strategically poor but usable plan is still output."""
    fields = {"objective", "priorities", "preserve", "threats", "tera_policy", "contingencies"}
    def text(value):
        return isinstance(value, str) and bool(value.strip())
    if not isinstance(plan, dict) or set(plan) != fields:
        raise PlanOutputError("planner response must contain the six strategic plan fields")
    if not text(plan["objective"]) or not text(plan["tera_policy"]):
        raise PlanOutputError("planner objective and tera_policy must be nonempty strings")
    for key in ("priorities", "preserve", "threats"):
        if not isinstance(plan[key], list) or not all(text(item) for item in plan[key]):
            raise PlanOutputError(f"planner {key} must be an array of nonempty strings")
    if (not isinstance(plan["contingencies"], list)
            or any(not isinstance(item, dict) or set(item) != {"if", "then"}
                   or not text(item["if"]) or not text(item["then"])
                   for item in plan["contingencies"])):
        raise PlanOutputError("planner contingencies require if/then string objects")
    return copy.deepcopy(plan)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PlanOutputError("duplicate field in planner JSON")
        value[key] = item
    return value


def parse_plan(content, *, finish_reason=None):
    if finish_reason in ("length", "max_tokens"):
        raise PlanOutputError("planner response was truncated")
    if not isinstance(content, str) or not content.strip():
        raise PlanOutputError("planner response was empty")
    def invalid_constant(_):
        raise PlanOutputError("nonfinite number in planner JSON")
    try:
        plan = json.loads(content, object_pairs_hook=_unique_object, parse_constant=invalid_constant)
    except (ValueError, TypeError) as error:
        if isinstance(error, PlanOutputError):
            raise
        raise PlanOutputError("planner response is not a JSON object") from None
    return validate_plan(plan)


def build_planner_messages(context, config, previous_plan=None, since=None):
    payload = candidate_input(context.payload, config)
    if "guide" in config["prompts"]:
        # Use the prepared text, never reread an editable path during a decision.
        guide = config["prompts"]["guide"].get("text")
        if not isinstance(guide, str) or not guide.strip():
            raise DecisionConsistencyError("planner guide must contain frozen nonempty text")
        system = config["prompts"]["planner"]["text"] + "\n\n" + guide
    else:
        # Preserve the exact EP-145 composition for configurations frozen before
        # the independent guide asset existed. New load_config always resolves it.
        instructions = payload["questions"]["action"]["instructions"]
        parts = instructions.split("\n\n", 1)
        if len(parts) != 2 or not parts[0].startswith("Choose exactly one supplied legal candidate"):
            raise DecisionConsistencyError("planner requires the v6 observation guide")
        guide = parts[1]
        lead_instruction = ("\nChoose the lead Pokemon using your own team and the opponent's public "
                            "team preview. Other team slots keep their original relative order.")
        if guide.endswith(lead_instruction):
            guide = guide[:-len(lead_instruction)]
        system = config["prompts"]["planner"]["text"] + "\n\nOBSERVATION AND CALCULATION GUIDE\n\n" + guide
    current = dict(state=payload["state"], criteria=payload["questions"]["action"]["criteria"])
    user = dict(current=current, previous_plan=copy.deepcopy(previous_plan),
                public_events_since_plan=public_events(context.prefix, context.boundary,
                    actor=context.actor, battle=context.protocol_battle, since=since))
    return [dict(role="system", content=system),
            dict(role="user", content=_json(user))]


@dataclass
class _ActorState:
    plan: dict | None = None
    plan_turn: int | None = None
    plan_boundary: dict | None = None
    plan_decision: str | None = None
    seen_events: set = field(default_factory=set)
    pending_events: dict = field(default_factory=dict)
    last_boundary: tuple | None = None
    last_turn: int = 0


class PlanningController:
    def __init__(self, config, planner, executor, record, token_guard=None):
        self.config = copy.deepcopy(config)
        self.planner = planner
        self.executor = executor
        self.record = record
        self.token_guard = token_guard
        self._states = {}
        self._locks = {}
        self._fingerprints = {}
        self._tasks = {}
        self._pending_cleanup = {}
        self._sent = set()
        self._closed = set()

    def _record(self, context, event_type, **data):
        self.record(redact(dict(type=event_type, decision=context.decision_id,
            battle=context.battle, protocol_battle=context.protocol_battle,
            actor=context.actor, rqid=context.rqid,
            turn=context.turn, boundary=context.boundary, **copy.deepcopy(data))))

    def _check_identity(self, context):
        previous = self._fingerprints.get(context.key)
        if previous is not None and previous != context.fingerprint:
            raise DecisionConsistencyError("same rqid has different observation or candidate order")
        self._fingerprints[context.key] = context.fingerprint

    async def decide(self, context, *, ensure_current=None):
        if (context.battle, context.actor) in self._closed:
            raise DecisionConsistencyError("battle actor has already ended")
        self._check_identity(context)
        reused = context.key in self._tasks
        if not reused:
            self._tasks[context.key] = asyncio.create_task(self._decide(context, ensure_current))
        result = await asyncio.shield(self._tasks[context.key])
        if reused:
            await self._ensure_current(ensure_current)
            self._record(context, "selection", choice=result.choice, command=result.command,
                         automatic=result.automatic, reused=True,
                         plan_generated_turn=result.plan["generated_turn"] if result.plan else None,
                         plan_age=result.plan["age_turns"] if result.plan else None)
        return replace(copy.deepcopy(result), reused=reused)

    @staticmethod
    async def _ensure_current(callback):
        if callback is not None and await callback() is False:
            raise StaleDecisionError("request or legal candidates changed while planning")

    def _advice(self, state, turn):
        if state.plan is None:
            return None
        return dict(plan=copy.deepcopy(state.plan), generated_turn=state.plan_turn,
                    age_turns=turn - state.plan_turn, decision=state.plan_decision,
                    boundary=copy.deepcopy(state.plan_boundary))

    async def _decide(self, context, ensure_current):
        actor_key = context.battle, context.actor
        lock = self._locks.setdefault(actor_key, asyncio.Lock())
        async with lock:
            if actor_key in self._closed:
                raise StaleDecisionError("battle actor ended before decision")
            await self._ensure_current(ensure_current)
            state = self._states.setdefault(actor_key, _ActorState())
            position = coordinates(context.boundary)
            if ((state.last_boundary is not None and position < state.last_boundary)
                    or context.turn < state.last_turn):
                raise DecisionConsistencyError("decision cutoff moved backwards")
            state.last_boundary, state.last_turn = position, context.turn
            base = candidate_input(context.payload, self.config)
            payload = copy.deepcopy(base)
            commands = context.commands
            criteria = payload["questions"]["action"]["criteria"]
            rows = public_events(context.prefix, context.boundary,
                                 actor=context.actor, battle=context.protocol_battle)
            events = trigger_events(rows, decision_kind=payload["state"].get("decision_kind"),
                                    rqid=context.rqid, enabled=self.config["trigger"].get("events", ()))
            for event in events:
                identity = event_identity(event)
                if identity not in state.seen_events:
                    state.seen_events.add(identity)
                    state.pending_events[identity] = event
            settings = self.config["trigger"]
            policy = settings["policy"]
            reasons = []
            age = context.turn - state.plan_turn if state.plan_turn is not None else None
            if policy == "off":
                reasons = ["off"]
            elif len(criteria) == 1:
                reasons = ["single_candidate"]
            else:
                if state.plan is None:
                    reasons.append("initial")
                if policy == "every_decision":
                    reasons.append("every_decision")
                if (policy in ("periodic", "events_or_periodic") and age is not None
                        and age >= settings["interval_turns"]):
                    reasons.append("periodic")
                if policy in ("events", "events_or_periodic"):
                    pending = {event["kind"] for event in state.pending_events.values()}
                    reasons.extend("event:" + kind for kind in settings["events"] if kind in pending)
                if not reasons:
                    reasons = ["plan_reuse"]
            should_call = reasons[0] not in ("off", "single_candidate", "plan_reuse")
            self._record(context, "planner_decision", should_call=should_call, reasons=reasons,
                         plan_age=age, plan_generated_turn=state.plan_turn,
                         pending_events=list(state.pending_events.values()))
            if should_call:
                messages = build_planner_messages(context, self.config,
                    previous_plan=self._advice(state, context.turn), since=state.plan_boundary)
                self._record(context, "planner_request", messages=messages)
                try:
                    if actor_key in self._closed:
                        raise StaleDecisionError("battle actor ended before planner request")
                    response = await self.planner.plan(messages, request_id=context.decision_id)
                    if not isinstance(response, dict):
                        raise PlanOutputError("planner client returned no response object")
                    self._record(context, "planner_response", **response)
                    plan = parse_plan(response.get("content"), finish_reason=response.get("finish_reason"))
                    if response.get("plan") is not None and response["plan"] != plan:
                        raise PlanOutputError("parsed planner plan differs from original content")
                    await self._ensure_current(ensure_current)
                except Exception as error:
                    self._record(context, "planner_failure", category=getattr(error, "category", "internal"),
                                 message=str(error), scope=getattr(error, "scope", "collection"))
                    raise
                state.plan, state.plan_turn = plan, context.turn
                state.plan_boundary, state.plan_decision = context.boundary, context.decision_id
                state.pending_events.clear()
            advice = None if policy == "off" else self._advice(state, context.turn)
            if advice is not None:
                payload["state"]["planner_advice"] = advice
                payload["questions"]["action"]["instructions"] += (
                    "\n\n" + self.config["prompts"]["executor"]["text"])
            if self.token_guard is not None:
                self.token_guard(copy.deepcopy(payload))
            self._record(context, "input", payload=payload, base_payload=base, commands=commands)
            started = time.monotonic()
            automatic = len(criteria) == 1
            if automatic:
                choice = next(iter(criteria))
            else:
                if actor_key in self._closed:
                    raise StaleDecisionError("battle actor ended before executor request")
                body = await self.executor(copy.deepcopy(payload), decision=context.decision_id)
                self._record(context, "response", body=body, elapsed_seconds=time.monotonic() - started)
                choice = validate_answer(body, criteria)
                self._record(context, "judgment_diagnostics",
                    diagnostics=judgment_diagnostics(body["answers"]["action"], criteria))
            await self._ensure_current(ensure_current)
            if list(payload["questions"]["action"]["criteria"]) != list(commands):
                raise DecisionConsistencyError("candidate order changed during execution")
            self._record(context, "selection", choice=choice, command=commands[choice],
                         automatic=automatic, reused=False, elapsed_seconds=time.monotonic() - started,
                         plan_age=advice["age_turns"] if advice else None,
                         plan_generated_turn=advice["generated_turn"] if advice else None)
            return DecisionResult(context.decision_id, payload, choice, commands[choice], automatic, False, advice)

    def was_sent(self, context):
        self._check_identity(context)
        return context.key in self._sent

    def mark_sent(self, context):
        """Reserve the one allowed send immediately before the caller transmits it."""
        if (context.battle, context.actor) in self._closed:
            raise StaleDecisionError("battle actor ended before transmission")
        self._check_identity(context)
        task = self._tasks.get(context.key)
        if task is None or not task.done() or task.cancelled() or task.exception() is not None:
            raise DecisionConsistencyError("cannot send a decision without a completed selection")
        if context.key in self._sent:
            return False
        self._sent.add(context.key)
        return True

    def end_battle(self, battle, actor):
        """Discard strategy while retaining duplicate/sent identity tombstones."""
        key = battle, actor
        self._closed.add(key)
        self._states.pop(key, None)
        self._locks.pop(key, None)
        for decision_key, task in list(self._tasks.items()):
            if decision_key[:2] == key:
                if not task.done():
                    self._pending_cleanup[decision_key] = task
                    owner = task.get_loop()
                    try:
                        current = asyncio.get_running_loop()
                    except RuntimeError:
                        current = None
                    if owner is current:
                        task.cancel()
                    elif owner.is_running():
                        owner.call_soon_threadsafe(task.cancel)
                self._tasks.pop(decision_key)

    async def wait_pending(self, battle=None, actor=None):
        """Drain internal shielded work on its owning loop before freezing logs.

        This consumes already reported task exceptions; it is a cleanup boundary,
        not a success result or a retry. end_battle schedules cancellation first.
        """
        current = asyncio.get_running_loop()
        groups = {}
        pending = {**self._tasks, **self._pending_cleanup}
        for key, task in pending.items():
            if (battle is not None and key[0] != battle) or (actor is not None and key[1] != actor):
                continue
            if task.done():
                if not task.cancelled():
                    task.exception()
                continue
            groups.setdefault(task.get_loop(), []).append(task)
        async def drain(tasks):
            await asyncio.gather(*tasks, return_exceptions=True)
        for owner, tasks in groups.items():
            if owner is current:
                await drain(tasks)
            elif owner.is_running():
                await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(drain(tasks), owner))
            else:
                raise DecisionConsistencyError("actor loop stopped before pending decision cleanup")
        for key, task in list(self._pending_cleanup.items()):
            if task.done():
                self._pending_cleanup.pop(key, None)
