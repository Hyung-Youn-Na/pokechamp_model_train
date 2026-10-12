"""Isolated truth-set checks. Outputs must never become action or summary inputs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ..benchmark_player import normalize_name
from .calculations import field_for, own_spec
from .calculator import Calculator
from .state import STATS


def validate(battle_root, fixture_root):
    from poke_env.data import GenData
    from poke_env.teambuilder.teambuilder import Teambuilder

    results = []
    for case_id, move, expected_kind in [
        ("IO-C01", "Draco Meteor", "faint"),
        ("IO-C02", "Earthquake", "immune"),
        ("IO-C03", "Ruination", "rounded_damage"),
    ]:
        fixture = json.loads((Path(fixture_root) / f"{case_id}.json").read_text())
        battle_id = fixture["identity"]["battle_id"]
        manifest = json.loads((Path(battle_root) / battle_id / "manifest.json").read_text())
        # Deliberately separate from the normalizer: this is the ONLY path that
        # accesses opponent showdown_team, and it returns review evidence only.
        truth = next(t["showdown_team"] for t in manifest["teams"] if t["role"] == "opponent")
        obs = fixture["current_observation"]
        opponent = next(p for p in obs["opponent_confirmed"] if p["active"])
        original = next(
            s
            for s in Teambuilder.parse_showdown_team(truth)
            if normalize_name(s.species or s.nickname) == opponent["species"]
        )
        base_hp = GenData.from_gen(9).pokedex[opponent["species"]]["baseStats"]["hp"]
        level = original.level or 100
        maximum = (
            math.floor((2 * base_hp + original.ivs[0] + original.evs[0] // 4) * level / 100)
            + level
            + 10
        )
        if opponent["hp"] != opponent["max_hp"]:
            raise ValueError("posthoc exact-start check requires full observed HP")
        defender = {
            "name": opponent["species"],
            "entry_effects_observed": True,
            "options": {
                "level": level,
                "ability": original.ability,
                "item": original.item or "",
                "nature": original.nature or "Serious",
                "ivs": dict(zip(STATS, original.ivs)),
                "evs": dict(zip(STATS, original.evs)),
                "boosts": {k: v for k, v in opponent["boosts"].items() if k != "hp"},
                "curHP": maximum,
                "status": (opponent["status"] or "").lower(),
            },
        }
        active = next(p for p in obs["self_team"] if p["active"])
        with Calculator() as calc:
            response = calc.calculate(
                {"case": case_id, "purpose": "posthoc_truth_only"},
                [
                    {
                        "scenario_id": case_id,
                        "attacker": own_spec(active),
                        "defender": defender,
                        "move": move,
                        "field": field_for(obs),
                    }
                ],
            )
            computed = response["entries"][0]["damage_range_hp"]
        events = [
            json.loads(line)
            for line in (Path(battle_root) / battle_id / "events.jsonl").read_text().splitlines()
        ]
        cutoff = fixture["recent_events"][-1]["event_seq"]
        following = [
            e for e in events if e["event_seq"] > cutoff and e["event_type"] == "protocol_in"
        ]
        observed = next(e for e in following if f"|{move}|" in e["protocol"])
        text = observed["protocol"]
        target = "p2a: " if fixture["identity"]["actor_id"] == "p1" else "p1a: "
        if expected_kind == "faint":
            valid = computed[0] >= maximum and f"|faint|{target}" in text
        elif expected_kind == "immune":
            valid = computed == [0, 0] and f"|-immune|{target}" in text
        else:
            percentage = math.ceil((maximum - computed[0]) * 100 / maximum)
            valid = computed[0] == computed[1] and f"|{percentage}/100" in text
        results.append(
            {
                "case": case_id,
                "valid": valid,
                "event_seq": observed["event_seq"],
                "truth_damage_range": computed,
                "truth_max_hp": maximum,
                "engine_patch": response["engine_patch"],
                "remaining_hp_range": [max(0, maximum - n) for n in reversed(computed)],
                "observed_precision": expected_kind,
                "interpretation": "capped/rounded HP evidence; uncapped damage unobserved",
            }
        )
        if not valid:
            break
    return results


def main():
    from .. import benchmark as b

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-root", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    checks = validate(args.truth_root.resolve(strict=True), args.fixture_root.resolve(strict=True))
    passed = len(checks) == 3 and all(c["valid"] for c in checks)
    result = dict(checks=checks, posthoc_damage_passed=passed, offline_gate_passed=False,
                  cloud_calls=0, truth_root=str(args.truth_root.resolve()),
                  fixture_root=str(args.fixture_root.resolve()))
    b.seal_json(args.output / "result.json", result)
    print(json.dumps(result, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
