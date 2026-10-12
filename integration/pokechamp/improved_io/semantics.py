"""Read-only scene rubric audit; future evidence is never returned to the actor."""

from __future__ import annotations

import json
from pathlib import Path

from .calculations import own_spec

# Event assertions below are tied to the authored rubric, not optimal-action labels.
AFTER = {
    "IO-C01": (17, ["|Draco Meteor|", "|faint|"], []),
    "IO-C02": (31, ["|Earthquake|", "|-immune|p2a:"], []),
    "IO-C03": (
        43,
        ["|Ruination|", "|51/100", "|-enditem|p2a: Tinkaton|Air Balloon"],
        ["|-terastallize|"],
    ),
    "IO-C04": (66, ["tox", "[from] ability: Poison Heal"], []),
    "IO-C05": (156, ["|Sucker Punch|", "|-supereffective|p2a: Slowking", "|135/393"], []),
    "IO-C06": (182, ["|Close Combat|", "|265/415"], ["|Ice Fang|"]),
    "IO-C07": (102, ["|Earth Power|", "|faint|p2a: Slayboi Carti"], ["|Bitter Blade|", "|-heal|"]),
    "IO-C08": (114, ["|Earth Power|", "|faint|p2a: Dubya"], ["|Hydro Steam|"]),
    "IO-C09": (164, ["|faint|p2a: Die w A Smile"], ["|Healing Wish|", "|-heal|"]),
    "IO-C10": (71, ["|Thunder Wave|", "|-immune|p2a: Landorus", "|Earth Power|"], []),
    "IO-C11": (155, ["|Draco Meteor|", "|6/100 par"], []),
    "IO-C12": (109, ["|Giga Drain|", "|faint|p1a: Landorus"], ["|U-turn|"]),
    "IO-C13": (135, ["|Pyro Ball|", "|-miss|"], []),
    "IO-C14": (84, ["|Pyro Ball|", "|168/318", "|Eject Button"], ["|Psychic Noise|"]),
    "IO-C15": (96, ["|Pyro Ball|", "|-resisted|", "|faint|p2a: Dubya"], ["|Hydro Steam|"]),
}


def audit(case, value, *, recent=None):
    """Return individual assertions, including negative evidence and its time boundary."""
    spec = case["case"]
    checks = []

    def check(name, valid, evidence):
        checks.append(dict(name=name, passed=bool(valid), evidence=evidence))

    obs = value["current_observation"]
    active = next(p for p in obs["self_team"] if p["active"])
    opponent = next(p for p in obs["opponent_confirmed"] if p["active"])
    entries = value["calculation_bundle"]["entries"]
    before = "\n".join(e["protocol"] for e in case["protocol"])
    requests = [
        json.loads(line[9:])
        for line in before.splitlines()
        if line.startswith("|request|") and line[9:]
    ]
    raw_team = requests[-1]["side"]["pokemon"]
    check(
        "self_request_all_moves_hp_stats",
        all(
            all(p[k] == raw[k] for k in ("ident", "condition", "moves", "stats"))
            for p, raw in zip(obs["self_team"], raw_team, strict=True)
        ),
        {"request_id": value["identity"]["request_id"]},
    )
    check(
        "predecision_only",
        value["recent_events"] == (case["protocol"] if recent is None else recent)
        and all(e["event_seq"] < case["cutoff"] for e in value["recent_events"]),
        case["cutoff"],
    )
    check(
        "conditional_damage_not_execution",
        "does not establish KO" in value["calculation_bundle"]["uncertainty"]
        and all(
            e.get("ko_chance_given_hit") is None and e.get("survival_given_hit") is None
            for e in entries
        )
        and obs["order_assessment"]["relation"] == "unknown",
        "Hit-conditioned ranges; no selected action is promoted to an executed action.",
    )
    check(
        "public_prior_boundary",
        all(
            h["confirmed_moves"] == opponent["moves"]
            and h["source"] == "fixed_gen9_ou_prior"
            and h["joint_probability"] is None
            for h in value["opponent_hypotheses"]
        ),
        {"confirmed_moves": opponent["moves"], "ability": opponent["ability"]},
    )
    cid = spec["id"]

    def outgoing(move):
        return [e for e in entries if e["scenario_id"].startswith(f"out-move-{move}-")]

    if cid == "IO-C01":
        check(
            "draco_calculated_not_posthoc_label",
            bool(outgoing("dracometeor")),
            outgoing("dracometeor")[:1],
        )
    elif cid in ("IO-C02", "IO-C03"):
        check(
            "balloon_current_not_future_pop",
            opponent["item"] == "airballoon"
            and opponent["tera_type"] is None
            and "|-enditem|p2a: Tinkaton|Air Balloon" not in before,
            {"item": opponent["item"], "tera_type": opponent["tera_type"]},
        )
        if cid == "IO-C02":
            rows = outgoing("earthquake")
            check(
                "earthquake_immune",
                rows and all(e["damage_range_hp"] == [0, 0] for e in rows),
                rows[:1],
            )
        else:
            rows = outgoing("ruination")
            check(
                "ruination_positive_conditional",
                rows and all(e["damage_range_hp"][0] > 0 for e in rows),
                rows[:1],
            )
    elif cid == "IO-C04":
        check(
            "poison_heal_and_revealed_knockoff",
            opponent["status"] == "TOX"
            and opponent["ability"] == "poisonheal"
            and "knockoff" in opponent["moves"]
            and "[from] ability: Poison Heal" in before,
            opponent,
        )
    elif cid == "IO-C05":
        rows = [
            e
            for e in entries
            if e["scenario_id"].startswith("in-slowkinggalar-")
            and e.get("move", {}).get("type") == "Dark"
        ]
        check(
            "dark_physical_conditional_on_future_attack",
            rows
            and all(
                e["move"]["type"] == "Dark" and e["move"]["category"] == "Physical" for e in rows
            )
            and value["request"]["force_switch_cause"] == "faint"
            and "suckerpunch" not in opponent["moves"],
            {
                "computed_dark_moves": rows[:1],
                "sucker_punch": "not yet revealed; outside selected prior moves; survival unknown",
            },
        )
    elif cid == "IO-C06":
        hydrapple = next(p for p in obs["self_team"] if p["species"] == "hydrapple")
        check(
            "hydrapple_grounded_and_coverage_unconfirmed",
            hydrapple["ability"] == "regenerator"
            and "icefang" not in opponent["moves"]
            and "closecombat" not in opponent["moves"],
            {"self": hydrapple, "confirmed_moves": opponent["moves"]},
        )
    elif cid == "IO-C08":
        check(
            "spa_activation_not_speed",
            "PROTOSYNTHESISSPA" in active["effects"]
            and active["stats"]["spe"] == 317
            and own_spec(active)["options"]["boostedStat"] == "spa",
            {"effects": active["effects"], "speed": active["stats"]["spe"]},
        )
    elif cid == "IO-C09":
        venusaur = next(p for p in obs["self_team"] if p["species"] == "venusaur")
        check("healing_wish_not_applied", venusaur["condition"] == "82/301", venusaur["condition"])
    elif cid == "IO-C10":
        rows = outgoing("thunderwave")
        check(
            "thunder_wave_effect_not_legality",
            rows and all(e["effect_assessment"].startswith("immune:") for e in rows),
            rows[:1],
        )
    elif cid == "IO-C11":
        check(
            "current_spa_minus_two",
            active["boosts"]["spa"] == -2 and own_spec(active)["options"]["boosts"]["spa"] == -2,
            outgoing("dracometeor")[:1],
        )
    elif cid == "IO-C13":
        check(
            "rounded_hp_not_ko_guarantee",
            opponent["hp"] == 55 and bool(outgoing("pyroball")),
            outgoing("pyroball")[:1],
        )
    elif cid == "IO-C15":
        rows = [e for e in entries if e["scenario_id"].startswith("in-walkingwake-pyroball-")]
        check(
            "exact_low_hp_and_incoming_range",
            active["condition"] == "29/339"
            and own_spec(active)["options"]["curHP"] == 29
            and bool(rows),
            rows[:1],
        )
    # This reader is deliberately separate from normalize/compute and never writes to value.
    events = {
        e["event_seq"]: e
        for e in (
            json.loads(line)
            for line in (Path(case["bundle"]) / "events.jsonl").read_text().splitlines()
        )
    }
    seq, required, forbidden = AFTER[cid]
    text = events[seq]["protocol"]
    check(
        "historical_effects_expected_and_must_not",
        seq > case["cutoff"]
        and all(s in text for s in required)
        and not any(s in text for s in forbidden),
        {
            "event_seq": seq,
            "required": required,
            "forbidden": forbidden,
            "scope": "postdecision review only; not model input",
        },
    )
    if cid == "IO-C05":
        check(
            "switch_precedes_next_turn_attack",
            "|switch|p2a: Slowking" in events[150]["protocol"]
            and "|Sucker Punch|" not in events[150]["protocol"],
            [150, 156],
        )
    if cid == "IO-C12":
        check(
            "replacement_after_faint",
            "|switch|p1a: Cinderace" in events[115]["protocol"],
            [109, 115],
        )
    if cid == "IO-C14":
        check(
            "eject_before_replacement_no_psychic_noise",
            "|switch|p2a: Dubya" in events[90]["protocol"]
            and "|Psychic Noise|" not in events[90]["protocol"],
            [84, 90],
        )
    return dict(
        case=cid,
        expected=spec["expected"],
        must_not=spec["must_not"],
        checks=checks,
        passed=all(c["passed"] for c in checks),
        scope="input semantics and historical interpretation, not model output or optimality",
    )
