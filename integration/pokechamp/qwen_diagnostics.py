"""Read-only diagnostic prompt/schema helpers; no q readout or transmission."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from . import qwen_value as v

PROFILE = 'qwen-state-diagnostic-v1'
VERSION = PROFILE
PROJECTION_VERSION = 'qwen-diagnostic-candidate-projection-v1'
PROMPT = Path(__file__).with_name('prompts') / (PROFILE + '.txt')
MAX_NEW_TOKENS = 512
MAX_LEN = 16384
INPUT_VERSIONS = ('jev-choice-v4', 'qwen-candidate-state-v1')
FIELDS = {'action_id', 'scenario', 'order', 'post_state', 'damage_applicability', 'survival', 'ko'}
REASONING_KEYS = {'reasoning', 'analysis', 'thought', 'thoughts', 'chain_of_thought', 'rationale', 'explanation'}


def _short_json(value, *, depth=0):
    if depth > 6:
        raise ValueError('diagnostic structure is too deep')
    if isinstance(value, dict):
        if len(value) > 24 or any(not isinstance(k, str) or len(k) > 96 for k in value):
            raise ValueError('invalid diagnostic object')
        for key, child in value.items():
            if key.lower() in REASONING_KEYS:
                raise ValueError('internal reasoning is not a diagnostic prediction')
            _short_json(child, depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > 24:
            raise ValueError('diagnostic list is too long')
        for child in value:
            _short_json(child, depth=depth + 1)
    elif isinstance(value, str):
        if len(value) > 1000:
            raise ValueError('diagnostic text is too long')
    elif value is None or type(value) is bool:
        return
    elif type(value) in (int, float):
        if type(value) is float and not math.isfinite(value):
            raise ValueError('nonfinite diagnostic number')
    else:
        raise ValueError('diagnostic values must be JSON data')


def validate(body):
    """Validate references without changing the request or deriving hidden facts."""
    if not isinstance(body, dict) or set(body) != {'observation', 'actions', 'action_id', 'scenario'}:
        raise ValueError('expected observation, actions, action_id and public scenario only')
    v.data_module().check_boundary(body)
    _, actions = v.validate_input(
        {'observation': body['observation'], 'actions': body['actions']},
        allowed_versions=INPUT_VERSIONS)
    action_id = body['action_id']
    if not isinstance(action_id, str) or action_id not in {a['action_id'] for a in actions}:
        raise ValueError('diagnostic action_id is not a supplied legal action')
    if not isinstance(body['scenario'], dict) or not body['scenario']:
        raise ValueError('diagnostic scenario must be a nonempty public conditions object')
    _short_json(body['scenario'])
    # The original action validator checks ordered coverage and candidate/command links.
    return body


def encode(body, tok):
    """Return one independent diagnostic prompt with an untruncated output reserve."""
    validate(body)
    payload, projection_info = _project(body)
    messages = [{'role': 'system', 'content': PROMPT.read_text()},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False,
                    separators=(',', ':'), allow_nan=False)}]
    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                    enable_thinking=False)
    ids = tok.encode(prompt, add_special_tokens=False)
    if not ids or len(ids) + MAX_NEW_TOKENS > MAX_LEN:
        raise ValueError(f'diagnostic input has {len(ids)} tokens plus {MAX_NEW_TOKENS} '
                         f'reserved output tokens; no truncation')
    audit = dict(diagnostic_profile=PROFILE, action_id=body['action_id'], tokens=len(ids),
                 input_tokens=len(ids), max_new_tokens=MAX_NEW_TOKENS,
                 prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                 token_sha256=hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
                 projection_info=projection_info)
    return ids, audit


def _project(body):
    """Scope only added code outcomes in a fresh, already-validated model payload."""
    projected = copy.deepcopy(body)
    observation = projected['observation']
    state = observation['state']
    evaluations = state.get('candidate_evaluations')
    retained, omitted = [], []
    if evaluations is not None:
        legal_ids = {action['action_id'] for action in projected['actions']}
        if (not isinstance(evaluations, dict) or any(key not in legal_ids or
                not isinstance(value, dict) for key, value in evaluations.items())):
            raise ValueError('invalid diagnostic candidate evaluations')
        criteria = observation['questions']['action']['criteria']
        chosen = projected['action_id']
        reference = criteria[chosen].get('evaluation_ref', chosen)
        if reference != chosen:
            raise ValueError('diagnostic evaluation_ref must identify the evaluated action')
        keep = set()
        pending = [chosen]
        while pending:
            action_id = pending.pop()
            if not isinstance(action_id, str) or action_id not in evaluations:
                raise ValueError('unresolved diagnostic candidate evaluation reference')
            if action_id in keep:
                continue
            keep.add(action_id)
            evaluation = evaluations[action_id]
            if 'same_outcomes_as_action_id' in evaluation:
                pending.append(evaluation['same_outcomes_as_action_id'])
            comparison = evaluation.get('tera_comparison')
            if comparison is not None:
                if not isinstance(comparison, dict):
                    raise ValueError('invalid diagnostic Tera comparison')
                if 'non_tera_action_id' in comparison:
                    pending.append(comparison['non_tera_action_id'])
        retained = [key for key in evaluations if key in keep]
        omitted = [key for key in evaluations if key not in keep]
        state['candidate_evaluations'] = {key: evaluations[key] for key in retained}
    info = dict(version=PROJECTION_VERSION, retained_action_ids=retained,
                omitted_action_ids=omitted,
                projected_observation_sha256=hashlib.sha256(json.dumps(observation,
                    ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest())
    action = next(action for action in projected['actions']
                  if action['action_id'] == projected['action_id'])
    payload = dict(observation=observation, legal_actions=projected['actions'],
                   evaluated_action=action, scenario=projected['scenario'],
                   diagnostic_projection=dict(version=PROJECTION_VERSION,
                       evaluated_action_id=projected['action_id'], retained_action_ids=retained,
                       omitted_action_ids=omitted, scope='candidate_evaluations_only',
                       omitted_evaluation_refs='not_projected_for_this_single_action_diagnostic'))
    return payload, info


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate diagnostic field: ' + key)
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('nonfinite diagnostic number: ' + value)


def _verdict(value):
    def status(item):
        return type(item) is bool or isinstance(item, str) and item in ('conditional', 'unknown')
    if status(value):
        return
    if not isinstance(value, dict) or not {'status'} <= set(value) <= {'status', 'conditions', 'reason'}:
        raise ValueError('survival and ko require a boolean, conditional or unknown status')
    if not status(value['status']):
        raise ValueError('invalid conditional verdict status')
    if 'conditions' in value and (not isinstance(value['conditions'], list) or
            len(value['conditions']) > 4 or any(not isinstance(c, str) or not c.strip() or len(c) > 240
                                             for c in value['conditions'])):
        raise ValueError('invalid verdict conditions')
    if 'reason' in value and (not isinstance(value['reason'], str) or len(value['reason']) > 240):
        raise ValueError('invalid verdict reason')


def parse(text, action_id):
    """Validate a generated prediction; callers preserve raw failures without repair."""
    if not isinstance(text, str) or not text.strip() or len(text) > 8192:
        raise ValueError('empty or oversized diagnostic output')
    try:
        result = json.loads(text, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('diagnostic output is not one complete JSON object') from exc
    if not isinstance(result, dict) or set(result) != FIELDS:
        raise ValueError('diagnostic output must contain exactly the seven prediction fields')
    if result['action_id'] != action_id:
        raise ValueError('diagnostic action_id mismatch')
    if (not isinstance(result['scenario'], (str, dict)) or not result['scenario'] or
            isinstance(result['scenario'], str) and not result['scenario'].strip()):
        raise ValueError('diagnostic scenario must state its conditions')
    if not isinstance(result['order'], str) or not result['order'].strip() or len(result['order']) > 240:
        raise ValueError('diagnostic order must be a short conditional statement')
    if not isinstance(result['post_state'], dict) or not isinstance(result['damage_applicability'], dict):
        raise ValueError('diagnostic post_state and damage_applicability must be objects')
    _short_json(result)
    v.data_module().check_boundary(result)
    _verdict(result['survival'])
    _verdict(result['ko'])
    return result
