"""New qualification cannot alter or bypass the original one-shot policy."""

import copy
from pathlib import Path

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.improved_io import calcfix32, direct32
from integration.pokechamp.improved_io import experiment_policy as policy
from integration.pokechamp.improved_io.battle_only_budget import definition
from integration.pokechamp.improved_io.receipts import source_identity


def test_policy_identity_preserves_original_and_isolates_repeat():
    original = policy.selection(policy.DIRECT)
    assert original["experiment_policy_identity"]["sha256"] == (
        "2771f8ac2268c0de0bd038e97cb3f8d76da3d3ff9c1bb83facc74e5bb0f58f2a"
    )
    new = policy.selection(policy.CALCFIX)
    assert policy.is_direct(new) and policy.is_calcfix(new)
    assert definition(new)["decision"] == "D-034"
    assert definition(new)["paid_recovery_limit"] == 0
    assert definition(new)["stage_caps"] == {"compare32": 32}
    assert "regression" not in direct32.skipped_for(new)
    assert direct32.skipped_for(original) == direct32.SKIPPED
    with pytest.raises(ValueError, match="policy mismatch"):
        policy.same(original, new)
    tampered = copy.deepcopy(new)
    tampered["experiment_policy_identity"]["paid_recovery_limit"] = 1
    with pytest.raises(ValueError, match="identity mismatch"):
        policy.selected(tampered)


def receipt(tmp_path):
    evidence = tmp_path / "independent.txt"
    evidence.write_text("local test evidence")
    value = dict(
        qualification="calculator-clone-independent-regression-v1",
        passed=True,
        checks=dict.fromkeys(calcfix32.REQUIRED, True),
        source_files=source_identity(),
        evidence_files={str(evidence): b.digest(evidence)},
    )
    path = tmp_path / "verification.json"
    b.seal_json(path, value)
    return path, value


def test_prepare_requires_qualification_before_creating_output(tmp_path):
    target = tmp_path / "prepared"
    with pytest.raises(ValueError, match="requires sealed"):
        direct32.prepare(target, experiment_policy=policy.CALCFIX)
    assert not target.exists()


def test_qualification_fails_closed_on_missing_check_evidence_or_source(tmp_path):
    path, value = receipt(tmp_path)
    calcfix32.verify_qualification(path)
    for i, field in enumerate(("checks", "source_files")):
        invalid = copy.deepcopy(value)
        invalid[field] = {}
        target = tmp_path / f"invalid{i}.json"
        b.seal_json(target, invalid)
        with pytest.raises(ValueError):
            calcfix32.verify_qualification(target)
    Path(next(iter(value["evidence_files"]))).write_text("changed")
    with pytest.raises(ValueError, match="evidence drift"):
        calcfix32.verify_qualification(path)


def test_calcfix_preparation_preserves_exact_original_cohort(tmp_path):
    path, _ = receipt(tmp_path)
    target = tmp_path / "prepared"
    prepared = direct32.prepare(
        target, experiment_policy=policy.CALCFIX, verification=path
    )
    assert prepared["experiment_policy_identity"]["experiment_id"] == "EX-029"
    direct32.read_stage(target / "result.json", "prepare")
    manifest = b.read_sealed(target / "manifest.json")
    original = b.read_sealed(calcfix32.ORIGINAL_PREPARED / "manifest.json")
    assert manifest["compare_schedule"] == original["compare_schedule"]
    assert manifest["original"]["first_clock"]["path"].endswith(
        "ex028/cloud-clock.json"
    )
    manifest["compare_schedule"][0]["actor_seeds"][0] += 1
    with pytest.raises(ValueError, match="compare_schedule mismatch"):
        calcfix32.validate_manifest(manifest)


@pytest.mark.parametrize(
    "name,expected",
    [(policy.DIRECT, "ex028-c0-compare32"), (policy.CALCFIX, "ex029-c0-compare32")],
)
def test_default_run_directory_preserves_original_convention(
    tmp_path, monkeypatch, name, expected
):
    from integration.pokechamp.improved_io import battle_only, battle_only_budget

    selected = policy.selection(name)
    monkeypatch.setattr(direct32, "read_stage", lambda *a, **k: selected)
    monkeypatch.setattr(battle_only_budget, "require_cohort", lambda *a, **k: {})
    monkeypatch.setattr(battle_only_budget, "clock", lambda *a, **k: {})
    monkeypatch.setattr(battle_only_budget, "claim_stage", lambda *a, **k: None)
    monkeypatch.setattr(
        battle_only, "execution", lambda *a, **k: {"evidence": selected}
    )
    monkeypatch.setattr(
        b, "read_sealed", lambda *a: {**selected, "compare_schedule": []}
    )
    monkeypatch.setattr(b, "seal_json", lambda *a: None)

    def capture(root, experiment_id, *args):
        assert experiment_id == expected
        raise RuntimeError("local admission capture; no execution")

    monkeypatch.setattr(b, "plan", capture)
    with pytest.raises(RuntimeError, match="local admission capture"):
        direct32.run(
            tmp_path,
            tmp_path / "prepared/result.json",
            tmp_path / "stage",
            study=tmp_path / "study",
        )


def test_poststop_correction_rejects_foreign_source_or_slots(tmp_path):
    defect = tmp_path / "defects"
    defect.mkdir()
    manifest = dict(
        source_files={"worker": "sealed"}, compare_schedule=[{"slot_id": "B-one"}]
    )
    impact = dict(
        experiment="EX-029",
        collection_source_files={"worker": "sealed"},
        matches=[dict(slot_id="B-one", first_contamination={"turn": 2})],
        invalid_slots=["B-one"],
        changed_inputs=1,
        runtime_fix_applied=False,
    )
    b.seal_json(defect / "reentry-impact.json", impact)
    b.seal_json(defect / "reentry-independent.json", dict(passed=True))
    b.seal_json(tmp_path / "halt-c0.json", dict(category="calculation"))
    assert calcfix32.defect_correction(tmp_path, manifest)["invalid_slots"] == ["B-one"]
    for changed in (
        dict(source_files={"worker": "changed"}),
        dict(compare_schedule=[]),
    ):
        with pytest.raises(ValueError, match="provenance mismatch"):
            calcfix32.defect_correction(tmp_path, {**manifest, **changed})
