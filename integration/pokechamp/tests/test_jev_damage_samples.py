"""Damage sample correctness and bounded-information regressions (no API/battles)."""
import copy
import json
from pathlib import Path

import pytest

from integration.pokechamp.diagnostics.damage_sets import SetSnapshot, candidates, expand_sets, public_history
from integration.pokechamp.diagnostics.jev_damage import Engine, percentage_range, transform
from integration.pokechamp.diagnostics.jev_damage_samples import bounded, unchanged_boundaries
from integration.pokechamp.diagnostics.jev_damage_verify import individual_calls, synthesize
from integration.pokechamp.observation.build import DEFAULT_BUILD


@pytest.fixture(scope="module")
def fixture():
    return json.loads((Path(__file__).parent / "fixtures/jev-damage-prefix.json").read_text())


@pytest.fixture(scope="module")
def dex():
    return json.loads((DEFAULT_BUILD / "dex.json").read_text())


def convert(case, dex, engine=None, snapshot=None):
    if engine is None:
        with Engine() as owned_engine:
            return convert(case, dex, owned_engine, snapshot)
    return transform(case["payload"], case["official"], case["prefix"], case["own_team"],
                     dex, snapshot or SetSnapshot(), engine)


@pytest.fixture(scope="module")
def baseline(fixture, dex):
    return convert(fixture, dex)


def active(payload, side):
    return next(m for m in payload["state"][side + "_team"] if m["active"])


def test_set_coherence_and_vector_choices():
    sets = [dict(name="physical", pokemon="Mew", abilities=["Synchronize"], natures=["Adamant"],
                 evconfigs=[{"hp": 252, "atk": 252}, {"atk": 252, "spe": 252}],
                 ivconfigs=[{"spa": 0}], items=["Choice Band", "Life Orb"], teratypes=["Fire"],
                 moveslots=[[{"move": x}] for x in ("Tackle", "Earthquake", "U-turn", "Roost")]),
            dict(name="special", pokemon="Mew", abilities=["Synchronize"], natures=["Modest"],
                 evconfigs=[{"spa": 252, "spe": 252}], ivconfigs=[{"atk": 0}], items=["Choice Specs"],
                 teratypes=["Water"], moveslots=[[{"move": x}] for x in ("Surf", "Psychic", "Flamethrower", "Roost")])]
    rows = list(expand_sets(sets))
    assert len(rows) == 5
    for row in rows:
        if row["set_name"] == "physical":
            assert row["nature"] == "Adamant" and row["item"] != "Choice Specs"
            assert row["ivs"]["spa"] == 0 and row["ivs"]["atk"] == 31
            assert row["tera_types"] == ["Fire"] and "surf" not in row["moves"]
        else:
            assert row["nature"] == "Modest" and row["evs"]["atk"] == 0
            assert row["ivs"]["atk"] == 0 and row["tera_types"] == ["Water"]


def mon(**kw):
    return dict(dict(moves=[], item="unknown_item", ability_known=False, ability=None,
                     level=100, tera_type=""), **kw)


def test_consumption_then_trick_does_not_filter_on_received_item():
    sets, _ = SetSnapshot().load("zapdos")
    prefix = [dict(event_seq=1, protocol="\n".join([
        "|start", "|switch|p2a: Zapdos|Zapdos|100/100",
        "|-enditem|p2a: Zapdos|Heavy-Duty Boots|[from] move: Knock Off",
        "|-item|p2a: Zapdos|Choice Scarf|[from] move: Trick"]))]
    history = public_history(prefix, "p2: Zapdos")
    assert history["initial_items"] == ["heavydutyboots"] and history["item_changed"]
    for current in (None, "choicescarf"):
        accepted, _ = candidates(sets, mon(item=current), history)
        assert len(accepted) == 5
        assert all(c["current_item"] == (current or "") for c in accepted)
        assert all(c["item"] == "Heavy-Duty Boots" for c in accepted)
    incompatible = public_history([dict(event_seq=1, protocol="|-enditem|p2a: Zapdos|Leftovers")], "p2: Zapdos")
    assert not candidates(sets, mon(item=None), incompatible)[0]


def test_observed_moves_and_tera_condition_whole_set():
    sets, _ = SetSnapshot().load("zapdos")
    history = public_history([], "p2: Zapdos")
    accepted, rejected = candidates(sets, mon(moves=["heatwave"]), history)
    assert len(accepted) == 1 and rejected
    assert accepted[0]["set_name"] == "Offensive"
    assert accepted[0]["tera_types"] == ["Fire"]
    assert not candidates(sets, mon(moves=["heatwave"], tera_type="Steel"), history)[0]
    assert not candidates(sets, mon(moves=["thunder"]), history)[0]


def test_public_ability_change_keeps_original_constraint_separate():
    sets, _ = SetSnapshot().load("zapdos")
    history = public_history([dict(event_seq=1, protocol="\n".join([
        "|-ability|p2a: Zapdos|Static", "|-ability|p2a: Zapdos|Levitate|[from] move: Skill Swap"]))], "p2: Zapdos")
    accepted, _ = candidates(sets, mon(ability_known=True, ability="levitate"), history)
    assert len(accepted) == 5
    assert all(c["ability"] == "Static" and c["current_ability"] == "levitate" for c in accepted)
    assert not candidates(sets, mon(ability_known=True, ability="pressure"), public_history([], "p2: Zapdos"))[0]


def test_snapshot_wrong_hash_or_date_rejected(tmp_path):
    raw = b"[]"
    (tmp_path / "zapdos.json").write_bytes(raw)
    provenance = dict(sha256="wrong", format="gen9ou", retrieved_at="2026-09-18T00:00:00Z")
    (tmp_path / "zapdos.provenance.json").write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="identity/date"):
        SetSnapshot(tmp_path).load("zapdos")
    import hashlib
    provenance.update(sha256=hashlib.sha256(raw).hexdigest(), retrieved_at="2026-09-19T00:00:00Z")
    (tmp_path / "zapdos.provenance.json").write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="identity/date"):
        SetSnapshot(tmp_path).load("zapdos")


def test_mimic_and_sketch_history_not_five_move_contradiction():
    lines = ["|start", "|switch|p2a: Mew|Mew|100/100", "|move|p2a: Mew|Mimic|p1a: Mew",
             "|-start|p2a: Mew|Mimic|Surf", "|move|p2a: Mew|Surf|p1a: Mew"]
    history = public_history([dict(event_seq=1, protocol="\n".join(lines))], "p2: Mew")
    assert history["original_moves"] == ["mimic"]
    assert history["replacements"] == {"mimic": "surf"}
    lines += ["|switch|p2a: Zapdos|Zapdos|100/100", "|switch|p2a: Mew|Mew|100/100"]
    assert not public_history([dict(event_seq=1, protocol="\n".join(lines))], "p2: Mew")["replacements"]
    lines += ["|-activate|p2a: Mew|move: Sketch|Earthquake", "|switch|p2a: Zapdos|Zapdos|100/100"]
    assert public_history([dict(event_seq=1, protocol="\n".join(lines))], "p2: Mew")["replacements"] == {"sketch": "earthquake"}


def test_per_candidate_maximum_hp_and_outward_rounding():
    assert percentage_range([dict(damage_range_hp=[100, 150], defender_max_hp=400),
                             dict(damage_range_hp=[90, 150], defender_max_hp=300)]) == [25.0, 50.0]
    assert percentage_range([dict(damage_range_hp=[100, 400], defender_max_hp=300)]) == [33.3, 133.4]
    assert percentage_range([dict(damage_range_hp=[0, 0], defender_max_hp=321)]) == [0.0, 0.0]
    with pytest.raises(ValueError, match="incomplete"):
        percentage_range([dict(excluded_with_reason="unsupported")])


def test_both_directions_denominators_labels_pp_and_candidate_copies(fixture, baseline):
    after, audit = baseline
    unchanged_boundaries(fixture["payload"], after)
    assert audit["branches"] == ["current", "self_tera", "opponent_tera", "both_tera"]
    incoming = [r for r in audit["calculations"] if r["direction"] == "incoming"]
    outgoing = [r for r in audit["calculations"] if r["direction"] == "outgoing"]
    assert {r["result"]["defender_max_hp"] for r in incoming} == {283}
    assert {r["result"]["defender_max_hp"] for r in outgoing} == {321, 383}
    for r in incoming:
        if r["branch"] == "self_tera":
            assert r["scenario"]["defender"]["options"]["teraType"] == "Bug"
            assert "teraType" not in r["scenario"]["attacker"]["options"]
        if r["move"] == "heatwave":
            assert audit["candidates"][-1]["candidate_id"] == r["candidate_id"]
            if r["branch"] == "opponent_tera":
                assert r["opponent_new_tera"] == "Fire"
    self_moves = {m["id"]: m for m in active(after, "self")["moves"]}
    for old in active(fixture["payload"], "self")["moves"]:
        assert self_moves[old["id"]]["current_pp"] == old["current_pp"]
        assert "power" not in self_moves[old["id"]]
    for candidate in after["questions"]["action"]["criteria"].values():
        if "move" in candidate:
            assert candidate["move"]["damage_pct"] == self_moves[candidate["move"]["id"]]["damage_pct"]
            assert "power" not in candidate["move"]
    for m in active(after, "opponent")["moves"]:
        assert m["knowledge"] == "hypothesized" and "current_pp" not in m
        assert m["id"] in after["state"]["effect_reference"]["moves"]
    assert next(m for m in active(after, "opponent")["moves"] if m["id"] == "roost")["damage_pct"] is None


def test_self_opponent_semantics_are_actor_relative_on_p2(fixture, dex, baseline):
    encoded = json.dumps(fixture).replace("p1", "SIDE_TMP").replace("p2", "p1").replace("SIDE_TMP", "p2")
    case = json.loads(encoded)
    after, audit = convert(case, dex)
    assert after["state"]["actor"] == "p2"
    assert audit["branches"] == baseline[1]["branches"]
    for side in ("self", "opponent"):
        assert active(after, side)["moves"] == active(baseline[0], side)["moves"]


@pytest.mark.parametrize("lines,applied", [
    (["|-terastallize|p2a: Zapdos|Steel"], True),
    (["|-terastallize|p2a: Zapdos|Steel", "|switch|p2a: Ting-Lu|Ting-Lu|100/100"], False),
    (["|-terastallize|p2a: Zapdos|Steel", "|switch|p2a: Ting-Lu|Ting-Lu|100/100",
      "|switch|p2a: Zapdos|Zapdos, tera:Steel|100/100"], True),
])
def test_opponent_tera_consumption_bench_and_return(fixture, dex, lines, applied):
    case = synthesize(fixture, lines, dex)
    after, audit = convert(case, dex)
    assert audit["branches"] == ["current", "self_tera"]
    assert active(after, "opponent")["tera_type"] == ("Steel" if applied else "")
    for row in audit["calculations"]:
        opposing = row["scenario"]["defender" if row["direction"] == "outgoing" else "attacker"]
        assert opposing["options"].get("teraType") == ("Steel" if applied else None)


def test_known_and_hypothetical_moves_and_missing_support(fixture, dex):
    case = synthesize(fixture, ["|move|p2a: Zapdos|Hurricane|p1a: Lokix"], dex)
    after, _ = convert(case, dex)
    moves = {m["id"]: m for m in active(after, "opponent")["moves"]}
    assert moves["hurricane"]["knowledge"] == "observed"
    assert moves["heatwave"]["knowledge"] == "hypothesized"
    case = synthesize(fixture, ["|move|p2a: Zapdos|Thunder|p1a: Lokix"], dex)
    after, audit = convert(case, dex)
    assert not audit["candidates"] and audit["excluded_candidates"]
    assert all(m["damage_pct"] is None and m["damage_reason"] == "no_compatible_recommended_set"
               for m in active(after, "self")["moves"])
    assert active(after, "opponent")["moves"][0]["knowledge"] == "observed"


def test_unsupported_state_does_not_look_like_immunity(fixture, dex):
    case = synthesize(fixture, ["|-start|p2a: Zapdos|Substitute"], dex)
    after, audit = convert(case, dex)
    for move in active(after, "self")["moves"]:
        assert set(move["damage_pct"].values()) == {None}
        assert all("SUBSTITUTE" in r for r in move["damage_reason"].values())
    assert audit["calculations"] and all("error" in r for r in audit["calculations"])


def test_screens_reverse_with_attack_direction(fixture, dex, baseline):
    case = synthesize(fixture, ["|-sidestart|p1: Controlled|Reflect"], dex)
    after, audit = convert(case, dex)
    for row in audit["calculations"]:
        field = row["scenario"]["field"]
        target = "defenderSide" if row["direction"] == "incoming" else "attackerSide"
        assert field[target]["isReflect"] is True
    get = lambda payload: next(m["damage_pct"]["current"] for m in active(payload, "opponent")["moves"] if m["id"] == "uturn")
    assert get(after)[1] < get(baseline[0])[1]
    assert active(after, "self")["moves"] == active(baseline[0], "self")["moves"]


def test_one_failed_candidate_invalidates_whole_branch(fixture, dex):
    class Failing:
        def __init__(self, engine):
            self.engine = engine
            self.failed = False

        def calculate(self, scenario):
            if not self.failed:
                self.failed = True
                return dict(scenario_id=scenario["scenario_id"], excluded_with_reason="injected_unsupported")
            return self.engine.calculate(scenario)

    with Engine() as real:
        after, audit = convert(fixture, dex, Failing(real))
    move = active(after, "self")["moves"][0]
    assert move["damage_pct"]["current"] is None
    assert move["damage_reason"]["current"] == "injected_unsupported"
    assert move["damage_pct"]["self_tera"] is not None
    assert len(audit["calculations"]) == 236  # No candidate silently omitted.


def test_future_lines_and_foreign_payload_cannot_enter(fixture, dex):
    records = copy.deepcopy(fixture["prefix"])
    records[-1]["protocol"] += "\n|move|p2a: Zapdos|Thunder|p1a: Lokix\n|-terastallize|p2a: Zapdos|Fire"
    records.append(dict(event_seq=999999, protocol="|win|foreign-future"))
    assert bounded(records, fixture["boundary"]) == fixture["prefix"]
    poisoned = copy.deepcopy(fixture)
    active(poisoned["payload"], "opponent")["ability"] = "future-private-sentinel"
    with pytest.raises(ValueError, match="bounded JEV"):
        convert(poisoned, dex)
    poisoned = copy.deepcopy(fixture)
    poisoned["official"]["request"]["side"]["id"] = "p2"
    with pytest.raises(ValueError, match="foreign request"):
        convert(poisoned, dex)


@pytest.mark.parametrize("kind", ["lead", "forced_switch"])
def test_out_of_scope_inputs_are_exactly_preserved(fixture, dex, kind):
    case = copy.deepcopy(fixture)
    case["payload"]["state"]["decision_kind"] = kind
    after, audit = convert(case, dex)
    assert after == case["payload"] and not audit["calculations"]


def spec(name="Mew", maximum=341, **options):
    opts = dict(level=100, ability="", item="", nature="Serious", evs=dict.fromkeys(("hp", "atk", "def", "spa", "spd", "spe"), 0),
                ivs=dict.fromkeys(("hp", "atk", "def", "spa", "spd", "spe"), 31), boosts={}, curHP=maximum, status="")
    opts.update(options)
    return dict(name=name, options=opts, entry_effects_observed=True)


def scenario(move, attacker=None, defender=None, **field):
    return dict(scenario_id=move, attacker=attacker or spec(), defender=defender or spec(), move=move, field=field)


@pytest.mark.parametrize("move,defender,expected", [
    ("earthquake", spec("Zapdos", 321), [0, 0]),
    ("seismictoss", spec("Blissey", 651), [100, 100]),
    ("nightshade", spec("Blissey", 651), [0, 0]),
    ("ruination", spec(curHP=201), [100, 100]),
    ("endeavor", spec(), [0, 0]),
])
def test_immunity_and_fixed_damage_individual_smogon(move, defender, expected):
    case = scenario(move, defender=defender)
    with Engine() as engine:
        result = engine.calculate(case)
    assert result["damage_range_hp"] == expected
    assert result["damage_range_hp"] == individual_calls([case])["entries"][0]["damage_range_hp"]
    assert result["defender_max_hp"] != defender["options"]["curHP"] or move != "ruination"


@pytest.mark.parametrize("options,hits", [({}, [2, 3, 4, 5]), ({"item": "Loaded Dice"}, [4, 5]), ({"ability": "Skill Link"}, [5])])
def test_multihit_counts_and_raw_oracle(options, hits):
    case = scenario("iciclespear", attacker=spec("Cloyster", 241, **options))
    with Engine() as engine:
        result = engine.calculate(case)
    assert [r["hits"] for r in result["damage_variants"]] == hits
    direct = individual_calls([dict(case, move_options={"hits": n}) for n in hits])["entries"]
    assert [r["damage_range_hp"] for r in direct] == [r["damage_range_hp"] for r in result["damage_variants"]]


@pytest.mark.parametrize("move,item,hits", [("tripleaxel", "", [3]), ("triplekick", "", [3]),
    ("populationbomb", "", [10]), ("populationbomb", "Loaded Dice", list(range(4, 11)))])
def test_accuracy_failures_excluded_but_random_hit_counts_retained(move, item, hits):
    case = scenario(move, attacker=spec(item=item))
    with Engine() as engine:
        result = engine.calculate(case)
    assert [v["hits"] for v in result["damage_variants"]] == hits
    assert len(result["worker_damage_variants"]) > len(hits)
    oracle = individual_calls([dict(case, move_options={"hits": n}) for n in hits])["entries"]
    assert [v["damage_range_hp"] for v in result["damage_variants"]] == [r["damage_range_hp"] for r in oracle]


def test_unsupported_loaded_dice_state_is_explicit():
    with Engine() as engine:
        result = engine.calculate(scenario("iciclespear", attacker=spec(item="Loaded Dice"), isMagicRoom=True))
    assert "damage_range_hp" not in result and "unsupported" in result["excluded_with_reason"]


def test_forced_crit_and_ordinary_crit_not_unioned():
    cases = [scenario("stormthrow", attacker=spec(boosts={"atk": -6}), defender=spec(boosts={"def": 6}),
                      defenderSide={"isReflect": True}), scenario("karatechop")]
    direct = individual_calls(cases)["entries"]
    assert direct[0]["is_crit"] is True and direct[1]["is_crit"] is False
    with Engine() as engine:
        assert [engine.calculate(c)["damage_range_hp"] for c in cases] == [r["damage_range_hp"] for r in direct]


def test_weather_terrain_screens_burn_boosts_individual_oracle():
    cases = [scenario("flamethrower", weather="Sun"), scenario("surf", weather="Rain"),
             scenario("thunderbolt", terrain="Electric"),
             scenario("tackle", attacker=spec(status="brn", boosts={"atk": 2}), defenderSide={"isReflect": True}),
             scenario("psychic", defenderSide={"isLightScreen": True})]
    direct = individual_calls(cases)["entries"]
    with Engine() as engine:
        assert [engine.calculate(c)["damage_range_hp"] for c in cases] == [r["damage_range_hp"] for r in direct]


def test_history_dependent_unsupported_is_not_zero():
    with Engine() as engine:
        result = engine.calculate(scenario("counter"))
    assert "damage_range_hp" not in result
    assert "history" in result["excluded_with_reason"]
