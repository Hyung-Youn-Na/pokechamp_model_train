"""Independent raw protocol checks for EP-051; does not use the B state reducer.

Checks are bounded to the recorded EX-042 event vocabulary. No opponent submission
is loaded. Unknown facts remain unchecked and are counted explicitly.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from poke_env.data import GenData


def ident(value):
    return re.sub(r"^(p[12])[a-z]:", r"\1:", value)


def token(value):
    return re.sub("[^a-z0-9]", "", value.lower())


STATS = ("atk", "def", "spa", "spd", "spe", "accuracy", "evasion", "hp")


class PublicFacts:
    def __init__(self):
        self.mons = {}
        self.weather = {}
        self.turn = 0
        self.kinds = Counter()
        self.dex = GenData.from_gen(9).pokedex
        self.request = None

    def mon(self, key):
        return self.mons.setdefault(
            key,
            dict(
                moves=set(),
                item="unknown_item",
                ability=None,
                active=False,
                boosts=dict.fromkeys(STATS, 0),
                status=None,
            ),
        )

    def feed(self, protocol):
        for line in protocol.splitlines():
            p = line.split("|")
            if len(p) < 2:
                continue
            kind = p[1]
            self.kinds[kind] += 1
            if kind == "request" and p[2]:
                self.request = json.loads("|".join(p[2:]))
            elif kind == "turn":
                self.turn = int(p[2])
            elif kind == "-weather":
                self.weather = {} if p[2] == "none" else {token(p[2]): self.turn}
            if len(p) < 3:
                continue
            holder = next((s[5:] for s in p[3:] if s.startswith("[of] p")), None)
            source = next(
                (
                    s[len("[from] ability: ") :]
                    for s in p[3:]
                    if s.startswith("[from] ability: ")
                ),
                None,
            )
            if source and holder:
                self.mon(ident(holder))["ability"] = token(source)
            if not re.fullmatch(r"p[12][a-z]?: .+", p[2]):
                continue
            key = ident(p[2])
            mon = self.mon(key)
            if kind in ("switch", "drag"):
                for other, value in self.mons.items():
                    if other[:2] == key[:2]:
                        value["active"] = False
                        value["boosts"] = dict.fromkeys(STATS, 0)
                mon["active"] = True
                mon["species"] = token(p[3].split(",")[0])
                mon["base_types"] = [
                    s.upper() for s in self.dex[mon["species"]]["types"]
                ]
                self.health(mon, p[4])
            elif kind in ("-damage", "-heal"):
                self.health(mon, p[3])
            elif kind == "faint":
                mon.update(hp=0, status="FNT")
                mon.pop("tera", None)
            elif kind == "-status":
                mon["status"] = p[3].upper()
            elif kind == "-curestatus":
                mon["status"] = None
            elif kind in ("-boost", "-unboost"):
                n = int(p[4]) * (1 if kind == "-boost" else -1)
                mon["boosts"][p[3]] = min(6, max(-6, mon["boosts"][p[3]] + n))
            elif kind == "move" and not any(s.startswith("[from]") for s in p[4:]):
                if token(p[3]) not in ("struggle", "recharge"):
                    mon["moves"].add(token(p[3]))
            elif kind == "-terastallize":
                mon["tera"] = p[3].upper()
            elif kind == "-item":
                mon["item"] = token(p[3])
            elif kind == "-enditem":
                mon["item"] = None
            elif kind == "-ability":
                mon["ability"] = token(p[3])
            elif kind == "-activate" and p[3].startswith("ability: "):
                mon["ability"] = token(p[3][len("ability: ") :])
            if not holder:
                if source and kind in ("-heal", "-immune", "-boost", "-unboost"):
                    mon["ability"] = token(source)
                item = next(
                    (
                        s[len("[from] item: ") :]
                        for s in p[3:]
                        if s.startswith("[from] item: ")
                    ),
                    None,
                )
                if item and kind in ("-heal", "-damage", "-status"):
                    mon["item"] = token(item)

    @staticmethod
    def health(mon, condition):
        hp, *status = condition.split()
        if "/" in hp:
            current, maximum = map(int, hp.split("/"))
            mon.update(hp=current, max_hp=maximum)
        else:
            assert hp == "0"
            mon["hp"] = 0
        mon["status"] = status[0].upper() if status else None

    def check(self, value):
        checks = Counter()
        unknown = Counter()
        issues = []
        observation = value["current_observation"]

        def equal(kind, path, expected, actual):
            checks[kind] += 1
            if expected != actual:
                issues.append(
                    dict(check=kind, path=path, expected=expected, actual=actual)
                )

        equal(
            "weather",
            "weather",
            self.weather,
            {token(k): v for k, v in observation["weather"].items()},
        )
        for i, mon in enumerate(observation["self_team"]):
            raw = self.request["side"]["pokemon"][i]
            for field in (
                "ident",
                "details",
                "condition",
                "active",
                "stats",
                "moves",
                "baseAbility",
                "ability",
                "item",
                "teraType",
            ):
                if field in raw:
                    equal(
                        "self_request",
                        f"self_team[{i}].{field}",
                        raw[field],
                        mon.get(field),
                    )
            fact = self.mons.get(mon["ident"])
            if fact and mon["active"]:
                equal(
                    "self_boosts",
                    f"self_team[{i}].boosts",
                    fact["boosts"],
                    mon["boosts"],
                )
            if fact and "base_types" in fact:
                equal(
                    "self_types",
                    f"self_team[{i}].battle_types",
                    fact["base_types"],
                    mon["battle_types"],
                )
                types = (
                    [fact["tera"]]
                    if fact.get("tera") and fact["tera"] != "STELLAR"
                    else fact["base_types"]
                )
                equal(
                    "self_types",
                    f"self_team[{i}].effective_types",
                    types,
                    mon["effective_types"],
                )
        for i, mon in enumerate(observation["opponent_confirmed"]):
            fact = self.mons.get(mon["ident"])
            if fact is None or "species" not in fact:
                unknown["opponent_not_publicly_switched_in"] += 1
                continue
            path = f"opponent_confirmed[{i}]"
            for key in ("species", "hp", "max_hp", "status", "item", "ability"):
                if key == "ability" and fact[key] is None:
                    unknown["opponent_ability"] += 1
                    continue
                if key == "item" and fact[key] == "unknown_item":
                    unknown["opponent_item"] += 1
                    continue
                if key in fact:
                    equal("opponent_" + key, path + "." + key, fact[key], mon[key])
            equal(
                "opponent_moves",
                path + ".moves",
                sorted(fact["moves"]),
                sorted(mon["moves"]),
            )
            if mon["active"]:
                equal(
                    "opponent_boosts", path + ".boosts", fact["boosts"], mon["boosts"]
                )
            equal(
                "opponent_types",
                path + ".battle_types",
                fact["base_types"],
                mon["battle_types"],
            )
            types = (
                [fact["tera"]]
                if fact.get("tera") and fact["tera"] != "STELLAR"
                else fact["base_types"]
            )
            equal(
                "opponent_types",
                path + ".effective_types",
                types,
                mon["effective_types"],
            )
        return dict(checks=dict(checks), unknown=dict(unknown), issues=issues)


def run(root, output):
    output.mkdir(parents=True, exist_ok=False)
    totals = Counter()
    counts = Counter()
    unknown = Counter()
    issues = []
    vocabulary = Counter()
    for path in sorted(
        (root / "experiments/ex042-cloud/battles").glob("*/events.jsonl")
    ):
        facts = PublicFacts()
        rows = []
        cutoff = None
        for line in path.open():
            if '"event_type":"protocol_in"' in line:
                e = json.loads(line)
                facts.feed(e["protocol"])
            elif '"event_type":"decision_start"' in line:
                e = json.loads(line)
                cutoff = e["event_seq"]
            elif '"event_type":"input_snapshot"' in line:
                e = json.loads(line)
                value = e["original_input"]
                if value["identity"]["input_version"] != "calculator-input-v2":
                    totals["lead_snapshots_excluded"] += 1
                    continue
                result = facts.check(value)
                counts.update(result["checks"])
                unknown.update(result["unknown"])
                row = dict(
                    bundle=str(path.parent),
                    snapshot_event_seq=e["event_seq"],
                    cutoff=cutoff,
                    **result,
                )
                rows.append(row)
                totals["battle_snapshots"] += 1
                if result["issues"]:
                    issues.append(row)
        vocabulary.update(facts.kinds)
        totals["actors"] += 1
        (output / (path.parent.name + ".json")).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
        )
    result = dict(
        totals=dict(totals),
        checks=dict(counts),
        unknown=dict(unknown),
        vocabulary=dict(vocabulary),
        issues=issues,
        independent_of_B_reducer=True,
        limitations=[
            "Public facts only; not a full Gen9 damage oracle.",
            "Opponent private settings never loaded.",
        ],
    )
    (output / "index.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({**result, "issues": len(issues)}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("/workspace/.pokechamp-data"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    run(args.root, args.output)
