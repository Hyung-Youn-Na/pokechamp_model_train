"""Eight bounded requests on the one server subsequently used for collection."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

from .config import BASELINE, EVIDENCE, MAX_TOKENS, MODEL_DIR, MODEL_ID, ROOT, RUN
from .storage import digest, file_hash, read, write


def prepare_requests():
    from importlib.metadata import version
    import torch
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    from integration.jev27b.model import PINNED_PACKAGES
    from .model import Jev9BModel
    from .formatting import format_request, tokenize_request

    target = RUN / 'gates'
    target.mkdir(parents=True, exist_ok=True)
    if (target / 'requests.json').exists():
        raise FileExistsError('prepared requests already exist')
    model = Jev9BModel()
    model._verify_model_files()
    head = load_file(str(MODEL_DIR / 'head.safetensors'), device='cpu')
    model._validate_head(head, torch)
    packages = {name: version(name) for name in PINNED_PACKAGES}
    if any(packages[name].split('+')[0] != pinned for name, pinned in PINNED_PACKAGES.items()):
        raise ValueError('existing model environment differs from pinned versions')
    write(EVIDENCE / 'model-ready.json', dict(passed=True,
        model=model.model_id, revision=model.revision, head_shape=list(head['proj.weight'].shape),
        head_dtype=str(head['proj.weight'].dtype), choice_temperature=model.choice_temperature,
        packages=packages, file_verification=model.verification,
        environment_reinstalled=False, gpu_inferences=0, backbone_loaded=False))
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True,
                                               trust_remote_code=False)
    saved = ROOT / 'project_context/exec-plans/evidence/ep093/certainty-v1'
    requests = []
    for name, source, count in (('lead-6', 'lead-1', 6),
                                ('turn-13', 'turn-sample-01', 13),
                                ('forced-switch-5', 'forced-switch', 5)):
        path = saved / source / 'after-detailed.json'
        payload = read(path)
        payload['state']['version'] = 'jev-choice-v4'
        if len(payload['questions']['action']['criteria']) != count:
            raise ValueError('representative candidate count changed')
        requests.append((name, payload, path))
    long_path = BASELINE / 'gates/memory/ex083-memory-stopped-prime-request.json'
    short_path = BASELINE / 'gates/memory/ex083-memory-short-1-request.json'
    long_payload = read(long_path)['request']
    short_payload = read(short_path)['request']
    requests.extend((name, copy.deepcopy(payload), path) for name, payload, path in (
        ('long-preserved', long_payload, long_path),
        ('memory-short-1', short_payload, short_path),
        ('memory-long-1', long_payload, long_path),
        ('memory-short-2', short_payload, short_path),
        ('memory-long-2', long_payload, long_path)))
    rows = []
    for name, payload, path in requests:
        payload['model'] = MODEL_ID
        formatted = format_request(payload)
        encoded = tokenize_request(tokenizer, formatted)
        rows.append(dict(name=name, payload=payload,
            candidate_ids=list(formatted.candidate_ids), input_tokens=len(encoded['input_ids']),
            prompt_sha256=formatted.prompt_sha256, input_ids_sha256=digest(encoded['input_ids']),
            source=dict(path=str(path), sha256=file_hash(path))))
    if rows[4]['input_tokens'] >= rows[5]['input_tokens']:
        raise ValueError('short/long lengths not ordered')
    write(target / 'requests.json', dict(requests=rows, max_inferences=8, input_truncation=False))
    result = dict(passed=True, requests=8, gpu_inferences=0, max_tokens=MAX_TOKENS,
        max_input_tokens=max(r['input_tokens'] for r in rows),
        cases=[{k: r[k] for k in ('name', 'input_tokens', 'candidate_ids')} for r in rows],
        requests_sha256=file_hash(target / 'requests.json'),
        tokenizer_sha256=file_hash(MODEL_DIR / 'tokenizer.json'))
    write(EVIDENCE / 'lengths.json', result)
    return result


def compare_repeat(first, second, *, check_memory=True):
    a, b = (x['answers']['action'] for x in (first, second))
    if list(a['probabilities']) != list(b['probabilities']):
        raise ValueError('repeat candidate mapping changed')
    delta = max(abs(a['probabilities'][key] - b['probabilities'][key])
                for key in a['probabilities'])
    if a['choice'] != b['choice'] or not math.isfinite(delta) or delta > 1e-4:
        raise ValueError('repeated selection/probabilities changed beyond tolerance')
    if not check_memory:
        return dict(passed=True, same_choice=True, max_probability_difference=delta,
                    memory_comparison=False)
    before, after = first['metadata'], second['metadata']
    if (before['gpu_allocated_bytes'] != after['gpu_allocated_bytes']
            or any(y > x for x, y in zip(before['gpu_reserved_bytes'],
                                         after['gpu_reserved_bytes'], strict=True))):
        raise ValueError('same-server repeat did not reclaim memory')
    return dict(passed=True, same_choice=True, max_probability_difference=delta,
                allocated_equal=True, reserved_nonincreasing=True)


def verify_inference(journal, request_id, payload, response, transport):
    from .client import request_bytes
    if transport.get('cache_reused') is not False or transport.get('attempt') != 1:
        raise ValueError('qualification requires one fresh HTTP inference')
    raw = request_bytes(payload)
    with sqlite3.connect(Path(journal).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM requests WHERE request_id=?', (request_id,)).fetchone()
        count = db.execute("SELECT COUNT(*) FROM events WHERE request_id=? AND kind='inference_started'",
                           (request_id,)).fetchone()[0]
        if (row is None or row['state'] != 'completed' or row['inference_calls'] != 1 or count != 1
                or row['request_body'] != raw or row['body_sha256'] != hashlib.sha256(raw).hexdigest()
                or row['response_status'] != 200 or json.loads(row['response_body']) != response
                or hashlib.sha256(row['response_body']).hexdigest() != row['response_sha256']):
            raise ValueError('qualification inference differs from durable journal')


def qualify(client, sources):
    from integration.pokechamp.jev_battle import validate_answer
    from .model import fixed_device_map
    from .config import runtime_profile

    health = client.health()
    if health['device_map'] != fixed_device_map():
        raise ValueError('loaded four-device placement differs')
    if (health['serving_config']['tensor_placement_verified'] is not True
            or health['serving_config']['head_dtype'] != 'float32'
            or health['serving_config']['adapter'] != 'merged'):
        raise ValueError('model placement, head or official adapter not verified')
    if sum(health['requests'].values()) != 0:
        raise ValueError('qualification requires a fresh server')
    write(RUN / 'serving/loaded.json', health)
    prepared = RUN / 'gates/requests.json'
    lengths = read(EVIDENCE / 'lengths.json')
    if file_hash(prepared) != lengths['requests_sha256']:
        raise ValueError('prepared requests changed')
    requests = read(prepared)['requests']
    if len(requests) != 8:
        raise ValueError('qualification request budget differs')
    responses = []
    journal = RUN / 'serving/server/requests.sqlite3'
    for row in requests:
        request_id = 'ex085-gate-' + row['name']
        write(RUN / 'gates' / (row['name'] + '-request.json'), dict(request_id=request_id, **row))
        result = client.evaluate(row['payload'], request_id=request_id, retries=0)
        write(RUN / 'gates' / (row['name'] + '-response.json'), result)
        write(RUN / 'gates' / (row['name'] + '-transport.json'), client.last_transport)
        metadata = result['metadata']
        if (metadata['candidate_ids'] != row['candidate_ids']
                or metadata['prompt_sha256'] != row['prompt_sha256']
                or result['usage']['input_tokens'] != row['input_tokens']):
            raise ValueError('server formatting or candidate order differs')
        criteria = row['payload']['questions']['action']['criteria']
        validate_answer(result, criteria)
        probabilities = result['answers']['action']['probabilities']
        if list(probabilities) != list(criteria) or any(not math.isfinite(v) for v in probabilities.values()):
            raise ValueError('candidate probability linkage or finiteness differs')
        limit = runtime_profile().allocator_bytes
        for kind in ('gpu_allocated_bytes', 'gpu_reserved_bytes', 'gpu_peak_allocated_bytes'):
            if len(metadata[kind]) != 4 or any(type(v) is not int or not 0 <= v <= limit for v in metadata[kind]):
                raise ValueError('qualification allocator limit exceeded')
        verify_inference(journal, request_id, row['payload'], result, client.last_transport)
        responses.append(result)
        print(json.dumps(dict(stage='gpu_preflight', case=row['name'], completed=len(responses),
            input_tokens=row['input_tokens'], seconds=metadata['elapsed_seconds'])), flush=True)
    repeats = [compare_repeat(responses[a], responses[b]) for a, b in ((4, 6), (5, 7))]
    prime_repeat = compare_repeat(responses[3], responses[5], check_memory=False)
    final = client.health()
    if final['requests'] != {'completed': 8} or final['identity'] != health['identity']:
        raise ValueError('qualification count or identity differs')
    receipt = dict(passed=True, cpu_passed=read(EVIDENCE / 'cpu.json')['passed'],
        length_passed=lengths['passed'], server_loads=1, inferences=8,
        serving_identity=health['identity'], source=sources, server_journal=str(journal),
        input_data_identity=__import__('integration.pokechamp.jev_v4', fromlist=['data_identity']).data_identity(),
        max_input_tokens=max(r['input_tokens'] for r in requests), repeated_memory_passed=True,
        repeats=repeats, prime_repeat=prime_repeat,
        input_tokens=sum(r['usage']['input_tokens'] for r in responses),
        inference_seconds=sum(r['metadata']['elapsed_seconds'] for r in responses),
        limitation='대표8요청 실행 가능성 검증; 모든 길이 안정성/일반 성능 미평가', at=time.time())
    if not receipt['cpu_passed'] or not receipt['length_passed']:
        raise ValueError('preparation gate not passed')
    write(EVIDENCE / 'entry-gates.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare'])
    parser.parse_args()
    print(json.dumps(prepare_requests(), ensure_ascii=False))
