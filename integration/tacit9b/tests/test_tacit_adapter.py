"""CPU contracts for the pinned prompts and always-thinking pipeline."""
from contextlib import nullcontext
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integration.tacit9b import formatting as fmt
from integration.tacit9b.model import OfficialModel, close_thought, official_module
from integration.tacit9b.config import MODEL_DIR

PAYLOAD = dict(model='morriszjm/Tacit-9B', state={'full': '관측', 'plan': ['preserve', 'goal']}, questions={
    'action': dict(type='choice', instructions='choose full', criteria={
        'z': {'command': '/choose move 1'}, 'a': {'command': '/choose move 2'}})})


class TacitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from transformers import AutoTokenizer
        cls.tok = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
        cls.official = official_module()
        cls.tacit = cls.official.Tacit(None, cls.tok, batch_size=1)

    def test_official_prompt_token_equivalence_and_mapping(self):
        formatted = fmt.format_request(PAYLOAD)
        encoded = fmt.tokenize_request(self.tok, formatted)
        item = self.tacit._normalise(fmt.choice_request(PAYLOAD))
        for system, userfn, thinking, key in [
            (self.official.ONE_FORWARD_SYSTEM, self.official._one_forward_user, False, 'input_ids'),
            (self.official.COT_SYSTEM, self.official._cot_user, True, 'thinking_input_ids')]:
            user = userfn(item['state'], item['question'], item['kind'], item['options'], item['labels'])
            rendered = self.tacit._render(system, user, thinking)
            self.assertEqual(encoded[key], self.tok.encode(rendered, add_special_tokens=False))
        self.assertEqual(formatted.candidate_ids, ('z', 'a'))
        self.assertEqual([json.loads(x) for x in formatted.option_texts],
                         [{'z': PAYLOAD['questions']['action']['criteria']['z']},
                          {'a': PAYLOAD['questions']['action']['criteria']['a']}])
        with self.assertRaises(fmt.InputTooLong):
            fmt.tokenize_request(self.tok, formatted, max_tokens=2)

    def test_ending_semantics(self):
        for text, cap, reason, closed in [('reason</think>discard', 999, 'natural', 'reason</think>'),
                                         ('reason', 1, 'length', 'reason\n</think>'),
                                         ('reason' + self.tok.eos_token, 999, 'eos', 'reason\n</think>')]:
            result = close_thought(self.tok, self.tok.encode(text, add_special_tokens=False), cap)
            self.assertEqual(result['finish_reason'], reason)
            self.assertEqual(result['closed_text'], closed)
        reordered = copy.deepcopy(PAYLOAD)
        reordered['questions']['action']['criteria'] = dict(reversed(list(reordered['questions']['action']['criteria'].items())))
        self.assertNotEqual(fmt.payload_seed(PAYLOAD), fmt.payload_seed(reordered))

    def test_high_confidence_always_thinks_no_first_pass_leak_and_usage(self):
        import torch
        tok = self.tok
        class FakeModel(torch.nn.Module):
            device = 'cpu'
            def __init__(self):
                super().__init__()
                self.inputs = []
            def forward(self, input_ids, **kwargs):
                self.inputs.append(input_ids[0].tolist())
                logits = torch.full((1, 1, len(tok)), -10.0)
                preferred = 'A' if len(self.inputs) == 1 else ' B'
                logits[0, 0, tok.encode(preferred, add_special_tokens=False)[0]] = 10
                return type('Output', (), dict(logits=logits))()
            def generate(self, input_ids, **kwargs):
                self(input_ids=input_ids)
                self(input_ids=torch.tensor([[100]]))
                self.sampling = kwargs
                suffix = tok.encode('reason</think>', add_special_tokens=False)
                return torch.cat([input_ids, torch.tensor([suffix])], dim=1)
        model = FakeModel()
        adapter = OfficialModel()
        adapter.tokenizer = tok
        adapter.classifier = self.official.Tacit(self.official._TransformersEngine(model, tok), tok)
        adapter._allocator = lambda phase: None
        adapter._journal = lambda event: None
        with patch('torch.cuda.synchronize'), patch('torch.random.fork_rng', return_value=nullcontext()):
            result = adapter.evaluate(PAYLOAD)
        self.assertEqual(result['first_pass']['choice'], 'z')
        self.assertEqual(result['answers']['action']['choice'], 'a')
        encoded = fmt.tokenize_request(tok, fmt.format_request(PAYLOAD))
        self.assertEqual(model.inputs[1], encoded['thinking_input_ids'])
        self.assertEqual(result['physical_forward_calls'], 4)
        self.assertEqual(result['processed_input_tokens'], sum(map(len, model.inputs)))
        self.assertEqual(result['usage']['input_tokens'], sum(v['input_tokens'] for v in result['stages'].values()))
        self.assertEqual(result['usage']['output_tokens'], len(result['thinking']['token_ids']))
        self.assertEqual(result['thinking']['finish_reason'], 'natural')
        self.assertEqual(model.sampling['max_new_tokens'], 8192)
        self.assertEqual(model.sampling['temperature'], .6)
        self.assertEqual(model.sampling['top_p'], .95)
        self.assertEqual(model.sampling['top_k'], 20)
        # A resource stop after generation must preserve its complete raw result first.
        failed_model = FakeModel()
        adapter.classifier = self.official.Tacit(self.official._TransformersEngine(failed_model, tok), tok)
        journal = []
        adapter._journal = lambda event: journal.append(copy.deepcopy(event))
        def fail_after_thinking(phase):
            if phase == 'thinking':
                raise RuntimeError('allocator limit')
        adapter._allocator = fail_after_thinking
        with patch('torch.cuda.synchronize'), patch('torch.random.fork_rng', return_value=nullcontext()):
            with self.assertRaisesRegex(RuntimeError, 'allocator limit'):
                adapter.evaluate(PAYLOAD)
        thinking_event = next(event for event in journal if event['type'] == 'thinking')
        self.assertEqual(thinking_event['response']['text'], 'reason</think>')
        self.assertTrue(thinking_event['response']['token_ids'])
        self.assertIn('seconds', thinking_event['stages']['thinking'])
        self.assertEqual(journal[-1]['type'], 'forward_failure')
        self.assertEqual(len(failed_model.inputs), 3)



if __name__ == '__main__':
    unittest.main()

class PreflightTests(unittest.IsolatedAsyncioTestCase):
    async def test_gate_precedes_diagnostics_and_budget_counts_eleven(self):
        from integration.tacit9b.preflight import run_preflight
        data = dict(requests=[dict(case=str(i), payload=PAYLOAD) for i in range(8)],
                    diagnostic_requests=[dict(case=str(i), source={'turn': i}, payload=PAYLOAD) for i in (2, 5, 6)])
        config = dict(evaluation=dict(executor_repeat_policy='probability_diagnostic',
                                      executor_preflight=dict(data=data)))
        for fail in (False, True):
            calls = []
            reservations = []
            async def executor(payload, *, decision):
                calls.append(decision)
                return dict(answers={'action': dict(choice='a' if fail and len(calls)==8 else 'z',
                                                    probabilities={'z': .9, 'a': .1})})
            with TemporaryDirectory() as directory:
                if fail:
                    with self.assertRaises(ValueError):
                        await run_preflight(config, executor, directory, before_executor=lambda **k: reservations.append(k))
                    self.assertEqual(len(calls), 8)
                    self.assertFalse((Path(directory) / 'diagnostic-results.json').exists())
                else:
                    await run_preflight(config, executor, directory, before_executor=lambda **k: reservations.append(k))
                    self.assertEqual(len(calls), 11)
                    self.assertEqual(len(reservations), 11)
                    self.assertEqual(len(json.loads((Path(directory) / 'diagnostic-results.json').read_text())), 3)

    async def test_existing_service_replays_whole_pipeline(self):
        from integration.jev27b.server import LocalService, json_bytes
        from integration.tacit9b.config import MODEL_ID, REVISION
        import hashlib
        class FakePipeline:
            calls = 0
            def metadata(self):
                return dict(model=MODEL_ID, revision=REVISION, loaded=True, serving_identity='a'*64)
            def evaluate(self, payload):
                self.calls += 1
                return dict(model=MODEL_ID, answers={}, physical_forward_calls=12)
        model = FakePipeline()
        with TemporaryDirectory() as directory:
            service = LocalService(model, directory, model_id=MODEL_ID, revision=REVISION)
            raw = json_bytes(PAYLOAD)
            kw = dict(request_id='ex104-test-1', body_sha256=hashlib.sha256(raw).hexdigest(), expected_identity='a'*64)
            first = service.evaluate(raw, **kw)
            last = service.evaluate(raw, **kw)
            self.assertEqual(first[0], 200)
            self.assertEqual(first[1], last[1])
            self.assertTrue(last[2])
            self.assertEqual(model.calls, 1)
            service.close()
