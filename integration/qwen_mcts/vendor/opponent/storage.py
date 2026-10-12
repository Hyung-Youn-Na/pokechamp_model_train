"""Canonical identities, durable atomic files and exclusive coordinator ownership."""
from __future__ import annotations
import contextlib
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / '.pokechamp-data/experiments/ex065-joint-q'
MASTER = 20260929
VERSION = 'ex065-rollout-v1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    path = Path(path)
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as f:
            return json.load(f)
    return json.loads(path.read_text())


def atomic(path, value, *, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Insertion order is part of the official candidate contract; canonical JSON
    # is for hashes only, never reorder request move slots or candidate mappings.
    raw = (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if path.suffix == '.gz':
        raw = gzip.compress(raw, compresslevel=1, mtime=0)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        if immutable:
            try:
                os.link(tmp, path)
            except FileExistsError:
                if Path(tmp).read_bytes() != path.read_bytes():
                    raise ValueError('immutable file collision: ' + str(path))
        else:
            os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return sha(path)


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def jsonl(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            for value in values:
                f.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def seed(*parts, simulator=False):
    raw = hashlib.sha256(canonical(['EX065', MASTER, *parts])).digest()
    return [int.from_bytes(raw[i:i+2], 'big') for i in range(0, 8, 2)] if simulator else int.from_bytes(raw[:4], 'big')


def rollout_seeds(observation_id, replicate):
    return dict(simulator=seed(observation_id, replicate, 'simulator', simulator=True),
                actors={s: seed(observation_id, replicate, s) for s in ('p1', 'p2')})


@contextlib.contextmanager
def owner(directory):
    path = Path(directory) / 'coordinator.lock'
    with path.open('a+') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('another EX-065 coordinator owns the ledger') from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
