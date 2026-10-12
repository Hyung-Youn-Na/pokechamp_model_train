"""EX-038 opt-in wire boundary; EP-034's frozen converter remains unchanged."""

from . import experiment_policy as policy
from .delivery import generate, parse_json, validate_delivery


def enabled(selection):
    if selection.get("observation_backend") == "official-client-v1" and "battle_delivery" in selection:
        if selection["battle_delivery"] not in ("B", "B2"):
            raise ValueError("unknown official battle delivery")
        return selection["battle_delivery"] == "B2"
    return policy.selected(selection).get("experiment_policy") in (policy.B2, policy.LEAD)


def build(full, version="v1.2.0"):
    if version == "v1.4.0":
        from ..observation.delivery import build as official_build

        return official_build(full, kind="b2")
    if version not in ("v1.2.0", "v1.3.0"):
        raise ValueError("unsupported B2 transmission version")
    if version == "v1.3.0":
        from ..effects.delivery import build as enriched

        return enriched(full, kind="b2")
    return generate(full, "B2", battle_format="gen9ou")


def validate(full, delivery, system, user, version="v1.2.0"):
    if version == "v1.4.0":
        from ..observation.delivery import validate as official_validate

        return official_validate(full, delivery, system, user, kind="b2")
    if version not in ("v1.2.0", "v1.3.0"):
        raise ValueError("unsupported B2 transmission version")
    if version == "v1.3.0":
        from ..effects.delivery import validate as enriched

        return enriched(full, delivery, system, user, kind="b2")
    if delivery is None or delivery.candidate_version != "B2":
        raise ValueError("B2 delivery required")
    validate_delivery(full, delivery, battle_format="gen9ou")
    if system != delivery.system_prompt or user != delivery.user_json:
        raise ValueError("actual B2 wire strings mismatch")
    return parse_json(delivery.source_link_json)


def original_for_call(event, snapshots):
    """Load and verify an original separately from the actual transmitted input."""
    request = event["request"]
    link = request.get("delivery_identity")
    if link is None:
        if ((request.get("battle_prompt_identity") or {}).get("version") == "v1.3.0"
                or (request.get("team_preview_prompt_identity") or {}).get("version") in ("v1.1.0", "v1.2.0")):
            raise ValueError("effect call missing original delivery linkage")
        if request.get("call_role") == "team_preview":
            return parse_json(event["user_prompt"])
        if enabled(request):
            raise ValueError("B2 call missing delivery identity")
        return parse_json(event["user_prompt"])
    official = link.get("format_version") == "official-observation-delivery-v1"
    enriched = link.get("format_version") == "effect-delivery-v1"
    if not enabled(request) and not enriched and not official:
        raise ValueError("unexpected delivery identity")
    snapshot = snapshots[request["input_snapshot_event_seq"]]
    full = snapshot["original_input"]
    if (snapshot["decision_seq"] != event["decision_seq"]
            or snapshot["event_seq"] >= event["event_seq"]
            or snapshot["delivery_identity"] != link):
        raise ValueError("B2 snapshot linkage mismatch")
    if official:
        from ..observation.delivery import build as official_build
        from ..observation.delivery import validate as official_validate
        from .battle_prompts import identity as battle_identity

        kind = "b2" if enabled(request) else "battle"
        if (request.get("call_role") != "self_action" or link["kind"] != kind
                or request.get("observation_backend") != "official-client-v1"
                or request.get("identity") != full["identity"]
                or request.get("battle_prompt_identity") != battle_identity("v1.4.0")):
            raise ValueError("official request identity mismatch")
        delivery = official_build(full, kind=kind)
        expected = official_validate(full, delivery, event["system_prompt"], event["user_prompt"], kind=kind)
        if link != expected:
            raise ValueError("official original linkage mismatch")
        return full
    if link.get("format_version") == "lead-components-v2":
        from ..lead_rules import build as lead_build
        from ..lead_rules import validate as lead_validate

        selected = request.get("team_preview_prompt_identity")
        if (request.get("call_role") != "team_preview" or link.get("kind") != "lead"
                or request.get("identity") != full["identity"] or selected != link["prompt_identity"]):
            raise ValueError("lead component request linkage mismatch")
        delivery = lead_build(full, selected)
        expected = lead_validate(full, delivery, event["system_prompt"], event["user_prompt"], selected)
        if link != expected:
            raise ValueError("lead component original linkage mismatch")
        return full
    if enriched:
        from ..effects.delivery import build as effect_build
        from ..effects.delivery import validate as effect_validate
        from .battle_prompts import identity as battle_identity

        preview = request.get("call_role") == "team_preview"
        expected_kind = "lead" if preview else "b2" if enabled(request) else "battle"
        selected = request.get("team_preview_prompt_identity") if preview else request.get(
            "battle_prompt_identity")
        if (link["kind"] != expected_kind or request.get("identity") != full["identity"]
                or selected != (link["prompt_identity"] if preview else battle_identity("v1.3.0"))):
            raise ValueError("effect request role/version/identity linkage mismatch")
        delivery = effect_build(full, kind=link["kind"])
        effect_validate(full, delivery, event["system_prompt"], event["user_prompt"],
                        kind=link["kind"])
        if link != parse_json(delivery.source_link_json):
            raise ValueError("effect original linkage mismatch")
        return full
    delivery = build(full)
    if link != parse_json(delivery.source_link_json):
        raise ValueError("B2 original linkage mismatch")
    validate(full, delivery, event["system_prompt"], event["user_prompt"])
    return full
