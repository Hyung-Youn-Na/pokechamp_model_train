"""EX-083 numerical and uninterrupted-serving gates; never launches a battle."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
import sqlite3
import time

from .client import request_bytes
from .config import EVIDENCE, MODEL_DIR, ROOT
from .formatting import format_request
from .storage import digest, file_hash, read, write

PARENT_EVIDENCE_SEAL = 'a40be7bc927aaa90e9eb0170822bd4f10988dbc381f13d2dc0d1ef445e682193'
TOLERANCE = 1e-4
ALLOCATOR_BYTES = 40 * 1024**3
NVML_BYTES = 44 * 1024**3


def preserved_preparation():
    """Bind archived gates to the approved bytes, including both 2GPU reloads."""
    from .study import verify_seal
    if file_hash(EVIDENCE / 'checksums.sha256') != PARENT_EVIDENCE_SEAL:
        raise ValueError('approved EX-082 evidence seal changed')
    files = verify_seal(EVIDENCE)
    for name in ('download.json', 'environment.json', 'lengths/report.json',
                 'reload-a/result.json', 'reload-b/result.json'):
        if read(EVIDENCE / name).get('passed') is not True:
            raise ValueError('preserved preparation failed: ' + name)
    census = read(EVIDENCE / 'lengths/report.json')
    if (census['requests'] != 1073 or census['above_limit'] != 0
            or census['max_tokens'] != 32768 or census['max_input_tokens'] > 32768
            or census['formatting_sha256'] != file_hash(Path(__file__).with_name('formatting.py'))
            or census['tokenizer_sha256'] != file_hash(MODEL_DIR / 'tokenizer.json')
            or census['source_events_sha256'] != file_hash(ROOT / '.pokechamp-data/jev/ex058-live/events.jsonl')
            or census['rows_sha256'] != file_hash(EVIDENCE / 'lengths/requests.jsonl')):
        raise ValueError('preserved length/formatter/tokenizer gate is stale')
    return dict(passed=True, evidence=str(EVIDENCE), seal_sha256=PARENT_EVIDENCE_SEAL,
                sealed_files=len(files), length_census=census,
                cases_sha256=file_hash(EVIDENCE / 'lengths/cases.json'),
                reloads={name: file_hash(EVIDENCE / name / 'result.json')
                         for name in ('reload-a', 'reload-b')})


def archived_requests(parent):
    """Read successful responses in original order; retain the one unfinished input."""
    requests, responses, rows = {}, set(), []
    for line in (Path(parent) / 'events.jsonl').open():
        event = json.loads(line)
        if event['type'] == 'http_request':
            decision = event['decision']
            raw = event['raw_body'].encode()
            if (raw != request_bytes(event['body'])
                    or hashlib.sha256(raw).hexdigest() != event['body_sha256']):
                raise ValueError('parent request bytes/hash mismatch')
            old = requests.setdefault(decision, event)
            if any(old[key] != event[key] for key in ('body', 'raw_body', 'request_id', 'body_sha256')):
                raise ValueError('parent retry changed request identity')
        elif event['type'] == 'response':
            decision = event['decision']
            if decision in responses or decision not in requests:
                raise ValueError('duplicate or unlinked parent response')
            responses.add(decision)
            request = requests[decision]
            if event['body']['transport']['request_id'] != request['request_id']:
                raise ValueError('parent response request identity mismatch')
            rows.append(dict(decision=decision, request=request, response=event))
    missing = [event for key, event in requests.items() if key not in responses]
    if len(rows) != 591 or len(missing) != 1 or len(requests) != 592:
        raise ValueError('parent replay denominator must be 591 complete and one unfinished')
    if [r['request']['event_seq'] for r in rows] != sorted(r['request']['event_seq'] for r in rows):
        raise ValueError('parent successful requests are not in original order')
    shortest = min(rows, key=lambda r: r['response']['body']['usage']['input_tokens'])
    return rows, missing[0], shortest


def numerical_difference(expected, actual, body):
    """Check all native candidate probabilities, their linkage, choice and prompt."""
    formatted = format_request(body)
    ids = list(formatted.candidate_ids)
    left, right = expected['answers']['action'], actual['answers']['action']
    for response, answer in ((expected, left), (actual, right)):
        metadata = response['metadata']
        if (metadata['candidate_ids'] != ids
                or metadata['prompt_sha256'] != formatted.prompt_sha256
                or set(answer['probabilities']) != set(ids)
                or answer['choice'] not in ids):
            raise ValueError('candidate, choice, or prompt linkage differs')
        if any(type(value) not in (float, int) or not math.isfinite(value)
               or not 0 <= value <= 1 for value in answer['probabilities'].values()):
            raise ValueError('native probability is nonfinite or out of range')
    if expected['usage'] != actual['usage']:
        raise ValueError('same original input has different token usage')
    delta = max(abs(left['probabilities'][key] - right['probabilities'][key]) for key in ids)
    return dict(passed=left['choice'] == right['choice'] and delta <= TOLERANCE,
                same_choice=left['choice'] == right['choice'],
                candidate_ids=ids, max_probability_difference=delta, tolerance=TOLERANCE)


def compare_reloads(directory):
    directory = Path(directory)
    paths = [directory / 'reload-a', directory / 'reload-b',
             EVIDENCE / 'reload-a', EVIDENCE / 'reload-b']
    results = [read(path / 'result.json') for path in paths]
    inputs = read(EVIDENCE / 'lengths/cases.json')
    if len(inputs) != 5 or any(not value.get('passed') for value in results):
        raise ValueError('four complete saved five-input reload results are required')
    if results[0]['pid'] == results[1]['pid']:
        raise ValueError('two independent new reload processes are required')
    identities = [value['metadata']['serving_identity'] for value in results]
    if identities[0] != identities[1] or identities[0] == identities[2]:
        raise ValueError('4GPU serving identity must agree and be distinct from 2GPU')
    rows = []
    for i, j in itertools.combinations(range(4), 2):
        for a, b, case in zip(results[i]['cases'], results[j]['cases'], inputs, strict=True):
            if (a['name'] != case['name'] or b['name'] != case['name']
                    or a['payload_sha256'] != digest(case['body'])
                    or b['payload_sha256'] != digest(case['body'])):
                raise ValueError('reload cases or original input hashes differ')
            rows.append(dict(left=str(paths[i]), right=str(paths[j]), name=case['name'],
                             **numerical_difference(a['body'], b['body'], case['body'])))
    result = dict(passed=all(row['passed'] for row in rows), cases=rows,
                  max_probability_difference=max(row['max_probability_difference'] for row in rows),
                  tolerance=TOLERANCE, serving_identity=identities[0],
                  processes=[value['pid'] for value in results],
                  result_hashes={str(path): file_hash(path / 'result.json') for path in paths})
    write(directory / 'reload-comparison.json', result)
    if not result['passed']:
        raise RuntimeError('4GPU independent/preserved-2GPU numerical gate failed')
    return result


def allocator_evidence(response):
    metadata = response['metadata']
    values = {key: metadata[key] for key in (
        'gpu_allocated_bytes', 'gpu_reserved_bytes', 'gpu_peak_allocated_bytes')}
    if any(not isinstance(vector, list) or len(vector) != 4 for vector in values.values()):
        raise ValueError('all four GPU allocator measurements are required')
    if any(type(value) is not int or not 0 <= value <= ALLOCATOR_BYTES
           for vector in values.values() for value in vector):
        raise ValueError('4GPU allocator exceeds the 40GiB gate')
    return values


def verify_fresh_inference(journal, request_id, body, response, transport):
    """Verify committed execution, not just a response claiming a fresh call."""
    if transport.get('cache_reused') is not False or transport.get('attempt') != 1:
        raise ValueError('validation must use one new request ID and actual inference')
    with sqlite3.connect(Path(journal).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM requests WHERE request_id=?', (request_id,)).fetchone()
        starts = db.execute("SELECT COUNT(*) FROM events WHERE request_id=? AND kind='inference_started'",
                            (request_id,)).fetchone()[0]
        raw = request_bytes(body)
        if (row is None or row['state'] != 'completed' or row['inference_calls'] != 1 or starts != 1
                or row['request_body'] != raw or row['body_sha256'] != hashlib.sha256(raw).hexdigest()
                or row['response_status'] != 200 or json.loads(row['response_body']) != response
                or hashlib.sha256(row['response_body']).hexdigest() != row['response_sha256']):
            raise ValueError('new validation inference does not match the durable journal')
    return dict(passed=True, request_id=request_id, inference_calls=1, inference_starts=1, cache_reused=False)


def call_record(client, body, request_id, directory, journal, *, source):
    started = time.time()
    write(Path(directory) / (request_id + '-request.json'),
          dict(at=started, request_id=request_id, request=body, source=source))
    response = client.evaluate(body, request_id=request_id, retries=0)
    record = dict(at=started, seconds=time.time()-started, request_id=request_id,
                  request_sha256=digest(body), source=source, response=response,
                  transport=client.last_transport)
    # Retain returned evidence even when the subsequent gate rejects it.
    write(Path(directory) / (request_id + '-response.json'), record)
    record['inference'] = verify_fresh_inference(journal, request_id, body, response, client.last_transport)
    record['allocator'] = allocator_evidence(response)
    return record


def replay_parent(client, parent, directory, journal):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    rows, stopped, shortest = archived_requests(parent)
    compared = []
    for number, row in enumerate(rows, 1):
        request = row['request']
        request_id = f'ex083-replay-{number:04d}'
        saved = call_record(client, request['body'], request_id, directory, journal,
                            source=dict(parent=str(parent), decision=row['decision'],
                                        event_seq=request['event_seq'], request_id=request['request_id']))
        result = dict(number=number, decision=row['decision'], request_id=request_id,
                      **numerical_difference(row['response']['body'], saved['response'], request['body']))
        write(directory / f'comparison-{number:04d}.json', result)
        compared.append(result)
        if not result['passed']:
            write(directory / 'result.json', dict(passed=False, planned=591, completed=number,
                                                  comparisons=compared, failed_request_id=request_id))
            raise RuntimeError(f'parent replay numerical gate failed at {number}/591')
        if number % 10 == 0 or number == 591:
            print(json.dumps(dict(stage='parent-replay', completed=number, planned=591,
                                  max_probability_difference=max(r['max_probability_difference'] for r in compared))),
                  flush=True)
    result = dict(passed=True, planned=591, completed=len(compared), comparisons=compared,
                  original_events_sha256=file_hash(Path(parent) / 'events.jsonl'),
                  new_ids=591, actual_inferences=591, cache_reused=0,
                  max_probability_difference=max(row['max_probability_difference'] for row in compared),
                  tolerance=TOLERANCE)
    write(directory / 'result.json', result)
    return result, stopped, shortest


def memory_gate(client, stopped, shortest, directory, journal, *, server_pid, expected_gpus):
    from .resource import gpu_facts
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    sequence = [('stopped-prime', stopped), ('short-1', shortest['request']),
                ('stopped-1', stopped), ('short-2', shortest['request']), ('stopped-2', stopped)]
    records = []
    for name, request in sequence:
        saved = call_record(client, request['body'], 'ex083-memory-' + name, directory, journal,
                            source=dict(decision=request['decision'], request_id=request['request_id']))
        expected_tokens = 16604 if name.startswith('stopped') else shortest['response']['body']['usage']['input_tokens']
        if saved['response']['usage']['input_tokens'] != expected_tokens:
            raise ValueError('continuous memory input token count differs from the original')
        health, facts = client.health(), gpu_facts()
        if health['server_pid'] != server_pid or any(facts[i]['uuid'] != expected_gpus[i]['uuid'] for i in range(4)):
            raise ValueError('memory gate server process or GPU identity changed')
        if any(facts[i]['memory_used_mib'] * 1024**2 > NVML_BYTES for i in range(4)):
            raise ValueError('continuous memory gate exceeded NVML 44GiB')
        health_allocator = allocator_evidence(dict(metadata=health['resource']))
        saved.update(name=name, health=health, health_allocator=health_allocator,
                     gpus={i: facts[i] for i in range(4)})
        write(directory / (name + '.json'), saved)
        records.append(saved)
    comparisons = []
    # Compare the two short and two long inputs in the declared post-prime sequence.
    for a, b in ((records[1], records[3]), (records[2], records[4])):
        for boundary in ('allocator', 'health_allocator'):
            left, right = a[boundary], b[boundary]
            same = left['gpu_allocated_bytes'] == right['gpu_allocated_bytes']
            no_growth = all(y <= x for x, y in zip(left['gpu_reserved_bytes'], right['gpu_reserved_bytes'], strict=True))
            comparisons.append(dict(first=a['name'], second=b['name'], boundary=boundary,
                                    allocated_equal=same, reserved_nonincreasing=no_growth,
                                    passed=same and no_growth))
    result = dict(passed=all(row['passed'] for row in comparisons), sequence=[name for name, _ in sequence],
                  comparisons=comparisons, continuous_server_pid=server_pid, actual_inferences=5,
                  cache_clears=0, server_restarts=0, max_continuously_validated_tokens=16604,
                  allocator_budget_bytes=ALLOCATOR_BYTES, nvml_stop_bytes=NVML_BYTES,
                  max_future_input_tokens=32768)
    write(directory / 'result.json', result)
    if not result['passed']:
        raise RuntimeError('uninterrupted repeat-input memory stability gate failed')
    return result


def ordinary_gate(client, directory, journal):
    from integration.pokechamp.jev_battle import validate_answer
    case = next(case for case in read(EVIDENCE / 'lengths/cases.json') if case['name'] == 'turn-sample-01')
    saved = call_record(client, case['body'], 'ex083-ordinary-preflight-v1', directory, journal,
                        source=dict(path=str(EVIDENCE / 'lengths/cases.json'), name=case['name']))
    choice = validate_answer(saved['response'], case['body']['questions']['action']['criteria'])
    result = dict(passed=True, choice=choice, retries=0, new_battles=0, **saved)
    write(Path(directory) / 'ordinary-preflight.json', result)
    return result
