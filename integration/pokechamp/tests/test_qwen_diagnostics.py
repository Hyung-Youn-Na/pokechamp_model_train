"""Public input boundaries and observable prediction contracts, without a model."""
import copy
from contextlib import nullcontext
import hashlib
import json
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from integration.pokechamp import decision_instructions as instructions
from integration.pokechamp import qwen_diagnostics as diagnostic
from integration.pokechamp import qwen_value as value


@pytest.fixture
def body():
    original = json.loads((value.TRAINING / 'data/inputs.jsonl').read_text().splitlines()[0])
    return dict(observation=copy.deepcopy(original['observation']),
                actions=copy.deepcopy(original['actions']), action_id=original['actions'][0]['action_id'],
                scenario={'opponent_lead': 'not_identified', 'sets': 'public_recommended_assumptions'})


@pytest.fixture
def prediction(body):
    return dict(action_id=body['action_id'], scenario='Opponent stays and uses Pyro Ball; neither side uses Tera.',
        order='Self first under the supplied effective Speed assumption.',
        post_state={'target_survives': True, 'self_defense_stage_after_move': 0},
        damage_applicability={'supplied_incoming_damage_still_applicable': False,
                             'updated_incoming_damage': 'not_provided',
                             'reason': 'Close Combat changed the defensive boost.'},
        survival='unknown', ko={'status': False, 'conditions': ['Target survives Close Combat.']})


class Tokenizer:
    def __init__(self, length=100):
        self.length = length
        self.messages = None

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs == dict(tokenize=False, add_generation_prompt=True, enable_thinking=False)
        self.messages = messages
        return json.dumps(messages, ensure_ascii=False)

    def encode(self, prompt, **kwargs):
        assert kwargs == dict(add_special_tokens=False)
        return list(range(self.length))


@pytest.mark.parametrize('kind', ['lead', 'turn_action', 'forced_switch'])
def test_selected_procedure_and_original_contract_are_preserved(kind):
    original = (instructions.PROMPTS / 'jev-choice-v4.txt').read_text()
    actual = instructions.compose(original, kind)
    assert actual.endswith(original)
    assert actual.count(original) == 1
    assert actual.index('CURRENT DECISION PROCEDURE: ' + kind.upper().replace('_', ' ')) == 0
    assert actual.count('SHARED INTERPRETATION FOR THIS DECISION') == 1
    for other in instructions.PROCEDURES:
        assert actual.count('CURRENT DECISION PROCEDURE: ' + other.upper().replace('_', ' ')) == int(other == kind)
    assert 'describe those calculations\' limits' in actual


def test_decision_specific_sequence_and_uncertainty():
    original = 'OUTPUT CONTRACT\nKeep legal IDs.\n'
    lead = instructions.compose(original, 'lead')
    turn = instructions.compose(original, 'turn_action')
    forced = instructions.compose(original, 'forced_switch')
    assert 'No current active matchup' in lead
    assert 'voluntary switch replaces your move' in turn
    assert 'no matching recalculation' in turn or 'absent a matching recalculation' in turn
    assert 'same move without new Tera' in turn
    assert 'Ruination removes half the current HP' in turn
    assert 'not an unconditional priority' in turn
    assert 'Do not apply an already completed attack again' in forced
    assert 'not every replacement starts a new turn' in forced
    with pytest.raises(ValueError, match='unsupported decision'):
        instructions.compose(original, 'pivot')
    with pytest.raises(ValueError, match='unsupported decision'):
        instructions.compose(original, [])


@pytest.mark.parametrize('original', ['', None, []])
def test_missing_original_contract_is_rejected(original):
    with pytest.raises(ValueError, match='original instructions'):
        instructions.compose(original, 'lead')


@pytest.mark.parametrize('version', diagnostic.INPUT_VERSIONS)
def test_diagnostic_validates_both_explicit_versions_without_mutation(body, version):
    body['observation']['state']['version'] = version
    before = copy.deepcopy(body)
    assert diagnostic.validate(body) is body
    assert body == before


@pytest.mark.parametrize('mutation', ['illegal', 'coverage', 'command', 'version', 'empty_scenario', 'extra'])
def test_bad_reference_or_request_cannot_reach_encoding(body, mutation):
    if mutation == 'illegal':
        body['action_id'] = 'move_99'
    elif mutation == 'coverage':
        body['actions'].pop()
    elif mutation == 'command':
        body['actions'][0]['command'] = 'switch 99'
    elif mutation == 'version':
        body['observation']['state']['version'] = 'unregistered-input'
    elif mutation == 'empty_scenario':
        body['scenario'] = {}
    else:
        body['q_values'] = {}
    with pytest.raises(ValueError):
        diagnostic.encode(body, Tokenizer())


@pytest.mark.parametrize('field', ['snapshot', 'counts', 'values', 'provenance', 'future_seed', 'root_opponent_choice'])
def test_scenario_cannot_leak_teacher_or_future_state(body, field):
    body['scenario']['nested'] = [{field: 'private'}]
    with pytest.raises(ValueError, match='forbidden model input'):
        diagnostic.validate(body)


def test_diagnostic_prompt_is_independent_of_binary_q_and_audited(body):
    before = copy.deepcopy(body)
    tok = Tokenizer()
    ids, audit = diagnostic.encode(body, tok)
    assert body == before and len(ids) == audit['input_tokens'] == audit['tokens']
    assert audit['max_new_tokens'] == 512 and audit['diagnostic_profile'] == diagnostic.PROFILE
    assert len(audit['prompt_sha256']) == len(audit['token_sha256']) == 64
    payload = json.loads(tok.messages[1]['content'])
    assert payload['evaluated_action']['action_id'] == body['action_id']
    assert payload['scenario'] == body['scenario']
    assert 'Final binary question:' not in tok.messages[1]['content']
    assert 'Never invent an exact damage range' in tok.messages[0]['content']
    assert payload['observation'] == body['observation']
    assert audit['projection_info']['retained_action_ids'] == []
    assert audit['projection_info']['omitted_action_ids'] == []


def _add_evaluations(body):
    state = body['observation']['state']
    state['version'] = value.STATE_VERSION
    state['candidate_evaluations'] = {
        action['action_id']: dict(kind='move', scenario_rows=[[index, 'unknown']])
        for index, action in enumerate(body['actions'])}
    state['candidate_scenario_columns'] = ['self_hp_after_first', 'self_survival']
    for action in body['actions']:
        action_id = action['action_id']
        criterion = body['observation']['questions']['action']['criteria'][action_id]
        criterion['evaluation_ref'] = action_id
        action['description'] = copy.deepcopy(criterion)
    return state['candidate_evaluations']


def test_diagnostic_projection_preserves_request_and_all_explicit_dependencies(body):
    evaluations = _add_evaluations(body)
    body['action_id'] = 'team_3'
    evaluations['team_3'].update(same_outcomes_as_action_id='team_2',
                                tera_comparison={'non_tera_action_id': 'team_1', 'resource_spent': True})
    evaluations['team_2']['same_outcomes_as_action_id'] = 'team_4'
    before = copy.deepcopy(body)
    tok = Tokenizer()
    _, audit = diagnostic.encode(body, tok)
    payload = json.loads(tok.messages[1]['content'])
    retained = ['team_1', 'team_2', 'team_3', 'team_4']
    omitted = ['team_5', 'team_6']
    expected = copy.deepcopy(body['observation'])
    expected['state']['candidate_evaluations'] = {key: evaluations[key] for key in retained}
    assert payload['observation'] == expected
    assert payload['legal_actions'] == body['actions']
    assert payload['evaluated_action'] == body['actions'][2]
    assert payload['scenario'] == body['scenario']
    assert body == before
    marker = payload['diagnostic_projection']
    assert marker['version'] == diagnostic.PROJECTION_VERSION
    assert marker['retained_action_ids'] == retained and marker['omitted_action_ids'] == omitted
    assert marker['omitted_evaluation_refs'] == 'not_projected_for_this_single_action_diagnostic'
    assert 'not unknown calculations' in tok.messages[0]['content']
    info = audit['projection_info']
    assert set(info) == {'version', 'retained_action_ids', 'omitted_action_ids',
                         'projected_observation_sha256'}
    assert info['retained_action_ids'] == retained and info['omitted_action_ids'] == omitted
    assert info['projected_observation_sha256'] == hashlib.sha256(json.dumps(expected,
        ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    # A caller can change its projected copy without changing any raw request alias.
    projected, _ = diagnostic._project(body)
    projected['observation']['state']['candidate_evaluations']['team_3']['scenario_rows'][0][0] = 999
    projected['legal_actions'][0]['description']['pokemon'] = 'changed'
    assert body == before


@pytest.mark.parametrize('reference', ['team_99', None, [], ''])
def test_unresolved_projection_dependency_is_rejected(body, reference):
    evaluations = _add_evaluations(body)
    evaluations['team_1']['same_outcomes_as_action_id'] = reference
    before = copy.deepcopy(body)
    with pytest.raises(ValueError, match='unresolved diagnostic'):
        diagnostic.encode(body, Tokenizer())
    assert body == before


def test_raw_contract_is_checked_before_other_calculations_are_omitted(body):
    _add_evaluations(body)
    body['actions'][-1]['description']['evaluation_ref'] = 'team_99'
    before = copy.deepcopy(body)
    with pytest.raises(ValueError, match='candidate description mismatch'):
        diagnostic.encode(body, Tokenizer())
    assert body == before


def test_projection_preserves_output_reserve_and_omits_only_other_code_outcomes(body):
    evaluations = _add_evaluations(body)
    for action_id, evaluation in evaluations.items():
        if action_id != body['action_id']:
            evaluation['scenario_rows'] = [['large conditional outcome ' * 1000]]
    before = copy.deepcopy(body)

    class SizeTokenizer(Tokenizer):
        def encode(self, prompt, **kwargs):
            assert kwargs == dict(add_special_tokens=False)
            return list(range(len(prompt) // 4))

    tok = SizeTokenizer()
    assert len(json.dumps(body, ensure_ascii=False)) // 4 + diagnostic.MAX_NEW_TOKENS > diagnostic.MAX_LEN
    ids, audit = diagnostic.encode(body, tok)
    assert len(ids) + audit['max_new_tokens'] <= diagnostic.MAX_LEN
    assert audit['projection_info']['retained_action_ids'] == [body['action_id']]
    assert body == before


@pytest.mark.parametrize('length', [0, diagnostic.MAX_LEN - diagnostic.MAX_NEW_TOKENS + 1])
def test_output_reservation_rejects_empty_or_overflow_without_truncation(body, length):
    with pytest.raises(ValueError, match='no truncation'):
        diagnostic.encode(body, Tokenizer(length))


def test_output_reservation_accepts_exact_boundary(body):
    ids, audit = diagnostic.encode(body, Tokenizer(diagnostic.MAX_LEN - diagnostic.MAX_NEW_TOKENS))
    assert len(ids) + audit['max_new_tokens'] == diagnostic.MAX_LEN


def test_compact_prediction_keeps_unknown_and_conditional(prediction, body):
    actual = diagnostic.parse(json.dumps(prediction), body['action_id'])
    assert actual['post_state']['self_defense_stage_after_move'] == 0
    assert actual['damage_applicability']['supplied_incoming_damage_still_applicable'] is False
    assert actual['survival'] == 'unknown'
    prediction['survival'] = {'status': 'conditional', 'conditions': ['Matching changed-state damage is provided.']}
    assert diagnostic.parse(json.dumps(prediction), body['action_id'])['survival']['status'] == 'conditional'


@pytest.mark.parametrize('mutation', ['wrong_id', 'extra', 'reasoning', 'nonfinite', 'probability', 'long_order'])
def test_invalid_generated_prediction_is_rejected_without_repair(prediction, body, mutation):
    if mutation == 'wrong_id':
        prediction['action_id'] = 'move_99'
    elif mutation == 'extra':
        prediction['q_values'] = {'move_1': .6}
    elif mutation == 'reasoning':
        prediction['post_state']['reasoning'] = 'a long internal chain'
    elif mutation == 'nonfinite':
        prediction['post_state']['hp'] = float('nan')
    elif mutation == 'probability':
        prediction['survival'] = .75
    else:
        prediction['order'] = 'first ' * 50
    with pytest.raises(ValueError):
        diagnostic.parse(json.dumps(prediction), body['action_id'])


@pytest.mark.parametrize('output', ['A', '```json\n{}\n```', '{"action_id":',
                                  '{"action_id":"move_1","action_id":"move_2"}', '[]'])
def test_malformed_or_duplicate_output_is_a_measurement_failure(output):
    with pytest.raises(ValueError):
        diagnostic.parse(output, 'move_1')


@pytest.mark.parametrize('outcome', ['valid', 'invalid_json', 'timeout', 'alternate_eos'])
def test_runtime_generation_is_isolated_and_preserves_failures(body, prediction, outcome, monkeypatch, tmp_path):
    from integration.pokechamp import qwen_server as server

    class GenerationConfig(SimpleNamespace):
        @classmethod
        def from_dict(cls, config):
            return cls(**copy.deepcopy(config))

    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        GenerationConfig=GenerationConfig, StoppingCriteria=object, StoppingCriteriaList=list))
    clock = SimpleNamespace(now=0.)
    monkeypatch.setattr(server, 'time', SimpleNamespace(monotonic=lambda: clock.now))
    before = {'do_sample': True, 'num_beams': 4, 'max_new_tokens': 16, 'use_cache': False,
              'eos_token_id': [99, 100], 'pad_token_id': 0}
    raw = 'A' if outcome == 'invalid_json' else json.dumps(prediction)
    output_ids = ([7] * 511 + [100]) if outcome == 'alternate_eos' else [7, 8, 99]
    calls, contexts = [], []

    class DiagnosticTokenizer(Tokenizer):
        pad_token_id, eos_token_id = 0, 99
        def decode(self, ids, **kwargs):
            assert ids == output_ids and kwargs == dict(skip_special_tokens=True)
            return raw

    class Generated:
        def __init__(self, tokens):
            self.tokens = tokens
        def __getitem__(self, index):
            assert index[0] == 0
            return SimpleNamespace(tolist=lambda: self.tokens[index[1]])

    def tensor(data, **kwargs):
        assert kwargs == dict(device='cuda:0', dtype='long')
        return SimpleNamespace(data=data)

    def ones(shape, **kwargs):
        assert kwargs == dict(device='cuda:0', dtype='long')
        return SimpleNamespace(shape=shape)

    def autocast(device, **kwargs):
        assert device == 'cuda' and kwargs == dict(dtype='bfloat16')
        contexts.append('autocast')
        return nullcontext()

    def no_grad():
        contexts.append('no_grad')
        return nullcontext()

    class Event:
        def __init__(self, **kwargs):
            assert kwargs == dict(enable_timing=True)
        def record(self):
            pass
        def elapsed_time(self, end):
            return 42.

    def generate(**kwargs):
        calls.append(kwargs)
        config = kwargs['generation_config']
        assert config.do_sample is False and config.num_beams == 1
        assert config.max_new_tokens == 512 and config.use_cache is True
        assert config.return_dict_in_generate is False and config.output_scores is False
        assert config.pad_token_id == 0
        assert kwargs['stopping_criteria'][0](None, None) is False
        ids = kwargs['input_ids'].data[0]
        assert kwargs['attention_mask'].shape == (1, len(ids))
        if outcome == 'timeout':
            clock.now = 11.
            assert kwargs['stopping_criteria'][0](None, None) is True
        return Generated(ids + output_ids)

    runtime = object.__new__(server.Runtime)
    runtime.lock = threading.Lock()
    runtime.failed = None
    runtime.diagnostics_enabled = True
    runtime.allowed_versions = diagnostic.INPUT_VERSIONS
    runtime.diagnostic_requests, runtime.diagnostic_gpu_seconds = 0, 0.
    runtime.requests, runtime.forwards, runtime.gpu_seconds = 7, 11, 12.3
    runtime.generation_config_before = copy.deepcopy(before)
    runtime.tok = DiagnosticTokenizer()
    runtime.policy = SimpleNamespace(model=SimpleNamespace(generate=generate))
    runtime.pv = SimpleNamespace(torch=SimpleNamespace(
        tensor=tensor, ones=ones, long='long', bfloat16='bfloat16', no_grad=no_grad, autocast=autocast,
        cuda=SimpleNamespace(Event=Event, synchronize=lambda: None)))
    runtime.output, runtime.data = tmp_path, value.data_module()
    runtime.save_progress = lambda: None
    result = runtime.diagnose(body, 10.)
    expected = 'valid' if outcome == 'alternate_eos' else outcome
    assert result['status'] == expected
    assert (result['prediction'] is not None) == (expected == 'valid')
    assert result['raw_output'] == raw and result['output_tokens'] == len(output_ids)
    assert result['gpu_seconds'] == runtime.diagnostic_gpu_seconds == .042
    assert runtime.diagnostic_requests == len(calls) == 1
    assert contexts == ['no_grad', 'autocast']
    assert (runtime.requests, runtime.forwards, runtime.gpu_seconds) == (7, 11, 12.3)
    assert runtime.failed is None and runtime.generation_config_before == before
    assert not runtime.lock.locked()
    record = json.loads((tmp_path / 'diagnostic-00001.jsonl').read_text())
    assert record['response']['status'] == expected and record['response']['raw_output'] == raw


def test_diagnostic_endpoint_is_disabled_by_default(body, monkeypatch):
    from http.server import ThreadingHTTPServer
    import urllib.error
    from integration.pokechamp.qwen_server import handler

    runtime = SimpleNamespace(diagnostics_enabled=False)
    http = ThreadingHTTPServer(('127.0.0.1', 0), handler(runtime))
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(value, 'ENDPOINT', f'http://127.0.0.1:{http.server_port}')
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            value.request('/diagnose', body)
        assert error.value.code == 404
    finally:
        http.shutdown()
        thread.join(timeout=2)
        http.server_close()
