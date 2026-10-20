"""Lossless numeric Choice prompt and the official text-only processor path."""
from integration.jev27b.formatting import (
    FormattedRequest, InputTooLong, InputValidationError, MAX_OPTIONS, MAX_TOKENS,
    format_request as validate_request, _text,
)

FORMAT_VERSION = 'jev-omni-official-text-v1'


def choice_request(payload):
    original = validate_request(payload)
    return dict(state=_text(payload['state']),
                question=_text(payload['questions'][original.question_name]['instructions']),
                options=list(original.option_texts))


def format_request(payload):
    original = validate_request(payload)
    request = choice_request(payload)
    options = request['options']
    choices = '\n'.join(f'{i + 1}. {value}' for i, value in enumerate(options))
    prompt = (f"{request['state']}\n\n---\n\nQUESTION: {request['question']}\n\nOPTIONS:\n{choices}\n\n"
              f"Reply with only the number of the correct option (1-{len(options)}).\n"
              'Output a single number and nothing else.')
    return FormattedRequest(prompt, original.question_name, original.candidate_ids, original.option_texts)


def messages(formatted):
    return [{'role': 'user', 'content': [{'type': 'text', 'text': formatted.prompt}]}]


def tokenize_request(processor, formatted, max_tokens=MAX_TOKENS):
    if type(max_tokens) is not int or not 1 <= max_tokens <= MAX_TOKENS:
        raise InputValidationError('invalid token limit')
    inputs = processor.apply_chat_template(messages(formatted), add_generation_prompt=True,
        tokenize=True, return_dict=True, return_tensors='pt', enable_thinking=False)
    ids = inputs['input_ids']
    if ids.ndim != 2 or ids.shape[0] != 1 or ids.shape[1] < 1:
        raise InputValidationError('expected one nonempty unpadded text sequence')
    if ids.shape[1] > max_tokens:
        raise InputTooLong(ids.shape[1], max_tokens)
    return {k: v[0].tolist() for k, v in inputs.items()}


def mapped_response(payload, official, input_tokens):
    formatted = format_request(payload)
    index = official.get('prediction_index')
    if (type(index) is not int or not 0 <= index < len(formatted.candidate_ids)
            or official.get('prediction') != formatted.option_texts[index]):
        raise InputValidationError('official prediction index/option mismatch')
    # Auxiliary scores do not override an executable official choice (C-046).
    raw = official.get('probabilities', {})
    if not isinstance(raw, dict):
        raw = {}
    probabilities = {key: raw.get(option) for key, option in zip(formatted.candidate_ids, formatted.option_texts)}
    answer = dict(type='choice', choice=formatted.candidate_ids[index],
                  probabilities=probabilities, confidence=official.get('confidence'))
    from .config import MODEL_ID
    return dict(model=MODEL_ID, answers={formatted.question_name: answer},
                usage=dict(input_tokens=input_tokens, output_tokens=0), official_response=official)
