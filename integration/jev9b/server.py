"""Single-inference EX-085 service using the shared durable request journal."""
import argparse
import os
from pathlib import Path
import signal

from integration.jev27b import server as shared
from .client import PROTOCOL
from .config import MAX_TOKENS, MODEL_DIR, MODEL_ID, REVISION, RUN

LocalHTTPServer = shared.LocalHTTPServer
RegistryError = shared.RegistryError
json_bytes = shared.json_bytes


class RequestRegistry(shared.RequestRegistry):
    def __init__(self, path, identity):
        super().__init__(path, identity, protocol=PROTOCOL)


class LocalService(shared.LocalService):
    def __init__(self, model, run_dir):
        super().__init__(model, run_dir, model_id=MODEL_ID, revision=REVISION,
                         protocol=PROTOCOL, validate_before_inference=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, default=MODEL_DIR)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--budget-root', type=Path, default=RUN)
    parser.add_argument('--host', default='127.0.0.1', choices=('127.0.0.1',))
    parser.add_argument('--port', default=18785, type=int, choices=(18785,))
    parser.add_argument('--profile', default='ex085', choices=('ex085',))
    args = parser.parse_args(argv)
    from .model import Jev9BModel
    from .resource import own_gpus

    def terminate(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    service = httpd = None
    with own_gpus(args.run_dir, profile=args.profile, budget_root=args.budget_root):
        try:
            model = Jev9BModel(args.model_dir, max_tokens=MAX_TOKENS, profile=args.profile).load()
            service = LocalService(model, args.run_dir)
            httpd = LocalHTTPServer((args.host, args.port), service)
            httpd.serve_forever(poll_interval=0.25)
        finally:
            if httpd is not None:
                httpd.server_close()
            if service is not None:
                if (args.run_dir / f'resource-stop-{os.getpid()}.json').exists():
                    service.registry.halt('resource_limit', 'resource watchdog terminated owned server')
                service.close()


if __name__ == '__main__':
    main()
