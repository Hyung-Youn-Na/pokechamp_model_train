"""CPU tokenizer census, invoked in the already installed JEV runtime."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
from transformers import AutoTokenizer
from .pipeline import ROOT,iter_records,write,sha
from .records import messages,digest

def run(output):
    summaries={};counts={}
    for name in ('tacit9b','jev27b'):
        path=ROOT/'.pokechamp-data'/(name+'-runtime')/'model'
        tok=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
        maximum=0;maximum_total=0;bad=[];number=0
        for row in iter_records(output):
            prompt=tok.apply_chat_template(messages(row,include_answer=False),tokenize=False,add_generation_prompt=True)
            full=tok.apply_chat_template(messages(row),tokenize=False,add_generation_prompt=False)
            n=len(tok(prompt,add_special_tokens=False,truncation=False)['input_ids'])
            total=len(tok(full,add_special_tokens=False,truncation=False)['input_ids'])
            counts.setdefault(row['id'],{})[name]=dict(input_tokens=n,total_tokens=total,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
            maximum=max(maximum,n);maximum_total=max(maximum_total,total);number+=1
            if n>32768 or total>32768:bad.append(row['id'])
        summaries[name]=dict(rows=number,max_input_tokens=maximum,max_total_tokens=maximum_total,over_limit=bad,
            tokenizer_files={p.name:sha(p) for p in path.iterdir() if p.is_file() and (p.name.startswith('tokenizer') or p.name=='chat_template.jinja')},
            format='local tokenizer native chat template, full system/user/question/options, generation prefix; no truncation')
    with (output/'lengths.jsonl').open('w') as f:
        for key in sorted(counts):f.write(json.dumps(dict(id=key,counts=counts[key]),ensure_ascii=False)+'\n')
    report=dict(passed=all(not s['over_limit'] for s in summaries.values()),canonical_sha256=sha(output/'canonical.jsonl'),models=summaries,
                python=sys.executable,cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),downloads=0)
    write(output/'lengths.json',report)
    return report
if __name__=='__main__':
    result=run(Path(sys.argv[1]));print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
