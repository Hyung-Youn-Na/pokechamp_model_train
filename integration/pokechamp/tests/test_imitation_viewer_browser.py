"""합성 EX-071 export의 이동 후 오프라인 열람; 실제 배틀 evidence가 아니다."""

from __future__ import annotations

import json
import shutil

import pytest

from integration.pokechamp.imitation import viewer
from integration.pokechamp.tests import test_imitation_battle as fixtures

snapshot = fixtures.snapshot
choice = fixtures.choice
schedule = fixtures.schedule
viewer_source = fixtures.viewer_source


def test_moved_viewer_offline_navigation_and_actual_payloads(viewer_source, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    original = tmp_path / "export"
    viewer.export(viewer_source, original)
    moved = tmp_path / "independent-location" / "ex071"
    shutil.copytree(original, moved)
    expected = json.loads((moved / "battle-01/decisions.json").read_text())
    with playwright.sync_playwright() as work:
        browser = work.chromium.launch(headless=True)
        try:
            context = browser.new_context(offline=True)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto((moved / "index.html").as_uri(), wait_until="domcontentloaded")
            assert page.locator("tbody tr").count() == 40
            page.goto((moved / "battle-01/index.html").as_uri(), wait_until="domcontentloaded")
            page.wait_for_function("document.getElementById('decision').options.length === 3")
            assert "정상 응답 미수신" in page.locator("#mode").inner_text()
            assert page.locator("#response").inner_text() == '{"error":"</script>"}'
            assert (
                json.loads(page.locator("#input").inner_text()) == expected["decisions"][0]["input"]
            )
            page.locator("#next").click()
            assert "모델 미호출" in page.locator("#mode").inner_text()
            assert page.locator("#candidates tr").count() == 1
            assert "미호출/미수신" in page.locator("#candidates").inner_text()
            page.locator("body").click(position={"x": 2, "y": 2})
            page.keyboard.press("ArrowRight")
            assert page.locator("#decision").input_value() == "2"
            assert page.locator("#candidates tr").count() == 3
            assert page.locator("#candidates tr.selected").count() == 1
            assert "33.333%" in page.locator("#candidates").inner_text()
            assert (
                json.loads(page.locator("#response").inner_text())
                == expected["decisions"][2]["response"]
            )
            with page.expect_download() as download:
                page.locator("#download").click()
            assert download.value.suggested_filename == "decision-3.json"
            assert not errors
            context.close()
        finally:
            browser.close()
