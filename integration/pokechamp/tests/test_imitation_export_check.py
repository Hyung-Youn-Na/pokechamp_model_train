"""실제 Chromium helper의 합성 export 회귀; 실제 배틀 evidence가 아니다."""

from __future__ import annotations

import json
import shutil

import pytest

from integration.pokechamp.imitation import battle, browser_check, reporting, viewer
from integration.pokechamp.imitation.storage import atomic, read, sha
from integration.pokechamp.tests import test_imitation_battle as fixtures

snapshot = fixtures.snapshot
choice = fixtures.choice
schedule = fixtures.schedule
viewer_source = fixtures.viewer_source


def test_actual_browser_helper_checks_moved_synthetic_export_and_preserves_seals(
    viewer_source, tmp_path
):
    pytest.importorskip("playwright.sync_api")
    mixed = tmp_path / "synthetic-mixed-status-source"
    shutil.copytree(viewer_source, mixed)
    summary = read(mixed / "result.json")
    summary["outcomes"][0]["status"] = "failed"
    summary["outcomes"][1]["status"] = "incomplete"
    summary = dict(
        reporting.summarize(read(mixed / "manifest.json")["schedule"], summary["outcomes"]),
        outcomes=summary["outcomes"],
    )
    atomic(mixed / "result.json", summary)
    atomic(mixed / "report.md", reporting.report_markdown(summary).encode())
    (mixed / "checksums.sha256").unlink()
    battle.seal(mixed)
    output = tmp_path / "export"
    viewer.export(mixed, output)
    before = {path: sha(path / "checksums.sha256") for path in (viewer_source, mixed, output)}
    receipt = tmp_path / "browser-check.json"
    assert browser_check.main(["--viewer", str(output), "--receipt", str(receipt)]) == 0
    result = read(receipt)
    assert result["passed"] and result["originals_unchanged"]
    assert result["index_rows"] == result["checked_pages"] == 40
    assert result["checked_decisions"] == 3 and result["page_errors"] == []
    assert result["pages"][0]["checked_indices"] == [0, 1, 2]
    assert result["pages"][0]["downloads"] == 1
    assert result["pages"][0]["navigation"] and result["pages"][0]["keyboard"]
    assert [page["status"] for page in result["pages"][:3]] == [
        "failed",
        "incomplete",
        "unattempted",
    ]
    assert all(page["decision_count"] == 0 for page in result["pages"][1:])
    assert result["playwright_version"] and result["chromium_version"]
    assert result["model_calls"] == result["battle_calls"] == 0
    assert {path: sha(path / "checksums.sha256") for path in before} == before
    with pytest.raises(FileExistsError, match="already exists"):
        browser_check.check(output, receipt)


def test_browser_helper_rejects_tampered_export_before_opening_browser(viewer_source, tmp_path):
    output = tmp_path / "export"
    viewer.export(viewer_source, output)
    (output / "battle-01/decisions.json").write_text(json.dumps({"changed": True}))
    result = browser_check.check(output, tmp_path / "rejected.json")
    assert not result["passed"] and result["checked_pages"] == 0
    assert "sealed entry" in result["errors"][0]["detail"]


def test_browser_helper_cannot_write_receipt_into_sealed_export(viewer_source, tmp_path):
    output = tmp_path / "export"
    viewer.export(viewer_source, output)
    with pytest.raises(ValueError, match="outside the sealed viewer"):
        browser_check.check(output, output / "browser-check.json")
    assert not (output / "browser-check.json").exists()


def test_browser_helper_cannot_write_receipt_into_sealed_source(viewer_source, tmp_path):
    output = tmp_path / "export"
    viewer.export(viewer_source, output)
    before = browser_check.sealed_files(viewer_source)
    with pytest.raises(ValueError, match="outside the sealed source"):
        browser_check.check(output, viewer_source / "browser-check.json")
    assert browser_check.sealed_files(viewer_source) == before
