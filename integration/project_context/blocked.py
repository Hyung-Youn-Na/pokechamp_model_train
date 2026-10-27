"""Navigation dispositions for historically blocked plans, not execution approvals."""

import json
import os
import re
from pathlib import Path

from .registry import ROOT, record_metadata

CATEGORIES = {
    "awaiting": "해결 대기",
    "resolved": "후속 해결·종결",
    "ended": "진행 종료",
    "review": "확인 필요",
}


def load_classification(root=ROOT):
    path = Path(root) / "project_context/catalog/blocked.json"
    if not path.exists():
        return {"records": {}}

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate blocked classification key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(), object_pairs_hook=unique)


def classified_rows(registry, metadata, root=ROOT):
    entries = load_classification(root)["records"]
    rows = {}
    for key in registry["records"]:
        if not key.startswith("EP-") or metadata[key]["state"] != "Blocked":
            continue
        rows[key] = entries.get(key, {
            "category": "review",
            "reason": "관리 분류 미등록: 현재 처리 필요와 후속 범위를 확인해야 한다.",
            "evidence": [key], "experiments": [], "followups": [],
        })
    return rows


def summary(rows):
    text = "| 관리 분류 | 계획 수 |\n|---|---|\n"
    for category, label in CATEGORIES.items():
        count = sum(row["category"] == category for row in rows.values())
        text += f"| [{label}](blocked.md#{category}) | {count} |\n"
    return text


def render_blocked(registry, metadata, root=ROOT):
    context = Path(root) / "project_context"
    page = context / "catalog/blocked.md"
    rows = classified_rows(registry, metadata, root)

    def links(keys):
        return " · ".join(
            f"[{key}]({os.path.relpath(context / registry['records'][key]['path'], page.parent)})"
            for key in keys
        ) or "—"

    body = (
        "# Blocked 계획 별도 분류\n\n<!-- generated: scripts/context-catalog build -->\n\n"
        "당시 실행 판정은 모두 원문의 Blocked로 보존한다. 아래는 현재 관리 분류이며 "
        "실험 재개 승인·원실험 성공·장애의 영구 해소를 뜻하지 않는다.\n"
        "분류 단위는 EP이며 관련 EX를 함께 연결한다. Paused는 "
        "[계획 색인](plans.md#paused-plans)에서 별도로 확인한다.\n\n"
        "해결 대기는 현재 이어갈 필요까지 확인된 경우에만 사용한다. 후속이 있어도 "
        "부분 교정·다른 과제의 완료에 그쳤으면 확인 필요에 둔다. 분류가 없는 새 Blocked도 "
        "확인 필요로 표시한다.\n\n"
        + summary(rows) + "\n"
    )
    reviewed = load_classification(root).get("reviewed_at")
    if reviewed:
        body += f"관리 분류 검토 기준일: {reviewed}. 새 미분류 Blocked는 확인 필요에 함께 표시한다.\n\n"
    for category, label in CATEGORIES.items():
        body += f'<a id="{category}"></a>\n\n## {label}\n\n'
        matching = [(k, v) for k, v in sorted(rows.items()) if v["category"] == category]
        if not matching:
            body += "현재 근거로 확인된 항목 없음. 미완료라는 이유만으로 새 작업을 만들지 않는다.\n\n"
            continue
        body += "| 계획·원문 판정 | 관련 실험 | 분류 이유 | 후속·근거 |\n|---|---|---|---|\n"
        for key, row in matching:
            reason = row["reason"].replace("|", "/").replace("\n", " ")
            title = metadata[key]["title"].split(" — ", 1)[-1].replace("|", "/")
            # Status descriptions may contain relative Markdown links; the original
            # record is linked above, so keep the label as text in this separate view.
            status = metadata[key]["status"].replace("|", "/")
            status = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", status)
            support = "후속: " + links(row.get("followups", []))
            if row.get("resolved_by"):
                support += "<br>종결 근거: " + links([row["resolved_by"]])
            support += "<br>판단 근거: " + links(row["evidence"])
            body += (
                f"| {links([key])}<br>{title}<br>{status} | {links(row.get('experiments', []))} "
                f"| {reason} | {support} |\n"
            )
        body += "\n"
    return body.rstrip() + "\n"


def validate_classification(registry, root=ROOT):
    context = Path(root) / "project_context"
    records = registry["records"]
    errors = []
    for key, entry in load_classification(root)["records"].items():
        if key not in records or not key.startswith("EP-"):
            errors.append(f"unknown blocked plan: {key}")
            continue
        try:
            if record_metadata(context / records[key]["path"])["state"] != "Blocked":
                errors.append(f"classification requires Blocked source: {key}")
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
        if entry.get("category") not in CATEGORIES:
            errors.append(f"unknown blocked category: {key}")
        if not entry.get("reason", "").strip() or not entry.get("evidence"):
            errors.append(f"blocked classification needs reason and evidence: {key}")
        for field in ("evidence", "followups", "experiments"):
            values = entry.get(field, [])
            if len(values) != len(set(values)):
                errors.append(f"duplicate blocked {field}: {key}")
            for target in values:
                if target not in records:
                    errors.append(f"unknown blocked {field}: {key} -> {target}")
                elif field == "experiments" and not target.startswith("EX-"):
                    errors.append(f"expected EX reference: {key} -> {target}")
        if entry.get("category") == "resolved":
            target = entry.get("resolved_by")
            if (target not in records or target == key
                    or target not in entry.get("followups", [])
                    or target not in entry.get("evidence", [])):
                errors.append(f"resolved classification needs an evidenced successor: {key}")
            else:
                state = record_metadata(context / records[target]["path"])["state"]
                if not target.startswith(("EP-", "EX-")) or state != "Completed":
                    errors.append(f"resolved successor is not completed: {key} -> {target}")
    return errors
