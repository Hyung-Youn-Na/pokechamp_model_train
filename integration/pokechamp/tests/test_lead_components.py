"""C-040 independent lead treatments; no external provider or new battle run."""

# ruff: noqa: F811 -- imported pytest fixtures
import asyncio
import copy
import itertools
import json
import random
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
import ollama
import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp import effects
from integration.pokechamp import lead_rules as rules
from integration.pokechamp import team_preview as lead
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.effects import delivery as legacy
from integration.pokechamp.improved_io import battle_prompts, live_delivery
from integration.pokechamp.improved_io.backend import FixedBackend
from integration.pokechamp.providers import ZaiChatClient, provider_config
from integration.pokechamp.tests.test_team_preview import (
    context,
    events,
    fixture,  # noqa: F401
    player,
    protocol,
)

COMBINATIONS = list(itertools.product(rules.STRATEGIES, rules.RULES))


def resign(full):
    full["identity"].pop("input_sha256")
    full["identity"]["input_sha256"] = lead.digest(full)
    return full


def test_extraction_and_known_rules(tmp_path):
    subprocess.run(
        ["node", str(rules.ASSETS / "extract.cjs"), str(tmp_path)], check=True
    )
    for name in ("dex-v2.json", "provenance.json", "LICENSE"):
        assert (tmp_path / name).read_bytes() == (rules.ASSETS / name).read_bytes()
    dex, provenance = rules.asset()
    assert provenance["source_commit"] == effects.identity()["source_commit"]
    assert provenance["extractor_sha256"] == rules.sha(
        (rules.ASSETS / "extract.cjs").read_bytes()
    )
    s, m = dex["species"], dex["moves"]
    assert s["zapdos"]["non_tera_type_multipliers"]["Ice"] == 2
    assert s["zapdos"]["non_tera_type_multipliers"]["Ground"] == 0
    assert s["tinkaton"]["non_tera_type_multipliers"]["Fire"] == 2
    assert s["ceruledge"]["type_status_immunities"] == ["brn"]
    assert s["zapdos"]["type_status_immunities"] == ["par"]
    assert s["tinkaton"]["type_status_immunities"] == ["psn", "tox"]
    assert s["kyurem"]["type_status_immunities"] == ["frz"]
    assert set(s["ditto"]["possible_abilities"]) == {"limber", "imposter"}
    assert "magicbounce" in s["hatterene"]["possible_abilities"]
    assert "moldbreaker" in s["tinkaton"]["possible_abilities"]
    assert (
        "defog" not in s["zapdos"]["possible_related_moves"]
    )  # Gen9 origin, not past gen
    assert "uturn" in s["zapdos"]["possible_related_moves"]
    assert "chillyreception" in s["slowkinggalar"]["possible_related_moves"]
    assert "grassyglide" in s["rillaboom"]["possible_related_moves"]
    assert all("batonpass" not in row["possible_related_moves"] for row in s.values())
    assert all("shedtail" not in row["possible_related_moves"] for row in s.values())
    assert m["hurricane"]["base_accuracy"] == 70
    assert m["thunder"]["base_accuracy"] == 70
    assert m["fakeout"]["priority"] == 3
    assert m["grassyglide"]["priority"] == 0  # conditional priority is in desc
    assert m["uturn"]["flags"]["contact"] == 1
    assert m["stealthrock"]["flags"]["reflectable"] == 1


def test_public_cosmetic_forms_are_known_without_hidden_set_lookup(fixture):
    full = context(fixture)
    for name in ("Gastrodon-East", "Floette-Blue", "Deerling-Winter"):
        full["opponent_preview"][0]["details"] = name
        wire = rules.augment(resign(full))
        key = effects.normalize(name)
        assert wire["lead_rules"]["opponent_entries"][0]["form_candidates"] == [key]
        assert wire["lead_rules"]["species_facts"][key]["base_types"]
        assert wire["opponent_preview"][0]["details"] == name


def test_four_combinations_independent_and_legacy_bytes(fixture):
    full = context(fixture)
    ds = {c: rules.build(full, rules.prompt_identity(*c)) for c in COMBINATIONS}
    old = legacy.build(full, kind="lead")
    assert ds["legacy-v1", "effects-v1"].system_prompt == old.system_prompt
    assert ds["legacy-v1", "effects-v1"].user_json == old.user_json
    for r in rules.RULES:
        assert ds["legacy-v1", r].user_json == ds["matchup-v2", r].user_json
    for s in rules.STRATEGIES:
        plain, enriched = (ds[s, r].system_prompt for r in rules.RULES)
        assert (
            enriched
            == plain + "\n---\n\n" + (rules.ASSETS / "rules-guide.txt").read_text()
        )
    assert full == context(fixture)
    for selected, delivery in ds.items():
        link = rules.validate(
            full,
            delivery,
            delivery.system_prompt,
            delivery.user_json,
            rules.prompt_identity(*selected),
        )
        assert link["lead_strategy"]["version"] == selected[0]
        assert link["lead_rules"]["version"] == selected[1]
        for damaged in [
            replace(delivery, user_json=delivery.user_json + " "),
            replace(delivery, system_prompt=delivery.system_prompt + " "),
        ]:
            with pytest.raises(ValueError):
                rules.validate(
                    full,
                    damaged,
                    damaged.system_prompt,
                    damaged.user_json,
                    rules.prompt_identity(*selected),
                )


def test_slot_moves_never_backfilled_and_possibilities_not_ownership(fixture):
    full = context(fixture, "p2")
    zapdos = next(p for p in full["self_team"] if p["species"] == "zapdos")
    zapdos["moves"] = ["roost"]
    out = rules.augment(resign(full))
    facts = out["lead_rules"]
    assert facts["self_slots"][zapdos["lead_slot"] - 1]["supplied_move_refs"] == [
        "roost"
    ]
    assert "uturn" in facts["species_facts"]["zapdos"]["possible_related_moves"]
    zapdos.pop("moves")
    out = rules.augment(resign(full))
    assert (
        out["lead_rules"]["self_slots"][zapdos["lead_slot"] - 1]["supplied_move_refs"]
        == []
    )
    assert "moves" not in out["self_team"][zapdos["lead_slot"] - 1]
    full["opponent_preview"][0]["details"] = "Hatterene, F"
    full["opponent_preview"][1]["details"] = "Zamazenta-*"
    out = rules.augment(resign(full))
    p = out["lead_rules"]["opponent_entries"][1]
    assert p["form_candidates"] == ["zamazenta", "zamazentacrowned"]
    assert p["form_ambiguous"]
    assert "base_types" not in p["common_facts"]
    assert out["opponent_preview"][0] == full["opponent_preview"][0]
    assert "ability" not in out["opponent_preview"][0]
    assert "magicbounce" in out["effect_reference"]["abilities"]
    assert "moldbreaker" in out["effect_reference"]["abilities"]
    assert (
        out["effect_reference"]["abilities"]["magicbounce"]
        == effects.build({"ability": "Magic Bounce"})["abilities"]["magicbounce"]
    )
    # Each desc has a single authoritative kind/ID position, even when both teams refer to it.
    assert len(out["effect_reference"]["moves"]) == len(
        set(out["effect_reference"]["moves"])
    )


@pytest.mark.parametrize("role", ["p1", "p2"])
def test_private_opponent_and_future_changes_leave_enrichment_unchanged(fixture, role):
    original = context(fixture, role)
    changed = copy.deepcopy(fixture)
    other = 1 if role == "p1" else 0
    changed[0][other] = "SECRET OPPONENT TEAM NEVER READ"
    changed[1]["requests"][other]["side"]["pokemon"][0].update(
        moves=["splash"], ability="Shadow Tag", item="Choice Scarf", teraType="Water"
    )
    assert rules.augment(context(changed, role)) == rules.augment(original)
    public = protocol(fixture[1], role)
    public[-1]["protocol"] += (
        "\n|start\n|turn|9\n|move|p2: Secret|Surf|p1: Target\n|win|Secret"
    )
    full = lead.build_input(
        fixture[0][int(role[-1]) - 1],
        public,
        battle_id="fixture-" + role,
        actor_id=role,
        decision_seq=1,
    )
    assert rules.augment(full) == rules.augment(original)


@pytest.mark.parametrize("strategy,rule", COMBINATIONS)
@pytest.mark.parametrize("role", ["p1", "p2"])
@pytest.mark.parametrize("slot", range(1, 7))
def test_each_slot_both_sides_rng_and_send(
    tmp_path, fixture, strategy, rule, role, slot
):
    actor, battle, recorder, sent = player(
        tmp_path, fixture, role, content=json.dumps({"lead_slot": slot})
    )
    actor.llm.team_preview_prompt_identity = rules.prompt_identity(strategy, rule)
    random.seed(4321)
    original = actor.random_teampreview(battle)
    after = random.getstate()
    random.seed(4321)
    asyncio.run(actor._handle_battle_request(battle, from_teampreview_request=True))
    assert random.getstate() == after
    assert actor.sent == [
        (lead.command_for_lead(original, slot, list(range(1, 7))), battle.battle_tag)
    ]
    assert len(sent) == 1
    recorded = events(recorder)
    call = next(e for e in recorded if e["event_type"] == "llm_call")
    snapshots = {
        e["event_seq"]: e for e in recorded if e["event_type"] == "input_snapshot"
    }
    assert live_delivery.original_for_call(call, snapshots)["identity"]["side"] == role
    assert call["request"]["team_preview_prompt_identity"] == rules.prompt_identity(
        strategy, rule
    )


@pytest.mark.parametrize("strategy,rule", COMBINATIONS)
def test_prepare_verify_independent_seals(tmp_path, strategy, rule):
    root = tmp_path / "prepared"
    value = study.prepare(root, lead_strategy=strategy, lead_rules=rule)
    assert study.verify_prepared(root) == value
    assert value["team_preview_prompt_identity"] == rules.prompt_identity(
        strategy, rule
    )
    assert value["execution"]["evidence"][
        "battle_prompt_identity"
    ] == battle_prompts.identity("v1.4.0")
    prompts = b.read_sealed(root / "prompts.json")
    from integration.pokechamp.observation.delivery import asset as official_asset
    assert prompts["battle_system"] == official_asset("b2-prompt.txt")
    assert prompts["lead_system"] == rules.system_prompt(strategy, rule)
    damaged = copy.deepcopy(value)
    damaged["lead_rules"] = "invalid"
    (root / "plan.json").unlink()
    (root / "plan.json.sha256").unlink()
    b.seal_json(root / "plan.json", damaged)
    with pytest.raises(ValueError):
        study.verify_prepared(root)


@pytest.mark.parametrize("ex", ["EX-039", "EX-040", "EX-041", "EX-042"])
def test_historical_experiment_options_rejected_before_writes(tmp_path, ex):
    with pytest.raises(ValueError, match="historical"):
        study.prepare(tmp_path / "new", experiment_id=ex, lead_strategy="matchup-v2")
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("provider", ["ollama", "zai"])
@pytest.mark.parametrize("strategy,rule", COMBINATIONS)
def test_mock_http_ledger_snapshot_and_following_b2(
    tmp_path, fixture, provider, strategy, rule
):
    environment = dict(
        POKECHAMP_PROVIDER=provider,
        OLLAMA_API_KEY="unit-key",
        ZAI_API_KEY="unit-key",
        ZAI_BASE_URL="https://zai.example.test/v4",
    )
    root = tmp_path / "prepared"
    with patch.object(
        study, "prepared_provider", lambda **_: provider_config(environment)
    ):
        prepared = study.prepare(root, lead_strategy=strategy, lead_rules=rule,
                                 observation_backend="legacy-poke-env")
    row = prepared["schedule"][0]
    role = next(
        "p" + str(i + 1)
        for i, s in enumerate(row["actor_settings"])
        if s["team_preview_policy"] == "llm_lead"
    )
    actor_id = "/".join((prepared["experiment_id"], row["slot_id"] + "-a1", role))
    actor, battle, recorder, _ = player(tmp_path / "actor", fixture, role)
    wire = []
    content = ['{"lead_slot":3}']

    def handler(request):
        wire.append(json.loads(request.content))
        if provider == "ollama":
            response = dict(
                model="glm-5.3-flash",
                message=dict(role="assistant", content=content[0], thinking="mock"),
                done=True,
                done_reason="stop",
                prompt_eval_count=17,
                eval_count=5,
            )
        else:
            response = dict(
                model="glm-5.3-flash",
                choices=[
                    dict(
                        index=0,
                        finish_reason="stop",
                        message=dict(
                            role="assistant",
                            content=content[0],
                            reasoning_content="mock",
                        ),
                    )
                ],
                usage=dict(prompt_tokens=17, completion_tokens=5, total_tokens=22),
            )
        return httpx.Response(200, json=response)

    def factory(**kw):
        if provider == "zai":
            return ZaiChatClient(
                **kw, api_key="unit-key", transport=httpx.MockTransport(handler)
            )
        return ollama.Client(**kw, transport=httpx.MockTransport(handler))

    llm = FixedBackend(
        environ={
            **environment,
            "POKECHAMP_LEAD_STUDY_ROOT": str(root),
            "POKECHAMP_IO_ACTOR": actor_id,
        },
        trace_sink=recorder,
        client_factory=factory,
    )
    actor.llm = llm
    llm.experiment_policy = study.policy_selection()
    llm.team_preview_prompt_identity = prepared["team_preview_prompt_identity"]
    llm.battle_prompt_identity = battle_prompts.identity("v1.3.0")
    asyncio.run(actor._handle_battle_request(battle, from_teampreview_request=True))
    recorded = events(recorder)
    call = next(e for e in recorded if e["event_type"] == "llm_call")
    snapshots = {
        e["event_seq"]: e for e in recorded if e["event_type"] == "input_snapshot"
    }
    full = live_delivery.original_for_call(call, snapshots)
    assert wire[0]["messages"] == [
        dict(role="system", content=call["system_prompt"]),
        dict(role="user", content=call["user_prompt"]),
    ]
    intent = b.read_sealed(call["request"]["request_intent"])
    assert (
        intent["payload"]["request"]["delivery_identity"]
        == call["request"]["delivery_identity"]
    )
    assert intent["payload"]["user_prompt"] == call["user_prompt"]
    assert actor.sent[0][0].startswith("/team 3")
    llm.role = "team_preview"
    with pytest.raises(ValueError, match="wire mismatch"):
        llm.get_LLM_action(
            call["system_prompt"] + " ",
            call["user_prompt"],
            llm.model,
            temperature=0,
            json_format=False,
        )
    assert len(wire) == 1
    llm.role = "self_action"
    # Reuse an archived first-turn observation, not a new game or model evaluation.
    source = Path(
        "/workspace/.pokechamp-data/experiments/ex041-zai/battles/b01-r1-s0-a1-p1/events.jsonl"
    )
    following = next(
        e["original_input"]
        for e in map(json.loads, source.open())
        if e["event_type"] == "input_snapshot"
        and e["original_input"]["identity"]["input_version"] == "calculator-input-v2"
    )
    following = copy.deepcopy(following)
    following["identity"]["decision_seq"] = 2
    content[0] = "mock action\n" + json.dumps(following["request"]["legal_actions"][0])
    llm.input_context = following
    llm.io_profile = "io-battle-only-v1"
    llm.role = "self_action"
    llm.runtime_identity = study.runtime_identity()
    llm.delivery = live_delivery.build(following, version="v1.3.0")
    recorder.begin_decision(
        showdown_turn=1, decision_kind="turn_action", battle_state={}
    )
    llm.get_LLM_action(
        llm.delivery.system_prompt,
        llm.delivery.user_json,
        llm.model,
        temperature=0,
        json_format=False,
    )
    assert wire[1]["messages"] == [
        dict(role="system", content=llm.delivery.system_prompt),
        dict(role="user", content=llm.delivery.user_json),
    ]
    assert wire[1]["messages"][0]["content"] == legacy.asset("b2-prompt.txt")
    assert {k: v for k, v in wire[0].items() if k != "messages"} == {
        k: v for k, v in wire[1].items() if k != "messages"
    }
    assert llm.team_preview_prompt_identity == rules.prompt_identity(strategy, rule)
    assert "lead_rules" not in json.loads(llm.delivery.user_json)
    assert full["identity"]["input_version"] == "team-preview-v1"
    assert study.shared.usage(root)["responses"] == 2
    retained = events(recorder)
    retained_calls = [e for e in retained if e["event_type"] == "llm_call"]
    b.seal_json(
        tmp_path / "mock-http-evidence.json",
        dict(
            passed=True,
            provider=provider,
            strategy=strategy,
            rules=rule,
            external_model_calls=0,
            http_bodies=wire,
            events=retained,
            intents=[
                b.read_sealed(e["request"]["request_intent"]) for e in retained_calls
            ],
            responses=[
                b.read_sealed(
                    Path(e["request"]["request_intent"]).with_name(
                        Path(e["request"]["request_intent"]).name.replace(
                            "intent-", "response-"
                        )
                    )
                )
                for e in retained_calls
            ],
            checks=[
                "wire_snapshot_intent_response",
                "lead_command",
                "tamper_before_http",
                "following_b2_prompt_options_unchanged",
            ],
        ),
    )
    llm.client._client.close()
