"""Separate browser environment; copied exports are tested with network disabled."""
import json
from pathlib import Path
import shutil
import sys
import tempfile


def check(task):
    from playwright.sync_api import sync_playwright

    rows = []
    with tempfile.TemporaryDirectory(prefix="fixed-matchup-view-") as temporary:
        moved = Path(temporary) / "moved"
        moved.mkdir()
        shutil.copy2(Path(task["export"]) / "index.html", moved / "index.html")
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
            for slot in task["sample"]:
                page.goto((moved / slot / "index.html").as_uri(), wait_until="domcontentloaded", timeout=20000)
                data = page.locator("#data").text_content()
                records = json.loads(data)["records"]
                if records:
                    observed = json.loads(page.locator("#input").text_content())
                    if observed != records[0]["observation"]:
                        raise ValueError("offline input mismatch")
                    if len(records) > 1:
                        page.locator("#next").click()
                        if records[1]["choice"] not in page.locator("#position").text_content():
                            raise ValueError("offline decision navigation mismatch")
                if not page.locator("#protocol").text_content() or errors:
                    raise ValueError("offline protocol/javascript failure: " + str(errors))
                rows.append(dict(slot=slot, decisions=len(records), passed=True))
            browser.close()
    return dict(passed=True, moved=True, offline=True, sampled=rows, exhaustive=False)


if __name__ == "__main__":
    print(json.dumps(check(json.loads(Path(sys.argv[1]).read_text()))))
