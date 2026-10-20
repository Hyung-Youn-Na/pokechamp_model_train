"""Download both fixed revisions and verify every official file without a logical disk cap."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request

from integration.jev27b.download import download_one, download_xet
from integration.jev9b.download import file_identity
from integration.jev27b.storage import file_hash, read, write
from .config import BASE_MODEL_ID, BASE_REVISION, EVIDENCE, MODEL_DIR, MODEL_ID, REVISION, RUNTIME


def inventories():
    return read(Path(__file__).with_name('official-files.json'))


def verify_receipt(model_dir=MODEL_DIR, evidence=EVIDENCE):
    model_dir, evidence = Path(model_dir), Path(evidence)
    receipt = read(evidence / 'download.json')
    expected = inventories()
    if (receipt.get('passed') is not True or receipt.get('model') != MODEL_ID
            or receipt.get('revision') != REVISION or receipt.get('base_model') != BASE_MODEL_ID
            or receipt.get('base_revision') != BASE_REVISION
            or receipt.get('model_directory') != str(model_dir.resolve())):
        raise ValueError('missing or foreign MiniCPM official file receipt')
    official = {str(Path(bundle['subdirectory']) / e['path']): e
                for bundle in expected for e in bundle['files']}
    rows = receipt['files']
    if len(rows) != len(official) or {r['path'] for r in rows} != set(official):
        raise ValueError('MiniCPM official inventory differs')
    for row in rows:
        entry = official[row['path']]
        if (row['bytes'] != entry['size'] or row['git_oid'] != entry['oid']
                or row['official_sha256'] != entry.get('lfs', {}).get('oid')
                or len(row['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in row['sha256'])
                or row['official_sha256'] is not None and row['sha256'] != row['official_sha256']
                or file_identity(model_dir / row['path']) != row['file_identity']):
            raise ValueError('verified MiniCPM file changed: ' + row['path'])
    if receipt['bytes'] != sum(e['size'] for e in official.values()):
        raise ValueError('MiniCPM download byte total differs')
    return receipt


def download(*, workers=2, transfer='xet'):
    if workers not in range(1, 9) or transfer not in ('xet', 'http'):
        raise ValueError('invalid download worker count or transfer')
    from integration.jev_eval.resource import disk_bytes, disk_roots
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if (EVIDENCE / 'download.json').exists():
        return verify_receipt()
    os.environ.update(HF_HOME=str(RUNTIME / 'hub-metadata'),
        HF_XET_CACHE=str(RUNTIME / 'xet-cache'), HF_XET_CHUNK_CACHE_SIZE_BYTES='0',
        HF_XET_HIGH_PERFORMANCE='1', HF_XET_NUM_CONCURRENT_RANGE_GETS='8',
        HF_HUB_DISABLE_XET='0', HF_HUB_DOWNLOAD_TIMEOUT='600')
    tasks = []
    for bundle in inventories():
        url = f"https://huggingface.co/api/models/{bundle['model']}/tree/{bundle['revision']}?recursive=true&limit=1000"
        with urllib.request.urlopen(url, timeout=60) as response:
            entries = json.load(response)
        if entries != bundle['files']:
            raise ValueError('fixed official tree differs: ' + bundle['model'])
        path = EVIDENCE / ('base-tree.json' if bundle['subdirectory'] else 'jev-tree.json')
        if path.exists() and read(path) != bundle:
            raise ValueError('official tree changed during download resume')
        write(path, bundle)
        tasks.extend((bundle, entry) for entry in entries)
    missing = sum(e['size'] for b, e in tasks
                  if not (MODEL_DIR / b['subdirectory'] / e['path']).exists())
    initial = dict(bytes=disk_bytes('EX-091'), limit_bytes=None,
                   free_bytes=shutil.disk_usage(RUNTIME).free,
                   roots=[str(p) for p in disk_roots('EX-091')])
    if initial['free_bytes'] < missing:
        raise OSError('insufficient physical disk space for pinned MiniCPM bundle')
    write(EVIDENCE / 'download-start.json', dict(at=time.time(), files=len(tasks),
        missing_bytes=missing, initial_disk=initial, model_loads=0, inferences=0))

    def one(task):
        bundle, entry = task
        target = MODEL_DIR / bundle['subdirectory']
        function = download_xet if transfer == 'xet' and entry['size'] >= 100 * 1024**2 else download_one
        row = function(entry, model_dir=target, model_id=bundle['model'], revision=bundle['revision'])
        row['path'] = str(Path(bundle['subdirectory']) / row['path'])
        row['file_identity'] = file_identity(MODEL_DIR / row['path'])
        return row

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one, tasks))
    receipt = dict(passed=True, model=MODEL_ID, revision=REVISION,
        base_model=BASE_MODEL_ID, base_revision=BASE_REVISION,
        model_directory=str(MODEL_DIR.resolve()), files=rows, bytes=sum(r['bytes'] for r in rows),
        initial_disk=initial, disk_bytes=disk_bytes('EX-091'), disk_limit_bytes=None,
        workers=workers, transfer=transfer, completed_at=time.time(),
        source_sha256=file_hash(Path(__file__)),
        verification='official-content-identity-once-then-local-stat-identity')
    write(EVIDENCE / 'download.json', receipt)
    return receipt


if __name__ == '__main__':
    receipt = download()
    print(json.dumps(dict(passed=receipt['passed'], files=len(receipt['files']), bytes=receipt['bytes'])))
