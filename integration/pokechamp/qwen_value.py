"""Wire contract shared by the CPU battle client and the EVE GPU server."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
EVE = ROOT / '.tools/eve-rlcd/worktrees/pokemon-training'
TRAINING = ROOT / '.pokechamp-data/training/ex061'
ADAPTER = TRAINING / 'train/epoch-3-adapter'
RUNTIME = ROOT / '.pokechamp-data/qwen/ex062-server'
LIVE = ROOT / '.pokechamp-data/qwen/ex062-live'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep103'
ENDPOINT = 'http://127.0.0.1:8765'
PROFILE = 'qwen-local-value-v1'
OLD_VERSION = 'jev-choice-v4'
STATE_VERSION = 'qwen-candidate-state-v1'
SUPPORTED_VERSIONS = (OLD_VERSION, STATE_VERSION)
MAX_LEN = 16384
TIMEOUT = 600
MODEL = 'Qwen/Qwen3.5-4B'
REVISION = '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
ADAPTER_SHA = 'fdc82e7e3cc3bc564b2baafc26dd888a3c540f2f13428bac2f204d592297ee23'


def data_module():
    # Only the server imports Torch/ValuePolicy; the battle environment stays separate.
    if str(EVE) not in sys.path:
        sys.path.insert(0, str(EVE))
    from rlcd import pokemon_data
    return pokemon_data


def actions_from(payload, commands):
    from .branch_rollouts.common import command
    criteria = payload['questions']['action']['criteria']
    if list(criteria) != list(commands):
        raise ValueError('candidate order or coverage mismatch')
    return [dict(action_id=k, command=command(commands[k]), description=v)
            for k, v in criteria.items()]


def validate_input(body, *, allowed_versions=None):
    if not isinstance(body, dict) or set(body) != {'observation', 'actions'}:
        raise ValueError('expected observation and ordered actions only')
    data = data_module()
    data.check_boundary(body)
    observation, actions = body['observation'], body['actions']
    allowed_versions = (OLD_VERSION,) if allowed_versions is None else tuple(allowed_versions)
    if not allowed_versions or any(version not in SUPPORTED_VERSIONS for version in allowed_versions):
        raise ValueError('unsupported configured input version')
    if (not isinstance(observation, dict) or observation.get('state', {}).get('version') not in allowed_versions
            or not isinstance(actions, list) or not actions):
        raise ValueError('expected an explicitly enabled observation version and ordered actions')
    criteria = observation['questions']['action']['criteria']
    ids, commands = [], []
    for action in actions:
        if not isinstance(action, dict) or set(action) != {'action_id', 'command', 'description'}:
            raise ValueError('invalid action fields')
        key = action['action_id']
        if not isinstance(key, str) or not key or action['description'] != criteria.get(key):
            raise ValueError('candidate description mismatch')
        data.command_check(action, observation)
        ids.append(key)
        commands.append(action['command'])
    if ids != list(criteria) or len(set(ids)) != len(ids) or len(set(commands)) != len(commands):
        raise ValueError('candidate order, duplicate or coverage mismatch')
    return observation, actions


def validate_response(body, actions):
    if not isinstance(body, dict) or body.get('profile') != PROFILE:
        raise ValueError('invalid response profile')
    if body.get('revision') != REVISION or body.get('adapter_sha256') != ADAPTER_SHA:
        raise RuntimeError('server model identity changed')
    values = body.get('q_values')
    ids = [a['action_id'] for a in actions]
    if (not isinstance(values, dict) or list(values) != ids or
            any(type(q) not in (float, int) or not math.isfinite(q) or not 0 <= q <= 1
                for q in values.values())):
        raise ValueError('incomplete or nonfinite q values')
    chosen = max(actions, key=lambda a: values[a['action_id']])
    if body.get('choice') != chosen['action_id'] or body.get('command') != chosen['command']:
        raise ValueError('choice or command differs from ordered maximum q')
    audit = body.get('candidates')
    if not isinstance(audit, list) or [r.get('action_id') for r in audit] != ids:
        raise ValueError('incomplete token audit')
    for row in audit:
        if (type(row.get('tokens')) is not int or not 0 < row['tokens'] <= MAX_LEN or
                any(not isinstance(row.get(k), str) or len(row[k]) != 64
                    for k in ('prompt_sha256', 'token_sha256'))):
            raise ValueError('invalid token audit')
    return chosen['action_id']


def request(path, body=None, *, timeout=TIMEOUT):
    encoded = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
    req = urllib.request.Request(ENDPOINT + path, data=encoded,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def verify_adapter():
    data = data_module()
    seals = dict(line.split('  ', 1)[::-1] for line in (TRAINING / 'checksums.sha256').read_text().splitlines())
    for path in sorted(ADAPTER.iterdir()):
        if path.is_file() and data.sha256(path) != seals[str(path.relative_to(TRAINING))]:
            raise RuntimeError('sealed adapter file changed: ' + path.name)
    if data.sha256(ADAPTER / 'adapter_model.safetensors') != ADAPTER_SHA:
        raise RuntimeError('adapter identity mismatch')
    return {p.name: data.sha256(p) for p in ADAPTER.iterdir() if p.is_file()}


def encoded_candidates(body, tok, *, allowed_versions=None):
    data = data_module()
    observation, actions = validate_input(body, allowed_versions=allowed_versions)
    encoded = []
    for action in actions:
        example = data.InputExample(observation, tuple(actions), action, data.question(action))
        prompt, ids = data.render(example, tok)
        if not ids or len(ids) > MAX_LEN:
            raise ValueError(f"input {action['action_id']} has {len(ids)} tokens; no truncation")
        encoded.append((ids, dict(action_id=action['action_id'], tokens=len(ids),
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            token_sha256=hashlib.sha256(json.dumps(ids).encode()).hexdigest())))
    return actions, encoded
