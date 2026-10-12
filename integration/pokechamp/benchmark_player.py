"""Pinned, parent-owned call-role instrumentation for the baseline benchmark."""

from __future__ import annotations

import ast
import inspect
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from typing import Any

from integration.pokechamp.cloud import CloudRequestError, OllamaCloudBackend


def normalize_name(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


@dataclass(frozen=True)
class ActionCandidate:
    kind: str
    name: str
    target: Any
    source: str

    def record(self):
        return {"action": {self.kind: self.name}, "source": self.source}


class ActionCandidates:
    def __init__(self, entries):
        self.entries = tuple(entries)
        self.failure_reason = None

    def records(self):
        return [entry.record() for entry in self.entries]

    def resolve(self, value):
        self.failure_reason = None
        if not isinstance(value, dict) or len(value) != 1:
            self.failure_reason = "expected exactly one action field"
        else:
            kind, name = next(iter(value.items()))
            if isinstance(name, str):
                matches = [
                    e
                    for e in self.entries
                    if e.kind == kind and normalize_name(e.name) == normalize_name(name)
                ]
                if len(matches) == 1:
                    return matches[0]
                self.failure_reason = (
                    "ambiguous action name" if matches else "action outside candidates"
                )
            else:
                self.failure_reason = "action name must be a string"
        raise ValueError(self.failure_reason)

    def instruction(self):
        return (
            "Choose exactly one allowed JSON object: "
            + json.dumps(
                [e.record()["action"] for e in self.entries], separators=(",", ":")
            )
            + ". Return only that object, without explanation or Markdown."
        )

    def order(self, value, create_order):
        entry = self.resolve(value)
        order = create_order(
            entry.target,
            dynamax=entry.kind == "dynamax",
            terastallize=entry.kind == "terastallize",
        )
        if order is None:
            raise ValueError("candidate could not be converted to an order")
        return order


def build_candidates(battle, sim=None, opponent=False):
    entries = []
    active = battle.opponent_active_pokemon if opponent else battle.active_pokemon
    forced = active is None or active.fainted or (not opponent and battle.force_switch)
    if opponent:
        observed = list(battle.opponent_team.values())
        preview = list(getattr(battle, "_teampreview_opponent_team", ()))
        # Observed state supersedes preview snapshots, including fainted/active flags.
        known_species = {p.species for p in observed}
        switches = [(p, "observed") for p in observed]
        switches += [
            (p, "public_preview") for p in preview if p.species not in known_species
        ]
        moves = []
        if not forced:
            from poke_env.environment.move import Move

            confirmed = list(active.moves)
            predicted = sim.get_opponent_current_moves(mon=active)
            for name in dict.fromkeys(confirmed + predicted):
                move = active.moves.get(name) or Move(name, gen=sim.gen.gen)
                moves.append((move, "observed" if name in confirmed else "inferred"))
    else:
        moves = [(m, "available_request") for m in battle.available_moves]
        switches = [(p, "available_request") for p in battle.available_switches]
    if not forced:
        for move, source in moves:
            entries.append(ActionCandidate("move", move.id, move, source))
            for kind, flag in (
                ("terastallize", "can_tera"),
                ("dynamax", "can_dynamax"),
            ):
                capability = "opponent_" + flag if opponent else flag
                allowed = getattr(battle, capability, False)
                if opponent and kind == "terastallize":
                    allowed = getattr(battle, "_opponent_can_terrastallize", False)
                if opponent and kind == "dynamax":
                    allowed = allowed and sim.gen.gen == 8
                if allowed:
                    entries.append(ActionCandidate(kind, move.id, move, source))
    for pokemon, source in switches:
        if pokemon is not active and not pokemon.active and not pokemon.fainted:
            entries.append(ActionCandidate("switch", pokemon.species, pokemon, source))
    return ActionCandidates(entries)


def opponent_state_prompt(battle, history):
    from integration.pokechamp.observability.player import snapshot_battle

    return (
        "Predict the opponent's next action. "
        "Player force_switch applies only to the player.\n"
        + history
        + "\nObserved state: "
        + json.dumps(snapshot_battle(battle))
    )


def abort_backend(backend, category):
    """Stop future calls while allowing an already paid response to be recorded."""
    if backend is not None and backend.terminal_error is None:
        backend.terminal_error = CloudRequestError(category, "battle cancelled")
        backend.failure_event.set()


class BenchmarkBackend(OllamaCloudBackend):
    role = "self_action"
    target: Any = None
    candidates = None
    inflight = False
    action_policy = "strict"
    io_context = None

    def get_LLM_action(self, *args, **kwargs):
        self.inflight = True
        try:
            result = super().get_LLM_action(*args, **kwargs)
            if self.terminal_error:
                raise self.terminal_error
            return result
        finally:
            self.inflight = False

    def _trace_llm_call(self, **payload):
        validation = dict(payload.get("validation", {}))
        validation["call_role"] = self.role
        validation["failure_reason"] = (
            self.candidates.failure_reason if self.candidates else None
        )
        validation["role_contract_valid"] = validation.get(
            "output_contract_valid", False
        )
        if self.role in ("tool_choice", "state_value"):
            validation["battle_action_valid"] = None
        payload["validation"] = validation
        reported = payload.get("response", {}).get("reported_model")
        if reported is not None and reported != self.model:
            self.terminal_error = CloudRequestError(
                "model", "reported model differs from declared model"
            )
            self.failure_event.set()
            payload["status"] = "failure"
            payload["validation"] = {
                **payload.get("validation", {}),
                "category": "model",
            }
        super()._trace_llm_call(**payload)

    def _request_context(self):
        from integration.pokechamp.observability.player import snapshot_battle

        from .improved_io.experiment_policy import selected

        return {
            **selected(getattr(self, "experiment_policy", {})),
            "call_role": self.role,
            "io_context": self.io_context,
            "action_candidates": self.candidates.records() if self.candidates else None,
            "target_state": snapshot_battle(self.target)
            if self.target is not None
            else None,
        }

    def _json_instruction(self):
        if self.candidates is not None and self.role in (
            "self_action",
            "opponent_action",
        ):
            return self.candidates.instruction()
        shape = {
            "tool_choice": '{"choice":"minimax"} or {"choice":"damage calculator"}',
            "state_value": '{"score":<integer from 1 to 100>}',
            "opponent_action": (
                "one predicted opponent action from the supplied opponent candidates"
            ),
            "self_action": "one available player action from the supplied state",
        }[self.role]
        return (
            f"Return only one compact JSON object: {shape}. "
            "No reasoning, explanation, or Markdown in message.content."
        )

    def _battle_action_valid(self, output, battle):
        if self.action_policy == "upstream":
            return None  # Conversion belongs exclusively to the pinned caller.
        try:
            value = json.loads(output)
        except (ValueError, TypeError):
            return False
        if not isinstance(value, dict):
            return False
        if self.role == "tool_choice":
            return set(value) == {"choice"} and value["choice"] in (
                "minimax",
                "damage calculator",
            )
        if self.role == "state_value":
            return (
                set(value) == {"score"}
                and type(value["score"]) is int
                and 1 <= value["score"] <= 100
            )
        if self.candidates is None:
            return False
        try:
            self.candidates.resolve(value)
            return True
        except ValueError:
            return False


def instrument_minimax(base):
    """Attach roles at two specific AST call sites; reject upstream shape drift.

    Transform the pinned function, keeping its algorithm, prompts and temperatures.
    This is deliberately not response/prompt-text based role inference.
    """
    function = base.tree_search_optimized
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    roles = []

    class Instrument(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "get_LLM_action"
            ):
                keywords = {kw.arg: kw.value for kw in node.keywords}
                limit = keywords.get("max_tokens")
                if not isinstance(limit, ast.Constant) or limit.value not in (100, 500):
                    raise RuntimeError("pinned minimax call-site contract changed")
                role = "tool_choice" if limit.value == 100 else "state_value"
                roles.append(role)
                node.keywords.append(
                    ast.keyword(arg="call_role", value=ast.Constant(role))
                )
                if role == "state_value":
                    for kw in node.keywords:
                        if kw.arg == "battle":
                            # Validation/telemetry must refer to the simulated leaf,
                            # while the upstream prompt and search remain unchanged.
                            kw.value = ast.parse(
                                "node.simulation.battle", mode="eval"
                            ).body
            return node

        def visit_Return(self, node):
            self.generic_visit(node)
            if isinstance(node.value, ast.Name) and node.value.id == "dmg_calc_out":
                return [
                    ast.parse("self._upstream_selected_damage(dmg_calc_out)").body[0],
                    node,
                ]
            return node

        def visit_ExceptHandler(self, node):
            self.generic_visit(node)
            note = ast.Expr(
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="_benchmark_note",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Constant("exception_fallback"),
                        ast.Constant(node.lineno),
                    ],
                    keywords=[],
                )
            )
            node.body.insert(0, note)
            return node

    tree = Instrument().visit(tree)
    if roles != ["tool_choice", "state_value"]:
        raise RuntimeError(f"unexpected minimax roles: {roles}")
    ast.fix_missing_locations(tree)
    namespace = dict(function.__globals__)
    exec(compile(tree, function.__code__.co_filename, "exec"), namespace)
    return namespace[function.__name__]


def instrument_io(base):
    function = base.io
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))

    class Instrument(ast.NodeTransformer):
        def visit_For(self, node):
            self.generic_visit(node)
            if (
                isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "range"
            ):
                node.body.insert(0, ast.parse("self._upstream_attempt()").body[0])
                node.body.append(
                    ast.parse("self._upstream_io_failure('candidate_connection')").body[
                        0
                    ]
                )
            return node

        def visit_ExceptHandler(self, node):
            self.generic_visit(node)
            if node.name == "e":
                node.body.insert(
                    0,
                    ast.parse(
                        "self._upstream_io_failure('json_parse' if isinstance(e, json.JSONDecodeError) else 'candidate_connection')"
                    ).body[0],
                )
            return node

        def visit_Assign(self, node):
            self.generic_visit(node)
            if (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "choose_max_damage_move"
            ):
                return [ast.parse("self._upstream_stage('io_exhausted')").body[0], node]
            return node

    tree = Instrument().visit(tree)
    ast.fix_missing_locations(tree)
    namespace = dict(function.__globals__)
    exec(compile(tree, function.__code__.co_filename, "exec"), namespace)
    return namespace[function.__name__]


def make_benchmark_llm_class(base):
    from integration.pokechamp.observability.player import make_traced_player_class

    traced = make_traced_player_class(base)

    class BenchmarkLLM(traced):
        tree_search_optimized = instrument_minimax(base)
        _upstream_io = instrument_io(base)
        _call_role = "self_action"
        _candidate_prompt = ""

        def _initialize_minimax_optimizer(self, battle):
            super()._initialize_minimax_optimizer(battle)
            if not self.use_optimized_minimax:
                self._benchmark_note("optimizer_initialization_failure")
                self.llm.terminal_error = CloudRequestError(
                    "algorithm", "declared optimized minimax could not initialize"
                )
                self.llm.failure_event.set()
                raise self.llm.terminal_error

        def _benchmark_note(self, kind, source_line=None):
            if self.llm.action_policy == "upstream":
                if self.llm.terminal_error:
                    raise self.llm.terminal_error
                # Identify the outer handler by its AST, retaining pinned depth bug.
                tree = ast.parse(
                    textwrap.dedent(inspect.getsource(base.tree_search_optimized))
                )
                outer = next(n for n in tree.body[0].body if isinstance(n, ast.Try))
                if (
                    kind == "exception_fallback"
                    and source_line == outer.handlers[0].lineno
                ):
                    self._upstream_stage(
                        "minimax_exception",
                        failure_type=type(sys.exc_info()[1]).__name__,
                        failure_reason=str(sys.exc_info()[1]),
                    )
                elif kind == "exception_fallback" and self._fallback_active:
                    self._upstream_stage("exception_handler", source_line=source_line)
            self.diagnostics.append({"kind": kind, "source_line": source_line})

        def _upstream_selected_damage(self, order):
            if self.llm.action_policy == "upstream":
                self._benchmark_note("selected_damage_calculator")
                self._order_refs.append(order)
                self._order_origins[id(order)] = "normal_damage_calculator"

        def _upstream_stage(self, stage, **extra):
            self._fallback_active = True
            record = {
                "kind": "fallback_stage",
                "stage": stage,
                "io_context": dict(self.llm.io_context or {}),
                **extra,
            }
            self._decision_provenance.append(record)
            self.diagnostics.append(record)

        def _upstream_attempt(self):
            if self.llm.terminal_error:
                raise self.llm.terminal_error
            self.llm.io_context["attempt"] += 1

        def _upstream_io_failure(self, cause):
            if self.llm.terminal_error:
                raise self.llm.terminal_error
            record = {
                "kind": "io_output_error",
                "cause": cause,
                "io_context": dict(self.llm.io_context),
            }
            self.diagnostics.append(record)
            self._decision_provenance.append(record)

        async def _handle_battle_request(self, *args, **kwargs):
            self._sent_origin = "upstream_action"
            self._decision_provenance = []
            return await super()._handle_battle_request(*args, **kwargs)

        def choose_move(self, battle):
            self._decision_provenance = []
            self._fallback_active = False
            self._order_origins = {}
            self._order_refs = []
            order = super().choose_move(battle)
            self._sent_origin = self._order_origins.get(id(order), "upstream_action")
            return order

        def choose_max_damage_move(self, battle):
            if self.llm.action_policy != "upstream":
                return super().choose_max_damage_move(battle)
            if self.llm.terminal_error:
                raise self.llm.terminal_error
            if self._fallback_active:
                self._upstream_stage("base_power")
            order = super().choose_max_damage_move(battle)
            if self._fallback_active:
                self._order_refs.append(order)
                self._order_origins[id(order)] = (
                    "fallback_base_power"
                    if battle.available_moves
                    else "fallback_random_or_default"
                )
            return order

        def choose_random_move(self, battle):
            if self.llm.action_policy == "upstream" and self._fallback_active:
                self._upstream_stage("random")
            return super().choose_random_move(battle)

        def choose_default_move(self):
            if self.llm.action_policy == "upstream" and self._fallback_active:
                self._upstream_stage("default_order")
            return super().choose_default_move()

        def dmg_calc_move(self, *args, **kwargs):
            fallback = self.llm.action_policy == "upstream" and self._fallback_active
            try:
                result = super().dmg_calc_move(*args, **kwargs)
            except Exception:
                if fallback:
                    self._upstream_stage("damage_calculator_failed")
                raise
            if fallback:
                if result[0] is None:
                    self._upstream_stage("damage_calculator_failed")
                else:
                    self._upstream_stage("damage_calculator")
                    self._order_refs.append(result[0])
                    self._order_origins[id(result[0])] = "fallback_damage_calculator"
            return result

        def io(self, *args, **kwargs):
            bound = inspect.signature(base.io).bind(self, *args, **kwargs)
            bound.apply_defaults()
            call = bound.arguments
            if self.llm.action_policy == "upstream":
                old_role, old_context = self._call_role, self.llm.io_context
                old_fallback = self._fallback_active
                self._call_role = (
                    "opponent_action" if call["dont_verify"] else "self_action"
                )
                self._io_serial += 1
                self.llm.io_context = {
                    "io_call_id": self._io_serial,
                    "attempt": 0,
                    "max_attempts": call["retries"],
                    "role": self._call_role,
                }
                self._fallback_active = False
                try:
                    result = self._upstream_io(*args, **kwargs)
                    if self.llm.terminal_error:
                        raise self.llm.terminal_error
                    record = {
                        "kind": "io_result",
                        "io_context": dict(self.llm.io_context),
                        "fallback": self._fallback_active,
                    }
                    self.diagnostics.append(record)
                    self._decision_provenance.append(record)
                    return result
                finally:
                    self._call_role, self.llm.io_context = old_role, old_context
                    self._fallback_active = old_fallback
            old = self._call_role
            self._call_role = (
                "opponent_action" if call["dont_verify"] else "self_action"
            )
            try:
                candidates = build_candidates(
                    call["battle"], call["sim"], call["dont_verify"]
                )
                self.llm.candidates = candidates
                if not candidates.entries:
                    raise ValueError("no action candidates")
                user_prompt = call["state_prompt"]
                if call["dont_verify"]:
                    user_prompt = opponent_state_prompt(
                        call["battle"],
                        call["sim"].get_turn_summary(call["battle"], n_turn=16),
                    )
                output = self.get_LLM_action(
                    system_prompt=call["system_prompt"],
                    user_prompt=user_prompt,
                    model=self.backend,
                    temperature=self.temperature,
                    max_tokens=300,
                    json_format=True,
                    battle=call["battle"],
                )
                return candidates.order(json.loads(output), self.create_order)
            except Exception as error:
                if self.llm.terminal_error is None:
                    self._benchmark_note("candidate_failure: " + str(error))
                    self.llm.terminal_error = CloudRequestError(
                        "output_contract", str(error)
                    )
                    self.llm.failure_event.set()
                raise self.llm.terminal_error from error
            finally:
                self._call_role = old

        def get_LLM_action(self, *args, call_role=None, **kwargs):
            bound = inspect.signature(base.get_LLM_action).bind(self, *args, **kwargs)
            bound.apply_defaults()
            call = dict(bound.arguments)
            call.pop("self")
            backend = call.pop("llm") or self.llm
            backend.role = call_role or self._call_role
            backend.target = call.get("battle")
            if backend.role in ("tool_choice", "state_value"):
                backend.candidates = None
            call["json_format"] = True
            output, _, _ = backend.get_LLM_action(**call)
            if backend.terminal_error:
                raise backend.terminal_error
            if backend.role == "tool_choice" and backend.action_policy != "upstream":
                self._benchmark_note(
                    "selected_" + json.loads(output)["choice"].replace(" ", "_")
                )
            return output

        def __init__(self, *args, **kwargs):
            self.diagnostics = []
            self._io_serial = 0
            self._decision_provenance = []
            self._fallback_active = False
            self._order_origins = {}
            self._order_refs = []
            self._sent_origin = "upstream_action"
            super().__init__(*args, **kwargs)
            traced_send = self.ps_client.send_message

            async def guarded_send(message, room="", message_2=None):
                if message.startswith(("/choose ", "/team ")):
                    if self.llm.terminal_error:
                        raise self.llm.terminal_error
                    cancel = getattr(self, "benchmark_cancel_path", None)
                    if cancel is not None and cancel.exists():
                        raise RuntimeError("peer_failure")
                if (
                    message.startswith("/choose ")
                    and self.llm.action_policy == "upstream"
                ):
                    self._trace(
                        "record_decision_result",
                        selected_action=message,
                        validation={
                            "action_policy": "upstream",
                            "action_origin": self._sent_origin,
                            "fallback_events": self._decision_provenance,
                        },
                    )
                if message.startswith("/choose ") and getattr(self.llm, "action_resolution", None):
                    self._trace("record_decision_result", selected_action=message,
                                validation={"action_resolution": self.llm.action_resolution,
                                            "action_origin": self._sent_origin})
                return await traced_send(message, room, message_2)

            self.ps_client.send_message = guarded_send

    return BenchmarkLLM
