"""D-045 defaults, historical identities, and real local coordinator admission."""

import threading
from types import SimpleNamespace

import pytest

from integration.pokechamp import a_diagnostic as d
from integration.pokechamp import ab_head_to_head as h
from integration.pokechamp import benchmark as b
from integration.pokechamp.action_study import parallel_budget, validation_gate
from integration.pokechamp.constants import OLLAMA_MODEL
from integration.pokechamp.execution import (
    CONCURRENCY_POLICY,
    concurrency_fields,
    gate_evidence,
    gate_parallel,
    gate_selection,
    validate_execution,
)
from integration.pokechamp.improved_io import battle_only, battle_only_gate, study
from integration.pokechamp.improved_io.conditions import require_parallel
from integration.pokechamp.permits import Permit
from integration.pokechamp.summary_diagnostics import prepare as summaries


@pytest.mark.parametrize("limit", [1, 3, 8, 9, 10])
def test_factories_honor_explicit_limits_and_default_eight(limit):
    factories = [
        lambda **kw: d.execution("fake", **kw),
        lambda **kw: h.execution("fake", **kw),
        lambda **kw: h.execution("fake", h.PROTECTFIX, **kw),
        lambda **kw: study.execution("offline.json", fake=True, **kw),
    ]
    for factory in factories:
        default = validate_execution(factory())
        assert default["battle_concurrency"] == 8
        value = validate_execution(factory(concurrency=limit))
        for key, expected in concurrency_fields(limit).items():
            assert value[key] == expected
        assert value["evidence"]["concurrency_policy"] == CONCURRENCY_POLICY
        require_parallel(value)
    for profile in (summaries.LEGACY_PROFILE, summaries.THINKING_PROFILE, summaries.MAX_PROFILE):
        assert summaries.config(profile)["account_limit"] == 8
        value = summaries.config(profile, concurrency=limit)
        assert value["account_limit"] == value["model_limit"] == limit


@pytest.mark.parametrize("bad", [0, 11, True, 8.0, "8", None])
def test_invalid_limits_rejected(bad):
    with pytest.raises(ValueError):
        d.execution("fake", concurrency=bad)
    with pytest.raises(ValueError):
        gate_selection(bad)


def test_execution_policy_and_legacy_validation():
    value = study.execution("offline", fake=True)
    value["evidence"]["concurrency_policy"] = "unknown"
    with pytest.raises(ValueError, match="unknown concurrency policy"):
        validate_execution(value)
    value["evidence"].pop("concurrency_policy")
    with pytest.raises(ValueError, match="requires battles10"):
        require_parallel(value)
    value.update(concurrency_fields(10))
    require_parallel(value)
    # Separate declared request limits remain supported by schema v1.
    value["account_request_limit"] = 3
    assert validate_execution(value)["account_request_limit"] == 3


@pytest.mark.parametrize("limit", [1, 8, 10])
def test_battle_only_reads_prepared_declaration(tmp_path, limit):
    b.seal_json(tmp_path / "manifest.json", gate_selection(limit))
    value = battle_only.execution(tmp_path / "result.json", stage="fake32", previous=None)
    assert value["battle_concurrency"] == limit
    assert value["account_request_limit"] == limit
    assert gate_evidence(value["evidence"]) == gate_selection(limit)


def test_gate_cells_legacy_and_new_declarations():
    assert gate_parallel({}) == 10
    assert gate_evidence({}) == {}
    for record, limit in (({}, 10), (gate_selection(), 8), (gate_selection(3), 3)):
        rows = battle_only_gate.schedule(gate_parallel(record))
        assert len(rows) == len({r["id"] for r in rows}) == 90
        assert {r["concurrency"] for r in rows} == {1, limit}
    with pytest.raises(ValueError, match="requires a policy"):
        gate_parallel({"parallel_concurrency": 8})
    with pytest.raises(ValueError):
        battle_only_gate.schedule(1)


@pytest.mark.parametrize("limit", [8, 10])
def test_metrics_follow_declaration_and_reject_wrong_cells(limit):
    rows = []
    for c in (1, limit):
        for i in range(72):
            start = (i // c) * 2
            rows.append(dict(
                concurrency=c, valid=True,
                trace=dict(request=dict(model=OLLAMA_MODEL), response=dict(
                    http_started_at=start, http_finished_at=start + 1,
                    http_elapsed_ms=1000,
                )),
            ))
    declaration = gate_selection(limit) if limit == 8 else None
    assert validation_gate(rows, declaration=declaration)["passed"]
    wrong = gate_selection(10 if limit == 8 else 8)
    assert not validation_gate(rows, declaration=wrong)["passed"]
    rows[-1]["concurrency"] = 2
    assert not validation_gate(rows, declaration=declaration)["passed"]


def test_budget_uses_actual_worker_count():
    attempts = [dict(slot=dict(pair=["io", "abyssal"]), duration_seconds=10)]
    schedule = [dict(pair=["io", "abyssal"]) for _ in range(20)]
    assert parallel_budget(attempts, schedule)["estimated_seconds"] == 30
    assert parallel_budget(attempts, schedule, workers=10)["estimated_seconds"] == 20
    assert parallel_budget(attempts, schedule, workers=1)["estimated_seconds"] == 200


@pytest.mark.parametrize("module,relative", [
    (d, "a-diagnostic64/ex035"),
    (h, "ab-head-to-head32/ex036"),
    (h, "ab-head-to-head32/ex037"),
])
def test_archived_fixed_profiles_still_verify(module, relative):
    root = b.WORKSPACE_ROOT / ".pokechamp-data" / relative
    before = b.digest(root / "plan.json")
    value = module.verify_prepared(root, current=False)
    assert value["execution"]["battle_concurrency"] == 10
    assert "concurrency_policy" not in value["execution"]["evidence"]
    if module is h:
        expected = module.execution(value["transport"], value["experiment_policy"], legacy=True)
    else:
        expected = module.execution(value["transport"], legacy=True)
    assert value["execution"] == expected
    assert b.digest(root / "plan.json") == before


@pytest.mark.parametrize("limit", [3, 4, 8, 10])
def test_real_coordinator_permits_ports_and_continuous_refill(tmp_path, monkeypatch, limit):
    root = tmp_path / "study"
    root.mkdir()
    count = limit * 2 + 1
    value = dict(
        transport="fake", execution=d.execution("fake", concurrency=limit),
        schedule=[dict(slot_id=f"s{i}") for i in range(count)],
    )
    api = SimpleNamespace(
        SLOT_COUNT=count, continuous_submission=True,
        verify_prepared=lambda *a: value, verify_entry=lambda *a: None,
        collection_deadline=lambda *a: None,
        report=lambda root: b.read_sealed(root / "batch.json"),
    )
    monkeypatch.setattr(b.cli, "ARTIFACT_ROOT", tmp_path / "artifacts")
    checked = []
    monkeypatch.setattr(d, "check_ports", lambda ports: checked.append(list(ports)))
    first_wave = threading.Barrier(limit, timeout=10)
    refilled = threading.Event()
    lock = threading.Lock()
    calls, active, maximum = [], set(), [0]

    def attempt(data, directory, plan, slot, number, *, port, broker_path, deadline):
        index = int(slot["slot_id"][1:])
        assert number == 1
        with lock:
            assert port not in active
            active.add(port)
            calls.append(index)
            maximum[0] = max(maximum[0], len(active))
        try:
            with Permit(broker_path, OLLAMA_MODEL):
                if index < limit:
                    first_wave.wait()
                    if index:
                        assert refilled.wait(10), "next slot must start before this wave drains"
                elif index == limit:
                    with lock:
                        assert len(active) == limit
                    refilled.set()
        finally:
            with lock:
                active.remove(port)
        return dict(slot_id=slot["slot_id"], eligible=True, category=None)

    monkeypatch.setattr(b, "run_attempt", attempt)
    result = d.run(root, tmp_path / "data", verification=None, protocol=api)
    assert refilled.is_set() and not active
    assert sorted(calls) == list(range(count))
    assert maximum[0] == limit
    assert checked == [list(range(8100, 8100 + limit))] * 2
    assert result["broker"]["maximum_account_permits"] == limit
    assert result["broker"]["maximum_model_permits"] == {OLLAMA_MODEL: limit}
    assert not any(result["broker"]["active_at_close"].values())
    dispatch = [r for r in result["events"] if r["event"] == "dispatch"]
    assert [r["slot_id"] for r in dispatch] == [f"s{i}" for i in range(count)]
    assert not (root / "first10-check.json").exists()


@pytest.mark.parametrize("experiment", ["ex021", "ex022", "ex025"])
def test_archived_summary_config_and_manifest_still_verify(experiment):
    root = b.WORKSPACE_ROOT / ".pokechamp-data/summary-diagnostics" / experiment
    before = b.digest(root / "manifest.json")
    # Historical semantic invalidations remain in force; this checks sealed configuration.
    value = summaries.verify(root, current=False, validate_semantics=False)
    assert value["config"] == summaries.config(
        value.get("profile", summaries.LEGACY_PROFILE), legacy=True
    )
    assert b.digest(root / "manifest.json") == before


def test_battle_execution_cannot_change_prepared_limit(tmp_path, monkeypatch):
    from integration.pokechamp.improved_io import battle_only_protocol as protocol

    b.seal_json(tmp_path / "manifest.json", gate_selection())
    monkeypatch.setattr(protocol, "read_stage", lambda *a: {})
    value = battle_only.execution(tmp_path / "result.json", stage="fake32", previous=None)
    protocol.require_offline(value)
    value["account_request_limit"] = 10
    with pytest.raises(ValueError, match="concurrency mismatch"):
        protocol.require_offline(value)
    value["account_request_limit"] = 8
    value["evidence"]["parallel_concurrency"] = 10
    with pytest.raises(ValueError, match="concurrency mismatch"):
        protocol.require_offline(value)
