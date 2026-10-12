"""Text response roles using the existing shared Cloud admission/recording path."""

from __future__ import annotations

import json

from ..benchmark_player import BenchmarkBackend
from ..cloud import CloudConfigurationError
from . import experiment_policy as policy
from .memory import validate_summary
from .output import ActionResponse, parse_action, recover_action


class FixedBackend(BenchmarkBackend):
    action_policy = "fixed"
    input_context = None
    parsed_action = None
    response_error = None
    battle_prompt_identity = None
    summary_prompt_identity = None
    io_profile = None
    experiment_policy = {}
    action_resolution = None
    runtime_identity = None
    delivery = None
    delivery_identity = None
    input_snapshot_event_seq = None
    team_preview_prompt_identity = None
    observation_backend = "legacy-poke-env"
    battle_delivery = None

    def __init__(self, *, summary_thinking_effort="low", **kwargs):
        self.summary_thinking_effort = summary_thinking_effort
        self._validate_summary_effort()
        super().__init__(**kwargs)

    def _validate_summary_effort(self):
        if self.summary_thinking_effort not in ("low", "high", "max"):
            raise CloudConfigurationError(
                "summary_thinking_effort must be low, high or max"
            )

    def _thinking_effort(self):
        self._validate_summary_effort()
        return (
            self.summary_thinking_effort
            if self.role in ("summary", "summary_rollup")
            else "low"
        )

    def get_LLM_action(self, system_prompt, user_prompt, *args, **kwargs):
        if self.role == "team_preview":
            from ..team_preview import PROMPT, prompt_identity

            selected = self.team_preview_prompt_identity or prompt_identity()
            if selected != prompt_identity(selected):
                raise ValueError("team preview prompt identity mismatch")
            if selected["version"] == "v1.2.0":
                from ..lead_rules import validate

                link = validate(self.lead_input, self.lead_delivery, system_prompt, user_prompt,
                                selected)
                self._snapshot(self.lead_input, link)
            elif selected["version"] == "v1.1.0":
                from ..effects.delivery import validate

                link = validate(self.lead_input, self.lead_delivery, system_prompt, user_prompt,
                                kind="lead")
                self._snapshot(self.lead_input, link)
            elif (system_prompt != PROMPT.read_text()
                  or user_prompt != json.dumps(self.lead_input, ensure_ascii=False)):
                raise ValueError("team preview transmitted input/prompt mismatch")
            if kwargs.get("json_format") is not False:
                raise ValueError("team preview transmitted input/prompt mismatch")
            return super().get_LLM_action(system_prompt, user_prompt, *args, **kwargs)
        self.parsed_action = None
        self.response_error = None
        self.action_resolution = None
        from . import live_delivery

        self.delivery_identity = None
        self.input_snapshot_event_seq = None
        compressed = live_delivery.enabled(self.experiment_policy)
        if self.observation_backend == "official-client-v1" and self.battle_delivery is not None:
            if self.battle_delivery not in ("B", "B2"):
                raise ValueError("unknown official battle delivery")
            compressed = self.battle_delivery == "B2"
        enriched = (self.battle_prompt_identity or {}).get("version") == "v1.3.0"
        official = self.observation_backend == "official-client-v1"
        from ..observation import selected as observation_selection

        observation_selection({"observation_backend": self.observation_backend})
        if not official and (
            (self.battle_prompt_identity or {}).get("version") == "v1.4.0"
            or (self.input_context or {}).get("identity", {}).get("observation_version") == "official-client-v1"
        ):
            raise ValueError("official input/prompt requires explicit official observation backend")
        if official:
            from ..observation.delivery import validate

            if not self.io_profile or self.role != "self_action" or (self.battle_prompt_identity or {}).get("version") != "v1.4.0":
                raise ValueError("official observation requires battle-only v1.4.0")
            self._snapshot(self.input_context, validate(
                self.input_context, self.delivery, system_prompt, user_prompt,
                kind="b2" if compressed else "battle"))
        elif compressed:
            if not self.io_profile or self.role != "self_action":
                raise ValueError("B2 requires battle-only self action")
            self.delivery_identity = live_delivery.validate(
                self.input_context, self.delivery, system_prompt, user_prompt,
                version=(self.battle_prompt_identity or {}).get("version", "v1.2.0"),
            )
            self._snapshot(self.input_context, self.delivery_identity)
        elif enriched:
            from ..effects.delivery import validate

            if not self.io_profile or self.role != "self_action":
                raise ValueError("effect battle delivery requires battle-only self action")
            self._snapshot(self.input_context, validate(
                self.input_context, self.delivery, system_prompt, user_prompt, kind="battle"))
        elif self.delivery is not None:
            raise ValueError("delivery is restricted to explicit B2 policy")
        if self.io_profile:
            from .battle_prompts import assemble, identity

            selected = self.battle_prompt_identity or identity()
            expected = assemble(
                self.input_context, version=selected["version"], declared=selected
            )
            if not official and not compressed and not enriched and (
                system_prompt != expected
                or json.loads(user_prompt) != self.input_context
            ):
                raise ValueError("battle prompt or transmitted user context mismatch")
            self.battle_prompt_identity = selected
        return super().get_LLM_action(system_prompt, user_prompt, *args, **kwargs)

    def _snapshot(self, original, link):
        if self.trace_sink is None:
            raise ValueError("model delivery original input recorder required")
        self.delivery_identity = link
        self.input_snapshot_event_seq = self.trace_sink.record_input_snapshot(
            original_input=original, delivery_identity=link,
        )
        if self.input_snapshot_event_seq is None:
            raise ValueError("model delivery original input was not persisted")

    def select_lead(self, context, temperature):
        from ..team_preview import PROMPT, digest, prompt_identity

        if policy.selected(self.experiment_policy).get("experiment_policy") != policy.LEAD:
            raise ValueError("team preview requires explicit B2 lead policy")
        unsigned = {**context, "identity": dict(context["identity"])}
        checksum = unsigned["identity"].pop("input_sha256")
        if digest(unsigned) != checksum or context["battle_format"] != "gen9ou":
            raise ValueError("team preview input identity mismatch")
        if [p["lead_slot"] for p in context["self_team"]] != list(range(1, 7)):
            raise ValueError("team preview candidate identity mismatch")
        old_role, old_candidates = self.role, self.candidates
        self.role, self.candidates = "team_preview", None
        self.lead_input = context
        self.lead_slot = None
        self.lead_error = None
        self.delivery_identity = self.input_snapshot_event_seq = None
        try:
            selected = self.team_preview_prompt_identity or prompt_identity()
            system, user = PROMPT.read_text(), json.dumps(context, ensure_ascii=False)
            if selected["version"] == "v1.2.0":
                from ..lead_rules import build

                self.lead_delivery = build(context, selected)
                system, user = self.lead_delivery.system_prompt, self.lead_delivery.user_json
            elif selected["version"] == "v1.1.0":
                from ..effects.delivery import build

                self.lead_delivery = build(context, kind="lead")
                system, user = self.lead_delivery.system_prompt, self.lead_delivery.user_json
            self.get_LLM_action(
                system, user, self.model,
                temperature=temperature, json_format=False,
            )
            return self.lead_slot
        finally:
            self.role, self.candidates = old_role, old_candidates

    def _request_context(self):
        from . import live_delivery
        from ..observation import OFFICIAL, selection
        observation = selection(OFFICIAL, check_build=False) if self.observation_backend == OFFICIAL else {}

        if self.role == "team_preview":
            from ..team_preview import prompt_identity

            return {
                **({"delivery_identity": self.delivery_identity,
                    "input_snapshot_event_seq": self.input_snapshot_event_seq}
                   if self.delivery_identity else {}),
                **policy.selected(self.experiment_policy), **observation, "call_role": "team_preview",
                "identity": self.lead_input["identity"], "condition_id": "B",
                "team_preview_policy": "llm_lead",
                "team_preview_prompt_identity": (
                    self.team_preview_prompt_identity or prompt_identity()),
            }
        if self.io_profile:
            from .battle_only_protocol import PROFILE, validate_context

            if self.io_profile != PROFILE or self.summary_prompt_identity is not None:
                raise ValueError("battle-only profile or summary configuration")
            if (self.battle_prompt_identity or {}).get(
                "version"
            ) in ("v1.2.0", "v1.3.0", "v1.4.0") and self.input_context.get("identity", {}).get(
                "input_version"
            ) != "calculator-input-v2":
                raise ValueError("v1.2.0 requires calculator-input-v2 state")
            validate_context(self.input_context, role=self.role)
        runtime = {}
        if policy.is_v2_repeat(self.experiment_policy):
            from .inputfix32 import verify_runtime

            runtime = verify_runtime(
                {**self.experiment_policy, **(self.runtime_identity or {}),
                 **({"observation_backend": self.observation_backend} if self.observation_backend == "official-client-v1" else {})},
                context=self.input_context,
                prompt_identity=self.battle_prompt_identity,
            )
        return {
            **({"delivery_identity": self.delivery_identity,
                "input_snapshot_event_seq": self.input_snapshot_event_seq}
               if self.delivery_identity else {}),
            **runtime,
            **policy.selected(self.experiment_policy),
            "call_role": self.role,
            "identity": self.input_context["identity"],
            **({**observation,
                "battle_delivery": self.battle_delivery or ("B2" if live_delivery.enabled(self.experiment_policy) else "B")} if self.observation_backend == "official-client-v1" else {}),
            "calculation_identity": self.input_context.get(
                "calculation_bundle", {}
            ).get("identity"),
            "condition_id": self.input_context["condition_id"],
            "summary_prompt_identity": self.summary_prompt_identity,
            **(
                {"battle_prompt_identity": self.battle_prompt_identity}
                if self.io_profile
                else {}
            ),
        }

    def _text_output_valid(self, content):
        if self.role == "team_preview":
            from ..team_preview import parse_lead

            try:
                self.lead_slot = parse_lead(content, [p["lead_slot"] for p in self.lead_input["self_team"]])
                return True
            except (ValueError, TypeError) as exc:
                self.lead_error = str(exc)
                return False
        self.parsed_action = None
        self.response_error = None
        self.action_resolution = None
        try:
            if self.role == "self_action":
                request = self.input_context["request"]
                self.parsed_action = parse_action(
                    content,
                    request["legal_actions"],
                    request_kind=request["kind"],
                    can_tera=request["can_tera"],
                    english_typography=self.io_profile == "io-battle-only-v1",
                )
            elif self.role in ("summary", "summary_rollup"):
                identity = self.input_context["identity"]
                validate_summary(
                    content,
                    battle_id=identity["battle_id"],
                    actor_id=identity["actor_id"],
                    event_ids=self.input_context["source_event_ids"],
                )
            else:
                raise ValueError("unsupported fixed call role")
            if policy.is_direct(self.experiment_policy) and self.parsed_action:
                self.action_resolution = dict(
                    raw_output_contract_valid=True,
                    output_error=None,
                    extracted_action=self.parsed_action.action,
                    executed_action=self.parsed_action.action,
                    selection_source="model_output",
                    recovery_error=None,
                )
            return True
        except (ValueError, KeyError, TypeError) as exc:
            self.response_error = str(exc)
            if policy.is_direct(self.experiment_policy) and self.role == "self_action":
                request = self.input_context["request"]
                self.action_resolution = recover_action(
                    content,
                    request["legal_actions"],
                    request_kind=request["kind"],
                    can_tera=request["can_tera"],
                    error=self.response_error,
                )
                self.parsed_action = ActionResponse(
                    "", self.action_resolution["executed_action"]
                )
            return False

    def _output_failure_recovered(self):
        return (
            policy.is_direct(self.experiment_policy)
            and self.role == "self_action"
            and self.action_resolution is not None
            and self.action_resolution["raw_output_contract_valid"] is False
        )

    def _trace_llm_call(self, **payload):
        if self.role == "team_preview":
            payload["validation"] = {
                **payload.get("validation", {}), "lead_slot": self.lead_slot,
                "text_failure_reason": self.lead_error,
            }
            payload["canonical_parsed_output"] = (
                {"lead_slot": self.lead_slot} if self.lead_slot is not None else None
            )
            return super()._trace_llm_call(**payload)
        payload["validation"] = {
            **payload.get("validation", {}),
            "text_failure_reason": self.response_error,
        }
        if self.action_resolution:
            payload["validation"]["action_resolution"] = self.action_resolution
            payload["canonical_parsed_output"] = self.action_resolution[
                "extracted_action"
            ]
            if self.action_resolution["raw_output_contract_valid"]:
                payload["validation"]["rationale"] = self.parsed_action.rationale
        elif self.parsed_action:
            payload["canonical_parsed_output"] = self.parsed_action.action
            payload["validation"]["rationale"] = self.parsed_action.rationale
        super()._trace_llm_call(**payload)
