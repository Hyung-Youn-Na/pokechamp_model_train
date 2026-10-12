"""Frozen input provenance and complete atomic optimizer checkpoints."""
from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import random
import shutil
import tempfile
import torch
from ..storage import ROOT, atomic, digest, read, sha
from .config import CONFIG
from .model import rng_state, restore_rng


def now():
    return datetime.now(timezone.utc).isoformat()


def source_hashes():
    paths = list(Path(__file__).parent.glob('*.py'))
    paths += [Path(__file__).parents[1]/(name+'.py') for name in ('data','serializer','storage')]
    paths += [ROOT/'scripts/pokechamp-joint-q']
    paths += [ROOT/'integration/pokechamp/tests/test_joint_q_learning.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.exists()}


def environment():
    return {p:importlib.metadata.version(p) for p in ('torch','transformers','peft','huggingface-hub',
                                                      'safetensors','numpy','tokenizers')}


def assert_frozen(out, data):
    frozen = read(Path(out)/'prepared/manifest.json')
    if frozen['config'] != CONFIG or frozen['sources'] != source_hashes() or frozen['packages'] != environment():
        raise ValueError('frozen source/config/environment changed')
    for name, expected in frozen['data_files'].items():
        if sha(Path(data)/name) != expected:
            raise ValueError('data file changed: '+name)
    for name, expected in frozen['prepared_files'].items():
        if sha(Path(out)/'prepared'/name) != expected:
            raise ValueError('prepared file changed: '+name)
    for path, expected in frozen['base_files'].items():
        if sha(path) != expected:
            raise ValueError('pinned Base file changed: '+path)
    return frozen


def shuffled(records, epoch):
    order = list(records)
    random.Random(f'{CONFIG["seed"]}:observations:{epoch}').shuffle(order)
    for r in order:
        ids = list(r.input.action_ids)
        random.Random(f'{CONFIG["seed"]}:candidates:{epoch}:{r.observation_id}').shuffle(ids)
        yield r.reordered(ids)


def file_manifest(directory):
    directory = Path(directory)
    return {str(p.relative_to(directory)):sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def validate_checkpoint(path):
    path = Path(path)
    manifest = read(path/'files.json')
    actual = file_manifest(path)
    actual.pop('files.json',None)
    if actual != manifest:
        raise ValueError('checkpoint file integrity failure: '+str(path))
    return read(path/'metadata.json')


def save_checkpoint(policy, optimizer, directory, *, cursor, frozen, initial_base_hashes):
    directory = Path(directory)
    directory.parent.mkdir(parents=True,exist_ok=True)
    if directory.exists():
        existing=validate_checkpoint(directory)
        if (existing['cursor']!=cursor or existing['frozen_manifest_sha256']!=digest(frozen)
                or existing['trainable_fingerprints']!=policy.trainable_fingerprints()):
            raise FileExistsError('different completed checkpoint already exists: '+str(directory))
        return directory
    temp = Path(tempfile.mkdtemp(prefix='.'+directory.name+'-',dir=directory.parent))
    try:
        policy.backbone.save_pretrained(temp/'adapter',safe_serialization=True)
        torch.save(policy.head.state_dict(),temp/'value_head.pt')
        torch.save(dict(optimizer=optimizer.state_dict(),rng=rng_state(),cursor=cursor),temp/'state.pt')
        atomic(temp/'metadata.json',dict(created_at=now(),config=CONFIG,cursor=cursor,
            target_modules=policy.target_modules,frozen_manifest_sha256=digest(frozen),
            sources=frozen['sources'],data_files=frozen['data_files'],base_files=frozen['base_files'],
            tokenizer_files=frozen['tokenizer_files'],base_fingerprints=initial_base_hashes,
            trainable_fingerprints=policy.trainable_fingerprints()))
        atomic(temp/'files.json',file_manifest(temp))
        for p in temp.rglob('*'):
            if p.is_file():
                with p.open('rb') as f:
                    os.fsync(f.fileno())
        os.rename(temp,directory)
        dfd=os.open(directory.parent,os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return directory


def restore_training(optimizer, path):
    validate_checkpoint(path)
    state = torch.load(Path(path)/'state.pt',map_location='cpu',weights_only=False)
    optimizer.load_state_dict(state['optimizer'])
    restore_rng(state['rng'])
    return state['cursor']


def set_latest(training, checkpoint):
    training, checkpoint = Path(training), Path(checkpoint)
    atomic(training/'latest.json',dict(path=str(checkpoint.resolve()),files_sha256=sha(checkpoint/'files.json')))
    # Epoch and initial checkpoints are permanent. Keep two complete transient
    # updates, so a partial directory/pointer write never destroys the prior one.
    updates = sorted(training.glob('update-*'))
    for old in updates[:-2]:
        shutil.rmtree(old)


def latest(training):
    pointer = read(Path(training)/'latest.json')
    path = Path(pointer['path'])
    if sha(path/'files.json') != pointer['files_sha256']:
        raise ValueError('latest checkpoint pointer mismatch')
    validate_checkpoint(path)
    return path
