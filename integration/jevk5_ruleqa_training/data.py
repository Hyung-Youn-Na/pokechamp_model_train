"""Strict QA-only projection; labels and provenance never enter the prompt."""
import copy
import subprocess
from pathlib import Path
from collections import Counter
from integration.pokechamp.rule_qa_training.data import read_json, write_json, read_rows, write_rows, sha
from integration.jevk5_battle import upstream_prompt as official
from .config import CONFIG, ROOT, DATA, MODEL
INSTRUCTION = 'Answer the Gen9 Pokémon rules question using the supplied evidence and explicit conditions. Do not choose a battle action.'


def source_identity():
    paths=list((ROOT/'integration/jevk5_ruleqa_training').glob('*.py'))
    paths += [ROOT/'scripts/jevk5-ruleqa-train',ROOT/'integration/jevk5_battle/upstream_prompt.py',
              ROOT/'integration/pokechamp/rule_qa_training/data.py',ROOT/'integration/pokechamp/rule_qa_training/model.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}


def project(row):
    assert row['representation']=='state_mc'
    options=row['options']; keys=[o['id'] for o in options]
    assert len(keys) in (3,4) and len(set(keys))==len(keys)
    assert keys.count(row['answer_id'])==1
    assert sum(o['text']==row['answer'] for o in options)==1
    assert next(o['text'] for o in options if o['id']==row['answer_id'])==row['answer']
    return dict(state=dict(state=row['context']['state'],battle_actions=row['context']['battle_actions'],conditions=row['conditions']),
                question=dict(type='choice',criteria={o['id']:o['text'] for o in options},
                              instructions=INSTRUCTION+'\nQuestion: '+row['question']))


def render(payload):
    q=payload['question']
    return official.prompt_text(payload['state'],q['instructions'],[t for _,t in official.decision_options(q)])


def encode(tokenizer,row):
    payload=project(row);q=payload['question']; texts=[t for _,t in official.decision_options(q)]
    text=render(payload)
    assert text==tokenizer.apply_chat_template(official.messages(payload['state'],q['instructions'],texts),
                        tokenize=False,add_generation_prompt=True,enable_thinking=False)
    ids=tokenizer.encode(text,add_special_tokens=False)
    if not 0<len(ids)<=CONFIG['max_length']:raise ValueError(f"untruncated length {row['id']}: {len(ids)}")
    labels=[tokenizer.encode(c,add_special_tokens=False) for c in official.LETTERS[:len(texts)]]
    assert all(len(x)==1 for x in labels) and len({x[0] for x in labels})==len(labels)
    keys=list(q['criteria']);target=keys.index(row['answer_id'])
    return dict(input_ids=ids,label_ids=[x[0] for x in labels],target=target,
                expected=[int(i==target) for i in range(len(keys))],option_ids=keys)


def prepare(output):
    from transformers import AutoTokenizer
    output=Path(output)
    if (output/'prepared.json').exists():raise FileExistsError('already prepared')
    output.mkdir(parents=True,exist_ok=True)
    assert read_json(DATA/'manifest.json')['status']=='exported'
    tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    clusters=read_json(DATA/'duplicate_clusters.json')
    component={g:i for i,gs in enumerate(clusters) for g in gs}
    canonical={r['id']:r for r in read_rows(DATA/'canonical.jsonl')}
    assert len(canonical)==5760
    used=set();split_components={};summary={};identities={}
    for split,count in [('train',1536),('validation',192),('test',192)]:
        source=read_rows(DATA/f'{split}.jsonl')
        assert len(source)==count*3
        rows=[r for r in source if r['representation']=='state_mc']; assert len(rows)==count
        prepared=[]
        for row in rows:
            assert canonical[row['id']]==row and row['split']==split and row['id'] not in used
            used.add(row['id'])
            encoded=encode(tokenizer,row)
            # Change every non-input field, including the correct answer: rendered input is invariant.
            probe=copy.deepcopy(row)
            for k in ['id','rule_id','group_id','scenario_id','split','rationale']:probe[k]='LEAK_SENTINEL'
            other=next(o for o in row['options'] if o['id']!=row['answer_id'])
            probe.update(answer_id=other['id'],answer=other['text'],oracle='LEAK_SENTINEL')
            assert render(project(probe))==render(project(row))
            prepared.append(dict(encoded,**{k:row[k] for k in ['id','rule_id','group_id','scenario_id','answer_id']},component=component[row['group_id']]))
        assert len({r['rule_id'] for r in rows})==24
        assert set(Counter(r['group_id'] for r in rows).values())=={2}
        split_components[split]={r['component'] for r in prepared}
        write_rows(output/f'{split}.jsonl',prepared)
        summary[split]=dict(rows=count,tokens=sum(len(r['input_ids']) for r in prepared),
            max_tokens=max(len(r['input_ids']) for r in prepared),components=len(split_components[split]),
            choices=dict(Counter(len(r['label_ids']) for r in prepared)))
        identities[str(DATA/f'{split}.jsonl')]=sha(DATA/f'{split}.jsonl')
    assert len(used)==1920 and len(split_components['test'])==82
    assert not any(split_components[a]&split_components[b] for a,b in [('train','test'),('train','validation'),('validation','test')])
    tokenizer.save_pretrained(output/'tokenizer')
    for name in ['canonical.jsonl','duplicate_clusters.json','manifest.json']:identities[str(DATA/name)]=sha(DATA/name)
    write_json(output/'config.json',CONFIG)
    write_json(output/'prepared.json',dict(config=CONFIG,summary=summary,data=identities,sources=source_identity(),
        model_files={p.name:sha(p) for p in MODEL.iterdir() if p.is_file()},
        tokenizer_files={p.name:sha(p) for p in (output/'tokenizer').iterdir() if p.is_file()},
        prepared_files={s:sha(output/f'{s}.jsonl') for s in summary},
        upstream_training_sha=sha(Path('/ref/jevk5/training/lora.py')),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    (output/'starting-git-status.txt').write_text(subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True))
    for name in source_identity():
        dest=output/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
    print(summary,flush=True)


def verify_prepared(output):
    manifest=read_json(output/'prepared.json')
    if manifest['config']!=CONFIG or manifest['sources']!=source_identity():raise ValueError('source/config changed')
    for split,digest in manifest['prepared_files'].items():
        if sha(output/f'{split}.jsonl')!=digest:raise ValueError('prepared data changed')
    for name,digest in manifest['tokenizer_files'].items():
        if sha(output/'tokenizer'/name)!=digest:raise ValueError('tokenizer changed')
    return manifest
