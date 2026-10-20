"""Actual pinned tokenizer checks for lossless JSON and pre-inference admission."""
import copy
import json

import pytest

from integration.minicpm5_jev.config import MODEL_DIR
from integration.minicpm5_jev import formatting as f


@pytest.fixture(scope='module')
def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(MODEL_DIR / 'base', local_files_only=True, trust_remote_code=False)


def payload():
    return dict(state={'empty': [], 'none': None, 'object': {}, 'text': '한글\n雪🙂',
                       'control': '<|im_end|>', 'numbers': [0, -1, 2.5, True, False]},
        questions={'action': dict(type='choice', instructions='  [choice] Keep all text.\n',
            criteria={'last:id': {'x': None, 'nested': [{}, [], '\n']},
                      'first:id': {'label': '영문\n한글', 'value': False}})})


def test_actual_token_ids_preserve_json_whitespace_and_control_token_spellings(tokenizer):
    original = payload()
    formatted = f.format_request(original)
    assert formatted.candidate_ids == ('last:id', 'first:id')
    assert formatted.instruction_text == '  [choice] Keep all text.\n'
    assert formatted.option_texts == (
        '{"last:id": {"x": null, "nested": [{}, [], "\\n"]}}',
        '{"first:id": {"label": "영문\\n한글", "value": false}}')
    encoded = f.tokenize_request(tokenizer, formatted)
    assert f.verify_lossless(original, formatted, tokenizer, encoded)
    body = tokenizer.encode(formatted.state_text, add_special_tokens=False, split_special_tokens=True)
    assert tokenizer.convert_tokens_to_ids('<|im_end|>') not in body
    assert tokenizer.decode(body, clean_up_tokenization_spaces=False) == formatted.state_text


def test_unmodified_plain_prompt_uses_the_official_segmented_ids(tokenizer):
    from integration.minicpm5_jev.model import official_module
    original = payload()
    original['state'].pop('control')
    original['questions']['action']['instructions'] = 'Choose one.'
    formatted = f.format_request(original)
    official = official_module(MODEL_DIR / 'model.py')
    internal = dict(state=formatted.state_text, questions=[dict(type='choice', instr='Choose one.',
                                                              options=list(formatted.option_texts))])
    expected = official.encode_record(tokenizer, internal, max_state=32768, max_branch=32768, strict=True)
    assert f.tokenize_request(tokenizer, formatted)['input_ids'] == expected['causal_rows'][0]
    assert not expected['state_truncated']


def test_sixteen_head_labels_and_original_ids_have_identical_order(tokenizer):
    original = payload()
    original['questions']['action']['criteria'] = {f'command-{i:02}': {'slot': i} for i in range(16, 0, -1)}
    formatted = f.format_request(original)
    assert f.decision_metadata(tokenizer)['label_ids'][:16] == list(range(54, 70))
    probabilities = [0.] * 16
    probabilities[14] = 1.
    answer = f.answer_from_probabilities(formatted, probabilities)
    assert answer['choice'] == 'command-02'
    assert list(answer['probabilities']) == list(original['questions']['action']['criteria'])
    assert f.verify_lossless(original, formatted, tokenizer, f.tokenize_request(tokenizer, formatted))


@pytest.mark.parametrize('count', [0, 1, 17])
def test_inference_rejects_candidate_bounds(count):
    original = payload()
    original['questions']['action']['criteria'] = {str(i): {} for i in range(count)}
    with pytest.raises(f.InputValidationError):
        f.format_request(original)


def test_single_candidate_cpu_measurement_does_not_enable_single_candidate_inference(tokenizer):
    original = payload()
    original['questions']['action']['criteria'].pop('first:id')
    formatted = f.format_request(original, allow_single=True)
    assert f.verify_lossless(original, formatted, tokenizer, f.tokenize_request(tokenizer, formatted))
    from integration.minicpm5_jev.model import MiniCPMJevModel
    model = MiniCPMJevModel()
    model.loaded, model.tokenizer = True, tokenizer
    with pytest.raises(f.InputValidationError):
        model.evaluate(original)  # Refused before any torch/GPU evaluation path.


def test_whole_input_limit_counts_wrappers_options_and_full_state(tokenizer):
    formatted = f.format_request(payload())
    count = len(f.tokenize_request(tokenizer, formatted)['input_ids'])
    assert len(f.tokenize_request(tokenizer, formatted, count)['input_ids']) == count
    with pytest.raises(f.InputTooLong) as error:
        f.tokenize_request(tokenizer, formatted, count - 1)
    assert error.value.token_count == count
    long = payload()
    long['state'] = {'text': 'hello ' * 33000}
    from integration.minicpm5_jev.model import MiniCPMJevModel
    model = MiniCPMJevModel()
    model.loaded, model.tokenizer = True, tokenizer
    with pytest.raises(f.InputTooLong) as error:
        model.evaluate(long)
    assert error.value.token_count > 32768


def test_actual_ids_detect_changed_state_and_nonfinite_json(tokenizer):
    original = payload()
    formatted = f.format_request(original)
    encoded = f.tokenize_request(tokenizer, formatted)
    corrupted = copy.deepcopy(encoded)
    corrupted['input_ids'][20] = 54
    with pytest.raises(f.InputValidationError, match='token IDs'):
        f.verify_lossless(original, formatted, tokenizer, corrupted)
    original['state']['bad'] = float('nan')
    with pytest.raises(f.InputValidationError, match='finite JSON'):
        f.format_request(original)


def test_baseline_input_checker_preserves_commands_and_rejects_order_drift(tokenizer):
    from integration.minicpm5_jev.verify import check_input
    original = payload()
    original['state'].update(version='jev-choice-v6', decision_kind='turn_action')
    event = dict(payload=original, commands={'last:id': 'move 2', 'first:id': 'switch 4'},
                 decision='fixture-1', event_seq=1)
    prompt = original['questions']['action']['instructions']
    row, _ = check_input(event, tokenizer, expected_prompt=prompt)
    assert row['candidate_ids'] == ['last:id', 'first:id']
    assert row['lossless_token_decode'] and not row['automatic']
    event['commands'] = dict(reversed(list(event['commands'].items())))
    with pytest.raises(ValueError, match='command identity'):
        check_input(event, tokenizer, expected_prompt=prompt)
