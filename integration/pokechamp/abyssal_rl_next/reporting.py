"""EX-075의 고정 상대 가중치와 실제 선택 행동만 사용하는 오프라인 평가."""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict

from ..imitation.reporting import percentile

OPPONENT_WEIGHTS = {"abyssal": 1.0}
RESULTS = ("win", "draw", "loss")
POINTS = {"win": 1.0, "draw": 0.5, "loss": 0.0}
STATUSES = ("completed", "failed", "incomplete", "unattempted", "invalid")
from .config import SEED
BOOTSTRAP_DRAWS = 10000


def _validated(outcomes):
    rows, seen = list(outcomes), set()
    for row in rows:
        slot = row["slot_id"]
        if slot in seen or row.get("status") not in STATUSES:
            raise ValueError("duplicate slot or invalid terminal status")
        seen.add(slot)
        completed = row["status"] == "completed"
        if completed != (row.get("result") in POINTS):
            raise ValueError("only normal terminal results may carry W/D/L")
        if not completed and row.get("result") is not None:
            raise ValueError("failed or interrupted games must have no result")
    return rows


def complete_outcomes(schedule, outcomes):
    """누락된 예정 슬롯을 미실행으로 유지하며 동결된 배정의 변경을 거부한다."""
    scheduled = {row["slot_id"]: row for row in schedule}
    if len(scheduled) != len(schedule):
        raise ValueError("duplicate scheduled slot")
    observed = {row["slot_id"]: row for row in _validated(outcomes)}
    if not set(observed) <= set(scheduled):
        raise ValueError("outcome outside frozen schedule")
    result = []
    identity = (
        "stage",
        "model",
        "round",
        "pair_id",
        "model_side",
        "opponent",
        "simulator_seed",
        "assignment",
        "model_seed",
        "opponent_seed",
        "teams",
    )
    for slot, planned in scheduled.items():
        row = observed.get(slot)
        if row is None:
            result.append(dict(planned, status="unattempted", result=None))
            continue
        for key in identity:
            if key in planned and row.get(key) != planned[key]:
                raise ValueError("outcome differs from frozen schedule: " + key)
        result.append(row)
    return result


def _counts(rows):
    statuses = Counter(row["status"] for row in rows)
    return dict(
        planned=len(rows),
        attempted=len(rows) - statuses["unattempted"],
        **{status: statuses[status] for status in STATUSES},
    )


def _weighted(values):
    # A missing opponent has no estimate; its weight is never reassigned.
    if any(values.get(opponent) is None for opponent in OPPONENT_WEIGHTS):
        return None
    return math.fsum(
        OPPONENT_WEIGHTS[opponent] * values[opponent] for opponent in OPPONENT_WEIGHTS
    )


def policy_summary(outcomes, *, expected_games=None):
    rows = _validated(outcomes)
    if any(row.get("opponent") not in OPPONENT_WEIGHTS for row in rows):
        raise ValueError("evaluation contains an unregistered opponent")
    opponents = {}
    for opponent, weight in OPPONENT_WEIGHTS.items():
        group = [row for row in rows if row["opponent"] == opponent]
        valid = [row for row in group if row["status"] == "completed"]
        counts = Counter(row["result"] for row in valid)
        opponents[opponent] = dict(
            weight=weight,
            **_counts(group),
            wins=counts["win"],
            draws=counts["draw"],
            losses=counts["loss"],
            mean_score=statistics.mean(POINTS[row["result"]] for row in valid)
            if valid
            else None,
            rates={
                result: counts[result] / len(valid) if valid else None
                for result in RESULTS
            },
        )
    total = _counts(rows)
    return dict(
        **total,
        complete=bool(rows)
        and total["completed"] == len(rows)
        and (expected_games is None or len(rows) == expected_games),
        expected_games=expected_games,
        opponents=opponents,
        mean_score=_weighted(
            {key: value["mean_score"] for key, value in opponents.items()}
        ),
        rates={
            result: _weighted(
                {key: value["rates"][result] for key, value in opponents.items()}
            )
            for result in RESULTS
        },
        opponent_weights=OPPONENT_WEIGHTS.copy(),
    )


def _cells(rows):
    result = {}
    for row in _validated(rows):
        if row.get("opponent") not in OPPONENT_WEIGHTS or row.get("model_side") not in (
            "p1",
            "p2",
        ):
            raise ValueError("invalid evaluation opponent or model side")
        key = (row["pair_id"], row["model_side"], row["assignment"])
        if row["assignment"] not in (0, 1):
            raise ValueError("invalid learner team assignment")
        if key in result:
            raise ValueError("duplicate evaluation cell")
        result[key] = row
    return result


def evaluation_complete(outcomes, *, expected_pairs):
    cells = _cells(outcomes)
    pairs = {key[0] for key in cells}
    return (
        len(pairs) == expected_pairs
        and len(cells) == expected_pairs * 4
        and all(row["status"] == "completed" for row in cells.values())
    )


def select_policy(candidates):
    """완료된 학습 dev 후보만 선택한다. 동점은 더 이른 라운드다."""
    candidates = list(candidates)
    if len(candidates) > 34:
        raise ValueError("more than 34 dev evaluations")
    eligible, rounds, names = [], set(), set()
    for candidate in candidates:
        model, round_id = candidate["model"], candidate["round"]
        if model != ("initial" if round_id == 0 else f"round-{round_id}"):
            raise ValueError("candidate name differs from round")
        if type(round_id) is not int or not 0 <= round_id <= 128:
            raise ValueError("invalid training candidate round")
        if round_id in rounds or model in names:
            raise ValueError("duplicate training candidate")
        rounds.add(round_id)
        names.add(model)
        rows = candidate["outcomes"]
        if not evaluation_complete(rows, expected_pairs=16):
            continue
        summary = policy_summary(rows, expected_games=64)
        eligible.append(
            {
                "model": model,
                "round": round_id,
                "win_rate": summary["rates"]["win"],
                "summary": summary,
            }
        )
    if not eligible:
        return None
    return min(eligible, key=lambda row: (-row["win_rate"], row["round"]))


def constant_reference(train_outcomes):
    """정상 train 경기의 결과 빈도. 결정 수로 가중하지 않는다."""
    rows = [row for row in _validated(train_outcomes) if row["status"] == "completed"]
    if not rows:
        return None
    counts = Counter(row["result"] for row in rows)
    return [counts[result] / len(rows) for result in RESULTS]


def _wdl(value):
    if isinstance(value, dict):
        if set(value) == set(RESULTS):
            value = [value[result] for result in RESULTS]
        elif set(value) == {"W", "D", "L"}:
            value = [value[result] for result in ("W", "D", "L")]
        else:
            raise ValueError("unknown W/D/L class order")
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("W/D/L must have three probabilities")
    if any(
        type(item) not in (int, float) or not math.isfinite(item) or not 0 <= item <= 1
        for item in value
    ):
        raise ValueError("invalid W/D/L probability")
    if not math.isclose(math.fsum(value), 1.0, abs_tol=1e-6, rel_tol=0):
        raise ValueError("W/D/L probabilities do not sum to one")
    return [float(item) for item in value]


def chosen_prediction(decision, field="wdl_before"):
    if field in decision:
        return _wdl(decision[field])
    if field != "wdl_before":
        raise ValueError("missing chosen-action predictions: " + field)
    choices = decision["action_ids"]
    choice = decision["choice"]
    if len(set(choices)) != len(choices) or choice not in choices:
        raise ValueError("invalid recorded candidate order or choice")
    values = decision["wdl_probabilities"]
    if isinstance(values, dict):
        if set(values) != set(choices):
            raise ValueError("W/D/L candidate identities differ")
        return _wdl(values[choice])
    if len(values) != len(choices):
        raise ValueError("W/D/L candidate count differs")
    return _wdl(values[choices.index(choice)])


def _selected_rows(outcomes, decisions):
    valid = {
        row["slot_id"]: row
        for row in _validated(outcomes)
        if row["status"] == "completed"
    }
    grouped, identities = defaultdict(list), set()
    for row in decisions:
        slot = row["slot_id"]
        if slot not in valid or row.get("automatic", False):
            continue
        identity = (slot, row["decision_id"])
        if identity in identities:
            raise ValueError("duplicate chosen-action observation")
        identities.add(identity)
        if row.get("terminal_status", "completed") != "completed":
            raise ValueError("prediction disagrees with terminal status")
        recorded = row.get("outcome")
        if recorded is not None:
            normalized = {"W": "win", "D": "draw", "L": "loss"}.get(recorded, recorded)
            if normalized != valid[slot]["result"]:
                raise ValueError("prediction disagrees with terminal result")
        if "action_ids" in row:
            actions = row["action_ids"]
            if (
                len(actions) < 2
                or len(actions) != len(set(actions))
                or row.get("choice") not in actions
            ):
                raise ValueError("invalid actual model selection")
        grouped[slot].append(row)
    return valid, grouped


def probability_metrics(outcomes, decisions, *, field="wdl_before", constant=None):
    """경기내 평균→상대 평균→고정 가중치. reliability도 같은 결정 가중치다."""
    rows = _validated(outcomes)
    if any(row.get("opponent") not in OPPONENT_WEIGHTS for row in rows):
        raise ValueError("probability evaluation contains unknown opponent")
    valid, grouped = _selected_rows(rows, decisions)
    constant = _wdl(constant) if constant is not None else None
    games, opponents = {}, {}
    for slot, decisions_for_game in grouped.items():
        outcome = valid[slot]
        true_class = RESULTS.index(outcome["result"])
        estimates = [
            constant if constant is not None else chosen_prediction(row, field)
            for row in decisions_for_game
        ]
        briers = [
            0.5
            * math.fsum((p - (index == true_class)) ** 2 for index, p in enumerate(wdl))
            for wdl in estimates
        ]
        nlls = [
            -math.log(wdl[true_class]) if wdl[true_class] > 0 else math.inf
            for wdl in estimates
        ]
        nll = statistics.mean(nlls)
        games[slot] = {
            "opponent": outcome["opponent"],
            "result": outcome["result"],
            "decisions": len(estimates),
            "half_brier": statistics.mean(briers),
            "nll": nll if math.isfinite(nll) else None,
            "nll_infinite": not math.isfinite(nll),
        }
    for opponent, weight in OPPONENT_WEIGHTS.items():
        group = [value for value in games.values() if value["opponent"] == opponent]
        infinite = any(value["nll_infinite"] for value in group)
        opponents[opponent] = {
            "weight": weight,
            "games": len(group),
            "decisions": sum(value["decisions"] for value in group),
            "half_brier": statistics.mean(value["half_brier"] for value in group)
            if group
            else None,
            "nll": statistics.mean(value["nll"] for value in group)
            if group and not infinite
            else None,
            "nll_infinite": infinite,
        }
    # Classwise reliability avoids conflating expected game score with win probability.
    bins = {
        result: [
            {
                "lower": i / 10,
                "upper": (i + 1) / 10,
                "include_upper": i == 9,
                "decisions": 0,
                "weight": 0.0,
                "predicted_sum": 0.0,
                "observed_sum": 0.0,
            }
            for i in range(10)
        ]
        for result in RESULTS
    }
    for slot, decisions_for_game in grouped.items():
        outcome = valid[slot]
        opponent = outcome["opponent"]
        mass = (
            OPPONENT_WEIGHTS[opponent]
            / opponents[opponent]["games"]
            / len(decisions_for_game)
        )
        for row in decisions_for_game:
            prediction = (
                constant if constant is not None else chosen_prediction(row, field)
            )
            for class_index, result in enumerate(RESULTS):
                p = prediction[class_index]
                target = bins[result][min(int(p * 10), 9)]
                target["decisions"] += 1
                target["weight"] += mass
                target["predicted_sum"] += mass * p
                target["observed_sum"] += mass * (outcome["result"] == result)
    for class_bins in bins.values():
        for entry in class_bins:
            weight = entry["weight"]
            entry["mean_prediction"] = (
                entry.pop("predicted_sum") / weight if weight else None
            )
            entry["observed_frequency"] = (
                entry.pop("observed_sum") / weight if weight else None
            )
    missing = sorted(set(valid) - set(grouped))
    infinite = any(value["nll_infinite"] for value in opponents.values())
    return {
        "prediction": field if constant is None else "train_game_frequency",
        "constant": constant,
        "classes": list(RESULTS),
        "games": len(games),
        "decisions": sum(map(len, grouped.values())),
        "normal_games": len(valid),
        "missing_prediction_games": missing,
        "all_normal_games_have_predictions": not missing,
        "half_brier": _weighted(
            {key: value["half_brier"] for key, value in opponents.items()}
        ),
        "nll": _weighted({key: value["nll"] for key, value in opponents.items()}),
        "nll_infinite": infinite,
        "zero_probability_nll": "infinity represented by nll=null and nll_infinite=true",
        "opponents": opponents,
        "per_game": games,
        "reliability": {
            "bins": 10,
            "classes": bins,
            "mass": sum(value["weight"] for value in bins["win"]),
            "weighting": "opponent_weight / games_for_opponent / decisions_in_game",
        },
        "probability_meaning": "actual_selected_action_terminal_WDL",
    }


def calibration_decision(outcomes, decisions, *, training_complete=True):
    outcomes, decisions = list(outcomes), list(decisions)
    complete = bool(training_complete) and evaluation_complete(
        outcomes, expected_pairs=6
    )
    if not complete:
        return {
            "adopt": False,
            "head": "before",
            "complete": False,
            "reason": "보정 또는 새 dev 평가 미완료",
            "before": None,
            "after": None,
        }
    _, grouped = _selected_rows(outcomes, decisions)
    if any("wdl_after" not in row for group in grouped.values() for row in group):
        return {
            "adopt": False,
            "head": "before",
            "complete": False,
            "reason": "보정 후 선택 행동 예측 미완료",
            "before": None,
            "after": None,
        }
    before = probability_metrics(outcomes, decisions, field="wdl_before")
    after = probability_metrics(outcomes, decisions, field="wdl_after")
    complete = (
        before["all_normal_games_have_predictions"]
        and after["all_normal_games_have_predictions"]
    )
    adopt = (
        complete
        and before["half_brier"] is not None
        and after["half_brier"] < before["half_brier"]
    )
    return {
        "adopt": adopt,
        "head": "after" if adopt else "before",
        "complete": complete,
        "reason": "가중 half-Brier 감소"
        if adopt
        else "보정 전 head 유지: 동점/악화 또는 선택 행동 예측 미완료",
        "before": before,
        "after": after,
    }


def paired_bootstrap(initial, selected, *, draws=BOOTSTRAP_DRAWS, seed=SEED):
    """64개 팀쌍의4셀을 함께 재표집하는 승률 및 대응 승률차 구간."""
    if type(draws) is not int or draws <= 0:
        raise ValueError('bootstrap draws must be positive')
    left, right = _cells(initial), _cells(selected)
    pairs = sorted({key[0] for key in set(left) | set(right)})
    clusters, missing = [], []
    for pair in pairs:
        wins, differences = [], []
        for assignment in (0, 1):
            for side in ('p1', 'p2'):
                key = (pair, side, assignment)
                a, b = left.get(key), right.get(key)
                if a and b:
                    for field in ('simulator_seed', 'model_seed', 'opponent_seed', 'teams'):
                        if field not in a or field not in b or a[field] != b[field]:
                            raise ValueError('paired conditions differ or missing: ' + field)
                if not a or not b or a['status'] != 'completed' or b['status'] != 'completed':
                    missing.append(key)
                    continue
                wins.append(float(b['result'] == 'win'))
                differences.append(float(b['result'] == 'win') - float(a['result'] == 'win'))
        if len(wins) == 4:
            clusters.append(dict(pair_id=pair, win_rate=statistics.mean(wins), delta=statistics.mean(differences)))
    complete = len(pairs) == len(clusters) == 64 and not missing
    ci_win = ci_delta = None
    if complete:
        rng = random.Random(seed)
        win_draws, delta_draws = [], []
        for _ in range(draws):
            sample = [clusters[rng.randrange(64)] for _ in range(64)]
            win_draws.append(sum(row['win_rate'] for row in sample) / 64)
            delta_draws.append(sum(row['delta'] for row in sample) / 64)
        ci_win = [percentile(win_draws, .025), percentile(win_draws, .975)]
        ci_delta = [percentile(delta_draws, .025), percentile(delta_draws, .975)]
    rate = statistics.mean(row['win_rate'] for row in clusters) if clusters else None
    difference = statistics.mean(row['delta'] for row in clusters) if clusters else None
    return dict(complete=complete, available_pairs=len(clusters), expected_pairs=64,
        missing=missing, win_rate=rate, win_rate_ci95=ci_win,
        mean_difference=difference, ci95=ci_delta,
        target_achieved=bool(complete and rate >= .6 and ci_win[0] > .5),
        improvement=bool(complete and ci_delta[0] > 0),
        bootstrap=dict(draws=draws, seed=seed, cluster='pair_id'), clusters=clusters)


def summarize(
    schedule, outcomes, *, decisions=(), train_outcomes=(), stage_status=None
):
    """전체 일정 분모를 보존하고 test의 선택/초기 모델만 비교한다."""
    rows = complete_outcomes(schedule, outcomes)
    decisions = list(decisions)
    test = [row for row in rows if row.get("stage") == "test"]
    initial = [row for row in test if row["model"] == "initial"]
    selected = [row for row in test if row["model"] == "selected"]
    models = {
        name: policy_summary(group, expected_games=256)
        for name, group in (("initial", initial), ("selected", selected))
    }
    paired = paired_bootstrap(initial, selected)
    stages = {
        stage: _counts([row for row in rows if row.get("stage") == stage])
        for stage in sorted({row.get("stage", "unknown") for row in rows})
    }
    probability = {}
    selected_slots = {row["slot_id"] for row in selected}
    selected_decisions = [row for row in decisions if row["slot_id"] in selected_slots]
    if selected_decisions:
        probability["before"] = probability_metrics(
            selected, selected_decisions, field="wdl_before"
        )
        if all(
            "wdl_after" in row
            for row in selected_decisions
            if not row.get("automatic", False)
        ):
            probability["after"] = probability_metrics(
                selected, selected_decisions, field="wdl_after"
            )
        reference = constant_reference(train_outcomes)
        if reference is not None:
            probability["constant"] = probability_metrics(
                selected, selected_decisions, constant=reference
            )
    stage_status = dict(stage_status or {})
    required = (
        "cpu_validation",
        "parent_restore",
        "gpu_preflight",
        "first_eight_audit",
        "training",
        "trained_candidate_dev",
        "all_decisions_audit",
        "independent_statistics",
        "head_action_invariance",
        "sampled_viewer_audit",
        "policy_selection",
        "calibration_decision",
        "resume_validation",
        "test",
        "viewer",
        "sealed",
        "cleanup",
    )
    missing = [name for name in required if stage_status.get(name) is not True]
    if not paired["complete"] and "test" not in missing:
        missing.append("test")
    return dict(
        experiment_id="EX-075",
        **_counts(rows),
        outcomes=rows,
        stages=stages,
        models=models,
        paired=paired,
        probability=probability,
        stage_status=stage_status,
        incomplete_requirements=missing,
        experiment_complete=not missing,
        target_achieved=paired["target_achieved"],
        performance_improved=paired["improvement"],
        opponent_weights=OPPONENT_WEIGHTS.copy(),
        interpretation="EX-074의 82라운드 모델 대비 추가 학습 효과이며 기존 최고 77라운드보다 우수하다는 주장은 하지 않음. "
        "확률 평가는 실제 선택 행동에만 적용하며 미선택 행동의 반사실적 정확성은 미검증.",
    )


def report_markdown(summary):
    paired = summary['paired']
    lines = ['# EX-075 82라운드 계승 추가 학습', '',
        f"실험 완료: {summary['experiment_complete']} · 승률 목표 달성: {summary['target_achieved']} · 82라운드 출발 모델 대비 개선 입증: {summary['performance_improved']}", '',
        '승률은 승/(승+무+패)이며 실패·중단은 결과로 변환하지 않는다.', '',
        '| 모델 | 정상/예정 | 승/무/패 | 승률 | 무승부 보정 점수 |',
        '|---|---:|---:|---:|---:|']
    for name, model in summary['models'].items():
        o = model['opponents']['abyssal']
        lines.append(f"| {name} | {o['completed']}/{o['planned']} | {o['wins']}/{o['draws']}/{o['losses']} | {o['rates']['win']} | {o['mean_score']} |")
    lines += ['', f"선택 정책 승률 95% 구간: {paired['win_rate_ci95']}",
        f"82라운드 출발 모델 대비 대응 승률차: {paired['mean_difference']} · 95% 구간: {paired['ci95']}",
        f"독립 팀쌍 {paired['available_pairs']}/64 · bootstrap {paired['bootstrap']['draws']}회.", '',
        '미완료 기준: ' + (', '.join(summary['incomplete_requirements']) or '없음'), '',
        '미실행 train/dev 슬롯은 시간 제한 실험의 예약 상한이며 모두 실행해야 하는 분모가 아니다.',
        '모든 정상 경기 뷰어를 내보내며 브라우저 전수·점진 전수 검증은 생략한다. ' +
        'train/dev/calibration/calibration_dev/test-initial/test-selected별 슬롯 ID 순 첫·마지막 정상 경기만 최대12경기 확인한다.',
        summary['interpretation'], '']
    return '\n'.join(lines)
