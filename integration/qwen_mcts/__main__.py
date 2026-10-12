"""EX-080 CLI. `prepare` and `verify` are CPU only; `run` starts the GPU2/GPU3 servers (D-127)."""
import argparse
import json
import os
import sys

from .config import DEFAULT_OUTPUT


def main(argv=None):
    parser = argparse.ArgumentParser(prog="qwen-mcts")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "verify", "run"):
        command = sub.add_parser(name)
        command.add_argument("--directory", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ.setdefault("TORCHINDUCTOR_COMPILE_THREADS", "1")
    if args.command == "prepare":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        from .prepare import prepare
        print(json.dumps(dict(identity=prepare(args.directory)["identity"])))
    elif args.command == "verify":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        from .prepare import verify
        print(json.dumps(dict(identity=verify(args.directory)["identity"])))
    else:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""   # the controller never touches a GPU; servers bind their own
        from .run import Controller
        print(json.dumps(Controller(args.directory).execute(), default=str))


if __name__ == "__main__":
    sys.exit(main())
