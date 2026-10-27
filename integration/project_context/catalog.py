"""Generate navigation from canonical records; never infer experimental success."""

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from .registry import ROOT, load_registry, record_metadata, resolve_record
from .blocked import classified_rows, render_blocked, summary, validate_classification


def link(path, source):
    return os.path.relpath(path, source.parent)


def rebase_links(text, original, page):
    def replace(match):
        target = match[1]
        if re.match(r"[a-zA-Z]+:|/", target):
            return match[0]
        path, separator, anchor = target.partition("#")
        destination = original.parent / path if path else original
        return "](" + link(destination, page) + (separator + anchor if separator else "") + ")"
    return re.sub(r"\]\(([^)\n]+)\)", replace, text)


def render(root=ROOT):
    context = Path(root) / "project_context"
    data = load_registry(root)
    records = data["records"]
    metadata = {key: record_metadata(resolve_record(key, root=root)) for key in records}
    pages = {}
    blocked_rows = classified_rows(data, metadata, root)

    def table(ids, page):
        lines = ["| ID | 제목 | 상태 |", "|---|---|---|"]
        for key in sorted(ids, key=lambda k: (k.split("-")[0], int(k.split("-")[1]))):
            meta = metadata[key]
            status = rebase_links(meta["status"], context / records[key]["path"], page)
            lines.append(
                f"| [{key}]({link(context / records[key]['path'], page)})"
                f" | {meta['title'].split(' — ', 1)[-1].replace('|', '/')} "
                f"| {status.replace('|', '/')} |"
            )
        return "\n".join(lines) + "\n"

    for prefix, filename, title in [
        ("D", "decisions.md", "결정 목록"),
        ("EP", "plans.md", "실행 계획 목록"),
        ("EX", "experiments.md", "실험 목록"),
    ]:
        page = context / "catalog" / filename
        ids = [k for k in records if k.startswith(prefix + "-")]
        body = f"# {title}\n\n<!-- generated: scripts/context-catalog build -->\n\n"
        body += "원문 상태를 그대로 표시한다. 완료 상태는 효능 개선을 뜻하지 않는다.\n\n"
        if prefix == "EP":
            for anchor, heading, states in [
                ("running-plans", "진행", {"Active", "Running"}),
                ("blocked-plans", "Blocked 별도 관리", {"Blocked"}),
                ("paused-plans", "일시 중지·기타 중단", {"Paused", "Incomplete", "Stopped"}),
                ("completed-plans", "완료", {"Completed"}),
                ("other-plans", "기타", {"Draft", "Planned", "Abandoned"}),
            ]:
                body += f'<a id="{anchor}"></a>\n\n## {heading}\n\n'
                if anchor == "blocked-plans":
                    body += (
                        "원래 판정과 현재 처리 필요 여부를 구분한다. "
                        "[별도 색인](blocked.md)에서 이유·후속·근거를 확인한다.\n\n"
                        + summary(blocked_rows) + "\n"
                    )
                    continue
                body += table([k for k in ids if metadata[k]["state"] in states], page) + "\n"
        else:
            body += table(ids, page)
        pages[page] = body
    pages[context / "catalog/blocked.md"] = render_blocked(data, metadata, root)

    for topic, spec in data["topics"].items():
        page = context / topic / "RECORDS.md"
        pages[page] = (
            f"# {spec['title']} — 기록 목록\n\n"
            "<!-- generated: scripts/context-catalog build -->\n\n"
            "원문은 한 곳에 두며 다른 주제의 관련 기록은 색인과 원문 링크로 연결한다.\n\n"
            + table([k for k, entry in records.items() if entry["topic"] == topic], page)
        )

    for field, filename, title in [
        ("methods", "by-method.md", "방법별 탐색"),
        ("models", "by-model.md", "관련 모델별 탐색"),
        ("datasets", "by-dataset.md", "관련 자료별 탐색"),
    ]:
        page = context / "catalog" / filename
        groups = defaultdict(list)
        for key, entry in records.items():
            values = entry.get(field, [])
            if field == "methods":
                values = [f"{axis} / {value}" for axis, tags in values.items() for value in tags]
            for value in values:
                groups[value].append(key)
        body = (
            f"# {title}\n\n<!-- generated: scripts/context-catalog build -->\n\n"
            "탐색 분류는 처치의 동일성·실제 실행·직접 비교 가능성을 보증하지 않는다. "
            "관련 모델·자료에는 기준선과 참조도 포함하며 실제 조건은 원문을 확인한다.\n\n"
        )
        body += "| 분류 | 기록 수 |\n|---|---|\n"
        for tag, ids in sorted(groups.items()):
            anchor = re.sub(r"[^\w\- ]", "", tag.lower()).replace(" ", "-")
            body += f"| [{tag}](#{anchor}) | {len(ids)} |\n"
        body += "\n"
        for tag, ids in sorted(groups.items()):
            body += f"## {tag}\n\n" + table(ids, page) + "\n"
        pages[page] = body

    page = context / "catalog/relations.md"
    body = (
        "# 기록 관계\n\n<!-- generated: scripts/context-catalog build -->\n\n"
        "references는 원문에 명시된 연결이다. baseline/evaluates/continues/corrects는 "
        "관계 근거를 확인한 항목만 등록한다. 연결 자체는 재개 승인이나 효능 판정이 아니다.\n\n"
        "| 출발 | 관계 | 대상 |\n|---|---|---|\n"
    )
    for key, entry in sorted(records.items()):
        for relation in entry.get("relations", []):
            if relation["type"] == "references":
                continue
            target = relation["target"]
            body += (
                f"| [{key}]({link(context / entry['path'], page)}) | {relation['type']} "
                f"| [{target}]({link(context / records[target]['path'], page)}) |\n"
            )
    pages[page] = body
    return {path: content.rstrip() + "\n" for path, content in pages.items()}


def validate(root=ROOT):
    context = Path(root) / "project_context"
    data = load_registry(root)
    errors = []
    paths = set()
    aliases = set()
    for key, entry in data["records"].items():
        try:
            path = resolve_record(key, root=root)
            record_metadata(path)
        except (ValueError, KeyError, OSError) as exc:
            errors.append(str(exc))
            continue
        if entry["path"] in paths:
            errors.append(f"duplicate canonical path: {key}")
        paths.add(entry["path"])
        if entry["topic"] not in data["topics"]:
            errors.append(f"unknown topic: {key}")
        if not path.name.startswith(key + "-"):
            errors.append(f"filename ID mismatch: {key}")
        for alias in entry.get("legacy_paths", []):
            if alias in aliases:
                errors.append(f"duplicate alias: {alias}")
            aliases.add(alias)
        for relation in entry.get("relations", []):
            if relation["target"] not in data["records"]:
                errors.append(f"unknown relation target: {key} -> {relation['target']}")
    for base in ("research", "shared"):
        for path in (context / base).rglob("*.md"):
            if path.name.startswith(("D-", "EP-", "EX-")):
                if path.relative_to(context).as_posix() not in paths:
                    errors.append(f"unregistered record: {path}")
    for relative in data["authorities"]:
        if not (context / relative).is_file():
            errors.append(f"missing authority: {relative}")
    errors.extend(validate_classification(data, root))
    return errors


def main():
    parser = argparse.ArgumentParser(description="연구 기록 ID와 생성 색인 관리")
    parser.add_argument("command", choices=["build", "check", "resolve"])
    parser.add_argument("record_id", nargs="?")
    args = parser.parse_args()
    if args.command == "resolve":
        print(resolve_record(args.record_id))
        return
    errors = validate()
    if errors:
        raise SystemExit("\n".join(errors))
    pages = render()
    stale = []
    for path, content in pages.items():
        if args.command == "build":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        elif not path.exists() or path.read_text() != content:
            stale.append(str(path.relative_to(ROOT)))
    if stale:
        raise SystemExit("stale generated pages:\n" + "\n".join(stale))
    print(json.dumps({"records": len(load_registry()["records"]), "pages": len(pages)}))


if __name__ == "__main__":
    main()
