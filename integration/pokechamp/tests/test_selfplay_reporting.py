"""합성 결과의 가중 분모·선택·보정·대응 추론 검사. 실제 실험 evidence가 아니다."""

from __future__ import annotations

import copy
import json
import math

import pytest

from integration.pokechamp.selfplay import reporting as r


def evaluation(model="selected", pairs=4, result="win", stage="dev"):
    return [
        {
            "slot_id": f"{model}-{pair}-{side}-{opponent}",
            "stage": stage,
            "model": model,
            "round": 1,
            "pair_id": f"pair-{pair:02d}",
            "model_side": side,
            "opponent": opponent,
            "status": "completed",
            "result": result,
            "turns": 2,
            "simulator_seed": [pair, 1, 2, 3],
        }
        for pair in range(pairs)
        for side in ("p1", "p2")
        for opponent in r.OPPONENT_WEIGHTS
    ]


def prediction(outcome, index=0, before=None, after=None):
    row = {
        "slot_id": outcome["slot_id"],
        "decision_id": f"decision-{index}",
        "automatic": False,
        "terminal_status": "completed",
        "outcome": {"win": "W", "draw": "D", "loss": "L"}[outcome["result"]],
        "action_ids": ["move:a", "move:b"],
        "choice": "move:b",
        "log_probabilities": [math.log(0.9), math.log(0.1)],
        "wdl_probabilities": [[0.99, 0.005, 0.005], before or [1 / 3] * 3],
        "wdl_before": before or [1 / 3] * 3,
    }
    if after is not None:
        row["wdl_after"] = after
    return row


def test_fixed_weights_preserve_opponent_raw_denominators_and_failures():
    rows = evaluation(pairs=1)
    for row in rows:
        row["result"] = "win" if row["opponent"] == "initial" else "loss"
    assert r.policy_summary(rows)["mean_score"] == 0.75
    rows[0].update(status="failed", result=None)
    summary = r.policy_summary(rows, expected_games=6)
    assert summary["failed"] == 1 and not summary["complete"]
    assert summary["opponents"]["initial"]["wins"] == 1
    assert summary["rates"] == {"win": 0.75, "draw": 0.0, "loss": 0.25}
    rows[0]["result"] = "loss"
    with pytest.raises(ValueError, match="normal terminal"):
        r.policy_summary(rows)


def test_missing_opponent_never_redistributes_fixed_weight():
    rows = [row for row in evaluation() if row["opponent"] == "initial"]
    summary = r.policy_summary(rows)
    assert summary["mean_score"] is None
    assert summary["opponents"]["initial"]["mean_score"] == 1


def test_probability_game_means_not_decision_counts_and_weighted_reliability():
    rows = evaluation(pairs=1)
    decisions = []
    for row in rows:
        if row["opponent"] == "initial":
            before = [1, 0, 0] if row["model_side"] == "p1" else [0, 0, 1]
            count = 20 if row["model_side"] == "p1" else 1
        else:
            before, count = [1, 0, 0], 2
        decisions.extend(
            prediction(row, index, before=before) for index in range(count)
        )
    metrics = r.probability_metrics(rows, decisions)
    assert metrics["half_brier"] == pytest.approx(0.375)
    assert metrics["nll"] is None and metrics["nll_infinite"]
    bins = metrics["reliability"]["classes"]["win"]
    assert bins[0]["weight"] == pytest.approx(0.375)
    assert bins[9]["weight"] == pytest.approx(0.625)
    assert bins[9]["include_upper"]
    assert bins[0]["observed_frequency"] == 1
    assert metrics["reliability"]["mass"] == pytest.approx(1)
    assert all(len(bins) == 10 for bins in metrics["reliability"]["classes"].values())
    json.dumps(metrics, allow_nan=False)


def test_probability_uses_selected_action_and_excludes_automatic_and_failed_games():
    rows = evaluation(pairs=1)
    decisions = [prediction(row, before=[0.2, 0.3, 0.5]) for row in rows]
    for decision in decisions:
        del decision["wdl_before"]
    decisions.append(dict(prediction(rows[0]), decision_id="auto", automatic=True))
    failed = dict(rows[0], slot_id="failed", status="failed", result=None)
    decisions.append(
        dict(prediction(rows[0]), slot_id="failed", wdl_before=[100, -99, 0])
    )
    result = r.probability_metrics(rows + [failed], decisions)
    assert result["decisions"] == 6
    assert result["half_brier"] == pytest.approx(0.49)
    assert result["nll"] == pytest.approx(-math.log(0.2))
    assert r.chosen_prediction(decisions[0]) == [0.2, 0.3, 0.5]


@pytest.mark.parametrize(
    "value", ([0.2, 0.2, 0.2], [1.1, 0, -0.1], [float("nan"), 0, 0])
)
def test_nonprobability_predictions_rejected(value):
    rows = evaluation()
    with pytest.raises(ValueError):
        r.probability_metrics(rows, [prediction(rows[0], before=value)])


def test_duplicate_or_terminal_mismatch_prediction_rejected():
    rows = evaluation()
    sample = prediction(rows[0])
    with pytest.raises(ValueError, match="duplicate"):
        r.probability_metrics(rows, [sample, sample])
    sample["outcome"] = "L"
    with pytest.raises(ValueError, match="terminal result"):
        r.probability_metrics(rows, [sample])


def test_constant_reference_counts_normal_games_once():
    rows = evaluation(pairs=1)
    rows[0]["result"] = "loss"
    rows[1]["result"] = "draw"
    rows[2].update(status="incomplete", result=None)
    assert r.constant_reference(rows) == [3 / 5, 1 / 5, 1 / 5]
    assert r.constant_reference([]) is None


def test_dev_selection_never_selects_initial_ties_earlier_and_requires_complete():
    candidates = [{"model": "initial", "round": 0, "outcomes": evaluation("initial")}]
    assert r.select_policy(candidates) is None
    candidates += [
        {
            "model": f"round-{i}",
            "round": i,
            "outcomes": evaluation(f"round-{i}", result="draw"),
        }
        for i in (2, 1)
    ]
    incomplete = evaluation("round-3")
    incomplete[0].update(status="failed", result=None)
    candidates.append({"model": "round-3", "round": 3, "outcomes": incomplete})
    selected = r.select_policy(candidates)
    assert selected["model"] == "round-1" and selected["mean_score"] == 0.5


def test_calibration_adoption_strict_same_observations_and_complete():
    rows = evaluation()
    decisions = [prediction(row, after=[0.7, 0.2, 0.1]) for row in rows]
    selected = r.calibration_decision(rows, decisions)
    assert selected["adopt"] and selected["head"] == "after"
    assert selected["before"]["decisions"] == selected["after"]["decisions"] == 24
    for decision in decisions:
        decision["wdl_after"] = decision["wdl_before"]
    assert not r.calibration_decision(rows, decisions)["adopt"]
    assert not r.calibration_decision(rows, decisions, training_complete=False)[
        "complete"
    ]
    rows[0].update(status="failed", result=None)
    assert not r.calibration_decision(rows, decisions)["adopt"]


def test_paired_bootstrap_resamples_ten_complete_team_pairs_and_is_reproducible():
    initial, selected = (
        evaluation("initial", 10, "loss", "test"),
        evaluation("selected", 10, "loss", "test"),
    )
    for row in selected:
        if row["opponent"] == "initial":
            row["result"] = "win"
    result = r.paired_bootstrap(initial, selected)
    assert result["complete"] and result["improvement"]
    assert result["mean_difference"] == 0.75 and result["ci95"] == [0.75, 0.75]
    assert result["bootstrap"] == {
        "draws": 10000,
        "seed": 20261002,
        "unit": "team_pair",
        "estimator": "mean of complete paired team-pair opponent-weighted score differences",
    }
    selected[0].update(status="failed", result=None)
    partial = r.paired_bootstrap(initial, selected)
    assert (
        partial["available_pairs"] == 9
        and not partial["complete"]
        and not partial["improvement"]
    )
    assert partial == r.paired_bootstrap(initial, selected)
    selected[1]["simulator_seed"] = [9, 9, 9, 9]
    with pytest.raises(ValueError, match="seeds differ"):
        r.paired_bootstrap(initial, selected)


def test_summary_preserves_unattempted_and_separates_completion_from_improvement():
    rows = evaluation("initial", 10, "loss", "test") + evaluation(
        "selected", 10, "win", "test"
    )
    schedule = [
        {
            key: value
            for key, value in row.items()
            if key not in ("status", "result", "turns")
        }
        for row in rows
    ]
    summary = r.summarize(schedule, rows)
    assert summary["performance_improved"] and not summary["experiment_complete"]
    assert "gpu_preflight" in summary["incomplete_requirements"]
    assert "RLCD 보조 손실만" in r.report_markdown(summary)
    partial = r.summarize(schedule, rows[:-1])
    assert partial["unattempted"] == 1 and not partial["performance_improved"]
    invalid = copy.deepcopy(rows)
    invalid[0]["model_side"] = "p2"
    with pytest.raises(ValueError, match="frozen schedule"):
        r.summarize(schedule, invalid)
