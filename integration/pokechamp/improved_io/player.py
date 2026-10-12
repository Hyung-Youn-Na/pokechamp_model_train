"""Fixed IO actor: observation → calculator → validated text → exact order."""

from __future__ import annotations

import json

from ..cloud import CloudRequestError
from ..team_preview import DEFAULT_POLICY, POLICIES, LeadPlayerMixin
from . import battle_prompts
from .calculations import compute
from .calculator import Calculator
from .gate import validate_input
from .memory import BattleMemory, summary_context
from .prompt_versions import asset, identity
from .state import normalize


def make_fixed_player(base):
    class FixedPlayer(LeadPlayerMixin, base):
        def __init__(
            self,
            *args,
            condition_id,
            battle_id,
            actor_id,
            summary_prompt_version="v1.0.0",
            io_profile=None,
            battle_prompt_version="v1.0.0",
            battle_prompt_identity=None,
            team_preview_policy=DEFAULT_POLICY,
            observation_backend="legacy-poke-env",
            battle_delivery=None,
            **kwargs,
        ):
            if team_preview_policy not in POLICIES:
                raise ValueError("unknown team_preview_policy")
            if team_preview_policy == "llm_lead":
                from . import experiment_policy as policy

                selection = getattr(kwargs.get("llm_backend"), "experiment_policy", {})
                if (condition_id != "B" or io_profile != "io-battle-only-v1"
                        or kwargs.get("battle_format") != "gen9ou"
                        or policy.selected(selection).get("experiment_policy") != policy.LEAD):
                    raise ValueError("llm_lead requires Gen9 OU battle-only B and explicit policy")
            from ..observation import OFFICIAL, selected

            self.observation_backend = selected({"observation_backend": observation_backend})
            if self.observation_backend == OFFICIAL and (
                condition_id != "B" or kwargs.get("battle_format") != "gen9ou"
                or io_profile != "io-battle-only-v1"
            ):
                raise ValueError("official observation requires Gen9 OU battle-only B/B2")
            if battle_delivery is not None and (self.observation_backend != OFFICIAL or battle_delivery not in ("B", "B2")):
                raise ValueError("explicit battle delivery requires official B/B2")
            if team_preview_policy == "llm_lead" and battle_delivery == "B":
                raise ValueError("llm_lead retains its B2 battle delivery")
            self.battle_delivery = battle_delivery
            self.io_official = None
            self.io_received_boundary = None
            self.team_preview_policy = team_preview_policy
            self._lead_tasks = {}
            self._lead_random_commands = {}
            self.lead_result = {}
            self.io_profile = io_profile
            if io_profile is not None:
                from .battle_only_protocol import PROFILE

                if io_profile != PROFILE or condition_id != "B":
                    raise ValueError("battle-only fixed actor must be B")
            self.io_summary_prompt_identity = (
                None if io_profile else identity(summary_prompt_version)
            )
            if not io_profile and (
                battle_prompt_version != "v1.0.0" or battle_prompt_identity
            ):
                raise ValueError("battle guide is restricted to battle-only B")
            if self.observation_backend == OFFICIAL and battle_prompt_version != "v1.4.0":
                raise ValueError("official observation requires explicit battle prompt v1.4.0")
            if battle_prompt_version == "v1.4.0" and self.observation_backend != OFFICIAL:
                raise ValueError("battle prompt v1.4.0 requires official observation")
            self.io_battle_prompt_identity = (
                battle_prompts.selected(
                    dict(
                        battle_prompt_version=battle_prompt_version,
                        battle_prompt_identity=battle_prompt_identity,
                    )
                )
                if io_profile
                else None
            )
            self.io_condition = condition_id
            self.io_battle_id = battle_id
            self.io_actor_id = actor_id
            self.io_own_team = kwargs["team"]
            self.io_protocol = []
            self.io_request = None
            self.io_boundaries = []
            self.io_row_boundaries = []
            self.io_summary_boundary = 0
            self.io_memory = BattleMemory(battle_id, actor_id, condition_id == "C")
            self.io_calculator = None
            self.io_last_input = None
            super().__init__(*args, **kwargs)

        def _trace(self, method, *args, **kwargs):
            result = super()._trace(method, *args, **kwargs)
            if method == "record_protocol" and self.observation_backend == "legacy-poke-env":
                protocol = args[0]
                self.io_protocol.append(
                    {
                        "event_seq": self._research_trace_sink._event_seq,
                        "protocol": protocol,
                    }
                )
                for line in protocol.splitlines():
                    if line.startswith("|request|") and line[9:]:
                        self.io_request = json.loads(line[9:])
            return result

        async def _handle_battle_message(self, messages):
            try:
                return await super()._handle_battle_message(messages)
            except Exception as error:
                if self.observation_backend == "official-client-v1":
                    if self.io_official is not None:
                        self.io_official.close()
                    if self.llm.terminal_error is None:
                        self.llm.terminal_error = CloudRequestError("input_contract", str(error))
                        self.llm.failure_event.set()
                raise

        def _received_protocol_row(self, event_seq, index, lines):
            protocol = "\n".join(lines[:index + 1])
            event = {"event_seq": event_seq, "protocol": protocol}
            if self.io_protocol and self.io_protocol[-1]["event_seq"] == event_seq:
                self.io_protocol[-1] = event
            else:
                self.io_protocol.append(event)
            self.io_received_boundary = dict(
                protocol_event_seq=event_seq, line_index=len(protocol.splitlines()) - 1,
            )
            line = lines[index]
            if line.startswith("|request|"):
                self.io_request = json.loads(line[9:]) if line[9:] else None
                if self.io_request and self.io_request.get("side", {}).get("id", self.io_actor_id) != self.io_actor_id:
                    raise ValueError("foreign official actor request")

        def _official_snapshot(self):
            from ..observation.runtime import OfficialClient

            if self.io_official is None:
                self.io_official = OfficialClient(self.io_actor_id)
            return self.io_official.snapshot(
                self.io_protocol, self.io_battle_id, boundary=self.io_received_boundary,
            )

        def _official_lead_snapshot(self, context=None):
            if self.observation_backend != "official-client-v1":
                return
            state = self._official_snapshot()
            self.llm.observation_backend = self.observation_backend
            self._research_trace_sink.record_observation_snapshot(
                boundary=self.io_received_boundary, official_state=state, normalized=context,
            )

        def teampreview(self, battle):
            self._official_lead_snapshot()
            return super().teampreview(battle)

        async def _handle_battle_request(self, battle, from_teampreview_request=False, maybe_default_order=False):
            if self.observation_backend == "official-client-v1" and maybe_default_order:
                raise ValueError("official request rejected; automatic default forbidden")
            return await super()._handle_battle_request(
                battle, from_teampreview_request=from_teampreview_request,
                maybe_default_order=maybe_default_order,
            )

        def close_calculator(self):
            if self.io_official is not None:
                self.io_official.close()
            if self.io_calculator is not None:
                self.io_calculator.close()

        def _call_fixed(self, role, context, prompt, battle):
            if self.io_profile:
                from .battle_only_protocol import validate_context

                validate_context(context, role=role)
                self.llm.io_profile = self.io_profile
                self.llm.battle_prompt_identity = self.io_battle_prompt_identity
            self.llm.observation_backend = getattr(self, "observation_backend", "legacy-poke-env")
            self.llm.battle_delivery = getattr(self, "battle_delivery", None)
            self.llm.role = role
            self.llm.input_context = context
            self.llm.summary_prompt_identity = self.io_summary_prompt_identity
            from . import live_delivery

            self.llm.delivery = None
            user_prompt = json.dumps(context, ensure_ascii=False)
            if self.llm.observation_backend == "official-client-v1":
                from ..observation.delivery import build

                kind = "b2" if (self.battle_delivery == "B2" or self.battle_delivery is None and live_delivery.enabled(self.llm.experiment_policy)) else "battle"
                self.llm.delivery = build(context, kind=kind)
                prompt, user_prompt = self.llm.delivery.system_prompt, self.llm.delivery.user_json
            elif live_delivery.enabled(self.llm.experiment_policy):
                self.llm.delivery = live_delivery.build(
                    context, self.io_battle_prompt_identity["version"])
                prompt = self.llm.delivery.system_prompt
                user_prompt = self.llm.delivery.user_json
            elif (self.io_battle_prompt_identity or {}).get("version") == "v1.3.0":
                from ..effects.delivery import build

                self.llm.delivery = build(context, kind="battle")
                prompt, user_prompt = self.llm.delivery.system_prompt, self.llm.delivery.user_json
            return self.llm.get_LLM_action(
                system_prompt=prompt,
                user_prompt=user_prompt,
                model=self.llm.model,
                temperature=self.temperature,
                json_format=False,
                battle=battle,
            )[0]

        def choose_move(self, battle):
            try:
                return self._fixed_decision(battle)
            except Exception as exc:
                from ..effects import EffectReferenceError

                if isinstance(exc, EffectReferenceError):
                    self.llm.effect_reference_error = exc.as_dict()
                if self.llm.terminal_error is None:
                    category = (
                        "calculation"
                        if type(exc).__name__ == "CalculationError"
                        else "input_contract"
                    )
                    self.llm.terminal_error = CloudRequestError(category, str(exc))
                    self.llm.failure_event.set()
                raise self.llm.terminal_error from exc

        def _fixed_decision(self, battle):
            if self.llm.terminal_error:
                raise self.llm.terminal_error
            self.io_last_input = None
            if self.io_calculator is None:
                self.io_calculator = Calculator()
            self.io_calculator.last_request = None
            self.io_calculator.last_response = None
            cutoff = self.io_boundaries[-10] if len(self.io_boundaries) >= 10 else 0
            recent = self.io_protocol[cutoff:]
            if self.observation_backend == "official-client-v1":
                from ..observation.normalize import normalize as official_normalize

                if len(self.io_row_boundaries) >= 10:
                    previous = self.io_row_boundaries[-10]
                    recent = []
                    for event in self.io_protocol:
                        if event["event_seq"] < previous["protocol_event_seq"]:
                            continue
                        text = event["protocol"]
                        offset = 0
                        if event["event_seq"] == previous["protocol_event_seq"]:
                            offset = previous["line_index"] + 1
                            text = "\n".join(text.splitlines()[offset:])
                        if text:
                            recent.append({**event, "protocol": text,
                                           **({"line_offset": offset} if offset else {})})

                official = self._official_snapshot()
                boundary = dict(self.io_received_boundary, turn=battle.turn,
                                request_id=battle.rqid,
                                decision_seq=self._research_trace_sink._decision_seq)
                try:
                    value, candidates = official_normalize(
                        official, self.io_own_team, recent, self.io_protocol,
                        battle_id=self.io_battle_id, actor_id=self.io_actor_id,
                        decision_seq=self._research_trace_sink._decision_seq,
                        build_identity=self.io_official.identity, boundary=boundary,
                    )
                except Exception as error:
                    self._research_trace_sink.record_observation_snapshot(
                        boundary=boundary, official_state=official, error=str(error),
                    )
                    raise
                self._research_trace_sink.record_observation_snapshot(
                    boundary=boundary, official_state=official, normalized=value,
                )
            else:
                value, candidates = normalize(
                    battle,
                    self.io_request,
                    self.io_own_team,
                    recent,
                    battle_id=self.io_battle_id,
                    actor_id=self.io_actor_id,
                    decision_seq=self._research_trace_sink._decision_seq,
                    observed_protocol=self.io_protocol,
                    semantics_version=(
                        "calculator-input-v2"
                        if self.io_battle_prompt_identity
                        and self.io_battle_prompt_identity["version"] in ("v1.2.0", "v1.3.0")
                        else None
                    ),
                )
            value["condition_id"] = self.io_condition
            self.io_last_input = value
            value["calculation_bundle"] = compute(value, self.io_calculator)
            validate_input(value)
            # The next request means the preceding action's protocol has been
            # incorporated. Never summarize immediately after merely selecting it.
            memory = self.io_memory
            if self.io_profile and (
                memory.enabled
                or memory.archive
                or memory.summaries
                or memory.consolidated
            ):
                raise ValueError("battle-only memory contamination")
            if memory.due():
                context = summary_context(
                    value,
                    self.io_protocol[self.io_summary_boundary :],
                    source_event_ids=[e["event_seq"] for e in self.io_protocol],
                    previous=memory.summaries[-1]
                    if memory.summaries
                    else memory.consolidated,
                    observed_protocol=self.io_protocol,
                )
                text = self._call_fixed(
                    "summary",
                    context,
                    asset("summary", self.io_summary_prompt_identity["version"])[0],
                    battle,
                )
                memory.accept(text, context["source_event_ids"])
                self.io_summary_boundary = len(self.io_protocol)
                if len(memory.summaries) == 3:
                    context["summaries"] = memory.summaries
                    text = self._call_fixed(
                        "summary_rollup",
                        context,
                        asset(
                            "summary_rollup", self.io_summary_prompt_identity["version"]
                        )[0],
                        battle,
                    )
                    memory.accept(text, context["source_event_ids"], rollup=True)
            latest = memory.summaries[-1] if memory.summaries else memory.consolidated
            if latest:
                value["battle_summary"] = {
                    "battle_id": self.io_battle_id,
                    "actor_id": self.io_actor_id,
                    "text": latest,
                }
            validate_input(value)
            self.llm.candidates = candidates
            prompt = (
                battle_prompts.assemble(
                    value,
                    version=self.io_battle_prompt_identity["version"],
                    declared=self.io_battle_prompt_identity,
                )
                if self.io_profile
                else battle_prompts.assemble()
            )
            self._call_fixed("self_action", value, prompt, battle)
            action = self.llm.parsed_action.action
            order = candidates.order(action, self.create_order)
            self.io_boundaries.append(len(self.io_protocol))
            if self.observation_backend == "official-client-v1":
                self.io_row_boundaries.append(dict(self.io_received_boundary))
            memory.decisions += 1
            self._sent_origin = (
                self.llm.action_resolution["selection_source"]
                if getattr(self.llm, "action_resolution", None)
                else "fixed_io"
            )
            return order

    return FixedPlayer
