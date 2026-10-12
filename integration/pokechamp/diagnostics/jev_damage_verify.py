"""Independent raw-call/aggregation checks and explicitly synthetic Tera cases."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from .damage_sets import ROOT, SetSnapshot
from .jev_damage import Engine, percentage_range, transform
from .jev_damage_samples import write
from ..jev_battle import INITIAL_PP_POLICY, make_input
from ..observation.build import DEFAULT_BUILD
from ..observation.runtime import OfficialClient


def synthesize(fixture, lines, dex):
    """Inject explicitly authored PUBLIC rows before a saved own request.

    This is client replay, not a new simulator battle or an EX-057 observation.
    """
    fixture = copy.deepcopy(fixture)
    prefix = fixture["prefix"]
    final = prefix[-1]["protocol"].splitlines()
    assert final[-1].startswith("|request|")
    prefix[-1]["protocol"] = "\n".join(final[:-1] + lines + final[-1:])
    boundary = dict(protocol_event_seq=prefix[-1]["event_seq"], line_index=len(final) + len(lines) - 1)
    client = OfficialClient(fixture["actor"])
    try:
        official = client.snapshot(prefix, "synthetic-ep082", boundary=boundary)
    finally:
        client.close()
    payload, _ = make_input(official, prefix, actor=fixture["actor"], dex=dex, initial_pp_policy=INITIAL_PP_POLICY)
    return dict(fixture, payload=payload, official=official, boundary=boundary,
                synthetic=True, recipe=lines, decision="synthetic-ep082")


def individual_calls(scenarios):
    process = subprocess.run(["node", str(ROOT / "integration/pokechamp/tests/damage_sample_oracle.cjs")],
                             input=json.dumps(scenarios), text=True, capture_output=True, check=True)
    return json.loads(process.stdout)


def verify_samples(output):
    output = Path(output)
    receipt = json.loads((output / "samples.json").read_text())
    scenarios, expected, selected, branch_checks = [], [], [], 0
    for sample in receipt["samples"]:
        folder = output / sample["sample"]
        audit = json.loads(gzip.decompress((folder / "audit.json.gz").read_bytes()))
        moves = json.loads((folder / "moves.json").read_text())["after"]
        candidates = {c["candidate_id"]: c for c in audit["candidates"]}
        if any(tag in sample["tags"] for tag in ("self_tera_after", "tera_on_bench", "tera_return")):
            assert audit["branches"] == ["current", "opponent_tera"]
        if "tera_return" in sample["tags"]:
            assert audit["normalized_active"]["self"]["terastallized"] == "Steel"
        grouped = defaultdict(list)
        representatives = set()
        for row in audit["calculations"]:
            key = (row["direction"], row["move"], row["branch"])
            grouped[key].append(row)
            candidate = candidates[row["candidate_id"]]
            if row["direction"] == "incoming":
                assert row["move"] in candidate["moves"]
                if "scenario" in row:
                    assert row["scenario"]["defender"]["options"].get("teraType") == (
                        audit["normalized_active"]["self"]["teraType"] if row["branch"] in ("self_tera", "both_tera")
                        else audit["normalized_active"]["self"].get("terastallized") or None)
            if row.get("opponent_new_tera"):
                assert row["opponent_new_tera"] in candidate["tera_types"]
            entry = row.get("result", {})
            if "damage_range_hp" not in entry:
                continue
            pair = (row["direction"], row["branch"])
            if pair not in representatives:
                representatives.add(pair)
                scenario = copy.deepcopy(row["scenario"])
                scenario["scenario_id"] = sample["sample"] + "/" + scenario["scenario_id"]
                scenarios.append(scenario)
                expected.append(entry)
                selected.append(dict(sample=sample["sample"], direction=row["direction"], branch=row["branch"],
                                     move=row["move"], candidate_id=row["candidate_id"],
                                     damage_range_hp=entry["damage_range_hp"], defender_max_hp=entry["defender_max_hp"]))
        for side, direction in (("self", "outgoing"), ("opponent", "incoming")):
            for move in moves[side]:
                for branch, displayed in (move["damage_pct"] or {}).items():
                    raw = grouped[direction, move["id"], branch]
                    failures = [r for r in raw if "damage_range_hp" not in r.get("result", {})]
                    if failures:
                        assert displayed is None
                    elif raw:
                        assert displayed == percentage_range([r["result"] for r in raw])
                    branch_checks += 1
    oracle = individual_calls(scenarios)
    assert oracle["version"] == "0.11.0"
    for direct, entry, row in zip(oracle["entries"], expected, selected, strict=True):
        for key in ("damage_range_hp", "defender_max_hp"):
            assert direct[key] == entry[key], (row, direct, entry)
        if "damage_rolls" in entry:
            assert direct["damage_rolls"] == entry["damage_rolls"], row
        row["individual_smogon_match"] = True
    write(output / "individual-smogon-comparison.json", dict(passed=True, engine=oracle["version"],
          patch=oracle["patch"], cases=selected, oracle_entries=oracle["entries"]))

    dex = json.loads((DEFAULT_BUILD / "dex.json").read_text())
    fixture = json.loads((output / "sample-01/source.json").read_text())
    recipes = {
        "opponent-tera": ["|-terastallize|p2a: Zapdos|Steel"],
        "opponent-tera-bench": ["|-terastallize|p2a: Zapdos|Steel",
                                "|switch|p2a: Ting-Lu|Ting-Lu|100/100"],
        "opponent-tera-return": ["|-terastallize|p2a: Zapdos|Steel",
                                 "|switch|p2a: Ting-Lu|Ting-Lu|100/100",
                                 "|switch|p2a: Zapdos|Zapdos, tera:Steel|100/100"],
    }
    synthetic = []
    with Engine() as engine:
        for label, lines in recipes.items():
            case = synthesize(fixture, lines, dex)
            after, audit = transform(case["payload"], case["official"], case["prefix"], case["own_team"],
                                     dex, SetSnapshot(), engine)
            assert audit["branches"] == ["current", "self_tera"]
            assert audit["candidates"]
            opponent = next(p for p in after["state"]["opponent_team"] if p["active"])
            if label != "opponent-tera-bench":
                assert opponent["tera_type"] == "Steel"
                assert all("Steel" in c["tera_types"] for c in audit["candidates"])
            folder = output / "synthetic" / label
            folder.mkdir(parents=True, exist_ok=False)
            write(folder / "source.json", case)
            write(folder / "before.json", case["payload"])
            write(folder / "after.json", after)
            with (folder / "audit.json.gz").open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
                    stream.write(json.dumps(audit, ensure_ascii=False, separators=(",", ":")).encode())
            synthetic.append(dict(case=label, synthetic=True, recipe=lines, branches=audit["branches"],
                                  compatible_candidates=len(audit["candidates"]), passed=True))
    verification = dict(passed=True, aggregation_branch_checks=branch_checks,
                        individual_smogon_comparisons=len(selected), synthetic=synthetic,
                        external_api_calls=0, new_battles=0,
                        limitations=["추천 세트 지원집합의 범위이며 모든 합법 세트를 포괄하지 않음",
                                     "미래 행동 조건/이력이 필요한 미지원 기술은 null",
                                     "상대 테라 관측은 합성 검증이며 EX-057 실제 관측이 아님"])
    write(output / "verification.json", verification)
    return verification


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(verify_samples(parser.parse_args().output), ensure_ascii=False))
