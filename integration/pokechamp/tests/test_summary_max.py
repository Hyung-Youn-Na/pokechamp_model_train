"""D-028: actual SDK serialization, source semantics, fixed memory and diagnostics."""

import json
import logging
import subprocess
from pathlib import Path

import pytest

from integration.pokechamp.improved_io.state import public_mon, public_revelations
from integration.pokechamp.summary_diagnostics.oracle import (
    raw_index,
    verify_public_abilities,
)


def test_pinned_drought_weather_source_is_public_on_named_holder(monkeypatch):
    from poke_env.environment.battle import Battle

    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.constants import POKECHAMP_ROOT

    monkeypatch.chdir(POKECHAMP_ROOT)

    event = json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("weather_ability.cjs"))],
            text=True,
        )
    )
    assert "|-weather|SunnyDay|[from] ability: Drought|[of] p2a: Sun Fox" in event["protocol"]
    battle = Battle("battle-gen9ou-weather", "observer", logging.getLogger("test"), gen=9)
    battle._format = "gen9ou"
    install_identity_adapter()
    for line in event["protocol"].splitlines():
        parts = line.split("|")
        if len(parts) > 1 and parts[1] not in ("", "t:", "split"):
            battle.parse_message(parts)
    assert battle.opponent_active_pokemon.ability is None
    facts = public_revelations([event])
    value = public_mon(
        battle.opponent_active_pokemon, {"ident": "p2: Sun Fox", **facts["p2: Sun Fox"]}
    )
    assert value["ability"] == "drought" and value["ability_known"] is True
    context = {"current_observation": {"opponent_confirmed": [value]}}
    reference = {
        "identity": {"battle_id": "b", "actor_id": "p1"},
        "source_events": [event],
    }
    verify_public_abilities(context, raw_index(reference))
    value.update(ability=None, ability_known=False)
    with pytest.raises(ValueError, match="ability"):
        verify_public_abilities(context, raw_index(reference))


def test_weather_upkeep_or_missing_holder_cannot_reveal_an_ability():
    rows = [
        {
            "protocol": "|-weather|SunnyDay|[upkeep]\n"
            "|-weather|SunnyDay|[from] ability: Drought\n"
            "|-weather|SunnyDay|[from] move: Sunny Day|[of] p2a: Mew"
        }
    ]
    assert public_revelations(rows) == {}


@pytest.mark.parametrize("effort", ["low", "max"])
def test_actual_sdk_serialization_and_role_switch(effort):
    import httpx

    from integration.pokechamp.calibration import Trace
    from integration.pokechamp.summary_diagnostics.compat import DiagnosticBackend, DiagnosticClient
    from integration.pokechamp.summary_diagnostics.runner import fake_text

    context = dict(
        identity=dict(battle_id="b", actor_id="p1", showdown_turn=1),
        condition_id="C",
        source_event_ids=[1],
        request=dict(kind="turn_action", can_tera=False, legal_actions=[{"move": "splash"}]),
    )
    trace = Trace()

    def respond(_):
        content = (
            'A local action.\n{"move":"splash"}'
            if backend.role == "self_action"
            else fake_text(context)
        )
        return httpx.Response(
            200,
            json=dict(
                model="glm-5.3-flash",
                message=dict(role="assistant", content=content),
                prompt_eval_count=3,
                eval_count=4,
                done_reason="stop",
            ),
        )

    backend = DiagnosticBackend(
        summary_thinking_effort=effort,
        environ={"OLLAMA_API_KEY": "fake"},
        trace_sink=trace,
        client_factory=lambda **kwargs: DiagnosticClient(
            **kwargs, transport=httpx.MockTransport(respond)
        ),
    )
    backend.input_context = context
    for role in ("summary", "summary_rollup", "self_action", "summary"):
        backend.role = role
        backend.get_LLM_action(
            "system", "user", backend.model, temperature=0, seed=100, json_format=False
        )
        body = trace.payload["serialized_request"]
        assert (
            body["think"]
            == trace.payload["request"]["thinking_effort"]
            == ("low" if role == "self_action" else effort)
        )
        assert body["options"] == dict(temperature=0, num_predict=131072, seed=100)
        assert body["messages"] == [
            dict(role="system", content="system"),
            dict(role="user", content="user"),
        ]
        assert trace.payload["request"]["call_role"] == role
    backend.client._client.close()


def test_adapter_low_matches_unmodified_sdk_body():
    import httpx
    import ollama

    from integration.pokechamp.summary_diagnostics.compat import DiagnosticClient

    bodies = []

    def respond(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}})

    args = dict(
        model="glm-5.3-flash",
        messages=[dict(role="user", content="literal 한국어")],
        stream=False,
        think="low",
        format=None,
        options=dict(temperature=0, num_predict=131072, seed=100),
    )
    for cls in (ollama.Client, DiagnosticClient):
        client = cls(
            host="https://ollama.com",
            timeout=300,
            transport=httpx.MockTransport(respond),
        )
        client.chat(**args)
        client._client.close()

    assert bodies[0] == bodies[1]


@pytest.fixture(scope="module")
def max_prepared(tmp_path_factory):
    from integration.pokechamp.summary_diagnostics.prepare import MAX_PROFILE, prepare

    path = tmp_path_factory.mktemp("max-preflight") / "prepared"
    assert prepare(path, profile=MAX_PROFILE)["scheduled"] == 132
    return path


def test_max_corpus_frozen_memory_and_counterbalance(max_prepared):
    from collections import Counter

    from integration.pokechamp import benchmark as b
    from integration.pokechamp.summary_diagnostics.prepare import verify

    manifest = verify(max_prepared)
    assert Counter(s["kind"] for s in manifest["scenes"]) == dict(first=8, followup=10, rollup=4)
    assert len(manifest["fixed_memory_files"]) == 14
    assert (
        sum(len(b.read_sealed(max_prepared / s["reference"])["facts"]) for s in manifest["scenes"])
        == 171
    )
    for repeat in range(3):
        slots = [s for s in manifest["schedule"] if s["repeat"] == repeat]
        assert Counter(s["condition"] for s in slots[::2]) == dict(low=11, max=11)
        assert all(a["input"] == z["input"] for a, z in zip(slots[::2], slots[1::2]))


def test_battle_weighting_and_incomplete_pairs(max_prepared):
    from integration.pokechamp import benchmark as b
    from integration.pokechamp.summary_diagnostics.maximum_report import METRICS, aggregate_maximum
    from integration.pokechamp.summary_diagnostics.runner import inventory

    manifest = b.read_sealed(max_prepared / "manifest.json")
    collection = inventory(max_prepared, manifest)
    checked = {}
    for slot in collection["slots"]:
        error = int(slot["scene"] == 0 and slot["condition"] == "low")
        checked[slot["blind_id"]] = dict(
            **{k: error for k in METRICS},
            retained=0,
            required=1,
            incorrect_facts=error,
            omitted_facts=0,
            factual_claims=1,
            erroneous_claims=error,
            unsupported=0,
            contradictions=0,
        )
    metrics = aggregate_maximum(manifest, collection, checked, {})
    group = manifest["scenes"][0]["battle_group"]
    n = sum(s["battle_group"] == group for s in manifest["scenes"])
    assert metrics["overall"]["max_minus_low"]["primary"] == pytest.approx(-1 / n / 6)
    assert metrics["per_input"]["0"]["max_minus_low"]["primary"] == -1
    slot = next(s for s in collection["slots"] if s["scene"] == 0)
    del checked[slot["blind_id"]]
    partial = aggregate_maximum(manifest, collection, checked, {})
    assert partial["per_input"]["0"]["max_minus_low"]["primary"] is None
    assert partial["overall"]["missing_battles"] == 1


@pytest.mark.parametrize("mutation", ["config", "role", "hash", "future", "memory", "prompt"])
def test_max_rejects_configuration_and_input_drift(max_prepared, tmp_path, mutation):
    from integration.pokechamp import benchmark as b
    from integration.pokechamp.summary_diagnostics.prepare import sha_text, verify
    from integration.pokechamp.tests.test_summary_diagnostics import clone

    path = clone(max_prepared, tmp_path)
    manifest = b.read_sealed(path / "manifest.json")
    if mutation == "config":
        manifest["config"]["thinking"] = ["low", "high"]
    else:
        filename = "inputs/s01.json"
        value = b.read_sealed(path / filename)
        if mutation == "role":
            value["role"] = "summary_rollup"
        elif mutation == "hash":
            value["user_prompt"] += " "
        elif mutation == "future":
            value["context"]["source_events"][-1]["event_seq"] = 999999
        elif mutation == "memory":
            value["context"]["previous_summary"] = "foreign previous memory"
        elif mutation == "prompt":
            value["summary_prompt_identity"]["version"] = "v1.1.1"
        if mutation in ("future", "memory"):
            value["user_prompt"] = json.dumps(value["context"], ensure_ascii=False)
            value["user_sha256"] = sha_text(value["user_prompt"])
        (path / filename).unlink()
        b.seal_json(path / filename, value)
        manifest["files"][filename] = b.digest(path / filename)
    (path / "manifest.json").unlink()
    b.seal_json(path / "manifest.json", manifest)
    with pytest.raises(ValueError):
        verify(path)


def test_max_fake_132_wire_blind_review_report_and_no_replacement(max_prepared, tmp_path):
    from integration.pokechamp import benchmark as b
    from integration.pokechamp.summary_diagnostics.maximum_report import (
        check_max_review,
    )
    from integration.pokechamp.summary_diagnostics.prepare import MAX_PROFILE, schedule
    from integration.pokechamp.summary_diagnostics.report import report
    from integration.pokechamp.summary_diagnostics.runner import inventory, run
    from integration.pokechamp.tests.test_summary_diagnostics import clone

    directory = clone(max_prepared, tmp_path)
    result = run(directory, fake={schedule(MAX_PROFILE)[0]["id"]: "format"})
    assert result["acquired"] == result["submitted"] == result["response_record"] == 132
    assert result["reason"] is None and result["failed"] == 0
    rows = [b.read_sealed(p) for p in (directory / "responses").glob("*.json")]
    assert len({r["pid"] for r in rows}) == 132
    assert all(r["trace"]["serialized_request"]["think"] in ("low", "max") for r in rows)
    collection = b.read_sealed(directory / "collection.json")
    assert not any(collection["broker"]["active_at_close"].values())
    assert report(directory)["acquired"] == 132
    package = b.read_sealed(directory / "blind.json")
    assert all(
        set(r) == {"blind_id", "scene", "text", "response_sha256"} for r in package["responses"]
    )
    review = {k: package[k] for k in ("manifest_sha256", "collection_sha256")}
    review["calls"] = {}
    for row in package["responses"]:
        facts = package["references"][str(row["scene"])]["facts"]
        review["calls"][row["blind_id"]] = dict(
            response_sha256=row["response_sha256"],
            facts={
                f["id"]: dict(
                    status="omitted",
                    retained=False,
                    quote="",
                    evidence=f["evidence"],
                    explanation="Fake response has no required factual content.",
                )
                for f in facts
            },
            errors=[],
            factual_claims=1,
            erroneous_claims=0,
            notes="Synthetic aggregation fixture only.",
        )
    checked = check_max_review(package, review)
    assert sum(c["format"] for c in checked.values()) == 1
    b.seal_json(directory / "test-review.json", review)
    assert report(directory, directory / "test-review.json")["complete"]
    final = b.read_sealed(directory / "report.json")
    assert final["metrics"]["overall"]["paired_complete_battles"] == 6
    assert final["metrics"]["overall"]["max_minus_low"]["primary"] == 0
    assert final["metrics"]["cost"]["max"]["finish_reasons"] == {"stop": 66}
    with pytest.raises(ValueError, match="already sealed"):
        run(directory, fake={})
    damaged = directory / "responses" / (rows[0]["id"] + ".json")
    original_bytes = damaged.read_bytes()
    damaged.write_text("corrupt")
    observation = inventory(directory, b.read_sealed(directory / "manifest.json"))
    assert observation["response_record"] == 132 and observation["failed"] == 1
    assert observation["acquired"] == 131
    damaged.write_bytes(original_bytes)
    assert inventory(directory, b.read_sealed(directory / "manifest.json"))["acquired"] == 132


@pytest.mark.parametrize("mode", ["timeout", "restart", "cancel"])
def test_max_provider_stop_and_owned_cleanup(max_prepared, tmp_path, mode):
    import threading
    import time

    from integration.pokechamp import benchmark as b
    from integration.pokechamp.summary_diagnostics.prepare import MAX_PROFILE, schedule
    from integration.pokechamp.summary_diagnostics.report import report
    from integration.pokechamp.summary_diagnostics.runner import clock, run
    from integration.pokechamp.tests.test_summary_diagnostics import clone

    directory = clone(max_prepared, tmp_path)
    if mode == "restart":
        first = clock(directory, now=1)
        result = run(directory, fake={})
        assert result["cloud_clock"] == first and result["submitted"] == 0
    elif mode == "cancel":
        stop = threading.Event()

        def cancel():
            until = time.time() + 20
            while not list((directory / "submitted").glob("*.json")) and time.time() < until:
                time.sleep(0.02)
            stop.set()

        thread = threading.Thread(target=cancel)
        thread.start()
        result = run(
            directory,
            fake={s["id"]: "hang" for s in schedule(MAX_PROFILE)},
            stop_event=stop,
            _test_deadlines=(20, 6),
        )
        thread.join()
        assert result["killed"] and result["unconfirmed"] > 0
    else:
        result = run(directory, fake={schedule(MAX_PROFILE)[0]["id"]: "timeout"})
        assert result["response_record"] == result["intended"] and result["failed"] >= 1
    assert result["reason"] is not None and result["submitted"] < 132
    assert result["intended"] + result["unexecuted"] == 132
    assert not __import__("multiprocessing").active_children()
    with pytest.raises(ValueError, match="halted"):
        run(directory, fake={})
    assert not report(directory)["complete"]
    assert b.read_sealed(directory / "report.json")["effect_estimates"] is None


def test_sdk_max_enum_rejection_and_adapter_invalid_rejection_before_http():
    import httpx
    import ollama
    from pydantic import ValidationError

    from integration.pokechamp.cloud import CloudConfigurationError
    from integration.pokechamp.summary_diagnostics.compat import DiagnosticClient

    def forbidden(_):
        pytest.fail("invalid input reached HTTP")

    for cls, effort, error in (
        (ollama.Client, "max", ValidationError),
        (DiagnosticClient, "medium", CloudConfigurationError),
    ):
        client = cls(transport=httpx.MockTransport(forbidden))
        with pytest.raises(error):
            client.chat(model="glm-5.3-flash", messages=[], think=effort)
        client._client.close()
