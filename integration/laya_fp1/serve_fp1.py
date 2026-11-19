"""EX-179 (D-213): fp1 serving — the EX-178 model scoring the live fp1 input (laya env).

    python -m integration.laya_fp1.serve_fp1 --checkpoint DIR --model laya-fp1 --ready-file F [--device cpu|cuda]

The `laya_imitation.serving` contract (`GET /health`, `POST /evaluate` -> model, checkpoint_sha256, input_sha256,
action_ids, probabilities, choice), with one addition: the request's `input` carries an `fp1` member (the public
prefix, own sets, snapshot, decision kind and the bot's previous choice; `battle_fp1.Fp1Session` adds it). It is
taken out before the input is validated, so `input_sha256` is the plain EX-071 input's hash, as the player checks.
The fp1 text is rendered by `render_worker` (foul-play venv, one tracker per game) and scored by
`laya_v10.training_v10.Policy10` at the checkpoint's own caps (2,048 / head 768 / option 64), like EX-178's tests.
The argmax of the served distribution is the choice (no guard), as in EX-174.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import threading

from integration.laya_imitation import config as c

MODELS = ('laya-fp1',)
INSTRUCTIONS = 'Pick the action a strong player would choose for me in this Gen 9 OU singles battle.'
FP_PYTHON = c.ROOT / '.tools/foul-play/.venv/bin/python'
MAX_BODY = 8 << 20


class Renderer:
    def __init__(self):
        env = dict(os.environ, PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH='%s:%s' % (c.ROOT, c.ROOT / '.tools/foul-play/src'), CUDA_VISIBLE_DEVICES='')
        self.process = subprocess.Popen([str(FP_PYTHON), '-m', 'integration.laya_fp1.render_worker'], cwd=c.ROOT,
                                        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        ready = json.loads(self.process.stdout.readline() or '{}')
        if ready.get('status') != 'ready':
            raise RuntimeError('fp1 render worker failed to start')
        self.version = ready['render']

    def call(self, request):
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('fp1 render worker exited')
        return json.loads(line)


def create_server(checkpoint, model_name, port=0, device='cpu'):
    from integration.laya_imitation.serving import checkpoint_identity
    from integration.laya_v10 import training_v10
    from integration.pokechamp.imitation.schema import ImitationInput
    from integration.laya_imitation.storage import sha
    training_v10.require_laya()
    training_v10.install(64)
    policy = training_v10.Policy10(checkpoint, device=device, token_limit=2048, head_limit=768)
    renderer = Renderer()
    code = {p.name: sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    identity = dict(ready=True, model=model_name, checkpoint=str(Path(checkpoint).resolve()),
                    checkpoint_sha256=checkpoint_identity(checkpoint), render=renderer.version,
                    fp1_render=dict(version=renderer.version, code=code), token_limit=2048, head_limit=768,
                    option_max_len=policy.option_max_len)
    lock = threading.Lock()

    def predict(value, fp1):
        ids = list(value.action_ids)
        criteria_in = value.body['questions']['action']['criteria']
        reply = renderer.call(dict(op='render', game=fp1['game'], side=fp1['side'], own_sets=fp1['own_sets'],
                                   lines=fp1['lines'], snapshot=fp1['snapshot'], decision_kind=fp1['decision_kind'],
                                   actions=[dict(id=k, description=v) for k, v in criteria_in.items()],
                                   previous=fp1.get('previous'),
                                   sample_id='%s:%s:%d:%s' % (fp1['game'], fp1['side'], len(fp1['lines']),
                                                              fp1['decision_kind'])))
        if 'error' in reply:
            raise ValueError('fp1 render failed: ' + reply['error'])
        if list(reply['criteria']) != ids:
            raise ValueError('fp1 option ids differ from the input')
        question = dict(type='choice', instructions=INSTRUCTIONS, criteria=reply['criteria'])
        [row] = policy.logits([policy.item(reply['state'], question)])
        probs, _ = policy.distribution(row, len(ids))
        probabilities = dict(zip(ids, probs))
        return dict(input_sha256=value.sha256, action_ids=ids, probabilities=probabilities,
                    choice=max(ids, key=lambda k: probabilities[k]), fp1_state=reply['state'],
                    fp1_criteria=reply['criteria'], fp1_diagnostics=reply['diagnostics'])

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            return

        def respond(self, code_, value):
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code_)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(encoded)

        def fail(self, code_, classification, message):
            self.respond(code_, {'error': {'classification': classification, 'message': str(message)}})

        def do_GET(self):
            if self.path != '/health':
                return self.fail(404, 'unknown_route', 'only /health and /evaluate are supported')
            self.respond(200, identity)

        def do_POST(self):
            if self.path != '/evaluate':
                return self.fail(404, 'unknown_route', 'only /health and /evaluate are supported')
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > MAX_BODY:
                    raise ValueError('request content length is missing or exceeds its transport limit')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or set(payload) != {'model', 'input'}:
                    raise ValueError('request must contain only model and input')
                if payload['model'] != model_name:
                    return self.fail(409, 'checkpoint_identity_mismatch', 'request model differs')
                body = dict(payload['input'])
                fp1 = body.pop('fp1')
                value = ImitationInput.from_body(body)
            except (ValueError, TypeError, KeyError) as exc:
                return self.fail(422, 'invalid_input', exc)
            try:
                with lock:
                    result = predict(value, fp1)
            except (ValueError, TypeError, KeyError) as exc:
                self.fail(422, 'invalid_input', exc)
            except Exception as exc:
                self.fail(500, 'model_failure', exc)
            else:
                self.respond(200, dict(model=model_name, checkpoint_sha256=identity['checkpoint_sha256'], **result))

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.model_identity = identity
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--model', required=True, choices=MODELS)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--ready-file')
    parser.add_argument('--device', default='cpu', choices=('cuda', 'cpu'))
    args = parser.parse_args(argv)
    server = create_server(args.checkpoint, args.model, args.port, args.device)
    host, bound = server.server_address
    if args.ready_file:
        Path(args.ready_file).write_text(json.dumps(dict(server.model_identity,
                                                         endpoint='http://%s:%d' % (host, bound))))

    def stop(number, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server.serve_forever()
    server.server_close()


if __name__ == '__main__':
    main()
