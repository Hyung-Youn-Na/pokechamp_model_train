"""Korean final report and seal for an EX-080 run (reads committed artifacts only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import PROTOCOL
from ..storage import read, sha


def events(run):
    path = Path(run) / "events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def dev_curve(run):
    rows = []
    for path in sorted((Path(run) / "rounds").glob("*/dev.json")):
        rows.append(read(path))
    return rows


def seal(run, *, exclude=("cache", "final/seal.json")):
    run = Path(run)
    lines = []
    for path in sorted(p for p in run.rglob("*") if p.is_file()):
        relative = path.relative_to(run).as_posix()
        if relative.split("/")[0] in exclude or relative in exclude:
            continue
        lines.append(f"{sha(path)}  {relative}")
    text = "\n".join(lines) + "\n"
    return text, hashlib.sha256(text.encode()).hexdigest(), len(lines)


def report(run, *, audit, viewer, browser, sealed):
    run = Path(run)
    manifest = read(run / "manifest.json")
    stop = read(run / "train-stop.json") if (run / "train-stop.json").exists() else None
    selection = read(run / "selection.json") if (run / "selection.json").exists() else None
    test = read(run / "test.json") if (run / "test.json").exists() else None
    log = events(run)
    start = next((e["at"] for e in log if e["event"] == "start"), None)
    end = log[-1]["at"] if log else None
    hours = (end - start) / 3600 if start and end else None
    curve = dev_curve(run)
    lines = ["# EX-080 최종 보고 — Qwen3.5-0.8B 행렬 탐색 자기대국", "",
             f"- identity: `{manifest['identity']}`",
             f"- 실행 경과(첫 시작~마지막 사건): {hours:.2f}시간" if hours else "- 실행 경과: 미상",
             f"- GPU: 물리 GPU2·3 (2장), 벽시계 기준 GPU 점유 약 {2 * hours:.1f} GPU·시간" if hours else "- GPU: 물리 GPU2·3", ""]
    lines += ["## 판정", ""]
    if test and test.get("complete"):
        p = test["primary"]
        verdict = "정책 개선 성공" if test["success"] else "정책 개선 미입증"
        lines += [f"- 주판정(고정 abyssal-tera-v1 상대 P1−P0 점수차): 점추정 {p['point']:+.4f}, "
                  f"32블록 대응 bootstrap 95% [{p['low']:+.4f}, {p['high']:+.4f}] → **{verdict}**",
                  "- 점수: 승1·무0.5·패0, 300턴 검열 0.5. P0는 균등 정책이라 하한 효과가 있을 수 있다.", ""]
    else:
        lines += ["- 잠긴 test가 완료되지 않아 효능은 판정하지 않는다.", ""]
    lines += ["## 학습 경과", ""]
    if stop:
        lines += [f"- 종료: round {stop['round']}, 사유 {', '.join(stop['reasons'])} (둔화: 직전 평가 대비 <{PROTOCOL['evaluation']['threshold']} "
                  f"{PROTOCOL['evaluation']['patience']}회 연속, 최소 {PROTOCOL['evaluation']['min_round']}라운드; 상한 {PROTOCOL['evaluation']['max_rounds']})", ""]
    lines += ["| round | 직전 평가 대비 점수 | 상대 | P0 대비 점수 | 검열 |", "|---:|---:|---|---:|---:|"]
    lines += [f"| {r['round']} | {r['score']:.4f} | {r['opponent']} | {r['p0_score']:.4f} | {r['censored']} |" for r in curve]
    lines += ["", "## 선택", ""]
    if selection:
        lines += [f"- 후보 라운드 {selection['candidates']}, round-robin {selection['games']}경기, Bradley–Terry 최고: round {selection['selected']}",
                  f"- 강도: {json.dumps(selection['strengths'], ensure_ascii=False)}"]
    lines += ["", "## 잠긴 test", ""]
    if test:
        lines += [f"- 상태 분포: {json.dumps(test['statuses'], ensure_ascii=False)}",
                  f"- 조건별 평균 점수: {json.dumps({k: (None if v is None else round(v, 4)) for k, v in test['means'].items()}, ensure_ascii=False)}",
                  f"- 보조 대비: {json.dumps(test['secondary'], ensure_ascii=False)}", f"- P1 대 P0 직접 대결(P1 점수): {test['direct']}"]
    lines += ["", "## 감사·뷰어·봉인", "",
              f"- 전수 감사: 경기 {audit['games']}(정상 {audit['normal']}), 결정 {audit['decisions']}, 탐색 재계산 {audit['searches']}, "
              f"재렌더 대조 {audit['rerendered']}, 리플레이 행 {audit['replay_rows']} — 통과",
              f"- 뷰어: [{viewer['games']}경기]({viewer['target']}/index.html), 오프라인 이동 브라우저 표본 {len(browser['sampled'])}개 통과(전수 아님)",
              f"- 봉인: {sealed['files']}개 파일, 목록 sha256 `{sealed['digest']}`", "",
              "## 한계", "",
              "- 양측 세트·현재 상태 공개 진단이며 일반 비공개 Gen9 OU 효능이 아니다. 학습 seed 하나, 고정 두 팀이다.",
              "- 비동기 배치 때문에 자기대국은 비트 단위로 재현되지 않는다(사전 허용오차 gate 통과, 실제 출력 기록, 감사는 기록에서 재계산).",
              "- EX-079(현 설계)와는 탐색·모델·P0가 달라 정성 비교만 가능하다."]
    return "\n".join(lines) + "\n"
