"""Generate reviewable EX-057 damage samples without network/model/battle calls."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .damage_sets import ROOT, SetSnapshot, digest
from .jev_damage import Engine, transform
from ..jev_battle import INITIAL_PP_POLICY, VERSION, make_input
from ..observation.build import DEFAULT_BUILD, verify
from ..observation.runtime import OfficialClient

SOURCE = ROOT / ".pokechamp-data/jev/ex057-live"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def bounded(records, boundary):
    result = []
    for record in records:
        if record["event_seq"] > boundary["protocol_event_seq"]:
            break
        text = record["protocol"]
        if record["event_seq"] == boundary["protocol_event_seq"]:
            lines = text.splitlines()
            if not 0 <= boundary["line_index"] < len(lines):
                raise ValueError("invalid protocol line cutoff")
            text = "\n".join(lines[:boundary["line_index"] + 1])
        result.append(dict(event_seq=record["event_seq"], protocol=text))
    if not result or result[-1]["event_seq"] != boundary["protocol_event_seq"]:
        raise ValueError("missing protocol cutoff")
    return result


def select_records(source):
    """First matching public state per feature, outcome/response blind.

    Each selected record immediately freezes its own prefix. Battle IDs are
    reused by isolated servers, so actor username, not room name, is the key.
    """
    protocols, previous, ordinals = defaultdict(list), {}, {}
    selected, tags, tera_benched = {}, set(), set()

    def add(tag, event):
        username = event["decision"].split("-")[0]
        row = selected.setdefault(event["decision"], dict(
            tags=[], battle_number=ordinals[username], event=copy.deepcopy(event),
            prefix=bounded(protocols[username], event["boundary"])))
        row["tags"].append(tag)
        tags.add(tag)

    with (source / "events.jsonl").open() as stream:
        for line in stream:
            event = json.loads(line)
            if event["type"] == "protocol":
                protocols[event["username"]].append(dict(event_seq=event["sequence"], protocol=event["protocol"]))
                continue
            if event["type"] != "input":
                continue
            username = event["decision"].split("-")[0]
            if username not in ordinals:
                ordinals[username] = len(ordinals) + 1
            state = event["payload"]["state"]
            if state["decision_kind"] != "turn_action":
                continue
            own = next(m for m in state["self_team"] if m["active"])
            opponent = next(m for m in state["opponent_team"] if m["active"])
            features = {"ordinary": state["turn"] == 1,
                        "boost": any(v for m in (own, opponent) for k, v in m["boosts"].items() if k != "spe"),
                        "weather": bool(state["weather"]),
                        "immunity": (any(m["type"] == "Ground" for m in own["moves"])
                                     and "Flying" in opponent["types"] and not opponent["tera_type"]),
                        "self_tera_after": bool(own["tera_type"]),
                        "opponent_tera_after": bool(opponent["tera_type"]),
                        "tera_on_bench": any(m["tera_type"] not in ("", "unknown", None) and not m["active"]
                                             for m in state["self_team"] + state["opponent_team"]),
                        "tera_return": username in tera_benched and bool(own["tera_type"])}
            for tag, matches in features.items():
                if matches and tag not in tags:
                    if tag in ("self_tera_after", "opponent_tera_after") and username in previous:
                        add(tag.replace("after", "before"), previous[username])
                    add(tag, event)
            if features["tera_on_bench"]:
                tera_benched.add(username)
            previous[username] = event
    return list(selected.values()), tags, len(ordinals)


def seal_check(directory):
    checked = {}
    for line in (directory / "checksums.sha256").read_text().splitlines():
        checksum, name = line.split("  ", 1)
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != checksum:
            raise ValueError("source seal mismatch: " + name)
        checked[name] = checksum
    return checked


def move_sections(payload):
    return {side: next(m for m in payload["state"][side + "_team"] if m["active"])["moves"]
            for side in ("self", "opponent")}


def unchanged_boundaries(before, after):
    for side in ("self_team", "opponent_team"):
        for old, new in zip(before["state"][side], after["state"][side], strict=True):
            if not old["active"]:
                assert old == new, "bench modified"
            else:
                assert {k: v for k, v in old.items() if k != "moves"} == {k: v for k, v in new.items() if k != "moves"}
    assert before["questions"]["action"]["criteria"].keys() == after["questions"]["action"]["criteria"].keys()
    for key, old in before["questions"]["action"]["criteria"].items():
        new = after["questions"]["action"]["criteria"][key]
        assert {k: v for k, v in old.items() if k != "move"} == {k: v for k, v in new.items() if k != "move"}


def generate(output, source=SOURCE):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    before_seal = seal_check(source)
    build = verify()
    dex = json.loads((DEFAULT_BUILD / "dex.json").read_text())
    manifest = json.loads((source / "manifest.json").read_text())
    assert manifest["experiment_id"] == "EX-057" and manifest["schema_version"] == VERSION
    rows, tags, battles = select_records(source)
    snapshot = SetSnapshot()
    summaries, fixtures = [], []
    with Engine() as engine:
        for index, selected in enumerate(rows, 1):
            event, prefix = selected["event"], selected["prefix"]
            schedule = manifest["schedule"][selected["battle_number"] - 1]
            assert schedule["jev_actor"] == event["actor"]
            # Project exactly the controlled actor's submitted set. Neither the
            # opponent team's text nor outcomes/responses enter transform().
            own_id = schedule["teams"][0 if event["actor"] == "p1" else 1]
            own_record = manifest["teams"][own_id]
            own_team = own_record["showdown_team"]
            assert hashlib.sha256(own_team.encode()).hexdigest() == own_record["sha256"]
            client = OfficialClient(event["actor"])
            try:
                official = client.snapshot(prefix, event["battle"], boundary=event["boundary"])
            finally:
                client.close()
            assert official == event["official"], "bounded official reconstruction"
            before, commands = make_input(official, prefix, actor=event["actor"], dex=dex,
                                           version=VERSION, initial_pp_policy=INITIAL_PP_POLICY)
            assert before == event["payload"] and commands == event["commands"], "archived JEV reconstruction"
            after, audit = transform(before, official, prefix, own_team, dex, snapshot, engine)
            unchanged_boundaries(before, after)
            name = f"sample-{index:02d}"
            folder = output / name
            folder.mkdir()
            full_before = dict(model=manifest["model"]["model"], **before)
            full_after = dict(model=manifest["model"]["model"], **after)
            write(folder / "before.json", full_before)
            write(folder / "after.json", full_after)
            write(folder / "moves.json", dict(before=move_sections(before), after=move_sections(after)))
            fixture = dict(payload=before, official=official, prefix=prefix, own_team=own_team,
                           actor=event["actor"], decision=event["decision"], boundary=event["boundary"])
            write(folder / "source.json", fixture)
            fixtures.append(fixture)
            with (folder / "audit.json.gz").open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
                    stream.write(json.dumps(audit, ensure_ascii=False, separators=(",", ":")).encode())
            sizes = {}
            for label, full in (("before", full_before), ("after", full_after)):
                compact = json.dumps(full, ensure_ascii=False, separators=(",", ":"))
                sizes[label + "_chars"] = len(compact)
                sizes[label + "_bytes"] = len(compact.encode())
            for unit in ("chars", "bytes"):
                sizes["delta_" + unit] = sizes["after_" + unit] - sizes["before_" + unit]
            active = {s: next(m for m in after["state"][s + "_team"] if m["active"]) for s in ("self", "opponent")}
            failures = Counter(str(r.get("error") or r.get("result", {}).get("excluded_with_reason"))
                               for r in audit["calculations"] if r.get("error") or "damage_range_hp" not in r.get("result", {}))
            summaries.append(dict(sample=name, tags=selected["tags"], slot_id=schedule["slot_id"],
                battle_number=selected["battle_number"], room=event["battle"], decision=event["decision"],
                turn=before["state"]["turn"], actor=event["actor"], boundary=event["boundary"],
                prefix_sha256=digest(prefix), species={k: m["species"] for k, m in active.items()},
                compatible_candidates=len(audit["candidates"]), excluded_candidates=len(audit["excluded_candidates"]),
                raw_calculations=len(audit["calculations"]), calculation_failures=dict(failures), sizes=sizes,
                source=audit["source"], branches=audit["branches"]))
    assert seal_check(source) == before_seal
    receipt = dict(passed=True, source=str(source.relative_to(ROOT)), source_seal_sha256=hashlib.sha256(
        (source / "checksums.sha256").read_bytes()).hexdigest(), preserved_sealed_files=len(before_seal),
        samples=summaries, covered_features=sorted(tags), selection_battles=battles,
        missing_features=sorted({"opponent_tera_after", "tera_return"} - tags),
        observation_build=build, recommended_sources=list(snapshot.sources.values()),
        exact_archived_reconstruction=True, bench_and_candidates_preserved=True,
        external_api_calls=0, new_battles=0, efficacy_evaluated=False)
    write(output / "samples.json", receipt)
    report(output, receipt)
    return receipt


def report(output, receipt):
    text = ["# 기술별 피해량 범위 프롬프트 샘플", "",
            "EX-057 저장 입력을 재현한 오프라인 검토 자료다. 모델 적용·성능·승률은 미평가이며 API·새 배틀은 0이다.", "",
            "## 전후 입력", "",
            "전체 JSON은 저장 payload와 고정 요청 모델을 결합한 객체다(원 HTTP 바이트가 아님). after는 전송하지 않은 제안 입력이다.",
            "문자/바이트는 `ensure_ascii=False`, 공백 없는 JSON의 Unicode 문자 수/UTF-8 바이트 수다. 토큰 수가 아니다.", "",
            "| 샘플 | 경기·진영·턴 | 대면 | 사례 | 후보 | 문자 전→후 (증감) | 바이트 전→후 (증감) | 자료 |",
            "|---|---|---|---|---:|---|---|---|"]
    for row in receipt["samples"]:
        s, name = row["sizes"], row["sample"]
        text.append(f"| {name} | {row['slot_id']}·{row['actor']}·{row['turn']} | {row['species']['self']} → {row['species']['opponent']} | "
                    f"{', '.join(row['tags'])} | {row['compatible_candidates']} | "
                    f"{s['before_chars']}→{s['after_chars']} ({s['delta_chars']:+}) | {s['before_bytes']}→{s['after_bytes']} ({s['delta_bytes']:+}) | "
                    f"[전]({name}/before.json) · [후]({name}/after.json) · [기술]({name}/moves.json) · [감사]({name}/audit.json.gz) |")
    text += ["", "## 기술 부분 비교", "",
             "구간은 `current / self_tera / opponent_tera / both_tera` 순서이며 self/opponent는 공격 방향과 관계없이 모델 진영 기준이다.",
             "각 값은 방어자 최대 HP 대비 %, 후보별 분모로 나눈 뒤 합산·소수 첫째 자리 바깥쪽 반올림했다. 100% 초과를 자르지 않는다.", ""]
    for row in receipt["samples"]:
        name = row["sample"]
        moves = json.loads((output / name / "moves.json").read_text())
        text += [f"### {name}: {row['species']['self']} ↔ {row['species']['opponent']}", "",
                 "| 방향 | 기술 | 전 power | 공개/예상 | 후 damage_pct | 사유 |", "|---|---|---:|---|---|---|"]
        for side in ("self", "opponent"):
            old = {m["id"]: m for m in moves["before"][side]}
            for m in moves["after"][side]:
                ranges = m["damage_pct"]
                shown = "null" if ranges is None else " / ".join(
                    f"{b}: {v}" for b, v in ranges.items())
                text.append(f"| {'자기→상대' if side == 'self' else '상대→자기'} | {m['id']} | "
                            f"{old.get(m['id'], {}).get('power', '—')} | {m.get('knowledge', '자기 요청')} | {shown} | {m.get('damage_reason', '')} |")
    text += ["", "## 경계와 재현", "",
             "- [선택 목록·크기·출처·검증](samples.json)에 slot_id·진영·턴·decision·protocol event/line cutoff를 기록했다.",
             "- 각 source.json은 자기 제출 세트와 actor의 해당 cutoff까지의 관측만 포함한다. 상대 제출 세트·응답·결과·미래 prefix는 변환기 인자가 아니다.",
             "- 추천 세트는 2026-09-18 Smogon OU 추출 JSON과 provenance 체크섬을 검증했다. 각 named set 안에서만 성격·EV/IV 벡터·아이템·특성·기술 슬롯을 전개한다. 설명문에만 있는 대안/조합 제약은 파싱하지 않는다.",
             "- 공개 아이템 소모/교환은 최초 세트 제약과 현재 보유를 구분한다. Mimic/Sketch 슬롯 교체를 추적하며 Transform 등 미지원은 null로 표시한다.",
             "- 상대 기술별로 그 기술을 가진 후보만 사용한다. 새 테라는 해당 후보의 추천 타입만 사용하며 이미 소모한 진영의 새 분기는 생략한다.",
             "- 공개 HP에 맞는 모든 정수 HP를 후보 최대 HP별로 전개한다. 일반 급소·빗나감·미정 행동/교체/선후공에 따른 미래 변화는 포함하지 않는다. 기술 성공 조건은 별도로 남는다.",
             "- 연속기의 무작위 2–5회 타수는 포함하지만 모든 명중 판정 성공을 조건으로 Triple Axel/Kick은 3회, Population Bomb은 10회(Loaded Dice는 무작위 4–10회)를 사용한다. 보정 전 worker 결과도 감사에 보존하며 운영 계산기는 변경하지 않았다.",
             "- 표시 type/category/accuracy/priority는 기존 Dex 기본값이고, Weather Ball 등 동적 기술 규칙은 피해량 계산에 반영한다.",
             "- 변화기 null과 면역 [0,0]을 구분한다. 실패 후보가 있으면 해당 구간 전체를 null로 표시하며 감사에서 실패 이유를 보존한다.",
             "- effect_reference에는 새 예상 기술의 고정 규칙 설명만 추가한다. 벤치·합법 행동 ID·명령·PP·기존 운영 버전은 보존한다.",
             "- audit.json.gz에는 후보/제외 사유·원시 HP 피해/roll/최대 HP·분기·계산 입력·계산기 패치 identity를 보존한다.",
             f"- 원 EX-057 봉인 {receipt['preserved_sealed_files']}파일의 전후 체크섬을 확인했다. 원자료와 뷰어는 수정하지 않았다.",
             f"- 저장 자료에서 없는 사례: {', '.join(receipt['missing_features']) or '없음'}. 합성 검증의 출처와 결과는 별도 verification.json에 기록한다.",
             "", "개별 수치 대조·합성/경계 테스트 결과는 [검증 기록](verification.json)을 참조한다.",
             "", "## 재현 명령", "", "저장 자료와 고정 Node/공식 관측 빌드가 있는 환경에서 새 출력 경로를 지정한다.", "", "```sh",
             "cd /workspace/pokechamp",
             "PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.diagnostics.jev_damage_samples --output /tmp/jev-damage-review-new",
             "PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.diagnostics.jev_damage_verify --output /tmp/jev-damage-review-new",
             "```", ""]
    (output / "report.md").write_text("\n".join(text))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.output)
    print(json.dumps({"passed": result["passed"], "samples": len(result["samples"]),
                      "missing_features": result["missing_features"]}, ensure_ascii=False))
