"""EP-117의 원본 보존·동일 통계·원 시계·전수 검증 gate."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts/pokechamp-selfplay-finalization-v3.py"
)
spec = importlib.util.spec_from_file_location("selfplay_finalization_recovery", PATH)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def test_deadline_has_no_extension():
    recovery.require_time(SimpleNamespace(remaining=lambda: 16))
    with pytest.raises(TimeoutError):
        recovery.require_time(SimpleNamespace(remaining=lambda: 15))


def test_original_pin_rejects_changed_file(tmp_path):
    path = tmp_path / "original-report.json"
    path.write_text("unchanged")
    pins = {str(path): recovery.sha(path)}
    recovery.verify_pins(pins)
    path.write_text("changed")
    with pytest.raises(ValueError, match="preserved artifact changed"):
        recovery.verify_pins(pins)


def test_only_completion_bookkeeping_may_change():
    original = {
        "paired": {"difference": 0.0875},
        "probability": {"brier": 0.2},
        "experiment_complete": False,
        "stage_status": {"viewer": False},
        "incomplete_requirements": ["viewer", "sealed", "finalization"],
    }
    new = dict(
        original,
        experiment_complete=True,
        stage_status={"viewer": True},
        incomplete_requirements=[],
    )
    recovery.compare_statistics(original, new)
    new["paired"] = {"difference": 0.2}
    with pytest.raises(ValueError, match="statistical output differs"):
        recovery.compare_statistics(original, new)


@pytest.fixture
def browser_receipt(tmp_path):
    (tmp_path / "checksums.sha256").write_text("source seal")
    receipt = {
        "passed": True,
        "source_unchanged": True,
        "export_unchanged": True,
        "moved_copy_verified": True,
        "offline": True,
        "checked_completed_pages": 2,
        "completed": 2,
        "pages": [{"passed": True}, {"passed": True}],
        "source_seal_sha256": recovery.sha(tmp_path / "checksums.sha256"),
        "export_seal_sha256": "fixed-export-sha",
        "verifier_sha256": recovery.sha(Path(recovery.viewer.__file__)),
        "javascript_errors": [],
        "external_requests": [],
    }
    return receipt, {"export_sha256": "fixed-export-sha"}, tmp_path


def test_complete_browser_receipt_required(browser_receipt):
    receipt, exported, source = browser_receipt
    recovery.verify_browser_receipt(receipt, exported, source, 2)


@pytest.mark.parametrize(
    "field,value",
    [
        ("passed", False),
        ("offline", False),
        ("source_unchanged", False),
        ("checked_completed_pages", 1),
        ("pages", [{"passed": True}]),
        ("pages", [{"passed": True}, {"passed": False}]),
        ("verifier_sha256", "changed"),
        ("external_requests", ["https://external.invalid"]),
    ],
)
def test_partial_or_changed_browser_receipt_rejected(browser_receipt, field, value):
    receipt, exported, source = browser_receipt
    receipt = copy.deepcopy(receipt)
    receipt[field] = value
    with pytest.raises(ValueError):
        recovery.verify_browser_receipt(receipt, exported, source, 2)


def test_prior_correction_is_preserved(tmp_path, monkeypatch):
    old = tmp_path / "run/corrections/finalization-v3"
    old.mkdir(parents=True)
    (old / "report.md").write_text("prior evidence")
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    monkeypatch.setattr(
        recovery,
        "preflight",
        lambda *_: {
            "directory": tmp_path / "run",
            "clock": SimpleNamespace(remaining=lambda: 100),
        },
    )
    with pytest.raises(FileExistsError):
        recovery.recover(tmp_path / "run", tmp_path / "validation.json")
    assert (old / "report.md").read_text() == "prior evidence"
    assert not (tmp_path / "exports").exists()


def test_budget_failure_creates_no_new_output(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    monkeypatch.setattr(
        recovery,
        "preflight",
        lambda *_: {
            "directory": tmp_path / "run",
            "clock": SimpleNamespace(remaining=lambda: 0),
        },
    )
    with pytest.raises(TimeoutError):
        recovery.recover(tmp_path / "run", tmp_path / "validation.json")
    assert list(tmp_path.iterdir()) == []


def test_raw_inventory_detects_addition_and_content_change(tmp_path):
    game = tmp_path / "games/slot"
    game.mkdir(parents=True)
    (game / "outcome.json").write_text('{"result":"win"}')
    original = recovery.raw_inventory(tmp_path)
    (game / "outcome.json").write_text('{"result":"loss"}')
    assert recovery.raw_inventory(tmp_path) != original
    (game / "outcome.json").write_text('{"result":"win"}')
    (game / "extra.json").write_text("{}")
    assert recovery.raw_inventory(tmp_path) != original


@pytest.mark.parametrize("fail_verification", [1, 2])
def test_seal_failure_never_publishes_complete_receipt(
    tmp_path, monkeypatch, fail_verification
):
    staged = tmp_path / ".correction-staging"
    exported = tmp_path / ".export-staging"
    staged.mkdir()
    exported.mkdir()
    (staged / "completed.json").write_text('{"experiment_complete":true}')
    (exported / "index.html").write_text("staged export")
    calls = []

    def reject(path):
        calls.append(path)
        if len(calls) == fail_verification:
            raise ValueError("independent seal verification failed")

    monkeypatch.setattr(recovery.viewer, "verify_source", reject)
    with pytest.raises(ValueError):
        recovery.commit_staged(
            staged,
            exported,
            tmp_path / "final",
            tmp_path / "export",
            SimpleNamespace(remaining=lambda: 100),
        )
    assert not (tmp_path / "final").exists()
    assert not (tmp_path / "export").exists()
    assert (staged / "completed.json").exists()


def test_success_is_committed_only_after_both_seals(tmp_path):
    staged, exported = tmp_path / ".staging", tmp_path / ".export-staging"
    staged.mkdir()
    exported.mkdir()
    (staged / "completed.json").write_text('{"experiment_complete":true}')
    (exported / "index.html").write_text("verified export")
    for folder in (staged, exported):
        for name in ("manifest.json", "result.json", "report.md"):
            (folder / name).write_text("independent fixture evidence")
    recovery.commit_staged(
        staged,
        exported,
        tmp_path / "final",
        tmp_path / "export",
        SimpleNamespace(remaining=lambda: 100),
    )
    assert not staged.exists() and not exported.exists()
    assert recovery.viewer.verify_source(tmp_path / "final")
    assert recovery.viewer.verify_source(tmp_path / "export")
