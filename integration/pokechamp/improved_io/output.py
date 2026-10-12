"""Exact text-action boundary for the fixed IO prompt."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ActionResponse:
    rationale: str
    action: dict


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_action(text, legal_actions, *, request_kind, can_tera, english_typography=False):
    if not isinstance(text, str) or "```" in text:
        raise ValueError("expected rationale and final-line JSON without Markdown fences")
    lines = text.strip().splitlines()
    if len(lines) < 2:
        raise ValueError("missing rationale")
    rationale = " ".join(line.strip() for line in lines[:-1]).strip()
    # Numbers may contain decimal points; only punctuation followed by whitespace/end
    # terminates a sentence. The fixed profile asks for short English prose.
    # D-030: English numeric ranges and quotes may use typographic punctuation.
    # Only the language check uses this view; raw evidence and exact JSON stay intact.
    language_view = (
        rationale.translate(str.maketrans("–—‘’“”", "--''\"\""))
        if english_typography
        else rationale
    )
    if (
        not re.search(r"[A-Za-z]", rationale)
        or re.search(r"[^\x00-\x7f]", language_view)
        or any(c in rationale for c in "{}[]")
        or not 1 <= len(re.findall(r"[.!?](?=\s|$)", rationale)) <= 2
        or rationale[-1:] not in ".!?"
    ):
        raise ValueError("expected one or two English rationale sentences and no extra JSON")
    action = json.loads(lines[-1], object_pairs_hook=unique_object)
    if not isinstance(action, dict) or len(action) != 1:
        raise ValueError("expected exactly one action")
    key, value = next(iter(action.items()))
    if key not in ("move", "switch", "terastallize") or not isinstance(value, str):
        raise ValueError("invalid action shape")
    if request_kind not in ("turn_action", "forced_switch"):
        raise ValueError("unsupported request kind")
    if request_kind == "forced_switch" and key != "switch":
        raise ValueError("forced replacement requires switch")
    if key == "terastallize" and can_tera is not True:
        raise ValueError("tera unavailable")
    if action not in legal_actions:
        raise ValueError("action outside exact request candidates")
    return ActionResponse(rationale, action)


def validate_exact_action(action, legal_actions, *, request_kind, can_tera):
    if not isinstance(action, dict) or len(action) != 1:
        raise ValueError("expected exactly one action")
    key, value = next(iter(action.items()))
    if key not in ("move", "switch", "terastallize") or not isinstance(value, str):
        raise ValueError("invalid action shape")
    if request_kind not in ("turn_action", "forced_switch"):
        raise ValueError("unsupported request kind")
    if request_kind == "forced_switch" and key != "switch":
        raise ValueError("forced replacement requires switch")
    if key == "terastallize" and can_tera is not True:
        raise ValueError("tera unavailable")
    if action not in legal_actions:
        raise ValueError("action outside exact request candidates")
    return action


def recover_action(text, legal_actions, *, request_kind, can_tera, error):
    """D-033 only: retain the failed model judgment and choose one sealed legal action."""
    if not legal_actions:
        raise ValueError("no legal candidates")
    kwargs = dict(request_kind=request_kind, can_tera=can_tera)
    # Invalid candidate metadata is a shared input defect, never repaired here.
    for action in legal_actions:
        validate_exact_action(action, legal_actions, **kwargs)
    extracted, reason = None, None
    decoder = json.JSONDecoder(object_pairs_hook=unique_object)
    objects, cursor = [], 0
    try:
        while cursor < len(text):
            if text[cursor] not in "{[":
                cursor += 1
                continue
            value, end = decoder.raw_decode(text, cursor)
            objects.append(value)
            cursor = end
        if len(objects) != 1:
            raise ValueError("expected one unique JSON action")
        extracted = objects[0]
        validate_exact_action(extracted, legal_actions, **kwargs)
        executed, origin = extracted, "extracted_action"
    except (ValueError, TypeError) as exc:
        reason = str(exc)
        executed, origin = legal_actions[0], "first_legal_fallback"
    return dict(raw_output_contract_valid=False, output_error=error,
                extracted_action=extracted, executed_action=executed,
                selection_source=origin, recovery_error=reason)
