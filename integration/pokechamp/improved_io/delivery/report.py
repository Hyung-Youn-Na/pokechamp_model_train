"""Read-only EX-037 census and paired character/UTF-8 measurements."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter

from ...observability.recorder import verify_bundle
from .. import battle_prompts
from . import (
    VERSIONS,
    capture_request,
    digest,
    dumps,
    generate_all,
    parse_json,
    restore_projection,
)
from .mapping import catalog as field_catalog
from .preservation import check_source


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _window(events, call):
    starts = [
        e
        for e in events
        if e["event_type"] == "decision_start" and e["decision_seq"] == call["decision_seq"]
    ]
    if len(starts) != 1:
        raise ValueError("missing or ambiguous original decision")
    cutoff = starts[0]["event_seq"]
    sent = {
        e["decision_seq"]
        for e in events
        if e["event_type"] == "wire_action"
        and e["event_seq"] < cutoff
        and e.get("send_status") == "sent"
        and e.get("action", "").startswith("/choose")
    }
    previous = sorted(
        e["event_seq"]
        for e in events
        if e["event_type"] == "decision_start" and e.get("decision_seq") in sent
    )
    boundary = previous[-10] if len(previous) >= 10 else 0
    window = [
        {k: e[k] for k in ("event_seq", "protocol")}
        for e in events
        if e["event_type"] == "protocol_in" and boundary < e["event_seq"] < cutoff
    ]
    return window, len(previous), boundary


def corpus(root):
    bundles = sorted(root.glob("*/manifest.json"))
    if len(bundles) != 64:
        raise ValueError(f"EX-037 requires 64 actor bundles, found {len(bundles)}")
    for manifest_path in bundles:
        manifest = parse_json(manifest_path.read_text())
        if manifest["metadata"]["condition_id"] != "B":
            continue
        sealed = verify_bundle(manifest_path.parent)
        if not sealed["valid"]:
            raise ValueError(f"original bundle seal failed: {sealed['errors']}")
        path = manifest_path.with_name("events.jsonl")
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        events = [parse_json(line) for line in path.open()]
        for event in events:
            if event["event_type"] != "llm_call":
                continue
            full = parse_json(event["user_prompt"])
            if (
                manifest["experiment_id"] != "ex037-cloud"
                or full["identity"]["battle_id"] != manifest["battle_id"]
                or full["identity"]["actor_id"] != manifest["metadata"]["actor_id"]
                or full["identity"]["decision_seq"] != event["decision_seq"]
                or event["request"]["identity"] != full["identity"]
            ):
                raise ValueError("original cohort/actor/decision linkage mismatch")
            response = event.get("response", {})
            received = response.get("http_status") == 200 and "error_type" not in response
            if not received and response.get("error_type") != "ReadTimeout":
                raise ValueError("unclassified response presence")
            window, previous, boundary = _window(events, event)
            if full["recent_events"] != window:
                raise ValueError("original recent-ten-decision window mismatch")
            origin = dict(
                events_path=str(path.resolve()),
                events_sha256=file_hash,
                manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                event_seq=event["event_seq"],
                decision_seq=event["decision_seq"],
            )
            yield (
                full,
                event,
                manifest,
                origin,
                dict(previous_sent_decisions=previous, boundary_event_seq=boundary),
            )


def sizes(delivery):
    """Top-level component lengths include key/colon; framing is a separate part."""
    value = parse_json(delivery.user_json)
    compact = delivery.candidate_version in ("B2", "B3")
    serial = dumps if compact else lambda v: json.dumps(v, ensure_ascii=False, allow_nan=False)
    colon, comma = (":", ",") if compact else (": ", ", ")
    parts = dict(
        system=delivery.system_prompt,
        user=delivery.user_json,
        total=delivery.system_prompt + delivery.user_json,
    )
    parts.update({f"user.{k}": json.dumps(k) + colon + serial(v) for k, v in value.items()})
    parts["user.json_framing"] = "{}" + comma * (len(value) - 1)
    if sum(len(v) for k, v in parts.items() if k.startswith("user.")) != len(delivery.user_json):
        raise ValueError("component sizes do not sum to user string")
    for key, child in value["calculation_bundle"].items():
        parts[f"calculation.{key}"] = json.dumps(key) + colon + serial(child)
    policy = (
        (battle_prompts.PROMPTS / "battle_fixed.txt").read_text()
        if delivery.candidate_version == "B0"
        else delivery.system_prompt.split("\n---\n\n")[0] + "\n"
    )
    parts["system.policy"] = policy
    parts["system.guide_and_separator"] = delivery.system_prompt[len(policy) :]
    result = {
        f"{name}.{unit}": len(text if unit == "chars" else text.encode("utf-8"))
        for name, text in parts.items()
        for unit in ("chars", "bytes")
    }
    result["log.source_link.chars"] = len(delivery.source_link_json)
    result["log.source_link.bytes"] = len(delivery.source_link_json.encode("utf-8"))
    return result


def _pp_changed(before, after):
    def slots(request):
        active = next(
            (p.get("ident") for p in request.get("side", {}).get("pokemon", []) if p.get("active")),
            None,
        )
        pp = {
            m["id"]: m["pp"]
            for slot in request.get("active", [])
            if slot
            for m in slot.get("moves", [])
            if "pp" in m
        }
        return active, pp

    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    previous, old_pp = slots(before)
    current, new_pp = slots(after)
    return (
        previous is not None
        and previous == current
        and any(old_pp[k] != new_pp[k] for k in old_pp.keys() & new_pp.keys())
    )


def features(full, window):
    entries = full["calculation_bundle"]["entries"]
    teams = (
        full["current_observation"]["self_team"] + full["current_observation"]["opponent_confirmed"]
    )
    protocol = "\n".join(e["protocol"] for e in full["recent_events"])
    requests = [
        json.loads(line[9:])
        for line in protocol.splitlines()
        if line.startswith("|request|") and line[9:]
    ]
    return {
        "forced_switch": full["request"]["kind"] == "forced_switch",
        "unrevealed_opponent_replacement": any(
            e["scenario_id"].endswith("-unknown-opponent") for e in entries
        ),
        "tera_legal": any("terastallize" in a for a in full["request"]["legal_actions"]),
        "protect_expired_parser_retained": any(
            "PROTECT" in p.get("parser_effects", {}) and "PROTECT" not in p.get("effects", {})
            for p in teams
        ),
        "future_sight": "futuresight" in dumps(full["calculation_bundle"]).lower()
        or "Future Sight" in protocol,
        "multi_hit": any(
            v.get("hits", 1) > 1 for e in entries for v in e.get("damage_variants", [])
        ),
        "multiple_damage_branches": any(len(e.get("damage_variants", [])) > 1 for e in entries),
        "speed_tie": any(
            e.get("conditional_order", {}).get("equal_priority_speed_relation") == "tie_possible"
            for e in entries
        ),
        "unknown_public_hp": any(
            p.get("max_hp") in (0, None) for p in full["current_observation"]["opponent_confirmed"]
        ),
        "excluded_damage": any("excluded_with_reason" in e for e in entries),
        "item_consumption_history": "|-enditem|" in protocol,
        "pp_change_history": any(_pp_changed(a, b) for a, b in zip(requests, requests[1:])),
        "ten_decision_boundary": window["previous_sent_decisions"] >= 10,
    }


def statistics_for(values):
    values = sorted(values)
    return dict(
        mean=statistics.mean(values),
        median=statistics.median(values),
        p95=values[math.ceil(len(values) * 0.95) - 1],
        maximum=max(values),
        sum=sum(values),
        n=len(values),
    )


def save_example(directory, full, versions, origin):
    directory.mkdir(parents=True)
    write(directory / "full-input.json", full)
    write(directory / "origin.json", origin)
    for version, delivery in versions.items():
        (directory / f"{version}.system.txt").write_text(delivery.system_prompt)
        (directory / f"{version}.user.json").write_text(delivery.user_json)
        write(directory / f"{version}.source-link.json", parse_json(delivery.source_link_json))


def audit(root, output):
    """New directory only: a failed run leaves its partial evidence in place."""
    output.mkdir(parents=True, exist_ok=False)
    rows, counts, examples = [], Counter(), {}
    boundary_counts, field_mapping = Counter(), Counter()
    seen, actors = set(), set()
    with (output / "checks.jsonl").open("w") as log:
        for full, event, manifest, origin, window in corpus(root):
            identity = full["identity"]
            key = (identity["battle_id"], identity["decision_seq"])
            if key in seen:
                raise ValueError("duplicate original input")
            seen.add(key)
            actors.add(identity["battle_id"])
            before = json.dumps(full, ensure_ascii=False)
            versions = generate_all(full, battle_format=manifest["battle_format"], origin=origin)
            if (
                versions["B0"].system_prompt != event["system_prompt"]
                or versions["B0"].user_json != event["user_prompt"]
            ):
                raise ValueError("B0 is not the exact original system/user string")
            response = event["response"]
            received = response.get("http_status") == 200 and "error_type" not in response
            counts["inputs"] += 1
            counts["responses" if received else "no_response"] += 1
            counts[
                "failed_battle_inputs"
                if manifest["result"]["outcome"] not in ("player_won", "player_lost", "tie")
                else "completed_battle_inputs"
            ] += 1
            flags = features(full, window)
            for name, active in flags.items():
                boundary_counts[name] += int(active)
            receipt = dict(
                identity=identity,
                origin=origin,
                response_received=received,
                original_call_status=event["status"],
                window=window,
                boundary_features=flags,
                candidates={},
            )
            for version, delivery in versions.items():
                restored = restore_projection(delivery)
                link = parse_json(delivery.source_link_json)
                check_source(full, restored, link["exclusions"])
                # The final offline adapter independently reruns original validation
                # and verifies exact strings/versions/linkage before serializing.
                captured = capture_request(full, delivery, battle_format="gen9ou", origin=origin)
                measurements = sizes(delivery)
                rows.append(
                    dict(
                        battle_id=identity["battle_id"],
                        decision_seq=identity["decision_seq"],
                        version=version,
                        response_received=received,
                        sizes=measurements,
                    )
                )
                receipt["candidates"][version] = dict(
                    system_sha256=link["system_sha256"],
                    user_sha256=link["user_sha256"],
                    wire_sha256=captured["wire_sha256"],
                    source_link_sha256=digest(delivery.source_link_json),
                    complete_source_restored=True,
                    final_request_captured=True,
                    excluded_values=len(link["exclusions"]),
                    sizes=measurements,
                )
                if version == "B1":
                    for item in link["exclusions"]:
                        normalized = ".".join(
                            "*" if isinstance(k, int) else k for k in item["path"]
                        )
                        field_mapping[(normalized, item["reason"])] += 1
            if json.dumps(full, ensure_ascii=False) != before:
                raise ValueError("transform mutated source input")
            log.write(dumps(receipt) + "\n")
            log.flush()
            tags = ["first_input"] if counts["inputs"] == 1 else []
            tags += [
                name
                for name in ("ten_decision_boundary", "forced_switch", "future_sight")
                if flags[name] and name not in examples
            ]
            if not received and "unanswered_input" not in examples:
                tags.append("unanswered_input")
            if tags:
                folder = f"examples/{identity['battle_id']}-d{identity['decision_seq']}"
                save_example(output / folder, full, versions, origin)
                for tag in tags:
                    examples[tag] = folder
            if counts["inputs"] % 25 == 0:
                print(f"Validated/captured {counts['inputs']}/1060 inputs × B0–B3", flush=True)
    if counts["inputs"] != 1060 or counts["responses"] != 1057 or counts["no_response"] != 3:
        raise ValueError(f"EX-037 denominator mismatch: {dict(counts)}")
    if len(actors) != 32:
        raise ValueError("EX-037 B actor denominator mismatch")
    metrics = sorted({key for row in rows for key in row["sizes"]})
    stats = {
        version: {
            metric: statistics_for(
                [row["sizes"].get(metric, 0) for row in rows if row["version"] == version]
            )
            for metric in metrics
        }
        for version in VERSIONS
    }
    reductions = {}
    for index, version in enumerate(VERSIONS):
        previous = VERSIONS[max(0, index - 1)]
        reductions[version] = {}
        for unit in ("chars", "bytes"):
            metric = f"total.{unit}"
            now, prev, base = (stats[v][metric]["mean"] for v in (version, previous, "B0"))
            reductions[version][unit] = dict(
                previous_version=previous,
                stage_mean_saved=prev - now,
                stage_reduction_percent=100 * (prev - now) / prev,
                cumulative_mean_saved=base - now,
                cumulative_reduction_percent=100 * (base - now) / base,
            )
    mapping = [
        dict(path=path, reason=reason, occurrences=n)
        for (path, reason), n in sorted(field_mapping.items())
    ]
    result = dict(
        passed=True,
        cohort="EX-037",
        counts=dict(counts),
        actors=len(actors),
        versions=VERSIONS,
        statistics=stats,
        reductions=reductions,
        boundary_counts=dict(boundary_counts),
        examples=examples,
        field_exclusions=mapping,
        tokenizer="unmeasured: exact model tokenizer not verified",
        model_calls=0,
        new_research_battles=0,
        limits=[
            "Structural information preservation, not model comprehension or efficacy.",
            "Offline final-message adapter; production battle wiring is future scope.",
            "Original calculator validation/replay is not an independent game-rule oracle.",
            "Request JSON whitespace/object key order is not tactical information; "
            "other protocol lines are preserved verbatim.",
        ],
    )
    write(output / "field-mapping.json", field_catalog())
    write(output / "sizes.json", rows)
    write(output / "result.json", result)
    (output / "report.md").write_text(markdown(result))
    return result


def markdown(result):
    counts = result["counts"]
    lines = [
        "# EP-034 — B 프롬프트 전수 오프라인 비교",
        "",
        f"EX-037 B {counts['inputs']}입력, {counts['responses']}응답·"
        f"{counts['no_response']}미수신, {result['actors']} actor. "
        "B0 원문 문자열 일치, 원본 검증·전체 정보 복원·최종 요청 포착을 B0–B3 모두 통과했다.",
        "",
        "판단력·승률·지연 효과는 측정하지 않았다. 모델 호출·새 연구 배틀0. "
        "정확한 모델 tokenizer를 검증하지 않아 토큰 절감률은 미측정이다.",
        "",
        "## 요청 전체 분량",
        "",
        "| 후보 | 평균 문자 | 중앙값 | p95 | 최대 | 단계 절감 | B0 대비 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for version in VERSIONS:
        s = result["statistics"][version]["total.chars"]
        r = result["reductions"][version]["chars"]
        lines.append(
            f"| {version} | {s['mean']:,.1f} | {s['median']:,.1f} | "
            f"{s['p95']:,} | {s['maximum']:,} | {r['stage_reduction_percent']:.2f}% | "
            f"{r['cumulative_reduction_percent']:.2f}% |"
        )
    lines += [
        "",
        "## 구성 요소 분포",
        "",
        "문자와 UTF-8 bytes를 각각 센다. p95는 nearest rank(ceil(0.95×n))다. "
        "각 셀은 평균 / 중앙값 / p95 / 최대이며 모든 후보 분모는1060이다. "
        "user.*는 key·colon을 포함하고 json_framing과 합하면 실제 user 문자열이다. "
        "calculation.*는 해당 구성의 세부 내역이므로 다시 합산하지 않는다. "
        "log.source_link는 모델 입력에 포함되지 않는다.",
        "",
    ]
    for unit in ("chars", "bytes"):
        lines += [
            f"### {unit}",
            "",
            "| 구성 요소 | B0 | B1 | B2 | B3 |",
            "|---|---:|---:|---:|---:|",
        ]
        for metric in sorted(result["statistics"]["B0"]):
            if not metric.endswith("." + unit):
                continue
            cells = []
            for version in VERSIONS:
                s = result["statistics"][version][metric]
                cells.append(
                    f"{s['mean']:,.1f} / {s['median']:,.1f} / {s['p95']:,} / {s['maximum']:,}"
                )
            lines.append("| " + metric.rsplit(".", 1)[0] + " | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## 단계별 UTF-8 byte 감소",
        "",
        "| 후보 | 이전 단계 대비 평균 감소 bytes | 단계 절감 | "
        "B0 대비 평균 감소 bytes | 누적 절감 |",
        "|---|---:|---:|---:|---:|",
    ]
    for version in VERSIONS:
        r = result["reductions"][version]["bytes"]
        lines.append(
            f"| {version} | {r['stage_mean_saved']:,.1f} | "
            f"{r['stage_reduction_percent']:.2f}% | {r['cumulative_mean_saved']:,.1f} | "
            f"{r['cumulative_reduction_percent']:.2f}% |"
        )
    lines += ["", "## 실제 전후 입력", ""]
    for tag, folder in result["examples"].items():
        lines.append(
            f"- {tag}: [원본]({folder}/full-input.json), "
            + ", ".join(
                f"[{v} system]({folder}/{v}.system.txt) · [{v} user]({folder}/{v}.user.json)"
                for v in VERSIONS
            )
            + f", [원본 연결·제외값]({folder}/B3.source-link.json)."
        )
    lines += [
        "",
        "## 전수 원자료의 경계 사례",
        "",
        "아래는 해당 속성을 포함한 입력 수로 서로 중복된다. 없는 경계는 별도 회귀에만 근거한다.",
        "",
    ]
    lines += [f"- {key}: {value}" for key, value in result["boundary_counts"].items()]
    lines += ["", "## 제외 필드 실측", "", "| 경로 | 사유 | 발생 수 |", "|---|---|---:|"]
    lines += [
        f"| `{r['path']}` | {r['reason']} | {r['occurrences']:,} |"
        for r in result["field_exclusions"]
    ]
    lines += [
        "",
        "## 검증과 한계",
        "",
        "[전수 검사·hash·응답 구분](checks.jsonl), [요청별 분량](sizes.json), "
        "[통계·단계 감소·분모](result.json). 별도 경계/회귀 결과와 필드 매핑은 "
        "상위 검토 보고서에 연결한다.",
        "",
        "기존 원본 패치/hash와 시나리오 재구성 검사를 재사용했다. 계산기의 규칙 정확성을 새로 "
        "입증한 실험은 아니다. 정보 복원은 원본 JSON 구조·배열 순서/중복/수치·원시 행 보존을 "
        "뜻한다. request JSON의 공백과 객체 key 순서는 정규화할 수 있다. "
        "간결한 설명서가 모델에게 똑같이 이해되는지, 변경분 읽기가 판단에 미치는 영향은 "
        "실제 모델 평가가 필요하다. 과거 선택 행동 일치는 정답으로 사용하지 않았다.",
        "",
    ]
    return "\n".join(lines)
