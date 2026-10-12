"""Source-linked blinded review and battle-weighted EX-025 descriptive reporting."""

from __future__ import annotations

import json
import time
from collections import Counter

from .. import benchmark as b
from ..concurrency_metrics import request_metrics
from .maximum import RECURRENCES
from .prepare import verify
from .report import blind, check_review, mean
from .runner import inventory

ARMS = ("low", "max")
METRICS = ("primary", "factual", "critical", "omission", "format", "retention")
COUNTS = (
    "scheduled",
    "intended",
    "submitted",
    "response_record",
    "acquired",
    "failed",
    "unexecuted",
    "unconfirmed",
)


def check_max_review(package, review):
    ids = set(review.get("calls", {}))
    if ids - {r["blind_id"] for r in package["responses"]}:
        raise ValueError("foreign reviewed response")
    subset = dict(package, responses=[r for r in package["responses"] if r["blind_id"] in ids])
    checked = check_review(subset, review)
    for response in subset["responses"]:
        row = review["calls"][response["blind_id"]]
        reference = package["references"][str(response["scene"])]
        by_id = {f["id"]: f for f in reference["facts"]}
        for fact_id, fact in row["facts"].items():
            required = {(e["event"], e["line"]) for e in by_id[fact_id]["evidence"]}
            actual = {(e["event"], e["line"]) for e in fact.get("evidence", [])}
            if not fact.get("explanation") or not actual or not actual <= required:
                raise ValueError("fact assessment requires original evidence and explanation")
            if fact["status"] == "incorrect" and (
                not fact["quote"] or fact["quote"] not in response["text"]
            ):
                raise ValueError("incorrect fact requires response quote")
            if (
                fact["status"] == "omitted"
                and fact["quote"]
                and fact["quote"] not in response["text"]
            ):
                raise ValueError("omission context quotation mismatch")
        for error in row["errors"]:
            if set(error.get("recurrences", [])) - set(RECURRENCES):
                raise ValueError("unknown prespecified recurrence")
    return checked


def aggregate_maximum(manifest, collection, checked, responses, review=None):
    per_input, costs, raw_rates = {}, {}, {}
    for arm in ARMS:
        slots = [r for r in collection["slots"] if r["condition"] == arm]
        acquired = [responses[r["id"]] for r in slots if r["acquired"]]
        traces = [r["trace"] for r in acquired]
        usage = [t["response"] for t in traces]
        costs[arm] = dict(
            scheduled=len(slots),
            **{k: sum(s[k] for s in slots) for k in COUNTS if k != "scheduled"},
            prompt_tokens=sum(
                t["prompt_tokens"] for t in usage if t.get("prompt_tokens") is not None
            ),
            completion_tokens=sum(
                t["completion_tokens"] for t in usage if t.get("completion_tokens") is not None
            ),
            unknown_token_responses=sum(
                t.get("prompt_tokens") is None or t.get("completion_tokens") is None for t in usage
            ),
            tokens_complete=all(s["acquired"] for s in slots if s["submitted"])
            and all(
                t.get("prompt_tokens") is not None and t.get("completion_tokens") is not None
                for t in usage
            ),
            http=request_metrics(traces),
            reported_models=dict(Counter(t.get("reported_model") for t in usage)),
            finish_reasons=dict(Counter(t.get("done_reason") for t in usage)),
        )
        arm_checked = [checked[s["blind_id"]] for s in slots if s["blind_id"] in checked]
        raw_rates[arm] = dict(
            reviewed=len(arm_checked),
            **{
                k: dict(
                    numerator=sum(x[k] for x in arm_checked),
                    denominator=len(arm_checked),
                )
                for k in METRICS
                if k != "retention"
            },
            retained_facts=sum(x["retained"] for x in arm_checked),
            incorrect_facts=sum(x["incorrect_facts"] for x in arm_checked),
            omitted_facts=sum(x["omitted_facts"] for x in arm_checked),
            required_facts=sum(x["required"] for x in arm_checked),
            factual_claims=sum(x["factual_claims"] for x in arm_checked),
            erroneous_claims=sum(x["erroneous_claims"] for x in arm_checked),
            unsupported=sum(x["unsupported"] for x in arm_checked),
            contradictions=sum(x["contradictions"] for x in arm_checked),
        )
        for scene in manifest["scenes"]:
            values = [
                checked[s["blind_id"]]
                for s in slots
                if s["scene"] == scene["scene"] and s["blind_id"] in checked
            ]
            per_input.setdefault(str(scene["scene"]), {})[arm] = dict(
                n=len(values),
                **{k: mean([r[k] for r in values]) for k in METRICS},
            )
    for values in per_input.values():
        complete = all(values[a]["n"] == 3 for a in ARMS)
        values["paired"] = complete
        values["max_minus_low"] = {
            k: values["max"][k] - values["low"][k] if complete else None for k in METRICS
        }
    strata = {}
    for kind in ("first", "followup", "rollup"):
        selected = [s for s in manifest["scenes"] if s["kind"] == kind]
        pairs = [
            per_input[str(s["scene"])] for s in selected if per_input[str(s["scene"])]["paired"]
        ]
        strata[kind] = dict(
            planned_inputs=len(selected),
            paired_inputs=len(pairs),
            missing_pairs=len(selected) - len(pairs),
            conditions={a: {k: mean([p[a][k] for p in pairs]) for k in METRICS} for a in ARMS},
            max_minus_low={k: mean([p["max_minus_low"][k] for p in pairs]) for k in METRICS},
            battle_groups=sorted({s["battle_group"] for s in selected}),
        )
    battles = {}
    for group in sorted({s["battle_group"] for s in manifest["scenes"]}):
        selected = [s for s in manifest["scenes"] if s["battle_group"] == group]
        pairs = [
            per_input[str(s["scene"])] for s in selected if per_input[str(s["scene"])]["paired"]
        ]
        complete = len(pairs) == len(selected)
        battles[group] = dict(
            planned_inputs=len(selected),
            paired_inputs=len(pairs),
            complete=complete,
            conditions={
                a: {k: mean([p[a][k] for p in pairs]) if complete else None for k in METRICS}
                for a in ARMS
            },
            max_minus_low={
                k: mean([p["max_minus_low"][k] for p in pairs]) if complete else None
                for k in METRICS
            },
        )
    complete_battles = [v for v in battles.values() if v["complete"]]
    overall = dict(
        planned_battles=len(battles),
        paired_complete_battles=len(complete_battles),
        missing_battles=len(battles) - len(complete_battles),
        conditions={
            a: {k: mean([v["conditions"][a][k] for v in complete_battles]) for k in METRICS}
            for a in ARMS
        },
        max_minus_low={k: mean([v["max_minus_low"][k] for v in complete_battles]) for k in METRICS},
    )
    recurrence = {code: {a: 0 for a in ARMS} for code in RECURRENCES}
    if review:
        for slot in collection["slots"]:
            audit = review["calls"].get(slot["blind_id"])
            if audit:
                for code in {c for e in audit["errors"] for c in e.get("recurrences", [])}:
                    recurrence[code][slot["condition"]] += 1
    return dict(
        per_input=per_input,
        strata=strata,
        per_battle=battles,
        overall=overall,
        cost=costs,
        raw_response_rates=raw_rates,
        prespecified_recurrence=recurrence,
    )


def report_maximum(directory, review_path=None):
    halt_path = directory / "halt.json"
    halt = b.read_sealed(halt_path) if halt_path.exists() else None
    invalid = bool(halt)
    manifest = verify(directory, current=False, validate_semantics=not invalid)
    collection = b.read_sealed(directory / "collection.json")
    if halt and (
        halt.get("manifest_sha256") != b.digest(directory / "manifest.json")
        or halt.get("collection_sha256") != b.digest(directory / "collection.json")
    ):
        raise ValueError("halt evidence binding mismatch")
    if collection["slots"] != inventory(directory, manifest)["slots"]:
        raise ValueError("response inventory drift")
    if (directory / "report-seal.json").exists():
        for name, digest in b.read_sealed(directory / "report-seal.json").items():
            if b.digest(directory / name) != digest:
                raise ValueError("report seal drift")
        result = b.read_sealed(directory / "report.json")
        return dict(
            complete=result["complete"],
            reviewed=result["reviewed"],
            report=str(directory / "report.md"),
        )
    package = blind(directory, manifest, collection)
    if review_path is None and not invalid:
        return dict(
            review="pending",
            blind_package=str(directory / "blind.json"),
            scheduled=132,
            acquired=collection["acquired"],
        )
    if invalid and review_path is not None:
        raise ValueError("halted diagnostic cannot restore valid comparison")
    review = b.read_sealed(review_path) if review_path else None
    checked = check_max_review(package, review) if review else {}
    responses = {
        s["id"]: b.read_sealed(directory / "responses" / (s["id"] + ".json"))
        for s in collection["slots"]
        if s["response_record"]
    }
    metrics = aggregate_maximum(manifest, collection, checked, responses, review)
    now = time.time()
    persistent = collection.get("cloud_clock")
    budget_ok = persistent is not None and now <= persistent["cleanup_deadline"]
    result = dict(
        complete=len(checked) == 132
        and collection["acquired"] == 132
        and not invalid
        and budget_ok,
        status="invalidated" if invalid else ("reviewed" if len(checked) == 132 else "incomplete"),
        fake=collection["fake"],
        reviewed=len(checked),
        review_pending=132 - len(checked),
        counts={k: collection[k] for k in COUNTS},
        metrics=metrics,
        checks=checked,
        batch_elapsed_seconds=collection["elapsed_seconds"],
        first_dispatch_to_report_seconds=now - persistent["first_dispatch_at"]
        if persistent
        else None,
        report_at=now,
        budget_ok=budget_ok,
        halt=halt,
        manifest_sha256=b.digest(directory / "manifest.json"),
        collection_sha256=b.digest(directory / "collection.json"),
        review_sha256=b.digest(review_path) if review_path else None,
    )
    if invalid:
        result["effect_estimates"] = None
        result["invalid_review_draft_count"] = halt.get("reviewed_draft", 0)
    if review:
        b.seal_json(directory / "review.json", review)
    b.seal_json(directory / "report.json", result)
    lines = [
        "# EX-025 요약 thinking low/max 진단",
        "",
        f"진단 {'완료' if result['complete'] else '미완료'}. "
        f"검토 {len(checked)}/132; 수집 {collection['acquired']}/132.",
        "",
    ]
    if invalid:
        lines += [f"전체 중단 사유: {halt.get('reason')}. 유효 효과 추정은 없다.", ""]
    lines += [
        "|입력 종류|입력 수|완전 대응|low 오류/누락 응답률|max 오류/누락 응답률|max−low|",
        "|---|---:|---:|---:|---:|---:|",
    ]

    def fmt(value):
        return "미확정" if value is None else f"{value:.4f}"

    for kind, values in metrics["strata"].items():
        lines.append(
            f"|{kind}|{values['planned_inputs']}|{values['paired_inputs']}|{fmt(values['conditions']['low']['primary'])}|{fmt(values['conditions']['max']['primary'])}|{fmt(values['max_minus_low']['primary'])}|"
        )
    overall = metrics["overall"]
    lines += [
        "",
        f"원배틀 동일 가중 전체: low {fmt(overall['conditions']['low']['primary'])}, "
        f"max {fmt(overall['conditions']['max']['primary'])}, "
        f"max−low {fmt(overall['max_minus_low']['primary'])}. "
        f"완전 원배틀 {overall['paired_complete_battles']}/{overall['planned_battles']}.",
        "",
        "입력별3반복을 먼저 평균한 뒤 같은 원배틀의 경계/진영/통합을 평균하고, 원배틀에 같은"
        " 가중치를 부여했다. 종류별 수치는 해당 입력의 평균이며 독립 표본 수/유의확률로 "
        "해석하지 않는다.",
        "",
        "|조건|제출|응답|검토|사실오류 응답|누락 응답|형식오류 응답|필수 보존|입력 "
        "token|출력 token|HTTP p50 ms|HTTP p95 ms|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        cost, rates = metrics["cost"][arm], metrics["raw_response_rates"][arm]
        lines.append(
            f"|{arm}|{cost['submitted']}|{cost['acquired']}|{rates['reviewed']}|{rates['factual']['numerator']}|{rates['omission']['numerator']}|{rates['format']['numerator']}|{rates['retained_facts']}/{rates['required_facts']}|{cost['prompt_tokens']}|{cost['completion_tokens']}|{cost['http']['http_p50_ms']}|{cost['http']['http_p95_ms']}|"
        )
    lines += [
        "",
        f"실제 수집 배치 시간 {collection['elapsed_seconds']:.2f}초; "
        f"최초 제출부터 보고까지 {result['first_dispatch_to_report_seconds']}초. "
        "비용은 관측 token이며 미확정 사용량을0으로 대체하지 않는다.",
        "",
        "|사전 지정 재발|low 응답 수|max 응답 수|",
        "|---|---:|---:|",
    ]
    for code, counts in metrics["prespecified_recurrence"].items():
        lines.append(f"|{code}|{counts['low']}|{counts['max']}|")
    lines += [
        "",
        "## 분모와 누락 대응",
        "",
        "```json",
        json.dumps(
            dict(
                counts=result["counts"],
                reviewed=len(checked),
                review_pending=result["review_pending"],
                overall_pairing={
                    k: v for k, v in overall.items() if k not in ("conditions", "max_minus_low")
                },
            ),
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## 해석",
        "",
        "모델 "
        "glm-5.3-flash·v1.1.2·temperature0·seed100·출력131072·provider"
        " 기본 context·timeout300초·계정/모델10/10·재시도0을 고정했다. 두"
        " 조건의 실제 HTTP 직렬화 think와 trace를 대조했다. 서버 내부 추론량을 "
        "직접 확인한 것은 아니다.",
        "진단 대상은 검증된 고정 이전메모리의22입력이다. 이전 실패응답은 분모에 합치지 "
        "않았다. 통합4입력은 두 원배틀의 양 진영에서 왔으므로 네 독립 배틀로 세지 않는다.",
        "오류 감소는 이 개발자료의 고정입력에서 thinking이 영향을 주었다는 탐색적 "
        "근거다. 오류가 남으면 max로 완전히 해결되지 않았음을 보고하며, 무차이만으로 모델이"
        " 유일 원인이라고 결론내리지 않는다.",
        "조건/thinking/token/지연을 가린 단일 검토이며 검토자는 연구 설계를 안다."
        " 사실 단위별 오류/누락 판정의 주관성과 같은 모델·seed·개발자료라는 한계가 있다."
        " 실제 연쇄 오류누적·행동·배틀·효능은 검증하지 않았다. 운영 적용과 EP-011/IO"
        " 재개는 자동 결정하지 않는다.",
        "",
        "## 응답별 오류 문장과 원문 근거",
        "",
    ]
    if review:
        for row in package["responses"]:
            audit = review["calls"].get(row["blind_id"])
            if not audit or not audit["errors"]:
                continue
            lines.append(f"### {row['blind_id']} / input {row['scene']}")
            for error in audit["errors"]:
                evidence = ", ".join(
                    f"event {r['event']} line {r['line']}" for r in error["evidence"]
                )
                lines += [
                    "",
                    "> " + error["quote"].replace("\n", "\n> "),
                    "",
                    error["explanation"] + " (" + evidence + ")",
                ]
    (directory / "report.md").write_text("\n".join(lines) + "\n")
    names = ["report.json", "report.md"] + (["review.json"] if review else [])
    b.seal_json(directory / "report-seal.json", {n: b.digest(directory / n) for n in names})
    return dict(
        complete=result["complete"],
        reviewed=len(checked),
        report=str(directory / "report.md"),
    )
