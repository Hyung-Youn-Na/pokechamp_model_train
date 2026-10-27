"""Predeclared T=1 metrics and pair-cluster, domain-stratified inference."""
from collections import defaultdict
import numpy as np
from .config import DOMAINS, CONFIG


def prediction(row,logits):
    z=np.asarray(logits,dtype=np.float64);logp=z-np.max(z);logp-=np.log(np.exp(logp).sum());p=np.exp(logp)
    y=row['target'];choice=int(p.argmax());one=np.zeros(len(p));one[y]=1
    return dict(id=row['id'],domain=row['domain'],group=row['group'],target=y,logits=z.tolist(),probabilities=p.tolist(),
                choice=choice,correct=choice==y,nll=float(-logp[y]),brier=float(((p-one)**2).sum()),confidence=float(p[choice]))


def metrics(rows):
    assert rows
    ece=0
    for i in range(10):
        group=[r for r in rows if i/10<=r['confidence']<(i+1)/10 or i==9 and r['confidence']==1]
        if group:ece+=len(group)/len(rows)*abs(np.mean([r['correct'] for r in group])-np.mean([r['confidence'] for r in group]))
    return dict(n=len(rows),correct=sum(r['correct'] for r in rows),accuracy=float(np.mean([r['correct'] for r in rows])),
        nll=float(np.mean([r['nll'] for r in rows])),brier=float(np.mean([r['brier'] for r in rows])),ece=float(ece),temperature=1.)


def summarize(rows):
    by=defaultdict(list)
    for r in rows:by[r['domain']].append(r)
    result={d:metrics(v) for d,v in by.items()}
    return dict(overall=metrics(rows),domains=result,
                macro_accuracy=float(np.mean([result[d]['accuracy'] for d in DOMAINS])) if set(DOMAINS)<=set(by) else None,
                macro_nll=float(np.mean([result[d]['nll'] for d in DOMAINS])) if set(DOMAINS)<=set(by) else None)


def select(epochs):
    assert sorted(x['epoch'] for x in epochs)==[1,2,3]
    return min(epochs,key=lambda x:(-x['metrics']['macro_accuracy'],x['metrics']['macro_nll'],x['epoch']))


def bootstrap(base,tuned):
    a={r['id']:r for r in base};b={r['id']:r for r in tuned};assert a.keys()==b.keys()
    domains=defaultdict(lambda:defaultdict(list))
    for k,x in a.items():
        y=b[k];assert (x['domain'],x['group'],x['target'])==(y['domain'],y['group'],y['target'])
        if x['domain'] in DOMAINS:domains[x['domain']][x['group']].append(int(y['correct'])-int(x['correct']))
    rng=np.random.default_rng(CONFIG['seed']);samples=np.zeros(10000);point=[]
    for d in DOMAINS:
        groups=domains[d];assert len(groups)==128 and all(len(v)==2 for v in groups.values())
        values=np.array([np.mean(groups[k]) for k in sorted(groups)])
        point.append(float(values.mean()));samples+=values[rng.integers(0,len(values),(10000,len(values)))].mean(1)/7
    return dict(difference=float(np.mean(point)),ci95=np.quantile(samples,[.025,.975]).tolist(),
                iterations=10000,seed=CONFIG['seed'],unit='contrast pair, stratified within seven domains')
