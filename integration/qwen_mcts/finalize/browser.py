"""Offline moved-copy browser check of sampled viewer pages (runs in the separate playwright interpreter
/tmp/ep037/tools/bin/python; adapted from fixed_matchup/browser_check.py)."""
import json
from pathlib import Path
import shutil
import sys
import tempfile


def check(task):
    from playwright.sync_api import sync_playwright
    rows = []
    with tempfile.TemporaryDirectory(prefix="ex080-view-") as temporary:
        moved = Path(temporary) / "moved"
        moved.mkdir()
        shutil.copy2(Path(task["export"]) / "index.html", moved / "index.html")
        if (Path(task["export"]) / "provenance.json").exists():
            shutil.copy2(Path(task["export"]) / "provenance.json", moved / "provenance.json")
        for slot in task["sample"]:
            shutil.copytree(Path(task["export"]) / slot, moved / slot)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(offline=True)
            context.route("http://**/*", lambda route: route.abort())
            context.route("https://**/*", lambda route: route.abort())
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto((moved / "index.html").as_uri(), wait_until="domcontentloaded", timeout=20000)
            listed = page.locator("tbody tr").count()
            provenance_linked = bool(page.locator('a[href="provenance.json"]').count()) and (moved / "provenance.json").exists()
            for slot in task["sample"]:
                page.goto((moved / slot / "index.html").as_uri(), wait_until="domcontentloaded", timeout=20000)
                records = json.loads(page.locator("#data").text_content())["records"]
                if records:
                    if records[0]["dynamic"] not in page.locator("#input").text_content():
                        raise ValueError(f"{slot}: offline model input mismatch")
                    if not page.locator("#response span.k").count():
                        raise ValueError(f"{slot}: response JSON is not highlighted")
                    for button in ("copy-input", "save-input", "copy-response", "save-response"):
                        if not page.locator(f"#{button}").count():
                            raise ValueError(f"{slot}: missing {button} control")
                    single = [s for s in ("p1", "p2") if len(records[0]["candidates"][s]) == 1]
                    if single and "모델 미호출" not in page.locator("#response").text_content():
                        raise ValueError(f"{slot}: automatic single-candidate choice is not marked")
                    if len(records) > 1:
                        page.locator("#next").click()
                        if f"2/{len(records)}" not in page.locator("#position").text_content():
                            raise ValueError(f"{slot}: offline decision navigation mismatch")
                        page.locator("body").press("ArrowLeft")
                        if f"1/{len(records)}" not in page.locator("#position").text_content():
                            raise ValueError(f"{slot}: arrow-key navigation mismatch")
                if not page.locator("#protocol").text_content() or errors:
                    raise ValueError(f"{slot}: offline protocol/javascript failure: {errors}")
                rows.append(dict(slot=slot, decisions=len(records), passed=True))
            browser.close()
    return dict(passed=True, moved=True, offline=True, listed=listed, provenance_linked=provenance_linked, sampled=rows,
                exhaustive=False)


if __name__ == "__main__":
    print(json.dumps(check(json.loads(Path(sys.argv[1]).read_text()))))
