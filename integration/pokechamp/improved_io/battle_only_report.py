"""D-030 denominators, recovery provenance and separate main-comparison review."""

from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from pathlib import Path

from .. import benchmark as b
from ..concurrency_metrics import request_metrics
from ..fallback_metrics import fallback_metrics
from . import battle_only_budget as budget
from . import experiment_policy as policy
from .battle_only_protocol import PROFILE, read_ref, ref


def summarize(schedule, attempts, *, invalid=(), superseded=()):
    """Keep legal completions regardless of explanation errors or poor outcomes."""
    invalid, superseded = set(invalid), set(superseded)
    valid, conditions = {}, {}
    for a in attempts:
        key = (a["cohort"], a["slot_id"])
        if a["eligible"] and key not in invalid and key not in superseded:
            if a["slot_id"] in valid:
                raise ValueError("duplicate valid completed slot across recovery")
            valid[a["slot_id"]] = a
    for condition in ("A", "B"):
        planned = [s for s in schedule if s["condition_id"] == condition]
        observed = [a for a in attempts if a["slot"]["condition_id"] == condition]
        completed = [
            a for a in valid.values() if a["slot"]["condition_id"] == condition
        ]
        by_opponent = {}
        for opponent in ("abyssal", "one_step"):
            results = Counter()
            for a in completed:
                if a["slot"]["pair"][1] != opponent:
                    continue
                actor = "p" + str(a["slot"]["methods"].index("io") + 1)
                results[a["actors"][actor]["outcome"]] += 1
            n = sum(results.values())
            by_opponent[opponent] = dict(
                wins=results["player_won"],
                draws=results["tied"],
                losses=results["player_lost"],
                valid_completed=n,
                score=(results["player_won"] + 0.5 * results["tied"]) / n
                if n
                else None,
            )
        scores = [v["score"] for v in by_opponent.values()]
        seen = {a["slot_id"] for a in observed}
        conditions[condition] = dict(
            planned=len(planned),
            attempted=len(observed),
            valid_completed=len(completed),
            completed_attempts=sum(a["eligible"] for a in observed),
            superseded_qualification=sum(
                (a["cohort"], a["slot_id"]) in superseded for a in observed
            ),
            failed=sum(
                not a["eligible"]
                and not a.get("uncertain", False)
                and (a["cohort"], a["slot_id"]) not in invalid
                for a in observed
            ),
            invalid=sum((a["cohort"], a["slot_id"]) in invalid for a in observed),
            uncertain=sum(a.get("uncertain", False) for a in observed),
            unexecuted=sum(s["slot_id"] not in seen for s in planned),
            unexecuted_slots=[
                s["slot_id"] for s in planned if s["slot_id"] not in seen
            ],
            recovery_attempts=sum(a["cohort"] == "c1" for a in observed),
            opponents=by_opponent,
            equally_weighted_score=statistics.mean(scores)
            if all(s is not None for s in scores)
            else None,
        )
    differences = {}
    paired_ids = sorted({s["paired_slot_id"] for s in schedule})
    for key in paired_ids:
        if all(c + "-" + key in valid for c in ("A", "B")):
            scores = []
            for c in ("A", "B"):
                a = valid[c + "-" + key]
                actor = "p" + str(a["slot"]["methods"].index("io") + 1)
                scores.append(
                    {"player_won": 1, "player_lost": 0, "tied": 0.5}[
                        a["actors"][actor]["outcome"]
                    ]
                )
            differences[key] = scores[1] - scores[0]
    return dict(
        conditions=conditions,
        completed_pairs=len(differences),
        paired_differences=differences,
        mean_paired_difference=statistics.mean(differences.values())
        if differences
        else None,
        missing_pairs=[p for p in paired_ids if p not in differences],
    )


def report(study, output, *, review=None):
    study = Path(study)
    registration = b.read_sealed(study / "study.json")
    if registration["profile"] != PROFILE:
        raise ValueError("foreign study")
    first = b.read_sealed(study / "cohorts/c0.json")
    prepared = Path(first["prepared"]["path"])
    read_ref(first["prepared"])
    manifest = b.read_sealed(prepared.parent / "manifest.json")
    selection = policy.same(registration, first, manifest)
    experiment_id = (
        selection["experiment_policy_identity"]["experiment_id"]
        if selection
        else "EX-026"
    )
    correction = {}
    if policy.is_calcfix(selection):
        from .calcfix32 import defect_correction

        correction = defect_correction(study, manifest)
    recovery = (
        b.read_sealed(study / "recovery-c1.json")
        if (study / "recovery-c1.json").exists()
        else None
    )
    stages, all_calls, review_calls, all_attempts, bundles, batches = (
        {},
        [],
        {},
        [],
        {},
        [],
    )
    for stage in ("cloud_gate", "smoke8", "compare32"):
        if policy.is_direct(selection) and stage != "compare32":
            stages[stage] = dict(status="skipped_by_user", planned=0)
            continue
        attempts, collections = [], []
        for claim_path in sorted((study / "cohorts").glob(f"*-{stage}.json")):
            claim = b.read_sealed(claim_path)
            directory = Path(claim["output"])
            if stage == "cloud_gate":
                if (directory / "collection.json").exists():
                    collections.append(
                        dict(
                            cohort=claim["cohort"],
                            collection=b.read_sealed(directory / "collection.json"),
                            reference=ref(directory / "collection.json"),
                            result=b.read_sealed(directory / "result.json")
                            if (directory / "result.json").exists()
                            else None,
                        )
                    )
                continue
            if not (directory / "benchmark.json").exists():
                continue
            target_ref = b.read_sealed(directory / "benchmark.json")
            value = read_ref(target_ref)
            target = Path(target_ref["path"]).parent
            b.verify_plan(target)
            observed = []
            for attempt_path in sorted((target / "attempts").glob("*/result.json")):
                attempt = b.read_sealed(attempt_path)
                for name, checksum in attempt["source_checksums"].items():
                    if b.digest(attempt_path.parent / name) != checksum:
                        raise ValueError("attempt source drift")
                observed.append(attempt)
            b.validate_attempts(value, observed)
            known = {a["slot_id"] for a in observed}
            for path in (target / "attempts").glob("*/request.json"):
                request = b.read_sealed(path)
                if request["slot"]["slot_id"] not in known:
                    observed.append(
                        dict(
                            slot=request["slot"],
                            slot_id=request["slot"]["slot_id"],
                            eligible=False,
                            category="uncertain",
                            uncertain=True,
                            actors={},
                        )
                    )
            for a in observed:
                a = dict(a, cohort=claim["cohort"])
                attempts.append(a)
                for role, actor in a["actors"].items():
                    if not actor.get("bundle"):
                        continue
                    bundle = Path(actor["bundle"])
                    if not b.verify_bundle(bundle)["valid"]:
                        raise ValueError("report actor seal drift")
                    bundles[str(bundle)] = b.digest(bundle / "events.jsonl")
                    for line in (bundle / "events.jsonl").read_text().splitlines():
                        e = json.loads(line)
                        if e["event_type"] != "llm_call":
                            continue
                        all_calls.append(e)
                        if a["slot"]["condition_id"] == "B":
                            key = str(bundle) + ":" + str(e["event_seq"])
                            review_calls[key] = dict(
                                stage=stage,
                                cohort=claim["cohort"],
                                slot=a["slot_id"],
                                actor=role,
                                event_seq=e["event_seq"],
                                events_sha256=b.digest(bundle / "events.jsonl"),
                                rationale=e.get("raw_content"),
                                eligible=a["eligible"],
                            )
            batches.extend(
                dict(b.read_sealed(p), stage=stage, cohort=claim["cohort"])
                for p in (target / "batches").glob("*.json")
            )
        invalid = (
            [("c0", s) for s in recovery["impact"].get(stage, [])] if recovery else []
        )
        if stage == "compare32" and correction:
            invalid.extend(("c0", slot) for slot in correction["invalid_slots"])
        if stage != "cloud_gate":
            scheduled = manifest[
                "smoke_schedule" if stage == "smoke8" else "compare_schedule"
            ]
            superseded = (
                [("c0", s) for s in recovery.get("requalification", {}).get(stage, [])]
                if recovery
                else []
            )
            stages[stage] = summarize(
                scheduled, attempts, invalid=invalid, superseded=superseded
            )
            all_attempts.extend(attempts)
        else:
            stages[stage] = dict(
                planned=90,
                collections=collections,
                collected=sum(
                    c["collection"].get("new_responses", c["collection"]["responses"])
                    for c in collections
                ),
                passed=any(c["result"] and c["result"]["passed"] for c in collections),
            )
    factual_review = dict(
        planned=len(review_calls),
        reviewed=0,
        errors=None,
        error_rate=None,
        pending=list(review_calls),
    )
    if review is not None:
        audit = b.read_sealed(review)
        if audit.get("bundles") != bundles or set(audit.get("calls", {})) != set(
            review_calls
        ):
            raise ValueError("battle explanation review denominator/source mismatch")
        errors = []
        for key, item in audit["calls"].items():
            if not isinstance(item.get("evidence"), str) or len(item["evidence"]) < 20:
                raise ValueError("battle review evidence missing")
            if not all(
                type(item.get(d)) is bool
                for d in ("facts", "identity", "timing", "calculation")
            ):
                raise ValueError("battle review dimensions missing")
            if not all(item[d] for d in ("facts", "identity", "timing", "calculation")):
                errors.append(key)
        factual_review.update(
            reviewed=len(review_calls),
            errors=errors,
            error_rate=len(errors) / len(review_calls) if review_calls else None,
            pending=[],
            reference=ref(review),
        )
    if policy.is_direct(selection):
        explanations = {
            k for k, v in review_calls.items() if v["rationale"] is not None
        }
        factual_review.update(
            collected_explanations=len(explanations),
            no_response_calls=len(review_calls) - len(explanations),
            reviewed_explanations=len(explanations) if review is not None else 0,
            error_rate=(
                len(set(factual_review["errors"]) & explanations) / len(explanations)
                if review is not None and explanations
                else None
            ),
        )
    usage = budget.usage(study)
    tokens = Counter()
    for path in (study / "requests").glob("response-*.json"):
        row = b.read_sealed(path)
        read_ref(row["intent"])
        for name in ("prompt_eval_count", "eval_count"):
            value = row["response"].get(name)
            if isinstance(value, int):
                tokens[name] += value
    primary = stages["compare32"]
    completed = (
        (
            policy.is_direct(selection)
            or (
                stages["cloud_gate"]["passed"]
                and sum(
                    c["valid_completed"]
                    for c in stages["smoke8"]["conditions"].values()
                )
                == 8
            )
        )
        and primary["completed_pairs"] == 16
        and factual_review["reviewed"] == len(review_calls)
        and not usage["uncertain"]
    )
    result = dict(
        profile=PROFILE,
        **selection,
        experiment_id=experiment_id,
        input_defect_correction=correction,
        clock=budget.clock(study) if (study / "cloud-clock.json").exists() else None,
        elapsed_since_first_cloud_seconds=(
            time.time() - budget.clock(study)["first_dispatch_at"]
            if (study / "cloud-clock.json").exists()
            else None
        ),
        exploratory=True,
        comparison_complete=completed,
        resource_cleanup="requires independent closure verification",
        stages=stages,
        usage=usage,
        confirmed_tokens=dict(tokens),
        battle_explanation_review=factual_review,
        review_inventory=review_calls,
        bundles=bundles,
        recovery=recovery,
        evaluation_recoveries=[
            b.read_sealed(p) for p in (study / "analyses").glob("*.json")
        ],
        request_metrics=request_metrics(all_calls),
        batch_elapsed_seconds=sum(v["elapsed_seconds"] for v in batches),
        batches=batches,
        upstream_fallback=fallback_metrics(
            [a for a in all_attempts if a["slot"]["condition_id"] == "A"]
        ),
        categories=dict(
            Counter(a.get("category") for a in all_attempts if a.get("category"))
        ),
        halts=[b.read_sealed(p) for p in study.glob("halt-*.json")],
    )
    output.mkdir(parents=True, exist_ok=False)
    if policy.is_direct(selection):
        from .direct32_report import extend

        result.update(
            extend(manifest, all_attempts, review_calls, review, output, batches)
        )
    if policy.is_movefix(selection):
        from .movefix32 import cumulative_report, verify_runtime

        result.update(verify_runtime(manifest))
        result["linked_repeat"] = cumulative_report(manifest, result)
    elif policy.is_inputfix(selection):
        from .inputfix32 import cumulative_report, verify_runtime

        result.update(verify_runtime(manifest))
        result["linked_repeat"] = cumulative_report(manifest, result)
    elif policy.is_calcfix(selection):
        from .calcfix32 import cumulative_report

        result["linked_repeat"] = cumulative_report(manifest, result)
    b.seal_json(output / "report.json", result)
    call_limit_label = (
        usage["call_limit"] if usage["call_limit"] is not None else "상한 없음"
    )
    lines = [
        f"# {experiment_id} — 요약 없는 improved_io A/B 비교",
        "",
        "유효 비교 완료."
        if completed
        else "미완료. 충족된 구현·수집·검토 범위를 분리한다.",
        "",
        "본 비교에는 점검 배틀과 과거 결과를 합치지 않는다. "
        "전체 B 구성의 탐색적 비교이며",
        "전투 prompt 단독 효과 또는 L1-L5 전체 효능을 추정하지 않는다.",
        "",
        "| 조건 | 예정 | 시도 | 유효 | 실패 | 무효 | 미실행 | 미확정 | 복구 시도 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for condition, row in primary["conditions"].items():
        lines.append(
            "| "
            + " | ".join(
                map(
                    str,
                    [condition]
                    + [
                        row[k]
                        for k in (
                            "planned",
                            "attempted",
                            "valid_completed",
                            "failed",
                            "invalid",
                            "unexecuted",
                            "uncertain",
                            "recovery_attempts",
                        )
                    ],
                )
            )
            + " |"
        )
    lines += [
        "",
        f"유효 대응 {primary['completed_pairs']}/16; "
        f"누락 {len(primary['missing_pairs'])}.",
        f"대응 B−A 평균: {primary['mean_paired_difference']}.",
        "",
        (
            f"총 요청 예약 {usage['reserved_calls']}/{call_limit_label}, "
            f"응답 {usage['responses']}, "
            f"미확정 {usage['uncertain']}."
        ),
        f"확정 입력/출력 tokens: {tokens['prompt_eval_count']}/{tokens['eval_count']}.",
        f"B 배틀 설명 검토: {factual_review['reviewed']}/{len(review_calls)}.",
        "",
        "단계·상대별 성적, 복구 및 오류 근거·비용·HTTP·fallback은 "
        "report.json에 연결했다.",
        "자원 정리와 이전 자료 보존은 별도 closure 검증이 필요하다.",
    ]
    if policy.is_direct(selection):
        fallback_count = result["upstream_fallback"]["all_attempts"]["io"][
            "sent_fallback_decisions"
        ]
        http_overlap = result["request_metrics"]["maximum_account_http_overlap"]
        lines += [
            "",
            f"32 slot 처리: {result['slots_processed']}/32; "
            f"자연 종료: {result['natural_completions']}/32.",
            (
                "EP-025 593회귀·독립28조건/16roll·81재생 봉인 재사용; "
                "새 실행 연결 변경분 검사 통과(최종 전체 회귀 재실행 아님); "
                "별도fake32·Cloud90·smoke8 생략."
                if policy.is_movefix(selection)
                else "EX-030 독립 검증·636재생 연결 및 새 정책 로컬 회귀·전달 통과; "
                "별도fake32·Cloud90·smoke8 생략."
                if policy.is_inputfix(selection)
                else "필수 결함·독립검증·회귀 통과; 15장면·fake32·Cloud90·smoke8 생략."
                if policy.is_calcfix(selection)
                else "사전 회귀·15장면·fake32·Cloud90·smoke8: skipped_by_user."
            ),
            "오류 처리 정책을 포함한 전체 구성의 개발 대진 탐색 비교다.",
            f"정상 출력만 있었던 유효 경기: {result['normal_output_completed_games']}.",
            "[32경기 목록](matches.html) · [상세 지표](report.json)",
        ]
        lines += [
            "",
            "| 조건 | 상대 | 승 | 패 | 무 | 유효 | 점수 |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for condition, row in primary["conditions"].items():
            for opponent, score in row["opponents"].items():
                lines.append(
                    f"| {condition} | {opponent} | {score['wins']} | "
                    f"{score['losses']} | "
                    f"{score['draws']} | {score['valid_completed']} | "
                    f"{score['score']} |"
                )
        for condition, row in primary["conditions"].items():
            lines += [
                "",
                f"{condition} 두 상대 동일 가중 평균: {row['equally_weighted_score']}.",
                "",
            ]
        lines += [
            f"B 원문 설명 {factual_review['reviewed_explanations']}/"
            f"{factual_review['collected_explanations']} 검토; "
            f"무응답 {factual_review['no_response_calls']}건은 설명 오류율에서 제외.",
            f"설명 오류율: {factual_review['error_rate']}; "
            f"차원별 중복 포함: {result['explanation_error_dimensions']}.",
            f"B 선택 출처: {result['b_action_sources']}.",
            f"B 실제 전송 출처: {result['b_sent_action_sources']}.",
            f"A 실제 fallback: {fallback_count}회.",
            "",
            "| 조건 | 요청 | 원문 응답 | 입력 token | 출력 token | HTTP 누적 초 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for condition, metrics in result["condition_request_metrics"].items():
            lines.append(
                f"| {condition} | {metrics['calls']} | {metrics['responses']} | "
                f"{metrics['prompt_tokens']} | {metrics['completion_tokens']} | "
                f"{metrics['cumulative_http_seconds']} |"
            )
        lines += [
            "",
            f"배틀 수집 벽시계: {result['batch_elapsed_seconds']:.3f}초.",
            f"실측 계정 HTTP 최대 동시성: {http_overlap}.",
            "timeout 요청의 provider 실행·청구·token은 미확정으로 남겼다. "
            "확정 token 합계는 하한이며 provider 청구금액 자료가 없어 "
            "금액을 산출하지 않는다.",
            f"재시도·재수집0. 완료 대응 {primary['completed_pairs']}/16쌍.",
        ]
    if policy.is_linked_repeat(selection):
        linked = result["linked_repeat"]
        original_elapsed = linked["elapsed_since_original_first_cloud_seconds"]
        lines += [
            "",
            "연결된 과거 실험과 새 실행은 독립 표본으로 합산하지 않는다. "
            "기존 비교는 별도 결함 정정 분석을 따른다.",
            f"원본 사용량 미확정 {linked['original_uncertain_requests']}건 보존; "
            f"누적 요청/응답/미확정: {linked['cumulative_usage']}.",
            f"누적 확정 token: {linked['cumulative_confirmed_tokens']}.",
            f"누적 수집 시간 {linked['cumulative_collection_seconds']:.3f}초; "
            f"원본 최초 Cloud부터 경과 {original_elapsed:.3f}초.",
        ]
    if correction:
        lines += [
            "",
            "공유 계산 결함으로 수집을 중단했다. 위 유효 성적은 영향 경기를 제외한다.",
            f"재등장 특성 입력 결함: {correction['changed_inputs']}입력, "
            f"{len(correction['invalid_slots'])}경기 및 의존 대응 비교 무효.",
            "자연 종료와 입력이 유효한 완료는 다르며, "
            "중단 전 원관측 성적은 별도 보존한다.",
            "수집 source의 재등장 결함은 미수정이다. "
            "추가 수집/재시도는 수행하지 않았다.",
            "자세한 최초 오염과 source/독립 재현은 "
            "defects/reentry-impact.json에 연결했다.",
        ]
    (output / "report.md").write_text("\n".join(lines) + "\n")
    return result
