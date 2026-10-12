import random
from types import SimpleNamespace as NS

import pytest

from integration.pokechamp.benchmark_player import BenchmarkBackend, instrument_io
from integration.pokechamp.cloud import CloudRequestError, _extract_upstream


def pinned():
    # Import has data paths relative to the pinned project.
    import poke_env  # noqa: F401

    from pokechamp.llm_player import LLMPlayer

    return LLMPlayer


class Harness:
    def __init__(self, outputs):
        self.backend = "fixture"
        self.temperature = 0.0
        self.outputs = iter(outputs)
        self.calls = []
        self.errors = []
        self.stages = []
        self.attempts = 0
        self.gen = NS(gen=9)

    def get_LLM_action(self, **kw):
        self.calls.append(kw)
        return next(self.outputs)

    def create_order(self, obj, **kw):
        return (getattr(obj, "id", getattr(obj, "species", None)), kw)

    def choose_max_damage_move(self, battle):
        return pinned().choose_max_damage_move(self, battle)

    def choose_random_move(self, battle):
        if battle.available_switches:
            return self.create_order(random.choice(battle.available_switches))
        return ("default", {})

    def _upstream_attempt(self):
        self.attempts += 1

    def _upstream_io_failure(self, cause):
        self.errors.append(cause)

    def _upstream_stage(self, stage):
        self.stages.append(stage)


def battle(moves=True):
    return NS(
        available_moves=[NS(id="splash", base_power=0), NS(id="protect", base_power=0)]
        if moves
        else [],
        available_switches=[NS(species="pikachu"), NS(species="charizard")],
        opponent_active_pokemon=NS(moves={"surf": NS(id="surf")}),
        opponent_team={"a": NS(species="gengar", active=False)},
    )


@pytest.mark.parametrize(
    "outputs,retries,opponent,moves",
    [
        (['{"move":"splash","thought":"accepted upstream"}'], 10, False, True),
        (["bad", '{"move":"splash"}'], 10, False, True),
        (['{"move":"missing"}'] * 10, 10, False, True),
        (["bad"] * 2, 2, True, True),
        (['{"move":"surf"}'], 2, True, True),
        (['{"switch":"gengar"}'], 2, True, True),
        (['{"switch":"pikachu"}'], 10, False, False),
        (["bad"] * 10, 10, False, False),
    ],
)
def test_pinned_io_equivalence(outputs, retries, opponent, moves):
    base = pinned()
    first, second = Harness(outputs), Harness(outputs)
    b = battle(moves)
    args = (retries, "SYSTEM", "STATE", "COT", "IO", "ACTIONS", b, NS())
    random.seed(987)
    result = base.io(first, *args, dont_verify=opponent)
    rng = random.getstate()
    random.seed(987)
    actual = instrument_io(base)(second, *args, dont_verify=opponent)
    assert actual == result
    assert random.getstate() == rng
    assert first.calls == second.calls
    assert second.attempts == len(first.calls)
    assert (
        first.calls[0]["user_prompt"]
        == "STATEACTIONSIOIn fewer than 3 sentences, let's think step by step:"
    )
    if outputs[-1] == "bad" or "missing" in outputs[-1]:
        assert second.stages == ["io_exhausted"]


@pytest.mark.parametrize(
    "raw",
    [
        'prefix {"move":"surf"} suffix',
        '{ "move": "surf" }',
        "bad",
        '{"x":{"move":"surf"}}',
        '"move":"surf"}',
    ],
)
def test_pinned_ollama_extraction(raw):
    from pokechamp.ollama_player import OllamaPlayer

    upstream = object.__new__(OllamaPlayer)
    upstream.model = "fixture"
    upstream.temperature = 0.7
    upstream.max_tokens = 8192
    upstream.context_window = 8192
    upstream.client = NS(chat=lambda **kw: {"message": {"content": raw}})
    result = upstream.get_LLM_action("S", "U", "fixture")[0]
    assert _extract_upstream(raw) == result


def backend(raw=None, error=None):
    calls = []

    def chat(**kw):
        calls.append(kw)
        if error:
            raise error
        return {"model": "glm-5.3-flash", "message": {"content": raw}}

    b = BenchmarkBackend(
        environ={"OLLAMA_API_KEY": "fixture"}, client_factory=lambda **_: NS(chat=chat)
    )
    b.action_policy = "upstream"
    return b, calls


def test_output_nonterminal_and_original_suffix_and_provider_terminal():
    b, calls = backend("bad")
    assert b.get_LLM_action("S", "U", "glm-5.3-flash", battle=NS(turn=1))[0] == "bad"
    assert b.terminal_error is None and not b.failure_event.is_set()
    assert calls[0]["messages"][1]["content"] == 'U\n{"'
    assert calls[0]["format"] == "json"
    assert calls[0]["options"]["num_predict"] == 131072
    b.get_LLM_action("S", "U", "glm-5.3-flash", battle=NS(turn=1))
    assert len(calls) == 2
    b, calls = backend(error=TimeoutError())
    with pytest.raises(CloudRequestError, match="timeout"):
        b.get_LLM_action("S", "U", "glm-5.3-flash")
    with pytest.raises(CloudRequestError):
        b.get_LLM_action("S", "U", "glm-5.3-flash")
    assert len(calls) == 1 and b.failure_event.is_set()


def benchmark_harness():
    from integration.pokechamp.benchmark_player import make_benchmark_llm_class

    cls = make_benchmark_llm_class(pinned())
    h = object.__new__(cls)
    h.llm = NS(action_policy="upstream", terminal_error=None, io_context=None)
    h.diagnostics = []
    h._decision_provenance = []
    h._fallback_active = False
    h._order_origins = {}
    h._order_refs = []
    h.backend = "fixture"
    h.temperature = 0
    h.K = 2
    return h


@pytest.mark.parametrize("damage_fails", [False, True])
def test_minimax_exception_preserves_fallback_action_and_rng(monkeypatch, damage_fails):
    import random

    from integration.pokechamp.benchmark_player import instrument_minimax

    base = pinned()
    import pokechamp.llm_player as module

    def broken_root(_):
        raise ValueError("fixture root failure")

    monkeypatch.setattr(
        module,
        "get_minimax_optimizer",
        lambda: NS(create_optimized_root=broken_root, cleanup_tree=lambda _: None),
    )
    damage = object()

    def dmg(self, b):
        if damage_fails:
            raise ValueError("fixture calculator failure")
        return damage, 1

    monkeypatch.setattr(base, "dmg_calc_move", dmg)
    h = benchmark_harness()
    h.create_order = lambda obj, **kw: obj
    b = battle()
    random.seed(10)
    original = base.tree_search_optimized(h, 10, b)
    expected_rng = random.getstate()
    random.seed(10)
    actual = instrument_minimax(base)(h, 10, b)
    assert actual is original
    assert random.getstate() == expected_rng
    assert "minimax_exception" in [d.get("stage") for d in h.diagnostics]
    assert h._order_origins[id(actual)].startswith("fallback_")
    if damage_fails:
        assert "damage_calculator_failed" in [d.get("stage") for d in h.diagnostics]


def test_provider_failure_escapes_original_io_catch_without_retry():
    h = benchmark_harness()
    h._io_serial = 0
    h._call_role = "self_action"
    calls = []

    def failed(**kw):
        calls.append(kw)
        h.llm.terminal_error = CloudRequestError("provider", "fixture")
        raise h.llm.terminal_error

    h.get_LLM_action = failed
    with pytest.raises(CloudRequestError):
        h.io(10, "S", "U", "C", "I", "A", battle(), NS())
    assert len(calls) == 1
    assert not any(d["kind"] == "fallback_stage" for d in h.diagnostics)


def test_nested_search_events_are_not_sent_actions_and_failed_games_preserved(tmp_path):
    import json

    from integration.pokechamp.fallback_metrics import fallback_metrics

    events = [
        {
            "event_type": "decision_result",
            "decision_seq": 1,
            "validation": {"action_origin": "upstream_action"},
        },
        {
            "event_type": "wire_action",
            "decision_seq": 1,
            "send_status": "sent",
            "action": "/choose move 1",
        },
        {
            "event_type": "decision_result",
            "decision_seq": 2,
            "validation": {"action_origin": "fallback_damage_calculator"},
        },
        {
            "event_type": "wire_action",
            "decision_seq": 2,
            "send_status": "sent",
            "action": "/choose move 2",
        },
        {
            "event_type": "wire_action",
            "decision_seq": 2,
            "send_status": "sent",
            "action": "/choose move 2",
        },
        {
            "event_type": "decision_result",
            "decision_seq": 3,
            "validation": {"action_origin": "fallback_base_power"},
        },
        {
            "event_type": "wire_action",
            "decision_seq": 3,
            "send_status": "failed",
            "action": "/choose move 2",
        },
    ]
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    actor = {
        "bundle": str(tmp_path),
        "diagnostics": [
            {
                "kind": "fallback_stage",
                "stage": s,
                "io_context": {"role": "opponent_action"},
            }
            for s in (
                "io_exhausted",
                "base_power",
                "minimax_exception",
                "damage_calculator",
            )
        ],
    }
    attempts = [
        {
            "eligible": False,
            "slot": {"methods": ["minimax", "abyssal"]},
            "actors": {"p1": actor},
        }
    ]
    result = fallback_metrics(attempts)
    r = result["all_attempts"]["minimax"]
    assert r["sent_decisions"] == 2 and r["sent_fallback_decisions"] == 1
    assert (
        r["games_with_sent_fallback"] == 1 and sum(r["fallback_stages"].values()) == 4
    )
    assert result["eligible_completed"]["minimax"]["actor_games"] == 0


@pytest.mark.parametrize("switches", [False, True])
def test_actual_random_and_default_rng_equivalence(switches):
    from logging import getLogger

    h = benchmark_harness()
    from poke_env.environment.battle import Battle
    from poke_env.environment.pokemon import Pokemon

    b = Battle("fixture", "fixture", getLogger("fixture"), 9)
    if switches:
        b._team = {
            "p1: Pikachu": Pokemon(gen=9, species="pikachu"),
            "p1: Charizard": Pokemon(gen=9, species="charizard"),
        }
        b._available_switches = list(b._team.values())
    random.seed(71)
    expected = pinned().choose_max_damage_move(h, b)
    rng = random.getstate()
    h._fallback_active = True
    random.seed(71)
    actual = h.choose_max_damage_move(b)
    assert expected.message == actual.message and random.getstate() == rng
    stages = [d.get("stage") for d in h.diagnostics]
    assert "random" in stages
    assert ("default_order" in stages) == (not switches)
