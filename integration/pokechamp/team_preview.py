"""C-033: one actor-owned lead decision, before the synchronous upstream send."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from pathlib import Path

from .benchmark_player import abort_backend, normalize_name
from .cloud import CloudRequestError

DEFAULT_POLICY = "seeded_random"
POLICIES = (DEFAULT_POLICY, "llm_lead")
VERSION = "v1.0.0"
PROMPT = Path(__file__).with_name("prompts") / "team-preview-v1.0.0.txt"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def prompt_identity(version=VERSION):
    if isinstance(version, dict):
        if version.get("version") == "v1.2.0":
            from .lead_rules import prompt_identity as composed

            return composed(version["lead_strategy"]["version"], version["lead_rules"]["version"])
        version = version["version"]
    if version == "v1.1.0":
        from .effects.delivery import prompt_identity as enriched

        return enriched("lead")
    if version != VERSION:
        raise ValueError("unsupported team preview prompt version")
    return dict(version=VERSION, sha256=hashlib.sha256(PROMPT.read_bytes()).hexdigest())


def actor_policy(slot, role, selection):
    """Absent actor settings retain the historical slot/configuration identity."""
    from .improved_io import experiment_policy as policy

    settings = slot.get("actor_settings")
    if settings is None:
        return DEFAULT_POLICY
    if (
        not isinstance(settings, list)
        or len(settings) != 2
        or any(not isinstance(s, dict) or set(s) != {"team_preview_policy"} for s in settings)
        or role not in ("p1", "p2")
    ):
        raise ValueError("invalid actor team preview settings")
    selected = settings[int(role[-1]) - 1]["team_preview_policy"]
    if selected not in POLICIES:
        raise ValueError("unknown team_preview_policy")
    if selected == "llm_lead" and (
        policy.selected(selection).get("experiment_policy") != policy.LEAD
        or slot.get("actor_conditions", [None, None])[int(role[-1]) - 1] != "B"
        or slot["methods"][int(role[-1]) - 1] != "io"
    ):
        raise ValueError("llm_lead requires the explicit B2 lead policy and a B actor")
    return selected


def parse_lead(content, candidates):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate lead key")
            result[key] = value
        return result

    value = json.loads(content, object_pairs_hook=pairs)
    if not isinstance(value, dict) or set(value) != {"lead_slot"}:
        raise ValueError("expected exactly one lead_slot field")
    slot = value["lead_slot"]
    if type(slot) is not int or slot not in candidates:
        raise ValueError("lead_slot must be an integer in the submitted candidates")
    return slot


def command_for_lead(random_command, slot, candidates):
    """Move just the selected slot, keeping all other relative positions."""
    if candidates != list(range(1, 7)):
        raise ValueError("Gen9 OU requires six submitted slots")
    if not isinstance(random_command, str) or not random_command.startswith("/team "):
        raise ValueError("invalid seeded team order")
    order = random_command.removeprefix("/team ")
    if len(order) != 6 or sorted(order) != list("123456"):
        raise ValueError("seeded team order is not the submitted slot permutation")
    if type(slot) is not int or slot not in candidates:
        raise ValueError("selected slot outside submitted mapping")
    lead = str(slot)
    return "/team " + lead + order.replace(lead, "")


def build_input(own_team, protocol, *, battle_id, actor_id, decision_seq):
    """Read own submission and the first public-preview/private-request pair.

    A protocol packet can contain later rows. Never consult battle objects, the
    latest mutable request, the opponent's source team or rows after this boundary.
    """
    from poke_env.teambuilder.teambuilder import Teambuilder

    request = None
    public = {"p1": [], "p2": []}
    cutoff = None
    preview_ref = None
    request_ref = None
    for event in protocol:
        for line_number, line in enumerate(event["protocol"].splitlines(), 1):
            parts = line.split("|")
            if len(parts) < 2:
                continue
            kind = parts[1]
            if kind in ("turn", "start", "win", "tie"):
                raise ValueError("preview boundary missing before battle start")
            if kind == "gametype" and parts[2] != "singles":
                raise ValueError("lead selection is singles only")
            if kind == "request" and line[9:] and request is None:
                request = json.loads(line[9:])
                request_ref = dict(event_seq=event["event_seq"], line=line_number)
            elif kind == "clearpoke" and preview_ref is None:
                public = {"p1": [], "p2": []}
            elif kind == "poke" and preview_ref is None:
                if len(parts) < 4 or parts[2] not in public:
                    raise ValueError("malformed public preview")
                public[parts[2]].append(dict(details=parts[3], source="public_team_preview"))
            elif kind == "teampreview" and preview_ref is None:
                preview_ref = dict(event_seq=event["event_seq"], line=line_number)
            if preview_ref is not None and request is not None:
                cutoff = dict(event_seq=event["event_seq"], line=line_number)
                break
        if cutoff is not None:
            break
    if cutoff is None or not request or request.get("teamPreview") is not True:
        raise ValueError("missing initial team preview request/boundary")
    side = request["side"]["id"]
    if side not in public:
        raise ValueError("invalid self request side")
    opponent = public["p2" if side == "p1" else "p1"]
    submitted = Teambuilder.parse_showdown_team(
        "\n".join(line.rstrip() for line in own_team.splitlines())
    )
    raw_team = request["side"]["pokemon"]
    if len(submitted) != 6 or len(raw_team) != 6 or len(opponent) != 6:
        raise ValueError("lead selection requires six own and six public opponent members")
    own = []
    for slot, (original, raw) in enumerate(zip(submitted, raw_team), 1):
        species = normalize_name(original.species or original.nickname)
        if normalize_name(raw["details"].split(",")[0]) != species or not raw["ident"].startswith(
            side + ": "
        ):
            raise ValueError("self request slot differs from actual submitted team")
        # Showdown uses base-form default names (e.g. Slowking for Slowking-Galar).
        # An explicit nickname is preserved; the species/order and move set still
        # bind every candidate to the submitted slot even without a nickname.
        if original.species and normalize_name(raw["ident"].split(": ", 1)[1]) != normalize_name(
            original.nickname
        ):
            raise ValueError("self preview nickname differs from submitted slot")
        if "moves" in raw and {normalize_name(m) for m in original.moves} != set(raw["moves"]):
            raise ValueError("self preview moves differ from submitted slot")
        # Whitelist request fields; do not infer defaults from species knowledge.
        member = dict(lead_slot=slot, species=species, source="self_submission_and_request")
        for key in ("ident", "details", "moves", "item", "stats", "condition", "teraType"):
            if key in raw:
                member[key] = copy.deepcopy(raw[key])
        for key, attribute in (("moves", "moves"), ("item", "item"), ("teraType", "tera_type")):
            known = getattr(original, attribute)
            if key != "moves" and key in member and known:
                if not isinstance(member[key], str) or normalize_name(
                    member[key]
                ) != normalize_name(known):
                    raise ValueError("self preview field differs from submitted slot")
            if key not in member and known:
                member[key] = copy.deepcopy(known)
        if "ability" in raw or "baseAbility" in raw:
            member["ability"] = raw.get("ability", raw.get("baseAbility"))
        elif original.ability:
            member["ability"] = original.ability
        if original.ability and (
            not isinstance(member.get("ability"), str)
            or normalize_name(member["ability"]) != normalize_name(original.ability)
        ):
            raise ValueError("self preview ability differs from submitted slot")
        own.append(member)
    value = dict(
        identity=dict(
            battle_id=battle_id,
            actor_id=actor_id,
            decision_seq=decision_seq,
            request_id=request.get("rqid"),
            side=side,
            input_version="team-preview-v1",
            protocol_cutoff=cutoff,
            public_preview_cutoff=preview_ref,
            self_request_ref=request_ref,
        ),
        battle_format="gen9ou",
        self_team=own,
        opponent_preview=opponent,
    )
    value["identity"]["input_sha256"] = digest(value)
    return value


class LeadPlayerMixin:
    """Only opt-in preview requests bypass the synchronous upstream boundary."""

    async def _handle_battle_message(self, split_messages):
        result = await super()._handle_battle_message(split_messages)
        if self.team_preview_policy == "llm_lead":
            # Upstream can receive public preview before the private request and
            # does not call _handle_battle_request for that later private packet.
            tag = split_messages[0][0].removeprefix(">")
            battle = self.battles.get(tag)
            if battle is not None and battle.in_team_preview and tag in self._lead_random_commands:
                await self._handle_battle_request(battle, from_teampreview_request=True)
        return result

    async def _handle_battle_request(
        self,
        battle,
        from_teampreview_request=False,
        maybe_default_order=False,
    ):
        if self.team_preview_policy != "llm_lead":
            return await super()._handle_battle_request(
                battle,
                from_teampreview_request=from_teampreview_request,
                maybe_default_order=maybe_default_order,
            )
        key = battle.battle_tag
        if not from_teampreview_request and not battle.in_team_preview:
            return await super()._handle_battle_request(
                battle,
                from_teampreview_request=False,
                maybe_default_order=maybe_default_order,
            )
        if not from_teampreview_request:
            if maybe_default_order:
                abort_backend(self.llm, "team_preview")
                raise self.llm.terminal_error
            return None
        if key not in self._lead_random_commands:
            # Preserve the inherited shuffle's timing and consumption even when
            # the server's private preview request has not arrived yet.
            self._lead_random_commands[key] = self.random_teampreview(battle)
        if not any("|request|" in e["protocol"] for e in self.io_protocol):
            return None
        # One task owns the decision context, RNG, request and send. Even a later
        # duplicate after preview ended cannot turn into a second call or a move.
        if key not in self._lead_tasks:
            self._lead_tasks[key] = asyncio.create_task(self._select_and_send_lead(battle))
        task = self._lead_tasks[key]
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            abort_backend(self.llm, "team_preview_cancelled")
            # Sync HTTP cannot be killed safely. Drain the owned task so its
            # response/permit are settled and no thread writes into a sealed bundle.
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not task.cancelled():
                task.exception()  # Retrieve a failed result even after repeated cancellation.
            raise

    async def _select_and_send_lead(self, battle):
        recorder = self._research_trace_sink
        handle = recorder.begin_decision(
            showdown_turn=0,
            decision_kind="team_preview",
            battle_state=dict(
                team_preview_policy="llm_lead", showdown_battle_tag=battle.battle_tag
            ),
        )
        try:
            if self.llm.terminal_error:
                raise self.llm.terminal_error
            # This is the exact inherited RNG operation, on the actor event loop.
            random_command = self._lead_random_commands[battle.battle_tag]
            context = build_input(
                self.io_own_team,
                self.io_protocol,
                battle_id=self.io_battle_id,
                actor_id=self.io_actor_id,
                decision_seq=handle.decision_seq,
            )
            if hasattr(self, "_official_lead_snapshot"):
                self._official_lead_snapshot(context)
            candidates = [p["lead_slot"] for p in context["self_team"]]
            command_for_lead(random_command, candidates[0], candidates)
            self.lead_result = dict(
                identity=context["identity"],
                prompt_identity=prompt_identity(
                    getattr(self.llm, "team_preview_prompt_identity", None)
                    if getattr(self.llm, "team_preview_prompt_identity", None) else VERSION),
                seeded_random_command=random_command,
                status="requesting",
            )
            slot = await asyncio.to_thread(self.llm.select_lead, context, self.temperature)
            if self.llm.terminal_error:
                raise self.llm.terminal_error
            if self.llm._cancelled():
                raise CloudRequestError("team_preview_cancelled", "cancelled before team send")
            command = command_for_lead(random_command, slot, candidates)
            self.lead_result.update(lead_slot=slot, command=command, status="selected")
            recorder.record_decision_result(
                selected_action=command,
                canonical_parsed_output={"lead_slot": slot},
                validation=dict(team_preview=self.lead_result, output_contract_valid=True),
            )
            await self.ps_client.send_message(command, battle.battle_tag)
            self.lead_result["status"] = "sent"
            return command
        except Exception as exc:
            from .effects import EffectReferenceError

            if isinstance(exc, EffectReferenceError):
                self.lead_result["input_error"] = exc.as_dict()
            if self.llm.terminal_error is None:
                self.llm.terminal_error = CloudRequestError("team_preview", str(exc))
                self.llm.failure_event.set()
            self.lead_result.update(
                status="failed",
                failure_category=getattr(self.llm.terminal_error, "category", "team_preview"),
            )
            recorder.record_decision_result(
                selected_action=None,
                success=False,
                validation=dict(team_preview=self.lead_result, output_contract_valid=False),
                error=dict(type=type(exc).__name__, category=self.lead_result["failure_category"]),
            )
            raise self.llm.terminal_error from exc
        finally:
            recorder.end_decision(handle)
