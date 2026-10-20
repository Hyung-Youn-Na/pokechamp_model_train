"""Portable originals and public turn logs for the explicitly registered v6 cohorts."""
from __future__ import annotations

import argparse
import copy
import html
import json
from pathlib import Path
import re
import shutil
import tempfile

from integration.jev27b.study import decision_groups, event_rows, file_hash, seal, verify_seal, write_json

from .turn_logs import ROOT, build_turn_log, parser_identity, raw_text, rows_for


HERE = Path(__file__).parent
ACTION_LABELS = ROOT / "integration/pokechamp/viewer_assets/action-labels.js"
NO_DAMAGE_PROFILE = "jev-choice-v6-no-damage"
NO_DAMAGE_LABEL = "피해 예측 비활성화 · 스피드 비교 유지"
EXPERIMENT_PROFILES = {**dict.fromkeys(("EX-086", "EX-087", "EX-088", "EX-089"), "jev-choice-v6"),
                       "EX-090": NO_DAMAGE_PROFILE, "EX-091": "jev-choice-v6"}
EXPERIMENTS = tuple(EXPERIMENT_PROFILES)
MINICPM_EXPERIMENT = "EX-091"


def _treatment_metadata(manifest):
    profile = EXPERIMENT_PROFILES.get(manifest.get("experiment_id"))
    if profile is None or manifest.get("schema_version") != profile:
        raise ValueError("public-memory viewer requires the registered experiment input profile")
    if profile == NO_DAMAGE_PROFILE:
        return dict(input_profile=profile, treatment=dict(
            damage_predictions_enabled=False, speed_comparison_enabled=True))
    return {}


def source_identity():
    paths = [Path(__file__), HERE / "turn_logs.py", HERE / "viewer.html", HERE / "viewer.js",
             HERE / "damage_data.py", HERE / "damage_viewer.js", ACTION_LABELS]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths}


def render_data(data):
    template = (HERE / "viewer.html").read_text()
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace(
        "&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    model = "MiniCPM5-2B-Jev" if data["experiment"] == MINICPM_EXPERIMENT else "JEV v6"
    return (template.replace("__TITLE__", html.escape(f"{data['experiment']} · {data['slot']}경기 · {model}"))
        .replace("__DATA__", encoded).replace("__ACTION_LABELS__", ACTION_LABELS.read_text())
        .replace("__VIEWER_JS__", (HERE / "viewer.js").read_text())
        .replace("__DAMAGE_JS__", (HERE / "damage_viewer.js").read_text()))


def _raw_paths(source, events, result):
    names = {"manifest.json", "events.jsonl", "result.json", "checksums.sha256"}
    if (source / "ledger.json").is_file():
        names.add("ledger.json")
    for event in events:
        if event.get("type") == "input" and event.get("input_audit"):
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


def _model_identity(source, manifest, outcome):
    """Tie the outcome actor to the frozen slot and recorded launch identity."""
    actor, user = outcome["jev_actor"], outcome["username"]
    if actor not in ("p1", "p2") or not isinstance(user, str) or not user:
        raise ValueError("missing model actor identity for public log")
    if "schedule" in manifest:
        matches = [slot for slot in manifest["schedule"] if slot["slot_id"] == outcome["slot_id"]]
        if len(matches) != 1 or matches[0]["jev_actor"] != actor:
            raise ValueError("model actor differs from manifest schedule")
    request = source / f"battle-{outcome['slot']}/request.json"
    if request.is_file():
        recorded = json.loads(request.read_text())
        if recorded["names"][actor] != user or recorded["slot"]["jev_actor"] != actor:
            raise ValueError("model username differs from recorded battle launch")
    return user, actor


def _battle_data(source, manifest, outcome, events, groups, *, text_renderer=None):
    user, actor = _model_identity(source, manifest, outcome)
    decisions = groups.get(user, [])
    treatment = _treatment_metadata(manifest)
    if treatment or manifest["experiment_id"] == MINICPM_EXPERIMENT:
        for decision in decisions:
            payload = decision["request"] or decision["observation"]
            if payload["state"].get("version") != manifest["schema_version"]:
                raise ValueError("decision input profile differs from the registered treatment")
    kwargs = {} if text_renderer is None else dict(text_renderer=text_renderer)
    turn_log = build_turn_log(events, user, actor, decisions, **kwargs)
    return dict(experiment=manifest["experiment_id"], slot=outcome["slot"], username=user,
                outcome=outcome, decisions=decisions, turn_log=turn_log, **treatment)


def export(source, output, *, compared=None):
    from integration.pokechamp.observability.render import _replay_html
    from . import damage_data
    source, output = Path(source), Path(output)
    verify_seal(source)
    manifest = json.loads((source / "manifest.json").read_text())
    experiment = manifest["experiment_id"]
    treatment = _treatment_metadata(manifest)
    viewer_files = source_identity()
    if any(manifest.get("source", {}).get(name) != value for name, value in viewer_files.items()):
        raise ValueError("viewer HTML/JS/converter source differs from frozen manifest")
    result = json.loads((source / "result.json").read_text())
    events, groups = list(event_rows(source)), decision_groups(source)
    saved_damage = experiment == MINICPM_EXPERIMENT
    entries = damage_data.input_events(events) if saved_damage else None
    parser = parser_identity()
    if len({outcome["username"] for outcome in result["outcomes"]}) != len(result["outcomes"]):
        raise ValueError("ambiguous model username across battles")
    if set(groups) - {outcome["username"] for outcome in result["outcomes"]}:
        raise ValueError("decisions without a recorded model outcome")
    # Source faults are diagnosed before writing a partially valid viewer.
    games = [_battle_data(source, manifest, outcome, events, groups) for outcome in result["outcomes"]]
    output.mkdir(parents=True, exist_ok=False)
    originals = {}
    for name in _raw_paths(source, events, result):
        target = output / "raw" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        originals[name] = file_hash(source / name)
    rows = []
    for data in games:
        outcome, log, slot = data["outcome"], data["turn_log"], data["slot"]
        target = output / f"battle-{slot}"
        target.mkdir()
        if saved_damage:
            damage_data.export_battle(source, target, data, entries)
        write_json(target / "decisions.json", data)
        write_json(target / "turn-logs.json", log)
        (target / "index.html").write_text(render_data(data))
        protocol = raw_text([row for turn in log["turns"] for row in turn["rows"]])
        (target / "showdown.log").write_text(protocol)
        (target / "replay.html").write_text(_replay_html(
            dict(battle_id=f"{experiment.lower().replace('-', '')}-battle-{slot}", teams=[]), protocol
        ).replace("Static protocol fallback", "오프라인 공개 경기 로그"))
        label = dict(player_won="승리", player_lost="패배", tied="무승부",
                     output_failure="모델 선택 실패").get(outcome.get("outcome"), "기술 실패")
        if not log["terminal"]:
            label += " · 진행 중 중단"
        elif outcome.get("completed") and not outcome.get("audit_passed"):
            label += " · 유효성 미충족"
        last = log["terminal"]["turn"] if log["terminal"] else "진행 중 중단"
        link_label = "입력·선택·턴 로그·Damage-calc" if saved_damage else "입력·선택·턴 로그"
        rows.append(f'<tr><td>{slot}</td><td>{html.escape(outcome["slot_id"])}</td>'
            f'<td>{html.escape(outcome["jev_actor"])}</td><td>{label}</td><td>{last}</td>'
            f'<td><a href="battle-{slot}/index.html">{link_label}</a></td></tr>')
    score = result["overall"]
    summary = (f'유효 {result["completed"]}/{result["planned"]} · {score["wins"]}승 '
               f'{score["draws"]}무 {score["losses"]}패 · 완료쌍 {result["completed_pairs"]}/16')
    if result.get("final_audit_passed") is False:
        summary = "최종 기술 감사 실패 · 성적 확정 보류 · " + summary
    description = (
        '<p>MiniCPM5-2B-Jev와 EX-089의 JEV-9B를 같은 v6 입력 정보·피해 예측·스피드 비교·'
        '정책·고정 대진에서 비교하는 모델 패키지 탐색 평가입니다. '
        '기준선 EX-089는 6승 0무 26패 · 점수 18.75%입니다. '
        '모델·토크나이저·모델 전용 입력 형식·GPU 배치가 함께 다르며, '
        '공식 기본 서버 그대로의 재현이나 모델 크기만의 효과·일반 성능 우위·동등성을 주장하지 않습니다.</p>'
        '<p>Damage-calc는 각 결정 당시 저장 계산을 그대로 연결합니다. 추가 피해 재계산은 없습니다.</p>'
        if saved_damage else
        f'<p id="treatment-note">{NO_DAMAGE_LABEL}</p>'
        '<p>EX-089와 동일한 모델·정책·고정 대진에서 피해 예측 정보와 해당 설명을 제거한 탐색 평가입니다. '
        '기준선 EX-089는 6승 0무 26패 · 점수 18.75%입니다. 입력 길이와 경기 진행 변화도 포함하며 '
        '일반 성능 개선이나 동등성을 확정하지 않습니다.</p>' if treatment else
        '<p>공개 정보 보존과 현재 상태 교정을 함께 적용한 고정 대진 탐색 평가입니다. '
        'EX-083은 2GPU 23경기와 4GPU 9경기의 계승 구성입니다. 일반 성능이나 모델 크기만의 효과를 주장하지 않습니다.</p>')
    model_label = "MiniCPM5-2B-Jev" if saved_damage else "JEV v6"
    (output / "index.html").write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{experiment} · {model_label}</title>'
        '<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:35px auto;padding:0 20px}'
        'table{width:100%;border-collapse:collapse}td,th{padding:8px;text-align:left;border-bottom:1px solid #ccd}a{color:#165fa5}</style>'
        f'<h1>{experiment} · {model_label} 대 Abyssal</h1><p>{summary}</p>'
        + description +
        '<p>전체 입력·응답·선택·턴별 공개 로그는 폴더 이동 후 오프라인에서 열립니다. '
        '실제 경기에서 확인된 실패와 합성 표시 검사를 구분합니다.</p>'
        f'<p>실패 {result["failed"]} · 무효 {result["invalid"]} · 미실행 {result["unattempted"]}</p>'
        '<table><thead><tr><th>경기</th><th>대진</th><th>진영</th><th>결과</th><th>턴</th><th>열기</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table><p><a href="result.json">상세 결과</a> · '
        '<a href="comparison.json">공통 유효쌍 비교</a> · <a href="raw/events.jsonl">전체 원문 기록</a> · '
        '<a href="provenance.json">원본·변환기 연결</a></p></html>')
    write_json(output / "result.json", result)
    write_json(output / "comparison.json", compared)
    damage_provenance = _saved_damage_provenance(len(entries)) if saved_damage else {}
    write_json(output / "provenance.json", dict(experiment=experiment, source=str(source),
        source_files=originals, copied_files={name: "raw/" + name for name in originals},
        viewer_source=viewer_files, turn_parser=parser,
        source_manifest_viewer_files={name: value for name, value in manifest.get("source", {}).items()
                                      if name in viewer_files},
        planned=result["planned"], completed=result["completed"], decisions=sum(map(len, groups.values())),
        turn_rows=sum(data["turn_log"]["row_count"] for data in games), actual_http_bytes_preserved=True,
        public_log_source="events.jsonl: this model username's received battle protocol only",
        probability_scope="one complete Choice; original native probabilities unchanged",
        **treatment, **damage_provenance))
    seal(output)
    return verify_data(source, output)


def _saved_damage_provenance(decisions):
    from .damage_data import VERSION
    return dict(display_version=VERSION, damage=dict(
        source="input event → input_audit.path/sha256 → saved damage",
        saved_only=True, decisions=decisions, per_decision_local_scripts=True,
        recalculations=0, model_calls=0, battles=0, scenario_order="original calculations array"))


def _without_prose(log):
    clean = copy.deepcopy(log)
    for turn in clean["turns"]:
        for row in turn["rows"]:
            for field in ("text", "parsed", "parser_error"):
                row.pop(field, None)
    return clean


def verify_data(source, output):
    """Compare every original, decision, public row, coordinate and turn boundary."""
    source, output = Path(source), Path(output)
    events, groups = list(event_rows(source)), decision_groups(source)
    manifest = json.loads((source / "manifest.json").read_text())
    result = json.loads((source / "result.json").read_text())
    provenance = json.loads((output / "provenance.json").read_text())
    treatment = _treatment_metadata(manifest)
    if treatment and any(provenance.get(key) != value for key, value in treatment.items()):
        raise ValueError("exported treatment provenance differs")
    if treatment and f'id="treatment-note">{NO_DAMAGE_LABEL}</p>' not in (output / "index.html").read_text():
        raise ValueError("exported treatment notice differs")
    expected_paths = _raw_paths(source, events, result)
    if set(provenance["source_files"]) != set(expected_paths):
        raise ValueError("exported original coverage differs")
    for name in expected_paths:
        if not file_hash(source / name) == provenance["source_files"][name] == file_hash(output / "raw" / name):
            raise ValueError("exported originals differ: " + name)
    from .damage_data import input_events, verify_battle
    entries = input_events(events)
    if manifest["experiment_id"] == MINICPM_EXPERIMENT and any(
            provenance.get(key) != value for key, value in _saved_damage_provenance(len(entries)).items()):
        raise ValueError("exported saved-only damage provenance differs")
    decisions, row_count, damage_count, damage_decisions = 0, 0, 0, 0
    for outcome in result["outcomes"]:
        target = output / f"battle-{outcome['slot']}"
        data = json.loads((target / "decisions.json").read_text())
        expected = _battle_data(source, manifest, outcome, events, groups, text_renderer=lambda rows, actor: rows)
        if treatment and "damage_index" in data:
            raise ValueError("disabled damage prediction cannot have a scenario display index")
        if {key: value for key, value in data.items() if key not in ("turn_log", "damage_index")} != {
                key: value for key, value in expected.items() if key != "turn_log"}:
            raise ValueError("exported observation/request/response/selection originals differ")
        if _without_prose(data["turn_log"]) != expected["turn_log"]:
            raise ValueError("exported public turn rows or cutoffs differ")
        if json.loads((target / "turn-logs.json").read_text()) != data["turn_log"]:
            raise ValueError("exported turn-log JSON differs")
        embedded = re.search(r'<script type="application/json" id="viewer-data">(.*?)</script>',
                             (target / "index.html").read_text(), re.S)
        if embedded is None or json.loads(embedded.group(1)) != data:
            raise ValueError("embedded original JSON differs")
        rows = [row for turn in expected["turn_log"]["turns"] for row in turn["rows"]]
        if (target / "showdown.log").read_text() != raw_text(rows):
            raise ValueError("exported public server raw rows differ")
        decisions += len(data["decisions"])
        row_count += len(rows)
        if provenance.get("display_version") == "jev-damage-viewer-v1" and "damage_index" not in data:
            raise ValueError("damage edition is missing a battle's decision index")
        if "damage_index" in data:
            damage_count += verify_battle(source, target, data, entries)
            damage_decisions += len(data["decisions"])
    if decisions != result["decisions"] or decisions != provenance["decisions"]:
        raise ValueError("exported decision denominator differs")
    if row_count != provenance["turn_rows"]:
        raise ValueError("exported public-row denominator differs")
    verify_seal(output)
    return dict(passed=True, games=len(result["outcomes"]), decisions=decisions, public_rows=row_count,
        damage_decisions=damage_decisions, damage_calculations=damage_count,
        original_files_compared=len(expected_paths), all_originals_compared=True,
        all_public_rows_and_cutoffs_compared=True,
        source_seal=file_hash(source / "checksums.sha256"), export_seal=file_hash(output / "checksums.sha256"),
        **treatment)


def _synthetic_failure(data, index):
    value = copy.deepcopy(data)
    value["synthetic"] = True
    value["outcome"].update(completed=False, audit_passed=False, outcome="output_failure")
    value["outcome"].pop("turns", None)
    value["decisions"] = [value["decisions"][index]]
    decision = value["decisions"][0]
    if "damage_index" in value:
        value["damage_index"] = {decision["id"]: value["damage_index"][decision["id"]]}
    decision.update(selection=None, wire=None, automatic=False)
    decision["technical"].update(selection=None, wire=None, synthetic_failure="표시 검증 전용 · 실제 응답/성적 아님")
    log = value["turn_log"]
    cutoff = log["decision_cutoffs"][decision["id"]]
    for turn in log["turns"]:
        turn["rows"] = [row for row in turn["rows"]
                        if (row["sequence"], row["line_index"]) <= (cutoff["sequence"], cutoff["line_index"])]
        turn["decision_ids"] = [decision["id"]] if turn["turn"] == decision["turn"] else []
    log["turns"] = [turn for turn in log["turns"] if turn["turn"] <= decision["turn"]]
    log.update(status="interrupted", terminal=None, terminal_label="진행 중 중단",
               decision_cutoffs={decision["id"]: cutoff}, row_count=sum(len(turn["rows"]) for turn in log["turns"]))
    return value


def _assert_summary(page, decision):
    """Check stored opponent names, zero/unknown HP, absence and suppression in actual DOM."""
    payload = decision["request"] or decision["observation"]
    page.click("#state-tab")
    for index, mon in enumerate(payload["state"]["opponent_team"]):
        row = page.locator(f'[data-opponent-index="{index}"]')
        cells = row.locator("td").all_text_contents()
        if mon["species"] not in cells[0]:
            raise ValueError("offline opponent summary species differs")
        hp = mon.get("hp_percent")
        if isinstance(hp, (float, int)) and not isinstance(hp, bool) and mon.get("hp_precision") != "unknown":
            if "%" not in cells[1] or (hp == 0 and not cells[1].startswith("0%")):
                raise ValueError("offline public HP summary lost a known percentage")
        elif "미확인" not in cells[1]:
            raise ValueError("offline public HP summary invented a percentage")
        moves = mon.get("moves")
        for move in moves if isinstance(moves, list) else []:
            if isinstance(move, dict) and (move.get("name") or move.get("id")) not in cells[2]:
                raise ValueError("offline public move name missing")
        for field, column in (("ability", 3), ("baseAbility", 4), ("item", 5)):
            value = mon.get(field)
            if not isinstance(value, dict):
                continue
            if value.get("knowledge") == "confirmed_absent" and "확인된 부재" not in cells[column]:
                raise ValueError("offline confirmed absence missing")
            if value.get("knowledge") == "suppressed" or value.get("suppressed") is True:
                if "억제됨" not in cells[column]:
                    raise ValueError("offline ability suppression missing")
            elif value.get("name") and value["name"] not in cells[column]:
                raise ValueError("offline effect name missing")


def _assert_treatment(page, data):
    if data.get("input_profile") != NO_DAMAGE_PROFILE:
        return False
    if not page.locator("#treatment-note").is_visible() or page.locator("#treatment-note").inner_text() != NO_DAMAGE_LABEL:
        raise ValueError("offline damage/speed treatment notice differs")
    page.click("#damage-tab")
    if (page.locator("#damage-status").get_attribute("data-state") != "disabled"
            or NO_DAMAGE_LABEL not in page.locator("#damage-status").inner_text()):
        raise ValueError("disabled damage prediction displayed as missing or calculated")
    if not page.locator("#damage-summary-section").is_hidden() or not page.locator("#damage-loaded").is_hidden():
        raise ValueError("disabled damage prediction displayed a calculation section")
    if any(not button.is_disabled() for button in page.locator('[data-copy="damage"],[data-download="damage"]').all()):
        raise ValueError("disabled damage prediction offered calculated JSON")
    if page.evaluate("window.jevDamageView.value()") is not None:
        raise ValueError("disabled damage prediction loaded calculation data")
    return True


def verify_browser(output, resource_check=None):
    """Move once and inspect at most five representative screens, not every turn."""
    from playwright.sync_api import sync_playwright
    from .config import experiment as settings
    from .damage_browser import check_saved_screen
    from .resource import disk_bytes
    output = Path(output)
    verify_seal(output)
    provenance = json.loads((output / "provenance.json").read_text())
    experiment = provenance["experiment"]
    cfg = settings(experiment)
    saved_damage = experiment == MINICPM_EXPERIMENT
    treatment = {key: provenance[key] for key in ("input_profile", "treatment") if key in provenance}
    size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    measure = resource_check or (lambda *, extra_roots: disk_bytes(experiment, extra_roots=extra_roots))
    before = measure(extra_roots=(output,))
    if cfg.disk_limit_bytes is not None and before + size > cfg.disk_limit_bytes:
        raise ValueError("relocated viewer copy would exceed disk budget")
    free_before = shutil.disk_usage(tempfile.gettempdir()).free
    if size > free_before:
        raise OSError("insufficient physical free space for relocated viewer copy")
    samples, errors, treatment_screens = {}, [], 0
    damage_checks = []
    normal_damage_count = -1
    synthetic = False
    with tempfile.TemporaryDirectory(prefix=experiment.lower() + "-offline-") as temporary:
        moved = Path(temporary) / "moved"
        shutil.copytree(output, moved)
        for path in sorted(moved.glob("battle-*/decisions.json")):
            data = json.loads(path.read_text())
            if not data["decisions"] and not data["turn_log"]["terminal"]:
                samples.setdefault("failure", (path.parent, None))
            for index, decision in enumerate(data["decisions"]):
                if decision["selection"] and decision["wire"] and not decision["automatic"]:
                    samples.setdefault("normal", (path.parent, index))
                    # Exercise filters on the largest saved calculation within the existing normal screen.
                    if saved_damage:
                        count = data["damage_index"][decision["id"]]["calculations"]
                        if count > normal_damage_count:
                            samples["normal"] = (path.parent, index)
                            normal_damage_count = count
                if decision["automatic"]:
                    samples.setdefault("automatic", (path.parent, index))
                if not decision["selection"] and not decision["wire"]:
                    samples.setdefault("failure", (path.parent, index))
                payload = decision["request"] or decision["observation"]
                if any(not mon.get("active") and (isinstance(mon.get("moves"), list) and mon["moves"]
                        or isinstance(mon.get("item"), dict) and mon["item"].get("knowledge") == "confirmed_absent")
                        for mon in payload["state"]["opponent_team"]):
                    samples.setdefault("public_bench", (path.parent, index))
                cutoff = data["turn_log"]["decision_cutoffs"][decision["id"]]
                part = next(turn for turn in data["turn_log"]["turns"] if turn["turn"] == decision["turn"])
                if any((row["sequence"], row["line_index"]) > (cutoff["sequence"], cutoff["line_index"])
                       for row in part["rows"]):
                    samples.setdefault("turn_log", (path.parent, index))
        if "failure" not in samples and samples:
            folder, index = samples.get("normal", next(iter(samples.values())))
            data = _synthetic_failure(json.loads((folder / "decisions.json").read_text()), index)
            target = moved / "synthetic-failure"
            target.mkdir()
            for reference in data.get("damage_index", {}).values():
                destination = target / reference["src"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(folder / reference["src"], destination)
            (target / "index.html").write_text(render_data(data))
            write_json(target / "decisions.json", data)
            samples["failure"] = (target, 0)
            synthetic = True
        peak = measure(extra_roots=(output, Path(temporary)))
        if cfg.disk_limit_bytes is not None and peak > cfg.disk_limit_bytes:
            raise ValueError("relocated viewer copy exceeds disk budget")
        free_after_copy = shutil.disk_usage(temporary).free
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = browser.new_context(offline=True)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            for name, (folder, index) in samples.items():
                data = json.loads((folder / "decisions.json").read_text())
                loaded = []
                def received(request):
                    if "/damage/decision-" in request.url:
                        loaded.append(request.url)
                page.on("request", received)
                page.goto((folder / "index.html").as_uri(), wait_until="domcontentloaded")
                decision = data["decisions"][index] if index is not None else None
                if decision:
                    page.select_option("#decision", str(index))
                    if json.loads(page.locator("#request-json").inner_text()) != (decision["request"] or decision["observation"]):
                        raise ValueError("offline visible request differs")
                    if decision["response"] is not None and json.loads(page.locator("#response-json").inner_text()) != decision["response"]:
                        raise ValueError("offline visible response differs")
                    _assert_summary(page, decision)
                metrics = page.locator("#metrics").inner_text()
                if name == "automatic" and ("API 미호출" not in metrics or "전송 요청이 아닙니다" not in page.locator("#request-note").inner_text()):
                    raise ValueError("automatic selection displayed as a model call")
                if name == "failure" and ("전송: 없음" not in metrics or "실패" not in page.locator("#heading").inner_text()):
                    raise ValueError("failed selection incorrectly displayed")
                if name == "failure" and not data["turn_log"]["terminal"] and "진행 중 중단" not in page.locator("#game-summary").inner_text():
                    raise ValueError("nonterminal failure not shown as interrupted")
                if saved_damage:
                    if loaded:
                        raise ValueError("saved damage loaded before opening its tab")
                    checked = check_saved_screen(page, folder, data, index, Path(temporary), filters=name == "normal")
                    if index is not None and len(loaded) != 1:
                        raise ValueError("saved damage did not load exactly the selected decision")
                    damage_checks.append(dict(screen=name, synthetic=bool(data.get("synthetic")), **checked))
                if name == "turn_log":
                    _check_turn_screen(page, data, decision, Path(temporary))
                treatment_screens += int(_assert_treatment(page, data))
                page.remove_listener("request", received)
            context.close()
            browser.close()
        if errors:
            raise ValueError("offline browser errors: " + repr(errors))
        after_browser = measure(extra_roots=(output, Path(temporary)))
        peak = max(peak, after_browser)
        if cfg.disk_limit_bytes is not None and peak > cfg.disk_limit_bytes:
            raise ValueError("relocated viewer browser artifacts exceed disk budget")
        free_after_browser = shutil.disk_usage(temporary).free
    required = {"normal", "automatic", "failure", "public_bench", "turn_log"}
    missing = sorted(required - set(samples))
    return dict(passed=True, offline_relocated=True, representative_screens=list(samples),
        unavailable_screens=missing, synthetic_failure_fixture=synthetic, browser_errors=errors,
        scope="available representative screens only; missing categories are not fabricated",
        full_browser_replay=False, relocated_copy_bytes=size, disk_bytes_with_temporary_copy=peak,
        disk_bytes_before_copy=before, disk_limit_bytes=cfg.disk_limit_bytes,
        temporary_filesystem_free_bytes_before_copy=free_before,
        temporary_filesystem_free_bytes_after_copy=free_after_copy,
        temporary_filesystem_free_bytes_after_browser=free_after_browser,
        damage_screens_checked=len(damage_checks), saved_damage_checks=damage_checks,
        treatment_screens_checked=treatment_screens, **treatment)


def _check_turn_screen(page, data, decision, temporary):
    log, turn = data["turn_log"], decision["turn"]
    page.click("#turn-log-tab")
    page.locator("#raw-turn-details").evaluate("element => element.open = true")
    for until in (False, True):
        page.locator("#until-decision").set_checked(until)
        expected = raw_text(rows_for(log, turn, decision_id=decision["id"], until_decision=until))
        if page.locator("#turn-raw").text_content() != expected:
            raise ValueError("offline turn raw scope differs from exact row cutoff")
        if until and page.locator("#turn-after").count():
            raise ValueError("future decision results visible in cutoff scope")
        page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true,value:{writeText:async text=>{window.copiedTurnRaw=text}}})")
        page.click('[data-copy="turn-raw"]')
        if page.evaluate("window.copiedTurnRaw") != expected:
            raise ValueError("copied turn raw differs from visible scope")
        with page.expect_download() as pending:
            page.click('[data-download="turn-raw"]')
        download = pending.value
        saved = temporary / download.suggested_filename
        download.save_as(saved)
        if saved.read_text() != expected:
            raise ValueError("downloaded turn raw differs from visible scope")
    same = [i for i, item in enumerate(data["decisions"]) if item["turn"] == turn]
    page.select_option("#turn", str(next(i for i, part in enumerate(log["turns"]) if part["turn"] == turn)))
    if page.locator("#decision").input_value() != str(same[0]):
        raise ValueError("turn selection did not choose first decision")
    if len(same) > 1:
        page.select_option("#decision", str(same[1]))
        if page.locator("#turn").input_value() != str(next(i for i, part in enumerate(log["turns"]) if part["turn"] == turn)):
            raise ValueError("same-turn decision disconnected from turn selection")
    empty = next((i for i, part in enumerate(log["turns"]) if not part["decision_ids"]), None)
    if empty is not None:
        page.select_option("#turn", str(empty))
        if page.locator("#decision").input_value() or not page.locator("#until-decision").is_disabled():
            raise ValueError("turn without decisions retained another turn's decision")
        if page.locator("#turn-raw").text_content() != raw_text(log["turns"][empty]["rows"]):
            raise ValueError("turn without decisions lost its public rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify-browser",))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    write_json(args.receipt, verify_browser(args.output))
