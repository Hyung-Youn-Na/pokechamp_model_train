"""EP-117: 동결된 EX-072 뷰어의 JSON 문자 표시만 별도 사본에서 교정한다."""

from __future__ import annotations

import copy
import json
import math
import shutil
import time
from pathlib import Path

from integration.pokechamp.imitation.storage import atomic, read, sha
from integration.pokechamp.selfplay import viewer

IDENTITY = "ex072-viewer-exact-json-v1"


def _replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("frozen viewer text does not match the registered correction")
    return text.replace(old, new, 1)


def _pretty(value):
    return (
        "없음"
        if value is None
        else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    )


def corrected_page(data):
    """큰 JSON 정수를 숫자형 그대로 보존한다. 행동 표·선택·검증 기준은 바꾸지 않는다."""
    exact = []
    for decision in data["decisions"]:
        technical = {
            "selection": decision.get("selection"),
            "wire": decision.get("wire"),
            "revalidation": decision.get("revalidation"),
            **(decision.get("technical") or {}),
        }
        exact.append(
            {
                "input": _pretty(decision.get("input")),
                "request": _pretty(decision.get("request")),
                "response": _pretty(decision.get("response")),
                "calibration": _pretty(decision.get("recorded_prediction")),
                "technical": _pretty(technical),
                "decision": _pretty(decision),
            }
        )
    script = _replace_once(
        viewer.SCRIPT,
        "const rows=data.decisions;let position=0;",
        "const exactRows=JSON.parse(document.getElementById('exact-json').textContent);\n"
        "const rows=data.decisions;let position=0;",
    )
    script = _replace_once(
        script,
        "function showJson(id,value){\n"
        " const text=value===null||value===undefined?'없음':JSON.stringify(value,null,2);",
        "function showJson(id,text){",
    )
    script = _replace_once(
        script,
        " showJson('input',d.input);showJson('request',d.request);\n"
        " if(d.response)showJson('response',d.response);\n"
        " else q('response').textContent=d.raw_response||'응답 기록 없음';\n"
        " showJson('calibration',d.recorded_prediction);\n"
        " showJson('technical',{selection:d.selection,wire:d.wire,revalidation:d.revalidation,...d.technical});",
        " const exact=exactRows[position];\n"
        " showJson('input',exact.input);showJson('request',exact.request);\n"
        " if(d.response)showJson('response',exact.response);\n"
        " else q('response').textContent=d.raw_response||'응답 기록 없음';\n"
        " showJson('calibration',exact.calibration);\n"
        " showJson('technical',exact.technical);",
    )
    script = _replace_once(
        script,
        " const blob=new Blob([JSON.stringify(rows[position]||{},null,2)],{type:'application/json'});",
        " const blob=new Blob([exactRows[position]?exactRows[position].decision:'{}'],{type:'application/json'});",
    )
    return _replace_once(
        viewer._page(data),
        "<script>" + viewer.SCRIPT + "</script>",
        '<script type="application/json" id="exact-json">'
        + viewer._encoded(exact)
        + "</script><script>"
        + script
        + "</script>",
    )


def _require_time(deadline):
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError("original absolute UNIX deadline is required")
    if time.time() >= deadline:
        raise TimeoutError(
            "original EX-072 deadline reached; correction cannot extend the clock"
        )


def _inventory(directory, *, deadline=None):
    result = {}
    for path in sorted(directory.rglob("*")):
        if deadline is not None:
            _require_time(deadline)
        if path.is_symlink():
            raise ValueError("viewer inventory contains a symlink")
        if path.is_file():
            result[str(path.relative_to(directory))] = sha(path)
    return result


def copy_export(original_leaf, new_leaf, original_receipt, *, deadline):
    """기존 export를 보존하고 페이지 JSON 표시·provenance만 교정한 새 봉인을 만든다.

    deadline은 최초 실행의 절대 UNIX 시각이다. 반환 inventory는 viewer.verify_source와
    같이 checksums.sha256를 제외한다. 실패 시 부분 사본은 보존하며 완료 receipt를 반환하지 않는다.
    """
    _require_time(deadline)
    original_leaf, new_leaf = Path(original_leaf).resolve(), Path(new_leaf).resolve()
    if new_leaf.exists():
        raise FileExistsError("corrected export destination already exists")
    if new_leaf.is_relative_to(original_leaf) or original_leaf.is_relative_to(new_leaf):
        raise ValueError(
            "corrected export must be separate from the preserved original"
        )
    receipt = (
        read(original_receipt)
        if isinstance(original_receipt, (str, Path))
        else copy.deepcopy(original_receipt)
    )
    original_files = viewer.verify_source(original_leaf)
    before = _inventory(original_leaf, deadline=deadline)
    original_seal = before["checksums.sha256"]
    if (
        receipt["export_sha256"] != original_seal
        or Path(receipt["index"]).resolve() != original_leaf / "index.html"
    ):
        raise ValueError("original export receipt identity differs")
    provenance = read(original_leaf / "provenance.json")
    source = Path(provenance["source"]).resolve()
    if new_leaf.is_relative_to(source):
        raise ValueError("corrected export must not modify the preserved source bundle")
    if (
        provenance.get("experiment_id") != "EX-072"
        or provenance["matches"] != receipt["matches"]
        or provenance["planned"] != receipt["planned"]
        or provenance["completed"] != receipt["completed"]
        or provenance["builder_sha256"] != sha(Path(viewer.__file__))
    ):
        raise ValueError(
            "original viewer provenance differs from the frozen builder or receipt"
        )
    source_seal = sha(source / "checksums.sha256")
    if source_seal != provenance["source_seal_sha256"]:
        raise ValueError("original source seal differs from export provenance")
    page_names = {
        f"battle-{index:03d}/index.html"
        for index in range(1, len(receipt["matches"]) + 1)
    }
    actual_pages = {
        str(path.relative_to(original_leaf))
        for path in original_leaf.glob("battle-*/index.html")
    }
    if actual_pages != page_names or not page_names <= set(original_files):
        raise ValueError("original viewer page denominator differs")
    allowed = page_names | {"provenance.json", "checksums.sha256"}
    helper_sha = sha(Path(__file__))
    _require_time(deadline)
    try:
        new_leaf.mkdir(parents=True, exist_ok=False)
        for name in sorted(before):
            _require_time(deadline)
            if Path(name).name == "checksums.sha256":
                continue
            destination = new_leaf / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_leaf / name, destination)
        for name in sorted(page_names):
            _require_time(deadline)
            data = read(new_leaf / Path(name).parent / "decisions.json")
            if (original_leaf / name).read_text() != viewer._page(data):
                raise ValueError(
                    "original HTML differs from the frozen viewer renderer: " + name
                )
            atomic(new_leaf / name, corrected_page(data).encode())
        corrected_provenance = copy.deepcopy(provenance)
        corrected_provenance["original_builder_sha256"] = provenance["builder_sha256"]
        corrected_provenance["builder_sha256"] = helper_sha
        corrected_provenance["exact_json_correction"] = {
            "identity": IDENTITY,
            "helper": str(Path(__file__).resolve()),
            "helper_sha256": helper_sha,
            "original_export": str(original_leaf),
            "original_export_seal_sha256": original_seal,
            "original_provenance_sha256": before["provenance.json"],
            "original_source_seal_sha256": source_seal,
            "change": "Python-preformatted JSON strings for display, copy, and download; numeric types preserved",
        }
        atomic(new_leaf / "provenance.json", corrected_provenance)
        unsealed = _inventory(new_leaf, deadline=deadline)
        if set(unsealed) != set(original_files):
            raise ValueError("corrected export file set differs")
        for name, digest in unsealed.items():
            if name not in allowed and digest != before[name]:
                raise ValueError("unapproved export file changed: " + name)
        _require_time(deadline)
        atomic(
            new_leaf / "checksums.sha256",
            "".join(
                digest + "  " + name + "\n" for name, digest in sorted(unsealed.items())
            ).encode(),
            immutable=True,
        )
        if viewer.verify_source(new_leaf) != unsealed:
            raise ValueError("new viewer seal verification differs")
        after = _inventory(new_leaf, deadline=deadline)
        if set(after) != set(original_files) | {"checksums.sha256"}:
            raise ValueError("corrected complete inventory differs")
        changed = {
            name for name in set(before) & set(after) if before[name] != after[name]
        }
        if changed != allowed:
            raise ValueError(
                "corrected export did not change exactly the registered files"
            )
        new_receipt = copy.deepcopy(receipt)
        new_receipt.update(
            index=str(new_leaf / "index.html"), export_sha256=after["checksums.sha256"]
        )
    finally:
        if (
            _inventory(original_leaf) != before
            or viewer.verify_source(original_leaf) != original_files
        ):
            raise ValueError("preserved original viewer changed during correction")
        if sha(source / "checksums.sha256") != source_seal:
            raise ValueError("preserved source seal changed during correction")
        if sha(Path(__file__)) != helper_sha:
            raise ValueError("correction helper changed during execution")
    _require_time(deadline)
    return new_receipt, unsealed
