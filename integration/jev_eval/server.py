"""One loaded model process per new experiment; reuse the durable request journal."""
import argparse
import os
import signal

from integration.jev27b import server as shared
from .config import EXPERIMENTS, PROTOCOL, experiment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', required=True, choices=EXPERIMENTS)
    args = parser.parse_args(argv)
    cfg = experiment(args.experiment)
    from .model import create_model
    from .resource import own_gpus
    from .failures import error_record
    from .storage import write

    def terminate(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    directory = cfg.run / 'serving'
    service = httpd = None
    try:
        with own_gpus(directory, config=cfg):
            try:
                model = create_model(cfg).load()
                write(directory / 'model-loaded.json', model.metadata())
                service = shared.LocalService(model, directory, model_id=cfg.model_id,
                    revision=cfg.revision, protocol=PROTOCOL, validate_before_inference=True)
                httpd = shared.LocalHTTPServer(('127.0.0.1', cfg.server_port), service)
                httpd.serve_forever(poll_interval=0.25)
            finally:
                if httpd is not None:
                    httpd.server_close()
                if service is not None:
                    if (directory / f'resource-stop-{os.getpid()}.json').exists():
                        service.registry.halt('resource_limit', 'resource watchdog terminated owned server')
                    service.close()
    except BaseException as error:
        if isinstance(error, SystemExit) and error.code == 128 + signal.SIGTERM and service is not None:
            write(directory / 'process-exit.json', dict(signal='SIGTERM', service_loaded=True))
        else:
            write(directory / 'process-failure.json', error_record(error))
        raise


if __name__ == '__main__':
    main()
