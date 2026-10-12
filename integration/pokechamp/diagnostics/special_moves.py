"""Seal and compare independent Gen9 move executions; never issue gate receipts.

Run from the repository root with the pinned pokechamp Python environment:
PYTHONPATH=. pokechamp/.venv/bin/python -m \
    integration.pokechamp.diagnostics.special_moves --output <new-directory>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
from collections import Counter
from pathlib import Path

from integration.pokechamp.constants import SUBMODULES, WORKSPACE_ROOT
from integration.pokechamp.improved_io.calculator import Calculator, expected_patch

HERE = Path(__file__).parent
ROOT = WORKSPACE_ROOT
NODE = HERE / "special_moves.cjs"
PRIOR = ROOT / "integration/pokechamp/improved_io/prior.json"
LABELS = {
    "match": "일치",
    "numerical_mismatch": "수치 불일치",
    "input_insufficient": "입력 표현 부족",
    "explicit_unsupported": "명시적 미지원",
    "excluded": "범위 제외",
    "validator_error": "검증기 오류",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def clean_env():
    return {
        k: v
        for k, v in os.environ.items()
        if not any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
    }


def node(request):
    result = subprocess.run(
        ["node", str(NODE)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=True,
        env=clean_env(),
    )
    return json.loads(result.stdout)


def verify_build_sources(loaded):
    """Check loaded Showdown source maps against pinned source, and seal both builds and maps."""
    checked = []
    for filename in loaded:
        path = Path(filename)
        if not path.is_relative_to(ROOT / "pokemon-showdown/dist"):
            continue
        source_map = path.with_suffix(path.suffix + ".map")
        if not source_map.is_file():
            raise ValueError(f"missing Showdown build source map: {path}")
        data = json.loads(source_map.read_text())
        for name, content in zip(data["sources"], data["sourcesContent"], strict=True):
            source = (path.parent / name).resolve()
            if source.read_text() != content:
                raise ValueError(f"Showdown build source drift: {source}")
        checked.append(str(source_map))
    return checked


def sources(loaded):
    paths = set(HERE.glob("*.py")) | set(HERE.glob("*.cjs")) | set(HERE.glob("*.md"))
    paths |= set((ROOT / "integration/pokechamp/improved_io").glob("*.py"))
    paths |= set((ROOT / "integration/pokechamp/improved_io/calculator").glob("*.json"))
    paths |= set((ROOT / "integration/pokechamp/improved_io/calculator").glob("*.cjs"))
    paths |= set((ROOT / "integration/pokechamp/tests").glob("*.py"))
    paths |= {
        ROOT / "project_context/RESEARCH_DESIGN.md",
        ROOT / "project_context/CONTRACTS.md",
        ROOT / "project_context/decisions/D-021-special-move-diagnostics.md",
    }
    paths |= {Path(p) for p in loaded}
    paths |= {Path(p) for p in verify_build_sources(loaded)}
    # Seal simulator source/build mechanics and calculator runtime, including lazy modules.
    for folder in [
        "pokemon-showdown/sim",
        "pokemon-showdown/data",
        "pokemon-showdown/dist/sim",
        "pokemon-showdown/dist/data",
        "integration/pokechamp/improved_io/calculator/node_modules/@smogon/calc/dist",
    ]:
        paths |= {p for p in (ROOT / folder).rglob("*") if p.suffix in (".js", ".ts", ".json")}
    paths.add(PRIOR)
    paths.add(ROOT / "integration/pokechamp/constants.py")
    paths.add(ROOT / json.loads(PRIOR.read_text())["source"])
    paths |= {
        ROOT / f"pokechamp/poke_env/data/static/teams/gen9ou/gen9ou{i}.txt" for i in [1, 2, 6, 12]
    }
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths) if p.is_file()}


def verify_source(manifest):
    for name, expected in manifest.items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"source identity drift: {name}")


def comparable(result):
    """Wall-clock protocol annotations are evidence, not deterministic move state."""
    result = json.loads(json.dumps(result))
    for observation in result["observations"]:
        observation["log"] = [line for line in observation["log"] if not line.startswith("|t:|")]
    return result


def gaps(fixture):
    reasons = list(fixture.get("representation_gaps", []))
    move = fixture["move"]
    contextual = {
        "Beat Up": "생존 파티 구성 입력 없음",
        "Sucker Punch": "상대 선택 행동/실행 순서 입력 없음",
        "Thunderclap": "상대 선택 행동/실행 순서 입력 없음",
        "Upper Hand": "상대 우선도 행동/실행 순서 입력 없음",
        "First Impression": "등장 이후 activeMoveActions 입력 없음",
        "Gigaton Hammer": "직전 사용/실패 이력 입력 없음",
        "Stomping Tantrum": "직전 실패 이력 입력 없음",
        "Temper Flare": "직전 실패 이력 입력 없음",
        "Avalanche": "이번 턴 피격 여부 입력 없음",
        "Payback": "이번 턴 상대 실행 여부 입력 없음",
        "Doom Desire": "미래 턴 예약/착탄 상태 입력 없음",
        "Future Sight": "미래 턴 예약/착탄 상태 입력 없음",
        "Meteor Beam": "충전 턴/즉시 발동 상태 입력 없음",
        "Solar Beam": "충전 턴/즉시 발동 상태 입력 없음",
        "Solar Blade": "충전 턴/즉시 발동 상태 입력 없음",
        "Fickle Beam": "위력 두 배의 확률 분기 지정 입력 없음",
    }
    if move in contextual:
        reasons.append(contextual[move])
    return reasons


def raw_roll(raw, index):
    damage = raw["damage"]
    if isinstance(damage, (float, int)):
        return damage
    if len(damage) == 16 and all(isinstance(x, (float, int)) for x in damage):
        return damage[index]
    return None


def per_hit_comparison(f, result):
    if f["mechanics"] != "multihit" or not f.get("hits"):
        return None
    checks = []
    for i, (observation, raw) in enumerate(zip(result["observations"], result["raw"], strict=True)):
        damage = raw["damage"]
        if not isinstance(damage, list) or not all(
            isinstance(row, list) and len(row) == 16 for row in damage
        ):
            return {
                "status": "input_insufficient",
                "reason": "raw가 타격별16개 배열을 반환하지 않음",
            }
        expected = [row[i] for row in damage]
        actual = [h["before_cap"] for h in observation["hits"]]
        early_faint = observation["after"]["defender"] == 0
        checks.append(actual == (expected[: len(actual)] if early_faint else expected))
    return {
        "status": "match" if all(checks) else "numerical_mismatch",
        "scope": "명시적 타수, 같은 난수의 각 타격; 조기 기절은 관측 prefix만 비교",
    }


def classify(f, result, wrappers):
    missing = gaps(f)
    observed = [o["direct_before_cap"] for o in result["observations"]]
    raw = [raw_roll(r, i) for i, r in enumerate(result["raw"])]
    wrapped = [w["entries"][0] for w in wrappers]
    if any("excluded_with_reason" in w for w in wrapped):
        return {
            "status": "explicit_unsupported",
            "reasons": [w.get("excluded_with_reason") for w in wrapped[:1]],
            "raw_semantics": "HP 재분배; 직접 피해와 동일시하지 않음",
        }
    if any(x is None for x in raw):
        missing.append("복합 타격 배열의 동시 난수와 전체 확률분포는 비교 범위 밖")
    # Preserve per-hit arrays instead of comparing their sum as a single hit.
    if f["mechanics"] == "multihit":
        missing.append("타격별 실행/기절과 계산기 aggregate를 단타 피해로 합치지 않음")
    wrapper_ranges = [w["damage_range_hp"] for w in wrapped]
    silent_zero = bool(missing) and all(r == [0, 0] for r in wrapper_ranges)
    if missing:
        return {
            "status": "input_insufficient",
            "reasons": sorted(set(missing)),
            "silent_zero_with_missing_input": silent_zero,
            "observed_before_cap": observed,
            "raw_rolls": raw,
        }
    wrapper_difference = any(
        w["damage_rolls"] != r["damage"] for w, r in zip(wrapped, result["raw"], strict=True)
    )
    mismatch = observed != raw or wrapper_difference
    return {
        "status": "numerical_mismatch" if mismatch else "match",
        "boundary": "raw-to-wrapper"
        if wrapper_difference
        else "showdown-to-raw"
        if mismatch
        else None,
        "observed_before_cap": observed,
        "raw_rolls": raw,
        "normal_zero": not mismatch and not any(observed),
    }


def unverified(candidates):
    """Explicit limits are frozen before results; no assertion of exhaustive branch coverage."""
    entries = []
    for c in candidates:
        if c["excluded"]:
            continue
        if c["mechanics"] == "conditional":
            entries.append(
                {
                    "move": c["id"],
                    "status": "input_insufficient",
                    "reason": "공통 HP/랭크/종족 무게 및 지정 on/off만 실행; 모든 속도·무게의 "
                    "정확한 분기 경계 전후, 전용 종족/도구/특성 조합은 미검증",
                    "callbacks": c["callbacks"],
                }
            )
        if c["mechanics"] == "multihit":
            entries.append(
                {
                    "move": c["id"],
                    "status": "input_insufficient",
                    "reason": "동일 난수의 타격 경로만 실행; 타격별 독립16^n 조합, "
                    "Loaded Dice 전체 분기와 연속 공격 중 모든 특성 발동 조합은 미검증",
                }
            )
    return entries


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    for name, meta in SUBMODULES.items():
        sha = subprocess.check_output(
            ["git", "-C", str(meta["path"]), "rev-parse", "HEAD"], text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(meta["path"]), "status", "--porcelain"], text=True
        ).strip()
        if sha != meta["sha"] or dirty:
            raise ValueError(f"pinned source identity failed: {name}")
    prior = json.loads(PRIOR.read_text())
    if digest(ROOT / prior["source"]) != prior["source_sha256"]:
        raise ValueError("prior source hash mismatch")
    teams = {
        str(i): (ROOT / f"pokechamp/poke_env/data/static/teams/gen9ou/gen9ou{i}.txt").read_text()
        for i in [1, 2, 6, 12]
    }
    catalog = node({"op": "catalog", "prior": prior, "teams": teams})
    manifest = {
        "schema_version": 1,
        "experiment": "EX-019",
        "offline_gate_passed": False,
        "submodules": {k: v["sha"] for k, v in SUBMODULES.items()},
        "engine_patch": expected_patch(),
        "source_hashes": sources(catalog.pop("loaded_sources")),
        "development_runs": {
            "ex019-special-moves-dev1": "검증기 오류: 날씨 source 누락",
            "ex019-special-moves-dev2": "검증기 오류: 재현 로그 timestamp 비교",
            "ex019-special-moves-dev3": (
                "무효: Snow 변환·Counter callback·최대 타수 오류; 수치 승계 금지"
            ),
        },
        "protocol": {
            "seed": [1, 2, 3, 4],
            "damage_factors": list(range(85, 101)),
            "direct_damage": "target.damage after Damage event, before HP cap",
            "execution": "test Format; runMove plus beforeTurnCallback; no residual turn",
            "continue": "independent discrepancy",
            "stop": "identity/state/oracle/validator error",
            "prior_default": "no observed moves: first four in frozen array; not top usage sort",
        },
        **catalog,
        "unverified": unverified(catalog["candidates"]),
    }
    write(output / "manifest.json", manifest)
    with tarfile.open(output / "sources.tar.gz", "x:gz") as archive:
        for name in manifest["source_hashes"]:
            archive.add(ROOT / name, arcname=name, recursive=False)
    manifest_hash = digest(output / "manifest.json")
    # Every fixture is frozen before starting the oracle or production wrapper.
    with (output / "oracle.jsonl").open("x") as stream, (
        output / "oracle.stderr.log"
    ).open("x") as errors:
        subprocess.run(
            ["node", str(NODE)],
            input=json.dumps({"op": "batch", "fixtures": manifest["fixtures"]}),
            stdout=stream,
            stderr=errors,
            text=True,
            check=True,
            env=clean_env(),
        )
    results = []
    with (
        Calculator() as calc,
        (output / "wrapper.jsonl").open("x") as wrapper_file,
        (output / "reproductions.jsonl").open("x") as replay_file,
    ):
        with (output / "oracle.jsonl").open() as oracle_file:
            for f, line in zip(manifest["fixtures"], oracle_file, strict=True):
                result = json.loads(line)
                if result["scenario_id"] != f["scenario_id"]:
                    raise ValueError("oracle coverage mismatch")
                wrappers = []
                for i, obs in enumerate(result["observations"]):
                    ef = obs["effective"]
                    scenario = {
                        k: ef[k] for k in ("scenario_id", "attacker", "defender", "move", "field")
                    }
                    response = calc.calculate(
                        {"diagnostic": f["scenario_id"], "roll": i}, [scenario]
                    )
                    wrappers.append(response)
                wrapper_file.write(
                    json.dumps({"scenario_id": f["scenario_id"], "responses": wrappers}) + "\n"
                )
                verdict = classify(f, result, wrappers)
                verdict["raw_per_hit"] = per_hit_comparison(f, result)
                if (
                    verdict["status"] == "numerical_mismatch"
                    or (verdict["raw_per_hit"] or {}).get("status") == "numerical_mismatch"
                ):
                    # New Node process, new Battle and freshly constructed Pokemon, no reused state.
                    replay = node({"op": "execute", "fixture": f})
                    if comparable(replay) != comparable(result):
                        raise ValueError(f"non-reproducible oracle: {f['scenario_id']}")
                    replay_file.write(json.dumps({"fixture": f, "result": replay}) + "\n")
                    with Calculator() as independent:
                        ef = replay["observations"][0]["effective"]
                        scenario = {
                            k: ef[k]
                            for k in ("scenario_id", "attacker", "defender", "move", "field")
                        }
                        repeated = independent.calculate(
                            {"diagnostic": f["scenario_id"], "roll": 0}, [scenario]
                        )
                        if repeated != wrappers[0]:
                            raise ValueError("wrapper reproduction drift")
                    verdict["reproduced"] = True
                results.append({"scenario_id": f["scenario_id"], "move": f["move"], **verdict})
    verify_source(manifest["source_hashes"])
    if digest(output / "manifest.json") != manifest_hash:
        raise ValueError("sealed manifest changed")
    summary = {
        "diagnostic_complete": True,
        "calculator_all_passed": False,
        "offline_gate_passed": False,
        "candidate_count": len(manifest["candidates"]),
        "fixture_count": len(results),
        "counts": dict(Counter(r["status"] for r in results)),
        "excluded_candidates": sum(bool(c["excluded"]) for c in manifest["candidates"]),
        "explicit_unverified": len(manifest["unverified"]),
        "results": results,
    }
    write(output / "results.json", summary)
    report(output, manifest, summary)
    seal(output)
    return {k: v for k, v in summary.items() if k != "results"}


def report(output, manifest, summary):
    candidates = {c["name"]: c for c in manifest["candidates"]}
    issues = {}
    for r in summary["results"]:
        if r["status"] != "match":
            issues.setdefault(r["move"], []).append(r)

    def priority(name):
        origins = candidates.get(name, {}).get("origins", [])
        return (
            not any(s.startswith("team:") for s in origins),
            not any(s.startswith("prior-default") for s in origins),
            name,
        )

    lines = [
        "# EX-019 특수 기술 피해 진단",
        "",
        "진단 자료 생성 완료. 계산기 전체 통과가 아니며 offline_gate_passed=false.",
        "",
        f"후보 {summary['candidate_count']}, 시험 {summary['fixture_count']}, "
        f"범위 제외 {summary['excluded_candidates']}, "
        f"명시적 미검증 {summary['explicit_unverified']}.",
        "",
        str(summary["counts"]),
        "",
        "| 기술 | 현재 수록/선택 영향 | 판정·시험 수 | 대표 사례 |",
        "|---|---|---:|---|",
    ]
    for name in sorted(issues, key=priority):
        origins = candidates.get(name, {}).get("origins", [])
        teams = sorted(set(s for s in origins if s.startswith("team:")))
        default = sorted(
            set(
                s.split(":", 1)[1]
                for s in origins
                if s.startswith("prior-default:") or s.startswith("prior-default-no-observed:")
            )
        )
        impact = ", ".join(teams) + (
            f"; 기본 prior {','.join(default)}" if default else "; prior 전체 또는 고위험만"
        )
        rows = issues[name]
        counts = dict(Counter(LABELS[r["status"]] for r in rows))
        lines.append(f"| {name} | {impact} | {counts} | {rows[0]['scenario_id']} |")
    lines += [
        "",
        "원응답·전후HP·타격별 차감 전/실제 피해·로그는 oracle.jsonl, wrapper.jsonl에 있다.",
        "수치 불일치는 reproductions.jsonl의 새 프로세스/새 fixture에서 재현했다.",
        "manifest.json의 unverified는 모든 경계 조합을 통과했다는 해석을 금지한다.",
        "수록/선택은 영향 가능성이다. Mew의 Aura Wheel/Double Shock/Hyperspace Fury 실패는",
        "종족/타입 제한 음성시험이며 정상 전용 종족의 prior 수치 오류를 뜻하지 않는다.",
        "실행·명중·KO 확률과 승률은 추정하지 않았다. "
        "반동·회복·잔여 피해를 직접 피해에 합치지 않았다.",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n")


def seal(output):
    hashes = {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()}
    write(output / "checksums.json", hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; refusing to alter existing evidence")
    try:
        print(json.dumps(run(args.output), ensure_ascii=False))
    except Exception as exc:
        if args.output.is_dir() and not (args.output / "failure.json").exists():
            write(
                args.output / "failure.json",
                {
                    "status": "validator_error",
                    "error": str(exc),
                    "diagnostic_complete": False,
                    "offline_gate_passed": False,
                },
            )
        raise


if __name__ == "__main__":
    main()
