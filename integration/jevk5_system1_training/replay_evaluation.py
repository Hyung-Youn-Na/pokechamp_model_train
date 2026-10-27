"""New local replay groups, disjoint by ID, log, and both team signatures."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import pyarrow.parquet as pq
from transformers import AutoTokenizer
from .config import ROOT, MODEL
from .data import rows,sha,dump,digest,render
from integration.replay_ko_system1.build import SOURCE,dex_data,protection,numeric_id,QUESTION
from integration.replay_ko_system1.parser import extract,projection,public_prefix,OUTCOMES
from integration.replay_ko_system1.audit import audit_raw


def build(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True);dex=dex_data()
    excluded_ids,excluded_teams,signature,receipt=protection(dex['species'])
    logs=set();public_logs=set()
    train=ROOT/'exports/replay-ko-system1-v1'
    for r in rows(train/'all.choice.jsonl'):
        m=r['metadata'];excluded_ids.add(m['replay_group']);logs.add(m['source_log_sha256']);excluded_teams.update(m['team_signatures'].values())
    for r in rows(ROOT/'exports/conditional-ko-system1-v1/all.choice.jsonl'):
        excluded_ids.update(numeric_id(v) for v in r['metadata']['source_replays'])
    # Full public-log equivalence is checked against original training sources as well.
    original=Path(json.loads((train/'manifest.json').read_text())['raw_evidence_root'])
    for p in original.glob('*.json'):
        source=json.loads(p.read_text());lines=source['text'].splitlines();public_logs.add(digest(public_prefix(lines,len(lines))))
    initial=dict(ids=len(excluded_ids),teams=len(excluded_teams),logs=len(logs),public_logs=len(public_logs))
    archive=json.loads((SOURCE/'manifest.json').read_text());assert archive['revision']=='b5820ff5d0c8d5e5cec692d55f756b6e5a66a203'
    hashes={r['path']:r['sha256'] for r in archive['files']};used={};counts=Counter();chosen=[];games=[]
    with (output/'rows.jsonl').open('x') as stream:
        for path in sorted((SOURCE/'data').glob('train-*.parquet')):
            relative=str(path.relative_to(SOURCE));assert sha(path)==hashes[relative];used[relative]=hashes[relative];offset=0
            for batch in pq.ParquetFile(path).iter_batches(batch_size=128):
                for j,source in enumerate(batch.to_pylist()):
                    counts['scanned']+=1
                    if source['gamemode']!='gen9ou':continue
                    bid=source['battle_id'];short=numeric_id(bid);lines=source['text'].splitlines()
                    rawsha=hashlib.sha256(source['text'].encode()).hexdigest();pub=digest(public_prefix(lines,len(lines)))
                    if short in excluded_ids or rawsha in logs or pub in public_logs:counts['excluded_identity']+=1;continue
                    teams={'p1':[],'p2':[]}
                    for line in lines:
                        f=line.split('|')
                        if len(f)>3 and f[1].lower()=='poke' and f[2] in teams:teams[f[2]].append(f[3].split(',')[0].replace('*','').rstrip('-'))
                    if any(len(v)!=6 for v in teams.values()):counts['missing_preview']+=1;continue
                    sigs={k:signature(v) for k,v in teams.items()}
                    if set(sigs.values())&excluded_teams:counts['excluded_team']+=1;continue
                    candidates,failures=extract(source['text'],dex['moves']);selected=[]
                    for label in [0,1]:
                        for c in sorted((v for v in candidates if v['target_index']==label),key=lambda v:digest([bid,v['move_index'],20261021])):
                            key=f'ex116-replay-{short}-{c["move_index"]}'
                            order=sorted(range(2),key=lambda v:digest([key,v]));target=order.index(label)
                            row=dict(metadata=dict(id=key,domain='replay',group='replay:'+short,split='validation' if len(games)<128 else 'test',
                                     replay_group=short,replay_id=bid,team_signatures=sigs,source_log_sha256=rawsha,public_log_digest=pub,
                                     source_file=relative,source_row=offset+j,move_line_index=c['move_index']),
                                     input=dict(state=c['state'],question=dict(type='choice',instructions=QUESTION,
                                         criteria={chr(65+i):OUTCOMES[v] for i,v in enumerate(order)})),
                                     target_index=target,target_distribution=[int(i==target) for i in range(2)],
                                     evidence=c['evidence']|dict(frame_end_index=c['frame_end'],turn=c['turn']))
                            ids=tok.encode(render(row,tok)[0],add_special_tokens=False)
                            if len(ids)>6144:counts['over_length']+=1;continue
                            assert row['input']['state']==projection(lines,c['move_index']);audit_raw(source['text'],row)
                            selected.append(row);break
                    if len(selected)!=2:counts['missing_both_labels']+=1;continue
                    excluded_ids.add(short);logs.add(rawsha);public_logs.add(pub);excluded_teams.update(sigs.values())
                    (output/'raw').mkdir(exist_ok=True);dump(output/'raw'/f'{short}.json',source)
                    for row in selected:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
                    games.append(dict(id=short,split=selected[0]['metadata']['split'],teams=sigs,source_log_sha256=rawsha))
                    if len(games)%32==0:print(json.dumps(dict(event='evaluation_replays',games=len(games))),flush=True)
                    if len(games)==384:break
                offset+=batch.num_rows
                if len(games)==384:break
            if len(games)==384:break
        assert len(games)==384,dict(accepted=len(games),counters=counts)
    dump(output/'validation.json',dict(passed=True,games=384,rows=768,initial_exclusions=initial,
                source_manifest=sha(SOURCE/'manifest.json'),source_shards=used,counters=dict(counts),protection=receipt,
                interpretation='balanced realized-outcome prediction, not natural KO probability',games_metadata=games))
