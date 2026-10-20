"""Pinned text-only model and assistant-position loss."""
import inspect
import torch
import torch.nn.functional as F
from .config import CONFIG, MODEL


def native_gdn():
    from transformers.models.qwen3_5 import modeling_qwen3_5 as module
    for name in ('torch_chunk_gated_delta_rule','torch_recurrent_gated_delta_rule',
                 'causal_conv1d_fn','causal_conv1d_update'):
        setattr(module, name, inspect.unwrap(getattr(module, name)))


def load_model(device, adapter=None, trainable=False):
    import transformers, peft
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model, PeftModel
    assert dict(torch=torch.__version__, transformers=transformers.__version__, peft=peft.__version__) == CONFIG['packages']
    native_gdn()
    base = AutoModelForCausalLM.from_pretrained(MODEL, local_files_only=True,
              dtype=torch.bfloat16, device_map={'':device}, attn_implementation='sdpa', use_kernels=False)
    if adapter is not None:
        model = PeftModel.from_pretrained(base, adapter, is_trainable=trainable)
    else:
        model = get_peft_model(base, LoraConfig(r=CONFIG['r'], lora_alpha=CONFIG['alpha'],
                  lora_dropout=CONFIG['dropout'], bias='none', target_modules='all-linear', task_type='CAUSAL_LM'))
    for name, param in model.named_parameters():
        if 'lora_' in name:
            param.data = param.data.float()
        elif param.requires_grad:
            raise ValueError(f'unexpected trainable base parameter {name}')
    lora_count = sum(p.numel() for n,p in model.named_parameters() if 'lora_' in n)
    assert lora_count == CONFIG['trainable_parameters'], lora_count
    assert all(p.device == torch.device(device) for p in model.parameters())
    model.config.use_cache = False
    if trainable:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        model.enable_input_require_grads()
    return model


def assistant_loss(model, row, device):
    ids = torch.tensor([row['input_ids']], device=device)
    start = row['prefix_length']
    positions = torch.arange(start-1, ids.shape[1]-1, device=device)
    with torch.autocast('cuda' if ids.is_cuda else 'cpu', dtype=torch.bfloat16, enabled=ids.is_cuda):
        logits = model(input_ids=ids, logits_to_keep=positions, use_cache=False).logits
        loss = F.cross_entropy(logits[0].float(), ids[0,start:], reduction='mean')
    return loss


def frozen_fingerprint(model):
    # Full frozen tensor byte digest in preflight only; no sampled equality claim.
    import hashlib
    result = hashlib.sha256()
    for name, param in model.named_parameters():
        if not param.requires_grad:
            result.update(name.encode())
            result.update(param.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return result.hexdigest()
