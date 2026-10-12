"""Atomic artifacts, stable identities and namespaced RNG (adapted from fixed_matchup/storage.py)."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .config import NAMESPACE, SEED


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def seed(*parts):
    """64-bit seed in this experiment's namespace; disjoint from EX-076..079 (no namespace there)."""
    return int(digest([SEED, NAMESPACE, *parts])[:16], 16)


def showdown_seed(*parts):
    value = seed("simulator", *parts)
    return [(value >> shift) & 65535 for shift in (0, 16, 32, 48)]


def read(path):
    return json.loads(Path(path).read_text())


def read_gz(path):
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def atomic_bytes(path, data, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic(path, value, *, exclusive=False):
    atomic_bytes(path, encoded(value) + b"\n", exclusive=exclusive)


def atomic_gz(path, value, *, exclusive=False):
    atomic_bytes(path, gzip.compress(encoded(value), mtime=0), exclusive=exclusive)


def pack_ids(ids):
    """int32 token ids -> base64 text (compact, exact)."""
    import array
    data = array.array("i", ids)
    if data.itemsize != 4:
        raise ValueError("int32 required")
    return base64.b64encode(data.tobytes()).decode()


def unpack_ids(text):
    import array
    data = array.array("i")
    data.frombytes(base64.b64decode(text))
    return data.tolist()
