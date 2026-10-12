"""D-032 admission boundaries, sealed policy propagation and legacy budget regression."""

import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.improved_io import battle_only_budget as budget
from integration.pokechamp.improved_io import battle_only_gate as gate
from integration.pokechamp.improved_io import battle_only_protocol as protocol
from integration.pokechamp.improved_io import experiment_policy as policy
from integration.pokechamp.improved_io.receipts import require_budget, source_identity
from integration.pokechamp.tests.test_battle_only import context, defect_record


@pytest.fixture
def registered(tmp_path):
    prepared = tmp_path / "prepared/result.json"
    b.seal_json(prepared, dict(**policy.selection(policy.LIVE), profile=protocol.PROFILE,
                              source_files=source_identity(), passed=True))
    root = tmp_path / "study"
    budget.register(root, prepared)
    return root, prepared


@pytest.mark.parametrize("change", ["name", "null_name", "missing_identity", "missing_limit",
                                    "numeric_limit", "hash", "orphan", "boolean_type"])
def test_unknown_missing_or_altered_policy_is_rejected(change):
    value = policy.selection(policy.LIVE)
    if change == "name":
        value["experiment_policy"] = "unapproved"
    elif change == "null_name":
        value["experiment_policy"] = None
    elif change == "missing_identity":
        del value["experiment_policy_identity"]
    elif change == "missing_limit":
        del value["experiment_policy_identity"]["call_limit"]
    elif change == "numeric_limit":
        value["experiment_policy_identity"]["call_limit"] = 4000
    elif change == "hash":
        value["experiment_policy_identity"]["sha256"] = "bad"
    elif change == "boolean_type":
        value["experiment_policy_identity"]["explanation_errors_block_entry"] = 0
    else:
        del value["experiment_policy"]
    with pytest.raises(ValueError, match="policy"):
        policy.selected(value)
    assert policy.selected({}) == {}


def test_live_reserves_after_four_hours_and_four_thousand_calls(registered, monkeypatch):
    root, _ = registered
    ids = [s["id"] for s in gate.schedule()]
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "out")
    first = budget.clock(root, create=True, now=100)
    assert first["stop_new_work_at"] is first["cleanup_deadline"] is None
    require_budget(first, 10**10, now=100 + 14401)
    original = Path.glob

    def glob(path, pattern):
        if path == root / "requests" and pattern == "intent-*.json":
            return iter(Path(f"intent-{i:06}.json") for i in range(4000))
        return original(path, pattern)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "glob", glob)
        intent = budget.reserve(root, "c0", "cloud_gate", ids[0], {})
        assert intent.name == "intent-004001.json"
    assert budget.clock(root, create=True, now=90000) == first
    assert budget.usage(root)["remaining_calls"] is None
    assert budget.usage(root)["uncertain"] == 1
    with pytest.raises(ValueError, match="duplicate"):
        budget.reserve(root, "c0", "cloud_gate", ids[0], {})


def test_null_deadline_requires_verified_study_and_full_policy(registered, tmp_path):
    root, _ = registered
    clock = budget.clock(root, create=True, now=100)
    fake = copy.deepcopy(clock)
    fake["study"]["sha256"] = "bad"
    with pytest.raises(ValueError):
        require_budget(fake)
    for key in ("experiment_policy", "experiment_policy_identity"):
        broken = copy.deepcopy(clock)
        del broken[key]
        with pytest.raises(ValueError):
            require_budget(broken)
    with pytest.raises(ValueError, match="bounded clock"):
        require_budget(dict(stop_new_work_at=None))
    with pytest.raises(ValueError, match="budget_stop"):
        require_budget(dict(stop_new_work_at=13600), now=14501)


def test_live_atomic_journal_restart_halt_and_recovery_once(registered, tmp_path, monkeypatch):
    root, prepared = registered
    ids = [s["id"] for s in gate.schedule()]
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "out")
    budget.clock(root, create=True, now=100)
    with ThreadPoolExecutor(max_workers=10) as pool:
        paths = list(pool.map(lambda i: budget.reserve(root, "c0", "cloud_gate", i, {}), ids[:10]))
    assert len(set(paths)) == 10
    budget.preserve_response(paths[0], {"message": {"content": "original"}})
    before = b.digest(root / "cloud-clock.json")
    budget.halt(root, "c0", "input", prepared)
    original_halt = b.digest(root / "halt-c0.json")
    monkeypatch.setattr(protocol, "read_stage", lambda *a, **k: b.read_sealed(prepared))
    defect = tmp_path / "defect.json"
    b.seal_json(defect, defect_record(root, prepared, tmp_path))
    result = budget.recover(root, defect, prepared)
    assert result["usage_before"]["reserved_calls"] == 10
    assert result["usage_before"]["uncertain"] == 9
    policy.same(budget.require_cohort(root, "c1"), b.read_sealed(prepared))
    assert b.digest(root / "cloud-clock.json") == before
    assert b.digest(root / "halt-c0.json") == original_halt
    with pytest.raises(FileExistsError):
        budget.recover(root, defect, prepared)


def test_recovery_cannot_change_experiment_policy(registered, tmp_path, monkeypatch):
    root, prepared = registered
    monkeypatch.setattr(protocol, "read_stage", lambda *a, **k: dict(source_files=source_identity()))
    defect = tmp_path / "defect.json"
    b.seal_json(defect, defect_record(root, prepared, tmp_path))
    with pytest.raises(ValueError, match="policy mismatch"):
        budget.recover(root, defect, prepared)


@pytest.fixture
def collected(registered, tmp_path, monkeypatch):
    """Synthetic complete wire/journal evidence; no provider or network is invoked."""
    root, prepared = registered
    selection = policy.selection(policy.LIVE)
    directory = tmp_path / "gate"
    system = "Sealed test system prompt."
    prompt = dict(version="v1.1.0", prompt_sha256=hashlib.sha256(system.encode()).hexdigest())
    state = context()
    user = json.dumps(state)
    content = 'I choose a legal attack.\n{"move":"surf"}'
    b.seal_json(prepared.parent / "manifest.json", dict(**selection, battle_prompt_identity=prompt))
    items = gate.schedule(10)  # This fixture represents a legacy declaration.
    budget.claim_stage(root, "c0", "cloud_gate", [i["id"] for i in items], directory)
    b.seal_json(directory / "inputs.json", dict(**selection, prepared=protocol.ref(prepared),
                scenes={i["case"]: state for i in items}))
    calls, outputs = {}, {}
    for item in items:
        intent = budget.reserve(root, "c0", "cloud_gate", item["id"],
                                dict(system_prompt=system, user_prompt=user))
        response = budget.preserve_response(intent, dict(message=dict(content=content)))
        name = item["id"] + ".json"
        row = dict(**selection, item_id=item["id"], role="self_action", context=state,
                   battle_prompt_identity=prompt, valid=True, category=None,
                   **{k: item[k] for k in ("case", "repeat", "concurrency")},
                   trace=dict(system_prompt=system, user_prompt=user, raw_content=content,
                       response=dict(http_status=200), request=dict(
                           battle_prompt_identity=prompt, request_intent=str(intent),
                           worker_response=str(response))))
        b.seal_json(directory / name, row)
        outputs[name] = b.digest(directory / name)
        calls[name] = dict(response_sha256=outputs[name], facts=False, identity=True,
                           timing=True, calculation=True, action_contract=True,
                           evidence="Synthetic fact error retained against the original input.")
    collection = dict(**selection, technical_passed=True, uncertain=0, failures=0,
                      call_outputs=outputs, local=protocol.ref(prepared))
    b.seal_json(directory / "collection.json", collection)
    audit = dict(collection_sha256=b.digest(directory / "collection.json"), calls=calls)
    review = tmp_path / "review.json"
    b.seal_json(review, audit)
    monkeypatch.setattr(protocol, "read_stage", lambda *a, **k: b.read_sealed(prepared))
    return root, directory, review


def test_legal_explanation_errors_allow_live_entry_without_semantic_pass(collected):
    root, directory, review = collected
    result = gate.finish(root, directory, review)
    assert result["passed"] and result["semantic_review"] == "failed"
    assert len(result["semantic_errors"]) == 90
    assert not (root / "halt-c0.json").exists()
    assert policy.review_blocks({}, result["semantic_errors"])


@pytest.mark.parametrize("change", ["missing_review", "output", "illegal", "policy", "prompt",
                                    "input", "hash", "journal"])
def test_live_entry_rejects_missing_review_or_corrupt_evidence(collected, tmp_path, change):
    root, directory, review = collected
    collection = b.read_sealed(directory / "collection.json")
    rows = {name: dict(b.read_sealed(directory / name), sha256=digest)
            for name, digest in collection["call_outputs"].items()}
    audit = b.read_sealed(review)
    name = next(iter(rows))
    if change == "missing_review":
        del audit["calls"][name]
        with pytest.raises(ValueError, match="denominator"):
            gate.validate_review(rows, audit, collection_hash=b.digest(directory / "collection.json"))
        return
    row = rows[name]
    if change == "output":
        row["trace"]["raw_content"] = 'I choose an attack. {"move":"surf"}'
    elif change == "illegal":
        row["trace"]["raw_content"] = 'I choose an attack.\n{"move":"illegal"}'
    elif change == "policy":
        del row["experiment_policy_identity"]
    elif change == "prompt":
        row["trace"]["system_prompt"] += "changed"
    elif change == "input":
        row["trace"]["user_prompt"] = "{}"
    elif change == "hash":
        row["battle_prompt_identity"]["prompt_sha256"] = "bad"
    else:
        row["trace"]["request"]["worker_response"] = str(tmp_path / "missing.json")
    with pytest.raises((ValueError, FileNotFoundError)):
        gate.validate_live_collection(directory, collection, rows)


def test_reviewed_action_contract_error_blocks_live_entry(collected, tmp_path):
    root, directory, original = collected
    audit = b.read_sealed(original)
    audit["calls"][next(iter(audit["calls"]))]["action_contract"] = False
    review = tmp_path / "action-review.json"
    b.seal_json(review, audit)
    result = gate.finish(root, directory, review)
    assert not result["passed"] and (root / "halt-c0.json").exists()


def test_actual_legacy_receipts_still_verify_without_current_source():
    root = b.WORKSPACE_ROOT / ".pokechamp-data"
    for path, stage in (
        ("io-battle-only/ex026-preflight/prepare/result.json", "prepare"),
        ("battle-field-guide/ep019/fake32-validated/result.json", "fake32"),
    ):
        assert protocol.read_stage(root / path, stage, current=False)["passed"]


def test_live_worker_with_no_deadline_preserves_wire_and_uses_broker(registered, tmp_path, monkeypatch):
    from types import SimpleNamespace

    from integration.pokechamp.improved_io import battle_prompts, cloud_gate
    from integration.pokechamp.improved_io.backend import FixedBackend
    from integration.pokechamp.permits import PermitBroker

    root, _ = registered
    state = b.read_sealed(b.WORKSPACE_ROOT /
        ".pokechamp-data/io-battle-only/ex026-preflight/prepare/offline/IO-C01.json")
    ids = [s["id"] for s in gate.schedule()]
    budget.claim_stage(root, "c0", "cloud_gate", ids, root / "out")
    budget.clock(root, create=True, now=100)
    calls = []

    def chat(**kwargs):
        calls.append(kwargs)
        return dict(model="glm-5.3-flash", done=True, done_reason="stop",
                    message=dict(content="This is a local delivery fixture.\n" +
                                 json.dumps(state["request"]["legal_actions"][0])))

    class Local(FixedBackend):
        def __init__(self, **kwargs):
            assert "POKECHAMP_BATCH_DEADLINE" not in kwargs["environ"]
            kwargs["environ"]["OLLAMA_API_KEY"] = "fixture-api-key-marker"
            super().__init__(**kwargs, client_factory=lambda **_: SimpleNamespace(chat=chat))

    monkeypatch.setenv("POKECHAMP_BATCH_DEADLINE", "1")
    monkeypatch.setattr(cloud_gate.cli, "_load_cloud_credential", lambda: None)
    monkeypatch.setattr(cloud_gate, "FixedBackend", Local)
    item = dict(**policy.selection(policy.LIVE), **battle_prompts.selection("v1.1.0"),
                profile=protocol.PROFILE, id=ids[0], role="self_action", context=state,
                study_root=str(root), cohort="c0", output_path=str(tmp_path / "wire.json"))
    with PermitBroker(tmp_path / "p.sock", 10, {"glm-5.3-flash": 10}, deadline=None) as broker:
        result = cloud_gate.call(item, str(broker.path), None)
        assert broker.snapshot()["maximum_account_permits"] == 1
    assert result["valid"] and len(calls) == 1
    assert calls[0]["messages"][0]["content"].count("BATTLE INPUT FIELD GUIDE v1.1.0") == 1
    assert calls[0]["think"] == "low"
    assert calls[0]["options"] == dict(temperature=0.0, num_predict=131072, seed=100)
    assert budget.usage(root)["reserved_calls"] == budget.usage(root)["responses"] == 1
