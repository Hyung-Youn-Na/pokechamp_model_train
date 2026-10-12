"""CPU preparation/verification and explicit, separate experimental execution."""
import argparse
import json
from pathlib import Path

from .config import DEFAULT_OUTPUT, DEFAULT_TEAMS


def main():
    parser = argparse.ArgumentParser(description="고정 공개 상태 자기대국/MCTS; run 계열만 실험 실행")
    parser.add_argument("command", choices=["stopping-prepare", "stopping-run", "stopping-finalize", "first-round-recover-prepare", "first-round-prepare", "first-round-run", "first-round-finalize", "prepare", "day-prepare", "recover-prepare", "verify", "run", "status", "finalize"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--team-root", type=Path, default=DEFAULT_TEAMS)
    parser.add_argument("--parent", type=Path, help="계승/복구 준비에 사용할 보존된 부모 실행 경로")
    args = parser.parse_args()
    if args.command.startswith("stopping-"):
        from .stopping import DEFAULT_OUTPUT as STOP_OUTPUT, PROTOCOL as STOP_PROTOCOL
        directory = STOP_OUTPUT if args.directory == DEFAULT_OUTPUT else args.directory
        if args.command == "stopping-prepare":
            if args.parent is None:
                parser.error("stopping-prepare requires --parent")
            from .stopping_prepare import prepare_stopping
            manifest = prepare_stopping(args.parent, directory)
            result = dict(identity=manifest["identity"], directory=str(directory), status="stopping_prepared_not_run")
        elif args.command == "stopping-run":
            from .stopping_run import run_stopping
            result = run_stopping(directory)
        else:
            from .finalize import finalize
            from .runtime import Clock, own_run
            if not (directory / "clock.json").exists():
                raise RuntimeError("cannot finalize an experiment that has not started")
            with own_run(directory):
                clock = Clock(directory, protocol=STOP_PROTOCOL)
                clock.enter("finalize")
                result = finalize(directory, protocol=STOP_PROTOCOL, check=clock.check)
    elif args.command.startswith("first-round-"):
        from .first_round import DEFAULT_OUTPUT as FIRST_OUTPUT, PROTOCOL as FIRST_PROTOCOL
        from .first_round import prepare_first_round, run_first_round
        directory = FIRST_OUTPUT if args.directory == DEFAULT_OUTPUT else args.directory
        if args.command == "first-round-recover-prepare":
            if args.parent is None:
                parser.error("first-round-recover-prepare requires --parent")
            if args.directory == DEFAULT_OUTPUT:
                directory = FIRST_OUTPUT.with_name(FIRST_OUTPUT.name + "-untimed")
            from .first_round_recovery import prepare_single_retry
            manifest = prepare_single_retry(args.parent, directory)
            result = dict(identity=manifest["identity"], directory=str(directory), status="single_retry_prepared_not_run")
        elif args.command == "first-round-prepare":
            if args.parent is None:
                parser.error("first-round-prepare requires --parent")
            manifest = prepare_first_round(args.parent, directory)
            result = dict(identity=manifest["identity"], directory=str(directory), status="first_round_prepared_not_run")
        elif args.command == "first-round-run":
            result = run_first_round(directory)
        else:
            from .finalize import finalize
            from .runtime import Clock, own_run
            if not (directory / "clock.json").exists():
                raise RuntimeError("cannot finalize an experiment that has not started")
            with own_run(directory):
                clock = Clock(directory, protocol=FIRST_PROTOCOL)
                clock.enter("finalize")
                result = finalize(directory, protocol=FIRST_PROTOCOL, check=clock.check)
    elif args.command == "day-prepare":
        if args.parent is None:
            parser.error("day-prepare requires --parent and a new --directory")
        from .day import prepare_day
        manifest = prepare_day(args.parent, args.directory)
        result = dict(identity=manifest["identity"], directory=str(args.directory), status="day_prepared_not_run")
    elif args.command == "recover-prepare":
        if args.parent is None:
            parser.error("recover-prepare requires --parent and a new --directory")
        from .recovery import prepare_fnt_recovery
        manifest = prepare_fnt_recovery(args.parent, args.directory)
        result = dict(identity=manifest["identity"], directory=str(args.directory), status="recovery_prepared_not_run")
    elif args.command == "prepare":
        from .prepare import prepare
        result = prepare(args.directory, team_root=args.team_root)
        result = dict(identity=result["identity"], directory=str(args.directory), status="prepared_not_run")
    elif args.command == "verify":
        import torch
        from .verification import verify
        torch.set_num_threads(2)
        result = verify(device="cpu")
    elif args.command == "run":
        from .runner import run
        result = run(args.directory)
    elif args.command == "finalize":
        from .finalize import finalize
        from .runtime import Clock, own_run
        if not (args.directory / "clock.json").exists():
            raise RuntimeError("cannot finalize an experiment that has not started")
        with own_run(args.directory):
            clock = Clock(args.directory)
            clock.enter("finalize")
            result = finalize(args.directory, check=clock.check)
    else:
        from .storage import read
        result = {name: read(args.directory / name) for name in
                  ("clock.json", "latest.json", "pilot-gate.json", "selection.json", "completed.json", "incomplete.json")
                  if (args.directory / name).exists()}
        result["stops"] = [read(p) for p in sorted((args.directory / "stops").glob("*.json"))]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
