"""v8lt serving with the EX-164 mixing rule: `laya_imitation.serving` with a wrapped policy, without editing that package.

The process builds the v8l `Policy` itself (as `serving.create_server` does for render v8l), registers the mixing
models in `serving.MODELS` for this process only, and passes an object whose `predict` is `mix.wrap(policy)`. The
served identity carries the rule parameters and the laya_mindgame file hashes.

    python -m integration.laya_mindgame.serve --checkpoint DIR --model laya-v8lt-mix --ready-file F [--device cuda|cpu]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import signal
import threading
from types import SimpleNamespace

from integration.laya_imitation import config as c
from integration.laya_imitation import serving

from . import mix

RENDER = 'v8l'


def create_server(checkpoint, model_name, port=0, device='cuda'):
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.policy import Policy
    from .battle import package_identity
    if model_name not in serving.MODELS:
        serving.MODELS = serving.MODELS + mix.MODELS
    calc = Calc()
    policy = Policy(checkpoint, device=device, head_limit=c.V2_HEAD_LIMIT, renderer=serving.v8l_renderer(calc),
                    token_limit=c.TOKEN_LIMIT)
    server = serving.create_server(checkpoint, model_name, port, policy=SimpleNamespace(predict=mix.wrap(policy)),
                                   device=device, render=RENDER)
    server.model_identity.update(calculator=calc.identity, decision=mix.identity(), mindgame_code=package_identity())
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--model', required=True, choices=mix.MODELS)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--ready-file')
    parser.add_argument('--device', default='cuda', choices=('cuda', 'cpu'))
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
