"""D-036 admission and real backend wire boundaries, with local responses only."""

import copy
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.constants import OLLAMA_MODEL
from integration.pokechamp.improved_io import battle_only, battle_only_budget, direct32
from integration.pokechamp.improved_io import experiment_policy as policy
from integration.pokechamp.improved_io import inputfix32 as fix
from integration.pokechamp.improved_io.backend import FixedBackend
from integration.pokechamp.improved_io.battle_prompts import assemble, identity
from integration.pokechamp.improved_io.receipts import source_identity
from integration.pokechamp.permits import PermitBroker
from integration.pokechamp.tests.test_cloud import fake_response


def receipt(tmp_path):
    evidence = tmp_path / "independent.txt"
    evidence.write_text("local test evidence, never a paid admission receipt")
    path = tmp_path / "verification.json"
    value = dict(
        qualification=fix.QUALIFICATION,
        passed=True,
        checks=dict.fromkeys(fix.REQUIRED, True),
        source_files=source_identity(),
        evidence_files={str(evidence): b.digest(evidence)},
        audit=fix.ref(fix.AUDIT / "final-verification.json"),
        runtime_identity=fix.runtime_identity(),
    )
    b.seal_json(path, value)
    return path, value


def test_identity_preserves_three_old_policy_hashes():
    old_source = (
        fix.AUDIT
        / "source-final/integration/pokechamp/improved_io/experiment_policy.py"
    )
    old = {}
    exec(old_source.read_text(), old)
    for name in (policy.LIVE, policy.DIRECT, policy.CALCFIX):
        assert policy.selection(name) == old["selection"](name)
    selected = policy.selection(policy.INPUTFIX)
    assert policy.is_direct(selected) and not policy.is_calcfix(selected)
    assert policy.required_prompt_version(selected) == "v1.2.0"
    assert battle_only_budget.definition(selected)["paid_recovery_limit"] == 0
    assert set(direct32.skipped_for(selected)) == {"fake32", "cloud_gate", "smoke8"}


@pytest.mark.parametrize("version", ["v1.0.0", "v1.1.0"])
def test_old_prompt_rejected_before_preparation(tmp_path, version):
    with pytest.raises(ValueError, match="requires battle prompt v1.2.0"):
        direct32.prepare(
            tmp_path / "prepared",
            experiment_policy=policy.INPUTFIX,
            battle_prompt_version=version,
        )
    assert not (tmp_path / "prepared").exists()


def test_qualification_missing_tampered_and_stale(tmp_path):
    with pytest.raises(ValueError, match="requires sealed"):
        direct32.prepare(tmp_path / "prepared", experiment_policy=policy.INPUTFIX)
    path, value = receipt(tmp_path)
    fix.verify_qualification(path)
    for i, field in enumerate(("checks", "source_files", "runtime_identity", "audit")):
        invalid = copy.deepcopy(value)
        invalid[field] = {}
        target = tmp_path / f"bad-{i}.json"
        b.seal_json(target, invalid)
        with pytest.raises(ValueError):
            fix.verify_qualification(target)
    Path(next(iter(value["evidence_files"]))).write_text("drift")
    with pytest.raises(ValueError, match="evidence drift"):
        fix.verify_qualification(path)


def test_preparation_schedule_execution_and_runtime_seals(tmp_path):
    path, _ = receipt(tmp_path)
    target = tmp_path / "prepared"
    direct32.prepare(target, experiment_policy=policy.INPUTFIX, verification=path)
    prepared = target / "result.json"
    direct32.read_stage(prepared, "prepare")
    manifest = b.read_sealed(target / "manifest.json")
    original = fix.read_ref(manifest["original"]["manifest"])
    assert manifest["compare_schedule"] == original["compare_schedule"]
    assert manifest["battle_prompt_identity"] == identity("v1.2.0")
    study = tmp_path / "study"
    battle_only_budget.register(study, prepared)
    clock = battle_only_budget.clock(study, create=True)
    assert clock["original_first_clock"] == manifest["original"]["first_clock"]
    ex = battle_only.execution(
        prepared, stage="compare32", previous=prepared, study=study
    )
    direct32.require_entry(b.BATTLE_ONLY_COMPARE_CONFIG, ex)
    for key in fix.runtime_identity():
        assert ex["evidence"][key] == manifest[key]
        invalid = copy.deepcopy(ex)
        invalid["evidence"].pop(key)
        with pytest.raises(ValueError, match="runtime identity"):
            direct32.require_entry(b.BATTLE_ONLY_COMPARE_CONFIG, invalid)
    changed = copy.deepcopy(manifest)
    changed["compare_schedule"][0]["actor_seeds"][0] += 1
    with pytest.raises(ValueError, match="compare_schedule mismatch"):
        fix.validate_manifest(changed)
    for key in fix.runtime_identity():
        changed = copy.deepcopy(manifest)
        changed.pop(key)
        with pytest.raises(ValueError, match="runtime identity"):
            fix.validate_manifest(changed)
    changed = copy.deepcopy(manifest)
    changed["battle_prompt_identity"] = identity("v1.1.0")
    with pytest.raises(ValueError, match="v1.2.0"):
        fix.validate_manifest(changed)


@lru_cache(maxsize=1)
def contexts():
    index = b.read_sealed(fix.AUDIT / "replay-final/index.json")
    values = []
    for side in ("p1", "p2"):
        for row in index["rows"]:
            value = b.read_sealed(fix.AUDIT / "replay-final" / (row["key"] + ".json"))[
                "input"
            ]
            if value["identity"]["actor_id"] == side:
                values.append(value)
                break
    assert len(values) == 2
    return values


def backend_for(value, client, socket=None):
    env = {"OLLAMA_API_KEY": "local-fixture"}
    if socket:
        env["POKECHAMP_PERMIT_SOCKET"] = str(socket)
    backend = FixedBackend(environ=env, client_factory=lambda **_: client)
    backend.experiment_policy = policy.selection(policy.INPUTFIX)
    backend.runtime_identity = fix.runtime_identity()
    backend.io_profile = "io-battle-only-v1"
    backend.battle_prompt_identity = identity("v1.2.0")
    backend.input_context = value
    return backend


def test_fake_parallel_wire_preserves_v2_sides_and_limit(tmp_path):
    values = contexts()
    socket = tmp_path / "permit.sock"
    lock = threading.Lock()
    state = dict(active=0, maximum=0)
    delivered = []

    def invoke(i):
        value = copy.deepcopy(values[i % 2])
        original = copy.deepcopy(value)

        def chat(**kwargs):
            with lock:
                state["active"] += 1
                state["maximum"] = max(state["maximum"], state["active"])
            try:
                assert json.loads(kwargs["messages"][-1]["content"]) == original
                assert kwargs["messages"][0]["content"] == assemble(
                    original, version="v1.2.0"
                )
                time.sleep(0.25)
                return fake_response(
                    "Local response.\n"
                    + json.dumps(value["request"]["legal_actions"][0])
                )
            finally:
                with lock:
                    state["active"] -= 1

        backend = backend_for(value, SimpleNamespace(chat=chat), socket)
        backend.get_LLM_action(
            assemble(value, version="v1.2.0"),
            json.dumps(value),
            OLLAMA_MODEL,
            json_format=False,
        )
        assert value == original
        context = backend._request_context()
        assert (
            context["identity"] == value["identity"] == context["calculation_identity"]
        )
        assert all(context[k] == v for k, v in fix.runtime_identity().items())
        assert len(backend.call_records) == 1 and backend.parsed_action
        delivered.append(context)

    with PermitBroker(socket, 10, {OLLAMA_MODEL: 10}) as broker:
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(invoke, range(20)))
        assert 2 <= state["maximum"] <= 10
        assert broker.maximum_total <= 10 and sum(broker.active.values()) == 0
    assert {x["identity"]["actor_id"] for x in delivered} == {"p1", "p2"}
    assert len(delivered) == 20 and not socket.exists()


@pytest.mark.parametrize(
    "mutation", ["runtime", "old_prompt", "old_input", "damage", "history", "foreign"]
)
def test_corruption_rejected_before_transport(mutation):
    value = copy.deepcopy(contexts()[0])
    calls = []
    backend = backend_for(
        value, SimpleNamespace(chat=lambda **kwargs: calls.append(kwargs))
    )
    if mutation == "runtime":
        backend.runtime_identity = {}
    elif mutation == "old_prompt":
        backend.battle_prompt_identity = identity("v1.1.0")
    elif mutation == "old_input":
        value["identity"].pop("input_version")
    elif mutation == "damage":
        value["calculation_bundle"]["entries"].pop()
    elif mutation == "history":
        value["current_observation"]["self_team"][0].pop("ability_history")
    else:
        value["calculation_bundle"]["identity"]["actor_id"] = "p2"
    with pytest.raises((ValueError, RuntimeError)):
        backend.get_LLM_action(
            assemble(version="v1.2.0"),
            json.dumps(value),
            OLLAMA_MODEL,
            json_format=False,
        )
    assert calls == []


def test_cumulative_usage_counts_each_predecessor_once():
    manifest = dict(
        original=fix.predecessor(fix.ORIGINAL, "EX-028", fix.ORIGINAL_PREPARED),
        preceding=fix.predecessor(
            fix.PREVIOUS, "EX-029", fix.PREVIOUS.with_name("ex029-prepared")
        ),
        audit=fix.ref(fix.AUDIT / "final-verification.json"),
    )
    result = dict(
        usage=dict(reserved_calls=2, responses=2, uncertain=0),
        confirmed_tokens={},
        batch_elapsed_seconds=3,
    )
    linked = fix.cumulative_report(manifest, result)
    assert linked["cumulative_usage"] == dict(
        reserved_calls=1212, responses=1211, uncertain=1
    )
    assert linked["original_uncertain_requests"] == 1
    assert linked["usage_experiments_counted_once"] == ["EX-028", "EX-029", "EX-031"]


def test_actual_fixed_player_cadence_uses_new_policy(monkeypatch):
    from integration.pokechamp.improved_io import memory_fixture

    class QualifiedBackend(FixedBackend):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.experiment_policy = policy.selection(policy.INPUTFIX)
            self.runtime_identity = fix.runtime_identity()

    monkeypatch.setattr(memory_fixture, "FixedBackend", QualifiedBackend)
    result = memory_fixture.run(battle_only=True, battle_prompt_version="v1.2.0")
    assert result["passed"] and result["actions"] == 31
    assert result["summaries"] == result["rollups"] == 0
    for call in result["wire_calls"]:
        request = call["request"]
        assert request["experiment_policy"] == policy.INPUTFIX
        assert request["calculator_semantics_version"] == "calculator-input-v2"
        assert (
            request["runtime_patch_identity"]
            == fix.runtime_identity()["runtime_patch_identity"]
        )
