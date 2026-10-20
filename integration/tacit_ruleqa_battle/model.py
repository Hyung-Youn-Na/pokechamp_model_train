"""Resident selected nonmerged LoRA; native no-Thinking action generation."""
import json
import sys
import time
from .core import ADAPTER


def serve():
    import torch
    from transformers import AutoTokenizer,set_seed
    from integration.pokechamp.rule_qa_training.model import load_model
    set_seed(20261019);torch.set_num_threads(4)
    if torch.cuda.device_count()!=1:raise ValueError('one owned physical GPU required')
    tokenizer=AutoTokenizer.from_pretrained(ADAPTER/'tokenizer',local_files_only=True)
    model=load_model(torch.device('cuda:0'),adapter=ADAPTER).eval()
    layers=[m for m in model.modules() if hasattr(m,'lora_A')]
    if not layers or any(m.merged for m in layers):raise ValueError('missing or merged adapter')
    print(json.dumps(dict(ready=True,lora_layers=len(layers),active_adapters=model.active_adapters,thinking=False,physical_uuid=str(torch.cuda.get_device_properties(0).uuid))),flush=True)
    for line in sys.stdin:
        request=json.loads(line)
        try:
            started=time.monotonic()
            text=tokenizer.apply_chat_template(request['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            inputs=tokenizer(text,return_tensors='pt',add_special_tokens=False)
            length=inputs['input_ids'].shape[1]
            if length>32768:raise ValueError(f'input exceeds32768: {length}')
            inputs={k:v.to('cuda:0') for k,v in inputs.items()}
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                output=model.generate(**inputs,max_new_tokens=192,do_sample=False,use_cache=True,
                       eos_token_id=tokenizer.eos_token_id,pad_token_id=tokenizer.pad_token_id,logits_to_keep=1)
            torch.cuda.synchronize();ids=output[0,length:].tolist()
            response=dict(id=request['id'],raw=tokenizer.decode(ids,skip_special_tokens=True),input_tokens=length,
                output_tokens=len(ids),output_ids=ids,truncated=len(ids)==192 and ids[-1]!=tokenizer.eos_token_id,
                latency_seconds=time.monotonic()-started,gpu_peak_allocated=torch.cuda.max_memory_allocated(),
                gpu_peak_reserved=torch.cuda.max_memory_reserved())
        except Exception as exc:response=dict(id=request['id'],error=dict(type=type(exc).__name__,detail=str(exc)))
        print(json.dumps(response),flush=True)


if __name__=='__main__':serve()
