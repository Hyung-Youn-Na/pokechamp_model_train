"""Sealed battle viewer and completion published only after evidence gates."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from . import config, reporting, viewer
from .runner import decisions_for, outcomes_for
from .storage import Clock, atomic, read, sha, write_jsonl


def seal(directory):
    directory = Path(directory)
    files = {
        str(p.relative_to(directory)): sha(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != "checksums.sha256"
    }
    atomic(
        directory / "checksums.sha256",
        "".join(f"{digest}  {name}\n" for name, digest in files.items()).encode(),
        immutable=True,
    )
    return files


def required_artifacts(directory, state, outcomes, decisions):
    """Missing or altered evidence must never disappear from a seal."""
    directory = Path(directory)
    required = [
        "manifest.json",
        "prepared/manifest.json",
        "clock.json",
        "resource.json",
        "latest.json",
    ]
    required.extend(
        "prepared/" + name
        for name in read(directory / "prepared/manifest.json")["files"]
    )
    paths = [directory / name for name in required]
    if not all(p.is_file() for p in paths):
        raise ValueError("required execution artifact is missing")
    for name, digest in read(directory / "prepared/manifest.json")["files"].items():
        if sha(directory / "prepared" / name) != digest:
            raise ValueError("prepared data differs from its frozen manifest")
        pointer = read(directory / "latest.json")
    checkpoint = Path(pointer["path"])
    if (
        not checkpoint.is_relative_to(directory / "checkpoints")
        or sha(checkpoint) != pointer["sha256"]
    ):
        raise ValueError("required restart checkpoint is missing or changed")
    paths.append(checkpoint)
    snapshots = state.get("snapshot_paths", {})
    if state.get("selected") and "final" not in snapshots:
        raise ValueError("selected policy has no locked final snapshot")
    for record in snapshots.values():
        path = Path(record["path"])
        if (
            not path.is_relative_to(directory / "snapshots")
            or sha(path) != record["sha256"]
        ):
            raise ValueError("snapshot is missing or changed")
        paths.append(path)
    if "final" in snapshots:
        lock = read(directory / "evaluation-lock.json")
        if (
            lock["final"] != snapshots["final"]
            or lock["selected"] != state["selected"]
            or lock["clock"] != read(directory / "clock.json")
            or lock["schedule_sha256"] != sha(directory / "prepared/schedule.json")
        ):
            raise ValueError("final policy/head identity differs from the test lock")
        paths.append(directory / "evaluation-lock.json")
    required_gates = {
        "gpu_preflight": "preflight",
        "first_eight_audit": "first-eight",
        "resume_validation": "resume",
    }
    for flag, name in required_gates.items():
        path = directory / "verification" / f"{name}.json"
        if state.get("checks", {}).get(flag):
            if not path.is_file() or read(path).get("passed") is not True:
                raise ValueError("required verification receipt is missing: " + flag)
            paths.append(path)
    covered = {r["slot_id"] for r in decisions}
    for row in outcomes:
        if row["status"] != "completed":
            continue
        attempt = directory / "games" / row["slot_id"]
        audit = read(attempt / "audit.json")
        if not audit["passed"]:
            raise ValueError("a completed game lacks its passing transmission audit")
        expected = audit.get("valid_decisions", 0)
        actual = sum(r["slot_id"] == row["slot_id"] for r in decisions)
        if actual != expected:
            raise ValueError("normal-game chosen-action probability data is missing")
        if (
            row["stage"] == "test"
            and row["model"] == "selected"
            and row["slot_id"] not in covered
        ):
            raise ValueError(
                "selected test game has no chosen-action probability evidence"
            )
    return sorted(set(paths))


def finalize(directory, *, export_root=None):
    directory = Path(directory).resolve()
    execution = read(directory / "manifest.json")
    if execution.get("experiment_id") != "EX-072":
        raise ValueError("finalization is restricted to an EX-072 execution")
    if (directory / "completed.json").exists():
        closed = read(directory / "completed.json")
        if sha(closed["result_path"]) != closed["result_sha256"]:
            raise ValueError("final result changed after completion")
        return closed
    final = directory / "final"
    if final.exists():
        raise FileExistsError(
            "preserve earlier finalization before a documented correction"
        )
    final.mkdir()
    state = (
        read(directory / "state.json") if (directory / "state.json").exists() else {}
    )
    schedule = read(directory / "prepared/schedule.json")
    outcomes = outcomes_for(directory, schedule)
    decisions = decisions_for(directory, outcomes)
    train = [r for r in outcomes if r["stage"] == "train"]
    checks = dict(state.get("checks", {}))
    checks["test"] = reporting.paired_bootstrap(
        [r for r in outcomes if r["stage"] == "test" and r["model"] == "initial"],
        [r for r in outcomes if r["stage"] == "test" and r["model"] == "selected"],
    )["complete"]
    # Interrupted claims need an explicit cleanup receipt, never an assumed pass.
    checks["cleanup"] = all(
        row.get("actors_cleaned") is True and row.get("server_cleaned") is True
        for row in outcomes
        if row["status"] != "unattempted"
    )
    checks.update(viewer=False, sealed=False)
    metadata = {
        "selection": state.get("selected"),
        "calibration": state.get("calibration_decision"),
        "final_model": state.get("snapshot_paths", {}).get("final"),
        "restart_checkpoint": read(directory / "latest.json")
        if (directory / "latest.json").exists()
        else None,
        "clock": read(directory / "clock.json")
        if (directory / "clock.json").exists()
        else None,
        "resource": read(directory / "resource.json")
        if (directory / "resource.json").exists()
        else None,
        "failure": read(directory / "failure.json")
        if (directory / "failure.json").exists()
        else None,
        "reason": state.get("reason"),
        "policy_updates": (state.get("trainer") or {}).get("global_updates", 0),
    }

    def summarize():
        result = reporting.summarize(
            schedule,
            outcomes,
            decisions=decisions,
            train_outcomes=train,
            stage_status=checks,
        )
        result.update(metadata)
        return result

    result = summarize()
    export_root = Path(
        export_root or config.ROOT / "exports/battle_viewers/ex072"
    ).resolve()
    owned_export = False
    failure = None
    try:
        clock = Clock(directory)

        def require_time():
            if clock.remaining() <= 15:
                raise TimeoutError(
                    "original experiment budget exhausted during finalization"
                )

        require_time()
        paths = required_artifacts(directory, state, outcomes, decisions)
        # Checkpoint/model/data integrity is checked before publishing any success.
        artifacts = {str(p.relative_to(directory)): sha(p) for p in paths}
        atomic(final / "artifact-manifest.json", artifacts, immutable=True)
        if checks["test"] and not {"before", "after", "constant"} <= set(
            result["probability"]
        ):
            raise ValueError(
                "required selected-action probability comparisons are missing"
            )
        bundle = final / "battles"
        bundle.mkdir()
        for row in outcomes:
            require_time()
            source = directory / "games" / row["slot_id"]
            if source.exists():
                destination = bundle / "games" / row["slot_id"]
                destination.mkdir(parents=True)
                for path in source.iterdir():
                    if path.is_file():
                        require_time()
                        shutil.copyfile(path, destination / path.name)
        manifest = {
            "experiment_id": "EX-072",
            "schedule": schedule,
            "execution": execution,
            "original_directory": str(directory),
            "prepared_manifest_sha256": sha(directory / "prepared/manifest.json"),
            "report_stage": "before_offline_viewer_verification",
        }
        atomic(bundle / "manifest.json", manifest, immutable=True)
        atomic(bundle / "result.json", result, immutable=True)
        pending = "\n이 문서는 오프라인 뷰어 검증 전의 보존 기록입니다. 최종 판정은 상위 실험 목록과 최종 report.md를 따릅니다.\n"
        atomic(
            bundle / "report.md",
            (reporting.report_markdown(result) + pending).encode(),
            immutable=True,
        )
        write_jsonl(bundle / "decisions.jsonl", decisions, immutable=True)
        require_time()
        seal(bundle)
        if export_root.exists():
            raise FileExistsError("prior EX-072 viewer must be preserved")
        require_time()
        export_root.mkdir(parents=True, exist_ok=False)
        owned_export = True
        receipt = viewer.export(
            bundle, export_root / "viewer", deadline=clock.deadline("total") - 15
        )
        atomic(final / "viewer-export.json", receipt, immutable=True)
        require_time()
        command = [
            "/tmp/ep037/tools/bin/python",
            "-m",
            "integration.pokechamp.selfplay",
            "verify-browser",
            "--source",
            str(bundle),
            "--export",
            str(export_root / "viewer"),
            "--receipt",
            str(final / "viewer-export.json"),
            "--report",
            str(final / "viewer-check.json"),
        ]
        completed = subprocess.run(
            command,
            cwd=config.ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=clock.remaining() - 15,
        )
        atomic(
            final / "viewer-check.log",
            (completed.stdout + completed.stderr).encode(),
            immutable=True,
        )
        if completed.returncode or not read(final / "viewer-check.json")["passed"]:
            raise ValueError("moved offline viewer verification failed")
        require_time()
        viewer.verify_source(bundle)
        for relative, digest in artifacts.items():
            if sha(directory / relative) != digest:
                raise ValueError("required artifact changed during finalization")
        checks["viewer"] = True
        checks["sealed"] = True
    except Exception as error:  # noqa: BLE001 -- preserve failure evidence at the execution boundary
        failure = {"type": type(error).__name__, "detail": str(error)}
        atomic(final / "failure.json", failure, immutable=True)
    result = summarize()
    if failure:
        result["finalization_error"] = failure
        result["experiment_complete"] = False
        result["incomplete_requirements"] = sorted(
            set(result["incomplete_requirements"] + ["finalization"])
        )
    atomic(final / "result.json", result, immutable=True)
    atomic(
        final / "report.md", reporting.report_markdown(result).encode(), immutable=True
    )
    if owned_export and export_root.exists():
        # The already tested, sealed viewer subtree is untouched. The final
        # report and outer listing are published separately after verification.
        for name in ("report.md", "result.json"):
            shutil.copyfile(final / name, export_root / name)
        atomic(
            export_root / "manifest.json",
            {
                "experiment_id": "EX-072",
                "execution": execution,
                "final_report_source": str(final),
                "verified_viewer": "viewer/index.html",
            },
            immutable=True,
        )
        atomic(
            export_root / "provenance.json",
            {
                "experiment_id": "EX-072",
                "original_manifest_sha256": sha(directory / "manifest.json"),
                "final_result_sha256": sha(final / "result.json"),
                "viewer_verification": read(final / "viewer-check.json")
                if (final / "viewer-check.json").exists()
                else None,
            },
            immutable=True,
        )
        listing = (
            (export_root / "viewer/index.html").read_text()
            if (export_root / "viewer/index.html").exists()
            else "<html><body>EX-072 내보내기 미완료</body></html>"
        )
        listing = listing.replace('href="battle-', 'href="viewer/battle-')
        status = f'<p>최종 실험 완료: {"예" if result["experiment_complete"] else "아니요"} · <a href="report.md">최종 보고</a></p>'
        listing = listing.replace("<main>", "<main>" + status)
        atomic(export_root / "index.html", listing.encode(), immutable=True)
        seal(export_root)
        index = export_root.parent / "index.html"
        if index.exists() and "ex072/index.html" not in index.read_text():
            content = index.read_text()
            link = (
                '<p><a href="ex072/index.html">EX-072 자기대국·RLCD 확률 보정</a></p>\n'
            )
            atomic(
                index,
                (
                    content.replace("</body>", link + "</body>")
                    if "</body>" in content
                    else content + link
                ).encode(),
            )
    closure = {
        "closed": True,
        "experiment_complete": result["experiment_complete"],
        "performance_improved": result["performance_improved"],
        "completed_at": time.time(),
        "result_path": str(final / "result.json"),
        "result_sha256": sha(final / "result.json"),
        "viewer_path": str(export_root / "index.html")
        if owned_export and (export_root / "index.html").exists()
        else None,
        "incomplete_requirements": result["incomplete_requirements"],
    }
    atomic(directory / "completed.json", closure, immutable=True)
    return closure
