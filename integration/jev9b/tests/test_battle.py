"""CPU saved-input, transport-ledger, no-send, denominator and viewer checks."""
from __future__ import annotations

import asyncio
import copy
import json
import threading
from types import SimpleNamespace

import httpx
import pytest

from integration.jev9b import audit, battle, client, study
IDENTITY = "9b-test-serving-identity"
from integration.pokechamp import jev_battle as j, jev_v4
from integration.pokechamp.observation.build import DEFAULT_BUILD

SAMPLES = j.ROOT / "project_context/exec-plans/evidence/ep093/certainty-v1"


@pytest.fixture
def saved():
    source = SAMPLES / "turn-sample-01"
    body = json.loads((source / "after-detailed.json").read_text())
    body["state"]["version"] = "jev-choice-v4"
    commands = json.loads((source / "commands.json").read_text())
    return body, commands


def player_fixture(saved, tmp_path, monkeypatch, *, mode="normal"):
    payload, commands = copy.deepcopy(saved)
    if mode == "single":
        first = next(iter(commands))
        commands = {first: commands[first]}
        payload["questions"]["action"]["criteria"] = {
            first: payload["questions"]["action"]["criteria"][first]}
    player = object.__new__(battle.player_class())
    actor = payload["state"]["actor"]
    rqid = payload["state"]["request_id"]
    player.request = dict(side=dict(id=actor), rqid=rqid)
    player.latest_rqid = rqid
    player.expected_actor = actor
    player.prefix, player.boundary, player.submitted_team = [], {}, ""
    player.official = SimpleNamespace(snapshot=lambda *_args, **_kwargs: {}, identity={})
    sent, records, evaluations = [], [], []

    async def send(*args):
        sent.append(args)

    async def evaluate(body, *, decision):
        evaluations.append((body, decision))
        if mode == "stale":
            player.latest_rqid = rqid + 1
        elif mode == "cancelled":
            player.session.failure_event.set()
        elif mode == "timeout":
            raise client.LocalRequestError("timeout", retryable=True)
        choice = "illegal" if mode == "illegal" else next(iter(commands))
        return dict(model=battle.MODEL, answers=dict(action=dict(type="choice", choice=choice,
            probabilities={key: 0.2 for key in commands}, confidence=0.1)),
            usage=dict(input_tokens=123, output_tokens=0))

    async def generate(*_args, **_kwargs):
        return payload, commands, {}, 0

    player.ps_client = SimpleNamespace(username="fixture", send_message=send)
    player.session = SimpleNamespace(directory=tmp_path, records=records, dex={},
        effect_reference_identity={}, initial_pp_policy=None, failure_event=asyncio.Event(),
        record=records.append, evaluate=evaluate, begin_decision=lambda: None,
        end_decision=lambda: None)
    monkeypatch.setattr(jev_v4, "generate", generate)
    monkeypatch.setattr(jev_v4, "save_audit", lambda *_args: {})
    current = dict(commands)
    if mode == "changed":
        current.pop(next(iter(current)))
    monkeypatch.setattr(j, "make_input", lambda *_args, **_kwargs: ({}, current))
    return player, SimpleNamespace(in_team_preview=False, battle_tag="fixture"), sent, records, evaluations


@pytest.mark.parametrize("mode", ["stale", "changed", "cancelled", "timeout", "illegal"])
def test_bad_or_stale_decisions_never_reach_wire(saved, tmp_path, monkeypatch, mode):
    player, game, sent, records, _ = player_fixture(saved, tmp_path, monkeypatch, mode=mode)
    with pytest.raises((ValueError, client.LocalRequestError)):
        asyncio.run(player._handle_battle_request(game))
    assert not sent
    assert not any(record["type"] in ("selection", "wire") for record in records)


@pytest.mark.parametrize("mode,expected_calls", [("normal", 1), ("single", 0)])
def test_legal_choice_and_single_candidate(saved, tmp_path, monkeypatch, mode, expected_calls):
    player, game, sent, records, evaluations = player_fixture(saved, tmp_path, monkeypatch, mode=mode)
    asyncio.run(player._handle_battle_request(game))
    assert len(evaluations) == expected_calls and len(sent) == 1
    selection = next(record for record in records if record["type"] == "selection")
    assert selection["automatic"] is (expected_calls == 0)
    assert sent[0][0] == selection["command"]
    assert selection["revalidated_request_id"] == selection["latest_request_id"]


def test_no_existing_or_alternate_run_can_be_resumed(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="fixed"):
        asyncio.run(battle.run(tmp_path / "different", expected_identity=IDENTITY, gate_receipt={}))
    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "preserve"
    sentinel.write_text("original")
    monkeypatch.setattr(study, "LIVE", target)
    with pytest.raises(FileExistsError, match="cannot resume"):
        asyncio.run(battle.run(target, expected_identity=IDENTITY, gate_receipt={}))
    assert sentinel.read_text() == "original"


@pytest.mark.parametrize("cleanup_error", [False, True])
def test_runner_isolates_illegal_choice_then_halts_on_technical_failure(tmp_path, monkeypatch, cleanup_error):
    """No real game: exercise admission/cleanup after each failure classification."""
    monkeypatch.chdir(battle.ROOT / 'pokechamp')
    from integration.pokechamp import cli, parallel_server, benchmark
    baseline, _ = study.load_baseline()
    manifest = dict(baseline, experiment_id="EX-085", source={})
    output = tmp_path / "live"
    monkeypatch.setattr(study, "LIVE", output)
    monkeypatch.setattr(study, "prepare_manifest", lambda *_args, **_kwargs: manifest)
    monkeypatch.setattr(study, "verify_live_identity", lambda *_args: None)
    monkeypatch.setattr(study, "snapshot_sources", lambda *_args: None)
    monkeypatch.setattr(audit, "audit", lambda *_args, **_kwargs: dict(passed=True, errors=[]))
    monkeypatch.setattr(audit, "final_check", lambda *_args, **_kwargs: dict(passed=True, errors=[]))

    class Session:
        def __init__(self, directory, **_kwargs):
            self.directory, self.records = directory, []
            self.calls, self.started, self.monotonic_started = 0, None, None
            self.failure_event = asyncio.Event()
            self.terminal_error = None

        def record(self, event):
            self.records.append(event)
            with (self.directory / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(event) + "\n")

        def fail(self, error):
            self.terminal_error = error
            self.failure_event.set()

        async def health(self):
            return {}

        async def close(self):
            if cleanup_error:
                raise RuntimeError("fixture client close failure")
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

    monkeypatch.setattr(battle, "Session", Session)
    monkeypatch.setattr(battle, "player_class", lambda: Player)
    monkeypatch.setattr(battle, "play_owned", play)
    monkeypatch.setattr(parallel_server, "BattleServer", Server)
    monkeypatch.setattr(battle.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(benchmark, "terminate", lambda process: setattr(process, "returncode", 0))
    monkeypatch.setattr(cli, "_close_players", close_players)
    result = asyncio.run(battle.run(output, expected_identity=IDENTITY, gate_receipt={}))
    assert admitted == [row["slot_id"] for row in baseline["schedule"][:2]]
    assert result["attempted"] == result["failed"] == 2 and result["unattempted"] == 30
    assert result["outcomes"][0]["failure_scope"] == "battle"
    assert result["outcomes"][1]["failure_scope"] == "collection"
    assert result["actual_losses"] == 0 and result["completed_pairs"] == 0
    assert result["error"]["type"] == "RuntimeError"
    if cleanup_error:
        events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
        assert any(e["type"] == "cleanup_failure" for e in events)


