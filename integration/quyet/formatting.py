"""Pinned official prompt v1 with strict prechecks; no truncated input is inferred."""
from dataclasses import dataclass
import hashlib
import json

from .config import MAX_TOKENS, MAX_OPTIONS


class InputTooLong(ValueError):
    pass


@dataclass(frozen=True)
class Prepared:
    prompt: str
    token_ids: list[int]
    state_tokens: int
    candidate_ids: tuple[str, ...]
    question_name: str

    def evidence(self):
        return dict(prompt=self.prompt, prompt_sha256=hashlib.sha256(self.prompt.encode()).hexdigest(),
                    input_tokens=len(self.token_ids), state_tokens=self.state_tokens,
                    candidate_ids=list(self.candidate_ids), question_name=self.question_name,
                    prompt_version=1, strict=True, truncated=False)


def prepare(tokenizer, payload, *, strict=True):
    from quyet.base import check_state
    from quyet.questions import parse_questions
    from quyet.llm.prompt import serialize_state, build_prompt
    if strict is not True:
        raise ValueError('EX-084 requires strict=True')
    if set(payload) - {'model', 'state', 'questions'}:
        raise ValueError('unexpected request fields')
    # Reject NaN or unserializable values before the official permissive describe().
    json.dumps(payload, allow_nan=False)
    check_state(payload['state'])
    decisions = parse_questions(payload['questions'])
    if len(decisions) != 1:
        raise ValueError('one stage, one Choice question required')
    name, decision = next(iter(decisions.items()))
    if decision.type != 'choice' or not 2 <= len(decision.labels) <= MAX_OPTIONS:
        raise ValueError('a model stage needs 2..10 Choice candidates')
    state_text = serialize_state(payload['state'], compact=False)
    state_ids = tokenizer(state_text, add_special_tokens=False, truncation=False)['input_ids']
    if len(state_ids) > MAX_TOKENS:
        raise InputTooLong(f'state tokens {len(state_ids)} exceed {MAX_TOKENS}; no truncation')
    prompt = build_prompt(tokenizer, state_text, decision, version=1)
    token_ids = tokenizer(prompt, add_special_tokens=False, truncation=False)['input_ids']
    if len(token_ids) > MAX_TOKENS:
        raise InputTooLong(f'prompt tokens {len(token_ids)} exceed {MAX_TOKENS}; no truncation')
    return Prepared(prompt, token_ids, len(state_ids), decision.labels, name)
