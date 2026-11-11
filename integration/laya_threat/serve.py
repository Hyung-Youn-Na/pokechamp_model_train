"""v9 serving (EX-157 / EX-158): `laya_imitation.serving` with the v9 renderer, without editing that package.

`laya_imitation.serving.create_server` builds its renderer from a fixed table, so this module builds the `Policy`
itself (v9 live renderer, EX-149 budgets) and passes it in. The same process registers the v9 models in
`serving.MODELS`, maps render `v9` to the `v9-all` dataset and checks the v9 generator source instead of a
laya_imitation file list. The served identity carries the calculator and the laya_threat file hashes.

    python -m integration.laya_threat.serve --checkpoint DIR --model laya-v9t --ready-file F [--device cuda|cpu]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import signal
import threading

from integration.laya_imitation import config as c
from integration.laya_imitation import serving
from integration.laya_imitation.storage import sha

from . import data_v9, paths

MODELS = ('laya-v9t', 'laya-v9t-initial')
RENDER = 'v9'


def register():
    """Make `serving` know render v9 and its models (this process only)."""
    if 'laya-v9t' not in serving.MODELS:
        serving.MODELS = serving.MODELS + MODELS
    if getattr(serving, '_v9_registered', False):
        return
    dataset, matches = serving._dataset, serving.renderer_matches_dataset
    serving._dataset = lambda render: paths.V9_DATASET if render == RENDER else dataset(render)
    serving.renderer_matches_dataset = lambda render='v1': data_v9.renderer_matches_dataset() if render == RENDER \
        else matches(render)
    serving._v9_registered = True


def create_server(checkpoint, model_name, port=0, device='cuda'):
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.policy import Policy
    register()
    calc = Calc()
    policy = Policy(checkpoint, device=device, head_limit=c.V2_HEAD_LIMIT, renderer=data_v9.live_renderer(calc),
                    token_limit=c.TOKEN_LIMIT)
    server = serving.create_server(checkpoint, model_name, port, policy=policy, device=device, render=RENDER)
    server.model_identity.update(calculator=calc.identity,
                                 threat_code={n: sha(paths.PACKAGE / n) for n in data_v9.OWN_FILES})
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
