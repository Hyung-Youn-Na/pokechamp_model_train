"""Fetch only the pinned text System 1 bundle and verify its official identity once."""
import argparse
import concurrent.futures
from functools import partial
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request

from integration.jev27b.download import download_one, download_xet, selected
from .config import DISK_BYTES, EVIDENCE, MODEL_DIR, MODEL_ID, REVISION, RUNTIME
from .resource import disk_bytes
from .storage import file_hash, read, write

# Official tree at the fixed revision. Entries carry the Git object ID for small
# files and LFS SHA256 for binary files; no vision or vLLM alternative is selected.
OFFICIAL_FILES = {
    'README.md': (54958, 'c9d7bf96827c2b13c628725d435b4a565dbdcd1f', None),
    'adapter/README.md': (5128, 'f78cffe68c4a32dfea6ec5761768486130ecb30f', None),
    'adapter/adapter_config.json': (1319, '5b1edc61e9b42ea013e3d8d5f45f08bf87b25f9d', None),
    'adapter/adapter_model.safetensors': (160486456, '8fedadab08bb7e85f33acc69e5145fad9cf174a4',
        '796386ace560ec5624bbfe83f5c505121e5c9f9654200a847f032cb333cd1f71'),
    'calibration.json': (1007, '18c9e8df7e36870b059d069bff0defdd7a024384', None),
    'chat_template.jinja': (7756, 'a585dec894e63da457d9440ec6aa7caa16d20860', None),
    'config.json': (2292, '6eb80e25cbc8a2e06bb2040246cca1b248660009', None),
    'head.safetensors': (393464, '066992c60bfae67d41ac90a4f0a8414015dd2bd8',
        'd960a6f5989402c6d08d74d8d435a21a031cc7878f3c4ac274a126c900f627e7'),
    'judge_config.json': (1435, '0a04e9335e597f39336f4f1b749997ee9704a435', None),
    'model-00001-of-00005.safetensors': (4234572344, 'ab0fba2ee617ebf647ff622e3d3f69ccd35799d2',
        'fdce203bd6767c95690c4695699e9e796fa53caeb06c7f6d43a014f7c513b32c'),
    'model-00002-of-00005.safetensors': (4199125880, '9633effed257da6b33e2f2f7881f034544298177',
        '64003b88d6e6871f2315e39356188082063ff879994434d5ce8c209b3c736a01'),
    'model-00003-of-00005.safetensors': (4215396752, 'f214428deb2b47e49eda6706ef3e36ed7c137df5',
        'ef7cf4227fb3f391bb2bcd5d79a3c10cd90d823dbf964f41a0aa34591377ae82'),
    'model-00004-of-00005.safetensors': (3224330536, 'c96e6bed9678d17b309ffa5a9843be2b1f7be989',
        '2265f2fcf900572fa0b7c645a9a64f662d4123daeeeda23e917411e907d66272'),
    'model-00005-of-00005.safetensors': (2034237568, '7a1670492c725c5be68f6ca47956025cbe4b1cf5',
        'dd63614f1dc80dce2d83be3f3e69af1f8a0ebc8add9b8e0abf3910f563e44344'),
    'model.safetensors.index.json': (35625, '9bc5e29ec8248fcf036a5946d29cd595ff5bc0f6', None),
    'tokenizer.json': (19989325, '5520bfd2dd834ce386c1312c410fa71af56db5ad',
        '06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523'),
    'tokenizer_config.json': (1124, 'd1a20cc3a8838d08eca9de8a7b84d510d60a0524', None),
}


def file_identity(path):
    stat = Path(path).stat()
    return dict(device=stat.st_dev, inode=stat.st_ino, bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns, ctime_ns=stat.st_ctime_ns)


def verify_tree(entries):
    wanted = sorted(filter(selected, entries), key=lambda e: (e['size'], e['path']))
    if len(wanted) != len(OFFICIAL_FILES) or {e['path'] for e in wanted} != set(OFFICIAL_FILES):
        raise ValueError('pinned JEV-9B text bundle inventory changed')
    for entry in wanted:
        expected = OFFICIAL_FILES[entry['path']]
        if (entry['size'], entry['oid'], entry.get('lfs', {}).get('oid')) != expected:
            raise ValueError('pinned official file identity changed: ' + entry['path'])
    return wanted


def verify_receipt(model_dir=MODEL_DIR, evidence=EVIDENCE):
    """Use a successful one-time hash receipt while rejecting changed local files.

    A changed inode, size, mtime or ctime is an integrity failure; it does not cause
    another hidden file hash or silently authorize a replacement model bundle.
    """
    model_dir, evidence = Path(model_dir), Path(evidence)
    receipt = read(evidence / 'download.json')
    tree = read(evidence / 'official-tree.json')
    if (receipt.get('passed') is not True or receipt.get('model') != MODEL_ID
            or receipt.get('revision') != REVISION
            or tree.get('model') != MODEL_ID or tree.get('revision') != REVISION
            or receipt.get('model_directory') != str(model_dir.resolve())):
        raise ValueError('missing or foreign JEV-9B official file receipt')
    wanted = verify_tree(tree['files'])
    files = receipt['files']
    if (len(files) != len(wanted) or {r['path'] for r in files} != set(OFFICIAL_FILES)
            or receipt['bytes'] != sum(e['size'] for e in wanted)):
        raise ValueError('JEV-9B receipt inventory differs')
    for row in files:
        size, git_oid, official_sha256 = OFFICIAL_FILES[row['path']]
        if ((row['bytes'], row['git_oid'], row['official_sha256']) != (size, git_oid, official_sha256)
                or len(row['sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['sha256'])
                or (official_sha256 is not None and row['sha256'] != official_sha256)
                or file_identity(model_dir / row['path']) != row['file_identity']):
            raise ValueError('verified model file changed: ' + row['path'])
    return receipt


def main(workers=2, transfer='xet'):
    if type(workers) is not int or not 1 <= workers <= 8 or transfer not in ('http', 'xet'):
        raise ValueError('invalid download worker count or transport')
    os.environ.update(HF_HOME=str(RUNTIME / 'hub-metadata'),
        HF_XET_CACHE=str(RUNTIME / 'xet-cache'), HF_XET_CHUNK_CACHE_SIZE_BYTES='0',
        HF_XET_HIGH_PERFORMANCE='1', HF_XET_NUM_CONCURRENT_RANGE_GETS='8',
        HF_HUB_DISABLE_XET='0', HF_HUB_DOWNLOAD_TIMEOUT='600')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if (EVIDENCE / 'download.json').exists():
        receipt = verify_receipt()
        print(json.dumps(dict(passed=True, reused_verification=True, bytes=receipt['bytes'])), flush=True)
        return receipt
    url = f'https://huggingface.co/api/models/{MODEL_ID}/tree/{REVISION}?recursive=true&limit=1000'
    with urllib.request.urlopen(url, timeout=600) as response:
        entries = json.load(response)
    wanted = verify_tree(entries)
    required = sum(entry['size'] for entry in wanted)
    missing = sum(entry['size'] for entry in wanted if not (MODEL_DIR / entry['path']).exists())
    if disk_bytes() + missing > DISK_BYTES or shutil.disk_usage(RUNTIME).free < missing:
        raise RuntimeError('combined preserved/reference/new download budget unavailable')
    tree = dict(url=url, model=MODEL_ID, revision=REVISION, files=entries)
    tree_path = EVIDENCE / 'official-tree.json'
    if tree_path.exists():
        if read(tree_path) != tree:
            raise ValueError('pinned official tree changed during download resume')
    else:
        write(tree_path, tree)
    print(json.dumps(dict(files=len(wanted), bytes=required, revision=REVISION)), flush=True)
    one = partial(download_one, model_dir=MODEL_DIR, model_id=MODEL_ID, revision=REVISION)
    transfer_file = partial(download_xet if transfer == 'xet' else download_one,
                            model_dir=MODEL_DIR, model_id=MODEL_ID, revision=REVISION)
    small = [entry for entry in wanted if entry['size'] < 100 * 1024**2]
    large = [entry for entry in wanted if entry not in small]
    results = [one(entry) for entry in small]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results.extend(pool.map(transfer_file, large))
    for row in results:
        row['file_identity'] = file_identity(MODEL_DIR / row['path'])
    used = disk_bytes()
    if used > DISK_BYTES:
        raise RuntimeError('download exceeded combined disk budget')
    receipt = dict(passed=True, model=MODEL_ID, revision=REVISION,
        model_directory=str(MODEL_DIR.resolve()), bytes=sum(r['bytes'] for r in results),
        files=results, workers=workers, transfer=transfer, disk_bytes=used,
        verification='official-content-identity-once-then-local-stat-identity',
        source_sha256=file_hash(Path(__file__)), completed_at=time.time())
    write(EVIDENCE / 'download.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=2)
    parser.add_argument('--transfer', choices=('http', 'xet'), default='xet')
    args = parser.parse_args()
    main(args.workers, args.transfer)
