"""D-031 catalog completeness, pinned semantics and local request delivery."""

import copy
import json
import logging
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.improved_io import battle_prompts as prompts
from integration.pokechamp.improved_io.battle_only_prepare import prepare
from integration.pokechamp.improved_io.battle_only_protocol import PROFILE, read_stage

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    directory = tmp_path_factory.mktemp("field-guide") / "prepare"
    prepare(
        ROOT / ".pokechamp-data/experiments/glm-upstream-fallback32-v1/battles",
        ROOT
        / ".pokechamp-data/benchmarks/glm-upstream-fallback32-v1"
        / "analysis/io_evidence.json",
        directory,
        battle_prompt_version="v1.1.0",  # Keep the D-031 historical contract explicit.
    )
    return directory


@pytest.fixture(scope="module")
def scene(prepared):
    return b.read_sealed(prepared / "offline/IO-C01.json")


def test_prepare_all_fifteen_complete_and_old_user_state_preserved(prepared):
    manifest = b.read_sealed(prepared / "manifest.json")
    assert manifest["battle_prompt_identity"] == prompts.identity("v1.1.0")
    record = b.read_sealed(prepared / "battle-prompt.json")
    for index in range(1, 16):
        name = f"IO-C{index:02}.json"
        context = b.read_sealed(prepared / "offline" / name)
        old = b.read_sealed(
            ROOT
            / ".pokechamp-data/io-battle-only/ex026-preflight/prepare/offline"
            / name
        )
        old["calculation_bundle"].pop("elapsed_ms")
        comparison = copy.deepcopy(context)
        comparison["calculation_bundle"].pop("elapsed_ms")
        if index == 6:
            # D-034: only the independently verified clone-defect calculations changed.
            corrected = json.loads(
                Path(__file__).with_name("entry_scene06_expected.json").read_text()
            )["entries"]
            assert len(corrected) == 24
            old["calculation_bundle"]["entries"] = [
                corrected.get(entry["scenario_id"], entry)
                for entry in old["calculation_bundle"]["entries"]
            ]
        assert (
            comparison == old
        )  # All observations, candidates and raw windows stay fixed.
        assert prompts.assemble(context, version="v1.1.0") == record["system_prompt"]
    assert len(record["input_sizes"]) == 15
    assert all(
        r["added_chars"] > 0 and r["added_bytes"] >= r["added_chars"]
        for r in record["input_sizes"]
    )
    assert read_stage(prepared / "result.json", "prepare")["passed"]


@pytest.mark.parametrize(
    "path",
    [
        ("new_field",),
        ("current_observation", "self_team", 0, "original_set", "ivs", "new_stat"),
        ("calculation_bundle", "entries", 0, "conditional_order", "win_probability"),
    ],
)
def test_new_fields_are_reported_not_dropped(scene, path):
    context = copy.deepcopy(scene)
    target = context
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = 1
    with pytest.raises(ValueError, match=path[-1]):
        prompts.check_fields(context)
    assert target[path[-1]] == 1


def test_removed_nested_definition_fails_even_inside_raw_request(scene):
    guide = prompts.catalog()
    del guide["definitions"]["request_mon"]["properties"]["stats"]["values"]
    # A missing dynamic schema cannot accidentally become a free-form object.
    with pytest.raises((ValueError, KeyError)):
        prompts.check_fields(scene, guide)
    guide = prompts.catalog()
    del guide["definitions"]["request_mon"]["properties"]["baseAbility"]
    with pytest.raises(ValueError, match=r"RequestJSON.side.pokemon\[0\].baseAbility"):
        prompts.check_fields(scene, guide)
    guide = prompts.catalog()
    del guide["definitions"]["original_set"]["properties"]["nature"]
    with pytest.raises(ValueError, match=r"original_set.nature"):
        prompts.check_fields(scene, guide)


def test_undocumented_embedded_json_and_pipes_in_names(scene):
    context = copy.deepcopy(scene)
    request = dict(rqid=998, side=dict(name="data|only", id="p1", pokemon=[]))
    context["recent_events"] = [
        dict(event_seq=1, protocol="|request|" + json.dumps(request))
    ]
    prompts.check_fields(context)
    request["side"]["undocumented"] = {"nested": 1}
    context["recent_events"][0]["protocol"] = "|turn|1\n|request|" + json.dumps(request)
    with pytest.raises(
        ValueError, match=r"protocol:line2.RequestJSON.side.undocumented"
    ):
        prompts.check_fields(context)
    context["recent_events"][0]["protocol"] = "|request|{broken"
    with pytest.raises(ValueError, match="invalid request JSON"):
        prompts.check_fields(context)
    context["recent_events"][0]["protocol"] = "|request|"
    prompts.check_fields(context)


def test_optional_request_branches_from_pinned_producers(scene):
    # Independently authored against sim/pokemon.ts, sim/side.ts and battle.ts,
    # including unavailable in this Gen9 singles experiment's fifteen scenes.
    options = dict(
        moves=[
            dict(move="Recharge", id="recharge"),
            dict(
                move="Splash",
                id="splash",
                pp=0,
                maxpp=64,
                target="self",
                disabled="hidden",
                disabledSource="Disable",
            ),
        ],
        maybeDisabled=True,
        maybeLocked=True,
        trapped=True,
        maybeTrapped=True,
        canTerastallize="Water",
        canMegaEvo=True,
        canMegaEvoX=True,
        canMegaEvoY=True,
        canUltraBurst=True,
        canDynamax=True,
        canZMove=[None, dict(move="Z-Splash", target="self")],
        maxMoves=dict(
            maxMoves=[dict(move="maxguard", target="self", disabled=True)],
            gigantamax="Pikachu",
        ),
    )
    requests = [
        dict(active=[options, None], noCancel=True, rqid=1),
        dict(forceSwitch=[True], noCancel=True, rqid=2),
        dict(wait=True, rqid=3),
        dict(teamPreview=True, maxChosenTeamSize=6, rqid=4),
    ]
    context = copy.deepcopy(scene)
    context["recent_events"] = [
        dict(event_seq=k, protocol="|request|" + json.dumps(req))
        for k, req in enumerate(requests, 1)
    ]
    prompts.check_fields(context)
    # Scalar/array unions must never open arbitrary nested objects.
    requests[0]["active"][0]["canZMove"][1]["new_key"] = True
    context["recent_events"][0]["protocol"] = "|request|" + json.dumps(requests[0])
    with pytest.raises(ValueError, match=r"canZMove\[1\].new_key"):
        prompts.check_fields(context)


def test_delayed_effect_branches_from_independent_simulator(scene):
    from integration.pokechamp.improved_io.protocol import observed_state

    output = json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("state_lifecycle.cjs"))],
            text=True,
        )
    )
    statuses = set()
    for scenario in output:
        for raw in scenario["rows"]:
            events = [dict(event_seq=1, protocol=raw["protocol"])]
            timing = observed_state(events)
            context = copy.deepcopy(scene)
            context["current_observation"]["protocol_state"] = timing
            context["calculation_bundle"]["pending_effects"] = timing["pending_effects"]
            prompts.check_fields(context)
            statuses |= {
                v["status"]
                for v in timing["delayed_history"] + timing["pending_effects"]
            }
    assert {
        "pending",
        "resolution_observed",
        "expired_without_public_resolution",
    } <= statuses
    # Resolution without an observed cast and battle-ended pending branch.
    for raw in (
        "|turn|3\n|-end|p2a: Mew|move: Future Sight",
        "|turn|1\n|move|p1a: Mew|Future Sight|p2a: Mew\n"
        "|-start|p1a: Mew|move: Future Sight\n|win|one",
    ):
        context["current_observation"]["protocol_state"] = observed_state(
            [dict(event_seq=1, protocol=raw)]
        )
        prompts.check_fields(context)


def test_unknown_replacement_and_status_exclusion_are_not_zero_damage(scene):
    from integration.pokechamp.improved_io.calculations import compute
    from integration.pokechamp.improved_io.calculator import Calculator

    context = copy.deepcopy(scene)
    context["request"].update(
        kind="forced_switch", legal_actions=[dict(switch="gliscor")]
    )
    opponent = next(
        p for p in context["current_observation"]["opponent_confirmed"] if p["active"]
    )
    opponent.update(fainted=True, hp=0)
    with Calculator() as calculator:
        context["calculation_bundle"] = compute(context, calculator)
    prompts.check_fields(context)
    entry = context["calculation_bundle"]["entries"][0]
    assert "excluded_with_reason" in entry and "damage_range_hp" not in entry
    status = [
        e for e in scene["calculation_bundle"]["entries"] if "effect_assessment" in e
    ]
    assert status and all("damage_range_hp" not in e for e in status)
    damage = [
        e for e in scene["calculation_bundle"]["entries"] if "damage_range_hp" in e
    ]
    assert damage and all(
        e["ko_chance_given_hit"] is None and e["survival_given_hit"] is None
        for e in damage
    )
    context["calculation_bundle"]["entries"] = [
        dict(scenario_id="multi", damage_rolls=[[1, 2], [3, 4]], damage_range_hp=[4, 6])
    ]
    prompts.check_fields(context)
    context["calculation_bundle"]["entries"][0]["damage_rolls"][0] = {"unknown": 1}
    with pytest.raises(ValueError, match="damage_rolls"):
        prompts.check_fields(context)


def test_pinned_counter_lifetimes_and_item_semantics():
    from poke_env.environment.battle import Battle
    from poke_env.environment.effect import Effect
    from poke_env.environment.pokemon import Pokemon
    from poke_env.environment.side_condition import SideCondition
    from poke_env.environment.weather import Weather

    from integration.pokechamp.improved_io.protocol import live_effects, observed_state
    from integration.pokechamp.improved_io.state import (
        hypotheses,
        public_mon,
        public_revelations,
    )

    mon = Pokemon(gen=9, species="mew")
    mon.start_effect("confusion")
    assert mon.effects[Effect.CONFUSION] == 0 and not Effect.CONFUSION.is_turn_countable
    assert live_effects(mon, "p2: Mew", {})["CONFUSION"] == 0
    mon.end_turn()
    assert mon.effects[Effect.CONFUSION] == 0
    guide = prompts.catalog()
    assert {e.name for e in Effect} == set(guide["key_rules"]["effect"]["allowed"])
    effect_description = guide["key_rules"]["effect"]["description"]
    for effect in Effect:
        if effect.is_turn_countable or effect.is_action_countable:
            assert effect.name in effect_description
    battle = Battle("battle-gen9ou-field", "one", logging.getLogger("guide"), gen=9)
    battle._player_role = "p1"
    raw = (
        "|turn|3\n|-sidestart|p1: one|Spikes\n|-sidestart|p1: one|Reflect\n"
        "|-weather|SunnyDay\n|turn|4\n|-sidestart|p1: one|Spikes\n"
        "|-weather|SunnyDay|[upkeep]"
    )
    for line in raw.splitlines():
        battle.parse_message(line.split("|"))
    timing = observed_state([dict(event_seq=1, protocol=raw)])
    assert battle.side_conditions[SideCondition.SPIKES] == 2
    assert battle.side_conditions[SideCondition.REFLECT] == 3
    assert battle.weather[Weather.SUNNYDAY] == 4
    assert timing["weather"]["SunnyDay"]["observed_start_turn"] == 3
    assert timing["weather"]["SunnyDay"]["last_update_turn"] == 4
    assert timing["sides"]["p1"]["Spikes"]["layers"] == 2
    assert mon.item == "unknown_item"
    mon.end_item("leftovers")
    assert mon.item is None
    facts = public_revelations([dict(protocol="|-enditem|p2a: Mew|Leftovers")])
    observed = public_mon(mon, facts["p2: Mew"])
    prior = json.loads((prompts.PROMPTS.parent / "prior.json").read_text())
    assert all(h["item"] == "" for h in hypotheses(observed, prior))


def test_hp_precision_against_showdown_gethealth():
    from integration.pokechamp.improved_io.calculations import public_hp_bounds

    # This executes the pinned independent simulator, not the integration's formula.
    source = r"""
const {Battle} = require('./pokemon-showdown/dist/sim');
const {Format} = require('./pokemon-showdown/dist/sim/dex-formats');
const format=new Format({name:'HP',mod:'gen9',gameType:'singles',ruleset:[]});
const b = new Battle({format,seed:[1,2,3,4]});
b.setPlayer('p1',{name:'one',team:[{species:'Mew',moves:['Splash']}]});
b.setPlayer('p2',{name:'two',team:[{species:'Mew',moves:['Splash']}]});
const p=b.p2.active[0], rows=[];
for(const maximum of [100,301,373]) {
 p.maxhp=maximum;
 for(const hp of [1,7,maximum-1,maximum]) {
  p.hp=hp; rows.push({hp,maximum,health:p.getHealth()});
 }
}
b.destroy(); process.stdout.write(JSON.stringify(rows));
"""
    rows = json.loads(
        subprocess.check_output(["node", "-e", source], cwd=ROOT, text=True)
    )
    for row in rows:
        current, scale = map(int, row["health"]["shared"].split("/"))
        low, high = public_hp_bounds(current, scale, row["maximum"])
        assert low <= row["hp"] <= high
        assert row["health"]["secret"] == f"{row['hp']}/{row['maximum']}"
        if row["hp"] == row["maximum"] - 1 and row["maximum"] > 100:
            assert current == 99


def test_legacy_version_identity_and_asset_tamper(tmp_path, monkeypatch, scene):
    assert prompts.selected({}) == prompts.identity("v1.0.0")
    assert prompts.assemble(scene) == (prompts.PROMPTS / "battle_fixed.txt").read_text()
    for wrong in (
        dict(battle_prompt_version="v2.0.0"),
        dict(battle_prompt_version="v1.1.0"),
        dict(battle_prompt_version="v1.1.0", battle_prompt_identity=prompts.identity()),
    ):
        with pytest.raises(ValueError, match="battle prompt"):
            prompts.selected(wrong)
    import shutil

    copied = tmp_path / "prompts"
    shutil.copytree(prompts.PROMPTS, copied)
    monkeypatch.setattr(prompts, "PROMPTS", copied)
    monkeypatch.setattr(prompts, "GUIDE", copied / "battle-v1.1.0/fields.json")
    prompts.GUIDE.write_text(prompts.GUIDE.read_text() + " ")
    with pytest.raises(ValueError, match="hash mismatch"):
        prompts.assemble(scene, version="v1.1.0")
    assert prompts.assemble(scene) == (copied / "battle_fixed.txt").read_text()


def test_execution_manifest_identity_mismatch_is_rejected(prepared, monkeypatch):
    from integration.pokechamp.improved_io import battle_only_protocol
    from integration.pokechamp.improved_io.battle_only import execution

    ex = execution(
        prepared / "result.json", stage="fake32", previous=prepared / "result.json"
    )
    assert ex["evidence"]["battle_prompt_identity"] == prompts.identity("v1.1.0")
    monkeypatch.setattr(
        battle_only_protocol, "read_stage", lambda *a, **k: dict(passed=True)
    )
    assert battle_only_protocol.require_offline(ex)["passed"]
    ex["evidence"].update(prompts.selection("v1.0.0"))
    with pytest.raises(ValueError, match="execution/preparation"):
        battle_only_protocol.require_offline(ex)


def test_worker_actual_messages_match_preparation_and_reject_drift(
    prepared, scene, tmp_path, monkeypatch
):
    from integration.pokechamp.improved_io import cloud_gate
    from integration.pokechamp.improved_io.backend import FixedBackend

    calls = []

    def chat(**kwargs):
        calls.append(kwargs)
        return dict(
            model="glm-5.3-flash",
            done=True,
            done_reason="stop",
            message=dict(
                content="This is a local delivery fixture.\n"
                + json.dumps(scene["request"]["legal_actions"][0])
            ),
        )

    class Local(FixedBackend):
        def __init__(self, **kwargs):
            super().__init__(
                environ={"OLLAMA_API_KEY": "local-fixture"},
                trace_sink=kwargs["trace_sink"],
                client_factory=lambda **_: SimpleNamespace(chat=chat),
            )

    monkeypatch.setattr(cloud_gate.cli, "_load_cloud_credential", lambda: None)
    monkeypatch.setattr(cloud_gate, "FixedBackend", Local)
    item = dict(
        id="local",
        role="self_action",
        profile=PROFILE,
        study_root="unused",
        cohort="c0",
        context=scene,
        output_path=str(tmp_path / "response.json"),
        **prompts.selection("v1.1.0"),
    )
    result = cloud_gate.call(item, "unused-socket", 1)
    assert result["valid"]
    wire = calls[0]["messages"]
    assert len(wire) == 2
    system = b.read_sealed(prepared / "battle-prompt.json")["system_prompt"]
    assert wire == [
        dict(role="system", content=system),
        dict(role="user", content=json.dumps(scene, ensure_ascii=False)),
    ]
    assert system.count("BATTLE INPUT FIELD GUIDE v1.1.0") == 1
    assert result["trace"]["request"]["battle_prompt_identity"] == prompts.identity(
        "v1.1.0"
    )
    item["battle_prompt_identity"] = prompts.identity()
    item["output_path"] = str(tmp_path / "bad.json")
    assert not cloud_gate.call(item, "unused-socket", 1)["valid"]
    assert len(calls) == 1
    # The final transport boundary rejects messages that bypassed builders.
    backend = Local(trace_sink=SimpleNamespace())
    backend.io_profile = PROFILE
    backend.battle_prompt_identity = prompts.identity("v1.1.0")
    backend.input_context = scene
    with pytest.raises(ValueError, match="transmitted"):
        backend.get_LLM_action(system + "extra", json.dumps(scene), "glm-5.3-flash")
    assert len(calls) == 1


def test_actor_actual31_messages_equal_shared_prompt(prepared):
    from integration.pokechamp.improved_io.memory_fixture import run

    result = run(battle_only=True, battle_prompt_version="v1.1.0")
    assert result["passed"] and result["cloud_calls"] == 0
    assert result["roles"] == ["self_action"] * 31
    expected = b.read_sealed(prepared / "battle-prompt.json")["system_prompt"]
    for call in result["wire_calls"]:
        context = json.loads(call["user_prompt"])
        assert (
            call["system_prompt"]
            == expected
            == prompts.assemble(context, version="v1.1.0")
        )
        assert call["system_prompt"].count("BATTLE INPUT FIELD GUIDE v1.1.0") == 1
        assert call["request"]["battle_prompt_identity"] == prompts.identity("v1.1.0")
        assert context["lesson_memory"] == [] and context["battle_summary"] is None
    assert not result["memory_archive"] and result["summary_prompt_identity"] is None


def test_historical_ex026_prepare_receipt_still_verifies():
    receipt = (
        ROOT / ".pokechamp-data/io-battle-only/ex026-preflight/prepare/result.json"
    )
    assert read_stage(receipt, "prepare", current=False)["passed"]


def test_old_cloud_selection_and_unknown_field_fail_before_dispatch(
    scene, tmp_path, monkeypatch
):
    from integration.pokechamp.improved_io import cloud_gate
    from integration.pokechamp.improved_io.backend import FixedBackend

    calls = []

    def chat(**kwargs):
        calls.append(kwargs)
        return dict(
            model="glm-5.3-flash",
            done=True,
            done_reason="stop",
            message=dict(
                content="Local historical selection.\n"
                + json.dumps(scene["request"]["legal_actions"][0])
            ),
        )

    class Local(FixedBackend):
        def __init__(self, **kwargs):
            super().__init__(
                environ={"OLLAMA_API_KEY": "local-fixture"},
                trace_sink=kwargs["trace_sink"],
                client_factory=lambda **_: SimpleNamespace(chat=chat),
            )

    monkeypatch.setattr(cloud_gate.cli, "_load_cloud_credential", lambda: None)
    monkeypatch.setattr(cloud_gate, "FixedBackend", Local)
    item = dict(
        id="legacy",
        role="self_action",
        profile=PROFILE,
        study_root="unused",
        cohort="c0",
        context=scene,
        output_path=str(tmp_path / "legacy.json"),
    )
    assert cloud_gate.call(item, "unused", 1)["valid"]
    assert calls[0]["messages"][0]["content"] == prompts.assemble()
    item.update(prompts.selection())
    item["context"] = {**scene, "undocumented": {"nested": True}}
    item["output_path"] = str(tmp_path / "undocumented.json")
    rejected = cloud_gate.call(item, "unused", 1)
    assert not rejected["valid"] and rejected["category"] == "input_contract"
    assert rejected["input_field_errors"] == ["$.undocumented (undocumented field)"]
    assert (
        b.read_sealed(Path(item["output_path"]))["input_field_errors"]
        == rejected["input_field_errors"]
    )
    assert len(calls) == 1


def test_optional_definition_deletions_and_type_mismatch_always_report_paths(scene):
    value = copy.deepcopy(scene)
    value["current_observation"]["self_team"][0]["effects"] = {"CONFUSION": False}
    with pytest.raises(ValueError, match=r"effects.CONFUSION.*integer"):
        prompts.check_fields(value)
    guide = prompts.catalog()
    guide["definitions"]["entry"]["properties"]["ko_chance_given_hit"][
        "description"
    ] = ""
    with pytest.raises(ValueError, match=r"ko_chance_given_hit.*missing description"):
        prompts.check_fields(scene, guide)


def test_pinned_tera_type_tuple_limit_is_explicit(scene):
    from poke_env.environment.pokemon import Pokemon

    from integration.pokechamp.improved_io.state import public_mon

    mon = Pokemon(gen=9, species="gliscor")
    mon.terastallize("water")
    public = public_mon(mon)
    assert public["types"] == ["WATER", "FLYING"]
    assert public["tera_type"] == "WATER" and mon.type_2 is None
    value = copy.deepcopy(scene)
    value["current_observation"]["opponent_confirmed"] = [public]
    prompts.check_fields(value)
    meaning = prompts.catalog()["definitions"]["public_mon"]["properties"]["types"][
        "description"
    ]
    assert "retain the original secondary type" in meaning
    assert "not proof of two current effective types" in meaning


@pytest.mark.parametrize("version", prompts.VERSIONS)
def test_final_battle_checker_uses_sealed_selection_and_rejects_drift(
    scene, tmp_path, monkeypatch, version
):
    from integration.pokechamp.improved_io import study

    directory = tmp_path / "benchmark"
    directory.mkdir()
    (directory / "plan.json").write_text("{}")
    (directory / "batches").mkdir()
    b.seal_json(directory / "batches/one.json", dict(maximum_battles=1))
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    event = dict(
        event_type="llm_call",
        timestamp_utc="2026-09-09T00:00:01+00:00",
        user_prompt=json.dumps(scene),
        system_prompt=prompts.assemble(scene, version=version),
        request=dict(
            call_role="self_action", battle_prompt_identity=prompts.identity(version)
        ),
    )
    events = [
        dict(
            event_type="protocol_in",
            protocol="|start",
            timestamp_utc="2026-09-09T00:00:00+00:00",
        ),
        event,
    ]

    def save():
        (bundle / "events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n"
        )

    plan = dict(
        config=dict(profile=PROFILE),
        execution=dict(battle_concurrency=1, evidence=prompts.selection(version)),
    )
    attempts = [
        dict(
            eligible=True,
            slot=dict(condition_id="B"),
            actors=dict(p1=dict(bundle=str(bundle))),
        )
    ]
    monkeypatch.setattr(study.b, "verify_plan", lambda _: plan)
    monkeypatch.setattr(study.b, "load_attempts", lambda _: attempts)
    monkeypatch.setattr(study.b, "validate_attempts", lambda *_: None)
    monkeypatch.setattr(study.b, "verify_bundle", lambda _: dict(valid=True))
    monkeypatch.setattr(study, "check_ports", lambda _: None)
    save()
    assert study.battle_checks(directory, planned=1, expected_concurrency=1)["passed"]
    event["system_prompt"] += "tampered"
    save()
    result = study.battle_checks(directory, planned=1, expected_concurrency=1)
    assert not result["passed"] and result["isolation_errors"] == [
        "battle-only action prompt drift"
    ]
    event["system_prompt"] = prompts.assemble(scene, version=version)
    event["request"].pop("battle_prompt_identity")
    save()
    result = study.battle_checks(directory, planned=1, expected_concurrency=1)
    assert result["passed"] == (version == "v1.0.0")
