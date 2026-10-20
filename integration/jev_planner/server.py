"""Serve a new condition using pinned JEV loaders and a new request journal."""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import signal

from .runtime import PROTOCOL, create_model, resource_roots, validate_resources, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port outside 1024..65535")
    config = json.loads(args.config.read_text())
    from .config import validate_mode
    validate_mode(config, "live")
    spec = validate_resources(config)
    directory = args.directory.resolve()
    if (directory / "server").exists() or (directory / "model-loaded.json").exists():
        raise FileExistsError("executor serving journals cannot be resumed")
    from integration.jev27b.resource import own_gpus
    from integration.jev27b.server import LocalHTTPServer, LocalService

    def terminate(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    service = httpd = model = None
    try:
        ownership = (nullcontext() if spec.get("external_server") else
            own_gpus(directory, profile=spec["runtime_name"], budget_root=directory.parent,
                     extra_roots=resource_roots(config, directory.parent),
                     initialize_cuda=config["executor"]["model"] != "jev35b-nvfp4"))
        with ownership:
            cache = Path(spec["model_dir"]).parent / "cache"
            os.environ.update(TRITON_CACHE_DIR=str(cache / "triton"),
                              TORCHINDUCTOR_CACHE_DIR=str(cache / "inductor"))
            model = create_model(config)
            if config["executor"]["model"] in ("jev35b-nvfp4", "jev-omni", "tacit9b", "tacit9b-vllm"):
                model.directory = directory
            model = model.load()
            write_json(directory / "model-loaded.json", model.metadata())
            service = LocalService(model, directory, model_id=spec["model_id"],
                revision=spec["revision"], protocol=PROTOCOL, validate_before_inference=True)
            try:
                httpd = LocalHTTPServer(("127.0.0.1", args.port), service)
                httpd.serve_forever(poll_interval=0.25)
            finally:
                if httpd is not None:
                    httpd.server_close()
                if (directory / f"resource-stop-{os.getpid()}.json").exists():
                    service.registry.halt("resource_limit", "owned resource watchdog stopped server")
                service.close()
    except BaseException as error:
        write_json(directory / "process-exit.json", dict(type=type(error).__name__,
            detail=str(error), service_loaded=service is not None))
        raise
    finally:
        if model is not None and hasattr(model, "close"):
            model.close()


if __name__ == "__main__":
    main()
