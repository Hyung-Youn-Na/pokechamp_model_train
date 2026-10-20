"""Lossless official Tacit first-pass and thinking prompts (pinned revision)."""
from dataclasses import dataclass
import hashlib
import json
from integration.jev27b.formatting import (
    FormattedRequest as BaseRequest, InputTooLong, InputValidationError,
    MAX_OPTIONS, MAX_TOKENS, format_request as validate_request, _text,
)

FORMAT_VERSION = 'tacit9b-official-always-thinking-v1'
ONE_FORWARD_SYSTEM = ('You are a decision function. You will be given a state and one question. '
                      'Reply with the answer label only: no words, no punctuation, no explanation.')
COT_SYSTEM = 'You are a careful assistant that answers questions about a given context.'


@dataclass(frozen=True)
class FormattedRequest(BaseRequest):
    thinking_prompt: str


def choice_request(payload):
    original = validate_request(payload)
    return dict(state=_text(payload['state']),
                question=_text(payload['questions'][original.question_name]['instructions']),
                options=list(original.option_texts), kind='choice')


def format_request(payload):
    original = validate_request(payload)
    request = choice_request(payload)
    state, question, options = request['state'], request['question'], request['options']
    lines = [f'{chr(65 + j)}. {o}' for j, o in enumerate(options)]
    first = '\n'.join(['State:', state if state else '(empty)', '', 'Question: ' + question,
                        'Options:', *lines, 'Answer with the letter only.'])
    thinking = '\n'.join([state.strip(), '', 'Question: ' + question.strip(), '', 'Options:',
        *lines, '', 'Think through the question, then give your final answer on the last line in '
        'exactly this form:', 'Answer: <option letter>'])
    return FormattedRequest(first, original.question_name, original.candidate_ids,
                            original.option_texts, thinking)


def render(tokenizer, system, user, thinking):
    msgs = [dict(role='system', content=system), dict(role='user', content=user)]
    text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=thinking)
    if text.endswith('<|start|>assistant'):
        text += '<|channel|>final<|message|>'
    return text


def tokenize_request(tokenizer, formatted, max_tokens=MAX_TOKENS):
    if type(max_tokens) is not int or not 1 <= max_tokens <= MAX_TOKENS:
        raise InputValidationError('invalid token limit')
    prompts = [render(tokenizer, ONE_FORWARD_SYSTEM, formatted.prompt, False),
               render(tokenizer, COT_SYSTEM, formatted.thinking_prompt, True)]
    encoded = []
    for prompt in prompts:
        ids = tokenizer.encode(prompt, add_special_tokens=False)
        if not ids or any(type(i) is not int or i < 0 for i in ids):
            raise InputValidationError('expected nonempty token IDs')
        if len(ids) > max_tokens:
            raise InputTooLong(len(ids), max_tokens)
        encoded.append(ids)
    return dict(input_ids=encoded[0], attention_mask=[1] * len(encoded[0]),
                thinking_input_ids=encoded[1], first_prompt=prompts[0], thinking_prompt=prompts[1])


def payload_seed(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def mapped_answer(formatted, official):
    index = official['index']
    if type(index) is not int or not 0 <= index < len(formatted.candidate_ids):
        raise InputValidationError('official index outside candidates')
    if official['answer'] != formatted.option_texts[index]:
        raise InputValidationError('official option/index mismatch')
    probs = {key: official['probs'].get(option)
             for key, option in zip(formatted.candidate_ids, formatted.option_texts)}
    return dict(type='choice', choice=formatted.candidate_ids[index], probabilities=probs,
                confidence=probs[formatted.candidate_ids[index]])
