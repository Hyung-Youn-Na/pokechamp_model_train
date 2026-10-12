"""Blind review packaging and scene-paired descriptive estimates, with explicit missingness."""

from __future__ import annotations

import json
import shutil
import statistics
from pathlib import Path

from .. import benchmark as b
from ..improved_io.memory import validate_summary
from .prepare import MAX_PROFILE, THINKING_PROFILE, conditions, verify
from .runner import inventory

KINDS = {"critical_fact", "factual", "unsupported", "contradiction", "format"}


def blind(directory, manifest, collection):
    rows = []
    for slot in sorted(collection["slots"], key=lambda s: s["blind_id"]):
        if not slot["acquired"]:
            continue
        path = directory / "responses" / f"{slot['id']}.json"
        response = b.read_sealed(path)
        rows.append(
            {
                "blind_id": slot["blind_id"],
                "scene": slot["scene"],
                "text": response["trace"]["raw_content"],
                "response_sha256": b.digest(path),
            }
        )
    package = {
        "manifest_sha256": b.digest(directory / "manifest.json"),
        "collection_sha256": b.digest(directory / "collection.json"),
        "responses": rows,
        "rubric": b.read_sealed(directory / "rubric.json"),
        "references": {
            str(s["scene"]): b.read_sealed(directory / s["reference"]) for s in manifest["scenes"]
        },
    }
    path = directory / "blind.json"
    if path.exists():
        if b.read_sealed(path) != package:
            raise ValueError("blind package drift")
    else:
        b.seal_json(path, package)
    return package


def check_review(package, review):
    if review.get("collection_sha256") != package["collection_sha256"]:
        raise ValueError("review collection mismatch")
    if review.get("manifest_sha256") != package["manifest_sha256"]:
        raise ValueError("review manifest mismatch")
    expected = {r["blind_id"]: r for r in package["responses"]}
    if set(review.get("calls", {})) != set(expected):
        raise ValueError("review response denominator mismatch")
    checked = {}
    for blind_id, response in expected.items():
        row = review["calls"][blind_id]
        reference = package["references"][str(response["scene"])]
        if row["response_sha256"] != response["response_sha256"]:
            raise ValueError("review response hash mismatch")
        truth = {f["id"]: f for f in reference["facts"]}
        if set(row["facts"]) != set(truth):
            raise ValueError("required fact denominator mismatch")
        for fact in row["facts"].values():
            status = fact.get("status", "retained" if fact["retained"] else "omitted")
            if status not in ("retained", "incorrect", "omitted") or (
                (status == "retained") != fact["retained"]
            ):
                raise ValueError("fact status disagrees with retention")
            if type(fact["retained"]) is not bool:
                raise ValueError("review fact must be explicit bool")
            if fact["retained"] and (not fact["quote"] or fact["quote"] not in response["text"]):
                raise ValueError("retained fact requires exact response quotation")
        evidence = {e["event_seq"]: e["protocol"].splitlines() for e in reference["source_events"]}
        for error in row["errors"]:
            if error["kind"] not in KINDS or not error["explanation"]:
                raise ValueError("invalid review error")
            if error["quote"] not in response["text"]:
                raise ValueError("error quotation not in response")
            if error["kind"] != "format" and (not error["quote"] or not error["evidence"]):
                raise ValueError("factual error requires original evidence")
            for ref in error["evidence"]:
                if ref["event"] not in evidence or not 1 <= ref["line"] <= len(
                    evidence[ref["event"]]
                ):
                    raise ValueError("review reference outside original evidence")
        for fact_id, fact in row["facts"].items():
            if fact.get("status") == "incorrect" and not any(
                fact_id in error.get("fact_ids", []) and error["kind"] != "format"
                for error in row["errors"]
            ):
                raise ValueError("incorrect required fact lacks linked error evidence")
        claims, wrong = row["factual_claims"], row["erroneous_claims"]
        if type(claims) is not int or type(wrong) is not int or not 0 <= wrong <= claims:
            raise ValueError("invalid claim counts")
        if any(e["kind"] != "format" for e in row["errors"]) and wrong == 0:
            raise ValueError("errors missing from claim numerator")
        format_error = None
        try:
            validate_summary(
                response["text"],
                battle_id=reference["identity"]["battle_id"],
                actor_id=reference["identity"]["actor_id"],
                event_ids=list(evidence),
            )
        except ValueError as exc:
            format_error = str(exc)
        not_retained = sum(not f["retained"] for f in row["facts"].values())
        omitted = sum(
            not f["retained"] and f.get("status", "omitted") == "omitted"
            for f in row["facts"].values()
        )
        critical = any(
            e["kind"] == "critical_fact" or e.get("critical", False) for e in row["errors"]
        )
        violated = format_error is not None or any(e["kind"] == "format" for e in row["errors"])
        factual = any(e["kind"] != "format" for e in row["errors"])
        primary_error = (
            factual if package.get("rubric", {}).get("primary_all_factual_errors") else critical
        )
        checked[blind_id] = {
            "primary": int(primary_error or omitted > 0 or violated),
            "critical": int(critical),
            "omission": int(omitted > 0),
            "format": int(violated),
            "retained": len(truth) - not_retained,
            "omitted_facts": omitted,
            "incorrect_facts": not_retained - omitted,
            "required": len(truth),
            "retention": (len(truth) - not_retained) / len(truth),
            "factual_claims": claims,
            "erroneous_claims": wrong,
            "unsupported": sum(e["kind"] == "unsupported" for e in row["errors"]),
            "contradictions": sum(e["kind"] == "contradiction" for e in row["errors"]),
            "format_reason": format_error,
        }
        if package.get("rubric", {}).get("primary_all_factual_errors"):
            checked[blind_id]["factual"] = int(factual)
    return checked


def mean(values):
    return statistics.mean(values) if values else None


def contrasts_for(manifest):
    return (
        (("low", "high"),)
        if manifest.get("profile") == THINKING_PROFILE
        else (("H0", "H1"), ("H2", "H3"), ("H0", "H2"), ("H1", "H3"), ("H0", "H3"))
    )


def aggregate(manifest, collection, checked, responses):
    scene_means = {}
    cost = {}
    for condition in conditions(manifest):
        slots = [s for s in collection["slots"] if s["condition"] == condition]
        acquired = [responses[s["id"]] for s in slots if s["id"] in responses and s["acquired"]]
        traces = [r["trace"]["response"] for r in acquired]
        cost[condition] = {
            "scheduled": len(slots),
            "submitted": sum(s["submitted"] for s in slots),
            "acquired": len(acquired),
            "failed": sum(s["failed"] for s in slots),
            "unexecuted": sum(s["unexecuted"] for s in slots),
            "unconfirmed": sum(s["unconfirmed"] for s in slots),
            "prompt_tokens": sum(
                t["prompt_tokens"] for t in traces if t.get("prompt_tokens") is not None
            ),
            "completion_tokens": sum(
                t["completion_tokens"] for t in traces if t.get("completion_tokens") is not None
            ),
            "http_ms_mean": mean(
                [t["http_elapsed_ms"] for t in traces if t.get("http_elapsed_ms") is not None]
            ),
            "request_elapsed_ms_mean": mean([t["elapsed_ms"] for t in traces]),
            "tokens_complete": all(s["acquired"] for s in slots if s["submitted"])
            and all(
                t.get("prompt_tokens") is not None and t.get("completion_tokens") is not None
                for t in traces
            ),
            "unknown_token_responses": sum(
                t.get("prompt_tokens") is None or t.get("completion_tokens") is None for t in traces
            ),
            "condition_wall_span_seconds": (
                max(r["finished_at"] for r in acquired) - min(r["started_at"] for r in acquired)
                if acquired
                else None
            ),
        }
        for scene in manifest["scenes"]:
            sample = [
                checked[s["blind_id"]]
                for s in slots
                if s["scene"] == scene["scene"] and s["blind_id"] in checked
            ]
            scene_means[scene["scene"], condition] = {
                "n": len(sample),
                **{
                    k: mean([r[k] for r in sample])
                    for k in ("primary", "critical", "omission", "format", "retention")
                },
                "factual_claims": sum(r["factual_claims"] for r in sample),
                "erroneous_claims": sum(r["erroneous_claims"] for r in sample),
                "unsupported": sum(r["unsupported"] for r in sample),
                "contradictions": sum(r["contradictions"] for r in sample),
            }
    strata = {}
    for stratum in ("existing", "additional"):
        scene_ids = [s["scene"] for s in manifest["scenes"] if s["stratum"] == stratum]
        summaries = {}
        for condition in conditions(manifest):
            complete = [
                scene_means[i, condition] for i in scene_ids if scene_means[i, condition]["n"] == 3
            ]
            summaries[condition] = {
                "complete_scenes": len(complete),
                "scheduled_scenes": len(scene_ids),
                **{
                    k: mean([r[k] for r in complete])
                    for k in ("primary", "critical", "omission", "format", "retention")
                },
                **{
                    k: sum(r[k] for r in complete)
                    for k in ("factual_claims", "erroneous_claims", "unsupported", "contradictions")
                },
            }
        contrasts = {}
        for a, c in contrasts_for(manifest):
            paired = [i for i in scene_ids if scene_means[i, a]["n"] == scene_means[i, c]["n"] == 3]
            contrasts[a + "->" + c] = {
                "paired_scenes": len(paired),
                "missing_pairs": len(scene_ids) - len(paired),
                **{
                    k + "_difference": mean(
                        [scene_means[i, c][k] - scene_means[i, a][k] for i in paired]
                    )
                    for k in ("primary", "critical", "omission", "retention")
                },
            }
        four = [
            i
            for i in scene_ids
            if manifest.get("profile") != THINKING_PROFILE
            and all(scene_means[i, c]["n"] == 3 for c in conditions(manifest))
        ]
        interaction = mean(
            [
                scene_means[i, "H3"]["primary"]
                - scene_means[i, "H2"]["primary"]
                - scene_means[i, "H1"]["primary"]
                + scene_means[i, "H0"]["primary"]
                for i in four
            ]
        )
        strata[stratum] = {
            "conditions": summaries,
            "contrasts": contrasts,
            "interaction_primary": interaction,
            "four_way_paired_scenes": len(four),
        }
    return {
        "strata": strata,
        "cost": cost,
        "scene_means": {f"s{i:02}-{c}": value for (i, c), value in scene_means.items()},
    }


def report(directory, review=None):
    directory = Path(directory).resolve()
    if b.read_sealed(directory / "manifest.json").get("profile") == MAX_PROFILE:
        from .maximum_report import report_maximum

        return report_maximum(directory, review)
    halt_path = directory / "halt.json"
    halt = b.read_sealed(halt_path) if halt_path.exists() else None
    invalidated = halt and halt["reason"] in {"input_transform_error", "evaluation_reference_error"}
    # A newer oracle must reject the old bad input for execution, while its
    # hash-verified forensic report remains readable. invalid_report validates
    # the sealed failure and its manifest/collection bindings before returning.
    manifest = verify(directory, current=False, validate_semantics=not invalidated)
    collection = b.read_sealed(directory / "collection.json")
    current = inventory(directory, manifest)
    if current["slots"] != collection["slots"]:
        raise ValueError("response inventory changed after collection seal")
    if invalidated:
        if review is not None:
            raise ValueError("invalidated inputs/reference: review cannot restore comparison")
        return invalid_report(directory, manifest, collection, halt)
    package = blind(directory, manifest, collection)
    if review is None:
        return {
            "review": "pending",
            "blind_package": str(directory / "blind.json"),
            "scheduled": len(manifest["schedule"]),
            "acquired": collection["acquired"],
        }
    audit = b.read_sealed(Path(review))
    checked = check_review(package, audit)
    responses = {
        s["id"]: b.read_sealed(directory / "responses" / f"{s['id']}.json")
        for s in collection["slots"]
        if s["response_record"]
    }
    metrics = aggregate(manifest, collection, checked, responses)
    result = {
        "complete": len(checked) == len(manifest["schedule"])
        and collection["acquired"] == len(manifest["schedule"])
        and not collection.get("reason")
        and not halt_path.exists(),
        "fake": collection["fake"],
        "reviewed": len(checked),
        "counts": {
            k: collection[k]
            for k in (
                "scheduled",
                "intended",
                "submitted",
                "acquired",
                "failed",
                "unexecuted",
                "unconfirmed",
            )
        },
        "batch_elapsed_seconds": collection["elapsed_seconds"],
        "metrics": metrics,
        "collection_sha256": b.digest(directory / "collection.json"),
        "review_sha256": b.digest(Path(review)),
        "checks": checked,
    }
    # Analysis-only correction provenance: never rewrite the prepared Cloud source.
    source_differences = {}
    for name, prepared_digest in manifest["source_files"].items():
        current_digest = b.digest(Path(name))
        if current_digest != prepared_digest:
            relative = Path(name).relative_to(b.WORKSPACE_ROOT)
            target = directory / "analysis-source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(name, target)
            source_differences[str(relative)] = {
                "prepared": prepared_digest,
                "analysis": current_digest,
            }
    result["analysis_source_differences"] = source_differences
    fact_counts, error_counts = {}, {}
    for slot in collection["slots"]:
        if slot["blind_id"] not in checked:
            continue
        audit_row = audit["calls"][slot["blind_id"]]
        for fact_id, fact in audit_row["facts"].items():
            key = f"s{slot['scene']:02}:{fact_id}"
            fact_counts.setdefault(
                key,
                {c: {"retained": 0, "incorrect": 0, "omitted": 0} for c in conditions(manifest)},
            )
            status = fact.get("status", "retained" if fact["retained"] else "omitted")
            fact_counts[key][slot["condition"]][status] += 1
        for code in {e.get("code", e["kind"]) for e in audit_row["errors"]}:
            key = f"s{slot['scene']:02}:{code}"
            error_counts.setdefault(key, {c: 0 for c in conditions(manifest)})
            error_counts[key][slot["condition"]] += 1
    result["fact_counts"] = fact_counts
    result["error_recurrence"] = error_counts
    b.seal_json(directory / "review.json", audit)
    b.seal_json(directory / "report.json", result)
    lines = [f"# {manifest['experiment']} 요약 진단", "", "## 오류 문장 → 원본 근거", ""]
    for response in package["responses"]:
        row = audit["calls"][response["blind_id"]]
        if not row["errors"]:
            continue
        lines.append(f"### {response['blind_id']} / scene {response['scene']}")
        for error in row["errors"]:
            refs = ", ".join(f"event {r['event']} line {r['line']}" for r in error["evidence"])
            lines.extend(
                ["", f"> {error['quote']}", "", f"{error['kind']}: {error['explanation']} ({refs})"]
            )
    lines.extend(
        [
            "",
            "## 조건별 재현 횟수·오류·누락 변화",
            "",
            "차이는 뒤 조건−앞 조건이다. 완전한 3반복 장면만 대응 비교한다.",
            "",
            "|자료|조건|장면|주지표|중요 오류|누락|형식|필수 보존율|",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for stratum, values in metrics["strata"].items():
        for condition, value in values["conditions"].items():
            nums = [
                "미확정" if value[k] is None else f"{value[k]:.3f}"
                for k in ("primary", "critical", "omission", "format", "retention")
            ]
            lines.append(
                f"|{stratum}|{condition}|{value['complete_scenes']}|" + "|".join(nums) + "|"
            )
    lines.extend(
        [
            "",
            "### 오류 유형별 조건별 재현 요약 수",
            "",
            "|장면:오류 코드|" + "|".join(conditions(manifest)) + "|",
            "|---|" + "---:|" * len(conditions(manifest)),
        ]
    )
    for key, counts in sorted(error_counts.items()):
        lines.append("|" + key + "|" + "|".join(str(counts[c]) for c in conditions(manifest)) + "|")
    lines.extend(
        [
            "",
            "대응 대비·결합 차이 및 장면별 수치는 report.json에 기록한다.",
            "",
            "## 분모와 비용",
            "",
            "```json",
            json.dumps(
                {
                    "counts": result["counts"],
                    "cost": metrics["cost"],
                    "batch_elapsed_seconds": result["batch_elapsed_seconds"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "## 해석 한계",
            "",
            "기존4/추가8 모두 같은 개발 자료다. 단일 모델·고정 seed의3반복이며 "
            "반복을 독립 장면으로 세지 않는다.",
            "검토자는 연구 설계를 알고 있는 단일 검토자다. "
            "조건명이 가려져도 완전한 독립 이중맹검은 아니다.",
            "차이가 없거나 오류가 남아도 모델 성능 한계를 확정하지 않는다. "
            "누락 증가와 함께 해석한다.",
            "조건별 wall span은 교차 제출 기간이므로 합산하지 않는다. "
            "HTTP/provider 내부 병렬성은 구별한다.",
            "EX-020/EP-011은 중단 상태이며 운영 적용·재개는 별도 결정이다.",
        ]
    )
    (directory / "report.md").write_text("\n".join(lines) + "\n")
    b.seal_json(
        directory / "report-seal.json",
        {
            "report.md": b.digest(directory / "report.md"),
            "report.json": b.digest(directory / "report.json"),
            "review.json": b.digest(directory / "review.json"),
        },
    )
    return {
        "complete": result["complete"],
        "reviewed": len(checked),
        "report": str(directory / "report.md"),
    }


def invalid_report(directory, manifest, collection, halt):
    """Preserve costs and failure evidence without estimating invalid treatment effects."""
    evidence_path = directory / halt["evidence"]
    if evidence_path.parent != directory or b.digest(evidence_path) != halt["evidence_sha256"]:
        raise ValueError("halt evidence mismatch")
    evidence = b.read_sealed(evidence_path)
    for name in ("manifest", "collection"):
        if evidence[name + "_sha256"] != b.digest(directory / (name + ".json")):
            raise ValueError("halt provenance mismatch")
    if (directory / "report-seal.json").exists():
        for name, digest in b.read_sealed(directory / "report-seal.json").items():
            if b.digest(directory / name) != digest:
                raise ValueError("invalid report drift")
        result = b.read_sealed(directory / "report.json")
        if result.get("halt_sha256") != b.digest(directory / "halt.json"):
            raise ValueError("report predates invalidation")
        return {"complete": False, "status": "invalidated", "report": str(directory / "report.md")}
    responses = {
        s["id"]: b.read_sealed(directory / "responses" / f"{s['id']}.json")
        for s in collection["slots"]
        if s["response_record"]
    }
    cost = aggregate(manifest, collection, {}, responses)["cost"]
    result = {
        "complete": False,
        "status": "invalidated",
        "reason": halt["reason"],
        "fake": collection["fake"],
        "counts": {
            k: collection[k]
            for k in (
                "scheduled",
                "intended",
                "submitted",
                "response_record",
                "acquired",
                "failed",
                "unexecuted",
                "unconfirmed",
            )
        },
        "reviewed_draft_invalid": evidence["reviewed_draft"],
        "review_pending": evidence["review_pending"],
        "valid_reviewed": 0,
        "effect_estimates": None,
        "paired_scenes": {
            group: {
                "planned": sum(s["stratum"] == group for s in manifest["scenes"]),
                "valid": 0,
                "missing": sum(s["stratum"] == group for s in manifest["scenes"]),
                "applies_to": [a + "->" + c for a, c in contrasts_for(manifest)],
            }
            for group in ("existing", "additional")
        },
        "cost": cost,
        "batch_elapsed_seconds": collection["elapsed_seconds"],
        "runtime_output_contract_records": sum(
            r["category"] == "output_contract" for r in responses.values()
        ),
        "halt_sha256": b.digest(directory / "halt.json"),
        "evidence_sha256": b.digest(evidence_path),
        "manifest_sha256": b.digest(directory / "manifest.json"),
        "collection_sha256": b.digest(directory / "collection.json"),
    }
    if manifest.get("profile") == THINKING_PROFILE:
        return invalid_thinking_report(directory, manifest, evidence, result)
    lines = [
        "# EX-021 중단 보고서",
        "",
        "Status: Blocked / invalidated / 진단 미완료",
        "",
        f"{collection['acquired']}응답 수집 후 입력 변환 오류가 확인되어 전체 비교를 중단했다. "
        "오류율·누락률·harness 효과는 산출하지 않는다.",
        "",
        "## 오류 문장 → 원본 근거",
        "",
        "H1/H3가 weather 숫자를 `activation_turn`으로 잘못 명명했다. "
        "pinned parser는 upkeep을 포함한 매 `-weather`에서 `self.turn`으로 값을 갱신한다.",
        "",
    ]
    example = evidence.get("model_example")
    if example:
        lines.extend(
            [
                f"> {example['quote']}",
                "",
                f"응답 {example['blind_id']} ({example['schedule']['id']})에서 입력의 잘못된 "
                "시점을 그대로 인용했다. 이는 발견 사례이며 전체 재현율이 아니다.",
                "",
            ]
        )
    for scene in evidence.get("affected_scenes", []):
        start, last = scene["actual_activation"], scene["last_update"]
        lines.extend(
            [
                f"- scene {scene['scene']} ({scene['name']}): 실제 시작 turn {start['turn']} "
                f"(event {start['event']} line {start['line']}); 마지막 upkeep turn {last['turn']} "
                f"(event {last['event']} line {last['line']}). 원본 상태 {scene['weather_raw']}.",
            ]
        )
    reference_error = evidence.get("additional_reference_error")
    if reference_error:
        lines.extend(
            [
                "",
                f"독립 수기 기준도 scene {reference_error['scene']}의 sun 시작을 "
                f"turn {reference_error['sealed_expected_activation_turn']}로 잘못 적었다. "
                f"실제 turn {reference_error['actual_protocol_activation_turn']}이며 다음 턴 마커 "
                "앞의 강제 교체 이벤트다. 변환과 기준을 분리해 작성하는 것만으로 "
                "오류를 막지 못했다.",
            ]
        )
    affected_inputs = {
        name for scene in evidence.get("affected_scenes", []) for name in scene["affected_inputs"]
    }
    exposure = {
        c: sum(s["condition"] == c and s["input"] in affected_inputs for s in collection["slots"])
        for c in conditions(manifest)
    }
    result["invalid_input_exposure_scheduled"] = exposure
    lines.extend(
        [
            "",
            "## 조건별 재현 횟수 → 오류·누락 변화",
            "",
            f"확인된 오류 입력 {len(affected_inputs)}개. 조건별 해당 입력의 예정 호출 수: "
            f"{exposure}. 이는 오류 입력 노출 분모이며 모델 오류 재현율이 아니다. "
            "평가 기준 오류의 영향 범위는 별도로 위 원본 근거에 명시했다.",
            "",
            "기존4장면/추가8장면의 모든 효과 추정을 무효화했다. "
            "오류·누락·필수 사실 보존율 및 다섯 대응 대비와 결합 효과는 미확정이다. "
            f"검토 초안{evidence['reviewed_draft']}/{collection['scheduled']}를 무효 자료로 "
            f"보존했고{evidence['review_pending']}/{collection['scheduled']} 검토는 중단했다. "
            "각 대비의 유효 장면 쌍은 기존0/4·추가0/8이다. 영향을 받지 않은 장면만 "
            "사후 선택해 비교하지 않는다.",
            "",
            "## 분모와 실측 비용",
            "",
            "```json",
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "counts",
                        "reviewed_draft_invalid",
                        "review_pending",
                        "valid_reviewed",
                        "cost",
                        "batch_elapsed_seconds",
                        "runtime_output_contract_records",
                    )
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "runtime output_contract 수는 실행기 형식 검사의 결과이며 "
            "완료된 수기 형식 오류율이 아니다. "
            "조건 wall span은 교차 제출 기간이므로 합산하지 않는다. 비용은 실제 수집 기록이며 "
            "유효 treatment의 성능·효율 비교로 해석하지 않는다.",
            "",
            "## 해석 한계와 보존",
            "",
            "사전238회귀와 가역 복원 검사가 통과했으나 weather 숫자의 의미와 수기 정답의 "
            "강제 교체 턴을 충분히 검증하지 못했다. 입력 바이트의 정보 복원만으로 주석 의미의 "
            "정확성이 보장되지 않는다. 모델 성능 한계나 harness 개선 효과를 결론 내릴 수 없다.",
            "",
            "manifest·입력·원본 근거·확보 응답·사전 검증 receipt는 당시 바이트로 보존했다. "
            "halt.json과 input-transform-failure.json이 사전 통과의 현재 유효성을 철회한다. "
            "수집 후 로컬 수정은 이 실행에 소급하지 않으며 재호출·보충·Cloud 채점은 없다. "
            "EX-020 halt/receipt/clock과 EP-011 Blocked는 보존한다.",
            "",
            "검토자는 설계를 아는 단일 검토자이며 독립 이중맹검은 아니다. 기존/추가 모두 같은 "
            "개발 자료이고 동일 seed 반복은 독립 장면이 아니다. 운영 적용·새 진단·EX-020 재개는 "
            "별도 결정 사항이다.",
        ]
    )
    b.seal_json(directory / "report.json", result)
    (directory / "report.md").write_text("\n".join(lines) + "\n")
    b.seal_json(
        directory / "report-seal.json",
        {
            "report.json": b.digest(directory / "report.json"),
            "report.md": b.digest(directory / "report.md"),
        },
    )
    return {"complete": False, "status": "invalidated", "report": str(directory / "report.md")}


def invalid_thinking_report(directory, manifest, evidence, result):
    """Record the sealed failure's actual cause without EX-021-specific assumptions."""
    affected_inputs = {
        name for scene in evidence.get("affected_scenes", []) for name in scene["affected_inputs"]
    }
    result["invalid_input_exposure_scheduled"] = {
        c: sum(s["condition"] == c and s["input"] in affected_inputs for s in manifest["schedule"])
        for c in conditions(manifest)
    }
    result["failure_evidence"] = evidence
    differences = {}
    for name, prepared_digest in manifest["source_files"].items():
        current_digest = b.digest(Path(name))
        if current_digest != prepared_digest:
            relative = Path(name).relative_to(b.WORKSPACE_ROOT)
            target = directory / "analysis-source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(name, target)
            differences[str(relative)] = {"prepared": prepared_digest, "analysis": current_digest}
    result["analysis_source_differences"] = differences
    lines = [
        f"# {manifest['experiment']} 중단 보고서",
        "",
        "Status: Blocked / invalidated / 진단 미완료",
        "",
        evidence["cause"],
        "",
        "## 오류 문장 → 원본 근거",
        "",
    ]
    example = evidence.get("model_example")
    if example:
        lines.extend(
            [f"> {example['quote']}", "", "발견 사례이며 조건별 오류 재현율이 아니다.", ""]
        )
    for scene in evidence.get("affected_scenes", []):
        lines.extend(
            [
                f"### scene {scene['scene']} / {scene['name']}",
                "",
                "```json",
                json.dumps(scene, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## 유효 분모와 실측 비용",
            "",
            f"전체 비교를 무효화했다. 유효 검토0/{result['counts']['scheduled']}, "
            "기존0/4·추가0/8 장면 쌍이다. "
            "사실 오류·누락·형식·보존율·주장 오류·모순 및 low/high 효과는 미확정이다. "
            "영향이 확인되지 않은 장면만 사후 선택하여 비교하지 않는다.",
            "",
            "```json",
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "counts",
                        "reviewed_draft_invalid",
                        "review_pending",
                        "valid_reviewed",
                        "cost",
                        "batch_elapsed_seconds",
                        "runtime_output_contract_records",
                        "invalid_input_exposure_scheduled",
                    )
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "오류 입력 노출 수는 모델 오류 재현율이 아니다. token·HTTP 지연은 실제 수집 비용이며 "
            "유효 treatment의 효율 비교가 아니다. runtime output_contract는 실행기 기록이며 "
            "완료된 수기 형식 오류율이 아니다. 교차 제출한 조건별 wall span은 합산하지 않는다.",
            "",
            "## 검증 한계와 보존",
            "",
            evidence.get(
                "contract_conflict", "입력/평가 기준 오류에 대한 사전 중단 규칙을 적용했다."
            ),
            "",
            "manifest·원본·입력·기준·72응답·사전 검증 receipt·첫 제출 시계는 보존했다. "
            "halt.json이 사전 통과의 현재 유효성을 철회하며 재제출을 차단한다. "
            "중단 후 로컬 수정의 source 차이는 analysis_source_differences에 기록하고 "
            "analysis-source에 보존했다. 그 수정은 이번 실행에 소급하지 않는다.",
            "",
            "설계를 아는 단일 검토자로 독립 이중맹검이 아니다. "
            f"{result['reviewed_draft_invalid']}건 초안은 무효로 보존하고 "
            f"나머지{result['review_pending']}건의 채점을 중단했다. 기존4/추가8 모두 "
            "사용한 개발 자료다. 이전 무효 실행의 응답은 비교 분모에 섞지 않았다.",
            "",
            "추가 유료 호출·보충·재질문·Cloud 채점은 없다. 운영 기본값 low와 EX-020/021 "
            "중단 상태를 유지한다. 새 진단이나 운영 적용·EX-020 재개는 별도 결정이다.",
        ]
    )
    b.seal_json(directory / "report.json", result)
    (directory / "report.md").write_text("\n".join(lines) + "\n")
    b.seal_json(
        directory / "report-seal.json",
        {
            "report.json": b.digest(directory / "report.json"),
            "report.md": b.digest(directory / "report.md"),
        },
    )
    return {"complete": False, "status": "invalidated", "report": str(directory / "report.md")}
