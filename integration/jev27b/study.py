"""Frozen EX-058 schedule, EX-082 accounting, and portable result artifacts."""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
import time

from integration.pokechamp import jev_battle as j, jev_v4

ROOT = j.ROOT
BASELINE = ROOT / ".pokechamp-data/jev/ex058-live"
LIVE = ROOT / ".pokechamp-data/jev/ex082-live"
EVIDENCE = ROOT / "project_context/exec-plans/evidence/ep134"
EXPORT = ROOT / "exports/battle_viewers/ex082"
PROFILE = "jev27b-ex058-reproduction-v1"
POINTS = {"player_won": 1.0, "tied": 0.5, "player_lost": 0.0}


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".writing")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def seal(directory):
    directory = Path(directory)
    files = sorted(p for p in directory.rglob("*")
                   if p.is_file() and p != directory / "checksums.sha256")
    (directory / "checksums.sha256").write_text("".join(
        f"{file_hash(p)}  {p.relative_to(directory)}\n" for p in files))


def verify_seal(directory):
    directory = Path(directory)
    result = {}
    for line in (directory / "checksums.sha256").read_text().splitlines():
        checksum, name = line.split("  ", 1)
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or name in result:
            raise ValueError("invalid sealed path")
        if file_hash(path) != checksum:
            raise ValueError("source seal mismatch: " + name)
        result[name] = checksum
    return result


def load_baseline(*, full_seal=False):
    from integration.pokechamp.jev_study import validate_schedule
    seals = (verify_seal(BASELINE) if full_seal else
             {name: checksum for checksum, name in (
                 line.split("  ", 1) for line in
                 (BASELINE / "checksums.sha256").read_text().splitlines())})
    if seals.get("manifest.json") != file_hash(BASELINE / "manifest.json"):
        raise ValueError("EX-058 manifest seal mismatch")
    manifest = json.loads((BASELINE / "manifest.json").read_text())
    if manifest["experiment_id"] != "EX-058" or manifest["schema_version"] != "jev-choice-v4":
        raise ValueError("wrong reproduction baseline")
    validate_schedule(manifest["schedule"])
    if j.digest(manifest["schedule"]) != manifest["schedule_sha256"]:
        raise ValueError("EX-058 schedule hash mismatch")
    for team in manifest["teams"].values():
        if hashlib.sha256(team["showdown_team"].encode()).hexdigest() != team["sha256"]:
            raise ValueError("EX-058 team text hash mismatch")
        if file_hash(ROOT / team["source"]) != team["sha256"]:
            raise ValueError("EX-058 original team file changed")
    if manifest["prompt"] != j.PROMPT.with_name("jev-choice-v4.txt").read_text():
        raise ValueError("EX-058 prompt changed")
    if manifest["input_data_identity"] != jev_v4.data_identity():
        raise ValueError("EX-058 calculator, role, or fixed set data changed")
    return manifest


def source_identity():
    source = j.source_identity()
    files = sorted(p for p in Path(__file__).parent.rglob("*")
                   if p.is_file() and p.suffix in (".py", ".json", ".txt"))
    launcher = ROOT / "scripts/jev27b"
    if launcher.is_file():
        files.append(launcher)
    source.update({str(p.relative_to(ROOT)): file_hash(p) for p in files})
    return source


def snapshot_sources(directory, sources):
    for name, expected in sources.items():
        path = ROOT / name
        if file_hash(path) != expected:
            raise ValueError("source changed during freeze: " + name)
        target = Path(directory) / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def validate_gate_receipt(receipt, *, expected_identity, sources, baseline):
    required = ("passed", "cpu_passed", "length_passed", "reload_passed", "preflight_passed")
    if not isinstance(receipt, dict) or any(receipt.get(key) is not True for key in required):
        raise ValueError("CPU, token length, reload, and single preflight gates are required")
    expected = dict(serving_identity=expected_identity, source=sources,
        input_data_identity=baseline["input_data_identity"],
        baseline_manifest_sha256=file_hash(BASELINE / "manifest.json"))
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ValueError("gate receipt identity mismatch: " + key)
    journal = receipt.get("server_journal")
    if not isinstance(journal, str) or not Path(journal).is_file():
        raise ValueError("the serving process request journal is required")


def prepare_manifest(expected_identity, gate_receipt, *, endpoint):
    from .battle import MODEL, REVISION, RETRY_DELAYS, TIMEOUT, TRANSPORT_POLICY
    from .client import base_url
    from integration.pokechamp import cli
    baseline = load_baseline(full_seal=True)
    sources = source_identity()
    validate_gate_receipt(gate_receipt, expected_identity=expected_identity,
                          sources=sources, baseline=baseline)
    return dict(experiment_id="EX-082", execution_profile=PROFILE,
        version=jev_v4.VERSION, schema_version=jev_v4.VERSION,
        validation_version=j.VALIDATION_VERSION, initial_pp_policy=j.INITIAL_PP_POLICY,
        effect_reference_identity=j.effects.identity(), input_data_identity=jev_v4.data_identity(),
        schedule=copy.deepcopy(baseline["schedule"]), teams=copy.deepcopy(baseline["teams"]),
        schedule_sha256=baseline["schedule_sha256"],
        schedule_origin=dict(experiment="EX-058", path=str((BASELINE / "manifest.json").relative_to(ROOT)),
                             sha256=file_hash(BASELINE / "manifest.json")),
        model=dict(model=MODEL, revision=REVISION, endpoint=base_url(endpoint) + "/v1/systemone",
                   serving_identity=expected_identity),
        server_journal=str(Path(gate_receipt["server_journal"]).resolve()),
        prompt=baseline["prompt"], source=sources, fake=False, timer_enabled=False,
        transport_policy=TRANSPORT_POLICY, provider_retries=3,
        retry_delays_seconds=list(RETRY_DELAYS),
        limits=dict(games=32, calls=None, collection_seconds=None, total_seconds=None,
                    stage_seconds=None, battle_seconds=None, concurrency=1,
                    inference_concurrency=1, request_timeout_seconds=TIMEOUT,
                    input_tokens=32768, retries=3, recollection=0),
        submodules={name: dict(sha=config["sha"]) for name, config in cli.SUBMODULES.items()},
        observation_build=baseline["observation_build"], gate_receipt_sha256=j.digest(gate_receipt),
        rng_isolation="separate-processes", created_at=time.time(), efficacy_evidence=False,
        interpretation="local-public-JEV27B-vs-historical-cloud-JEV-fixed-matchups")


def verify_live_identity(manifest):
    if manifest["source"] != source_identity():
        raise ValueError("source changed during collection")
    if manifest["input_data_identity"] != jev_v4.data_identity():
        raise ValueError("input data changed during collection")
    baseline = load_baseline()
    if manifest["schedule"] != baseline["schedule"] or manifest["teams"] != baseline["teams"]:
        raise ValueError("frozen schedule or teams changed")
    if manifest["observation_build"] != baseline["observation_build"]:
        raise ValueError("observation build differs from EX-058")


def summarize(session, outcomes, schedule, error=None):
    records = session.records
    inputs = {e["decision"]: e for e in records if e["type"] == "input"}
    selections = {e["decision"]: e for e in records if e["type"] == "selection"}
    responses = [e for e in records if e["type"] == "response"]
    transports = [e for e in records if e["type"] == "transport"]
    wires = [e for e in records if e["type"] == "wire"]
    failures = [e for e in records if e["type"] == "attempt_failure"]
    raw = [e for e in records if e["type"] == "http_response"]
    valid = [o for o in outcomes if o.get("completed") and o.get("audit_passed") and not o.get("error")]
    pair_members = {}
    for outcome in valid:
        pair_members.setdefault(outcome["paired_slot_id"], []).append(outcome)
    pairs = {key: sum(POINTS[o["outcome"]] for o in pair) / 2
             for key, pair in pair_members.items()
             if len(pair) == 2 and {o["jev_actor"] for o in pair} == {"p1", "p2"}}

    def score(items):
        return dict(games=len(items), wins=sum(o["outcome"] == "player_won" for o in items),
            draws=sum(o["outcome"] == "tied" for o in items),
            losses=sum(o["outcome"] == "player_lost" for o in items),
            score=sum(POINTS[o["outcome"]] for o in items) / len(items) if items else None)

    def usage(event):
        value = event["body"].get("usage")
        return value if isinstance(value, dict) else {}

    received_usage = {key: sum(usage(e).get(key, 0) for e in responses)
                      for key in ("input_tokens", "output_tokens")}
    missing_usage = sum(not isinstance(e["body"].get("usage"), dict) or any(
        key not in e["body"]["usage"] for key in received_usage) for e in responses)
    logical = {e["decision"] for e in transports}
    successful = {e["decision"] for e in responses}
    failed_decisions = {e["decision"] for e in failures}
    # Cached transport retries are not new model usage. Only missing logical
    # results/usage make the model token total unknown.
    unknown_usage = len(logical - successful) + missing_usage
    action_audit = all(w["decision"] in selections and w["decision"] in inputs
        and selections[w["decision"]]["command"] == w["command"]
        == inputs[w["decision"]]["commands"][selections[w["decision"]]["choice"]]
        for w in wires)
    result = dict(planned=len(schedule), attempted=len(outcomes), completed=len(valid),
        failed=sum(not o.get("completed") for o in outcomes),
        invalid=sum(o.get("completed", False) and (not o.get("audit_passed") or bool(o.get("error"))) for o in outcomes),
        unattempted=len(schedule) - len(outcomes), outcomes=outcomes,
        requests=session.calls, external_requests=0, local_http_requests=session.calls,
        logical_requests=len(logical), received_responses=len(responses),
        unanswered_requests=len(logical - successful),
        sent_actions=len(wires), automatic_actions=sum(e["automatic"] for e in selections.values()),
        action_audit_passed=action_audit, received_usage=received_usage,
        tokens=None if unknown_usage else received_usage,
        missing_usage_responses=missing_usage, usage_unknown_requests=unknown_usage,
        retry_attempts=len(transports) - len(logical), http_responses=len(raw),
        http_errors=sum(e["status_code"] >= 400 for e in raw),
        http_no_response=len(transports) - len(raw),
        provider_failed_attempts=len(failures), recovered_requests=len(failed_decisions & successful),
        exhausted_requests=sum(e["attempt"] == 4 and e.get("retryable", False) for e in failures),
        actual_models=sorted({e["body"].get("model", "missing") for e in responses}),
        latency_seconds=[e["elapsed_seconds"] for e in responses],
        http_latency_seconds=[e["elapsed_seconds"] for e in raw],
        input_generation_seconds=[e["input_generation_seconds"] for e in inputs.values()],
        input_tokens=[usage(e)["input_tokens"] for e in responses if "input_tokens" in usage(e)],
        elapsed_collection_seconds=(time.monotonic() - session.monotonic_started
                                    if session.monotonic_started is not None else 0),
        first_request_at=session.started, collection_deadline=None, cleanup_deadline=None,
        completed_pairs=len(pairs), pair_scores=pairs,
        mean_pair_score=sum(pairs.values()) / len(pairs) if pairs else None,
        overall=score(valid),
        by_block={key: score([o for o in valid if o["block_id"] == key])
                  for key in sorted({r["block_id"] for r in schedule})},
        by_actor={actor: score([o for o in valid if o["jev_actor"] == actor]) for actor in ("p1", "p2")},
        judgment_diagnostics=[e for e in records if e["type"] == "judgment_diagnostics" and e["diagnostics"]],
        error=error, efficacy_evidence=False, explanation_review="미평가(기본 제외)")
    result.update(actual_wins=result["overall"]["wins"], actual_draws=result["overall"]["draws"],
                  actual_losses=result["overall"]["losses"])
    result["passed"] = (len(valid) == len(schedule) == 32 and len(pairs) == 16
        and not error and action_audit and len(wires) == len(inputs)
        and len(transports) == session.calls)
    return result


def event_rows(directory):
    with (Path(directory) / "events.jsonl").open() as stream:
        for line in stream:
            yield json.loads(line)


def compare_data(before, after):
    """Paired descriptive scores, allowing only the declared local model change."""
    from integration.pokechamp.jev_comparison import match_metrics
    bm, br, be = before
    nm, nr, ne = after
    if (bm["experiment_id"], nm["experiment_id"]) != ("EX-058", "EX-082"):
        raise ValueError("wrong comparison identities")
    for key in ("schema_version", "schedule", "teams", "prompt", "input_data_identity"):
        if bm[key] != nm[key]:
            raise ValueError("EX-058 comparison treatment drift: " + key)
    if bm["schema_version"] != "jev-choice-v4":
        raise ValueError("wrong comparison input version")
    old = {o["slot_id"]: o for o in br["outcomes"]}
    new = {o["slot_id"]: o for o in nr["outcomes"]}
    if len(old) != len(br["outcomes"]) or len(new) != len(nr["outcomes"]):
        raise ValueError("duplicate comparison slot")
    rows, pairs = [], {}
    for row in bm["schedule"]:
        slot = row["slot_id"]
        a, b = match_metrics(old.get(slot), be), match_metrics(new.get(slot), ne)
        for metrics, outcome in ((a, old.get(slot)), (b, new.get(slot))):
            if outcome and outcome.get("error"):
                metrics.update(valid=False, score=None)
        common = a["valid"] and b["valid"]
        # A completed battle with a technical error remains invalid even if an
        # earlier audit succeeded before the error was found.
        common = common and not (old.get(slot, {}).get("error") or new.get(slot, {}).get("error"))
        item = dict(slot_id=slot, paired_slot_id=row["paired_slot_id"], before=a, after=b,
            comparable=common, score_delta=b["score"] - a["score"] if common else None)
        rows.append(item)
        pairs.setdefault(row["paired_slot_id"], []).append(item)
    deltas = {key: sum(row["score_delta"] for row in pair) / 2 for key, pair in pairs.items()
              if len(pair) == 2 and all(row["comparable"] for row in pair)}
    return dict(before_experiment="EX-058", after_experiment="EX-082",
        requested_model_before=bm["model"], requested_model_after=nm["model"],
        actual_models_before=br["actual_models"], actual_models_after=nr["actual_models"],
        planned_games=len(rows), comparable_games=sum(row["comparable"] for row in rows),
        planned_pairs=len(pairs), common_completed_pairs=len(deltas),
        missing_common_pairs=sorted(set(pairs) - set(deltas)), pair_deltas=deltas,
        mean_pair_score_delta=sum(deltas.values()) / len(deltas) if deltas else None,
        matches=rows, causal_evidence=False, pooled_64_game_score=False,
        token_counts_use_different_tokenizers=True,
        interpretation="로컬 공개 JEV-27B와 과거 클라우드 JEV의 고정 대진 탐색 비교")


def comparison(source):
    source = Path(source)
    verify_seal(BASELINE)
    verify_seal(source)
    after_result = json.loads((source / "result.json").read_text())
    if after_result.get("final_audit_passed") is not True:
        raise ValueError("comparison requires a successful final technical audit")
    return compare_data((load_baseline(), json.loads((BASELINE / "result.json").read_text()), list(event_rows(BASELINE))),
        (json.loads((source / "manifest.json").read_text()),
         after_result, list(event_rows(source))))


def decision_groups(source):
    """Build the existing JEV renderer's schema from actual HTTP body records."""
    groups = {}
    for event in event_rows(source):
        if event.get("decision"):
            groups.setdefault(event["decision"], []).append(event)
    battles = {}
    for decision, events in groups.items():
        by_type = {event["type"]: event for event in events}
        if "input" not in by_type:
            raise ValueError("transport without an input record")
        entry = by_type["input"]
        request = by_type.get("http_request")
        response = by_type.get("response")
        selection = by_type.get("selection")
        automatic = bool(selection and selection["automatic"])
        if automatic and (request or response):
            raise ValueError("automatic selection has a model request")
        item = dict(id=decision, turn=entry["payload"]["state"]["turn"],
            kind=entry["payload"]["state"]["decision_kind"], automatic=automatic,
            request=request["body"] if request else None,
            observation=None if request else entry["payload"],
            response=response["body"] if response else None, selection=selection,
            wire=by_type.get("wire"), elapsed=response["elapsed_seconds"] if response else None,
            diagnostics=by_type.get("judgment_diagnostics", {}).get("diagnostics", []),
            technical=dict(input_boundary=entry["boundary"],
                observation_identity=entry["observation_identity"], transport=by_type.get("transport"),
                http_response=by_type.get("http_response"), selection=selection,
                wire=by_type.get("wire"), http_attempt_history=[e for e in events if e["type"] in
                    ("transport", "http_request", "http_response", "local_transport",
                     "attempt_failure", "provider_retry", "request_cancelled")]))
        battles.setdefault(decision.split("-")[0], []).append(item)
    return battles


def export(source, output=EXPORT, *, compared=None):
    from integration.pokechamp.observability.render import _replay_html
    source, output = Path(source), Path(output)
    verify_seal(source)
    manifest = json.loads((source / "manifest.json").read_text())
    result = json.loads((source / "result.json").read_text())
    if manifest["experiment_id"] != "EX-082":
        raise ValueError("wrong EX-082 export source")
    groups = decision_groups(source)
    protocols = {}
    for event in event_rows(source):
        if event["type"] == "protocol":
            protocols.setdefault(event["username"], []).extend(line for line in
                event["protocol"].splitlines() if line.startswith("|")
                and not line.startswith(("|request|", "|sentchoice|")))
    assets = ROOT / "integration/pokechamp/viewer_assets"
    template = (assets / "jev-researcher.html").read_text().replace(
        "__ACTION_LABELS__", (assets / "action-labels.js").read_text())
    template = template.replace('href="../decisions.html"', 'href="decisions.json"')
    template = template.replace("(data.outcome.outcome==='player_won'?'승리':'패배')",
        "({player_won:'승리',player_lost:'패배',tied:'무승부',output_failure:'모델 선택 실패'}[data.outcome.outcome]||'기술 실패')")
    template = template.replace("function stateView(d,p)",
        "function displayEffect(v){return typeof v==='object'&&v!==null?(v.name||v.id||'미확인'):v;}\nfunction stateView(d,p)")
    template = template.replace("m.ability,m.item", "displayEffect(m.ability),displayEffect(m.item)")
    template = template.replace("기록된 요청 모델과 payload를 합친 전송 JSON 객체입니다. HTTP 바이트 원문이 아닌 기록 기반 복원이며 값은 변경하지 않았습니다.",
        "기록된 실제 HTTP 요청 JSON입니다. 기술 기록에 요청 바이트·request ID·본문 해시와 재시도를 보존했습니다.")
    output.mkdir(parents=True, exist_ok=False)
    matches, table = [], []
    labels = dict(player_won="승리", player_lost="패배", tied="무승부", output_failure="모델 선택 실패")
    for outcome in result["outcomes"]:
        slot, user = outcome["slot"], outcome["username"]
        target = output / f"battle-{slot}"
        target.mkdir()
        protocol = "\n".join(protocols.get(user, [])) + "\n"
        (target / "showdown.log").write_text(protocol)
        replay = _replay_html(dict(battle_id=f"ex082-battle-{slot}", teams=[]), protocol)
        replay = replay.replace("Static protocol fallback", "오프라인 경기 로그")
        (target / "replay.html").write_text(replay)
        decisions = groups.get(user, [])
        data = dict(experiment="EX-082", slot=slot, username=user, outcome=outcome, decisions=decisions)
        write_json(target / "decisions.json", data)
        if decisions:
            encoded = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
            page = template.replace("__TITLE__", f"EX-082 · {slot}경기 · JEV-27B")
            page = page.replace("__DATA__", encoded)
        else:
            page = ('<!doctype html><html lang="ko"><meta charset="utf-8">'
                    '<p>입력 수집 전 종료된 경기입니다.</p><a href="replay.html">보존된 경기 로그</a>'
                    "<pre>" + html.escape(json.dumps(outcome, ensure_ascii=False, indent=2)) + "</pre></html>")
        (target / "index.html").write_text(page)
        label = labels.get(outcome.get("outcome"), "기술 실패")
        if outcome.get("completed") and not outcome.get("audit_passed"):
            label += " · 유효성 미충족"
        if result.get("final_audit_passed") is False:
            label += " · 최종 유효성 미확정"
        table.append(f'<tr><td>{slot}</td><td>{html.escape(outcome["slot_id"])}</td>'
            f'<td>{" / ".join(outcome["teams"])}</td><td>{outcome["jev_actor"]}</td><td>{label}</td>'
            f'<td>{outcome.get("turns", "—")}</td><td><a href="battle-{slot}/index.html">입력·응답·리플레이</a></td></tr>')
        matches.append(dict(slot=slot, slot_id=outcome["slot_id"], decisions=len(decisions),
                            protocol_sha256=file_hash(target / "showdown.log")))
    summary = (f'유효 {result["completed"]}/{result["planned"]} · JEV-27B {result["actual_wins"]}승 '
               f'{result["actual_draws"]}무 {result["actual_losses"]}패 · 완료쌍 {result["completed_pairs"]}/16')
    if result.get("final_audit_passed") is False:
        summary = "최종 기술 감사 실패 · 성적 확정 보류. 아래는 보존된 경기별 기록입니다."
    write_json(output / "result.json", result)
    if compared is not None:
        write_json(output / "comparison.json", compared)
    (output / "index.html").write_text('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>EX-082 · JEV-27B</title>'
        '<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px;line-height:1.7}'
        'table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #ccc}'
        '.scroll{overflow:auto}a{color:#165fa5}</style><a href="../index.html">← 실험 목록</a>'
        f'<h1>EX-082 · JEV-27B 대 Abyssal</h1><p>{summary}</p>'
        '<p>추가 학습 없는 로컬 공개 JEV-27B와 과거 클라우드 JEV(EX-058)의 고정 대진 탐색 비교입니다. '
        '모델·토크나이저·서빙이 다르며 일반 성능 우위를 입증하지 않습니다.</p>'
        '<p>입력·응답·선택·경기 로그는 폴더 이동 후 오프라인으로 열립니다. 애니메이션에는 인터넷 연결이 필요합니다.</p>'
        f'<p>실패 {result["failed"]} · 무효 {result["invalid"]} · 미실행 {result["unattempted"]}</p>'
        '<div class="scroll"><table><thead><tr><th>경기</th><th>대진</th><th>p1 / p2 팀</th>'
        '<th>JEV 진영</th><th>결과</th><th>턴</th><th>열기</th></tr></thead><tbody>'
        + "".join(table) + '</tbody></table></div><p><a href="result.json">상세 결과</a>'
        + (' · <a href="comparison.json">공통 완료쌍 비교</a>' if compared is not None else "") + "</p></html>")
    (output / "README.md").write_text("# EX-082 JEV-27B 뷰어\n\n폴더 전체를 이동한 뒤 index.html을 여세요.\n"
        "입력·응답·선택·공개 로그는 오프라인에서 열립니다. 애니메이션에는 인터넷 연결이 필요합니다.\n"
        f"원자료: {source}\n원자료의 봉인과 이 열람용 복사본은 별도입니다.\n")
    write_json(output / "provenance.json", dict(experiment="EX-082", source=str(source),
        source_files={name: file_hash(source / name) for name in
                      ("manifest.json", "events.jsonl", "result.json", "checksums.sha256")},
        planned=result["planned"], completed=result["completed"], matches=matches,
        renderer_sha256=file_hash(Path(__file__)),
        template_sha256=file_hash(assets / "jev-researcher.html"),
        action_labels_sha256=file_hash(assets / "action-labels.js"),
        request_provenance="recorded actual HTTP request JSON; original bytes and hash in technical history"))
    seal(output)
    return dict(passed=True, matches=len(matches), decisions=sum(len(v) for v in groups.values()),
                source_seal=file_hash(source / "checksums.sha256"),
                export_seal=file_hash(output / "checksums.sha256"), summary=summary)


def verify_viewer(source, output):
    """Independently compare every embedded request/response/selection to raw events."""
    source, output = Path(source), Path(output)
    verify_seal(source)
    verify_seal(output)
    groups = decision_groups(source)
    result = json.loads((source / "result.json").read_text())
    checked = 0
    for outcome in result["outcomes"]:
        target = output / f"battle-{outcome['slot']}"
        data = json.loads((target / "decisions.json").read_text())
        expected = groups.get(outcome["username"], [])
        if data["decisions"] != expected or data["outcome"] != outcome:
            raise ValueError("viewer differs from source events")
        if expected:
            page = (target / "index.html").read_text()
            match = re.search(r'<script type="application/json" id="viewer-data">(.*?)</script>', page, re.S)
            if match is None or json.loads(match.group(1)) != data:
                raise ValueError("embedded viewer data differs")
        checked += len(expected)
    return dict(passed=True, decisions_checked=checked, raw_json_exact=True,
                source_seal_valid=True, export_seal_valid=True)


def verify_browser(output):
    """Relocate the whole export and check every visible JSON decision offline."""
    from playwright.sync_api import sync_playwright
    output = Path(output)
    verify_seal(output)
    result = json.loads((output / "result.json").read_text())
    errors, checked = [], 0
    with tempfile.TemporaryDirectory(prefix="ex082-offline-") as temporary:
        relocated = Path(temporary) / "moved-viewer"
        shutil.copytree(output, relocated)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(offline=True)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto((relocated / "index.html").as_uri(), wait_until="domcontentloaded")
            for outcome in result["outcomes"]:
                target = relocated / f"battle-{outcome['slot']}"
                data = json.loads((target / "decisions.json").read_text())
                page.goto((target / "index.html").as_uri(), wait_until="domcontentloaded")
                for index, decision in enumerate(data["decisions"]):
                    page.select_option("#decision", str(index))
                    displayed = json.loads(page.locator("#request-json").inner_text())
                    if displayed != (decision["request"] or decision["observation"]):
                        raise ValueError("displayed request JSON differs")
                    if decision["response"] is not None:
                        if json.loads(page.locator("#response-json").inner_text()) != decision["response"]:
                            raise ValueError("displayed response JSON differs")
                    checked += 1
            context.close()
            browser.close()
    if errors:
        raise ValueError("offline viewer browser errors: " + repr(errors))
    return dict(passed=True, offline_relocated=True, displayed_json_checked=checked,
                browser_errors=errors, external_requests=0)


def finalize(source=LIVE, output=EXPORT, *, evidence=EVIDENCE, browser=False):
    from .audit import audit
    source, output, evidence = Path(source), Path(output), Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    checked = audit(source)
    write_json(evidence / "live-audit.json", checked)
    result = json.loads((source / "result.json").read_text())
    compared = (comparison(source) if checked["passed"] and result.get("final_audit_passed") is True
                else dict(available=False, reason="최종 기술 감사 미통과로 성적 비교 보류"))
    write_json(evidence / "comparison.json", compared)
    exported = export(source, output, compared=compared)
    verified = verify_viewer(source, output)
    write_json(evidence / "viewer-verification.json", verified)
    browser_result = verify_browser(output) if browser else None
    if browser_result is not None:
        write_json(evidence / "viewer-browser.json", browser_result)
    return dict(audit=checked, comparison=compared, export=exported,
                viewer=verified, browser=browser_result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("finalize", "verify-viewer", "verify-browser", "compare"))
    parser.add_argument("--source", type=Path, default=LIVE)
    parser.add_argument("--output", type=Path, default=EXPORT)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    if args.command == "finalize":
        result = finalize(args.source, args.output, evidence=args.evidence)
    elif args.command == "verify-viewer":
        result = verify_viewer(args.source, args.output)
    elif args.command == "verify-browser":
        result = verify_browser(args.output)
        write_json(args.evidence / "viewer-browser.json", result)
    else:
        result = comparison(args.source)
        write_json(args.evidence / "comparison.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
