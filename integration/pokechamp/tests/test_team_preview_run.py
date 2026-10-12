"""EX-039 stage barriers, one-shot ledger and incomplete-pair denominators."""

import copy
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp import team_preview_report as report
from integration.pokechamp import team_preview_run as runner
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.cloud import CloudRequestError


def test_first_slot_selects_entire_pair_and_other_order_is_preserved():
    schedule = study.schedule()
    first, rest = runner.staged_schedule(schedule)
    assert [r["slot_id"] for r in first] == ["b03-r3-s0", "b03-r3-s1"]
    assert len(rest) == 30 and len({r["slot_id"] for r in first + rest}) == 32
    assert rest == [r for r in schedule if r["paired_slot_id"] != "b03-r3"]
    assert first[0]["teams"] == first[1]["teams"] == ["2", "6"]
    assert first[0]["battle_seed"] == first[1]["battle_seed"]
    assert first[0]["actor_seeds"] == first[1]["actor_seeds"]


@pytest.mark.parametrize("gate_passed,expected", [(True, 32), (False, 2)])
def test_schedule_gate_barrier_no_supplement_or_retry(tmp_path, monkeypatch, gate_passed, expected):
    value = dict(schedule=study.schedule(), execution=study.execution("fake"))
    monkeypatch.setattr(study, "verify_prepared", lambda _: value)
    monkeypatch.setattr(study, "collection_deadline", lambda _: None)
    observed, lock = [], threading.Lock()
    gate_completed = False
    first, _ = runner.staged_schedule(value["schedule"])
    first_ids = {r["slot_id"] for r in first}

    def worker(data, root, prepared, slot, number, **kwargs):
        assert number == 1
        assert slot["slot_id"] in first_ids or gate_completed
        with lock:
            observed.append(slot["slot_id"])
        return dict(slot_id=slot["slot_id"], eligible=True, category=None)

    def gate(root, attempts, prepared, snapshot):
        nonlocal gate_completed
        assert len(attempts) == 2 and set(observed) == first_ids
        gate_completed = True
        return dict(passed=gate_passed)

    broker = SimpleNamespace(
        path=tmp_path / "broker",
        stop=lambda: None,
        snapshot=lambda: dict(active_at_close={}, events=[]),
    )
    attempts = runner.execute_schedule(
        tmp_path, tmp_path / "data", value, broker, worker=worker, gate_check=gate
    )
    assert len(attempts) == len(observed) == len(set(observed)) == expected
    assert len(list((tmp_path / "dispatch").glob("*.json"))) == expected
    assert b.read_sealed(tmp_path / "first-pair-check.json")["passed"] is gate_passed
    assert (tmp_path / "halt.json").exists() is (not gate_passed)


def test_shared_defect_prevents_followup_even_if_gate_mock_says_pass(tmp_path, monkeypatch):
    value = dict(schedule=study.schedule(), execution=study.execution("fake"))
    monkeypatch.setattr(study, "verify_prepared", lambda _: value)
    monkeypatch.setattr(study, "collection_deadline", lambda _: None)
    broker = SimpleNamespace(
        path=tmp_path / "broker",
        stop=lambda: None,
        snapshot=lambda: dict(active_at_close={}, events=[]),
    )

    def worker(data, root, prepared, slot, number, **kwargs):
        return dict(slot_id=slot["slot_id"], eligible=False, category="calculation")

    attempts = runner.execute_schedule(
        tmp_path,
        tmp_path / "data",
        value,
        broker,
        worker=worker,
        gate_check=lambda *args: dict(passed=True),
    )
    assert len(attempts) == 2
    assert b.read_sealed(tmp_path / "halt.json")["category"] == "calculation"


def test_pair_scores_exclude_failed_game_without_assigning_zero():
    rows = [
        dict(r, status="valid_completed", reason=None, outcome="player_won")
        for r in study.schedule()
    ]
    # Pair1 is W/L (0.5); pair2 draw/draw (0.5); pair3 W/missing (excluded).
    groups = {}
    for row in rows:
        groups.setdefault(row["paired_slot_id"], []).append(row)
    keys = sorted(groups)
    groups[keys[0]][1]["outcome"] = "player_lost"
    for row in groups[keys[1]]:
        row["outcome"] = "tied"
    groups[keys[2]][1].update(status="failed", reason="timeout", outcome="aborted")
    pairs = report.paired_scores(rows)
    assert len(pairs) == 16 and sum(p["complete"] for p in pairs) == 15
    assert pairs[0]["llm_score_mean"] == pairs[1]["llm_score_mean"] == 0.5
    assert pairs[2]["llm_score_mean"] is None and pairs[2]["valid_games"] == 1
    assert pairs[2]["missing"][0]["reason"] == "timeout"
    assert sum(p["llm_score_mean"] for p in pairs if p["complete"]) / 15 == 14 / 15
    assert report.summarize(rows)["valid_completed"] == 31


def test_latency_p95_nearest_rank_and_empty_denominator():
    assert report.distribution([])["p95"] is None
    values = report.distribution(list(range(1, 21)))
    assert (values["median"], values["p95"], values["maximum"]) == (10.5, 19, 20)


def test_atomic_duplicate_lead_reservation_consumes_one_and_keeps_uncertain(tmp_path):
    root = tmp_path / "prepared"
    value = study.prepare(root)
    slot = value["schedule"][0]
    actor = "/".join((value["experiment_id"], slot["slot_id"] + "-a1", "p2"))
    payload = dict(
        request=dict(call_role="team_preview", identity=dict(decision_seq=1)),
        system_prompt="test",
        user_prompt="test",
    )

    def reserve():
        try:
            return study.reserve(root, actor, payload)
        except CloudRequestError as exc:
            return exc.category

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: reserve(), range(8)))
    assert sum(isinstance(r, Path) for r in outcomes) == 1
    assert outcomes.count("integrity") == 7
    with sqlite3.connect(root / "ledger.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1
    clock_hash = b.digest(root / "cloud-clock.json")
    later = copy.deepcopy(payload)
    later["request"]["call_role"] = "self_action"
    later["request"]["identity"]["decision_seq"] = 2
    study.reserve(root, actor, later)
    with pytest.raises(CloudRequestError, match="duplicate"):
        study.reserve(root, actor, later)
    assert b.digest(root / "cloud-clock.json") == clock_hash
    usage, requests = report.usage(root, value, [])
    assert sum(u["reserved"] for u in usage) == 2
    assert sum(u["uncertain_requests"] for u in usage) == 2
    assert sum(u["token_usage_unconfirmed"] for u in usage) == 2
    assert len(requests) == 2


def test_forged_or_stale_local_entry_is_rejected(tmp_path):
    root = tmp_path / "prepared"
    value = study.prepare(root, experiment_id="EX-039")
    path = tmp_path / "verification.json"
    b.seal_json(
        path,
        dict(
            source_files=value["parent_files"],
            local_passed=True,
            wire_passed=True,
            execution_protocol=study.EXECUTION_PROTOCOL,
        ),
    )
    with pytest.raises(ValueError, match="evidence missing"):
        runner.verify_entry(root, path)


def test_policy_hash_preserved_and_money_excluded():
    assert study.POLICY["decision"] == "D-052"
    assert study.EXECUTION_PROTOCOL["decision"] == "D-053"
    assert study.EXECUTION_PROTOCOL["monetary_cap"] is None
    assert study.EXECUTION_PROTOCOL["monetary_cap_basis"] == "explicit_user_exclusion"
    assert study.EXECUTION_PROTOCOL["call_limit"] == 8000
