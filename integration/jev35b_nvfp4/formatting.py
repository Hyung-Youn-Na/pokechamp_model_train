"""Lossless official text Choice payloads; A-P slots retain original candidate IDs."""
from integration.jev27b.formatting import (
    FormattedRequest, InputTooLong, InputValidationError, MAX_OPTIONS, MAX_TOKENS,
    answer_from_probabilities, format_request, tokenize_request,
)

FORMAT_VERSION = 'jev35b-nvfp4-official-choice-v1'


def choice_request(payload):
    formatted = format_request(payload)
    question = payload['questions'][formatted.question_name]['instructions']
    if not isinstance(question, str):
        import json
        question = json.dumps(question, ensure_ascii=False, allow_nan=False)
    # Text/dict state uses the official _parts renderer. List state has multimodal
    # semantics there; stringify it as text to preserve our complete JSON state.
    state = payload['state']
    if isinstance(state, list):
        import json
        state = json.dumps(state, ensure_ascii=False, allow_nan=False)
    return dict(kind='choice', state=state, question=question,
                options=list(formatted.option_texts), strategy='single', thinking='off',
                system2_only=False, return_reasoning=False)


def mapped_response(payload, response):
    formatted = format_request(payload)
    if response.get('options') != list(formatted.option_texts):
        raise InputValidationError('official options changed order or content')
    if (response.get('kind') != 'choice' or response.get('model') != 'autotrust/JEV-35B-NVFP4'
            or response.get('num_model_requests') != 1 or response.get('thinking', {}).get('used', False)):
        raise InputValidationError('unexpected official System 1 response identity/count')
    answer = answer_from_probabilities(formatted, response['probabilities'])
    index = response.get('choice_index')
    if (type(index) is not int or not 0 <= index < len(formatted.candidate_ids)
            or formatted.candidate_ids[index] != answer['choice']
            or response.get('choice') != formatted.option_texts[index]):
        raise InputValidationError('official choice index disagrees with probabilities/options')
    usage = response['usage']
    if (type(usage.get('prompt_tokens')) is not int or not 1 <= usage['prompt_tokens'] <= MAX_TOKENS
            or usage.get('completion_tokens') != 1):
        raise InputValidationError('official full-input/readout usage mismatch')
    return dict(model=response['model'], answers={formatted.question_name: answer},
                usage=dict(input_tokens=usage['prompt_tokens'], output_tokens=usage['completion_tokens']),
                official_response=response)
