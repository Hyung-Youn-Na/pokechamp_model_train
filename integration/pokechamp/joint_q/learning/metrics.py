"""Observation-weighted metrics and paired resampling from stored predictions."""
from collections import defaultdict
import numpy as np
from .config import CONFIG

METRICS=('mse','mae','soft_target_brier','regret','best_action_rate')


def observation(row):
    q,p=np.array(row['target_q'],dtype=np.float64),np.array(row['predicted_q'],dtype=np.float64)
    if q.shape!=p.shape or q.ndim!=1 or not len(q) or not np.isfinite(p).all() or np.any((p<0)|(p>1)):
        raise ValueError('invalid stored prediction')
    chosen=int(np.argmax(p))
    mse=float(np.mean((p-q)**2))
    return dict(mse=mse,mae=float(np.mean(np.abs(p-q))),soft_target_brier=2*mse,
                regret=float(q.max()-q[chosen]),best_action_rate=float(q[chosen]==q.max()),
                discriminating=bool(q.max()>q.min()),candidates=len(q),chosen_id=row['action_ids'][chosen])


def aggregate(values):
    values=list(values)
    return dict(observations=len(values),candidates=sum(r['candidates'] for r in values),
                **{m:float(np.mean([r[m] for r in values])) if values else None for m in METRICS})


def report(predictions):
    scores=[(r,observation(r)) for r in predictions]
    result={}
    for name,filtered in [('all',scores),('discriminating',[(r,s) for r,s in scores if s['discriminating']])]:
        groups=defaultdict(list)
        games,teams=defaultdict(list),defaultdict(list)
        for r,s in filtered:
            groups[r['fingerprint']].append(s)
            games[r['game_id']].append(s)
            teams[str(r['team_number'])].append(s)
        equal=[]
        for values in groups.values():
            equal.append(dict(candidates=values[0]['candidates'],
                              **{m:float(np.mean([s[m] for s in values])) for m in METRICS}))
        result[name]=dict(metrics=aggregate(s for r,s in filtered),
            per_game={g:aggregate(v) for g,v in games.items()},
            per_opponent_team={g:aggregate(v) for g,v in teams.items()},
            duplicates=dict(first_observation=aggregate(v[0] for v in groups.values()),
                equal_fingerprint_weight=aggregate(equal),duplicates=len(filtered)-len(groups)))
    return result


def paired_bootstrap(selected, baseline):
    if ([r['observation_id'] for r in selected] != [r['observation_id'] for r in baseline]
            or any(a['action_ids']!=b['action_ids'] or a['target_q']!=b['target_q']
                   for a,b in zip(selected,baseline,strict=True))):
        raise ValueError('paired prediction coverage/order/target differs')
    groups=sorted({r['group_id'] for r in selected})
    if len(groups)!=5:
        raise ValueError('expected five independent test team groups')
    rng=np.random.default_rng(CONFIG['bootstrap_seed'])
    samples=rng.integers(0,5,size=(CONFIG['bootstrap_replicates'],5))
    result={}
    for scope in ('all','discriminating'):
        differences={g:[] for g in groups}
        for a,b in zip(selected,baseline,strict=True):
            x,y=observation(a),observation(b)
            if scope=='discriminating' and not x['discriminating']:
                continue
            differences[a['group_id']].append([x[m]-y[m] for m in METRICS])
        sums=np.array([np.sum(differences[g],axis=0) if differences[g] else np.zeros(len(METRICS)) for g in groups])
        counts=np.array([len(differences[g]) for g in groups])
        denominator=counts[samples].sum(1)
        valid=denominator>0
        draws=sums[samples].sum(1)[valid]/denominator[valid,None]
        result[scope]=dict(groups=5,observations=int(counts.sum()),replicates=len(draws),
            undefined_replicates=int((~valid).sum()),seed=CONFIG['bootstrap_seed'],
            contrasts={m:dict(selected_minus_baseline=float(sums[:,i].sum()/counts.sum()),
                percentile_95_ci=np.quantile(draws[:,i],[.025,.975]).tolist()) for i,m in enumerate(METRICS)})
    return result
