"""Run: python loading.py choice-row.json --device cuda:0 (base model must be cached)."""
import argparse
import os
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
import inspect
import json
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from peft import PeftModel
import upstream_prompt as official

def main():
    p=argparse.ArgumentParser();p.add_argument('row',type=Path);p.add_argument('--device',default='cuda:0');args=p.parse_args()
    torch.use_deterministic_algorithms(True);torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
    here=Path(__file__).resolve().parent;identity=json.loads((here/'base-model.json').read_text())
    from transformers.models.qwen3_5 import modeling_qwen3_5 as native
    for name in ['torch_chunk_gated_delta_rule','torch_recurrent_gated_delta_rule','causal_conv1d_fn','causal_conv1d_update']:setattr(native,name,inspect.unwrap(getattr(native,name)))
    base=AutoModelForCausalLM.from_pretrained(identity['model'],revision=identity['revision'],local_files_only=True,dtype=torch.bfloat16,device_map={'':args.device},attn_implementation='sdpa',use_kernels=False)
    model=PeftModel.from_pretrained(base,here).eval()
    for name,param in model.named_parameters():
        if 'lora_' in name:param.data=param.data.float()
    tok=AutoTokenizer.from_pretrained(here/'tokenizer',local_files_only=True);row=json.loads(args.row.read_text());inp=row['input'];q=inp['question'];options=official.decision_options(q)
    text=official.prompt_text(inp['state'],q['instructions'],[v for _,v in options]);ids=tok.encode(text,add_special_tokens=False)
    if not 0<len(ids)<=6144 or not 2<=len(options)<=11:raise ValueError('unsupported input length or candidate count')
    letters=[tok.encode(chr(65+i),add_special_tokens=False) for i in range(len(options))];assert all(len(v)==1 for v in letters)
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16,enabled=args.device.startswith('cuda')):
        z=model(input_ids=torch.tensor([ids],device=args.device),logits_to_keep=1,use_cache=False).logits[0,-1,[v[0] for v in letters]].double()
    probabilities=z.softmax(-1);choice=int(probabilities.argmax())
    print(json.dumps(dict(choice=options[choice][0],probabilities=probabilities.tolist(),temperature=1)))
if __name__=='__main__':main()
