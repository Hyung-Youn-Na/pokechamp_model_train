"""CPU-only official prompt and mocked external completions contracts."""
import copy
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integration.tacit9b.config import MODEL_DIR, MODEL_ID, REVISION
from integration.tacit9b.model import official_module
from integration.tacit9b_vllm import formatting as fmt
from integration.tacit9b_vllm.model import OfficialModel, label_ids, read_result, MAX_CONTEXT, HTTP_LIMIT

PAYLOAD = dict(model=MODEL_ID, state={'facts': '전체 공개 관측', 'plan': ['first', 'second']}, questions={
    'action': dict(type='choice', instructions='choose from the complete candidates', criteria={
        'z': {'command': '/choose move 1'}, 'a': {'command': '/choose move 2'}})})


class FakeResponse:
    def __init__(self, body, status=200):
        self.status_code = status
        self.text = json.dumps(body, ensure_ascii=False)
    def json(self):
        return json.loads(self.text)


class FakeHTTP:
    def __init__(self, tokenizer, *, missing_label=False, malformed=False, status=200, finish='natural'):
        self.tok = tokenizer
        self.requests = []
        self.missing_label = missing_label
        self.malformed = malformed
        self.status = status
        self.finish = finish
    def post(self, url, *, json):
        request = copy.deepcopy(json)
        self.requests.append(request)
        if self.status != 200:
            return FakeResponse({'error': 'test upstream error'}, self.status)
        if request['max_tokens'] == 1:
            token_ids = [self.tok.encode('Z', add_special_tokens=False)[0]]
            labels = request['logprob_token_ids']
            scores = {f'token_id:{i}': (-.01 if j == (0 if len(self.requests)==1 else 1) else -6)
                      for j, i in enumerate(labels)}
            scores[f'token_id:{token_ids[0]}'] = -.001
            if self.missing_label:
                scores.pop(f'token_id:{labels[-1]}')
            logs = dict(top_logprobs=[scores])
            finish_reason, stop_reason = 'length', None
            text = self.tok.decode(token_ids, skip_special_tokens=False)
        else:
            if self.finish == 'natural':
                token_ids = self.tok.encode('reason</think>', add_special_tokens=False)
                finish_reason, stop_reason = 'stop', '</think>'
            elif self.finish == 'eos':
                token_ids = self.tok.encode('reason' + self.tok.eos_token, add_special_tokens=False)
                finish_reason, stop_reason = 'stop', None
            else:
                token_ids = self.tok.encode('x', add_special_tokens=False)*8192
                finish_reason, stop_reason = 'length', None
            text = self.tok.decode(token_ids, skip_special_tokens=False)
            logs = None
        body = dict(model='tacit9b', id='mock-' + str(len(self.requests)),
            choices=[dict(index=0, text=text, token_ids=token_ids,
                prompt_token_ids=request['prompt'], logprobs=logs,
                finish_reason=finish_reason, stop_reason=stop_reason)],
            usage=dict(prompt_tokens=len(request['prompt']), completion_tokens=len(token_ids),
                       total_tokens=len(request['prompt'])+len(token_ids)))
        if self.malformed:
            body['choices'][0]['prompt_token_ids'] = None
        return FakeResponse(body)
    def close(self):
        pass


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from transformers import AutoTokenizer
        cls.tok = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
        cls.official = official_module()
        cls.tacit = cls.official.Tacit(None, cls.tok, batch_size=1)

    def adapter(self, directory, **kwargs):
        adapter = OfficialModel()
        adapter.directory = Path(directory)
        adapter.tokenizer = self.tok
        adapter.client = FakeHTTP(self.tok, **kwargs)
        adapter._verify_external = lambda: None
        return adapter

    def test_official_prompt_labels_and_full_normalization(self):
        payload = copy.deepcopy(PAYLOAD)
        payload['questions']['action']['criteria'] = {f'candidate-{i}': {'v': i} for i in range(16)}
        formatted = fmt.format_request(payload)
        encoded = fmt.tokenize_request(self.tok, formatted)
        item = self.tacit._normalise(fmt.choice_request(payload))
        for system, userfn, thinking, key in [
            (self.official.ONE_FORWARD_SYSTEM, self.official._one_forward_user, False, 'input_ids'),
            (self.official.COT_SYSTEM, self.official._cot_user, True, 'thinking_input_ids')]:
            user = userfn(item['state'], item['question'], item['kind'], item['options'], item['labels'])
            rendered = self.tacit._render(system, user, thinking)
            self.assertEqual(encoded[key], self.tok.encode(rendered, add_special_tokens=False))
            self.assertEqual(label_ids(self.tok, 16, spaced_first=thinking),
                             self.tacit._label_ids(item['labels'], spaced_first=thinking))
        ids = label_ids(self.tok, 16, spaced_first=True)
        logs = {f'token_id:{i}': -1000.0-j for j, i in enumerate(ids)}
        result, values = read_result(formatted, {'logprobs': {'top_logprobs': [logs]}}, ids, 'cot')
        self.assertEqual(len(result['probs']), 16)
        self.assertAlmostEqual(sum(result['probs'].values()), 1)
        self.assertEqual(result['index'], 0)
        self.assertAlmostEqual(result['probs'][formatted.option_texts[0]], 1/sum(math.exp(-j) for j in range(16)))
        with self.assertRaises(fmt.InputTooLong):
            fmt.tokenize_request(self.tok, formatted, max_tokens=2)

    def test_always_thinking_no_first_pass_leak_three_calls_and_usage(self):
        with TemporaryDirectory() as directory:
            adapter = self.adapter(directory)
            result = adapter.evaluate(PAYLOAD)
            requests = adapter.client.requests
            self.assertEqual(len(requests), 3)
            self.assertEqual(result['first_pass']['choice'], 'z')
            self.assertEqual(result['answers']['action']['choice'], 'a')
            encoded = fmt.tokenize_request(self.tok, fmt.format_request(PAYLOAD))
            self.assertEqual(requests[1]['prompt'], encoded['thinking_input_ids'])
            expected_final = encoded['thinking_prompt'] + 'reason</think>\n\nAnswer:'
            self.assertEqual(requests[2]['prompt'], self.tok.encode(expected_final, add_special_tokens=False))
            self.assertEqual(result['usage']['output_tokens'], len(result['thinking']['token_ids'])+2)
            self.assertEqual(result['usage']['input_tokens'], sum(len(r['prompt']) for r in requests))
            self.assertIsNone(result['physical_forward_calls'])
            self.assertIsNone(result['processed_input_tokens'])
            self.assertEqual(result['external_http_calls'], 3)
            self.assertEqual({r['seed'] for r in requests}, {fmt.payload_seed(PAYLOAD)})
            self.assertEqual(requests[1]['max_tokens'], 8192)
            self.assertEqual(requests[1]['temperature'], .6)
            self.assertEqual(requests[1]['top_p'], .95)
            self.assertEqual(requests[1]['top_k'], 20)
            self.assertTrue(requests[1]['include_stop_str_in_output'])
            for request in (requests[0], requests[2]):
                self.assertEqual(request['logprobs'], 1)
                self.assertEqual(len(request['logprob_token_ids']), 2)
                self.assertTrue(request['return_tokens_as_token_ids'])
            journal = [json.loads(line) for line in (Path(directory)/'tacit-http.jsonl').read_text().splitlines()]
            self.assertEqual([r['type'] for r in journal],
                ['http_request','http_response','first_pass','http_request','http_response','thinking',
                 'http_request','http_response','official_response'])

    def test_natural_length_eos_close_and_read(self):
        for finish in ('natural', 'length', 'eos'):
            with self.subTest(finish=finish), TemporaryDirectory() as directory:
                adapter = self.adapter(directory, finish=finish)
                result = adapter.evaluate(PAYLOAD)
                self.assertEqual(result['thinking']['finish_reason'], finish)
                self.assertEqual(result['thinking']['forced_close'], finish != 'natural')
                self.assertTrue(result['thinking']['closed_text'].endswith('</think>'))
                self.assertTrue(result['thinking']['token_ids'])

    def test_missing_candidate_prompt_mismatch_and_http_error_preserve_raw_without_retry(self):
        for params in (dict(missing_label=True), dict(malformed=True), dict(status=503)):
            with self.subTest(params=params), TemporaryDirectory() as directory:
                adapter = self.adapter(directory, **params)
                with self.assertRaises((ValueError, RuntimeError)):
                    adapter.evaluate(PAYLOAD)
                self.assertEqual(len(adapter.client.requests), 1)
                journal = [json.loads(line) for line in (Path(directory)/'tacit-http.jsonl').read_text().splitlines()]
                self.assertEqual(journal[1]['type'], 'http_response')
                self.assertTrue(journal[1]['raw_body'])
                self.assertEqual(journal[-1]['type'], 'pipeline_failure')

    def test_external_budget_context_and_transport_failure_no_retry(self):
        with TemporaryDirectory() as directory:
            adapter = self.adapter(directory)
            adapter.external_http_calls = HTTP_LIMIT
            with self.assertRaisesRegex(RuntimeError, 'budget'):
                adapter.evaluate(PAYLOAD)
            self.assertEqual(len(adapter.client.requests), 0)
            adapter.external_http_calls = 0
            with self.assertRaises(fmt.InputTooLong):
                adapter._complete([1]*MAX_CONTEXT, stage='final_read', seed=1, max_tokens=1)
            adapter.client.post = lambda *a, **k: (_ for _ in ()).throw(TimeoutError('mock timeout'))
            with self.assertRaises(TimeoutError):
                adapter.evaluate(PAYLOAD)
            self.assertEqual(adapter.external_http_calls, 1)
            journal = [json.loads(line) for line in (Path(directory)/'tacit-http.jsonl').read_text().splitlines()]
            self.assertEqual(sum(r['type']=='http_request' for r in journal), 1)
            self.assertEqual(sum(r['type']=='http_failure' for r in journal), 1)

    def test_duplicate_front_request_replays_complete_three_call_pipeline(self):
        from integration.jev27b.server import LocalService, json_bytes
        import hashlib
        with TemporaryDirectory() as directory:
            adapter = self.adapter(directory)
            adapter.loaded = True
            adapter.identity = 'a'*64
            service = LocalService(adapter, directory, model_id=MODEL_ID, revision=REVISION)
            raw = json_bytes(PAYLOAD)
            headers = dict(request_id='ex105-test-1', body_sha256=hashlib.sha256(raw).hexdigest(), expected_identity='a'*64)
            first = service.evaluate(raw, **headers)
            repeated = service.evaluate(raw, **headers)
            self.assertEqual(first[0], 200)
            self.assertEqual(first[1], repeated[1])
            self.assertTrue(repeated[2])
            self.assertEqual(len(adapter.client.requests), 3)
            service.close()


if __name__ == '__main__':
    unittest.main()
