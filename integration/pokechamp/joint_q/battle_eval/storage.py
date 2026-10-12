"""Small CPU-only durable I/O and original-artifact preservation helpers."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def atomic(path, value, *, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            os.link(name, path)
            os.unlink(name)
        else:
            os.replace(name, path)
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def append(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def file_manifest(directory):
    directory = Path(directory)
    return {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def checkpoint_identity():
    from .config import CHECKPOINT, MODEL, REVISION
    expected = read(CHECKPOINT / 'files.json')
    actual = file_manifest(CHECKPOINT)
    actual.pop('files.json', None)
    if actual != expected:
        raise ValueError('original EX066 checkpoint integrity failure')
    meta = read(CHECKPOINT / 'metadata.json')
    if (meta['config']['model'] != MODEL or meta['config']['revision'] != REVISION
            or meta['cursor']['updates'] != 615):
        raise ValueError('unexpected EX066 selected checkpoint identity')
    return dict(model=MODEL, revision=REVISION, checkpoint_path=str(CHECKPOINT),
                checkpoint_sha256=expected['adapter/adapter_model.safetensors'],
                head_sha256=expected['value_head.pt'], files=expected,
                files_manifest_sha256=sha(CHECKPOINT / 'files.json'),
                training_physical_gpu=meta['config']['physical_gpu'])


def preservation(*, full=False):
    from .config import ROOT, ORIGINAL, CHECKPOINT, DATA
    manifest = read(ORIGINAL / 'prepared/manifest.json')
    sources = {name: sha(ROOT / name) for name in manifest['sources']}
    if sources != manifest['sources']:
        raise ValueError('original EX066 source changed')
    protected = ['STOP.json', 'training/selection.json', 'training/validation-epoch3.jsonl',
                 'reload/validation.jsonl', 'prepared/manifest.json', 'prepared/validation-epoch0.jsonl']
    files = {name: sha(ORIGINAL / name) for name in protected if (ORIGINAL / name).exists()}
    files['checkpoint/files.json'] = sha(CHECKPOINT / 'files.json')
    result = dict(sources=sources, original_files=files, checkpoint=checkpoint_identity())
    if full:
        for name, expected in manifest['data_files'].items():
            if sha(DATA / name) != expected:
                raise ValueError('original training data changed: ' + name)
        for name, expected in manifest['prepared_files'].items():
            if sha(ORIGINAL / 'prepared' / name) != expected:
                raise ValueError('original prepared data changed: ' + name)
        for name, expected in manifest['base_files'].items():
            if sha(name) != expected:
                raise ValueError('original Base/tokenizer changed: ' + name)
        result['full_original_hash_check'] = True
    return result


def clock(directory, *, start=False):
    from .config import LIMITS
    path = Path(directory) / 'clock.json'
    if not path.exists():
        if not start:
            return None
        begin = time.time()
        atomic(path, dict(started_at=begin, deadline_at=begin + LIMITS['total_seconds'],
                          total_seconds=LIMITS['total_seconds'], at=now()), immutable=True)
    result = read(path)
    if result['deadline_at'] - result['started_at'] != LIMITS['total_seconds']:
        raise ValueError('EX081 first clock or budget changed')
    return result


def remaining(directory):
    value = clock(directory)
    return float('inf') if value is None else max(0, value['deadline_at'] - time.time())
