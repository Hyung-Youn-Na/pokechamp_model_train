"""Loopback-only fixed-checkpoint service with the EX-071 `/health` + `/evaluate` contract.

The EX-071 player (`imitation/player.py`) talks to it unchanged: the request carries the
validated `ImitationInput` body, and the response carries model, checkpoint, input hash, action
order, a full-precision distribution and its argmax. The renderer and dex must be byte-identical to
the ones that built the training data, so offline and live inputs cannot drift.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import threading

from integration.pokechamp.imitation.schema import ImitationInput
from integration.pokechamp.imitation.serving import CheckpointIdentityMismatch, _unique_pairs

from . import config as c
from . import input_variants, tera_decision
from .storage import digest, read, sha

MAX_BODY_BYTES = 4 * 1024 * 1024
MODELS = ('laya-selected', 'laya-initial', 'laya-v1', 'laya-v2', 'laya-v2-initial', 'laya-v2t', 'laya-v2t-initial',
          'laya-v2te', 'laya-v2te-initial', 'laya-v3t', 'laya-v3t-initial', 'laya-v4t', 'laya-v4t-initial',
          'laya-v2tw', 'laya-v2tw-initial', 'laya-v5t', 'laya-v5t-initial',
          'laya-v2t-fix', 'laya-v2t-info', 'laya-v2t-info-initial',
          'laya-v2t-fix-tp1', 'laya-v2t-fix-tp3', 'laya-v2t-fix-tp3-initial', 'laya-v2t-fix-tdef',
          'laya-v6st', 'laya-v6st-initial', 'laya-v6ht', 'laya-v6ht-initial')


def checkpoint_identity(path):
    files = {p.relative_to(path).as_posix(): sha(p) for p in sorted(Path(path).rglob('*'))
             if p.is_file() and '.cache' not in p.parts and p.name not in ('README.md', 'checksums.sha256')}
    return digest(files)


V2_RENDER_FILES = ('compact.py', 'dex.py', 'dex_gen9.json', 'compact_v2.py', 'features.py', 'dex_v2.py',
                   'dex_gen9_v2.json', 'assumed_sets_v2.json', 'calc.cjs')


V3_RENDER_FILES = V2_RENDER_FILES + ('compact_v3.py', 'features_v3.py', 'usage_sets_v3.json')
V4_RENDER_FILES = V2_RENDER_FILES + ('compact_v4.py', 'features_v4.py', 'effect_knowledge.py', 'effect_rules.json',
                                     'dex_gen9_effects.json')
V5_RENDER_FILES = V4_RENDER_FILES + ('compact_v5.py', 'features_v5.py')
V6_RENDER_FILES = V5_RENDER_FILES + ('compact_v6.py', 'data_v6.py')


def _dataset(render):
    return {'v1': c.DATASET, 'v2': c.V2_DATASET, 'v3': c.V3_DATASET, 'v4': c.V4_DATASET, 'v5': c.V5_DATASET,
            'v6s': c.V6S_DATASET, 'v6h': c.V6H_DATASET,
            'v2fix': c.V2_DATASET, 'v2info': c.V2_DATASET, 'v2fixtd': c.V2_DATASET}[render]


def renderer_matches_dataset(render='v1'):
    if render in input_variants.RENDERS or render == tera_decision.RENDER:   # EX-139/140: v2-trained, v5 renderer files
        return input_variants.matches()
    dataset = _dataset(render)
    names = {'v1': ('compact.py', 'dex.py', 'dex_gen9.json'), 'v2': V2_RENDER_FILES, 'v3': V3_RENDER_FILES,
             'v4': V4_RENDER_FILES, 'v5': V5_RENDER_FILES, 'v6s': V6_RENDER_FILES, 'v6h': V6_RENDER_FILES}[render]
    generator = dataset / 'generator-source'
    package = c.ROOT / 'integration/laya_imitation'
    return all(sha(generator / name) == sha(package / name) for name in names)


def v2_renderer(calc):
    from . import compact_v2, features
    return lambda value: compact_v2.render(value, compact_v2.MODULES, features.compute(value, calc))


def v3_renderer(calc):
    from . import compact_v3, features_v3
    return lambda value: compact_v3.render(value, compact_v3.MODULES, features_v3.compute(value, calc))


def v4_renderer(calc):
    from . import compact_v4, features_v4
    return lambda value: compact_v4.render(value, compact_v4.MODULES, features_v4.compute(value, calc))


def v5_renderer(calc):
    """D-195: live inputs carry the parser fields that EX-071 rows get from `laya-item-state/v1`."""
    from . import compact_v5, features_v5
    return lambda value: compact_v5.render(value, compact_v5.MODULES, features_v5.compute(value, calc))


def v6_renderer(variant):
    """D-198: `v6s` / `v6h` (the latter needs inputs with `early_history`, requested by the battle worker)."""
    def factory(calc):
        from . import data_v6
        return data_v6.live_renderer(variant, calc)
    return factory


def variant_renderer(render):
    """EX-139 (D-196): `v2fix` / `v2info` live renderer factory for the v2-trained EX-124 checkpoint."""
    return lambda calc: input_variants.renderer(render, calc)


def create_server(checkpoint, model_name, port=0, policy=None, device='cuda', render='v1'):
    if model_name not in MODELS:
        raise ValueError('unknown model identity: ' + model_name)
    if not renderer_matches_dataset(render):
        raise ValueError('live renderer differs from the one that built the %s dataset' % render)
    dataset = _dataset(render)
    calc = None
    if policy is None:
        from .policy import Policy
        if render == 'v1':
            policy = Policy(checkpoint, device=device)
        else:
            from .features import Calc
            calc = Calc()
            renderer = dict(v2=v2_renderer, v3=v3_renderer, v4=v4_renderer, v5=v5_renderer,
                            v2fix=variant_renderer('v2fix'), v2info=variant_renderer('v2info'),
                            v2fixtd=tera_decision.renderer, v6s=v6_renderer('v6s'), v6h=v6_renderer('v6h'))[render](calc)
            policy = Policy(checkpoint, device=device, head_limit=c.V2_HEAD_LIMIT, renderer=renderer,
                            token_limit=c.V6H_TOKEN_LIMIT if render == 'v6h' else c.TOKEN_LIMIT)
    identity = dict(ready=True, model=model_name, checkpoint=str(Path(checkpoint).resolve()),
                    checkpoint_sha256=checkpoint_identity(checkpoint),
                    render=read(dataset / 'manifest.json')['render'],
                    token_limit=c.V6H_TOKEN_LIMIT if render == 'v6h' else c.TOKEN_LIMIT,
                    head_limit=c.HEAD_LIMIT if render == 'v1' else c.V2_HEAD_LIMIT,
                    calculator=calc.identity if calc else None)
    if render in input_variants.RENDERS:
        identity.update(input_variants.identity(render))
    if render == tera_decision.RENDER:
        identity.update(tera_decision.identity())
    predict = policy.predict
    if model_name in tera_decision.FACTORS:   # EX-140: Tera-pooled decision distribution
        identity['decision'] = tera_decision.decision_identity(model_name)
        predict = tera_decision.decide(policy, tera_decision.FACTORS[model_name])
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            return

        def respond(self, code, value):
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(encoded)

        def fail(self, code, classification, message):
            self.respond(code, {'error': {'classification': classification, 'message': str(message)}})

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
                payload = json.loads(raw, object_pairs_hook=_unique_pairs)
                if not isinstance(payload, dict) or set(payload) != {'model', 'input'}:
                    raise ValueError('request must contain only model and input')
                if payload['model'] != model_name:
                    raise CheckpointIdentityMismatch('request model differs from this fixed-checkpoint service')
                value = ImitationInput.from_body(payload['input'])
            except CheckpointIdentityMismatch as exc:
                self.fail(409, 'checkpoint_identity_mismatch', exc)
                return
            except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                self.fail(422, 'invalid_input', exc)
                return
            try:
                with lock:
                    result = predict(value)
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


def main(checkpoint, model_name, port=0, ready_file=None, device='cuda', render='v1'):
    """Serve until SIGTERM/SIGINT. Expects CUDA_VISIBLE_DEVICES set by the owning controller."""
    server = create_server(checkpoint, model_name, port, device=device, render=render)
    host, bound = server.server_address
    if ready_file:
        Path(ready_file).write_text(json.dumps(dict(server.model_identity, endpoint='http://%s:%d' % (host, bound))))

    def stop(number, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server.serve_forever()
    server.server_close()
