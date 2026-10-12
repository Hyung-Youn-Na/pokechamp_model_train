"""EX-067 identities; deliberately separate from EX-066's sealed storage module."""
from __future__ import annotations

import hashlib
from .storage import ROOT, canonical

EXPERIMENT = 'EX-067'
NAMESPACE = 'EX067'
MASTER = 20260930
VERSION = 'ex067-abyssal-tera-rollout-v2'
DEFAULT = ROOT / '.pokechamp-data/experiments/ex067-abyssal-tera-joint-q'
BACKUP = '/mnt/digicap/combined/hyna/backup/pokechamp/ex067-abyssal-tera-joint-q'
WORKERS = 16
CAPTURE_WORKERS = 4
INPUT_WORKERS = 8
CONTINUATION_INSTRUCTION = (
    'For this dataset, the fixed Abyssal continuation on BOTH sides is abyssal-tera-v1, '
    'the deterministic offensive/defensive Terastallization variant. Each q is conditional '
    'on that continuation after the supplied first action. This does not establish optimal '
    'play or improved battle performance.'
)


def describe_continuation(value):
    """Keep JointInput/schema/loader; clarify the global target, never a decision reason."""
    import json
    from .serializer import JointInput
    if type(value) is not JointInput:
        raise TypeError('JointInput required')
    payload=value.payload
    payload['instructions'] += '\n\n' + CONTINUATION_INSTRUCTION
    return JointInput(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False))


def seed(*parts, simulator=False):
    raw = hashlib.sha256(canonical([NAMESPACE, MASTER, *parts])).digest()
    return ([int.from_bytes(raw[i:i+2], 'big') for i in range(0, 8, 2)]
            if simulator else int.from_bytes(raw[:4], 'big'))


def rollout_seeds(observation_id, replicate):
    return dict(simulator=seed(observation_id, replicate, 'simulator', simulator=True),
                actors={side: seed(observation_id, replicate, side) for side in ('p1', 'p2')})


def policy_spec():
    from ..abyssal_tera import POLICY_ID, DEFAULT_CONFIG, policy_config_hash
    config = DEFAULT_CONFIG.as_dict()
    return dict(policy_id=POLICY_ID, config=config, config_hash=policy_config_hash(config))


def validate_manifest(manifest):
    if (manifest['experiment'] != EXPERIMENT or manifest['namespace'] != NAMESPACE
            or manifest['master_seed'] != MASTER or manifest['version'] != VERSION
            or manifest['policy'] != policy_spec()):
        raise ValueError('EX-067 frozen identity or policy differs')
    return manifest


def seed_function(manifest):
    if manifest.get('namespace') == NAMESPACE:
        validate_manifest(manifest)
        return rollout_seeds
    if manifest.get('namespace', 'EX065') != 'EX065':
        raise ValueError('unknown experiment namespace')
    from .storage import rollout_seeds as legacy
    return legacy
