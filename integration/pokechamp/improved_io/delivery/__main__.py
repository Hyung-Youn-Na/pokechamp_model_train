"""Explicit offline CLI. Run from the pinned pokechamp working directory."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from . import capture_request, generate, parse_json
from .report import audit, write


def main():
    parser = argparse.ArgumentParser(description="B0–B3 offline prompt generation and census")
    commands = parser.add_subparsers(dest="command", required=True)
    single = commands.add_parser("generate")
    single.add_argument("--input", type=Path, required=True)
    single.add_argument("--candidate", choices=("B0", "B1", "B2", "B3"), required=True)
    single.add_argument("--battle-format", choices=("gen9ou",), required=True)
    single.add_argument("--output", type=Path, required=True)
    census = commands.add_parser("audit-ex037")
    census.add_argument("--bundles", type=Path, required=True)
    census.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "audit-ex037":
        result = audit(args.bundles.resolve(), args.output.resolve())
        print(result["counts"])
        return
    content = args.input.read_bytes()
    full = parse_json(content.decode("utf-8"))
    origin = dict(
        input_path=str(args.input.resolve()), input_file_sha256=hashlib.sha256(content).hexdigest()
    )
    delivery = generate(full, args.candidate, battle_format=args.battle_format, origin=origin)
    captured = capture_request(full, delivery, battle_format=args.battle_format, origin=origin)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "system.txt").write_text(delivery.system_prompt)
    (args.output / "user.json").write_text(delivery.user_json)
    write(args.output / "source-link.json", parse_json(delivery.source_link_json))
    write(args.output / "captured-request.json", captured)
    print(args.output)


if __name__ == "__main__":
    main()
