"""Five representative requests plus four memory probes, all on the collection server."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import time

from .config import BASELINE, EVIDENCE, MAX_TOKENS, MODEL_DIR, MODEL_ID, RUN
from .policy import type_request, detail_request, split_candidates
from .storage import read, write, file_hash


def prepare_requests():
    from transformers import AutoTokenizer
    from .formatting import prepare
    target = RUN / 'gates'
    target.mkdir(parents=True, exist_ok=True)
    if (target / 'requests.json').exists():
        raise FileExistsError('prepared requests already exist')
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    parent = Path('/workspace/.pokechamp-data/jev/ex082-live/events.jsonl')
    lead = mixed = None
    for line in parent.open():
        event = json.loads(line)
        if event['type'] != 'input':
            continue
        payload = event['payload']
        groups = split_candidates(payload)
        if lead is None and payload['state']['decision_kind'] == 'lead':
            lead = copy.deepcopy(payload)
        if mixed is None and groups and list(map(len, groups.values())) == [8, 5]:
            mixed = copy.deepcopy(payload)
        if lead is not None and mixed is not None:
            break
    if lead is None or mixed is None:
        raise ValueError('representative lead/8+5 saved requests unavailable')
    long_path = BASELINE / 'gates/memory/ex083-memory-stopped-prime-request.json'
    short_path = BASELINE / 'gates/memory/ex083-memory-short-1-request.json'
    long_payload = read(long_path)['request']; long_payload.pop('model')
    short_payload = read(short_path)['request']; short_payload.pop('model')
    # The long case retains the entire archived state and all details in its type descriptions.
    long_request = type_request(long_payload)
    short_request = detail_request(short_payload)
    requests = [('lead', detail_request(lead)), ('action-type', type_request(mixed)),
                ('moves-8', detail_request(mixed, 'move')), ('switches-5', detail_request(mixed, 'switch')),
                ('long-preserved', long_request), ('memory-short-1', short_request),
                ('memory-long-1', long_request), ('memory-short-2', short_request), ('memory-long-2', long_request)]
    rows = []
    for name, payload in requests:
        payload = dict(model=MODEL_ID, **payload)
        formatted = prepare(tokenizer, payload, strict=True)
        rows.append(dict(name=name, payload=payload, formatter=formatted.evidence()))
    if rows[5]['formatter']['input_tokens'] >= rows[6]['formatter']['input_tokens']:
        raise ValueError('short/long probe lengths not ordered')
    write(target / 'requests.json', dict(requests=rows, max_inferences=9,
        source_references=[dict(path=str(p), sha256=file_hash(p)) for p in (long_path, short_path)],
        source_parent_events=str(parent), input_truncation=False))
    write(EVIDENCE / 'lengths.json', dict(passed=True, requests=len(rows),
        cases=[dict(name=r['name'], input_tokens=r['formatter']['input_tokens'],
                    state_tokens=r['formatter']['state_tokens']) for r in rows],
        state_limit=MAX_TOKENS, prompt_limit=MAX_TOKENS, gpu_inferences=0,
        tokenizer_sha256=file_hash(MODEL_DIR / 'tokenizer.json')))


def qualify(client, sources):
    from integration.pokechamp.jev_battle import validate_answer
    from .model import fixed_device_map
    from .config import runtime_profile
    health = client.health()
    if health['placement']['device_map'] != fixed_device_map() or not health['placement']['tied_embeddings']:
        raise ValueError('loaded four-device placement differs')
    if sum(health['requests'].values()) != 0:
        raise ValueError('qualification requires a fresh server with no previous inference')
    write(RUN / 'serving/loaded.json', health)
    requests = read(RUN / 'gates/requests.json')['requests']
    if len(requests) != 9:
        raise ValueError('qualification request budget differs')
    responses = []
    for row in requests:
        request_id = 'ex084-gate-' + row['name']
        write(RUN / 'gates' / (row['name'] + '-request.json'), dict(request_id=request_id, **row))
        result = client.evaluate(row['payload'], request_id=request_id, retries=0)
        write(RUN / 'gates' / (row['name'] + '-response.json'), result)
        write(RUN / 'gates' / (row['name'] + '-transport.json'), client.last_transport)
        formatter = result['metadata']['formatter']
        if formatter != row['formatter']:
            raise ValueError('server formatter differs from CPU prepared request')
        criteria = row['payload']['questions']['action']['criteria']
        validate_answer(result, criteria)
        probabilities = result['answers']['action']['probabilities']
        if list(probabilities) != list(criteria):
            raise ValueError('official candidate probability linkage differs')
        settings = runtime_profile()
        if any(v > settings.allocator_bytes for values in result['metadata']['memory_after'].values() for v in values):
            raise ValueError('qualification allocator limit exceeded')
        responses.append(result)
        print(json.dumps(dict(stage='gpu_preflight', case=row['name'], completed=len(responses),
            input_tokens=formatter['input_tokens'], seconds=result['metadata']['elapsed_seconds'])), flush=True)
    for first, second in ((5, 7), (6, 8)):
        a, b = (responses[i]['metadata']['memory_after'] for i in (first, second))
        if a['allocated'] != b['allocated'] or any(x > y for x, y in zip(b['reserved'], a['reserved'])):
            raise ValueError('same-server repeat did not reclaim memory')
    final = client.health()
    if final['requests'] != {'completed': 9} or final['identity'] != health['identity']:
        raise ValueError('qualification inference count/identity differs')
    receipt = dict(passed=True, cpu_passed=read(EVIDENCE / 'cpu.json')['passed'],
        length_passed=read(EVIDENCE / 'lengths.json')['passed'], server_loads=1, inferences=9,
        serving_identity=health['identity'], source=sources,
        server_journal=str(RUN / 'serving/server/requests.sqlite3'),
        input_data_identity=__import__('integration.pokechamp.jev_v4', fromlist=['data_identity']).data_identity(),
        max_input_tokens=max(r['metadata']['formatter']['input_tokens'] for r in responses),
        ordinary_preflight_included=True, repeated_memory_passed=True,
        limitation='대표9요청의 실행 가능성 검증; 모든 길이 안정성/일반 성능 미평가', at=time.time())
    if not receipt['cpu_passed'] or not receipt['length_passed']:
        raise ValueError('preparation gate not passed')
    write(EVIDENCE / 'entry-gates.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare'])
    parser.parse_args()
    prepare_requests()
