"""Validation-only selection/calibration and paired component inference."""
import numpy as np

def probabilities(logits, temperature=1.):
    z=np.asarray(logits,dtype=np.float64)/temperature
    if not np.isfinite(z).all():raise ValueError('nonfinite logits')
    z-=z.max();p=np.exp(z);return p/p.sum()


def score(row, logits):
    p=probabilities(logits);winner=int(p.argmax())
    return dict(logits=list(logits),probabilities=p.tolist(),choice=row['option_ids'][winner],
                target=row['target'],correct=winner==row['target'],failure=None)


def summarize(rows, temperature=1.):
    correct=[];nll=[];brier=[];conf=[];groups={};rules={}
    for row in rows:
        z=np.asarray(row['logits'],dtype=np.float64)/temperature
        p=probabilities(row['logits'],temperature);ok=int(p.argmax())==row['target']
        correct.append(ok);conf.append(float(p.max()))
        nll.append(float(np.log(np.exp(z-z.max()).sum())+z.max()-z[row['target']]))
        target=np.zeros(len(p));target[row['target']]=1
        brier.append(float(((p-target)**2).sum()))
        groups.setdefault(row['group_id'],[]).append(ok);rules.setdefault(row['rule_id'],[]).append(ok)
    bins=np.minimum((np.array(conf)*10).astype(int),9);ece=0.
    for i in range(10):
        mask=bins==i
        if mask.any():ece+=mask.mean()*abs(np.asarray(correct)[mask].mean()-np.asarray(conf)[mask].mean())
    return dict(n=len(rows),correct=sum(correct),accuracy=float(np.mean(correct)),nll=float(np.mean(nll)),
        brier=float(np.mean(brier)),ece=float(ece),temperature=float(temperature),
        paired=dict(n=len(groups),both_correct=sum(len(v)==2 and all(v) for v in groups.values())),
        rules={k:dict(n=len(v),correct=sum(v),accuracy=float(np.mean(v))) for k,v in sorted(rules.items())})


def choose(epochs):
    assert sorted(e['epoch'] for e in epochs)==[1,2,3]
    return min(epochs,key=lambda e:(-e['metrics']['accuracy'],e['metrics']['nll'],e['epoch']))


def fit_temperature(rows):
    candidates=sorted(set(np.logspace(-1,1,401).tolist()+[1.]))
    values=[(summarize(rows,t)['nll'],abs(t-1),t) for t in candidates]
    best=min(values)
    return dict(temperature=best[2],validation_nll=best[0],grid_count=len(candidates),scope='rule_qa_only')


def bootstrap(base,tuned):
    b={r['id']:r for r in base};t={r['id']:r for r in tuned}
    assert b.keys()==t.keys() and len(b)==192
    components={}
    for ident,x in b.items():
        y=t[ident];assert x['component']==y['component']
        components.setdefault(x['component'],[]).append(int(y['correct'])-int(x['correct']))
    assert len(components)==82
    sums=np.array([sum(v) for _,v in sorted(components.items())]);counts=np.array([len(v) for _,v in sorted(components.items())])
    draw=np.random.default_rng(20261020).integers(0,82,size=(10000,82))
    diffs=sums[draw].sum(1)/counts[draw].sum(1)
    return dict(components=82,replicates=10000,seed=20261020,difference=float(sums.sum()/counts.sum()),ci95=np.quantile(diffs,[.025,.975]).tolist())
