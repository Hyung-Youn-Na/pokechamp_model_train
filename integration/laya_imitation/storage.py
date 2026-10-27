"""Durable writes and sealing for EP-208 outputs (reuses the EX-071 deterministic helpers)."""
from __future__ import annotations
from pathlib import Path
import json
import subprocess
import time

from integration.pokechamp.imitation.storage import atomic, canonical, digest, jsonl, read, sha, write_jsonl

from .config import ROOT

__all__ = ['atomic', 'canonical', 'digest', 'jsonl', 'read', 'sha', 'write_jsonl', 'seal', 'verify_seal',
           'source_identity', 'append_jsonl', 'now']


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')


def seal(directory, *, skip=()):
    directory = Path(directory)
    files = sorted(p for p in directory.rglob('*')
                   if p.is_file() and p.name != 'checksums.sha256' and not any(part in skip for part in p.parts))
    (directory / 'checksums.sha256').write_text(
        ''.join('%s  %s\n' % (sha(p), p.relative_to(directory)) for p in files))
    return len(files)


def verify_seal(directory):
    directory = Path(directory)
    bad = []
    for line in (directory / 'checksums.sha256').read_text().splitlines():
        expected, name = line.split('  ', 1)
        if sha(directory / name) != expected:
            bad.append(name)
    return bad


def append_jsonl(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
        f.flush()


def source_identity():
    """Commit, laya_imitation file hashes and the list of uncommitted paths (not their content)."""
    git = lambda *a: subprocess.check_output(['git', '-C', str(ROOT), *a], text=True).strip()
    package = ROOT / 'integration/laya_imitation'
    files = {str(p.relative_to(ROOT)): sha(p) for p in sorted(package.rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts}
    for extra in ('integration/pokechamp/imitation/schema.py', 'integration/pokechamp/imitation/player.py',
                  'integration/pokechamp/imitation/replay.py', 'scripts/laya-imitation'):
        if (ROOT / extra).exists():
            files[extra] = sha(ROOT / extra)
    return dict(commit=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
                dirty=git('status', '--porcelain', '--untracked-files=no').splitlines(), files=files)
