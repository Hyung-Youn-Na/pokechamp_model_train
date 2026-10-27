"""Freeze evaluation before any learning and freeze executable dependencies before GPU use."""
import copy
import json
from collections import Counter,defaultdict
from pathlib import Path
import shutil
import subprocess
from .config import CONFIG, ROOT, MODEL, DOMAINS
from .data import TokenStore,TokenWriter,rows,sha,dump,digest,render,normalized_input


def evaluation(output,rule_path):
    from transformers import AutoTokenizer
    output=Path(output);tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    engine=subprocess.check_output(['git','-C',str(ROOT/'pokemon-showdown'),'rev-parse','HEAD'],text=True).strip()
    assert engine=='e64915c0eab066db1d3e732b1280386468dd7415'
    inputs=[];groups=defaultdict(list)
    for r in rows(rule_path):
        assert r['evidence']['expected']==r['evidence']['observed']==r['answer']
        order=sorted(r['options'],key=lambda v:digest([r['id'],v,CONFIG['seed']]))
        target=order.index(r['answer'])
        row=dict(metadata={k:r[k] for k in ['id','domain','group','split']},input=dict(state=r['state'],question=dict(type='choice',
            instructions='Answer the stated Generation 9 mechanics question from the explicit conditions. Choose one answer without an explanation.\nQuestion: '+r['question'],
            criteria={chr(65+i):v for i,v in enumerate(order)})),target_index=target,
            target_distribution=[int(i==target) for i in range(len(order))],evidence=r['evidence'])
        inputs.append(row);groups[r['group']].append(row)
    assert len(inputs)==2688 and len(groups)==1344
    for d in DOMAINS:
        for split,n in [('validation',64),('test',128)]:
            selected=[v for v in groups.values() if v[0]['metadata']['domain']==d and v[0]['metadata']['split']==split]
            assert len(selected)==n and all(len(v)==2 for v in selected)
    inputs+=list(rows(output/'evaluation-replays/rows.jsonl'))
    train=TokenStore(output/'train');known={m['input_digest'] for m in train.metadata};seen=set();split_groups=defaultdict(set)
    writers={s:TokenWriter(output/s) for s in ['validation','test']}
    counts=Counter();group_split={};canonical=[]
    for r in inputs:
        m=r['metadata'];s=m['split'];group=m['group'];key=normalized_input(r)
        assert key not in known and key not in seen,'duplicate normalized state/question/options'
        seen.add(key)
        assert group not in group_split or group_split[group]==s;group_split[group]=s
        split_groups[s].add(group)
        text,options=render(r,tok);ids=tok.encode(text,add_special_tokens=False)
        labels=[tok.encode(chr(65+i),add_special_tokens=False) for i in range(len(options))];assert all(len(a)==1 for a in labels)
        probe=copy.deepcopy(r);probe['metadata']={'leak':'SENTINEL'};probe['evidence']='SENTINEL';probe['target_index']=-1;probe['target_distribution']=[]
        assert render(probe)==(text,options)
        writers[s].add(ids,[v[0] for v in labels],r['target_index'],dict(id=m['id'],domain=m['domain'],group=group,input_digest=key))
        counts[s+':'+m['domain']]+=1;canonical.append(r)
    assert not split_groups['validation']&split_groups['test']
    for s,w in writers.items():w.close();assert len(w.targets)=={'validation':1152,'test':2304}[s]
    with (output/'evaluation-canonical.jsonl').open('x') as f:
        for r in canonical:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    # A semantic novelty audit is separate from exact text hashes. The seven generators
    # compose effects absent from the original question-event contracts (see review).
    dump(output/'evaluation-validation.json',dict(passed=True,counts=dict(counts),groups={s:len(v) for s,v in split_groups.items()},
        normalized_input_intersections=0,source_rule_rows_sha=sha(rule_path),showdown_commit=engine,
        split_policy='hash-ranked source profiles, all two-state variants kept together',
        semantic_review='project_context/exec-plans/evidence/ep203/evaluation-review.md',
        replay_audit_sha=sha(output/'evaluation-replays/validation.json')))


def source_identity():
    paths=list((ROOT/'integration/jevk5_system1_training').rglob('*.py'))+list((ROOT/'integration/jevk5_system1_training').glob('*.cjs'))
    paths += [ROOT/'integration/jevk5_ruleqa_training'/n for n in ['model.py','config.py']]
    paths += [ROOT/'integration/jevk5_battle/upstream_prompt.py',ROOT/'scripts/jevk5-system1-train']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}


def freeze(output):
    from integration.project_context.registry import freeze_document,resolve_record
    output=Path(output);assert not (output/'prepared.json').exists()
    for name in ['training','evaluation']:assert json.loads((output/f'{name}-validation.json').read_text())['passed']
    assert (ROOT/'project_context/exec-plans/evidence/ep203/evaluation-review.md').exists()
    sources=source_identity()
    for name in sources:
        dest=output/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    freeze_document(resolve_record('EX-116'),output/'protocol/EX-116.md')
    shutil.copy2(ROOT/'project_context/exec-plans/evidence/ep203/evaluation-review.md',output/'protocol/evaluation-review.md')
    files={str(p.relative_to(output)):sha(p) for name in ['train','validation','test','diagnostic','tokenizer','protocol'] for p in (output/name).rglob('*') if p.is_file()}
    files.update({n:sha(output/n) for n in ['training-validation.json','evaluation-validation.json','evaluation-canonical.jsonl']})
    dump(output/'prepared.json',dict(config=CONFIG,sources=sources,files=files))


def verify(output):
    p=json.loads((Path(output)/'prepared.json').read_text())
    assert p['config']==CONFIG and p['sources']==source_identity(),'source/config drift'
    for name,h in p['files'].items():assert sha(Path(output)/name)==h,('prepared data drift',name)
    return p


def diagnostics(output):
    from transformers import AutoTokenizer
    from .config import SOURCES
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True);writer=TokenWriter(Path(output)/'diagnostic')
    selected={}
    for domain,folder,subsets,_ in SOURCES:
        if domain not in ['type','role']:continue
        for subset in subsets:
            for row in rows(ROOT/'exports'/folder/f'{subset}.choice.jsonl'):
                m=row['metadata'];key=m['semantic_group'] if domain=='type' else m['id']
                selected.setdefault((domain,key),row)
    for (domain,key),row in sorted(selected.items()):
        for reverse in ([False] if domain=='type' else [False,True]):
            r=copy.deepcopy(row);criteria=r['input']['question']['criteria'];answer=list(criteria.values())[r['target_index']]
            options=list(criteria.values());options=options[::-1] if reverse else options
            r['input']['question']['criteria']={chr(65+i):v for i,v in enumerate(options)}
            ids=tok.encode(render(r,tok)[0],add_special_tokens=False)
            labels=[tok.encode(chr(65+i),add_special_tokens=False)[0] for i in range(len(options))]
            writer.add(ids,labels,options.index(answer),dict(id=f'diagnostic:{domain}:{key}:{reverse}',
                domain=domain+('-reordered' if reverse else '-original'),group=domain+':'+key,input_digest=normalized_input(r)))
    writer.close();assert len(writer.targets)==3080+3717*2
