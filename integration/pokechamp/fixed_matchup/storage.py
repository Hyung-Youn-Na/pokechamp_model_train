"""Atomic artifacts, stable identities and disjoint RNG namespaces."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from .config import SEED


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def seed(*parts):
    return int(digest([SEED, *parts])[:16], 16)


def showdown_seed(*parts):
    value = seed("simulator", *parts)
    return [(value >> shift) & 65535 for shift in (0, 16, 32, 48)]


def read(path):
    return json.loads(Path(path).read_text())


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
