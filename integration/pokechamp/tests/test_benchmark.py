import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp.benchmark import (
    CORE_REPEAT_CONFIG,
    CORE_SMOKE_CONFIG,
    DEFAULT_CONFIG,
    make_schedule,
    read_sealed,
    repeat_budget,
    seal_json,
    summarize_attempts,
)
from integration.pokechamp.benchmark_player import BenchmarkBackend, instrument_minimax


def test_schedule_has_balanced_seats_and_no_confirmation_leak():
    plan = make_schedule(DEFAULT_CONFIG, {})
    assert len(plan["schedule"]) == 40
    assert len(plan["development_teams"]) == 8
    assert len(plan["confirmation_teams"]) == 5
    assert {1, 2} <= set(plan["development_teams"])
    assert not set(plan["development_teams"]) & set(plan["confirmation_teams"])
    assert plan == make_schedule(DEFAULT_CONFIG, {})
    for slot in plan["schedule"]:
        assert set(slot["teams"]) <= set(plan["development_teams"])
        opposite = [
            s
            for s in plan["schedule"]
            if s["pair"] == slot["pair"]
            and s["block_id"] == slot["block_id"]
            and s["swap"] != slot["swap"]
        ]
        assert len(opposite) == 1
        assert opposite[0]["methods"] == slot["methods"][::-1]
        assert opposite[0]["teams"] == slot["teams"]
        assert opposite[0]["battle_seed"] == slot["battle_seed"]


def test_unapproved_main_and_changed_protocol_are_rejected():
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["blocks_per_pair"] = 200
    with pytest.raises(ValueError):
        make_schedule(config, {})


def test_legacy_schedule_matches_ex002_fingerprint():
    schedule = make_schedule(DEFAULT_CONFIG, {})["schedule"]
    assert hashlib.sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest() == (
        "76dbbac1e73554fc799a1616c8bbfb0561789fe809cf56be3879667e639dc30b"
    )


@pytest.mark.parametrize(
    "config,count,blocks",
    [
        (CORE_SMOKE_CONFIG, 8, 1),
        (CORE_REPEAT_CONFIG, 32, 4),
    ],
)
def test_core_profiles_balance_shared_blocks_and_swap_method_team_seat(config, count, blocks):
    value = make_schedule(config, {})
    assert value == make_schedule(json.loads(json.dumps(config)), {})
    assert value["development_teams"] == [1, 2, 5, 6, 9, 11, 12, 13]
    assert value["confirmation_teams"] == [3, 4, 7, 8, 10]
    schedule = value["schedule"]
    assert len(schedule) == count
    assert len({s["slot_id"] for s in schedule}) == count
    expected_pairs = {(m, o) for m in ("io", "minimax") for o in ("abyssal", "one_step")}
    assert {tuple(s["pair"]) for s in schedule} == expected_pairs
    for pair in expected_pairs:
        slots = [s for s in schedule if tuple(s["pair"]) == pair]
        assert len(slots) == blocks * 2
        for slot in slots:
            assert set(slot["teams"]) <= set(value["development_teams"])
            (opposite,) = [
                s for s in slots if s["block_id"] == slot["block_id"] and s["swap"] != slot["swap"]
            ]
            assert opposite["methods"] == slot["methods"][::-1]
            assert opposite["teams"] == slot["teams"]
            assert opposite["teams"][1] != slot["teams"][0]
            peers = [s for s in schedule if s["block_id"] == slot["block_id"]]
            for peer in peers:
                for key in ("teams", "battle_seed", "actor_seeds"):
                    assert peer[key] == slot[key]
    path = Path(__file__).parents[1] / "configs" / f"{config['phase']}.json"
    assert json.loads(path.read_text()) == config


@pytest.mark.parametrize(
    "field,value",
    [
        ("seed", 123),
        ("blocks_per_pair", 2),
        ("retry_transient", 2),
        ("pairs", [["io", "random"]]),
        ("battle_watchdog_seconds", 300),
        ("methods", ["io", "random"]),
        ("extra", True),
    ],
)
def test_core_profile_rejects_protocol_drift(field, value):
    config = copy.deepcopy(CORE_SMOKE_CONFIG)
    config[field] = value
    with pytest.raises(ValueError):
        make_schedule(config, {})


def test_repeat_budget_includes_failed_retry_and_requires_all_core_slots():
    schedule = make_schedule(CORE_SMOKE_CONFIG, {})["schedule"]
    attempts = [{"slot": s, "slot_id": s["slot_id"], "duration_seconds": 100} for s in schedule]
    assert repeat_budget(attempts[:-1], schedule)["fits_with_margin"] is None
    attempts.append({**attempts[0], "duration_seconds": 200})
    budget = repeat_budget(attempts, schedule)
    assert budget["observed_attempt_seconds"] == 1000
    assert budget["estimated_seconds"] == 4000
    assert budget["with_margin_seconds"] == 6000
    assert budget["fits_with_margin"] is True
    for a in attempts:
        a["duration_seconds"] *= 3
    assert repeat_budget(attempts, schedule)["fits_with_margin"] is False


def test_seal_refuses_tamper_and_overwrite(tmp_path):
    path = tmp_path / "fixture.json"
    seal_json(path, {"n": 1})
    assert read_sealed(path) == {"n": 1}
    with pytest.raises(FileExistsError):
        seal_json(path, {"n": 2})
    path.write_text("{}")
    with pytest.raises(RuntimeError, match="integrity"):
        read_sealed(path)


def backend(role):
    obj = object.__new__(BenchmarkBackend)
    obj.role = role
    obj.target = None
    obj.proposed_actions = ""
    return obj


def test_tool_and_score_are_not_validated_as_actions():
    assert backend("tool_choice")._battle_action_valid('{"choice":"minimax"}', None)
    assert backend("state_value")._battle_action_valid('{"score":70}', None)
    for invalid in (
        '{"score":101}',
        '{"score":true}',
        '{"score":"50"}',
        '{"move":"tackle"}',
    ):
        assert not backend("state_value")._battle_action_valid(invalid, None)
    assert not backend("tool_choice")._battle_action_valid('{"choice":"other"}', None)


def test_missing_candidate_contract_fails_closed():
    assert not backend("self_action")._battle_action_valid('{"switch":"Pikachu"}', None)
    assert not backend("opponent_action")._battle_action_valid('{"move":"surf"}', None)


def attempt(slot, outcome, *, category=None, identity="s1"):
    return {
        "slot_id": identity,
        "slot": {"slot_id": identity, "methods": slot},
        "category": category,
        "eligible": category is None,
        "actors": {
            "p1": {"outcome": outcome},
            "p2": {
                "outcome": {
                    "player_won": "player_lost",
                    "player_lost": "player_won",
                    "tied": "tied",
                    "interrupted": "interrupted",
                }[outcome]
            },
        },
    }


def test_denominators_draw_and_failed_retry_cost_not_counted_as_loss():
    attempts = [
        attempt(["io", "abyssal"], "interrupted", category="timeout"),
        attempt(["io", "abyssal"], "player_won"),
        attempt(["io", "one_step"], "tied", identity="s2"),
        attempt(
            ["minimax", "abyssal"],
            "interrupted",
            category="output_contract",
            identity="s3",
        ),
    ]
    report = summarize_attempts(attempts, 40)
    assert report["attempts"] == 4
    assert report["processed_slots"] == 3
    assert report["eligible_slots"] == 2
    assert report["primary_score"] == {"io": 0.75, "minimax": None}
    assert report["pairwise"]["io vs abyssal"]["L"] == 0
    with pytest.raises(RuntimeError, match="duplicate"):
        summarize_attempts(attempts + [attempts[1]], 40)


def test_instrument_pinned_minimax_preserves_temperature_and_assigns_roles():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pokechamp"))
    import poke_env  # noqa: F401
    from pokechamp.llm_player import LLMPlayer

    patched = instrument_minimax(LLMPlayer)
    assert "tool_choice" in patched.__code__.co_consts
    assert "state_value" in patched.__code__.co_consts
    assert 0.6 in patched.__code__.co_consts


def test_request_role_instruction_does_not_force_score_into_action():
    assert "score" in backend("state_value")._json_instruction()
    assert "available action" not in backend("state_value")._json_instruction()


def test_role_specific_wire_request_and_first_error_stays_terminal():
    from integration.pokechamp.cloud import CloudRequestError
    from integration.pokechamp.constants import OLLAMA_MODEL
    from integration.pokechamp.tests.test_cloud import FakeClient, fake_response

    client = FakeClient(fake_response('{"score":73}'))
    instance = BenchmarkBackend(
        environ={"OLLAMA_API_KEY": "fixture"}, client_factory=lambda **_: client
    )
    instance.role = "state_value"
    result = instance.get_LLM_action("system", "state", OLLAMA_MODEL, battle=SimpleNamespace())
    assert json.loads(result[0]) == {"score": 73}
    assert "score" in client.calls[0]["messages"][1]["content"]
    assert client.calls[0]["options"]["num_predict"] == 131072
    assert "num_ctx" not in client.calls[0]["options"]
    client.response = fake_response('{"score":1000}')
    with pytest.raises(CloudRequestError):
        instance.get_LLM_action("system", "state", OLLAMA_MODEL, battle=SimpleNamespace())
    count = len(client.calls)
    with pytest.raises(CloudRequestError):
        instance.get_LLM_action("system", "state", OLLAMA_MODEL, battle=SimpleNamespace())
    assert len(client.calls) == count
    assert instance.inflight is False


def test_resume_attempt_sequence_and_schedule_identity():
    from integration.pokechamp.benchmark import validate_attempts

    plan = make_schedule(DEFAULT_CONFIG, {})
    slot = plan["schedule"][0]
    first = {
        "slot_id": slot["slot_id"],
        "slot": slot,
        "attempt_id": "a1",
        "number": 1,
        "category": "timeout",
    }
    second = {**first, "attempt_id": "a2", "number": 2, "category": None}
    validate_attempts(plan, [first, second])
    with pytest.raises(RuntimeError, match="retry not permitted"):
        validate_attempts(plan, [{**first, "category": "output_contract"}, second])
    with pytest.raises(RuntimeError, match="sealed schedule"):
        validate_attempts(plan, [{**first, "slot": {**slot, "teams": [9, 10]}}])


def test_sealed_success_with_conflicting_protocol_is_rejected(tmp_path):
    from integration.pokechamp.benchmark import check_actor_evidence
    from integration.pokechamp.observability.recorder import (
        BattleBundleConfig,
        BattleRecorder,
    )

    recorder = BattleRecorder.create(
        tmp_path,
        BattleBundleConfig(
            experiment_id="fixture",
            battle_id="p1",
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
        ),
    )
    recorder.record_protocol(">battle-fixture\n|win|loser")
    recorder.finish(outcome="player_won", result={})
    actor = {
        "bundle": str(recorder.bundle_path),
        "outcome": "player_won",
        "player_role": "p1",
    }
    assert check_actor_evidence(actor, "p1", {"p1": "winner", "p2": "loser"}) == "integrity"


def test_benchmark_seed_injection_matches_actual_simulator(tmp_path):
    import os
    import subprocess

    root = Path(__file__).resolve().parents[3]
    record = tmp_path / "seed.jsonl"
    env = dict(os.environ)
    env.pop("OLLAMA_API_KEY", None)
    env.update(
        POKECHAMP_SHOWDOWN_ROOT=str(root / "pokemon-showdown"),
        POKECHAMP_SHOWDOWN_SEED="100,100,100,100",
        POKECHAMP_BENCHMARK_SEED="1,2,3,4",
        POKECHAMP_BENCHMARK_SEED_RECORD=str(record),
    )
    source = (
        "const {BattleStream}=require('./pokemon-showdown/dist/sim/battle-stream');"
        "const s=new BattleStream();"
        "s._writeLine('start', JSON.stringify({formatid:'gen9ou'}));"
        "console.log(s.battle.prngSeed);"
    )
    completed = subprocess.run(
        [
            "node",
            "--require",
            str(root / "integration/pokechamp/showdown_seed_preload.cjs"),
            "-e",
            source,
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "1,2,3,4"
    assert json.loads(record.read_text())["seed"] == "1,2,3,4"


@pytest.mark.parametrize(
    "config,count",
    [
        (None, 40),
        (CORE_SMOKE_CONFIG, 8),
        (CORE_REPEAT_CONFIG, 32),
    ],
)
def test_cli_plan_and_empty_analysis_need_no_provider(tmp_path, monkeypatch, config, count):
    from integration.pokechamp.benchmark import command

    monkeypatch.setenv("POKECHAMP_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    config_path = tmp_path / "config.json" if config else None
    if config_path:
        config_path.write_text(json.dumps(config))
    assert command("plan", "fixture-pilot", config_path) == 0
    sealed = read_sealed(tmp_path / "benchmarks/fixture-pilot/plan.json")
    assert sealed["environment"]["llm"]["request_timeout_seconds"] == 600.0
    assert sealed["environment"]["llm"]["max_output_tokens"] == 131072
    assert sealed["environment"]["llm"]["context_window"] is None
    assert command("analyze", "fixture-pilot") == 0
    report = json.loads((tmp_path / "benchmarks/fixture-pilot/report.json").read_text())
    assert report["scheduled_slots"] == count
    assert report["attempts"] == 0
    assert report["primary_score"] == {"io": None, "minimax": None}
    assert command("plan", "fixture-pilot", config_path) == 2
    assert report["repeat_budget"]["fits_with_margin"] is None
    if config_path:
        assert command("run", "fixture-pilot", config_path) == 2
        assert command("analyze", "fixture-pilot", config_path) == 2


@pytest.mark.parametrize("config", [DEFAULT_CONFIG, CORE_SMOKE_CONFIG, CORE_REPEAT_CONFIG])
def test_runner_resumes_without_repeating_success_or_output_failure(tmp_path, monkeypatch, config):
    from integration.pokechamp import benchmark as module

    plan = make_schedule(config, {})
    plan["experiment_id"] = "fixture"
    state = []
    calls = []
    monkeypatch.setattr(module, "verify_plan", lambda *a, **kw: plan)
    monkeypatch.setattr(module, "load_attempts", lambda *a: list(state))
    monkeypatch.setattr(module.cli, "_server_status", lambda: {"ready": False})
    monkeypatch.setattr(module, "analyze", lambda *a: None)

    def fake_attempt(root, directory, value, slot, number):
        calls.append((slot["slot_id"], number))
        category = None
        if slot == plan["schedule"][0] and number == 1:
            category = "timeout"
        if slot == plan["schedule"][1]:
            category = "output_contract"
        value = {
            "slot": slot,
            "slot_id": slot["slot_id"],
            "number": number,
            "attempt_id": slot["slot_id"] + str(number),
            "category": category,
            "eligible": category is None,
        }
        state.append(value)
        return value

    monkeypatch.setattr(module, "run_attempt", fake_attempt)
    module.run(tmp_path, tmp_path)
    assert len(calls) == len(plan["schedule"]) + 1
    assert len([x for x in calls if x[0] == plan["schedule"][1]["slot_id"]]) == 1
    module.run(tmp_path, tmp_path)
    assert len(calls) == len(plan["schedule"]) + 1


def test_start_failure_does_not_stop_someone_elses_server(tmp_path, monkeypatch):
    from integration.pokechamp import benchmark as module

    def rejected(**kwargs):
        raise RuntimeError("existing server")

    monkeypatch.setattr(module.cli, "_start_server", rejected)
    stops = []
    monkeypatch.setattr(module.cli, "command_server", lambda action: stops.append(action))
    slot = make_schedule(DEFAULT_CONFIG, {})["schedule"][0]
    result = module.run_attempt(
        tmp_path, tmp_path, {"experiment_id": "fixture", "source": {}}, slot, 1
    )
    assert result["category"] == "configuration"
    assert stops == []


def test_peer_cancellation_records_inflight_response_and_prevents_next_call():
    import threading

    from integration.pokechamp.benchmark_player import abort_backend
    from integration.pokechamp.cloud import CloudRequestError
    from integration.pokechamp.constants import OLLAMA_MODEL
    from integration.pokechamp.tests.test_cloud import FakeClient, fake_response

    entered, release = threading.Event(), threading.Event()

    class PendingClient(FakeClient):
        def chat(self, **kwargs):
            entered.set()
            assert release.wait(5)
            return super().chat(**kwargs)

    client = PendingClient(fake_response('{"score":60}'))
    instance = BenchmarkBackend(
        environ={"OLLAMA_API_KEY": "fixture"}, client_factory=lambda **_: client
    )
    instance.role = "state_value"
    errors = []

    def call():
        try:
            instance.get_LLM_action("system", "state", OLLAMA_MODEL, battle=SimpleNamespace())
        except CloudRequestError as error:
            errors.append(error.category)

    thread = threading.Thread(target=call)
    thread.start()
    assert entered.wait(5)
    abort_backend(instance, "peer_failure")
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert errors == ["peer_failure"]
    assert len(instance.call_records) == 1
    assert instance.prompt_tokens == 11
    call()
    assert len(client.calls) == 1
    assert errors == ["peer_failure", "peer_failure"]


def test_nonretryable_failure_cannot_be_hidden_by_peer_timeout():
    from integration.pokechamp.benchmark import failure_category

    assert failure_category("output_contract", "timeout") == "output_contract"
    assert failure_category("timeout", "output_contract") == "output_contract"
    assert failure_category("auth", "action_contract") == "auth"
    assert failure_category("timeout", "peer_failure") == "timeout"


def test_concurrent_cancel_markers_preserve_first_record(tmp_path):
    import threading

    from integration.pokechamp.benchmark import signal_cancel

    workers = [
        threading.Thread(target=signal_cancel, args=(tmp_path, "output_contract", role))
        for role in ("p1", "p2")
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert json.loads((tmp_path / "cancel.json").read_text())["category"] == "output_contract"


def test_two_actor_peer_cancel_seals_both_bundles_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("POKECHAMP_PROVIDER", "ollama")
    import subprocess
    import sys

    from integration.pokechamp import benchmark as module

    if module.cli._server_status()["ready"]:
        pytest.skip("exclusive local Showdown server is currently in use")
    wrapper = tmp_path / "actor_fixture.py"
    wrapper.write_text("""
import json, sys, time
from pathlib import Path
from types import SimpleNamespace
from integration.pokechamp import cli, benchmark_player
from integration.pokechamp.benchmark import worker
role = sys.argv[2]
Original = benchmark_player.BenchmarkBackend
class FixtureBackend(Original):
    def __init__(self, **kwargs):
        outer = self
        class Client:
            def chat(self, **request):
                time.sleep(3 if role == 'p1' else 1)
                target = outer.target
                if role == 'p2':
                    output = {'move': 'not_a_legal_move'}
                elif target.available_moves:
                    output = {'move': target.available_moves[0].id}
                else:
                    output = {'switch': target.available_switches[0].species}
                return SimpleNamespace(model=outer.model,
                    message=SimpleNamespace(content=json.dumps(output), thinking=''),
                    prompt_eval_count=10, eval_count=5, done_reason='stop')
        super().__init__(environ={'OLLAMA_API_KEY':'fixture', 'POKECHAMP_TRANSPORT_POLICY':'legacy-300-v1'},
            client_factory=lambda **_:Client(), **kwargs)
benchmark_player.BenchmarkBackend = FixtureBackend
cli._load_cloud_credential = lambda: None
raise SystemExit(worker(Path(sys.argv[1]), role))
""")
    monkeypatch.setenv("PYTHONPATH", f"{module.WORKSPACE_ROOT}:{module.POKECHAMP_ROOT}")
    original_popen = subprocess.Popen

    def fixture_popen(args, **kwargs):
        if "--worker" in args:
            args = [sys.executable, str(wrapper), args[-2], args[-1]]
        return original_popen(args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", fixture_popen)
    slot = make_schedule(DEFAULT_CONFIG, {})["schedule"][0]
    slot = {**slot, "methods": ["io", "io"], "slot_id": "peer-cancel-fixture"}
    result = module.run_attempt(
        tmp_path,
        tmp_path,
        {
            "experiment_id": "peer-cancel-fixture",
            "source": {"fixture_provider": True, "network_calls": 0},
        },
        slot,
        1,
    )
    assert result["category"] == "output_contract"
    assert result["actors"]["p1"]["category"] == "peer_failure"
    assert result["actors"]["p2"]["category"] == "output_contract"
    for actor in result["actors"].values():
        bundle = Path(actor["bundle"])
        manifest = json.loads((bundle / "manifest.json").read_text())
        assert manifest["evidence_complete"]
        events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
        assert sum(e["event_type"] == "llm_call" for e in events) == 1
        assert not any(
            e["event_type"] == "wire_action" and e["action"].startswith("/choose") for e in events
        )


def test_reliability_separates_own_error_peer_and_retry_denominators():
    from integration.pokechamp.benchmark import method_reliability

    slot = {"slot_id": "s1", "methods": ["io", "abyssal"]}
    failed = {
        "slot": slot,
        "slot_id": "s1",
        "eligible": False,
        "actors": {"p1": {"category": "timeout"}, "p2": {"category": "peer_failure"}},
    }
    success = {
        **failed,
        "eligible": True,
        "actors": {"p1": {"category": None}, "p2": {"category": None}},
    }
    rows = method_reliability([failed, success], [slot])
    assert rows["io"]["own_errors"] == {"timeout": 1}
    assert rows["abyssal"]["own_errors"] == {}
    assert rows["abyssal"]["peer_interruptions"] == 1
    assert rows["io"]["assigned_slots"] == rows["io"]["processed_slots"] == 1
    assert rows["io"]["actor_attempts"] == 2
    assert rows["io"]["completion_fraction_of_assigned"] == 1


def test_analysis_counts_sent_fallbacks_and_extrapolates_with_matchup_mix(tmp_path, monkeypatch):
    from integration.pokechamp import benchmark as b

    monkeypatch.setattr(b, "fallback_source_map", lambda _: {"outer_handler_relative_line": 246})
    value = make_schedule(DEFAULT_CONFIG, {})
    attempts = []
    for slot in value["schedule"]:
        actors = {}
        for i, method in enumerate(slot["methods"]):
            bundle = tmp_path / (slot["slot_id"] + method)
            bundle.mkdir()
            # Deliberately expensive Random matchups must receive their smaller main weight.
            tokens = 100 if "random" in slot["methods"] else 10
            events = [
                {
                    "event_type": "llm_call",
                    "status": "success",
                    "validation": {"call_role": "self_action", "json_valid": True},
                    "response": {"prompt_tokens": tokens, "completion_tokens": 2},
                },
                {"event_type": "wire_action", "send_status": "sent", "action": "/team 123456"},
                {"event_type": "wire_action", "send_status": "sent", "action": "/choose move 1"},
            ]
            (bundle / "events.jsonl").write_text("\n".join(map(json.dumps, events)))
            actors[f"p{i + 1}"] = {
                "bundle": str(bundle),
                "category": None,
                "duration_seconds": 2,
                "diagnostics": [
                    {"kind": "exception_fallback", "source_line": 246},
                    {"kind": "exception_fallback", "source_line": 118},
                ],
            }
        attempts.append(
            {
                "slot": slot,
                "slot_id": slot["slot_id"],
                "attempt_id": slot["slot_id"] + "-a1",
                "eligible": True,
                "actors": actors,
                "category": None,
            }
        )
    # One failed minimax game: its handler entries are not completed fallback actions.
    failed = next(a for a in attempts if "minimax" in a["slot"]["methods"])
    failed["eligible"] = False
    failed["category"] = "algorithm"
    role = f"p{failed['slot']['methods'].index('minimax') + 1}"
    failed["actors"][role]["category"] = "output_contract"
    report = {"main_scenarios": [{"core_pair_games": 200}]}
    b.enrich_report(report, attempts, value, tmp_path)
    fallback = report["minimax_fallback"]
    assert fallback["eligible_minimax_actor_games"] == 15
    assert fallback["sent_choose_actions"] == 15
    assert fallback["outer_search_action_fallbacks"] == 15
    assert fallback["other_exception_handler_entries"] == {"118": 15}
    assert report["main_scenarios"][0]["resource_estimate"]["io"]["prompt_tokens"] == 8000
    assert len(report["failure_category_discrepancies"]) == 1


@pytest.mark.parametrize("category", ["timeout", "output_contract", "auth", "watchdog"])
def test_fast_worker_exit_preserves_final_actor_category(tmp_path, monkeypatch, category):
    from integration.pokechamp import benchmark as b

    monkeypatch.setattr(b.cli, "_start_server", lambda **_: {"pid": 123})
    monkeypatch.setattr(b.cli, "_read_server_pid", lambda: 123)
    monkeypatch.setattr(b.cli, "command_server", lambda _: 0)
    monkeypatch.setattr(b, "check_actor_evidence", lambda *args: None)
    monkeypatch.setattr(b, "terminate", lambda _: None)

    def already_exited(command, **kwargs):
        directory, role = Path(command[-2]), command[-1]
        b.write_json(
            directory / f"{role}.result.json",
            {
                "category": category if role == "p1" else "peer_failure",
                "outcome": "interrupted",
                "bundle": "fixture",
            },
        )
        return SimpleNamespace(poll=lambda: 2, returncode=2)

    monkeypatch.setattr(b.subprocess, "Popen", already_exited)
    (tmp_path / "attempts").mkdir()
    slot = make_schedule(DEFAULT_CONFIG, {})["schedule"][0]
    result = b.run_attempt(tmp_path, tmp_path, {"experiment_id": "fixture", "source": {}}, slot, 1)
    assert result["eligible"] is False
    assert result["category"] == category
