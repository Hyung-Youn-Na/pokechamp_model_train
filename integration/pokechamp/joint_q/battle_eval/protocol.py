"""Target-free loopback wire contract shared by native client and GPU server."""
import hashlib
import json
import math
from ..serializer import JointInput
from .config import PROFILE


def json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate model JSON field: ' + key)
        value[key] = item
    return value


def input_sha256(joint):
    return hashlib.sha256(joint.payload_json.encode()).hexdigest()


def request_payload(joint):
    if type(joint) is not JointInput:
        raise TypeError('JointInput required')
    return dict(profile=PROFILE, payload_json=joint.payload_json)


def validate_request(body):
    if not isinstance(body, dict) or set(body) != {'profile', 'payload_json'}:
        raise ValueError('exact EX081 model input fields required')
    if body['profile'] != PROFILE or not isinstance(body['payload_json'], str):
        raise ValueError('unknown EX081 input profile')
    json.loads(body['payload_json'], object_pairs_hook=json_object)
    result = JointInput(body['payload_json'])
    json.dumps(result.payload, allow_nan=False)
    return result


def validate_response(response, action_ids):
    if not isinstance(response, dict) or response.get('profile') != PROFILE:
        raise ValueError('unexpected EX081 response profile')
    values = response.get('q_values')
    if not isinstance(values, dict) or tuple(values) != tuple(action_ids):
        raise ValueError('candidate q IDs/order differ from input')
    if not values or any(type(v) not in (int, float) or not 0 <= v <= 1 or not math.isfinite(v)
                         for v in values.values()):
        raise ValueError('invalid candidate q values')
    expected = max(action_ids, key=values.__getitem__)
    if response.get('choice') != expected:
        raise ValueError('choice differs from original-order maximum q')
    return expected
