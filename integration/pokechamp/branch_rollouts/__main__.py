from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import DEFAULT_OUTPUT, ROOT, prepare


def main():
    parser = argparse.ArgumentParser(description="EX-060 sealed battle branch dataset")
    parser.add_argument("stage", choices=("prepare", "reconstruct", "validate", "collect", "report", "finalize"))
    parser.add_argument("--directory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--viewer-directory", type=Path, default=ROOT / "exports/battle_viewers/ex060")
    args = parser.parse_args()
    if args.stage == "prepare":
        result = prepare(args.directory)
    elif args.stage == "reconstruct":
        from .runner import reconstruct
        result = reconstruct(args.directory)
    elif args.stage == "collect":
        from .runner import collect
        result = collect(args.directory)
    elif args.stage == "validate":
        from .validate import validate
        result = validate(args.directory)
    elif args.stage == "finalize":
        from .audit import finalize
        result = finalize(args.directory, viewer_directory=args.viewer_directory)
    else:
        from .report import export_report
        result = export_report(args.directory, viewer_directory=args.viewer_directory)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
