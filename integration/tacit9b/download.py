"""Validate local pinned Tacit assets against the official Hub tree."""
import hashlib
import json

from .config import MODEL_DIR, EVIDENCE, MODEL_ID, REVISION


def identity(path, row):
    size = path.stat().st_size
    if size != row['size']:
        raise ValueError('official file size mismatch: ' + row['path'])
    sha = hashlib.sha256()
    git = hashlib.sha1(f'blob {size}\0'.encode())
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            sha.update(chunk)
            git.update(chunk)
    expected = row['lfs']['oid'] if 'lfs' in row else row['oid']
    actual = sha.hexdigest() if 'lfs' in row else git.hexdigest()
    if actual != expected:
        raise ValueError('official file identity mismatch: ' + row['path'])
    return dict(path=row['path'], size=size, sha256=sha.hexdigest(), official_identity=expected)


def verify():
    rows = json.loads((EVIDENCE / 'official-tree.json').read_text())
    files = [identity(MODEL_DIR / row['path'], row) for row in rows if row['type'] == 'file']
    if not files:
        raise ValueError('missing official asset tree')
    return dict(model=MODEL_ID, revision=REVISION, files=files, passed=True)
