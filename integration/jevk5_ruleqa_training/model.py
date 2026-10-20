"""Pinned text-only model and final-position choice loss."""
import inspect
import torch
import torch.nn.functional as F
from .config import CONFIG, MODEL, TARGETS


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
                  lora_dropout=CONFIG['dropout'], bias='none', target_modules=[t for t in TARGETS if t in {n.rsplit('.',1)[-1] for n,_ in base.named_modules()}], task_type='CAUSAL_LM'))
    for name, param in model.named_parameters():
        if 'lora_' in name:
            param.data = param.data.float()
        else:
            if param.requires_grad:raise ValueError(f'unexpected trainable base parameter {name}')
            assert param.dtype==torch.bfloat16,(name,param.dtype)
    lora_count = sum(p.numel() for n,p in model.named_parameters() if 'lora_' in n)
    assert lora_count == CONFIG['trainable_parameters'], lora_count
    for name,param in model.named_parameters():
        if 'lora_' in name:
            assert name.split('.lora_')[0].rsplit('.',1)[-1] in TARGETS,name
            assert param.dtype==torch.float32
    assert all(p.device == torch.device(device) for p in model.parameters())
    model.config.use_cache = False
    if trainable:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        model.enable_input_require_grads()
    return model


def frozen_fingerprint(model):
    # Full frozen tensor byte digest in preflight only; no sampled equality claim.
    import hashlib
    result = hashlib.sha256()
    for name, param in model.named_parameters():
        if not param.requires_grad:
            result.update(name.encode())
            result.update(param.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return result.hexdigest()


class ChoiceReadout(torch.nn.Module):
    """DDP owns this forward, including the option restriction and CE graph."""
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, input_ids, label_ids):
        logits = self.model(input_ids=input_ids, logits_to_keep=1, use_cache=False).logits
        return logits[0,-1,label_ids].float()


def choice_logits(reader, row, device):
    ids=torch.tensor([row['input_ids']],device=device)
    labels=torch.tensor(row['label_ids'],device=device)
    with torch.autocast('cuda',dtype=torch.bfloat16,enabled=ids.is_cuda):
        return reader(ids,labels)


def assistant_loss(reader,row,device):
    logits=choice_logits(reader,row,device)
    return F.cross_entropy(logits[None],torch.tensor([row['target']],device=device))
