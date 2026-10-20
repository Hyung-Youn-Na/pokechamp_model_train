import asyncio,json,time
from integration.openai_decisions_battle import battle,study,audit,session as session_module
from integration.openai_decisions_battle.core import BASELINE
from integration.jev27b import battle as old_battle
from integration.pokechamp import jev_battle as j
def test_runner_isolates_illegal_choice_then_halts_on_technical_failure(tmp_path, monkeypatch):
    """No real game: exercise admission/cleanup after each failure classification."""
    monkeypatch.chdir(battle.ROOT / 'pokechamp')
    from integration.pokechamp import cli, parallel_server, benchmark
    from poke_env.player.player import Player  # load dependencies before mocking Popen
    baseline = json.loads((BASELINE/'manifest.json').read_text())
    manifest = dict(baseline, experiment_id="EX-109", source={})
    output = tmp_path / "live"
    monkeypatch.setattr(study, "verify_live_identity", lambda *_args: None)
    monkeypatch.setattr(audit, "audit", lambda *_args, **_kwargs: dict(passed=True, errors=[]))

    class Session:
        def __init__(self, directory, **_kwargs):
            self.directory, self.records = directory, []
            self.calls, self.started, self.monotonic_started = 0, time.time(), time.monotonic()
            self.fake, self.prior_calls = True, 0
            self.failure_event = asyncio.Event()
            self.terminal_error = None

        def record(self, event):
            self.records.append(event)
            with (self.directory / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(event) + "\n")

        def fail(self, error):
            self.terminal_error = error
            self.failure_event.set()

        def remaining(self):
            return 3600

        async def close(self):
            return

        async def wait_decisions(self):
            return

    class Process:
        pid = 1
        returncode = None

        def poll(self):
            return self.returncode

    class Server:
        def __init__(self, *_args):
            self.created = False
            self.process = Process()

        def start(self):
            self.created = True

        def close(self):
            self.created = False
            self.process.returncode = 0

    class Player:
        official = None

        def __init__(self, **_kwargs):
            pass

    admitted = []

    async def play(_player, _role, _names, attempt, **_kwargs):
        admitted.append(json.loads((attempt / "request.json").read_text())["slot"]["slot_id"])
        if len(admitted) == 1:
            raise j.UnusableChoice("illegal model candidate")
        raise RuntimeError("owned peer exited")

    async def close_players(_players):
        return

    monkeypatch.setattr(session_module, "Session", Session)
    monkeypatch.setattr(session_module, "player_class", lambda: Player)
    monkeypatch.setattr(old_battle, "play_owned", play)
    monkeypatch.setattr(parallel_server, "BattleServer", Server)
    monkeypatch.setattr(battle.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(benchmark, "terminate", lambda process: setattr(process, "returncode", 0))
    monkeypatch.setattr(cli, "_close_players", close_players)
    monkeypatch.setattr(study, "final_check", lambda *_: dict(passed=True,errors=[]))
    result = asyncio.run(battle.run(output, manifest=manifest, key="fake", first_request_at=time.time(), fake=True))
    assert admitted == [row["slot_id"] for row in baseline["schedule"][:2]]
    assert result["attempted"] == result["failed"] == 2 and result["unattempted"] == 30
    assert result["outcomes"][0]["failure_scope"] == "battle"
    assert result["outcomes"][1]["failure_scope"] == "collection"
    assert result["actual_losses"] == 0 and result["completed_pairs"] == 0
    assert result["error"]["type"] == "RuntimeError"

