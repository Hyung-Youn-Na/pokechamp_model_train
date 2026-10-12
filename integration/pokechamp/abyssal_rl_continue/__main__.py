"""EX-074 standalone preparation, bounded execution, resume and evidence tools."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "verify", "run", "worker", "status", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("--output", type=Path, default=config.OUTPUT)
        if name == "run":
            p.add_argument("--resume", action="store_true")
    p = sub.add_parser("actor")
    p.add_argument("--attempt", type=Path, required=True)
    p.add_argument("--role", choices=("p1", "p2"), required=True)
    p = sub.add_parser("verify-browser")
    for name in ("source", "export", "receipt", "report"):
        p.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    from .storage import atomic, read

    if args.command == "prepare":
        from .prepare import prepare

        result = prepare(args.output)
    elif args.command == "verify":
        from .verification import verify

        result = verify(args.output)
    elif args.command == "status":
        result = {
            name: read(args.output / name)
            for name in ("progress.json", "supervisor.json", "completed.json")
            if (args.output / name).exists()
        }
    elif args.command == "run":
        from .execution import supervisor

        code = supervisor(args.output, resume=args.resume)
        if code != 0 and read(args.output / "supervisor-exit.json").get("reason") != "budget":
            # Preserve a technical stop for evidence-based recovery inside the
            # same original budget; do not declare the experiment closed.
            return code
        if (
            code == 130
            and read(args.output / "supervisor-exit.json").get("reason") != "budget"
        ):
            return code
        from .finalize import finalize

        result = finalize(args.output)
    elif args.command == "worker":
        from .runner import run_worker

        return run_worker(args.output)
    elif args.command == "actor":
        from ..selfplay.player import worker

        result = asyncio.run(worker(args.attempt, args.role))
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0 if result["status"] == "completed" else 1
    elif args.command == "finalize":
        from .finalize import finalize

        result = finalize(args.output)
    else:
        from .viewer import verify_browser

        result = verify_browser(args.source, args.export, read(args.receipt))
        atomic(args.report, result, immutable=True)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
