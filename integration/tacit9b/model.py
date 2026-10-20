"""Pinned Transformers Tacit pipeline with always-thinking and physical evidence."""
from collections import Counter
import hashlib
import importlib.util
import inspect
from importlib.metadata import version
import json
import os
import time

from .config import MODEL_DIR, MODEL_ID, REVISION
from .formatting import choice_request, format_request, tokenize_request, mapped_answer, payload_seed, InputTooLong

PINNED = {'torch': '2.13.0+cu129', 'transformers': '5.17.0', 'accelerate': '1.15.0'}
MAX_NEW_TOKENS = 8192
NATIVE_CONTEXT = 262144
SAMPLING = dict(temperature=0.6, top_p=0.95, top_k=20)


def official_module():
    spec = importlib.util.spec_from_file_location('pinned_tacit', MODEL_DIR / 'tacit_decision.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def close_thought(tokenizer, token_ids, max_tokens=MAX_NEW_TOKENS):
    raw = tokenizer.decode(token_ids, skip_special_tokens=False)
    thought = raw
    for eos in (tokenizer.eos_token or '', '<|im_end|>', '<|endoftext|>'):
        if eos and thought.endswith(eos):
            thought = thought[:-len(eos)]
    natural = '</think>' in thought
    reason = 'natural' if natural else ('length' if len(token_ids) >= max_tokens else 'eos')
    thought = thought[:thought.index('</think>') + len('</think>')] if natural else thought + '\n</think>'
    return dict(token_ids=token_ids, text=raw, closed_text=thought, finish_reason=reason,
                forced_close=not natural)


class OfficialModel:
    def __init__(self):
        self.directory = None
        self.loaded = False
        self.identity = None
        self.forward_calls = 0
        self.classifier = None

    def load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from .download import verify
        packages = {key: version(key) for key in PINNED}
        if packages != PINNED:
            raise RuntimeError(f'Tacit package identity mismatch: {packages}')
        receipt = verify()
        if self.directory is None or not (self.directory / f'gpu-acquire-{os.getpid()}.json').is_file():
            raise RuntimeError('Tacit requires owned GPU0 and serving directory')
        ownership = json.loads((self.directory / f'gpu-acquire-{os.getpid()}.json').read_text())
        if ownership['physical_gpus'] != [0] or torch.cuda.device_count() != 1:
            raise RuntimeError('Tacit requires physical GPU0 only')
        from integration.jev27b.resource import canonical_gpu_uuid
        expected_uuid = ownership['gpus']['0']['uuid']
        if (os.environ.get('CUDA_VISIBLE_DEVICES') != expected_uuid or
                canonical_gpu_uuid(torch.cuda.get_device_properties(0).uuid) != canonical_gpu_uuid(expected_uuid)):
            raise RuntimeError('Tacit GPU0 UUID does not match ownership')
        # Bypass optional-package/Hub dispatch, retaining the installed Torch reference functions.
        from transformers.models.qwen3_5 import modeling_qwen3_5 as gdn
        for name in ('torch_chunk_gated_delta_rule', 'torch_recurrent_gated_delta_rule',
                     'causal_conv1d_fn', 'causal_conv1d_update'):
            setattr(gdn, name, inspect.unwrap(getattr(gdn, name)))
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, dtype=torch.bfloat16,
            device_map='cuda', local_files_only=True, attn_implementation='sdpa', use_kernels=False).eval()
        official = official_module()
        self.classifier = official.Tacit(official._TransformersEngine(model, tokenizer), tokenizer,
            adaptive=False, max_cot_share=None, batch_size=1, cot_max_tokens=MAX_NEW_TOKENS, **SAMPLING)
        self.tokenizer = tokenizer
        if any(v.device.type != 'cuda' or v.device.index != 0 for v in model.parameters()):
            raise RuntimeError('model escaped single GPU0 placement')
        if any(v.dtype != torch.bfloat16 for v in model.parameters()):
            raise RuntimeError('model parameter dtype escaped BF16')
        text_config = model.config.get_text_config()
        if text_config.max_position_embeddings != NATIVE_CONTEXT:
            raise RuntimeError('native context identity mismatch')
        self.load_details = dict(packages=packages, model_class=type(model).__name__,
            tokenizer_class=type(tokenizer).__name__,
            model_parameter_dtypes=dict(Counter(str(v.dtype) for v in model.parameters())),
            attention='sdpa', gdn='torch-native', quantization=None, batch_size=1,
            thinking_mode='always', cot_max_tokens=MAX_NEW_TOKENS, sampling=SAMPLING)
        self.identity = hashlib.sha256(json.dumps(dict(revision=REVISION, files=receipt['files'],
            packages=packages, pid=os.getpid()), sort_keys=True).encode()).hexdigest()
        self.loaded = True
        self._allocator('loaded')
        return self

    def _allocator(self, phase):
        import torch
        sample = dict(at=time.time(), phase=phase, forward=self.forward_calls,
            allocated_bytes=torch.cuda.memory_allocated(0), reserved_bytes=torch.cuda.memory_reserved(0),
            peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(0))
        with (self.directory / f'allocator-{os.getpid()}.jsonl').open('a') as stream:
            stream.write(json.dumps(sample) + '\n')
        if max(sample[k] for k in ('allocated_bytes', 'reserved_bytes', 'peak_allocated_bytes',
                                  'peak_reserved_bytes')) > 40 * 1024**3:
            raise RuntimeError('Tacit allocator exceeded 40 GiB')

    def validate_input(self, payload):
        formatted = format_request(payload)
        return formatted, tokenize_request(self.tokenizer, formatted)

    def _journal(self, event):
        with (self.directory / 'tacit-forward.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(at=time.time(), forward=self.forward_calls, **event),
                                    ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def evaluate(self, payload):
        import torch
        formatted, encoded = self.validate_input(payload)
        tacit = self.classifier
        model = tacit.engine.model
        item = tacit._normalise(choice_request(payload))
        stages = {}
        stage = None
        expected = None
        initial = self.forward_calls
        seed = payload_seed(payload)
        def before_forward(_model, args, kwargs):
            ids = kwargs.get('input_ids', args[0] if args else None)
            tokens = ids.detach().cpu()[0].tolist()
            metrics = stages[stage]
            if metrics['forward_calls'] == 0 and tokens != expected:
                raise ValueError('official forward tokens differ from CPU guard')
            self.forward_calls += 1
            metrics['forward_calls'] += 1
            metrics['processed_input_tokens'] += len(tokens)
            self._journal(dict(type='forward_started', stage=stage, seed=seed,
                input_tokens=len(tokens), prompt_sha256=formatted.prompt_sha256,
                input_ids_sha256=hashlib.sha256(json.dumps(tokens).encode()).hexdigest()))
        def begin(name, ids):
            nonlocal stage, expected
            stage, expected = name, ids
            stages[name] = dict(input_tokens=len(ids), processed_input_tokens=0, forward_calls=0)
            return time.perf_counter()
        def end(started):
            torch.cuda.synchronize()
            stages[stage]['seconds'] = time.perf_counter() - started
        hook = model.register_forward_pre_hook(before_forward, with_kwargs=True)
        try:
            started = begin('first_pass', encoded['input_ids'])
            first_lp = tacit.engine.read([encoded['first_prompt']],
                [tacit._label_ids(item['labels'], spaced_first=False)])[0]
            first = tacit._result(item, first_lp, 'one_forward')
            end(started)
            self._journal(dict(type='first_pass', response=first, seed=seed, stages=stages))
            self._allocator('first_pass')
            prompt = encoded['thinking_prompt']
            started = begin('thinking', encoded['thinking_input_ids'])
            enc = self.tokenizer(prompt, return_tensors='pt', add_special_tokens=False).to(model.device)
            with torch.no_grad(), torch.random.fork_rng(devices=[0]):
                torch.manual_seed(seed)
                generated = model.generate(**enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=True,
                    stop_strings=['</think>'], tokenizer=self.tokenizer,
                    pad_token_id=self.tokenizer.pad_token_id, **SAMPLING)
            tokens = generated[0, enc['input_ids'].shape[1]:].detach().cpu().tolist()
            thinking = dict(close_thought(self.tokenizer, tokens), seed=seed)
            end(started)
            self._journal(dict(type='thinking', response=thinking, stages=stages))
            self._allocator('thinking')
            # Preserve the official Transformers decode -> close -> reencode semantics.
            read_prompt = prompt + thinking['closed_text'] + '\n\nAnswer:'
            read_ids = self.tokenizer.encode(read_prompt, add_special_tokens=False)
            if len(read_ids) > NATIVE_CONTEXT:
                raise InputTooLong(len(read_ids), NATIVE_CONTEXT)
            started = begin('final_read', read_ids)
            final_lp = tacit.engine.read([read_prompt],
                [tacit._label_ids(item['labels'], spaced_first=True)])[0]
            official = tacit._result(item, final_lp, 'cot', first_pass=first, reasoning_tokens=len(tokens))
            end(started)
            self._journal(dict(type='official_response', response=official, stages=stages))
            self._allocator('final_read')
        except BaseException as error:
            self._journal(dict(type='forward_failure', stage=stage,
                error=dict(type=type(error).__name__, detail=str(error))))
            raise
        finally:
            hook.remove()
        return dict(model=MODEL_ID, answers={formatted.question_name: mapped_answer(formatted, official)},
            first_pass=mapped_answer(formatted, first), official_response=official,
            official_request=choice_request(payload), thinking=thinking, stages=stages,
            original_input_tokens=dict(first_pass=len(encoded['input_ids']), thinking=len(encoded['thinking_input_ids'])),
            physical_forward_calls=self.forward_calls-initial,
            usage=dict(input_tokens=sum(v['input_tokens'] for v in stages.values()), output_tokens=len(tokens)),
            processed_input_tokens=sum(v['processed_input_tokens'] for v in stages.values()),
            metadata=self.metadata())

    def metadata(self):
        return dict(model=MODEL_ID, revision=REVISION, loaded=self.loaded, serving_identity=self.identity,
            backend='transformers-official', activation_dtype='bfloat16', physical_gpus=[0],
            max_input_tokens=32768, max_context_tokens=NATIVE_CONTEXT, forward_calls=self.forward_calls,
            thinking_mode='always', cot_max_tokens=MAX_NEW_TOKENS, sampling=SAMPLING,
            load_details=getattr(self, 'load_details', None))

    def close(self):
        self.loaded = False
        self.classifier = None
