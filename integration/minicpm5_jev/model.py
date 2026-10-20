"""Strict pinned official MiniCPM backbone/LoRA/head with the EX-091 formatter."""
from collections import Counter
from functools import lru_cache
import hashlib
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import time

from integration.jev27b.model import Jev27BModel, ModelIntegrityError, PINNED_PACKAGES, sha256_file
from integration.jev27b.storage import digest
from .config import (BASE_MODEL_ID, BASE_REVISION, CHOICE_TEMPERATURE, EVIDENCE, HEAD_SHAPE,
                     MAX_TOKENS, MODEL_DIR, MODEL_ID, NUM_LAYERS, REVISION)
from .download import verify_receipt
from .formatting import (FORMAT_VERSION, answer_from_probabilities, decision_metadata,
                         format_request, tokenize_request)

HEAD_FIELDS = dict(letter_weight=HEAD_SHAPE, letter_bias=(255,), choice_k_bias=(33, 32),
                   score_k_bias=(33, 32), noul_bias=(2,), score_bias=(11,), type_temps=(3,))
TYPE_TEMPERATURES = dict(choice=1.1314, noul=1.2338, score=0.4213)
MODEL_PACKAGES = dict(PINNED_PACKAGES, tokenizers='0.23.2')


def reject_overrides(environment=None):
    environment = os.environ if environment is None else environment
    names = sorted(key for key in environment if key.startswith('MINICPM_S1_'))
    if names:
        raise ModelIntegrityError('MiniCPM environment overrides are not allowed: ' + ', '.join(names))


@lru_cache(maxsize=4)
def official_module(path):
    """Import only the previously hash-verified revision; no server entry point runs."""
    spec = importlib.util.spec_from_file_location('_ex091_official_minicpm', str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_head(head, torch):
    expected = dict(base_model=BASE_MODEL_ID, lora_r=16, lora_targets='all', top_k_layers=0,
                    head_dim=256, readout='native_lm_head_letters_pride',
                    temperature=CHOICE_TEMPERATURE, type_temperatures=TYPE_TEMPERATURES)
    if not isinstance(head, dict) or any(head.get(key) != value for key, value in expected.items()):
        raise ModelIntegrityError('pinned MiniCPM head metadata or calibration differs')
    state = head.get('state_dict')
    if not isinstance(state, dict) or set(state) != set(HEAD_FIELDS):
        raise ModelIntegrityError('MiniCPM head state keys differ; missing heads are forbidden')
    for name, shape in HEAD_FIELDS.items():
        value = state[name]
        if (not isinstance(value, torch.Tensor) or tuple(value.shape) != shape
                or value.dtype != torch.float32 or not bool(torch.isfinite(value).all())):
            raise ModelIntegrityError('MiniCPM head shape/dtype/finite check failed: ' + name)
    expected_temps = torch.tensor(list(TYPE_TEMPERATURES.values()), dtype=torch.float32)
    if not torch.equal(state['type_temps'].cpu(), expected_temps):
        raise ModelIntegrityError('saved per-type head temperatures differ')
    return state


def adapter_shapes():
    shapes = {}
    projections = dict(q_proj=('self_attn', 2048, 2048), k_proj=('self_attn', 2048, 256),
        v_proj=('self_attn', 2048, 256), o_proj=('self_attn', 2048, 2048),
        gate_proj=('mlp', 2048, 6144), up_proj=('mlp', 2048, 6144), down_proj=('mlp', 6144, 2048))
    for layer in range(NUM_LAYERS):
        for name, (group, inputs, outputs) in projections.items():
            prefix = f'base_model.model.layers.{layer}.{group}.{name}'
            shapes[prefix + '.lora_A.weight'] = (16, inputs)
            shapes[prefix + '.lora_B.weight'] = (outputs, 16)
    return shapes


class MiniCPMJevModel(Jev27BModel):
    model_id, revision = MODEL_ID, REVISION
    head_shape = HEAD_SHAPE
    choice_temperature = CHOICE_TEMPERATURE
    format_version = FORMAT_VERSION
    allowed_profiles = ('ex091',)
    device_map_factory = staticmethod(lambda profile: {'lm': 0, 'head': 0})

    def __init__(self, model_dir=MODEL_DIR, *, max_tokens=MAX_TOKENS, profile='ex091', evidence_dir=EVIDENCE):
        self.evidence_dir = Path(evidence_dir)
        super().__init__(model_dir, max_tokens=max_tokens, profile=profile)

    def _verify_model_files(self):
        reject_overrides()
        try:
            receipt = verify_receipt(self.model_dir, self.evidence_dir)
            config = json.loads((self.model_dir / 'base/config.json').read_text())
            expected = dict(model_type='llama', hidden_size=2048, num_hidden_layers=42,
                intermediate_size=6144, num_attention_heads=16, num_key_value_heads=2,
                head_dim=128, vocab_size=130560, tie_word_embeddings=False, max_position_embeddings=131072)
            if any(config.get(key) != value for key, value in expected.items()):
                raise ValueError('MiniCPM backbone configuration differs')
            adapter = json.loads((self.model_dir / 'adapter_config.json').read_text())
            if (adapter['base_model_name_or_path'] != BASE_MODEL_ID or adapter['peft_type'] != 'LORA'
                    or adapter['task_type'] != 'FEATURE_EXTRACTION' or adapter['r'] != 16
                    or adapter['lora_alpha'] != 32 or adapter['lora_dropout'] != 0
                    or adapter['layers_to_transform'] is not None or adapter['modules_to_save'] is not None
                    or set(adapter['target_modules']) != {'q_proj', 'k_proj', 'v_proj', 'o_proj',
                                                          'gate_proj', 'up_proj', 'down_proj'}):
                raise ValueError('MiniCPM adapter configuration differs')
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ModelIntegrityError('MiniCPM verified bundle identity failed: ' + str(error)) from error
        self.verification = dict(mode=receipt['verification'],
            receipt_sha256=sha256_file(self.evidence_dir / 'download.json'),
            model_directory=str(self.model_dir), files=len(receipt['files']), bytes=receipt['bytes'])
        return {row['path']: row['sha256'] for row in receipt['files']}

    def cpu_ready(self):
        """Validate the complete head/adapter and label rows without loading a backbone."""
        files = self._verify_model_files()
        import torch
        from safetensors import safe_open
        from transformers import AutoTokenizer
        packages = {name: version(name) for name in MODEL_PACKAGES}
        if any(packages[name].split('+')[0] != expected for name, expected in MODEL_PACKAGES.items()):
            raise ModelIntegrityError('existing JEV model environment differs from pinned versions')
        head = torch.load(self.model_dir / 'head.pt', map_location='cpu', weights_only=True)
        state = validate_head(head, torch)
        checkpoint = json.loads((self.model_dir / 'checkpoint_meta.json').read_text())
        if any(head[key] != checkpoint[key] for key in ('base_model', 'lora_r', 'lora_targets',
                'top_k_layers', 'head_dim', 'readout', 'temperature', 'type_temperatures')):
            raise ModelIntegrityError('head.pt and checkpoint metadata differ')
        tokenizer = AutoTokenizer.from_pretrained(self.model_dir / 'base', local_files_only=True,
                                                  trust_remote_code=False)
        meta = decision_metadata(tokenizer)
        official = official_module(self.model_dir / 'model.py')
        native_meta = official.tokenizer_decision_meta(tokenizer)
        if any(meta[key] != native_meta[key] for key in meta):
            raise ModelIntegrityError('official tokenizer labels or wrapper token IDs differ')
        index = json.loads((self.model_dir / 'base/model.safetensors.index.json').read_text())
        shard = self.model_dir / 'base' / index['weight_map']['lm_head.weight']
        with safe_open(str(shard), framework='pt', device='cpu', backend='pread') as reader:
            projection = reader.get_slice('lm_head.weight')
            if projection.get_shape() != [130560, HEAD_SHAPE[1]]:
                raise ModelIntegrityError('base vocabulary projection shape differs')
            native_rows = torch.cat([projection[i:i + 1, :] for i in meta['label_ids']]).float()
        if not torch.equal(native_rows, state['letter_weight']):
            raise ModelIntegrityError('255 saved head rows do not match native label-token rows')
        shapes = adapter_shapes()
        with safe_open(str(self.model_dir / 'adapter_model.safetensors'), framework='pt', device='cpu') as reader:
            if set(reader.keys()) != set(shapes):
                raise ModelIntegrityError('adapter key inventory differs')
            for key, shape in shapes.items():
                value = reader.get_tensor(key)
                if (tuple(value.shape) != shape or value.dtype != torch.float32
                        or not bool(torch.isfinite(value).all())):
                    raise ModelIntegrityError('adapter shape/dtype/finite check failed: ' + key)
        native_head = official.LetterReadoutHead(state['letter_weight'])
        native_head.load_state_dict(state, strict=True)
        self._head_data = head
        self._label_meta = meta
        ready = dict(passed=True, model=self.model_id, revision=self.revision,
            base_model=BASE_MODEL_ID, base_revision=BASE_REVISION, file_identity=files,
            model_verification=self.verification, packages=packages, head_shape=list(HEAD_SHAPE),
            head_dtype='torch.float32', choice_temperature=float(state['type_temps'][0]),
            fallback_temperature=head['temperature'], prior_enabled=True,
            choice_k_prior_nonzero={str(k): int(torch.count_nonzero(state['choice_k_bias'][k, :k]))
                                    for k in range(2, 17)},
            label_names=meta['label_names'], label_token_ids=meta['label_ids'],
            native_head_rows_equal=True, adapter_keys=len(shapes), adapter='unmerged',
            environment_reinstalled=False, backbone_loaded=False,
            cuda_initialized=torch.cuda.is_initialized(), gpu_inferences=0)
        return ready, tokenizer

    def _source_hashes(self):
        names = ('model.py', 'formatting.py', 'config.py', 'download.py', 'official-files.json')
        return {'minicpm5_jev/' + name: sha256_file(Path(__file__).with_name(name)) for name in names}

    def load(self):
        if self.loaded:
            return self
        ready, self.tokenizer = self.cpu_ready()
        import torch
        from peft import PeftModel, get_peft_model_state_dict
        from safetensors import safe_open
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise ModelIntegrityError('exactly the owned GPU0 must be visible')
        self._torch = torch
        torch.cuda.set_device(0)
        torch.manual_seed(0)
        torch.cuda.manual_seed_all(0)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.set_float32_matmul_precision('highest')
        torch.use_deterministic_algorithms(True)
        official = official_module(self.model_dir / 'model.py')
        # The official constructor copies the native label rows, keeps PEFT LoRA
        # unmerged, and runs the BF16 Llama backbone with SDPA and no KV cache.
        self.model = official.MiniCPMSystemOne(base_model=str(self.model_dir / 'base'),
            tok=self.tokenizer, device='cuda:0', lora_r=16, head_dim=256, dtype=torch.bfloat16,
            adapter_dir=self.model_dir, lora_targets='all', top_k_layers=0, grad_ckpt=False)
        self.model.head.load_state_dict(self._head_data['state_dict'], strict=True)
        self.model.head.temperature = self._head_data['temperature']
        self.model.head.use_prior = True
        self.model.eval()
        self.model.requires_grad_(False)
        if not isinstance(self.model.lm, PeftModel):
            raise ModelIntegrityError('official unmerged LoRA model is missing')
        if any(getattr(module, 'merged_adapters', []) for module in self.model.lm.modules()):
            raise ModelIntegrityError('MiniCPM LoRA must remain unmerged')
        actual_adapter = get_peft_model_state_dict(self.model.lm)
        if set(actual_adapter) != set(adapter_shapes()):
            raise ModelIntegrityError('loaded adapter key inventory differs')
        with safe_open(str(self.model_dir / 'adapter_model.safetensors'), framework='pt', device='cpu') as reader:
            if any(not torch.equal(value.detach().cpu(), reader.get_tensor(key))
                   for key, value in actual_adapter.items()):
                raise ModelIntegrityError('loaded LoRA weights differ from the verified file')
        for name, value in list(self.model.named_parameters()) + list(self.model.named_buffers()):
            if value.device.type != 'cuda' or value.device.index != 0:
                raise ModelIntegrityError('MiniCPM tensor is outside GPU0: ' + name)
        for name, value in self.model.lm.named_parameters():
            expected_dtype = torch.float32 if 'lora_' in name else torch.bfloat16
            if value.dtype != expected_dtype:
                raise ModelIntegrityError('official backbone/adapter dtype differs: ' + name)
        if any(value.dtype != torch.float32 for value in self.model.head.buffers()):
            raise ModelIntegrityError('MiniCPM decision head must remain FP32')
        if self.model.head.training or not self.model.head.use_prior:
            raise ModelIntegrityError('saved prior calibration is not active')
        serving = dict(runtime_profile=self.profile.name, physical_gpus=[0],
            allocator_limit_bytes=self.profile.allocator_bytes, nvml_gpu_limit_bytes=self.profile.gpu_bytes,
            host_limit_bytes=self.profile.host_bytes, disk_limit_bytes=self.profile.disk_bytes,
            decision_head_device='cuda:0', tensor_placement_verified=True,
            format=FORMAT_VERSION, max_input_tokens=MAX_TOKENS, max_options=16,
            native_max_position_embeddings=131072, truncation=False, add_special_tokens=False, batch_size=1,
            backbone_dtype='bfloat16', head_dtype='float32', adapter='unmerged', adapter_dtype='float32',
            head_choice_slots=[0, 16], decision_head_shape=list(HEAD_SHAPE),
            label_names=self._label_meta['label_names'], label_token_ids=self._label_meta['label_ids'],
            temperature=ready['choice_temperature'], fallback_temperature=self._head_data['temperature'],
            prior_enabled=True, choice_k_prior_nonzero=ready['choice_k_prior_nonzero'],
            candidate_rotation_pride=False, date_facts=False, default_server_preprocessing_reproduced=False,
            quantization=None, offload=None, use_cache=False, output_hidden_states=False,
            readout='official-final-token-letter-head', attention='sdpa-flash-only',
            tf32=False, deterministic_algorithms=True, seed=0,
            cublas_workspace_config=os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
            cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'), torch_cuda_version=torch.version.cuda,
            parameter_dtypes=dict(Counter(str(p.dtype) for p in self.model.parameters())),
            source_sha256=self._source_hashes())
        self._metadata = dict(model=self.model_id, revision=self.revision,
            base_model=BASE_MODEL_ID, base_revision=BASE_REVISION, loaded=True,
            model_files_sha256=ready['file_identity'], packages=ready['packages'],
            device_map={'lm': 0, 'head': 0}, serving_config=serving,
            model_verification=self.verification, decision_head_shape=list(HEAD_SHAPE))
        encoded = json.dumps(self._metadata, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode()
        self._metadata['serving_identity'] = hashlib.sha256(encoded).hexdigest()
        self.loaded = True
        del actual_adapter
        self._check_memory()
        return self

    def validate_input(self, payload):
        if not self.loaded:
            raise ModelIntegrityError('load the model before evaluation')
        tokenize_request(self.tokenizer, format_request(payload), self.max_tokens)

    def evaluate(self, payload):
        if not self.loaded:
            raise ModelIntegrityError('load the model before evaluation')
        formatted = format_request(payload)
        encoded = tokenize_request(self.tokenizer, formatted, self.max_tokens)
        row = dict(causal_rows=[encoded['input_ids']], state_ids=[],
                   n_opts=[len(formatted.candidate_ids)], q_types=['choice'])
        torch = self._torch
        from torch.nn.attention import SDPBackend, sdpa_kernel
        started = time.monotonic()
        with torch.inference_mode(), sdpa_kernel([SDPBackend.FLASH_ATTENTION]):
            # Exactly one official causal row; no predict_record preprocessing,
            # candidate rotation, date augmentation, or vocabulary decoding.
            (logits, probabilities), = self.model.logits_and_probs(row)
        values = probabilities.tolist()
        if not bool(torch.isfinite(logits).all()):
            raise ModelIntegrityError('nonfinite MiniCPM native head logits')
        answer = answer_from_probabilities(formatted, values)
        self._check_memory()
        return dict(model=self.model_id, answers={formatted.question_name: answer},
            usage=dict(input_tokens=len(encoded['input_ids']), output_tokens=0),
            metadata=dict(revision=self.revision, serving_identity=self._metadata['serving_identity'],
                format=FORMAT_VERSION, prompt_sha256=formatted.prompt_sha256,
                input_ids_sha256=digest(encoded['input_ids']), candidate_ids=list(formatted.candidate_ids),
                elapsed_seconds=time.monotonic() - started, **self._resource()))
