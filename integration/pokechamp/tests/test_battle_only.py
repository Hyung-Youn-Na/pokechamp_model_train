"""D-030 profile, no-memory, request accounting and paired defect recovery regressions."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.cloud import CloudRequestError, OllamaCloudBackend
from integration.pokechamp.improved_io import battle_only_budget as budget
from integration.pokechamp.improved_io.battle_only_gate import schedule, validate_review
from integration.pokechamp.improved_io.battle_only_protocol import (
    PROFILE,
    read_stage,
    ref,
    replay_window,
    restrict_schedule,
    validate_context,
)
from integration.pokechamp.improved_io.battle_only_report import summarize
from integration.pokechamp.improved_io.calculator import expected_patch
from integration.pokechamp.improved_io.receipts import source_identity
from integration.pokechamp.improved_io.state import stable_id


def context():
    value = dict(
        request=dict(kind="turn_action", legal_actions=[{"move": "surf"}], can_tera=False),
        current_observation={},
        opponent_hypotheses=[],
        recent_events=[],
        lesson_memory=[],
        battle_summary=None,
        unknowns=[],
        condition_id="B",
    )
    identity = dict(
        battle_id="b",
        actor_id="p1",
        decision_seq=1,
        request_id=1,
        state_id=stable_id({k: v for k, v in value.items() if k != "condition_id"}),
        showdown_turn=1,
    )
    value.update(
        identity=identity,
        calculation_bundle=dict(
            identity=identity,
            status="success",
            engine_version="0.11.0",
            engine="@smogon/calc",
            generation=9,
            engine_patch=expected_patch(),
            coverage=[{"scenario_id": "s1"}],
            entries=[{"scenario_id": "s1"}],
        ),
    )
    return value


@pytest.fixture
def registered(tmp_path):
    prepared = tmp_path / "prepared/result.json"
    b.seal_json(prepared, dict(profile=PROFILE, source_files=source_identity(), passed=True))
    root = tmp_path / "study"
    budget.register(root, prepared)
    return root, prepared


def test_ab_schedule_and_legacy_abc_remain_distinct():
    reference = b.make_schedule(b.CORE_REPEAT_CONFIG, {})
    for config, count in ((b.BATTLE_ONLY_SMOKE_CONFIG, 8), (b.BATTLE_ONLY_COMPARE_CONFIG, 32)):
        value = b.make_schedule(config, {})
        assert set(value["conditions"]) == {"A", "B"}
        assert len(value["schedule"]) == count
        assert value == b.make_schedule(config, {})
        for i in range(0, count, 2):
            pair = value["schedule"][i : i + 2]
            assert {s["condition_id"] for s in pair} == {"A", "B"}
            assert pair[0]["paired_slot_id"] == pair[1]["paired_slot_id"]
        for slot in value["schedule"]:
            original = next(
                s for s in reference["schedule"] if s["slot_id"] == slot["paired_slot_id"]
            )
            assert all(slot[k] == v for k, v in original.items() if k != "slot_id")
    assert len(b.make_schedule(b.IO_COMPARE_CONFIG, {})["schedule"]) == 48
    assert set(b.make_schedule(b.IO_COMPARE_CONFIG, {})["conditions"]) == {"A", "B", "C"}


@pytest.mark.parametrize(
    "change",
    [
        {"condition_id": "C"},
        {"battle_summary": {"battle_id": "b", "actor_id": "p1", "text": "x"}},
        {"lesson_memory": ["x"]},
        {"calculation_bundle": {}},
    ],
)
def test_b_input_contamination_or_missing_calc_blocks(change):
    value = context()
    validate_context(value)
    value.update(change)
    with pytest.raises((ValueError, KeyError)):
        validate_context(value)


def test_stale_calculation_and_summary_role_are_preprovider_failures():
    value = context()
    value["calculation_bundle"]["identity"] = dict(value["identity"], request_id=9)
    with pytest.raises(ValueError, match="stale"):
        validate_context(value)
    with pytest.raises(ValueError, match="role"):
        validate_context(context(), role="summary")


def test_live31_has_zero_summary_rollup_archive_and_last10_window():
    from integration.pokechamp.improved_io.memory_fixture import run

    result = run(battle_only=True)
    assert result["passed"]
    assert result["roles"] == ["self_action"] * 31
    assert result["summaries"] == result["rollups"] == 0
    assert not result["memory_archive"]
    assert result["summary_prompt_identity"] is None


def test_window_uses_sent_decisions_not_turn_or_llm_retry_count(tmp_path):
    events, prefix = [], []
    for i in range(1, 32):
        event = dict(event_type="protocol_in", event_seq=i * 10, protocol=f"|turn|{i}")
        prefix.append(event)
        events += [
            event,
            dict(event_type="decision_start", event_seq=i * 10 + 1, decision_seq=i),
            dict(event_type="llm_call", event_seq=i * 10 + 2, decision_seq=i),
            dict(event_type="llm_call", event_seq=i * 10 + 3, decision_seq=i),
            dict(
                event_type="wire_action",
                event_seq=i * 10 + 4,
                decision_seq=i,
                action="/choose move surf",
                send_status="sent",
            ),
        ]
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    result = replay_window(tmp_path, 311, prefix)
    assert [e["event_seq"] for e in result] == list(range(220, 311, 10))
    assert len(replay_window(tmp_path, 51, prefix[:5])) == 5


@pytest.mark.parametrize("parallel", [8, 10])
def test_gate90_exact_declared_cells_and_no_c(parallel):
    items = schedule(parallel)
    assert len(items) == len({s["id"] for s in items}) == 90
    for c in (1, parallel):
        for r in range(3):
            assert len([s for s in items if s["concurrency"] == c and s["repeat"] == r]) == 15
    assert all("-B-" in s["id"] for s in items)


def test_receipt_rejects_legacy_profile_even_when_passed(tmp_path):
    path = tmp_path / "legacy.json"
    b.seal_json(path, dict(stage="cloud_gate", passed=True, conditions={"A": {}, "B": {}, "C": {}}))
    with pytest.raises(ValueError, match="gate did not pass"):
        read_stage(path, "cloud_gate")


def test_initial_clock_delayed_until_dispatch_and_cannot_reset(registered):
    root, _ = registered
    assert not (root / "cloud-clock.json").exists()
    with pytest.raises(ValueError, match="missing"):
        budget.clock(root)
    first = budget.clock(root, create=True, now=100)
    assert budget.clock(root, create=True, now=200) == first
    assert first["stop_new_work_at"] == 13600 and first["cleanup_deadline"] == 14500


def test_stage_claim_rejects_duplicate_denominator_and_foreign_id(registered):
    root, _ = registered
    ids = [s["id"] for s in schedule()]
    with pytest.raises(ValueError, match="denominator"):
        budget.claim_stage(root, "c0", "cloud_gate", ids[:-1], root / "out")
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "out")
    with pytest.raises(FileExistsError):
        budget.claim_stage(root, "c0", "cloud_gate", ids, root / "new-output")
    with pytest.raises(ValueError, match="unregistered"):
        budget.reserve(root, "c0", "cloud_gate", "foreign", {})


def test_atomic_reservations_duplicate_and_uncertain_count_are_preserved(registered):
    root, _ = registered
    ids = [s["id"] for s in schedule()]
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "out")
    with ThreadPoolExecutor(max_workers=10) as pool:
        paths = list(pool.map(lambda i: budget.reserve(root, "c0", "cloud_gate", i, {}), ids[:10]))
    assert len(set(paths)) == 10
    assert budget.usage(root)["uncertain"] == 10
    budget.preserve_response(paths[0], {"message": {"content": "saved"}})
    assert budget.usage(root)["responses"] == 1
    assert budget.usage(root)["reserved_calls"] == 10
    before = b.digest(root / "cloud-clock.json")
    with pytest.raises(ValueError, match="duplicate"):
        budget.reserve(root, "c0", "cloud_gate", ids[0], {})
    assert b.digest(root / "cloud-clock.json") == before


def test_total_call_cap_includes_uncertain_and_never_credits_back(registered, monkeypatch):
    root, _ = registered
    ids = [s["id"] for s in schedule()]
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "out")
    budget.clock(root, create=True)
    original = Path.glob

    def glob(path, pattern):
        if path == root / "requests" and pattern == "intent-*.json":
            return iter(Path(f"intent-{i:06}.json") for i in range(4000))
        return original(path, pattern)

    monkeypatch.setattr(Path, "glob", glob)
    with pytest.raises(ValueError, match="budget exhausted"):
        budget.reserve(root, "c0", "cloud_gate", ids[0], {})


def test_deadline_blocks_reservation_before_http(registered):
    root, _ = registered
    ids = [s["id"] for s in schedule()]
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "out")
    budget.clock(root, create=True, now=100)
    with pytest.raises(ValueError, match="budget_stop"):
        budget.reserve(root, "c0", "cloud_gate", ids[0], {})
    assert budget.usage(root)["reserved_calls"] == 0


def test_source_drift_halt_and_new_root_cannot_reset_identity(registered, monkeypatch, tmp_path):
    root, prepared = registered
    with pytest.raises(FileExistsError):
        budget.register(tmp_path / "other-study", prepared)
    monkeypatch.setattr(budget, "source_identity", lambda: {})
    with pytest.raises(ValueError, match="source changed"):
        budget.require_cohort(root, "c0")
    budget.halt(root, "c0", "model_error", prepared)
    with pytest.raises(ValueError, match="halted"):
        budget.require_cohort(root, "c0", current=False)


def test_upstream_internal_additional_calls_all_get_journaled(registered):
    root, _ = registered
    slots = b.make_schedule(b.BATTLE_ONLY_SMOKE_CONFIG, {})["schedule"]
    budget.claim_stage(root, "c0", "smoke8", [s["slot_id"] for s in slots], root / "out")
    env = dict(
        OLLAMA_API_KEY="local",
        POKECHAMP_IO_STUDY_ROOT=str(root),
        POKECHAMP_IO_COHORT="c0",
        POKECHAMP_IO_STAGE="smoke8",
        POKECHAMP_IO_ACTOR="test/" + slots[0]["slot_id"] + "-a1/p1",
    )
    backend = OllamaCloudBackend(
        environ=env,
        client_factory=lambda **_: SimpleNamespace(
            chat=lambda **_: dict(
                model="glm-5.3-flash",
                message={"content": "invalid original output"},
                done=True,
                done_reason="stop",
            )
        ),
    )
    backend.action_policy = "upstream"
    for _ in range(3):
        backend.get_LLM_action("original", "original", backend.model, json_format=True)
    assert budget.usage(root)["reserved_calls"] == budget.usage(root)["responses"] == 3
    assert len(list((root / "requests").glob("response-*.json"))) == 3


def test_worker_response_is_sealed_before_output_contract_failure(registered):
    root, _ = registered
    ids = [s["id"] for s in schedule()]
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "out")
    backend = OllamaCloudBackend(
        environ=dict(
            OLLAMA_API_KEY="local",
            POKECHAMP_IO_STUDY_ROOT=str(root),
            POKECHAMP_IO_COHORT="c0",
            POKECHAMP_IO_STAGE="cloud_gate",
            POKECHAMP_IO_ACTOR=ids[0],
        ),
        client_factory=lambda **_: SimpleNamespace(
            chat=lambda **_: dict(
                model="glm-5.3-flash",
                message={"content": "not json"},
                done=True,
                done_reason="stop",
            )
        ),
    )
    with pytest.raises(CloudRequestError):
        backend.get_LLM_action("fixed", "input", backend.model)
    usage = budget.usage(root)
    assert usage["reserved_calls"] == usage["responses"] == 1 and usage["uncertain"] == 0


def defect_record(root, prepared, tmp_path, *, kind="input"):
    verification = tmp_path / "verification.json"
    if not verification.exists():
        b.seal_json(verification, dict(independent=True, reproduced=True, regressions=True))
    slots = [
        s["slot_id"] for s in b.make_schedule(b.BATTLE_ONLY_COMPARE_CONFIG, {})["schedule"][:2]
    ]
    original = b.read_sealed(prepared)
    return dict(
        kind=kind,
        discovered_at_stage="compare32",
        symptom="independent input omission",
        original=ref(prepared),
        verification=ref(verification),
        source_before=original["source_files"],
        source_after=original["source_files"],
        impact={"compare32": slots},
        recollect={"compare32": slots},
        evidence="original raw row and independent fixture",
        scope_proven=True,
        model_error_reclassified=False,
    )


def test_recovery_preserves_clock_calls_halt_and_both_sides(registered, tmp_path, monkeypatch):
    root, prepared = registered
    monkeypatch.setattr(
        "integration.pokechamp.improved_io.battle_only_protocol.read_stage",
        lambda *_, **__: b.read_sealed(prepared),
    )
    budget.clock(root, create=True)
    ids = [s["id"] for s in schedule()]
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "original")
    budget.reserve(root, "c0", "cloud_gate", ids[0], {})
    budget.halt(root, "c0", "input", prepared)
    before = b.digest(root / "cloud-clock.json"), b.digest(root / "halt-c0.json")
    record = defect_record(root, prepared, tmp_path)
    defect = tmp_path / "defect.json"
    b.seal_json(defect, record)
    result = budget.recover(root, defect, prepared)
    assert result["usage_before"]["reserved_calls"] == 1
    assert budget.usage(root)["uncertain"] == 1
    assert (b.digest(root / "cloud-clock.json"), b.digest(root / "halt-c0.json")) == before
    assert budget.require_cohort(root, "c1")["recovery"] == ref(root / "recovery-c1.json")
    slots = b.make_schedule(b.BATTLE_ONLY_COMPARE_CONFIG, {})["schedule"]
    ex = dict(
        evidence=dict(
            io_transport="cloud",
            io_cohort="c1",
            io_stage="compare32",
            io_recovery=ref(root / "recovery-c1.json"),
        )
    )
    assert len(restrict_schedule(slots, ex)) == 2
    budget.claim_stage(root, "c1", "compare32", record["recollect"]["compare32"], root / "recover")
    with pytest.raises(FileExistsError):
        budget.recover(root, defect, prepared)


@pytest.mark.parametrize(
    "change", ["one_side", "model_error", "unproven", "no_regression", "wrong_source"]
)
def test_invalid_recovery_rejected(registered, tmp_path, monkeypatch, change):
    root, prepared = registered
    monkeypatch.setattr(
        "integration.pokechamp.improved_io.battle_only_protocol.read_stage",
        lambda *_, **__: b.read_sealed(prepared),
    )
    budget.clock(root, create=True)
    budget.halt(root, "c0", "input", prepared)
    value = defect_record(root, prepared, tmp_path)
    if change == "one_side":
        value["recollect"]["compare32"] = value["recollect"]["compare32"][:1]
    elif change == "model_error":
        value["model_error_reclassified"] = True
    elif change == "unproven":
        value["scope_proven"] = False
    elif change == "no_regression":
        p = tmp_path / "bad-verification.json"
        b.seal_json(p, dict(independent=True, reproduced=True, regressions=False))
        value["verification"] = ref(p)
    else:
        value["source_after"] = {}
    defect = tmp_path / "defect.json"
    b.seal_json(defect, value)
    with pytest.raises(ValueError):
        budget.recover(root, defect, prepared)
    assert not (root / "cohorts/c1.json").exists()


def test_rubric_correction_requires_disclosure_and_no_recollection(
    registered, tmp_path, monkeypatch
):
    root, prepared = registered
    monkeypatch.setattr(
        "integration.pokechamp.improved_io.battle_only_protocol.read_stage",
        lambda *_, **__: b.read_sealed(prepared),
    )
    value = defect_record(root, prepared, tmp_path, kind="rubric")
    value.update(
        impact=["response1", "response2"],
        symmetric_response_ids=["response1", "response2"],
        recollect={},
        posthoc_disclosure=True,
    )
    path = tmp_path / "rubric-v2.json"
    b.seal_json(path, value)
    result = budget.recover(root, path, prepared)
    assert result["posthoc_disclosure"] is True
    assert not (root / "cloud-clock.json").exists()
    assert not (root / "cohorts/c1.json").exists()


def test_review_has_exact_denominator_and_claim_evidence():
    rows = {"a.json": {"sha256": "a"}}
    review = dict(
        collection_sha256="c",
        calls={
            "a.json": dict(
                response_sha256="a",
                facts=True,
                identity=True,
                timing=True,
                calculation=True,
                action_contract=True,
                evidence="Raw event12 and actual input active HP and calculation s1 agree.",
            )
        },
    )
    assert validate_review(rows, review, collection_hash="c") == []
    review["calls"]["a.json"]["calculation"] = False
    assert validate_review(rows, review, collection_hash="c")[0]["dimensions"] == ["calculation"]
    review["calls"]["a.json"]["evidence"] = ""
    with pytest.raises(ValueError, match="evidence"):
        validate_review(rows, review, collection_hash="c")


def attempt(slot, cohort="c0", eligible=True, outcome="player_lost"):
    role = "p" + str(slot["methods"].index("io") + 1)
    return dict(
        cohort=cohort,
        slot=slot,
        slot_id=slot["slot_id"],
        eligible=eligible,
        actors={role: {"outcome": outcome}},
        category=None if eligible else "input_contract",
    )


def test_recovery_denominators_keep_invalid_failures_and_legal_losses():
    slots = b.make_schedule(b.BATTLE_ONLY_COMPARE_CONFIG, {})["schedule"]
    old = [attempt(s) for s in slots[:2]]
    new = [attempt(s, "c1", outcome="player_won") for s in slots[:2]]
    result = summarize(slots, old + new, invalid=[("c0", s["slot_id"]) for s in slots[:2]])
    assert result["completed_pairs"] == 1
    for c in ("A", "B"):
        row = result["conditions"][c]
        assert row["attempted"] == 2
        assert row["invalid"] == row["recovery_attempts"] == row["valid_completed"] == 1
    losses = summarize(slots, old)
    assert losses["completed_pairs"] == 1
    assert all(v["valid_completed"] == 1 for v in losses["conditions"].values())
    with pytest.raises(ValueError, match="duplicate valid"):
        summarize(slots, old + new)


def fake_gate_worker(item, broker_path, deadline, *, failed=False):
    """Local process/permit/journal fixture; no network client is constructed."""
    from integration.pokechamp.permits import Permit

    root = Path(item["study_root"])
    with Permit(broker_path, "glm-5.3-flash"):
        intent = budget.reserve(root, item["cohort"], "cloud_gate", item["id"], {})
        # Measure broker capacity, not serial source-hash/worker startup speed.
        # Wait for this synthetic batch to enter before timing its mock HTTP.
        concurrency = item["metadata"]["concurrency"]
        if concurrency > 1:
            batch = (int(item["metadata"]["case"][-2:]) - 1) // concurrency
            expected = min(concurrency, 15 - batch * concurrency)
            ready = Path(item["output_path"]).parent / (
                f"fixture-ready-c{concurrency}-r{item['metadata']['repeat']}-b{batch}"
            )
            ready.mkdir(exist_ok=True)
            (ready / item["id"]).touch(exist_ok=False)
            ready_deadline = min(deadline, time.time() + 15)
            while len(list(ready.iterdir())) < expected:
                if time.time() >= ready_deadline:
                    raise TimeoutError("mock HTTP batch did not reach its expected capacity")
                time.sleep(0.005)
        start = time.time()
        time.sleep(0.3)
        response = dict(
            model="glm-5.3-flash",
            message={
                "content": 'Damage is 12–15 HP.\n{"move":"surf"}'
                if failed
                else 'Local fixture.\n{"move":"surf"}'
            },
            prompt_eval_count=1,
            eval_count=1,
        )
        budget.preserve_response(intent, response)
        end = time.time()
    row = dict(
        item_id=item["id"],
        role="self_action",
        context=item["context"],
        valid=not failed,
        category="output_contract" if failed else None,
        **item["metadata"],
        trace=dict(
            raw_content=response["message"]["content"],
            request=dict(model="glm-5.3-flash", call_role="self_action"),
            response=dict(
                http_status=200,
                http_started_at=start,
                http_finished_at=end,
                http_elapsed_ms=round((end - start) * 1000),
            ),
            validation=dict(output_contract_valid=True),
        ),
    )
    b.seal_json(Path(item["output_path"]), row)
    return row


def fake_failed_gate_worker(item, broker_path, deadline):
    return fake_gate_worker(item, broker_path, deadline, failed=True)


@pytest.mark.parametrize("failed", [False, True])
def test_fake_gate_collection_seals_responses_and_stops_without_resubmission(
    registered, tmp_path, monkeypatch, failed
):
    from integration.pokechamp.improved_io import battle_only_gate as gate

    root, prepared = registered
    scenes = []
    for i in range(1, 16):
        path = tmp_path / f"scene{i}.json"
        b.seal_json(path, context())
        scenes.append(dict(case=f"IO-C{i:02}", input=ref(path)))
    b.seal_json(prepared.parent / "manifest.json", dict(scenes=scenes))
    monkeypatch.setattr(gate, "read_stage", lambda *_, **__: {})
    output = tmp_path / "gate"
    result = gate.collect(
        root,
        prepared,
        prepared,
        output,
        worker=fake_failed_gate_worker if failed else fake_gate_worker,
    )
    if failed:
        assert result["attempted"] == 1
        assert result["responses"] == 1
        assert (root / "halt-c0.json").exists()
    else:
        assert result["technical_passed"]
        assert result["responses"] == result["attempted"] == 90
        assert result["parallel"]["maximum_account_http_overlap"] == 10
    assert budget.usage(root)["responses"] == result["responses"]
    original = b.digest(root / "cloud-clock.json")
    with pytest.raises((ValueError, FileExistsError)):
        gate.collect(root, prepared, prepared, tmp_path / "new-gate", worker=fake_gate_worker)
    assert b.digest(root / "cloud-clock.json") == original


@pytest.mark.parametrize("previous_passed", [True, False])
def test_source_requalification_only_reuses_previously_passed_gate(
    registered, tmp_path, monkeypatch, previous_passed
):
    root, prepared = registered
    monkeypatch.setattr(
        "integration.pokechamp.improved_io.battle_only_protocol.read_stage",
        lambda *_, **__: b.read_sealed(prepared),
    )
    gate_ids = [s["id"] for s in schedule()]
    original = tmp_path / "original-gate"
    b.seal_json(original / "result.json", dict(passed=previous_passed))
    budget.claim_stage(root, "c0", "cloud_gate", gate_ids, original)
    budget.clock(root, create=True)
    budget.halt(root, "c0", "input", prepared)
    record = defect_record(root, prepared, tmp_path)
    record["requalification"] = {"cloud_gate": gate_ids}
    record["recollect"]["cloud_gate"] = gate_ids
    record["requalification_reason"] = "New source requires gate qualification; old inputs intact."
    path = tmp_path / "requalification.json"
    b.seal_json(path, record)
    if previous_passed:
        result = budget.recover(root, path, prepared)
        assert "cloud_gate" not in result["impact"]
        assert len(result["requalification"]["cloud_gate"]) == 90
    else:
        with pytest.raises(ValueError, match="failed model gate"):
            budget.recover(root, path, prepared)


def test_requalification_preserves_completed_attempts_without_duplicate_scores():
    slots = b.make_schedule(b.BATTLE_ONLY_SMOKE_CONFIG, {})["schedule"]
    original = [attempt(s) for s in slots]
    repeated = [attempt(s, "c1") for s in slots]
    result = summarize(slots, original + repeated, superseded=[("c0", s["slot_id"]) for s in slots])
    for row in result["conditions"].values():
        assert row["completed_attempts"] == 8
        assert row["valid_completed"] == row["superseded_qualification"] == 4
        assert row["invalid"] == 0


@pytest.mark.parametrize("dash", ["–", "—"])
def test_english_typography_preserves_raw_json_and_legacy_behavior(dash):
    from integration.pokechamp.improved_io.output import parse_action

    text = f"Calculated damage is 12{dash}15 HP.\n" + '{"move":"surf"}'
    kwargs = dict(request_kind="turn_action", can_tera=False)
    with pytest.raises(ValueError):
        parse_action(text, [{"move": "surf"}], **kwargs)
    parsed = parse_action(text, [{"move": "surf"}], english_typography=True, **kwargs)
    assert parsed.action == {"move": "surf"} and dash in parsed.rationale
    for bad in (
        '피해는 12 HP입니다.\n{"move":"surf"}',
        'Damage is 12–15 HP.\n{"move":"surf","move":"surf"}',
        'Damage is 12–15 HP.\n{"move":"illegal"}',
    ):
        with pytest.raises(ValueError):
            parse_action(bad, [{"move": "surf"}], english_typography=True, **kwargs)


def test_evaluation_resume_does_not_reclassify_invalid_actions_or_change_trace():
    from integration.pokechamp.improved_io.battle_only_recovery import reevaluate

    row = dict(
        context=context(),
        valid=False,
        category="output_contract",
        trace=dict(
            raw_content='Damage is 12–15 HP.\n{"move":"surf"}',
            response={"http_status": 200},
            validation={"output_contract_valid": False},
        ),
    )
    result = reevaluate(row)
    assert result["valid"] and result["trace"] == row["trace"]
    assert row["valid"] is False
    row["trace"]["raw_content"] = 'Damage is 12–15 HP.\n{"move":"illegal"}'
    with pytest.raises(ValueError):
        reevaluate(row)


def test_evaluation_resume_input_equivalence_excludes_only_recorded_calculator_time(tmp_path):
    from integration.pokechamp.improved_io.battle_only_recovery import equivalent_inputs

    old = context()
    old["calculation_bundle"]["elapsed_ms"] = 10
    new = json.loads(json.dumps(old))
    new["calculation_bundle"]["elapsed_ms"] = 20
    path = tmp_path / "new.json"
    b.seal_json(path, new)
    assert equivalent_inputs(
        {"IO-C01": old}, {"scenes": [{"case": "IO-C01", "input": ref(path)}]}
    ) == {"IO-C01": old}
    new["request"]["legal_actions"] = [{"move": "other"}]
    changed = tmp_path / "changed.json"
    b.seal_json(changed, new)
    with pytest.raises(ValueError, match="input/treatment drift"):
        equivalent_inputs({"IO-C01": old}, {"scenes": [{"case": "IO-C01", "input": ref(changed)}]})


@pytest.mark.parametrize("parallel", [8, 10])
def test_evaluation_recovery_resumes89_without_recalling_original_response(
    registered, tmp_path, monkeypatch, parallel
):
    from integration.pokechamp.execution import gate_selection
    from integration.pokechamp.improved_io import battle_only_gate as gate

    root, prepared = registered
    declaration = gate_selection() if parallel == 8 else {}
    scenes = []
    for i in range(1, 16):
        path = tmp_path / f"scene-{i}.json"
        b.seal_json(path, context())
        scenes.append(dict(case=f"IO-C{i:02}", input=ref(path)))
    criteria = tmp_path / "criteria.json"
    b.seal_json(criteria, dict(profile=PROFILE))
    b.seal_json(
        prepared.parent / "manifest.json",
        dict(
            **declaration,
            scenes=scenes,
            prompt_sha256="fixed",
            prior_sha256="fixed",
            calculation_identity="fixed",
            criteria=ref(criteria),
        ),
    )
    monkeypatch.setattr(gate, "read_stage", lambda *_, **__: {})
    monkeypatch.setattr(
        "integration.pokechamp.improved_io.battle_only_protocol.read_stage",
        lambda *_, **__: b.read_sealed(prepared),
    )
    old_dir = tmp_path / "gate-old"
    original = gate.collect(root, prepared, prepared, old_dir, worker=fake_failed_gate_worker)
    assert original["responses"] == 1
    old_file = next(old_dir.glob("action-*.json"))
    before = (
        b.digest(old_file),
        b.digest(root / "cloud-clock.json"),
        b.digest(root / "halt-c0.json"),
    )
    verification = tmp_path / "independent.json"
    b.seal_json(verification, dict(independent=True, reproduced=True, regressions=True))
    source = b.read_sealed(prepared)["source_files"]
    record = dict(
        kind="evaluation",
        discovered_at_stage="cloud_gate",
        symptom="ASCII typography",
        original=ref(prepared),
        verification=ref(verification),
        source_before=source,
        source_after=source,
        impact=[old_file.name],
        symmetric_response_ids=[old_file.name],
        recollect={},
        evidence="Independent Unicode punctuation/unchanged JSON check",
        scope_proven=True,
        model_error_reclassified=False,
        resume_unexecuted=True,
        collection=ref(old_dir / "collection.json"),
        inputs=ref(old_dir / "inputs.json"),
    )
    defect = tmp_path / "defect-evaluation.json"
    b.seal_json(defect, record)
    restored = budget.recover(root, defect, prepared)
    assert len(restored["resume_schedule"]) == 89 and not restored["paid_recollection"]
    assert budget.require_cohort(root, "e1")["cohort"] == "e1"
    resumed = gate.collect(
        root, prepared, prepared, tmp_path / "gate-e1", cohort="e1", worker=fake_gate_worker
    )
    assert resumed["technical_passed"] and resumed["responses"] == 90
    assert resumed["inherited_responses"] == 1 and resumed["new_responses"] == 89
    assert budget.usage(root)["reserved_calls"] == budget.usage(root)["responses"] == 90
    assert before == (
        b.digest(old_file),
        b.digest(root / "cloud-clock.json"),
        b.digest(root / "halt-c0.json"),
    )
    assert not (root / "cohorts/c1.json").exists()
