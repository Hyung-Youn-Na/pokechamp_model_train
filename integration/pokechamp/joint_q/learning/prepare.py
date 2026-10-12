import json
from pathlib import Path
import time
from ..data import TrainingRecord, load
from ..serializer import JointInput
from ..storage import atomic, digest, jsonl, read, rows, sha
from .artifacts import environment, now, shuffled, source_hashes
from .config import CONFIG, EXPECTED
from .model import snapshot, tokenizer
from .render import render, EncodedInput


def prepare(data, out, download=False):
    start = time.perf_counter()
    directory = Path(out)/'prepared'
    directory.mkdir(parents=True,exist_ok=False)
    path, tok = snapshot(download), tokenizer()
    from huggingface_hub import HfApi
    from .config import MODEL, REVISION
    official=HfApi(token=False).model_info(MODEL,revision=REVISION,files_metadata=True)
    if official.sha!=REVISION:
        raise ValueError('official model revision differs')
    lfs={f.rfilename:f.lfs.sha256 for f in official.siblings if f.lfs is not None}
    for name,expected in lfs.items():
        if (path/name).exists() and sha(path/name)!=expected:
            raise ValueError('downloaded file differs from official LFS SHA-256: '+name)
    atomic(directory/'model-source.json',dict(model=MODEL,revision=official.sha,
        official_lfs_sha256=lfs,downloaded_lfs_verified=[name for name in lfs if (path/name).exists()]))
    copy = read(Path(data)/'copy-verification.json')
    if not copy.get('passed'):
        raise ValueError('verified EX-065 copy required')
    # The copy receipt is checked independently against the supplied source hashes.
    for name, entry in copy['files'].items():
        if sha(Path(data)/name) != entry['source_sha256']:
            raise ValueError('EX-065 copy checksum differs: '+name)
    raw = rows(Path(data)/'inputs.jsonl')
    meta = read(Path(data)/'manifest.json')
    games = {g['game_id']:g for g in meta['games']}
    if len(games) != 80 or any(r['quarantined'] for r in raw):
        raise ValueError('unexpected missing/quarantined game')
    records = {split:list(load(data,split=split)) for split in EXPECTED}
    observed = {}
    metadata = {}
    for split, expected in EXPECTED.items():
        selected = [r for r in raw if r['split']==split]
        counts=(len({r['game_id'] for r in selected}),len(records[split]),sum(len(r.q) for r in records[split]))
        if counts != expected or len(selected) != len(records[split]):
            raise ValueError(f'{split} denominator differs: {counts} != {expected}')
        observed[split]=dict(games=counts[0],observations=counts[1],candidates=counts[2])
        for r in selected:
            g=games[r['game_id']]
            if g['split'] != split:
                raise ValueError('game/split identity mismatch')
            metadata[r['observation_id']]=dict(split=split,game_id=r['game_id'],
                team_number=g['team_number'],group_id=g['group_id'],fingerprint=r['fingerprint'])
    for field in ('group_id','fingerprint'):
        sets={split:{m[field] for m in metadata.values() if m['split']==split} for split in EXPECTED}
        if any(sets[a]&sets[b] for a,b in [('train','validation'),('train','test'),('validation','test')]):
            raise ValueError('split overlap in '+field)
    jsonl(directory/'metadata.jsonl',[dict(observation_id=k,**v) for k,v in metadata.items()])
    tok.save_pretrained(directory/'tokenizer')
    summaries, isolation = {}, 0
    for split, epoch in [('train',0),('validation',0)]+[('train',e) for e in range(1,4)]:
        sequence=records[split] if epoch==0 else list(shuffled(records[split],epoch))
        encoded_rows=[]
        for i,r in enumerate(sequence):
            encoded=render(r.input,tok)
            altered=TrainingRecord('private-observation-id',r.input,tuple(1-q for q in r.q))
            if altered.input != r.input or altered.input.action_ids != encoded.action_ids:
                raise ValueError('target/private mutation changed model input')
            # Explicitly vary saved teacher/private/provenance fields. Only the
            # loader's immutable model_input bytes may cross the renderer API.
            stored=dict(model_input=r.input.payload_json,q_targets=altered.q,
                        private={'snapshot':'changed'},seed=-1,observation_id='changed')
            if JointInput(stored['model_input']) != r.input:
                raise ValueError('private record mutation changed input')
            if epoch==0:
                if render(altered.input,tok) != encoded:
                    raise ValueError('target mutation changed tokens')
                isolation+=1
            by_id=dict(zip(r.input.action_ids,r.q,strict=True))
            if tuple(by_id[k] for k in encoded.action_ids) != r.q:
                raise ValueError('target/readout order mismatch')
            encoded_rows.append(encoded.to_row(r.observation_id))
            if (i+1)%100==0:
                atomic(directory/'progress.json',dict(phase='tokenize',split=split,epoch=epoch,
                    observations=i+1,elapsed_seconds=time.perf_counter()-start))
        name=f'{split}-epoch{epoch}.jsonl'
        jsonl(directory/name,encoded_rows)
        lengths=[e['tokens'] for e in encoded_rows]
        summaries[name]=dict(observations=len(lengths),minimum=min(lengths),maximum=max(lengths),
            mean=sum(lengths)/len(lengths),tokens=sum(lengths),
            longest=max(encoded_rows,key=lambda r:r['tokens'])['observation_id'])
    summaries['test']='not tokenized before final configuration lock'
    base_files={str(p.resolve()):sha(p) for p in sorted(path.iterdir()) if p.is_file()}
    tokenizer_names=('tokenizer','vocab','merges','chat_template')
    manifest=dict(created_at=now(),config=CONFIG,data_directory=str(Path(data).resolve()),
        data_files={n:sha(Path(data)/n) for n in ('inputs.jsonl','targets.jsonl','manifest.json','copy-verification.json')},
        base_files=base_files,tokenizer_files={p.name:sha(p) for p in path.iterdir() if p.name.startswith(tokenizer_names)},
        sources=source_hashes(),packages=environment(),denominators=observed,
        token_summary=summaries,target_private_isolation_observations=isolation,
        prepared_files={str(p.relative_to(directory)):sha(p) for p in directory.rglob('*')
                        if p.is_file() and p.name!='progress.json'},truncated=0,excluded=0)
    atomic(directory/'manifest.json',manifest,immutable=True)
    atomic(directory/'progress.json',dict(phase='complete',elapsed_seconds=time.perf_counter()-start))
    return manifest


def encoded_rows(out, split, epoch=0):
    values=rows(Path(out)/'prepared'/f'{split}-epoch{epoch}.jsonl')
    if len({r['observation_id'] for r in values}) != len(values):
        raise ValueError('duplicate encoded observation')
    return [(r['observation_id'],EncodedInput.from_row(r)) for r in values]


def aligned_records(data, encoded, split):
    by_id={r.observation_id:r for r in load(data,split=split)}
    if set(by_id) != {oid for oid,e in encoded}:
        raise ValueError('encoded record coverage mismatch')
    return [(by_id[oid].reordered(e.action_ids),e) for oid,e in encoded]
