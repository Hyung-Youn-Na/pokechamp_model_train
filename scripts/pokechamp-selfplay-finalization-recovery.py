#!/usr/bin/env python3
"""EX-072의 원 봉인을 보존하는 EP-117 CPU 최종화 정정 경로."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.pokechamp.selfplay import execution, reporting, viewer
from integration.pokechamp.selfplay.finalize import (
    required_artifacts,
    seal,
)
from integration.pokechamp.selfplay.runner import decisions_for
from integration.pokechamp.selfplay.storage import (
    Clock,
    atomic,
    read,
    sha,
)

BROWSER_PYTHON = Path("/tmp/ep037/tools/bin/python")
DEPENDENCIES = Path("/ref/kev/.venv/lib/python3.13/site-packages")
IDENTITY = "finalization-v2"
BROWSER_BOOTSTRAP = """import sys
sys.path.append(sys.argv[1])
from integration.pokechamp.selfplay.viewer import verify_browser
from integration.pokechamp.selfplay.storage import atomic
result = verify_browser(sys.argv[2], sys.argv[3], sys.argv[4])
atomic(sys.argv[5], result, immutable=True)
"""


def require_time(clock):
    if clock.remaining() <= 15:
        raise TimeoutError("original EX-072 budget exhausted; no new clock permitted")


def verify_pins(pins):
    for name, digest in pins.items():
        if sha(Path(name)) != digest:
            raise ValueError("preserved artifact changed: " + name)


def raw_inventory(directory):
    return {
        str(p.relative_to(directory)): sha(p)
        for p in (directory / "games").rglob("*")
        if p.is_file()
    }


def commit_staged(output, exported, destination, export_destination, clock):
    """Complete receipts remain in staging until both seals have passed."""
    if destination.exists() or export_destination.exists():
        raise FileExistsError("final correction destination already exists")
    seal(exported)
    viewer.verify_source(exported)
    seal(output)
    viewer.verify_source(output)
    require_time(clock)
    exported.rename(export_destination)
    try:
        output.rename(destination)
    except Exception:
        export_destination.rename(exported)
        raise


def compare_statistics(original, recomputed):
    """Allow only completion bookkeeping to differ; all scientific output is fixed."""
    for key, value in recomputed.items():
        if key in ("stage_status", "incomplete_requirements", "experiment_complete"):
            continue
        if original.get(key) != value:
            raise ValueError("original statistical output differs: " + key)


def verify_browser_receipt(receipt, export_receipt, source, count):
    for key in (
        "passed",
        "source_unchanged",
        "export_unchanged",
        "moved_copy_verified",
        "offline",
    ):
        if receipt.get(key) is not True:
            raise ValueError("required browser gate failed: " + key)
    if (
        receipt.get("checked_completed_pages") != count
        or receipt.get("completed") != count
        or len(receipt.get("pages", [])) != count
        or not all(p.get("passed") is True for p in receipt["pages"])
        or receipt.get("export_seal_sha256") != export_receipt["export_sha256"]
        or receipt.get("source_seal_sha256") != sha(source / "checksums.sha256")
        or receipt.get("verifier_sha256") != sha(Path(viewer.__file__))
        or receipt.get("javascript_errors") != []
        or receipt.get("external_requests") != []
    ):
        raise ValueError("browser coverage, identity, or offline result differs")


def preflight(directory, validation):
    directory = Path(directory).resolve()
    execution.assert_frozen(directory)
    manifest = read(directory / "manifest.json")
    if manifest.get("experiment_id") != "EX-072":
        raise ValueError("recovery is restricted to EX-072")
    clock = Clock(directory)
    require_time(clock)
    validation = Path(validation).resolve()
    tests = read(validation)
    if tests.get("passed") is not True or tests.get("recovery_source_sha256") != sha(
        Path(__file__)
    ):
        raise ValueError("this recovery source has no passing regression receipt")
    original = read(directory / "final/result.json")
    closure = read(directory / "completed.json")
    if (
        closure.get("closed") is not True
        or closure.get("experiment_complete") is not False
        or Path(closure["result_path"]).resolve() != directory / "final/result.json"
        or closure["result_sha256"] != sha(directory / "final/result.json")
        or set(closure["incomplete_requirements"])
        != {"finalization", "sealed", "viewer"}
        or set(original["incomplete_requirements"])
        != {"finalization", "sealed", "viewer"}
        or original["stage_status"].get("viewer") is not False
        or original["stage_status"].get("sealed") is not False
        or "ModuleNotFoundError: No module named 'httpx'"
        not in (directory / "final/viewer-check.log").read_text()
    ):
        raise ValueError(
            "original closure is not the registered browser-import failure"
        )
    bundle = directory / "final/battles"
    old_export = Path(closure["viewer_path"]).resolve().parent
    if old_export != ROOT / "exports/battle_viewers/ex072":
        raise ValueError("unexpected original export identity")
    source_files = viewer.verify_source(bundle)
    viewer.verify_source(old_export)
    export_files = viewer.verify_source(old_export / "viewer")
    if read(bundle / "manifest.json")["execution"] != manifest:
        raise ValueError("original bundle execution identity differs")
    raw_files = raw_inventory(directory)
    if raw_files != {
        name: digest
        for name, digest in source_files.items()
        if name.startswith("games/")
    }:
        raise ValueError("raw game files differ from the preserved source bundle")
    schedule = read(directory / "prepared/schedule.json")
    state = read(directory / "state.json")
    outcomes = [
        read(directory / "games" / slot["slot_id"] / "outcome.json")
        for slot in schedule
    ]
    decisions = decisions_for(directory, outcomes)
    artifacts = {
        str(p.relative_to(directory)): sha(p)
        for p in required_artifacts(directory, state, outcomes, decisions)
    }
    if artifacts != read(directory / "final/artifact-manifest.json"):
        raise ValueError("required artifacts differ from the original finalization")
    checks = dict(original["stage_status"])
    if not all(
        r.get("actors_cleaned") is True and r.get("server_cleaned") is True
        for r in outcomes
    ):
        raise ValueError("game resource cleanup evidence is incomplete")
    data = {
        "schedule": schedule,
        "outcomes": outcomes,
        "decisions": decisions,
        "train_outcomes": [r for r in outcomes if r["stage"] == "train"],
    }
    recomputed = reporting.summarize(**data, stage_status=checks)
    compare_statistics(original, recomputed)
    if recomputed["completed"] != 584 or recomputed["incomplete_requirements"] != [
        "viewer",
        "sealed",
    ]:
        raise ValueError("recovery may only complete the registered finalization gates")
    pins = {str(directory / name): digest for name, digest in artifacts.items()}
    pins.update(
        {
            str(directory / name): sha(directory / name)
            for name in (
                "completed.json",
                "final/result.json",
                "final/report.md",
                "final/failure.json",
                "final/viewer-check.log",
                "final/artifact-manifest.json",
                "final/viewer-export.json",
                "final/battles/checksums.sha256",
                "state.json",
                "selection.json",
                "calibration-decision.json",
            )
        }
    )
    pins.update(
        {
            str(old_export / "checksums.sha256"): sha(old_export / "checksums.sha256"),
            str(old_export / "viewer/checksums.sha256"): sha(
                old_export / "viewer/checksums.sha256"
            ),
            str(validation): sha(validation),
            str(Path(__file__)): sha(Path(__file__)),
        }
    )
    return {
        "directory": directory,
        "original": original,
        "clock": clock,
        "bundle": bundle,
        "old_export": old_export,
        "source_files": source_files,
        "export_files": export_files,
        "raw_files": raw_files,
        "pins": pins,
        "checks": checks,
        "data": data,
    }


def recover(directory, validation):
    context = preflight(directory, validation)
    directory, clock = context["directory"], context["clock"]
    destination = directory / "corrections" / IDENTITY
    export_destination = ROOT / "exports/battle_viewers/ex072-finalization-v2"
    output = destination.with_name("." + IDENTITY + "-staging")
    exported = export_destination.with_name("." + export_destination.name + "-staging")
    if any(
        path.exists() for path in (output, exported, destination, export_destination)
    ):
        raise FileExistsError(
            "preserve prior correction; this identity cannot overwrite it"
        )
    require_time(clock)
    output.mkdir(parents=True)
    started = time.time()
    correction = {
        "experiment_id": "EX-072",
        "identity": IDENTITY,
        "plan": "EP-117",
        "scope": "CPU browser-import/finalization correction; no new games, updates, or model calls",
        "original_clock": clock.record,
        "started_at": started,
        "original_failure": read(directory / "final/failure.json"),
        "original_completed": read(directory / "completed.json"),
        "original_pins": context["pins"],
        "source": str(Path(__file__).resolve()),
        "source_sha256": sha(Path(__file__)),
        "browser_python": str(BROWSER_PYTHON),
        "appended_dependency_path": str(DEPENDENCIES),
        "browser_verifier_sha256": sha(Path(viewer.__file__)),
        "original_statistics_unchanged": True,
    }
    atomic(output / "recovery.json", correction, immutable=True)
    try:
        require_time(clock)
        exported.mkdir(parents=True)
        shutil.copytree(context["old_export"] / "viewer", exported / "viewer")
        if viewer.verify_source(exported / "viewer") != context["export_files"]:
            raise ValueError(
                "corrected export is not byte-identical to the original viewer"
            )
        export_receipt = read(directory / "final/viewer-export.json")
        export_receipt["index"] = str(exported / "viewer/index.html")
        export_receipt["copied_from"] = str(context["old_export"] / "viewer")
        atomic(output / "browser-export.json", export_receipt, immutable=True)
        command = [
            str(BROWSER_PYTHON),
            "-c",
            BROWSER_BOOTSTRAP,
            str(DEPENDENCIES),
            str(context["bundle"]),
            str(exported / "viewer"),
            str(output / "browser-export.json"),
            str(output / "viewer-check.json"),
        ]
        atomic(output / "browser-command.json", command, immutable=True)
        require_time(clock)
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=clock.remaining() - 15,
        )
        atomic(
            output / "viewer-check.log",
            (completed.stdout + completed.stderr).encode(),
            immutable=True,
        )
        if completed.returncode:
            raise ValueError("corrected browser process failed; see viewer-check.log")
        browser = read(output / "viewer-check.json")
        verify_browser_receipt(browser, export_receipt, context["bundle"], 584)
        require_time(clock)
        verify_pins(context["pins"])
        execution.assert_frozen(directory)
        if viewer.verify_source(context["bundle"]) != context["source_files"]:
            raise ValueError("original source bundle changed during recovery")
        viewer.verify_source(context["old_export"])
        if viewer.verify_source(exported / "viewer") != context["export_files"]:
            raise ValueError("new export changed during verification")
        if raw_inventory(directory) != context["raw_files"]:
            raise ValueError("raw game files changed during browser verification")
        final_export_receipt = dict(
            export_receipt,
            index=str(export_destination / "viewer/index.html"),
            verified_staging_index=export_receipt["index"],
        )
        atomic(output / "viewer-export.json", final_export_receipt, immutable=True)
        checks = dict(context["checks"], viewer=True, sealed=True)
        recomputed = reporting.summarize(**context["data"], stage_status=checks)
        compare_statistics(context["original"], recomputed)
        if not recomputed["experiment_complete"]:
            raise ValueError("required completion gates remain incomplete")
        result = dict(context["original"])
        result.update(recomputed)
        result.pop("finalization_error", None)
        result["correction"] = correction
        result["original_finalization_error"] = correction["original_failure"]
        atomic(output / "result.json", result, immutable=True)
        notice = (
            "\n이 보고서는 EP-117의 finalization-v2 정정본입니다. 원 브라우저 환경의 httpx 누락으로 "
            "최초 최종화가 미완료됐으며, 원 실패 보고·봉인·시계를 보존한 채 동일 검증기로 "
            "전584경기를 이동 후 오프라인 검사했습니다. 학습·대국·가중치·통계·평가 기준 변경은 "
            "없습니다. [정정 출처와 원본 해시](recovery.json)를 함께 보존합니다.\n"
        )
        report = reporting.report_markdown(result) + notice
        atomic(output / "report.md", report.encode(), immutable=True)
        shutil.copyfile(directory / "manifest.json", output / "manifest.json")
        for name in (
            "result.json",
            "report.md",
            "manifest.json",
            "recovery.json",
            "viewer-check.json",
        ):
            shutil.copyfile(output / name, exported / name)
        listing = (
            (exported / "viewer/index.html")
            .read_text()
            .replace('href="battle-', 'href="viewer/battle-')
            .replace('href="provenance.json"', 'href="recovery.json"')
        )
        status = '<p>최종 실험 완료: 예 · finalization-v2 정정본 · <a href="report.md">최종 보고</a></p>'
        atomic(
            exported / "index.html",
            listing.replace("<main>", "<main>" + status).encode(),
            immutable=True,
        )
        require_time(clock)
        verify_pins(context["pins"])
        require_time(clock)
        closure = {
            "closed": True,
            "experiment_complete": True,
            "performance_improved": result["performance_improved"],
            "identity": IDENTITY,
            "completed_at": time.time(),
            "result_path": str(destination / "result.json"),
            "result_sha256": sha(output / "result.json"),
            "viewer_path": str(export_destination / "index.html"),
            "verified_viewer_seal_sha256": export_receipt["export_sha256"],
            "original_completed_sha256": sha(directory / "completed.json"),
            "clock_sha256": sha(directory / "clock.json"),
            "incomplete_requirements": [],
        }
        atomic(output / "completed.json", closure, immutable=True)
        commit_staged(output, exported, destination, export_destination, clock)
        atomic(
            directory / "corrections/latest.json",
            {
                "identity": IDENTITY,
                "completed_path": str(destination / "completed.json"),
                "completed_sha256": sha(destination / "completed.json"),
                "original_completed_sha256": sha(directory / "completed.json"),
            },
            immutable=True,
        )
        index = export_destination.parent / "index.html"
        if index.exists():
            link = '<p><a href="ex072-finalization-v2/index.html">EX-072 자기대국·RLCD 최종 검증 정정본</a></p>\n'
            content = index.read_text()
            if "ex072-finalization-v2/index.html" not in content:
                atomic(
                    index,
                    (
                        content.replace("</body>", link + "</body>")
                        if "</body>" in content
                        else content + link
                    ).encode(),
                )
        return closure
    except Exception as error:
        if not destination.exists():
            atomic(
                directory / "corrections" / (IDENTITY + ".failure.json"),
                {
                    "type": type(error).__name__,
                    "detail": str(error),
                    "failed_at": time.time(),
                    "original_clock": clock.record,
                },
                immutable=True,
            )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(recover(args.directory, args.validation), ensure_ascii=False))


if __name__ == "__main__":
    main()
