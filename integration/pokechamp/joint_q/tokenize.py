"""Run in the EVE environment: CPU tokenizer only, offline, no model import/load."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from .storage import ROOT,atomic,digest,jsonl,rows,sha
from .serializer import JointInput,render


def main(directory):
    from transformers import AutoTokenizer
    directory=Path(directory)
    model=ROOT/'.tools/eve-rlcd/worktrees/pokemon-training/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
    tokenizer=AutoTokenizer.from_pretrained(str(model),local_files_only=True)
    output=[]
    for row in rows(directory/'inputs.jsonl'):
        prompt,ids=render(JointInput(row['model_input']),tokenizer)
        output.append(dict(observation_id=row['observation_id'],tokens=len(ids),over_16384=len(ids)>16384,
                           prompt_sha256=digest(prompt),token_sha256=digest(ids)))
    jsonl(directory/'tokens.jsonl',output)
    lengths=[r['tokens'] for r in output]
    result=dict(observations=len(output),minimum=min(lengths,default=0),maximum=max(lengths,default=0),
                mean=sum(lengths)/len(lengths) if lengths else 0,over_16384=sum(r['over_16384'] for r in output),
                truncated=0,model_calls=0,device='CPU',inputs_sha256=sha(directory/'inputs.jsonl'),
                tokenizer_files={p.name:sha(p) for p in model.iterdir() if p.name.startswith(('tokenizer','vocab','merges','chat_template'))})
    atomic(directory/'token-summary.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    main(sys.argv[1])
