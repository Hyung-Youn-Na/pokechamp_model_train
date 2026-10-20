"""Portable complete JEV-9B originals and three relocated offline display checks."""
from __future__ import annotations

import argparse
import copy
import html
import json
from pathlib import Path
import re
import shutil
import tempfile

from integration.jev27b.study import decision_groups

from .config import DISK_BYTES, EXPORT, ROOT, RUN
from .study import (
    INTERPRETATION, REFERENCE_INTERPRETATION, event_rows, file_hash, seal, verify_seal, write_json,
)


def render_data(data):
    assets = ROOT / "integration/pokechamp/viewer_assets"
    template = (assets / "jev-researcher.html").read_text().replace(
        "__ACTION_LABELS__", (assets / "action-labels.js").read_text())
    template = template.replace('href="../decisions.html"', 'href="decisions.json"')
    template = template.replace("(data.outcome.outcome==='player_won'?'승리':'패배')",
        "({player_won:'승리',player_lost:'패배',tied:'무승부',output_failure:'모델 선택 실패'}[data.outcome.outcome]||'기술 실패')")
    template = template.replace("data.outcome.turns+'턴 · JEV '",
        "(Number.isFinite(data.outcome.turns)?data.outcome.turns+'턴':'진행 중 중단')+' · JEV '")
    template = template.replace("function stateView(d,p)",
        "function displayEffect(v){return typeof v==='object'&&v!==null?(v.name||v.id||'미확인'):v;}\nfunction stateView(d,p)")
    template = template.replace("m.ability,m.item", "displayEffect(m.ability),displayEffect(m.item)")
    template = template.replace(
        "기록된 요청 모델과 payload를 합친 전송 JSON 객체입니다. HTTP 바이트 원문이 아닌 기록 기반 복원이며 값은 변경하지 않았습니다.",
        "기록된 실제 HTTP 요청 JSON입니다. 기술 기록에 요청 바이트·request ID·본문 해시와 재시도를 보존했습니다.")
    if data.get("synthetic"):
        template = template.replace('<main class="layout">',
            '<p role="note">합성 실패 표시 검사 · 실제 경기·모델 추론·성적에 포함하지 않습니다.</p><main class="layout">')
    encoded = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return template.replace("__TITLE__", f"EX-085 · {data['slot']}경기 · JEV-9B").replace("__DATA__", encoded)


def _protocols(events):
    protocols = {}
    for event in events:
        if event["type"] == "protocol":
            protocols.setdefault(event["username"], []).extend(line for line in event["protocol"].splitlines()
                if line.startswith("|") and not line.startswith(("|request|", "|sentchoice|")))
    return {user: "\n".join(lines) + "\n" for user, lines in protocols.items()}


def _raw_paths(source, events, result):
    names = {"manifest.json", "events.jsonl", "result.json", "checksums.sha256"}
    if (source / "ledger.json").is_file():
        names.add("ledger.json")
    for event in events:
        if event["type"] == "input" and event.get("input_audit"):
            names.add(event["input_audit"]["path"])
    for outcome in result["outcomes"]:
        for filename in ("request.json", "outcome.json", "audit.json"):
            name = f"battle-{outcome['slot']}/{filename}"
            if (source / name).is_file():
                names.add(name)
    for name in names:
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()) or not path.is_file():
            raise ValueError("invalid original export path: " + name)
    return sorted(names)


def export(source=RUN / "collection", output=EXPORT, *, compared=None):
    from integration.pokechamp.observability.render import _replay_html
    source, output = Path(source), Path(output)
    verify_seal(source)
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest["experiment_id"] != "EX-085":
        raise ValueError("wrong JEV-9B export source")
    result = json.loads((source / "result.json").read_text())
    events = list(event_rows(source))
    groups, protocols = decision_groups(source), _protocols(events)
    output.mkdir(parents=True, exist_ok=False)
    originals = {}
    for name in _raw_paths(source, events, result):
        target = output / "raw" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        originals[name] = file_hash(source / name)
    rows = []
    for outcome in result["outcomes"]:
        slot, user = outcome["slot"], outcome["username"]
        target = output / f"battle-{slot}"
        target.mkdir()
        data = dict(experiment="EX-085", slot=slot, username=user, outcome=outcome,
                    decisions=groups.get(user, []))
        write_json(target / "decisions.json", data)
        if data["decisions"]:
            page = render_data(data)
        else:
            page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><p>입력 수집 전 종료된 경기입니다.</p>'
                    '<a href="replay.html">보존된 경기 로그</a><pre>'
                    + html.escape(json.dumps(outcome, ensure_ascii=False, indent=2)) + "</pre></html>")
        (target / "index.html").write_text(page)
        protocol = protocols.get(user, "\n")
        (target / "showdown.log").write_text(protocol)
        (target / "replay.html").write_text(_replay_html(
            dict(battle_id=f"ex085-battle-{slot}", teams=[]), protocol).replace(
                "Static protocol fallback", "오프라인 경기 로그"))
        label = dict(player_won="승리", player_lost="패배", tied="무승부",
                     output_failure="모델 선택 실패").get(outcome.get("outcome"), "기술 중단")
        if outcome.get("completed") and not outcome.get("audit_passed"):
            label += " · 유효성 미충족"
        rows.append(f'<tr><td>{slot}</td><td>{html.escape(outcome["slot_id"])}</td><td>{outcome["jev_actor"]}</td>'
            f'<td>{label}</td><td>{outcome.get("turns", "—")}</td>'
            f'<td><a href="battle-{slot}/index.html">입력·응답·선택·리플레이</a></td></tr>')
    score = result["overall"]
    summary = (f'유효 {result["completed"]}/{result["planned"]} · {score["wins"]}승 '
               f'{score["draws"]}무 {score["losses"]}패 · 완료쌍 {result["completed_pairs"]}/16')
    if result.get("final_audit_passed") is False:
        summary = "최종 기술 감사 실패 · 성적 확정 보류 · " + summary
    (output / "index.html").write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>EX-085 · JEV-9B</title>'
        '<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:35px auto;padding:0 20px}'
        'table{width:100%;border-collapse:collapse}td,th{padding:8px;text-align:left;border-bottom:1px solid #ccd}a{color:#165fa5}</style>'
        '<a href="../index.html">← 실험 목록</a><h1>EX-085 · JEV-9B 대 Abyssal</h1>'
        f'<p>{summary}</p><p>{INTERPRETATION}입니다. {REFERENCE_INTERPRETATION}입니다. '
        '일반 성능 우위나 모델 크기만의 효과를 주장하지 않습니다.</p>'
        '<p>전체 입력·응답·선택·공개 로그는 폴더 이동 후 오프라인으로 열립니다. 리플레이 애니메이션에는 인터넷 연결이 필요합니다.</p>'
        f'<p>실패 {result["failed"]} · 무효 {result["invalid"]} · 미실행 {result["unattempted"]}</p>'
        '<table><thead><tr><th>경기</th><th>대진</th><th>진영</th><th>결과</th><th>턴</th><th>열기</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table><p><a href="result.json">상세 결과</a> · '
        '<a href="comparison.json">EX-083 공통쌍 비교</a> · <a href="raw/events.jsonl">전체 원문 기록</a> · '
        '<a href="provenance.json">원본·복사본 연결</a></p></html>')
    write_json(output / "result.json", result)
    write_json(output / "comparison.json", compared)
    write_json(output / "provenance.json", dict(experiment="EX-085", source=str(source),
        source_files=originals, copied_files={name: "raw/" + name for name in originals},
        renderer_sha256=file_hash(Path(__file__)),
        template_sha256=file_hash(ROOT / "integration/pokechamp/viewer_assets/jev-researcher.html"),
        action_labels_sha256=file_hash(ROOT / "integration/pokechamp/viewer_assets/action-labels.js"),
        planned=result["planned"], completed=result["completed"],
        decisions=sum(map(len, groups.values())), actual_http_bytes_preserved=True,
        probability_scope="one complete Choice; original native probabilities unchanged"))
    seal(output)
    return verify_data(source, output)


def verify_data(source, output):
    """Compare every exported original, decision, embedded JSON and public replay log."""
    source, output = Path(source), Path(output)
    events = list(event_rows(source))
    groups, protocols = decision_groups(source), _protocols(events)
    result = json.loads((source / "result.json").read_text())
    provenance = json.loads((output / "provenance.json").read_text())
    expected_paths = _raw_paths(source, events, result)
    if set(provenance["source_files"]) != set(expected_paths):
        raise ValueError("exported original coverage differs")
    for name in expected_paths:
        if not file_hash(source / name) == provenance["source_files"][name] == file_hash(output / "raw" / name):
            raise ValueError("exported originals differ: " + name)
    decisions = 0
    for outcome in result["outcomes"]:
        target = output / f"battle-{outcome['slot']}"
        data = json.loads((target / "decisions.json").read_text())
        expected = dict(experiment="EX-085", slot=outcome["slot"], username=outcome["username"],
                        outcome=outcome, decisions=groups.get(outcome["username"], []))
        if data != expected:
            raise ValueError("exported observation/request/response/selection originals differ")
        if data["decisions"]:
            embedded = re.search(r'<script type="application/json" id="viewer-data">(.*?)</script>',
                                 (target / "index.html").read_text(), re.S)
            if embedded is None or json.loads(embedded.group(1)) != expected:
                raise ValueError("embedded original decision JSON differs")
        if (target / "showdown.log").read_text() != protocols.get(outcome["username"], "\n"):
            raise ValueError("exported replay protocol differs")
        decisions += len(data["decisions"])
    if decisions != result["decisions"]:
        raise ValueError("exported decision denominator differs")
    verify_seal(output)
    return dict(passed=True, games=len(result["outcomes"]), decisions=decisions,
        original_files_compared=len(expected_paths), all_originals_compared=True,
        source_seal=file_hash(source / "checksums.sha256"), export_seal=file_hash(output / "checksums.sha256"))


def verify_browser(output):
    from playwright.sync_api import sync_playwright
    from .resource import disk_bytes
    output = Path(output)
    verify_seal(output)
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    before = disk_bytes(extra_roots=(output,))
    if before + size > DISK_BYTES:
        raise ValueError("relocated viewer copy would exceed disk budget")
    samples, errors = {}, []
    synthetic = False
    with tempfile.TemporaryDirectory(prefix="ex085-offline-") as temporary:
        moved = Path(temporary) / "moved"
        shutil.copytree(output, moved)
        for path in sorted(moved.glob("battle-*/decisions.json")):
            data = json.loads(path.read_text())
            for index, decision in enumerate(data["decisions"]):
                if decision["selection"] and decision["wire"] and not decision["automatic"]:
                    samples.setdefault("normal", (path.parent, index))
                if decision["automatic"]:
                    samples.setdefault("automatic", (path.parent, index))
                if not decision["selection"] and not decision["wire"]:
                    samples.setdefault("failure", (path.parent, index))
            if len(samples) == 3:
                break
        if "failure" not in samples and samples:
            folder, index = samples.get("normal", next(iter(samples.values())))
            data = copy.deepcopy(json.loads((folder / "decisions.json").read_text()))
            data["synthetic"] = True
            data["outcome"].update(completed=False, audit_passed=False, outcome="output_failure")
            data["outcome"].pop("turns", None)
            data["decisions"] = [data["decisions"][index]]
            decision = data["decisions"][0]
            decision.update(selection=None, wire=None, automatic=False)
            if decision["response"]:
                decision["response"]["answers"]["action"]["choice"] = "synthetic-invalid-choice"
            decision["technical"].update(selection=None, wire=None,
                synthetic_failure="표시 검증 전용 · 실제 응답/성적 아님")
            target = moved / "synthetic-failure"
            target.mkdir()
            (target / "index.html").write_text(render_data(data))
            write_json(target / "decisions.json", data)
            samples["failure"] = (target, 0)
            synthetic = True
        peak = disk_bytes(extra_roots=(output, Path(temporary)))
        if peak > DISK_BYTES:
            raise ValueError("relocated viewer copy exceeds disk budget")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = browser.new_context(offline=True)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto((moved / "index.html").as_uri(), wait_until="domcontentloaded")
            for name, (folder, index) in samples.items():
                data = json.loads((folder / "decisions.json").read_text())
                decision = data["decisions"][index]
                page.goto((folder / "index.html").as_uri(), wait_until="domcontentloaded")
                page.select_option("#decision", str(index))
                if json.loads(page.locator("#request-json").inner_text()) != (decision["request"] or decision["observation"]):
                    raise ValueError("offline visible request differs")
                if decision["response"] is not None:
                    if json.loads(page.locator("#response-json").inner_text()) != decision["response"]:
                        raise ValueError("offline visible response differs")
                metrics = page.locator("#metrics").inner_text()
                if name == "automatic" and ("API 미호출" not in metrics or
                        "전송 요청이 아닙니다" not in page.locator("#request-note").inner_text()):
                    raise ValueError("automatic selection displayed as a model call")
                if name == "failure" and ("전송: 없음" not in metrics or
                        "실패" not in page.locator("#heading").inner_text()):
                    raise ValueError("failed selection incorrectly displayed")
            context.close()
            browser.close()
        if errors:
            raise ValueError("offline browser errors: " + repr(errors))
    missing = sorted({"normal", "automatic", "failure"} - set(samples))
    return dict(passed=not missing, offline_relocated=True, representative_screens=list(samples),
        unavailable_screens=missing, synthetic_failure_fixture=synthetic, browser_errors=errors,
        full_browser_replay=False, relocated_copy_bytes=size, disk_bytes_with_temporary_copy=peak)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify-browser",))
    parser.add_argument("--output", type=Path, default=EXPORT)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    write_json(args.receipt, verify_browser(args.output))
