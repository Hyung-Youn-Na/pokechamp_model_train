"""CPU-only Kev pokechamp r1 HTTP and ordered noul contract (C-054)."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
from urllib.parse import urlsplit
import urllib.error
import urllib.request

from .joint_q.serializer import JointInput

ENDPOINT = 'http://127.0.0.1:8019'
MODEL = 'kev-latest'
PROFILE = 'kev-joint-noul-v1'
TIMEOUT = 600
# Verbatim /ref/kev/scripts/build_pokechamp_ex065.py QUESTION and describe().
QUESTION = ('Candidate {action_id} ({action}): if we choose it now and both sides then continue with the Abyssal policy, '
            'do we win the game?')
CONTINUATION_PROFILE = 'kev-continuation-noul-v1'
CONTINUATION_QUESTION = (
    "Candidate {action_id} ({action}): If we choose this action now, and our side subsequently continues "
    "using Kev's current action-selection policy while the opponent continues using the Abyssal policy, "
    "what is our probability of winning the game?")
QUESTIONS = {PROFILE: QUESTION, CONTINUATION_PROFILE: CONTINUATION_QUESTION}


def question_template(profile=PROFILE):
    if not isinstance(profile, str) or profile not in QUESTIONS:
        raise ValueError('unknown Kev profile: ' + repr(profile))
    return QUESTIONS[profile]


def describe(action):
    if action['kind'] == 'team':
        return f"lead with {action['pokemon']}"
    if action['kind'] == 'switch':
        return f"switch to {action['pokemon']}"
    if action['kind'] == 'move':
        return f"use {action['name']}" + (' and Terastallize' if action['action_id'].endswith('_terastallize') else '')
    raise ValueError(f"unknown candidate kind {action['kind']!r} ({action['action_id']})")


def request_payload(joint, *, model=MODEL, profile=PROFILE):
    question = question_template(profile)
    if type(joint) is not JointInput:
        raise TypeError('Kev accepts JointInput only, never a training record')
    if not isinstance(model, str) or not model:
        raise ValueError('invalid Kev model name')
    questions = {}
    for action in joint.payload['actions']:
        key = action['action_id']
        if not isinstance(key, str) or not key:
            raise ValueError('invalid candidate ID')
        questions[key] = dict(type='noul', instructions=question.format(action_id=key, action=describe(action)))
    # Do not parse/re-serialize the state: exact training bytes are authoritative.
    return dict(model=model, state=joint.payload_json, questions=questions)


def validate_input(body, *, profile=PROFILE):
    question_template(profile)
    if not isinstance(body, dict) or set(body) != {'model', 'state', 'questions'}:
        raise ValueError('expected model, string state and ordered noul questions only')
    if not isinstance(body['state'], str):
        raise ValueError('Kev state must be the JointInput JSON string')
    joint = JointInput(body['state'])
    expected = request_payload(joint, model=body['model'], profile=profile)
    if (not isinstance(body['questions'], dict) or list(body['questions']) != list(expected['questions'])
            or body['questions'] != expected['questions']):
        raise ValueError('Kev question wording, order or coverage differs from declared profile')
    # State is a string on the wire, so check its decoded numbers separately.
    json.dumps(joint.payload, allow_nan=False)
    json.dumps(body, allow_nan=False)
    return joint


def input_sha256(joint):
    if type(joint) is not JointInput:
        raise TypeError('JointInput required')
    return hashlib.sha256(joint.payload_json.encode('utf-8')).hexdigest()


def request_bytes(body, *, profile=PROFILE):
    validate_input(body, profile=profile)
    return json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _action_ids(action_ids):
    if isinstance(action_ids, (str, bytes)):
        raise ValueError('ordered candidate IDs required')
    ids = tuple(action_ids)
    if (not ids or any(not isinstance(key, str) or not key for key in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('empty, malformed or duplicate candidate IDs')
    return ids


def probabilities(body, action_ids):
    ids = _action_ids(action_ids)
    answers = body.get('answers') if isinstance(body, dict) else None
    if not isinstance(answers, dict) or set(answers) != set(ids):
        raise ValueError('incomplete or foreign Kev candidate answers')
    values = {}
    for key in ids:
        answer = answers[key]
        if not isinstance(answer, dict) or answer.get('type') != 'noul':
            raise ValueError('invalid noul answer type: ' + key)
        value = answer.get('noul')
        if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
            raise ValueError('invalid or nonfinite noul probability: ' + key)
        values[key] = value
    return values


def validate_response(body, action_ids):
    values = probabilities(body, action_ids)
    # max preserves the first JointInput candidate on a tie, regardless of answer order.
    return max(values, key=values.__getitem__)


def base_url(endpoint):
    """Numeric loopback only; credentials, DNS, paths and URL overrides are forbidden."""
    try:
        parsed = urlsplit(endpoint)
        if (not isinstance(endpoint, str) or any(c.isspace() or ord(c) < 32 for c in endpoint)
                or any(c in endpoint for c in ('\\', '@', '%', '?', '#'))
                or parsed.scheme != 'http' or parsed.path not in ('', '/')
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or not parsed.port
                or not ipaddress.ip_address(parsed.hostname).is_loopback):
            raise ValueError('invalid endpoint')
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('Kev endpoint must be an HTTP loopback IP with an explicit port') from exc
    return endpoint.rstrip('/')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate response JSON key')
        value[key] = item
    return value


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('nonfinite response JSON number')
    return value


def _invalid_constant(_value):
    raise ValueError('invalid response JSON constant')


def request(path='/v1/systemone', body=None, *, endpoint=ENDPOINT, timeout=TIMEOUT,
            api_key=None, on_response=None, profile=PROFILE):
    """One physical request, with no retries, proxy use or redirects.

    on_response receives (status_code, raw_body) before JSON parsing, including
    HTTP errors, so malformed replies can be preserved without logging headers.
    """
    question_template(profile)
    endpoint = base_url(endpoint)
    if path not in ('/v1/systemone', '/v1/models'):
        raise ValueError('unsupported Kev route')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('invalid Kev timeout')
    if (path == '/v1/systemone') != (body is not None):
        raise ValueError('systemone requires POST body; models requires GET')
    encoded = None
    if body is not None:
        encoded = request_bytes(body, profile=profile)
    headers = {'Content-Type': 'application/json'}
    if api_key:
        if not isinstance(api_key, str) or any(ord(c) < 32 for c in api_key):
            raise ValueError('invalid Kev API key')
        headers['Authorization'] = 'Bearer ' + api_key
    req = urllib.request.Request(endpoint + path, data=encoded, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        response = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if on_response is not None:
            on_response(exc.code, exc.read().decode('utf-8', errors='replace'))
        raise
    with response:
        raw = response.read()
        if on_response is not None:
            on_response(response.status, raw.decode('utf-8', errors='replace'))
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_json_object,
                          parse_float=_finite_float, parse_constant=_invalid_constant)
