"""Frozen, set-coherent Smogon candidates conditioned only on a public prefix.

This is an offline diagnostic prior, never the production marginal prior.
Descriptions are not parsed into additional sets or cross-slot constraints.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
from pathlib import Path

from ..improved_io.protocol import ident, protocol_rows
from ..improved_io.state import STATS, set_forms

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = (ROOT / "exports/pokemon-role-data/pokemon_role_db_gen9ou_2026-08_1695"
            / "data/raw/smogon")


def token(value):
    return "".join(c for c in str(value).lower() if c.isalnum())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


class SetSnapshot:
    def __init__(self, directory=SNAPSHOT):
        self.directory = Path(directory)
        self.paths = {token(p.stem): p for p in self.directory.glob("*.json")
                      if not p.name.endswith(".provenance.json")}
        self.sources = {}

    def load(self, species):
        matches = set_forms(token(species)) & self.paths.keys()
        if not matches:
            return [], {"reason": "no_recommended_species", "species": species}
        if len(matches) != 1:
            raise ValueError("ambiguous Smogon battle-form ancestry")
        path = self.paths[matches.pop()]
        raw = path.read_bytes()
        provenance_path = path.with_suffix(".provenance.json")
        provenance = json.loads(provenance_path.read_text())
        checksum = hashlib.sha256(raw).hexdigest()
        if (checksum != provenance["sha256"] or provenance["format"] != "gen9ou"
                or not provenance["retrieved_at"].startswith("2026-09-18T")):
            raise ValueError("Smogon snapshot identity/date mismatch")
        source = dict(path=str(path.relative_to(ROOT)), sha256=checksum,
                      provenance_path=str(provenance_path.relative_to(ROOT)),
                      provenance_sha256=hashlib.sha256(provenance_path.read_bytes()).hexdigest(),
                      url=provenance["url"], retrieved_at=provenance["retrieved_at"])
        self.sources[source["path"]] = source
        sets = []
        for strategy in json.loads(raw):
            if strategy["format"] != "OU":
                raise ValueError("foreign format in frozen OU snapshot")
            if strategy.get("outdated"):
                continue
            for moveset in strategy.get("movesets", []):
                if token(moveset["pokemon"]) not in set_forms(token(species)):
                    raise ValueError("foreign species in Smogon recommendation")
                sets.append(moveset)
        return sets, source


def public_history(prefix, pokemon_ident):
    """Keep original-set constraints distinct from changed current holdings.

    An enditem reveals the item before consumption/removal. An item received
    through Trick/Recycle/etc. is not evidence of the submitted item. Mimic
    resets on switch; Sketch persists. Called/reflected moves are not set slots.
    Unknown transformation semantics fail closed in the caller.
    """
    result = dict(initial_items=[], initial_abilities=[], original_moves=[],
                  replacements={}, item_changed=False, ability_changed=False,
                  unsupported=[], evidence=[])
    occupants, temporary = {}, set()

    def add(field, value, ref):
        name = token(value)
        if name and name not in result[field]:
            result[field].append(name)
            result["evidence"].append(dict(field=field, value=name, ref=ref))

    for p, _, ref in protocol_rows(prefix):
        kind = p[1]
        target = ident(p[2]) if len(p) > 2 and ": " in p[2] and p[2].startswith(("p1", "p2")) else None
        holder = next((ident(x[5:]) for x in p if x.startswith("[of] p")), target)
        if kind in ("switch", "drag", "replace") and target:
            slot = p[2].split(":", 1)[0]
            if occupants.get(slot) == pokemon_ident:
                for original in temporary:
                    result["replacements"].pop(original, None)
                temporary.clear()
            occupants[slot] = target
        if target == pokemon_ident and kind == "-transform":
            result["unsupported"].append("transformed_stats_and_moves")
        if target == pokemon_ident and kind in ("-start", "-activate") and len(p) > 4:
            original = token(p[3].removeprefix("move: "))
            if original in ("mimic", "sketch"):
                add("original_moves", original, ref)
                result["replacements"][original] = token(p[4])
                if original == "mimic":
                    temporary.add(original)
        if target == pokemon_ident and kind == "move" and not any(x.startswith("[from]") for x in p[4:]):
            move = token(p[3])
            if move not in result["replacements"].values() and move not in ("struggle", "recharge"):
                add("original_moves", move, ref)
        if target == pokemon_ident and kind == "-item":
            # Frisk is a reveal. All other attributed acquisitions may change
            # the original item, even if no preceding enditem was emitted.
            acquired = any(x.startswith("[from]") and x != "[from] ability: Frisk" for x in p[4:])
            if acquired:
                result["item_changed"] = True
            if not result["item_changed"]:
                add("initial_items", p[3], ref)
        if target == pokemon_ident and kind == "-enditem":
            if not result["item_changed"]:
                add("initial_items", p[3], ref)
            result["item_changed"] = True
        if target == pokemon_ident and kind == "-ability":
            if any(x.startswith("[from] move:") or x.startswith("[from] ability:") for x in p[4:]):
                result["ability_changed"] = True
            if not result["ability_changed"]:
                add("initial_abilities", p[3], ref)
        if holder == pokemon_ident:
            for field, changed, tag in (("initial_items", "item_changed", "item"),
                                        ("initial_abilities", "ability_changed", "ability")):
                if not result[changed]:
                    for x in p:
                        if x.startswith("[from] " + tag + ": "):
                            add(field, x.split(": ", 1)[1], ref)
            if kind in ("-activate", "-start", "-end", "-immune") and len(p) > 3:
                if p[3].startswith("ability: ") and not result["ability_changed"]:
                    add("initial_abilities", p[3].split(": ", 1)[1], ref)
    return result


def expand_sets(sets):
    """Cartesian choices are scoped to one named set; EV and IV vectors stay whole."""
    for set_index, moveset in enumerate(sets):
        if not moveset.get("abilities") or not moveset.get("natures") or not moveset.get("moveslots"):
            raise ValueError("incomplete recommended set")
        slots = [[token(m["move"]) for m in slot] for slot in moveset["moveslots"]]
        if len(slots) != 4 or any(not s for s in slots):
            raise ValueError("invalid recommended move slots")
        choices = itertools.product(
            moveset["natures"], moveset.get("evconfigs") or [{}],
            moveset.get("ivconfigs") or [{}], moveset.get("items") or [""],
            moveset["abilities"], itertools.product(*slots))
        for index, (nature, evs, ivs, item, ability, moves) in enumerate(choices):
            if len(set(moves)) != len(moves):
                continue  # A slash option can occur in two slots, not twice in a legal set.
            row = dict(candidate_id=f"set{set_index}-choice{index}", set_index=set_index,
                       set_name=moveset["name"], species=moveset["pokemon"], nature=nature,
                       evs={s: evs.get(s, 0) for s in STATS}, ivs={s: ivs.get(s, 31) for s in STATS},
                       item=item, ability=ability, moves=list(moves),
                       tera_types=list(moveset.get("teratypes", [])),
                       levels=list(moveset.get("levels") or [100]))
            if (any(type(v) is not int or not 0 <= v <= 252 for v in row["evs"].values())
                    or sum(row["evs"].values()) > 510
                    or any(type(v) is not int or not 0 <= v <= 31 for v in row["ivs"].values())):
                raise ValueError("invalid recommended spread")
            yield row


def candidates(sets, mon, history, *, public_facts=False):
    accepted, excluded = [], []
    original_moves = set(history["original_moves"])
    if not history["replacements"] and not public_facts:
        original_moves.update(mon["moves"])
    for candidate in expand_sets(sets):
        reasons = []
        if not original_moves <= set(candidate["moves"]):
            reasons.append("observed_original_moves")
        if any(token(candidate["item"]) != item for item in history["initial_items"]):
            reasons.append("observed_original_item")
        if (not history["item_changed"] and mon["item"] != "unknown_item"
                and token(candidate["item"]) != token(mon["item"] or "")):
            reasons.append("observed_current_item")
        if any(token(candidate["ability"]) != ability for ability in history["initial_abilities"]):
            reasons.append("observed_original_ability")
        if (not history["ability_changed"] and mon["ability_known"] and mon["ability"]
                and token(candidate["ability"]) != token(mon["ability"])):
            reasons.append("observed_current_ability")
        if candidate["levels"] and mon["level"] not in candidate["levels"]:
            reasons.append("observed_level")
        if mon["tera_type"] and token(mon["tera_type"]) not in {token(t) for t in candidate["tera_types"]}:
            reasons.append("observed_tera_type")
        if reasons:
            excluded.append(dict(candidate_id=candidate["candidate_id"], reasons=reasons))
            continue
        candidate = copy.deepcopy(candidate)
        candidate["original_moves"] = candidate["moves"][:]
        candidate["moves"] = [history["replacements"].get(m, m) for m in candidate["moves"]]
        candidate["current_item"] = (candidate["item"] if mon["item"] == "unknown_item" else mon["item"] or "")
        candidate["current_ability"] = mon["ability"] if mon["ability_known"] else candidate["ability"]
        accepted.append(candidate)
    return accepted, excluded
