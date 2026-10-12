"""One-attempt, loopback-only HTTP transport for the EX066 joint q server."""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.request

from ...kev_value import base_url, _NoRedirect, _json_object, _finite_float, _invalid_constant
from . import protocol

TIMEOUT = 600
RESPONSE_IDENTITY = ('profile', 'model', 'revision', 'checkpoint_sha256', 'head_sha256',
                     'server_pid', 'server_started_at', 'source_sha256')
HEALTH_IDENTITY = RESPONSE_IDENTITY + ('physical_gpu', 'gpu_uuid')


class IdentityError(RuntimeError):
    """Shared serving/provenance failure; never a model judgment failure."""


def request_bytes(body):
    protocol.validate_request(body)
    return json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def request(path='/evaluate', body=None, *, endpoint, timeout=TIMEOUT, on_response=None):
    """Send exactly once, bypass proxies/redirects, and preserve pre-parse replies."""
    endpoint = base_url(endpoint)
    if path not in ('/evaluate', '/health') or (path == '/evaluate') != (body is not None):
        raise ValueError('evaluate requires POST body; health requires GET')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= TIMEOUT:
        raise ValueError('invalid joint q request timeout')
    encoded = request_bytes(body) if body is not None else None
    req = urllib.request.Request(endpoint + path, data=encoded, headers={'Content-Type': 'application/json'})
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


def validate_identity(body, expected, *, health=False):
    keys = HEALTH_IDENTITY if health else RESPONSE_IDENTITY
    if not isinstance(body, dict) or not isinstance(expected, dict):
        raise IdentityError('missing joint q server identity')
    for key in keys:
        if key not in expected or body.get(key) != expected[key]:
            raise IdentityError('joint q server identity changed: ' + key)
    if body.get('profile') != protocol.PROFILE:
        raise IdentityError('unexpected joint q profile')
    if health and (body.get('ready') is not True or body.get('physical_gpu') != 0):
        raise IdentityError('qualified GPU0 server is not ready')
    return body


def health(endpoint, expected, *, timeout=10):
    return validate_identity(request('/health', endpoint=endpoint, timeout=timeout), expected, health=True)
