"""Exported adapter readout example; execute with a prepared QA row as JSON."""
import json
import sys
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

if __name__=='__main__':
    import inspect
    from transformers.models.qwen3_5 import modeling_qwen3_5 as native
    for name in ('torch_chunk_gated_delta_rule','torch_recurrent_gated_delta_rule','causal_conv1d_fn','causal_conv1d_update'):
        setattr(native,name,inspect.unwrap(getattr(native,name)))
    directory=Path(__file__).resolve().parent
    base=AutoModelForCausalLM.from_pretrained('alibiserikbay/JevK5-9B',
        revision='d6521a18a86999190e9d775c915af3d6d6772fc4',dtype=torch.bfloat16,
        attn_implementation='sdpa',device_map={'':'cuda:0'},use_kernels=False)
    model=PeftModel.from_pretrained(base,directory).eval()
    for name,p in model.named_parameters():
        if 'lora_' in name:p.data=p.data.float()
    tokenizer=AutoTokenizer.from_pretrained(directory/'tokenizer')
    row=json.loads(Path(sys.argv[1]).read_text())
    ids=torch.tensor([row['input_ids']],device='cuda:0')
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        z=model(input_ids=ids,logits_to_keep=1,use_cache=False).logits[0,-1,row['label_ids']].float()
    temperature=json.loads((directory/'calibration.json').read_text())['selected']['temperature']
    p=torch.softmax(z.double()/temperature,-1)
    print(dict(choice=row['option_ids'][int(p.argmax())],probabilities=p.tolist()))
