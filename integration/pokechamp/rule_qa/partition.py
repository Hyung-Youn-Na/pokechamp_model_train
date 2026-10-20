"""Assign source groups, joining duplicated semantic cases before rendering rows."""
from __future__ import annotations
from collections import Counter,defaultdict
import random
from . import SEED
from .records import concise,digest


def normalize_facts(value,key=None):
    if isinstance(value,dict):return {k:normalize_facts(v,k) for k,v in value.items()}
    if isinstance(value,list):
        result=[normalize_facts(v) for v in value]
        if key in ('types','defensive_types','original_types','target_defensive_types','reserve_types','stab_types'):
            return sorted(result)
        if key=='opponent_moves':return sorted(result,key=lambda x:x.get('id',''))
        return result
    if isinstance(value,float) and value.is_integer():return int(value)
    return value

def semantic_key(row):
    q=row['question']
    # Only actual rule-relevant public facts; type order has no meaning in these questions.
    return digest(dict(facts=normalize_facts(concise(q['facts'])),conditions=q['conditions'],question=q['question']))


def state_key(row):
    def normalize(x):
        if isinstance(x,dict):return {k:normalize(v) for k,v in x.items() if k not in ('nickname','request_id')}
        if isinstance(x,list):return [normalize(v) for v in x]
        return x
    return digest(normalize(row['input']))


def components(rows):
    parent={r['spec']['group_id']:r['spec']['group_id'] for r in rows}
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    seen={}
    for row in rows:
        group=row['spec']['group_id']
        for kind,key in [('semantic',semantic_key(row)),('state',state_key(row))]:
            if (kind,key) in seen:
                a,b=find(group),find(seen[kind,key]);parent[a]=b
            else:seen[kind,key]=group
    result=defaultdict(list)
    for group in parent:result[find(group)].append(group)
    return sorted([sorted(v) for v in result.values()])


def assign(rows,groups):
    pairs=defaultdict(list)
    for row in rows:pairs[row['spec']['group_id']].append(semantic_key(row))
    seen_pairs={}
    for group,keys in pairs.items():
        key=digest(sorted(keys))
        if key in seen_pairs:raise ValueError(f'duplicate contrast groups: {seen_pairs[key]} and {group}')
        seen_pairs[key]=group
    clusters=components(rows)
    if groups==1:return {r['spec']['group_id']:'train' for r in rows},clusters
    # Solve connected rule families jointly, so a shared case can belong to any split.
    rule_parent={f'R{r:02}':f'R{r:02}' for r in range(1,25)}
    def find(r):
        while rule_parent[r]!=r:rule_parent[r]=rule_parent[rule_parent[r]];r=rule_parent[r]
        return r
    for cluster in clusters:
        rules=sorted({g.split('-')[0] for g in cluster})
        for r in rules[1:]:rule_parent[find(r)]=find(rules[0])
    families=defaultdict(list)
    for r in rule_parent:families[find(r)].append(r)
    result={}
    for family in sorted(families.values()):
        family=sorted(family);k=len(family)
        items=[c for c in clusters if c[0].split('-')[0] in family]
        random.Random(f'{SEED}:{",".join(family)}:components').shuffle(items)
        target=(4,)*(2*k)
        # State is (validation counts, test counts); unselected components are train.
        paths={(0,)*(2*k):((),())}
        for i,cluster in enumerate(items):
            counts=Counter(g.split('-')[0] for g in cluster)
            weight=tuple(counts[r] for r in family)
            if max(weight)>4:continue
            updated=dict(paths)
            for state,(valid,test) in paths.items():
                for split in (0,1):
                    offset=k*split
                    values=list(state)
                    for j,w in enumerate(weight):values[offset+j]+=w
                    nxt=tuple(values)
                    if max(nxt)>4 or nxt in updated:continue
                    updated[nxt]=(valid+(i,),test) if split==0 else (valid,test+(i,))
            paths=updated
        if target not in paths:
            raise ValueError('cannot allocate 32/4/4 without duplicate leakage for '+','.join(family))
        valid,test=paths[target]
        for i,cluster in enumerate(items):
            label='validation' if i in valid else 'test' if i in test else 'train'
            for group in cluster:result[group]=label
    for r in range(1,25):
        rule=f'R{r:02}'
        counts=Counter(v for g,v in result.items() if g.startswith(rule+'-'))
        if counts!=dict(train=32,validation=4,test=4):raise ValueError(f'{rule}: partition count mismatch {counts}')
    return result,clusters
