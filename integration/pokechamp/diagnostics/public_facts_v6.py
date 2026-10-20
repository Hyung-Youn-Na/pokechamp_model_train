"""Same-cutoff public facts for EX-086/087; never an incremental payload cache.

The protocol owns disclosure and lifetime. The official snapshot owns roster
identity/current battle effects, but its inferred item/ability/move memories do
not establish disclosure. Raw rows and corrections stay in the separate audit.
"""
from __future__ import annotations

import copy
import json
import re

from .damage_sets import digest, token
from ..improved_io.protocol import ident, protocol_rows
from ..improved_io.state import set_forms

VERSION = "jev-public-facts-v6"
UNKNOWN = "unknown"
IDENT = re.compile(r"p[12][a-z]?: .+")
SWAPS = {"skillswap", "wanderingspirit"}
STOLEN = {"thief", "covet", "magician", "pickpocket", "bestow"}
# SIM-PROTOCOL.md assigns a type to each argument. In particular, the SIDE
# in -sidestart/-sideend uses the same `p2: name` spelling as a Pokemon, but
# names a trainer. Text/control/unknown rows cannot establish public facts.
POKEMON_ROWS = frozenset({
    'switch', 'drag', 'replace', 'detailschange', 'move', 'cant', 'faint', 'swap',
    '-damage', '-heal', '-sethp', '-status', '-curestatus', '-cureteam',
    '-boost', '-unboost', '-setboost', '-swapboost', '-copyboost', '-invertboost',
    '-clearboost', '-clearpositiveboost', '-clearnegativeboost',
    '-fail', '-block', '-miss', '-notarget', '-immune', '-resisted', '-supereffective', '-crit',
    '-item', '-enditem', '-ability', '-endability', '-transform', '-formechange',
    '-mega', '-primal', '-burst', '-zpower', '-terastallize',
    '-start', '-end', '-singleturn', '-singlemove', '-activate', '-prepare',
    '-mustrecharge', '-hitcount', '-waiting', '-combine', '-anim',
})
FIELD_ROWS = frozenset({
    '-sidestart', '-sideend', '-swapsideconditions', '-weather',
    '-fieldstart', '-fieldend', '-fieldactivate', '-clearallboost',
})


def _empty(key):
    return dict(ident=key, entered=False, active=False, species=None, form_species=None, hp=UNKNOWN,
                status=UNKNOWN, fainted=False, moves=[], original_moves=[],
                temporary_replacements={}, persistent_replacements={},
                transformed=False, transformed_moves=[], transform_target=None,
                item=UNKNOWN, initial_items=[], item_changed=False,
                ability=UNKNOWN, baseAbility=UNKNOWN, initial_abilities=[],
                native_by_species={}, base_ability_changed=False,
                ability_temporary=False, ability_changed=False, item_suppressed=False,
                explicit_suppression=False, suppressed=False, gas_ended=False,
                unsupported=[], evidence=[])


def reconstruct(official, prefix, *, actor, dex):
    """Rebuild every known individual from this complete, actor-bound prefix.

    A prefix may finish inside a frame. Its physical row count, last request and
    turn must agree with the official snapshot; unresolved split streams and
    non-unique identities are errors rather than heuristic identity joins.
    """
    request = official.get("request") or {}
    if actor not in ("p1", "p2") or request.get("side", {}).get("id") != actor:
        raise ValueError("foreign actor in v6 public facts")
    if official.get("gen") != 9 or official.get("game_type") != "singles":
        raise ValueError("v6 public facts require Gen9 singles")
    if not prefix or any(e.get("line_offset", 0) for e in prefix):
        raise ValueError("incomplete v6 public prefix")
    lines = [line for e in prefix for line in e["protocol"].splitlines()]
    if official.get("consumed") != len(lines):
        raise ValueError("v6 observation cutoff mismatch")
    if "|init|battle" not in lines:
        raise ValueError("v6 requires the complete battle prefix")
    parsed = list(protocol_rows(prefix))
    requests = [json.loads("|".join(p[2:])) for p, _, _ in parsed
                if p[1] == "request" and len(p) > 2 and p[2]]
    if not requests or requests[-1] != request:
        raise ValueError("v6 stale request or mismatched cutoff")
    if any(r.get("side", {}).get("id", actor) != actor for r in requests):
        raise ValueError("foreign private request in v6 prefix")
    if any(p[1] == "split" for p, _, _ in parsed):
        raise ValueError("unresolved split in v6 public prefix")
    turns = [turn for _, turn, _ in parsed if turn is not None]
    if request.get("teamPreview"):
        if turns or not any(line.startswith("|teampreview") for line in lines) or official["turn"] != 0:
            raise ValueError("unproven v6 preview boundary")
    elif "|start" not in lines or not turns or turns[-1] != official["turn"]:
        raise ValueError("incomplete or future v6 public prefix")

    pokemon, occupants = {}, {}
    magic_room = False

    def row(key):
        if not key or not IDENT.fullmatch(key):
            raise ValueError("ambiguous public Pokemon identity")
        return pokemon.setdefault(ident(key), _empty(ident(key)))

    def evidence(mon, field, value, ref, protocol, reason):
        mon["evidence"].append(dict(field=field, value=copy.deepcopy(value),
                                    ref=copy.deepcopy(ref), protocol=protocol, reason=reason))

    def add(mon, field, value, ref, protocol, reason):
        value = token(value)
        if value and value not in mon[field]:
            mon[field].append(value)
            evidence(mon, field, value, ref, protocol, reason)

    def reveal_ability(mon, value, ref, protocol, *, change=False):
        value = token(value) or UNKNOWN
        if value == UNKNOWN:
            return
        if not mon["ability_temporary"] and not mon["transformed"] and not change:
            if mon["baseAbility"] not in (UNKNOWN, value):
                # A publicly announced form change may alter the native ability.
                # The unresolved transition is kept unknown until disclosure.
                if not mon.pop("form_ability_pending", False):
                    raise ValueError("conflicting public base ability identity")
            mon["baseAbility"] = value
            mon['native_by_species'][mon['form_species']] = value
            if not mon["ability_changed"]:
                add(mon, "initial_abilities", value, ref, protocol, "native_ability_disclosed")
        if change:
            mon["ability_temporary"] = True
            mon["ability_changed"] = True
        mon["ability"] = value
        mon["gas_ended"] = False
        evidence(mon, "ability", value, ref, protocol,
                 "public_ability_change" if change else "public_ability_identity")

    def reveal_item(mon, value, ref, protocol, *, acquisition=False):
        value = token(value) or None
        if acquisition:
            mon["item_changed"] = True
        if not mon["item_changed"]:
            add(mon, "initial_items", value or "", ref, protocol, "original_item_disclosed")
        # A consumed Berry's heal/status row follows its enditem. Only an
        # explicit acquisition can revive a publicly absent holding.
        if acquisition or mon["item"] == UNKNOWN or mon["item"] == value:
            mon["item"] = value
            evidence(mon, "item", value, ref, protocol,
                     "public_item_acquisition" if acquisition else "public_item_identity")

    def reset(mon, ref, protocol):
        mon["active"] = False
        mon["temporary_replacements"] = {}
        mon["transformed"] = False
        mon["transformed_moves"] = []
        mon["transform_target"] = None
        mon["ability_temporary"] = False
        mon["ability"] = mon["baseAbility"]
        mon["explicit_suppression"] = False
        mon['item_suppressed'] = False
        mon["gas_ended"] = False
        evidence(mon, "switch_reset", True, ref, protocol,
                 "temporary_moves_ability_suppression_and_effects_expire")

    def current_moves(mon):
        if mon["transformed"]:
            return mon["transformed_moves"][:]
        replacements = dict(mon["persistent_replacements"], **mon["temporary_replacements"])
        return list(dict.fromkeys(replacements.get(m, m) for m in mon["original_moves"]))

    def disclose_move(mon, value, ref, protocol):
        value = token(value)
        if value in ("", "struggle", "recharge"):
            return
        if mon["transformed"]:
            add(mon, "transformed_moves", value, ref, protocol, "temporary_transform_move")
        elif value not in current_moves(mon):
            add(mon, "original_moves", value, ref, protocol, "public_owned_move")

    def health(mon, condition, ref, protocol):
        match = re.fullmatch(r"(\d+)/(\d+)(?: (\w+))?", condition)
        if condition.startswith("0 fnt"):
            old = mon["hp"]
            maximum = old["maximum"] if isinstance(old, dict) else 100
            value, status = dict(current=0, maximum=maximum, precision="rounded_public_fraction"), "fnt"
        elif match and 0 <= int(match[1]) <= int(match[2]) and int(match[2]) > 0:
            value = dict(current=int(match[1]), maximum=int(match[2]), precision="rounded_public_fraction")
            status = match[3] or ""
        else:
            raise ValueError("unresolved public HP condition")
        mon.update(hp=value, status="" if status == "fnt" else status,
                   fainted=status == "fnt")
        evidence(mon, "hp", value, ref, protocol, "public_hp_at_this_row_no_hidden_healing")

    for p, turn, ref in parsed:
        kind = p[1]
        if kind not in POKEMON_ROWS | FIELD_ROWS:
            continue
        protocol = "|".join(p)
        target = (ident(p[2]) if kind in POKEMON_ROWS and len(p) > 2
                  and IDENT.fullmatch(p[2]) else None)
        of = [ident(x[5:]) for x in p if x.startswith("[of] ") and IDENT.fullmatch(x[5:])]
        if len(set(of)) > 1:
            raise ValueError("ambiguous public event owner")
        other = of[0] if of else None
        sources = [x[7:] for x in p if x.startswith("[from] ")]
        source = token(sources[0].split(": ", 1)[-1]) if sources else ""
        effect = token(p[3].split(": ", 1)[-1]) if len(p) > 3 else ""
        if kind in ("request", "sentchoice"):
            continue  # Private self data is not public move/ability evidence.
        if kind in ("-fieldstart", "-fieldend") and len(p) > 2 and token(p[2]) == "movemagicroom":
            magic_room = kind == "-fieldstart"
        if kind == "replace":
            raise ValueError("ambiguous public identity replacement (Illusion)")
        if target and kind in ("switch", "drag"):
            mon = row(target)
            species = token(p[3].split(",")[0])
            if mon["species"] and not (set_forms(species) & set_forms(mon["species"])):
                raise ValueError("one public identifier names different individuals")
            slot = p[2].split(":", 1)[0]
            if slot in occupants:
                reset(row(occupants[slot]), ref, protocol)
            reset(mon, ref, protocol)
            occupants[slot] = target
            if mon['form_species'] not in (None, species):
                mon['baseAbility'] = mon['native_by_species'].get(species, UNKNOWN)
                mon['ability'] = mon['baseAbility']
            mon['form_species'] = species
            mon['base_ability_changed'] = mon['species'] not in (None, species)
            mon.update(entered=True, active=True, species=mon['species'] or species)
            health(mon, p[4], ref, protocol)
        elif target and kind == 'detailschange':
            mon = row(target)
            species = token(p[3].split(',')[0])
            mon["form_ability_pending"] = True
            mon['form_species'] = species
            mon['baseAbility'] = mon['native_by_species'].get(species, UNKNOWN)
            mon['ability'] = mon['baseAbility']
            mon['ability_changed'] = True
            mon['base_ability_changed'] = species != mon['species']
            # The observer fills a species ability default here. Only a public
            # announcement (or a previously disclosed same-form native ability)
            # can establish the new identity; its original set stays separate.
            evidence(mon, 'ability', mon['ability'], ref, protocol, 'public_form_change_invalidates_inferred_default')
        elif target and kind in ("-damage", "-heal", "-sethp", "faint"):
            mon = row(target)
            health(mon, "0 fnt" if kind == "faint" else p[3], ref, protocol)
            if kind == "-sethp" and len(p) > 5 and IDENT.fullmatch(p[4]):
                health(row(p[4]), p[5], ref, protocol)
            if kind == "faint":
                # Gen9 Battle.faintMessages clears volatiles, moves and ability
                # before the fainted individual becomes an inactive reserve.
                reset(mon, ref, protocol)
                mon["gas_ended"] = True
        if not target:
            # Field/weather ability origins still disclose their [of] owner.
            if other:
                for source_text in sources:
                    if source_text.startswith("ability: "):
                        if other not in pokemon or not pokemon[other]['entered']:
                            raise ValueError('public ability source lacks an established individual')
                        reveal_ability(pokemon[other], source_text[9:], ref, protocol)
            continue
        mon = row(target)
        if not mon["entered"] and kind not in ("-item", "-ability"):
            raise ValueError("public event lacks an established individual")
        if kind == "move" and len(p) > 3 and not sources:
            disclose_move(mon, p[3], ref, protocol)
        if kind in ("-start", "-activate") and effect in ("mimic", "sketch") and len(p) > 4:
            disclose_move(mon, effect, ref, protocol)
            name = "temporary_replacements" if effect == "mimic" else "persistent_replacements"
            mon[name][effect] = token(p[4])
            evidence(mon, name, mon[name], ref, protocol, "mimic_resets_sketch_persists")
        if kind == "-transform":
            donor = row(p[3])
            if not donor["entered"] or donor is mon:
                raise ValueError("ambiguous Transform target")
            mon.update(transformed=True, transform_target=donor["ident"],
                       transformed_moves=current_moves(donor))
            mon["ability"] = donor["ability"]
            mon["ability_temporary"] = True
            evidence(mon, "transform", donor["ident"], ref, protocol,
                     "copy_only_public_target_facts_no_private_moves_or_stats")
        if kind == "-activate" and effect == "forewarn" and len(p) > 4:
            donor = row(other) if other else None
            if donor is None:
                matches = [m for m in pokemon.values() if m["active"] and m["ident"][:2] != target[:2]]
                if len(matches) != 1:
                    raise ValueError("ambiguous Forewarn target")
                donor = matches[0]
            disclose_move(donor, p[4], ref, protocol)
        if kind == "-start" and effect in ("disable", "encore") and len(p) > 4 and not p[4].startswith("["):
            disclose_move(mon, p[4], ref, protocol)

        if kind == "-item":
            acquisition = bool(source and source != "frisk")
            reveal_item(mon, p[3], ref, protocol, acquisition=acquisition)
            if source in STOLEN and other:
                donor = row(other)
                reveal_item(donor, p[3], ref, protocol)
                donor.update(item=None, item_changed=True)
                evidence(donor, "item", None, ref, protocol, "public_transfer_removes_donor_item")
        elif kind == "-enditem":
            reveal_item(mon, p[3], ref, protocol)
            mon.update(item=None, item_changed=True)
            evidence(mon, "item", None, ref, protocol, "public_item_consumption_or_removal")

        if kind == "-activate" and effect in SWAPS:
            if not other or len(p) < 6 or not p[4] or not p[5]:
                raise ValueError("unresolved public ability swap owners")
            donor = row(other)
            # Server emits source, move, targetAbility, sourceAbility, [of] target.
            reveal_ability(mon, p[5], ref, protocol)
            reveal_ability(donor, p[4], ref, protocol)
            reveal_ability(mon, p[4], ref, protocol, change=True)
            reveal_ability(donor, p[5], ref, protocol, change=True)
        elif kind == "-ability":
            if source in ('trace', 'receiver', 'powerofalchemy'):
                reveal_ability(mon, source, ref, protocol)
                if not other:
                    raise ValueError("copying ability lacks a public donor")
                reveal_ability(row(other), p[3], ref, protocol)
                reveal_ability(mon, p[3], ref, protocol, change=True)
            else:
                change = bool(source and "[fail]" not in p)
                if source in ("roleplay", "receiver", "powerofalchemy") and other:
                    reveal_ability(row(other), p[3], ref, protocol)
                # Newer protocol can carry the replaced identity in arg 4.
                if len(p) > 4 and p[4] and not p[4].startswith("[") and p[4] != "boost":
                    reveal_ability(mon, p[4], ref, protocol)
                reveal_ability(mon, p[3], ref, protocol, change=change)
        elif kind == "-endability":
            if len(p) > 3 and p[3] and not p[3].startswith("["):
                reveal_ability(mon, p[3], ref, protocol)
            if sources and any(s.startswith("move: ") for s in sources):
                mon.update(ability=UNKNOWN, ability_temporary=True, ability_changed=True)
                evidence(mon, "ability", UNKNOWN, ref, protocol, "ability_change_pending_public_identity")
            else:
                mon["explicit_suppression"] = True
                evidence(mon, "suppressed", True, ref, protocol, "public_ability_suppression")
        elif kind == "-activate" and effect in ("mummy", "lingeringaroma"):
            reveal_ability(mon, effect, ref, protocol)
            if other and len(p) > 4 and not p[4].startswith("["):
                donor = row(other)
                reveal_ability(donor, p[4], ref, protocol)
                reveal_ability(donor, effect, ref, protocol, change=True)
        elif kind in ("-activate", "-start", "-end", "-immune", "-block", "cant") and len(p) > 3:
            if p[3].startswith("ability: "):
                reveal_ability(mon, p[3][9:], ref, protocol)
            elif p[3].startswith("item: "):
                reveal_item(mon, p[3][6:], ref, protocol)
        if kind in ("-start", "-end") and effect == "gastroacid":
            mon["explicit_suppression"] = kind == "-start"
        if kind in ('-start', '-end') and effect == 'embargo':
            mon['item_suppressed'] = kind == '-start'
        if kind == "-end" and effect == "neutralizinggas":
            mon["gas_ended"] = True
        if kind == "-status":
            mon["status"] = p[3]
        elif kind in ("-curestatus", "-cureteam"):
            if kind == "-cureteam":
                for member in pokemon.values():
                    if member["ident"][:2] == target[:2]:
                        member["status"] = ""
            else:
                mon["status"] = ""

        # Most [from]/[of] fields identify the causal holder. Ability-change
        # rows and item acquisition abilities use special ownership above.
        for source_text in sources:
            if source_text.startswith("ability: ") and kind not in ("-ability", "-transform"):
                holder = mon if kind == "-item" and source in {"pickup", "harvest", "magician", "pickpocket"} else row(other or target)
                reveal_ability(holder, source_text[9:], ref, protocol)
            elif source_text.startswith("item: ") and kind != "-enditem":
                reveal_item(row(other or target), source_text[6:], ref, protocol)
        if kind == "-transform" and source:
            # Imposter belongs to the transforming Pokemon, not the target.
            if source == "imposter":
                mon["baseAbility"] = "imposter"
                mon['native_by_species'][mon['form_species']] = 'imposter'
                add(mon, "initial_abilities", "imposter", ref, protocol, "transforming_ability_disclosed")

    official_mons = [m for s in official["sides"] for m in s["pokemon"] if m.get("ident")]
    keys = [m["ident"] for m in official_mons]
    if len(keys) != len(set(keys)) or any(ident(k) != k for k in keys):
        raise ValueError("ambiguous official Pokemon identities")
    for mon in official_mons:
        fact = pokemon.get(mon["ident"])
        if not fact or not fact["entered"]:
            if mon["ident"].startswith(actor + ":"):
                continue
            raise ValueError("official identity lacks public entry evidence")
        if bool(mon["active"]) != fact["active"]:
            raise ValueError("official/public active identity mismatch")
    for key, mon in pokemon.items():
        if mon["entered"] and key not in keys:
            raise ValueError("public individual missing from official roster")

    gas = [m for m in pokemon.values() if m["active"] and not m["fainted"]
           and m["ability"] == "neutralizinggas" and not m["gas_ended"]
           and not m["explicit_suppression"] and not m["transformed"]]
    own = {m["ident"]: m for m in request["side"]["pokemon"]}
    for mon in pokemon.values():
        ability, item = mon["ability"], mon["item"]
        if mon["ident"] in own:
            # Only suppression calculation may use the actor's current request.
            # It never discloses that private identity to the opponent facts.
            ability = token(own[mon["ident"]].get("ability", "")) or UNKNOWN
            item = token(own[mon["ident"]].get("item", "")) or None
        flags = dex.get("BattleAbilities", {}).get(ability, {}).get("flags", {})
        suppressed = mon["explicit_suppression"]
        if mon["active"] and gas and ability != "neutralizinggas" and not suppressed:
            item_suppressed = magic_room or mon['item_suppressed']
            if flags.get("cantsuppress") or (item == "abilityshield" and not item_suppressed):
                suppressed = False
            elif ability == UNKNOWN or (item == UNKNOWN and not item_suppressed):
                suppressed = UNKNOWN
            else:
                suppressed = True
        if mon["active"] and mon["transformed"] and flags.get("notransform"):
            suppressed = True
        mon["suppressed"] = suppressed if mon["active"] else False
        mon["moves"] = current_moves(mon)
        if mon["transformed"]:
            mon["unsupported"].append("transformed_stats_and_moves")
        if mon["suppressed"] == UNKNOWN:
            mon["unsupported"].append("public_ability_suppression_unresolved")
        if mon["ability_temporary"] and mon["ability"] == UNKNOWN:
            mon["unsupported"].append("changed_current_ability_unknown")
        if mon.get('form_ability_pending') and mon['ability'] == UNKNOWN:
            mon['unsupported'].append('public_form_ability_unknown')
        if mon["item_changed"] and mon["item"] == UNKNOWN:
            mon["unsupported"].append("changed_current_item_unknown")
    return dict(version=VERSION, actor=actor,
                cutoff=dict(event_seq=prefix[-1]["event_seq"],
                            line_index=len(prefix[-1]["protocol"].splitlines()) - 1,
                            consumed=len(lines), turn=official["turn"], request_id=request.get("rqid")),
                official_sha256=digest(official), prefix_sha256=digest(prefix), pokemon=pokemon)


def history(facts, pokemon_ident):
    """Original set evidence and current replacements for the unchanged filter."""
    mon = facts["pokemon"][pokemon_ident]
    return dict(initial_items=copy.deepcopy(mon["initial_items"]),
                initial_abilities=copy.deepcopy(mon["initial_abilities"]),
                original_moves=copy.deepcopy(mon["original_moves"]),
                replacements=dict(mon["persistent_replacements"], **mon["temporary_replacements"]),
                item_changed=mon["item_changed"],
                ability_changed=mon["ability_temporary"] or mon['base_ability_changed'],
                unsupported=copy.deepcopy(mon["unsupported"]), evidence=copy.deepcopy(mon["evidence"]))


def apply(payload, facts, dex):
    """Correct only opponent public fields; leave owned details/candidates intact."""
    result = copy.deepcopy(payload)
    supplements = []
    for mon in result["state"]["opponent_team"]:
        fact = facts["pokemon"].get(mon["ident"], _empty(mon["ident"]))
        changes = dict(item=fact["item"], ability=fact["ability"], baseAbility=fact["baseAbility"],
                       hp=copy.deepcopy(fact["hp"]), status=fact["status"])
        if fact["suppressed"] is True:
            changes["ability"] = "(suppressed)"
        changes["moves"] = []
        for key in fact["moves"]:
            entry = dex["BattleMovedex"].get(key)
            if not entry:
                raise ValueError("public move missing from pinned Dex: " + key)
            changes["moves"].append(dict(id=key, **{out: entry.get(source, "unknown") for out, source in
                (("type", "type"), ("category", "category"), ("power", "basePower"),
                 ("accuracy", "accuracy"), ("priority", "priority"))}))
        if not mon["active"]:
            changes.update(boosts={}, volatiles={}, turnstatuses={}, movestatuses={}, status_data={})
        for key, value in changes.items():
            if mon.get(key) != value:
                supplements.append(dict(ident=mon["ident"], field=key,
                    observed=copy.deepcopy(mon.get(key, UNKNOWN)), public_value=copy.deepcopy(value),
                    reason="same_cutoff_public_disclosure_and_lifetime"))
            mon[key] = value
    return result, supplements
