"""v10 serving (EX-161 / EX-162): `laya_imitation.serving` with the v10 renderer, without editing that package.

Like `laya_threat.serve`: this process builds the `Policy` itself (`training_v10.Policy10` at the checkpoint's own
caps, the live v10 renderer with a calculator and an engine judge) and registers render `v10` and its models in
`serving`. Requests must carry `early_history` (the EX-162 worker adds it for the v10 models). The laya with
`option_max_len` must be first on PYTHONPATH (`paths.LAYA_SOURCE`).

    python -m integration.laya_v10.serve_v10 --checkpoint DIR --model laya-v10t --ready-file F [--device cuda|cpu]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import signal
import threading

from integration.laya_imitation import serving
from integration.laya_imitation.storage import sha

from . import data_v10, paths, training_v10

MODELS = ('laya-v10t', 'laya-v10t-initial')
RENDER = 'v10'


def register():
    """Make `serving` know render v10 and its models (this process only)."""
    if 'laya-v10t' not in serving.MODELS:
        serving.MODELS = serving.MODELS + MODELS
    if getattr(serving, '_v10_registered', False):
        return
    dataset, matches = serving._dataset, serving.renderer_matches_dataset
    serving._dataset = lambda render: paths.V10_DATASET if render == RENDER else dataset(render)
    serving.renderer_matches_dataset = lambda render='v1': data_v10.renderer_matches_dataset() if render == RENDER \
        else matches(render)
    serving._v10_registered = True


def create_server(checkpoint, model_name, port=0, device='cuda'):
    from integration.laya_engine import judge as J
    from integration.laya_imitation.features import Calc
    training_v10.require_laya()
    register()
    calc, judge = Calc(), J.Judge()
    budget = data_v10.budget()
    policy = training_v10.Policy10(checkpoint, device=device, renderer=data_v10.live_renderer(calc, judge),
                                   token_limit=paths.TOKEN_LIMIT, head_limit=budget['head'])
    if policy.option_max_len not in (budget['option'], 48):
        raise ValueError('checkpoint option cap %d differs from the dataset %d' % (policy.option_max_len,
                                                                                  budget['option']))
    server = serving.create_server(checkpoint, model_name, port, policy=policy, device=device, render=RENDER)
    server.model_identity.update(calculator=calc.identity, judge=J.identity(), option_max_len=policy.option_max_len,
                                 v10_code={n: sha(paths.PACKAGE / n) for n in data_v10.OWN_FILES})
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--model', required=True, choices=MODELS)
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
