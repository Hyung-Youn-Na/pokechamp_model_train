"""EX-071의 전체 분모와 대진별 대응 bootstrap; 저장 결과만 읽는다."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

POINTS = {"win": 1.0, "draw": 0.5, "loss": 0.0}
SEED = 20261001


def read_json(path):
    return json.loads(Path(path).read_text())


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jsonl(path):
    path = Path(path)
    return (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path.exists()
        else []
    )


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower, upper = math.floor(index), math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def latencies(values):
    values = list(values)
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("invalid recorded inference latency")
    return dict(
        count=len(values),
        mean=statistics.mean(values) if values else None,
        median=statistics.median(values) if values else None,
        p95=percentile(values, 0.95),
        total=sum(values),
    )


def _complete(row):
    return row.get("status") == "completed" and row.get("result") in POINTS


def summarize(schedule, outcomes, *, inference_latencies=None, draws=10000, seed=SEED):
    """게임 평균과 공통 완료 slot의 대응 평균은 분모를 따로 유지한다."""
    expected = {r["slot_id"]: r for r in schedule}
    if len(expected) != len(schedule):
        raise ValueError("duplicate scheduled slot")
    observed = {}
    allowed = {"completed", "failed", "incomplete", "unattempted", "invalid"}
    for row in outcomes:
        slot = row["slot_id"]
        if slot in observed or slot not in expected or row.get("status") not in allowed:
            raise ValueError("unknown, duplicate or invalid outcome")
        for key in ("pair_id", "model", "model_side", "opponent"):
            if row[key] != expected[slot][key]:
                raise ValueError("outcome differs from frozen schedule: " + key)
        if (row["status"] == "completed") != (row.get("result") in POINTS):
            raise ValueError("unfinished game must not be converted to a score")
        observed[slot] = row
    if set(observed) != set(expected):
        raise ValueError("report requires an outcome for every scheduled slot")

    models = {}
    for model in ("initial", "selected"):
        rows = [r for r in observed.values() if r["model"] == model]
        valid = [r for r in rows if _complete(r)]
        counts = Counter(r["status"] for r in rows)
        wdl = Counter(r["result"] for r in valid)
        models[model] = dict(
            planned=len(rows),
            attempted=len(rows) - counts["unattempted"],
            **{key: counts[key] for key in sorted(allowed)},
            wins=wdl["win"],
            draws=wdl["draw"],
            losses=wdl["loss"],
            completion_rate=len(valid) / len(rows) if rows else None,
            mean_score=sum(POINTS[r["result"]] for r in valid) / len(valid) if valid else None,
            inference_seconds=latencies((inference_latencies or {}).get(model, [])),
        )

    cells = defaultdict(dict)
    for row in observed.values():
        key = (row["pair_id"], row["model_side"], row["opponent"])
        if row["model"] in cells[key]:
            raise ValueError("duplicate model in paired cell")
        cells[key][row["model"]] = row
    clusters, paired, missing = defaultdict(list), [], []
    for key, cell in sorted(cells.items()):
        if set(cell) != {"initial", "selected"}:
            raise ValueError("schedule omits a paired model")
        item = dict(
            pair_id=key[0],
            model_side=key[1],
            opponent=key[2],
            slots={model: row["slot_id"] for model, row in cell.items()},
        )
        if all(_complete(row) for row in cell.values()):
            delta = POINTS[cell["selected"]["result"]] - POINTS[cell["initial"]["result"]]
            clusters[key[0]].append(delta)
            paired.append(dict(item, delta=delta))
        else:
            missing.append(
                dict(item, statuses={model: row["status"] for model, row in cell.items()})
            )

    differences = [r["delta"] for r in paired]
    available = [clusters[key] for key in sorted(clusters)]
    bootstrap = []
    if available:
        rng = random.Random(seed)
        for _ in range(draws):
            selected = [available[rng.randrange(len(available))] for _ in available]
            bootstrap.append(sum(map(sum, selected)) / sum(map(len, selected)))
    initial, selected = models["initial"]["mean_score"], models["selected"]["mean_score"]
    unpaired_difference = (
        selected - initial if initial is not None and selected is not None else None
    )
    counts = Counter(r["status"] for r in observed.values())
    return dict(
        experiment_id="EX-071",
        probability_meaning="action_selection_probability",
        planned=len(schedule),
        attempted=len(schedule) - counts["unattempted"],
        **{key: counts[key] for key in sorted(allowed)},
        models=models,
        normal_game_mean_difference=unpaired_difference,
        paired=dict(
            planned_cells=len(cells),
            completed_cells=len(paired),
            missing_cells=missing,
            planned_clusters=len({r["pair_id"] for r in schedule}),
            available_clusters=len(available),
            cluster_cell_counts={key: len(v) for key, v in clusters.items()},
            mean_difference=statistics.mean(differences) if differences else None,
            ci95=[percentile(bootstrap, 0.025), percentile(bootstrap, 0.975)]
            if bootstrap
            else None,
            bootstrap=dict(
                draws=draws,
                seed=seed,
                unit="team_matchup",
                estimator=(
                    "slot-weighted mean of common completed paired cells within resampled blocks"
                ),
            ),
            cells=paired,
        ),
        interpretation=(
            "5대진의 첫 탐색 평가이며 작은 표본과 대응 누락의 한계가 있습니다. "
            "행동 선택 확률은 승률이 아닙니다. 구간이 0을 포함하거나 대응 자료가 부족하면 "
            "개선은 불확실하며 효과가 없다는 증거로 해석하지 않습니다."
        ),
    )


def report_markdown(summary):
    def number(value):
        return "미산출" if value is None else f"{value:.4f}"

    rows = [
        "# EX-071 첫 배틀 평가",
        "",
        summary["interpretation"],
        "",
        f"예정 {summary['planned']} · 시도 {summary['attempted']} · 정상 {summary['completed']} · "
        f"실패 {summary['failed']} · 미완료 {summary['incomplete']} · 무효 {summary['invalid']} · "
        f"미실행 {summary['unattempted']}경기.",
        "",
        "| 모델 | 정상/예정 | 승/무/패 | 평균 점수 | 추론 평균/p95(초) |",
        "|---|---:|---:|---:|---:|",
    ]
    for model, label in (("initial", "초기"), ("selected", "학습 선택")):
        entry = summary["models"][model]
        latency = entry["inference_seconds"]
        rows.append(
            f"| {label} | {entry['completed']}/{entry['planned']} | "
            f"{entry['wins']}/{entry['draws']}/{entry['losses']} | {number(entry['mean_score'])} | "
            f"{number(latency['mean'])}/{number(latency['p95'])} |"
        )
    paired = summary["paired"]
    interval = paired["ci95"]
    interval_text = f"[{number(interval[0])}, {number(interval[1])}]" if interval else "미산출"
    ordinary_difference = number(summary["normal_game_mean_difference"])
    rows += [
        "",
        "평균 점수는 `(승 + 0.5 × 무)/정상 종료 경기`입니다. 시간·턴 제한과 실패는 "
        "패배 또는 무승부로 바꾸지 않았습니다.",
        "",
        f"정상 경기 평균의 학습−초기 차이는 {ordinary_difference}입니다. "
        f"공통 정상 {paired['completed_cells']}/{paired['planned_cells']} slot, "
        f"{paired['available_clusters']}/{paired['planned_clusters']}대진의 대응 차이는 "
        f"{number(paired['mean_difference'])}이며, 대진별 bootstrap 10,000회의 95% 구간은 "
        f"{interval_text}입니다.",
        "",
        "[전체 결과·대응 누락](result.json) · [동결 일정과 출처](manifest.json)",
        "",
    ]
    return "\n".join(rows)
