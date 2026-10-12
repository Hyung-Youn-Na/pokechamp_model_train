"""팀 파일 기반 409종 열람 DB를 재현 가능하게 생성·검사한다. 원본 패키지/팀은 읽기 전용."""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rules import BANNED_ROLES, EXTRA_FUNCTIONS, infer

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT/'project_context/exec-plans/evidence/ep091'
PACKAGE = ROOT/'exports/pokemon-role-data/pokemon_role_db_gen9ou_2026-08_1695'
SHA = lambda b: hashlib.sha256(b).hexdigest()
ID = lambda x: re.sub('[^a-z0-9]', '', x.lower())


def read_json(p): return json.loads(Path(p).read_text())


def write_json(p, value, two_places=False):
    text=json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    if two_places:
        text=re.sub(r'(: )(-?\d+\.\d+(?:[eE][+-]?\d+)?)(,?\n)',lambda m:m[1]+format(float(m[2]),'.2f')+m[3],text)
    Path(p).write_text(text)


def signature(m):
    return (m['id'],m['item'],m['ability'],tuple(sorted(m['moves'])),tuple(m['types']),m['tera_type'])


def parse_team(text, dex):
    members=[]
    for block in re.split(r'\n\s*\n',text.strip()):
        lines=[v.strip() for v in block.splitlines()]
        label,sep,item=lines[0].partition(' @ ')
        label=re.sub(r' \([MF]\)$','',label)
        match=re.search(r'\(([^)]+)\)$',label)
        name=match.group(1) if match else label
        key=ID(name)
        if key not in dex['species']: raise ValueError(f'종 식별 불가: {name}')
        fields=dict(v.split(': ',1) for v in lines[1:] if ': ' in v)
        moves=[ID(v[2:]) for v in lines if v.startswith('- ')]
        assert 1<=len(moves)<=4 and len(moves)==len(set(moves)),(key,moves)
        assert all(m in dex['moves'] for m in moves),(key,moves)
        ability=ID(fields['Ability']);tera=ID(fields['Tera Type']);item=ID(item) if sep else 'none'
        assert ability in dex['abilities'] and (item=='none' or item in dex['items']), (key,ability,item)
        assert tera in {'normal','fire','water','electric','grass','ice','fighting','poison','ground','flying','psychic','bug','rock','ghost','dragon','dark','steel','fairy','stellar'}
        members.append(dict(id=key,pokemon=dex['species'][key]['name'],item=item,ability=ability,
                            moves=moves,types=dex['species'][key]['types'],tera_type=tera))
    assert len(members)==6, len(members)
    return members


def atom_key(e):
    if e['type']=='all_of': return ('all_of',tuple(sorted(atom_key(c) for c in e['conditions'])))
    return (e['type'],e['value'])


def known(m):
    return {('item',m['item']),('ability',m['ability']),('tera_type',m['tera_type'])}|{('move',x) for x in m['moves']}|{('type',x) for x in m['types']}


def match(e,k):
    if e['type']=='all_of':return all(match(c,k) for c in e['conditions'])
    return (e['type'],e['value']) in k


def flat_match(e,k):
    atoms=[(c['type'],c['value']) for c in e['conditions']] if e['type']=='all_of' else [(e['type'],e['value'])]
    return set(atoms)<=k


def assess(mon, record, independent=False):
    k=known(mon); result={'assigned':[],'mixed':[],'contradicted':[],'unmatched':[]}
    for role in record['possible_roles']:
        fn=flat_match if independent else match
        signals={p:[e for e in es if fn(e,k)] for p,es in role['evidence'].items()}
        positive=bool(signals['strong'] or signals['supporting']);negative=bool(signals['contradictory'])
        decision={(True,False):'assigned',(True,True):'mixed',(False,True):'contradicted',(False,False):'unmatched'}[positive,negative]
        result[decision].append(role['role'])
    return result


def cleaned_source(src):
    """이전 열람본의 사용자 편집: source/notes/status·노력치 제외, 남은 결합 조건 보존."""
    profiles=set(src['taxonomy'].get('evidence_profile_definitions',{}))
    ev_text=re.compile(r'\bEVs?\b|effort\s+values?|invest(?:ment|ments|ed|s|ing)?\b|노력치|\bev_profile\b',re.I)
    def project(e):
        if e['type']=='ev_profile' or (e['type']=='speed_tier' and e.get('value') in profiles):return None
        if e['type']=='all_of':
            children=[v for c in e['conditions'] if (v:=project(c)) is not None]
            if not children:return None
            if len(children)==1:return children[0]
            result={'type':'all_of','conditions':children}
        else: result={'type':e['type'],'value':e['value']}
        explanation=e.get('explanation')
        if explanation and not ev_text.search(explanation) and not any(v in explanation for v in profiles):result['explanation']=explanation
        return result
    DROP=object()
    def clean(x,key=''):
        if isinstance(x,dict):
            return {k:c for k,v in x.items() if not (any(p in {'source','sources','notes','status'} for p in k.split('_')) or k in {'metadata','spreads','distribution_denominators','distribution_totals','evidence_profile_definitions','ev_profile'}) and (c:=clean(v,k)) is not DROP}
        if isinstance(x,list):return [c for v in x if (c:=clean(v,key)) is not DROP]
        if isinstance(x,str) and (ev_text.search(x) or (key in {'explanation','prior_rationale','description'} and any(v in x for v in profiles))):return DROP
        return x
    out={}
    for mon in src['pokemon']:
        rec=clean(mon)
        for field,key in [('possible_roles','role'),('set_archetypes','id')]:
            orig={r[key]:r for r in mon[field]}
            for r in rec[field]:r['evidence']={p:[v for e in es if (v:=project(e)) is not None] for p,es in orig[r[key]]['evidence'].items()}
        rec['possible_roles']=[r for r in rec['possible_roles'] if any(r['evidence'].values()) and (rec['id'],r['role']) not in BANNED_ROLES]
        role_ids={r['role'] for r in rec['possible_roles']}
        for s in rec['set_archetypes']:s['roles']=[r for r in s['roles'] if r in role_ids]
        rec['set_archetypes']=[s for s in rec['set_archetypes'] if s['roles']]
        out[rec['id']]=rec
    return out


def build(output_dir):
    output_dir.mkdir(parents=True,exist_ok=True)
    mechanics_path=EVIDENCE/'mechanics.json';original_path=PACKAGE/'data/generated/gen9ou_role_db.json';baseline_path=EVIDENCE/'before-44.json'
    originals={str(p):p.read_bytes() for p in [mechanics_path,original_path,baseline_path]}
    dex=json.loads(originals[str(mechanics_path)]);original=json.loads(originals[str(original_path)]);baseline=json.loads(originals[str(baseline_path)])
    team_files=sorted(Path('/tmp/metamon_cache/teams/modern_replays/gen9ou').rglob('*.gen9ou_team'))
    fixed=sorted((ROOT/'pokechamp/poke_env/data/static/teams/gen9ou').glob('gen9ou*.txt'),key=lambda p:int(p.stem[6:]))
    assert len(team_files)==25192 and len(fixed)==13
    stats=defaultdict(lambda:dict(count=0,teams=0,abilities=Counter(),items=Counter(),moves=Counter(),tera_types=Counter()))
    manifests=[];unique={};slot_index=[];names={};set_counts=Counter();counts_by_species=Counter()
    for corpus,files in [('modern_replays',team_files),('fixed',fixed)]:
        for p in files:
            raw=p.read_bytes();members=parse_team(raw.decode(),dex)
            origin={'corpus':corpus,'path':str(p),'sha256':SHA(raw)};manifests.append(origin)
            seen=set()
            for slot,m in enumerate(members,1):
                key=signature(m);sid=SHA(json.dumps(key,separators=(',',':')).encode())[:24]
                if sid in unique:assert signature(unique[sid]['pokemon'])==key
                else:unique[sid]={'pokemon':m,'occurrences':0,'examples':[],'corpus_counts':Counter()}
                u=unique[sid];u['occurrences']+=1;u['corpus_counts'][corpus]+=1
                if len(u['examples'])<3:u['examples'].append(dict(path=str(p),slot=slot))
                slot_index.append((len(manifests)-1,slot,sid))
                counts_by_species[m['id']]+=1;names[m['id']]=m['pokemon'];st=stats[m['id']];st['count']+=1
                st['abilities'][m['ability']]+=1;st['items'][m['item']]+=1;st['tera_types'][m['tera_type']]+=1
                st['moves'].update(m['moves']);seen.add(m['id'])
            for sp in seen:stats[sp]['teams']+=1
    assert len(stats)==409 and len(slot_index)==151230
    baseline_map={p['id']:p for p in baseline['pokemon']}
    imported=cleaned_source(original)
    initial={}
    for sp in stats:
        initial[sp]=copy.deepcopy(baseline_map.get(sp,imported.get(sp,dict(id=sp,pokemon=names[sp],format='gen9ou',common_functions=[],possible_roles=[],set_archetypes=[],typical_constraints=[]))))
        if sp in baseline_map:assert initial[sp]==baseline_map[sp]
    expanded=copy.deepcopy(initial)
    # 같은 종·역할·조건을 하나의 추가 근거로 모으고 대응하는 실제 관측을 추적한다.
    additions={};rule_inventory={}
    for sid,u in sorted(unique.items()):
        m=u['pokemon']
        for signal in infer(m,dex):
            assert all(c in known(m) for c in signal.conditions), (sid,signal)
            key=(m['id'],signal.role,signal.conditions)
            if key not in additions:additions[key]={'signal':signal,'occurrences':0,'sets':0,'examples':[], 'rules':set()}
            a=additions[key];a['rules'].add(signal.rule)
            # 동일 실제 세트의 같은 근거를 중복 집계하지 않는다.
            if sid not in a.get('_seen',set()):
                a.setdefault('_seen',set()).add(sid);a['occurrences']+=u['occurrences'];a['sets']+=1
                if len(a['examples'])<3:a['examples'].append(sid)
            rule_inventory.setdefault(signal.rule,{'roles':set(),'functions':set(),'explanations':set()})
            ri=rule_inventory[signal.rule];ri['roles'].add(signal.role);ri['functions'].update(signal.functions);ri['explanations'].add(signal.explanation)
    provenance=[];new_roles=0;new_evidence=0;existing_evidence=0
    by_species_role=defaultdict(list)
    for key,a in sorted(additions.items()):by_species_role[(key[0],key[1])].append(a)
    for (sp,role_id),signals in sorted(by_species_role.items()):
        rec=expanded[sp];role=next((r for r in rec['possible_roles'] if r['role']==role_id),None)
        if role is None:
            new_roles+=1
            role=dict(role=role_id,prior=None,prior_rationale='실제 저장 세트의 기술·특성·아이템과 효과를 대조한 조건부 기능 추론이다. OU 실전성·역할 빈도에 대한 사전 등급은 평가하지 않았다.',
                      scope='set',functions=[],evidence={'strong':[],'supporting':[],'contradictory':[]})
            rec['possible_roles'].append(role)
        existing={atom_key(e) for es in role['evidence'].values() for e in es}
        archetype_evidence=[]
        for a in signals:
            signal=a['signal'];e=signal.evidence();was_added=atom_key(e) not in existing
            if was_added:role['evidence']['supporting'].append(e);existing.add(atom_key(e));new_evidence+=1
            else:existing_evidence+=1
            role['functions']=sorted(set(role['functions'])|set(signal.functions))
            archetype_evidence.append(e)
            provenance.append(dict(pokemon=sp,role=role_id,rules=sorted(a['rules']),conditions=[dict(type=k,value=v) for k,v in signal.conditions],
                                   appended=was_added,matched_sets=a['sets'],matched_slots=a['occurrences'],example_set_ids=a['examples']))
        arch_id='observed_'+role_id
        assert all(s['id']!=arch_id for s in rec['set_archetypes'])
        rec['set_archetypes'].append(dict(id=arch_id,name='실제 세트의 '+role_id+' 가능성',roles=[role_id],
                                         evidence={'strong':[],'supporting':archetype_evidence,'contradictory':[]}))
        rec['common_functions']=sorted(set(rec['common_functions'])|set(role['functions']))
    total_teams=len(manifests)
    for sp,rec in expanded.items():
        st=stats[sp]
        usage=dict(pokemon=rec['pokemon'],raw_count=st['count'],usage_fraction=round(st['teams']/total_teams,2))
        for f in ['abilities','items','moves','tera_types']:
            usage[f]={k:round(v/st['count'],2) for k,v in sorted(st[f].items(),key=lambda kv:(-kv[1],kv[0]))}
        rec['observed_usage']=usage
        if not rec['typical_constraints']:
            rec['typical_constraints']=[dict(id='conditional_mechanical_inference',description='관측된 구성에서 가능한 기능을 연결한 추론이며 현재 HP·날씨·상대 정보·발동 성공·OU 실전성이나 승률을 보장하지 않는다.')]
    db={k:copy.deepcopy(v) for k,v in baseline.items() if k!='pokemon'}
    db['schema_version']='team-pool-role-db-v2'
    for ident,desc in EXTRA_FUNCTIONS.items():
        assert all(x['id']!=ident for x in db['function_registry']['functions'])
        db['function_registry']['functions'].append(dict(id=ident,description=desc))
    db['function_registry']['version']='team-pool-functions-v2'
    db['pokemon']=[expanded[sp] for sp in sorted(expanded,key=lambda s:(-stats[s]['teams'],s))]
    # 전수 평가: 실제 슬롯을 모두 포함하되 같은 관측 구성의 판정은 재사용한다.
    coverage={};uncovered=[];newly_covered=0;totals=Counter();zero_species=[]
    for sid,u in sorted(unique.items()):
        m=u['pokemon'];old=assess(m,initial[m['id']]);new=assess(m,expanded[m['id']]);independent=assess(m,expanded[m['id']],True)
        assert new==independent
        assert set(old['assigned'])<=set(new['assigned']), (sid,old,new)
        coverage[sid]={'before':old,'after':new}
        n=u['occurrences']
        if not old['assigned']:totals['before_uncovered_slots']+=n
        if not new['assigned']:
            totals['after_uncovered_slots']+=n
            uncovered.append(dict(set_id=sid,**u,assessment=new))
        if old['mixed']:totals['before_mixed_slots']+=n
        if new['mixed']:totals['after_mixed_slots']+=n
        for decision,rs in new.items():totals[decision+'_roles']+=len(rs)*n
    for sp in expanded:
        if not expanded[sp]['possible_roles']:zero_species.append(sp)
    validate(db,initial,baseline_map,dex,provenance,unique)
    manifest=dict(team_files=manifests,input_files=[dict(path=str(p),sha256=SHA(b)) for p,b in originals.items()],
                  code_files=[dict(path=str(p.relative_to(ROOT)),sha256=SHA(p.read_bytes())) for p in [Path(__file__),Path(__file__).with_name('rules.py')]],
                  scope='modern_replays25192 + fixed13; duplicates retained as file records; all observed species/forms, not all legal gen9ou species')
    summary=dict(species_count=len(expanded),team_count=total_teams,slot_count=len(slot_index),unique_role_input_sets=len(unique),
                 reviewed_source_species=sum(x.get('annotation_status')=='reviewed' for x in original['pokemon'] if x['id'] in expanded),
                 existing_44_species=len(baseline_map),new_species=len(expanded)-len(baseline_map),
                 new_roles=new_roles,new_evidence=new_evidence,already_present_evidence=existing_evidence,
                 total_roles=sum(len(m['possible_roles']) for m in expanded.values()),zero_role_species=zero_species,
                 uncovered_unique_sets=len(uncovered),**dict(totals))
    write_json(output_dir/'expanded.json',db,True)
    assert read_json(output_dir/'expanded.json')==db
    write_json(output_dir/'input_manifest.json',manifest)
    write_json(output_dir/'summary.json',summary)
    write_json(output_dir/'additions.json',provenance)
    write_json(output_dir/'rules.json',{k:{p:sorted(vs) for p,vs in v.items()} for k,v in sorted(rule_inventory.items())})
    write_json(output_dir/'uncovered.json',uncovered)
    # 재검토에 필요한 입력/판정은 압축하되 원본 경로·슬롯 연결은 전부 보존한다.
    for filename,rows in [('sets.jsonl.gz',(dict(set_id=sid,**u,assessment=coverage[sid]) for sid,u in sorted(unique.items()))),
                          ('slots.jsonl.gz',(dict(file_index=f,slot=n,set_id=sid) for f,n,sid in slot_index))]:
        with (output_dir/filename).open('wb') as target:
            with gzip.GzipFile(fileobj=target,mode='wb',mtime=0,filename='') as gz:
                for row in rows:gz.write((json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode())
    assert all(Path(p).read_bytes()==b for p,b in originals.items())
    for f in manifests: assert SHA(Path(f['path']).read_bytes())==f['sha256']
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary


def validate(db,initial,baseline_map,dex,provenance,unique):
    ids={m['id'] for m in db['pokemon']};assert len(ids)==409
    role_ids={r['id'] for r in db['taxonomy']['roles']}
    function_ids={f['id'] for f in db['function_registry']['functions']}
    def check_e(e):
        if e['type']=='all_of':
            assert len(e['conditions'])>=2 and all(c['type']!='all_of' for c in e['conditions'])
            assert len({atom_key(c) for c in e['conditions']})==len(e['conditions'])
            for c in e['conditions']:check_e(c)
        else:
            assert e['type'] in {'item','ability','move','type','tera_type'},e
            if e['type'] in {'move','item','ability'}:
                group={'move':'moves','item':'items','ability':'abilities'}[e['type']]
                assert e['value'] in dex[group] or (e['type']=='item' and e['value']=='none'),e
    def forbidden(x):
        if isinstance(x,dict):
            for k,v in x.items():
                assert not any(part in {'source','sources','notes','status'} for part in k.split('_')),k
                assert k not in {'spreads','ev_profile','evidence_profile_definitions','distribution_totals','distribution_denominators'},k
                forbidden(v)
        elif isinstance(x,list):
            for v in x:forbidden(v)
    forbidden(db)
    for rec in db['pokemon']:
        assert rec['id'] in dex['species'] and rec['pokemon']==dex['species'][rec['id']]['name']
        old=initial[rec['id']];roles={r['role']:r for r in rec['possible_roles']}
        assert len(roles)==len(rec['possible_roles'])
        for r in roles.values():
            assert r['role'] in role_ids and (rec['id'],r['role']) not in BANNED_ROLES
            assert r['prior'] in {None,'high','medium','low','niche'}
            assert set(r['functions'])<=function_ids and set(r['functions'])<=set(rec['common_functions'])
            assert r['evidence']['strong'] or r['evidence']['supporting']
            for es in r['evidence'].values():
                for e in es:check_e(e)
        for prev in old['possible_roles']:
            now=roles[prev['role']]
            for key in ('role','prior','scope','prior_rationale'):
                assert now.get(key)==prev.get(key)
            for kind,es in prev['evidence'].items():
                assert all(e in now['evidence'][kind] for e in es)
            assert set(prev['functions'])<=set(now['functions'])
        for s in rec['set_archetypes']:
            assert set(s['roles'])<=roles.keys()
            for es in s['evidence'].values():
                for e in es:check_e(e)
        assert len({s['id'] for s in rec['set_archetypes']})==len(rec['set_archetypes'])
        assert set(old['common_functions'])<=set(rec['common_functions'])
        assert all(s in rec['set_archetypes'] for s in old['set_archetypes'])
        for f in ('abilities','items','moves','tera_types'):
            values=list(rec['observed_usage'][f].values());assert values==sorted(values,reverse=True)
    for p in provenance:
        assert p['matched_sets']>0 and p['matched_slots']>=p['matched_sets']
        for sid in p['example_set_ids']:
            m=unique[sid]['pokemon'];assert m['id']==p['pokemon']
            assert all((c['type'],c['value']) in known(m) for c in p['conditions'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=EVIDENCE/'build')
    build(parser.parse_args().output_dir)
