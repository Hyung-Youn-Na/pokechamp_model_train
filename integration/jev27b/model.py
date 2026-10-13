"""Pinned JEV-27B Transformers System 1 loader; no GPU work at module import.

Official inference recipe:
https://huggingface.co/autotrust/JEV-27B/blob/51740a8891c2a8baefd969237fd44187b3e3a115/README.md
The caller owns the selected profile's GPU locks, limits, and isolated environment.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import copy
import hashlib
from importlib.metadata import PackageNotFoundError, version
import inspect
import json
import os
from pathlib import Path
import time
from typing import Any

from .config import runtime_profile
from .formatting import (FORMAT_VERSION, MAX_TOKENS, answer_from_probabilities,
                         format_request, tokenize_request)

MODEL_ID = "autotrust/JEV-27B"
REVISION = "51740a8891c2a8baefd969237fd44187b3e3a115"
CHOICE_TEMPERATURE = 1.0161280671450397
GPU_LIMIT_BYTES = 44 * 1024 ** 3
PINNED_PACKAGES = {
    "torch": "2.8.0", "transformers": "5.17.0", "accelerate": "1.15.0", "peft": "0.21.0",
    "flash-linear-attention": "0.5.2", "fla-core": "0.5.2", "causal-conv1d": "1.7.0",
    "triton": "3.4.0", "safetensors": "0.8.0",
}
# LFS SHA256 values come from the pinned Hub tree; small-file SHA256 values were
# calculated from that revision's raw bytes. Verify before trusting local model identity.
MODEL_FILES_SHA256 = {
    "config.json": "5a1c114fa93e7c2cdc262732ad831f786022fef86041f0c551576f9c3faff017",
    "judge_config.json": "372748b6c876e008ad05ecfb3a361f481e85444eaa083b31234dbded5c2f7cb1",
    "calibration.json": "902f4f26fdf1b92224c32b706ee6cea381f6465621c82975bf7e0023c02d9dd2",
    "adapter/adapter_config.json": "eb550297441bde5ab9d78678e50aa8ed3f28a87912435c8da3d97cd3c82280c7",
    "adapter/adapter_model.safetensors": "7bdb88d73895931d3cfc55ba95766f45df50f244f631d8fe55255f67ec0b6569",
    "head.safetensors": "8256776bac46e653a3e126ab4e8d5e6d0eed73e7fa6f1e55306083607e44753d",
    "tokenizer.json": "06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523",
    "tokenizer_config.json": "66e427c470fe580fe8c7b5725d857af23d8417e37fae62667ec698306a19987b",
    "model.safetensors.index.json": "ec488a70bc7aff67524bdd2cec46e1579a5d34643a22c4a800883dbf03d2d8eb",
    "model-00001-of-00013.safetensors": "db2b7b40984acce0aba155c5d662c962c8be3a343c286902f04067b832eb1cb6",
    "model-00002-of-00013.safetensors": "d619ecfeb02568617e304b9e2220d8445f9133a878042400828521f5e223a9c4",
    "model-00003-of-00013.safetensors": "60adcb827a302f0e7aacccc0bd0840d894c221671248a594514745c53ad5d6ac",
    "model-00004-of-00013.safetensors": "62aef67ee25767082503d0fade7c432c1d9425206d0824e9a812af5b9148948e",
    "model-00005-of-00013.safetensors": "f2f0d54be97d1d5f852cb84c59598d6de3126be2de63587a81c4f50dac46867d",
    "model-00006-of-00013.safetensors": "e6f48774997760439d70c6bd6242c5ecf130d9edf0bac2ac558180f57f385846",
    "model-00007-of-00013.safetensors": "a5545d3e075a0c77b3d7c5538de8df0df150f0fe859b4dd7a5f708ff7d5d15a0",
    "model-00008-of-00013.safetensors": "62aee5ddd323e4390c084e46a3c20bbf98919cc52443136e6f75c099cb2b6d44",
    "model-00009-of-00013.safetensors": "9bb707f2841fef0be82f44074ed8e42922782635f9f8c4b430ccee882d51c175",
    "model-00010-of-00013.safetensors": "0f6761163164a3c6315b139e408934db4201caf89d9eed2f297e0f7b693b59d6",
    "model-00011-of-00013.safetensors": "e188b8858675dc9ed116967af43c912cc3dedabf2592851e2901e3b7f86f8938",
    "model-00012-of-00013.safetensors": "2e9dca8bb19513668aa2972e7c6453395b0145f1a3693fa17120d36e8f986f66",
    "model-00013-of-00013.safetensors": "68bbd88d686dfe82e0e98277c6e5a5f5fa0eabbbeea858eb5e8508e2fba2858a",
}


class ModelIntegrityError(RuntimeError):
    """Pinned source, environment, placement, or numerical integrity failed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 ** 2), b""):
            digest.update(block)
    return digest.hexdigest()


def fixed_device_map(profile='ex082') -> dict[str, int]:
    """Balance 64 intact decoder layers and the two large embedding matrices."""
    settings = runtime_profile(profile)
    if settings.name == 'ex083':
        return {"model.embed_tokens": 0, "model.rotary_emb": 0, "model.norm": 3, "lm_head": 3,
                **{f"model.layers.{i}": 0 if i < 14 else 1 if i < 32 else 2 if i < 50 else 3
                   for i in range(64)}}
    return {"model.embed_tokens": 0, "model.rotary_emb": 0, "model.norm": 1, "lm_head": 1,
            **{f"model.layers.{i}": 0 if i < 32 else 1 for i in range(64)}}


def _check_placement(model, device_map):
    """Verify actual tensors at every module boundary, including all decoder layers."""
    tensors = list(model.named_parameters()) + list(model.named_buffers())
    if not tensors:
        raise ModelIntegrityError('loaded model has no tensors')
    for name, value in tensors:
        matches = [prefix for prefix in device_map if name == prefix or name.startswith(prefix + '.')]
        if not matches:
            raise ModelIntegrityError(f'unmapped model tensor: {name}')
        expected = device_map[max(matches, key=len)]
        if value.device.type != 'cuda' or value.device.index != expected:
            raise ModelIntegrityError(f'wrong tensor placement: {name} is {value.device}, expected cuda:{expected}')


def _deterministic_autotune() -> None:
    # FLA's timing-selected Triton launch configs changed outputs across reloads in
    # EX-080. Keep the first working config in declared order in this process only.
    # This preserves the official FLA algorithm and freezes its launch choice.
    import math
    from triton.runtime import autotuner
    if getattr(autotuner.Autotuner, "_ex082_deterministic", False):
        return
    measured = autotuner.Autotuner._bench

    def ordered(self, *args, config, **meta):
        timings = measured(self, *args, config=config, **meta)
        if any(math.isinf(t) for t in timings):
            return timings
        order = next((i for i, candidate in enumerate(self.configs)
                      if candidate is config or str(candidate) == str(config)), len(self.configs))
        return [float(order)] * len(timings)

    autotuner.Autotuner._bench = ordered
    autotuner.Autotuner._ex082_deterministic = True


def _kernel_implementations() -> dict[str, str]:
    """Refuse Transformers' implicit reference fallback if an extension failed import."""
    from transformers.models.qwen3_5 import modeling_qwen3_5 as qwen
    actual = {}
    for name, prefix in (("torch_chunk_gated_delta_rule", "fla."),
                         ("torch_recurrent_gated_delta_rule", "fla."),
                         ("causal_conv1d_fn", "causal_conv1d."),
                         ("causal_conv1d_update", "causal_conv1d.")):
        bindings = inspect.getclosurevars(getattr(qwen, name)).nonlocals
        implementation = bindings.get("implementation")
        module = getattr(implementation, "__module__", "")
        if not bindings.get("is_new_implementation") or not module.startswith(prefix):
            raise ModelIntegrityError(f"pinned optimized kernel unavailable: {name}")
        actual[name] = f"{module}.{implementation.__name__}"
    return actual


@contextmanager
def _sequential_pread_checkpoint_io():
    """Keep Transformers' loader while bounding resident checkpoint staging.

    Transformers 5.17 keeps every shard's safe_open alive until conversion finishes.
    Its Linux mmap backend can therefore retain the full 50 GiB checkpoint in RSS.
    safetensors 0.8's pread backend owns a file descriptor and materializes only the
    requested tensor; synchronous conversion bounds staging to that tensor. This
    temporary process-local override changes byte transport, not tensor conversion,
    GPU placement, model weights, or the installed Transformers package.
    """
    from safetensors import safe_open
    from transformers import modeling_utils
    original = modeling_utils.safe_open
    if original is not safe_open:
        raise ModelIntegrityError("unexpected existing checkpoint reader override")
    previous_async = os.environ.get("HF_DEACTIVATE_ASYNC_LOAD")

    def pread_open(filename, *args, **kwargs):
        kwargs["backend"] = "pread"
        return safe_open(filename, *args, **kwargs)

    modeling_utils.safe_open = pread_open
    os.environ["HF_DEACTIVATE_ASYNC_LOAD"] = "1"
    try:
        yield
    finally:
        modeling_utils.safe_open = original
        if previous_async is None:
            os.environ.pop("HF_DEACTIVATE_ASYNC_LOAD", None)
        else:
            os.environ["HF_DEACTIVATE_ASYNC_LOAD"] = previous_async


def _check_finite_parameters(model, torch) -> None:
    """Check merged weights with at most 2**20 elements per temporary bool mask."""
    for name, parameter in model.named_parameters():
        value = parameter.detach()
        # Split existing storage views, avoiding reshape/contiguous copies of the
        # 2.37 GiB embedding matrices or any other complete parameter.
        if value.ndim == 0:
            chunks = (value,)
        else:
            elements_per_row = max(1, value.numel() // value.shape[0])
            chunks = value.split(max(1, 2 ** 20 // elements_per_row), dim=0)
        for chunk in chunks:
            if not bool(torch.isfinite(chunk).all()):
                raise ModelIntegrityError(f"nonfinite merged parameter: {name}")


class Jev27BModel:
    """Explicitly load once per process, then run one uncached Choice prefill at a time."""

    def __init__(self, model_dir: str | Path, *, max_tokens: int = MAX_TOKENS, profile='ex082'):
        self.profile = runtime_profile(profile)
        self.devices = tuple(range(len(self.profile.physical_gpus)))
        if max_tokens != MAX_TOKENS:
            raise ValueError("JEV-27B freezes the input limit at 32768 tokens")
        self.model_dir = Path(model_dir).resolve()
        self.max_tokens = max_tokens
        self.loaded = False
        self._metadata: dict[str, Any] = {"model": MODEL_ID, "revision": REVISION,
                                          "loaded": False, "serving_identity": None}

    def load(self) -> Jev27BModel:
        if self.loaded:
            return self
        packages = {}
        for name, expected in PINNED_PACKAGES.items():
            try:
                packages[name] = version(name)
            except PackageNotFoundError as error:
                raise ModelIntegrityError(f"missing pinned package {name}") from error
            if packages[name].split("+")[0] != expected:
                raise ModelIntegrityError(f"{name} is {packages[name]}, expected {expected}")
        try:
            version("kernels")
        except PackageNotFoundError:
            packages["kernels"] = None
        else:
            raise ModelIntegrityError("Hub kernels are not part of the frozen FLA/causal-conv1d backend")
        for name, expected in MODEL_FILES_SHA256.items():
            path = self.model_dir / name
            if not path.is_file() or sha256_file(path) != expected:
                raise ModelIntegrityError(f"pinned model file mismatch: {name}")
        # The caller may already have imported Torch to establish its allocation cap.
        # All modifications here affect only this owned server process.
        os.environ.setdefault("TORCHINDUCTOR_COMPILE_THREADS", "1")
        import torch
        from peft import PeftModel
        from safetensors.torch import load_file
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if not torch.cuda.is_available() or torch.cuda.device_count() != len(self.devices):
            raise ModelIntegrityError("exactly the profile's owned GPUs must be visible")
        torch.cuda.set_device(0)
        torch.manual_seed(0)
        torch.cuda.manual_seed_all(0)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.set_float32_matmul_precision("highest")
        torch.use_deterministic_algorithms(True)
        _deterministic_autotune()
        kernel_implementations = _kernel_implementations()
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), local_files_only=True,
                                                       trust_remote_code=False)
        device_map = fixed_device_map(self.profile.name)
        from transformers.modeling_utils import _is_on_hf_mount
        if _is_on_hf_mount(str(self.model_dir)):
            raise ModelIntegrityError("HF mount would bypass the bounded pread checkpoint reader")
        with _sequential_pread_checkpoint_io():
            base = AutoModelForCausalLM.from_pretrained(
                str(self.model_dir), dtype=torch.bfloat16, device_map=device_map,
                low_cpu_mem_usage=True, local_files_only=True, trust_remote_code=False,
                disable_mmap=False, attn_implementation="sdpa")
        self.model = PeftModel.from_pretrained(
            base, str(self.model_dir / "adapter"), local_files_only=True,
            is_trainable=False).merge_and_unload()
        self.model.eval()
        self.model.requires_grad_(False)
        self.model.config.use_cache = False
        _check_finite_parameters(self.model, torch)
        _check_placement(self.model, device_map)
        if any("lora_" in name for name, _ in self.model.named_parameters()):
            raise ModelIntegrityError("adapter did not fully merge")
        head = load_file(str(self.model_dir / "head.safetensors"), device="cpu")
        if (set(head) != {"proj.weight", "proj.bias"}
                or tuple(head["proj.weight"].shape) != (24, 5120)
                or tuple(head["proj.bias"].shape) != (24,)
                or any(value.dtype != torch.float32 for value in head.values())):
            raise ModelIntegrityError("decision head is not the pinned FP32 24-slot head")
        head_device = f'cuda:{self.devices[-1]}'
        self._weight = head["proj.weight"].to(head_device)
        self._bias = head["proj.bias"].to(head_device)
        if any(value.device.type != 'cuda' or value.device.index != self.devices[-1]
               or value.dtype != torch.float32 for value in (self._weight, self._bias)):
            raise ModelIntegrityError('decision head placement or FP32 dtype changed')
        cfg = json.loads((self.model_dir / "judge_config.json").read_text())
        calibration = json.loads((self.model_dir / "calibration.json").read_text())
        if (cfg["slots"]["ranges"]["choice"] != [8, 24]
                or cfg["slots"]["template_version"] != "bare-v1"
                or calibration["per_kind"]["choice"] != CHOICE_TEMPERATURE):
            raise ModelIntegrityError("choice slot layout or calibration changed")
        self.temperature = calibration["per_kind"]["choice"]
        self._metadata = {
            "model": MODEL_ID, "revision": REVISION, "loaded": True,
            "model_files_sha256": dict(MODEL_FILES_SHA256), "packages": packages,
            "device_map": device_map,
            "serving_config": {
                "runtime_profile": self.profile.name,
                "physical_gpus": list(self.profile.physical_gpus),
                "allocator_limit_bytes": self.profile.allocator_bytes,
                "nvml_gpu_limit_bytes": self.profile.gpu_bytes,
                "host_limit_bytes": self.profile.host_bytes,
                "disk_limit_bytes": self.profile.disk_bytes,
                "decision_head_device": head_device,
                "tensor_placement_verified": True,
                "format": FORMAT_VERSION, "max_input_tokens": MAX_TOKENS,
                "native_max_position_embeddings": self.model.config.max_position_embeddings,
                "truncation": False, "add_special_tokens": False, "batch_size": 1,
                "backbone_dtype": "bfloat16", "head_dtype": "float32", "adapter": "merged",
                "safe_merge": False, "merge": "official-peft-default-fp32-delta-add-to-bf16-base",
                "merged_finite_check_chunk_elements": 2 ** 20,
                "weight_loading": {"api": "transformers.from_pretrained",
                                   "safetensors_backend": "pread", "async_loading": False},
                "head_choice_slots": [8, 24], "temperature": self.temperature,
                "quantization": None, "offload": None, "use_cache": False,
                "output_hidden_states": False, "readout": "final_norm_last_token",
                "attention": "sdpa-flash-only", "gated_delta": "flash-linear-attention-0.5.2",
                "kernel_implementations": kernel_implementations,
                "triton_autotune": "first-working-config-in-declared-order",
                "tf32": False, "deterministic_algorithms": True, "seed": 0,
                "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "torch_cuda_version": torch.version.cuda,
                "parameter_dtypes": dict(Counter(str(p.dtype) for p in self.model.parameters())),
                "source_sha256": {p.name: sha256_file(p) for p in
                                  (Path(__file__), Path(__file__).with_name("formatting.py"),
                                   Path(__file__).with_name("config.py"), Path(__file__).with_name("resource.py"))},
            },
        }
        encoded = json.dumps(self._metadata, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode()
        self._metadata["serving_identity"] = hashlib.sha256(encoded).hexdigest()
        self.loaded = True
        self._check_memory()
        return self

    def _resource(self) -> dict[str, Any]:
        if not self.loaded:
            return {}
        torch = self._torch
        return {"gpu_allocated_bytes": [torch.cuda.memory_allocated(i) for i in self.devices],
                "gpu_reserved_bytes": [torch.cuda.memory_reserved(i) for i in self.devices],
                "gpu_peak_allocated_bytes": [torch.cuda.max_memory_allocated(i) for i in self.devices]}

    def _check_memory(self) -> None:
        resource = self._resource()
        if any(value > self.profile.allocator_bytes for values in resource.values() for value in values):
            raise ModelIntegrityError(f'GPU allocator use exceeded {self.profile.allocator_bytes // 1024**3} GiB')

    def metadata(self) -> dict[str, Any]:
        result = copy.deepcopy(self._metadata)
        result["resource"] = self._resource()
        return result

    def health(self) -> dict[str, Any]:
        return self.metadata()

    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.loaded:
            raise ModelIntegrityError("load the model before evaluation")
        formatted = format_request(payload)
        encoded = tokenize_request(self.tokenizer, formatted, self.max_tokens)
        torch = self._torch
        from torch.nn.attention import SDPBackend, sdpa_kernel
        inputs = {name: torch.tensor([values], dtype=torch.long, device="cuda:0")
                  for name, values in encoded.items()}
        started = time.monotonic()
        with torch.inference_mode():
            # Flash-only avoids silent O(sequence_length**2) eager/math allocations.
            # Failure to support it is a gate failure, never an automatic fallback.
            with torch.autocast("cuda", dtype=torch.bfloat16), sdpa_kernel([SDPBackend.FLASH_ATTENTION]):
                output = self.model.model(**inputs, use_cache=False, output_hidden_states=False,
                                          return_dict=True)
                hidden = output.last_hidden_state[0, -1].float().to(self._weight.device)
            del output
            # The official readout is FP32, outside BF16 autocast. No vocabulary logits
            # and no token decoding are needed for System 1.
            logits = (self._weight @ hidden + self._bias) / self.temperature
            probabilities = torch.softmax(logits[8:8 + len(formatted.candidate_ids)], 0).tolist()
        self._check_memory()
        try:
            answer = answer_from_probabilities(formatted, probabilities)
        except ValueError as error:
            raise ModelIntegrityError("nonfinite or malformed native decision probabilities") from error
        count = len(encoded["input_ids"])
        return {"model": MODEL_ID, "answers": {formatted.question_name: answer},
                "usage": {"input_tokens": count, "output_tokens": 0},
                "metadata": {"revision": REVISION,
                             "serving_identity": self._metadata["serving_identity"],
                             "format": FORMAT_VERSION, "prompt_sha256": formatted.prompt_sha256,
                             "candidate_ids": list(formatted.candidate_ids),
                             "elapsed_seconds": time.monotonic() - started, **self._resource()}}
