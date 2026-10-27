"""Derive supervised direct-classification inputs, never completion SFT targets."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from transformers import AutoTokenizer
from integration.jevk5_battle import upstream_prompt as official

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
SOURCE=Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-type-matchup/v1')
OUTPUT=SOURCE.parents[1]/'gen9-type-system1/v1'
MODEL=Path('/root/.cache/huggingface/hub/models--alibiserikbay--JevK5-9B/snapshots/d6521a18a86999190e9d775c915af3d6d6772fc4')
CLASSES=[0,0.25,0.5,1,2,4]
INSTRUCTION=('Choose the Generation 9 type-effectiveness multiplier, without generating reasoning. '
 'Use only standard type interactions and the stated Terastallization state. The attack type is final; '
 'Stellar means Tera Blast used by a Stellar-Terastallized attacker. '
 'Ignore STAB, abilities, items, weather, field effects, extra added types, and other move-specific exceptions. '
 'This is a synthetic type calculation, not a battle-action selection.')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def line(f,x):f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')


def project(r):
    return dict(state=dict(attack_type=r['attack_type'],defender_types=r['defender_types'],
                           defender_tera_type=r['defender_tera_type']),
                question=dict(type='choice',instructions=INSTRUCTION,criteria=r['options']))


def features(r, attacks, types, modes):
    return [int(r['attack_type']==a) for a in attacks]+[int(t in r['defender_types']) for t in types]+[
        int(r['defender_tera_type']==m) for m in modes]


def build(source,output):
    if output.exists():raise FileExistsError(output)
    for entry in (source/'checksums.sha256').read_text().splitlines():
        expected,name=entry.split('  ',1);assert sha(source/name)==expected,name
    assert json.loads((source/'validation.json').read_text())['passed']
    rows=[json.loads(s) for s in (source/'canonical.jsonl').read_text().splitlines()]
    assert len(rows)==64980
    types=json.loads((source/'type_chart.json').read_text())['types'];attacks=types+['Stellar'];modes=[None]+types+['Stellar']
    feature_names=['attack:'+t for t in attacks]+['original_defender:'+t for t in types]+['defender_tera:'+(t or 'none') for t in modes]
    assert len(feature_names)==57
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    letters=[tok.encode(c,add_special_tokens=False) for c in 'ABCDEF']
    assert all(len(x)==1 for x in letters) and len({x[0] for x in letters})==6
    output.mkdir(parents=True)
    global_counts=Counter(r['semantic_group'] for r in rows)
    totals={}; lengths=[]
    for subset,n in [('base',3078),('extension',61902)]:
        part=[r for r in rows if r['subset']==subset];assert len(part)==n
        counts=Counter(r['semantic_group'] for r in part)
        vectors=[];ys=[];ws=[];tokens=[];choice_rows=[]
        with (output/f'{subset}.classification.jsonl').open('w') as cls, (output/f'{subset}.choice.jsonl').open('w') as choice:
            for r in part:
                v=features(r,attacks,types,modes);target=CLASSES.index(r['multiplier']);payload=project(r)
                meta=dict(id=r['id'],semantic_group=r['semantic_group'],subset=subset,
                    inverse_group_weight_subset=1/counts[r['semantic_group']],
                    inverse_group_weight_all=1/global_counts[r['semantic_group']])
                expected=[int(i==target) for i in range(6)]
                line(cls,dict(metadata=meta,features=v,target_class=target,target_distribution=expected))
                option_ids=list(payload['question']['criteria']);ct=option_ids.index(r['answer_id'])
                assert payload['question']['criteria'][option_ids[ct]]==f"{r['multiplier']:g}x"
                line(choice,dict(metadata=meta,input=payload,target_index=ct,
                                 target_distribution=[int(i==ct) for i in range(6)]))
                options=[t for _,t in official.decision_options(payload['question'])]
                text=official.prompt_text(payload['state'],INSTRUCTION,options)
                native=tok.apply_chat_template(official.messages(payload['state'],INSTRUCTION,options),tokenize=False,
                                               add_generation_prompt=True,enable_thinking=False)
                assert text==native
                # Alter all labels and derived fields: neither model input is allowed to change.
                probe=copy.deepcopy(r)
                for k in ['id','semantic_group','multiplier','effective_defender_types','factors','answer_id','rationale','question','split']:
                    probe[k]='LEAK_SENTINEL'
                assert project(probe)==payload and features(probe,attacks,types,modes)==v
                assert sum(v[:19])==1 and sum(v[19:37])==len(r['defender_types']) and sum(v[37:])==1
                vectors.append(v);ys.append(target);ws.append(meta['inverse_group_weight_subset'])
                tokens.append(text);choice_rows.append(dict(metadata=meta,label_ids=[x[0] for x in letters],
                    target=ct,expected=[int(i==ct) for i in range(6)],option_ids=option_ids))
        # Batch tokenization, preserving full native prefixes and no appended answer tokens.
        with (output/f'{subset}.jevk5.tokens.jsonl').open('w') as f:
            for start in range(0,n,256):
                batch=tok(tokens[start:start+256],add_special_tokens=False,padding=False,truncation=False)['input_ids']
                for j,ids in enumerate(batch,start):
                    assert 0<len(ids)<=6144
                    assert tok.decode(ids,skip_special_tokens=False)==tokens[j]
                    lengths.append(len(ids));line(f,dict(choice_rows[j],input_ids=ids))
        x=np.array(vectors,dtype=np.uint8);y=np.array(ys,dtype=np.int64);weights=np.array(ws,dtype=np.float64)
        np.savez_compressed(output/f'{subset}.classification.npz',X=x,y=y,inverse_group_weight_subset=weights)
        with np.load(output/f'{subset}.classification.npz',allow_pickle=False) as z:
            assert np.array_equal(z['X'],x) and np.array_equal(z['y'],y)
            assert np.allclose(z['inverse_group_weight_subset'],weights)
        # Independently align persisted representations and source labels by row.
        paths=[output/f'{subset}.{kind}.jsonl' for kind in ['classification','choice','jevk5.tokens']]
        saved=[[json.loads(s) for s in p.read_text().splitlines()] for p in paths]
        assert all(len(a)==n for a in saved)
        for r,c,q,t in zip(part,*saved):
            assert c['metadata']['id']==q['metadata']['id']==t['metadata']['id']==r['id']
            assert CLASSES[c['target_class']]==r['multiplier']
            assert list(q['input']['question']['criteria'])[q['target_index']]==r['answer_id']
            assert q['target_index']==t['target'] and q['target_distribution']==t['expected']
        assert np.isclose(weights.sum(),len(counts))
        totals[subset]=dict(rows=n,semantic_groups=len(counts),class_counts=dict(Counter(ys)))
        print(subset,n,'validated',flush=True)
    dump(output/'schema.json',dict(feature_names=feature_names,class_multipliers=CLASSES,
         choice_letters=list('ABCDEF'),label_ids=[x[0] for x in letters],format='gen9-type-system1-v1',
         input_fields=['features OR input.state/input.question OR input_ids'],
         classification_loss='CE(six_class_logits, target_class)',choice_loss='CE(last_input_logits[label_ids], target)',
         weight_policy='Optional; subset weight sums to one per group within each file. all weight is for combined pool. Do not multiply both.',
         split='train_pool_only'))
    validation=dict(passed=True,rows=len(rows),subsets=totals,feature_dimensions=57,classes=6,
        input_tokens={'min':min(lengths),'max':max(lengths)},native_template_checked=len(rows),
        label_and_metadata_mutation_checked=len(rows),persisted_rows_checked=len(rows),
        single_token_choices=True,no_answer_completion=True,model_loaded=False,training_executed=False)
    dump(output/'validation.json',validation)
    shutil.copyfile(HERE/'README.md',output/'README.md');shutil.copyfile(HERE/'losses.py',output/'losses.py')
    shutil.copyfile(ROOT/'integration/jevk5_battle/LICENSE',output/'PROMPT_LICENSE')
    shutil.copyfile(ROOT/'integration/jevk5_battle/NOTICE',output/'PROMPT_NOTICE')
    src=output/'source';src.mkdir()
    for p in HERE.glob('*.py'):shutil.copyfile(p,src/p.name)
    dump(output/'manifest.json',dict(schema='gen9-type-system1-v1',plan='EP-193',parent=str(source),
         parent_manifest_sha256=sha(source/'manifest.json'),parent_canonical_sha256=sha(source/'canonical.jsonl'),
         tokenizer=str(MODEL),tokenizer_files={p.name:sha(p) for p in MODEL.iterdir() if p.is_file() and ('token' in p.name or 'chat' in p.name)},
         prompt_source_sha256=sha(ROOT/'integration/jevk5_battle/upstream_prompt.py'),
         validation=validation,files={str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()}))
    (output/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(output)}\n' for p in sorted(output.rglob('*'))
        if p.is_file() and p.name!='checksums.sha256'))
    return validation


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SOURCE);p.add_argument('--output',type=Path,default=OUTPUT)
    args=p.parse_args();print(json.dumps(build(args.source,args.output),indent=2))
