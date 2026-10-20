"""CPU frontend: exact candidate logprobs, three durable no-retry vLLM calls."""
import hashlib
import json
import math
import os
from pathlib import Path
import time

from integration.tacit9b.model import close_thought
from .config import ENDPOINT, HTTP_LIMIT, MAX_CONTEXT, MODEL_DIR, MODEL_ID, REVISION, SERVED_MODEL
from .formatting import choice_request, format_request, tokenize_request, mapped_answer, payload_seed, InputTooLong

MAX_NEW_TOKENS = 8192
SAMPLING = dict(temperature=0.6, top_p=0.95, top_k=20)
UNOBSERVED = 'external_vllm_does_not_expose_physical_forward_allocator_or_processed_tokens'


def label_ids(tokenizer, count, *, spaced_first):
    ids = []
    for label in 'ABCDEFGHIJKLMNOP'[:count]:
        candidates = (' ' + label, label) if spaced_first else (label, ' ' + label)
        for candidate in candidates:
            encoded = tokenizer.encode(candidate, add_special_tokens=False)
            if len(encoded) == 1:
                ids.append(encoded[0])
                break
        else:
            raise ValueError('label is not a single tokenizer token')
    if len(set(ids)) != count:
        raise ValueError('candidate token IDs collide')
    return ids


def read_result(formatted, choice, requested_ids, route):
    """Require every requested label, then normalize full-vocabulary logprobs over labels."""
    scores = choice.get('logprobs', {}).get('top_logprobs')
    if not isinstance(scores, list) or len(scores) != 1 or not isinstance(scores[0], dict):
        raise ValueError('one scoring position with candidate logprobs is required')
    values = []
    for token_id in requested_ids:
        key = f'token_id:{token_id}'
        value = scores[0].get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f'missing or nonfinite candidate logprob: {key}')
        values.append(value)
    maximum = max(values)
    exponentials = [math.exp(v - maximum) for v in values]
    total = sum(exponentials)
    probabilities = [v / total for v in exponentials]
    index = max(range(len(values)), key=values.__getitem__)
    top = sorted(values, reverse=True)
    return dict(answer=formatted.option_texts[index], index=index,
        probs=dict(zip(formatted.option_texts, probabilities)), margin=top[0] - top[1], route=route), values


class OfficialModel:
    def __init__(self):
        self.directory = None
        self.loaded = False
        self.identity = None
        self.external_http_calls = 0
        self.client = None
        self.external_identity = None

    def load(self):
        import httpx
        from transformers import AutoTokenizer
        from integration.jev_planner.external_runtime import verify_identity
        if self.directory is None:
            raise RuntimeError('external frontend requires a serving directory')
        self.directory = Path(self.directory)
        self.external_identity = json.loads((self.directory / 'external-identity.json').read_text())
        receipt = self.external_identity
        expected = dict(endpoint=ENDPOINT, model=SERVED_MODEL, model_revision=REVISION,
                        max_model_len=MAX_CONTEXT, physical_gpus=[1])
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise ValueError('external server receipt does not match EX-105')
        if Path(receipt['model_dir']).resolve() != MODEL_DIR.resolve():
            raise ValueError('external model directory differs from pinned tokenizer')
        verify_identity(receipt)
        if (self.directory / 'tacit-http.jsonl').exists():
            raise FileExistsError('external frontend inference journal cannot be resumed')
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=False)
        self.tokenizer.padding_side = 'left'
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.client = httpx.Client(timeout=600, trust_env=False, follow_redirects=False)
        self.identity = hashlib.sha256(json.dumps(dict(revision=REVISION, external_identity=receipt,
            frontend_pid=os.getpid()), sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        self.loaded = True
        self._journal(dict(type='frontend_loaded', external_identity=receipt, serving_identity=self.identity))
        return self

    def validate_input(self, payload):
        formatted = format_request(payload)
        return formatted, tokenize_request(self.tokenizer, formatted)

    def _journal(self, event):
        with (self.directory / 'tacit-http.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(at=time.time(), **event), ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def _verify_external(self):
        from integration.jev_planner.external_runtime import verify_identity
        verify_identity(self.external_identity, health=False)

    def _complete(self, prompt_ids, *, stage, seed, **params):
        self._verify_external()
        if self.external_http_calls >= HTTP_LIMIT:
            raise RuntimeError('external vLLM HTTP budget exhausted')
        max_tokens = params['max_tokens']
        if len(prompt_ids) + max_tokens > MAX_CONTEXT:
            raise InputTooLong(len(prompt_ids) + max_tokens, MAX_CONTEXT)
        request = dict(model=SERVED_MODEL, prompt=prompt_ids, stream=False, n=1,
            add_special_tokens=False, return_token_ids=True, skip_special_tokens=False,
            seed=seed, **params)
        self.external_http_calls += 1
        number = self.external_http_calls
        self._journal(dict(type='http_request', http_call=number, stage=stage, seed=seed, request_body=request))
        started = time.perf_counter()
        try:
            response = self.client.post(ENDPOINT + '/completions', json=request)
        except BaseException as error:
            self._journal(dict(type='http_failure', http_call=number, stage=stage,
                elapsed_seconds=time.perf_counter()-started,
                error=dict(type=type(error).__name__, detail=str(error))))
            raise
        seconds = time.perf_counter()-started
        # Preserve even malformed/error responses before parsing, mapping, or resource gates.
        self._journal(dict(type='http_response', http_call=number, stage=stage,
            status_code=response.status_code, raw_body=response.text, elapsed_seconds=seconds))
        self._verify_external()
        if response.status_code != 200:
            raise RuntimeError(f'external vLLM HTTP status {response.status_code}; no retry')
        body = response.json()
        if body.get('model') != SERVED_MODEL or len(body.get('choices', [])) != 1:
            raise ValueError('external response model/choice identity mismatch')
        choice = body['choices'][0]
        if choice.get('index') != 0 or choice.get('finish_reason') not in ('stop', 'length'):
            raise ValueError('invalid external completion index/finish')
        output_ids = choice.get('token_ids')
        if (not isinstance(output_ids, list) or not output_ids or
                any(type(v) is not int or v < 0 for v in output_ids) or len(output_ids) > max_tokens):
            raise ValueError('missing or invalid generated token IDs')
        returned_prompt = choice.get('prompt_token_ids')
        if returned_prompt != prompt_ids:
            raise ValueError('external response prompt token IDs differ')
        usage = body.get('usage')
        if (not isinstance(usage, dict) or usage.get('prompt_tokens') != len(prompt_ids) or
                usage.get('completion_tokens') != len(output_ids) or
                usage.get('total_tokens') != len(prompt_ids) + len(output_ids)):
            raise ValueError('external usage/token ID counts differ')
        if choice['finish_reason'] == 'length' and len(output_ids) != max_tokens:
            raise ValueError('external length stop before frozen generation limit')
        metrics = dict(seconds=seconds, input_tokens=len(prompt_ids), output_tokens=len(output_ids),
            prompt_token_ids=prompt_ids, output_token_ids=output_ids, usage=usage,
            raw_response_id=body.get('id'), http_calls=1, http_call=number,
            forward_calls=None, processed_input_tokens=None, measurement_unavailable_reason=UNOBSERVED)
        return choice, metrics

    def _read(self, formatted, prompt_ids, *, stage, seed, spaced_first):
        ids = label_ids(self.tokenizer, len(formatted.candidate_ids), spaced_first=spaced_first)
        choice, metrics = self._complete(prompt_ids, stage=stage, seed=seed, max_tokens=1,
            temperature=0.0, logprobs=1, logprob_token_ids=ids, return_tokens_as_token_ids=True)
        result, values = read_result(formatted, choice, ids,
                                     'one_forward' if stage == 'first_pass' else 'cot')
        metrics.update(label_token_ids=ids, label_logprobs=values)
        return result, metrics

    def evaluate(self, payload):
        formatted, encoded = self.validate_input(payload)
        seed = payload_seed(payload)
        started = self.external_http_calls
        stages = {}
        try:
            first, stages['first_pass'] = self._read(formatted, encoded['input_ids'],
                stage='first_pass', seed=seed, spaced_first=False)
            self._journal(dict(type='first_pass', response=first, seed=seed, stages=stages))
            choice, stages['thinking'] = self._complete(encoded['thinking_input_ids'], stage='thinking',
                seed=seed, max_tokens=MAX_NEW_TOKENS, stop=['</think>'],
                include_stop_str_in_output=True, **SAMPLING)
            thinking = dict(close_thought(self.tokenizer, choice['token_ids']), seed=seed,
                server_text=choice['text'], server_finish_reason=choice['finish_reason'],
                server_stop_reason=choice.get('stop_reason'))
            self._journal(dict(type='thinking', response=thinking, stages=stages))
            read_prompt = encoded['thinking_prompt'] + thinking['closed_text'] + '\n\nAnswer:'
            final_ids = self.tokenizer.encode(read_prompt, add_special_tokens=False)
            final, stages['final_read'] = self._read(formatted, final_ids,
                stage='final_read', seed=seed, spaced_first=True)
            final.update(first_pass=first, reasoning_tokens=len(thinking['token_ids']))
            self._journal(dict(type='official_response', response=final, stages=stages))
        except BaseException as error:
            self._journal(dict(type='pipeline_failure', seed=seed, completed_stages=list(stages),
                error=dict(type=type(error).__name__, detail=str(error))))
            raise
        return dict(model=MODEL_ID, answers={formatted.question_name: mapped_answer(formatted, final)},
            first_pass=mapped_answer(formatted, first), official_response=final,
            official_request=choice_request(payload), thinking=thinking, stages=stages,
            original_input_tokens=dict(first_pass=len(encoded['input_ids']), thinking=len(encoded['thinking_input_ids'])),
            physical_forward_calls=None, processed_input_tokens=None,
            measurement_unavailable_reason=UNOBSERVED, external_http_calls=self.external_http_calls-started,
            usage=dict(input_tokens=sum(v['input_tokens'] for v in stages.values()),
                       output_tokens=sum(v['output_tokens'] for v in stages.values())), metadata=self.metadata())

    def metadata(self):
        return dict(model=MODEL_ID, revision=REVISION, loaded=self.loaded, serving_identity=self.identity,
            backend='external-vllm', activation_dtype='bfloat16', physical_gpus=[1],
            max_input_tokens=32768, max_context_tokens=MAX_CONTEXT,
            forward_calls=None, allocator_bytes=None, processed_input_tokens=None,
            measurement_unavailable_reason=UNOBSERVED, external_http_calls=self.external_http_calls,
            external_http_limit=HTTP_LIMIT, external_identity=self.external_identity,
            thinking_mode='always', cot_max_tokens=MAX_NEW_TOKENS, sampling=SAMPLING)

    def close(self):
        self.loaded = False
        if self.client is not None:
            self.client.close()
        self.client = None
