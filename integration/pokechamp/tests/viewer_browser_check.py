"""Run explicitly with Playwright installed; creates only temporary viewer fixtures.

PYTHONPATH=. python integration/pokechamp/tests/viewer_browser_check.py --output /tmp/viewer-check
Use --chromium to select an already installed Chromium executable.
"""

import argparse
import json
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from integration.pokechamp.observability.render import _report_html
from integration.pokechamp.tests.test_viewer_navigation import make_turn_fixture


def check_viewer(output, chromium=None):
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix="viewer-fixture-") as temporary:
        bundle = make_turn_fixture(Path(temporary), turns=150)
        uri = (bundle / "report.html").as_uri()
        protocol_only = Path(temporary) / "protocol-only.html"
        protocol_only.write_text(
            _report_html(
                {},
                [
                    dict(
                        event_type="protocol_in",
                        event_seq=1,
                        protocol="|turn|999\n|message|protocol only",
                    )
                ],
                ["fixture partial"],
                {"valid": False},
            )
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chromium)
            context = browser.new_context(viewport={"width": 1600, "height": 1000})
            # The viewer itself and its iframe remain local; all external requests fail.
            context.route("https://**/*", lambda route: route.abort())
            context.route("http://**/*", lambda route: route.abort())
            context.set_offline(True)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""window.cspViolations = [];
              document.addEventListener('securitypolicyviolation', e => {
                window.cspViolations.push(e.effectiveDirective);
              });""")

            def selected(number):
                expect(page.locator(".turn-panel:visible")).to_have_count(1)
                expect(page.locator(f"#viewer-turn-{number}")).to_be_visible()
                expect(page.locator(f"#viewer-tab-{number}")).to_have_attribute(
                    "aria-selected", "true"
                )
                expect(page.locator(f"#viewer-tab-{number}")).to_have_attribute(
                    "tabindex", "0"
                )
                expect(page.locator("#turn-select")).to_have_value(str(number - 1))

            page.goto(uri)
            selected(1)
            expect(page.locator("#turn-previous")).to_be_disabled()
            expect(page.locator("#turn-select option")).to_have_count(152)
            page.locator("#viewer-tab-2").click()
            selected(2)
            expect(page.locator(".turn-panel:visible .decision")).to_have_count(2)
            expect(page.locator(".turn-panel:visible .llm-call")).to_have_count(3)
            expect(page.locator(".turn-panel:visible .llm-response")).to_have_count(6)
            assert page.locator(".llm-response").evaluate_all("""nodes => nodes.every(n =>
              !n.closest('details') && getComputedStyle(n).maxHeight === 'none')""")
            assert (
                page.locator("#decision-2 .llm-response")
                .first.text_content()
                .endswith("\nline" * 300)
            )
            assert (
                page.locator("#decision-2 .llm-response").nth(3).text_content()
                == "기록된 응답 없음"
            )
            assert page.locator("#decision-2 .llm-call details").evaluate_all(
                "nodes => nodes.every(n => !n.open)"
            )
            page.locator("#decision-2 .llm-call details summary").first.click()
            expect(
                page.locator("#decision-2 .llm-call details").first.locator("pre").first
            ).to_be_visible()
            original = page.locator("#decision-2 > details").filter(
                has_text="검증용 원본 입력"
            )
            original.locator("summary").click()
            expect(original.locator("pre")).to_contain_text("B2-original")
            metadata = (
                page.locator("#decision-2 .llm-call details")
                .filter(has_text="Request / response metadata")
                .first
            )
            metadata.locator("summary").click()
            expect(metadata).to_contain_text("request-value")
            checks.append("all calls/reasoning/raw/input/B2 original/metadata readable")

            page.locator("#turn-select").select_option("150")
            selected(151)
            page.locator("#turn-next").click()
            selected(152)
            expect(page.locator("#turn-next")).to_be_disabled()
            page.locator("#turn-previous").click()
            selected(151)
            page.reload()
            selected(151)
            page.go_back()
            selected(152)
            page.go_forward()
            selected(151)
            checks.append("150-turn dropdown/previous/next/reload/history")

            page.goto(uri + "#decision-3")
            selected(2)
            expect(page.locator("#decision-3")).to_be_in_viewport()
            page.reload()
            selected(2)
            page.goto(uri)
            problem = page.locator('a[href="#battle-turn-battle-actor-p1-decision-2"]')
            problem.click()
            selected(2)
            expect(page.locator("#decision-2")).to_be_in_viewport()
            page.goto(uri + "#battle-turn-battle-actor-p1-decision-2")
            selected(2)
            # A real native decision link exercises same-document hidden-target navigation.
            page.evaluate("""() => {
                const a = document.createElement('a');
                a.href = '#decision-5'; a.id = 'fixture-decision-link'; a.textContent = 'Decision 5';
                document.querySelector('nav').append(a);
            }""")
            page.locator("#fixture-decision-link").click()
            selected(4)
            page.go_back()
            selected(2)
            page.go_forward()
            selected(4)
            page.goto(uri + "#%E0%A4%A")
            selected(1)
            checks.append(
                "issue/native decision links/direct URL/encoded invalid hash/history"
            )

            tab = page.locator("#viewer-tab-1")
            tab.focus()
            page.keyboard.press("ArrowRight")
            selected(2)
            expect(page.locator("#viewer-tab-2")).to_be_focused()
            page.keyboard.press("End")
            selected(152)
            page.keyboard.press("ArrowRight")
            selected(1)
            page.keyboard.press("ArrowLeft")
            selected(152)
            page.keyboard.press("Home")
            selected(1)
            page.keyboard.press("Tab")
            expect(page.locator("#turn-select")).to_be_focused()
            checks.append("ARIA tab/tabpanel relationships and roving keyboard focus")

            timeline_id = page.locator("#complete-timeline .protocol").first.get_attribute("id")
            page.goto(uri + "#" + timeline_id)
            expect(page.locator("#complete-timeline")).to_have_attribute("open", "")
            expect(page.locator("#" + timeline_id)).to_be_in_viewport()
            assert page.locator("[id]").evaluate_all(
                "ns => new Set(ns.map(n=>n.id)).size === ns.length"
            )
            assert (
                page.locator("#owned").count() == 0
                and page.evaluate("window.owned") is None
            )
            assert not page.evaluate(
                "window.cspViolations.filter(v => v === 'script-src-elem')"
            )
            # Prove the hash policy rejects an unapproved inline script in the same document.
            page.evaluate("""() => {const s = document.createElement('script');
              s.textContent = 'window.injected = true'; document.body.append(s);} """)
            assert page.evaluate("window.injected") is None
            page.wait_for_function("window.cspViolations.includes('script-src-elem')")
            checks.append(
                "full protocol anchors/unique IDs/HTML escaping/CSP allows viewer and blocks injection/offline"
            )

            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(uri + "#decision-3")
            selected(2)
            page.wait_for_timeout(100)
            rect = page.locator("#decision-3").bounding_box()
            replay = page.locator(".replay-panel").bounding_box()
            assert rect["y"] >= replay["y"] + replay["height"] - 1
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#turn-select").select_option("149")
            selected(150)
            page.screenshot(path=str(output / "narrow.png"))
            page.locator("#turn-select").select_option("1")
            page.set_viewport_size({"width": 1600, "height": 1000})
            page.locator("#turn-next").click()
            page.locator("#turn-previous").click()
            page.screenshot(path=str(output / "desktop.png"))
            checks.append(
                "390px viewport dropdown/tabs/no horizontal overflow/anchor clears sticky replay"
            )

            page.goto(protocol_only.as_uri())
            expect(page.locator("#turn-navigation")).to_be_hidden()
            page.locator("#complete-timeline summary").click()
            expect(page.locator("#timeline-event-1")).to_contain_text("protocol only")
            checks.append("decision-free partial protocol record")
            assert errors == [], errors

            static = browser.new_context(
                java_script_enabled=False, viewport={"width": 390, "height": 844}
            )
            static.set_offline(True)
            static.route("https://**/*", lambda route: route.abort())
            nojs = static.new_page()
            nojs.goto(uri)
            expect(nojs.locator("#turn-navigation")).to_be_hidden()
            expect(nojs.locator(".turn-panel:visible")).to_have_count(152)
            expect(nojs.locator(".llm-response:visible")).to_have_count(6)
            nojs.locator("#complete-timeline summary").click()
            expect(nojs.locator("#complete-timeline .protocol:visible")).to_have_count(
                154
            )
            checks.append(
                "JavaScript disabled: every turn/response/full protocol readable offline"
            )
            version = browser.version
            browser.close()
    result = {
        "browser": "Chromium " + version,
        "checks": checks,
        "passed": len(checks),
        "page_errors": errors,
    }
    (output / "browser-results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chromium")
    args = parser.parse_args()
    check_viewer(args.output, args.chromium)
