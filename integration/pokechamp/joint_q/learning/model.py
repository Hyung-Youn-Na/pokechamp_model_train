"""Official Qwen text weights + text-only LoRA + one shared FP32 value head."""
import hashlib
import math
from pathlib import Path
import random
import numpy as np
import torch
from torch import nn
from ..storage import atomic, read, sha
from .config import CONFIG, MODEL, REVISION, CACHE
from .render import EncodedInput, render


def snapshot(download=False):
    from huggingface_hub import snapshot_download
    return Path(snapshot_download(MODEL,revision=REVISION,cache_dir=str(CACHE),
        local_files_only=not download,token=False,
        allow_patterns=['*.json','*.jinja','*.safetensors','merges.txt','vocab.json','README.md']))


def tokenizer(path=None):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(path or snapshot(),local_files_only=True,trust_remote_code=False)
    if not tok.is_fast or not tok.chat_template:
        raise ValueError('official fast tokenizer with chat template required')
    return tok


def seed_all():
    random.seed(CONFIG['seed'])
    np.random.seed(CONFIG['seed'])
    torch.manual_seed(CONFIG['seed'])
    torch.cuda.manual_seed_all(CONFIG['seed'])
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


def rng_state():
    return dict(python=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),
                cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [])


def restore_rng(state):
    random.setstate(state['python'])
    np.random.set_state(state['numpy'])
    torch.set_rng_state(state['torch'])
    if state['cuda']:
        torch.cuda.set_rng_state_all(state['cuda'])


def fingerprints(module, predicate=lambda name:True):
    return {name:hashlib.sha256(p.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
            for name,p in module.named_parameters() if predicate(name)}


def load_base(evidence):
    from safetensors import safe_open
    from transformers import AutoConfig, Qwen3_5ForCausalLM
    path = snapshot()
    cfg = AutoConfig.from_pretrained(path,local_files_only=True,trust_remote_code=False).text_config
    if cfg.hidden_size != CONFIG['hidden_size']:
        raise ValueError('unexpected text hidden size')
    cfg.use_cache = False
    causal, info = Qwen3_5ForCausalLM.from_pretrained(path,config=cfg,dtype=torch.bfloat16,
        attn_implementation=CONFIG['attention'],output_loading_info=True,
        local_files_only=True,trust_remote_code=False)
    tied = causal.lm_head.weight.data_ptr() == causal.model.embed_tokens.weight.data_ptr()
    missing = [k for k in info['missing_keys'] if not (k=='lm_head.weight' and tied)]
    unexpected = [k for k in info['unexpected_keys'] if not k.startswith(('model.visual.','mtp.'))]
    if missing or unexpected or info.get('mismatched_keys') or info.get('error_msgs'):
        raise ValueError(f'official text loading mismatch: {info}')
    base = causal.model.to(dtype=torch.bfloat16)
    actual, checked = base.state_dict(), set()
    index = read(path/'model.safetensors.index.json')['weight_map']
    for file in sorted(set(index.values())):
        with safe_open(path/file,framework='pt',device='cpu') as handle:
            for source in handle.keys():
                if not source.startswith('model.language_model.'):
                    continue
                key = source.removeprefix('model.language_model.')
                if key not in actual or not torch.equal(actual[key],handle.get_tensor(source).to(torch.bfloat16)):
                    raise ValueError('loaded text tensor differs from pinned checkpoint: '+source)
                checked.add(key)
    if checked != set(actual) or any(p.dtype != torch.bfloat16 for p in base.parameters()):
        raise ValueError('incomplete BF16 text weight coverage')
    atomic(evidence,dict(model=MODEL,revision=REVISION,class_name=type(base).__name__,
        tensors_verified=len(checked),parameters=sum(p.numel() for p in base.parameters()),
        loading_info={k:list(v) if isinstance(v,set) else v for k,v in info.items()},
        tied_lm_head=tied,base_dtype='bfloat16'))
    return base


class JointValuePolicy(nn.Module):
    def __init__(self, backbone, tok, checkpoint=None, device='cuda:0'):
        super().__init__()
        from peft import LoraConfig, PeftModel, get_peft_model
        targets = [name for name,m in backbone.named_modules() if isinstance(m,nn.Linear)]
        if not targets:
            raise ValueError('text Linear target modules missing')
        if checkpoint is None:
            self.backbone = get_peft_model(backbone,LoraConfig(r=8,lora_alpha=16,lora_dropout=0,
                                                              target_modules=targets,bias='none'))
        else:
            self.backbone = PeftModel.from_pretrained(backbone,Path(checkpoint)/'adapter',
                is_trainable=True,local_files_only=True)
            saved = read(Path(checkpoint)/'metadata.json')
            if saved['target_modules'] != targets or saved['config'] != CONFIG:
                raise ValueError('checkpoint model contract mismatch')
        for name,p in self.backbone.named_parameters():
            trainable = 'lora_' in name
            if p.requires_grad != trainable:
                raise ValueError('unexpected trainability: '+name)
            if trainable:
                p.data = p.data.float()
            elif p.dtype != torch.bfloat16:
                raise ValueError('frozen base must remain BF16: '+name)
        self.head = nn.Linear(CONFIG['hidden_size'],1,dtype=torch.float32)
        with torch.no_grad():
            self.head.weight.normal_(0,.01/math.sqrt(CONFIG['hidden_size']))
            self.head.bias.zero_()
        if checkpoint is not None:
            self.head.load_state_dict(torch.load(Path(checkpoint)/'value_head.pt',map_location='cpu',weights_only=True))
        self.backbone.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        self.backbone.config.use_cache = False
        self.tokenizer, self.target_modules, self.device_name = tok, targets, device
        self.to(device)

    def values(self, encoded: EncodedInput, padding=0):
        if type(encoded) is not EncodedInput:
            raise TypeError('EncodedInput required')
        if padding < 0 or len(encoded.input_ids)+padding > CONFIG['max_tokens']:
            raise ValueError('invalid input padding')
        pad_id = self.tokenizer.pad_token_id
        if pad_id is None:
            pad_id = self.tokenizer.eos_token_id
        x = torch.tensor([list(encoded.input_ids)+[pad_id]*padding],device=self.device_name,dtype=torch.long)
        mask = torch.tensor([[1]*len(encoded.input_ids)+[0]*padding],device=self.device_name,dtype=torch.long)
        if padding:
            # Microbatch1 has exactly one complete observation. Pack its valid
            # prefix so length-dependent BF16 kernels never see masked padding.
            # This removes only padding, never any observation/candidate token.
            x=x[:,:len(encoded.input_ids)].contiguous()
            mask=mask[:,:len(encoded.input_ids)].contiguous()
        with torch.autocast('cuda',dtype=torch.bfloat16,enabled=x.is_cuda):
            output = self.backbone(input_ids=x,attention_mask=mask,use_cache=False)
            hidden = output.last_hidden_state[0,list(encoded.readout_positions)]
        with torch.autocast('cuda',enabled=False):
            q = self.head(hidden.float()).squeeze(-1).sigmoid()
        if not bool(torch.isfinite(q).all()):
            raise FloatingPointError('nonfinite candidate q')
        return q

    def predict(self, value):
        """One backbone forward for all independently valued legal candidates."""
        encoded = render(value,self.tokenizer)
        with torch.no_grad():
            q = self.values(encoded).cpu().tolist()
        return dict(zip(encoded.action_ids,q,strict=True))

    def base_fingerprints(self):
        return fingerprints(self.backbone,lambda name:'lora_' not in name)

    def trainable_fingerprints(self):
        return fingerprints(self,lambda name:'lora_' in name or name.startswith('head.'))
