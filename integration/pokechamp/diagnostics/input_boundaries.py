"""EX-030 independent raw-fact and worker-option audits."""

from __future__ import annotations

import json
import re
from pathlib import Path

STATS = ("atk", "def", "spa", "spd", "spe", "accuracy", "evasion", "hp")


def key(value):
    return re.sub(r"^(p[12])[a-z]:", r"\1:", value)


def norm(value):
    return re.sub("[^a-z0-9]", "", value.lower())


def audit_raw(item, value):
    """Reference facts are interpreted directly from original wire rows.

    This checker deliberately does not import normalization/protocol helpers or
    consult opponent team data. Unhandled state-changing messages are errors.
    """
    actor = value["identity"]["actor_id"]
    ranks = {}
    health = {}
    statuses = {}
    occupants = {}
    abilities = {}
    items = {}
    moves = {}

    def stages(who):
        return ranks.setdefault(who, dict.fromkeys(STATS, 0))

    consumed = {}
    entries = {}
    weather = {}
    sides = {"p1": {}, "p2": {}}
    turn = None
    faint_counts = {"p1": 0, "p2": 0}
    latest = None
    for event in item["prefix"]:
        assert event["event_seq"] < item["cutoff"]
        for number, line in enumerate(event["protocol"].splitlines(), 1):
            f = line.split("|")
            if len(f) < 2:
                continue
            kind = f[1]
            who = key(f[2]) if len(f) > 2 and re.match(r"p[12][a-z]?: ", f[2]) else None
            if kind == "start":
                turn = 0
            elif kind == "turn":
                turn = int(f[2])
            elif kind == "request" and f[2]:
                latest = json.loads("|".join(f[2:]))
                if "side" in latest:
                    assert latest["side"]["id"] == actor
            elif kind in ("switch", "drag"):
                old = occupants.get(f[2].split(":")[0])
                if old:
                    ranks[old] = dict.fromkeys(STATS, 0)
                occupants[f[2].split(":")[0]] = who
                ranks[who] = dict.fromkeys(STATS, 0)
                token = f[4].split()
                health[who] = list(map(int, token[0].split("/")))
                statuses[who] = token[1].upper() if len(token) > 1 else None
                entries.setdefault(who, []).append(
                    {"event": event["event_seq"], "line": number}
                )
            elif kind in ("-boost", "-unboost"):
                amount = int(f[4]) * (1 if kind == "-boost" else -1)
                stages(who)[f[3]] = max(-6, min(6, stages(who)[f[3]] + amount))
            elif kind in (
                "-setboost",
                "-swapboost",
                "-copyboost",
                "-clearboost",
                "-clearallboost",
                "-invertboost",
            ):
                raise ValueError(
                    "additional independent boost reference needed: " + line
                )
            elif kind in ("-damage", "-heal", "-sethp"):
                hp = f[3].split()[0]
                if "/" in hp:
                    health[who] = list(map(int, hp.split("/")))
                elif hp == "0":
                    health[who] = [0, health.get(who, [None, None])[1]]
                if (
                    kind == "-heal"
                    and len(f) == 5
                    and f[4].startswith("[from] ability: ")
                ):
                    abilities[who] = norm(f[4][16:])
            elif kind == "faint":
                health[who] = [0, health.get(who, [None, None])[1]]
                statuses[who] = "FNT"
                faint_counts[who[:2]] += 1
            elif kind == "-status":
                statuses[who] = f[3].upper()
                if len(f) == 5 and f[4] in (
                    "[from] item: Toxic Orb",
                    "[from] item: Flame Orb",
                ):
                    items[who] = norm(f[4][13:])
            elif kind == "-curestatus":
                statuses[who] = None
            elif kind == "-item":
                items[who] = norm(f[3])
            elif kind == "-enditem":
                items[who] = None
            elif (
                kind == "move"
                and not any(s.startswith("[from]") for s in f[4:])
                and norm(f[3]) not in ("struggle", "recharge")
            ):
                moves.setdefault(who, set()).add(norm(f[3]))
            elif kind == "-ability":
                abilities[who] = norm(f[3])
                if "boost" in f[4:]:
                    consumed.setdefault(who, {}).setdefault(norm(f[3]), []).append(
                        {"event": event["event_seq"], "line": number}
                    )
            elif kind == "-endability":
                abilities[who] = ""
            elif kind == "-activate" and f[3] in (
                "ability: Protosynthesis",
                "ability: Quark Drive",
                "ability: Supreme Overlord",
            ):
                abilities[who] = norm(f[3][9:])
            elif kind == "-weather":
                weather = {} if f[2] == "none" else {norm(f[2]).upper(): turn}
                source = next(
                    (s[16:] for s in f[3:] if s.startswith("[from] ability: ")), None
                )
                holder = next(
                    (key(s[5:]) for s in f[3:] if s.startswith("[of] p")), None
                )
                if source and holder:
                    abilities[holder] = norm(source)
            elif kind in ("-sidestart", "-sideend"):
                side = f[2][:2]
                name = f[3].removeprefix("move: ").upper().replace(" ", "_")
                if kind == "-sideend":
                    sides[side].pop(name, None)
                elif name in ("SPIKES", "TOXIC_SPIKES"):
                    sides[side][name] = sides[side].get(name, 0) + 1
                else:
                    sides[side][name] = turn
    assert latest == item["request"]
    own = value["current_observation"]["self_team"]
    obs = value["current_observation"]
    assert len(own) == len(latest["side"]["pokemon"])
    assertions = 0
    for raw, actual in zip(latest["side"]["pokemon"], own, strict=True):
        for name, data in raw.items():
            assert actual[name] == data, (raw["ident"], name)
            assertions += 1
        assert actual["boosts"] == stages(raw["ident"]), (raw["ident"], "ranks")
        assertions += 1
    for actual in obs["opponent_confirmed"]:
        who = actual["ident"]
        assert actual["boosts"] == stages(who), (who, "opponent ranks")
        assertions += 1
        if who in health:
            assert actual["hp"] == health[who][0], (who, "public HP")
            assert actual["max_hp"] == health[who][1], (who, "public max HP")
            assertions += 2
        if who in abilities:
            assert actual["ability"] == abilities[who], (
                who,
                "ability",
                actual["ability"],
                abilities[who],
            )
            assertions += 1
        if who in items:
            assert actual["item"] == items[who], (
                who,
                "item",
                actual["item"],
                items[who],
            )
            assertions += 1
        assert moves.get(who, set()) <= set(actual["moves"]), (who, "confirmed moves")
        assertions += 1
    for actual in [*own, *obs["opponent_confirmed"]]:
        if "ability_history" not in actual:
            continue
        history = actual["ability_history"]
        who = actual["ident"]
        assert history["activations"] == consumed.get(who, {}), (who, "consumption")
        assert history["entries"] == entries.get(who, []), (who, "entry refs")
        assert history["team_faints"] == faint_counts[who[:2]], (who, "team faints")
        assertions += 3
    assert obs["weather"] == weather, ("weather", obs["weather"], weather)
    assert obs["self_side_conditions"] == sides[actor], (
        "self side",
        obs["self_side_conditions"],
        sides[actor],
    )
    other = "p2" if actor == "p1" else "p1"
    assert obs["opponent_side_conditions"] == sides[other], (
        "opponent side",
        obs["opponent_side_conditions"],
        sides[other],
    )
    assertions += 3
    return {"assertions": assertions, "last_raw_turn": turn, "public_only": True}


def audit_worker(value, request, response):
    """Expected options come directly from explicit state and guesses."""
    obs = value["current_observation"]
    own = {p["species"]: p for p in obs["self_team"]}
    opponent = next(
        (p for p in obs["opponent_confirmed"] if p["active"] and not p["fainted"]), None
    )
    assert request["identity"] == response["identity"] == value["identity"]
    assert (
        request["semantics_version"]
        == response["semantics_version"]
        == "calculator-input-v2"
    )
    assert [s["scenario_id"] for s in request["scenarios"]] == [
        e["scenario_id"] for e in response["entries"]
    ]
    assert (
        response["entries"] == value["calculation_bundle"]["entries"]
        or not request["scenarios"]
    )
    assertions = 4
    for s in request["scenarios"]:
        incoming = s["scenario_id"].startswith("in-")
        for role, source in [
            (
                "attackerSide",
                "opponent_side_conditions" if incoming else "self_side_conditions",
            ),
            (
                "defenderSide",
                "self_side_conditions" if incoming else "opponent_side_conditions",
            ),
        ]:
            expected_side = {}
            for name, option in [
                ("STEALTH_ROCK", "isSR"),
                ("SPIKES", "spikes"),
                ("REFLECT", "isReflect"),
                ("LIGHT_SCREEN", "isLightScreen"),
                ("AURORA_VEIL", "isAuroraVeil"),
                ("TAILWIND", "isTailwind"),
                ("TOXIC_SPIKES", "toxicSpikes"),
                ("STICKY_WEB", "isStickyWeb"),
            ]:
                if name in obs[source]:
                    expected_side[option] = (
                        obs[source][name]
                        if name in ("SPIKES", "TOXIC_SPIKES")
                        else True
                    )
            assert s["field"][role] == expected_side, (s["scenario_id"], role)
            assertions += 1
        me = s["defender" if incoming else "attacker"]
        them = s["attacker" if incoming else "defender"]
        p = own[me.get("tera_projection", {}).get("from_species", me["name"])]
        o = me["options"]
        source = p["original_set"]
        for field in ("nature", "evs", "ivs", "level"):
            assert o[field] == source[field], (s["scenario_id"], field)
            assertions += 1
        assert o["curHP"] == int(p["condition"].split("/")[0])
        assertions += 1
        assert o["item"] == p["item"]
        assertions += 1
        condition = p["condition"].split()
        assert o["status"] == (condition[1] if len(condition) > 1 else "")
        assertions += 1
        assert me["battle_types"] == [t.title() for t in p["battle_types"]]
        assertions += 1
        assert o["boosts"] == {k: v for k, v in p["boosts"].items() if k != "hp"}
        assertions += 1
        expected = (
            me["tera_projection"]["ability"]
            if "tera_projection" in me
            else ""
            if p["ability_history"]["suppressed"]
            else p["ability"]
        )
        assert o["ability"] == expected
        assertions += 1
        assert me["projected_entry"] == (not p["active"])
        assertions += 1
        if norm(p["ability"]) in ("dauntlessshield", "intrepidsword"):
            assert me["entry_effects_observed"] == (
                p["active"]
                or bool(p["ability_history"]["activations"].get(norm(p["ability"])))
            )
            assertions += 1
        match = re.search(r"-h(\d+)-hp(\d+)$", s["scenario_id"])
        assert match
        guess = value["opponent_hypotheses"][int(match[1])]
        g = them["options"]
        assert g["curHP"] == int(match[2])
        assert g["nature"] == guess["spread"]["nature"]
        assert g["evs"] == dict(
            zip(
                ("hp", "atk", "def", "spa", "spd", "spe"),
                guess["spread"]["stats"],
                strict=True,
            )
        )
        assert g["ability"] == guess["ability"]
        assert g["item"] == guess["item"]
        assert g["ivs"] == guess["ivs"]
        assert g["boosts"] == {k: v for k, v in opponent["boosts"].items() if k != "hp"}
        assert g["status"] == (opponent["status"] or "").lower()
        assert them["battle_types"] == [t.title() for t in opponent["battle_types"]]
        for field in ("ability", "item"):
            if opponent[field] not in ("unknown_item", None) or (
                field == "item" and opponent[field] is None
            ):
                # None is public absence; unrevealed ability stays a prior assumption.
                if field == "item" or opponent[field]:
                    assert norm(g[field] or "") == norm(opponent[field] or "")
        assert them["entry_effects_observed"] is True
        assertions += 8
        if incoming:
            assert s["move"] in guess["moves"]
            assertions += 1
    return {
        "assertions": assertions,
        "scenario_count": len(request["scenarios"]),
        "worker_to_llm_entries_exact": True,
    }


def run(directory, output):
    from .input_audit import inputs

    rows = []
    for item in inputs():
        identity = f"{item['experiment']}-{item['slot']}-{item['event']['event_seq']}"
        artifact = json.loads((directory / (identity + ".json")).read_text())
        row = {"key": identity}
        try:
            row["raw"] = audit_raw(item, artifact["input"])
            row["worker"] = audit_worker(
                artifact["input"],
                artifact["worker_request"],
                artifact["worker_response"],
            )
            row["passed"] = True
        except (AssertionError, ValueError, KeyError, TypeError) as error:
            row.update(passed=False, error=repr(error))
        rows.append(row)
    result = dict(inputs=len(rows), passed=all(r["passed"] for r in rows), rows=rows)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        {
            "inputs": len(rows),
            "passed": result["passed"],
            "failures": [r for r in rows if not r["passed"]][:10],
        }
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.directory, args.output)
