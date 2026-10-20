"""Fetch pinned official files and verify LFS SHA256 or Git blob identity."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request
import time

from .config import MODEL_DIR, EVIDENCE, REVISION


def identity(path, row):
    size = path.stat().st_size
    if size != row['size']:
        raise ValueError('official file size mismatch: ' + row['path'])
    sha = hashlib.sha256()
    git = hashlib.sha1(f'blob {size}\0'.encode())
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            sha.update(chunk); git.update(chunk)
    actual = sha.hexdigest() if 'lfs' in row else git.hexdigest()
    expected = row['lfs']['oid'] if 'lfs' in row else row['oid']
    if actual != expected:
        raise ValueError('official file identity mismatch: ' + row['path'])
    return dict(path=row['path'], size=size, sha256=sha.hexdigest(), official_identity=expected)


def selected(row):
    return row['type'] == 'file' and not row['path'].startswith(('assets/',))


def verify():
    rows = json.loads((EVIDENCE / 'official-tree.json').read_text())
    files = [identity(MODEL_DIR / row['path'], row) for row in rows if selected(row)]
    return dict(model='akhilaaa3/Jev-Omni', revision=REVISION, files=files, passed=True)


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    url = f'https://huggingface.co/api/models/akhilaaa3/Jev-Omni/tree/{REVISION}?recursive=true&limit=1000'
    rows = json.load(urllib.request.urlopen(url, timeout=60))
    (EVIDENCE / 'official-tree.json').write_text(json.dumps(rows, indent=2) + '\n')
    def fetch(row):
        path = MODEL_DIR / row['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temp = path.with_suffix(path.suffix + '.partial')
            url = f'https://huggingface.co/akhilaaa3/Jev-Omni/resolve/{REVISION}/{row["path"]}'
            for attempt in range(5):
                offset = temp.stat().st_size if temp.exists() else 0
                if offset == row['size']:
                    break
                request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'})
                try:
                    with urllib.request.urlopen(request, timeout=60) as response:
                        resume = offset > 0 and response.status == 206
                        with temp.open('ab' if resume else 'wb') as output:
                            while chunk := response.read(1024**2):
                                output.write(chunk)
                    if temp.stat().st_size != row['size']:
                        raise OSError('incomplete official download')
                    break
                except OSError:
                    if attempt == 4:
                        raise
                    time.sleep(1)
            identity(temp, row)
            temp.rename(path)
        result = identity(path, row)
        print(json.dumps(result), flush=True)
        return result
    with ThreadPoolExecutor(max_workers=16) as pool:
        files = list(pool.map(fetch, [r for r in rows if selected(r)]))
    (EVIDENCE / 'model-receipt.json').write_text(json.dumps(dict(revision=REVISION, files=files, passed=True), indent=2) + '\n')


if __name__ == '__main__':
    main()
