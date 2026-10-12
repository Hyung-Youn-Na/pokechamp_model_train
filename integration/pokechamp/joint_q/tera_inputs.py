"""EX-067 public Tera resource history, separate from current Pokemon typing."""
from __future__ import annotations

import json
import re

from .serializer import JointInput

VERSION = 'ex067-public-tera-observation-v2'
OLD_STATE_RULE = 'false terastallized means not used on this Pokemon.'
NEW_STATE_RULE = (
    'false terastallized is the current Pokemon flag and can also describe a fainted former Tera user. '
    'state.terastallization_used records each team\'s public Tera resource consumption; '
    'it remains true after its user faints.'
)
OLD_INSTRUCTION = 'terastallized is actual use, not availability.'
NEW_INSTRUCTION = (
    'terastallized is the current per-Pokemon flag. Consult state.terastallization_used '
    'for whether self or opponent has spent its once-per-battle Tera resource, '
    'including after its user faints.'
)


def public_tera_used(prefix, *, actor='p2'):
    """Only completed public protocol events contribute; requests are ignored."""
    if actor not in ('p1', 'p2'):
        raise ValueError('unknown public observer side')
    used = set()
    for event in prefix:
        for line in event['protocol'].splitlines():
            if not line.startswith('|-terastallize|'):
                continue
            fields = line.split('|')
            if len(fields) != 4 or not re.fullmatch(r'p[12][a-z]?: .+', fields[2]) or not fields[3]:
                raise ValueError('malformed public Tera event')
            side = fields[2][:2]
            if side in used:
                raise ValueError('multiple public Tera uses on one side')
            used.add(side)
    other = 'p1' if actor == 'p2' else 'p2'
    return dict(self=actor in used, opponent=other in used)


def with_public_tera(value, prefix):
    """Retain JointInput and current type fields; add two observed resource bits."""
    if type(value) is not JointInput:
        raise TypeError('JointInput required')
    payload = value.payload
    state = payload['state']
    spent = public_tera_used(prefix, actor=state['actor'])
    if 'terastallization_used' in state and state['terastallization_used'] != spent:
        raise ValueError('existing public Tera resource facts disagree')
    state['terastallization_used'] = spent
    rules = state['information_rules']
    if OLD_STATE_RULE in rules:
        state['information_rules'] = rules.replace(OLD_STATE_RULE, NEW_STATE_RULE)
    elif NEW_STATE_RULE not in rules:
        raise ValueError('unknown per-Pokemon Tera semantics')
    if OLD_INSTRUCTION in payload['instructions']:
        payload['instructions'] = payload['instructions'].replace(OLD_INSTRUCTION, NEW_INSTRUCTION)
    elif NEW_INSTRUCTION not in payload['instructions']:
        raise ValueError('unknown Tera input instruction')
    return JointInput(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
