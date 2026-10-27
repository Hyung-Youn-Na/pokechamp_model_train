"""Streaming source verification and compact, read-only token stores."""
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import random
import numpy as np
from .config import CONFIG, MODEL, ROOT, SOURCES, SHARES
from integration.jevk5_battle import upstream_prompt as official


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def dump(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(path)


def rows(path):
    with Path(path).open() as f:
        for line in f:yield json.loads(line)


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def render(row, tokenizer=None):
    inp=row['input'];assert set(inp)=={'state','question'}
    question=inp['question'];options=official.decision_options(question)
    text=official.prompt_text(inp['state'],question['instructions'],[v for _,v in options])
    if tokenizer is not None:
        native=tokenizer.apply_chat_template(official.messages(inp['state'],question['instructions'],[v for _,v in options]),
                    tokenize=False,add_generation_prompt=True,enable_thinking=False)
        assert text==native,'native nonthinking template differs'
    return text,[k for k,_ in options]


def normalized_input(row):
    # Candidate order is immaterial to scene identity; retain question event/conditions.
    inp=copy.deepcopy(row['input'])
    inp['question']['criteria']=sorted(inp['question']['criteria'].values())
    return digest(inp)


def group_for(domain,row):
    m=row['metadata']
    if domain=='type':return m['semantic_group']
    if domain=='replay':return m['replay_group']
    if domain=='conditional':return m['profile_group']
    if domain=='role':
        answer=list(row['input']['question']['criteria'].values())[row['target_index']]
        return m['queried_role_id']+':'+answer
    return m['rule_id']


def weights(metadata):
    counts=Counter((m['domain'],m['group']) for m in metadata)
    raw=np.array([counts[(m['domain'],m['group'])]**-.5 for m in metadata],dtype=np.float64)
    totals=defaultdict(float)
    for m,w in zip(metadata,raw):totals[m['domain']]+=w
    for i,m in enumerate(metadata):raw[i]*=SHARES[m['domain']]/totals[m['domain']]*len(metadata)
    assert np.isfinite(raw).all() and (raw>0).all()
    return raw


class TokenWriter:
    def __init__(self,path):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=False)
        self.stream=(self.path/'tokens.i32').open('xb');self.offsets=[0];self.labels=[];self.targets=[];self.metadata=[]
    def add(self,ids,labels,target,metadata):
        assert 0<len(ids)<=CONFIG['max_length'] and 2<=len(labels)<=11
        assert len(set(labels))==len(labels) and 0<=target<len(labels)
        a=np.asarray(ids,dtype='<i4');self.stream.write(a.tobytes());self.offsets.append(self.offsets[-1]+len(a))
        self.labels.append(labels+[-1]*(11-len(labels)));self.targets.append(target);self.metadata.append(metadata)
    def close(self,training=False):
        self.stream.close();np.save(self.path/'offsets.npy',np.array(self.offsets,dtype=np.int64))
        np.save(self.path/'labels.npy',np.array(self.labels,dtype=np.int64));np.save(self.path/'targets.npy',np.array(self.targets,dtype=np.int64))
        np.save(self.path/'weights.npy',weights(self.metadata) if training else np.ones(len(self.metadata),dtype=np.float64))
        with (self.path/'metadata.jsonl').open('x') as f:
            for m in self.metadata:f.write(json.dumps(m,ensure_ascii=False)+'\n')
        dump(self.path/'manifest.json',dict(rows=len(self.targets),tokens=self.offsets[-1],
            files={p.name:sha(p) for p in self.path.iterdir() if p.is_file()}))


class TokenStore:
    def __init__(self,path):
        self.path=Path(path)
        self.tokens=np.memmap(self.path/'tokens.i32',dtype='<i4',mode='r')
        for name in ['offsets','labels','targets','weights']:setattr(self,name,np.load(self.path/f'{name}.npy',mmap_mode='r'))
        self.metadata=list(rows(self.path/'metadata.jsonl'))
    def __len__(self):return len(self.targets)
    def __getitem__(self,i):
        return dict(input_ids=self.tokens[self.offsets[i]:self.offsets[i+1]],
                    label_ids=self.labels[i][self.labels[i]>=0],target=int(self.targets[i]),
                    weight=float(self.weights[i]),**self.metadata[i])
    @property
    def lengths(self):return np.diff(self.offsets)


def epoch_batches(size,epoch):
    order=list(range(size));random.Random(CONFIG['seed']+epoch).shuffle(order)
    for start in range(0,size,CONFIG['global_batch']):yield order[start:start+CONFIG['global_batch']]


def microbatches(indices,lengths,limit):
    assert limit in CONFIG['microbatch_candidates']
    batch=[]
    for i in sorted(indices,key=lambda i:(int(lengths[i]),i)):
        if batch and (len(batch)>=limit or int(lengths[i])*(len(batch)+1)>CONFIG['padded_token_budget']):
            yield batch;batch=[]
        batch.append(i)
    if batch:yield batch


def prepare_training(output):
    from transformers import AutoTokenizer
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    letter_ids=[tok.encode(c,add_special_tokens=False) for c in 'ABCDEFGHIJK']
    assert all(len(v)==1 for v in letter_ids)
    writer=TokenWriter(output/'train');seen=set();source_files={};counts={};lengths=[]
    try:
        for domain,folder,subsets,expected in SOURCES:
            source=ROOT/'exports'/folder
            for entry in (source/'checksums.sha256').read_text().splitlines():
                expected_sha,name=entry.split('  ',1);assert sha(source/name)==expected_sha,(folder,name)
            n=0
            for subset in subsets:
                cp=source/f'{subset}.choice.jsonl';tp=source/f'{subset}.jevk5.tokens.jsonl'
                source_files[str(cp)]=sha(cp);source_files[str(tp)]=sha(tp)
                for c,t in zip(rows(cp),rows(tp),strict=True):
                    text,options=render(c,tok);ids=tok.encode(text,add_special_tokens=False)
                    assert ids==t['input_ids'] and options==t['option_ids']
                    target=c['target_index'];k=len(options);one=[int(i==target) for i in range(k)]
                    assert c['target_distribution']==t['expected']==one and sum(one)==1
                    assert t['target']==target and t['metadata']==c['metadata']
                    assert t['label_ids']==[v[0] for v in letter_ids[:k]]
                    criteria=c['input']['question']['criteria'];assert len(set(criteria.values()))==k
                    probe=copy.deepcopy(c);probe['metadata']={'sentinel':'LEAK'};probe['target_index']=-1;probe['target_distribution']='LEAK'
                    assert render(probe)==(text,options)
                    uid=domain+':'+c['metadata']['id'];assert uid not in seen;seen.add(uid)
                    d=domain+str(c['metadata']['priority']) if domain=='mechanics' else domain
                    writer.add(ids,t['label_ids'],target,dict(id=uid,domain=d,group=group_for(domain,c),
                        input_digest=normalized_input(c),source_metadata=c['metadata']))
                    lengths.append(len(ids));n+=1
            assert n==expected,(domain,n,expected);counts[domain]=n
            print(json.dumps(dict(event='source_verified',domain=domain,rows=n)),flush=True)
        assert len(seen)==130149
        writer.close(training=True)
    finally:
        if not writer.stream.closed:writer.stream.close()
    tok.save_pretrained(output/'tokenizer')
    store=TokenStore(output/'train');actual={d:float(sum(w for m,w in zip(store.metadata,store.weights) if m['domain']==d)/len(store)) for d in SHARES}
    assert all(abs(actual[d]-SHARES[d])<1e-10 for d in SHARES)
    for e in range(3):
        batches=list(epoch_batches(len(store),e));flat=sum(batches,[])
        assert len(batches)==1356 and len(batches[-1])==69 and sorted(flat)==list(range(len(store)))
    result=dict(passed=True,rows=len(store),counts=counts,domain_weight_share=actual,input_tokens=sum(lengths),
                total_exposure_tokens=3*sum(lengths),min_tokens=min(lengths),max_tokens=max(lengths),sources=source_files,
                truncations=0,completion_tokens=0,epoch_exposure='exactly_once')
    dump(output/'training-validation.json',result);return result
