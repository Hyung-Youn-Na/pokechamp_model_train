"""C-047 실제 export를 새 위치에서 Chromium 오프라인으로 검증한다."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import platform
import re
import shutil
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

from .storage import atomic, read, sha

LABELS = dict(
    completed="정상 종료", failed="실패", incomplete="미완료", unattempted="미실행", invalid="무효"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sealed_files(directory):
    """봉인의 모든 항목과 실제 파일 집합을 함께 대조한다."""
    directory = Path(directory).resolve()
    recorded = {}
    for line in (directory / "checksums.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = (directory / name).resolve()
        require(
            re.fullmatch(r"[0-9a-f]{64}", digest)
            and name not in recorded
            and path.is_relative_to(directory)
            and sha(path) == digest,
            "invalid sealed entry: " + name,
        )
        recorded[name] = digest
    actual = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file() and path != directory / "checksums.sha256"
    }
    require(actual == set(recorded), "seal does not cover the complete bundle")
    return recorded


def source_decisions(source, data):
    """표시용 JSON을 독립 원 이벤트의 입력·응답·전송과 전수 대조한다."""
    slot = data["outcome"]["slot_id"]
    path = source / "games" / slot / "events.jsonl"
    grouped = defaultdict(dict)
    for line in path.read_text().splitlines() if path.exists() else []:
        event = json.loads(line)
        if event.get("decision"):
            grouped[event["decision"]][event["type"]] = event
    original = [(key, rows) for key, rows in grouped.items() if "input" in rows]
    require(
        [d["id"] for d in data["decisions"]] == [key for key, _ in original],
        "viewer decision denominator/order differs from original events",
    )
    for item, (_, rows) in zip(data["decisions"], original, strict=True):
        entry = rows["input"]
        expected = dict(
            input=entry["body"],
            input_body_json=entry["body_json"],
            input_sha256=entry["input_sha256"],
            request=rows.get("http_request", {}).get("body"),
            response=rows.get("response", {}).get("body"),
            raw_response=rows.get("http_response", {}).get("raw_body"),
            selection=rows.get("selection"),
            wire=rows.get("wire"),
            revalidation=rows.get("revalidation"),
        )
        require(
            all(item[key] == value for key, value in expected.items()),
            "viewer decision differs from original input/response/wire",
        )
        require(
            list(item["criteria"].items())
            == list(entry["body"]["questions"]["action"]["criteria"].items()),
            "viewer candidate order differs from original input",
        )
        state = json.loads(entry["body"]["state"])["snapshot"]
        require(
            (item["turn"], item["kind"]) == (state["turn"], state["decision_kind"]),
            "viewer turn/kind differs from original input",
        )


def indices(items):
    if not items:
        return []
    selected, seen = {0, len(items) - 1}, set()
    for index, item in enumerate(items):
        choice = item.get("selection") or {}
        key = (
            item["kind"],
            choice.get("automatic"),
            item["request"] is not None,
            item["response"] is not None,
            item["wire"] is not None,
            str(choice.get("choice", "")).endswith(":tera"),
        )
        if key not in seen:
            selected.add(index)
            seen.add(key)
    return sorted(selected)


def inspect_decision(page, item, index, total):
    require(page.locator("#decision").input_value() == str(index), "wrong selected decision")
    require(
        page.locator("#status").inner_text()
        == f"턴 {item['turn']} · {item['kind']} · {index + 1}/{total}",
        "wrong decision heading",
    )
    require(
        json.loads(page.locator("#input").inner_text()) == item["input"],
        "displayed model input differs from saved JSON",
    )
    request = page.locator("#request").text_content()
    require(
        (json.loads(request) if item["request"] is not None else request)
        == (item["request"] if item["request"] is not None else "없음"),
        "displayed HTTP request differs from saved JSON",
    )
    response = page.locator("#response").inner_text()
    require(
        (json.loads(response) if item["response"] is not None else response)
        == (
            item["response"]
            if item["response"] is not None
            else item["raw_response"] or "응답 기록 없음"
        ),
        "displayed response differs from saved JSON",
    )
    selection = item["selection"] or {}
    mode = (
        "모델 미호출 · 유일한 합법 행동"
        if selection.get("automatic")
        else "모델 응답 수신"
        if item["response"] is not None
        else "요청 전송 · 정상 응답 미수신"
        if item["request"] is not None
        else "모델 호출 전 종료"
    )
    require(page.locator("#mode").inner_text() == mode, "wrong inference/automatic status")
    sent = "실제 전송: " + item["wire"]["command"] if item["wire"] else "실제 전송 기록 없음"
    require(page.locator("#sent").inner_text() == sent, "wrong actual wire display")
    rows = page.locator("#candidates tr").evaluate_all(
        "rows => rows.map(r => ({cells:[...r.cells].map(c=>c.textContent),"
        "selected:r.classList.contains('selected')}))"
    )
    require(len(rows) == len(item["criteria"]), "wrong candidate denominator")
    probabilities = (item["response"] or {}).get("probabilities", {})
    for row, (aid, description) in zip(rows, item["criteria"].items(), strict=True):
        chosen = selection.get("choice") == aid
        require(
            row["cells"][:2] == [aid, description]
            and row["selected"] == chosen
            and row["cells"][3] == ("선택" if chosen else ""),
            "wrong candidate/selected row",
        )
        shown, expected = row["cells"][2], probabilities.get(aid)
        if expected is None:
            require(shown == "미호출/미수신", "missing inference was shown as a probability")
        else:
            require(
                math.isfinite(expected)
                and shown.endswith("%")
                and abs(float(shown[:-1]) / 100 - expected) <= 0.000005000001,
                "displayed probability differs from saved response",
            )
    technical = json.loads(page.locator("#technical").text_content())
    require(
        technical["selection"] == item["selection"]
        and technical["wire"] == item["wire"]
        and technical["revalidation"] == item["revalidation"],
        "wrong transmission details",
    )
    require(
        page.locator("#previous").is_disabled() == (index == 0)
        and page.locator("#next").is_disabled() == (index == total - 1),
        "wrong decision navigation boundary",
    )


def inspect_page(page, path, data):
    page.goto(path.as_uri(), wait_until="domcontentloaded")
    items, outcome = data["decisions"], data["outcome"]
    require(page.locator("#decision option").count() == len(items), "wrong decision menu")
    heading = page.locator("main > p").first.inner_text()
    require(
        LABELS[outcome["status"]] in heading and (outcome.get("result") or "점수 없음") in heading,
        "wrong battle status/score",
    )
    selected = set(indices(items))
    for index in sorted(selected):
        page.locator("#decision").select_option(str(index))
        inspect_decision(page, items[index], index, len(items))
    if not items:
        require(
            page.locator("#status").inner_text() == "저장된 모델 결정이 없습니다."
            and page.locator("#candidates tr").count() == 0
            and page.locator("#previous").is_disabled()
            and page.locator("#next").is_disabled(),
            "empty decision page invents a decision",
        )
        return dict(
            slot_id=outcome["slot_id"],
            status=outcome["status"],
            decision_count=0,
            checked_indices=[],
            navigation=False,
            keyboard=False,
            downloads=0,
        )
    if len(items) > 1:
        page.locator("#decision").select_option("0")
        page.locator("#next").click()
        inspect_decision(page, items[1], 1, len(items))
        page.locator("#previous").click()
        require(page.locator("#decision").input_value() == "0", "previous button failed")
        page.locator("body").click(position={"x": 2, "y": 2})
        page.keyboard.press("ArrowRight")
        inspect_decision(page, items[1], 1, len(items))
        page.keyboard.press("ArrowLeft")
        require(page.locator("#decision").input_value() == "0", "keyboard previous failed")
        page.locator("#download").focus()
        page.keyboard.press("ArrowRight")
        require(page.locator("#decision").input_value() == "0", "keyboard captured button input")
        selected.add(1)
    last = len(items) - 1
    page.locator("#decision").select_option(str(last))
    with page.expect_download() as event:
        page.locator("#download").click()
    download = event.value
    require(
        download.suggested_filename == f"decision-{last + 1}.json"
        and download.failure() is None
        and read(download.path()) == items[last],
        "download differs from saved decision JSON",
    )
    return dict(
        slot_id=outcome["slot_id"],
        status=outcome["status"],
        decision_count=len(items),
        checked_indices=sorted(selected),
        navigation=len(items) > 1,
        keyboard=len(items) > 1,
        downloads=1,
    )


def check(viewer, receipt):
    viewer, receipt = Path(viewer).resolve(), Path(receipt).resolve()
    if receipt.exists():
        raise FileExistsError("browser receipt already exists; preserve earlier evidence")
    require(not receipt.is_relative_to(viewer), "receipt must be outside the sealed viewer")
    provenance = read(viewer / "provenance.json")
    source = Path(provenance["source"]).resolve()
    require(not receipt.is_relative_to(source), "receipt must be outside the sealed source")
    result = dict(
        passed=False,
        viewer=str(viewer),
        at=time.time(),
        helper_sha256=sha(Path(__file__)),
        python=platform.python_version(),
        offline=True,
        temporary_copy=True,
        model_calls=0,
        battle_calls=0,
        checked_pages=0,
        checked_decisions=0,
        page_errors=[],
        pages=[],
        errors=[],
    )
    original = {}
    try:
        original[viewer] = (sha(viewer / "checksums.sha256"), sealed_files(viewer))
        result["viewer_checksums_sha256"] = original[viewer][0]
        summary = read(viewer / "result.json")
        original[source] = (sha(source / "checksums.sha256"), sealed_files(source))
        require(
            original[source][0] == provenance["source_seal_sha256"]
            and original[source][1] == provenance["source_files"],
            "source provenance mismatch",
        )
        result["source_checksums_sha256"] = original[source][0]
        result["source"] = str(source)
        outcomes = summary["outcomes"]
        require(
            summary["planned"] == len(outcomes) == 40
            and outcomes == read(source / "result.json")["outcomes"],
            "wrong forty-slot results",
        )
        counts = Counter(row["status"] for row in outcomes)
        require(all(summary[key] == counts[key] for key in LABELS), "wrong status denominator")
        for name, expected in provenance["copied_files"].items():
            require(
                sha(viewer / name) == expected == original[source][1][name],
                "copied source file mismatch: " + name,
            )
        from playwright.sync_api import sync_playwright

        result["playwright_version"] = importlib.metadata.version("playwright")
        with tempfile.TemporaryDirectory(prefix="ex071-viewer-check-") as temporary:
            moved = Path(temporary) / "moved" / "ex071"
            shutil.copytree(viewer, moved)
            require(sealed_files(moved) == original[viewer][1], "moved viewer copy differs")
            with sync_playwright() as work:
                browser = work.chromium.launch(headless=True)
                try:
                    result["chromium_version"] = browser.version
                    context = browser.new_context(offline=True, accept_downloads=True)
                    page = context.new_page()
                    page.set_default_timeout(15000)
                    page.on("pageerror", lambda error: result["page_errors"].append(str(error)))
                    page.goto((moved / "index.html").as_uri(), wait_until="domcontentloaded")
                    require(
                        page.locator("tbody tr").count() == 40, "index does not show forty slots"
                    )
                    shown = page.locator("tbody tr").evaluate_all(
                        "rows => rows.map(r => [...r.cells].map(c => c.textContent))"
                    )
                    expected = [
                        [row["slot_id"]]
                        + [
                            str(row.get(key) or "—")
                            for key in (
                                "model",
                                "model_side",
                                "opponent",
                                "status",
                                "result",
                                "turns",
                            )
                        ]
                        for row in outcomes
                    ]
                    require(shown == expected, "index rows differ from saved outcomes")
                    heading = (
                        f"예정40 · 시도{summary['attempted']} · 정상{summary['completed']} · "
                        f"실패{summary['failed']} · 미완료{summary['incomplete']} · "
                        f"무효{summary['invalid']} · 미실행{summary['unattempted']}"
                    )
                    require(
                        page.locator("main > p").first.inner_text() == heading,
                        "index status denominators differ from saved results",
                    )
                    for index, outcome in enumerate(outcomes, 1):
                        href = f"battle-{index:02d}/index.html"
                        require(
                            page.locator(f'a[href="{href}"]').count() == 1,
                            "index omits a battle link",
                        )
                    result["index_rows"] = 40
                    for index, outcome in enumerate(outcomes, 1):
                        folder = moved / f"battle-{index:02d}"
                        data = read(folder / "decisions.json")
                        require(data["outcome"] == outcome, "page outcome differs from original")
                        source_decisions(source, data)
                        checked = inspect_page(page, folder / "index.html", data)
                        result["pages"].append(checked)
                        result["checked_pages"] += 1
                        result["checked_decisions"] += len(checked["checked_indices"])
                    context.close()
                finally:
                    browser.close()
            require(sealed_files(moved) == original[viewer][1], "browser changed the moved copy")
        require(not result["page_errors"], "offline browser raised page errors")
        result["passed"] = result["checked_pages"] == 40
    except Exception as error:
        result["errors"].append(dict(type=type(error).__name__, detail=str(error)))
    finally:
        unchanged = bool(original)
        for path, (digest, files) in original.items():
            try:
                require(
                    sha(path / "checksums.sha256") == digest and sealed_files(path) == files,
                    "original seal changed during browser verification: " + str(path),
                )
            except Exception as error:
                result["errors"].append(dict(type=type(error).__name__, detail=str(error)))
                result["passed"] = False
                unchanged = False
        result["originals_unchanged"] = unchanged
    result["finished_at"] = time.time()
    atomic(receipt, result, immutable=True)
    return result


def absolute_path(value):
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("an absolute path is required")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer", required=True, type=absolute_path)
    parser.add_argument("--receipt", required=True, type=absolute_path)
    args = parser.parse_args(argv)
    result = check(args.viewer, args.receipt)
    print(
        json.dumps(
            {
                key: result.get(key)
                for key in ("passed", "checked_pages", "checked_decisions", "page_errors", "errors")
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
