"""EX-060의 분모·조건부 행동 가치·오프라인 열람 자료를 생성한다."""
from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any


TERMINAL = {"win", "draw", "loss"}
STATUSES = TERMINAL | {"censored", "error", "aborted"}
SCORES = {"win": 1.0, "draw": 0.5, "loss": 0.0}
LIMITATION = (
    "원경기의 숨은 서버 상태와 양측 Abyssal 후속 정책에 조건부인 추정값입니다. "
    "최적 정책·JEV 승률·일반 Gen9 OU 성능을 나타내지 않습니다. "
    "후보 값의 합은 1이 아니며 최고 표본평균을 확정 최선으로 판정하지 않습니다. "
    "기존 Abyssal의 일반 경로 테라 미사용 한계를 유지합니다. "
    "이 대진은 개발 자료이며 독립 평가 holdout에서 제외합니다."
)


def _positive_integer(value: Any, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _attempt_id(value: Any) -> str:
    if (type(value) is int and value > 0) or (isinstance(value, str) and value):
        return str(value)
    raise ValueError("missing or invalid attempt_id")


def wilson_interval(wins: int, total: int) -> list[float]:
    """승리 지시변수의 양측 Wilson 95% 구간; 점수 q의 구간은 아니다."""
    if type(wins) is not int or not 0 <= wins <= total or total <= 0:
        raise ValueError("invalid Wilson counts")
    z = 1.959963984540054
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def _validate_anchors(anchors: list[dict]) -> dict[str, dict]:
    result = {}
    for anchor in anchors:
        key = anchor.get("anchor_id")
        if not isinstance(key, str) or not key or key in result:
            raise ValueError("missing or duplicate anchor_id")
        actions = anchor.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError(f"empty actions: {key}")
        action_ids = [a.get("action_id") for a in actions]
        if any(not isinstance(a, str) or not a for a in action_ids) or len(set(action_ids)) != len(action_ids):
            raise ValueError(f"missing or duplicate action_id: {key}")
        if anchor.get("original_action_id") not in action_ids:
            raise ValueError(f"original action absent: {key}")
        result[key] = anchor
    return result


def _resolve_attempts(anchors: dict[str, dict], rollouts: list[dict], repetitions: int):
    latest, attempts, superseded = {}, {}, []
    candidates = {key: {a["action_id"] for a in value["actions"]} for key, value in anchors.items()}
    for row in rollouts:
        anchor, action, replicate = row.get("anchor_id"), row.get("action_id"), row.get("replicate")
        if anchor not in candidates or action not in candidates[anchor]:
            raise ValueError("rollout references unknown anchor/action")
        if type(replicate) is not int or not 0 <= replicate < repetitions:
            raise ValueError("replicate outside declared range")
        if row.get("status") not in STATUSES:
            raise ValueError("unknown rollout status")
        attempt_id = _attempt_id(row.get("attempt_id"))
        if attempt_id in attempts:
            raise ValueError("duplicate attempt_id")
        key = (anchor, action, replicate)
        previous = latest.get(key)
        replacement = row.get("supersedes_attempt_id")
        replacement = _attempt_id(replacement) if replacement is not None else None
        if previous is not None:
            if replacement != previous["attempt_id"]:
                raise ValueError("duplicate rollout requires explicit supersedes_attempt_id")
            superseded.append(previous["attempt_id"])
        elif replacement is not None:
            raise ValueError("supersedes_attempt_id is not the current attempt for this rollout")
        latest[key] = dict(row, attempt_id=attempt_id)
        attempts[attempt_id] = row
    return latest, superseded


def summarize(manifest: dict, anchors: list[dict], rollouts: list[dict], *, attempts: list[dict] | None = None) -> dict:
    """Pure aggregation; superseded attempts remain in physical attempt counts."""
    repetitions = _positive_integer(manifest.get("expected_repetitions", 32), "expected_repetitions")
    by_id = _validate_anchors(anchors)
    action_count = sum(len(a["actions"]) for a in anchors)
    planned = action_count * repetitions
    if manifest.get("planned_rollouts", planned) != planned:
        raise ValueError("planned_rollouts differs from anchor/action coverage")
    latest, superseded = _resolve_attempts(by_id, rollouts, repetitions)
    missing_ids, missing_keys = [], set()
    reserved = {}
    if attempts is not None:
        for attempt in attempts:
            if attempt.get("kind") != "rollout":
                continue
            aid = _attempt_id(attempt.get("number"))
            identity = tuple(attempt.get("identity", []))
            if aid in reserved or len(identity) != 3:
                raise ValueError("duplicate or invalid rollout reservation")
            root, action, rep = identity
            if (root not in by_id or action not in {a["action_id"] for a in by_id[root]["actions"]}
                    or type(rep) is not int or not 0 <= rep < repetitions):
                raise ValueError("reservation references unknown rollout")
            reserved[aid] = identity
        recorded_ids = set()
        for row in rollouts:
            aid = _attempt_id(row["attempt_id"])
            if reserved.get(aid) != (row["anchor_id"], row["action_id"], row["replicate"]):
                raise ValueError("rollout has no matching reservation")
            recorded_ids.add(aid)
        missing_ids = [aid for aid in reserved if aid not in recorded_ids]
        missing_keys = {reserved[aid] for aid in missing_ids}
    effective_status = Counter(row["status"] for row in latest.values())
    physical_status = Counter(row["status"] for row in rollouts)
    roots = []
    for anchor in anchors:
        key = anchor["anchor_id"]
        values = []
        for action in anchor["actions"]:
            aid = action["action_id"]
            rows = {rep: latest[(key, aid, rep)] for rep in range(repetitions) if (key, aid, rep) in latest}
            counts = Counter(r["status"] for r in rows.values())
            terminal = sum(counts[s] for s in TERMINAL)
            missing = {rep for root, action_id, rep in missing_keys if root == key and action_id == aid}
            attempted = len(set(rows) | missing)
            complete = len(rows) == repetitions and terminal == repetitions and not missing
            values.append(dict(
                action_id=aid, command=action.get("command"), expected_repetitions=repetitions,
                attempted=attempted, terminal=terminal, unattempted=repetitions - attempted,
                missing_result_branches=len(missing),
                **{s: counts[s] for s in sorted(STATUSES)}, complete=complete,
                p_win=counts["win"] / repetitions if complete else None,
                q_score=(counts["win"] + 0.5 * counts["draw"]) / repetitions if complete else None,
                p_win_wilson95=wilson_interval(counts["win"], repetitions) if complete else None,
                delta_original_q=None, paired_repetitions=0,
            ))
        original = next(v for v in values if v["action_id"] == anchor["original_action_id"])
        for value in values:
            if value["complete"] and original["complete"]:
                differences = [
                    SCORES[latest[(key, value["action_id"], rep)]["status"]]
                    - SCORES[latest[(key, original["action_id"], rep)]["status"]]
                    for rep in range(repetitions)
                ]
                value["delta_original_q"] = sum(differences) / repetitions
                value["paired_repetitions"] = repetitions
        complete = all(v["complete"] for v in values)
        best = max(v["q_score"] for v in values) if complete else None
        roots.append(dict(
            anchor_id=key, decision_id=anchor.get("decision_id"), turn=anchor.get("turn"),
            phase=anchor.get("phase"), original_action_id=anchor["original_action_id"],
            complete=complete, ranking_status="empirical_only" if complete else "incomplete",
            empirical_best_action_ids=[v["action_id"] for v in values if v["q_score"] == best] if complete else [],
            certified_best_action_id=None, values=values,
        ))
    return dict(
        schema_version="branch-rollout-summary-v1", experiment_id=manifest.get("experiment_id", "EX060"),
        expected_repetitions=repetitions, anchors=len(anchors), actions=action_count,
        planned=planned, attempted=len(set(latest) | missing_keys),
        physical_attempts=len(reserved) if attempts is not None else len(rollouts),
        recorded_attempts=len(rollouts), missing_result_attempt_ids=missing_ids,
        missing_result_attempts=len(missing_ids), reservation_audited=attempts is not None,
        superseded_attempts=len(superseded), superseded_attempt_ids=superseded,
        physical_status_counts={s: physical_status[s] for s in sorted(STATUSES)},
        status_counts={s: effective_status[s] for s in sorted(STATUSES)},
        terminal=sum(effective_status[s] for s in TERMINAL), unattempted=planned - len(set(latest) | missing_keys),
        complete_actions=sum(v["complete"] for root in roots for v in root["values"]),
        complete_anchors=sum(root["complete"] for root in roots),
        collection_complete=bool(anchors) and not missing_ids and all(root["complete"] for root in roots),
        efficacy_evidence=False, limitation=LIMITATION, roots=roots,
    )


def _assert_model_boundary(value: Any, path="input") -> None:
    forbidden = {"snapshot", "snapshot_path", "private_snapshot", "simulator_snapshot", "simulator_state",
                 "server_state", "full_state", "hidden_state", "opponent_private",
                 "opponent_set", "opponent_sets", "future", "future_trace", "trace", "trace_path",
                 "rollout", "rollouts", "seed", "seeds", "rng", "prng", "rng_state", "random_state"}
    if isinstance(value, dict):
        for key, child in value.items():
            lower = str(key).lower()
            if lower in forbidden or lower.endswith(("_seed", "_seeds", "_rng_state")):
                raise ValueError(f"privileged field in model input: {path}.{key}")
            _assert_model_boundary(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _assert_model_boundary(child, f"{path}[{i}]")


def training_rows(manifest: dict, anchors: list[dict], summary: dict) -> list[dict]:
    """Only declared observations/actions and aggregated targets cross this boundary."""
    roots = {root["anchor_id"]: root for root in summary["roots"]}
    source_refs = manifest.get("source_refs")
    if source_refs is None:
        source_refs = [{"experiment_id": manifest.get("source_experiment"), "slot": manifest.get("source_slot"),
                        "directory": manifest.get("source_directory"),
                        "source_files": {key: value for key, value in manifest.get("source_hashes", {}).items()
                                         if key in ("manifest.json", "events.jsonl", "result.json")}}]
    result = []
    for anchor in anchors:
        observation = anchor["observation"]
        actions = [{k: a[k] for k in ("action_id", "command", "description") if k in a} for a in anchor["actions"]]
        _assert_model_boundary(observation)
        _assert_model_boundary(actions)
        root = roots[anchor["anchor_id"]]
        result.append(dict(
            schema_version="branch-rollout-training-v1", anchor_id=anchor["anchor_id"],
            decision_id=anchor.get("decision_id"), observation=observation, actions=actions,
            original_action_id=anchor["original_action_id"], complete=root["complete"],
            values=root["values"], target_condition="fixed_hidden_state_abyssal_continuation",
            provenance={"experiment_id": manifest.get("experiment_id", "EX060"),
                        "source_refs": source_refs},
        ))
    return result


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _number(value: float | None) -> str:
    return "미산출" if value is None else f"{value:.4f}"


def _slug(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def _page(title: str, body: str) -> str:
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'">'
            f'<title>{_escape(title)}</title><style>'
            'body{font:16px system-ui;max-width:1250px;margin:30px auto;padding:0 16px;line-height:1.6}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:7px;text-align:left}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#165fa5}.scroll{overflow:auto}'
            '</style></head><body>' + body + '</body></html>')


def _public_log(directory: Path, relative: str) -> str:
    trace = (directory / relative).resolve()
    if not trace.is_relative_to(directory.resolve()):
        raise ValueError("trace_path escapes collection directory")
    opener = gzip.open if trace.suffix == ".gz" else open
    with opener(trace, "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    value = data.get("public_log", data.get("protocol"))
    if isinstance(value, list) and all(isinstance(line, str) for line in value):
        value = "\n".join(value)
    if not isinstance(value, str):
        raise ValueError("trace has no public protocol")
    lines = value.splitlines()
    if any(line.startswith(("|request|", "|sentchoice|", "|split|")) for line in lines):
        raise ValueError("private protocol in public replay")
    return value + ("\n" if value and not value.endswith("\n") else "")


def export_viewer(directory: Path, output: Path, manifest: dict, anchors: list[dict],
                  rollouts: list[dict], summary: dict, training: list[dict]) -> dict:
    from ..observability.render import _replay_html

    output.mkdir(parents=True, exist_ok=True)
    (output / "anchors").mkdir(exist_ok=True)
    (output / "replays").mkdir(exist_ok=True)
    training_by_id = {r["anchor_id"]: r for r in training}
    anchor_by_id = {a["anchor_id"]: a for a in anchors}
    by_anchor = {a["anchor_id"]: [] for a in anchors}
    superseded = set(summary["superseded_attempt_ids"])
    replay_count = 0
    for row in rollouts:
        replay_link = "로그 없음"
        if row.get("trace_path"):
            protocol = _public_log(directory, row["trace_path"])
            slug = _slug(_attempt_id(row["attempt_id"]))
            page = _replay_html({"battle_id": f'ex060-{slug}', "teams": []}, protocol)
            page = page.replace('<html lang="en">', '<html lang="ko">').replace(
                'The animated panel uses the official Pokémon Showdown replay asset.\n'
                'If it is unavailable, the Static protocol fallback below remains fully local.',
                '애니메이션은 인터넷 연결이 필요합니다. 아래 공개 경기 로그는 오프라인에서 열립니다.'
            ).replace('Static protocol fallback', '오프라인 공개 경기 로그')
            (output / "replays" / f"{slug}.html").write_text(page, encoding="utf-8")
            replay_link = f'<a href="../replays/{slug}.html">공개 리플레이</a>'
            replay_count += 1
        by_anchor[row["anchor_id"]].append(
            '<tr>' + ''.join(f'<td>{_escape(row.get(key, ""))}</td>' for key in
                            ("action_id", "replicate", "status", "turns", "elapsed_seconds", "attempt_id"))
            + f'<td>{"대체됨" if _attempt_id(row["attempt_id"]) in superseded else "현재"}</td><td>{replay_link}</td></tr>'
        )
    index_rows = []
    for root in summary["roots"]:
        key = root["anchor_id"]
        slug = _slug(key)
        anchor = anchor_by_id[key]
        stats = []
        for v in root["values"]:
            interval = "미산출" if v["p_win_wilson95"] is None else "–".join(_number(x) for x in v["p_win_wilson95"])
            stats.append('<tr>' + ''.join(f'<td>{_escape(x)}</td>' for x in (
                v["action_id"], v["command"], f'{v["win"]}/{v["draw"]}/{v["loss"]}',
                f'{v["terminal"]}/{v["expected_repetitions"]}',
                f'{v["censored"]}/{v["error"]}/{v["aborted"]}/{v["unattempted"]}/{v["missing_result_branches"]}',
                _number(v["p_win"]), interval, _number(v["q_score"]), _number(v["delta_original_q"]),
            )) + '</tr>')
        payload = training_by_id[key]
        body = (f'<a href="../index.html">전체 결정 목록</a><h1>{_escape(key)}</h1>'
                f'<p>턴 {_escape(root["turn"])} · {_escape(root["phase"])} · '
                f'원선택 {_escape(root["original_action_id"])} · {_escape(root["ranking_status"])}</p>'
                f'<p>최고 표본평균 후보: {_escape(root["empirical_best_action_ids"])}</p>'
                f'<p>{_escape(LIMITATION)}</p>'
                '<details><summary>당시 모델 관측·합법 행동 후보</summary><pre>'
                + _escape(json.dumps({"observation": payload["observation"], "actions": payload["actions"]}, ensure_ascii=False, indent=2))
                + '</pre></details><h2>행동별 통계</h2><div class="scroll"><table><thead><tr>'
                '<th>후보</th><th>명령</th><th>승/무/패</th><th>terminal/예정</th><th>검열/오류/중단/미실행/미기록</th>'
                '<th>p_win</th><th>승률 Wilson95%</th><th>q</th><th>원선택 대비 q</th></tr></thead><tbody>'
                + ''.join(stats) + '</tbody></table></div><h2>모든 분기 시도</h2><div class="scroll"><table><thead><tr>'
                '<th>후보</th><th>반복</th><th>결과</th><th>턴</th><th>초</th><th>시도 ID</th><th>채택</th><th>열람</th>'
                '</tr></thead><tbody>' + ''.join(by_anchor[key]) + '</tbody></table></div>')
        (output / "anchors" / f"{slug}.html").write_text(_page(key, body), encoding="utf-8")
        index_rows.append(
            f'<tr><td><a href="anchors/{slug}.html">{_escape(key)}</a></td>'
            f'<td>{_escape(root["turn"])}</td><td>{_escape(root["phase"])}</td>'
            f'<td>{len(anchor["actions"])}</td><td>{_escape(root["ranking_status"])}</td>'
            f'<td>{_escape(root["empirical_best_action_ids"])}</td></tr>'
        )
    title = f'{summary["experiment_id"]} · 한 경기 행동별 분기 자료'
    body = (f'<h1>{_escape(title)}</h1><p>예정 {summary["planned"]} · 시도 {summary["attempted"]} · '
            f'정상 종료 {summary["terminal"]} · 미실행 {summary["unattempted"]} · '
            f'물리 시도 {summary["physical_attempts"]} · 대체 시도 {summary["superseded_attempts"]} · '
            f'결과 미기록 {summary["missing_result_attempts"]}</p>'
            f'<p>{_escape(summary["status_counts"])}</p><p>{_escape(LIMITATION)}</p>'
            '<p>입력·통계·공개 로그는 폴더를 옮긴 뒤에도 오프라인에서 열립니다. '
            '리플레이 애니메이션에는 인터넷 연결이 필요합니다.</p>'
            '<p><a href="summary.json">집계 JSON</a> · <a href="report.md">한국어 보고</a> · '
            '<a href="training.jsonl">학습용 통계 JSONL</a></p><div class="scroll"><table><thead><tr>'
            '<th>결정</th><th>턴</th><th>종류</th><th>후보 수</th><th>순위 상태</th><th>최고 표본평균 후보</th>'
            '</tr></thead><tbody>' + ''.join(index_rows) + '</tbody></table></div>')
    (output / "index.html").write_text(_page(title, body), encoding="utf-8")
    _write_json(output / "summary.json", summary)
    (output / "training.jsonl").write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in training), encoding="utf-8")
    (output / "report.md").write_text(_report_markdown(summary), encoding="utf-8")
    provenance = dict(experiment_id=summary["experiment_id"], source=str(directory.resolve()),
                      source_files={name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                    for name in ("manifest.json", "anchors.jsonl", "rollouts.jsonl", "attempts.jsonl")
                                    if (directory / name).exists()},
                      builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      anchors=len(anchors), replays=replay_count)
    _write_json(output / "provenance.json", provenance)
    return {"viewer": str(output / "index.html"), "replays": replay_count}


def _report_markdown(summary: dict) -> str:
    state = "수집 완료" if summary["collection_complete"] else "수집 미완료"
    text = [f'# {summary["experiment_id"]} 행동별 분기 데이터', '',
            f'**{state}.** {summary["anchors"]}개 결정·{summary["actions"]}개 후보, 후보당 {summary["expected_repetitions"]}회 예정.', '',
            '| 분모 | 수 |', '|---|---:|']
    for label, field in [("예정 분기", "planned"), ("시도한 분기", "attempted"), ("물리 시도", "physical_attempts"),
                         ("대체된 시도", "superseded_attempts"), ("결과 기록 시도", "recorded_attempts"),
                         ("예약 후 결과 미기록", "missing_result_attempts"), ("정상 종료", "terminal"), ("미실행", "unattempted"),
                         ("완료 후보", "complete_actions"), ("완료 결정", "complete_anchors")]:
        text.append(f'| {label} | {summary[field]} |')
    for status in sorted(STATUSES):
        text.append(f'| {status} | {summary["status_counts"][status]} |')
    text.extend(['', '물리 시도는 대체된 원본도 포함합니다. 승무패 분모는 현재 채택된 시도만 사용하며 '
                 '중복은 명시적 supersedes_attempt_id가 있어야 합니다. 검열·오류·중단·미실행을 패배나 무승부로 채우지 않습니다. '
                 '예약 원장이 있으면 결과 누락을 미실행과 구분하며 해당 후보의 값·순위를 확정하지 않습니다.', '',
                 '모든 반복이 정상 종료한 후보만 p_win, Wilson 95% 승률 구간, q=(승+0.5×무)/반복 수를 산출합니다. '
                 '후보와 원선택이 모두 완료된 경우 같은 반복끼리 점수 차이를 평균합니다. '
                 '미완료 후보가 있는 결정의 순위는 미확정입니다. Wilson 구간은 승리 확률에만 적용하며 q의 구간이 아닙니다.', '',
                 LIMITATION, '', '[후보별 전체 통계](summary.json) · [학습용 통계](training.jsonl)', ''])
    return '\n'.join(text)


def export_report(directory: str | Path, *, viewer_directory: str | Path | None = None) -> dict:
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    anchors = _jsonl(directory / "anchors.jsonl")
    rollouts = _jsonl(directory / "rollouts.jsonl")
    attempt_path = directory / "attempts.jsonl"
    summary = summarize(manifest, anchors, rollouts, attempts=_jsonl(attempt_path) if attempt_path.exists() else None)
    training = training_rows(manifest, anchors, summary)
    _write_json(directory / "summary.json", summary)
    (directory / "report.md").write_text(_report_markdown(summary), encoding="utf-8")
    (directory / "training.jsonl").write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in training), encoding="utf-8")
    if viewer_directory is not None:
        summary["viewer_export"] = export_viewer(directory, Path(viewer_directory), manifest, anchors, rollouts, summary, training)
    return summary
