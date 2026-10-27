"""Run-local immutable inputs and append-only, secret-free decision records."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import time

from integration.pokechamp.providers import redact
from .config import ROOT, digest, read_json


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(redact(value), stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_identity():
    from integration.project_context.registry import runtime_paths
    paths = []
    for directory in ('integration/jev_planner', 'integration/jev27b', 'integration/jev9b',
                      'integration/jev_eval', 'integration/minicpm5_jev', 'integration/jev35b_nvfp4', 'integration/jev_omni', 'integration/tacit9b', 'integration/tacit9b_vllm', 'integration/pokechamp'):
        paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file()
                     and 'tests' not in p.parts and p.suffix in ('.py', '.cjs', '.js', '.html', '.json', '.txt')
                     and not (directory == 'integration/jev_planner'
                              and any(part in ('prompts', 'examples', 'fixtures') for part in p.parts)))
    paths.append(ROOT / 'scripts/jev-planner')
    paths.extend(runtime_paths(root=ROOT))
    return {str(p.relative_to(ROOT)): file_hash(p) for p in sorted(set(paths))}


def snapshot_sources(directory, identity):
    for name, expected in identity.items():
        path = ROOT / name
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('source changed while preparing: ' + name)
        target = Path(directory) / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)


def verify_prepared(directory, *, current_source=True):
    directory = Path(directory)
    manifest = read_json(directory / 'manifest.json')
    if manifest.get('schema_version') != 'jev-planner-run-v1':
        raise ValueError('not a prepared JEV planner run')
    expected = (directory / 'manifest.sha256').read_text().strip()
    if file_hash(directory / 'manifest.json') != expected:
        raise ValueError('prepared manifest changed')
    for name, sha in manifest['source'].items():
        if file_hash(directory / 'source' / name) != sha:
            raise ValueError('source snapshot changed: ' + name)
        if current_source and file_hash(ROOT / name) != sha:
            raise ValueError('source changed after preparation; prepare a new run: ' + name)
    for item in manifest['conditions']:
        if digest(item['config']) != item['config_sha256']:
            raise ValueError('condition config identity changed')
        condition = directory / 'conditions' / item['name']
        if read_json(condition / 'config.json') != item['config']:
            raise ValueError('saved condition config changed')
        for role, prompt in item['config']['prompts'].items():
            if file_hash(condition / 'prompts' / (role + '.txt')) != prompt['sha256']:
                raise ValueError('saved prompt changed: ' + role)
    return manifest


class Recorder:
    """A single condition's journal; preserves protocol's own sequence coordinates."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'events.jsonl'
        self.lock = threading.RLock()
        self.records = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('x', encoding='utf-8')

    def __call__(self, event):
        with self.lock:
            row = redact({'at': time.time(), 'event_seq': len(self.records) + 1, **event})
            encoded = json.dumps(row, ensure_ascii=False, allow_nan=False)
            self.stream.write(encoded + '\n')
            self.stream.flush()
            self.records.append(json.loads(encoded))
            return row

    def close(self):
        with self.lock:
            self.stream.close()
