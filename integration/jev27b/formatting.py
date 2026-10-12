"""Lossless EX-082 adaptation to the pinned JEV-27B bare-v1 decision prompt."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

MAX_TOKENS = 32768
MAX_OPTIONS = 16
FORMAT_VERSION = "jev27b-bare-v1-full-criteria-v1"


class InputValidationError(ValueError):
    """An input cannot be represented by the frozen Choice-only interface."""


class InputTooLong(InputValidationError):
    def __init__(self, token_count: int, max_tokens: int):
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(f"input has {token_count} tokens; untruncated limit is {max_tokens}")


@dataclass(frozen=True)
class FormattedRequest:
    prompt: str
    question_name: str
    candidate_ids: tuple[str, ...]
    option_texts: tuple[str, ...]

    @property
    def prompt_sha256(self) -> str:
        return hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, (dict, list)):
        raise InputValidationError("state and instructions must be a string, object, or array")
    try:
        # This is the official serve_decide._parts dictionary rendering. Keep insertion
        # order and full JSON values; escaping embedded newlines keeps each option one line.
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise InputValidationError("input is not finite JSON") from error


def format_request(payload: Mapping[str, Any]) -> FormattedRequest:
    """Preserve state/instructions and every ordered candidate ID plus its entire object.

    The surrounding template is the revision-pinned README's Transformers bare-v1
    formatter. Each original ``criteria`` entry is one JSON option. The A-P labels
    are positional readout slots; original IDs remain the executable action identity.
    """
    if not isinstance(payload, Mapping) or "state" not in payload:
        raise InputValidationError("payload requires state and exactly one choice question")
    questions = payload.get("questions")
    if not isinstance(questions, dict) or len(questions) != 1:
        raise InputValidationError("exactly one choice question is required")
    name, question = next(iter(questions.items()))
    if not isinstance(name, str) or not name or not isinstance(question, dict):
        raise InputValidationError("invalid question name or object")
    if question.get("type") != "choice" or "instructions" not in question:
        raise InputValidationError("only choice questions with instructions are supported")
    criteria = question.get("criteria")
    if not isinstance(criteria, dict) or not 2 <= len(criteria) <= MAX_OPTIONS:
        raise InputValidationError("Choice needs 2..16 candidates; single candidates must bypass inference")
    if any(not isinstance(key, str) or not key or not isinstance(value, dict)
           for key, value in criteria.items()):
        raise InputValidationError("candidate IDs must be nonempty strings and candidates must be objects")
    state = _text(payload["state"])
    instructions = _text(question["instructions"])
    options = tuple(_text({key: value}) for key, value in criteria.items())
    lines = [f"{'ABCDEFGHIJKLMNOP'[i]}) {option}" for i, option in enumerate(options)]
    prompt = (f"[kind] choice\n[state] {state}\n[question] {instructions}\n[options]\n"
              + "\n".join(lines) + "\n[decision]:")
    return FormattedRequest(prompt, name, tuple(criteria), options)


def tokenize_request(tokenizer: Any, formatted: FormattedRequest,
                     max_tokens: int = MAX_TOKENS) -> dict[str, list[int]]:
    """Tokenize the whole prompt on CPU, then refuse overlong inputs before a GPU call."""
    if type(max_tokens) is not int or not 1 <= max_tokens <= MAX_TOKENS:
        raise InputValidationError("token limit must be a positive integer no larger than 32768")
    encoded = tokenizer(formatted.prompt, add_special_tokens=False, truncation=False,
                        padding=False, return_attention_mask=True)
    ids, mask = encoded.get("input_ids"), encoded.get("attention_mask")
    if not isinstance(ids, list) or not ids or any(type(i) is not int or i < 0 for i in ids):
        raise InputValidationError("tokenizer must return one nonempty list of token IDs")
    if len(ids) > max_tokens:
        raise InputTooLong(len(ids), max_tokens)
    if not isinstance(mask, list) or len(mask) != len(ids) or any(i != 1 for i in mask):
        raise InputValidationError("unpadded tokenizer attention mask must contain exactly one per token")
    return {"input_ids": ids, "attention_mask": mask}


def answer_from_probabilities(formatted: FormattedRequest,
                              probabilities: Sequence[float]) -> dict[str, Any]:
    """Map native head slots to original candidate IDs, retaining first-slot ties."""
    values = list(probabilities)
    if len(values) != len(formatted.candidate_ids):
        raise InputValidationError("probability and candidate counts differ")
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise InputValidationError("model probabilities must be finite and in [0, 1]")
    if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-5):
        raise InputValidationError("native softmax probabilities do not sum to one")
    index = max(range(len(values)), key=values.__getitem__)
    return {"type": "choice", "choice": formatted.candidate_ids[index],
            "probabilities": dict(zip(formatted.candidate_ids, values)), "confidence": values[index]}
