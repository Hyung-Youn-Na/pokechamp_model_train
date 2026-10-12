"""EP-117: 독립 큰 정수 사례로 실제 Chromium JSON 표시·복사·다운로드를 검증한다."""

from __future__ import annotations

import copy
import importlib.util
import json
import time
from pathlib import Path

import pytest

from integration.pokechamp.imitation.storage import read, sha, write_jsonl
from integration.pokechamp.selfplay import viewer
from integration.pokechamp.tests import test_selfplay_viewer as fixtures

source = fixtures.source

HELPER = Path(__file__).resolve().parents[3] / "scripts/selfplay_viewer_exact_json.py"
SPEC = importlib.util.spec_from_file_location("selfplay_viewer_exact_json", HELPER)
exact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exact)

OBSERVED_SEED = 12032933256718738492
UNSAFE_POSITIVE = 9007199254740993
UNSAFE_NEGATIVE = -9007199254740995
MAX_UINT64 = 18446744073709551615
ESCAPED = '</script><script>window.exact_json_injected="bad"</script>&end'


@pytest.fixture
def large_source(source):
    path = source / "games/synthetic-complete/events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    for event in events:
        if event.get("decision") != "model-call":
            continue
        if event["type"] == "input":
            event["body"]["diagnostic"] = {"signed": UNSAFE_NEGATIVE, "text": ESCAPED}
            event["body_json"] = json.dumps(event["body"], ensure_ascii=False)
            event["boundary"] = {
                "seed": MAX_UINT64,
                "nested": [UNSAFE_NEGATIVE, UNSAFE_POSITIVE],
            }
        if event["type"] == "response":
            event["body"].update(
                rng_seed=OBSERVED_SEED,
                sampling_seed=UNSAFE_POSITIVE,
                rng={"seed": MAX_UINT64, "nested": {"seed": UNSAFE_NEGATIVE}},
                diagnostic=ESCAPED,
            )
    model_input = next(
        event["body"]
        for event in events
        if event.get("decision") == "model-call" and event["type"] == "input"
    )
    events.append(
        {
            "type": "http_request",
            "decision": "model-call",
            "body": {
                "input": model_input,
                "seed": OBSERVED_SEED,
                "nested": {"seed": UNSAFE_NEGATIVE},
            },
        }
    )
    records = [
        json.loads(line)
        for line in (source / "decisions.jsonl").read_text().splitlines()
    ]
    records[0]["model_version"] = {"synthetic_sequence": MAX_UINT64}
    write_jsonl(path, events)
    write_jsonl(source / "decisions.jsonl", records)
    (source / "checksums.sha256").unlink()
    viewer._seal(source)
    return source


@pytest.fixture
def original(large_source, tmp_path):
    leaf = tmp_path / "original-export"
    receipt = viewer.export(large_source, leaf)
    return leaf, receipt


def test_standalone_copy_changes_only_registered_html_and_provenance(
    large_source, original, tmp_path
):
    old, receipt = original
    old_files, source_files = exact._inventory(old), exact._inventory(large_source)
    frozen_viewer_sha = sha(Path(viewer.__file__))
    receipt_before = copy.deepcopy(receipt)
    target = tmp_path / "corrected-export"
    new_receipt, files = exact.copy_export(
        old, target, receipt, deadline=time.time() + 60
    )
    after = exact._inventory(target)
    changed = {name for name in old_files if old_files[name] != after[name]}
    assert changed == {
        "battle-001/index.html",
        "battle-002/index.html",
        "provenance.json",
        "checksums.sha256",
    }
    assert set(after) == set(old_files)
    assert exact._inventory(old) == old_files
    assert exact._inventory(large_source) == source_files
    assert sha(Path(viewer.__file__)) == frozen_viewer_sha
    assert files == viewer.verify_source(target)
    assert "checksums.sha256" not in files
    assert receipt == receipt_before
    assert new_receipt == dict(
        receipt,
        index=str(target / "index.html"),
        export_sha256=sha(target / "checksums.sha256"),
    )
    provenance = read(target / "provenance.json")
    assert provenance["original_builder_sha256"] == frozen_viewer_sha
    assert provenance["builder_sha256"] == sha(HELPER)
    assert (
        provenance["exact_json_correction"]["original_export_seal_sha256"]
        == receipt["export_sha256"]
    )
    assert provenance["source_files"] == read(old / "provenance.json")["source_files"]


def test_real_browser_preserves_integer_types_in_panels_clipboard_and_download(
    large_source, original, tmp_path
):
    playwright = pytest.importorskip("playwright.sync_api")
    old, receipt = original
    target = tmp_path / "corrected-browser-export"
    exact.copy_export(old, target, receipt, deadline=time.time() + 60)
    data = read(target / "battle-001/decisions.json")
    expected = data["decisions"][1]
    before = copy.deepcopy(data)
    assert exact.corrected_page(data) == (target / "battle-001/index.html").read_text()
    assert data == before
    with playwright.sync_playwright() as work:
        browser = work.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                offline=True, permissions=["clipboard-read", "clipboard-write"]
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(
                (target / "battle-001/index.html").as_uri(),
                wait_until="domcontentloaded",
            )
            page.locator("#decision").select_option("1")
            response = json.loads(page.locator("#response").text_content())
            request = json.loads(page.locator("#request").text_content())
            model_input = json.loads(page.locator("#input").text_content())
            technical = json.loads(page.locator("#technical").text_content())
            calibration = json.loads(page.locator("#calibration").text_content())
            assert response == expected["response"] and request == expected["request"]
            assert model_input == expected["input"]
            assert (
                type(response["rng_seed"]) is int
                and response["rng_seed"] == OBSERVED_SEED
            )
            assert (
                type(response["sampling_seed"]) is int
                and response["sampling_seed"] == UNSAFE_POSITIVE
            )
            assert response["rng"]["seed"] == MAX_UINT64
            assert response["rng"]["nested"]["seed"] == UNSAFE_NEGATIVE
            assert (
                request["seed"] == OBSERVED_SEED
                and request["nested"]["seed"] == UNSAFE_NEGATIVE
            )
            assert model_input["diagnostic"]["signed"] == UNSAFE_NEGATIVE
            assert technical["boundary"]["seed"] == MAX_UINT64
            assert calibration["model_version"]["synthetic_sequence"] == MAX_UINT64
            assert page.locator("#candidates tr.selected td").all_text_contents()[
                2:6
            ] == ["75.000%", "20.000%", "30.000%", "50.000%"]
            for panel in ("input", "response"):
                page.locator(f'[data-copy="{panel}"]').click()
                clipboard = page.evaluate("navigator.clipboard.readText()")
                assert json.loads(clipboard) == expected[panel]
            with page.expect_download() as pending:
                page.locator("#download").click()
            downloaded = Path(pending.value.path()).read_text()
            decoded = json.loads(downloaded)
            assert decoded == expected
            assert type(decoded["response"]["rng_seed"]) is int
            assert f'"rng_seed": {OBSERVED_SEED}' in downloaded
            assert decoded["request"]["nested"]["seed"] == UNSAFE_NEGATIVE
            assert decoded["response"]["diagnostic"] == ESCAPED
            assert json.loads(page.locator("#data").text_content()) == data
            assert page.evaluate("window.exact_json_injected") is None
            assert not errors
            context.close()
        finally:
            browser.close()


def test_original_strict_verifier_detects_loss_and_passes_unchanged_for_corrected_copy(
    large_source, original, tmp_path
):
    pytest.importorskip("playwright.sync_api")
    old, receipt = original
    source_before, old_before = exact._inventory(large_source), exact._inventory(old)
    with pytest.raises(ValueError, match="model input differs"):
        viewer.verify_browser(large_source, old, receipt)
    target = tmp_path / "strict-corrected-export"
    corrected, files = exact.copy_export(
        old, target, receipt, deadline=time.time() + 60
    )
    checked = viewer.verify_browser(large_source, target, corrected)
    assert checked["passed"] and checked["checked_completed_pages"] == 1
    assert checked["source_unchanged"] and checked["export_unchanged"]
    assert checked["verifier_sha256"] == sha(Path(viewer.__file__))
    assert (
        exact._inventory(large_source) == source_before
        and exact._inventory(old) == old_before
    )
    assert viewer.verify_source(target) == files


def test_expired_original_deadline_and_existing_destination_never_write(
    original, tmp_path
):
    old, receipt = original
    target = tmp_path / "expired"
    with pytest.raises(TimeoutError):
        exact.copy_export(old, target, receipt, deadline=time.time() - 1)
    assert not target.exists()
    target.mkdir()
    (target / "preserved.txt").write_text("previous evidence")
    with pytest.raises(FileExistsError):
        exact.copy_export(old, target, receipt, deadline=time.time() + 60)
    assert (target / "preserved.txt").read_text() == "previous evidence"
    assert list(target.iterdir()) == [target / "preserved.txt"]


def test_wrong_receipt_or_modified_frozen_html_is_rejected(original, tmp_path):
    old, receipt = original
    with pytest.raises(ValueError, match="receipt identity"):
        exact.copy_export(
            old,
            tmp_path / "bad-receipt",
            dict(receipt, export_sha256="0" * 64),
            deadline=time.time() + 60,
        )
    page = old / "battle-001/index.html"
    page.write_text(page.read_text() + "<!-- unregistered change -->")
    (old / "checksums.sha256").unlink()
    viewer._seal(old)
    preserved = exact._inventory(old)
    with pytest.raises(ValueError, match="frozen viewer renderer"):
        exact.copy_export(
            old,
            tmp_path / "bad-html",
            dict(receipt, export_sha256=sha(old / "checksums.sha256")),
            deadline=time.time() + 60,
        )
    assert exact._inventory(old) == preserved
