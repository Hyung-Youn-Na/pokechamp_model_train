"""EX-067 정책의 관측 경계·동결 규칙·Tera 투영 검증."""
import copy
import json
import pickle
import random
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from poke_env.data import GenData
from poke_env.environment.move import Move
from poke_env.environment.pokemon_type import PokemonType
from poke_env.player.baselines import AbyssalPlayer
from poke_env.player.battle_order import BattleOrder
from integration.pokechamp.abyssal_tera import (
    AbyssalTeraPlayer, Attack, Context, DEFAULT_CONFIG, POLICY_CONFIG_HASH, POLICY_ID,
    effective_stat, estimate_damage, policy_config_hash, project_mon, stab_multiplier,
    type_multiplier,
)


@pytest.fixture(autouse=True)
def canonical_cwd(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[3] / "pokechamp")


def mon(species, *, hp=1, moves=(), item="", ability="", tera=None, stats=None, boosts=None):
    dex = GenData.from_gen(9).pokedex[species]
    base = dex["baseStats"]
    projected = {k: 2 * v + 31 + 21 + (110 if k == "hp" else 5) for k, v in base.items()}
    if stats:
        projected.update(stats)
    types = [PokemonType.from_name(t) for t in dex["types"]]
    return SimpleNamespace(species=species, level=100, base_stats=base, stats=projected,
        max_hp=projected["hp"], current_hp_fraction=hp, current_hp=projected["hp"] * hp,
        _type_1=types[0], _type_2=types[1] if len(types) == 2 else None,
        _terastallized_type=PokemonType.from_name(tera) if tera else None, terastallized=bool(tera),
        ability=ability, item=item, status=None, effects={}, weight=dex["weightkg"],
        boosts=dict.fromkeys(("atk", "def", "spa", "spd", "spe", "accuracy", "evasion"), 0) | (boosts or {}),
        moves={m: Move(m, gen=9) for m in moves}, fainted=hp == 0)


def battle(own=None, opponent=None, moves=("earthquake", "stealthrock"), tera="Steel", switches=()):
    own = own or mon("garchomp", hp=.8)
    opponent = opponent or mon("clefable", moves=("moonblast",))
    return SimpleNamespace(active_pokemon=own, opponent_active_pokemon=opponent,
        available_moves=[Move(m, gen=9) for m in moves], available_switches=list(switches),
        team={"p1: Own": own} | {f"p1: Bench{i}": m for i, m in enumerate(switches)},
        opponent_team={"p2: Other": opponent}, can_tera=PokemonType.from_name(tera) if tera else None,
        force_switch=False, turn=7, weather={}, fields={}, side_conditions={}, opponent_side_conditions={})


def policy(monkeypatch, baseline_id="stealthrock"):
    player = object.__new__(AbyssalTeraPlayer)
    player.policy_config = DEFAULT_CONFIG.as_dict()
    player.policy_config_hash = POLICY_CONFIG_HASH
    player._tera_public_moves = {}
    player._tera_non_slot_moves = {}
    player._tera_transformed = set()
    player.last_policy_audit = None
    calls = []

    def choose(_self, state):
        calls.append(state)
        return BattleOrder(Move(baseline_id, gen=9))

    monkeypatch.setattr(AbyssalPlayer, "choose_move", choose)
    return player, calls


def damage(move, own, foe, *, context=Context(), tera=None):
    return estimate_damage(Move(move, gen=9), project_mon(own, own=True, tera_type=tera),
                           project_mon(foe, own=False), context)


def test_frozen_configuration_and_stable_hash():
    assert len(policy_config_hash()) == 64
    assert policy_config_hash(DEFAULT_CONFIG.as_dict()) == POLICY_CONFIG_HASH
    altered = DEFAULT_CONFIG.as_dict() | {"finish_accuracy": .85}
    with pytest.raises(ValueError, match="frozen"):
        policy_config_hash(altered)
    with pytest.raises(Exception):
        DEFAULT_CONFIG.finish_accuracy = .85


def test_original_stab_and_changed_defense_do_not_use_pinned_type_methods():
    source = mon("garchomp", tera="Steel")
    source.types = (PokemonType.STEEL, PokemonType.DRAGON)  # pinned bug
    source.damage_multiplier = lambda _: pytest.fail("pinned multiplier must not be used")
    value = project_mon(source, own=True)
    assert value.original_types == ("dragon", "ground")
    assert value.defensive_types == ("steel",)
    assert type_multiplier("fairy", value.defensive_types) == .5
    assert stab_multiplier(value, "dragon") == 1.5
    assert stab_multiplier(value, "ground") == 1.5
    assert stab_multiplier(value, "steel") == 1.5
    same = project_mon(mon("garchomp"), own=True, tera_type="Ground")
    assert stab_multiplier(same, "ground") == 2
    assert stab_multiplier(same, "dragon") == 1.5


def test_tera_blast_selects_type_and_boosted_offensive_category():
    own = mon("dragonite", stats={"atk": 350, "spa": 200})
    foe = mon("scizor")
    before = damage("terablast", own, foe)
    after = damage("terablast", own, foe, tera="Fire")
    assert (before.type, before.category) == ("normal", "special")
    assert (after.type, after.category, after.offensive_stat) == ("fire", "physical", "atk")
    assert after.damage > 4 * before.damage
    own.boosts["spa"] = 3
    assert damage("terablast", own, foe, tera="Fire").category == "special"
    own.boosts["spa"] = 0
    own.ability = "hustle"
    assert damage("terablast", own, foe, tera="Fire").accuracy == .8


def test_body_press_uses_defense_and_physical_burn():
    own, foe = mon("corviknight"), mon("blissey")
    first = damage("bodypress", own, foe)
    own.stats["atk"] *= 4
    assert damage("bodypress", own, foe).damage == first.damage
    own.boosts["def"] = 2
    assert damage("bodypress", own, foe).damage > 1.9 * first.damage
    own.status = "brn"
    burned = damage("bodypress", own, foe)
    own.status = None
    assert burned.damage == pytest.approx(damage("bodypress", own, foe).damage / 2)


def test_body_press_uses_modify_attack_not_defense_item_ability_or_weather():
    own, foe = mon("avalugg"), mon("blissey")
    basic = damage("bodypress", own, foe).damage
    own.ability = "furcoat"
    assert damage("bodypress", own, foe).damage == basic
    assert damage("bodypress", own, foe, context=Context(weather="snowscape")).damage == basic
    own.ability = ""
    own.item = "choiceband"
    assert damage("bodypress", own, foe).damage > 1.4 * basic
    own = mon("chansey", item="eviolite")
    eviolite = damage("bodypress", own, foe).damage
    own.item = ""
    assert damage("bodypress", own, foe).damage == eviolite


def test_weather_ball_heavy_slam_and_fixed_damage_are_distinct():
    own, foe = mon("heatran"), mon("clefable")
    normal = damage("weatherball", own, foe)
    sun = damage("weatherball", own, foe, context=Context(weather="sunnyday"))
    assert normal.type == "normal" and sun.type == "fire"
    assert sun.damage > normal.damage * 4
    heavy = damage("heavyslam", mon("celesteela"), mon("joltik"))
    light = damage("heavyslam", mon("joltik"), mon("celesteela"))
    assert heavy.damage > light.damage
    own = mon("blissey")
    neutral = damage("seismictoss", own, foe)
    assert neutral.damage == pytest.approx(100 / project_mon(foe, own=False).max_hp)
    assert damage("seismictoss", own, foe, tera="Fighting").damage == neutral.damage
    assert damage("seismictoss", own, mon("dragapult")).damage == 0
    assert damage("ruination", own, mon("clefable", hp=.4)).damage == .2


@pytest.mark.parametrize("move,ability", [
    ("thunderbolt", "voltabsorb"), ("surf", "waterabsorb"),
    ("flamethrower", "flashfire"), ("energyball", "sapsipper"),
    ("earthquake", "levitate"), ("shadowball", "bulletproof"),
])
def test_public_immunities_and_mold_breaker(move, ability):
    own, foe = mon("mew"), mon("mew", ability=ability)
    assert damage(move, own, foe).damage == 0
    own.ability = "moldbreaker"
    assert damage(move, own, foe).damage > 0


def test_ogerpon_new_tera_changes_ability_and_boost_once():
    own = mon("ogerponhearthflame", ability="moldbreaker", item="hearthflamemask")
    foe = mon("heatran", ability="flashfire")
    before = project_mon(own, own=True)
    after = project_mon(own, own=True, tera_type="Fire")
    assert before.ability == "moldbreaker"
    assert after.ability == "embodyaspecthearthflame" and after.boosts["atk"] == 1
    assert damage("ivycudgel", own, foe).damage > 0
    assert damage("ivycudgel", own, foe, tera="Fire").damage == 0
    already = mon("ogerponhearthflametera", tera="Fire", ability="embodyaspecthearthflame", boosts={"atk": 1})
    assert project_mon(already, own=True).boosts["atk"] == 1
    water = mon("ogerponwellspring", ability="waterabsorb")
    normal = project_mon(water, own=True)
    transformed = project_mon(water, own=True, tera_type="Water")
    attacker = project_mon(mon("manaphy"), own=False)
    assert transformed.boosts["spd"] == 1 and transformed.ability == "embodyaspectwellspring"
    assert estimate_damage(Move("surf", gen=9), attacker, normal, Context()).damage == 0
    assert estimate_damage(Move("surf", gen=9), attacker, transformed, Context()).damage > 0


@pytest.mark.parametrize("ability,move", [("vesselofruin", "surf"), ("tabletsofruin", "bodypress")])
def test_public_ruin_offense_scalars_and_holder_exemptions(ability, move):
    own, foe = mon("mew"), mon("tinglu", ability=ability)
    reduced = damage(move, own, foe).damage
    foe.ability = ""
    ordinary = damage(move, own, foe).damage
    assert .74 < reduced / ordinary < .80
    own.ability = foe.ability = ability
    assert damage(move, own, foe).damage == ordinary
    own.ability = "moldbreaker"
    assert damage(move, own, foe).damage == reduced


@pytest.mark.parametrize("ability,move", [("swordofruin", "tackle"), ("beadsofruin", "surf")])
def test_public_ruin_defense_scalars_and_holder_exemptions(ability, move):
    own, foe = mon("mew", ability=ability), mon("mew")
    boosted = damage(move, own, foe).damage
    own.ability = ""
    ordinary = damage(move, own, foe).damage
    assert boosted > 1.3 * ordinary
    own.ability = foe.ability = ability
    assert damage(move, own, foe).damage == ordinary
    foe.ability = "neutralizinggas"
    assert damage(move, own, foe).damage is None


def test_defensive_tera_overrides_hazard_and_preserves_baseline_call_count(monkeypatch):
    player, calls = policy(monkeypatch)
    state = battle()
    before = pickle.dumps(state)
    py, np_state = random.getstate(), np.random.get_state()
    result = player.choose_move(state)
    assert result.terastallize and result.order.id == "earthquake"
    assert player.last_policy_audit["reason"] == "defensive_stabilization"
    assert len(calls) == 1 and calls[0] is state
    assert pickle.dumps(state) == before
    assert random.getstate() == py
    assert all(np.array_equal(a, b) for a, b in zip(np.random.get_state(), np_state))
    json.dumps(player.last_policy_audit, allow_nan=False)


def test_safe_switch_conserves_tera_unless_preserving_boost_or_entry_damage(monkeypatch):
    player, _ = policy(monkeypatch)
    state = battle(switches=[mon("corviknight")])
    assert not player.choose_move(state).terastallize
    assert player.last_policy_audit["safe_switch"] is True
    state.active_pokemon.boosts["def"] = 2
    assert player.choose_move(state).terastallize
    state.active_pokemon.boosts["def"] = 0
    state.side_conditions = {"stealthrock": 1}
    assert player.choose_move(state).terastallize
    state.available_switches[0].item = "heavydutyboots"
    assert not player.choose_move(state).terastallize


@pytest.mark.parametrize("utility,expected", [("recover", True), ("swordsdance", True),
                                            ("protect", False), ("stealthrock", False), ("partingshot", False)])
def test_defensive_tera_requires_useful_followup(monkeypatch, utility, expected):
    player, _ = policy(monkeypatch, utility)
    state = battle(moves=(utility,))
    assert player.choose_move(state).terastallize is expected
    if expected:
        assert player.last_policy_audit["reason"] == "defensive_stabilization"


def test_offensive_finish_can_choose_tera_blast(monkeypatch):
    player, _ = policy(monkeypatch, "dragonclaw")
    state = battle(mon("dragonite", stats={"atk": 350, "spa": 200}),
                   mon("scizor", hp=.75, moves=("bulletpunch",)),
                   moves=("dragonclaw", "terablast"), tera="Fire")
    result = player.choose_move(state)
    assert result.terastallize and result.order.id == "terablast"
    assert player.last_policy_audit["reason"] == "offensive_finish"


def test_boosted_or_endgame_offense_and_nonqualifying_preservation(monkeypatch):
    player, _ = policy(monkeypatch, "woodhammer")
    state = battle(mon("rillaboom"), mon("dondozo", moves=("surf",)),
                   moves=("woodhammer",), tera="Grass")
    result = player.choose_move(state)
    assert result.terastallize
    assert player.last_policy_audit["reason"] == "boosted_or_endgame_offense"
    state.team.update({"p1: Bench1": mon("mew"), "p1: Bench2": mon("mew")})
    assert not player.choose_move(state).terastallize
    state.active_pokemon.boosts["atk"] = 2
    assert player.choose_move(state).terastallize
    assert player.last_policy_audit["reason"] == "boosted_or_endgame_offense"


def test_priority_precedes_speed_and_conditional_priority_cannot_confirm_finish():
    own = project_mon(mon("dragonite", stats={"spe": 100}), own=True)
    foe = project_mon(mon("dragapult", stats={"spe": 400}), own=False)
    fast = estimate_damage(Move("extremespeed", gen=9), own, foe, Context())
    slow = estimate_damage(Move("tackle", gen=9), foe, own, Context())
    assert AbyssalTeraPlayer._first(fast, [slow], own, foe, Context())
    sucker = estimate_damage(Move("suckerpunch", gen=9), own, foe, Context())
    assert sucker.conditional and not AbyssalTeraPlayer._first(sucker, [slow], own, foe, Context())
    own = replace(own, stats=own.stats | {"spe": foe.stats["spe"] * 1.05})
    assert not AbyssalTeraPlayer._first(slow, [slow], own, foe, Context())
    own = replace(own, stats=own.stats | {"spe": foe.stats["spe"] * 1.11})
    assert AbyssalTeraPlayer._first(slow, [slow], own, foe, Context())


def test_force_switch_spent_tera_and_stellar_keep_baseline(monkeypatch):
    player, calls = policy(monkeypatch)
    for update in (dict(force_switch=True), dict(can_tera=None), dict(can_tera="Stellar")):
        state = battle()
        state.__dict__.update(update)
        assert not player.choose_move(state).terastallize
    assert len(calls) == 3


def test_post_tera_attack_rescore_uses_original_stab_and_target_new_type(monkeypatch):
    player, _ = policy(monkeypatch, "dragonclaw")
    state = battle(mon("garchomp", tera="Steel"), mon("clefable"),
                   moves=("dragonclaw", "earthquake"), tera=None)
    result = player.choose_move(state)
    assert result.order.id == "earthquake" and not result.terastallize
    assert player.last_policy_audit["reason"] == "post_tera_attack_rescore"


def test_unsupported_damage_is_unknown_and_blocks_safety_triggers(monkeypatch):
    value = damage("storedpower", mon("mew"), mon("mew"))
    assert value.damage is None and value.unsupported
    player, _ = policy(monkeypatch)
    state = battle(opponent=mon("clefable", moves=("moonblast", "storedpower")))
    assert not player.choose_move(state).terastallize
    assert player.last_policy_audit["metrics"]["IT"] is None


def test_unknown_normal_damage_cannot_be_used_as_zero_tera_gain(monkeypatch):
    player, _ = policy(monkeypatch, "terablast")
    state = battle(mon("cinderace", ability="libero"), mon("scizor", hp=.5),
                   moves=("terablast",), tera="Fire")
    result = player.choose_move(state)
    assert not result.terastallize
    assert player.last_policy_audit["metrics"]["O0"] is None
    state = battle(mon("mew"), mon("ferrothorn", hp=.5),
                   moves=("storedpower", "terablast"), tera="Fire")
    assert not player.choose_move(state).terastallize
    assert player.last_policy_audit["metrics"]["O0"] is None


def test_post_tera_does_not_replace_unknown_baseline_attack(monkeypatch):
    player, _ = policy(monkeypatch, "storedpower")
    state = battle(mon("mew", tera="Fire"), mon("scizor"),
                   moves=("storedpower", "terablast"), tera=None)
    assert player.choose_move(state).order.id == "storedpower"


def test_post_tera_rescore_does_not_replace_stronger_conditional_attack_with_weaker_one(monkeypatch):
    player, _ = policy(monkeypatch, "suckerpunch")
    state = battle(mon("kingambit", tera="Dark"), mon("mew"),
                   moves=("suckerpunch", "tackle"), tera=None)
    assert player.choose_move(state).order.id == "suckerpunch"


def test_known_absent_items_are_distinct_from_unknown_for_dynamic_power():
    own, foe = mon("mew"), mon("mew")
    no_item = damage("knockoff", own, foe).damage
    foe.item = "leftovers"
    assert damage("knockoff", own, foe).damage > no_item * 1.4
    foe.item = "unknown_item"
    assert damage("knockoff", own, foe).damage is None


def test_public_move_hook_recovers_filtered_moves_and_tags_assumptions(monkeypatch):
    player, _ = policy(monkeypatch)
    state = battle(opponent=mon("clefable"))
    foe = project_mon(state.opponent_active_pokemon, own=False)
    before = player._incoming_attacks(state, foe)
    assert {a.source for a in before} == {"unrevealed_stab_assumption"}
    for name in ("Moonblast", "Knock Off", "Stealth Rock", "Protect"):
        player.observe_public_line("|move|p2a: Other|" + name + "|p1a: Own")
    attacks = player._incoming_attacks(state, foe)
    assert {a.move_id for a in attacks} == {"moonblast", "knockoff"}
    assert {a.source for a in attacks} == {"revealed_move"}
    player.observe_public_line("|move|p2a: Random|Fissure|p1a: Own|[from] move: Metronome")
    assert player._tera_public_moves["p2: Random"] == {"metronome"}
    player.observe_public_line("|move|p2a: Other|Moonblast|p1a: Own|[from] move: Sleep Talk")
    assert "sleeptalk" in player._tera_public_moves["p2: Other"]


def test_bounced_copied_and_struggle_moves_do_not_fill_hidden_slots(monkeypatch):
    player, _ = policy(monkeypatch)
    state = battle(opponent=mon("hatterene", moves=("psychic", "drainingkiss", "calmmind", "stealthrock")))
    for mid in ("Psychic", "Draining Kiss", "Calm Mind"):
        player.observe_public_line(f"|move|p2a: Other|{mid}|p1a: Own")
    player.observe_public_line("|move|p2a: Other|Stealth Rock|p1a: Own|[from] ability: Magic Bounce")
    player.observe_public_line("|move|p2a: Other|Struggle|p1a: Own")
    values = player._incoming_attacks(state, project_mon(state.opponent_active_pokemon, own=False))
    assert sum(a.source == "unrevealed_stab_assumption" for a in values) == 4
    assert "stealthrock" not in player._tera_public_moves["p2: Other"]
    assert "struggle" not in player._tera_public_moves["p2: Other"]
    player.observe_public_line("|move|p2a: Other|Stealth Rock|p1a: Own")
    assert not any(a.source == "unrevealed_stab_assumption" for a in player._incoming_attacks(
        state, project_mon(state.opponent_active_pokemon, own=False)))


def test_public_type_change_does_not_use_stale_original_typing(monkeypatch):
    player, _ = policy(monkeypatch, "terablast")
    state = battle(mon("cinderace", ability="libero"), mon("scizor", hp=.5),
                   moves=("terablast",), tera="Fire")
    state.active_pokemon.effects["typechange"] = 1
    assert not player.choose_move(state).terastallize
    assert player.last_policy_audit["metrics"]["IT"] is None


def test_one_canonical_call_preserves_its_exact_random_draws(monkeypatch):
    player, _ = policy(monkeypatch)
    calls = []
    def canonical(_self, state):
        calls.append((random.random(), float(np.random.random())))
        return BattleOrder(Move("stealthrock", gen=9))
    monkeypatch.setattr(AbyssalPlayer, "choose_move", canonical)
    py, np_state = random.getstate(), np.random.get_state()
    expected = (random.random(), float(np.random.random()))
    after_py, after_np = random.getstate(), np.random.get_state()
    random.setstate(py)
    np.random.set_state(np_state)
    try:
        assert player.choose_move(battle()).terastallize
        assert calls == [expected]
        assert random.getstate() == after_py
        assert all(np.array_equal(a, b) for a, b in zip(np.random.get_state(), after_np))
    finally:
        random.setstate(py)
        np.random.set_state(np_state)


def test_same_observation_ignores_opponent_private_stats_set_and_future_rng(monkeypatch):
    player, _ = policy(monkeypatch)
    state = battle()
    first = player.choose_move(state).message
    audit = copy.deepcopy(player.last_policy_audit)
    class NoRead(dict):
        def __iter__(self):
            pytest.fail("private data was read")
        def get(self, *args, **kwargs):
            pytest.fail("private data was read")
    state.opponent_active_pokemon.stats = NoRead(atk=9999)
    state.opponent_active_pokemon._sets = NoRead(private="sentinel")
    state.opponent_active_pokemon._last_request = NoRead(private="sentinel")
    state.opponent_active_pokemon._terastallized_type = PokemonType.FIRE
    state.future_rng = NoRead(seed=987987)
    py, np_state = random.getstate(), np.random.get_state()
    try:
        random.seed(8675309)
        np.random.seed(1900)
        assert player.choose_move(state).message == first
        assert player.last_policy_audit == audit
    finally:
        random.setstate(py)
        np.random.set_state(np_state)


def test_transformed_mon_remains_unsupported_when_observer_cannot_prove_restoration(monkeypatch):
    player, _ = policy(monkeypatch)
    state = battle()
    player.observe_public_line("|-transform|p2a: Other|p1a: Own")
    assert not player.choose_move(state).terastallize
    assert player.last_policy_audit["reason"] == "unsupported_transform"
    player.observe_public_line("|switch|p2a: Other|Clefable|100/100")
    assert not player.choose_move(state).terastallize
    assert player.last_policy_audit["reason"] == "unsupported_transform"
