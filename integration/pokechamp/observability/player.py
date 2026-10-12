"""Parent-owned player and transport hooks for research battle tracing."""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from enum import Enum
from typing import Any

from ..providers import redact


def _value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_value(item) for item in value]
    return str(value)


def _attribute(value: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(value, name, default)
    except Exception:
        return default


def _pokemon_snapshot(pokemon: Any) -> dict[str, Any] | None:
    if pokemon is None:
        return None
    return {
        "species": _value(_attribute(pokemon, "species")),
        "active": bool(_attribute(pokemon, "active", False)),
        "fainted": bool(_attribute(pokemon, "fainted", False)),
        "level": _value(_attribute(pokemon, "level")),
        "gender": _value(_attribute(pokemon, "gender")),
        "types": _value(_attribute(pokemon, "types", ())),
        "tera_type": _value(_attribute(pokemon, "tera_type")),
        "current_hp": _value(_attribute(pokemon, "current_hp")),
        "max_hp": _value(_attribute(pokemon, "max_hp")),
        "hp_fraction": _value(_attribute(pokemon, "current_hp_fraction")),
        "status": _value(_attribute(pokemon, "status")),
        "item": _value(_attribute(pokemon, "item")),
        "ability": _value(_attribute(pokemon, "ability")),
        "boosts": _value(_attribute(pokemon, "boosts", {})),
        "effects": _value(_attribute(pokemon, "effects", {})),
        "known_moves": sorted(
            str(move_id)
            for move_id in (_attribute(pokemon, "moves", {}) or {}).keys()
        ),
    }


def _team_snapshot(team: Any) -> list[dict[str, Any]]:
    if isinstance(team, Mapping):
        members = team.values()
    elif isinstance(team, (list, tuple)):
        members = team
    else:
        members = ()
    return [snapshot for member in members if (snapshot := _pokemon_snapshot(member))]


def _move_snapshot(move: Any) -> dict[str, Any]:
    return {
        "id": _value(_attribute(move, "id")),
        "current_pp": _value(_attribute(move, "current_pp")),
        "max_pp": _value(_attribute(move, "max_pp")),
        "base_power": _value(_attribute(move, "base_power")),
        "type": _value(_attribute(move, "type")),
        "disabled": bool(_attribute(move, "disabled", False)),
    }


def snapshot_battle(battle: Any) -> dict[str, Any]:
    """Return a stable, JSON-safe decision-time view without mutating poke-env."""

    return {
        "showdown_battle_tag": _value(_attribute(battle, "battle_tag")),
        "showdown_turn": _value(_attribute(battle, "turn")),
        "request_id": _value(
            _attribute(battle, "rqid", _attribute(battle, "_rqid"))
        ),
        "in_team_preview": bool(_attribute(battle, "in_team_preview", False)),
        "force_switch": _value(_attribute(battle, "force_switch", False)),
        "trapped": bool(_attribute(battle, "trapped", False)),
        "wait": _value(_attribute(battle, "wait")),
        "can_dynamax": bool(_attribute(battle, "can_dynamax", False)),
        "can_tera": bool(_attribute(battle, "can_tera", False)),
        "weather": _value(_attribute(battle, "weather", {})),
        "fields": _value(_attribute(battle, "fields", {})),
        "side_conditions": _value(_attribute(battle, "side_conditions", {})),
        "opponent_side_conditions": _value(
            _attribute(battle, "opponent_side_conditions", {})
        ),
        "active_pokemon": _pokemon_snapshot(
            _attribute(battle, "active_pokemon")
        ),
        "opponent_active_pokemon": _pokemon_snapshot(
            _attribute(battle, "opponent_active_pokemon")
        ),
        "available_moves": [
            _move_snapshot(move)
            for move in (_attribute(battle, "available_moves", ()) or ())
        ],
        "available_switches": [
            _pokemon_snapshot(pokemon)
            for pokemon in (_attribute(battle, "available_switches", ()) or ())
        ],
        "team": _team_snapshot(_attribute(battle, "team", {})),
        "opponent_team": _team_snapshot(
            _attribute(battle, "opponent_team", {})
        ),
    }


def _decision_kind(battle: Any, from_teampreview_request: bool) -> str:
    if from_teampreview_request or bool(
        _attribute(battle, "in_team_preview", False)
    ):
        return "team_preview"
    active = _attribute(battle, "active_pokemon")
    force_switch = _attribute(battle, "force_switch", False)
    if bool(force_switch) or bool(_attribute(active, "fainted", False)):
        return "forced_switch"
    if not (_attribute(battle, "available_moves", ()) or ()) and (
        _attribute(battle, "available_switches", ()) or ()
    ):
        return "forced_switch"
    return "turn_action"


def _safe_error(error: Exception) -> dict[str, str]:
    detail = str(error)
    detail = redact(detail)
    return {"type": type(error).__name__, "detail": detail}


def _is_battle_action(message: Any) -> bool:
    return isinstance(message, str) and message.startswith(
        ("/choose ", "/team ", "/forfeit")
    )


class TraceablePlayerMixin:
    """Mixin inserted ahead of the pinned upstream player without editing it."""

    _research_trace_sink: Any

    def _trace(self, method: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return getattr(self._research_trace_sink, method)(*args, **kwargs)
        except Exception as error:
            try:
                self._research_trace_sink.record_logging_error(
                    operation=f"player_hook.{method}",
                    error_type=type(error).__name__,
                )
            except Exception:
                pass
            warnings.warn(
                f"research trace hook {method} failed; gameplay continues "
                f"({type(error).__name__})",
                RuntimeWarning,
                stacklevel=2,
            )
            return None

    def _install_transport_trace(self) -> None:
        original_send = self.ps_client.send_message

        async def traced_send(message: str, room: str = "", message_2: Any = None):
            if not _is_battle_action(message):
                return await original_send(message, room, message_2)

            self._trace("record_decision_result", selected_action=message)
            wire_payload = "|".join(
                [room, message, str(message_2)] if message_2 else [room, message]
            )
            try:
                result = await original_send(message, room, message_2)
            except Exception as error:
                self._trace(
                    "record_wire_action",
                    action=message,
                    battle_tag=room or None,
                    send_status="failed",
                    wire_payload=wire_payload,
                    error=_safe_error(error),
                )
                raise
            self._trace(
                "record_wire_action",
                action=message,
                battle_tag=room or None,
                send_status="sent",
                wire_payload=wire_payload,
            )
            return result

        self.ps_client.send_message = traced_send

    async def _handle_battle_message(self, split_messages: list[list[str]]):
        protocol = "\n".join(
            "|".join(str(field) for field in split_message)
            for split_message in split_messages
        )
        official = getattr(self, "observation_backend", None) == "official-client-v1"
        if official:
            self._research_trace_sink.record_protocol(protocol, fatal=True)
        else:
            self._trace("record_protocol", protocol)
        if official:
            from ..observation.cursor import CursorMessages

            event_seq = self._research_trace_sink._event_seq
            lines = protocol.split("\n")
            split_messages = CursorMessages(
                split_messages,
                lambda index: self._received_protocol_row(event_seq, index, lines),
            )
        return await super()._handle_battle_message(split_messages)

    async def _handle_battle_request(
        self,
        battle: Any,
        from_teampreview_request: bool = False,
        maybe_default_order: bool = False,
    ):
        if (
            bool(_attribute(battle, "in_team_preview", False))
            and not from_teampreview_request
        ):
            return await super()._handle_battle_request(
                battle,
                from_teampreview_request=from_teampreview_request,
                maybe_default_order=maybe_default_order,
            )

        handle = self._trace(
            "begin_decision",
            showdown_turn=_attribute(battle, "turn"),
            decision_kind=_decision_kind(battle, from_teampreview_request),
            battle_state=snapshot_battle(battle),
        )
        try:
            return await super()._handle_battle_request(
                battle,
                from_teampreview_request=from_teampreview_request,
                maybe_default_order=maybe_default_order,
            )
        except Exception as error:
            self._trace(
                "record_decision_result",
                selected_action=None,
                success=False,
                validation={"action_selected": False},
                error=_safe_error(error),
            )
            raise
        finally:
            if handle is not None:
                self._trace("end_decision", handle)


def make_traced_player_class(base_class: type[Any]) -> type[Any]:
    """Create a parent-owned traced subclass around the pinned upstream class."""

    class ResearchTracedPlayer(TraceablePlayerMixin, base_class):
        def __init__(self, *args: Any, trace_sink: Any, **kwargs: Any) -> None:
            self._research_trace_sink = trace_sink
            super().__init__(*args, **kwargs)
            self._install_transport_trace()

    ResearchTracedPlayer.__name__ = f"ResearchTraced{base_class.__name__}"
    ResearchTracedPlayer.__qualname__ = ResearchTracedPlayer.__name__
    return ResearchTracedPlayer
