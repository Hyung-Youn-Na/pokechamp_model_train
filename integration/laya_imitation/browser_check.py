"""Relocated, offline check of an EX-119 viewer export (UI v1 basics), with a screenshot.

Run with a Playwright interpreter: `python -m integration.laya_imitation.browser_check <viewer> <receipt.json> [h2h]`.
`h2h` (EX-134): two pages per game (`battle-NNN` and the other model's `battle-NNNb`); both are opened.
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile

from playwright.sync_api import sync_playwright

TABS = ['요청 JSON', '응답 원문', '상태·후보 요약', '턴 로그', '기술 기록', '압축 입력', '선택지 확률', '선택·전송']


def _game_page(page, selector, errors):
    page.locator(selector).first.click()
    page.wait_for_selector('[role=tab]')
    assert [t.inner_text() for t in page.locator('[role=tab]').all()] == TABS
    assert page.locator('#request-tab').get_attribute('aria-selected') == 'true'
    data = json.loads(page.locator('#viewer-data').text_content())
    first = page.locator('#position').inner_text()
    page.locator('body').click(position=dict(x=5, y=5))
    page.keyboard.press('ArrowRight')
    assert page.locator('#position').inner_text() != first
    for name in TABS:
        page.locator('[role=tab]', has_text=name).click()
        assert page.locator('#raw').text_content() is not None
    page.locator('[role=tab]', has_text='압축 입력').click()
    assert 'turn ' in page.locator('#raw').text_content()
    turns = page.locator('#turn option').count()
    page.locator('#next-turn').click()
    assert not errors, errors
    return len(data['decisions']), turns


def inspect_h2h(source, receipt):
    checks = {}
    with tempfile.TemporaryDirectory(prefix='ex134-relocated-') as tmp:
        target = Path(tmp) / 'viewer'
        shutil.copytree(source, target)
        games = sorted(p for p in target.glob('battle-*/index.html') if not p.parent.name.endswith('b'))
        others = sorted(target.glob('battle-*b/index.html'))
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
            for width in (1440, 390):
                context = browser.new_context(viewport=dict(width=width, height=1000))
                context.set_offline(True)
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto((target / 'index.html').as_uri())
                assert page.locator('tr').count() == len(games) + 1
                base = _game_page(page, 'a[href^="battle-"]:not([href$="b/index.html"])', errors)
                if width == 1440:
                    page.screenshot(path=str(Path(receipt).with_suffix('.png')), full_page=False)
                page.goto((target / 'index.html').as_uri())
                other = _game_page(page, 'a[href$="b/index.html"]', errors) if others else None
                checks[str(width)] = dict(games=len(games), other_side_pages=len(others), base_decisions=base[0],
                                          base_turns=base[1], other_decisions=other and other[0], tabs=TABS,
                                          page_errors=errors)
                context.close()
            browser.close()
    Path(receipt).write_text(json.dumps(dict(passed=True, offline=True, relocated=True, checks=checks),
                                        ensure_ascii=False, indent=1))
    return checks


def inspect(source, receipt):
    checks = {}
    with tempfile.TemporaryDirectory(prefix='ex119-relocated-') as tmp:
        target = Path(tmp) / 'viewer'
        shutil.copytree(source, target)
        games = sorted(target.glob('battle-*/index.html'))
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
            for width in (1440, 390):
                context = browser.new_context(viewport=dict(width=width, height=1000))
                context.set_offline(True)
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto((target / 'index.html').as_uri())
                assert page.locator('tr').count() == len(games) + 1
                page.locator('a', has_text='입력·응답·리플레이').first.click()
                page.wait_for_selector('[role=tab]')
                assert [t.inner_text() for t in page.locator('[role=tab]').all()] == TABS
                assert page.locator('#request-tab').get_attribute('aria-selected') == 'true'
                data = json.loads(page.locator('#viewer-data').text_content())
                first = page.locator('#position').inner_text()
                page.locator('body').click(position=dict(x=5, y=5))
                page.keyboard.press('ArrowRight')
                assert page.locator('#position').inner_text() != first
                for name in TABS:
                    page.locator('[role=tab]', has_text=name).click()
                    assert page.locator('#raw').text_content() is not None
                page.locator('[role=tab]', has_text='압축 입력').click()
                assert 'turn ' in page.locator('#raw').text_content()
                turns = page.locator('#turn option').count()
                page.locator('#next-turn').click()
                assert not errors, errors
                if width == 1440:
                    page.screenshot(path=str(Path(receipt).with_suffix('.png')), full_page=False)
                checks[str(width)] = dict(games=len(games), decisions=len(data['decisions']), turns=turns,
                                          tabs=TABS, page_errors=errors)
                context.close()
            browser.close()
    Path(receipt).write_text(json.dumps(dict(passed=True, offline=True, relocated=True, checks=checks),
                                        ensure_ascii=False, indent=1))
    return checks


if __name__ == '__main__':
    check = inspect_h2h if sys.argv[3:] == ['h2h'] else inspect
    print(json.dumps(check(sys.argv[1], sys.argv[2]), ensure_ascii=False))
