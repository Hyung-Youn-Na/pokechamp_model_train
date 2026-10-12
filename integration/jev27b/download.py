"""Download the pinned official bundle, checking LFS SHA256 or Git blob identity."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path

from .config import DISK_BYTES, EVIDENCE, MODEL_DIR, MODEL_ID, REVISION, RUNTIME
from .storage import file_hash, read, write


def selected(entry):
    name = entry['path']
    return entry['type'] == 'file' and (
        name.startswith('model-') or name.startswith('adapter/') or
        name in {'README.md', 'config.json', 'tokenizer.json', 'tokenizer_config.json',
                 'model.safetensors.index.json', 'calibration.json', 'judge_config.json',
                 'head.safetensors', 'serve_decide.py', 'chat_template.jinja'})


def verify(path, entry):
    if path.stat().st_size != entry['size']:
        raise ValueError(f"download size mismatch: {entry['path']}")
    sha = file_hash(path)
    if 'lfs' in entry:
        valid = sha == entry['lfs']['oid']
    else:
        blob = b'blob ' + str(entry['size']).encode() + b'\0' + path.read_bytes()
        valid = hashlib.sha1(blob).hexdigest() == entry['oid']
    if not valid:
        raise ValueError(f"official file hash mismatch: {entry['path']}")
    return dict(path=entry['path'], bytes=entry['size'], sha256=sha,
                official_sha256=entry.get('lfs', {}).get('oid'), git_oid=entry['oid'])


def download_one(entry):
    target = MODEL_DIR / entry['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return verify(target, entry)
    temporary = target.with_name(target.name + '.partial')
    url = f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{entry["path"]}'
    for attempt in range(4):
        offset = temporary.stat().st_size if temporary.exists() else 0
        if offset == entry['size']:
            break
        try:
            request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
            with urllib.request.urlopen(request, timeout=600) as response:
                append = offset and response.status == 206
                with temporary.open('ab' if append else 'wb') as output:
                    while chunk := response.read(8 * 1024**2):
                        output.write(chunk)
                        if output.tell() > entry['size']:
                            raise ValueError('response larger than pinned file')
            if temporary.stat().st_size == entry['size']:
                break
            raise OSError('incomplete download')
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep((10, 30, 60)[attempt])
    result = verify(temporary, entry)
    temporary.replace(target)
    print(json.dumps(dict(downloaded=entry['path'], bytes=entry['size'])), flush=True)
    return result


def download_xet(entry):
    target = MODEL_DIR / entry['path']
    if target.exists():
        return verify(target, entry)
    from huggingface_hub import hf_hub_download
    path = Path(hf_hub_download(MODEL_ID, entry['path'], revision=REVISION,
        local_dir=MODEL_DIR, token=False))
    result = verify(path, entry)
    print(json.dumps(dict(downloaded=entry['path'], bytes=entry['size'], transfer='xet')), flush=True)
    return result


def main(workers=2, transfer='xet'):
    os.environ.update(HF_HOME=str(RUNTIME / 'hub-metadata'),
        HF_XET_CACHE=str(RUNTIME / 'xet-cache'), HF_XET_CHUNK_CACHE_SIZE_BYTES='0',
        HF_XET_HIGH_PERFORMANCE='1', HF_XET_NUM_CONCURRENT_RANGE_GETS='8',
        HF_HUB_DISABLE_XET='0', HF_HUB_DOWNLOAD_TIMEOUT='600')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    url = f'https://huggingface.co/api/models/{MODEL_ID}/tree/{REVISION}?recursive=true&limit=1000'
    with urllib.request.urlopen(url, timeout=600) as response:
        entries = json.load(response)
    wanted = sorted(filter(selected, entries), key=lambda e: (e['size'], e['path']))
    required = sum(e['size'] for e in wanted)
    if required + 15 * 1024**3 > DISK_BYTES or shutil.disk_usage(RUNTIME).free < required:
        raise RuntimeError('download resource budget unavailable')
    tree = dict(url=url, model=MODEL_ID, revision=REVISION, files=entries)
    tree_path = EVIDENCE / 'official-tree.json'
    if tree_path.exists():
        if read(tree_path) != tree:
            raise ValueError('pinned official tree changed during download resume')
    else:
        write(tree_path, tree)
    print(json.dumps(dict(files=len(wanted), bytes=required, revision=REVISION)), flush=True)
    small = [entry for entry in wanted if entry['size'] < 100 * 1024**2]
    large = [entry for entry in wanted if entry not in small]
    results = [download_one(entry) for entry in small]
    # Each worker owns a different file, never a second full Hub/Xet cache copy.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results.extend(pool.map(download_xet if transfer == 'xet' else download_one, large))
    write(EVIDENCE / 'download.json', dict(passed=True, model=MODEL_ID, revision=REVISION,
          bytes=sum(x['bytes'] for x in results), files=results, workers=workers, transfer=transfer,
          source_sha256=file_hash(Path(__file__)), completed_at=time.time()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=2)
    parser.add_argument('--transfer', choices=('http', 'xet'), default='xet')
    args = parser.parse_args()
    main(args.workers, args.transfer)
