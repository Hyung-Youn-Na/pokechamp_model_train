"""Loopback-only fixed-checkpoint service for the EX-071 Choice policy."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import signal
import threading
import urllib.request

from .model import (BASE, REVISION, PRECISION, STATE_TOKEN_LIMIT, Policy,
                    checkpoint_identity, json_bytes, verify_checkpoint)


MAX_BODY_BYTES = 4 * 1024 * 1024


class CheckpointIdentityMismatch(ValueError):
    pass


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field: ' + key)
        result[key] = value
    return result


def health(model_name, checkpoint):
    return dict(ready=True, model=model_name, checkpoint=str(Path(checkpoint).resolve()),
                checkpoint_sha256=checkpoint_identity(checkpoint), base=BASE,
                revision=REVISION, precision=PRECISION, state_token_limit=STATE_TOKEN_LIMIT)


def predict_body(policy, payload, *, model_name, checkpoint_sha256):
    if not isinstance(payload, dict) or set(payload) != {'model', 'input'}:
        raise ValueError('request must contain only model and input')
    if payload['model'] != model_name:
        raise CheckpointIdentityMismatch('request model differs from this fixed-checkpoint service')
    # The shared serializer is also the strict incoming HTTP boundary. Nothing
    # outside its allowlist, including targets/audit fields, reaches the policy.
    from .schema import ImitationInput
    value = ImitationInput.from_body(payload['input'])
    prediction = policy.predict(value)
    return dict(model=model_name, checkpoint_sha256=checkpoint_sha256, **prediction)


def create_server(checkpoint, *, model_name, host='127.0.0.1', port=0, policy=None):
    if host != '127.0.0.1':
        raise ValueError('imitation serving may bind only IPv4 loopback')
    if model_name not in ('initial', 'selected'):
        raise ValueError('unknown EX-071 model identity')
    verify_checkpoint(checkpoint)
    policy = policy if policy is not None else Policy(checkpoint=checkpoint)
    policy.eval()
    identity = health(model_name, checkpoint)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            # Requests and replies are preserved by the battle controller;
            # avoid writing observation text into an uncontrolled server log.
            return

        def respond(self, code, value):
            encoded = json_bytes(value)
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(encoded)

        def fail(self, code, classification, message):
            self.respond(code, {'error': {'classification': classification,
                                         'message': str(message)}})

        def do_GET(self):
            if self.path != '/health':
                self.fail(404, 'unknown_route', 'only /health and /evaluate are supported')
                return
            self.respond(200, identity)

        def do_POST(self):
            if self.path != '/evaluate':
                self.fail(404, 'unknown_route', 'only /health and /evaluate are supported')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > MAX_BODY_BYTES:
                    raise ValueError('request content length is missing or exceeds its transport limit')
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('truncated HTTP request body')
                def reject_constant(value):
                    raise ValueError('nonfinite JSON constant: ' + value)
                payload = json.loads(raw, object_pairs_hook=_unique_pairs,
                                     parse_constant=reject_constant)
            except (ValueError, UnicodeError) as exc:
                self.fail(422, 'invalid_input', exc)
                return
            try:
                with lock:
                    result = predict_body(policy, payload, model_name=model_name,
                                          checkpoint_sha256=identity['checkpoint_sha256'])
            except CheckpointIdentityMismatch as exc:
                self.fail(409, 'checkpoint_identity_mismatch', exc)
            except Exception as exc:
                # Kev's typed overflow is a per-decision admission failure;
                # every other source/model fault remains a shared defect.
                from .model import _kev
                _, kev = _kev()
                if isinstance(exc, kev.ContextOverflow):
                    self.fail(413, 'input_length_exceeded', exc)
                elif isinstance(exc, (ValueError, TypeError, KeyError)):
                    self.fail(422, 'invalid_input', exc)
                else:
                    self.fail(500, 'model_failure', exc)
            else:
                self.respond(200, result)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.policy = policy
    server.model_identity = identity
    return server


def verify_saved_probabilities(policy, model_name, checkpoint, records, reference, *, clock=None):
    """Mandatory reload/serving gate using saved validation rows, never test."""
    if not records or len(records) > 8 or len(records) != len(reference):
        raise ValueError('serving parity needs one to eight aligned saved samples')
    server = create_server(checkpoint, model_name=model_name, policy=policy)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    endpoint = f'http://127.0.0.1:{server.server_address[1]}/evaluate'
    # Explicitly disable proxies and redirects; parity is the same loopback
    # route the player calls, with no retry or alternate inference path.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    details = []
    try:
        for row, saved in zip(records, reference, strict=True):
            if clock is not None:
                clock.require(60)
            if row['sample_id'] != saved['sample_id']:
                raise ValueError('serving parity sample identities differ')
            payload = dict(model=model_name, input=row['input'])
            request = urllib.request.Request(endpoint, data=json_bytes(payload),
                headers={'Content-Type': 'application/json'}, method='POST')
            with opener.open(request, timeout=1200) as response:
                actual = json.load(response)
            if (actual['model'] != model_name
                    or actual['checkpoint_sha256'] != server.model_identity['checkpoint_sha256']
                    or actual['input_sha256'] != saved['input_sha256']
                    or actual['action_ids'] != saved['action_ids']
                    or actual['token_count'] != saved['token_count']):
                raise ValueError('served model, input or candidate identity differs from saved validation')
            probabilities = [actual['probabilities'][k] for k in saved['action_ids']]
            if not all(math.isfinite(p) and 0 <= p <= 1 for p in probabilities):
                raise ValueError('served probability is nonfinite or out of range')
            difference = max(abs(a - b) for a, b in zip(probabilities, saved['probabilities'], strict=True))
            details.append(dict(sample_id=row['sample_id'], input_sha256=actual['input_sha256'],
                                maximum_probability_difference=difference,
                                saved_probabilities=saved['probabilities'],
                                served_probabilities=probabilities,
                                saved_choice=saved['choice'], served_choice=actual['choice']))
            if difference > 1e-6 or actual['choice'] != saved['choice']:
                raise ValueError('checkpoint reload/HTTP serving changed saved probabilities')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    return dict(passed=True, model=model_name,
                checkpoint_sha256=server.model_identity['checkpoint_sha256'],
                precision=PRECISION, samples=details,
                maximum_probability_difference=max(r['maximum_probability_difference'] for r in details),
                tolerance=1e-6, transport='loopback_http_evaluate',
                model_path='unmerged_full_row_fp32_pointer',
                requests=len(details), retries=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--model', choices=('initial', 'selected'), required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    from .learning import evaluation_lock, validate_gpu
    validate_gpu(args.output)
    lock = evaluation_lock(args.output)
    if (args.checkpoint.resolve() != Path(lock['model_checkpoints'][args.model]).resolve()
            or checkpoint_identity(args.checkpoint) != lock['checkpoint_sha256'][args.model]):
        raise ValueError('server checkpoint differs from the locked evaluation model')
    server = create_server(args.checkpoint, model_name=args.model, host=args.host, port=args.port)
    def stop(number, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(json_bytes(server.model_identity).decode('utf-8'), flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
