"""python -m integration.pokechamp.summary_diagnostics prepare|run|report."""

import argparse
import json
import sys
from pathlib import Path

from ..constants import POKECHAMP_ROOT
from ..execution import DEFAULT_CONCURRENCY
from .prepare import LEGACY_PROFILE, MAX_PROFILE, THINKING_PROFILE, prepare
from .report import report
from .runner import run


def main():
    sys.path.insert(0, str(POKECHAMP_ROOT))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "run", "report"):
        p = sub.add_parser(command)
        p.add_argument("directory", type=Path)
        if command == "prepare":
            p.add_argument("--concurrency", type=int, choices=range(1, 11), default=DEFAULT_CONCURRENCY)
            p.add_argument(
                "--profile",
                choices=(LEGACY_PROFILE, THINKING_PROFILE, MAX_PROFILE),
                default=LEGACY_PROFILE,
            )
        if command == "run":
            p.add_argument("--fake", action="store_true")
        if command == "report":
            p.add_argument("--review", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.directory, profile=args.profile, concurrency=args.concurrency)
    elif args.command == "run":
        result = run(args.directory, fake={} if args.fake else None)
    else:
        result = report(args.directory, args.review)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
