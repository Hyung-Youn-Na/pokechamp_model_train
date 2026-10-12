"""EP-055 one-shot local collection using the existing benchmark actor/recorder."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from integration.pokechamp import benchmark, cli
from integration.pokechamp.parallel_server import BattleServer

ROOT = Path(__file__).resolve().parents[3]
EX044 = ROOT / ".pokechamp-data/b2-lead/ex044-cloud/attempts/b04-r3-s0-a1/request.json"


class CursorMessages(list):
    """Preserve upstream lists; observe the actual protocol loop's current row.

    Upstream first builds descriptions by indexing a slice, then parses by
    iterating split_messages[1:]. Only iteration updates this cursor. The trace
    mixin also iterates the complete frame before parsing; the parser loop resets
    it before any decision. No message, RNG call, or parser branch is changed.
    """

    def __init__(self, values, mark, offset=0):
        super().__init__(values)
        self.mark, self.offset = mark, offset

    def __iter__(self):
        for i, value in enumerate(super().__iter__()):
            self.mark(self.offset + i)
            yield value

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(key, slice):
            start, _, step = key.indices(len(self))
            if step != 1:
                raise ValueError("Unsupported upstream message slicing")
            return CursorMessages(value, self.mark, self.offset + start)
        return value


def worker(directory, actor):
    # Existing worker imports this factory lazily; replace only in this process.
    from integration.pokechamp.observability import player as tracing

    original = tracing.make_traced_player_class

    def diagnostic_factory(base):
        parent = original(base)

        class DiagnosticPlayer(parent):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.benchmark_watchdog_seconds = 600

            async def _handle_battle_message(self, messages):
                self.diagnostic_event_seq = self._research_trace_sink._event_seq + 1
                wrapped = CursorMessages(messages, lambda row: setattr(self, "diagnostic_row", row))
                return await super()._handle_battle_message(wrapped)

            async def _handle_battle_request(self, battle, from_teampreview_request=False, maybe_default_order=False):
                if not (battle.in_team_preview and not from_teampreview_request):
                    boundary = dict(
                        actor=actor,
                        decision_seq=self._research_trace_sink._decision_seq + 1,
                        protocol_event_seq=self.diagnostic_event_seq,
                        line_index=self.diagnostic_row,
                        request_id=battle.rqid,
                        turn=battle.turn,
                    )
                    # Synchronous write before action selection; failure is fatal.
                    with (directory / f"{actor}.boundaries.jsonl").open("a") as stream:
                        stream.write(json.dumps(boundary) + "\n")
                return await super()._handle_battle_request(
                    battle, from_teampreview_request=from_teampreview_request,
                    maybe_default_order=maybe_default_order,
                )

        return DiagnosticPlayer

    tracing.make_traced_player_class = diagnostic_factory
    return benchmark.worker(directory, actor)


def run(directory, *, port=8100):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)  # prevents accidental rerun
    source = json.loads(EX044.read_text())
    slot = {key: source["slot"][key] for key in ("teams", "actor_seeds", "battle_seed")}
    slot.update(slot_id="ep055-single", methods=["abyssal", "abyssal"], pair=["abyssal", "abyssal"])
    request = dict(experiment_id="ep055-observation", data_root=str(directory / "data"),
                   attempt_id="abyssal-single", slot=slot, source=cli._research_source_snapshot(),
                   names={"p1": "ep055abyssalp1", "p2": "ep055abyssalp2"}, port=port)
    benchmark.seal_json(directory / "request.json", request)
    processes, logs = [], []
    server = BattleServer(directory, port, slot["battle_seed"])
    started = time.monotonic()
    result = dict(attempted=1, replayed=0, timeout_seconds=600, status="incomplete")
    try:
        server.start()
        for actor in ("p2", "p1"):
            env = cli._child_environment(PYTHONPATH=f"{ROOT}:{ROOT / 'pokechamp'}",
                PYTHONHASHSEED=str(slot["actor_seeds"][int(actor[-1]) - 1]))
            for key in list(env):
                if any(word in key for word in ("API_KEY", "PERMIT_SOCKET", "STUDY_ROOT", "BATCH_DEADLINE")):
                    del env[key]
            env.update({key: "1" for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")})
            log = (directory / f"{actor}.log").open("xb")
            logs.append(log)
            processes.append(subprocess.Popen(
                [sys.executable, "-m", "integration.pokechamp.diagnostics.observation_run", "worker", str(directory), "--actor", actor],
                cwd=ROOT / "pokechamp", env=env, stdout=log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True))
        while any(p.poll() is None for p in processes):
            if time.monotonic() - started >= 600:
                raise TimeoutError("600 second collection limit; no rematch")
            if any(p.poll() not in (None, 0) for p in processes):
                raise RuntimeError("Actor failure; no rematch")
            time.sleep(0.1)
        actors = {actor: json.loads((directory / f"{actor}.result.json").read_text()) for actor in ("p1", "p2")}
        if any(a.get("category") for a in actors.values()):
            raise RuntimeError("Actor reported failure")
        result.update(status="completed", actors=actors)
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        benchmark.signal_cancel(directory, "diagnostic_stop")
    finally:
        for p in processes:
            benchmark.terminate(p)
        for log in logs:
            log.close()
        try:
            server.close()
            result["cleanup"] = "owned processes stopped, port released, worktree removed"
        except Exception as error:
            result["cleanup_error"] = str(error)
        result["duration_seconds"] = time.monotonic() - started
        benchmark.write_json(directory / "result.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("run", "worker"))
    p.add_argument("directory", type=Path)
    p.add_argument("--actor", choices=("p1", "p2"))
    p.add_argument("--port", type=int, default=8100)
    args = p.parse_args()
    return worker(args.directory, args.actor) if args.command == "worker" else run(args.directory, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
