"""Lossless Choice JSON inside the pinned MiniCPM chat/question/answer template.

The official server flattens JSON, strips instructions, sanitizes user strings and
trims long states. EX-091 preserves the JSON values and exact instructions instead.
User fragments are encoded as ordinary text, so literal control-token spellings
remain data without changing their decoded text. This is an explicit adaptation,
not a reproduction of the default server's preprocessing.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import string
from typing import Mapping

from integration.jev27b.formatting import InputTooLong, InputValidationError, answer_from_probabilities
from .config import MAX_OPTIONS, MAX_TOKENS

FORMAT_VERSION = 'minicpm5-chat-full-json-choice-v1'
CHAT_HEAD = '<s><|im_start|>user\nContext:\n'
CHAT_TAIL = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\nAnswer: ('
LABELS = tuple(string.ascii_uppercase[:MAX_OPTIONS])


def json_text(value):
    try:
        # Insertion order, null/empty containers, Unicode and embedded newlines all
        # survive a JSON round trip. No flattening or string coercion is allowed.
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise InputValidationError('input is not finite JSON') from error


@dataclass(frozen=True)
class FormattedRequest:
    question_name: str
    candidate_ids: tuple[str, ...]
    option_texts: tuple[str, ...]
    state_text: str
    instruction_text: str

    @property
    def user_parts(self):
        return (self.state_text, '\n\nQuestion: ' + self.instruction_text + '\nOptions:',
                *(f'\n({LABELS[i]}) {option}' for i, option in enumerate(self.option_texts)))

    @property
    def prompt(self):
        return CHAT_HEAD + ''.join(self.user_parts) + CHAT_TAIL

    @property
    def prompt_sha256(self):
        return hashlib.sha256(self.prompt.encode('utf-8')).hexdigest()


def format_request(payload, *, allow_single=False):
    if not isinstance(payload, Mapping) or 'state' not in payload:
        raise InputValidationError('payload requires state and exactly one Choice question')
    questions = payload.get('questions')
    if not isinstance(questions, dict) or len(questions) != 1:
        raise InputValidationError('exactly one Choice question is required')
    name, question = next(iter(questions.items()))
    if not isinstance(name, str) or not name or not isinstance(question, dict):
        raise InputValidationError('invalid question name or object')
    if question.get('type') != 'choice' or 'instructions' not in question:
        raise InputValidationError('only Choice questions with instructions are supported')
    criteria = question.get('criteria')
    minimum = 1 if allow_single else 2
    if not isinstance(criteria, dict) or not minimum <= len(criteria) <= MAX_OPTIONS:
        raise InputValidationError('Choice needs 2..16 candidates; single candidates must bypass inference')
    if any(not isinstance(key, str) or not key or not isinstance(value, dict)
           for key, value in criteria.items()):
        raise InputValidationError('candidate IDs must be nonempty strings and candidates must be objects')
    instructions = question['instructions']
    return FormattedRequest(name, tuple(criteria), tuple(json_text({k: v}) for k, v in criteria.items()),
        json_text(payload['state']), instructions if isinstance(instructions, str) else json_text(instructions))


@lru_cache(maxsize=4)
def decision_metadata(tokenizer):
    """Reproduce the official label discovery and verify the frozen chat wrappers."""
    prefix = tokenizer.encode('Answer: (', add_special_tokens=False)
    labels, ids = [], []
    candidates = list(string.ascii_uppercase) + [a + b for a in string.ascii_uppercase
                                                for b in string.ascii_uppercase]
    for label in candidates:
        encoded = tokenizer.encode(f'Answer: ({label}', add_special_tokens=False)
        if len(encoded) == len(prefix) + 1 and encoded[:-1] == prefix and encoded[-1] not in ids:
            labels.append(label)
            ids.append(encoded[-1])
            if len(ids) == 255:
                break
    sentinel = '@@SYSTEMONE_USER_CONTENT@@'
    rendered = tokenizer.apply_chat_template([{'role': 'user', 'content': sentinel}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False)
    head, tail = rendered.split(sentinel)
    for opened, closed in (('<think>\n', '</think>\n\n'), ('<think>', '</think>\n\n')):
        if tail.endswith(opened):
            tail += closed
    if (head + 'Context:\n' != CHAT_HEAD or tail + 'Answer: (' != CHAT_TAIL
            or len(ids) != 255 or tuple(labels[:MAX_OPTIONS]) != LABELS
            or ids[:MAX_OPTIONS] != list(range(54, 70))):
        raise InputValidationError('pinned MiniCPM chat wrappers or head label/token mapping differs')
    return dict(label_names=labels, label_ids=ids,
                chat_head_ids=tokenizer.encode(CHAT_HEAD, add_special_tokens=False),
                chat_tail_ids=tokenizer.encode(CHAT_TAIL, add_special_tokens=False))


def tokenize_request(tokenizer, formatted, max_tokens=MAX_TOKENS):
    if type(max_tokens) is not int or not 1 <= max_tokens <= MAX_TOKENS:
        raise InputValidationError('token limit must be a positive integer no larger than 32768')
    meta = decision_metadata(tokenizer)
    ids = list(meta['chat_head_ids'])
    for part in formatted.user_parts:
        ids.extend(tokenizer.encode(part, add_special_tokens=False, split_special_tokens=True))
    ids.extend(meta['chat_tail_ids'])
    if not ids or any(type(value) is not int or value < 0 for value in ids):
        raise InputValidationError('tokenizer did not return one nonempty list of token IDs')
    if len(ids) > max_tokens:
        raise InputTooLong(len(ids), max_tokens)
    # One unpadded causal row; no state/branch sub-limit and no truncation.
    return dict(input_ids=ids, attention_mask=[1] * len(ids))


def verify_lossless(payload, formatted, tokenizer, encoded):
    """Decode actual token IDs and recover every original JSON value and its order."""
    question = payload['questions'][formatted.question_name]
    expected_instructions = question['instructions']
    if not isinstance(expected_instructions, str):
        if json.loads(formatted.instruction_text) != expected_instructions:
            raise InputValidationError('instructions changed during JSON rendering')
    elif formatted.instruction_text != expected_instructions:
        raise InputValidationError('instructions changed during rendering')
    restored = {}
    for option in formatted.option_texts:
        item = json.loads(option)
        if not isinstance(item, dict) or len(item) != 1:
            raise InputValidationError('candidate object was not preserved')
        restored.update(item)
    if (json.loads(formatted.state_text) != payload['state'] or restored != question['criteria']
            or list(restored) != list(question['criteria'])
            or tuple(restored) != formatted.candidate_ids):
        raise InputValidationError('state/candidate content or order changed')
    decoded = tokenizer.decode(encoded['input_ids'], skip_special_tokens=False,
                               clean_up_tokenization_spaces=False)
    if decoded != formatted.prompt:
        raise InputValidationError('actual token IDs do not losslessly decode to the full prompt')
    return True
