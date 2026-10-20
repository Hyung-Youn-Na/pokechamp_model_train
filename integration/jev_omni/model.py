"""Pinned official BF16 classifier with owned single-forward evidence."""
from collections import Counter
import hashlib
import importlib.util
from importlib.metadata import version
import json
import os
import time

from .config import MODEL_DIR, MODEL_ID, REVISION
from .formatting import choice_request, format_request, tokenize_request, mapped_response

PINNED = {'torch': '2.13.0+cu129', 'torchvision': '0.28.0+cu129',
          'transformers': '5.17.0', 'accelerate': '1.15.0'}


def official_module():
    spec = importlib.util.spec_from_file_location('pinned_jev_omni', MODEL_DIR / 'jev_omni.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OfficialModel:
    def __init__(self):
        self.directory = None
        self.loaded = False
        self.identity = None
        self.forward_calls = 0
        self.classifier = None

    def load(self):
        import torch
        import transformers
        from .download import verify
        packages = {key: version(key) for key in PINNED}
        if packages != PINNED:
            raise RuntimeError(f'Omni package identity mismatch: {packages}')
        receipt = verify()
        if self.directory is None or not (self.directory / f'gpu-acquire-{os.getpid()}.json').is_file():
            raise RuntimeError('Omni requires owned GPU0 and serving directory')
        ownership = json.loads((self.directory / f'gpu-acquire-{os.getpid()}.json').read_text())
        if ownership['physical_gpus'] != [0] or torch.cuda.device_count() != 1:
            raise RuntimeError('Omni requires physical GPU0 only')
        official = official_module()
        config = transformers.AutoConfig.from_pretrained(MODEL_DIR, local_files_only=True)
        model = getattr(transformers, config.architectures[0]).from_pretrained(
            MODEL_DIR, dtype=torch.bfloat16, device_map='cuda', local_files_only=True).eval()
        decision = json.loads((MODEL_DIR / 'decision_config.json').read_text())
        if decision['hidden_size'] != 3840 or decision['output_classes'] != 256:
            raise ValueError('unexpected head identity')
        head = official._Head256(decision['hidden_size']).to('cuda').eval()
        head.load_state_dict(torch.load(MODEL_DIR / 'head.pt', map_location='cuda', weights_only=True))
        backbone_path, decoder = official._find_backbone(model)
        self.processor = transformers.AutoProcessor.from_pretrained(MODEL_DIR, local_files_only=True)
        self.classifier = official.JevOmni(model, head, self.processor, decoder, 'cuda')
        if any(v.device.type != 'cuda' or v.device.index != 0 for v in model.parameters()):
            raise RuntimeError('model escaped single GPU0 placement')
        self.load_details = dict(packages=packages, model_class=type(model).__name__,
            processor_class=type(self.processor).__name__, backbone_path=backbone_path,
            model_parameter_dtypes=dict(Counter(str(v.dtype) for v in model.parameters())),
            head_tensor_dtypes=dict(Counter(str(v.dtype) for v in head.state_dict().values())),
            classifier_extra=dict(self.classifier._extra), media_used=False, quantization=None,
            batch_size=1, use_cache=False, enable_thinking=False)
        self.identity = hashlib.sha256(json.dumps(dict(revision=REVISION, files=receipt['files'],
            packages=packages, pid=os.getpid()), sort_keys=True).encode()).hexdigest()
        self.loaded = True
        self._allocator("loaded")
        return self

    def _allocator(self, phase):
        import torch
        sample = dict(at=time.time(), phase=phase, forward=self.forward_calls,
                      allocated_bytes=torch.cuda.memory_allocated(0),
                      reserved_bytes=torch.cuda.memory_reserved(0),
                      peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
                      peak_reserved_bytes=torch.cuda.max_memory_reserved(0))
        with (self.directory / f'allocator-{os.getpid()}.jsonl').open('a') as stream:
            stream.write(json.dumps(sample) + '\n')
        if max(sample[k] for k in ('allocated_bytes', 'reserved_bytes',
                                   'peak_allocated_bytes', 'peak_reserved_bytes')) > 40 * 1024**3:
            raise RuntimeError('Omni allocator exceeded 40 GiB')

    def validate_input(self, payload):
        formatted = format_request(payload)
        return formatted, tokenize_request(self.processor, formatted)

    def _journal(self, event):
        with (self.directory / 'omni-forward.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(at=time.time(), forward=self.forward_calls, **event),
                                   ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def evaluate(self, payload):
        formatted, encoded = self.validate_input(payload)
        request = choice_request(payload)
        model = self.classifier.model
        def before_forward(_model, args, kwargs):
            ids = kwargs['input_ids'].detach().cpu()[0].tolist()
            if ids != encoded['input_ids']:
                raise ValueError('official forward tokens differ from CPU guard')
            self.forward_calls += 1
            self._journal(dict(type='forward_started', input_tokens=len(ids),
                prompt_sha256=formatted.prompt_sha256,
                input_ids_sha256=hashlib.sha256(json.dumps(ids).encode()).hexdigest()))
        hook = model.register_forward_pre_hook(before_forward, with_kwargs=True)
        initial = self.forward_calls
        try:
            official = self.classifier.predict(**request)
            self._journal(dict(type='official_response', response=official))
        except BaseException as error:
            self._journal(dict(type='forward_failure', error=dict(type=type(error).__name__, detail=str(error))))
            raise
        finally:
            hook.remove()
            self._allocator("after_forward")
        if self.forward_calls != initial + 1:
            raise RuntimeError('official classifier did not perform exactly one forward')
        result = mapped_response(payload, official, len(encoded['input_ids']))
        result['official_request'] = request
        result['metadata'] = self.metadata()
        return result

    def metadata(self):
        return dict(model=MODEL_ID, revision=REVISION, loaded=self.loaded, serving_identity=self.identity,
                    backend='transformers-official', activation_dtype='bfloat16', head_slots=256,
                    physical_gpus=[0], max_input_tokens=32768, forward_calls=self.forward_calls,
                    load_details=getattr(self, 'load_details', None))

    def close(self):
        self.loaded = False
        self.classifier = None
