"""Single-GPU serialized snapshot inference for frozen collection policies."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from ..imitation.model import json_bytes
from ..imitation.schema import ImitationInput
from ..imitation.serving import MAX_BODY_BYTES, _unique_pairs


class Service:
    def __init__(self, policy, snapshots, *, port=8030):
        self.policy, self.snapshots = policy, snapshots
        self.loaded = None
        self.lock = threading.Lock()
        self.failure = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def respond(self, code, body):
                data = json_bytes(body)
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.respond(200, dict(ready=owner.failure is None,
                                       models={k:v['identity'] for k,v in owner.snapshots.items()}))

            def do_POST(self):
                code=200
                try:
                    if self.path != '/evaluate':
                        raise ValueError('unregistered route')
                    length = int(self.headers.get('Content-Length', 0))
                    if not 0 < length <= MAX_BODY_BYTES:
                        raise ValueError('invalid request size')
                    body = json.loads(self.rfile.read(length), object_pairs_hook=_unique_pairs)
                    if set(body) != {'model', 'input', 'seed'} or type(body['seed']) is not int:
                        raise ValueError('invalid sampling request')
                    value = ImitationInput.from_body(body['input'])
                    with owner.lock:
                        if owner.failure:
                            raise RuntimeError('shared model failure already recorded')
                        record = owner.snapshots[body['model']]
                        if owner.loaded != body['model']:
                            owner.policy.load_weights(record['weights'])
                            owner.policy.set_stage('inference')
                            owner.loaded = body['model']
                        result = owner.policy.predict(value.body, seed=body['seed'],
                                                      alternate_head=record.get('alternate_head'))
                        primary=record.get('primary_head','before')
                        main=result['wdl_probabilities']
                        alternate=result.get('wdl_probabilities_after',main)
                        result['wdl_probabilities_before']=alternate if primary=='after' else main
                        result['wdl_probabilities_after']=main if primary=='after' else alternate
                        result['primary_head']=primary
                    result_body=dict(result, model=body['model'],
                                     checkpoint_sha256=record['identity'], rng_seed=body['seed'])
                except Exception as error:
                    from ..imitation.model import _kev
                    _, kev = _kev()
                    overflow = isinstance(error, kev.ContextOverflow)
                    if not overflow:
                        owner.failure = dict(type=type(error).__name__, detail=str(error))
                    code=413 if overflow else 500
                    result_body=dict(error=dict(type=type(error).__name__, detail=str(error)))
                try:
                    self.respond(code,result_body)
                except (BrokenPipeError,ConnectionResetError):
                    # A timed-out actor cannot accept a late reply. It does not
                    # invalidate the model or admit a second request.
                    pass

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        # Closing collection must join every in-flight GPU forward before the
        # runner restores learner weights or starts an optimizer step.
        self.server.daemon_threads = False
        self.server.block_on_close = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.endpoint = f'http://127.0.0.1:{self.server.server_address[1]}'

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)
