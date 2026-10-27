import json

from integration.project_context.blocked import classified_rows, load_classification
from integration.project_context.catalog import render, validate
from integration.project_context.registry import ROOT, load_registry, record_metadata
from integration.project_context.tests.test_registry import fixture_registry


def test_unclassified_blocked_is_visible_without_becoming_active(tmp_path):
    path, _ = fixture_registry(tmp_path)
    path.write_text("# EP-001 — 표본\n\n- 상태: Blocked — 분모 미달\n")
    before = path.read_bytes()
    pages = render(tmp_path)
    detail = pages[tmp_path / "project_context/catalog/blocked.md"]
    assert "확인 필요" in detail and "관리 분류 미등록" in detail and "[EP-001]" in detail
    plans = pages[tmp_path / "project_context/catalog/plans.md"]
    assert "[EP-001]" not in plans
    assert "[확인 필요](blocked.md#review) | 1" in plans
    assert path.read_bytes() == before
    assert validate(tmp_path) == []


def test_paused_is_not_mixed_into_blocked(tmp_path):
    path, _ = fixture_registry(tmp_path)
    path.write_text("# EP-001 — 표본\n\n- 상태: Paused\n")
    pages = render(tmp_path)
    assert "[EP-001]" in pages[tmp_path / "project_context/catalog/plans.md"]
    assert "[EP-001]" not in pages[tmp_path / "project_context/catalog/blocked.md"]


def test_resolved_requires_a_completed_distinct_evidenced_successor(tmp_path):
    path, _ = fixture_registry(tmp_path)
    path.write_text("# EP-001 — 표본\n\n- 상태: Blocked\n")
    entry = {"category": "resolved", "reason": "후속 처리",
             "evidence": ["EP-001"], "followups": [], "experiments": []}
    sidecar = tmp_path / "project_context/catalog/blocked.json"
    sidecar.write_text(json.dumps({"records": {"EP-001": entry}}))
    assert any("evidenced successor" in x for x in validate(tmp_path))
    entry.update(resolved_by="EP-001", followups=["EP-001"])
    sidecar.write_text(json.dumps({"records": {"EP-001": entry}}))
    assert any("evidenced successor" in x for x in validate(tmp_path))
    entry.update(category="not-a-category", evidence=["EP-999"])
    sidecar.write_text(json.dumps({"records": {"EP-001": entry}}))
    errors = validate(tmp_path)
    assert any("unknown blocked category" in x for x in errors)
    assert any("unknown blocked evidence" in x for x in errors)


def test_real_review_covers_every_blocked_plan_and_preserves_partial_recovery():
    registry = load_registry()
    metadata = {k: record_metadata(ROOT / "project_context" / e["path"])
                for k, e in registry["records"].items()}
    rows = classified_rows(registry, metadata)
    sidecar = load_classification()["records"]
    expected = {k for k, meta in metadata.items()
                if k.startswith("EP-") and meta["state"] == "Blocked"}
    assert set(rows) == expected
    assert set(sidecar) <= set(rows)
    assert rows["EP-140"]["resolved_by"] == "EP-141"
    assert rows["EP-179"]["resolved_by"] == "EP-180"
    assert rows["EP-108"]["category"] == "review"
    assert rows["EP-041"]["category"] == "ended"
    assert "EP-126" not in rows
    assert validate() == []
