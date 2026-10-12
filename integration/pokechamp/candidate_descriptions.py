"""Lossless exact-string sharing of repeated effects and conditional role text."""
from __future__ import annotations

from collections import Counter
import copy
import re

POOL = 'effect_descriptions'
REFERENCE = 'general_effect_ref'
ORIGINAL = 'general_effect'
MIN_LENGTH = 80
ROLE_POOL = 'role_descriptions'
POOLS = {POOL: 'e', ROLE_POOL: 'r'}


def _role_parent(path):
    return (len(path) >= 4 and path[0] == 'state' and
            path[1] in ('self_team', 'opponent_team') and type(path[2]) is int and
            path[3] == 'role_summary')


def _description(path, key):
    if key == ORIGINAL:
        return POOL, REFERENCE
    if _role_parent(path):
        if len(path) == 4 and key == 'scope':
            return ROLE_POOL, 'scope_ref'
        if len(path) == 6 and path[4] == 'roles' and type(path[5]) is int and key == 'description':
            return ROLE_POOL, 'description_ref'
    return None


def _reference(path, key):
    original = {REFERENCE: ORIGINAL, 'scope_ref': 'scope', 'description_ref': 'description'}.get(key)
    rule = _description(path, original) if original else None
    return (rule[0], original) if rule and key == rule[1] else None


def _state(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('state'), dict):
        raise ValueError('description sharing requires a payload with state')
    return payload['state']


def expand(payload):
    """Resolve exact references into a new copy, preserving fields and key order."""
    state = _state(payload)
    pools = {name: state.get(name, {}) for name in POOLS}
    for name, pool in pools.items():
        if not isinstance(pool, dict) or any(not isinstance(key, str) or
                re.fullmatch(POOLS[name] + r'\d+', key) is None or not isinstance(text, str)
                for key, text in pool.items()):
            raise ValueError('invalid description registry: ' + name)
    referenced = {name: set() for name in POOLS}

    def visit(value, path=()):
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                if path == ('state',) and key in POOLS:
                    continue
                rule = _reference(path, key)
                if rule:
                    pool_name, original = rule
                    if original in value:
                        raise ValueError('description contains both text and reference')
                    if not isinstance(child, str) or child not in pools[pool_name]:
                        raise ValueError('unresolved ' + key + ': ' + str(child))
                    referenced[pool_name].add(child)
                    result[original] = pools[pool_name][child]
                else:
                    result[key] = visit(child, path + (key,))
            return result
        if isinstance(value, list):
            return [visit(child, path + (index,)) for index, child in enumerate(value)]
        return copy.deepcopy(value)

    expanded = visit(payload)
    if any(referenced[name] != set(pool) for name, pool in pools.items()):
        raise ValueError('description registry contains unreferenced entries')
    return expanded


def compact(payload):
    """Share repeated long effects and role wording; IDs, facts and text are intact."""
    original = expand(payload)
    frequencies = {name: Counter() for name in POOLS}

    def count(value, path=()):
        if isinstance(value, dict):
            for key, child in value.items():
                rule = _description(path, key)
                if rule and isinstance(child, str) and len(child) >= (MIN_LENGTH if rule[0] == POOL else 1):
                    frequencies[rule[0]][child] += 1
                count(child, path + (key,))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                count(child, path + (index,))

    count(original)
    texts = {name: [text for text, frequency in counter.items() if frequency > 1]
             for name, counter in frequencies.items()}
    refs = {name: {text: POOLS[name] + str(index) for index, text in enumerate(values)}
            for name, values in texts.items()}

    def visit(value, path=()):
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                rule = _description(path, key)
                if rule and isinstance(child, str) and child in refs[rule[0]]:
                    result[rule[1]] = refs[rule[0]][child]
                else:
                    result[key] = visit(child, path + (key,))
            return result
        if isinstance(value, list):
            return [visit(child, path + (index,)) for index, child in enumerate(value)]
        return copy.deepcopy(value)

    result = visit(original)
    for name, values in texts.items():
        if values:
            result['state'][name] = {refs[name][text]: text for text in values}
    return result
