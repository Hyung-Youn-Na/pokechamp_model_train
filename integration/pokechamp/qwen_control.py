"""Owned process lifecycle and frozen EX-061 HTTP replay checks."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
import uuid

from . import qwen_value as v

STATE = v.RUNTIME / 'owner.json'


def process_identity(pid):
    path = Path('/proc') / str(pid)
    try:
        # comm can contain spaces; split after its final closing parenthesis.
        tail = (path / 'stat').read_text().rsplit(')', 1)[1].split()
        return dict(start_ticks=tail[19], state=tail[0],
                    args=(path / 'cmdline').read_bytes().decode().split('\0'))
    except FileNotFoundError:
        return None


def owned(record):
    actual = process_identity(record['pid'])
    return bool(actual and actual['state'] != 'Z' and actual['start_ticks'] == record['start_ticks']
                and 'integration.pokechamp.qwen_server' in actual['args']
                and record['owner'] in actual['args'])


def status():
    record = json.loads(STATE.read_text()) if STATE.exists() else None
    health = None
    try:
        health = v.request('/health', timeout=2)
    except (OSError, ValueError):
        pass
    return dict(owned_running=bool(record and owned(record)), owner=record, health=health)


def start(*, candidate_state=False, diagnostics=False, deadline_at=None, owner_token=None):
    if owner_token is not None and re.fullmatch(r'[a-f0-9]{32}', owner_token) is None:
        raise ValueError('invalid owned collection token')
    if deadline_at is not None and time.time() >= deadline_at:
        raise TimeoutError('owned server loading deadline expired')
    if STATE.exists() and owned(json.loads(STATE.read_text())):
        existing = status()
        if owner_token is not None and existing['owner']['owner'] != owner_token:
            raise ValueError('owned server belongs to a different collection')
        health = existing.get('health') or {}
        expected = v.SUPPORTED_VERSIONS if candidate_state else (v.OLD_VERSION,)
        if (tuple(health.get('allowed_input_versions', (v.OLD_VERSION,))) != expected or
                bool(health.get('diagnostics_enabled')) != diagnostics):
            raise ValueError('owned server has different explicit input/diagnostic settings')
        return existing
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 8765))
    v.verify_adapter()
    v.RUNTIME.mkdir(parents=True, exist_ok=True)
    owner = owner_token or uuid.uuid4().hex
    output = v.RUNTIME / owner
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='1', HF_HOME=str(v.EVE / '.cache/huggingface'),
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1',
        PYTHONPATH=str(v.ROOT), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    with (v.RUNTIME / (owner + '.log')).open('xb') as log:
        process = subprocess.Popen([str(v.EVE / '.venv-eve-rlcd/bin/python'), '-m',
            'integration.pokechamp.qwen_server', '--owner', owner, '--output', str(output),
            *(['--candidate-state'] if candidate_state else []),
            *(['--diagnostics'] if diagnostics else []),
            *(['--deadline-at', str(deadline_at)] if deadline_at is not None else [])],
            cwd=v.ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
    identity = process_identity(process.pid)
    record = dict(pid=process.pid, start_ticks=identity['start_ticks'], owner=owner,
                  output=str(output), started_at=time.time())
    v.data_module().dump(STATE, record)
    while owned(record):
        if deadline_at is not None and time.time() >= deadline_at:
            stop(timeout=60, expected_owner=record)
            raise TimeoutError('owned server loading deadline expired')
        result = status()
        if result['health'] and result['health']['ready']:
            return result
        time.sleep(.5)
    raise RuntimeError('owned server startup failed; inspect ' + str(v.RUNTIME / (owner + '.log')))


def stop(*, timeout=None, expected_owner=None):
    if not STATE.exists():
        return dict(stopped=True, reason='no owned process')
    record = json.loads(STATE.read_text())
    if expected_owner is not None and any(record.get(k) != expected_owner.get(k)
            for k in ('owner', 'pid', 'start_ticks')):
        return dict(stopped=False, reason='owned process identity changed; left untouched')
    if owned(record):
        os.kill(record['pid'], signal.SIGTERM)
        deadline = None if timeout is None else time.monotonic() + timeout
        while owned(record):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('owned server cleanup deadline expired')
            time.sleep(.2)
    result = dict(stopped=True, owner=record)
    closure = Path(record['output']) / 'closure.json'
    result['closure'] = json.loads(closure.read_text()) if closure.exists() else None
    return result


def probe(output):
    output.mkdir(parents=True, exist_ok=False)
    data = v.data_module()
    examples = data.load_examples(v.TRAINING / 'data')
    tokens = {(r['anchor_id'], r['action_id']): r['input_ids']
              for r in data.jsonl(v.TRAINING / 'prepared/tokens.jsonl')}
    expected_audit = {(r['anchor_id'], r['action_id']): r
                     for r in json.loads((v.TRAINING / 'prepared/input-audit.json').read_text())['records']}
    predictions = {(r['anchor_id'], r['action_id']): r['q']
                   for r in data.jsonl(v.TRAINING / 'reload/reload.jsonl')}
    # Revalidate the converted data and frozen replay files before any forward.
    seals = dict(line.split('  ', 1)[::-1] for line in (v.TRAINING / 'checksums.sha256').read_text().splitlines())
    for name in ['prepared/tokens.jsonl', 'prepared/input-audit.json', 'reload/reload.jsonl']:
        if data.sha256(v.TRAINING / name) != seals[name]:
            raise RuntimeError('replay source seal mismatch: ' + name)
    groups = {}
    for example in examples:
        groups.setdefault(example.anchor_id, []).append(example)
    difference, candidates = 0.0, 0
    for anchor, group in groups.items():
        example = group[0].input
        body = dict(observation=example.observation, actions=list(example.actions))
        response = v.request('/evaluate', body)
        v.validate_response(response, body['actions'])
        for row in response['candidates']:
            key = anchor, row['action_id']
            audit = expected_audit[key]
            for field in ('tokens', 'prompt_sha256', 'token_sha256'):
                if row[field] != audit[field]:
                    raise RuntimeError('saved prompt/token mismatch: ' + str(key))
            if row['tokens'] != len(tokens[key]):
                raise RuntimeError('saved token count mismatch')
            difference = max(difference, abs(response['q_values'][key[1]] - predictions[key]))
            candidates += 1
        data.dump(output / (anchor + '.json'), dict(input=body, response=response))
        print(json.dumps(dict(observations=len(list(output.glob('*.json'))), candidates=candidates,
                              max_q_difference=difference)), flush=True)
    result = dict(passed=difference <= 1e-4 and len(groups) == 22 and candidates == 167,
                  observations=len(groups), candidates=candidates, max_q_difference=difference,
                  prompt_and_token_hashes_exact=True, optimizer_updates=0,
                  health=v.request('/health'), source_hashes={n: data.sha256(v.TRAINING / n)
                     for n in ['prepared/tokens.jsonl', 'prepared/input-audit.json', 'reload/reload.jsonl']})
    data.dump(output / 'verification.json', result)
    if not result['passed']:
        raise RuntimeError('GPU replay verification failed')
    return result


def token_audit(source, output):
    data = v.data_module()
    from rlcd.pokemon_value import tokenizer
    tok = tokenizer()
    events = data.jsonl(source / 'events.jsonl')
    inputs = {e['decision']: e for e in events if e['type'] == 'input'}
    checked = 0
    for response in (e for e in events if e['type'] == 'response'):
        entry = inputs[response['decision']]
        _, encoded = v.encoded_candidates(dict(observation=entry['payload'], actions=entry['actions']), tok)
        for (_, actual), expected in zip(encoded, response['body']['candidates']):
            if any(actual[k] != expected[k] for k in actual):
                raise ValueError('battle prompt/token hash mismatch')
            checked += 1
    result = dict(passed=True, observations=len(inputs), candidates=checked, cuda_initialized=False)
    data.dump(output, result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['start', 'status', 'stop', 'probe', 'token-audit'])
    p.add_argument('--output', type=Path)
    p.add_argument('--source', type=Path)
    p.add_argument('--candidate-state', action='store_true')
    p.add_argument('--diagnostics', action='store_true')
    p.add_argument('--deadline-at', type=float, help='absolute UNIX loading deadline')
    args = p.parse_args()
    if args.command == 'start':
        result = start(candidate_state=args.candidate_state, diagnostics=args.diagnostics,
                       deadline_at=args.deadline_at)
    elif args.command in ('status', 'stop'):
        result = globals()[args.command]()
    elif args.command == 'probe':
        result = probe(args.output or v.EVIDENCE / 'gpu-probe')
    else:
        result = token_audit(args.source or v.LIVE, args.output or v.EVIDENCE / 'token-audit.json')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
