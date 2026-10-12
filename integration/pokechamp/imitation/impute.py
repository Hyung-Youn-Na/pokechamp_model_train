"""Deterministic, corpus-only restoration of the player's original sets.

This module does not infer an opponent's hidden information for model input. Full
replay evidence is only used to constrain the *own* original set for each POV.
"""
from __future__ import annotations

from collections import defaultdict
import copy
import hashlib
import json
import re

SEED = 20261001

# Exact battleOnly links from the pinned Showdown Dex. Never collapse all forms
# by baseSpecies: masks, Keldeo-Resolute, Transform and Illusion are not aliases.
BATTLE_ONLY_ORIGINAL_SPECIES = {
    "ogerpontealtera": "ogerpon",
    "ogerponwellspringtera": "ogerponwellspring",
    "ogerponhearthflametera": "ogerponhearthflame",
    "ogerponcornerstonetera": "ogerponcornerstone",
    "mimikyubusted": "mimikyu",
}
FORME_CHANGED_ABILITIES = frozenset(BATTLE_ONLY_ORIGINAL_SPECIES) - {"mimikyubusted"}


def ident(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def species_ident(value):
    value = ident(value)
    # Current Showdown emits Greninja in public details for the internal
    # Battle Bond set forme; this is the single confirmed source alias.
    return "greninja" if value == "greninjabond" else value


def switch_original_species(value):
    """Map only known public battle-only forms to their exact original form."""
    value = ident(value)
    return BATTLE_ONLY_ORIGINAL_SPECIES.get(value, value)


def lines_of(raw):
    if isinstance(raw, dict):
        raw = raw["log"]
    return raw.splitlines() if isinstance(raw, str) else list(raw)


def extract_teams(raw):
    """Preview order is the stable original slot order, never nickname order."""
    teams = {"p1": [], "p2": []}
    for line in lines_of(raw):
        parts = line.split("|")
        if len(parts) >= 4 and parts[1] == "poke" and parts[2] in teams:
            species = parts[3].split(",")[0].strip()
            teams[parts[2]].append(species)
    if any(len(v) != 6 or len({ident(s) for s in v}) != 6 for v in teams.values()):
        raise ValueError("six distinct preview slots are required")
    return teams


def revealed_original_sets(raw):
    """Track provenance through called moves, changing items and abilities.

    Receiving an item from Trick does not make it an original item. Evidence for
    the donor is recorded only while that donor still holds its original item.
    Unsupported changes fail closed; they do not silently constrain a wrong set.
    """
    teams = extract_teams(raw)
    result = {side: [dict(species=s, moves=[], item=None, ability=None, teraType=None,
                          gender=None, level=100,
                          evidence=[]) for s in roster] for side, roster in teams.items()}
    preview_slots = {"p1": 0, "p2": 0}
    for line in lines_of(raw):
        parts = line.split("|")
        if len(parts) >= 4 and parts[1] == "poke" and parts[2] in result:
            side = parts[2]
            row = result[side][preview_slots[side]]
            for detail in parts[3].split(",")[1:]:
                detail = detail.strip()
                if detail in {"M", "F"}:
                    row["gender"] = detail
                elif re.fullmatch(r"L\d+", detail):
                    row["level"] = int(detail[1:])
            preview_slots[side] += 1
    nick = {}
    active = {}
    item_original = {(s, i): True for s in teams for i in range(6)}
    ability_original = dict(item_original)
    pending_trade = {}
    unsupported = set()
    stay_moves = defaultdict(set)
    ignored_items = set()
    magic_room = False

    def locate(token):
        # The species in a switch is authoritative; subsequent logs use nickname.
        token = token.removeprefix("[of] ")
        return nick.get(token) or active.get(token[:2])

    def add(key, field, value, lineno):
        if key is None:
            return
        side, slot = key
        row = result[side][slot]
        if field == "moves":
            if ident(value) not in {ident(x) for x in row[field]}:
                row[field].append(value)
        elif row[field] is None:
            row[field] = value
        elif ident(row[field]) != ident(value):
            unsupported.add((side, f"conflicting_original_{field}"))
        row["evidence"].append(dict(line=lineno, field=field, value=value))

    called = {"assist", "copycat", "mefirst", "metronome", "mirrormove", "naturepower",
              "snatch", "magiccoat", "magicbounce", "dancer"}
    for lineno, line in enumerate(lines_of(raw), 1):
        parts = [p.strip() for p in line.split("|")[1:]]
        if not parts:
            continue
        event, *args = parts
        if event in {"switch", "drag"} and len(args) >= 2:
            side, species = args[0][:2], ident(args[1].split(",")[0])
            original_species = switch_original_species(species)
            candidates = [i for i, s in enumerate(teams.get(side, [])) if ident(s) == original_species]
            if len(candidates) != 1:
                unsupported.add((side, "unresolved_switch_species"))
                continue
            key = (side, candidates[0])
            nick[args[0]] = key
            active[side] = key
            # Ogerpon's Embody Aspect belongs to the public Tera form, including
            # later switch-ins. Mimikyu-Busted retains its original Disguise.
            ability_original[key] = species not in FORME_CHANGED_ABILITIES
            stay_moves[key].clear()
            ignored_items.discard(key)
        elif event in {"detailschange", "-formechange"} and len(args) >= 2:
            key = locate(args[0])
            species = ident(args[1].split(",")[0])
            if key and species in FORME_CHANGED_ABILITIES:
                ability_original[key] = False
        elif event in {"replace", "-transform"}:
            for side in teams:
                unsupported.add((side, "unsupported_identity_change"))
        elif event == "move" and len(args) >= 2:
            key = locate(args[0])
            sources = [ident(a.split(":", 1)[-1].replace("[from] ", ""))
                       for a in args[3:] if a.startswith("[from]")]
            if any(x in called for x in sources):
                continue
            if ident(args[1]) in {"struggle", "recharge"}:
                continue
            add(key, "moves", args[1], lineno)
            if key and not sources and item_original[key] and key not in ignored_items and not magic_room:
                stay_moves[key].add(ident(args[1]))
                if len(stay_moves[key]) > 1:
                    result[key[0]][key[1]]["multiple_original_item_moves"] = True
        elif event == "-activate" and len(args) > 1 and ident(args[1]) in {"movetrick", "moveswitcheroo"}:
            key = locate(args[0])
            other = next((locate(x) for x in args[2:] if x.startswith("[of] ")), None)
            if key and other:
                pending_trade[key] = (other, item_original[other])
                pending_trade[other] = (key, item_original[key])
                item_original[key] = item_original[other] = False
            else:
                unsupported.add((args[0][:2], "unresolved_item_exchange"))
        elif event in {"-item", "-enditem"} and len(args) > 1:
            key = locate(args[0])
            if key is None:
                continue
            source = " ".join(args[2:]).lower()
            if "trick" in source or "switcheroo" in source:
                donor = pending_trade.get(key)
                if donor and donor[1]:
                    add(donor[0], "item", args[1], lineno)
                if not donor:
                    unsupported.add((key[0], "unresolved_item_exchange"))
                item_original[key] = False
            elif any(x in source for x in ("thief", "covet", "bestow", "pickpocket", "magician", "symbiosis")):
                for side in teams:
                    unsupported.add((side, "unsupported_item_transfer"))
            else:
                if item_original[key]:
                    add(key, "item", args[1], lineno)
                if event == "-enditem":
                    item_original[key] = False
        elif event == "-ability" and len(args) > 1:
            key = locate(args[0])
            if key is None:
                continue
            if any(a == "[from] ability: Trace" for a in args[2:]):
                if ability_original[key]:
                    add(key, "ability", "Trace", lineno)
                holder = next((locate(a) for a in args[2:] if a.startswith("[of] ")), None)
                if holder and ability_original[holder]:
                    add(holder, "ability", args[1], lineno)
                ability_original[key] = False
            elif any("[from]" in a for a in args[2:]):
                ability_original[key] = False
            elif ability_original[key]:
                add(key, "ability", args[1], lineno)
        elif event == "-endability" and args:
            key = locate(args[0])
            if key:
                ability_original[key] = False
        elif event == "-terastallize" and len(args) > 1:
            add(locate(args[0]), "teraType", args[1], lineno)
        elif event in {"-fieldstart", "-fieldend"} and args and ident(args[0]) == "movemagicroom":
            magic_room = event == "-fieldstart"
        elif event in {"-start", "-end"} and len(args) > 1 and ident(args[1]) in {"embargo", "moveembargo"}:
            key = locate(args[0])
            if key:
                if event == "-start":
                    ignored_items.add(key)
                else:
                    ignored_items.discard(key)
        if args:
            # Effect source holders are explicit [of] values. Without [of], the
            # subject owns the ability (e.g. Intimidate, Protosynthesis).
            ability = next((a[len("[from] ability: "):] for a in args if a.startswith("[from] ability: ")), None)
            if not ability and event in {"-activate", "-start"} and len(args) > 1 and args[1].startswith("ability: "):
                ability = args[1][len("ability: "):]
            if ability and not (event == "-ability" and any(a == "[from] ability: Trace" for a in args)):
                holder = next((locate(a) for a in args if a.startswith("[of] ")), locate(args[0]))
                if holder and ability_original.get(holder):
                    add(holder, "ability", ability, lineno)
    return result, sorted(unsupported)


class SetCorpus:
    def __init__(self, entries):
        self.by_species = defaultdict(list)
        for entry in entries:
            pokemon = entry.get("set", entry)
            row = dict(set=copy.deepcopy(pokemon), count=int(entry.get("count", 1)),
                       sources=entry.get("sources", []))
            if row["count"] <= 0:
                raise ValueError("set frequencies must be positive")
            row["id"] = hashlib.sha256(json.dumps(pokemon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.by_species[species_ident(pokemon["species"])].append(row)
        for rows in self.by_species.values():
            rows.sort(key=lambda r: r["id"])

    def impute(self, revealed, replay_id, side):
        chosen, audits = [], []
        for slot, observed in enumerate(revealed, 1):
            possible = []
            for row in self.by_species[species_ident(observed["species"])]:
                candidate = row["set"]
                if not {ident(m) for m in observed["moves"]}.issubset({ident(m) for m in candidate["moves"]}):
                    continue
                if any(observed[field] is not None and ident(observed[field]) != ident(candidate.get(field, ""))
                       for field in ("item", "ability", "teraType")):
                    continue
                if observed.get("gender") and candidate.get("gender") and observed["gender"] != candidate["gender"]:
                    continue
                if int(candidate.get("level", 100)) != observed.get("level", 100):
                    continue
                if (observed.get("multiple_original_item_moves") and
                        ident(candidate.get("item", "")) in {"choiceband", "choicespecs", "choicescarf"} and
                        ident(candidate.get("ability", "")) != "klutz"):
                    continue
                possible.append(row)
            if not possible:
                return None, dict(reason="no_matching_legal_set", perspective=side, slot=slot,
                                  species=observed["species"], revealed=observed)
            total = sum(row["count"] for row in possible)
            key = f"EX071:{SEED}:{replay_id}:{side}:{slot}"
            draw = int.from_bytes(hashlib.sha256(key.encode()).digest(), "big") % total
            for row in possible:
                draw -= row["count"]
                if draw < 0:
                    selected = row
                    break
            chosen.append(copy.deepcopy(selected["set"]))
            if observed.get("gender"):
                chosen[-1]["gender"] = observed["gender"]
            audits.append(dict(slot=slot, set_id=selected["id"], sources=selected["sources"],
                               count=selected["count"], compatible_entries=len(possible),
                               compatible_frequency=total, observed=observed,
                               inferred_fields=[f for f in ("item", "ability", "teraType") if observed[f] is None],
                               inferred_moves=sorted(set(map(ident, selected["set"]["moves"])) - set(map(ident, observed["moves"]))),
                               inferred_other_fields=["nature", "evs", "ivs"]))
        return chosen, audits
