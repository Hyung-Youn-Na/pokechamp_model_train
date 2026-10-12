"""Offline policy equivalence, state cloning, visibility and RNG isolation."""
import copy
import json
import pickle
import random
from pathlib import Path

import numpy as np
import pytest

from integration.pokechamp.battle_adapter import BattleEnvironmentError
from integration.pokechamp.branch_rollouts.policy import Actor
from poke_env.player.baselines import AbyssalPlayer
from poke_env.player.battle_order import BattleOrder
from poke_env.ps_client.account_configuration import AccountConfiguration


@pytest.fixture(autouse=True)
def canonical_working_directory(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[3] / "pokechamp")


def request(*, preview=False, forced=False):
    mons = [
        dict(ident="p1: Spark", details="Pikachu, M", condition="211/211",
             active=not preview, stats={"atk": 146, "def": 116, "spa": 136, "spd": 136, "spe": 216},
             moves=["thunderbolt", "quickattack"], baseAbility="static", item="lightball"),
        dict(ident="p1: Flame", details="Charizard, M", condition="297/297",
             active=False, stats={"atk": 204, "def": 192, "spa": 254, "spd": 206, "spe": 236},
             moves=["flamethrower", "airslash"], baseAbility="blaze", item="heavydutyboots"),
    ]
    result = {"side": {"name": "Alice", "id": "p1", "pokemon": mons}}
    if preview:
        result["teamPreview"] = True
    elif forced:
        result["forceSwitch"] = [True]
        mons[0]["condition"] = "0 fnt"
    else:
        result["active"] = [{"moves": [
            dict(move="Thunderbolt", id="thunderbolt", pp=24, maxpp=24, target="normal", disabled=False),
            dict(move="Quick Attack", id="quickattack", pp=48, maxpp=48, target="normal", disabled=False),
        ], "canTerastallize": "Electric"}]
    return result


def feed_request(actor, req):
    actor.feed(["|request|" + json.dumps(req)])


def fixture_actor(seed=100, *, preview=False):
    actor = Actor("p1", "Alice", seed)
    actor.feed([
        "|init|battle", "|player|p1|Alice|1|", "|player|p2|Bob|2|",
        "|teamsize|p1|2", "|teamsize|p2|2", "|gametype|singles", "|gen|9",
        "|tier|[Gen 9] OU", "|clearpoke", "|poke|p1|Pikachu, M|",
        "|poke|p1|Charizard, M|", "|poke|p2|Squirtle, M|", "|poke|p2|Venusaur, M|",
    ])
    feed_request(actor, request(preview=True))
    if not preview:
        actor.feed([
            "|start", "|switch|p1a: Spark|Pikachu, M|211/211",
            "|switch|p2a: Shell|Squirtle, M|100/100", "|turn|1",
        ])
        feed_request(actor, request())
    return actor


def numpy_state_equal(a, b):
    return a[0] == b[0] and np.array_equal(a[1], b[1]) and a[2:] == b[2:]


def test_preview_matches_canonical_avatar_then_shuffle_rng():
    actor = fixture_actor(745, preview=True)
    host_py, host_np = random.getstate(), np.random.get_state()
    try:
        random.seed(745)
        np.random.seed(745)
        reference = AbyssalPlayer(
            account_configuration=AccountConfiguration("Reference", None),
            battle_format="gen9ou", start_listening=False,
        )
        expected = reference.teampreview(copy.deepcopy(actor.battle)).removeprefix("/")
    finally:
        random.setstate(host_py)
        np.random.set_state(host_np)
    assert actor.choose() == expected


def test_normal_choice_matches_canonical_policy_and_uses_request_slot():
    actor = fixture_actor()
    # Direct canonical call over an independent equivalent observation.
    reference = Actor.restore(actor.snapshot())
    with reference._rng():
        expected_order = reference.player.choose_move(reference.battle)
    assert expected_order.order.id == "thunderbolt"
    assert actor.choose() == "move 1"
    assert actor.choose() == reference._command(expected_order)


def test_snapshot_restores_observer_policy_rng_without_network_objects():
    actor = fixture_actor(984, preview=True)
    snapshot = actor.snapshot()
    restored = Actor.restore(snapshot)
    other = Actor.restore(snapshot)
    assert actor.choose() == restored.choose()
    restored.player.pokemon_move_dict["private"] = {"x": [1]}
    restored.battle.team["p1: Spark"].damage("100/211")
    assert "private" not in other.player.pokemon_move_dict
    assert "private" not in actor.player.pokemon_move_dict
    assert other.battle.team["p1: Spark"].current_hp == 211
    state = pickle.loads(snapshot)
    assert "ps_client" not in state["policy"]
    assert not any("queue" in key or "condition" in key for key in state["policy"])
    assert restored.snapshot()


def test_actor_operations_preserve_host_rng_and_are_order_independent():
    host_py, host_np = random.getstate(), np.random.get_state()
    a, b = fixture_actor(17, preview=True), fixture_actor(42, preview=True)
    a_snap, b_snap = a.snapshot(), b.snapshot()
    first_a, first_b = a.choose(), b.choose()
    b_again, a_again = Actor.restore(b_snap), Actor.restore(a_snap)
    assert b_again.choose() == first_b
    assert a_again.choose() == first_a
    a.reseed(19)
    a.choose()
    assert random.getstate() == host_py
    assert numpy_state_equal(np.random.get_state(), host_np)


def test_reseed_changes_only_future_rng_and_is_repeatable():
    actor = fixture_actor(11, preview=True)
    clone = Actor.restore(actor.snapshot())
    actor.reseed(121)
    clone.reseed(121)
    assert actor.choose() == clone.choose()
    assert actor.request == clone.request


def test_live_actors_do_not_share_mutable_policy_lookup_caches():
    from pokechamp.data_cache import get_cached_move_effect
    a, b = fixture_actor(), fixture_actor(22)
    a.choose()
    b.choose()
    a.player.move_effect["private-test-entry"] = {"x": [1]}
    assert "private-test-entry" not in b.player.move_effect
    assert "private-test-entry" not in get_cached_move_effect()
    a.choose()
    assert a.player.move_effect["private-test-entry"] == {"x": [1]}


def test_forced_switch_and_tera_slot_mapping():
    actor = fixture_actor()
    move = actor.battle.available_moves[1]
    assert actor._command(BattleOrder(move, terastallize=True)) == "move 2 terastallize"
    actor.feed(["|faint|p1a: Spark"])
    feed_request(actor, request(forced=True))
    assert actor.choose() == "switch 2"


def test_wait_and_terminal_are_errors_not_fallback_actions():
    actor = fixture_actor()
    feed_request(actor, {"wait": True})
    with pytest.raises(BattleEnvironmentError, match="waiting"):
        actor.choose()
    feed_request(actor, request())
    actor.feed(["|win|Bob"])
    with pytest.raises(BattleEnvironmentError, match="terminal"):
        actor.choose()


def test_monotonic_rqid_and_visibility_guards():
    actor = fixture_actor()
    assert actor.request["rqid"] == 2
    wrong = request()
    wrong["side"]["id"] = "p2"
    with pytest.raises(BattleEnvironmentError, match="other actor"):
        feed_request(actor, wrong)
    regressed = request()
    regressed["rqid"] = 1
    with pytest.raises(BattleEnvironmentError, match="regressed"):
        feed_request(actor, regressed)
    with pytest.raises(BattleEnvironmentError, match="actor-filtered"):
        actor.feed(["|split|p2"])


def test_player_identity_unknown_protocol_and_missing_request_fail_closed():
    actor = Actor("p1", "Alice", 1)
    with pytest.raises(BattleEnvironmentError, match="current request"):
        actor.choose()
    with pytest.raises(BattleEnvironmentError, match="identity"):
        actor.feed(["|player|p1|SomebodyElse|1|"])
    with pytest.raises(BattleEnvironmentError):
        actor.feed(["|unknown-new-state-event|x"])


def test_canonical_random_fallback_is_preserved_with_both_rngs(monkeypatch):
    actor = fixture_actor(99)
    clone = Actor.restore(actor.snapshot())
    def sampled(player, battle):
        # Exercise both RNGs without changing the underlying fallback algorithm.
        np.random.random()
        return player.choose_random_move(battle)
    monkeypatch.setattr(AbyssalPlayer, "choose_move", sampled)
    assert [actor.choose() for _ in range(20)] == [clone.choose() for _ in range(20)]
    assert actor._python_rng == clone._python_rng
    assert numpy_state_equal(actor._numpy_rng, clone._numpy_rng)
