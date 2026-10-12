"""Small deterministic identities and durable writes without old experiment imports."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    data = value if isinstance(value, bytes) else canonical(value).encode()
    return hashlib.sha256(data).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def atomic(path, value, *, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        raise FileExistsError(path)
    data = value if isinstance(value, bytes) else (canonical(value) + '\n').encode()
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if immutable:
            # Exclusive link closes the exists/check race for frozen receipts.
            os.link(temporary, path)
            os.unlink(temporary)
        else:
            os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def jsonl(path):
    with Path(path).open() as f:
        for number, line in enumerate(f, 1):
            if not line.strip():
                raise ValueError(f'blank JSONL line {path}:{number}')
            yield json.loads(line)


def write_jsonl(path, records, *, immutable=False):
    # Choice criterion insertion order is semantic; never sort JSONL model inputs.
    atomic(path, ''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':'),
                                   allow_nan=False) + '\n' for row in records).encode(), immutable=immutable)
