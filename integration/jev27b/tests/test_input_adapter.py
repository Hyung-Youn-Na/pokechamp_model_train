"""The local player sends the explicitly selected projection without changing actions."""
import asyncio
from types import SimpleNamespace

import pytest

from integration.jev27b import battle
from integration.jev27b.tests.test_battle import player_fixture, saved  # noqa: F401


@pytest.mark.parametrize("mode,expected_calls", [("normal", 1), ("single", 0)])
def test_explicit_input_adapter_reaches_request_and_audit(
        saved, tmp_path, monkeypatch, mode, expected_calls):  # noqa: F811
    player, game, sent, records, evaluations = player_fixture(
        saved, tmp_path, monkeypatch, mode=mode)
    generated = []
    original = battle.jev_v4.generate

    async def generate(*args, **kwargs):
        payload, commands, audit, elapsed = await original(*args, **kwargs)
        payload["state"]["version"] = "jev-choice-v6"
        generated.append((args, kwargs))
        return payload, commands, audit, elapsed

    adapter = SimpleNamespace(generate=generate,
        save_audit=lambda *_args: {"path": "input-audits/v6.json.gz"})
    player.__class__ = battle.player_class(input_adapter=adapter)
    asyncio.run(player._handle_battle_request(game))
    assert len(generated) == 1
    observed = next(row for row in records if row["type"] == "input")
    selected = next(row for row in records if row["type"] == "selection")
    assert observed["payload"]["state"]["version"] == "jev-choice-v6"
    assert observed["input_audit"]["path"] == "input-audits/v6.json.gz"
    assert len(evaluations) == expected_calls
    assert selected["command"] == observed["commands"][selected["choice"]] == sent[0][0]
    assert selected["automatic"] is (expected_calls == 0)
