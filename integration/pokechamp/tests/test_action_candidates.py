import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from integration.pokechamp.battle_adapter import (
    BattleEnvironmentError,
    exact_get_pokemon,
    guard_parser,
    identity,
    update_team_from_request,
)
from integration.pokechamp.benchmark_player import (
    ActionCandidate,
    ActionCandidates,
    BenchmarkBackend,
    build_candidates,
)


def mon(species, **kwargs):
    return NS(species=species, active=False, fainted=False, moves={}, **kwargs)


def state():
    active, opposing = mon("tinkaton"), mon("blastoise")
    active.active = opposing.active = True
    switch, unseen, dead = mon("pikachu"), mon("charizard"), mon("gengar")
    dead.fainted = True
    return NS(
        active_pokemon=active,
        opponent_active_pokemon=opposing,
        available_moves=[NS(id="playrough")],
        available_switches=[switch],
        can_tera=True,
        can_dynamax=False,
        force_switch=False,
        opponent_team={"a": opposing, "b": dead},
        _teampreview_opponent_team=[unseen, mon("gengar"), mon("blastoise")],
    )


def test_candidates_share_prompt_validation_and_object_conversion():
    battle = state()
    candidates = build_candidates(battle)
    backend = object.__new__(BenchmarkBackend)
    backend.role, backend.candidates = "self_action", candidates
    for entry in candidates.entries:
        value = entry.record()["action"]
        assert json.dumps(value, separators=(",", ":")) in candidates.instruction()
        assert backend._battle_action_valid(json.dumps(value), battle)
        assert candidates.order(value, lambda p, **_: p) is entry.target
    assert backend._battle_action_valid('{"move":"Play Rough"}', battle)
    assert not backend._battle_action_valid('{"move":"Gigaton Hammer"}', battle)
    assert candidates.failure_reason == "action outside candidates"
    assert not backend._battle_action_valid('{"move":"playrough","reason":"x"}', battle)


def test_opponent_public_unseen_fainted_force_and_inference():
    battle = state()
    battle.force_switch = [True]
    sim = NS(gen=NS(gen=9), get_opponent_current_moves=lambda **_: ["surf", "icebeam"])
    candidates = build_candidates(battle, sim, opponent=True)
    values = [e.record()["action"] for e in candidates.entries]
    assert {"switch": "charizard"} in values
    assert {"move": "surf"} in values and {"move": "icebeam"} in values
    assert {"switch": "gengar"} not in values and {"switch": "blastoise"} not in values
    assert all(
        e.source in ("observed", "inferred", "public_preview")
        for e in candidates.entries
    )
    battle.opponent_active_pokemon.fainted = True
    assert all(e.kind == "switch" for e in build_candidates(battle, sim, True).entries)
    assert all(e.kind == "switch" for e in build_candidates(battle).entries)


def test_name_collision_empty_and_failed_conversion():
    c = ActionCandidates(
        [
            ActionCandidate("switch", n, object(), "public_preview")
            for n in ("mr-mime", "Mr Mime")
        ]
    )
    with pytest.raises(ValueError, match="ambiguous"):
        c.resolve({"switch": "mr mime"})
    with pytest.raises(ValueError, match="outside"):
        ActionCandidates([]).resolve({"move": "surf"})
    with pytest.raises(ValueError, match="converted"):
        build_candidates(state()).order({"move": "playrough"}, lambda *a, **kw: None)


def test_identity_side_and_nickname_preserved():
    assert identity("p1a: Mr-Mime") == ("p1", "p1: Mr-Mime")
    own, opponent = mon("pikachu"), mon("charizard")
    battle = NS(
        _player_role="p1",
        _team={"p1: Same": own},
        _opponent_team={"p2: Same": opponent},
    )
    assert exact_get_pokemon(battle, "p1a: Same") is own
    assert exact_get_pokemon(battle, "p2a: Same") is opponent
    with pytest.raises(BattleEnvironmentError, match="side"):
        exact_get_pokemon(battle, "p2: Same", force_self_team=True)


def test_request_nickname_can_equal_another_species_without_merging():
    def pokemon(species):
        p = mon(species)
        p.update_from_request = lambda r: None
        return p

    pikachu, charizard = pokemon("pikachu"), pokemon("charizard")
    battle = NS(
        _player_role="p1", _team={"p1: Pikachu": pikachu, "p1: Charizard": charizard}
    )
    update_team_from_request(
        battle,
        {
            "pokemon": [
                {"ident": "p1: Charizard", "details": "Pikachu"},
                {"ident": "p1: Pikachu", "details": "Charizard"},
            ]
        },
    )
    assert battle._team == {"p1: Charizard": pikachu, "p1: Pikachu": charizard}


def test_parser_exception_is_actor_local():
    async def fail(_):
        raise ValueError("parser exploded")

    async def ok(_):
        return 7

    first, second = (
        NS(ps_client=NS(_handle_battle_message=fail)),
        NS(ps_client=NS(_handle_battle_message=ok)),
    )
    guard_parser(first)
    guard_parser(second)
    with pytest.raises(BattleEnvironmentError, match="parser exploded"):
        asyncio.run(first.ps_client._handle_battle_message([]))
    assert asyncio.run(second.ps_client._handle_battle_message([])) == 7
    assert first.benchmark_environment_error.category == "environment"
    assert second.benchmark_environment_error is None


def test_operational_gate_requires_all_144_and_actual_overlap():
    from integration.pokechamp.action_study import validation_gate

    rows = []
    for concurrency in (1, 10):
        for i in range(72):
            start = i * 2 if concurrency == 1 else (i // 10) * 2
            rows.append(
                {
                    "valid": True,
                    "concurrency": concurrency,
                    "trace": {
                        "request": {"model": "fixture"},
                        "response": {
                            "http_started_at": start,
                            "http_finished_at": start + 1,
                            "http_elapsed_ms": 1000,
                            "http_status": 200,
                        },
                    },
                }
            )
    assert validation_gate(rows)["passed"]
    rows[0]["valid"] = False
    assert not validation_gate(rows)["passed"]
    rows[0]["valid"] = True
    assert not validation_gate(rows[:-1])["passed"]
    for row in rows[72:]:
        row["trace"]["response"]["http_elapsed_ms"] = 2001
    assert not validation_gate(rows)["passed"]


def test_no_retry_execution_option_preserves_legacy_default():
    from integration.pokechamp.constants import OLLAMA_MODEL
    from integration.pokechamp.execution import validate_execution

    config = {
        "version": 1,
        "battle_concurrency": 10,
        "account_request_limit": 10,
        "model_request_limits": {OLLAMA_MODEL: 10},
        "evidence": {"decision": "D-017"},
        "stop_new_work_at": None,
    }
    assert "retry_transient" not in validate_execution(config)
    assert validate_execution({**config, "retry_transient": 0})["retry_transient"] == 0
    with pytest.raises(ValueError):
        validate_execution({**config, "retry_transient": True})
