"""Synthetic mechanics and public-state boundary tests; no experimental A/B game."""
import copy
import json
import subprocess

import pytest

from integration.pokechamp.branch_rollouts.simulator import SimulatorError
from integration.pokechamp.fixed_matchup.config import ROOT
from integration.pokechamp.fixed_matchup.search import search
from integration.pokechamp.fixed_matchup.simulator import Simulator
from integration.pokechamp.fixed_matchup.storage import digest
from integration.pokechamp.fixed_matchup.verification import FIXTURE_TEAMS, MatrixGame, cpu_checks, uniform


def mon(species, ability, moves, item="", tera="Normal"):
    return f"{species}{' @ ' + item if item else ''}\nAbility: {ability}\nTera Type: {tera}\n" + "\n".join("- " + m for m in moves)


def start(teams=FIXTURE_TEAMS):
    sim = Simulator("real")
    sim.init(teams, [1, 2, 3, 4])
    return sim, sim.advance({"p1": "lead:1", "p2": "lead:1"})


def action(frame, side, move, tera=False):
    return next(a["id"] for a in frame["observations"][side]["actions"]
                if f":{move}:{'tera' if tera else 'normal'}" in a["id"])


def physical_mon(frame, side, index=0):
    return frame["root"]["physical"]["sides"][0 if side == "p1" else 1]["pokemon"][index]


def test_simulator_and_matrix_acceptance():
    assert cpu_checks()["passed"]


def test_future_rng_and_input_log_do_not_cross_boundary():
    code = """
const assert=require('node:assert/strict');
const {Battle}=require('./pokemon-showdown/dist/sim/battle');
const {Teams}=require('./pokemon-showdown/dist/sim/teams');
const {PRNG}=require('./pokemon-showdown/dist/sim/prng');
const {exportPublic}=require('./integration/pokechamp/fixed_matchup/public_state.cjs');
const b=new Battle({formatid:'gen9ou',seed:'1,2,3,4',strictChoices:true,send:()=>{}});
for(const s of ['p1','p2'])b.setPlayer(s,{name:s,team:Teams.import('Pikachu\\nAbility: Static\\n- Thunderbolt')});
const old=exportPublic(b); b.prng=new PRNG('7,8,9,10'); b.inputLog.push('SECRET-SEED');
b.sides[0].lastSelectedMove='unrevealed-intent';
assert.deepEqual(old,exportPublic(b)); b.choose('p1','team 1');
assert.throws(()=>exportPublic(b),/submitted action/);b.destroy();
"""
    subprocess.run(["node", "-e", code], cwd=ROOT, check=True, capture_output=True)


@pytest.mark.parametrize("where", ["top", "side", "pokemon", "effect"])
def test_injected_secret_or_unknown_field_is_rejected(where):
    with Simulator("real") as actual:
        frame = actual.init(FIXTURE_TEAMS, [1, 2, 3, 4])
    root = copy.deepcopy(frame["root"])
    if where == "top":
        root["physical"]["prng"] = "123,456,789,123"
    elif where == "side":
        root["physical"]["sides"][0]["choice"] = {"actions": ["secret"]}
    elif where == "pokemon":
        root["physical"]["sides"][0]["pokemon"][0]["hidden_secret"] = "leak"
    else:
        root["physical"]["sides"][0]["pokemon"][0]["itemState"]["future_seed"] = [1, 2, 3, 4]
    with Simulator("search") as branch, pytest.raises(SimulatorError):
        branch.restore(root, [4, 3, 2, 1])


def test_real_cannot_restore_and_search_cannot_init():
    with Simulator("real") as actual:
        root = actual.init(FIXTURE_TEAMS, [1, 2, 3, 4])["root"]
        with pytest.raises(SimulatorError, match="actual game cannot restore"):
            actual.restore(root, [1, 2, 3, 4])
    with Simulator("search") as branch, pytest.raises(SimulatorError, match="search cannot create"):
        branch.init(FIXTURE_TEAMS, [1, 2, 3, 4])


def test_joint_actions_are_validated_before_either_is_submitted():
    with Simulator("real") as actual:
        actual.init(FIXTURE_TEAMS, [1, 2, 3, 4])
        with pytest.raises(SimulatorError, match="missing or illegal joint action"):
            actual.advance({"p1": "lead:1", "p2": "lead:999"})


def test_tera_and_original_slot_mapping():
    sim, frame = start()
    with sim:
        legal = frame["observations"]["p1"]["actions"]
        assert any(a["id"].endswith(":tera") for a in legal)
        frame = sim.advance({"p1": action(frame, "p1", "nastyplot", True),
                             "p2": action(frame, "p2", "moonblast")})
        assert physical_mon(frame, "p1")["terastallized"] == "Steel"
        assert not any(a["id"].endswith(":tera") for a in frame["observations"]["p1"]["actions"])
        frame = sim.advance({"p1": "switch:2", "p2": action(frame, "p2", "moonblast")})
        assert any(a["id"] == "switch:1" and a["command"] == "switch 2"
                   for a in frame["observations"]["p1"]["actions"])


@pytest.mark.parametrize("move,expected", [("Thunder Wave", "par"), ("Toxic", "tox")])
def test_status_counters_roundtrip(move, expected):
    teams = {"p1": mon("Clefable", "Magic Guard", [move, "Moonblast"]),
             "p2": mon("Blissey", "Natural Cure", ["Soft-Boiled"])}
    sim, frame = start(teams)
    with sim, Simulator("search") as branch:
        for _ in range(5):
            frame = sim.advance({"p1": frame["observations"]["p1"]["actions"][0]["id"],
                                 "p2": action(frame, "p2", "softboiled")})
            if physical_mon(frame, "p2")["status"] == expected:
                break
        assert physical_mon(frame, "p2")["status"] == expected
        restored = branch.restore(frame["root"], [5, 6, 7, 8])
        assert restored["observations"] == frame["observations"]


@pytest.mark.parametrize("move,condition", [("Stealth Rock", "stealthrock"), ("Spikes", "spikes")])
def test_hazards_and_protect(move, condition):
    teams = {"p1": mon("Gliscor", "Poison Heal", [move, "Protect"], "Toxic Orb"),
             "p2": mon("Blissey", "Natural Cure", ["Soft-Boiled"])}
    sim, frame = start(teams)
    with sim, Simulator("search") as branch:
        frame = sim.advance({"p1": frame["observations"]["p1"]["actions"][0]["id"],
                             "p2": action(frame, "p2", "softboiled")})
        assert condition in frame["root"]["physical"]["sides"][1]["sideConditions"]
        assert physical_mon(frame, "p1")["status"] == "tox"
        frame = sim.advance({"p1": action(frame, "p1", "protect"), "p2": action(frame, "p2", "softboiled")})
        assert branch.restore(frame["root"], [2, 3, 4, 5])["observations"] == frame["observations"]


def test_salt_cure_and_knock_off():
    teams = {"p1": mon("Garganacl", "Purifying Salt", ["Salt Cure", "Recover"], "Leftovers"),
             "p2": mon("Clefable", "Magic Guard", ["Knock Off", "Moonlight"], "Leftovers")}
    sim, frame = start(teams)
    with sim, Simulator("search") as branch:
        frame = sim.advance({"p1": action(frame, "p1", "saltcure"), "p2": action(frame, "p2", "knockoff")})
        assert physical_mon(frame, "p1")["item"] == ""
        assert "saltcure" in physical_mon(frame, "p2")["volatiles"]
        assert branch.restore(frame["root"], [2, 3, 4, 5])["observations"] == frame["observations"]


def test_life_orb_current_item_is_public_and_removed_state_does_not_revert():
    teams = {"p1": mon("Reuniclus", "Regenerator", ["Psychic Noise"], "Life Orb"),
             "p2": mon("Clefable", "Magic Guard", ["Knock Off", "Moonlight"])}
    sim, frame = start(teams)
    with sim:
        assert "item:lifeorb" in {c for t in frame["observations"]["p2"]["tokens"] for c in t["categories"]}
        frame = sim.advance({"p1": action(frame, "p1", "psychicnoise"), "p2": action(frame, "p2", "knockoff")})
        assert physical_mon(frame, "p1")["item"] == ""
        assert "item:lifeorb" not in {c for t in frame["observations"]["p2"]["tokens"] for c in t["categories"]}


def test_hidden_pivot_queue_is_rejected():
    teams = {"p1": mon("Dragapult", "Clear Body", ["U-turn"]) + "\n\n" + mon("Blissey", "Natural Cure", ["Soft-Boiled"]),
             "p2": mon("Blissey", "Natural Cure", ["Seismic Toss"])}
    sim, frame = start(teams)
    with sim, pytest.raises(SimulatorError, match="hidden pending action"):
        sim.advance({"p1": action(frame, "p1", "uturn"), "p2": action(frame, "p2", "seismictoss")})


def test_mcts_determinism_visit_conservation_and_depth():
    first = search({}, MatrixGame([[1, 1], [-1, -1]]), uniform, search_seed=44, simulations=64)
    second = search({}, MatrixGame([[1, 1], [-1, -1]]), uniform, search_seed=44, simulations=64)
    assert first["sides"] == second["sides"]
    assert first["transitions"] == 64
    assert all(sum(v["visits"]) == 64 for v in first["sides"].values())


def test_chance_uses_search_seed_not_an_oracle_future():
    import random
    class Chance(MatrixGame):
        def restore(self, root, seed):
            self.rng = random.Random(str(seed))
            return super().restore(root, seed)

        def advance(self, actions):
            return dict(ended=True, winner="p1" if self.rng.random() < 0.7 else "p2")
    result = search({}, Chance(None), uniform, search_seed=91, simulations=2048)
    assert 0.3 < result["mean_value"] < 0.5


def test_real_search_with_synthetic_root_preserves_actual_game():
    sim, frame = start()
    with sim, Simulator("search") as branch:
        original = digest(sim.evidence()["snapshot"])
        result = search(frame["root"], branch, uniform, search_seed=7, simulations=16)
        assert all(sum(row["visits"]) == 16 for row in result["sides"].values())
        assert digest(sim.evidence()["snapshot"]) == original
