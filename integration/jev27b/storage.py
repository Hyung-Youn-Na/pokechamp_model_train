"""Small evidence helpers; existing evidence is never silently replaced."""
import hashlib
import json
import os
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def write(path, value, *, immutable=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if immutable:
        with path.open('x') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    else:
        temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
        temporary.write_text(data)
        temporary.replace(path)


def read(path):
    return json.loads(Path(path).read_text())
