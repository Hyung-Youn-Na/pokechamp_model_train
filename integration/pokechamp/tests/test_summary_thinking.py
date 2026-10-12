"""EX-022 independent evidence, role routing, identical prompts, and worker lifecycle."""

import copy
import json
import logging
import shutil
import subprocess
import threading
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.calibration import Trace
from integration.pokechamp.cloud import CloudConfigurationError
from integration.pokechamp.improved_io.backend import FixedBackend
from integration.pokechamp.improved_io.calculations import ability_effects, field_for
from integration.pokechamp.improved_io.calculator import CalculationError
from integration.pokechamp.improved_io.protocol import live_effects, observed_state
from integration.pokechamp.improved_io.state import hypotheses, public_revelations
from integration.pokechamp.summary_diagnostics.oracle import verify_annotations, verify_reference
from integration.pokechamp.summary_diagnostics.prepare import (
    THINKING_PROFILE,
    prepare,
    schedule,
    verify,
)
from integration.pokechamp.summary_diagnostics.report import aggregate, report
from integration.pokechamp.summary_diagnostics.runner import clock, fake_text, run


def event(text, seq=1):
    return {"event_seq": seq, "protocol": text, "showdown_turn": 99}


@pytest.mark.parametrize("effort", ["low", "high", "max"])
def test_role_thinking_wire_record_matches_and_returns_to_action_low(effort):
    trace, wires = Trace(), []
    context = dict(
        identity=dict(battle_id="b", actor_id="p1", showdown_turn=1),
        condition_id="C",
        source_event_ids=[1],
        request=dict(kind="turn_action", can_tera=False, legal_actions=[{"move": "splash"}]),
    )

    def chat(**kwargs):
        wires.append(kwargs)
        text = (
            'A local action.\n{"move":"splash"}'
            if backend.role == "self_action"
            else fake_text(context)
        )
        return dict(
            model="glm-5.3-flash",
            message=dict(content=text),
            prompt_eval_count=3,
            eval_count=4,
            done_reason="stop",
        )

    backend = FixedBackend(
        summary_thinking_effort=effort,
        environ={"OLLAMA_API_KEY": "fake"},
        client_factory=lambda **_: SimpleNamespace(chat=chat),
        trace_sink=trace,
    )
    backend.input_context = context
    for role in ("summary", "self_action", "summary_rollup", "self_action"):
        backend.role = role
        backend.get_LLM_action("system", "user", backend.model, json_format=False, think="max")
        expected = effort if role != "self_action" else "low"
        assert wires[-1]["think"] == trace.payload["request"]["thinking_effort"] == expected
        assert backend.call_records[-1]["thinking_effort"] == expected


@pytest.mark.parametrize("invalid", [None, True, "medium", "HIGH", 1, ""])
def test_bad_effort_rejected_before_client_creation(invalid):
    def forbidden(**_):
        pytest.fail("client creation should not occur")

    with pytest.raises(CloudConfigurationError):
        FixedBackend(summary_thinking_effort=invalid, client_factory=forbidden)


def test_mutated_bad_effort_rejected_before_network():
    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "fake"}, client_factory=lambda **_: SimpleNamespace()
    )
    backend.summary_thinking_effort = "invalid"
    with pytest.raises(CloudConfigurationError):
        backend.get_LLM_action("s", "u", backend.model)


def test_weather_start_refresh_end_and_side_layers():
    data = [
        event(
            "|start\n|turn|3\n|-weather|SunnyDay|[from] ability: Drought\n"
            "|-sidestart|p2: x|Spikes\n|-sidestart|p1: y|move: Stealth Rock\n|turn|4\n"
            "|-weather|SunnyDay|[upkeep]\n|-sidestart|p2: x|Spikes"
        )
    ]
    state = observed_state(data)
    assert state["weather"]["SunnyDay"]["observed_start_turn"] == 3
    assert state["weather"]["SunnyDay"]["last_update_turn"] == 4
    assert state["sides"]["p2"]["Spikes"]["layers"] == 2
    assert state["sides"]["p1"]["Stealth Rock"]["observed_start_turn"] == 3
    state = observed_state(data + [event("|-weather|none\n|-sideend|p2: x|Spikes", 2)])
    assert state["weather"] == {} and state["sides"]["p2"] == {}


@pytest.mark.parametrize("mode", ["switch", "immune", "failed_recast", "silent_expiry"])
def test_future_sight_slot_lifetime_from_pinned_simulator(mode):
    rows = json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("state_lifecycle.cjs"))], text=True
        )
    )
    fixture = next(r for r in rows if r["mode"] == mode)
    for i, snapshot in enumerate(fixture["rows"]):
        state = observed_state([event(snapshot["protocol"])])
        assert bool(state["pending_effects"]) == bool(snapshot["pending"])
        if i < 2:
            effect = state["pending_effects"][0]
            assert effect["observed_start_turn"] == 1 and effect["target_slot"] == "p2a"
            assert effect["user"] == "p1: Slowking" and not effect["immediate_damage"]
            if i == 1 and mode != "failed_recast":
                assert effect["current_occupant"] == "p2: " + snapshot["target"]
        else:
            history = state["delayed_history"]
            assert len(history) == 1
            assert history[0]["status"] == (
                "expired_without_public_resolution"
                if mode == "silent_expiry"
                else "resolution_observed"
            )
    if mode == "immune":
        assert fixture["rows"][1]["hp"] == fixture["rows"][2]["hp"]


def test_unknown_delayed_start_and_battle_end():
    state = observed_state([event("|-start|p1a: Slowking|move: Future Sight")])
    assert state["pending_effects"][0]["observed_start_turn"] is None
    assert state["pending_effects"][0]["target_slot"] is None
    state = observed_state(
        [
            event(
                "|turn|7\n|move|p1a: Slowking|Future Sight|p2a: Mew\n"
                "|-start|p1a: Slowking|move: Future Sight\n|win|caster"
            )
        ]
    )
    assert not state["pending_effects"] and state["delayed_history"][0]["status"] == "battle_ended"


def test_parser_counter_and_faint_effects():
    from poke_env.environment.battle import Battle
    from poke_env.environment.effect import Effect

    battle = Battle("futurecounter", "caster", logging.getLogger(__name__), 9)
    for line in (
        "|player|p1|caster||",
        "|player|p2|target||",
        "|switch|p1a: Slowking|Slowking-Galar|393/393",
        "|switch|p2a: Mew|Mew|100/100",
        "|turn|7",
        "|-start|p1a: Slowking|move: Future Sight",
        "|turn|8",
    ):
        battle.parse_message(line.split("|"))
    mon = battle.active_pokemon
    assert mon.effects[Effect.FUTURE_SIGHT] == 1
    assert "FUTURE_SIGHT" not in live_effects(mon, "p1: Slowking", {})
    mon.start_effect("quarkdrivespe")
    mon.faint()
    assert live_effects(mon, "p1: Slowking", {}) == {}
    assert mon.effects  # Raw parser evidence survives.


def test_ended_quark_family_does_not_leave_boosted_stat():
    from poke_env.environment.effect import Effect

    mon = SimpleNamespace(fainted=False, effects={Effect.QUARKDRIVESPE: 0})
    timing = observed_state(
        [event("|turn|1\n|-start|p1a: X|quarkdrivespe\n|-end|p1a: X|Quark Drive|[silent]")]
    )
    assert live_effects(mon, "p1: X", timing) == {}


def test_consumed_item_and_suppressed_ability_never_reappear_from_prior():
    prior = {
        "data": {
            "mew": {
                "spreads": [{"percentage": 100}],
                "items": [{"name": "Leftovers", "percentage": 100}],
                "abilities": [{"name": "Synchronize"}],
                "moves": [],
            }
        }
    }
    mon = dict(species="mew", item=None, ability="", ability_known=True, moves=[])
    guesses = hypotheses(mon, prior)
    assert all(g["item"] == g["ability"] == "" for g in guesses)
    rows = [
        event(
            "|switch|p2a: X|Mew|100/100\n|-ability|p2a: X|Synchronize\n"
            "|-ability|p2a: X|Levitate|[from] move: Skill Swap\n|-endability|p2a: X"
        )
    ]
    assert public_revelations(rows)["p2: X"]["ability"] == ""
    rows.append(event("|switch|p2a: Y|Chansey|100/100\n|switch|p2a: X|Mew|100/100", 2))
    assert public_revelations(rows)["p2: X"]["ability"] == "synchronize"


def test_ambiguous_quark_activation_rejected():
    with pytest.raises(CalculationError, match="ambiguous"):
        ability_effects({"effects": {"QUARKDRIVESPE": 0, "QUARKDRIVESPA": 0}})


def test_field_side_orientation_preserves_layers():
    value = dict(
        weather={},
        field={},
        self_side_conditions={"REFLECT": 7},
        opponent_side_conditions={"SPIKES": 3},
    )
    field = field_for(value)
    assert field["attackerSide"] == {"isReflect": True}
    assert field["defenderSide"] == {"spikes": 3}


@pytest.fixture(scope="module")
def prepared_thinking(tmp_path_factory):
    directory = tmp_path_factory.mktemp("thinking") / "prepared"
    assert prepare(directory, profile=THINKING_PROFILE)["scheduled"] == 72
    return directory


def test_72_schedule_balanced_and_one_prompt_per_scene(prepared_thinking):
    manifest = verify(prepared_thinking)
    rows = manifest["schedule"]
    assert len(rows) == len({r["id"] for r in rows}) == len({r["blind_id"] for r in rows}) == 72
    assert len({r["input"] for r in rows}) == 12
    assert set(Counter((r["scene"], r["condition"]) for r in rows).values()) == {3}
    for repeat in range(3):
        assert set(
            Counter(
                (r["condition"], r["order"] % 2) for r in rows if r["repeat"] == repeat
            ).values()
        ) == {6}
    assert manifest["config"]["thinking"] == ["low", "high"]


@pytest.mark.parametrize(
    "corruption",
    [
        "annotation_turn",
        "annotation_actor",
        "hp",
        "weather_meaning",
        "reference_turn",
        "reference_actor",
        "shared_turn",
        "self_hp",
        "future",
    ],
)
def test_independent_oracle_rejects_corruption(prepared_thinking, corruption):
    raw = b.read_sealed(prepared_thinking / "references/s01.json")
    context = b.read_sealed(prepared_thinking / "inputs/s01.json")["context"]
    damage = next(
        r
        for r in context["harness_annotations"]["event_annotations"]
        if r["ref"] == {"event": 70, "line": 7}
    )
    if corruption in ("annotation_turn", "shared_turn"):
        damage["turn"] = 10
    if corruption in ("reference_turn", "shared_turn"):
        fact = next(f for f in raw["facts"] if f["id"] == "ninetales_hits")
        next(e for e in fact["evidence"] if e["event"] == 70 and e["line"] == 7)["turn"] = 10
    if corruption == "annotation_actor":
        damage["target"] = "p1: Kurama Chakra Mode"
    if corruption == "hp":
        damage["hp_after"]["current"] = 0
    if corruption == "weather_meaning":
        next(
            r for r in context["harness_annotations"]["numeric_state"] if r["path"][1] == "weather"
        )["meaning"] = "activation_turn"
    if corruption == "reference_actor":
        raw["facts"][-1]["evidence"][0]["parts"][2] = "p2a: Slowking"
    if corruption == "self_hp":
        raw["facts"][1]["self_request"]["condition"] = "349/349"
    if corruption == "future":
        raw["source_events"][-1]["event_seq"] = raw["cutoff"]
    with pytest.raises(ValueError):
        verify_reference(raw)
        verify_annotations(context, raw)


def test_72_fake_lifecycle_report_and_wire_effort(prepared_thinking, tmp_path):
    directory = tmp_path / "run"
    shutil.copytree(prepared_thinking, directory)
    first = schedule(THINKING_PROFILE)[0]["id"]
    result = run(directory, fake={first: "format"})
    assert result["scheduled"] == result["submitted"] == result["acquired"] == 72
    assert result["failed"] == result["unconfirmed"] == result["unexecuted"] == 0
    assert report(directory)["scheduled"] == 72
    package = b.read_sealed(directory / "blind.json")
    audit = dict(
        collection_sha256=package["collection_sha256"],
        manifest_sha256=package["manifest_sha256"],
        calls={},
    )
    pids = set()
    for slot in b.read_sealed(directory / "collection.json")["slots"]:
        r = b.read_sealed(directory / "responses" / (slot["id"] + ".json"))
        assert r["trace"]["request"]["thinking_effort"] == slot["condition"]
        pids.add(r["pid"])
    assert len(pids) == 72
    for r in package["responses"]:
        audit["calls"][r["blind_id"]] = dict(
            response_sha256=r["response_sha256"],
            facts={
                f["id"]: dict(retained=False, status="omitted", quote="")
                for f in package["references"][str(r["scene"])]["facts"]
            },
            errors=[],
            factual_claims=1,
            erroneous_claims=0,
        )
    b.seal_json(directory / "test-review.json", audit)
    assert report(directory, directory / "test-review.json")["complete"]
    final = b.read_sealed(directory / "report.json")
    assert final["metrics"]["strata"]["additional"]["contrasts"]["low->high"]["paired_scenes"] == 8
    assert sum(c["format"] for c in final["checks"].values()) == 1
    assert not __import__("multiprocessing").active_children()
    with pytest.raises(ValueError, match="already sealed"):
        run(directory, fake={})


@pytest.mark.parametrize("mode", ["timeout", "restart", "cancel"])
def test_72_halt_cancel_restart_preserves_clock(prepared_thinking, tmp_path, mode):
    directory = tmp_path / "run"
    shutil.copytree(prepared_thinking, directory)
    stop = threading.Event()
    fake = {schedule(THINKING_PROFILE)[0]["id"]: "timeout"} if mode == "timeout" else {}
    thread = None
    if mode == "restart":
        initial = clock(directory, now=1)
    elif mode == "cancel":
        fake = {r["id"]: "hang" for r in schedule(THINKING_PROFILE)}

        def cancel():
            until = time.time() + 15
            while not list((directory / "submitted").glob("*.json")) and time.time() < until:
                time.sleep(0.02)
            stop.set()

        thread = threading.Thread(target=cancel)
        thread.start()
    result = run(
        directory, fake=fake, stop_event=stop, _test_deadlines=(20, 4) if mode == "cancel" else None
    )
    if thread:
        thread.join()
    assert result["reason"] and result["intended"] + result["unexecuted"] == 72
    assert result["submitted"] < 72
    if mode == "restart":
        assert result["cloud_clock"] == initial
    if mode == "cancel":
        assert result["killed"] and result["unconfirmed"] > 0
    first = (directory / "cloud-clock.json").read_bytes()
    assert clock(directory, now=time.time() + 99999)["experiment"] == "EX-022"
    assert (directory / "cloud-clock.json").read_bytes() == first
    with pytest.raises(ValueError, match="halted"):
        run(directory, fake={})
    assert not __import__("multiprocessing").active_children()


def test_missing_repeat_marks_pairs_incomplete():
    slots = [
        dict(r, submitted=True, acquired=True, failed=False, unexecuted=False, unconfirmed=False)
        for r in schedule(THINKING_PROFILE)
    ]
    manifest = dict(
        profile=THINKING_PROFILE,
        scenes=[dict(scene=i, stratum="existing" if i < 4 else "additional") for i in range(12)],
    )
    metrics = aggregate(manifest, dict(slots=slots), {}, {})
    assert metrics["strata"]["existing"]["contrasts"]["low->high"]["missing_pairs"] == 4


def test_missing_tokens_preserved_as_unknown():
    trace = Trace()
    context = dict(
        identity=dict(battle_id="b", actor_id="p1"), condition_id="C", source_event_ids=[1]
    )
    response = dict(model="glm-5.3-flash", message=dict(content=fake_text(context)))
    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "fake"},
        trace_sink=trace,
        client_factory=lambda **_: SimpleNamespace(chat=lambda **kw: response),
    )
    backend.role, backend.input_context = "summary", context
    backend.get_LLM_action("s", "u", backend.model, json_format=False)
    assert trace.payload["response"]["prompt_tokens"] is None
    assert backend.call_records[-1]["completion_tokens"] is None


@pytest.mark.parametrize("maximum", [100, 301, 349, 383, 513])
def test_public_hp_intervals_against_pinned_gethealth(maximum):
    from integration.pokechamp.improved_io.calculations import public_hp_bounds

    script = """
const {Pokemon}=require('./pokemon-showdown/dist/sim/pokemon');
const {Battle}=require('./pokemon-showdown/dist/sim');
const {Format}=require('./pokemon-showdown/dist/sim/dex-formats');
const b=new Battle({format:new Format({name:'HP',mod:'gen9',gameType:'singles',ruleset:[]})});
b.setPlayer('p1',{name:'a',team:[{species:'Mew',moves:['Splash']}]});
b.setPlayer('p2',{name:'b',team:[{species:'Mew',moves:['Splash']}]});
const p=b.p2.active[0],rows=[];p.maxhp=Number(process.argv[1]);
for(p.hp=1;p.hp<=p.maxhp;p.hp++)rows.push([p.hp,p.getHealth().shared]);
process.stdout.write(JSON.stringify(rows));b.destroy();
"""
    rows = json.loads(
        subprocess.check_output(
            ["node", "-e", script, str(maximum)], text=True, cwd=b.WORKSPACE_ROOT
        )
    )
    for percent in {int(shared.split("/")[0]) for _, shared in rows}:
        hp = [n for n, shared in rows if shared == f"{percent}/100"]
        assert public_hp_bounds(percent, 100, maximum) == (min(hp), max(hp))


def test_hypothetical_public_hp_unsupported_scale_fails():
    from integration.pokechamp.improved_io.calculations import public_hp_bounds

    with pytest.raises(CalculationError):
        public_hp_bounds(45, 48, 300)


def test_terrain_replacement_and_field_removal():
    state = observed_state(
        [
            event(
                "|turn|4\n|-fieldstart|move: Electric Terrain\n"
                "|turn|5\n|-fieldstart|move: Grassy Terrain\n"
                "|-fieldstart|move: Trick Room\n|-fieldend|move: Trick Room"
            )
        ]
    )
    assert set(state["field"]) == {"Grassy Terrain"}
    assert state["field"]["Grassy Terrain"]["observed_start_turn"] == 5


def test_observation_corruption_and_missing_annotation_fail(prepared_thinking):
    from integration.pokechamp.summary_diagnostics.oracle import verify_observation

    context = b.read_sealed(prepared_thinking / "inputs/s01.json")["context"]
    raw = b.read_sealed(prepared_thinking / "references/s01.json")
    original = copy.deepcopy(context)
    context["current_observation"]["self_team"][0]["condition"] = "349/349"
    with pytest.raises(ValueError, match="request field"):
        verify_observation(context, raw)
    context = original
    context["harness_annotations"]["event_annotations"].pop()
    with pytest.raises(ValueError, match="coverage"):
        verify_observation(context, raw)


def test_real_compute_exchanges_actor_and_defender_sides():
    from integration.pokechamp.improved_io.calculations import compute

    value = b.read_sealed(
        b.WORKSPACE_ROOT / ".pokechamp-data/io-improvement/ex020/offline-v8/IO-C02.json"
    )
    observation = value["current_observation"]
    observation["self_side_conditions"] = {"REFLECT": 7}
    observation["opponent_side_conditions"] = {"SPIKES": 3}
    calls = []

    class Capture:
        def calculate(self, identity, scenarios):
            calls.extend(scenarios)
            return {"identity": identity, "entries": []}

    compute(value, Capture())
    outgoing = [r for r in calls if r["scenario_id"].startswith("out-")]
    incoming = [r for r in calls if r["scenario_id"].startswith("in-")]
    assert outgoing and incoming
    assert all(
        r["field"]["attackerSide"] == {"isReflect": True}
        and r["field"]["defenderSide"] == {"spikes": 3}
        for r in outgoing
    )
    assert all(
        r["field"]["attackerSide"] == {"spikes": 3}
        and r["field"]["defenderSide"] == {"isReflect": True}
        for r in incoming
    )
    assert {r["attacker"]["name"] for r in incoming} == {r["defender"]["name"] for r in outgoing}


@pytest.mark.parametrize("ability", ["Supreme Overlord", "Quark Drive", "Protosynthesis"])
def test_public_activation_holder_survives_switch_and_suppression(ability):
    from poke_env.environment.pokemon import Pokemon

    from integration.pokechamp.improved_io.state import public_mon

    token = ability.lower().replace(" ", "")
    rows = [event(f"|switch|p2a: K|Kingambit|100/100\n|-activate|p2a: K|ability: {ability}")]
    facts = public_revelations(rows)
    mon = Pokemon(gen=9, species="kingambit")
    assert mon.ability is None  # The parser-only fallback cannot supply this public fact.
    observed = public_mon(mon, {"ident": "p2: K", **facts["p2: K"]})
    assert (observed["ability"], observed["ability_known"]) == (token, True)
    rows.append(event("|-endability|p2a: K", 2))
    assert public_revelations(rows)["p2: K"]["ability"] == ""
    rows.append(event("|switch|p2a: M|Mew|100/100\n|switch|p2a: K|Kingambit|100/100", 3))
    assert public_revelations(rows)["p2: K"]["ability"] == token
    # A temporary gained ability must not become the natural ability on reentry.
    rows[0] = event(
        f"|switch|p2a: K|Mew|100/100\n|-ability|p2a: K|{ability}|[from] move: Skill Swap\n"
        f"|-activate|p2a: K|ability: {ability}"
    )
    assert public_revelations(rows)["p2: K"]["ability"] is None


@pytest.mark.parametrize("corruption", ["missing", "wrong_actor", "shared_false_annotation"])
def test_independent_public_ability_oracle(prepared_thinking, corruption):
    from integration.pokechamp.summary_diagnostics.oracle import verify_observation

    raw = b.read_sealed(prepared_thinking / "references/s01.json")
    context = b.read_sealed(prepared_thinking / "inputs/s01.json")["context"]
    king = next(
        m
        for m in context["current_observation"]["opponent_confirmed"]
        if m["species"] == "kingambit"
    )
    assert (king["ability"], king["ability_known"]) == ("supremeoverlord", True)
    assert verify_observation(context, raw)
    if corruption == "wrong_actor":
        king["ability"] = "quarkdrive"
    else:
        king["ability"], king["ability_known"] = None, False
    if corruption == "shared_false_annotation":
        raw["facts"].append({"id": "corrupt_ability", "expected": "Kingambit ability is unknown."})
        context["harness_annotations"]["ability_note"] = "Kingambit ability is unknown."
    with pytest.raises(ValueError, match="public ability"):
        verify_observation(context, raw)


def test_thinking_invalid_report_preserves_cost_and_blocks_recovery(
    prepared_thinking, tmp_path, monkeypatch
):
    directory = tmp_path / "invalid"
    shutil.copytree(prepared_thinking, directory)
    run(directory, fake={})
    evidence = {
        "manifest_sha256": b.digest(directory / "manifest.json"),
        "collection_sha256": b.digest(directory / "collection.json"),
        "reviewed_draft": 2,
        "review_pending": 70,
        "cause": "공개 Supreme Overlord가 unknown으로 전달됨.",
        "affected_scenes": [{"scene": 1, "name": "fixture", "affected_inputs": ["s01.json"]}],
    }
    b.seal_json(directory / "failure.json", evidence)
    b.seal_json(
        directory / "halt.json",
        {
            "reason": "input_transform_error",
            "evidence": "failure.json",
            "evidence_sha256": b.digest(directory / "failure.json"),
        },
    )
    # Corrected semantic validation rejects old inputs; forensic reports still
    # verify hashes and sealed invalidation provenance, without claiming validity.
    from integration.pokechamp.summary_diagnostics import oracle

    def reject(*_):
        raise ValueError("public ability old input")

    monkeypatch.setattr(oracle, "verify_public_abilities", reject)
    with pytest.raises(ValueError, match="public ability"):
        verify(directory, current=False)
    assert report(directory)["status"] == "invalidated"
    final = b.read_sealed(directory / "report.json")
    assert not final["complete"] and final["effect_estimates"] is None
    assert final["counts"]["acquired"] == 72
    assert final["invalid_input_exposure_scheduled"] == {"low": 3, "high": 3}
    assert final["reviewed_draft_invalid"] == 2 and final["review_pending"] == 70
    assert all(v["acquired"] == 36 for v in final["cost"].values())
    markdown = (directory / "report.md").read_text()
    assert (
        "EX-022" in markdown
        and "Supreme Overlord" in markdown
        and "EX-021 중단 보고서" not in markdown
    )
    assert "2건 초안" in markdown and "70건의 채점" in markdown
    before = b.digest(directory / "report-seal.json")
    assert report(directory)["status"] == "invalidated"
    assert b.digest(directory / "report-seal.json") == before
    with pytest.raises(ValueError, match="cannot restore"):
        report(directory, directory / "fake-review.json")
    with pytest.raises(ValueError, match="halted"):
        run(directory, fake={})
    (directory / "failure.json").unlink()
    (directory / "failure.json.sha256").unlink()
    b.seal_json(directory / "failure.json", {**evidence, "cause": "changed"})
    with pytest.raises(ValueError, match="halt evidence"):
        report(directory)
