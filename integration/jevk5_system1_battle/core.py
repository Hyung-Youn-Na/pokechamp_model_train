"""Lossless v6 formatting and native JevK5 readout over all candidate logits."""
from functools import lru_cache
import json
import math
from pathlib import Path
import os

from integration.pokechamp.jev_battle import UnusableChoice
from . import upstream_prompt as official

ROOT = Path(__file__).resolve().parents[2]
ROOT_RUN = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-123')
GPU_INDEX = int(os.environ.get('EX123_GPU', '1'))
if GPU_INDEX not in (1,2,3):raise ValueError('only physical GPUs 1,2,3 are authorized')
RUN = ROOT_RUN / 'shards' / f'gpu{GPU_INDEX}'
BASELINE = ROOT_RUN.parent / 'EX-089/collection'
EXPORT_ROOT = ROOT / 'exports/battle_viewers/ex123'
EXPORT = EXPORT_ROOT / f'gpu{GPU_INDEX}'
EXPERIMENT = 'EX-123'
MODEL = 'jevk5-system1'
MODEL_ID = 'alibiserikbay/JevK5-9B'
REVISION = 'd6521a18a86999190e9d775c915af3d6d6772fc4'
MODEL_DIR = Path('/root/.cache/huggingface/hub/models--alibiserikbay--JevK5-9B/snapshots') / REVISION
SERVER_PORT = 18850 + GPU_INDEX
ENDPOINT = f'http://127.0.0.1:{SERVER_PORT}/v1'
PORT = 8103 + GPU_INDEX
TIMEOUT = 120.
TEMPERATURE = 1.0
MAX_CONTEXT = 32768
CALL_LIMIT = {1:7500,2:6250,3:6250}[GPU_INDEX]
COLLECTION_SECONDS = 43200
RETRY_DELAYS = (2, 5, 10)


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


@lru_cache(maxsize=1)
def tokenizer():
    from tokenizers import Tokenizer
    return Tokenizer.from_file(str(MODEL_DIR / 'tokenizer.json'))


def label_ids(count):
    encoded = [tokenizer().encode(x, add_special_tokens=False).ids for x in official.LETTERS[:count]]
    if not 2 <= count <= 16 or any(len(x) != 1 for x in encoded):
        raise ValueError('requires 2..16 single-token option letters')
    values = [x[0] for x in encoded]
    if len(set(values)) != count:
        raise ValueError('option token IDs are not unique')
    return values


def question_parts(payload):
    if set(payload) != {'state', 'questions'} or set(payload['questions']) != {'action'}:
        raise ValueError('unexpected v6 fields')
    if payload['state']['version'] != 'jev-choice-v6':
        raise ValueError('detailed v6 input required')
    q = payload['questions']['action']
    if set(q) != {'type', 'instructions', 'criteria'} or q['type'] != 'choice':
        raise ValueError('unexpected action question fields')
    if not 2 <= len(q['criteria']) <= 16:
        raise ValueError('one-pass JevK5 requires 2..16 options')
    if not all(isinstance(k, str) and ': ' not in k for k in q['criteria']):
        raise ValueError('invalid option key')
    return q


def formatted_prompt(payload):
    q = question_parts(payload)
    # Official decision_options renders each option as "id: description". The v6
    # description is an object, so serialize it without dropping any fields.
    descriptions = [key + ': ' + dumps(value) for key, value in q['criteria'].items()]
    return official.prompt_text(payload['state'], q['instructions'], descriptions)


def to_request(payload):
    q = question_parts(payload)
    ids = tokenizer().encode(formatted_prompt(payload), add_special_tokens=False).ids
    if len(ids) + 1 > MAX_CONTEXT:
        raise ValueError('untruncated prompt exceeds model context')
    return dict(model=MODEL, prompt=ids, stream=False, n=1, max_tokens=1,
        temperature=0., seed=20261020, add_special_tokens=False, return_token_ids=True,
        skip_special_tokens=False, logprobs=1, logprob_token_ids=label_ids(len(q['criteria'])),
        return_tokens_as_token_ids=True)


def from_request(request):
    text = tokenizer().decode(request['prompt'], skip_special_tokens=False)
    prefix = '<|im_start|>system\n' + official.SYSTEM + '<|im_end|>\n<|im_start|>user\n'
    suffix = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    if not text.startswith(prefix) or not text.endswith(suffix):
        raise ValueError('native non-thinking template differs')
    data = json.loads(text[len(prefix):-len(suffix)])
    if set(data) != {'evidence', 'criterion', 'options'}:
        raise ValueError('unexpected native input fields')
    criteria = {}
    for i, row in enumerate(data['options']):
        if set(row) != {'letter', 'description'} or row['letter'] != official.LETTERS[i]:
            raise ValueError('letter ordering differs')
        key, content = row['description'].split(': ', 1)
        if key in criteria:
            raise ValueError('duplicate original ID')
        criteria[key] = json.loads(content)
    return dict(state=data['evidence'], questions=dict(action=dict(type='choice',
        instructions=data['criterion'], criteria=criteria)))


def calibrated(values):
    if not values or any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise UnusableChoice('nonfinite/missing option logprobs')
    z = [x / TEMPERATURE for x in values]
    p = [math.exp(x - max(z)) for x in z]
    total = sum(p)
    return [x / total for x in p]


def normalized_response(raw, payload, request=None):
    request = request or to_request(payload)
    if not isinstance(raw, dict) or raw.get('model') != MODEL:
        raise ValueError('external model identity differs')
    choices = raw.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError('unexpected completion envelope')
    choice = choices[0]
    if choice.get('index') != 0 or choice.get('finish_reason') not in ('stop', 'length'):
        raise ValueError('unexpected completion index/finish')
    if choice.get('prompt_token_ids') != request['prompt']:
        raise ValueError('server prompt token IDs differ')
    outputs = choice.get('token_ids')
    if not isinstance(outputs, list) or len(outputs) != 1 or type(outputs[0]) is not int:
        raise ValueError('one generated readout token required')
    usage = raw.get('usage')
    if not isinstance(usage, dict) or any(usage.get(k) != v for k, v in {
            'prompt_tokens':len(request['prompt']), 'completion_tokens':1,
            'total_tokens':len(request['prompt']) + 1}.items()):
        raise ValueError('external usage/token identity differs')
    try:
        positions = choice['logprobs']['top_logprobs']
        if len(positions) != 1:
            raise KeyError('position count')
        values = [positions[0]['token_id:' + str(x)] for x in request['logprob_token_ids']]
    except (KeyError, TypeError, IndexError):
        raise UnusableChoice('missing candidate logprobs') from None
    probs = calibrated(values)
    keys = list(question_parts(payload)['criteria'])
    winner = max(range(len(keys)), key=probs.__getitem__)
    return dict(model=MODEL, answers=dict(action=dict(type='choice', choice=keys[winner],
        probabilities=dict(zip(keys, probs)), confidence=probs[winner])),
        usage=dict(input_tokens=usage['prompt_tokens'], output_tokens=usage['completion_tokens']),
        metadata=dict(readout='jevk5-option-logprob-v1', temperature=TEMPERATURE,
            label_token_ids=request['logprob_token_ids'], label_logprobs=values,
            generated_token_ids=outputs, generated_text=choice.get('text'),
            generated_text_used_for_policy=False, physical_forward_calls=None,
            physical_forward_calls_unavailable='external vLLM does not expose internal forward count'))

ADAPTER = ROOT_RUN.parent / "EX-116/adapter-selected"
BASE_MODEL_NAME = "jevk5-9b-base"

