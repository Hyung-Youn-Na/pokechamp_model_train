"""D-057: exact rules, information boundaries and actual pre-provider validation."""

# ruff: noqa: F811 -- pytest fixtures are imported and requested by parameter name.

import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from integration.pokechamp import effects
from integration.pokechamp import team_preview as lead
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.effects import delivery
from integration.pokechamp.improved_io import battle_prompts as bp
from integration.pokechamp.improved_io import live_delivery
from integration.pokechamp.observability.render import _decision_card, _group_decisions
from integration.pokechamp.tests.test_b2_live import call, setup  # noqa: F401
from integration.pokechamp.tests.test_team_preview import (  # noqa: F401
    backend,
    context,
    events,
    fixture,
)


@pytest.fixture(scope="module")
def original():
    path = Path(
        "/workspace/.pokechamp-data/experiments/ex041-zai/battles/b01-r1-s0-a1-p1/events.jsonl"
    )
    for event in map(json.loads, path.open()):
        if event["event_type"] == "input_snapshot":
            return event["original_input"]
    raise AssertionError("missing source snapshot")


def test_exact_pinned_dex_extraction_license_and_all_descriptions(tmp_path):
    subprocess.run(["node", str(effects.ASSETS / "extract.cjs"), str(tmp_path)], check=True)
    for name in ("gen9-effects-v1.json", "provenance.json", "LICENSE"):
        assert (tmp_path / name).read_bytes() == (effects.ASSETS / name).read_bytes()
    asset = json.loads((tmp_path / "gen9-effects-v1.json").read_text())
    assert [len(asset[k]) for k in effects.KINDS] == [537, 314, 936]
    # Sensitive activation/exception/consumption/lifetime clauses must be verbatim.
    for kind, key, clause in (
        ("abilities", "protosynthesis", "it ends when this Pokemon is no longer active"),
        ("abilities", "quarkdrive", "If multiple stats are tied"),
        ("items", "boosterenergy", "Single use."),
        ("moves", "protect", "Fails if the user moves last this turn."),
        ("moves", "futuresight", "two turns after this move is used"),
    ):
        assert clause in asset[kind][key]["desc"]


def test_reference_dedup_independent_requests_and_no_recursive_expansion():
    value = {
        "self_team": [{"item": "Booster Energy"}, {"item": "boosterenergy"}],
        "opponent_hypotheses": [{"item": "Booster Energy"}],
        "calculation_bundle": {"scenarios": [{"item": "boosterenergy"}] * 20},
    }
    original = copy.deepcopy(value)
    table = effects.build(value)
    assert set(table["items"]) == {"boosterenergy"}
    assert table["abilities"] == table["moves"] == {}  # prose mentions two abilities
    assert effects.build({"item": "boosterenergy"}) == table
    assert value == original
    assert effects.augment(value)["effect_reference"] == table


def test_condition_and_history_references_do_not_establish_current_possession():
    value = dict(
        item=None,
        ability="",
        protocol_state=dict(
            ended_ability_effects={"p2: foe": {"protosynthesis": True}},
            field={"Electric Terrain": {}},
            sides={"p1": {"Stealth Rock": {}}},
        ),
        recent_events=[
            dict(
                protocol="|-enditem|p2a: foe|Booster Energy\n"
                "|move|p2a: foe|Protect|p2a: foe\n"
                "|-damage|p1a: me|99/100|[from] ability: Rough Skin"
            )
        ],
    )
    table = effects.build(value)
    assert set(table["abilities"]) == {"protosynthesis", "roughskin"}
    assert set(table["items"]) == {"boosterenergy"}
    assert set(table["moves"]) == {"protect", "electricterrain", "stealthrock"}
    assert value["item"] is None and value["ability"] == ""


@pytest.mark.parametrize("value", ["", None, "unknown_item", "UNKNOWN", "none", "noability"])
def test_states_not_dictionary_entries(value):
    assert all(not v for v in effects.build({"item": value, "ability": value}).values())


@pytest.mark.parametrize(
    "value,path",
    [
        ({"ability": "not-a-real-ability"}, "$.ability"),
        (
            {"recent_events": [{"protocol": "|-enditem|p2a: x|nonexistent-item"}]},
            "$.recent_events[0].protocol:line1",
        ),
        (
            {"calculation_bundle": {"scenarios": [{"move": {"name": "not-a-move"}}]}},
            "$.calculation_bundle.scenarios[0].move.name",
        ),
    ],
)
def test_unknown_actual_reference_fails_with_path_and_id(value, path):
    with pytest.raises(effects.EffectReferenceError) as exc:
        effects.build(value)
    assert exc.value.path == path and exc.value.reference_id
    assert exc.value.category == "input_contract"


def test_own_request_stable_move_id_not_dynamic_display_or_nickname():
    value = {
        "recent_events": [
            {
                "protocol": "|request|"
                + json.dumps(
                    {
                        "active": [
                            {
                                "moves": [
                                    {
                                        "id": "hiddenpower",
                                        "move": "Hidden Power Fire 60",
                                        "pp": 4,
                                        "maxpp": 8,
                                    }
                                ]
                            }
                        ]
                    }
                )
            }
        ],
        "opponent_preview": [{"details": "Protect, L100"}],
        "nickname": "Leftovers",
        "protocol": "|c|user|[from] ability: Levitate",
    }
    table = effects.build(value)
    assert set(table["moves"]) == {"hiddenpower"}
    assert not table["abilities"] and not table["items"]


def test_lead_structure_private_boundary_and_future_prefix(fixture):
    full = context(fixture)
    old = copy.deepcopy(full)
    new = delivery.build(full, kind="lead")
    wire = json.loads(new.user_json)
    assert full == old
    own_refs = effects.build({"self_team": full["self_team"]})
    assert wire["effect_reference"] == own_refs
    assert wire["opponent_preview"] == full["opponent_preview"]
    # A private field, even if valid Dex data, is outside the public schema.
    for field, value in [("moves", ["spore"]), ("ability", "levitate"), ("item", "leftovers")]:
        bad = copy.deepcopy(full)
        bad["opponent_preview"][0][field] = value
        bad["identity"].pop("input_sha256")
        bad["identity"]["input_sha256"] = lead.digest(bad)
        with pytest.raises(bp.FieldCoverageError, match="opponent_preview"):
            delivery.build(bad, kind="lead")


@pytest.mark.parametrize("kind", ["battle", "b2"])
def test_actual_battle_fields_and_wrong_types_are_closed(original, kind):
    new = delivery.build(original, kind=kind)
    wire = json.loads(new.user_json)
    guide = (
        bp.catalog("v1.3.0") if kind == "battle" else json.loads(delivery.asset("b2-fields.json"))
    )
    bp.check_fields(wire, guide)
    bad = copy.deepcopy(wire)
    bad["current_observation"]["self_team"][0]["new_private_field"] = 1
    with pytest.raises(bp.FieldCoverageError, match="new_private_field"):
        bp.check_fields(bad, guide)
    bad = copy.deepcopy(wire)
    bad["effect_reference"]["items"][next(iter(bad["effect_reference"]["items"]))]["desc"] = []
    with pytest.raises(bp.FieldCoverageError, match="expected string"):
        bp.check_fields(bad, guide)
    if kind == "b2":
        bad = copy.deepcopy(wire)
        bad["calculation_bundle"]["scenarios"][0]["opponent_condition"]["hp"] = "bad"
        with pytest.raises(bp.FieldCoverageError, match="expected integer"):
            bp.check_fields(bad, guide)
    # Repeating scenarios changes data size, not the description dictionary.
    data = copy.deepcopy(wire)
    dictionary = data.pop("effect_reference")
    if kind == "b2":
        data["calculation_bundle"]["scenarios"] *= 4
        assert effects.build(data) == dictionary


def test_shared_types_rendered_once_and_scenario_rules():
    text = delivery.asset("b2-prompt.txt")
    assert text.count("Shared type: scenario_result\n") == 1
    assert text.count("scenario_result.scenario_state.items[].item ") == 1
    assert "same_as_variant" in text and "hypothesis_index" in text
    assert "Never multiply or add an effect again" in text
    assert bp.DEFAULT_VERSION == "v1.3.0"


@pytest.mark.parametrize("change", ["system", "user", "original", "dictionary", "identity"])
def test_enriched_b2_tamper_rejected_before_provider(setup, change):
    full, llm, recorder, sent = setup
    llm.battle_prompt_identity = bp.identity("v1.3.0")
    llm.delivery = delivery.build(full, kind="b2")
    if change == "system":
        llm.delivery = replace(llm.delivery, system_prompt=llm.delivery.system_prompt + " ")
    elif change == "user":
        llm.delivery = replace(llm.delivery, user_json=llm.delivery.user_json + " ")
    elif change == "original":
        full["identity"]["state_hash"] = "bad"
    elif change == "dictionary":
        wire = json.loads(llm.delivery.user_json)
        wire["effect_reference"]["items"].clear()
        llm.delivery = replace(llm.delivery, user_json=json.dumps(wire))
    else:
        llm.battle_prompt_identity = bp.identity("v1.2.0")
    with pytest.raises(ValueError):
        call(llm)
    assert sent == []


@pytest.mark.parametrize("kind", ["battle", "b2"])
def test_enriched_wire_snapshot_and_viewer(setup, kind):
    full, llm, recorder, sent = setup
    llm.battle_prompt_identity = bp.identity("v1.3.0")
    if kind == "battle":
        llm.experiment_policy = {}
        llm.client.chat = lambda **kw: (
            sent.append(kw)
            or dict(
                model="glm-5.3-flash",
                message=dict(
                    content="A local fixture action.\n"
                    + json.dumps(full["request"]["legal_actions"][0])
                ),
                done=True,
                done_reason="stop",
            )
        )
    llm.delivery = delivery.build(full, kind=kind)
    call(llm)
    assert sent[0]["messages"][1]["content"] == llm.delivery.user_json
    recorded = events(recorder)
    snapshots = {e["event_seq"]: e for e in recorded if e["event_type"] == "input_snapshot"}
    event = next(e for e in recorded if e["event_type"] == "llm_call")
    assert live_delivery.original_for_call(event, snapshots) == full
    assert event["request"]["delivery_identity"]["effect_reference_identity"] == effects.identity()
    decisions, _ = _group_decisions(recorded)
    html = _decision_card(decisions[-1])
    assert "effect_reference" in html and "gen9-effects-v1" in html and "검증용 원본 입력" in html


def test_enriched_lead_actual_wire_and_tamper(fixture, tmp_path):
    from integration.pokechamp.observability.recorder import (
        BattleBundleConfig,
        BattleRecorder,
    )

    recorder = BattleRecorder.create(
        tmp_path,
        BattleBundleConfig(
            experiment_id="unit",
            battle_id="unit",
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
        ),
    )
    recorder.begin_decision(showdown_turn=0, decision_kind="team_preview", battle_state={})
    llm, sent = backend(recorder)
    llm.team_preview_prompt_identity = lead.prompt_identity("v1.1.0")
    full = context(fixture)
    assert llm.select_lead(full, 0) == 3
    call = next(e for e in events(recorder) if e["event_type"] == "llm_call")
    snapshots = {e["event_seq"]: e for e in events(recorder) if e["event_type"] == "input_snapshot"}
    assert live_delivery.original_for_call(call, snapshots) == full
    assert "effect_reference" in sent[0]["messages"][1]["content"]
    from integration.pokechamp.team_preview_report import check_lead_input

    selected = lead.prompt_identity("v1.1.0")
    check_lead_input(call, snapshots, full, selected)
    corrupted = {**call, "user_prompt": call["user_prompt"] + " altered"}
    with pytest.raises(ValueError):
        check_lead_input(corrupted, snapshots, full, selected)
    with pytest.raises(ValueError):
        check_lead_input(call, snapshots, full, lead.prompt_identity("v1.0.0"))
    llm.team_preview_prompt_identity = {**llm.team_preview_prompt_identity, "sha256": "bad"}
    with pytest.raises(ValueError, match="identity"):
        llm.select_lead(full, 0)
    assert len(sent) == 1


def test_new_prepare_seals_prompts_but_cannot_inherit_old_execution(tmp_path):
    root = tmp_path / "new"
    value = study.prepare(root, transport="cloud")
    assert study.verify_prepared(root) == value
    assert value["execution"]["evidence"]["battle_prompt_version"] == "v1.4.0"
    assert value["team_preview_prompt_identity"]["version"] == "v1.2.0"
    assert value["paid_budget"] is None and study.execution_protocol(value)["experiment"] is None
    assert not value["execution_authorized"]
    with pytest.raises(ValueError, match="no registered experiment"):
        study.register_execution(root, approval_record=tmp_path / "old-approval")
    with pytest.raises(Exception, match="no execution approval"):
        study.reserve(root, "actor", {})
    assert not (root / "cloud-clock.json").exists()


@pytest.mark.parametrize("ex", ["EX-039", "EX-040", "EX-041"])
def test_explicit_historical_prepare_keeps_old_prompt_versions(tmp_path, ex):
    root = tmp_path / ex
    value = study.prepare(root, experiment_id=ex)
    assert study.verify_prepared(root) == value
    assert value["execution"]["evidence"]["battle_prompt_version"] == "v1.2.0"
    assert value["team_preview_prompt_identity"] == lead.prompt_identity()
    assert "preparation_version" not in value


def test_new_b_gate_persists_original_and_sends_effect_dictionary(original, tmp_path, monkeypatch):
    from integration.pokechamp.improved_io import cloud_gate
    from integration.pokechamp.improved_io.backend import FixedBackend

    sent = []

    def make_backend(**kwargs):
        from types import SimpleNamespace

        return FixedBackend(
            environ={"OLLAMA_API_KEY": "local-fixture"},
            trace_sink=kwargs["trace_sink"],
            client_factory=lambda **kw: SimpleNamespace(
                chat=lambda **kw: (
                    sent.append(kw)
                    or dict(
                        model="glm-5.3-flash",
                        message=dict(
                            content="A local action.\n"
                            + json.dumps(original["request"]["legal_actions"][0])
                        ),
                        done=True,
                        done_reason="stop",
                    )
                )
            ),
        )

    monkeypatch.setattr(cloud_gate, "FixedBackend", make_backend)
    monkeypatch.setattr(cloud_gate.cli, "_load_cloud_credential", lambda: None)
    target = tmp_path / "gate.json"
    item = dict(
        id="local-gate",
        profile="io-battle-only-v1",
        role="self_action",
        context=original,
        study_root=str(tmp_path),
        cohort="local",
        output_path=str(target),
        **bp.selection("v1.3.0"),
    )
    row = cloud_gate.call(item, "unused-socket", None)
    assert row["valid"] and row["category"] is None
    assert json.loads(sent[0]["messages"][1]["content"])["effect_reference"]
    assert Path(str(target) + ".input-snapshot.json").exists()
    assert row["input_snapshot"]["original_input"] == original


def test_missing_description_and_punctuation_only_id_are_not_silently_omitted(monkeypatch):
    asset, provenance = effects._asset()
    broken = copy.deepcopy(asset)
    broken["items"]["leftovers"]["desc"] = ""
    monkeypatch.setattr(effects, "_asset", lambda: (broken, provenance))
    for value in ("leftovers", "???"):
        with pytest.raises(effects.EffectReferenceError):
            effects.build({"item": value})


def test_lead_failed_reference_records_path_before_model(fixture, tmp_path, monkeypatch):
    import asyncio

    from integration.pokechamp.tests.test_team_preview import player

    actor, battle, recorder, sent = player(tmp_path, fixture)
    actor.llm.team_preview_prompt_identity = lead.prompt_identity("v1.1.0")
    original_builder = lead.build_input

    def invalid(*args, **kwargs):
        value = original_builder(*args, **kwargs)
        value["self_team"][0]["item"] = "not-a-real-item"
        value["identity"].pop("input_sha256")
        value["identity"]["input_sha256"] = lead.digest(value)
        return value

    monkeypatch.setattr(lead, "build_input", invalid)
    with pytest.raises(Exception, match="team_preview"):
        asyncio.run(actor._handle_battle_request(battle, from_teampreview_request=True))
    assert sent == []
    result = next(e for e in events(recorder) if e["event_type"] == "decision_result")
    error = result["validation"]["team_preview"]["input_error"]
    assert error == dict(path="$.self_team[0].item", kind="items", reference_id="not-a-real-item")


def test_trace_prompt_metadata_cannot_disagree_with_enriched_strings(setup):
    full, llm, recorder, _ = setup
    llm.battle_prompt_identity = bp.identity("v1.3.0")
    llm.delivery = delivery.build(full, kind="b2")
    call(llm)
    recorded = events(recorder)
    snapshots = {e["event_seq"]: e for e in recorded if e["event_type"] == "input_snapshot"}
    event = next(e for e in recorded if e["event_type"] == "llm_call")
    event["request"]["battle_prompt_identity"] = bp.identity("v1.2.0")
    with pytest.raises(ValueError, match="linkage"):
        live_delivery.original_for_call(event, snapshots)


def test_old_runtime_does_not_depend_on_new_effect_assets(monkeypatch):
    from integration.pokechamp.improved_io.inputfix32 import (
        runtime_identity,
        verify_runtime,
    )

    old = bp.identity("v1.2.0")
    original_identity = bp.identity

    def identity(version="v1.0.0"):
        assert version != "v1.3.0", "historical request inspected new assets"
        return original_identity(version)

    monkeypatch.setattr(bp, "identity", identity)
    assert verify_runtime({**study.policy_selection(), **runtime_identity()}, prompt_identity=old)


@pytest.mark.parametrize(
    "prompt",
    [
        {"battle_prompt_identity": {"version": "v1.3.0"}},
        {"team_preview_prompt_identity": {"version": "v1.1.0"}, "call_role": "team_preview"},
    ],
)
def test_new_trace_requires_original_link_even_if_user_json_parses(prompt):
    with pytest.raises(ValueError, match="missing original delivery linkage"):
        live_delivery.original_for_call({"request": prompt, "user_prompt": "{}"}, {})


def test_pinned_public_activation_arguments_and_bracket_tags():
    table = effects.build(
        {
            "recent_events": [
                {
                    "protocol": "\n".join(
                        [
                            "|-activate|p2a: foe|move: Skill Swap|Levitate|Pressure|[of] p1a: me",
                            "|-activate|p2a: foe|move: Poltergeist|Life Orb",
                            "|-activate|p2a: foe|ability: Forewarn|Earthquake|[of] p1a: me",
                            "|-activate|p1a: me|item: Leppa Berry|Protect|[consumed]",
                            "|-enditem|p2a: foe|Sitrus Berry|[from] stealeat|[move] Bug Bite",
                            "|-singlemove|p2a: foe|Grudge",
                            "|-terastallize|p2a: foe|Psychic",
                        ]
                    )
                }
            ]
        }
    )
    assert set(table["items"]) == {"lifeorb", "leppaberry", "sitrusberry"}
    assert set(table["abilities"]) == {"levitate", "pressure", "forewarn"}
    assert set(table["moves"]) == {
        "skillswap",
        "poltergeist",
        "earthquake",
        "protect",
        "bugbite",
        "grudge",
    }
    with pytest.raises(effects.EffectReferenceError, match="undefined-ability"):
        effects.build(
            {"protocol": "|-activate|p2a: foe|move: Skill Swap|undefined-ability|Pressure"}
        )
