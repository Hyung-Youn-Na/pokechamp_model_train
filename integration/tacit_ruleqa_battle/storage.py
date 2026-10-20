"""Small durable artifacts and source identity."""
import hashlib
import json
import os
from pathlib import Path
from .core import ROOT


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    temporary.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def source_files():
    # Shared imports are frozen alongside dedicated code; preserve existing edits.
    return sorted(p for p in (ROOT/'integration').rglob('*') if p.is_file()
                  and p.suffix in ('.py', '.cjs', '.js', '.json', '.txt', '.html') and '__pycache__' not in p.parts)


def seal(directory):
    directory = Path(directory)
    files = sorted(p for p in directory.rglob('*') if p.is_file() and p.name not in ('checksums.sha256', 'reservation-state.json'))
    (directory/'checksums.sha256').write_text(''.join(f'{digest(p)}  {p.relative_to(directory)}\n' for p in files))
