"""One resident FP32, unmerged PEFT model; JSON-lines request server."""
import json
import sys
import time
from .core import ADAPTER, BASE


def serve():
    import torch
    import transformers
    import peft
    from transformers import AutoTokenizer, AutoModelForCausalLM, set_seed
    from peft import PeftModel
    if transformers.__version__ != '5.17.0' or peft.__version__ != '0.21.0':
        raise RuntimeError('frozen runtime version mismatch')
    set_seed(42)
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    tokenizer = AutoTokenizer.from_pretrained(ADAPTER, local_files_only=True)
    base = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float32, local_files_only=True)
    model = PeftModel.from_pretrained(base, ADAPTER, is_trainable=False).to('cuda:0').eval()
    if any(p.dtype != torch.float32 for p in model.parameters()):
        raise ValueError('non-FP32 parameter')
    layers = [m for m in model.modules() if hasattr(m, 'lora_A')]
    if len(layers) != 196 or any(m.merged for m in layers) or not model.active_adapters:
        raise ValueError('adapter missing or merged')
    print(json.dumps(dict(ready=True, dtype='float32', lora_layers=len(layers),
        active_adapters=model.active_adapters, transformers=transformers.__version__, peft=peft.__version__)), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            started = time.monotonic()
            text = tokenizer.apply_chat_template(request['messages'], tokenize=False,
                add_generation_prompt=True, enable_thinking=False)
            inputs = tokenizer(text, return_tensors='pt', add_special_tokens=False)
            length = inputs['input_ids'].shape[1]
            if length > 1024:
                raise ValueError(f'input token limit exceeded: {length}')
            inputs = {k: v.to('cuda:0') for k, v in inputs.items()}
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=64, do_sample=False,
                    pad_token_id=tokenizer.eos_token_id, use_cache=True)
            torch.cuda.synchronize()
            ids = output[0, length:].tolist()
            eos = model.generation_config.eos_token_id
            eos = eos if isinstance(eos, list) else [eos]
            response = dict(id=request['id'], raw=tokenizer.decode(ids, skip_special_tokens=True),
                input_tokens=length, output_tokens=len(ids), output_ids=ids,
                truncated=len(ids) == 64 and ids[-1] not in eos,
                latency_seconds=time.monotonic()-started,
                gpu_peak_allocated=torch.cuda.max_memory_allocated(),
                gpu_peak_reserved=torch.cuda.max_memory_reserved())
        except Exception as exc:
            response = dict(id=request['id'], error=dict(type=type(exc).__name__, detail=str(exc)))
        print(json.dumps(response), flush=True)


if __name__ == '__main__':
    serve()
