"""EX081 CLI. All stages preserve the first clock and original experiment."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
from . import config as c, storage as s


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare','diagnose','qualify','run','finalize','status'))
    parser.add_argument('--directory', type=Path, default=c.OUTPUT)
    args = parser.parse_args()
    if args.stage == 'status':
        result = s.read(args.directory / 'status.json') if (args.directory / 'status.json').exists() else {'phase':'not_started'}
        print(json.dumps(result, ensure_ascii=False))
        return
    args.directory.mkdir(parents=True, exist_ok=True)
    def stop(*_):
        raise KeyboardInterrupt('EX081 owner interruption')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with (args.directory / 'controller.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage == 'prepare':
            from .prepare import prepare
            result = prepare(args.directory)
        elif args.stage == 'diagnose':
            from .diagnose import diagnose
            result = diagnose(args.directory)
        else:
            from .control import qualify, run, finalize
            if args.stage == 'qualify':
                _, _, result = qualify(args.directory)
            elif args.stage == 'run':
                result = run(args.directory)
            else:
                result = finalize(args.directory)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.stage == 'run' and (result.get('stopped') or result.get('completed') != 20):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
